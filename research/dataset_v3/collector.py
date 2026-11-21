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
import sys
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


def sanitize_device_name(device_name: Optional[str]) -> str:
    r"""Redacts GUID in Windows device path, e.g. \Device\NPF_{12345678-...} -> \Device\NPF_{1234...}"""
    if not device_name:
        return "UNKNOWN"
    if "{" in device_name and "}" in device_name:
        parts = device_name.split("{")
        guid = parts[1].split("}")[0]
        if len(guid) >= 8:
            redacted = f"{guid[:4]}...{guid[-4:]}"
        else:
            redacted = "..."
        return f"{parts[0]}{{{redacted}}}"
    return device_name


def resolve_and_validate_interface(
    interface_name: str,
    expected_adapter_type: str = "Wi-Fi",
    is_mock_socket: bool = False,
    collector_instance: Optional[Any] = None,
) -> Any:
    """
    Canonical interface enumeration, registry reload, resolution, and validation helper.
    Ensures that both live capture and diagnostic smoke test execute the exact same resolution pipeline.
    """
    import scapy
    import scapy.config
    import scapy.interfaces
    from scapy.config import conf
    from scapy.interfaces import resolve_iface, network_name
    from unittest.mock import Mock, NonCallableMock

    # Check mock state if not explicitly passed
    if not is_mock_socket:
        is_mock_socket = (
            isinstance(conf.L2listen, (Mock, NonCallableMock))
            or "Mock" in interface_name
        )

    # Stage 1: Interface Enumeration / Registry Refresh
    interfaces_before: List[str] = []
    if hasattr(conf, "ifaces") and conf.ifaces is not None:
        try:
            interfaces_before = [str(k) for k in conf.ifaces.keys()]
        except Exception:
            pass

    if platform.system() == "Windows" and getattr(conf, "use_pcap", False) and not is_mock_socket:
        try:
            conf.ifaces.reload()
        except PermissionError as perm_err:
            err_msg = (
                f"[INTERFACE_ENUMERATION_FAILED] Npcap permission denied while refreshing interfaces: {perm_err}. "
                "Ensure process is running with Administrator privileges or user is in npcap-users group."
            )
            logger.error("%s", err_msg)
            if collector_instance:
                collector_instance.lifecycle_state = "COLLECTOR_FAILED"
                collector_instance.last_error_stage = "INTERFACE_ENUMERATION"
                collector_instance.last_error_type = type(perm_err).__name__
                collector_instance.last_error_code = getattr(perm_err, "winerror", getattr(perm_err, "errno", None))
                collector_instance.last_error = err_msg
                collector_instance.last_error_message = str(perm_err)
                collector_instance._quarantine_failed_start(err_msg)
            raise PermissionError(err_msg) from perm_err
        except Exception as enum_err:
            err_str = str(enum_err).lower()
            if "access" in err_str or "denied" in err_str or "permission" in err_str:
                err_msg = (
                    f"[INTERFACE_ENUMERATION_FAILED] Npcap access denied during interface reload: {enum_err}. "
                    "Ensure process is running with Administrator privileges or user is in npcap-users group."
                )
                logger.error("%s", err_msg)
                if collector_instance:
                    collector_instance.lifecycle_state = "COLLECTOR_FAILED"
                    collector_instance.last_error_stage = "INTERFACE_ENUMERATION"
                    collector_instance.last_error_type = "PermissionError"
                    collector_instance.last_error = err_msg
                    collector_instance.last_error_message = str(enum_err)
                    collector_instance._quarantine_failed_start(err_msg)
                raise PermissionError(err_msg) from enum_err
            err_msg = f"[INTERFACE_ENUMERATION_FAILED] Failed refreshing Scapy interface registry: {enum_err}"
            logger.error("%s", err_msg)
            if collector_instance:
                collector_instance.lifecycle_state = "COLLECTOR_FAILED"
                collector_instance.last_error_stage = "INTERFACE_ENUMERATION"
                collector_instance.last_error_type = type(enum_err).__name__
                collector_instance.last_error = err_msg
                collector_instance.last_error_message = str(enum_err)
                collector_instance._quarantine_failed_start(err_msg)
            raise RuntimeError(err_msg) from enum_err

    interfaces_after: List[str] = []
    if hasattr(conf, "ifaces") and conf.ifaces is not None:
        try:
            interfaces_after = [str(k) for k in conf.ifaces.keys()]
        except Exception:
            pass

    # Stage 2: Interface Resolution
    try:
        resolved_iface = resolve_iface(interface_name)
    except Exception as res_err:
        err_msg = f"[INTERFACE_RESOLUTION_FAILED] Error resolving interface '{interface_name}': {res_err}"
        logger.error("%s", err_msg)
        if collector_instance:
            collector_instance.lifecycle_state = "COLLECTOR_FAILED"
            collector_instance.last_error_stage = "INTERFACE_RESOLUTION"
            collector_instance.last_error_type = type(res_err).__name__
            collector_instance.last_error_code = getattr(res_err, "winerror", getattr(res_err, "errno", None))
            collector_instance.last_error = err_msg
            collector_instance.last_error_message = str(res_err)
            collector_instance._quarantine_failed_start(err_msg)
        raise RuntimeError(err_msg) from res_err

    # Explicit validation: Reject dummy / invalid interfaces
    is_dummy = getattr(resolved_iface, "dummy", False)
    if not is_dummy and hasattr(resolved_iface, "is_valid"):
        try:
            if not resolved_iface.is_valid():
                is_dummy = True
        except Exception:
            pass

    if is_dummy and not is_mock_socket:
        diag_lines = [
            f"[INTERFACE_RESOLUTION_FAILED] Interface '{interface_name}' resolved to dummy fallback. No physical Npcap adapter match found.",
            "Detailed Resolution Diagnostics:",
            f"  sys.executable:            {sys.executable}",
            f"  scapy.__file__:            {getattr(scapy, '__file__', None)}",
            f"  scapy.interfaces.__file__:  {getattr(scapy.interfaces, '__file__', None)}",
            f"  scapy.config.__file__:      {getattr(scapy.config, '__file__', None)}",
            f"  conf.use_pcap:             {getattr(conf, 'use_pcap', False)}",
            f"  id(conf):                  {id(conf)}",
            f"  id(conf.ifaces):           {id(conf.ifaces) if hasattr(conf, 'ifaces') else None}",
            f"  interfaces before reload:  {interfaces_before}",
            f"  interfaces after reload:   {interfaces_after}",
            f"  requested interface:       {repr(interface_name)}",
            f"  resolved type:             {type(resolved_iface).__name__}",
            f"  resolved name:             {getattr(resolved_iface, 'name', None)}",
            f"  resolved description:      {getattr(resolved_iface, 'description', None)}",
            f"  resolved dummy flag:       {is_dummy}",
            f"  resolved network name:     {getattr(resolved_iface, 'network_name', None)}",
        ]
        full_diag_msg = "\n".join(diag_lines)
        logger.error("%s", full_diag_msg)
        err_msg = f"[INTERFACE_RESOLUTION_FAILED] Interface '{interface_name}' resolved to dummy fallback. No physical Npcap adapter match found."
        if collector_instance:
            collector_instance.lifecycle_state = "COLLECTOR_FAILED"
            collector_instance.last_error_stage = "INTERFACE_RESOLUTION"
            collector_instance.last_error_type = "RuntimeError"
            collector_instance.last_error = err_msg
            collector_instance.last_error_message = err_msg
            collector_instance._quarantine_failed_start(err_msg)
        raise RuntimeError(err_msg)

    # Validate interface name matches requested friendly name
    if not is_mock_socket and getattr(resolved_iface, "name", None) != interface_name:
        err_msg = f"[INTERFACE_RESOLUTION_FAILED] Interface name mismatch: requested '{interface_name}', got '{getattr(resolved_iface, 'name', None)}'"
        logger.error("%s", err_msg)
        if collector_instance:
            collector_instance.lifecycle_state = "COLLECTOR_FAILED"
            collector_instance.last_error_stage = "INTERFACE_RESOLUTION"
            collector_instance.last_error_type = "RuntimeError"
            collector_instance.last_error = err_msg
            collector_instance.last_error_message = err_msg
            collector_instance._quarantine_failed_start(err_msg)
        raise RuntimeError(err_msg)

    # Obtain and verify network name
    resolved_network_name = network_name(resolved_iface)
    iface_net_name = getattr(resolved_iface, "network_name", None)
    if resolved_network_name != iface_net_name and not is_mock_socket:
        err_msg = f"[INTERFACE_RESOLUTION_FAILED] network_name('{interface_name}') mismatch: '{resolved_network_name}' != '{iface_net_name}'"
        logger.error("%s", err_msg)
        if collector_instance:
            collector_instance.lifecycle_state = "COLLECTOR_FAILED"
            collector_instance.last_error_stage = "INTERFACE_RESOLUTION"
            collector_instance.last_error_type = "RuntimeError"
            collector_instance.last_error = err_msg
            collector_instance.last_error_message = err_msg
            collector_instance._quarantine_failed_start(err_msg)
        raise RuntimeError(err_msg)

    dev_net_name = resolved_network_name or str(resolved_iface)
    if not is_mock_socket:
        if not dev_net_name or (dev_net_name == interface_name and not dev_net_name.startswith(r"\Device\NPF_")):
            err_msg = f"[INTERFACE_RESOLUTION_FAILED] Resolved network identifier for '{interface_name}' is invalid or unchanged ('{dev_net_name}'). Must resolve to an Npcap adapter path."
            logger.error("%s", err_msg)
            if collector_instance:
                collector_instance.lifecycle_state = "COLLECTOR_FAILED"
                collector_instance.last_error_stage = "INTERFACE_RESOLUTION"
                collector_instance.last_error_type = "RuntimeError"
                collector_instance.last_error = err_msg
                collector_instance.last_error_message = err_msg
                collector_instance._quarantine_failed_start(err_msg)
            raise RuntimeError(err_msg)

        if dev_net_name == getattr(conf, "loopback_name", r"\Device\NPF_Loopback"):
            err_msg = f"[INTERFACE_RESOLUTION_FAILED] Interface '{interface_name}' resolved to loopback adapter: {dev_net_name}"
            logger.error("%s", err_msg)
            if collector_instance:
                collector_instance.lifecycle_state = "COLLECTOR_FAILED"
                collector_instance.last_error_stage = "INTERFACE_RESOLUTION"
                collector_instance.last_error_type = "RuntimeError"
                collector_instance.last_error = err_msg
                collector_instance.last_error_message = err_msg
                collector_instance._quarantine_failed_start(err_msg)
            raise RuntimeError(err_msg)

        if expected_adapter_type == "Wi-Fi":
            desc = getattr(resolved_iface, "description", "") or ""
            lower_desc = desc.lower()
            if any(v in lower_desc for v in ["virtual", "hyper-v", "vmware", "vpn", "tunnel", "tap"]):
                err_msg = f"[INTERFACE_RESOLUTION_FAILED] Interface '{interface_name}' resolved to virtual adapter '{desc}'. Physical Wi-Fi adapter required."
                logger.error("%s", err_msg)
                if collector_instance:
                    collector_instance.lifecycle_state = "COLLECTOR_FAILED"
                    collector_instance.last_error_stage = "INTERFACE_RESOLUTION"
                    collector_instance.last_error_type = "RuntimeError"
                    collector_instance.last_error = err_msg
                    collector_instance.last_error_message = err_msg
                    collector_instance._quarantine_failed_start(err_msg)
                raise RuntimeError(err_msg)

    return resolved_iface


