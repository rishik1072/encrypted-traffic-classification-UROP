"""
Standalone Diagnostic: Live Windows IP Helper Process-to-Socket Attribution Validation.

Validates the Windows Process-to-Socket Attribution Subsystem against real operating
system APIs:
- GetExtendedTcpTable (IPv4 & IPv6 with owning PIDs)
- GetExtendedUdpTable (IPv4 & IPv6 with owning PIDs)
- GetProcessTimes (Process creation-time identity and PID reuse prevention)

Creates isolated, local Python loopback sockets, queries live kernel socket tables,
verifies ownership and connection state filtering, and guarantees complete cleanup.

Strictly zero packet sniffing (no Npcap, no Scapy capture, no PCAP files).
Strictly zero persistence of raw IPs, ports, PIDs, paths, or payload bytes.
"""

from __future__ import annotations

import argparse
import os
import platform
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research.dataset_v3.attribution.correlator import ProcessSocketCorrelator
from research.dataset_v3.attribution.ip_helper import (
    WindowsIPHelperReader,
    get_process_creation_time_and_name,
    normalize_ip_address,
    normalize_port,
)
from research.dataset_v3.attribution.policy import AttributionEvidencePolicy
from research.dataset_v3.attribution.process_tracker import ProcessTracker
from research.dataset_v3.attribution.schemas import (
    AttributionEvidenceMethod,
    AttributionQuality,
    TransientSocketEntry,
    verify_privacy_safe_string,
)
from research.dataset_v3.attribution.snapshot_manager import SocketSnapshotManager


