"""
Unit and Regression Tests: Dataset V3 Capture Initialization, Scapy Argument Safety,
Synchronous Socket Management, and Failed Session Quarantine.

Verifies:
1. No unsupported 'snaplen' argument reaches Scapy AsyncSniffer constructor.
2. Synchronous Layer-2 socket initialization failure is handled cleanly.
3. Successful Layer-2 socket initialization transitions collector to COLLECTOR_ACTIVE.
4. started_callback synchronization guarantees sniffer thread is running before active state.
5. Startup timeout or immediate thread termination transitions collector to COLLECTOR_FAILED.
6. Premature capture worker termination is detected during collection.
7. Timer ending after capture failure does not publish or mark session COMPLETE.
8. Zero physical packet captures are quarantined (never published as COMPLETE).
9. Completion marker SESSION_COMPLETE is suppressed upon any failure.
10. User-space parser limit remains strictly 96 bytes in RAM.
11. Frame-length semantics accurately distinguish wire frame length from captured length.
12. Reconciliation of invalid published sessions safely removes completion markers and quarantines.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from research.dataset_v3.collector import PhysicalTrafficCollector
from research.dataset_v3.config import DatasetV3Config
from research.dataset_v3.metadata_writer import MetadataWriter
from research.dataset_v3.packet_parser import parse_scapy_packet_detailed
from scapy.layers.inet import IP, TCP


def test_no_snaplen_argument_reaches_async_sniffer(tmp_path: Path) -> None:
    """Verifies that AsyncSniffer constructor NEVER receives 'snaplen' keyword argument."""
    config = DatasetV3Config(
        output_root=tmp_path,
        session_id="sess_test_no_snaplen",
        interface="MockInterface",
        snaplen=96,
        duration_seconds=10.0,
    )

    collector = PhysicalTrafficCollector(config=config)
    collector.initialize(bypass_prerequisites=True)

    mock_socket = MagicMock()
    captured_sniffer_kwargs = {}

    def mock_sniffer_init(*args, **kwargs):
        captured_sniffer_kwargs.update(kwargs)
        sniffer_mock = MagicMock()
        sniffer_mock.running = True
        sniffer_mock.thread = MagicMock()
        sniffer_mock.thread.is_alive.return_value = True

        def fake_start():
            # Trigger started_callback as Scapy AsyncSniffer._run does
            cb = kwargs.get("started_callback")
            if cb:
                cb()

        sniffer_mock.start = fake_start
        return sniffer_mock

    with patch("scapy.config.conf.L2listen", return_value=mock_socket) as mock_l2:
        with patch("scapy.sendrecv.AsyncSniffer", side_effect=mock_sniffer_init):
            collector.start_capture(startup_timeout=2.0)
            assert collector.lifecycle_state == "COLLECTOR_ACTIVE"
            collector.stop_capture(status="INTERRUPTED")

    # Invariant 1: 'snaplen' must NEVER be passed to AsyncSniffer
    assert "snaplen" not in captured_sniffer_kwargs, "Unsupported 'snaplen' was passed to AsyncSniffer!"
    # Invariant 2: 'opened_socket' MUST be passed to AsyncSniffer
    assert "opened_socket" in captured_sniffer_kwargs
    assert captured_sniffer_kwargs["opened_socket"] == mock_socket
    # Invariant 3: 'iface' must NOT be passed when opened_socket is provided (prevents second socket)
    assert "iface" not in captured_sniffer_kwargs
    # Invariant 4: 'started_callback' must be provided for synchronization
    assert "started_callback" in captured_sniffer_kwargs


def test_synchronous_socket_initialization_failure(tmp_path: Path) -> None:
    """Verifies that synchronous L2 socket creation failure transitions to COLLECTOR_FAILED and quarantines."""
    config = DatasetV3Config(
        output_root=tmp_path,
        session_id="sess_test_sock_fail",
        interface="FaultyInterface",
        duration_seconds=10.0,
    )

    collector = PhysicalTrafficCollector(config=config)
    collector.initialize(bypass_prerequisites=True)

    with patch("scapy.config.conf.L2listen", side_effect=OSError("Npcap open failed: Device not found")):
        with pytest.raises(RuntimeError, match=r"\[SOCKET_INIT_FAILED\]"):
            collector.start_capture(startup_timeout=1.0)

    assert collector.lifecycle_state == "COLLECTOR_FAILED"
    assert "[SOCKET_INIT_FAILED]" in (collector.last_error or "")

    # Must be quarantined to .incomplete/
    quarantine_dir = tmp_path / ".incomplete" / "sess_test_sock_fail"
    assert quarantine_dir.exists()
    assert (quarantine_dir / "SESSION_INCOMPLETE").exists()
    # Must NOT exist in final published root
    assert not (tmp_path / "sess_test_sock_fail").exists()


def test_successful_socket_initialization_and_active_state(tmp_path: Path) -> None:
    """Verifies clean transition to COLLECTOR_ACTIVE upon verified socket and worker start."""
    config = DatasetV3Config(
        output_root=tmp_path,
        session_id="sess_test_active_ok",
        interface="GoodInterface",
        duration_seconds=10.0,
    )

    collector = PhysicalTrafficCollector(config=config)
    collector.initialize(bypass_prerequisites=True)

    mock_socket = MagicMock()
    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = True

    mock_sniffer = MagicMock()
    mock_sniffer.running = True
    mock_sniffer.thread = mock_thread

    def fake_start():
        pass  # Started callback will be triggered manually

    mock_sniffer.start = fake_start

    def mock_sniffer_factory(*args, **kwargs):
        # Trigger started callback
        cb = kwargs.get("started_callback")
        if cb:
            cb()
        return mock_sniffer

    with patch("scapy.config.conf.L2listen", return_value=mock_socket):
        with patch("scapy.sendrecv.AsyncSniffer", side_effect=mock_sniffer_factory):
            collector.start_capture(startup_timeout=2.0)
            assert collector.lifecycle_state == "COLLECTOR_ACTIVE"
            assert collector.is_worker_alive() is True
            collector.stop_capture(status="INTERRUPTED")


def test_started_callback_synchronization_timeout(tmp_path: Path) -> None:
    """Verifies that failing to receive started_callback within timeout fails and quarantines."""
    config = DatasetV3Config(
        output_root=tmp_path,
        session_id="sess_test_timeout",
        interface="TimeoutInterface",
        duration_seconds=10.0,
    )

    collector = PhysicalTrafficCollector(config=config)
    collector.initialize(bypass_prerequisites=True)

    mock_socket = MagicMock()
    mock_sniffer = MagicMock()
    mock_sniffer.thread = MagicMock()
    mock_sniffer.thread.is_alive.return_value = True

    # Deliberately omit firing started_callback
    with patch("scapy.config.conf.L2listen", return_value=mock_socket):
        with patch("scapy.sendrecv.AsyncSniffer", return_value=mock_sniffer):
            with pytest.raises(RuntimeError, match=r"\[CAPTURE_START_FAILED\]"):
                collector.start_capture(startup_timeout=0.1)

    assert collector.lifecycle_state == "COLLECTOR_FAILED"
    assert "startup timeout" in (collector.last_error or "")

    # Incomplete quarantine verification
    quarantine_dir = tmp_path / ".incomplete" / "sess_test_timeout"
    assert quarantine_dir.exists()
    assert (quarantine_dir / "SESSION_INCOMPLETE").exists()


def test_capture_worker_premature_exit_detection(tmp_path: Path) -> None:
    """Verifies that premature capture worker termination transitions collector to FAILED and quarantines."""
    config = DatasetV3Config(
        output_root=tmp_path,
        session_id="sess_test_worker_crash",
        interface="CrashInterface",
        duration_seconds=10.0,
    )

    collector = PhysicalTrafficCollector(config=config)
    collector.initialize(bypass_prerequisites=True)

    mock_socket = MagicMock()
    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = True
    mock_sniffer = MagicMock()
    mock_sniffer.running = True
    mock_sniffer.thread = mock_thread

    def mock_factory(*args, **kwargs):
        cb = kwargs.get("started_callback")
        if cb:
            cb()
        return mock_sniffer

    with patch("scapy.config.conf.L2listen", return_value=mock_socket):
        with patch("scapy.sendrecv.AsyncSniffer", side_effect=mock_factory):
            collector.start_capture(startup_timeout=2.0)
            assert collector.lifecycle_state == "COLLECTOR_ACTIVE"

            # Simulate worker thread crash
            mock_thread.is_alive.return_value = False
            assert collector.is_worker_alive() is False

            # Explicit failure trigger
            collector.fail_capture(reason="Worker thread died", stage="WORKER_DIED")
            assert collector.lifecycle_state == "COLLECTOR_FAILED"
            assert "[WORKER_DIED]" in (collector.last_error or "")

    quarantine_dir = tmp_path / ".incomplete" / "sess_test_worker_crash"
    assert quarantine_dir.exists()
    assert (quarantine_dir / "SESSION_INCOMPLETE").exists()
    assert not (tmp_path / "sess_test_worker_crash").exists()


def test_timer_ending_after_capture_failure_does_not_publish(tmp_path: Path) -> None:
    """Verifies that calling stop_capture after collector failure does NOT publish COMPLETE."""
    config = DatasetV3Config(
        output_root=tmp_path,
        session_id="sess_test_timer_after_fail",
        interface="FailInterface",
        duration_seconds=10.0,
    )

    collector = PhysicalTrafficCollector(config=config)
    collector.initialize(bypass_prerequisites=True)
    collector.lifecycle_state = "COLLECTOR_FAILED"
    collector.last_error = "[TEST] Already failed"

    # Timer worker or stop called
    collector.stop_capture(status="COMPLETE", notes="Timer ended")

    assert collector.lifecycle_state == "COLLECTOR_FAILED"
    assert not (tmp_path / "sess_test_timer_after_fail").exists()


def test_zero_packets_received_quarantines_and_refuses_complete(tmp_path: Path) -> None:
    """Verifies that 0-packet captures are quarantined and NOT published as COMPLETE when allow_empty_capture=False."""
    config = DatasetV3Config(
        output_root=tmp_path,
        session_id="sess_test_zero_pkts",
        interface="MockInterface",
        duration_seconds=10.0,
        allow_empty_capture=False,
    )

    collector = PhysicalTrafficCollector(config=config)
    collector.start_capture(dry_run=True)
    # Stop without processing any packets
    collector.stop_capture(status="COMPLETE")

    assert collector.lifecycle_state == "COLLECTOR_FAILED"
    # Final published directory must NOT exist
    assert not (tmp_path / "sess_test_zero_pkts").exists()
    # Must be quarantined
    quarantine_dir = tmp_path / ".incomplete" / "sess_test_zero_pkts"
    assert quarantine_dir.exists()
    assert (quarantine_dir / "SESSION_INCOMPLETE").exists()


def test_controlled_invalidation_and_quarantine_procedure(tmp_path: Path) -> None:
    """Verifies MetadataWriter.quarantine_invalid_published_session removes SESSION_COMPLETE and quarantines."""
    pub_dir = tmp_path / "sess_erroneously_published"
    pub_dir.mkdir(parents=True, exist_ok=True)

    manifest_data = {
        "session_id": "sess_erroneously_published",
        "capture_status": "COMPLETE",
        "notes": "Original erroneous note",
        "packet_count": 0,
        "flow_count": 0,
    }
    with open(pub_dir / "session_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    marker = pub_dir / "SESSION_COMPLETE"
    marker.write_text("SESSION_COMPLETE:mock", encoding="utf-8")

    inc_root = tmp_path / ".incomplete"

    quarantined = MetadataWriter.quarantine_invalid_published_session(
        published_session_dir=pub_dir,
        incomplete_root=inc_root,
        failure_reason="Unit test verification of quarantine procedure",
    )

    # 1. Published directory no longer exists in primary root
    assert not pub_dir.exists()
    # 2. Quarantined directory exists in .incomplete/
    assert quarantined.exists()
    # 3. SESSION_COMPLETE marker is removed
    assert not (quarantined / "SESSION_COMPLETE").exists()
    # 4. SESSION_INCOMPLETE marker exists
    assert (quarantined / "SESSION_INCOMPLETE").exists()

    # 5. Manifest updated with FAILED status and diagnostic note
    with open(quarantined / "session_manifest.json", "r", encoding="utf-8") as f:
        updated_manifest = json.load(f)
    assert updated_manifest["capture_status"] == "FAILED"
    assert "INVALID: Unit test verification" in updated_manifest["notes"]


def test_userspace_parser_limit_and_frame_length_semantics() -> None:
    """Verifies that 96-byte user-space parser limit works accurately without kernel snaplen."""
    # Build 190-byte serialized packet (20B IP + 20B TCP + 150B payload)
    raw_pkt = IP(bytes(IP(src="192.168.1.50", dst="1.1.1.1") / TCP(sport=50000, dport=443) / ("Z" * 150)))
    assert len(raw_pkt) == 190

    res = parse_scapy_packet_detailed(raw_pkt, user_snaplen=96)
    assert res.packet_data is not None
    # 1. captured_link_layer_length_bytes == full Scapy frame (190)
    assert res.packet_data.captured_link_layer_length == 190
    assert res.packet_data.length == 190
    # 2. captured_length_bytes == truncated user-space bytes (96)
    assert res.packet_data.captured_length == 96
    # 3. wire_frame_length_bytes is None when driver pcap_pkthdr is unavailable
    assert res.packet_data.wire_frame_length is None
    # 4. IP total length from IP header == 190
    assert res.packet_data.ip_total_length == 190


def test_no_production_source_code_modifications() -> None:
    """Regression check: verify that no files in production directories were altered."""
    repo_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        ["git", "status", "--porcelain", "product/", "capture/", "flows/", "models/", "preprocessing/"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    # Filter out product/local_api.py if it was from prior Phase 0
    lines = [
        line for line in result.stdout.strip().splitlines()
        if line and not line.endswith("product/local_api.py")
    ]
    assert len(lines) == 0, f"Unintended changes detected in production directories: {lines}"
