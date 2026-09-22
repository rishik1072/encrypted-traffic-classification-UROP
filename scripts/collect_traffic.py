"""
Single-Session Strict Real Traffic Collection CLI.

Requires a valid physical or wireless network interface (e.g. 'Wi-Fi').
Fails closed with non-zero exit code if capture encounters an error or zero packets.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from capture.collection_runner import CollectionRunner
from capture.session_manager import CollectionSession
from capture.traffic_activities import TRAFFIC_ACTIVITIES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("collect_traffic")


def main():
    parser = argparse.ArgumentParser(description="Collect Controlled Real Encrypted Traffic (Strict Mode).")
    parser.add_argument("--class", dest="traffic_class", required=True, choices=["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"], help="Target traffic class")
    parser.add_argument("--duration", type=int, default=60, help="Capture duration in seconds (default: 60)")
    parser.add_argument("--warmup", type=int, default=3, help="Warmup seconds (default: 3)")
    parser.add_argument("--interface", type=str, default="Wi-Fi", help="Network capture interface (e.g. 'Wi-Fi')")
    parser.add_argument("--notes", type=str, default="", help="Optional notes regarding the activity")
    parser.add_argument("--seq", type=int, default=1, help="Sequence number")
    args = parser.parse_args()

    activity_info = TRAFFIC_ACTIVITIES.get(args.traffic_class, {})
    print("\n=======================================================")
    print("      CONTROLLED REAL TRAFFIC COLLECTION (STRICT REAL)  ")
    print("=======================================================")
    print(f"[*] Target Class:       {args.traffic_class}")
    print(f"[*] Intended Activity:  {activity_info.get('activity')}")
    print(f"[*] Capture Duration:   {args.duration}s (Warmup: {args.warmup}s)")
    print(f"[*] Requested Adapter:  '{args.interface}'")
    print(f"[*] Capture Mode:       STRICT REAL (No Synthetic Fallbacks)")
    print("-------------------------------------------------------")
    print(">>> OPERATOR: Prepare to perform ONLY the intended activity.")
    print("=======================================================\n")

    session = CollectionSession.create(
        traffic_class=args.traffic_class,
        seq_num=args.seq,
        capture_source="REAL_LIVE_CAPTURE",
        notes=args.notes or activity_info.get("activity", ""),
    )

    runner = CollectionRunner(interface=args.interface)
    result_session = runner.run_session(
        session=session,
        duration_seconds=args.duration,
        warmup_seconds=args.warmup,
    )

    print("\n=======================================================")
    print("               COLLECTION SESSION RESULT               ")
    print("=======================================================")
    print(f"[*] Session ID:       {result_session.session_id}")
    print(f"[*] Lifecycle State:  {result_session.state.value}")
    print(f"[*] Capture Source:   {result_session.capture_source}")
    print(f"[*] Packets Captured: {result_session.packet_count}")
    print(f"[*] Bytes Captured:   {result_session.byte_count:,} bytes")
    print(f"[*] Flows Detected:   {result_session.flow_count}")
    print(f"[*] Metadata Path:    {result_session.metadata_path or 'None'}")
    print(f"[*] SHA-256 Digest:   {result_session.sha256[:16] if result_session.sha256 else 'None'}...")
    if result_session.error_code or result_session.error_message:
        print(f"[!] Capture Error:    [{result_session.error_code}] {result_session.error_message}")
        print("\nSESSION STATUS: FAILED (No real data registered)\n")
        sys.exit(1)

    print("\nSESSION STATUS: SUCCESS (Registered as REAL_LIVE_CAPTURE)\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
