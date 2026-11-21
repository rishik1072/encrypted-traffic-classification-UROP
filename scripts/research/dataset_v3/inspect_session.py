"""
CLI Tool: Inspect Dataset V3 Session Metadata and Early-Prefix Horizons.

Usage:
    python scripts/research/dataset_v3/inspect_session.py --session data/research_v3/sess_xxx
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def inspect_session(session_path: Path) -> None:
    manifest_p = session_path / "session_manifest.json"
    flows_p = session_path / "flow_index.csv"
    labels_p = session_path / "labels.csv"
    packets_p = session_path / "packet_metadata.jsonl"
    val_p = session_path / "validation_report.json"

    if not manifest_p.exists():
        print(f"Error: {manifest_p} not found.")
        return

    with open(manifest_p, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print("=" * 70)
    print(f"DATASET V3 SESSION INSPECTION: {manifest.get('session_id')}")
    print("=" * 70)
    print(f"  Intended Class  : {manifest.get('intended_traffic_class')}")
    print(f"  Application     : {manifest.get('application_alias')}")
    print(f"  Activity        : {manifest.get('collection_activity')}")
    print(f"  Environment     : {manifest.get('environment_id')} ({manifest.get('adapter_type')})")
    print(f"  Tunnel State    : {manifest.get('tunnel_status')}")
    print(f"  Start UTC       : {manifest.get('collection_start_utc')}")
    print(f"  End UTC         : {manifest.get('collection_end_utc')}")
    print(f"  Status          : {manifest.get('capture_status')}")
    print(f"  Device Pseudonym: {manifest.get('device_pseudonym')}")
    print(f"  Total Packets   : {manifest.get('packet_count')}")
    print(f"  Total Flows     : {manifest.get('flow_count')}")

    # Labels breakdown
    if labels_p.exists():
        classes_counter = Counter()
        qualities_counter = Counter()
        with open(labels_p, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                classes_counter[r["traffic_class"]] += 1
                qualities_counter[r["label_quality"]] += 1

        print("\n--- Ground-Truth Labels Breakdown ---")
        for cls, cnt in classes_counter.items():
            print(f"  Class '{cls:15s}': {cnt} flows")
        print("  Label Qualities:")
        for q, cnt in qualities_counter.items():
            print(f"    - {q:15s}: {cnt} flows")

    # Packet prefix coverage inspection
    if packets_p.exists():
        packet_counts_by_flow = Counter()
        with open(packets_p, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                packet_counts_by_flow[rec["flow_id"]] += 1

        total_flows = len(packet_counts_by_flow)
        print("\n--- Early-Prefix Horizon Feasibility ---")
        print(f"  Total Active Flows Observed: {total_flows}")
        for k in (1, 3, 5, 10, 20):
            meeting_k = sum(1 for cnt in packet_counts_by_flow.values() if cnt >= k)
            pct = (meeting_k / total_flows * 100.0) if total_flows > 0 else 0.0
            print(f"  Horizon K = {k:2d} packets: {meeting_k:4d}/{total_flows} flows ({pct:5.1f}% coverage)")

    # Validation status
    if val_p.exists():
        with open(val_p, "r", encoding="utf-8") as f:
            val = json.load(f)
        status_str = "VALID" if val.get("is_valid") else "INVALID"
        print(f"\n--- Validation Status: {status_str} ---")
        if not val.get("is_valid"):
            for err in val.get("errors", []):
                print(f"  [ERROR] {err}")
    print("=" * 70)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect Dataset V3 Session")
    parser.add_argument("--session", type=str, required=True, help="Path to session directory")
    args = parser.parse_args()
    inspect_session(Path(args.session))
    return 0


if __name__ == "__main__":
    sys.exit(main())
