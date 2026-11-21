"""
Regression Test Suite for Dataset V3 Packet Length Semantics.

Validates the 10 critical packet length scenarios:
1. Standard Ethernet II (14B L2 + IP total length).
2. Single VLAN (802.1Q 18B L2 + IP total length).
3. QinQ VLAN (802.1ad 22B L2 + IP total length).
4. Ethernet padding (small 40B IP packet padded to 60B link-layer frame; refutes 14 + IP).
5. IPv4 options (IHL = 6, 24B IPv4 header).
6. IPv6 extension headers (Hop-by-Hop, Routing, Destination Options).
7. User-space packet truncation (raw 500B packet sliced to snaplen 96).
8. Missing native wire length (live Scapy packet where wirelen is None).
9. Packet length versus captured length (packet_length == captured_link_layer_length_bytes != captured_length_bytes).
10. Exact compatibility with production len(pkt) feature convention (FeatureExtractor parity).
"""

from __future__ import annotations

import json
import socket
import struct
from pathlib import Path
from typing import List, Tuple

import pytest

from preprocessing.feature_extractor import FeatureExtractor
from research.dataset_v3.flow_manager import FlowManager
from research.dataset_v3.packet_parser import (
    ParseStatus,
    TransientPacketData,
    parse_raw_ip_bytes_detailed,
    parse_scapy_packet_detailed,
)
from research.dataset_v3.schemas import PacketMetadataRecord


def _make_ipv4_tcp_frame(
    l2_prefix: bytes,
    ip_total_len: int,
    sport: int = 12345,
    dport: int = 443,
    payload_len: int = 0,
    pad_bytes: bytes = b"",
    ihl_words: int = 5,
    ip_options: bytes = b"",
) -> bytes:
    """Helper to build synthesized Ethernet/IP/TCP frames with exact byte control."""
    src_ip = socket.inet_aton("192.168.1.100")
    dst_ip = socket.inet_aton("104.244.42.1")
    ver_ihl = (4 << 4) | (ihl_words & 0x0F)

    ip_hdr = struct.pack(
        "!BBHHHBBH4s4s",
        ver_ihl,
        0,
        ip_total_len,
        100,
        0,
        64,
        6,  # TCP
        0,
        src_ip,
        dst_ip,
    ) + ip_options

    tcp_hdr = struct.pack(
        "!HHIIBBHHH",
        sport,
        dport,
        1,
        0,
        (5 << 4),  # 20B TCP header
        0x18,      # PSH+ACK
        65535,
        0,
        0,
    )

    payload = b"A" * payload_len
    return l2_prefix + ip_hdr + tcp_hdr + payload + pad_bytes


# ---------------------------------------------------------------------------
# Test 1: Standard Ethernet II (14B L2 + IP total length)
# ---------------------------------------------------------------------------
def test_standard_ethernet_ii() -> None:
    l2_hdr = b"\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99\xaa\xbb\x08\x00"  # 14B EtherType 0x0800
    ip_len = 100  # 20B IP + 20B TCP + 60B payload
    frame = _make_ipv4_tcp_frame(l2_hdr, ip_total_len=ip_len, payload_len=60)
    assert len(frame) == 114  # 14 + 100

    result = parse_raw_ip_bytes_detailed(frame, orig_frame_len=114, wire_len=114)
    assert result.status == ParseStatus.VALID_METADATA
    pkt = result.packet_data
    assert pkt is not None

    assert pkt.captured_link_layer_length == 114
    assert pkt.wire_length == 114  # Canonical feature length
    assert pkt.captured_length == 114
    assert pkt.ip_total_length == 100
    assert pkt.wire_frame_length == 114
    assert pkt.protocol == "TCP"

    # FlowManager integration
    fm = FlowManager(session_id="test_sess_01")
    rec, _ = fm.process_packet(pkt)
    assert rec.captured_link_layer_length_bytes == 114
    assert rec.packet_length == 114
    assert rec.captured_length_bytes == 114
    assert rec.wire_frame_length_bytes == 114
    assert rec.ip_total_length_bytes == 100


