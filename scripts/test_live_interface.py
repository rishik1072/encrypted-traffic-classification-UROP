"""
Direct Live Network Interface Sniff Test.

Validates that Scapy and Npcap can open the specified adapter (e.g. 'Wi-Fi'),
capture real packets, and calculate volumes without any synthetic injection.
Exits non-zero if capture fails or zero packets are received.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, List

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from capture.interface_resolver import resolve_capture_interface


def test_live_interface(interface_name: str = "Wi-Fi", duration_seconds: int = 10) -> bool:
    print("\n=======================================================")
    print("                LIVE INTERFACE SNIFF TEST              ")
    print("=======================================================\n")
    print(f"[*] Requested Interface: '{interface_name}'")

    try:
        iface_obj = resolve_capture_interface(interface_name)
        iface_desc = getattr(iface_obj, "description", str(iface_obj))
        iface_id = getattr(iface_obj, "name", str(iface_obj))
        print(f"[*] Resolved Scapy Adapter: {iface_id} ({iface_desc})")
    except Exception as e:
        print(f"[!] INTERFACE RESOLUTION FAILED: {e}")
        print("\nSTATUS: FAIL\n")
        return False

    print(f"[*] Starting Scapy live sniff loop for {duration_seconds} seconds...")
    captured_packets: List[Any] = []

    try:
        from scapy.all import sniff
        def _handler(pkt: Any):
            captured_packets.append(pkt)

        sniff(
            iface=iface_obj,
            prn=_handler,
            timeout=duration_seconds,
            store=False,
            filter="ip or ip6",
        )
    except Exception as e:
        print(f"[!] ADAPTER OPEN OR CAPTURE ERROR: {e}")
        print("\nSTATUS: FAIL\nReason: Unable to open capture adapter or unprivileged access.\n")
        return False

    packet_count = len(captured_packets)
    total_bytes = sum(len(p) for p in captured_packets)

    print(f"[*] Capture Duration: {duration_seconds} sec")
    print(f"[*] Packets Captured: {packet_count}")
    print(f"[*] Bytes Captured:   {total_bytes:,} bytes")

    if packet_count == 0:
        print("\nSTATUS: FAIL\nReason: Zero packets captured during active sniffing window.")
        return False

    print("\nSTATUS: PASS\n")
    return True


def main():
    parser = argparse.ArgumentParser(description="Test Live Network Interface with Scapy.")
    parser.add_argument("--interface", type=str, default="Wi-Fi", help="Target adapter name (default: Wi-Fi)")
    parser.add_argument("--duration", type=int, default=10, help="Sniff duration in seconds (default: 10)")
    args = parser.parse_args()

    success = test_live_interface(interface_name=args.interface, duration_seconds=args.duration)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
