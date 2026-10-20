"""
Windows Network Interface Resolver for Scapy and Npcap.

Maps friendly adapter names (e.g. 'Wi-Fi', 'Ethernet') to valid Scapy NetworkInterface
objects or Npcap device names (e.g. '\\Device\\NPF_{GUID}').
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CACHED_INTERFACES: Optional[List[Dict[str, Any]]] = None
_LAST_IFACE_SCAN_TIME: float = 0.0


def _get_windows_adapters_safe() -> List[Dict[str, Any]]:
    """Safe, non-blocking discovery of Windows network adapters using Registry and psutil."""
    import winreg
    import socket
    import psutil

    guid_map: Dict[str, str] = {}
    net_key = r"SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, net_key) as k:
            i = 0
            while True:
                try:
                    guid = winreg.EnumKey(k, i)
                    i += 1
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{net_key}\\{guid}\\Connection") as ck:
                            name, _ = winreg.QueryValueEx(ck, "Name")
                            guid_map[name] = guid
                    except OSError:
                        pass
                except OSError:
                    break
    except Exception:
        pass

    adapters: List[Dict[str, Any]] = []
    try:
        stats_map = psutil.net_if_stats()
        addrs_map = psutil.net_if_addrs()
        for name, addrs in addrs_map.items():
            if name.startswith("Local Area Connection*") or name.startswith("Bluetooth"):
                continue
            ip = ""
            for a in addrs:
                if a.family == socket.AF_INET:
                    ip = a.address
                    break
            stats = stats_map.get(name)
            is_up = bool(stats and stats.isup and ip and ip != "0.0.0.0" and not ip.startswith("169.254."))
            guid = guid_map.get(name, "{00000000-0000-0000-0000-000000000000}")
            adapters.append({
                "identifier": name,
                "friendly_name": name,
                "description": f"{name} Network Adapter",
                "network_name": rf"\Device\NPF_{guid}",
                "guid": guid,
                "ip": ip,
                "is_up": is_up,
                "scapy_object": None,
            })
    except Exception as e:
        logger.debug("Safe Windows adapter enumeration error: %s", e)

    return adapters


def list_scapy_interfaces(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Returns detailed metadata for all Scapy/Npcap interfaces available on the system."""
    global _CACHED_INTERFACES, _LAST_IFACE_SCAN_TIME
    now = time.time()
    if not force_refresh and _CACHED_INTERFACES is not None and (now - _LAST_IFACE_SCAN_TIME) < 60.0:
        return _CACHED_INTERFACES

    interfaces: List[Dict[str, Any]] = []

    # On Windows, non-admin processes or environments without interactive UAC
    # cannot safely initialize Scapy's Npcap without hanging. Use safe Windows enumeration.
    import platform
    is_win = platform.system() == "Windows"
    is_adm = False
    if is_win:
        try:
            import ctypes
            is_adm = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            is_adm = False

    if is_win and not is_adm:
        interfaces = _get_windows_adapters_safe()
        _CACHED_INTERFACES = interfaces
        _LAST_IFACE_SCAN_TIME = now
        return interfaces

    try:
        from scapy.config import conf
        conf.interactive = False
        import scapy.all  # Crucial: imports arch/windows modules so conf.ifaces is populated

        if conf.ifaces is not None:
            for iface_key, iface_obj in conf.ifaces.items():
                friendly_name = getattr(iface_obj, "name", str(iface_key))
                description = getattr(iface_obj, "description", "")
                network_name = getattr(iface_obj, "network_name", str(iface_key))
                guid = getattr(iface_obj, "guid", str(iface_key))
                ip = getattr(iface_obj, "ip", "")

                is_up = bool(ip and ip not in ["0.0.0.0", "169.254.0.0", ""])
                if ip and not ip.startswith("169.254.") and ip != "0.0.0.0":
                    is_up = True

                interfaces.append({
                    "identifier": str(iface_key),
                    "friendly_name": friendly_name,
                    "description": description,
                    "network_name": network_name,
                    "guid": guid,
                    "ip": ip,
                    "is_up": is_up,
                    "scapy_object": iface_obj,
                })
    except Exception as e:
        logger.warning("Scapy interface enumeration error: %s", e)

    if not interfaces and is_win:
        interfaces = _get_windows_adapters_safe()

    _CACHED_INTERFACES = interfaces
    _LAST_IFACE_SCAN_TIME = now
    return interfaces


def resolve_capture_interface(user_interface_name: Optional[str] = None) -> Any:
    """
    Resolves a user-provided interface string to a valid Scapy NetworkInterface object or identifier.
    Supports friendly names like 'Wi-Fi', descriptions, or raw Npcap network names.
    """
    all_ifaces = list_scapy_interfaces()
    if not all_ifaces:
        raise RuntimeError("No capture interfaces detected. Ensure Npcap is installed and running.")

    # 1. If no interface requested, choose recommended active Wi-Fi or active Ethernet
    if not user_interface_name or user_interface_name.strip() == "":
        for item in all_ifaces:
            fname = item["friendly_name"].lower()
            if ("wi-fi" in fname or "wifi" in fname) and item["is_up"] and "warp" not in fname:
                logger.info("Auto-selected active Wi-Fi interface: %s (%s)", item["friendly_name"], item["network_name"])
                return item.get("scapy_object") or item["network_name"]

        for item in all_ifaces:
            fname = item["friendly_name"].lower()
            if item["is_up"] and "warp" not in fname and "loopback" not in fname:
                logger.info("Auto-selected active interface: %s (%s)", item["friendly_name"], item["network_name"])
                return item.get("scapy_object") or item["network_name"]

        return all_ifaces[0].get("scapy_object") or all_ifaces[0]["network_name"]

    target = user_interface_name.strip().lower()

    # 2. Exact match on friendly name (e.g. 'Wi-Fi', 'Ethernet')
    for item in all_ifaces:
        if item["friendly_name"].lower() == target:
            logger.info("Resolved interface '%s' by exact friendly name -> %s (%s)", user_interface_name, item["friendly_name"], item["network_name"])
            return item.get("scapy_object") or item["network_name"]

    # 3. Substring match on friendly name or hardware description (avoiding WARP unless asked)
    for item in all_ifaces:
        fname = item["friendly_name"].lower()
        desc = item["description"].lower()
        if (target in fname or target in desc) and ("warp" not in fname or "warp" in target):
            logger.info("Resolved interface '%s' by substring match -> %s (%s)", user_interface_name, item["friendly_name"], item["network_name"])
            return item.get("scapy_object") or item["network_name"]

    # 4. Match on network_name (e.g. '\\Device\\NPF_{...}') or GUID
    for item in all_ifaces:
        if target in item["network_name"].lower() or target in item["guid"].lower() or target in item["identifier"].lower():
            logger.info("Resolved interface '%s' by Npcap network name -> %s", user_interface_name, item["network_name"])
            return item.get("scapy_object") or item["network_name"]

    available_names = [f"'{i['friendly_name']}' ({i['description']})" for i in all_ifaces]
    raise ValueError(
        f"Unable to resolve network interface '{user_interface_name}'. "
        f"Available interfaces: {', '.join(available_names)}"
    )
