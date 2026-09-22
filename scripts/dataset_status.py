"""
Dataset Balance and Collection Status Tracker.

Displays real vs synthetic counts, target progression (e.g. 10/10 per class),
total flows, total packets, and validation summary.
Separates REAL DATASET counts strictly from SYNTHETIC TEST FIXTURES.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

TARGETS_PER_CLASS = {
    "Web": 10,
    "Video": 10,
    "Messaging": 10,
    "VoIP": 10,
    "File Transfer": 10,
    "Other": 10,
}


def print_dataset_status(manifest_path: str = "data/dataset_manifest.csv", flows_real_path: str = "data/processed/flows/flows_real.csv"):
    m_p = Path(manifest_path)
    if not m_p.exists():
        print(f"[!] Manifest not found at {manifest_path}")
        return

    with open(m_p, "r", encoding="utf-8") as f:
        records = list(csv.DictReader(f))

    # Strict Real Filter
    real_records = [
        r for r in records
        if r.get("data_origin") == "real"
        and r.get("capture_source") == "REAL_LIVE_CAPTURE"
        and r.get("validation_status") == "PASS"
    ]
    synth_records = [r for r in records if r not in real_records]

    real_by_class = {c: 0 for c in TARGETS_PER_CLASS}
    total_pkts = 0
    total_bytes = 0

    for r in real_records:
        c = r.get("traffic_class", "Other")
        if c in real_by_class:
            real_by_class[c] += 1
        total_pkts += int(r.get("packet_count", 0))
        total_bytes += int(r.get("byte_count", 0))

    # Read actual generated real flows if available
    total_real_flows = 0
    fl_p = Path(flows_real_path)
    if fl_p.exists():
        try:
            csv.field_size_limit(sys.maxsize)
        except OverflowError:
            csv.field_size_limit(2147483647)
        with open(fl_p, "r", encoding="utf-8") as f:
            total_real_flows = sum(1 for _ in csv.DictReader(f))

    total_real_sessions = len(real_records)
    total_target_sessions = sum(TARGETS_PER_CLASS.values())

    print("\n=======================================================")
    print("      REAL TRAFFIC RESEARCH DATASET STATUS (STRICT)    ")
    print("=======================================================")
    print(f"{'Traffic Class':<16} | {'Real Sessions':<14} | {'Target':<8} | {'Progress'}")
    print("-------------------------------------------------------")
    for c, target in TARGETS_PER_CLASS.items():
        cnt = real_by_class.get(c, 0)
        pct = (cnt / target) * 100
        bar = "#" * int(pct / 10) + "-" * (10 - int(pct / 10))
        print(f"{c:<16} | {cnt:<14} | {target:<8} | [{bar}] {pct:.0f}%")
    print("-------------------------------------------------------")
    print(f"Total Real Sessions:     {total_real_sessions} / {total_target_sessions} ({(total_real_sessions/total_target_sessions)*100:.1f}%)")
    print(f"Total Real Flows:        {total_real_flows:,}")
    print(f"Total Real Packets:      {total_pkts:,}")
    print(f"Total Real Data Volume:  {total_bytes / (1024*1024):.2f} MB")
    print("-------------------------------------------------------")
    print("## SYNTHETIC TEST FIXTURES")
    print(f"Total Synthetic Fixtures:{len(synth_records)} (Excluded from research experiments)")
    print("=======================================================\n")


if __name__ == "__main__":
    print_dataset_status()
