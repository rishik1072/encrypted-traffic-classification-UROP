"""
Physical Network Traffic Collector for Dataset V3.

Manages the complete physical Npcap capture lifecycle:
- Interface verification and elevation checks.
- Zero-payload packet extraction and transient flow assembly.
- Atomic session persistence under data/research_v3/<session_id>/.
- Automatic post-capture validation and ground-truth annotation.
- Strict refusal to fall back to synthetic or demo modes.
"""

from __future__ import annotations

import logging
import platform
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Set

from research.dataset_v3.annotation import GroundTruthAnnotator
from research.dataset_v3.config import DatasetV3Config
from research.dataset_v3.flow_manager import FlowManager
from research.dataset_v3.manifest import ManifestManager
from research.dataset_v3.metadata_writer import MetadataWriter
from research.dataset_v3.packet_parser import (
    ParseStatus,
    TransientPacketData,
    parse_raw_ip_bytes,
    parse_raw_ip_bytes_detailed,
    parse_scapy_packet,
    parse_scapy_packet_detailed,
)
from research.dataset_v3.schemas import FlowIndexRecord, SessionManifest
from research.dataset_v3.validator import DatasetV3Validator

logger = logging.getLogger("research.dataset_v3.collector")


class PhysicalTrafficCollector:
    """
    Physical network packet metadata collector for Dataset V3.
    """

    def __init__(self, config: DatasetV3Config) -> None:
        self.config = config
        self.session_id = config.session_id
        self.final_dir = config.final_session_dir
        self.staging_dir = config.staging_session_dir
        self.incomplete_dir = config.incomplete_session_dir

        self.lifecycle_state = "COLLECTOR_IDLE"
        self.last_error: Optional[str] = None

        self.flow_manager = FlowManager(
            session_id=self.session_id,
            idle_timeout_seconds=config.flow_idle_timeout_seconds,
            active_timeout_seconds=config.flow_active_timeout_seconds,
            max_packets_per_flow=config.max_packets_per_flow,
        )

        self.metadata_writer = MetadataWriter(
            final_dir=self.final_dir,
            staging_dir=self.staging_dir,
            incomplete_dir=self.incomplete_dir,
            session_id=self.session_id,
        )

        self.annotator = GroundTruthAnnotator(config=self.config)
        self.validator = DatasetV3Validator()
        self.verified_flow_ids: Set[str] = set()
        self.candidate_flow_ids: Set[str] = set()
        self.residual_other_flow_ids: Set[str] = set()

        self._manifest: Optional[SessionManifest] = None
        self._sniffer: Any = None
        self._stop_event = threading.Event()
        self._timer_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        # Telemetry
        self.packets_captured_count = 0
        self.packets_processed_count = 0
        self.parsing_failures_count = 0
        self.processing_failures_count = 0
        self.truncated_headers_count = 0
        self.unsupported_protocols_count = 0
        self.unsupported_fragments_count = 0
        self.queue_drops_count = 0
        self.start_monotonic: Optional[float] = None

    def initialize(self, bypass_prerequisites: bool = False) -> None:
        """
        Validates environment prerequisites, interface existence, and initializes storage.
        Stops and raises an exception if physical capture cannot be guaranteed.
        """
        self.lifecycle_state = "COLLECTOR_INITIALIZING"
        logger.info("Initializing Dataset V3 Physical Collector for session '%s'", self.session_id)

        # 1. Interface validation (strict: explicit interface must be provided)
        if not self.config.interface:
            self.lifecycle_state = "COLLECTOR_FAILED"
            self.last_error = "No physical network interface was specified."
            raise ValueError(
                "Explicit physical network interface must be specified. "
                "Dataset V3 strictly forbids automatic fallback to synthetic or loopback interfaces."
            )

        # 2. System prerequisites
        if not bypass_prerequisites:
            ready, reason = DatasetV3Config.check_system_prerequisites()
            if not ready:
                self.lifecycle_state = "COLLECTOR_FAILED"
                self.last_error = reason
                logger.error("Capture prerequisite failure: %s", reason)
                raise PermissionError(f"Cannot initialize physical capture: {reason}")

        # 3. Create initial manifest and initialize writer
        self._manifest = ManifestManager.create_initial_manifest(self.config)
        self.metadata_writer.initialize_session(self._manifest)

        self.lifecycle_state = "COLLECTOR_READY"

    def start_capture(self, dry_run: bool = False) -> None:
        """
        Starts the physical packet capture.
        If dry_run=True, initializes state without starting physical Npcap sniffer (for testing).
        """
        with self._lock:
            if self.lifecycle_state not in ("COLLECTOR_READY", "COLLECTOR_IDLE"):
                raise RuntimeError(f"Cannot start capture in state: {self.lifecycle_state}")

            if self.lifecycle_state == "COLLECTOR_IDLE":
                self.initialize(bypass_prerequisites=dry_run)

            self.lifecycle_state = "COLLECTOR_STARTING"
            self.start_monotonic = time.monotonic()
            self._stop_event.clear()

            if dry_run:
                self.lifecycle_state = "COLLECTOR_ACTIVE"
                logger.info("Collector started in DRY_RUN mode (testing mode; no live sniffer).")
                return

            # Live Physical Sniffer Execution
            try:
                from scapy.sendrecv import AsyncSniffer

                logger.info(
                    "Starting Scapy AsyncSniffer on interface '%s' (filter='%s', promisc=%s)",
                    self.config.interface,
                    self.config.pcap_filter,
                    self.config.promiscuous,
                )

                sniffer_kwargs = {
                    "iface": self.config.interface,
                    "filter": self.config.pcap_filter,
                    "promisc": self.config.promiscuous,
                    "prn": self._packet_callback,
                    "store": False,
                }
                if self.config.snaplen is not None:
                    sniffer_kwargs["snaplen"] = self.config.snaplen

                self._sniffer = AsyncSniffer(**sniffer_kwargs)
                self._sniffer.start()
                self.lifecycle_state = "COLLECTOR_ACTIVE"

                # Start duration timer thread if positive duration
                if self.config.duration_seconds > 0:
                    self._timer_thread = threading.Thread(
                        target=self._duration_timer_worker,
                        name=f"v3_timer_{self.session_id}",
                        daemon=True,
                    )
                    self._timer_thread.start()

            except Exception as e:
                self.lifecycle_state = "COLLECTOR_FAILED"
                self.last_error = f"Physical capture start failure: {e}"
                logger.error("Failed to start physical packet sniffer: %s", e)
                raise RuntimeError(
                    f"Physical capture failed to start on interface '{self.config.interface}': {e}. "
                    "Dataset V3 refuses to fall back to synthetic capture."
                ) from e

    def _packet_callback(self, raw_packet: Any) -> None:
        """Internal callback invoked for each packet captured on the physical wire."""
        if self._stop_event.is_set():
            return

        self.packets_captured_count += 1
        res = parse_scapy_packet_detailed(raw_packet, user_snaplen=self.config.snaplen)
        if res.status == ParseStatus.VALID_METADATA and res.packet_data is not None:
            self._process_transient_packet(res.packet_data)
        elif res.status == ParseStatus.TRUNCATED_HEADER:
            self.truncated_headers_count += 1
        elif res.status == ParseStatus.FRAGMENT_UNSUPPORTED:
            self.unsupported_fragments_count += 1
        elif res.status == ParseStatus.UNSUPPORTED_PROTOCOL:
            self.unsupported_protocols_count += 1
        else:
            self.parsing_failures_count += 1

    def process_raw_ip_bytes(
        self,
        data: bytes,
        ts: Optional[float] = None,
        wire_len: Optional[int] = None,
        orig_frame_len: Optional[int] = None,
    ) -> None:
        """Public ingestion method for feeding raw IP bytes in test harnesses."""
        res = parse_raw_ip_bytes_detailed(
            data, ts=ts, wire_len=wire_len, orig_frame_len=orig_frame_len
        )
        if res.status == ParseStatus.VALID_METADATA and res.packet_data is not None:
            self.packets_captured_count += 1
            self._process_transient_packet(res.packet_data)
        elif res.status == ParseStatus.TRUNCATED_HEADER:
            self.truncated_headers_count += 1
        elif res.status == ParseStatus.FRAGMENT_UNSUPPORTED:
            self.unsupported_fragments_count += 1
        elif res.status == ParseStatus.UNSUPPORTED_PROTOCOL:
            self.unsupported_protocols_count += 1
        else:
            self.parsing_failures_count += 1

    def register_verified_flow(self, flow_id: str) -> None:
        """Registers a flow ID with explicit attribution evidence (e.g. socket/PID match)."""
        with self._lock:
            self.verified_flow_ids.add(flow_id)

    def register_temporal_flow(self, flow_id: str) -> None:
        """Registers a flow with only temporal overlap during the collection window."""
        with self._lock:
            self.candidate_flow_ids.add(flow_id)

    def register_residual_other_flow(self, flow_id: str) -> None:
        """Registers a flow independently verified to belong to the residual traffic category."""
        with self._lock:
            self.residual_other_flow_ids.add(flow_id)

    def register_primary_flow(self, flow_id: str, has_explicit_evidence: bool = True) -> None:
        """
        Registers a primary flow. If has_explicit_evidence=True, flow receives VERIFIED.
        If has_explicit_evidence=False (temporal overlap only), flow receives AMBIGUOUS (traffic_class=None).
        """
        with self._lock:
            if has_explicit_evidence:
                self.verified_flow_ids.add(flow_id)
            else:
                self.candidate_flow_ids.add(flow_id)

    def set_primary_flows(self, flow_ids: Set[str], has_explicit_evidence: bool = True) -> None:
        """Sets primary flows with specified evidence level."""
        with self._lock:
            if has_explicit_evidence:
                self.verified_flow_ids = set(flow_ids)
            else:
                self.candidate_flow_ids = set(flow_ids)

    def _process_transient_packet(self, transient: TransientPacketData) -> None:
        """Processes transient packet, updates flow manager, and writes zero-payload record."""
        try:
            self.packets_processed_count += 1
            pkt_record, completed_flow = self.flow_manager.process_packet(transient)
            self.metadata_writer.write_packet(pkt_record)

            # Check periodic flow timeouts every 100 packets
            if self.packets_processed_count % 100 == 0:
                now_ts = transient.timestamp
                newly_completed = self.flow_manager.check_timeouts(now_ts)
        except Exception as e:
            self.processing_failures_count += 1
            logger.error("Processing failure for packet in session %s: %s", self.session_id, e)

    def _duration_timer_worker(self) -> None:
        """Monitors session duration and triggers graceful stop upon timeout."""
        duration = self.config.duration_seconds
        while not self._stop_event.is_set():
            elapsed = time.monotonic() - (self.start_monotonic or time.monotonic())
            if elapsed >= duration:
                logger.info("Session duration (%.1f s) reached. Stopping capture...", duration)
                self.stop_capture(status="COMPLETE", notes="Reached configured duration limit.")
                break
            time.sleep(0.5)

    def stop_capture(self, status: str = "COMPLETE", notes: str = "") -> None:
        """
        Gracefully stops packet capture, finalizes all flows, runs validation on staging,
        and either publishes to final destination or quarantines to .incomplete/.
        """
        # Normalize status
        if status == "COMPLETED":
            status = "COMPLETE"

        with self._lock:
            if self.lifecycle_state in ("COLLECTOR_STOPPING", "COLLECTOR_COMPLETED", "COLLECTOR_FAILED"):
                return

            self.lifecycle_state = "COLLECTOR_STOPPING"
            self._stop_event.set()
            logger.info("Stopping Dataset V3 capture session '%s'", self.session_id)

            # 1. Stop live sniffer if active
            kernel_drops = None
            if self._sniffer is not None:
                try:
                    if getattr(self._sniffer, "running", False):
                        self._sniffer.stop()
                    if hasattr(self._sniffer, "stats"):
                        try:
                            s = self._sniffer.stats()
                            if s and len(s) >= 2:
                                kernel_drops = int(s[1])
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning("Error stopping AsyncSniffer: %s", e)
                finally:
                    self._sniffer = None

            # 2. Finalize all active flows
            completed_flows = self.flow_manager.finalize_all()
            self.metadata_writer.write_flow_index(completed_flows)

            # 3. Generate ground-truth labels
            labels = self.annotator.generate_initial_labels(
                completed_flows,
                verified_flow_ids=self.verified_flow_ids if self.verified_flow_ids else None,
                ambiguous_flow_ids=self.candidate_flow_ids if self.candidate_flow_ids else None,
                residual_other_flow_ids=self.residual_other_flow_ids if self.residual_other_flow_ids else None,
            )
            self.metadata_writer.write_labels(labels)

            # 4. Finalize manifest in staging
            if self._manifest is not None:
                verified_cnt = sum(1 for l in labels if l.label_quality == "VERIFIED")
                manifest_quality = "VERIFIED" if verified_cnt > 0 else "AMBIGUOUS"
                ManifestManager.finalize_manifest(
                    manifest=self._manifest,
                    packet_count=self.packets_processed_count,
                    flow_count=len(completed_flows),
                    status=status,
                    label_quality=manifest_quality,
                    notes=notes,
                    kernel_buffer_drops=kernel_drops,
                    queue_drops=self.queue_drops_count,
                    parsing_failures=self.parsing_failures_count,
                    processing_failures=self.processing_failures_count,
                )
                self.metadata_writer.write_manifest(self._manifest)

            # 5. Flush and close packets before validation
            self.metadata_writer.flush_and_close_packets()

            # 6. Run automatic validation on the staging directory
            val_report = self.validator.validate_session(self.staging_dir)
            self.metadata_writer.write_validation_report(val_report)

            # 7. Atomic publication or quarantine
            if val_report.is_valid and status == "COMPLETE":
                published_path = self.metadata_writer.publish_complete_session(self._manifest)
                self.lifecycle_state = "COLLECTOR_COMPLETED"
                logger.info(
                    "Session successfully validated and published to %s: %d packets, %d flows",
                    published_path,
                    self.packets_processed_count,
                    len(completed_flows),
                )
            else:
                fail_reason = "; ".join(val_report.errors) if val_report.errors else f"Status: {status}"
                quarantined_path = self.metadata_writer.quarantine_incomplete_session(
                    self._manifest, failure_reason=fail_reason
                )
                self.lifecycle_state = "COLLECTOR_FAILED" if not val_report.is_valid else "COLLECTOR_INTERRUPTED"
                logger.warning(
                    "Session validation failed or status=%s. Quarantined to %s (Reason: %s)",
                    status,
                    quarantined_path,
                    fail_reason,
                )

            self.metadata_writer.close()
