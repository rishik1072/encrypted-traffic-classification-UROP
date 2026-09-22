"""
Inspect Dataset Manifest CLI.

Displays all registered dataset records, distinguishing REAL_LIVE_CAPTURE from SYNTHETIC_TEST fixtures.
Supports --origin {real, synthetic, all}. Robust against None/missing values.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def inspect_dataset(manifest_path: str = "data/dataset_manifest.csv", origin_filter: str = "all"):
    p = Path(manifest_path)
    if not p.exists():
        print(f"[!] Manifest not found at {manifest_path}")
        return

    with open(p, "r", encoding="utf-8") as f:
        all_records = list(csv.DictReader(f))

    if origin_filter != "all":
        records = [r for r in all_records if r.get("data_origin", "synthetic") == origin_filter]
    else:
        records = all_records

    print("\n=======================================================")
    print(f"      DATASET MANIFEST REGISTRY AUDIT (origin={origin_filter})")
    print("=======================================================")
    print(f"{'Session / File ID':<30} | {'Class':<12} | {'Origin':<9} | {'Source':<24} | {'Status':<6} | {'Pkts':<7} | {'Bytes (MB)'}")
    print("-" * 105)

    for r in records:
        fid = str(r.get("session_id") or r.get("file_id") or "<missing>")[:30]
        t_class = str(r.get("traffic_class") or "<missing>")[:12]
        origin = str(r.get("data_origin") or "<missing>")[:9]
        source = str(r.get("capture_source") or r.get("source") or "<missing>")[:24]
        status = str(r.get("validation_status") or "<missing>")[:6]
        
        pkts_raw = r.get("packet_count")
        try:
            pkts = f"{int(pkts_raw):,}" if pkts_raw is not None and str(pkts_raw).isdigit() else str(pkts_raw or "<missing>")
        except Exception:
            pkts = str(pkts_raw or "<missing>")

        bytes_raw = r.get("byte_count")
        try:
            bytes_mb = f"{float(bytes_raw)/(1024*1024):.2f}" if bytes_raw is not None and str(bytes_raw).replace(".", "", 1).isdigit() else "<missing>"
        except Exception:
            bytes_mb = "<missing>"

        print(f"{fid:<30} | {t_class:<12} | {origin:<9} | {source:<24} | {status:<6} | {pkts:<7} | {bytes_mb}")

    print("-" * 105)
    print(f"Total Registry Entries Displayed: {len(records)} (Total in Manifest: {len(all_records)})\n")


def main():
    parser = argparse.ArgumentParser(description="Inspect dataset manifest.")
    parser.add_argument("--origin", default="all", choices=["real", "synthetic", "all"], help="Filter by data origin (default: all)")
    args = parser.parse_args()
    inspect_dataset(origin_filter=args.origin)


if __name__ == "__main__":
    main()
