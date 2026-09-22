"""
Strict Fail-Closed Collection Runner Engine.

Executes genuine live packet captures using resolved Scapy network interfaces.
NEVER generates synthetic packet fallbacks when live capture fails.
Immediately marks sessions as FAILED on adapter errors or zero packets.
"""

from __future__ import annotations

import csv
import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from capture.capture_integrity import validate_real_capture
from capture.capture_validator import CaptureValidator
from capture.interface_resolver import resolve_capture_interface
from capture.metadata_exporter import MetadataExporter
from capture.packet_capture import LiveSniffer, RawPacketMetadata
from capture.session_logger import SessionLogger
from capture.session_manager import CollectionSession, SessionState

logger = logging.getLogger(__name__)


@dataclass
class CaptureResult:
    success: bool
    packet_count: int
    byte_count: int
    packets: List[Dict[str, Any]]
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class CollectionRunner:
    def __init__(
        self,
        interface: Optional[str] = None,
        output_dir: str = "data/raw/metadata",
        manifest_path: str = "data/dataset_manifest.csv",
        version_manifest_path: str = "results/tables/dataset_version_manifest.csv",
    ) -> None:
        self.interface_name = interface
        self.output_dir = output_dir
        self.manifest_path = Path(manifest_path)
        self.version_manifest_path = Path(version_manifest_path)
        self.exporter = MetadataExporter(output_dir=output_dir)
        self.validator = CaptureValidator(min_packets=10, min_bytes=500)
        self.logger = SessionLogger()

    def run_session(
        self,
        session: CollectionSession,
        duration_seconds: int = 30,
        warmup_seconds: int = 2,
    ) -> CollectionSession:
        logger.info("=== Starting Strict Live Collection Session: %s (%s) ===", session.session_id, session.traffic_class)

        # 1. Resolve Interface
        try:
            resolved_iface = resolve_capture_interface(self.interface_name)
            iface_desc = getattr(resolved_iface, "description", str(resolved_iface))
            iface_id = getattr(resolved_iface, "name", str(resolved_iface))
            logger.info("Resolved capture interface: %s (%s)", iface_id, iface_desc)
        except Exception as e:
            logger.error("Failed to resolve network interface '%s': %s", self.interface_name, e)
            session.transition_to(SessionState.FAILED)
            session.error_code = "INTERFACE_RESOLUTION_FAILED"
            session.error_message = str(e)
            self.logger.log_session(session.to_dict())
            return session

        # 2. Warmup
        session.transition_to(SessionState.WARMUP)
        time.sleep(warmup_seconds)

        # 3. Live Capture
        session.transition_to(SessionState.CAPTURING)
        session.start_time = time.time()

        capture_res = self._execute_live_sniff(resolved_iface, duration_seconds)

        session.end_time = time.time()
        session.duration = session.end_time - session.start_time
        session.transition_to(SessionState.FINALIZING)

        # Fail closed if live capture failed
        if not capture_res.success:
            logger.error("Live packet capture failed: [%s] %s", capture_res.error_code, capture_res.error_message)
            session.transition_to(SessionState.FAILED)
            session.error_code = capture_res.error_code
            session.error_message = capture_res.error_message
            self.logger.log_session(session.to_dict())
            return session

        # 4. Export Whitelisted Metadata (Zero-Payload)
        meta_file = self.exporter.export_session_metadata(
            session_id=session.session_id,
            traffic_class=session.traffic_class,
            packet_records=capture_res.packets,
        )
        session.metadata_path = meta_file
        session.sha256 = self.exporter.calculate_file_sha256(meta_file)

        # 5. Validate Capture
        val_res = self.validator.validate_metadata_file(meta_file)
        session.packet_count = val_res.packet_count
        session.byte_count = val_res.byte_count
        session.flow_count = val_res.flow_count

        integrity_report = validate_real_capture(session.to_dict(), min_packets=self.validator.min_packets, min_bytes=self.validator.min_bytes)

        if val_res.is_valid and integrity_report.is_valid:
            session.transition_to(SessionState.VALIDATED)
            self._register_in_manifest(session)
            self._register_in_version_manifest(session)
            logger.info("Session %s successfully VALIDATED and registered as real capture!", session.session_id)
        else:
            session.transition_to(SessionState.FAILED)
            all_errors = val_res.reasons + integrity_report.reasons
            session.error_message = "; ".join(all_errors)
            logger.warning("Session %s validation FAILED: %s", session.session_id, session.error_message)

        # 6. Structured JSONL Log
        self.logger.log_session(session.to_dict())
        return session

    def _execute_live_sniff(self, iface_obj: Any, duration_seconds: int) -> CaptureResult:
        captured_packets: List[Dict[str, Any]] = []
        error_container: List[Exception] = []

        try:
            from scapy.all import sniff

            def _on_pkt(pkt: Any) -> None:
                try:
                    if not pkt.haslayer("IP") and not pkt.haslayer("IPv6"):
                        return
                    is_ipv6 = pkt.haslayer("IPv6")
                    ip_layer = pkt["IPv6"] if is_ipv6 else pkt["IP"]
                    
                    protocol = "OTHER"
                    src_port = 0
                    dst_port = 0
                    tcp_flags = ""

                    if pkt.haslayer("TCP"):
                        protocol = "TCP"
                        src_port = int(pkt["TCP"].sport)
                        dst_port = int(pkt["TCP"].dport)
                        tcp_flags = str(pkt["TCP"].flags)
                    elif pkt.haslayer("UDP"):
                        protocol = "UDP"
                        src_port = int(pkt["UDP"].sport)
                        dst_port = int(pkt["UDP"].dport)

                    captured_packets.append({
                        "timestamp": float(getattr(pkt, "time", time.time())),
                        "length": len(pkt),
                        "ip_version": 6 if is_ipv6 else 4,
                        "protocol": protocol,
                        "source_port": src_port,
                        "destination_port": dst_port,
                        "tcp_flags": tcp_flags,
                        "direction": "forward",
                    })
                except Exception:
                    pass

            def _sniff_worker():
                try:
                    sniff(
                        iface=iface_obj,
                        prn=_on_pkt,
                        timeout=duration_seconds,
                        store=False,
                        filter="ip or ip6",
                    )
                except Exception as ex:
                    error_container.append(ex)

            worker = threading.Thread(target=_sniff_worker, daemon=True)
            worker.start()
            worker.join(timeout=duration_seconds + 3.0)

            if error_container:
                return CaptureResult(
                    success=False,
                    packet_count=0,
                    byte_count=0,
                    packets=[],
                    error_code="ADAPTER_SNIFF_EXCEPTION",
                    error_message=str(error_container[0]),
                )

            total_bytes = sum(p["length"] for p in captured_packets)
            if not captured_packets:
                return CaptureResult(
                    success=False,
                    packet_count=0,
                    byte_count=0,
                    packets=[],
                    error_code="ZERO_PACKETS_CAPTURED",
                    error_message=f"No packets captured on interface '{iface_obj}' during {duration_seconds}s window.",
                )

            return CaptureResult(
                success=True,
                packet_count=len(captured_packets),
                byte_count=total_bytes,
                packets=captured_packets,
            )
        except Exception as e:
            return CaptureResult(
                success=False,
                packet_count=0,
                byte_count=0,
                packets=[],
                error_code="CAPTURE_ENGINE_ERROR",
                error_message=str(e),
            )

    def _register_in_manifest(self, session: CollectionSession) -> None:
        file_id = f"real_{session.session_id}"
        
        # Check uniqueness constraint
        if self.manifest_path.exists():
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    if r.get("session_id") == session.session_id or r.get("file_id") == file_id:
                        raise ValueError(f"Uniqueness constraint violated: session_id '{session.session_id}' already registered in manifest.")

        file_exists = self.manifest_path.exists()
        with open(self.manifest_path, "a", newline="", encoding="utf-8") as f:
            fields = [
                "file_id", "pcap_path", "metadata_path", "raw_source_type", "raw_source_path",
                "traffic_class", "source", "capture_date", "session_id", "environment_id",
                "device_id", "dataset_id", "capture_duration", "packet_count", "byte_count",
                "flow_count", "validation_status", "data_origin", "capture_source", "notes"
            ]
            writer = csv.DictWriter(f, fieldnames=fields)
            if not file_exists or os.path.getsize(self.manifest_path) == 0:
                writer.writeheader()

            norm_meta_path = str(session.metadata_path).replace("\\", "/")
            writer.writerow({
                "file_id": file_id,
                "pcap_path": "",
                "metadata_path": norm_meta_path,
                "raw_source_type": "METADATA_CSV",
                "raw_source_path": norm_meta_path,
                "traffic_class": session.traffic_class,
                "source": "controlled_wifi_capture",
                "capture_date": time.strftime("%Y-%m-%d"),
                "session_id": session.session_id,
                "environment_id": session.environment_id,
                "device_id": session.device_id,
                "dataset_id": session.dataset_id,
                "capture_duration": round(session.duration, 2),
                "packet_count": session.packet_count,
                "byte_count": session.byte_count,
                "flow_count": session.flow_count,
                "validation_status": "PASS",
                "data_origin": "real",
                "capture_source": "REAL_LIVE_CAPTURE",
                "notes": session.notes,
            })

    def _register_in_version_manifest(self, session: CollectionSession) -> None:
        file_exists = self.version_manifest_path.exists()
        self.version_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.version_manifest_path, "a", newline="", encoding="utf-8") as f:
            fields = ["dataset_id", "session_id", "metadata_path", "sha256", "traffic_class", "capture_date", "environment_id", "device_id", "capture_source"]
            writer = csv.DictWriter(f, fieldnames=fields)
            if not file_exists or os.path.getsize(self.version_manifest_path) == 0:
                writer.writeheader()
            writer.writerow({
                "dataset_id": session.dataset_id,
                "session_id": session.session_id,
                "metadata_path": session.metadata_path,
                "sha256": session.sha256,
                "traffic_class": session.traffic_class,
                "capture_date": time.strftime("%Y-%m-%d"),
                "environment_id": session.environment_id,
                "device_id": session.device_id,
                "capture_source": "REAL_LIVE_CAPTURE",
            })
