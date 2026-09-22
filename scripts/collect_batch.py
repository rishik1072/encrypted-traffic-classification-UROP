"""
Batch Traffic Collection CLI.

Iterates across multiple sessions with clear operator prompts.
Usage:
    python scripts/collect_batch.py --class Web --sessions 3 --duration 10
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from capture.collection_runner import CollectionRunner
from capture.session_manager import CollectionSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("collect_batch")


def main():
    parser = argparse.ArgumentParser(description="Batch Collect Controlled Traffic Sessions.")
    parser.add_argument("--class", dest="traffic_class", required=True, choices=["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"], help="Target traffic class")
    parser.add_argument("--sessions", type=int, default=3, help="Number of sessions to collect (default: 3)")
    parser.add_argument("--duration", type=int, default=15, help="Duration per session in seconds (default: 15)")
    parser.add_argument("--interface", type=str, default=None, help="Network capture interface")
    args = parser.parse_args()

    print(f"\n[*] Starting Batch Collection for Class: '{args.traffic_class}' ({args.sessions} sessions)\n")
    runner = CollectionRunner(interface=args.interface)

    for i in range(1, args.sessions + 1):
        print(f"\n--- [Session {i}/{args.sessions}] Preparing {args.traffic_class} Capture ---")
        session = CollectionSession.create(traffic_class=args.traffic_class, seq_num=i)
        res = runner.run_session(session=session, duration_seconds=args.duration, warmup_seconds=2)
        print(f"-> Session {res.session_id}: {res.state.value} ({res.packet_count} pkts, {res.flow_count} flows)")
        if i < args.sessions:
            print("-> Waiting 3s cooldown buffer before next session...")
            time.sleep(3)

    print("\n[*] Batch collection completed successfully.\n")


if __name__ == "__main__":
    main()