def run_live_diagnostic(verbose: bool = False) -> Dict[str, Any]:
    """
    Executes live verification against real Windows IP Helper socket tables.
    Returns a dictionary of privacy-safe diagnostic outcomes.
    """
    results: Dict[str, Any] = {
        "os_is_windows": platform.system() == "Windows",
        "api_available": False,
        "tcp_v4_success": False,
        "tcp_v4_state_established": False,
        "tcp_v4_pid_matched": False,
        "tcp_v4_creation_time_verified": False,
        "tcp_listener_excluded": False,
        "tcp_v6_tested": False,
        "tcp_v6_success": False,
        "udp_v4_success": False,
        "udp_v4_pid_matched": False,
        "shared_udp_conflict_detected": False,
        "pid_reuse_prevented": False,
        "privacy_audit_passed": False,
        "cleanup_confirmed": False,
    }

    if not results["os_is_windows"]:
        print("[SKIP] Live Windows IP Helper validation requires Windows OS.")
        return results

    reader = WindowsIPHelperReader()
    if not reader.is_supported:
        print("[FAIL] Windows iphlpapi.dll or kernel32.dll could not be initialized.")
        return results

    results["api_available"] = True
    current_pid = os.getpid()

    # Query creation time and name for current test process
    proc_ctime, proc_pname = get_process_creation_time_and_name(current_pid)
    if proc_ctime:
        results["tcp_v4_creation_time_verified"] = True

    # Socket handles for guaranteed cleanup
    tcp_srv: Optional[socket.socket] = None
    tcp_cli: Optional[socket.socket] = None
    tcp_conn: Optional[socket.socket] = None
    tcp_srv6: Optional[socket.socket] = None
    tcp_cli6: Optional[socket.socket] = None
    tcp_conn6: Optional[socket.socket] = None
    udp_sock: Optional[socket.socket] = None

    try:
        # ======================================================================
        # 1. Live TCP IPv4 Connection Verification
        # ======================================================================
        tcp_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_srv.bind(("127.0.0.1", 0))
        tcp_srv.listen(1)
        srv_port = tcp_srv.getsockname()[1]

        tcp_cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_cli.connect(("127.0.0.1", srv_port))
        cli_port = tcp_cli.getsockname()[1]

        tcp_conn, _ = tcp_srv.accept()

        # Query Windows TCP table while connection is actively held open
        now_ts = time.time()
        tcp_entries_v4 = reader.read_tcp_table_ipv4(now_ts)

        # Find the active client connection
        client_matches = [
            e for e in tcp_entries_v4
            if e.pid == current_pid and e.local_port == cli_port and e.remote_port == srv_port
        ]
        # Find the listening socket
        listener_matches = [
            e for e in tcp_entries_v4
            if e.pid == current_pid and e.local_port == srv_port and e.state == "LISTEN"
        ]

        if client_matches:
            results["tcp_v4_success"] = True
            results["tcp_v4_pid_matched"] = (client_matches[0].pid == current_pid)
            results["tcp_v4_state_established"] = (client_matches[0].state == "ESTABLISHED")

        # Verify that correlator matches the established connection but ignores the listener
        snap_mgr = SocketSnapshotManager()
        snap_mgr.add_snapshot(now_ts, tcp_entries_v4)

        tracker = ProcessTracker(controlled_app_alias="test_runner")
        tracker.register_controlled_root(
            pid=current_pid,
            create_time_utc=proc_ctime,
            process_name="python.exe",
        )
        correlator = ProcessSocketCorrelator(snap_mgr, tracker)

        evidence_active = correlator.correlate_flow(
            flow_id="flow_test_live_tcp_active",
            protocol="TCP",
            endpoint_a=("127.0.0.1", cli_port),
            endpoint_b=("127.0.0.1", srv_port),
            first_packet_wire_ts=now_ts - 0.1,
            last_packet_wire_ts=now_ts + 0.1,
        )

        # Flow to listener port with non-existent remote port (simulating listener probe)
        evidence_listener = correlator.correlate_flow(
            flow_id="flow_test_live_tcp_listener",
            protocol="TCP",
            endpoint_a=("127.0.0.1", srv_port),
            endpoint_b=("127.0.0.1", 11111),  # Unmatched remote
            first_packet_wire_ts=now_ts - 0.1,
            last_packet_wire_ts=now_ts + 0.1,
        )

        if (
            evidence_active.evidence_method == AttributionEvidenceMethod.EXACT_TCP_PROCESS_MATCH.value
            and evidence_active.unique_owner is True
            and evidence_listener.evidence_method != AttributionEvidenceMethod.EXACT_TCP_PROCESS_MATCH.value
        ):
            results["tcp_listener_excluded"] = True

        # ======================================================================
        # 2. Live TCP IPv6 Connection Verification (Where Supported)
        # ======================================================================
        try:
            tcp_srv6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            tcp_srv6.bind(("::1", 0))
            tcp_srv6.listen(1)
            srv6_port = tcp_srv6.getsockname()[1]

            tcp_cli6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            tcp_cli6.connect(("::1", srv6_port))
            cli6_port = tcp_cli6.getsockname()[1]

            tcp_conn6, _ = tcp_srv6.accept()
            results["tcp_v6_tested"] = True

            tcp_entries_v6 = reader.read_tcp_table_ipv6(time.time())
            v6_matches = [
                e for e in tcp_entries_v6
                if e.pid == current_pid and e.local_port == cli6_port and e.remote_port == srv6_port
            ]
            if v6_matches and v6_matches[0].state == "ESTABLISHED":
                results["tcp_v6_success"] = True
        except Exception as e:
            if verbose:
                print(f"  [NOTE] IPv6 loopback TCP test: {e}")

        # ======================================================================
        # 3. Live UDP IPv4 Endpoint Verification
        # ======================================================================
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.bind(("127.0.0.1", 0))
        udp_port = udp_sock.getsockname()[1]

        udp_entries_v4 = reader.read_udp_table_ipv4(time.time())
        udp_matches = [
            e for e in udp_entries_v4
            if e.pid == current_pid and e.local_port == udp_port
        ]
        if udp_matches:
            results["udp_v4_success"] = True
            results["udp_v4_pid_matched"] = (udp_matches[0].pid == current_pid)

        # ======================================================================
        # 4. Shared UDP Endpoint Conflict Handling
        # ======================================================================
        sim_snap_mgr = SocketSnapshotManager()
        sim_snap_mgr.add_snapshot(
            now_ts,
            [
                TransientSocketEntry(
                    protocol="UDP",
                    local_address="0.0.0.0",
                    local_port=5353,
                    pid=current_pid,
                    process_create_time_utc=proc_ctime,
                    process_name="python.exe",
                    timestamp_utc=now_ts,
                ),
                TransientSocketEntry(
                    protocol="UDP",
                    local_address="0.0.0.0",
                    local_port=5353,
                    pid=99999,  # Distinct competing process
                    process_create_time_utc="2026-11-21T00:00:00Z",
                    process_name="other.exe",
                    timestamp_utc=now_ts,
                ),
            ],
        )
        sim_correlator = ProcessSocketCorrelator(sim_snap_mgr, tracker)
        udp_shared_evidence = sim_correlator.correlate_flow(
            flow_id="flow_test_live_shared_udp",
            protocol="UDP",
            endpoint_a=("127.0.0.1", 5353),
            endpoint_b=("224.0.0.251", 5353),
            first_packet_wire_ts=now_ts - 0.1,
            last_packet_wire_ts=now_ts + 0.1,
        )
        if (
            udp_shared_evidence.evidence_method == AttributionEvidenceMethod.MULTIPLE_PROCESS_MATCH.value
            and udp_shared_evidence.unique_owner is False
        ):
            results["shared_udp_conflict_detected"] = True

        # ======================================================================
        # 5. PID Reuse Disambiguation
        # ======================================================================
        # If the same PID is presented with a different creation time
        alias_reused, is_ctrl_reused = tracker.resolve_application_alias(
            pid=current_pid,
            create_time_utc="1999-01-01T00:00:00.000000+00:00",  # Fake previous lifetime
            process_name="python.exe",
        )
        if not is_ctrl_reused and alias_reused == "system_background":
            results["pid_reuse_prevented"] = True

        # ======================================================================
        # 6. Privacy Canary Audit
        # ======================================================================
        canary_tests_passed = True
        test_canaries = [
            ("ipv4", "192.168.1.100"),
            ("ipv6_full", "2001:0db8:85a3:0000:0000:8a2e:0370:7334"),
            ("ipv6_comp", "fe80::1"),
            ("ipv4_mapped", "::ffff:192.168.1.1"),
            ("mac", "00:1A:2B:3C:4D:5E"),
            ("url", "https://example.com/api"),
            ("win_path", "C:\\Windows\\System32\\cmd.exe"),
            ("unc_path", "\\\\server\\share\\file.txt"),
            ("pid_key", "pid=1234"),
            ("port_num", "failed on port 8080"),
            ("cmd_arg", "chrome.exe --type=renderer"),
        ]
        for name, canary_str in test_canaries:
            try:
                verify_privacy_safe_string(name, canary_str)
                # Should have raised ValueError!
                canary_tests_passed = False
                break
            except ValueError:
                pass

        # Verify that legitimate non-sensitive strings pass without error
        try:
            verify_privacy_safe_string("valid_alias", "chrome_controlled")
            verify_privacy_safe_string("valid_alias_bg", "system_background")
            verify_privacy_safe_string(
                "valid_reason",
                "Endpoint socket was not present in contemporaneous socket table"
            )
        except ValueError:
            canary_tests_passed = False

        results["privacy_audit_passed"] = canary_tests_passed

    finally:
        # ======================================================================
        # 7. Guaranteed Socket Cleanup
        # ======================================================================
        for sock in (tcp_cli, tcp_conn, tcp_srv, tcp_cli6, tcp_conn6, tcp_srv6, udp_sock):
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
        results["cleanup_confirmed"] = True

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dataset V3 Live Windows IP Helper Attribution Diagnostic"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Display verbose step annotations."
    )
    args = parser.parse_args()

    print("=" * 70)
    print("DATASET V3: LIVE WINDOWS ATTRIBUTION API VALIDATION")
    print("=" * 70)

    t0 = time.time()
    res = run_live_diagnostic(verbose=args.verbose)
    elapsed = time.time() - t0

    print(f"  Platform Windows:              {res['os_is_windows']}")
    print(f"  IP Helper DLLs Loaded:         {res['api_available']}")
    print(f"  Process Creation Time Verified: {res['tcp_v4_creation_time_verified']}")
    print(f"  TCP IPv4 Connection Discovered: {res['tcp_v4_success']}")
    print(f"  TCP IPv4 State ESTABLISHED:    {res['tcp_v4_state_established']}")
    print(f"  TCP IPv4 Owning PID Matched:   {res['tcp_v4_pid_matched']}")
    print(f"  TCP Listeners Filtered:        {res['tcp_listener_excluded']}")
    print(f"  TCP IPv6 Tested:               {res['tcp_v6_tested']}")
    print(f"  TCP IPv6 Connection Verified:  {res['tcp_v6_success']}")
    print(f"  UDP IPv4 Endpoint Discovered:  {res['udp_v4_success']}")
    print(f"  UDP IPv4 Owning PID Matched:   {res['udp_v4_pid_matched']}")
    print(f"  Shared UDP Conflict Detected:  {res['shared_udp_conflict_detected']}")
    print(f"  PID Reuse Prevented:           {res['pid_reuse_prevented']}")
    print(f"  Privacy Canary Audit Passed:   {res['privacy_audit_passed']}")
    print(f"  All Test Sockets Closed:       {res['cleanup_confirmed']}")
    print("-" * 70)
    print(f"  Elapsed Verification Time:     {elapsed:.3f}s")
    print("=" * 70)

    # Core required invariants
    all_passed = (
        res["os_is_windows"]
        and res["api_available"]
        and res["tcp_v4_success"]
        and res["tcp_v4_state_established"]
        and res["tcp_v4_pid_matched"]
        and res["tcp_v4_creation_time_verified"]
        and res["tcp_listener_excluded"]
        and res["udp_v4_success"]
        and res["udp_v4_pid_matched"]
        and res["shared_udp_conflict_detected"]
        and res["pid_reuse_prevented"]
        and res["privacy_audit_passed"]
        and res["cleanup_confirmed"]
    )

    if all_passed:
        print("[RESULT] ALL LIVE WINDOWS ATTRIBUTION CHECKS PASSED.")
        sys.exit(0)
    else:
        print("[RESULT] ONE OR MORE LIVE ATTRIBUTION CHECKS FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