# ---------------------------------------------------------------------------
# Test 2: Single VLAN (802.1Q 18B L2 + IP total length)
# ---------------------------------------------------------------------------
def test_single_vlan_8021q() -> None:
    # 12B MACs + 2B TPID (0x8100) + 2B TCI (VLAN 100) + 2B EtherType (0x0800) = 18B
    l2_vlan = b"\x00" * 12 + b"\x81\x00\x00\x64\x08\x00"
    ip_len = 100
    frame = _make_ipv4_tcp_frame(l2_vlan, ip_total_len=ip_len, payload_len=60)
    assert len(frame) == 118  # 18 + 100

    result = parse_raw_ip_bytes_detailed(frame, orig_frame_len=118, wire_len=118)
    assert result.status == ParseStatus.VALID_METADATA
    pkt = result.packet_data
    assert pkt is not None

    assert pkt.captured_link_layer_length == 118
    assert pkt.wire_length == 118
    assert pkt.captured_length == 118
    assert pkt.ip_total_length == 100
    assert pkt.wire_frame_length == 118

    # Crucial scientific check: 14 + IP fails for 802.1Q!
    assert 14 + pkt.ip_total_length == 114
    assert pkt.captured_link_layer_length != 14 + pkt.ip_total_length


# ---------------------------------------------------------------------------
# Test 3: QinQ VLAN (802.1ad Double Tagged 22B L2 + IP total length)
# ---------------------------------------------------------------------------
def test_qinq_double_vlan() -> None:
    # 12B MACs + 2B S-Tag (0x88A8) + 2B TCI + 2B C-Tag (0x8100) + 2B TCI + 2B EtherType (0x0800) = 22B
    l2_qinq = b"\x00" * 12 + b"\x88\xa8\x00\x0a\x81\x00\x00\x14\x08\x00"
    ip_len = 100
    frame = _make_ipv4_tcp_frame(l2_qinq, ip_total_len=ip_len, payload_len=60)
    assert len(frame) == 122  # 22 + 100

    result = parse_raw_ip_bytes_detailed(frame, orig_frame_len=122, wire_len=122)
    assert result.status == ParseStatus.VALID_METADATA
    pkt = result.packet_data
    assert pkt is not None

    assert pkt.captured_link_layer_length == 122
    assert pkt.wire_length == 122
    assert pkt.captured_length == 122
    assert pkt.ip_total_length == 100
    assert pkt.wire_frame_length == 122

    # Crucial scientific check: 14 + IP fails by 8 bytes for QinQ!
    assert 14 + pkt.ip_total_length == 114
    assert pkt.captured_link_layer_length - (14 + pkt.ip_total_length) == 8


# ---------------------------------------------------------------------------
# Test 4: Ethernet Padding (small 40B IP packet padded to 60B link-layer frame)
# ---------------------------------------------------------------------------
def test_ethernet_padding_refutes_14_plus_ip() -> None:
    """
    Standard Ethernet requires a minimum frame length of 60 bytes (excluding FCS).
    A pure TCP ACK has 20B IPv4 + 20B TCP = 40B IP total length.
    With 14B Ethernet header, total is 54B.
    The NIC or switch pads 6 bytes of zeros to satisfy the 60B wire minimum.
    This test proves that 14 + IP is 54, which fails to match the genuine 60B frame length!
    """
    l2_hdr = b"\x00" * 12 + b"\x08\x00"  # 14B
    ip_len = 40  # Pure ACK: 20B IP + 20B TCP, 0 payload
    pad_bytes = b"\x00" * 6  # 6 bytes padding
    frame = _make_ipv4_tcp_frame(l2_hdr, ip_total_len=ip_len, payload_len=0, pad_bytes=pad_bytes)
    assert len(frame) == 60  # 14 + 40 + 6 = 60

    result = parse_raw_ip_bytes_detailed(frame, orig_frame_len=60, wire_len=60)
    assert result.status == ParseStatus.VALID_METADATA
    pkt = result.packet_data
    assert pkt is not None

    # Lengths
    assert pkt.captured_link_layer_length == 60
    assert pkt.wire_length == 60
    assert pkt.ip_total_length == 40
    assert pkt.captured_length == 60

    # Formal refutation of 14 + IP formula
    computed_14_plus_ip = 14 + pkt.ip_total_length
    assert computed_14_plus_ip == 54
    assert pkt.captured_link_layer_length != computed_14_plus_ip
    assert pkt.captured_link_layer_length == 60


