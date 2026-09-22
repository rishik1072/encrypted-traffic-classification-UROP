"""
Live Packet Capture and Sniffing Interface.

Extracts Layer-3, Layer-4, and initial TLS ClientHello handshake metadata
WITHOUT decrypting packet payloads.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Generator, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RawPacketMetadata:
    """Represents payload-agnostic metadata extracted from a single network packet."""
    timestamp: float
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    length: int
    tcp_flags: Optional[int] = None
    tls_sni: Optional[str] = None
    tls_version: Optional[str] = None
    tls_cipher_suites_count: Optional[int] = None
    tls_extensions_count: Optional[int] = None


class BasePacketCapture:
    """Abstract interface for packet capture backends."""

    def read_packets(self) -> Generator[RawPacketMetadata, None, None]:
        """Yields packet metadata items sequentially."""
        raise NotImplementedError("Subclasses must implement read_packets.")


class PCAPReader(BasePacketCapture):
    """
    Reads packets from an offline PCAP / PCAPNG file.
    Extracts transport and network header statistics without inspecting payload bytes.
    """

    def __init__(self, pcap_path: str | Path) -> None:
        self.pcap_path = Path(pcap_path)
        if not self.pcap_path.exists():
            raise FileNotFoundError(f"PCAP file not found: {self.pcap_path}")
        logger.info("Initialized PCAPReader with source: %s", self.pcap_path)

    def read_packets(self) -> Generator[RawPacketMetadata, None, None]:
        """Reads packets from PCAP file, extracting zero-payload Layer-3/Layer-4 metadata."""
        logger.debug("Reading packets from %s", self.pcap_path)
        # 1. Fast native PCAP binary reader (instantaneous, zero external dependency overhead)
        try:
            import struct
            import socket
            with open(self.pcap_path, "rb") as f:
                hdr = f.read(24)
                if len(hdr) == 24:
                    magic, _, _, _, _, _, linktype = struct.unpack("<IHHiIII", hdr)
                    if magic in (0xa1b2c3d4, 0xd4c3b2a1):
                        endian = "<" if magic == 0xa1b2c3d4 else ">"
                        count = 0
                        while True:
                            p_hdr = f.read(16)
                            if len(p_hdr) < 16:
                                break
                            ts_sec, ts_usec, incl_len, _ = struct.unpack(f"{endian}IIII", p_hdr)
                            data = f.read(incl_len)
                            if len(data) < incl_len:
                                break
                            ts = ts_sec + ts_usec / 1e6

                            # Determine IP header offset based on data link type
                            ip_offset = 0
                            if linktype == 1:  # Ethernet
                                ip_offset = 14
                            elif linktype in (228, 101, 12):  # Raw IPv4/IPv6
                                ip_offset = 0

                            if len(data) > ip_offset + 20:
                                ver = data[ip_offset] >> 4
                                if ver == 4:
                                    ihl = (data[ip_offset] & 0x0F) * 4
                                    proto_num = data[ip_offset + 9]
                                    src_ip = socket.inet_ntoa(data[ip_offset + 12 : ip_offset + 16])
                                    dst_ip = socket.inet_ntoa(data[ip_offset + 16 : ip_offset + 20])
                                    proto = "TCP" if proto_num == 6 else ("UDP" if proto_num == 17 else "OTHER")

                                    transport_offset = ip_offset + ihl
                                    if len(data) >= transport_offset + 4:
                                        sport, dport = struct.unpack("!HH", data[transport_offset : transport_offset + 4])
                                    else:
                                        sport, dport = 0, 0

                                    tcp_flags = None
                                    if proto == "TCP" and len(data) >= transport_offset + 14:
                                        tcp_flags = int(data[transport_offset + 13])

                                    count += 1
                                    yield RawPacketMetadata(
                                        timestamp=ts,
                                        src_ip=src_ip,
                                        dst_ip=dst_ip,
                                        src_port=sport,
                                        dst_port=dport,
                                        protocol=proto,
                                        length=len(data),
                                        tcp_flags=tcp_flags,
                                    )
                        if count > 0:
                            return
        except Exception as e:
            logger.debug("Fast native PCAP read failed, falling back to Scapy: %s", e)

        # 2. Scapy fallback
        try:
            from scapy.utils import PcapReader as ScapyPcapReader
            with ScapyPcapReader(str(self.pcap_path)) as pcap_reader:
                for packet in pcap_reader:
                    parsed = parse_scapy_packet(packet)
                    if parsed is not None:
                        yield parsed
        except Exception:
            return


def check_capture_prerequisites(interface: Optional[str] = None) -> tuple[bool, str]:
    """
    Validates host environment for live packet capture (Npcap on Windows, permissions).
    Returns (is_ready, diagnostic_message).
    """
    import platform
    if platform.system() == "Windows":
        try:
            from product.environment import check_npcap
            npcap_info = check_npcap()
            if npcap_info.get("status") == "FAIL":
                return False, "Npcap packet capture driver was not detected on this system."
        except ImportError:
            pass
    return True, "Capture prerequisites satisfied."


def _default_sniff(*args: Any, **kwargs: Any) -> Any:
    """Wrapper around scapy.sendrecv.sniff allowing clean interception in test environments."""
    from scapy.sendrecv import sniff
    return sniff(*args, **kwargs)


class LiveSniffer(BasePacketCapture):
    """
    Real-time live network interface packet capture backend.
    Sniffs live traffic from a network interface (Npcap on Windows, libpcap on Linux).
    Extracts Layer-3/Layer-4 zero-payload flow attributes.
    """

    def __init__(
        self,
        interface: Optional[str] = None,
        pcap_filter: Optional[str] = None,
        promiscuous: bool = True,
    ) -> None:
        self.interface = interface
        self.pcap_filter = pcap_filter
        self.promiscuous = promiscuous
        self._is_running = False
        self.packets_captured_count = 0
        logger.info("Initialized LiveSniffer on interface: %s (filter: '%s')", interface, pcap_filter)

    def check_capture_prerequisites(self) -> None:
        """
        Validates that the host environment has required packet capture drivers and libraries.
        Raises RuntimeError or PermissionError if live capture is impossible.
        """
        ok, msg = check_capture_prerequisites(self.interface)
        if not ok:
            raise RuntimeError(
                f"{msg}\nLive packet capture requires Npcap (https://npcap.com/) installed with "
                "'WinPcap API-compatible Mode' enabled."
            )

        if self.interface:
            try:
                from capture.interface_resolver import list_scapy_interfaces
                ifaces = list_scapy_interfaces()
                valid_names = set()
                for ifc in ifaces:
                    valid_names.add(ifc.get("friendly_name", "").lower())
                    valid_names.add(ifc.get("network_name", "").lower())
                    valid_names.add(ifc.get("description", "").lower())
                
                if self.interface.lower() not in valid_names and self.interface not in ("any", "lo", "loopback"):
                    # Check if interface name matches partially
                    matched = any(self.interface.lower() in name for name in valid_names if name)
                    if not matched:
                        raise ValueError(
                            f"Network interface '{self.interface}' was not found among available host adapters.\n"
                            f"Available adapters: {', '.join(sorted(i.get('friendly_name', '') for i in ifaces if i.get('friendly_name')))}"
                        )
            except (ImportError, ValueError):
                raise
            except Exception as e:
                logger.debug("Interface pre-validation note: %s", e)

    def start_sniffing(
        self,
        callback: Callable[[RawPacketMetadata], None],
        duration_seconds: Optional[float] = None,
        packet_count: int = 0,
    ) -> None:
        """
        Starts live packet capture on the configured network interface.
        Invokes callback for each valid packet.
        """
        self.check_capture_prerequisites()
        self._is_running = True
        self.packets_captured_count = 0
        logger.info("Starting live capture loop (duration=%s, count=%d)...", duration_seconds, packet_count)

        try:
            def _packet_handler(pkt: Any) -> None:
                if not self._is_running:
                    return
                parsed = parse_scapy_packet(pkt)
                if parsed:
                    self.packets_captured_count += 1
                    callback(parsed)

            # Convert friendly name to resolved Scapy interface if on Windows
            resolved_iface = self.interface
            if self.interface:
                try:
                    from capture.interface_resolver import resolve_capture_interface
                    res = resolve_capture_interface(self.interface)
                    if res.get("scapy_object") is not None:
                        resolved_iface = res["scapy_object"]
                    elif res.get("network_name"):
                        resolved_iface = res["network_name"]
                except Exception:
                    resolved_iface = self.interface

            _default_sniff(
                iface=resolved_iface,
                filter=self.pcap_filter,
                prn=_packet_handler,
                stop_filter=lambda p: not self._is_running,
                timeout=duration_seconds,
                count=packet_count,
                store=False,
                promisc=self.promiscuous,
            )
        except PermissionError:
            logger.error("Live capture requires administrative/root privileges on this interface.")
            raise
        except ImportError:
            logger.warning("Scapy is required for live network sniffing.")
            raise RuntimeError("Scapy packet capture backend is not installed.")
        except RuntimeError as re:
            err_str = str(re)
            if "winpcap is not installed" in err_str or "layer 2" in err_str:
                raise RuntimeError(
                    "Npcap / WinPcap packet capture driver is not installed or service is stopped.\n"
                    "Install Npcap with 'WinPcap API-compatible Mode' checked to enable live packet capture."
                ) from re
            raise
        except Exception as e:
            logger.error("Live packet capture error: %s", e)
            raise
        finally:
            self._is_running = False

    def stop(self) -> None:
        """Stops the active capture session."""
        self._is_running = False
        logger.info("Stopped LiveSniffer")


    @staticmethod
    def list_available_interfaces() -> List[str]:
        """Returns list of network interface names available for capture."""
        try:
            from scapy.interfaces import get_if_list
            return list(get_if_list())
        except Exception:
            return ["eth0", "wlan0", "lo", "Wi-Fi", "Ethernet"]


def parse_scapy_packet(pkt: Any) -> Optional[RawPacketMetadata]:
    """Converts a Scapy packet into RawPacketMetadata, ignoring payload contents."""
    try:
        if not pkt.haslayer("IP") and not pkt.haslayer("IPv6"):
            return None

        is_ipv6 = pkt.haslayer("IPv6")
        ip_layer = pkt["IPv6"] if is_ipv6 else pkt["IP"]
        src_ip = ip_layer.src
        dst_ip = ip_layer.dst

        timestamp = float(getattr(pkt, "time", time.time()))
        length = len(pkt)

        protocol = "OTHER"
        src_port = 0
        dst_port = 0
        tcp_flags = None

        if pkt.haslayer("TCP"):
            protocol = "TCP"
            tcp_layer = pkt["TCP"]
            src_port = int(tcp_layer.sport)
            dst_port = int(tcp_layer.dport)
            tcp_flags = int(tcp_layer.flags)
        elif pkt.haslayer("UDP"):
            protocol = "UDP"
            udp_layer = pkt["UDP"]
            src_port = int(udp_layer.sport)
            dst_port = int(udp_layer.dport)

        # Extract unencrypted TLS ClientHello metadata if present
        tls_sni = None
        tls_version = None
        cipher_count = None
        ext_count = None

        if pkt.haslayer("TLS"):
            tls_layer = pkt["TLS"]
            tls_version = getattr(tls_layer, "version", None)
            if hasattr(tls_layer, "msg") and tls_layer.msg:
                for msg in tls_layer.msg:
                    if getattr(msg, "name", "") == "TLSClientHello":
                        tls_sni = getattr(msg, "servername", None)
                        ciphers = getattr(msg, "ciphers", [])
                        cipher_count = len(ciphers) if ciphers else 0
                        exts = getattr(msg, "ext", [])
                        ext_count = len(exts) if exts else 0

        return RawPacketMetadata(
            timestamp=timestamp,
            src_ip=src_ip,
            dst_ip=dst_ip,
            src_port=src_port,
            dst_port=dst_port,
            protocol=protocol,
            length=length,
            tcp_flags=tcp_flags,
            tls_sni=str(tls_sni) if tls_sni else None,
            tls_version=str(tls_version) if tls_version else None,
            tls_cipher_suites_count=cipher_count,
            tls_extensions_count=ext_count,
        )
    except Exception as e:
        logger.debug("Failed to parse packet: %s", e)
        return None
