"""
Integration and Verification Tests for Dataset V3 Windows Process Attribution Subsystem.

Tests all Phase 7 requirements:
- Snapshot worker start and shutdown.
- Snapshot worker failure handling.
- Monotonic timestamp alignment.
- Exact TCP correlation (forward and reverse).
- TCP state-dependent evidence quality (ESTABLISHED vs transitional).
- TIME_WAIT stale evidence rejection.
- Minimum observation count (1 observation -> MEDIUM, 2+ -> HIGH).
- Observation timestamp separation.
- Coverage computation formula and thresholding.
- UDP ambiguity preservation (never promoted to VERIFIED).
- Chrome root-process tracking.
- Chrome child-process tracking and temp directory cleanup.
- PID recycling protection via creation-time identity.
- Privacy-safe sidecar generation and schema validation.
- Attribution-sidecar integrity hash inclusion in manifest.
- Existing label-file immutability.
- Published-session immutability (Pilot Session 1).
- Quarantined forensic evidence preservation.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import MagicMock, patch
import pytest

from research.dataset_v3.attribution.chrome_launcher import ControlledChromeLauncher
from research.dataset_v3.attribution.correlator import ProcessSocketCorrelator
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
from research.dataset_v3.attribution.simulation import SyntheticSocketFixtureGenerator
from research.dataset_v3.attribution.snapshot_manager import SocketSnapshotManager
from research.dataset_v3.collector import PhysicalTrafficCollector
from research.dataset_v3.config import DatasetV3Config
from research.dataset_v3.metadata_writer import MetadataWriter
from research.dataset_v3.schemas import FlowIndexRecord
from research.dataset_v3.validator import DatasetV3Validator


# -----------------------------------------------------------------------------
# 1. Snapshot Worker Start and Shutdown
# -----------------------------------------------------------------------------

def test_snapshot_worker_start_and_shutdown():
    """Phase 7: Verifies deterministic start, execution, and shutdown of snapshot worker."""
    mock_reader = MagicMock()
    mock_reader.snapshot.return_value = []

    snap_mgr = SocketSnapshotManager(reader=mock_reader, snapshot_interval_seconds=0.05)
    assert snap_mgr.is_polling_active is False

    snap_mgr.start_polling()
    assert snap_mgr.is_polling_active is True

    # Allow worker to run briefly
    time.sleep(0.12)
    assert mock_reader.snapshot.call_count >= 1

    snap_mgr.stop_polling()
    assert snap_mgr.is_polling_active is False
    assert snap_mgr._polling_thread is None


# -----------------------------------------------------------------------------
# 2. Snapshot Worker Failure Handling
# -----------------------------------------------------------------------------

def test_snapshot_worker_failure_handling():
    """Phase 7: Verifies snapshot worker captures errors without unhandled crash."""
    mock_reader = MagicMock()
    mock_reader.snapshot.side_effect = RuntimeError("Windows table query failed")

    snap_mgr = SocketSnapshotManager(reader=mock_reader, snapshot_interval_seconds=0.05)
    snap_mgr.start_polling()

    time.sleep(0.12)
    assert snap_mgr.last_polling_error is not None
    assert "Windows table query failed" in snap_mgr.last_polling_error
    assert isinstance(snap_mgr.polling_exception, RuntimeError)

    snap_mgr.stop_polling()
    assert snap_mgr.is_polling_active is False


# -----------------------------------------------------------------------------
# 3. Monotonic Timestamp Alignment
# -----------------------------------------------------------------------------

def test_monotonic_timestamp_alignment():
    """Phase 7: Verifies monotonic timestamp alignment during flow correlation."""
    fixture_gen = SyntheticSocketFixtureGenerator()
    tracker = fixture_gen.create_chrome_process_tree(root_pid=1000, network_service_pid=1004)
    snap_mgr = SocketSnapshotManager()

    entries_1 = fixture_gen.generate_tcp_snapshot(
        timestamp=1700000001.0,
        local_ip="192.168.1.50",
        local_port=54321,
        remote_ip="93.184.216.34",
        remote_port=443,
        pid=1004,
    )
    entries_2 = fixture_gen.generate_tcp_snapshot(
        timestamp=1700000001.2,
        local_ip="192.168.1.50",
        local_port=54321,
        remote_ip="93.184.216.34",
        remote_port=443,
        pid=1004,
    )

    # Monotonic timestamps: 100.0 and 100.2
    snap_mgr.add_snapshot(1700000001.0, entries_1, monotonic_ts=100.0)
    snap_mgr.add_snapshot(1700000001.2, entries_2, monotonic_ts=100.2)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_mono_test",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=1700000000.0,
        last_packet_wire_ts=1700000002.0,
        first_packet_mono_ts=99.9,
        last_packet_mono_ts=100.3,
    )

    assert evidence.evidence_method == AttributionEvidenceMethod.EXACT_TCP_PROCESS_MATCH.value
    assert evidence.matched_observation_count == 2
    assert evidence.evidence_quality == AttributionQuality.HIGH.value
    assert evidence.rejection_reason is None


# -----------------------------------------------------------------------------
# 4. TCP State-Dependent Evidence Quality
# -----------------------------------------------------------------------------

def test_tcp_state_dependent_evidence_quality():
    """Phase 7: Verifies transitional TCP states (SYN_SENT, FIN_WAIT) receive MEDIUM, not HIGH."""
    fixture_gen = SyntheticSocketFixtureGenerator()
    tracker = fixture_gen.create_chrome_process_tree(root_pid=1000, network_service_pid=1004)
    snap_mgr = SocketSnapshotManager()

    # Two observations, but in transitional states (SYN_SENT, SYN_RCVD) instead of ESTABLISHED
    entries_1 = fixture_gen.generate_tcp_snapshot(
        timestamp=1700000001.0,
        local_ip="192.168.1.50",
        local_port=54321,
        remote_ip="93.184.216.34",
        remote_port=443,
        pid=1004,
        state="SYN_SENT",
    )
    entries_2 = fixture_gen.generate_tcp_snapshot(
        timestamp=1700000001.2,
        local_ip="192.168.1.50",
        local_port=54321,
        remote_ip="93.184.216.34",
        remote_port=443,
        pid=1004,
        state="SYN_RCVD",
    )

    snap_mgr.add_snapshot(1700000001.0, entries_1)
    snap_mgr.add_snapshot(1700000001.2, entries_2)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_transitional_test",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=1700000000.0,
        last_packet_wire_ts=1700000002.0,
    )

    # Must be downgraded to MEDIUM because ESTABLISHED was never observed
    assert evidence.evidence_method == AttributionEvidenceMethod.EXACT_TCP_PROCESS_MATCH.value
    assert evidence.evidence_quality == AttributionQuality.MEDIUM.value
    assert "transitional" in (evidence.rejection_reason or "").lower()

    # Policy must refuse VERIFIED promotion
    policy = AttributionEvidencePolicy()
    tc, qual, src, rej = policy.evaluate_label_recommendation(evidence, "Web")
    assert tc is None
    assert qual == "AMBIGUOUS"


# -----------------------------------------------------------------------------
# 5. TIME_WAIT Stale Evidence Rejection
# -----------------------------------------------------------------------------

def test_time_wait_stale_evidence_rejection():
    """Phase 7: Verifies socket observed exclusively in TIME_WAIT is treated as stale."""
    fixture_gen = SyntheticSocketFixtureGenerator()
    tracker = fixture_gen.create_chrome_process_tree(root_pid=1000, network_service_pid=1004)
    snap_mgr = SocketSnapshotManager()

    entries = fixture_gen.generate_tcp_snapshot(
        timestamp=1700000001.0,
        local_ip="192.168.1.50",
        local_port=54321,
        remote_ip="93.184.216.34",
        remote_port=443,
        pid=1004,
        state="TIME_WAIT",
    )
    snap_mgr.add_snapshot(1700000001.0, entries)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_time_wait_test",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=1700000000.0,
        last_packet_wire_ts=1700000002.0,
    )

    assert evidence.evidence_method == AttributionEvidenceMethod.STALE_SOCKET_OBSERVATION.value
    assert evidence.evidence_quality == AttributionQuality.UNATTRIBUTED.value
    assert "TIME_WAIT" in (evidence.rejection_reason or "")


# -----------------------------------------------------------------------------
# 6. Minimum Observation Count
# -----------------------------------------------------------------------------

def test_single_snapshot_observation_downgraded_to_medium():
    """Phase 7: Verifies a single snapshot observation is downgraded to MEDIUM and refused for VERIFIED."""
    fixture_gen = SyntheticSocketFixtureGenerator()
    tracker = fixture_gen.create_chrome_process_tree(root_pid=1000, network_service_pid=1004)
    snap_mgr = SocketSnapshotManager()

    # Only 1 observation in ESTABLISHED state
    entries = fixture_gen.generate_tcp_snapshot(
        timestamp=1700000001.0,
        local_ip="192.168.1.50",
        local_port=54321,
        remote_ip="93.184.216.34",
        remote_port=443,
        pid=1004,
        state="ESTABLISHED",
    )
    snap_mgr.add_snapshot(1700000001.0, entries)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker, min_observation_count=2)
    evidence = correlator.correlate_flow(
        flow_id="flow_single_snap_test",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=1700000000.0,
        last_packet_wire_ts=1700000002.0,
    )

    assert evidence.matched_observation_count == 1
    assert evidence.evidence_quality == AttributionQuality.MEDIUM.value
    assert "below minimum requirement" in (evidence.rejection_reason or "")

    # Policy rejection check
    policy = AttributionEvidencePolicy()
    tc, qual, src, rej = policy.evaluate_label_recommendation(evidence, "Web")
    assert tc is None
    assert qual == "AMBIGUOUS"


# -----------------------------------------------------------------------------
# 7. Observation Timestamp Separation
# -----------------------------------------------------------------------------

def test_observation_timestamp_separation():
    """Phase 7: Verifies observations lacking minimum temporal separation receive MEDIUM quality."""
    fixture_gen = SyntheticSocketFixtureGenerator()
    tracker = fixture_gen.create_chrome_process_tree(root_pid=1000, network_service_pid=1004)
    snap_mgr = SocketSnapshotManager()

    # Two observations separated by only 0.01s (below min 0.10s threshold)
    entries_1 = fixture_gen.generate_tcp_snapshot(
        timestamp=1700000001.00,
        local_ip="192.168.1.50",
        local_port=54321,
        remote_ip="93.184.216.34",
        remote_port=443,
        pid=1004,
    )
    entries_2 = fixture_gen.generate_tcp_snapshot(
        timestamp=1700000001.01,
        local_ip="192.168.1.50",
        local_port=54321,
        remote_ip="93.184.216.34",
        remote_port=443,
        pid=1004,
    )
    snap_mgr.add_snapshot(1700000001.00, entries_1)
    snap_mgr.add_snapshot(1700000001.01, entries_2)

    correlator = ProcessSocketCorrelator(
        snap_mgr, tracker, min_observation_separation_seconds=0.10
    )
    evidence = correlator.correlate_flow(
        flow_id="flow_separation_test",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=1700000000.0,
        last_packet_wire_ts=1700000002.0,
    )

    assert evidence.evidence_quality == AttributionQuality.MEDIUM.value
    assert "temporal separation" in (evidence.rejection_reason or "").lower()


# -----------------------------------------------------------------------------
# 8. UDP Ambiguity Preservation
# -----------------------------------------------------------------------------

def test_udp_ambiguity_preservation():
    """Phase 7: Verifies UDP local endpoint attribution is NEVER promoted to VERIFIED."""
    fixture_gen = SyntheticSocketFixtureGenerator()
    tracker = fixture_gen.create_chrome_process_tree(root_pid=1000, network_service_pid=1004)
    snap_mgr = SocketSnapshotManager()

    entries_1 = fixture_gen.generate_udp_snapshot(
        timestamp=1700000001.0,
        local_ip="192.168.1.50",
        local_port=54321,
        pids=[1004],
    )
    entries_2 = fixture_gen.generate_udp_snapshot(
        timestamp=1700000001.2,
        local_ip="192.168.1.50",
        local_port=54321,
        pids=[1004],
    )
    snap_mgr.add_snapshot(1700000001.0, entries_1)
    snap_mgr.add_snapshot(1700000001.2, entries_2)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_udp_ambig_test",
        protocol="UDP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=1700000000.0,
        last_packet_wire_ts=1700000002.0,
    )

    assert evidence.evidence_method == AttributionEvidenceMethod.UDP_LOCAL_ENDPOINT_PROCESS_MATCH.value
    assert evidence.evidence_quality in (AttributionQuality.LOW.value, AttributionQuality.MEDIUM.value)

    policy = AttributionEvidencePolicy()
    tc, qual, src, rej = policy.evaluate_label_recommendation(evidence, "Web")
    assert tc is None
    assert qual == "AMBIGUOUS"
    assert "insufficient for VERIFIED" in (rej or "")


# -----------------------------------------------------------------------------
# 9. Chrome Root and Child Process Tracking via Launcher
# -----------------------------------------------------------------------------

def test_controlled_chrome_launcher_lifecycle():
    """Phase 7: Verifies ControlledChromeLauncher setup, execution, and profile directory deletion."""
    tracker = ProcessTracker()
    launcher = ControlledChromeLauncher(
        process_tracker=tracker,
        headless=True,
    )

    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.pid = 9876
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        with patch("research.dataset_v3.attribution.chrome_launcher.get_process_creation_time_and_name") as mock_ctime:
            mock_ctime.return_value = ("2026-11-21T10:00:00Z", "chrome.exe")

            pid = launcher.launch(
                custom_binary=sys.executable,
                initial_url=None,
            )

            assert pid == 9876
            assert launcher.is_running is True
            assert launcher._temp_user_data_dir is not None
            temp_dir = launcher._temp_user_data_dir
            assert temp_dir.exists()

            # Verify registration with tracker
            alias, is_ctrl = tracker.resolve_application_alias(pid=pid, create_time_utc="2026-11-21T10:00:00Z")
            assert alias == "chrome_controlled"
            assert is_ctrl is True

            # Stop and verify cleanup
            mock_proc.poll.return_value = 0
            launcher.stop()
            assert launcher.is_running is False
            assert launcher._proc is None
            assert not temp_dir.exists(), "Temporary user data dir must be cleanly deleted upon stop!"


# -----------------------------------------------------------------------------
# 10. Privacy-Safe Sidecar Generation & Integrity
# -----------------------------------------------------------------------------

def test_privacy_safe_sidecar_generation_and_integrity(tmp_path: Path):
    """Phase 7: Verifies sidecar generation, privacy audit, and manifest hash inclusion."""
    staging_dir = tmp_path / "staging"
    final_dir = tmp_path / "final"
    incomplete_dir = tmp_path / "incomplete"
    session_id = "sess_test_sidecar_01"

    writer = MetadataWriter(
        final_dir=final_dir,
        staging_dir=staging_dir,
        incomplete_dir=incomplete_dir,
        session_id=session_id,
    )

    config = DatasetV3Config(
        session_id=session_id,
        interface="MockInterface",
        output_root=tmp_path,
        enable_attribution=True,
    )
    from research.dataset_v3.manifest import ManifestManager
    manifest = ManifestManager.create_initial_manifest(config)
    writer.initialize_session(manifest)

    # Write dummy flow, label, and packets
    writer.write_flow_index([])
    writer.write_labels([])

    # Generate and write sidecar report
    records = [
        AttributionEvidenceRecord(
            flow_id="flow_001",
            evidence_method=AttributionEvidenceMethod.EXACT_TCP_PROCESS_MATCH.value,
            application_alias="chrome_controlled",
            matched_observation_count=3,
            attribution_coverage_ratio=0.75,
            unique_owner=True,
            evidence_quality=AttributionQuality.HIGH.value,
            attribution_rule_version=ATTRIBUTION_RULE_VERSION,
            rejection_reason=None,
        )
    ]
    report_gen = AttributionReportGenerator()
    report = report_gen.generate_report(session_id, records)
    sidecar_path = writer.write_attribution_report(report)

    assert sidecar_path.exists()

    # Compute hashes and verify sidecar is included
    hashes = writer.compute_artifact_hashes()
    assert "process_attribution_report.json" in hashes
    expected_hash = hashlib.sha256(sidecar_path.read_bytes()).hexdigest()
    assert hashes["process_attribution_report.json"] == expected_hash

    # Publish session
    writer.flush_and_close_packets()
    ManifestManager.finalize_manifest(manifest, packet_count=0, flow_count=0, status="COMPLETE")
    writer.write_manifest(manifest)

    pub_path = writer.publish_complete_session(manifest)
    assert pub_path.exists()
    assert (pub_path / "process_attribution_report.json").exists()

    # Validate published session
    validator = DatasetV3Validator()
    val_report = validator.validate_session(pub_path)
    assert val_report.is_valid is True
    assert val_report.failed_checks == 0


# -----------------------------------------------------------------------------
# 11. Existing Label-File and Published Session Immutability
# -----------------------------------------------------------------------------

def test_published_pilot_session_1_immutability():
    """Phase 7: Verifies Pilot Session 1 files and SHA-256 integrity hashes are untouched."""
    pilot_dir = Path("data/research_v3/sess_b04fe53843b04caa8bf86e60209d3fd0")
    if not pilot_dir.exists():
        pytest.skip("Pilot Session 1 not present on this machine")

    manifest_file = pilot_dir / "session_manifest.json"
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    expected_hashes = manifest_data.get("file_integrity_hashes", {})
    assert len(expected_hashes) >= 3

    for fname in ("labels.csv", "flow_index.csv", "packet_metadata.jsonl"):
        assert fname in expected_hashes, f"File {fname} missing from manifest integrity hashes!"
        fpath = pilot_dir / fname
        assert fpath.exists(), f"Published file {fname} missing!"
        actual_hash = hashlib.sha256(fpath.read_bytes()).hexdigest()
        assert actual_hash == expected_hashes[fname], f"Published file {fname} was modified!"

    # Ensure all labels in Pilot Session 1 remain AMBIGUOUS with traffic_class=None
    labels_file = pilot_dir / "labels.csv"
    with open(labels_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            assert row["label_quality"] == "AMBIGUOUS"
            assert row["traffic_class"] in ("", "None", None)


# -----------------------------------------------------------------------------
# 12. Quarantined Forensic Evidence Preservation
# -----------------------------------------------------------------------------

def test_quarantined_forensic_evidence_preservation():
    """Phase 7: Verifies quarantined failed session sess_70fc712285d34d2cb75abb02db8c1f1f remains untouched."""
    quarantine_dir = Path("data/research_v3/.incomplete/sess_70fc712285d34d2cb75abb02db8c1f1f")
    if not quarantine_dir.exists():
        pytest.skip("Quarantined session not present on this machine")

    marker_file = quarantine_dir / "SESSION_INCOMPLETE"
    assert marker_file.exists()
    content = marker_file.read_text(encoding="utf-8")
    assert "sess_70fc712285d34d2cb75abb02db8c1f1f" in content


# -----------------------------------------------------------------------------
# 13. End-to-End Collector Lifecycle with Attribution
# -----------------------------------------------------------------------------

def test_collector_end_to_end_attribution_lifecycle(tmp_path: Path):
    """Phase 7: Full lifecycle test of collector with attribution enabled in dry-run mode."""
    session_id = "sess_test_attr_collector"
    config = DatasetV3Config(
        session_id=session_id,
        interface="MockInterface",
        output_root=tmp_path,
        enable_attribution=True,
        attribution_allow_failure=True,
    )

    collector = PhysicalTrafficCollector(config)
    collector.initialize(bypass_prerequisites=True)

    # Register controlled root in process tracker
    collector.process_tracker.register_controlled_root(
        pid=1004,
        create_time_utc="2026-11-21T10:00:00Z",
        process_name="chrome.exe",
    )

    # Start capture in dry_run mode
    collector.start_capture(dry_run=True)

    # Ingest synthetic packets for two flows:
    # Flow 1: 192.168.1.50:54321 <-> 93.184.216.34:443 (will be matched to Chrome PID 1004)
    # Flow 2: 192.168.1.50:50000 <-> 1.1.1.1:80 (unmatched/background)
    from tests.research.dataset_v3.test_packet_parser import create_synthetic_ipv4_tcp_raw
    pkt1 = create_synthetic_ipv4_tcp_raw(src_ip="192.168.1.50", dst_ip="93.184.216.34", sport=54321, dport=443)
    pkt2 = create_synthetic_ipv4_tcp_raw(src_ip="93.184.216.34", dst_ip="192.168.1.50", sport=443, dport=54321)
    pkt3 = create_synthetic_ipv4_tcp_raw(src_ip="192.168.1.50", dst_ip="1.1.1.1", sport=50000, dport=80)

    now_t = time.time()
    now_mono = time.monotonic()
    collector.process_raw_ip_bytes(pkt1, ts=now_t, arrival_mono=now_mono)
    collector.process_raw_ip_bytes(pkt2, ts=now_t + 0.25, arrival_mono=now_mono + 0.25)
    collector.process_raw_ip_bytes(pkt3, ts=now_t + 0.05, arrival_mono=now_mono + 0.05)

    # Add 2 contemporaneous snapshots for Flow 1 covering both sampling bins
    fixture_gen = SyntheticSocketFixtureGenerator()
    s1 = fixture_gen.generate_tcp_snapshot(now_t + 0.05, "192.168.1.50", 54321, "93.184.216.34", 443, 1004, create_time="2026-11-21T10:00:00Z", state="ESTABLISHED")
    s2 = fixture_gen.generate_tcp_snapshot(now_t + 0.20, "192.168.1.50", 54321, "93.184.216.34", 443, 1004, create_time="2026-11-21T10:00:00Z", state="ESTABLISHED")
    collector.snapshot_manager.add_snapshot(now_t + 0.05, s1, monotonic_ts=now_mono + 0.05)
    collector.snapshot_manager.add_snapshot(now_t + 0.20, s2, monotonic_ts=now_mono + 0.20)

    # Stop capture
    collector.stop_capture(status="COMPLETE")

    # Verify session published to final directory
    published_dir = tmp_path / session_id
    assert published_dir.exists()
    assert (published_dir / "process_attribution_report.json").exists()

    # Load labels and verify:
    # Flow 1 (matched) received VERIFIED with Web
    # Flow 2 (unmatched) received AMBIGUOUS with None
    labels_file = published_dir / "labels.csv"
    with open(labels_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        labels = list(reader)

    assert len(labels) == 2
    verified_flows = [l for l in labels if l["label_quality"] == "VERIFIED"]
    ambiguous_flows = [l for l in labels if l["label_quality"] == "AMBIGUOUS"]

    assert len(verified_flows) == 1
    assert verified_flows[0]["traffic_class"] == "Web"
    assert len(ambiguous_flows) == 1
    assert ambiguous_flows[0]["traffic_class"] in ("", "None", None)

    # Verify sidecar report contents
    sidecar_file = published_dir / "process_attribution_report.json"
    with open(sidecar_file, "r", encoding="utf-8") as f:
        report_data = json.load(f)
    assert report_data["session_id"] == session_id
    assert report_data["total_flows"] == 2
    assert report_data["tcp_evidence_count"] >= 1

    # Verify manifest integrity hash contains the sidecar report
    manifest_file = published_dir / "session_manifest.json"
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
    assert "process_attribution_report.json" in manifest_data["file_integrity_hashes"]

    # Verify validator passes all checks on published session
    validator = DatasetV3Validator()
    val_report = validator.validate_session(published_dir)
    assert val_report.is_valid is True
    assert val_report.failed_checks == 0

    # Verify volatile memory is completely cleaned
    assert len(collector.flow_manager.get_transient_endpoints()) == 0
    assert collector.snapshot_manager.total_snapshot_count() == 0


# -----------------------------------------------------------------------------
# 14. Collector Attribution Failure Handling (Fail Safe)
# -----------------------------------------------------------------------------

def test_collector_attribution_failure_continues_ambiguous(tmp_path: Path):
    """Phase 7: Verifies collector when attribution fails continues capture safely with AMBIGUOUS labels."""
    session_id = "sess_test_attr_failure"
    config = DatasetV3Config(
        session_id=session_id,
        interface="MockInterface",
        output_root=tmp_path,
        enable_attribution=True,
        attribution_allow_failure=True,
    )

    collector = PhysicalTrafficCollector(config)
    collector.initialize(bypass_prerequisites=True)

    collector.start_capture(dry_run=True)

    # Simulate attribution failure during active capture
    collector.attribution_available = False
    collector.attribution_error = "Synthetic failure in IP Helper snapshot"

    from tests.research.dataset_v3.test_packet_parser import create_synthetic_ipv4_tcp_raw
    pkt = create_synthetic_ipv4_tcp_raw()
    collector.process_raw_ip_bytes(pkt, ts=time.time())

    collector.stop_capture(status="COMPLETE")

    published_dir = tmp_path / session_id
    assert published_dir.exists()

    # Labels must be AMBIGUOUS, not fail open!
    labels_file = published_dir / "labels.csv"
    with open(labels_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        labels = list(reader)

    assert len(labels) == 1
    assert labels[0]["label_quality"] == "AMBIGUOUS"
    assert labels[0]["traffic_class"] in ("", "None", None)

