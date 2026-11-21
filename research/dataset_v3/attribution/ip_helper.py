"""
Windows IP Helper API Wrapper for Process-to-Socket Attribution.

Interrogates Windows network socket tables via iphlpapi.dll:
- GetExtendedTcpTable (IPv4 & IPv6 with owning PID)
- GetExtendedUdpTable (IPv4 & IPv6 with owning PID)
- GetProcessTimes & QueryFullProcessImageNameW (PID reuse and creation identity)

Normalizes endpoint representations and isolates all volatile network metadata
strictly in memory.
"""

from __future__ import annotations

import ctypes
import ipaddress
import logging
import os
import platform
import socket
import struct
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from research.dataset_v3.attribution.schemas import TransientProcessIdentity, TransientSocketEntry

logger = logging.getLogger("research.dataset_v3.attribution.ip_helper")

# --- WIN32 CONSTANTS ---
AF_INET = 2
AF_INET6 = 23

# Table class constants
TCP_TABLE_OWNER_PID_ALL = 5
UDP_TABLE_OWNER_PID = 1

# Process access rights
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# Error codes
ERROR_INSUFFICIENT_BUFFER = 122
NO_ERROR = 0

# TCP State Map (RFC 793 / MIB_TCP_STATE)
TCP_STATE_MAP = {
    1: "CLOSED",
    2: "LISTEN",
    3: "SYN_SENT",
    4: "SYN_RCVD",
    5: "ESTABLISHED",
    6: "FIN_WAIT_1",
    7: "FIN_WAIT_2",
    8: "CLOSE_WAIT",
    9: "CLOSING",
    10: "LAST_ACK",
    11: "TIME_WAIT",
    12: "DELETE_TCB",
}


def normalize_ip_address(ip_str: str) -> str:
    """
    Normalizes an IPv4 or IPv6 address string into canonical form:
    - Strips scope IDs (e.g. fe80::1%12 -> fe80::1).
    - Unwraps IPv4-mapped IPv6 addresses (::ffff:192.168.1.1 -> 192.168.1.1).
    - Preserves wildcard representations (0.0.0.0, ::).
    """
    if not ip_str:
        return "0.0.0.0"

    cleaned = ip_str.split("%")[0].strip()

    try:
        ip_obj = ipaddress.ip_address(cleaned)
        # Unwrap IPv4-mapped IPv6 (::ffff:a.b.c.d)
        if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
            return str(ip_obj.ipv4_mapped)
        return str(ip_obj)
    except ValueError:
        return cleaned.lower()


def normalize_port(port: int) -> int:
    """Ensures port integer is within valid 16-bit range."""
    return port & 0xFFFF


def _decode_port_from_dword(dw_port: int) -> int:
    """Decodes network-byte-order port stored in Windows DWORD."""
    return ((dw_port & 0xFF) << 8) | ((dw_port >> 8) & 0xFF)


# --- WIN32 API DECLARATIONS (CONDITIONAL ON WINDOWS) ---
_is_windows = platform.system() == "Windows"
_iphlpapi = None
_kernel32 = None

if _is_windows:
    try:
        import ctypes.wintypes
        _iphlpapi = ctypes.windll.iphlpapi
        _kernel32 = ctypes.windll.kernel32
    except Exception as e:
        logger.warning("Failed loading Windows native libraries: %s", e)


