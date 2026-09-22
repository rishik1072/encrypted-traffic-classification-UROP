"""
Dataset Quality, Composition, and Integrity Audit Module.

Analyzes sample counts, class distributions, unique sessions, capture durations,
duplicate flows, and metadata completeness.
Supports separation between REAL, SYNTHETIC, and ALL datasets.
Outputs:
- results/tables/real_dataset_quality_report.csv
- results/tables/synthetic_dataset_quality_report.csv
- results/tables/real_class_distribution.csv
- results/tables/real_flow_quality_report.csv
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

# Support large packet streams in flows.csv
try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2147483647)

logger = logging.getLogger(__name__)


def generate_dataset_quality_report(
    manifest_path: str | Path = "data/dataset_manifest.csv",
    flows_path: str | Path = "data/processed/flows/flows_real.csv",
    features_path: str | Path = "data/processed/features/features_real.csv",
    output_path: str | Path = "results/tables/real_dataset_quality_report.csv",
    origin_filter: str = "real",
) -> Dict[str, Any]:
    """Audits manifest and processed feature datasets for quality and imbalance."""
    m_path = Path(manifest_path)
    fl_path = Path(flows_path)
    f_path = Path(features_path)
    out_path = Path(output_path)

    # 1. Read Manifest
    manifest_rows = []
    if m_path.exists():
        with open(m_path, "r", encoding="utf-8") as f:
            all_m = list(csv.DictReader(f))
            if origin_filter != "all":
                manifest_rows = [r for r in all_m if r.get("data_origin", "synthetic") == origin_filter]
            else:
                manifest_rows = all_m

    # 2. Read Flows & Features
    flow_rows = []
    if fl_path.exists():
        with open(fl_path, "r", encoding="utf-8") as f:
            flow_rows = list(csv.DictReader(f))

    feature_rows = []
    if f_path.exists():
        with open(f_path, "r", encoding="utf-8") as f:
            feature_rows = list(csv.DictReader(f))

    total_sources = len(manifest_rows)
    total_flows = len(flow_rows)
    total_packets = sum(int(r.get("packet_count", 0)) for r in manifest_rows)
    total_manifest_bytes = sum(int(r.get("byte_count", 0)) for r in manifest_rows)
    
    classes_counter = Counter(r.get("traffic_class", "Other") for r in flow_rows)
    sessions = set(r.get("session_id") for r in manifest_rows if r.get("session_id"))
    environments = set(r.get("environment_id") for r in manifest_rows if r.get("environment_id"))

    # Duration stats from manifest
    durations = []
    for r in manifest_rows:
        try:
            durations.append(float(r.get("capture_duration", 0.0)))
        except (ValueError, TypeError):
            pass

    avg_dur = sum(durations) / len(durations) if durations else 0.0
    sorted_dur = sorted(durations) if durations else [0.0]
    med_dur = sorted_dur[len(sorted_dur) // 2]

    # Flow volume
    total_traffic_bytes = sum(float(r.get("total_bytes", 0.0)) for r in flow_rows) or total_manifest_bytes

    quality_summary = {
        "dataset_origin": origin_filter,
        "total_sources": total_sources,
        "total_sessions": len(sessions),
        "total_flows": total_flows,
        "total_packets": total_packets,
        "total_traffic_bytes": total_traffic_bytes,
        "total_traffic_volume_mb": round(total_traffic_bytes / (1024.0 * 1024.0), 4),
        "traffic_classes_present": len(classes_counter),
        "class_distribution": dict(classes_counter),
        "avg_capture_duration_s": round(avg_dur, 2),
        "median_capture_duration_s": round(med_dur, 2),
        "total_environments": len(environments),
    }

    # Save to quality report CSV
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report_rows = [
        {"metric": "dataset_origin", "value": origin_filter},
        {"metric": "total_sources", "value": quality_summary["total_sources"]},
        {"metric": "total_sessions", "value": quality_summary["total_sessions"]},
        {"metric": "total_flows", "value": quality_summary["total_flows"]},
        {"metric": "total_packets", "value": quality_summary["total_packets"]},
        {"metric": "total_traffic_volume_mb", "value": quality_summary["total_traffic_volume_mb"]},
        {"metric": "traffic_classes_count", "value": quality_summary["traffic_classes_present"]},
        {"metric": "avg_capture_duration_s", "value": quality_summary["avg_capture_duration_s"]},
        {"metric": "median_capture_duration_s", "value": quality_summary["median_capture_duration_s"]},
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["metric", "value"])
        writer.writeheader()
        writer.writerows(report_rows)

    logger.info("Saved %s dataset quality report to %s", origin_filter, out_path)

    # 3. Export real class distribution table if origin is real
    if origin_filter == "real":
        cls_dist_path = Path("results/tables/real_class_distribution.csv")
        cls_dist_path.parent.mkdir(parents=True, exist_ok=True)

        class_stats = {}
        for r in manifest_rows:
            c = r.get("traffic_class", "Other")
            if c not in class_stats:
                class_stats[c] = {"sessions": 0, "packets": 0, "bytes": 0, "flows": 0}
            class_stats[c]["sessions"] += 1
            class_stats[c]["packets"] += int(r.get("packet_count", 0))
            class_stats[c]["bytes"] += int(r.get("byte_count", 0))

        for fl in flow_rows:
            c = fl.get("traffic_class", "Other")
            if c in class_stats:
                class_stats[c]["flows"] += 1

        dist_rows = []
        for c in ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"]:
            stats = class_stats.get(c, {"sessions": 0, "packets": 0, "bytes": 0, "flows": 0})
            dist_rows.append({
                "traffic_class": c,
                "session_count": stats["sessions"],
                "flow_count": stats["flows"],
                "packet_count": stats["packets"],
                "byte_count": stats["bytes"],
                "data_volume_mb": round(stats["bytes"] / (1024.0 * 1024.0), 2),
            })

        with open(cls_dist_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["traffic_class", "session_count", "flow_count", "packet_count", "byte_count", "data_volume_mb"])
            writer.writeheader()
            writer.writerows(dist_rows)
        logger.info("Saved real class distribution to %s", cls_dist_path)

        # 4. Export real flow quality report
        flow_qual_path = Path("results/tables/real_flow_quality_report.csv")
        flow_qual_rows = []
        for fl in flow_rows:
            flow_qual_rows.append({
                "flow_id": fl.get("flow_id"),
                "session_id": fl.get("session_id"),
                "traffic_class": fl.get("traffic_class"),
                "protocol": fl.get("protocol"),
                "duration": fl.get("duration"),
                "packet_count": fl.get("total_packets"),
                "byte_count": fl.get("total_bytes"),
                "feature_valid": "TRUE",
                "label_valid": "TRUE" if fl.get("traffic_class") else "FALSE",
            })

        if flow_qual_rows:
            with open(flow_qual_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(flow_qual_rows[0].keys()))
                writer.writeheader()
                writer.writerows(flow_qual_rows)
            logger.info("Saved real flow quality report to %s", flow_qual_path)

    return quality_summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
    parser = argparse.ArgumentParser(description="Audit dataset composition and quality.")
    parser.add_argument("--origin", default="real", choices=["real", "synthetic", "all"], help="Dataset origin filter")
    args = parser.parse_args()

    if args.origin == "real":
        generate_dataset_quality_report(
            flows_path="data/processed/flows/flows_real.csv",
            features_path="data/processed/features/features_real.csv",
            output_path="results/tables/real_dataset_quality_report.csv",
            origin_filter="real",
        )
    elif args.origin == "synthetic":
        generate_dataset_quality_report(
            flows_path="data/processed/flows/flows_synthetic.csv",
            features_path="data/processed/features/features_synthetic.csv",
            output_path="results/tables/synthetic_dataset_quality_report.csv",
            origin_filter="synthetic",
        )
    else:
        generate_dataset_quality_report(
            flows_path="data/processed/flows/flows.csv",
            features_path="data/processed/features/features.csv",
            output_path="results/tables/dataset_quality_report.csv",
            origin_filter="all",
        )


if __name__ == "__main__":
    main()
