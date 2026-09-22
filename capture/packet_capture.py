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
        """Reads packets from PCAP file via Scapy."""
        logger.debug("Reading packets from %s", self.pcap_path)
        try:
            from scapy.all import PcapReader as ScapyPcapReader
            with ScapyPcapReader(str(self.pcap_path)) as pcap_reader:
                for packet in pcap_reader:
                    parsed = parse_scapy_packet(packet)
                    if parsed is not None:
                        yield parsed
        except ImportError:
            logger.warning("Scapy not installed or failed to import. Yielding no packets.")
            return


class LiveSniffer(BasePacketCapture):
    """
    Real-time live network interface packet capture backend.
    """

    def __init__(
        self,
        interface: Optional[str] = None,
        pcap_filter: str = "ip or ip6",
        promiscuous: bool = True,
    ) -> None:
        self.interface = interface
        self.pcap_filter = pcap_filter
        self.promiscuous = promiscuous
        self._is_running = False
        logger.info("Initialized LiveSniffer on interface: %s (filter: '%s')", interface, pcap_filter)

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
        self._is_running = True
        logger.info("Starting live capture loop (duration=%s, count=%d)...", duration_seconds, packet_count)

        try:
            from scapy.all import sniff
            def _packet_handler(pkt: Any) -> None:
                if not self._is_running:
                    return
                parsed = parse_scapy_packet(pkt)
                if parsed:
                    callback(parsed)

            sniff(
                iface=self.interface,
                filter=self.pcap_filter,
                prn=_packet_handler,
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
            from scapy.all import get_if_list
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