# ---------------------------------------------------------------------------
# Test 5: IPv4 Options (IHL = 6, 24B IPv4 header)
# ---------------------------------------------------------------------------
def test_ipv4_options() -> None:
    l2_hdr = b"\x00" * 12 + b"\x08\x00"  # 14B
    # IHL = 6 (24 bytes IPv4 header), options = 4 bytes NOP NOP NOP EOL
    options = b"\x01\x01\x01\x00"
    ip_len = 24 + 20 + 30  # 24B IP + 20B TCP + 30B payload = 74B
    frame = _make_ipv4_tcp_frame(
        l2_hdr,
        ip_total_len=ip_len,
        payload_len=30,
        ihl_words=6,
        ip_options=options,
    )
    assert len(frame) == 88  # 14 + 74 = 88

    result = parse_raw_ip_bytes_detailed(frame, orig_frame_len=88, wire_len=88)
    assert result.status == ParseStatus.VALID_METADATA
    pkt = result.packet_data
    assert pkt is not None

    assert pkt.captured_link_layer_length == 88
    assert pkt.wire_length == 88
    assert pkt.ip_total_length == 74
    assert pkt.protocol == "TCP"
    # Verify TCP ports correctly extracted at offset 14 + 24 = 38
    assert pkt.src_port == 12345
    assert pkt.dst_port == 443


# ---------------------------------------------------------------------------
# Test 6: IPv6 Extension Headers (Hop-by-Hop Options)
# ---------------------------------------------------------------------------
def test_ipv6_extension_headers() -> None:
    l2_hdr = b"\x00" * 12 + b"\x86\xdd"  # 14B EtherType IPv6
    src_ip = socket.inet_pton(socket.AF_INET6, "2001:db8::1")
    dst_ip = socket.inet_pton(socket.AF_INET6, "2001:db8::2")

    # IPv6 base header: Next Header = 0 (Hop-by-Hop), payload_len = 8 (HBH) + 20 (TCP) + 20 (payload) = 48
    ipv6_base = struct.pack(
        "!IHBB16s16s",
        (6 << 28),
        48,  # payload length
        0,   # Next Header = Hop-by-Hop (0)
        64,  # Hop Limit
        src_ip,
        dst_ip,
    )

    # Hop-by-Hop header: Next Header = 6 (TCP), Hdr Ext Len = 0 (8 bytes total: (0+1)*8)
    # Options: PadN (2 bytes type 1, len 4, 4 zero bytes)
    hbh_hdr = struct.pack("!BB6s", 6, 0, b"\x01\x04\x00\x00\x00\x00")

    tcp_hdr = struct.pack("!HHIIBBHHH", 40000, 443, 1, 0, (5 << 4), 0x18, 65535, 0, 0)
    payload = b"B" * 20
    frame = l2_hdr + ipv6_base + hbh_hdr + tcp_hdr + payload
    assert len(frame) == 14 + 40 + 8 + 20 + 20  # 102 bytes

    result = parse_raw_ip_bytes_detailed(frame, orig_frame_len=102, wire_len=102)
    assert result.status == ParseStatus.VALID_METADATA
    pkt = result.packet_data
    assert pkt is not None

    assert pkt.captured_link_layer_length == 102
    assert pkt.wire_length == 102
    assert pkt.ip_total_length == 88  # 40B base + 48B payload
    assert pkt.protocol == "TCP"
    assert pkt.src_port == 40000
    assert pkt.dst_port == 443


