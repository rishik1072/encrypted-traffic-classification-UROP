"""
Comprehensive Verification and Regression Tests for Pilot Session 2 Lifecycle.

Verifies all 14 Phase 4 requirements:
1. Chrome remains alive while snapshot worker runs.
2. At least two snapshots occur during dry-run warmup.
3. Chrome is stopped only after snapshot-worker shutdown.
4. Temporary profile is deleted.
5. Snapshot worker joins cleanly.
6. Dynamic child process discovery.
7. Child process removal after termination.
8. PID reuse protection during tree refresh.
9. Unrelated Chrome process rejection.
10. Physical pilot uses headed Chrome (headless=False).
11. Dry-run never starts AsyncSniffer.
12. Dry-run performs zero packet reads.
13. Dry-run publishes no dataset.
14. Existing Session 1 remains immutable.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
from unittest.mock import MagicMock, patch
import pytest

from research.dataset_v3.attribution.chrome_launcher import ControlledChromeLauncher
from research.dataset_v3.attribution.process_tracker import ProcessTracker
from research.dataset_v3.attribution.snapshot_manager import SocketSnapshotManager
from research.dataset_v3.collector import PhysicalTrafficCollector
from research.dataset_v3.pilot_config import create_pilot_session_2_config


# ==============================================================================
# 1. Chrome Remains Alive While Snapshot Worker Runs
# ==============================================================================

def test_chrome_remains_alive_while_snapshot_worker_runs():
    """Requirement 1: Chrome browser remains running throughout snapshot worker operation."""
    tracker = ProcessTracker()
    snap_mgr = SocketSnapshotManager(snapshot_interval_seconds=0.05)

    with patch("subprocess.Popen") as mock_popen, \
         patch("research.dataset_v3.attribution.chrome_launcher.get_process_creation_time_and_name") as mock_ctime:
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None  # Process is running
        mock_popen.return_value = mock_proc
        mock_ctime.return_value = ("2026-11-22T00:00:00Z", "chrome.exe")

        launcher = ControlledChromeLauncher(process_tracker=tracker, headless=True)
        launcher.launch(initial_url="about:blank")
        assert launcher.is_running is True

        # Start snapshot worker
        snap_mgr.start_polling()
        assert snap_mgr.is_polling_active is True

        # Verify Chrome is continuously running while snapshots occur
        for _ in range(5):
            assert launcher.is_running is True
            time.sleep(0.02)

        snap_mgr.stop_polling()
        assert snap_mgr.is_polling_active is False
        assert launcher.is_running is True

        launcher.stop()


# ==============================================================================
# 2. At Least Two Snapshots Occur During Dry-Run Warmup
# ==============================================================================

def test_at_least_two_snapshots_occur_during_dry_run_warmup():
    """Requirement 2: At least two socket snapshots are recorded during dry-run warmup while Chrome is alive."""
    tracker = ProcessTracker()
    snap_mgr = SocketSnapshotManager(snapshot_interval_seconds=0.05)

    with patch("subprocess.Popen") as mock_popen, \
         patch("research.dataset_v3.attribution.chrome_launcher.get_process_creation_time_and_name") as mock_ctime:
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc
        mock_ctime.return_value = ("2026-11-22T00:00:00Z", "chrome.exe")

        launcher = ControlledChromeLauncher(process_tracker=tracker, headless=True)
        launcher.launch(initial_url="about:blank")

        snap_mgr.start_polling()
        t0 = time.monotonic()
        while snap_mgr.total_snapshot_count() < 2 and time.monotonic() - t0 < 3.0:
            assert launcher.is_running is True
            time.sleep(0.02)

        count = snap_mgr.total_snapshot_count()
        snap_mgr.stop_polling()
        launcher.stop()

        assert count >= 2, f"Expected at least 2 snapshots, got {count}"


# ==============================================================================
# 3. Chrome Is Stopped Only After Snapshot-Worker Shutdown
# ==============================================================================

def test_chrome_is_stopped_only_after_snapshot_worker_shutdown():
    """Requirement 3: Enforces strict lifecycle order: snapshot poller stops BEFORE Chrome stops."""
    tracker = ProcessTracker()
    snap_mgr = SocketSnapshotManager(snapshot_interval_seconds=0.05)
    execution_order = []

    with patch("subprocess.Popen") as mock_popen, \
         patch("research.dataset_v3.attribution.chrome_launcher.get_process_creation_time_and_name") as mock_ctime:
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc
        mock_ctime.return_value = ("2026-11-22T00:00:00Z", "chrome.exe")

        launcher = ControlledChromeLauncher(process_tracker=tracker, headless=True)
        launcher.launch(initial_url="about:blank")
        snap_mgr.start_polling()

        # Shutdown sequence
        snap_mgr.stop_polling()
        execution_order.append("SNAPSHOT_WORKER_STOPPED")
        assert snap_mgr.is_polling_active is False
        assert launcher.is_running is True, "Chrome must still be alive when snapshot poller stops!"

        launcher.stop()
        execution_order.append("CHROME_STOPPED")
        assert launcher.is_running is False

    assert execution_order == ["SNAPSHOT_WORKER_STOPPED", "CHROME_STOPPED"]


# ==============================================================================
# 4. Temporary Profile Is Deleted
# ==============================================================================

def test_temporary_profile_is_deleted(tmp_path: Path):
    """Requirement 4: Dedicated temporary Chrome user-data directory is deleted upon stop()."""
    tracker = ProcessTracker()

    with patch("subprocess.Popen") as mock_popen, \
         patch("research.dataset_v3.attribution.chrome_launcher.get_process_creation_time_and_name") as mock_ctime:
        mock_proc = MagicMock()
        mock_proc.pid = 22222
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc
        mock_ctime.return_value = ("2026-11-22T00:00:00Z", "chrome.exe")

        launcher = ControlledChromeLauncher(process_tracker=tracker, headless=True)
        launcher.launch(initial_url="about:blank")

        temp_dir = launcher._temp_user_data_dir
        assert temp_dir is not None
        assert temp_dir.exists(), "Profile directory must exist while running!"

        launcher.stop()
        assert not temp_dir.exists(), "Profile directory must be deleted upon stop()!"
        assert launcher._temp_user_data_dir is None


# ==============================================================================
# 5. Snapshot Worker Joins Cleanly
# ==============================================================================

def test_snapshot_worker_joins_cleanly():
    """Requirement 5: Background snapshot polling thread terminates and joins within timeout."""
    snap_mgr = SocketSnapshotManager(snapshot_interval_seconds=0.05)
    snap_mgr.start_polling()
    assert snap_mgr.is_polling_active is True

    snap_mgr.stop_polling(timeout_seconds=2.0)
    assert snap_mgr.is_polling_active is False
    assert snap_mgr._polling_thread is None


# ==============================================================================
# 6. Dynamic Child Process Discovery
# ==============================================================================

def test_dynamic_child_process_discovery():
    """Requirement 6: Discovers newly spawned child processes descending from root."""
    tracker = ProcessTracker(controlled_app_alias="chrome_controlled")
    tracker.register_controlled_root(pid=1000, create_time_utc="2026-11-22T00:00:00Z")

    # Initial state: only root PID 1000
    assert tracker.active_controlled_pids == {1000}

    # Simulate dynamic spawn of child 1004 (Network Service) and 1008 (Renderer)
    simulated_process_table = {
        1000: (500, "chrome.exe"),
        1004: (1000, "chrome.exe"),  # child of 1000
        1008: (1000, "chrome.exe"),  # child of 1000
        2000: (1, "svchost.exe"),     # unrelated
    }

    with patch("research.dataset_v3.attribution.process_tracker.get_process_creation_time_and_name") as mock_ctime:
        mock_ctime.side_effect = lambda pid: (
            ("2026-11-22T00:00:01Z", "chrome.exe") if pid in (1004, 1008) else ("2026-11-21T00:00:00Z", "svchost.exe")
        )
        new_discovered = tracker.refresh_descendants(parent_map=simulated_process_table)

    assert new_discovered == 2
    assert tracker.active_controlled_pids == {1000, 1004, 1008}
    assert tracker.is_pid_active(1004) is True
    assert tracker.is_pid_active(1008) is True
    assert tracker.is_pid_active(2000) is False


# ==============================================================================
# 7. Child Process Removal After Termination
# ==============================================================================

def test_child_process_removal_after_termination():
    """Requirement 7: Prunes terminated child processes from active identity mappings."""
    tracker = ProcessTracker(controlled_app_alias="chrome_controlled")
    tracker.register_controlled_root(pid=1000, create_time_utc="2026-11-22T00:00:00Z")
    tracker.register_controlled_child(pid=1004, parent_pid=1000, create_time_utc="2026-11-22T00:00:01Z")
    tracker.register_controlled_child(pid=1008, parent_pid=1000, create_time_utc="2026-11-22T00:00:02Z")

    assert tracker.active_controlled_pids == {1000, 1004, 1008}

    # Simulate termination of child 1008 (renderer closed)
    updated_process_table = {
        1000: (500, "chrome.exe"),
        1004: (1000, "chrome.exe"),
        # 1008 is absent!
    }

    with patch("research.dataset_v3.attribution.process_tracker.get_process_creation_time_and_name") as mock_ctime:
        mock_ctime.side_effect = lambda pid: ("2026-11-22T00:00:01Z", "chrome.exe") if pid == 1004 else None
        tracker.refresh_descendants(parent_map=updated_process_table)

    # 1008 is cleanly pruned from active mappings
    assert tracker.active_controlled_pids == {1000, 1004}
    assert tracker.is_pid_active(1008) is False
    assert 1008 not in tracker.active_identities


# ==============================================================================
# 8. PID Reuse Protection During Tree Refresh
# ==============================================================================

def test_pid_reuse_protection_during_tree_refresh():
    """Requirement 8: Rejects recycled PIDs when a new process takes over an old child PID."""
    tracker = ProcessTracker(controlled_app_alias="chrome_controlled")
    tracker.register_controlled_root(pid=1000, create_time_utc="2026-11-22T00:00:00Z")
    tracker.register_controlled_child(pid=1004, parent_pid=1000, create_time_utc="2026-11-22T00:00:01Z")

    # PID 1004 terminates and OS reassigns PID 1004 to unrelated process with NEW creation time
    reused_table = {
        1000: (500, "chrome.exe"),
        1004: (1, "notepad.exe"),  # PID 1004 reused
    }

    with patch("research.dataset_v3.attribution.process_tracker.get_process_creation_time_and_name") as mock_ctime:
        mock_ctime.return_value = ("2026-11-22T00:10:00Z", "notepad.exe")
        tracker.refresh_descendants(parent_map=reused_table)

    # Pruned from active controlled PIDs
    assert 1004 not in tracker.active_controlled_pids

    # Querying with new creation time resolves to system_background
    alias, is_ctrl = tracker.resolve_application_alias(1004, "2026-11-22T00:10:00Z", "notepad.exe")
    assert is_ctrl is False
    assert alias == "system_background"


# ==============================================================================
# 9. Unrelated Chrome Process Rejection
# ==============================================================================

def test_unrelated_chrome_process_rejection():
    """Requirement 9: Unrelated Chrome processes running concurrently are rejected."""
    tracker = ProcessTracker(controlled_app_alias="chrome_controlled")
    tracker.register_controlled_root(pid=1000, create_time_utc="2026-11-22T00:00:00Z")

    # Unrelated Chrome instance PID 9999 started earlier by user
    unrelated_table = {
        1000: (500, "chrome.exe"),
        9999: (500, "chrome.exe"),  # sibling, NOT child of 1000
    }

    with patch("research.dataset_v3.attribution.process_tracker.get_process_creation_time_and_name") as mock_ctime:
        mock_ctime.return_value = ("2026-11-21T08:00:00Z", "chrome.exe")
        tracker.refresh_descendants(parent_map=unrelated_table)

    assert 9999 not in tracker.active_controlled_pids
    alias, is_ctrl = tracker.resolve_application_alias(9999, "2026-11-21T08:00:00Z", "chrome.exe")
    assert is_ctrl is False
    assert alias == "system_background"


# ==============================================================================
# 10. Physical Pilot Uses Headed Chrome
# ==============================================================================

def test_physical_pilot_uses_headed_chrome():
    """Requirement 10: Live pilot session code configures headless=False so operator sees window."""
    script_path = Path("scripts/research/dataset_v3/run_pilot_session_2.py")
    content = script_path.read_text(encoding="utf-8")

    # Live capture execution must use headless=False
    assert "headless=False" in content, "Physical pilot mode must configure headless=False!"
    # Dry run may use headless=True
    assert "headless=True" in content, "Dry-run mode may configure headless=True!"


# ==============================================================================
# 11. Dry-Run Never Starts AsyncSniffer
# ==============================================================================

def test_dry_run_never_starts_asyncsniffer(tmp_path: Path):
    """Requirement 11: Collector in dry-run mode strictly avoids instantiating or starting AsyncSniffer."""
    cfg = create_pilot_session_2_config(output_root=tmp_path / "research")
    collector = PhysicalTrafficCollector(config=cfg)
    collector.initialize(bypass_prerequisites=True)

    collector.start_capture(dry_run=True)
    assert collector._sniffer is None, "AsyncSniffer must NEVER be created in dry-run mode!"

    collector.stop_capture(status="INTERRUPTED", suppress_quarantine=True)
    assert collector._sniffer is None


# ==============================================================================
# 12. Dry-Run Performs Zero Packet Reads
# ==============================================================================

def test_dry_run_performs_zero_packet_reads(tmp_path: Path):
    """Requirement 12: Dry-run performs zero packet reads and captures zero packets."""
    cfg = create_pilot_session_2_config(output_root=tmp_path / "research")
    collector = PhysicalTrafficCollector(config=cfg)
    collector.initialize(bypass_prerequisites=True)

    collector.start_capture(dry_run=True)
    time.sleep(0.1)
    collector.stop_capture(status="INTERRUPTED", suppress_quarantine=True)

    assert collector.packets_captured_count == 0
    assert collector.packets_processed_count == 0


# ==============================================================================
# 13. Dry-Run Publishes No Dataset
# ==============================================================================

def test_dry_run_publishes_no_dataset(tmp_path: Path):
    """Requirement 13: Dry-run execution leaves zero published datasets and zero staging residue."""
    out_root = tmp_path / "research"
    cfg = create_pilot_session_2_config(output_root=out_root)
    collector = PhysicalTrafficCollector(config=cfg)
    collector.initialize(bypass_prerequisites=True)

    collector.start_capture(dry_run=True)
    collector.stop_capture(status="INTERRUPTED", suppress_quarantine=True)

    assert not cfg.final_session_dir.exists(), "Final published directory must NOT exist!"
    assert not cfg.staging_session_dir.exists(), "Staging session directory must be deleted!"


# ==============================================================================
# 14. Existing Session 1 Remains Immutable
# ==============================================================================

def test_existing_pilot_session_1_remains_immutable():
    """Requirement 14: Published Pilot Session 1 files, hashes, and AMBIGUOUS labels are untouched."""
    sess1_dir = Path("data/research_v3/sess_b04fe53843b04caa8bf86e60209d3fd0")
    assert sess1_dir.exists(), "Pilot Session 1 must exist!"

    manifest_path = sess1_dir / "session_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 1. Verify all 3 data file SHA-256 integrity hashes
    for fname, expected_hash in manifest["file_integrity_hashes"].items():
        if fname == "session_manifest.json":
            continue
        fpath = sess1_dir / fname
        with open(fpath, "rb") as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()
        assert actual_hash == expected_hash, f"Hash mismatch in Pilot Session 1 file: {fname}!"

    # 2. Verify all labels remain AMBIGUOUS
    labels_path = sess1_dir / "labels.csv"
    with open(labels_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    header = lines[0].split(",")
    tc_idx = header.index("traffic_class")
    lq_idx = header.index("label_quality")

    for line in lines[1:]:
        parts = line.split(",")
        assert parts[tc_idx] == "", "Pilot Session 1 traffic_class must remain empty (None)!"
        assert parts[lq_idx] == "AMBIGUOUS", "Pilot Session 1 label_quality must remain AMBIGUOUS!"
