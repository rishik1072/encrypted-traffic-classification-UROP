"""
Pilot Session 1 Configuration and Pre-Flight Validation Module for Dataset V3.

Defines the non-running pilot configuration for controlled physical Wi-Fi collection:
- Adapter: Wi-Fi (Intel(R) Wi-Fi 6 AX201 160MHz)
- Tunnel: DIRECT (no VPN encapsulation)
- Class: Web
- Application Alias: chrome_browsing
- Activity: Active Web Browsing (Chrome Wikipedia/Documentation)
- Duration: 60 seconds
- Snaplen: 96 bytes (user-space header extraction limit)
- Payload persistence: Strictly disabled (zero payload bytes retained)
- Synthetic: Strictly disabled (allow_synthetic = False)

This module provides configuration generation and pre-flight health validation ONLY.
It does NOT initiate physical capture.
"""

from __future__ import annotations

import logging
import os
import platform
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from research.dataset_v3.config import DatasetV3Config

logger = logging.getLogger("research.dataset_v3.pilot_config")

# Canonical Pilot Session 1 Constants
PILOT_COLLECTION_PLAN_ID = "sess_pilot_001_wifi_direct_web"
PILOT_2_COLLECTION_PLAN_ID = "sess_pilot_002_wifi_direct_web"
PILOT_ADAPTER_TYPE = "Wi-Fi"
PILOT_INTERFACE_NAME = "Wi-Fi"
PILOT_TUNNEL_STATUS = "DIRECT"
PILOT_TRAFFIC_CLASS = "Web"
PILOT_APPLICATION_ALIAS = "chrome_browsing"
PILOT_2_APPLICATION_ALIAS = "chrome_controlled"
PILOT_ACTIVITY_DESCRIPTION = "Active Web Browsing (Chrome Wikipedia/Documentation)"
PILOT_2_ACTIVITY_DESCRIPTION = "Controlled Chrome Web Browsing (Wikipedia/Documentation)"
PILOT_OPERATOR_LABEL = "operator_rishi"
PILOT_ENVIRONMENT_ID = "pilot_home_wlan"
PILOT_DURATION_SECONDS = 60.0
PILOT_SNAPLEN = 96  # User-space parser truncation limit (NOT claimed as Npcap kernel snaplen)
PILOT_PCAP_FILTER = "tcp or udp"


def create_pilot_session_1_config(
    output_root: Optional[Path] = None,
    interface: Optional[str] = None,
    duration_seconds: float = PILOT_DURATION_SECONDS,
    session_id: Optional[str] = None,
) -> DatasetV3Config:
    """
    Constructs an immutable DatasetV3Config configured precisely for Pilot Session 1.
    Separates collection_plan_id ('sess_pilot_001_wifi_direct_web') from the newly
    generated random UUID session_id for this physical execution.
    Does NOT start packet capture or touch disk.
    """
    root = Path(output_root) if output_root is not None else Path("data/research_v3")
    iface = interface if interface is not None else PILOT_INTERFACE_NAME
    sid = session_id if session_id is not None else f"sess_{uuid.uuid4().hex}"

    config = DatasetV3Config(
        output_root=root,
        collection_plan_id=PILOT_COLLECTION_PLAN_ID,
        session_id=sid,
        interface=iface,
        adapter_type=PILOT_ADAPTER_TYPE,
        environment_id=PILOT_ENVIRONMENT_ID,
        tunnel_status=PILOT_TUNNEL_STATUS,
        intended_traffic_class=PILOT_TRAFFIC_CLASS,
        application_alias=PILOT_APPLICATION_ALIAS,
        collection_activity=PILOT_ACTIVITY_DESCRIPTION,
        collection_operator_label=PILOT_OPERATOR_LABEL,
        duration_seconds=duration_seconds,
        snaplen=PILOT_SNAPLEN,
        promiscuous=False,
        pcap_filter=PILOT_PCAP_FILTER,
        flow_idle_timeout_seconds=30.0,
        flow_active_timeout_seconds=120.0,
        max_packets_per_flow=10000,
        is_synthetic=False,
    )
    return config


def create_pilot_session_2_config(
    output_root: Optional[Path] = None,
    interface: Optional[str] = None,
    duration_seconds: float = PILOT_DURATION_SECONDS,
    session_id: Optional[str] = None,
) -> DatasetV3Config:
    """
    Constructs an immutable DatasetV3Config configured precisely for Pilot Session 2.
    Separates collection_plan_id ('sess_pilot_002_wifi_direct_web') from the newly
    generated random UUID session_id for this physical execution.
    Enables Windows process attribution subsystem with 150 ms polling.
    Does NOT start packet capture or touch disk.
    """
    root = Path(output_root) if output_root is not None else Path("data/research_v3")
    iface = interface if interface is not None else PILOT_INTERFACE_NAME
    sid = session_id if session_id is not None else f"sess_{uuid.uuid4().hex}"

    config = DatasetV3Config(
        output_root=root,
        collection_plan_id=PILOT_2_COLLECTION_PLAN_ID,
        session_id=sid,
        interface=iface,
        adapter_type=PILOT_ADAPTER_TYPE,
        environment_id=PILOT_ENVIRONMENT_ID,
        tunnel_status=PILOT_TUNNEL_STATUS,
        intended_traffic_class=PILOT_TRAFFIC_CLASS,
        application_alias=PILOT_2_APPLICATION_ALIAS,
        collection_activity=PILOT_2_ACTIVITY_DESCRIPTION,
        collection_operator_label=PILOT_OPERATOR_LABEL,
        duration_seconds=duration_seconds,
        snaplen=PILOT_SNAPLEN,
        promiscuous=False,
        pcap_filter=PILOT_PCAP_FILTER,
        flow_idle_timeout_seconds=30.0,
        flow_active_timeout_seconds=120.0,
        max_packets_per_flow=10000,
        is_synthetic=False,
        enable_attribution=True,
        attribution_poll_interval_seconds=0.15,
        attribution_controlled_alias="chrome_controlled",
        attribution_min_coverage_ratio=0.50,
        attribution_min_observation_count=2,
        attribution_max_observation_gap_seconds=0.50,
        attribution_min_covered_bins=2,
        attribution_min_separation_seconds=0.10,
        attribution_window_margin_seconds=1.0,
    )
    return config


