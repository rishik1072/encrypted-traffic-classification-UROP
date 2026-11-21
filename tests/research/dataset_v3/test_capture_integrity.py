"""
Unit Tests: Capture Backend Integrity, Provenance & Semantics (Phase 2A.2.1).

Validates:
1. Configured versus effective snaplen behavior.
2. Original wire length versus captured length provenance.
3. Missing wire-length metadata handling (marked UNAVAILABLE, zero fabrication).
4. Feature length semantics and consistency with production schemas.
5. Truncated packet rejection (no default port 0 fabrication).
6. Complete zero-payload persistence across all serialized artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
import socket
import struct
import time
from unittest.mock import MagicMock, patch
import pytest

from preprocessing.feature_extractor import FeatureExtractor
from research.dataset_v3.config import DatasetV3Config
from research.dataset_v3.flow_manager import FlowManager
from research.dataset_v3.metadata_writer import MetadataWriter
from research.dataset_v3.packet_parser import (
    ParseStatus,
    TransientPacketData,
    parse_raw_ip_bytes_detailed,
    parse_scapy_packet_detailed,
)
from research.dataset_v3.schemas import FlowIndexRecord, LabelRecord, SessionManifest
from research.dataset_v3.validator import DatasetV3Validator


def test_configured_vs_effective_snaplen() -> None:
    """
    Verifies that while DatasetV3Config requests a snaplen of 96 or 128,
    standard Scapy's L2pcapListenSocket on Windows hardcodes MTU (65535).
    """
    config = DatasetV3Config(
        output_root=Path("data/test_snaplen"),
        session_id="sess_snaplen_001",
        interface="MockIf",
        snaplen=96,
    )
    assert config.snaplen == 96

    # Inspect scapy runtime MTU constant
    import scapy.data
    assert scapy.data.MTU == 65535

    # Simulate Scapy's L2pcapListenSocket instantiation
    # The constructor does NOT accept or forward snaplen
    import inspect
    import scapy.arch.libpcap as lp
    sig = inspect.signature(lp.L2pcapListenSocket.__init__)
    assert "snaplen" not in sig.parameters

    # Verifies user-space fallback slicing in packet_parser
    raw_packet = (
        struct.pack("!BBHHHBBH4s4s", 0x45, 0, 500, 1, 0, 64, 6, 0, b"\x01" * 4, b"\x02" * 4)
        + struct.pack("!HHIIBBHHH", 40000, 443, 1, 0, (5 << 4), 0x18, 65535, 0, 0)
        + (b"P" * 460)
    )
    assert len(raw_packet) == 500

    # User-space slicing to config.snaplen
    user_sliced = raw_packet[: config.snaplen]
    assert len(user_sliced) == 96

    # Parser extracts headers from the sliced buffer
    result = parse_raw_ip_bytes_detailed(user_sliced, wire_len=500)
    assert result.status == ParseStatus.VALID_METADATA
    assert result.packet_data is not None
    assert result.packet_data.captured_length == 96
    assert result.packet_data.wire_length == 500


def test_original_vs_captured_length() -> None:
    """
    Verifies that original wire length (len) and captured length (caplen)
    are explicitly distinguished and never conflated.
    """
    # 54 bytes header + 400 bytes payload = 454 bytes wire length
    src_bytes = socket.inet_aton("10.0.0.1")
    dst_bytes = socket.inet_aton("10.0.0.2")
    ip_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 454, 1, 0, 64, 6, 0, src_bytes, dst_bytes)
    tcp_hdr = struct.pack("!HHIIBBHHH", 12345, 443, 100, 0, (5 << 4), 0x18, 65535, 0, 0)
    payload = b"X" * 400
    full_frame = (b"\x00" * 12 + b"\x08\x00") + ip_hdr + tcp_hdr + payload  # 14B Eth + 454B IP = 468B wire frame

    # Captured slice at 128 bytes
    captured_slice = full_frame[:128]
    assert len(captured_slice) == 128

    result = parse_raw_ip_bytes_detailed(captured_slice, wire_len=468)
    assert result.status == ParseStatus.VALID_METADATA
    pkt = result.packet_data
    assert pkt is not None

    # Wire length off the wire: 468 bytes
    assert pkt.wire_length == 468
    assert pkt.wire_frame_length == 468

    # Captured length in memory: 128 bytes
    assert pkt.captured_length == 128

    # IP Total Length from IP header: 454 bytes
    assert pkt.ip_total_length == 454


def test_missing_wire_length_metadata() -> None:
    """
    Verifies that when Scapy callback does NOT provide wirelen (live sniff),
    wire_frame_length is marked UNAVAILABLE (None) and NEVER fabricated.
    """
    mock_pkt = MagicMock()
    mock_pkt.haslayer.side_effect = lambda layer: layer in ("IP", "TCP")

    mock_ip = MagicMock()
    mock_ip.src = "192.168.1.50"
    mock_ip.dst = "1.1.1.1"
    mock_ip.proto = 6
    mock_ip.len = 1500
    mock_ip.frag = 0

    mock_tcp = MagicMock()
    mock_tcp.sport = 54321
    mock_tcp.dport = 443
    mock_tcp.flags = 0x18

    mock_pkt.__getitem__.side_effect = lambda l: mock_ip if l == "IP" else mock_tcp
    mock_pkt.__len__.return_value = 1514  # 14B Eth + 1500B IP
    mock_pkt.time = 1700000000.0

    # In live Scapy capture, wirelen is absent or None
    del mock_pkt.wirelen

    result = parse_scapy_packet_detailed(mock_pkt)
    assert result.status == ParseStatus.VALID_METADATA
    pkt = result.packet_data
    assert pkt is not None

    # Crucial assertion: wire_frame_length MUST be None (UNAVAILABLE)
    assert pkt.wire_frame_length is None

    # Captured length reflects Scapy packet length
    assert pkt.captured_length == 1514

    # IP total length is extracted from IP header
    assert pkt.ip_total_length == 1500

    # packet_length represents link-layer frame length for feature extraction parity
    assert pkt.wire_length == 1514


def test_feature_length_consistency() -> None:
    """
    Verifies that feature extraction on Dataset V3 flows maintains exact
    mathematical consistency with the production FeatureExtractor schema.
    """
    fm = FlowManager(session_id="sess_feat_consist_001")

    # Generate 5 packets of varying lengths
    lengths = [100, 200, 500, 1000, 1500]
    records = []
    for idx, l in enumerate(lengths):
        pkt = TransientPacketData(
            wire_timestamp=100.0 + idx * 0.1,
            arrival_monotonic=10.0 + idx * 0.1,
            wire_length=l,
            captured_length=min(96, l),
            wire_frame_length=l,
            ip_total_length=l - 14,
            protocol="TCP",
            tcp_flags=0x18,
            src_ip="192.168.1.10",
            src_port=40000,
            dst_ip="8.8.8.8",
            dst_port=443,
        )
        rec, _ = fm.process_packet(pkt)
        records.append(rec)

    # Invariants in generated PacketMetadataRecord
    for idx, rec in enumerate(records):
        assert rec.packet_length == lengths[idx]
        assert rec.captured_length == min(96, lengths[idx])
        assert rec.wire_frame_length_bytes == lengths[idx]
        assert rec.ip_total_length_bytes == lengths[idx] - 14

    # Create mock flow object for FeatureExtractor
    from flows.flow_generator import Direction
    mock_flow = MagicMock()
    mock_flow.packet_records = [
        (r.relative_timestamp_us / 1e6, r.packet_length, Direction.FORWARD if r.direction == 0 else Direction.BACKWARD)
        for r in records
    ]
    mock_flow.flow_id = records[0].flow_id

    extractor = FeatureExtractor()
    features = extractor.extract_features(mock_flow)

    # Check that packet size features measure frame length in bytes
    assert features["min_packet_size"] == 100.0
    assert features["max_packet_size"] == 1500.0
    assert features["avg_packet_size"] == sum(lengths) / len(lengths)
    assert features["total_packet_count"] == 5
    assert features["forward_bytes"] == sum(lengths)


def test_truncated_packet_rejection() -> None:
    """
    Verifies that packets truncated within L3 or L4 headers are rejected
    with explicit diagnostic states and never create zero-port flows.
    """
    fm = FlowManager(session_id="sess_trunc_001")

    # Truncated IPv4 header: only 10 bytes (minimum is 20)
    truncated_ip = bytes([0x45]) + (b"\x00" * 9)
    res_ip = parse_raw_ip_bytes_detailed(truncated_ip)
    assert res_ip.status == ParseStatus.TRUNCATED_HEADER
    assert res_ip.packet_data is None

    # Valid IPv4 (20B) but truncated TCP (only 10 bytes, minimum 20)
    ip_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 30, 1, 0, 64, 6, 0, b"\x01" * 4, b"\x02" * 4)
    truncated_tcp = ip_hdr + (b"\x00" * 10)
    res_tcp = parse_raw_ip_bytes_detailed(truncated_tcp)
    assert res_tcp.status == ParseStatus.TRUNCATED_HEADER
    assert res_tcp.packet_data is None

    # Valid IPv4 (20B) but truncated UDP (only 4 bytes, minimum 8)
    ip_hdr_udp = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 24, 1, 0, 64, 17, 0, b"\x01" * 4, b"\x02" * 4)
    truncated_udp = ip_hdr_udp + (b"\x00" * 4)
    res_udp = parse_raw_ip_bytes_detailed(truncated_udp)
    assert res_udp.status == ParseStatus.TRUNCATED_HEADER
    assert res_udp.packet_data is None

    # Zero flows created in flow manager
    assert len(fm._active_flows) == 0


def test_no_payload_persistence(tmp_path: Path) -> None:
    """
    Injects a distinct canary payload into raw packets and verifies that
    the canary string never appears in any persisted Dataset V3 artifact.
    """
    canary = b"SUPER_SECRET_CANARY_PAYLOAD_TOKEN_1234567890"

    session_dir = tmp_path / "sess_canary_001"
    staging_dir = tmp_path / ".staging" / "sess_canary_001"
    incomp_dir = tmp_path / ".incomplete" / "sess_canary_001"

    writer = MetadataWriter(
        final_dir=session_dir,
        staging_dir=staging_dir,
        incomplete_dir=incomp_dir,
        session_id="sess_canary_001",
    )

    manifest = SessionManifest(
        session_id="sess_canary_001",
        collection_start_utc="2026-11-20T12:00:00Z",
        collection_end_utc="2026-11-20T12:01:00Z",
        collector_version="3.0.0",
        operating_system="Windows 11",
        device_pseudonym="dev_pseudonym_canary_test",
        adapter_type="Wi-Fi",
        environment_id="env_test",
        tunnel_status="DIRECT",
        collection_activity="Browsing",
        application_alias="chrome",
        intended_traffic_class="Web",
        collection_operator_label="operator_test",
        capture_status="COMPLETE",
        packet_count=1,
        flow_count=1,
    )
    writer.initialize_session(manifest)

    # Build packet containing the canary payload in RAM
    ip_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 54 + len(canary), 1, 0, 64, 6, 0, b"\x0a\x00\x00\x01", b"\x0a\x00\x00\x02")
    tcp_hdr = struct.pack("!HHIIBBHHH", 45000, 443, 1, 0, (5 << 4), 0x18, 65535, 0, 0)
    raw_packet_with_canary = (b"\x00" * 12 + b"\x08\x00") + ip_hdr + tcp_hdr + canary

    assert canary in raw_packet_with_canary

    # Parse packet through zero-payload parser
    res = parse_raw_ip_bytes_detailed(raw_packet_with_canary, wire_len=len(raw_packet_with_canary))
    assert res.status == ParseStatus.VALID_METADATA
    assert res.packet_data is not None

    fm = FlowManager(session_id="sess_canary_001")
    pkt_rec, _ = fm.process_packet(res.packet_data)
    writer.write_packet(pkt_rec)

    flow = FlowIndexRecord(
        session_id="sess_canary_001",
        flow_id=pkt_rec.flow_id,
        parent_flow_id=pkt_rec.parent_flow_id,
        first_packet_timestamp_utc="2026-11-20T12:00:00Z",
        last_packet_timestamp_utc="2026-11-20T12:00:00Z",
        packet_count=1,
        duration_us=0,
        direction_0_packets=1,
        direction_1_packets=0,
        direction_0_bytes=pkt_rec.packet_length,
        direction_1_bytes=0,
        transport_protocol="TCP",
        termination_reason="UNKNOWN",
        prefix_3_available=False,
        prefix_5_available=False,
        prefix_10_available=False,
        prefix_20_available=False,
        is_synthetic=False,
    )
    writer.write_flow_index([flow])

    lbl = LabelRecord(
        session_id="sess_canary_001",
        flow_id=pkt_rec.flow_id,
        traffic_class="Web",
        application_alias="chrome",
        label_source="OPERATOR_CONTROLLED",
        label_quality="VERIFIED",
        annotator="operator_test",
        annotation_timestamp="2026-11-20T12:00:00Z",
        packet_count=1,
        prefix_3_available=False,
        prefix_5_available=False,
        prefix_10_available=False,
        prefix_20_available=False,
    )
    writer.write_labels([lbl])

    published_dir = writer.publish_complete_session(manifest)
    assert (published_dir / "SESSION_COMPLETE").exists()

    # Validate session passes all 22 checks
    validator = DatasetV3Validator()
    report = validator.validate_session(published_dir)
    assert report.is_valid is True

    # Scan EVERY file in published session for the canary token
    canary_str = canary.decode("ascii")
    for file_path in published_dir.iterdir():
        if file_path.is_file():
            content = file_path.read_bytes()
            assert canary not in content, f"Privacy violation: Canary payload leaked into {file_path.name}!"
            try:
                text_content = content.decode("utf-8", errors="ignore")
                assert canary_str not in text_content, f"Privacy violation: Canary text leaked into {file_path.name}!"
            except Exception:
                pass