# ---------------------------------------------------------------------------
# Test 7: User-Space Packet Truncation (snaplen 96 vs 500B wire frame)
# ---------------------------------------------------------------------------
def test_user_space_packet_truncation() -> None:
    l2_hdr = b"\x00" * 12 + b"\x08\x00"  # 14B
    ip_len = 486  # 20B IP + 20B TCP + 446B payload
    full_frame = _make_ipv4_tcp_frame(l2_hdr, ip_total_len=ip_len, payload_len=446)
    assert len(full_frame) == 500

    # User-space truncation to snaplen 96
    truncated_slice = full_frame[:96]
    assert len(truncated_slice) == 96

    result = parse_raw_ip_bytes_detailed(
        truncated_slice,
        orig_frame_len=500,
        wire_len=500,
    )
    assert result.status == ParseStatus.VALID_METADATA
    pkt = result.packet_data
    assert pkt is not None

    # Distinct separation
    assert pkt.captured_length == 96  # Bytes in RAM
    assert pkt.captured_link_layer_length == 500  # Frame length before truncation
    assert pkt.wire_length == 500  # Canonical feature length
    assert pkt.wire_frame_length == 500  # Passed wire len
    assert pkt.ip_total_length == 486  # From IP header


# ---------------------------------------------------------------------------
# Test 8: Missing Native Wire Length (Live Scapy wirelen is None)
# ---------------------------------------------------------------------------
def test_missing_native_wire_length() -> None:
    try:
        from scapy.layers.inet import IP, TCP
        scapy_pkt = IP(src="192.168.1.50", dst="1.1.1.1") / TCP(sport=5555, dport=80)
    except Exception:
        pytest.skip("Scapy layers unavailable")

    # In live Scapy capture on Windows, wirelen attribute is None or missing
    assert getattr(scapy_pkt, "wirelen", None) is None

    result = parse_scapy_packet_detailed(scapy_pkt)
    assert result.status == ParseStatus.VALID_METADATA
    pkt = result.packet_data
    assert pkt is not None

    # wire_frame_length MUST be recorded as None (UNAVAILABLE), not fabricated!
    assert pkt.wire_frame_length is None
    # Canonical length is len(scapy_pkt)
    assert pkt.captured_link_layer_length == len(scapy_pkt)
    assert pkt.wire_length == len(scapy_pkt)
    assert pkt.captured_length == len(scapy_pkt)

    # In schema record:
    fm = FlowManager(session_id="test_sess_08")
    rec, _ = fm.process_packet(pkt)
    assert rec.wire_frame_length_bytes is None
    assert rec.packet_length == len(scapy_pkt)
    assert rec.captured_link_layer_length_bytes == len(scapy_pkt)


# ---------------------------------------------------------------------------
# Test 9: Packet Length Versus Captured Length
# ---------------------------------------------------------------------------
def test_packet_length_vs_captured_length() -> None:
    """
    Validates that packet_length == captured_link_layer_length_bytes != captured_length_bytes,
    and that JSON serialization/deserialization retains all 5 distinct fields.
    """
    rec = PacketMetadataRecord(
        session_id="sess_len_01",
        flow_id="flow_1234567890abcdef",
        parent_flow_id="flow_1234567890abcdef",
        packet_index=0,
        relative_timestamp_us=0,
        inter_arrival_time_us=0,
        packet_length=1500,
        captured_link_layer_length_bytes=1500,
        captured_length_bytes=96,
        wire_frame_length_bytes=None,
        ip_total_length_bytes=1486,
        direction=0,
        transport_protocol="TCP",
        tcp_flags=0x02,
        is_synthetic=False,
    )

    assert rec.packet_length == 1500
    assert rec.captured_link_layer_length_bytes == 1500
    assert rec.captured_length_bytes == 96
    assert rec.wire_frame_length_bytes is None
    assert rec.ip_total_length_bytes == 1486
    assert rec.packet_length != rec.captured_length_bytes

    # Roundtrip serialization
    d = rec.to_dict()
    assert d["packet_length"] == 1500
    assert d["captured_link_layer_length_bytes"] == 1500
    assert d["captured_length_bytes"] == 96
    assert d["wire_frame_length_bytes"] is None
    assert d["ip_total_length_bytes"] == 1486

    raw_json = json.dumps(d)
    restored = PacketMetadataRecord.from_dict(json.loads(raw_json))
    assert restored.packet_length == 1500
    assert restored.captured_link_layer_length_bytes == 1500
    assert restored.captured_length_bytes == 96
    assert restored.wire_frame_length_bytes is None
    assert restored.ip_total_length_bytes == 1486


