"""
List Available Capture Interfaces CLI.

Outputs friendly Windows adapter names, Scapy/Npcap identifiers, IP addresses,
and highlights recommended interfaces for live research collection.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from capture.interface_resolver import list_scapy_interfaces


def main():
    print("\n=======================================================")
    print("             AVAILABLE CAPTURE INTERFACES             ")
    print("=======================================================\n")

    ifaces = list_scapy_interfaces()
    if not ifaces:
        print("[!] No network capture interfaces found. Ensure Npcap is installed.")
        sys.exit(1)

    print(f"{'Friendly Name':<20} | {'Status':<8} | {'IP Address':<15} | {'Description / Identifier'}")
    print("-" * 75)

    recommended_iface = None
    for item in ifaces:
        fname = item["friendly_name"]
        status = "Up" if item["is_up"] else "Down"
        ip = item["ip"] or "None"
        desc = item["description"] or item["identifier"]

        flag = ""
        if ("wi-fi" in fname.lower() or "wifi" in fname.lower()) and item["is_up"] and "warp" not in fname.lower():
            flag = " [RECOMMENDED: Wi-Fi]"
            recommended_iface = fname

        print(f"{fname:<20} | {status:<8} | {ip:<15} | {desc[:26]}{flag}")

    print("-" * 75)
    if recommended_iface:
        print(f"\n[*] Recommended Capture Interface: '{recommended_iface}'")
        print(f"[*] Command to collect: python scripts/collect_traffic.py --class Web --interface \"{recommended_iface}\"\n")
    else:
        print("\n[*] Please choose an active interface from the table above.\n")


if __name__ == "__main__":
    main()
