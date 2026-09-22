"""
Npcap and Scapy Capture Environment Diagnostic Utility.

Verifies Windows OS, Npcap kernel driver installation, Scapy import, and active NICs.
"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict

from capture.interface_resolver import list_scapy_interfaces


def check_capture_environment() -> Dict[str, Any]:
    print("\n=======================================================")
    print("        NPCAP & CAPTURE ENVIRONMENT DIAGNOSTICS        ")
    print("=======================================================\n")

    os_type = platform.system()
    print(f"[*] Operating System: {os_type} ({platform.release()})")

    scapy_ok = False
    try:
        import scapy
        scapy_ok = True
        print(f"[*] Scapy Library:    OK (v{getattr(scapy, '__version__', 'unknown')})")
    except ImportError:
        print("[!] Scapy Library:    NOT INSTALLED -> FAIL")

    # Detect Npcap / WinPcap driver on Windows
    npcap_ok = False
    if os_type == "Windows":
        sys_root = os.environ.get("SystemRoot", "C:\\Windows")
        npcap_dll1 = Path(sys_root) / "System32" / "Npcap" / "wpcap.dll"
        npcap_dll2 = Path(sys_root) / "System32" / "wpcap.dll"
        npcap_service = Path(sys_root) / "System32" / "drivers" / "npcap.sys"

        if npcap_dll1.exists() or npcap_dll2.exists() or npcap_service.exists():
            npcap_ok = True
            print("[*] Npcap Driver:     OK (Kernel driver / wpcap.dll detected)")
        else:
            print("[!] Npcap Driver:     NOT DETECTED in System32 (Npcap required for live capture)")
    else:
        npcap_ok = True
        print("[*] Packet Engine:    Linux/Unix libpcap")

    # Detect Interfaces
    ifaces = list_scapy_interfaces() if scapy_ok else []
    print(f"[*] Interfaces Found: {len(ifaces)} capture-capable interfaces detected")

    wifi_found = any("wi-fi" in i["friendly_name"].lower() or "wifi" in i["friendly_name"].lower() for i in ifaces)
    print(f"[*] Wi-Fi Adapter:    {'FOUND & READY' if wifi_found else 'NOT FOUND'}")

    all_ready = scapy_ok and npcap_ok and len(ifaces) > 0
    print("\n=======================================================")
    print(f"  ENVIRONMENT STATUS: {'READY FOR LIVE CAPTURE' if all_ready else 'CAPTURE ENGINE ISSUE'}")
    print("=======================================================\n")

    return {
        "os": os_type,
        "scapy_ok": scapy_ok,
        "npcap_ok": npcap_ok,
        "interface_count": len(ifaces),
        "wifi_found": wifi_found,
        "ready": all_ready,
    }


if __name__ == "__main__":
    res = check_capture_environment()
    sys.exit(0 if res["ready"] else 1)