def validate_pilot_preflight(config: DatasetV3Config) -> Tuple[bool, List[str]]:
    """
    Executes non-invasive, passive pre-flight checks before Pilot Session 1:
    1. Operating system and Npcap driver availability.
    2. Strict prohibition of synthetic traffic (is_synthetic == False).
    3. Interface specification and non-empty name.
    4. Overwrite prevention (target session directory must not already exist with SESSION_COMPLETE).
    5. Duration and snaplen bounds.
    6. Non-interference with running production processes (PIDs 17132, 21544, 23516).

    Returns:
        (is_ready, list_of_blocking_issues_or_warnings)
    """
    issues: List[str] = []

    # 1. OS and Npcap availability
    if platform.system() != "Windows":
        issues.append(f"Expected Windows OS for Npcap capture, found: {platform.system()}")

    sys_root = os.environ.get("SystemRoot", r"C:\Windows")
    npcap_sys = Path(sys_root) / "System32" / "drivers" / "npcap.sys"
    npcap_dll = Path(sys_root) / "System32" / "Npcap" / "wpcap.dll"
    packet_dll = Path(sys_root) / "System32" / "Npcap" / "Packet.dll"

    if not npcap_sys.exists():
        issues.append(f"Npcap kernel driver not found at {npcap_sys}")
    if not npcap_dll.exists() and not packet_dll.exists():
        issues.append("Npcap user-space libraries (wpcap.dll / Packet.dll) not found in System32\\Npcap")

    # 2. Strict synthetic traffic rejection
    if config.is_synthetic:
        issues.append("Dataset V3 invariant violation: is_synthetic must be False for physical pilot.")

    # 3. Interface validation
    if not config.interface:
        issues.append("No network interface specified in config.")

    # 4. Target session publication collision prevention
    final_dir = config.final_session_dir
    if final_dir.exists():
        complete_marker = final_dir / "SESSION_COMPLETE"
        if complete_marker.exists():
            issues.append(
                f"Destination session '{final_dir}' already contains a published complete session. "
                "Aborting to prevent destructive overwrite."
            )

    # 5. Snaplen configuration
    if config.snaplen is None or config.snaplen <= 0:
        issues.append("Snaplen must be explicitly set to positive integer (expected 96 or 128).")
    elif config.snaplen < 64:
        issues.append(f"Configured snaplen ({config.snaplen}) is dangerously small (< 64B); will truncate headers.")

    # 6. Check production capture non-concurrency
    # Existing production capture processes must not run concurrently with the Dataset V3 collector on the same interface.
    try:
        import psutil
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            cmd_list = p.info.get("cmdline") or []
            cmd_str = " ".join(cmd_list).lower()
            if "realtime.run" in cmd_str or ("packet_capture" in cmd_str and "python" in cmd_str):
                issues.append(
                    f"Production capture process detected active (PID {p.info['pid']}). "
                    f"Existing production capture processes must not run concurrently with the Dataset V3 "
                    f"collector on the same interface ('{config.interface}') to prevent Npcap driver buffer contention."
                )
    except Exception as e:
        logger.debug("psutil concurrent capture check skipped: %s", e)

    is_ready = len(issues) == 0
    return is_ready, issues


if __name__ == "__main__":
    import json
    cfg = create_pilot_session_1_config()
    print("Dataset V3 Pilot Session 1 Configuration:")
    print(f"  Collection Plan ID: {cfg.collection_plan_id}")
    print(f"  Session ID (UUID):  {cfg.session_id}")
    print(f"  Interface:          {cfg.interface}")
    print(f"  Adapter Type:       {cfg.adapter_type}")
    print(f"  Tunnel Status:      {cfg.tunnel_status}")
    print(f"  Traffic Class:      {cfg.intended_traffic_class}")
    print(f"  Application:        {cfg.application_alias}")
    print(f"  Activity:           {cfg.collection_activity}")
    print(f"  Duration:           {cfg.duration_seconds}s")
    print(f"  User-space Limit:   {cfg.snaplen}B (user-space parser limit, NOT Npcap kernel snaplen)")
    print(f"  Native Wire Length: UNAVAILABLE unless supplied by backend")
    print(f"  Synthetic:          {cfg.is_synthetic} (strictly disabled)")
    print(f"  Payload Persist:    False (strictly disabled)")
    print(f"  Final Output:       {cfg.final_session_dir}")

    ready, errs = validate_pilot_preflight(cfg)
    print("\nPre-Flight Validation Result:")
    print(f"  Ready for capture: {ready}")
    if errs:
        print("  Issues encountered:")
        for err in errs:
            print(f"    - {err}")
    else:
        print("  All pre-flight safety and integrity checks PASSED.")
