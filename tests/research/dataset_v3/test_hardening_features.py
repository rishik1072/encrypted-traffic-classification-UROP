"""
Unit Tests: Dataset V3 Hardening Features (Phase 2A.2).

Validates:
- Snaplen payload truncation (captured length vs original wire length).
- Explicit header parsing diagnostic states (VALID, TRUNCATED, FRAGMENT, UNSUPPORTED, MALFORMED).
- 802.1Q VLAN header handling.
- Device pseudonym persistence across sessions on the same device.
- Drop and error telemetry tracking in session manifest.
- SHA-256 file integrity verification and tamper detection.
"""

from __future__ import annotations

import socket
import struct
import time
from pathlib import Path
import pytest

from research.dataset_v3.collector import PhysicalTrafficCollector
from research.dataset_v3.config import DatasetV3Config, get_or_create_device_pseudonym
from research.dataset_v3.flow_manager import FlowManager
from research.dataset_v3.manifest import ManifestManager
from research.dataset_v3.metadata_writer import MetadataWriter
from research.dataset_v3.packet_parser import (
    ParseStatus,
    TransientPacketData,
    parse_raw_ip_bytes,
    parse_raw_ip_bytes_detailed,
)
from research.dataset_v3.schemas import (
    FlowIndexRecord,
    LabelRecord,
    PacketMetadataRecord,
    SessionManifest,
)
from research.dataset_v3.validator import DatasetV3Validator
from tests.research.dataset_v3.test_validator import create_mock_session


def test_snaplen_truncation_parsing() -> None:
    # Build a raw IPv4/TCP packet with 500 bytes of payload (total wire length = 540 bytes)
    src_bytes = socket.inet_aton("192.168.1.10")
    dst_bytes = socket.inet_aton("10.0.0.1")
    tcp_hdr = struct.pack("!HHIIBBHHH", 50000, 443, 1000, 0, (5 << 4), 0x18, 65535, 0, 0)
    ip_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 540, 1, 0, 64, 6, 0, src_bytes, dst_bytes)
    full_wire_packet = ip_hdr + tcp_hdr + (b"X" * 500)

    assert len(full_wire_packet) == 540

    # Simulate snaplen=96 kernel truncation: user-space Scapy/receiver only gets first 96 bytes!
    truncated_bytes = full_wire_packet[:96]
    assert len(truncated_bytes) == 96

    # Parse truncated bytes with known original wire frame length
    t_pkt = parse_raw_ip_bytes(truncated_bytes, ts=100.0, orig_frame_len=540)
    assert t_pkt is not None
    assert t_pkt.wire_length == 540  # Original frame length
    assert t_pkt.captured_link_layer_length == 540
    assert t_pkt.ip_total_length == 540  # Extracted from IP total length header!
    assert t_pkt.captured_length == 96  # Actual bytes received into volatile RAM!
    assert t_pkt.protocol == "TCP"
    assert t_pkt.src_port == 50000
    assert t_pkt.dst_port == 443