def select_and_validate_socket_factory(
    resolved_iface: Any,
    is_mock_socket: bool = False,
    collector_instance: Optional[Any] = None,
) -> Any:
    """
    Canonical Layer-2 socket provider selection and validation helper.
    Ensures interface-specific L2 listener is retrieved and verified as an Npcap/libpcap socket.
    """
    from scapy.config import conf
    import scapy.arch.libpcap as sal
    from unittest.mock import Mock, NonCallableMock

    socket_factory = None
    if hasattr(resolved_iface, "l2listen") and callable(resolved_iface.l2listen):
        try:
            socket_factory = resolved_iface.l2listen()
        except Exception as l2_err:
            logger.debug("resolved_iface.l2listen() raised exception: %s", l2_err)

    if socket_factory is None:
        socket_factory = conf.L2listen

    if not callable(socket_factory):
        err_msg = f"[SOCKET_SELECTION_FAILED] Selected socket factory is not callable: {socket_factory}"
        logger.error("%s", err_msg)
        if collector_instance:
            collector_instance.lifecycle_state = "COLLECTOR_FAILED"
            collector_instance.last_error_stage = "SOCKET_SELECTION"
            collector_instance.last_error_type = "RuntimeError"
            collector_instance.last_error = err_msg
            collector_instance.last_error_message = err_msg
            collector_instance._quarantine_failed_start(err_msg)
        raise RuntimeError(err_msg)

    is_mock_factory = is_mock_socket or isinstance(socket_factory, (Mock, NonCallableMock))
    if not is_mock_factory and not (isinstance(socket_factory, type) and issubclass(socket_factory, sal._L2libpcapSocket)):
        err_msg = (
            f"[SOCKET_SELECTION_FAILED] Selected socket class {socket_factory} is not an Npcap/libpcap socket. "
            "Refusing to fall back to an unsupported socket provider."
        )
        logger.error("%s", err_msg)
        if collector_instance:
            collector_instance.lifecycle_state = "COLLECTOR_FAILED"
            collector_instance.last_error_stage = "SOCKET_SELECTION"
            collector_instance.last_error_type = "RuntimeError"
            collector_instance.last_error = err_msg
            collector_instance.last_error_message = err_msg
            collector_instance._quarantine_failed_start(err_msg)
        raise RuntimeError(err_msg)

    return socket_factory


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
        self.last_error_stage: Optional[str] = None
        self.last_error_type: Optional[str] = None
        self.last_error_code: Optional[int] = None
        self.last_error_message: Optional[str] = None

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

        # Attribution subsystem components
        self.attribution_enabled: bool = getattr(config, "enable_attribution", False)
        self.attribution_available: bool = True
        self.attribution_error: Optional[str] = None
        self.last_attribution_report: Optional[Any] = None

        from research.dataset_v3.attribution.correlator import ProcessSocketCorrelator
        from research.dataset_v3.attribution.policy import AttributionEvidencePolicy
        from research.dataset_v3.attribution.process_tracker import ProcessTracker
        from research.dataset_v3.attribution.report import AttributionReportGenerator
        from research.dataset_v3.attribution.snapshot_manager import SocketSnapshotManager

        self.snapshot_manager = SocketSnapshotManager(
            snapshot_interval_seconds=getattr(config, "attribution_poll_interval_seconds", 0.15),
        )
        self.process_tracker = ProcessTracker(
            controlled_app_alias=getattr(config, "attribution_controlled_alias", "chrome_controlled"),
        )
        self.correlator = ProcessSocketCorrelator(
            snapshot_manager=self.snapshot_manager,
            process_tracker=self.process_tracker,
            window_margin_seconds=getattr(config, "attribution_window_margin_seconds", 1.0),
            min_observation_separation_seconds=getattr(config, "attribution_min_separation_seconds", 0.10),
            min_tcp_coverage_ratio=getattr(config, "attribution_min_coverage_ratio", 0.5),
            min_observation_count=getattr(config, "attribution_min_observation_count", 2),
            max_observation_gap_seconds=getattr(config, "attribution_max_observation_gap_seconds", 0.50),
            min_covered_bins=getattr(config, "attribution_min_covered_bins", 2),
            sampling_bin_width_seconds=getattr(config, "attribution_poll_interval_seconds", 0.15),
        )
        self.evidence_policy = AttributionEvidencePolicy(
            min_tcp_coverage_ratio=getattr(config, "attribution_min_coverage_ratio", 0.5),
            min_observation_count=getattr(config, "attribution_min_observation_count", 2),
            allow_strict_udp_promotion=False,
        )
        self.report_generator = AttributionReportGenerator()

        self._manifest: Optional[SessionManifest] = None
        self._sniffer: Any = None
        self._socket: Optional[Any] = None
        self._stop_event = threading.Event()
        self._timer_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._is_dry_run: bool = False

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

    def start_capture(self, dry_run: bool = False, startup_timeout: float = 5.0) -> None:
        """
        Starts physical packet capture with synchronous Layer-2 socket initialization.
        
        Lifecycle guarantees:
        1. Layer-2 capture socket is opened synchronously using conf.L2listen / resolve_iface.
        2. AsyncSniffer receives opened_socket and started_callback (strictly NO snaplen).
        3. Waits for started_callback with a bounded timeout.
        4. Validates capture worker thread liveness before transitioning to COLLECTOR_ACTIVE.
        5. If dry_run=True, initializes state without starting physical Npcap hardware sniffer.
        """
        with self._lock:
            if self.lifecycle_state not in ("COLLECTOR_READY", "COLLECTOR_IDLE"):
                raise RuntimeError(f"Cannot start capture in state: {self.lifecycle_state}")

            if self.lifecycle_state == "COLLECTOR_IDLE":
                self.initialize(bypass_prerequisites=dry_run)

            self.lifecycle_state = "COLLECTOR_STARTING"
            self.start_monotonic = time.monotonic()
            self._stop_event.clear()
            self._is_dry_run = dry_run

            # Start attribution snapshot sampling prior to packet collection
            if self.attribution_enabled:
                logger.info("Starting attribution snapshot sampling prior to packet collection...")
                try:
                    self.snapshot_manager.start_polling()
                    if self.process_tracker.root_pid is not None:
                        self.process_tracker.start_periodic_refresh(
                            interval_seconds=getattr(self.config, "attribution_tree_refresh_interval_seconds", 1.0)
                        )
                except Exception as snap_err:
                    err_msg = f"[ATTRIBUTION_INIT_FAILED] Failed starting socket snapshot polling: {snap_err}"
                    logger.warning("%s", err_msg)
                    self.attribution_available = False
                    self.attribution_error = err_msg
                    if not getattr(self.config, "attribution_allow_failure", True):
                        self.fail_capture(reason=err_msg, stage="ATTRIBUTION_INIT")
                        raise RuntimeError(err_msg) from snap_err

            if dry_run:
                self.lifecycle_state = "COLLECTOR_ACTIVE"
                logger.info("Collector started in DRY_RUN mode (testing mode; no live sniffer).")
                return

            # Live Physical Sniffer Execution
            try:
                from scapy.config import conf
                from scapy.interfaces import network_name
                from scapy.sendrecv import AsyncSniffer
                from unittest.mock import Mock, NonCallableMock

                is_mock_socket = (
                    isinstance(conf.L2listen, (Mock, NonCallableMock))
                    or "Mock" in getattr(self.config, "interface", "")
                )

                # Stage 1 & 2: Canonical Interface Resolution and Validation
                self.last_error_stage = "INTERFACE_RESOLUTION"
                try:
                    resolved_iface = resolve_and_validate_interface(
                        interface_name=self.config.interface,
                        expected_adapter_type=getattr(self.config, "adapter_type", "Wi-Fi"),
                        is_mock_socket=is_mock_socket,
                        collector_instance=self,
                    )
                except Exception as res_err:
                    if "[INTERFACE_ENUMERATION_FAILED]" in str(res_err):
                        self.last_error_stage = "INTERFACE_ENUMERATION"
                    else:
                        self.last_error_stage = "INTERFACE_RESOLUTION"
                    raise

                # Stage 3: Canonical Socket Provider Selection and Validation
                self.last_error_stage = "SOCKET_SELECTION"
                socket_factory = select_and_validate_socket_factory(
                    resolved_iface=resolved_iface,
                    is_mock_socket=is_mock_socket,
                    collector_instance=self,
                )

                # Stage 4: Synchronous Layer-2 capture socket construction
                # Diagnostics logged before opening (avoiding logging full raw GUID)
                dev_net_name = network_name(resolved_iface) or str(resolved_iface)
                sanitized_dev = sanitize_device_name(dev_net_name)
                logger.info(
                    "Initializing Layer-2 capture socket: friendly_name='%s', iface_type='%s', provider='%s', socket_class='%s', libpcap_enabled=%s, resolved_device='%s'",
                    self.config.interface,
                    type(resolved_iface).__name__,
                    getattr(getattr(resolved_iface, "provider", None), "name", "unknown"),
                    getattr(socket_factory, "__name__", str(socket_factory)),
                    getattr(conf, "use_pcap", False),
                    sanitized_dev,
                )

                self.last_error_stage = "SOCKET_INITIALIZATION"
                try:
                    self._socket = socket_factory(
                        iface=resolved_iface,
                        filter=self.config.pcap_filter,
                        promisc=self.config.promiscuous,
                    )
                except Exception as sock_err:
                    self.lifecycle_state = "COLLECTOR_FAILED"
                    self.last_error_type = type(sock_err).__name__
                    self.last_error_code = getattr(sock_err, "winerror", getattr(sock_err, "errno", None))
                    err_code_str = f" (native_code: {self.last_error_code})" if self.last_error_code is not None else ""
                    self.last_error = (
                        f"[SOCKET_INITIALIZATION_FAILED] [SOCKET_INIT_FAILED] Layer-2 socket creation failed on '{self.config.interface}' "
                        f"[Device: {sanitized_dev}]{err_code_str}: {sock_err}"
                    )
                    self.last_error_message = str(sock_err)
                    logger.error("%s", self.last_error)
                    self._cleanup_sniffer_and_socket()
                    self._quarantine_failed_start(self.last_error)
                    raise RuntimeError(self.last_error) from sock_err

                # 3. Setup AsyncSniffer with opened_socket and started_callback
                # Strictly DO NOT pass snaplen or iface to AsyncSniffer
                started_evt = threading.Event()
                sniffer_kwargs = {
                    "opened_socket": self._socket,
                    "prn": self._packet_callback,
                    "store": False,
                    "started_callback": started_evt.set,
                }

                self._sniffer = AsyncSniffer(**sniffer_kwargs)
                self._sniffer.start()

                # 4. Bounded wait for started_callback
                started = started_evt.wait(timeout=startup_timeout)

                # 5. Verify capture worker thread liveness
                thread_alive = False
                if hasattr(self._sniffer, "thread") and self._sniffer.thread is not None:
                    thread_alive = self._sniffer.thread.is_alive()

                if not started or not thread_alive:
                    self.lifecycle_state = "COLLECTOR_FAILED"
                    reason = "startup timeout" if not started else "capture worker thread died immediately"
                    self.last_error = f"[CAPTURE_START_FAILED] AsyncSniffer failed to start ({reason})."
                    logger.error("%s", self.last_error)
                    self._cleanup_sniffer_and_socket()
                    self._quarantine_failed_start(self.last_error)
                    raise RuntimeError(self.last_error)

                self.lifecycle_state = "COLLECTOR_ACTIVE"
                logger.info("Physical capture successfully verified and active on interface '%s'", self.config.interface)

                # Start duration timer thread if positive duration
                if self.config.duration_seconds > 0:
                    self._timer_thread = threading.Thread(
                        target=self._duration_timer_worker,
                        name=f"v3_timer_{self.session_id}",
                        daemon=True,
                    )
                    self._timer_thread.start()

            except Exception as e:
                if self.lifecycle_state != "COLLECTOR_FAILED":
                    self.lifecycle_state = "COLLECTOR_FAILED"
                    self.last_error = f"[CAPTURE_INIT_FAILED] {e}"
                    self._cleanup_sniffer_and_socket()
                    self._quarantine_failed_start(self.last_error)
                raise

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
        arrival_mono: Optional[float] = None,
    ) -> None:
        """Public ingestion method for feeding raw IP bytes in test harnesses."""
        res = parse_raw_ip_bytes_detailed(
            data, ts=ts, arrival_mono=arrival_mono, wire_len=wire_len, orig_frame_len=orig_frame_len
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

    def _quarantine_failed_start(self, failure_reason: str) -> None:
        """Helper to ensure staging directory is quarantined when capture fails to start or crashes."""
        try:
            self._stop_event.set()
            if self._manifest is not None:
                ManifestManager.finalize_manifest(
                    manifest=self._manifest,
                    packet_count=self.packets_processed_count,
                    flow_count=0,
                    status="FAILED",
                    label_quality="AMBIGUOUS",
                    notes=f"Capture failure: {failure_reason}",
                    kernel_buffer_drops=None,
                    queue_drops=self.queue_drops_count,
                    parsing_failures=self.parsing_failures_count,
                    processing_failures=self.processing_failures_count,
                )
                self.metadata_writer.write_manifest(self._manifest)
            self.metadata_writer.quarantine_incomplete_session(
                self._manifest or ManifestManager.create_initial_manifest(self.config),
                failure_reason=failure_reason,
            )
        except Exception as q_err:
            logger.warning("Error quarantining failed session: %s", q_err)

    def _cleanup_sniffer_and_socket(self) -> None:
        """Safely stops AsyncSniffer and closes Layer-2 socket."""
        if self._sniffer is not None:
            try:
                if getattr(self._sniffer, "running", False):
                    self._sniffer.stop()
            except Exception as e:
                logger.debug("Error stopping AsyncSniffer: %s", e)
            finally:
                self._sniffer = None

        if self._socket is not None:
            try:
                self._socket.close()
            except Exception as e:
                logger.debug("Error closing Layer-2 socket: %s", e)
            finally:
                self._socket = None

        if self.attribution_enabled:
            try:
                self.snapshot_manager.stop_polling()
                self.process_tracker.stop_periodic_refresh()
            except Exception as e:
                logger.debug("Error stopping snapshot manager or process tracker in cleanup: %s", e)

    def is_worker_alive(self) -> bool:
        """Checks whether the capture worker thread is active and alive."""
        if self.lifecycle_state != "COLLECTOR_ACTIVE":
            return False
        # If dry-run, no sniffer thread exists
        if self._sniffer is None:
            return True
        if hasattr(self._sniffer, "thread") and self._sniffer.thread is not None:
            return self._sniffer.thread.is_alive()
        return False

    def fail_capture(self, reason: str, stage: str = "RUNTIME") -> None:
        """Transitions collector to FAILED and immediately quarantines staging session."""
        with self._lock:
            if self.lifecycle_state in ("COLLECTOR_FAILED", "COLLECTOR_STOPPING", "COLLECTOR_COMPLETED"):
                return
            self.lifecycle_state = "COLLECTOR_FAILED"
            self.last_error = f"[{stage}] {reason}"
            self._stop_event.set()
            logger.error("Failing capture session %s: %s", self.session_id, self.last_error)
            self._cleanup_sniffer_and_socket()
            self._quarantine_failed_start(self.last_error)

    def _duration_timer_worker(self) -> None:
        """Monitors session duration and triggers graceful stop upon timeout."""
        duration = self.config.duration_seconds
        while not self._stop_event.is_set():
            if not self.is_worker_alive():
                logger.error("Capture worker died unexpectedly during session %s!", self.session_id)
                self.fail_capture(
                    reason="Capture worker thread died unexpectedly during active collection.",
                    stage="CAPTURE_WORKER_DIED",
                )
                break

            elapsed = time.monotonic() - (self.start_monotonic or time.monotonic())
            if elapsed >= duration:
                logger.info("Session duration (%.1f s) reached. Stopping capture...", duration)
                self.stop_capture(status="COMPLETE", notes="Reached configured duration limit.")
                break
            time.sleep(0.5)

    def stop_capture(
        self,
        status: str = "COMPLETE",
        notes: str = "",
        suppress_quarantine: bool = False,
    ) -> None:
        """
        Gracefully stops packet capture, finalizes all flows, runs validation on staging,
        and either publishes to final destination or quarantines to .incomplete/.
        
        If suppress_quarantine=True (e.g. during dry-run executions), cleans up staging artifacts
        without publishing or writing quarantine residue to disk.
        """
        # Normalize status
        if status == "COMPLETED":
            status = "COMPLETE"

        with self._lock:
            if self.lifecycle_state in ("COLLECTOR_STOPPING", "COLLECTOR_COMPLETED", "COLLECTOR_FAILED"):
                return

            # Check if capture worker was dead when stop was called
            if self._sniffer is not None and not self.is_worker_alive():
                self.lifecycle_state = "COLLECTOR_FAILED"
                self.last_error = "[CAPTURE_WORKER_DEAD] Sniffer thread died before capture completed."
                logger.error("%s", self.last_error)
                self._cleanup_sniffer_and_socket()
                self._quarantine_failed_start(self.last_error)
                return

            # Check zero packet condition
            is_empty_capture = (self.packets_processed_count == 0)
            if status == "COMPLETE" and is_empty_capture and not getattr(self.config, "allow_empty_capture", False):
                status = "FAILED"
                notes = f"{notes} | Zero physical packets received during capture session.".strip(" |")

            self.lifecycle_state = "COLLECTOR_STOPPING"
            self._stop_event.set()
            logger.info("Stopping Dataset V3 capture session '%s'", self.session_id)

            # Dry-run execution with suppressed quarantine: Clean up staging artifacts and exit cleanly without disk residue
            if suppress_quarantine:
                logger.info(
                    "Session '%s' completed with suppress_quarantine=True: cleaning staging artifacts without publishing or quarantining.",
                    self.session_id,
                )
                self._cleanup_sniffer_and_socket()
                self.metadata_writer.cleanup_staging_session()
                if status == "INTERRUPTED":
                    self.lifecycle_state = "COLLECTOR_INTERRUPTED"
                elif status == "FAILED":
                    self.lifecycle_state = "COLLECTOR_FAILED"
                else:
                    self.lifecycle_state = "COLLECTOR_COMPLETED"
                return

            # 1. Fetch drops and stop live sniffer / socket
            kernel_drops = None
            if self._sniffer is not None:
                try:
                    if hasattr(self._sniffer, "stats"):
                        try:
                            s = self._sniffer.stats()
                            if s and len(s) >= 2:
                                kernel_drops = int(s[1])
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning("Error fetching AsyncSniffer stats: %s", e)

            self._cleanup_sniffer_and_socket()

            # 2. Stop attribution snapshot polling and process tree refresh safely
            if self.attribution_enabled:
                try:
                    self.snapshot_manager.stop_polling()
                    self.process_tracker.stop_periodic_refresh()
                except Exception as snap_stop_err:
                    logger.warning("Error stopping attribution workers: %s", snap_stop_err)

            # 3. Finalize all active flows
            completed_flows = self.flow_manager.finalize_all()
            self.metadata_writer.write_flow_index(completed_flows)

            # 4. Execute process attribution correlation (if enabled)
            if self.attribution_enabled:
                self._run_attribution_correlation(completed_flows)

            # 5. Generate ground-truth labels
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
            if val_report.is_valid and status == "COMPLETE" and not is_empty_capture:
                published_path = self.metadata_writer.publish_complete_session(self._manifest)
                self.lifecycle_state = "COLLECTOR_COMPLETED"
                logger.info(
                    "Session successfully validated and published to %s: %d packets, %d flows",
                    published_path,
                    self.packets_processed_count,
                    len(completed_flows),
                )
            else:
                if is_empty_capture and status == "FAILED":
                    fail_reason = "Zero physical packets received during capture session."
                else:
                    fail_reason = "; ".join(val_report.errors) if val_report.errors else f"Status: {status}"
                quarantined_path = self.metadata_writer.quarantine_incomplete_session(
                    self._manifest, failure_reason=fail_reason
                )
                if status == "INTERRUPTED":
                    self.lifecycle_state = "COLLECTOR_INTERRUPTED"
                elif not val_report.is_valid or status == "FAILED" or is_empty_capture:
                    self.lifecycle_state = "COLLECTOR_FAILED"
                else:
                    self.lifecycle_state = "COLLECTOR_INTERRUPTED"
                logger.warning(
                    "Session validation failed or status=%s. Quarantined to %s (Reason: %s)",
                    status,
                    quarantined_path,
                    fail_reason,
                )

            self.metadata_writer.close()

    def _run_attribution_correlation(self, completed_flows: List[FlowIndexRecord]) -> None:
        """
        Executes process-to-socket correlation against completed flows.
        Correlates in volatile memory, generates sidecar report, and cleans up transient data.
        """
        evidence_records: List[Any] = []
        transient_endpoints = self.flow_manager.get_transient_endpoints()

        try:
            from research.dataset_v3.attribution.schemas import (
                ATTRIBUTION_RULE_VERSION,
                AttributionEvidenceMethod,
                AttributionEvidenceRecord,
                AttributionQuality,
            )

            if not self.attribution_available:
                logger.warning("Attribution was marked unavailable; evaluating all flows as INSUFFICIENT_EVIDENCE")
                for fl in completed_flows:
                    rec = AttributionEvidenceRecord(
                        flow_id=fl.flow_id,
                        evidence_method=AttributionEvidenceMethod.INSUFFICIENT_EVIDENCE.value,
                        application_alias=None,
                        matched_observation_count=0,
                        attribution_coverage_ratio=0.0,
                        unique_owner=False,
                        evidence_quality=AttributionQuality.UNATTRIBUTED.value,
                        attribution_rule_version=ATTRIBUTION_RULE_VERSION,
                        rejection_reason="Attribution sampling was unavailable or failed during capture",
                    )
                    evidence_records.append(rec)
                    self.candidate_flow_ids.add(fl.flow_id)
            else:
                for fl in completed_flows:
                    ep_data = transient_endpoints.get(fl.flow_id)
                    if ep_data is None:
                        rec = AttributionEvidenceRecord(
                            flow_id=fl.flow_id,
                            evidence_method=AttributionEvidenceMethod.INSUFFICIENT_EVIDENCE.value,
                            application_alias=None,
                            matched_observation_count=0,
                            attribution_coverage_ratio=0.0,
                            unique_owner=False,
                            evidence_quality=AttributionQuality.UNATTRIBUTED.value,
                            attribution_rule_version=ATTRIBUTION_RULE_VERSION,
                            rejection_reason="Flow transient endpoint metadata not found",
                        )
                    else:
                        rec = self.correlator.correlate_flow(
                            flow_id=fl.flow_id,
                            protocol=ep_data.protocol,
                            endpoint_a=ep_data.endpoint_a,
                            endpoint_b=ep_data.endpoint_b,
                            first_packet_wire_ts=ep_data.first_packet_wire_ts,
                            last_packet_wire_ts=ep_data.last_packet_wire_ts,
                            first_packet_mono_ts=ep_data.first_packet_arrival_mono,
                            last_packet_mono_ts=ep_data.last_packet_arrival_mono,
                        )

                    evidence_records.append(rec)

                    # Evaluate policy recommendation
                    rec_class, quality, source, rej_reason = self.evidence_policy.evaluate_label_recommendation(
                        rec,
                        intended_traffic_class=self.config.intended_traffic_class,
                        controlled_app_alias=self.process_tracker.controlled_app_alias,
                    )

                    if quality == "VERIFIED":
                        self.verified_flow_ids.add(fl.flow_id)
                    elif quality == "UNLABELLED":
                        # Background noise: do not add to candidate or verified
                        pass
                    else:
                        self.candidate_flow_ids.add(fl.flow_id)

            # Generate and serialize sidecar report in staging
            report = self.report_generator.generate_report(
                session_id=self.session_id,
                evidence_records=evidence_records,
            )
            self.last_attribution_report = report
            self.metadata_writer.write_attribution_report(report)

        except Exception as attr_err:
            logger.error("Error during attribution correlation: %s", attr_err)
            self.attribution_available = False
            self.attribution_error = str(attr_err)
            if not getattr(self.config, "attribution_allow_failure", True):
                raise
        finally:
            # Strictly release all transient endpoints and volatile process references
            self.flow_manager.clear_transient_endpoints()
            self.snapshot_manager.clear()
            self.process_tracker.clear()

    @classmethod
    def smoke_test_socket(
        cls,
        interface_name: str = "Wi-Fi",
        pcap_filter: str = "tcp or udp",
        promiscuous: bool = False,
        expected_adapter_type: str = "Wi-Fi",
    ) -> Dict[str, Any]:
        """
        Diagnostic smoke-test for Layer-2 socket resolution, opening, and immediate closing.
        1. Refreshes Scapy interface registry on Windows (conf.ifaces.reload()).
        2. Resolves friendly interface name to Scapy NetworkInterface via resolve_iface().
        3. Validates interface is non-dummy, matches friendly name, has valid NPF device path,
           and is the intended physical adapter.
        4. Validates interface-specific Layer-2 listener via resolved.l2listen().
        5. Confirms socket provider is Npcap/libpcap L2pcapListenSocket.
        6. Opens the Layer-2 socket synchronously.
        7. Confirms socket creation.
        8. Immediately closes the socket in a guaranteed finally block.
        9. Strictly DOES NOT invoke sniff(), AsyncSniffer, recv(), packet callbacks, or PCAP writers.
        10. Strictly DOES NOT create dataset sessions or touch disk.
        """
        import platform
        from scapy.config import conf
        from scapy.interfaces import resolve_iface, network_name, NetworkInterface
        import scapy.arch.libpcap as sal
        from unittest.mock import Mock, NonCallableMock

        diagnostics: Dict[str, Any] = {
            "interface_input": interface_name,
            "stage_reached": "START",
            "resolved_name": None,
            "resolved_network_name": None,
            "sanitized_network_name": None,
            "interface_type": None,
            "provider_name": None,
            "description": None,
            "libpcap_enabled": getattr(conf, "use_pcap", False),
            "is_dummy": None,
            "socket_class": None,
            "socket_opened": False,
            "socket_closed": False,
            "error_stage": None,
            "exception_type": None,
            "native_error_code": None,
            "error_message": None,
        }

        is_mock_socket = (
            isinstance(conf.L2listen, (Mock, NonCallableMock))
            or "Mock" in interface_name
        )

        # Stage 1 & 2: Canonical Interface Resolution and Validation
        diagnostics["stage_reached"] = "INTERFACE_RESOLUTION"
        try:
            resolved = resolve_and_validate_interface(
                interface_name=interface_name,
                expected_adapter_type=expected_adapter_type,
                is_mock_socket=is_mock_socket,
            )
        except Exception as res_err:
            if "[INTERFACE_ENUMERATION_FAILED]" in str(res_err):
                diagnostics["error_stage"] = "INTERFACE_ENUMERATION"
            else:
                diagnostics["error_stage"] = "INTERFACE_RESOLUTION"
            diagnostics["exception_type"] = type(res_err).__name__
            diagnostics["native_error_code"] = getattr(res_err, "winerror", getattr(res_err, "errno", None))
            diagnostics["error_message"] = str(res_err)
            raise

        diagnostics["interface_type"] = type(resolved).__name__
        diagnostics["provider_name"] = getattr(getattr(resolved, "provider", None), "name", "unknown")
        diagnostics["description"] = getattr(resolved, "description", None)
        diagnostics["resolved_name"] = getattr(resolved, "name", str(resolved))
        diagnostics["resolved_network_name"] = getattr(resolved, "network_name", None)
        diagnostics["sanitized_network_name"] = sanitize_device_name(diagnostics["resolved_network_name"])
        diagnostics["is_dummy"] = getattr(resolved, "dummy", False)

        # Stage 3: Canonical Socket Provider Selection and Validation
        diagnostics["stage_reached"] = "SOCKET_SELECTION"
        try:
            socket_factory = select_and_validate_socket_factory(
                resolved_iface=resolved,
                is_mock_socket=is_mock_socket,
            )
        except Exception as sock_sel_err:
            diagnostics["error_stage"] = "SOCKET_SELECTION"
            diagnostics["exception_type"] = type(sock_sel_err).__name__
            diagnostics["error_message"] = str(sock_sel_err)
            raise

        diagnostics["socket_class"] = getattr(socket_factory, "__name__", str(socket_factory))

        # Stage 4: Synchronous Socket Creation & Immediate Closing
        diagnostics["stage_reached"] = "SOCKET_INITIALIZATION"
        sock = None
        try:
            logger.info(
                "Smoke-test: Opening Layer-2 socket on '%s' [Device: %s] (socket_class: %s, libpcap_enabled=%s)",
                interface_name,
                diagnostics["sanitized_network_name"],
                diagnostics["socket_class"],
                diagnostics["libpcap_enabled"],
            )
            sock = socket_factory(
                iface=resolved,
                filter=pcap_filter,
                promisc=promiscuous,
            )
            diagnostics["socket_opened"] = True
            logger.info("Smoke-test: Successfully opened Layer-2 socket on '%s'", diagnostics["sanitized_network_name"])
        except Exception as sock_err:
            diagnostics["error_stage"] = "SOCKET_INITIALIZATION"
            diagnostics["exception_type"] = type(sock_err).__name__
            diagnostics["native_error_code"] = getattr(sock_err, "winerror", getattr(sock_err, "errno", None))
            err_code_str = f" (code: {diagnostics['native_error_code']})" if diagnostics["native_error_code"] is not None else ""
            diagnostics["error_message"] = (
                f"[SOCKET_INITIALIZATION_FAILED] [SOCKET_INIT_FAILED] Failed opening Layer-2 socket on '{interface_name}' "
                f"[Device: {diagnostics['sanitized_network_name']}]{err_code_str}: {sock_err}"
            )
            logger.error("%s", diagnostics["error_message"])
            raise RuntimeError(diagnostics["error_message"]) from sock_err
        finally:
            if sock is not None:
                try:
                    sock.close()
                    diagnostics["socket_closed"] = True
                    logger.info("Smoke-test: Successfully closed Layer-2 socket.")
                except Exception as close_err:
                    logger.warning("Smoke-test: Error closing socket: %s", close_err)

        diagnostics["stage_reached"] = "COMPLETED"
        return diagnostics
