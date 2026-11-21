"""
Zero-Payload Transient Packet Parser for Dataset V3.

Extracts Layer-3/Layer-4 metadata, TCP termination flags, and transient 5-tuples.
Strictly strips and discards all payload bytes, MAC addresses, and application data.
Distinguishes original on-the-wire length from captured length when snaplen truncation is active.
"""

from __future__ import annotations

import logging
import struct
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("research.dataset_v3.packet_parser")


class ParseStatus(str, Enum):
    """
    Explicit diagnostic parsing states for captured packet evaluation.
    Guarantees that truncated, malformed, or unhandled frames never fabricate valid flows.
    """
    VALID_METADATA = "VALID_METADATA"
    TRUNCATED_HEADER = "TRUNCATED_HEADER"
    UNSUPPORTED_PROTOCOL = "UNSUPPORTED_PROTOCOL"
    MALFORMED_PACKET = "MALFORMED_PACKET"
    FRAGMENT_UNSUPPORTED = "FRAGMENT_UNSUPPORTED"


@dataclass(frozen=True)
class PacketParseResult:
    """Detailed parsing outcome containing status, transient data (if valid), and diagnostics."""
    status: ParseStatus
    packet_data: Optional[TransientPacketData] = None
    diagnostics: str = ""


def _init_scapy() -> None:
    """Safely pre-initializes Scapy layer definitions."""
    try:
        import platform
        if platform.system() == "Windows":
            import scapy.layers.l2
            import scapy.layers.inet
    except Exception as e:
        logger.debug("Scapy safe initialization note: %s", e)


_init_scapy()


@dataclass(frozen=True, init=False)
class TransientPacketData:
    """
    Transient, volatile in-memory packet representation.
    Used strictly inside the collection worker to update the flow manager.
    NEVER written to disk or logged.
    """
    wire_timestamp: float  # Timestamp from capture hardware / packet header
    arrival_monotonic: float  # Monotonic clock timestamp when callback received packet
    wire_length: int  # Canonical feature length matching production len(pkt)
    captured_link_layer_length: int  # Delivered link-layer frame length before truncation
    captured_length: int  # Bytes in buffer available to metadata parser after truncation
    wire_frame_length: Optional[int]  # Native pcap_pkthdr.len (None / UNAVAILABLE if not exposed)
    ip_total_length: Optional[int]  # Layer 3 IP Total Length from header
    protocol: str  # TCP, UDP, OTHER
    tcp_flags: Optional[int]
    has_fin: bool
    has_rst: bool
    # Volatile 5-tuple used ONLY for in-memory flow indexing:
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int

    def __init__(
        self,
        wire_timestamp: Optional[float] = None,
        arrival_monotonic: float = 0.0,
        wire_length: Optional[int] = None,
        captured_length: Optional[int] = None,
        wire_frame_length: Optional[int] = None,
        ip_total_length: Optional[int] = None,
        captured_link_layer_length: Optional[int] = None,
        protocol: str = "OTHER",
        tcp_flags: Optional[int] = None,
        has_fin: bool = False,
        has_rst: bool = False,
        src_ip: str = "",
        src_port: int = 0,
        dst_ip: str = "",
        dst_port: int = 0,
        timestamp: Optional[float] = None,
        length: Optional[int] = None,
    ) -> None:
        ts = wire_timestamp if wire_timestamp is not None else (timestamp if timestamp is not None else 0.0)
        raw_len = wire_length if wire_length is not None else (length if length is not None else 0)
        link_len = captured_link_layer_length if captured_link_layer_length is not None else raw_len
        c_len = captured_length if captured_length is not None else link_len

        object.__setattr__(self, "wire_timestamp", float(ts))
        object.__setattr__(self, "arrival_monotonic", float(arrival_monotonic))
        object.__setattr__(self, "wire_length", int(link_len))
        object.__setattr__(self, "captured_link_layer_length", int(link_len))
        object.__setattr__(self, "captured_length", int(c_len))
        object.__setattr__(self, "wire_frame_length", wire_frame_length)
        object.__setattr__(self, "ip_total_length", ip_total_length)
        object.__setattr__(self, "protocol", str(protocol))
        object.__setattr__(self, "tcp_flags", tcp_flags)
        object.__setattr__(self, "has_fin", bool(has_fin))
        object.__setattr__(self, "has_rst", bool(has_rst))
        object.__setattr__(self, "src_ip", str(src_ip))
        object.__setattr__(self, "src_port", int(src_port))
        object.__setattr__(self, "dst_ip", str(dst_ip))
        object.__setattr__(self, "dst_port", int(dst_port))

    @property
    def timestamp(self) -> float:
        return self.wire_timestamp

    @property
    def length(self) -> int:
        return self.wire_length