def test_header_parsing_explicit_states() -> None:
    src_bytes = socket.inet_aton("192.168.1.10")
    dst_bytes = socket.inet_aton("10.0.0.1")

    # 1. VALID_METADATA: Standard IPv4 / TCP
    ip_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 40, 1, 0, 64, 6, 0, src_bytes, dst_bytes)
    tcp_hdr = struct.pack("!HHIIBBHHH", 50000, 443, 1, 0, (5 << 4), 0x02, 65535, 0, 0)
    res_valid = parse_raw_ip_bytes_detailed(ip_hdr + tcp_hdr)
    assert res_valid.status == ParseStatus.VALID_METADATA
    assert res_valid.packet_data is not None
    assert res_valid.packet_data.protocol == "TCP"

    # 2. TRUNCATED_HEADER: Cut off in middle of TCP header (only 10 TCP bytes)
    res_trunc = parse_raw_ip_bytes_detailed(ip_hdr + tcp_hdr[:10])
    assert res_trunc.status == ParseStatus.TRUNCATED_HEADER
    assert res_trunc.packet_data is None

    # 3. FRAGMENT_UNSUPPORTED: Non-initial IPv4 fragment (frag_offset = 64 bytes)
    ip_frag_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 80, 1, (8 & 0x1FFF), 64, 6, 0, src_bytes, dst_bytes)
    res_frag = parse_raw_ip_bytes_detailed(ip_frag_hdr + (b"X" * 60))
    assert res_frag.status == ParseStatus.FRAGMENT_UNSUPPORTED
    assert res_frag.packet_data is None

    # 4. UNSUPPORTED_PROTOCOL: ICMP (protocol 1)
    ip_icmp_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 28, 1, 0, 64, 1, 0, src_bytes, dst_bytes)
    icmp_hdr = struct.pack("!BBHHH", 8, 0, 0, 1234, 1)
    res_icmp = parse_raw_ip_bytes_detailed(ip_icmp_hdr + icmp_hdr)
    assert res_icmp.status == ParseStatus.UNSUPPORTED_PROTOCOL
    assert res_icmp.packet_data is None

    # 5. MALFORMED_PACKET: Invalid IHL (IHL = 3 -> 12 bytes < 20 minimum)
    ip_bad_ihl = struct.pack("!BBHHHBBH4s4s", 0x43, 0, 40, 1, 0, 64, 6, 0, src_bytes, dst_bytes)
    res_malformed = parse_raw_ip_bytes_detailed(ip_bad_ihl + tcp_hdr)
    assert res_malformed.status == ParseStatus.MALFORMED_PACKET
    assert res_malformed.packet_data is None

    # 6. VLAN 802.1Q Frame
    eth_vlan_hdr = (
        b"\x00\x11\x22\x33\x44\x55"  # DMAC
        b"\x66\x77\x88\x99\xaa\xbb"  # SMAC
        b"\x81\x00"                  # 802.1Q EtherType
        b"\x00\x64"                  # VLAN ID 100
        b"\x08\x00"                  # Inner EtherType IPv4
    )
    vlan_frame = eth_vlan_hdr + ip_hdr + tcp_hdr
    res_vlan = parse_raw_ip_bytes_detailed(vlan_frame)
    assert res_vlan.status == ParseStatus.VALID_METADATA
    assert res_vlan.packet_data is not None
    assert res_vlan.packet_data.src_port == 50000


def test_device_pseudonym_persistence(tmp_path: Path) -> None:
    state_dir = tmp_path / "device_state"

    # Session 1 on this machine
    token1 = get_or_create_device_pseudonym(state_dir)
    assert token1.startswith("dev_pseudonym_")

    config1 = DatasetV3Config(
        output_root=tmp_path / "data1",
        session_id="s1",
        interface="MockIf",
        device_state_dir=state_dir,
    )
    assert config1.device_pseudonym == token1

    # Session 2 on the same machine -> MUST be identical!
    config2 = DatasetV3Config(
        output_root=tmp_path / "data2",
        session_id="s2",
        interface="MockIf",
        device_state_dir=state_dir,
    )
    assert config2.device_pseudonym == token1
    assert config2.device_pseudonym == config1.device_pseudonym

    # Another machine / state dir -> receives a different pseudonym
    other_state_dir = tmp_path / "other_device_state"
    config_other = DatasetV3Config(
        output_root=tmp_path / "data3",
        session_id="s3",
        interface="MockIf",
        device_state_dir=other_state_dir,
    )
    assert config_other.device_pseudonym != token1


def test_tcp_fin_rst_termination() -> None:
    fm = FlowManager(session_id="sess_tcp_term_001")

    # Flow A: Normal TCP handshake and data
    p1 = TransientPacketData(
        wire_timestamp=100.0,
        wire_length=60,
        protocol="TCP",
        tcp_flags=0x02,  # SYN
        src_ip="192.168.1.10",
        src_port=40001,
        dst_ip="1.1.1.1",
        dst_port=443,
    )
    fm.process_packet(p1)

    # Packet with FIN flag (0x01 or has_fin=True)
    p2 = TransientPacketData(
        wire_timestamp=100.1,
        wire_length=60,
        protocol="TCP",
        tcp_flags=0x11,  # FIN + ACK
        has_fin=True,
        src_ip="192.168.1.10",
        src_port=40001,
        dst_ip="1.1.1.1",
        dst_port=443,
    )
    rec2, comp2 = fm.process_packet(p2)
    completed = fm.finalize_all()
    assert len(completed) == 1
    assert completed[0].termination_reason == "TCP_FIN"