# ---------------------------------------------------------------------------
# Test 10: Exact Compatibility with Production len(pkt) Feature Convention
# ---------------------------------------------------------------------------
def test_production_feature_extractor_parity() -> None:
    """
    Verifies that Dataset V3's canonical packet_length produces EXACT numerical
    feature values matching production FeatureExtractor.
    """
    from capture.packet_capture import RawPacketMetadata
    from flows.flow_generator import Direction, Flow, FlowKey

    # Construct mock bidirectional flow
    key = FlowKey(
        ip_a="192.168.1.10",
        port_a=50000,
        ip_b="104.244.42.1",
        port_b=443,
        protocol="TCP",
    )
    flow = Flow(
        key=key,
        initiator_ip="192.168.1.10",
        initiator_port=50000,
        start_time=1000.0,
        last_seen=1000.0,
    )

    # Simulate 5 packets in production: RawPacketMetadata(length=len(pkt))
    # Packet lengths: 54, 60, 500, 1500, 128
    simulated_lengths = [54, 60, 500, 1500, 128]
    timestamps = [1000.0, 1000.01, 1000.05, 1000.10, 1000.20]

    for ts, length in zip(timestamps, simulated_lengths):
        pkt = RawPacketMetadata(
            timestamp=ts,
            src_ip="192.168.1.10",
            dst_ip="104.244.42.1",
            src_port=50000,
            dst_port=443,
            protocol="TCP",
            length=length,
            tcp_flags=0x18,
        )
        flow.add_packet(pkt)

    extractor = FeatureExtractor()
    features = extractor.extract_features(flow)

    assert features is not None
    # Verify production statistics on simulated_lengths
    assert features["min_packet_size"] == min(simulated_lengths)
    assert features["max_packet_size"] == max(simulated_lengths)
    assert features["avg_packet_size"] == sum(simulated_lengths) / len(simulated_lengths)
    assert features["total_packet_count"] == 5
    assert features["forward_bytes"] == sum(simulated_lengths)

    # Now verify that Dataset V3 PacketMetadataRecord with packet_length provides
    # identical numbers:
    flow_v3 = Flow(
        key=key,
        initiator_ip="192.168.1.10",
        initiator_port=50000,
        start_time=1000.0,
        last_seen=1000.0,
    )
    for i, (ts, length) in enumerate(zip(timestamps, simulated_lengths)):
        v3_rec = PacketMetadataRecord(
            session_id="sess_parity_01",
            flow_id="flow_parity",
            parent_flow_id="flow_parity",
            packet_index=i,
            relative_timestamp_us=int((ts - 1000.0) * 1e6),
            inter_arrival_time_us=0,
            packet_length=length,  # Canonical feature length
            captured_link_layer_length_bytes=length,
            captured_length_bytes=min(length, 96),  # Truncated in RAM
            wire_frame_length_bytes=None,
            ip_total_length_bytes=length - 14,
            direction=0,
            transport_protocol="TCP",
        )
        # Using canonical packet_length
        pkt = RawPacketMetadata(
            timestamp=ts,
            src_ip="192.168.1.10",
            dst_ip="104.244.42.1",
            src_port=50000,
            dst_port=443,
            protocol="TCP",
            length=v3_rec.packet_length,
            tcp_flags=0x18,
        )
        flow_v3.add_packet(pkt)

    features_v3 = extractor.extract_features(flow_v3)
    assert features_v3 is not None

    # Absolute exact parity across all size and byte metrics
    assert features_v3["min_packet_size"] == features["min_packet_size"]
    assert features_v3["max_packet_size"] == features["max_packet_size"]
    assert features_v3["avg_packet_size"] == features["avg_packet_size"]
    assert features_v3["packet_size_variance"] == features["packet_size_variance"]
    assert features_v3["forward_bytes"] == features["forward_bytes"]
    assert features_v3["total_packet_count"] == features["total_packet_count"]

    # Critical divergence check: if someone had mistakenly extracted features from
    # captured_length_bytes (truncated at 96B), features would be completely corrupt!
    corrupt_lengths = [min(l, 96) for l in simulated_lengths]
    corrupt_avg = sum(corrupt_lengths) / len(corrupt_lengths)
    assert corrupt_avg != features["avg_packet_size"]
    assert max(corrupt_lengths) == 96 != features["max_packet_size"]
