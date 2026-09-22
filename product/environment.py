"""
Environment and Operating System Diagnostic Module for Windows Productization.

Detects Windows OS version, 64-bit architecture, administrator elevation,
Python runtime compatibility, and Npcap kernel driver status with actionable guidance.
"""

from __future__ import annotations

import ctypes
import logging
import os
from pathlib import Path
import platform
import sys
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def is_windows() -> bool:
    """Checks if host OS is Windows."""
    return platform.system() == "Windows"


def is_64bit() -> bool:
    """Checks if process and machine are 64-bit."""
    return sys.maxsize > 2**32 and platform.machine().endswith("64")


def is_admin() -> bool:
    """Detects whether current process runs with administrative/elevated privileges."""
    if not is_windows():
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def get_os_info() -> Dict[str, Any]:
    """Returns detailed OS identification metadata."""
    system_name = platform.system()
    release = platform.release()
    version = platform.version()
    machine = platform.machine()
    is_win11 = False

    if system_name == "Windows":
        try:
            # Windows 11 has build numbers >= 22000
            build_num = int(version.split(".")[-1]) if "." in version else 0
            if build_num >= 22000:
                is_win11 = True
        except Exception:
            pass

    display_name = "Windows 11" if is_win11 else f"{system_name} {release}"

    return {
        "system": system_name,
        "release": release,
        "version": version,
        "machine": machine,
        "display_name": display_name,
        "is_windows": is_windows(),
        "is_64bit": is_64bit(),
        "is_admin": is_admin(),
    }


def check_npcap() -> Dict[str, Any]:
    """
    Evaluates Npcap driver installation, DLL existence, and live capture capability.

    Returns structured status:
    - status: 'PASS' | 'WARNING' | 'FAIL'
    - message: Short explanation
    - details: Technical component status
    - instructions: Actionable guidance for user if missing
    """
    details: Dict[str, bool] = {
        "npcap_sys_driver": False,
        "npcap_wpcap_dll": False,
        "system32_wpcap_dll": False,
        "scapy_loaded": False,
        "winpcap_compat": False,
    }

    instructions = ""
    status = "FAIL"
    message = "Npcap driver or packet capture DLLs not found."

    # Check Scapy import
    try:
        import scapy.all  # noqa: F401
        details["scapy_loaded"] = True
    except Exception as e:
        logger.debug("Scapy import check note: %s", e)

    if not is_windows():
        # Non-Windows environments use standard libpcap
        status = "PASS"
        message = "Unix/Linux packet capture engine detected."
        return {
            "status": status,
            "message": message,
            "details": details,
            "instructions": "",
            "can_capture": True,
        }

    sys_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    npcap_dir = sys_root / "System32" / "Npcap"
    npcap_dll = npcap_dir / "wpcap.dll"
    sys32_dll = sys_root / "System32" / "wpcap.dll"
    driver_sys = sys_root / "System32" / "drivers" / "npcap.sys"

    if driver_sys.exists():
        details["npcap_sys_driver"] = True
    if npcap_dll.exists():
        details["npcap_wpcap_dll"] = True
    if sys32_dll.exists():
        details["system32_wpcap_dll"] = True
        details["winpcap_compat"] = True

    has_driver = details["npcap_sys_driver"]
    has_dll = details["npcap_wpcap_dll"] or details["system32_wpcap_dll"]

    if has_driver and has_dll and details["scapy_loaded"]:
        status = "PASS"
        message = "Npcap kernel driver and packet capture libraries are installed and ready."
    elif has_dll and details["scapy_loaded"]:
        status = "WARNING"
        message = "Packet capture DLL detected, but npcap.sys driver service could not be directly verified."
    elif not has_dll and not has_driver:
        status = "FAIL"
        message = "Npcap packet capture driver was NOT detected on this system."
        instructions = (
            "Encrypted Traffic Monitor requires Npcap for live packet sniffing on Windows.\n\n"
            "Action Required:\n"
            "1. Download Npcap from https://npcap.com/#download\n"
            "2. Run the installer with 'Install Npcap in WinPcap API-compatible Mode' checked.\n"
            "3. Restart the application or run in DEMO mode."
        )
    else:
        status = "WARNING"
        message = "Npcap installation appears incomplete or requires administrative permissions."
        instructions = (
            "Please ensure Npcap is installed with WinPcap compatibility mode.\n"
            "Try running the application as Administrator."
        )

    can_capture = status in ("PASS", "WARNING")

    return {
        "status": status,
        "message": message,
        "details": details,
        "instructions": instructions,
        "can_capture": can_capture,
    }


def format_npcap_instructions(npcap_result: Dict[str, Any]) -> str:
    """Returns human-readable user guidance when Npcap is missing or degraded."""
    if npcap_result.get("status") == "PASS":
        return "Npcap: PASS (Capture Engine Ready)"
    
    lines = [
        "--------------------------------------------------",
        f"NPCAP STATUS: {npcap_result.get('status')}",
        f"Details: {npcap_result.get('message')}",
        "--------------------------------------------------",
    ]
    if npcap_result.get("instructions"):
        lines.append(npcap_result["instructions"])
        lines.append("--------------------------------------------------")
    return "\n".join(lines)
