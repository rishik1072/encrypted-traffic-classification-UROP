"""
CLI Tool: Generate Dataset V3 Collection Progress Report.

Scans data/research_v3/ and tabulates progress across:
- Traffic classes (Web, Video, Messaging, VoIP, File Transfer, Other)
- Environments (Wi-Fi, Ethernet, Cellular)
- Tunnel states (DIRECT, VPN)
- Label quality distribution

Usage:
    python scripts/research/dataset_v3/generate_collection_report.py --root data/research_v3
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research.dataset_v3.schemas import VALID_ADAPTER_TYPES, VALID_TRAFFIC_CLASSES


def generate_report(root_dir: Path) -> str:
    lines = []
    lines.append("# Dataset V3 Collection Progress Report")
    lines.append(f"**Root Directory**: `{root_dir}`\n")

    if not root_dir.exists():
        lines.append("*Dataset root directory does not exist yet. No physical sessions captured.*")
        return "\n".join(lines)

    session_dirs = [d for d in root_dir.iterdir() if d.is_dir() and (d / "session_manifest.json").exists()]
    if not session_dirs:
        lines.append("*Zero physical collection sessions found.*")
        return "\n".join(lines)

    total_sessions = len(session_dirs)
    total_packets = 0
    total_flows = 0

    # Matrix: class x adapter_type -> count of VERIFIED flows
    class_env_matrix = defaultdict(lambda: defaultdict(int))
    quality_counts = defaultdict(int)

    for s_dir in session_dirs:
        with open(s_dir / "session_manifest.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)
        total_packets += manifest.get("packet_count", 0)
        total_flows += manifest.get("flow_count", 0)
        adapter = manifest.get("adapter_type", "Unknown")

        labels_p = s_dir / "labels.csv"
        if labels_p.exists():
            with open(labels_p, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    cls = r["traffic_class"]
                    q = r["label_quality"]
                    quality_counts[q] += 1
                    if q == "VERIFIED":
                        class_env_matrix[cls][adapter] += 1

    lines.append(f"### Collection Summary")
    lines.append(f"- **Completed Sessions**: {total_sessions}")
    lines.append(f"- **Total Flow Records**: {total_flows}")
    lines.append(f"- **Total Packet Records**: {total_packets}")
    lines.append("")

    lines.append("### Verified Flow Distribution Matrix (Class vs. Environment)")
    header = "| Traffic Class | " + " | ".join(sorted(VALID_ADAPTER_TYPES)) + " | Total Verified | Target (Pilot: 50) |"
    sep = "| :--- | " + " | ".join([":---:" for _ in VALID_ADAPTER_TYPES]) + " | :---: | :---: |"
    lines.append(header)
    lines.append(sep)

    for cls in sorted(VALID_TRAFFIC_CLASSES):
        row = [f"**{cls}**"]
        cls_tot = 0
        for env in sorted(VALID_ADAPTER_TYPES):
            cnt = class_env_matrix[cls][env]
            cls_tot += cnt
            row.append(str(cnt))
        row.append(f"**{cls_tot}**")
        row.append("50 flows" if cls_tot >= 50 else f"Pending ({cls_tot}/50)")
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    lines.append("### Label Quality Breakdown")
    for q, cnt in sorted(quality_counts.items()):
        lines.append(f"- **{q}**: {cnt} flows")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Dataset V3 Collection Progress Report")
    parser.add_argument("--root", type=str, default="data/research_v3", help="Dataset root directory")
    args = parser.parse_args()
    report = generate_report(Path(args.root))
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
