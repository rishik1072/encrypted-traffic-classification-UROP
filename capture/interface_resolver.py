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


def list_scapy_interfaces(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Returns detailed metadata for all Scapy/Npcap interfaces available on the system."""
    global _CACHED_INTERFACES, _LAST_IFACE_SCAN_TIME
    now = time.time()
    if not force_refresh and _CACHED_INTERFACES is not None and (now - _LAST_IFACE_SCAN_TIME) < 60.0:
        return _CACHED_INTERFACES

    interfaces: List[Dict[str, Any]] = []
    try:
        import scapy.all  # Crucial: imports arch/windows modules so conf.ifaces is populated
        from scapy.config import conf

        if conf.ifaces is None:
            logger.warning("conf.ifaces is None; Npcap driver may not be running.")
            return []

        for iface_key, iface_obj in conf.ifaces.items():
            # Scapy on Windows:
            # - iface_obj.name: Friendly Windows Name (e.g. 'Wi-Fi', 'Ethernet')
            # - iface_obj.description: Hardware Description (e.g. 'Intel(R) Wi-Fi 6 AX201')
            # - iface_obj.network_name: Npcap Device Path (e.g. '\\Device\\NPF_{GUID}')
            friendly_name = getattr(iface_obj, "name", str(iface_key))
            description = getattr(iface_obj, "description", "")
            network_name = getattr(iface_obj, "network_name", str(iface_key))
            guid = getattr(iface_obj, "guid", str(iface_key))
            ip = getattr(iface_obj, "ip", "")

            # Determine status
            is_up = bool(ip and ip not in ["0.0.0.0", "169.254.0.0", ""])
            # Special check for active non-APIPA IP
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

    _CACHED_INTERFACES = interfaces
    _LAST_IFACE_SCAN_TIME = now
    return interfaces


def resolve_capture_interface(user_interface_name: Optional[str] = None) -> Any:
    """
    Resolves a user-provided interface string to a valid Scapy NetworkInterface object.
    Supports friendly names like 'Wi-Fi', descriptions, or raw Npcap network names.
    """
    import scapy.all
    from scapy.config import conf

    all_ifaces = list_scapy_interfaces()
    if not all_ifaces:
        raise RuntimeError("No capture interfaces detected. Ensure Npcap is installed and running.")

    # 1. If no interface requested, choose recommended active Wi-Fi or active Ethernet
    if not user_interface_name or user_interface_name.strip() == "":
        for item in all_ifaces:
            fname = item["friendly_name"].lower()
            desc = item["description"].lower()
            if ("wi-fi" in fname or "wifi" in fname) and item["is_up"] and "warp" not in fname:
                logger.info("Auto-selected active Wi-Fi interface: %s (%s)", item["friendly_name"], item["network_name"])
                return item["scapy_object"]

        for item in all_ifaces:
            fname = item["friendly_name"].lower()
            if item["is_up"] and "warp" not in fname and "loopback" not in fname:
                logger.info("Auto-selected active interface: %s (%s)", item["friendly_name"], item["network_name"])
                return item["scapy_object"]

        return conf.iface

    target = user_interface_name.strip().lower()

    # 2. Exact match on friendly name (e.g. 'Wi-Fi', 'Ethernet')
    for item in all_ifaces:
        if item["friendly_name"].lower() == target:
            logger.info("Resolved interface '%s' by exact friendly name -> %s (%s)", user_interface_name, item["friendly_name"], item["network_name"])
            return item["scapy_object"]

    # 3. Substring match on friendly name or hardware description (avoiding WARP unless asked)
    for item in all_ifaces:
        fname = item["friendly_name"].lower()
        desc = item["description"].lower()
        if (target in fname or target in desc) and ("warp" not in fname or "warp" in target):
            logger.info("Resolved interface '%s' by substring match -> %s (%s)", user_interface_name, item["friendly_name"], item["network_name"])
            return item["scapy_object"]

    # 4. Match on network_name (e.g. '\\Device\\NPF_{...}') or GUID
    for item in all_ifaces:
        if target in item["network_name"].lower() or target in item["guid"].lower() or target in item["identifier"].lower():
            logger.info("Resolved interface '%s' by Npcap network name -> %s", user_interface_name, item["network_name"])
            return item["scapy_object"]

    # 5. Check if it's already in conf.ifaces dictionary directly
    if user_interface_name in conf.ifaces:
        return conf.ifaces[user_interface_name]

    available_names = [f"'{i['friendly_name']}' ({i['description']})" for i in all_ifaces]
    raise ValueError(
        f"Unable to resolve network interface '{user_interface_name}'. "
        f"Available interfaces: {', '.join(available_names)}"
    )
