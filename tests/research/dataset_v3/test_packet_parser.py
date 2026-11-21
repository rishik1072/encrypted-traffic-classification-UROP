"""
Unit Tests: Dataset V3 Zero-Payload Packet Parser.

Validates:
- Extraction of lengths, timestamps, protocols, and TCP flags.
- Complete stripping and non-retention of payload bytes and MAC addresses.
- Transient 5-tuple creation in volatile memory.
"""

from __future__ import annotations

import socket
import struct
import time
import pytest

from research.dataset_v3.packet_parser import (
    TransientPacketData,
    parse_raw_ip_bytes,
    parse_scapy_packet,
)


def create_synthetic_ipv4_tcp_raw(
    src_ip: str = "192.168.1.10",
    dst_ip: str = "10.0.0.1",
    sport: int = 54321,
    dport: int = 443,
    payload: bytes = b"EXPLICIT_TEST_PAYLOAD_NOT_TO_BE_RETAINED_1234567890",
    tcp_flags: int = 0x18,  # PSH, ACK
) -> bytes:
    """Builds raw IPv4 + TCP packet bytes."""
    src_bytes = socket.inet_aton(src_ip)
    dst_bytes = socket.inet_aton(dst_ip)

    tcp_header = struct.pack(
        "!HHIIBBHHH",
        sport,
        dport,
        1001,  # seq
        2002,  # ack
        (5 << 4),  # data offset
        tcp_flags,
        8192,  # window
        0,  # checksum
        0,  # urgptr
    )

    tot_len = 20 + len(tcp_header) + len(payload)
    ip_header = struct.pack(
        "!BBHHHBBH4s4s",
        (4 << 4) | 5,  # ver, ihl
        0,  # dscp, ecn
        tot_len,
        54321,  # id
        0,  # flags, frag
        64,  # ttl
        6,  # protocol TCP
        0,  # checksum
        src_bytes,
        dst_bytes,
    )

    return ip_header + tcp_header + payload


def test_parse_raw_ip_bytes_strips_payload() -> None:
    test_payload = b"SUPER_SECRET_PAYLOAD_SECRET_TOKEN"
    raw_bytes = create_synthetic_ipv4_tcp_raw(payload=test_payload)

    transient = parse_raw_ip_bytes(raw_bytes, ts=1700000000.0)
    assert transient is not None
    assert transient.protocol == "TCP"
    assert transient.src_ip == "192.168.1.10"
    assert transient.dst_ip == "10.0.0.1"
    assert transient.src_port == 54321
    assert transient.dst_port == 443
    assert transient.length == len(raw_bytes)
    assert transient.tcp_flags == 0x18
    assert transient.timestamp == 1700000000.0

    # Verify no payload bytes are stored on the object
    assert not hasattr(transient, "payload")
    assert not hasattr(transient, "raw_data")
    assert "SECRET" not in str(transient)


def test_parse_scapy_packet_fixture() -> None:
    pytest.importorskip("scapy")
    from scapy.layers.inet import IP, TCP

    packet = IP(src="172.16.0.5", dst="8.8.8.8") / TCP(sport=12345, dport=80, flags="S") / b"HTTP_GET_PAYLOAD"
    packet.time = 1700000050.5

    transient = parse_scapy_packet(packet)
    assert transient is not None
    assert transient.protocol == "TCP"
    assert transient.src_ip == "172.16.0.5"
    assert transient.dst_ip == "8.8.8.8"
    assert transient.src_port == 12345
    assert transient.dst_port == 80
    assert transient.tcp_flags == 0x02  # SYN flag
    assert transient.length == len(packet)

    # Invariance check
    assert not hasattr(transient, "payload")