def test_drop_telemetry_manifest_tracking(tmp_path: Path) -> None:
    config = DatasetV3Config(
        output_root=tmp_path,
        session_id="sess_drop_telemetry_001",
        interface="MockPhysicalInterface",
        snaplen=128,
        collection_day="2026-11-20",
    )
    manifest = ManifestManager.create_initial_manifest(config)
    assert manifest.snaplen == 128
    assert manifest.collection_day == "2026-11-20"
    assert manifest.queue_drops == 0
    assert manifest.parsing_failures == 0

    finalized = ManifestManager.finalize_manifest(
        manifest=manifest,
        packet_count=1000,
        flow_count=15,
        status="COMPLETE",
        kernel_buffer_drops=4,
        interface_drops=0,
        queue_drops=2,
        parsing_failures=1,
        processing_failures=0,
    )
    assert finalized.kernel_buffer_drops == 4
    assert finalized.queue_drops == 2
    assert finalized.parsing_failures == 1
    assert finalized.capture_status == "COMPLETE"


def test_file_integrity_hash_verification(tmp_path: Path) -> None:
    session_dir = tmp_path / "sess_integrity_001"
    staging_dir = tmp_path / ".staging" / "sess_integrity_001"
    incomp_dir = tmp_path / ".incomplete" / "sess_integrity_001"

    writer = MetadataWriter(
        final_dir=session_dir,
        staging_dir=staging_dir,
        incomplete_dir=incomp_dir,
        session_id="sess_integrity_001",
    )

    manifest = SessionManifest(
        session_id="sess_integrity_001",
        collection_start_utc="2026-11-20T12:00:00Z",
        collection_end_utc="2026-11-20T12:01:00Z",
        collector_version="3.0.0",
        operating_system="Windows 11",
        device_pseudonym="dev_pseudonym_123456",
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

    pkt = PacketMetadataRecord(
        session_id="sess_integrity_001",
        flow_id="flow_11111111111111111111111111111111",
        parent_flow_id="flow_11111111111111111111111111111111",
        packet_index=0,
        relative_timestamp_us=0,
        inter_arrival_time_us=0,
        packet_length=100,
        captured_length=96,
        direction=0,
        transport_protocol="TCP",
        tcp_flags=0x02,
        is_synthetic=False,
    )
    writer.write_packet(pkt)

    flow = FlowIndexRecord(
        session_id="sess_integrity_001",
        flow_id="flow_11111111111111111111111111111111",
        parent_flow_id="flow_11111111111111111111111111111111",
        first_packet_timestamp_utc="2026-11-20T12:00:00Z",
        last_packet_timestamp_utc="2026-11-20T12:00:00Z",
        packet_count=1,
        duration_us=0,
        direction_0_packets=1,
        direction_1_packets=0,
        direction_0_bytes=100,
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
        session_id="sess_integrity_001",
        flow_id="flow_11111111111111111111111111111111",
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

    # Publish complete session (computes hashes)
    published_dir = writer.publish_complete_session(manifest)
    assert (published_dir / "SESSION_COMPLETE").exists()

    validator = DatasetV3Validator()
    report = validator.validate_session(published_dir)
    assert report.is_valid is True

    # Now simulate file tampering on disk: modify labels.csv
    labels_file = published_dir / "labels.csv"
    with open(labels_file, "a", encoding="utf-8") as f:
        f.write("TAMPERED_ROW_INJECTED_AFTER_VALIDATION\n")

    report_tampered = validator.validate_session(published_dir)
    assert report_tampered.is_valid is False
    assert any("Check 22 FAIL" in err for err in report_tampered.errors)
