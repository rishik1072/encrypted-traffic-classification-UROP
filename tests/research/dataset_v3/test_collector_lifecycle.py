"""
Unit Tests: Dataset V3 Physical Collector Lifecycle.

Validates:
- Collector state machine transitions.
- Dry-run packet ingestion without physical Npcap hardware execution.
- Graceful stop and finalization.
- Refusal to fall back to synthetic or demo modes.
- Complete output file generation.
"""

from __future__ import annotations

import socket
import struct
from pathlib import Path
import pytest

from research.dataset_v3.collector import PhysicalTrafficCollector
from research.dataset_v3.config import DatasetV3Config


def create_test_packet_bytes(src_ip: str, dst_ip: str, sport: int, dport: int, length: int) -> bytes:
    """Builds synthetic IPv4/UDP packet bytes for collector ingestion."""
    src_bytes = socket.inet_aton(src_ip)
    dst_bytes = socket.inet_aton(dst_ip)
    udp_hdr = struct.pack("!HHHH", sport, dport, length - 20, 0)
    ip_hdr = struct.pack(
        "!BBHHHBBH4s4s",
        (4 << 4) | 5,
        0,
        length,
        1,
        0,
        64,
        17,  # UDP
        0,
        src_bytes,
        dst_bytes,
    )
    payload_len = max(0, length - 28)
    return ip_hdr + udp_hdr + (b"\x00" * payload_len)


def test_collector_dry_run_lifecycle(tmp_path: Path) -> None:
    config = DatasetV3Config(
        output_root=tmp_path,
        session_id="sess_lifecycle_001",
        interface="MockPhysicalInterface",
        intended_traffic_class="Messaging",
        application_alias="signal_chat",
        duration_seconds=10.0,
    )

    collector = PhysicalTrafficCollector(config=config)
    assert collector.lifecycle_state == "COLLECTOR_IDLE"

    # Start in dry-run mode (no live Npcap sniffer process spawned)
    collector.start_capture(dry_run=True)
    assert collector.lifecycle_state == "COLLECTOR_ACTIVE"

    # Feed 5 synthetic packets
    p_bytes_fwd = create_test_packet_bytes("192.168.1.10", "1.1.1.1", 45000, 443, 200)
    p_bytes_bwd = create_test_packet_bytes("1.1.1.1", "192.168.1.10", 443, 45000, 800)

    collector.process_raw_ip_bytes(p_bytes_fwd, ts=100.0)
    collector.process_raw_ip_bytes(p_bytes_bwd, ts=100.02)
    collector.process_raw_ip_bytes(p_bytes_fwd, ts=100.05)
    collector.process_raw_ip_bytes(p_bytes_bwd, ts=100.10)
    collector.process_raw_ip_bytes(p_bytes_fwd, ts=100.15)

    assert collector.packets_captured_count == 5
    assert collector.packets_processed_count == 5

    # Stop capture
    collector.stop_capture(status="COMPLETE", notes="Lifecycle dry-run completed.")
    assert collector.lifecycle_state == "COLLECTOR_COMPLETED"

    # Verify all 5 output files exist in final published directory
    s_dir = tmp_path / "sess_lifecycle_001"
    assert (s_dir / "session_manifest.json").exists()
    assert (s_dir / "packet_metadata.jsonl").exists()
    assert (s_dir / "flow_index.csv").exists()
    assert (s_dir / "labels.csv").exists()
    assert (s_dir / "validation_report.json").exists()
    assert (s_dir / "SESSION_COMPLETE").exists()

    # Staging should be cleaned up
    staging_dir = tmp_path / ".staging" / "sess_lifecycle_001"
    assert not staging_dir.exists()


def test_collector_quarantines_incomplete_session(tmp_path: Path) -> None:
    config = DatasetV3Config(
        output_root=tmp_path,
        session_id="sess_incomplete_001",
        interface="MockPhysicalInterface",
        intended_traffic_class="Messaging",
        application_alias="signal_chat",
    )
    collector = PhysicalTrafficCollector(config=config)
    collector.start_capture(dry_run=True)
    # Interrupted before completion
    collector.stop_capture(status="INTERRUPTED", notes="User Ctrl+C interrupt.")
    assert collector.lifecycle_state == "COLLECTOR_INTERRUPTED"

    # Final dir must not exist
    final_dir = tmp_path / "sess_incomplete_001"
    assert not final_dir.exists()

    # Incomplete quarantine directory must exist
    quarantine_dir = tmp_path / ".incomplete" / "sess_incomplete_001"
    assert quarantine_dir.exists()
    assert (quarantine_dir / "SESSION_INCOMPLETE").exists()


def test_collector_refuses_missing_interface(tmp_path: Path) -> None:
    config = DatasetV3Config(
        output_root=tmp_path,
        session_id="sess_no_iface",
        interface=None,  # Missing physical interface!
    )
    collector = PhysicalTrafficCollector(config=config)
    with pytest.raises(ValueError, match="Explicit physical network interface must be specified"):
        collector.initialize()
    assert collector.lifecycle_state == "COLLECTOR_FAILED"