def parse_scapy_packet_detailed(
    packet: Any,
    arrival_mono: Optional[float] = None,
    user_snaplen: Optional[int] = None,
) -> PacketParseResult:
    """
    Parses a live Scapy packet or test fixture with rigorous header validation.
    Extracts purely zero-payload timing, link-layer frame length, IP total length,
    protocol, flags, and transient 5-tuple.
    Discards the raw packet and payload bytes immediately.
    """
    if arrival_mono is None:
        arrival_mono = time.monotonic()

    try:
        # Check for IP or IPv6 layer
        has_ip = packet.haslayer("IP")
        has_ipv6 = packet.haslayer("IPv6")

        if not has_ip and not has_ipv6:
            return PacketParseResult(
                ParseStatus.UNSUPPORTED_PROTOCOL,
                diagnostics="Frame does not contain an IP or IPv6 network layer.",
            )

        # 1. Complete Scapy-delivered frame length before user-space truncation
        captured_link_layer_len = len(packet)

        # 2. Native wire length from driver if genuinely available (pcap_pkthdr.len)
        raw_wirelen = getattr(packet, "wirelen", None)
        wire_frame_len = int(raw_wirelen) if (raw_wirelen is not None and raw_wirelen > 0) else None

        # 3. Captured length in memory after any configured user-space truncation
        captured_len = (
            min(captured_link_layer_len, user_snaplen)
            if (user_snaplen is not None and user_snaplen > 0)
            else captured_link_layer_len
        )

        ts = float(getattr(packet, "time", time.time()))

        ip_total_len: Optional[int] = None
        if has_ip:
            ip_layer = packet["IP"]
            # Check IPv4 fragmentation: non-initial fragments have frag > 0 and NO L4 header!
            frag_offset = int(getattr(ip_layer, "frag", 0))
            if frag_offset > 0:
                return PacketParseResult(
                    ParseStatus.FRAGMENT_UNSUPPORTED,
                    diagnostics=f"Non-initial IPv4 fragment (frag_offset={frag_offset}). L4 header absent.",
                )
            try:
                ip_total_len = int(getattr(ip_layer, "len", 0))
            except Exception:
                ip_total_len = None
            src_ip = str(ip_layer.src)
            dst_ip = str(ip_layer.dst)
            proto_num = int(ip_layer.proto)
        else:
            ip_layer = packet["IPv6"]
            if packet.haslayer("IPv6ExtHdrFragment"):
                frag_hdr = packet["IPv6ExtHdrFragment"]
                if int(getattr(frag_hdr, "offset", 0)) > 0:
                    return PacketParseResult(
                        ParseStatus.FRAGMENT_UNSUPPORTED,
                        diagnostics="Non-initial IPv6 fragment. L4 header absent.",
                    )
            try:
                ip_total_len = int(getattr(ip_layer, "plen", 0)) + 40
            except Exception:
                ip_total_len = None
            src_ip = str(ip_layer.src)
            dst_ip = str(ip_layer.dst)
            proto_num = int(ip_layer.nh)

        # Transport layer extraction
        sport, dport = 0, 0
        tcp_flags: Optional[int] = None
        has_fin = False
        has_rst = False
        protocol_str = "OTHER"

        if proto_num == 6:
            if not packet.haslayer("TCP"):
                return PacketParseResult(
                    ParseStatus.TRUNCATED_HEADER,
                    diagnostics="Protocol indicates TCP (6) but TCP layer is absent or truncated in capture.",
                )
            protocol_str = "TCP"
            tcp_layer = packet["TCP"]
            sport = int(tcp_layer.sport)
            dport = int(tcp_layer.dport)
            try:
                raw_flags = int(tcp_layer.flags)
                tcp_flags = raw_flags
                has_fin = bool(raw_flags & 0x01)
                has_rst = bool(raw_flags & 0x04)
            except (ValueError, TypeError):
                tcp_flags = None

        elif proto_num == 17:
            if not packet.haslayer("UDP"):
                return PacketParseResult(
                    ParseStatus.TRUNCATED_HEADER,
                    diagnostics="Protocol indicates UDP (17) but UDP layer is absent or truncated in capture.",
                )
            protocol_str = "UDP"
            udp_layer = packet["UDP"]
            sport = int(udp_layer.sport)
            dport = int(udp_layer.dport)

        else:
            return PacketParseResult(
                ParseStatus.UNSUPPORTED_PROTOCOL,
                diagnostics=f"Transport protocol {proto_num} unsupported for 5-tuple flow tracking.",
            )

        # Canonical feature length matching production convention len(pkt)
        canonical_packet_len = captured_link_layer_len

        t_data = TransientPacketData(
            wire_timestamp=ts,
            arrival_monotonic=arrival_mono,
            wire_length=canonical_packet_len,
            captured_link_layer_length=captured_link_layer_len,
            captured_length=captured_len,
            wire_frame_length=wire_frame_len,
            ip_total_length=ip_total_len,
            protocol=protocol_str,
            tcp_flags=tcp_flags,
            has_fin=has_fin,
            has_rst=has_rst,
            src_ip=src_ip,
            src_port=sport,
            dst_ip=dst_ip,
            dst_port=dport,
        )
        return PacketParseResult(ParseStatus.VALID_METADATA, packet_data=t_data)

    except Exception as exc:
        return PacketParseResult(
            ParseStatus.MALFORMED_PACKET,
            diagnostics=f"Exception parsing Scapy packet structure: {exc}",
        )


