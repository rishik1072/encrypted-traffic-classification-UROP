"""
Check Capture Environment CLI.

Verifies Npcap, Scapy, and live interface capture capability.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from capture.pcap_environment import check_capture_environment


def main():
    res = check_capture_environment()
    sys.exit(0 if res["ready"] else 1)


if __name__ == "__main__":
    main()
