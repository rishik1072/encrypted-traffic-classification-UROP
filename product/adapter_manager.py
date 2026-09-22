"""
Network Adapter Discovery and Resolution Manager for Encrypted Traffic Monitor.

Wraps capture/interface_resolver.py to provide structured adapter metadata (friendly name,
hardware description, Npcap device path, up/down status, link speed) and user selection helpers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from capture.interface_resolver import list_scapy_interfaces, resolve_capture_interface

logger = logging.getLogger(__name__)


def list_adapters() -> List[Dict[str, Any]]:
    """
    Discovers and enumerates all local network adapters with normalized metadata.

    Returns:
        List of dictionaries with:
        - friendly_name: e.g. 'Wi-Fi', 'Ethernet'
        - interface_description: e.g. 'Intel(R) Wi-Fi 6 AX201 160MHz'
        - npcap_name: e.g. '\\Device\\NPF_{GUID}'
        - status: 'UP' | 'DOWN'
        - link_speed: estimated or reported link speed (e.g. 'Auto / 1 Gbps' or 'Wi-Fi')
        - ip: IP address if assigned
        - is_wifi: bool
        - is_ethernet: bool
        - scapy_object: Scapy NetworkInterface object
    """
    raw_ifaces = list_scapy_interfaces()
    adapters: List[Dict[str, Any]] = []

    for item in raw_ifaces:
        fname = item.get("friendly_name", "Unknown")
        desc = item.get("description", "")
        net_name = item.get("network_name", "")
        is_up = bool(item.get("is_up", False))
        ip = item.get("ip", "")

        fname_lower = fname.lower()
        desc_lower = desc.lower()

        is_wifi = "wi-fi" in fname_lower or "wifi" in fname_lower or "wireless" in desc_lower or "802.11" in desc_lower
        is_ethernet = "ethernet" in fname_lower or "eth" in fname_lower or "gigabit" in desc_lower or "realtek" in desc_lower or "intel" in desc_lower and not is_wifi

        # Determine link speed descriptor
        if is_wifi:
            link_speed = "Wi-Fi (802.11ax/ac/n)"
        elif is_ethernet:
            link_speed = "Ethernet (10/100/1000 Mbps)"
        elif "loopback" in fname_lower or "npcap loopback" in desc_lower:
            link_speed = "Loopback (Virtual)"
        elif "warp" in fname_lower or "cloudflare" in desc_lower or "wireguard" in desc_lower:
            link_speed = "Tunnel / VPN Virtual NIC"
        else:
            link_speed = "Auto-Negotiated"

        adapters.append({
            "friendly_name": fname,
            "interface_description": desc,
            "npcap_name": net_name,
            "status": "UP" if is_up else "DOWN",
            "link_speed": link_speed,
            "ip": ip,
            "is_wifi": is_wifi,
            "is_ethernet": is_ethernet,
            "scapy_object": item.get("scapy_object"),
        })

    return adapters


_CACHED_DEFAULT_ADAPTER: Optional[Dict[str, Any]] = None


def set_default_adapter(adapter: Optional[Dict[str, Any]]) -> None:
    """Explicitly sets the cached default adapter."""
    global _CACHED_DEFAULT_ADAPTER
    _CACHED_DEFAULT_ADAPTER = adapter


def get_default_adapter(force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """
    Identifies the best default active capture adapter (prioritizing active Wi-Fi, then active Ethernet).
    Caches the discovered adapter to avoid repeated hardware/Npcap enumerations.
    """
    global _CACHED_DEFAULT_ADAPTER
    if not force_refresh and _CACHED_DEFAULT_ADAPTER is not None:
        return _CACHED_DEFAULT_ADAPTER

    try:
        adapters = list_adapters()
    except Exception as e:
        logger.debug("list_adapters exception: %s", e)
        adapters = []

    res: Optional[Dict[str, Any]] = None
    if adapters:
        # 1. Look for active UP Wi-Fi adapter (non-tunnel)
        for ad in adapters:
            if ad["is_wifi"] and ad["status"] == "UP" and "warp" not in ad["friendly_name"].lower():
                res = ad
                break

        # 2. Look for active UP Ethernet adapter
        if not res:
            for ad in adapters:
                if ad["is_ethernet"] and ad["status"] == "UP" and "warp" not in ad["friendly_name"].lower():
                    res = ad
                    break

        # 3. Look for any active UP adapter
        if not res:
            for ad in adapters:
                if ad["status"] == "UP" and "loopback" not in ad["friendly_name"].lower():
                    res = ad
                    break

        if not res and adapters:
            res = adapters[0]

    # Fallback to last cached or standard default
    if not res:
        res = _CACHED_DEFAULT_ADAPTER or {
            "friendly_name": "Wi-Fi",
            "interface_description": "Default Wi-Fi Network Adapter",
            "npcap_name": r"\Device\NPF_Generic",
            "status": "UP",
            "link_speed": "Wi-Fi (802.11ax/ac/n)",
            "ip": "127.0.0.1",
            "is_wifi": True,
            "is_ethernet": False,
            "scapy_object": None,
        }

    _CACHED_DEFAULT_ADAPTER = res
    return res


def validate_adapter(adapter_name: str) -> Dict[str, Any]:
    """
    Validates that a named adapter exists, is recognized by Npcap/Scapy, and is ready for capture.
    """
    adapters = list_adapters()
    if not adapters:
        return {
            "valid": False,
            "message": "No network adapters detected by Npcap capture engine.",
            "adapter": None,
        }

    if not adapter_name or not adapter_name.strip():
        return {
            "valid": False,
            "message": "Adapter name cannot be empty or unavailable.",
            "adapter": None,
        }

    target = adapter_name.strip().lower()

    # Exact or substring match
    for ad in adapters:
        fname = ad["friendly_name"].lower()
        desc = ad["interface_description"].lower()
        npcap = ad["npcap_name"].lower()

        if target in (fname, desc, npcap) or (target in fname) or (target in desc):
            return {
                "valid": True,
                "message": f"Adapter '{ad['friendly_name']}' resolved and ready ({ad['status']}).",
                "adapter": ad,
            }

    available_names = [a["friendly_name"] for a in adapters]
    return {
        "valid": False,
        "message": f"Adapter '{adapter_name}' not found or not available. Available: {', '.join(available_names)}",
        "adapter": None,
    }