def parse_scapy_packet(packet: Any, arrival_mono: Optional[float] = None) -> Optional[TransientPacketData]:
    """Compatibility wrapper returning TransientPacketData for valid packets or None."""
    res = parse_scapy_packet_detailed(packet, arrival_mono)
    return res.packet_data if res.status == ParseStatus.VALID_METADATA else None


def parse_raw_ip_bytes_detailed(
    data: bytes,
    ts: Optional[float] = None,
    arrival_mono: Optional[float] = None,
    wire_len: Optional[int] = None,
    orig_frame_len: Optional[int] = None,
) -> PacketParseResult:
    """
    Fast binary parser for raw Ethernet frames, VLAN frames, and raw IPv4/IPv6 packets.
    Explicitly handles 802.1Q VLANs, IPv4 IHL, non-initial fragments, TCP Data Offset, and truncations.
    """
    if ts is None:
        ts = time.time()
    if arrival_mono is None:
        arrival_mono = time.monotonic()

    captured_len = len(data)
    if captured_len == 0:
        return PacketParseResult(ParseStatus.MALFORMED_PACKET, diagnostics="Buffer length is 0 bytes.")

    wire_frame_len = int(wire_len) if (wire_len is not None and wire_len > 0) else None
    captured_link_layer_len = (
        orig_frame_len
        if orig_frame_len is not None
        else (wire_frame_len if wire_frame_len is not None else captured_len)
    )

    ip_offset = 0

    # 1. Layer-2 Detection: Ethernet II, 802.1Q Single VLAN, or 802.1ad QinQ
    if captured_len >= 14:
        ethertype = struct.unpack("!H", data[12:14])[0]
        if ethertype in (0x8100, 0x88A8):  # 802.1Q Single VLAN or 802.1ad Service Tag
            if captured_len < 18:
                return PacketParseResult(ParseStatus.TRUNCATED_HEADER, diagnostics="Truncated VLAN tag.")
            inner_ethertype = struct.unpack("!H", data[16:18])[0]
            if inner_ethertype in (0x8100, 0x88A8):  # QinQ Double Tagged
                if captured_len < 22:
                    return PacketParseResult(ParseStatus.TRUNCATED_HEADER, diagnostics="Truncated QinQ VLAN tag.")
                ip_offset = 22
            else:
                ip_offset = 18
        elif ethertype in (0x0800, 0x86DD):  # Standard Ethernet II
            ip_offset = 14
        else:
            # Check if data starts directly with IP header without L2 encapsulation
            ver = data[0] >> 4
            if ver in (4, 6):
                ip_offset = 0
            else:
                return PacketParseResult(
                    ParseStatus.UNSUPPORTED_PROTOCOL,
                    diagnostics=f"Unsupported L2 EtherType: 0x{ethertype:04x}",
                )
    else:
        # Less than 14 bytes: check if raw IP header snippet
        ver = data[0] >> 4
        if ver in (4, 6):
            ip_offset = 0
        else:
            return PacketParseResult(
                ParseStatus.MALFORMED_PACKET,
                diagnostics=f"Frame too short ({captured_len} bytes) and invalid IP version {ver}.",
            )

    # 2. Layer-3 IP Header Parsing
    if captured_len < ip_offset + 1:
        return PacketParseResult(ParseStatus.TRUNCATED_HEADER, diagnostics="Truncated before IP header.")

    ip_ver = data[ip_offset] >> 4
    if ip_ver == 4:
        if captured_len < ip_offset + 20:
            return PacketParseResult(
                ParseStatus.TRUNCATED_HEADER,
                diagnostics=f"Truncated IPv4 base header: {captured_len - ip_offset} < 20 bytes.",
            )

        ihl = (data[ip_offset] & 0x0F) * 4
        if ihl < 20:
            return PacketParseResult(
                ParseStatus.MALFORMED_PACKET,
                diagnostics=f"Invalid IPv4 IHL: {ihl} < 20 bytes.",
            )
        if captured_len < ip_offset + ihl:
            return PacketParseResult(
                ParseStatus.TRUNCATED_HEADER,
                diagnostics=f"Truncated IPv4 options: {captured_len - ip_offset} < {ihl} bytes.",
            )

        ip_total_len = struct.unpack("!H", data[ip_offset + 2 : ip_offset + 4])[0]
        if ip_total_len < ihl:
            return PacketParseResult(
                ParseStatus.MALFORMED_PACKET,
                diagnostics=f"Invalid IPv4 total length: {ip_total_len} < IHL ({ihl}).",
            )

        # Check IP Fragmentation
        frag_field = struct.unpack("!H", data[ip_offset + 6 : ip_offset + 8])[0]
        frag_offset = (frag_field & 0x1FFF) * 8
        if frag_offset > 0:
            return PacketParseResult(
                ParseStatus.FRAGMENT_UNSUPPORTED,
                diagnostics=f"Non-initial IPv4 fragment (offset={frag_offset}). L4 header absent.",
            )

        proto_num = data[ip_offset + 9]
        import socket
        src_ip = socket.inet_ntoa(data[ip_offset + 12 : ip_offset + 16])
        dst_ip = socket.inet_ntoa(data[ip_offset + 16 : ip_offset + 20])
        trans_offset = ip_offset + ihl

    elif ip_ver == 6:
        if captured_len < ip_offset + 40:
            return PacketParseResult(
                ParseStatus.TRUNCATED_HEADER,
                diagnostics=f"Truncated IPv6 base header: {captured_len - ip_offset} < 40 bytes.",
            )

        payload_len = struct.unpack("!H", data[ip_offset + 4 : ip_offset + 6])[0]
        ip_total_len = 40 + payload_len

        import socket
        src_ip = socket.inet_ntop(socket.AF_INET6, data[ip_offset + 8 : ip_offset + 24])
        dst_ip = socket.inet_ntop(socket.AF_INET6, data[ip_offset + 24 : ip_offset + 40])

        next_hdr = data[ip_offset + 6]
        curr_offset = ip_offset + 40

        while next_hdr in (0, 43, 44, 51, 60):
            if next_hdr == 44:  # Fragment
                if captured_len < curr_offset + 8:
                    return PacketParseResult(
                        ParseStatus.TRUNCATED_HEADER,
                        diagnostics="Truncated IPv6 Fragment header.",
                    )
                frag_info = struct.unpack("!H", data[curr_offset + 2 : curr_offset + 4])[0]
                frag_offset = (frag_info >> 3) * 8
                if frag_offset > 0:
                    return PacketParseResult(
                        ParseStatus.FRAGMENT_UNSUPPORTED,
                        diagnostics=f"Non-initial IPv6 fragment (offset={frag_offset}).",
                    )
                next_hdr = data[curr_offset]
                curr_offset += 8
            elif next_hdr == 51:  # AH
                if captured_len < curr_offset + 2:
                    return PacketParseResult(
                        ParseStatus.TRUNCATED_HEADER,
                        diagnostics="Truncated IPv6 AH header.",
                    )
                hdr_len = (data[curr_offset + 1] + 2) * 4
                if captured_len < curr_offset + hdr_len:
                    return PacketParseResult(
                        ParseStatus.TRUNCATED_HEADER,
                        diagnostics="Truncated IPv6 AH payload.",
                    )
                next_hdr = data[curr_offset]
                curr_offset += hdr_len
            else:  # Hop-by-Hop, Routing, Dest Options
                if captured_len < curr_offset + 2:
                    return PacketParseResult(
                        ParseStatus.TRUNCATED_HEADER,
                        diagnostics=f"Truncated IPv6 extension header {next_hdr}.",
                    )
                hdr_len = (data[curr_offset + 1] + 1) * 8
                if captured_len < curr_offset + hdr_len:
                    return PacketParseResult(
                        ParseStatus.TRUNCATED_HEADER,
                        diagnostics=f"Truncated IPv6 extension header {next_hdr} body.",
                    )
                next_hdr = data[curr_offset]
                curr_offset += hdr_len

        proto_num = next_hdr
        trans_offset = curr_offset

    else:
        return PacketParseResult(
            ParseStatus.MALFORMED_PACKET,
            diagnostics=f"Invalid IP version: {ip_ver}",
        )

    # 3. Layer-4 Transport Header Parsing
    protocol_str = "OTHER"
    sport, dport = 0, 0
    tcp_flags = None
    has_fin = False
    has_rst = False

    if proto_num == 6:  # TCP
        protocol_str = "TCP"
        if captured_len < trans_offset + 20:
            return PacketParseResult(
                ParseStatus.TRUNCATED_HEADER,
                diagnostics=f"Truncated TCP header ({captured_len - trans_offset} < 20 bytes).",
            )

        sport, dport = struct.unpack("!HH", data[trans_offset : trans_offset + 4])
        data_offset = (data[trans_offset + 12] >> 4) * 4
        if data_offset < 20:
            return PacketParseResult(
                ParseStatus.MALFORMED_PACKET,
                diagnostics=f"Invalid TCP data offset ({data_offset} < 20).",
            )

        raw_flags = data[trans_offset + 13]
        tcp_flags = int(raw_flags)
        has_fin = bool(raw_flags & 0x01)
        has_rst = bool(raw_flags & 0x04)

    elif proto_num == 17:  # UDP
        protocol_str = "UDP"
        if captured_len < trans_offset + 8:
            return PacketParseResult(
                ParseStatus.TRUNCATED_HEADER,
                diagnostics=f"Truncated UDP header ({captured_len - trans_offset} < 8 bytes).",
            )

        sport, dport, udp_len = struct.unpack("!HHH", data[trans_offset : trans_offset + 6])
        if udp_len < 8:
            return PacketParseResult(
                ParseStatus.MALFORMED_PACKET,
                diagnostics=f"Invalid UDP length ({udp_len} < 8).",
            )

    else:
        return PacketParseResult(
            ParseStatus.UNSUPPORTED_PROTOCOL,
            diagnostics=f"Protocol {proto_num} is not supported for 5-tuple flow aggregation.",
        )

    canonical_packet_len = captured_link_layer_len

    t_data = TransientPacketData(
        wire_timestamp=ts,
        arrival_monotonic=arrival_mono,
        wire_length=canonical_packet_len,
        captured_link_layer_length=captured_link_layer_len,
        captured_length=captured_len,
        wire_frame_length=wire_frame_len,
        ip_total_length=ip_total_len,
        protocol=protocol_str,
        tcp_flags=tcp_flags,
        has_fin=has_fin,
        has_rst=has_rst,
        src_ip=src_ip,
        src_port=sport,
        dst_ip=dst_ip,
        dst_port=dport,
    )
    return PacketParseResult(ParseStatus.VALID_METADATA, packet_data=t_data)


def parse_raw_ip_bytes(
    data: bytes,
    ts: Optional[float] = None,
    arrival_mono: Optional[float] = None,
    wire_len: Optional[int] = None,
    orig_frame_len: Optional[int] = None,
) -> Optional[TransientPacketData]:
    """Compatibility wrapper returning TransientPacketData for valid packets or None."""
    res = parse_raw_ip_bytes_detailed(data, ts, arrival_mono, wire_len, orig_frame_len)
    return res.packet_data if res.status == ParseStatus.VALID_METADATA else None
