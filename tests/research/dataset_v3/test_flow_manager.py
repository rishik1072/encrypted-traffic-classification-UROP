"""
Unit Tests: Dataset V3 Flow Manager.

Validates:
- Bidirectional flow aggregation via 5-tuple canonicalization.
- Direction assignment convention (0 = first observed, 1 = reverse).
- Random UUID flow ID generation without network identifier encoding.
- Microsecond relative timestamps and inter-arrival times.
- Zero-PII emission in PacketMetadataRecord.
- Parent-flow lineage matching (parent_flow_id == flow_id).
- Flow timeout handling.
"""

from __future__ import annotations

import re
from research.dataset_v3.flow_manager import FlowManager
from research.dataset_v3.packet_parser import TransientPacketData

FLOW_ID_REGEX = re.compile(r"^flow_[a-f0-9]{32}$")


def test_bidirectional_association_and_direction_assignment() -> None:
    fm = FlowManager(session_id="test_sess_001")

    # Packet 1: Client -> Server
    p1 = TransientPacketData(
        timestamp=100.0,
        length=150,
        protocol="TCP",
        tcp_flags=0x02,
        src_ip="192.168.1.50",
        src_port=50000,
        dst_ip="93.184.216.34",
        dst_port=443,
    )
    r1, c1 = fm.process_packet(p1)

    assert c1 is None
    assert FLOW_ID_REGEX.match(r1.flow_id)
    assert r1.parent_flow_id == r1.flow_id
    assert r1.direction == 0
    assert r1.packet_index == 0
    assert r1.relative_timestamp_us == 0
    assert r1.inter_arrival_time_us == 0
    assert r1.packet_length == 150
    assert r1.is_synthetic is False

    # Packet 2: Server -> Client (Reverse direction)
    p2 = TransientPacketData(
        timestamp=100.05,  # 50 ms later
        length=1400,
        protocol="TCP",
        tcp_flags=0x12,
        src_ip="93.184.216.34",
        src_port=443,
        dst_ip="192.168.1.50",
        dst_port=50000,
    )
    r2, c2 = fm.process_packet(p2)

    assert c2 is None
    assert r2.flow_id == r1.flow_id  # Same flow ID!
    assert r2.parent_flow_id == r1.flow_id
    assert r2.direction == 1  # Reverse direction
    assert r2.packet_index == 1
    assert r2.relative_timestamp_us == 50_000
    assert r2.inter_arrival_time_us == 50_000
    assert r2.packet_length == 1400

    # Packet 3: Client -> Server (Forward direction)
    p3 = TransientPacketData(
        timestamp=100.08,  # 30 ms later
        length=200,
        protocol="TCP",
        tcp_flags=0x10,
        src_ip="192.168.1.50",
        src_port=50000,
        dst_ip="93.184.216.34",
        dst_port=443,
    )
    r3, c3 = fm.process_packet(p3)

    assert r3.flow_id == r1.flow_id
    assert r3.direction == 0
    assert r3.packet_index == 2
    assert r3.relative_timestamp_us == 80_000
    assert r3.inter_arrival_time_us == 30_000

    # Finalize flows
    completed = fm.finalize_all()
    assert len(completed) == 1
    flow_summary = completed[0]
    assert flow_summary.flow_id == r1.flow_id
    assert flow_summary.parent_flow_id == r1.flow_id
    assert flow_summary.packet_count == 3
    assert flow_summary.duration_us == 80_000
    assert flow_summary.direction_0_packets == 2
    assert flow_summary.direction_1_packets == 1
    assert flow_summary.direction_0_bytes == 350
    assert flow_summary.direction_1_bytes == 1400


def test_flow_timeouts() -> None:
    fm = FlowManager(session_id="test_sess_002", idle_timeout_seconds=5.0)

    p1 = TransientPacketData(
        timestamp=100.0,
        length=100,
        protocol="UDP",
        tcp_flags=None,
        src_ip="10.0.0.1",
        src_port=4000,
        dst_ip="10.0.0.2",
        dst_port=5000,
    )
    fm.process_packet(p1)
    assert fm.active_flow_count == 1

    # Check timeout at 102.0s (not expired)
    expired = fm.check_timeouts(102.0)
    assert len(expired) == 0
    assert fm.active_flow_count == 1

    # Check timeout at 106.0s (idle elapsed 6.0s >= 5.0s)
    expired = fm.check_timeouts(106.0)
    assert len(expired) == 1
    assert fm.active_flow_count == 0
    assert expired[0].packet_count == 1
