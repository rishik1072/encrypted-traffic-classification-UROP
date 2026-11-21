"""
Standalone Layer-2 Socket Diagnostic Smoke Test.

Executes safe, non-capturing diagnostic socket verification:
1. Resolves friendly interface name (e.g. "Wi-Fi") to Scapy NetworkInterface.
2. Displays non-sensitive resolution diagnostics.
3. Confirms socket provider is Npcap/libpcap L2pcapListenSocket.
4. Opens the Layer-2 socket synchronously.
5. Confirms socket creation.
6. Immediately closes the socket.
7. Does NOT start AsyncSniffer, does NOT sniff packets, does NOT create dataset sessions.
"""

from __future__ import annotations

import argparse
import logging
import platform
import sys
from pathlib import Path

# Check elevation on Windows before Scapy loads Npcap driver
if platform.system() == "Windows":
    import ctypes
    try:
        is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        is_admin = False
    if not is_admin:
        print("=" * 70)
        print("DATASET V3 LAYER-2 SOCKET DIAGNOSTIC SMOKE TEST: ELEVATION REQUIRED")
        print("=" * 70)
        print("Windows Npcap is configured with 'AdminOnly: 1'.")
        print("Opening Layer-2 sockets or enumerating physical adapters requires")
        print("Administrator privileges.")
        print("")
        print("Please run this command from an elevated Administrator terminal:")
        print("  1. Open PowerShell or Command Prompt as Administrator")
        print("  2. cd 'C:\\UROP project\\encrypted-traffic-classification-UROP'")
        print("  3. python scripts/research/dataset_v3/test_socket_smoke.py --interface \"Wi-Fi\"")
        print("=" * 70)
        sys.exit(5)  # ERROR_ACCESS_DENIED (5)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research.dataset_v3.collector import PhysicalTrafficCollector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_socket_smoke")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dataset V3 Layer-2 Socket Diagnostic Smoke Test"
    )
    parser.add_argument(
        "--interface",
        type=str,
        default="Wi-Fi",
        help="Interface friendly name or identifier (default: 'Wi-Fi').",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default="tcp or udp",
        help="PCAP BPF filter string (default: 'tcp or udp').",
    )
    parser.add_argument(
        "--promisc",
        action="store_true",
        help="Enable promiscuous mode for socket test.",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("DATASET V3 LAYER-2 SOCKET DIAGNOSTIC SMOKE TEST")
    print(f"Target Interface: '{args.interface}'")
    print(f"BPF Filter:       '{args.filter}'")
    print(f"Promiscuous:      {args.promisc}")
    print("=" * 70)

    try:
        diag = PhysicalTrafficCollector.smoke_test_socket(
            interface_name=args.interface,
            pcap_filter=args.filter,
            promiscuous=args.promisc,
        )
        print("\n" + "=" * 70)
        print("DIAGNOSTIC SMOKE TEST: PASSED")
        print(f"  Input Interface:        {diag['interface_input']}")
        print(f"  Resolved Name:          {diag['resolved_name']}")
        print(f"  Resolved Device Path:   {diag['sanitized_network_name']}")
        print(f"  Interface Type:         {diag['interface_type']}")
        print(f"  Provider Name:          {diag['provider_name']}")
        print(f"  libpcap Enabled:        {diag['libpcap_enabled']}")
        print(f"  Socket Provider Class:  {diag['socket_class']}")
        print(f"  Socket Opened:          {diag['socket_opened']}")
        print(f"  Socket Closed:          {diag['socket_closed']}")
        print(f"  Final Stage Reached:    {diag['stage_reached']}")
        print("=" * 70 + "\n")
        sys.exit(0)
    except Exception as e:
        print("\n" + "=" * 70)
        print("DIAGNOSTIC SMOKE TEST: FAILED")
        print(f"  Error Message: {e}")
        native_code = getattr(e, "winerror", getattr(e, "errno", None))
        if native_code is not None:
            print(f"  Native Error Code: {native_code}")
        print(f"  Exception Type: {type(e).__name__}")
        print("=" * 70 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
