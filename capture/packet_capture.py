"""
Live Packet Capture and Sniffing Interface.

Extracts Layer-3, Layer-4, and initial TLS ClientHello handshake metadata
WITHOUT decrypting packet payloads.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Generator, List, Optional

logger = logging.getLogger(__name__)


def _init_scapy() -> None:
    """Safely pre-initializes Scapy layer definitions and prevents hangs on Windows with AdminOnly Npcap."""
    try:
        import platform
        if platform.system() == "Windows":
            import scapy.interfaces
            from scapy.config import conf
            # Prevent conf.ifaces.reload() from invoking pcap_findalldevs() which hangs on Windows in un-elevated contexts
            conf.ifaces.reload = lambda *args, **kwargs: None
            import scapy.layers.l2
            import scapy.layers.inet
            try:
                import scapy.layers.tls
            except Exception:
                pass
    except Exception as e:
        logger.debug("Scapy safe initialization note: %s", e)


_init_scapy()


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
    _init_scapy()
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
        session_id: Optional[str] = None,
        queue_maxsize: int = 50000,
    ) -> None:
        self.interface = interface
        self.pcap_filter = pcap_filter
        self.promiscuous = promiscuous
        self.session_id = session_id
        self._is_running = False

        # Telemetry counters
        self.packets_captured_count = 0
        self.packets_forwarded_count = 0
        self.packets_dropped_count = 0
        self.packets_processed_count = 0
        self.processing_errors_count = 0
        self.last_packet_time: Optional[float] = None
        self.last_packet_processed_time: Optional[float] = None

        # Phase 2 explicit capture states: CAPTURE_STARTING, CAPTURE_ACTIVE, CAPTURE_RECEIVING, CAPTURE_IDLE, CAPTURE_FAILED
        self.capture_state: str = "CAPTURE_IDLE"
        self.last_capture_error: Optional[str] = None
        self.last_capture_error_stage: Optional[str] = None

        # Bounded packet ingestion queue and consumer thread
        self._packet_queue: queue.Queue[RawPacketMetadata] = queue.Queue(maxsize=queue_maxsize)
        self._consumer_thread: Optional[threading.Thread] = None

        logger.info("Initialized LiveSniffer on interface: %s (filter: '%s', session: %s)", interface, pcap_filter, session_id)

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

    def _get_current_capture_state(self) -> str:
        """Computes the instantaneous capture lifecycle state."""
        if self.last_capture_error:
            return "CAPTURE_FAILED"
        if not self._is_running:
            return "CAPTURE_IDLE"
        if self.last_packet_time and (time.time() - self.last_packet_time) <= 5.0:
            return "CAPTURE_RECEIVING"
        if self.packets_captured_count > 0:
            return "CAPTURE_IDLE"
        return "CAPTURE_ACTIVE"

    def start_sniffing(
        self,
        callback: Callable[[RawPacketMetadata], None],
        duration_seconds: Optional[float] = None,
        packet_count: int = 0,
    ) -> None:
        """
        Starts live packet capture on the configured network interface.
        Invokes callback for each valid packet via a bounded queue and consumer worker.
        """
        self.capture_state = "CAPTURE_STARTING"
        self.last_capture_error = None
        self.last_capture_error_stage = "PREREQUISITES"

        try:
            self.check_capture_prerequisites()
        except Exception as e:
            self.last_capture_error = str(e)
            self.last_capture_error_stage = "PREREQUISITES"
            self.capture_state = "CAPTURE_FAILED"
            raise

        self.last_capture_error_stage = "SCAPY_INIT"
        try:
            _init_scapy()
        except Exception as e:
            self.last_capture_error = str(e)
            self.last_capture_error_stage = "SCAPY_INIT"
            self.capture_state = "CAPTURE_FAILED"
            raise

        self._is_running = True
        self.packets_captured_count = 0
        self.packets_forwarded_count = 0
        self.packets_dropped_count = 0
        self.packets_processed_count = 0
        self.processing_errors_count = 0
        logger.info("Starting live capture loop (duration=%s, count=%d)...", duration_seconds, packet_count)

        # 1. Start dedicated packet queue consumer worker
        self.last_capture_error_stage = "CONSUMER_WORKER"
        def _consumer_loop() -> None:
            while self._is_running or not self._packet_queue.empty():
                try:
                    meta = self._packet_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    callback(meta)
                    self.packets_processed_count += 1
                    self.last_packet_processed_time = time.time()
                except Exception as cb_err:
                    self.processing_errors_count += 1
                    logger.debug("Packet consumer callback error: %s", cb_err)
                finally:
                    self._packet_queue.task_done()

        self._consumer_thread = threading.Thread(target=_consumer_loop, daemon=True, name="LiveSnifferConsumer")
        self._consumer_thread.start()

        # 2. Scapy physical packet handler
        try:
            self.last_capture_error_stage = "INTERFACE_RESOLUTION"
            # Convert friendly name to resolved Scapy interface if on Windows
            resolved_iface = self.interface
            if self.interface:
                try:
                    from capture.interface_resolver import resolve_capture_interface
                    res = resolve_capture_interface(self.interface)
                    if isinstance(res, dict):
                        resolved_iface = res.get("scapy_object") or res.get("network_name")
                    elif res is not None:
                        resolved_iface = res
                    else:
                        resolved_iface = self.interface
                    logger.info("LiveSniffer resolved interface '%s' -> %s", self.interface, resolved_iface)
                except Exception as e:
                    logger.warning("Interface resolution note for '%s': %s", self.interface, e)
                    resolved_iface = self.interface

            def _packet_handler(pkt: Any) -> None:
                if not self._is_running:
                    return
                now = time.time()
                self.packets_captured_count += 1
                self.last_packet_time = now
                parsed = parse_scapy_packet(pkt)
                if parsed:
                    try:
                        self._packet_queue.put_nowait(parsed)
                        self.packets_forwarded_count += 1
                    except queue.Full:
                        self.packets_dropped_count += 1
                        logger.warning("Packet queue full (%d items)! Dropped incoming physical packet.", self._packet_queue.maxsize)
                else:
                    self.packets_dropped_count += 1

            self.last_capture_error_stage = "SNIFF_LOOP"
            self.capture_state = "CAPTURE_ACTIVE"
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
        except PermissionError as pe:
            self.last_capture_error = "Live capture requires administrative/root privileges on this interface."
            self.last_capture_error_stage = "PERMISSION"
            self.capture_state = "CAPTURE_FAILED"
            logger.error("Live capture requires administrative/root privileges on this interface.")
            raise
        except ImportError as ie:
            self.last_capture_error = "Scapy is required for live network sniffing."
            self.last_capture_error_stage = "DEPENDENCY"
            self.capture_state = "CAPTURE_FAILED"
            logger.warning("Scapy is required for live network sniffing.")
            raise RuntimeError("Scapy packet capture backend is not installed.") from ie
        except RuntimeError as re:
            err_str = str(re)
            self.last_capture_error = err_str
            self.last_capture_error_stage = "DRIVER_RUNTIME"
            self.capture_state = "CAPTURE_FAILED"
            if "winpcap is not installed" in err_str or "layer 2" in err_str:
                raise RuntimeError(
                    "Npcap / WinPcap packet capture driver is not installed or service is stopped.\n"
                    "Install Npcap with 'WinPcap API-compatible Mode' checked to enable live packet capture."
                ) from re
            raise
        except Exception as e:
            self.last_capture_error = str(e)
            self.last_capture_error_stage = "SNIFF_EXCEPTION"
            self.capture_state = "CAPTURE_FAILED"
            logger.error("Live packet capture error: %s", e)
            raise
        finally:
            self._is_running = False
            if self._consumer_thread and self._consumer_thread.is_alive():
                self._consumer_thread.join(timeout=2.0)

    def stop(self) -> None:
        """Stops the active capture session."""
        self._is_running = False
        self.capture_state = "CAPTURE_IDLE"
        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=2.0)
        logger.info("Stopped LiveSniffer")

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns runtime ingestion telemetry counters."""
        return {
            "capture_packets_received": self.packets_captured_count,
            "packets_forwarded_to_processor": self.packets_forwarded_count,
            "packets_processed": self.packets_processed_count,
            "packets_dropped": self.packets_dropped_count,
            "processing_errors": self.processing_errors_count,
            "queue_depth": self._packet_queue.qsize() if hasattr(self, "_packet_queue") else 0,
            "worker_alive": self._consumer_thread.is_alive() if self._consumer_thread else False,
            "capture_thread_alive": self._is_running,
            "last_packet_at": self.last_packet_time,
            "last_packet_processed_at": self.last_packet_processed_time,
            "capture_state": self._get_current_capture_state(),
            "last_capture_error": self.last_capture_error,
            "last_capture_error_stage": self.last_capture_error_stage,
        }

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
        # Fallback dissection: if packet arrived as raw/generic Packet without L2/L3 dissection
        if not pkt.haslayer("IP") and not pkt.haslayer("IPv6"):
            try:
                from scapy.layers.l2 import Ether
                raw_bytes = bytes(pkt)
                dissected = Ether(raw_bytes)
                if dissected.haslayer("IP") or dissected.haslayer("IPv6"):
                    pkt = dissected
                elif hasattr(pkt, "payload") and pkt.payload:
                    inner = pkt.payload
                    if inner.haslayer("IP") or inner.haslayer("IPv6"):
                        pkt = inner
                    else:
                        return None
                else:
                    return None
            except Exception:
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