def get_process_creation_time_and_name(pid: int) -> Tuple[Optional[str], Optional[str]]:
    """
    Retrieves process creation timestamp (UTC ISO format) and executable base name.
    Used to disambiguate PIDs across process termination and reuse cycles.
    """
    if not _is_windows or not _kernel32 or pid <= 0:
        return None, None

    h_process = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_process:
        return None, None

    create_time_iso = None
    process_name = None

    try:
        from ctypes import wintypes
        # 1. Query Process Times
        c_time = wintypes.FILETIME()
        e_time = wintypes.FILETIME()
        k_time = wintypes.FILETIME()
        u_time = wintypes.FILETIME()

        if _kernel32.GetProcessTimes(
            h_process,
            ctypes.byref(c_time),
            ctypes.byref(e_time),
            ctypes.byref(k_time),
            ctypes.byref(u_time),
        ):
            ft = (c_time.dwHighDateTime << 32) + c_time.dwLowDateTime
            # Windows FILETIME: 100-ns intervals since 1601-01-01 UTC
            dt = datetime(1601, 1, 1, tzinfo=timezone.utc) + \
                 __import__("datetime").timedelta(microseconds=ft // 10)
            create_time_iso = dt.isoformat()

        # 2. Query Full Process Image Name
        buf_size = wintypes.DWORD(1024)
        name_buf = ctypes.create_unicode_buffer(1024)
        if _kernel32.QueryFullProcessImageNameW(h_process, 0, name_buf, ctypes.byref(buf_size)):
            full_path = name_buf.value
            process_name = os.path.basename(full_path).lower()

    except Exception as e:
        logger.debug("Failed querying process times for PID %d: %s", pid, e)
    finally:
        _kernel32.CloseHandle(h_process)

    return create_time_iso, process_name


class WindowsIPHelperReader:
    """
    Interrogates live Windows TCP and UDP socket tables via IP Helper APIs.
    """

    def __init__(self) -> None:
        self.is_supported = _is_windows and (_iphlpapi is not None)
        # Process identity cache during a single snapshot cycle: pid -> (create_time, name)
        self._proc_cache: Dict[int, Tuple[Optional[str], Optional[str]]] = {}

    def _resolve_pid(self, pid: int) -> Tuple[Optional[str], Optional[str]]:
        if pid not in self._proc_cache:
            self._proc_cache[pid] = get_process_creation_time_and_name(pid)
        return self._proc_cache[pid]

    def read_tcp_table_ipv4(self, now_ts: float) -> List[TransientSocketEntry]:
        """Reads all IPv4 TCP sockets with owning PIDs."""
        if not self.is_supported:
            return []

        entries: List[TransientSocketEntry] = []
        size = ctypes.wintypes.DWORD(0)

        # First call gets required buffer size
        res = _iphlpapi.GetExtendedTcpTable(None, ctypes.byref(size), True, AF_INET, TCP_TABLE_OWNER_PID_ALL, 0)
        if res not in (ERROR_INSUFFICIENT_BUFFER, NO_ERROR) or size.value == 0:
            return []

        buf = ctypes.create_string_buffer(size.value)
        res = _iphlpapi.GetExtendedTcpTable(buf, ctypes.byref(size), True, AF_INET, TCP_TABLE_OWNER_PID_ALL, 0)
        if res != NO_ERROR:
            return []

        num_entries = struct.unpack_from("<I", buf.raw, 0)[0]
        offset = 4
        # MIB_TCPROW_OWNER_PID: dwState (4), dwLocalAddr (4), dwLocalPort (4), dwRemoteAddr (4), dwRemotePort (4), dwOwningPid (4) = 24 bytes
        row_size = 24

        for _ in range(num_entries):
            if offset + row_size > len(buf.raw):
                break
            state_id, l_addr, l_port_raw, r_addr, r_port_raw, pid = struct.unpack_from("<IIIIII", buf.raw, offset)
            offset += row_size

            local_ip = normalize_ip_address(socket.inet_ntoa(struct.pack("<I", l_addr)))
            local_p = _decode_port_from_dword(l_port_raw)
            remote_ip = normalize_ip_address(socket.inet_ntoa(struct.pack("<I", r_addr)))
            remote_p = _decode_port_from_dword(r_port_raw)
            state_str = TCP_STATE_MAP.get(state_id, "UNKNOWN")

            ctime, pname = self._resolve_pid(pid)

            entries.append(
                TransientSocketEntry(
                    protocol="TCP",
                    local_address=local_ip,
                    local_port=local_p,
                    remote_address=remote_ip,
                    remote_port=remote_p,
                    state=state_str,
                    pid=pid,
                    process_create_time_utc=ctime,
                    process_name=pname,
                    timestamp_utc=now_ts,
                )
            )

        return entries

    def read_tcp_table_ipv6(self, now_ts: float) -> List[TransientSocketEntry]:
        """Reads all IPv6 TCP sockets with owning PIDs."""
        if not self.is_supported:
            return []

        entries: List[TransientSocketEntry] = []
        size = ctypes.wintypes.DWORD(0)

        res = _iphlpapi.GetExtendedTcpTable(None, ctypes.byref(size), True, AF_INET6, TCP_TABLE_OWNER_PID_ALL, 0)
        if res not in (ERROR_INSUFFICIENT_BUFFER, NO_ERROR) or size.value == 0:
            return []

        buf = ctypes.create_string_buffer(size.value)
        res = _iphlpapi.GetExtendedTcpTable(buf, ctypes.byref(size), True, AF_INET6, TCP_TABLE_OWNER_PID_ALL, 0)
        if res != NO_ERROR:
            return []

        num_entries = struct.unpack_from("<I", buf.raw, 0)[0]
        offset = 4
        # MIB_TCP6ROW_OWNER_PID:
        # ucLocalAddr (16), dwLocalScopeId (4), dwLocalPort (4),
        # ucRemoteAddr (16), dwRemoteScopeId (4), dwRemotePort (4),
        # dwState (4), dwOwningPid (4) = 56 bytes
        row_size = 56

        for _ in range(num_entries):
            if offset + row_size > len(buf.raw):
                break
            raw_row = buf.raw[offset : offset + row_size]
            offset += row_size

            local_bytes = raw_row[0:16]
            local_port_raw = struct.unpack_from("<I", raw_row, 20)[0]
            remote_bytes = raw_row[24:40]
            remote_port_raw = struct.unpack_from("<I", raw_row, 44)[0]
            state_id, pid = struct.unpack_from("<II", raw_row, 48)

            try:
                local_ip = normalize_ip_address(socket.inet_ntop(socket.AF_INET6, local_bytes))
            except Exception:
                local_ip = "::"
            try:
                remote_ip = normalize_ip_address(socket.inet_ntop(socket.AF_INET6, remote_bytes))
            except Exception:
                remote_ip = "::"

            local_p = _decode_port_from_dword(local_port_raw)
            remote_p = _decode_port_from_dword(remote_port_raw)
            state_str = TCP_STATE_MAP.get(state_id, "UNKNOWN")

            ctime, pname = self._resolve_pid(pid)

            entries.append(
                TransientSocketEntry(
                    protocol="TCP",
                    local_address=local_ip,
                    local_port=local_p,
                    remote_address=remote_ip,
                    remote_port=remote_p,
                    state=state_str,
                    pid=pid,
                    process_create_time_utc=ctime,
                    process_name=pname,
                    timestamp_utc=now_ts,
                )
            )

        return entries

    def read_udp_table_ipv4(self, now_ts: float) -> List[TransientSocketEntry]:
        """Reads all IPv4 UDP listeners/endpoints with owning PIDs."""
        if not self.is_supported:
            return []

        entries: List[TransientSocketEntry] = []
        size = ctypes.wintypes.DWORD(0)

        res = _iphlpapi.GetExtendedUdpTable(None, ctypes.byref(size), True, AF_INET, UDP_TABLE_OWNER_PID, 0)
        if res not in (ERROR_INSUFFICIENT_BUFFER, NO_ERROR) or size.value == 0:
            return []

        buf = ctypes.create_string_buffer(size.value)
        res = _iphlpapi.GetExtendedUdpTable(buf, ctypes.byref(size), True, AF_INET, UDP_TABLE_OWNER_PID, 0)
        if res != NO_ERROR:
            return []

        num_entries = struct.unpack_from("<I", buf.raw, 0)[0]
        offset = 4
        # MIB_UDPROW_OWNER_PID: dwLocalAddr (4), dwLocalPort (4), dwOwningPid (4) = 12 bytes
        row_size = 12

        for _ in range(num_entries):
            if offset + row_size > len(buf.raw):
                break
            l_addr, l_port_raw, pid = struct.unpack_from("<III", buf.raw, offset)
            offset += row_size

            local_ip = normalize_ip_address(socket.inet_ntoa(struct.pack("<I", l_addr)))
            local_p = _decode_port_from_dword(l_port_raw)

            ctime, pname = self._resolve_pid(pid)

            entries.append(
                TransientSocketEntry(
                    protocol="UDP",
                    local_address=local_ip,
                    local_port=local_p,
                    remote_address=None,
                    remote_port=None,
                    state=None,
                    pid=pid,
                    process_create_time_utc=ctime,
                    process_name=pname,
                    timestamp_utc=now_ts,
                )
            )

        return entries

    def read_udp_table_ipv6(self, now_ts: float) -> List[TransientSocketEntry]:
        """Reads all IPv6 UDP listeners/endpoints with owning PIDs."""
        if not self.is_supported:
            return []

        entries: List[TransientSocketEntry] = []
        size = ctypes.wintypes.DWORD(0)

        res = _iphlpapi.GetExtendedUdpTable(None, ctypes.byref(size), True, AF_INET6, UDP_TABLE_OWNER_PID, 0)
        if res not in (ERROR_INSUFFICIENT_BUFFER, NO_ERROR) or size.value == 0:
            return []

        buf = ctypes.create_string_buffer(size.value)
        res = _iphlpapi.GetExtendedUdpTable(buf, ctypes.byref(size), True, AF_INET6, UDP_TABLE_OWNER_PID, 0)
        if res != NO_ERROR:
            return []

        num_entries = struct.unpack_from("<I", buf.raw, 0)[0]
        offset = 4
        # MIB_UDP6ROW_OWNER_PID: ucLocalAddr (16), dwLocalScopeId (4), dwLocalPort (4), dwOwningPid (4) = 28 bytes
        row_size = 28

        for _ in range(num_entries):
            if offset + row_size > len(buf.raw):
                break
            raw_row = buf.raw[offset : offset + row_size]
            offset += row_size

            local_bytes = raw_row[0:16]
            local_port_raw = struct.unpack_from("<I", raw_row, 20)[0]
            pid = struct.unpack_from("<I", raw_row, 24)[0]

            try:
                local_ip = normalize_ip_address(socket.inet_ntop(socket.AF_INET6, local_bytes))
            except Exception:
                local_ip = "::"

            local_p = _decode_port_from_dword(local_port_raw)
            ctime, pname = self._resolve_pid(pid)

            entries.append(
                TransientSocketEntry(
                    protocol="UDP",
                    local_address=local_ip,
                    local_port=local_p,
                    remote_address=None,
                    remote_port=None,
                    state=None,
                    pid=pid,
                    process_create_time_utc=ctime,
                    process_name=pname,
                    timestamp_utc=now_ts,
                )
            )

        return entries

    def snapshot(self, timestamp: Optional[float] = None) -> List[TransientSocketEntry]:
        """
        Executes a complete point-in-time snapshot of all TCP and UDP sockets.
        Clears per-snapshot process cache after completion.
        """
        now_ts = timestamp if timestamp is not None else time.time()
        self._proc_cache.clear()

        all_entries: List[TransientSocketEntry] = []
        all_entries.extend(self.read_tcp_table_ipv4(now_ts))
        all_entries.extend(self.read_tcp_table_ipv6(now_ts))
        all_entries.extend(self.read_udp_table_ipv4(now_ts))
        all_entries.extend(self.read_udp_table_ipv6(now_ts))

        self._proc_cache.clear()
        return all_entries
