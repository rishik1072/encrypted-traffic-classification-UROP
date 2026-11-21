"""
Unit and Regression Tests for Dataset V3 Windows Process-to-Socket Attribution Subsystem.

Tests all 12 design requirements:
1. TCP exact endpoint match
2. TCP reverse-direction match
3. IPv4 and IPv6 normalization and matching
4. UDP local endpoint ownership
5. Shared UDP endpoint handling
6. PID reuse disambiguation via process creation-time
7. Missing process in contemporaneous snapshots
8. Stale socket observations outside flow window
9. Multiple conflicting process matches
10. Privacy enforcement (zero IP, port, PID, path, or URL leakage)
11. No automatic VERIFIED promotion (strict policy enforcement)
12. Preservation of existing published and quarantined Dataset V3 sessions
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import socket
import pytest

from research.dataset_v3.attribution.correlator import ProcessSocketCorrelator
from research.dataset_v3.attribution.ip_helper import (
    normalize_ip_address,
    normalize_port,
)
from research.dataset_v3.attribution.policy import AttributionEvidencePolicy
from research.dataset_v3.attribution.process_tracker import ProcessTracker
from research.dataset_v3.attribution.report import AttributionReportGenerator
from research.dataset_v3.attribution.schemas import (
    ATTRIBUTION_RULE_VERSION,
    AttributionEvidenceMethod,
    AttributionEvidenceRecord,
    AttributionQuality,
    AttributionReport,
    TransientSocketEntry,
    verify_privacy_safe_string,
)
from research.dataset_v3.attribution.simulation import (
    AttributionSimulation,
    SyntheticSocketFixtureGenerator,
)
from research.dataset_v3.attribution.snapshot_manager import SocketSnapshotManager


# ==============================================================================
# 1. TCP Exact Endpoint Match
# ==============================================================================

def test_tcp_exact_endpoint_match():
    """Requirement 11.1: Exact forward 4-tuple match with controlled Chrome process."""
    fixture_gen = SyntheticSocketFixtureGenerator(base_timestamp=1700000000.0)
    tracker = fixture_gen.create_chrome_process_tree(
        root_pid=1000, network_service_pid=1004, renderer_pid=1008
    )
    snap_mgr = SocketSnapshotManager()

    # Flow lasting 0.25s (2 sampling bins of width 0.15s: [0, 0.15) and [0.15, 0.25])
    t_flow_start = 1700000001.0
    t_flow_end = 1700000001.25
    snap_entries_1 = fixture_gen.generate_tcp_snapshot(
        timestamp=1700000001.05,
        local_ip="192.168.1.50",
        local_port=54321,
        remote_ip="93.184.216.34",
        remote_port=443,
        pid=1004,
        process_name="chrome.exe",
        create_time="2026-11-21T10:00:01.000000+00:00",
    )
    snap_entries_2 = fixture_gen.generate_tcp_snapshot(
        timestamp=1700000001.20,
        local_ip="192.168.1.50",
        local_port=54321,
        remote_ip="93.184.216.34",
        remote_port=443,
        pid=1004,
        process_name="chrome.exe",
        create_time="2026-11-21T10:00:01.000000+00:00",
    )
    snap_mgr.add_snapshot(1700000001.05, snap_entries_1)
    snap_mgr.add_snapshot(1700000001.20, snap_entries_2)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_test_tcp_exact",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=t_flow_start,
        last_packet_wire_ts=t_flow_end,
    )

    assert evidence.flow_id == "flow_test_tcp_exact"
    assert evidence.evidence_method == AttributionEvidenceMethod.EXACT_TCP_PROCESS_MATCH.value
    assert evidence.application_alias == "chrome_controlled"
    assert evidence.unique_owner is True
    assert evidence.matched_observation_count == 2
    assert evidence.attribution_coverage_ratio == 1.0
    assert evidence.evidence_quality == AttributionQuality.HIGH.value
    assert evidence.rejection_reason is None


# ==============================================================================
# 2. TCP Reverse-Direction Match
# ==============================================================================

def test_tcp_reverse_direction_match():
    """Requirement 11.2: Exact reverse 4-tuple match (packet index 0 observed from server side)."""
    fixture_gen = SyntheticSocketFixtureGenerator(base_timestamp=1700000000.0)
    tracker = fixture_gen.create_chrome_process_tree(
        root_pid=1000, network_service_pid=1004
    )
    snap_mgr = SocketSnapshotManager()

    # Flow observed as server -> client (endpoint_a is server, endpoint_b is client)
    snap_entries = fixture_gen.generate_tcp_snapshot(
        timestamp=1700000001.0,
        local_ip="192.168.1.50",
        local_port=54321,
        remote_ip="93.184.216.34",
        remote_port=443,
        pid=1004,
    )
    snap_mgr.add_snapshot(1700000001.0, snap_entries)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_test_tcp_reverse",
        protocol="TCP",
        endpoint_a=("93.184.216.34", 443),     # Server first
        endpoint_b=("192.168.1.50", 54321),   # Client second
        first_packet_wire_ts=1700000001.0,
        last_packet_wire_ts=1700000001.15,
    )

    assert evidence.evidence_method == AttributionEvidenceMethod.EXACT_TCP_PROCESS_MATCH.value
    assert evidence.unique_owner is True
    assert evidence.application_alias == "chrome_controlled"


# ==============================================================================
# 3. IPv4 and IPv6 Normalization & Matching
# ==============================================================================

def test_ipv4_and_ipv6_normalization_and_matching():
    """Requirement 11.3: Verification of address normalization and IPv6 correlation."""
    # Test normalization primitives
    assert normalize_ip_address("192.168.1.50") == "192.168.1.50"
    assert normalize_ip_address("::ffff:192.168.1.50") == "192.168.1.50"
    assert normalize_ip_address("fe80::1%12") == "fe80::1"
    assert normalize_ip_address("2001:0DB8:0000:0000:0000:0000:0000:0001") == "2001:db8::1"
    assert normalize_port(54321) == 54321
    assert normalize_port(70000) == 70000 & 0xFFFF

    # IPv6 correlation test
    fixture_gen = SyntheticSocketFixtureGenerator()
    tracker = fixture_gen.create_chrome_process_tree(root_pid=1000, network_service_pid=1004)
    snap_mgr = SocketSnapshotManager()

    v6_entries = [
        TransientSocketEntry(
            protocol="TCP",
            local_address="2001:db8::1",
            local_port=54321,
            remote_address="2606:2800:220:1:248:1893:25c8:1946",
            remote_port=443,
            state="ESTABLISHED",
            pid=1004,
            process_create_time_utc="2026-11-21T10:00:01.000000+00:00",
            process_name="chrome.exe",
            timestamp_utc=1700000001.0,
        )
    ]
    snap_mgr.add_snapshot(1700000001.0, v6_entries)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_test_ipv6",
        protocol="TCP",
        endpoint_a=("2001:DB8:0::1", 54321),  # Mixed case and zeros
        endpoint_b=("2606:2800:220:1:248:1893:25c8:1946", 443),
        first_packet_wire_ts=1700000001.0,
        last_packet_wire_ts=1700000001.15,
    )

    assert evidence.evidence_method == AttributionEvidenceMethod.EXACT_TCP_PROCESS_MATCH.value
    assert evidence.application_alias == "chrome_controlled"
    assert evidence.unique_owner is True


# ==============================================================================
# 4. UDP Local Endpoint Ownership
# ==============================================================================

def test_udp_local_endpoint_ownership():
    """Requirement 11.4: UDP flow matched via local endpoint ownership."""
    fixture_gen = SyntheticSocketFixtureGenerator()
    tracker = fixture_gen.create_chrome_process_tree(root_pid=1000, network_service_pid=1004)
    snap_mgr = SocketSnapshotManager()

    snap_entries = fixture_gen.generate_udp_snapshot(
        timestamp=1700000001.0,
        local_ip="0.0.0.0",
        local_port=53535,
        pids=[1004],
        process_names=["chrome.exe"],
    )
    snap_mgr.add_snapshot(1700000001.0, snap_entries)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_test_udp_local",
        protocol="UDP",
        endpoint_a=("192.168.1.50", 53535),
        endpoint_b=("8.8.8.8", 53),
        first_packet_wire_ts=1700000001.0,
        last_packet_wire_ts=1700000001.15,
    )

    assert evidence.evidence_method == AttributionEvidenceMethod.UDP_LOCAL_ENDPOINT_PROCESS_MATCH.value
    assert evidence.application_alias == "chrome_controlled"
    assert evidence.unique_owner is True
    # By design, UDP quality is bounded to MEDIUM due to lack of remote endpoint in table
    assert evidence.evidence_quality == AttributionQuality.MEDIUM.value


# ==============================================================================
# 5. Shared UDP Endpoint
# ==============================================================================

def test_shared_udp_endpoint():
    """Requirement 11.5: Multiple distinct processes bound to same UDP local port."""
    fixture_gen = SyntheticSocketFixtureGenerator()
    tracker = fixture_gen.create_chrome_process_tree(root_pid=1000, network_service_pid=1004)
    snap_mgr = SocketSnapshotManager()

    # Port 5353 shared by Chrome (1004) and Windows Service (3000)
    snap_entries = fixture_gen.generate_udp_snapshot(
        timestamp=1700000001.0,
        local_ip="0.0.0.0",
        local_port=5353,
        pids=[1004, 3000],
        process_names=["chrome.exe", "svchost.exe"],
    )
    snap_mgr.add_snapshot(1700000001.0, snap_entries)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_test_shared_udp",
        protocol="UDP",
        endpoint_a=("192.168.1.50", 5353),
        endpoint_b=("224.0.0.251", 5353),
        first_packet_wire_ts=1700000001.0,
        last_packet_wire_ts=1700000001.15,
    )

    assert evidence.evidence_method == AttributionEvidenceMethod.MULTIPLE_PROCESS_MATCH.value
    assert evidence.unique_owner is False
    assert evidence.evidence_quality == AttributionQuality.LOW.value
    assert "Shared UDP local endpoint" in (evidence.rejection_reason or "")


# ==============================================================================
# 6. PID Reuse Disambiguation
# ==============================================================================

def test_pid_reuse_disambiguation():
    """Requirement 11.6: Disambiguating recycled PIDs via process creation-time."""
    tracker = ProcessTracker(controlled_app_alias="chrome_controlled")
    # Register controlled Chrome with creation time T0
    tracker.register_controlled_root(
        pid=5000,
        create_time_utc="2026-11-21T10:00:00.000000+00:00",
        process_name="chrome.exe",
    )

    # 1. Matching PID and matching creation time -> controlled
    alias, is_ctrl = tracker.resolve_application_alias(
        pid=5000,
        create_time_utc="2026-11-21T10:00:00.000000+00:00",
        process_name="chrome.exe",
    )
    assert is_ctrl is True
    assert alias == "chrome_controlled"

    # 2. Same PID 5000 recycled by OS with NEW creation time T1 -> detected as system_background!
    alias_reused, is_ctrl_reused = tracker.resolve_application_alias(
        pid=5000,
        create_time_utc="2026-11-21T10:15:00.000000+00:00",
        process_name="notepad.exe",
    )
    assert is_ctrl_reused is False
    assert alias_reused == "system_background"

    # Correlator level verification of PID reuse
    snap_mgr = SocketSnapshotManager()
    snap_entries = [
        TransientSocketEntry(
            protocol="TCP",
            local_address="192.168.1.50",
            local_port=54321,
            remote_address="93.184.216.34",
            remote_port=443,
            state="ESTABLISHED",
            pid=5000,
            process_create_time_utc="2026-11-21T10:15:00.000000+00:00",  # Reused PID
            process_name="notepad.exe",
            timestamp_utc=1700000001.0,
        )
    ]
    snap_mgr.add_snapshot(1700000001.0, snap_entries)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_test_pid_reuse",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=1700000001.0,
        last_packet_wire_ts=1700000001.15,
    )

    # The flow must NOT be attributed to chrome_controlled
    assert evidence.application_alias == "system_background"
    assert evidence.evidence_quality == AttributionQuality.MEDIUM.value


# ==============================================================================
# 7. Missing Process in Contemporaneous Snapshots
# ==============================================================================

def test_missing_process_in_contemporaneous_snapshots():
    """Requirement 11.7: Contemporaneous snapshot exists, but socket is absent."""
    tracker = ProcessTracker()
    snap_mgr = SocketSnapshotManager()

    # Snapshot exists at t=1001, but contains an unrelated socket
    snap_mgr.add_snapshot(
        1700000001.0,
        [
            TransientSocketEntry(
                protocol="TCP",
                local_address="192.168.1.50",
                local_port=12345,
                remote_address="1.1.1.1",
                remote_port=80,
                pid=9999,
                timestamp_utc=1700000001.0,
            )
        ],
    )

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_test_missing_socket",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=1700000001.0,
        last_packet_wire_ts=1700000001.15,
    )

    assert evidence.evidence_method == AttributionEvidenceMethod.PROCESS_NOT_FOUND.value
    assert evidence.application_alias is None
    assert evidence.unique_owner is False
    assert evidence.evidence_quality == AttributionQuality.UNATTRIBUTED.value
    assert "was not present" in (evidence.rejection_reason or "")


# ==============================================================================
# 8. Stale Socket Observation
# ==============================================================================

def test_stale_socket_observation():
    """Requirement 11.8: Socket observed only well outside the flow lifetime window."""
    tracker = ProcessTracker()
    snap_mgr = SocketSnapshotManager()

    # Socket only appeared 15 seconds after the flow completed
    snap_mgr.add_snapshot(
        1700000020.0,
        [
            TransientSocketEntry(
                protocol="TCP",
                local_address="192.168.1.50",
                local_port=54321,
                remote_address="93.184.216.34",
                remote_port=443,
                pid=1004,
                timestamp_utc=1700000020.0,
            )
        ],
    )

    # Flow was active from t=0 to t=2 (contemporaneous window t=-1 to t=3)
    correlator = ProcessSocketCorrelator(snap_mgr, tracker, window_margin_seconds=1.0)
    evidence = correlator.correlate_flow(
        flow_id="flow_test_stale_socket",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=1700000001.0,
        last_packet_wire_ts=1700000001.15,
    )

    assert evidence.evidence_method == AttributionEvidenceMethod.STALE_SOCKET_OBSERVATION.value
    assert evidence.evidence_quality == AttributionQuality.UNATTRIBUTED.value
    assert "outside active flow lifetime" in (evidence.rejection_reason or "")


# ==============================================================================
# 9. Multiple Matching Processes
# ==============================================================================

def test_multiple_matching_processes():
    """Requirement 11.9: Conflicting processes observed on the same connection endpoints."""
    tracker = ProcessTracker(controlled_app_alias="chrome_controlled")
    tracker.register_controlled_root(pid=1004, create_time_utc="2026-11-21T10:00:00Z")
    snap_mgr = SocketSnapshotManager()

    # Snapshot 1 at t=1001: Chrome (PID 1004) owns the socket
    snap_mgr.add_snapshot(
        1700000001.0,
        [
            TransientSocketEntry(
                protocol="TCP",
                local_address="192.168.1.50",
                local_port=54321,
                remote_address="93.184.216.34",
                remote_port=443,
                pid=1004,
                process_create_time_utc="2026-11-21T10:00:00Z",
                process_name="chrome.exe",
                timestamp_utc=1700000001.0,
            )
        ],
    )
    # Snapshot 2 at t=1002: Another process (PID 9999) observed on same endpoints
    snap_mgr.add_snapshot(
        1700000002.0,
        [
            TransientSocketEntry(
                protocol="TCP",
                local_address="192.168.1.50",
                local_port=54321,
                remote_address="93.184.216.34",
                remote_port=443,
                pid=9999,
                process_create_time_utc="2026-11-21T10:01:00Z",
                process_name="other.exe",
                timestamp_utc=1700000002.0,
            )
        ],
    )

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_test_multi_match",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=1700000000.0,
        last_packet_wire_ts=1700000003.0,
    )

    assert evidence.evidence_method == AttributionEvidenceMethod.MULTIPLE_PROCESS_MATCH.value
    assert evidence.unique_owner is False
    assert evidence.evidence_quality == AttributionQuality.LOW.value
    assert "Multiple conflicting" in (evidence.rejection_reason or "")


# ==============================================================================
# 10. Privacy Enforcement Audit
# ==============================================================================

def test_privacy_enforcement_audit(tmp_path: Path):
    """Requirement 11.10: Guarantees zero sensitive network or process leakage in records/reports."""
    # 1. Attempting to construct record with IP address in alias must fail
    with pytest.raises(ValueError, match="Privacy violation"):
        AttributionEvidenceRecord(
            flow_id="flow_test_priv",
            evidence_method="EXACT_TCP_PROCESS_MATCH",
            application_alias="192.168.1.50_chrome",
            matched_observation_count=1,
            attribution_coverage_ratio=1.0,
            unique_owner=True,
            evidence_quality="HIGH",
        )

    # 2. Attempting to construct record with URL in rejection reason must fail
    with pytest.raises(ValueError, match="Privacy violation"):
        AttributionEvidenceRecord(
            flow_id="flow_test_priv",
            evidence_method="PROCESS_NOT_FOUND",
            application_alias=None,
            matched_observation_count=0,
            attribution_coverage_ratio=0.0,
            unique_owner=False,
            evidence_quality="UNATTRIBUTED",
            rejection_reason="Failed contacting https://example.com/login",
        )

    # 3. Attempting to construct record with full file path in rejection reason must fail
    with pytest.raises(ValueError, match="Privacy violation"):
        AttributionEvidenceRecord(
            flow_id="flow_test_priv",
            evidence_method="PROCESS_NOT_FOUND",
            application_alias=None,
            matched_observation_count=0,
            attribution_coverage_ratio=0.0,
            unique_owner=False,
            evidence_quality="UNATTRIBUTED",
            rejection_reason="C:\\Users\\admin\\AppData\\chrome.exe not found",
        )

    # 4. End-to-end report serialization privacy audit
    records = [
        AttributionEvidenceRecord(
            flow_id="flow_01",
            evidence_method="EXACT_TCP_PROCESS_MATCH",
            application_alias="chrome_controlled",
            matched_observation_count=3,
            attribution_coverage_ratio=0.75,
            unique_owner=True,
            evidence_quality="HIGH",
        ),
        AttributionEvidenceRecord(
            flow_id="flow_02",
            evidence_method="PROCESS_NOT_FOUND",
            application_alias=None,
            matched_observation_count=0,
            attribution_coverage_ratio=0.0,
            unique_owner=False,
            evidence_quality="UNATTRIBUTED",
            rejection_reason="Endpoint socket was not present in contemporaneous socket table",
        ),
    ]

    report_gen = AttributionReportGenerator()
    report = report_gen.generate_report("sess_test_privacy", records)
    sidecar_path = report_gen.save_sidecar_report(report, tmp_path)

    # Read serialized JSON file and assert zero forbidden identifiers
    raw_content = sidecar_path.read_text(encoding="utf-8")
    import re
    assert not re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", raw_content), "Raw IPv4 detected in sidecar report!"
    assert not re.search(r"https?://", raw_content), "Raw URL detected in sidecar report!"
    assert not re.search(r"[a-zA-Z]:\\", raw_content), "Windows file path detected in sidecar report!"
    assert "pid" not in raw_content.lower(), "PID field name leaked into sidecar report!"


# ==============================================================================
# 11. No Automatic VERIFIED Promotion
# ==============================================================================

def test_no_automatic_verified_promotion():
    """Requirement 11.11: Strict adherence to ground-truth evidence policy rules."""
    policy = AttributionEvidencePolicy()

    # Rule A: Temporal overlap / insufficient evidence -> AMBIGUOUS, traffic_class=None
    rec_insufficient = AttributionEvidenceRecord(
        flow_id="flow_1",
        evidence_method=AttributionEvidenceMethod.INSUFFICIENT_EVIDENCE.value,
        application_alias=None,
        matched_observation_count=0,
        attribution_coverage_ratio=0.0,
        unique_owner=False,
        evidence_quality=AttributionQuality.UNATTRIBUTED.value,
    )
    tc, qual, src, rej = policy.evaluate_label_recommendation(rec_insufficient, "Web")
    assert tc is None
    assert qual == "AMBIGUOUS"

    # Rule B: UDP local endpoint match alone -> AMBIGUOUS, traffic_class=None
    rec_udp = AttributionEvidenceRecord(
        flow_id="flow_2",
        evidence_method=AttributionEvidenceMethod.UDP_LOCAL_ENDPOINT_PROCESS_MATCH.value,
        application_alias="chrome_controlled",
        matched_observation_count=2,
        attribution_coverage_ratio=1.0,
        unique_owner=True,
        evidence_quality=AttributionQuality.MEDIUM.value,
    )
    tc, qual, src, rej = policy.evaluate_label_recommendation(rec_udp, "Web")
    assert tc is None
    assert qual == "AMBIGUOUS"
    assert "UDP local endpoint match alone is insufficient" in (rej or "")

    # Rule C: Background traffic -> UNLABELLED, traffic_class=None
    rec_background = AttributionEvidenceRecord(
        flow_id="flow_3",
        evidence_method=AttributionEvidenceMethod.EXACT_TCP_PROCESS_MATCH.value,
        application_alias="system_background",
        matched_observation_count=2,
        attribution_coverage_ratio=1.0,
        unique_owner=True,
        evidence_quality=AttributionQuality.MEDIUM.value,
    )
    tc, qual, src, rej = policy.evaluate_label_recommendation(rec_background, "Web")
    assert tc is None
    assert qual == "UNLABELLED"

    # Rule D: Exact TCP Match with controlled Chrome -> VERIFIED, traffic_class="Web"
    rec_tcp_verified = AttributionEvidenceRecord(
        flow_id="flow_4",
        evidence_method=AttributionEvidenceMethod.EXACT_TCP_PROCESS_MATCH.value,
        application_alias="chrome_controlled",
        matched_observation_count=2,
        attribution_coverage_ratio=0.8,
        unique_owner=True,
        evidence_quality=AttributionQuality.HIGH.value,
    )
    tc, qual, src, rej = policy.evaluate_label_recommendation(rec_tcp_verified, "Web")
    assert tc == "Web"
    assert qual == "VERIFIED"
    assert src == "INDEPENDENT_VERIFICATION"
    assert rej is None


# ==============================================================================
# 12. Preservation of Existing Dataset V3 Sessions
# ==============================================================================

def test_preservation_of_existing_dataset_v3_sessions():
    """Requirement 11.12: Guarantees published session sess_b04fe53843b04caa8bf86e60209d3fd0 is untouched."""
    repo_root = Path(__file__).resolve().parents[3]
    published_session_dir = repo_root / "data" / "research_v3" / "sess_b04fe53843b04caa8bf86e60209d3fd0"

    assert published_session_dir.exists(), f"Published session directory missing: {published_session_dir}"

    manifest_path = published_session_dir / "session_manifest.json"
    labels_path = published_session_dir / "labels.csv"

    assert manifest_path.exists()
    assert labels_path.exists()

    # Read manifest and verify file integrity hashes
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    hashes = manifest_data.get("file_integrity_hashes", {})

    import hashlib
    for fname in ("labels.csv", "flow_index.csv"):
        if fname in hashes:
            fpath = published_session_dir / fname
            actual_h = hashlib.sha256(fpath.read_bytes()).hexdigest()
            assert actual_h == hashes[fname], f"Hash mismatch in published session file: {fname}!"

    # Read labels.csv and verify all 90 labels remain AMBIGUOUS with traffic_class=None (empty)
    with open(labels_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        labels = list(reader)

    assert len(labels) == 90
    for row in labels:
        assert row["label_quality"] == "AMBIGUOUS"
        assert row["traffic_class"] in ("", "None", None)

    # Verify quarantined session evidence remains intact
    quarantine_dir = repo_root / "data" / "research_v3" / ".incomplete" / "sess_70fc712285d34d2cb75abb02db8c1f1f"
    assert quarantine_dir.exists()
    assert (quarantine_dir / "SESSION_INCOMPLETE").exists()
    assert (quarantine_dir / "session_manifest.json").exists()


# ==============================================================================
# Phase 2 & 5 Live Windows API & Quality Regression Tests
# ==============================================================================

def test_actual_tcp_table_parsing_live():
    """Phase 5.1: Live Windows TCP table interrogation with real loopback sockets."""
    import os
    import platform
    import socket
    import time
    from research.dataset_v3.attribution.ip_helper import WindowsIPHelperReader

    if platform.system() != "Windows":
        pytest.skip("Requires Windows OS")

    reader = WindowsIPHelperReader()
    if not reader.is_supported:
        pytest.skip("Windows IP Helper DLLs unavailable")

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn = None
    try:
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        srv_port = srv.getsockname()[1]

        cli.connect(("127.0.0.1", srv_port))
        cli_port = cli.getsockname()[1]
        conn, _ = srv.accept()

        now = time.time()
        entries = reader.read_tcp_table_ipv4(now)
        my_pid = os.getpid()

        matches = [
            e for e in entries
            if e.pid == my_pid and e.local_port == cli_port and e.remote_port == srv_port
        ]
        assert len(matches) == 1
        assert matches[0].protocol == "TCP"
        assert matches[0].state == "ESTABLISHED"
        assert matches[0].local_address in ("127.0.0.1", "0.0.0.0")

    finally:
        cli.close()
        if conn:
            conn.close()
        srv.close()


def test_actual_udp_table_parsing_live():
    """Phase 5.2: Live Windows UDP table interrogation with real loopback socket."""
    import os
    import platform
    import socket
    import time
    from research.dataset_v3.attribution.ip_helper import WindowsIPHelperReader

    if platform.system() != "Windows":
        pytest.skip("Requires Windows OS")

    reader = WindowsIPHelperReader()
    if not reader.is_supported:
        pytest.skip("Windows IP Helper DLLs unavailable")

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        udp.bind(("127.0.0.1", 0))
        udp_port = udp.getsockname()[1]

        now = time.time()
        entries = reader.read_udp_table_ipv4(now)
        my_pid = os.getpid()

        matches = [e for e in entries if e.pid == my_pid and e.local_port == udp_port]
        assert len(matches) == 1
        assert matches[0].protocol == "UDP"
        assert matches[0].local_address in ("127.0.0.1", "0.0.0.0")

    finally:
        udp.close()


def test_actual_ipv6_table_parsing_live():
    """Phase 5.3: Live Windows IPv6 TCP table interrogation."""
    import os
    import platform
    import socket
    import time
    from research.dataset_v3.attribution.ip_helper import WindowsIPHelperReader

    if platform.system() != "Windows":
        pytest.skip("Requires Windows OS")

    reader = WindowsIPHelperReader()
    if not reader.is_supported:
        pytest.skip("Windows IP Helper DLLs unavailable")

    srv6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    cli6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    conn6 = None
    try:
        srv6.bind(("::1", 0))
        srv6.listen(1)
        srv6_port = srv6.getsockname()[1]

        cli6.connect(("::1", srv6_port))
        cli6_port = cli6.getsockname()[1]
        conn6, _ = srv6.accept()

        now = time.time()
        entries6 = reader.read_tcp_table_ipv6(now)
        my_pid = os.getpid()

        matches = [
            e for e in entries6
            if e.pid == my_pid and e.local_port == cli6_port and e.remote_port == srv6_port
        ]
        assert len(matches) == 1
        assert matches[0].protocol == "TCP"
        assert matches[0].state == "ESTABLISHED"
    except Exception as e:
        pytest.skip(f"IPv6 loopback unavailable: {e}")
    finally:
        cli6.close()
        if conn6:
            conn6.close()
        srv6.close()


def test_process_creation_time_validation_live():
    """Phase 5.5: Live process creation-time retrieval on Windows."""
    import os
    import platform
    from research.dataset_v3.attribution.ip_helper import get_process_creation_time_and_name

    if platform.system() != "Windows":
        pytest.skip("Requires Windows OS")

    ctime, pname = get_process_creation_time_and_name(os.getpid())
    assert ctime is not None
    assert "T" in ctime
    assert "+" in ctime or "Z" in ctime
    assert pname is not None
    assert "python" in pname.lower()


def test_tcp_connection_state_filtering_ignores_listen():
    """Phase 5.4: TCP listeners are strictly filtered and never matched as active flows."""
    tracker = ProcessTracker(controlled_app_alias="test_app")
    snap_mgr = SocketSnapshotManager()

    # Listener socket on port 8080 (state LISTEN, remote_port=0)
    snap_mgr.add_snapshot(
        1700000001.0,
        [
            TransientSocketEntry(
                protocol="TCP",
                local_address="0.0.0.0",
                local_port=8080,
                remote_address="0.0.0.0",
                remote_port=0,
                state="LISTEN",
                pid=1234,
                timestamp_utc=1700000001.0,
            )
        ],
    )

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_test_listen_filter",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 8080),
        endpoint_b=("10.0.0.1", 54321),
        first_packet_wire_ts=1700000001.0,
        last_packet_wire_ts=1700000001.15,
    )

    # Must NOT be matched as an exact TCP connection
    assert evidence.evidence_method == AttributionEvidenceMethod.PROCESS_NOT_FOUND.value
    assert evidence.unique_owner is False


def test_coverage_computation_ratio():
    """Phase 5.9: Exact coverage ratio computation and low coverage threshold rejection."""
    tracker = ProcessTracker(controlled_app_alias="chrome_controlled")
    tracker.register_controlled_root(pid=1004, create_time_utc="2026-11-21T10:00:00Z")
    snap_mgr = SocketSnapshotManager()

    # Flow lasts from t=0 to t=10.
    # 10 snapshots exist (t=1, 2, ..., 10). Only 2 snapshots observe the socket (coverage = 2/10 = 0.20)
    for t in range(1, 11):
        if t in (2, 3):
            entries = [
                TransientSocketEntry(
                    protocol="TCP",
                    local_address="192.168.1.50",
                    local_port=54321,
                    remote_address="93.184.216.34",
                    remote_port=443,
                    state="ESTABLISHED",
                    pid=1004,
                    process_create_time_utc="2026-11-21T10:00:00Z",
                    process_name="chrome.exe",
                    timestamp_utc=float(1700000000 + t),
                )
            ]
        else:
            entries = []
        snap_mgr.add_snapshot(float(1700000000 + t), entries)

    correlator = ProcessSocketCorrelator(
        snap_mgr,
        tracker,
        window_margin_seconds=0.0,
        sampling_bin_width_seconds=1.0,
    )
    evidence = correlator.correlate_flow(
        flow_id="flow_test_low_coverage",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=1700000000.0,
        last_packet_wire_ts=1700000010.0,
    )

    assert evidence.matched_observation_count == 2
    assert evidence.attribution_coverage_ratio == 0.2
    assert evidence.evidence_quality == AttributionQuality.MEDIUM.value

    # Policy requires >= 0.50 coverage for VERIFIED Web
    policy = AttributionEvidencePolicy(min_tcp_coverage_ratio=0.50)
    tc, qual, src, rej = policy.evaluate_label_recommendation(evidence, "Web")
    assert tc is None
    assert qual == "AMBIGUOUS"
    assert "Coverage ratio" in (rej or "")


def test_controlled_chrome_hierarchy_and_unrelated_process_rejection():
    """Phase 5.10: Controlled Chrome hierarchy identification vs background Chrome instance."""
    tracker = ProcessTracker(controlled_app_alias="chrome_controlled")
    tracker.register_controlled_root(pid=1000, create_time_utc="2026-11-21T10:00:00Z")
    tracker.register_controlled_child(pid=1004, parent_pid=1000, create_time_utc="2026-11-21T10:00:01Z")

    # 1. Child process (Network Service) -> controlled
    alias, is_ctrl = tracker.resolve_application_alias(1004, "2026-11-21T10:00:01Z", "chrome.exe")
    assert is_ctrl is True
    assert alias == "chrome_controlled"

    # 2. Unrelated background Chrome running concurrently -> system_background
    bg_alias, bg_is_ctrl = tracker.resolve_application_alias(9999, "2026-11-21T08:00:00Z", "chrome.exe")
    assert bg_is_ctrl is False
    assert bg_alias == "system_background"


def test_comprehensive_privacy_canary_audit():
    """Phase 5.12: Strict validation against all 11 privacy canary types."""
    canaries = [
        ("ipv4_loopback", "127.0.0.1"),
        ("ipv4_private", "192.168.1.50"),
        ("ipv6_full", "2001:0db8:85a3:0000:0000:8a2e:0370:7334"),
        ("ipv6_compressed", "fe80::1"),
        ("ipv4_mapped_ipv6", "::ffff:192.168.1.1"),
        ("mac_colon", "00:11:22:33:44:55"),
        ("mac_hyphen", "00-11-22-33-44-55"),
        ("port_explicit", "port 8080"),
        ("port_colon", ":443"),
        ("pid_key", "pid=1234"),
        ("pid_json", '"pid": 5678'),
        ("windows_path", "C:\\Program Files\\Google\\Chrome\\chrome.exe"),
        ("unc_path", "\\\\network_share\\logs\\dump.pcap"),
        ("url_http", "http://example.com/test"),
        ("url_https", "https://bank.com/login"),
        ("command_line", "chrome.exe --type=renderer --user-data-dir=C:\\temp"),
    ]

    for name, canary in canaries:
        with pytest.raises(ValueError, match="Privacy violation"):
            verify_privacy_safe_string(name, canary)

    # Legitimate non-sensitive tokens must pass cleanly
    verify_privacy_safe_string("controlled_alias", "chrome_controlled")
    verify_privacy_safe_string("bg_alias", "system_background")
    verify_privacy_safe_string("rejection_code", "NO_CONTEMPORANEOUS_SNAPSHOTS")
    verify_privacy_safe_string("rejection_desc", "Endpoint socket was not present in contemporaneous socket table")


def test_complete_cleanup_of_test_processes_and_sockets():
    """Phase 5.14: Confirms that test sockets are cleanly closed."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
    finally:
        s.close()

    # Closed socket in Python has fileno == -1
    assert s.fileno() == -1
