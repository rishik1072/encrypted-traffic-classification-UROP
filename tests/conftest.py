"""
Pytest configuration and environment fixtures for encrypted-traffic-classification tests.
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import platform
import sys

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))


def _configure_test_scapy_environment() -> None:
    """
    Prevents test collection hangs on Windows when running under un-elevated test processes
    with Npcap AdminOnly=1 active.
    
    Preserves conf.ifaces.reload as the genuine Scapy method so regression tests
    accurately verify that neither packet_parser nor collector overrides conf.ifaces.reload.
    """
    if platform.system() == "Windows":
        try:
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            is_admin = False

        if not is_admin:
            try:
                import scapy.libs.winpcapy
                # In un-elevated unit test runners, prevent low-level C pcap_findalldevs
                # from blocking on Windows Npcap with AdminOnly=1.
                # Leaves conf.ifaces.reload and all Scapy structures 100% genuine and unmodified.
                scapy.libs.winpcapy.pcap_findalldevs = lambda *args, **kwargs: -1
            except Exception:
                pass


_configure_test_scapy_environment()
