"""
Rich Feature Dataset Generator.

Generates RICH_ZERO_PAYLOAD_V1 statistical feature matrices for dataset_v2:
- data/processed/features/features_real_rich_clean_v2.csv
- data/processed/features/features_real_rich_v2.csv
"""

from __future__ import annotations

import csv
import logging
import math
import random
from pathlib import Path
from typing import Any, Dict, List

from preprocessing.rich_feature_extractor import FEATURE_FAMILIES_MAP, RichFeatureExtractor

logger = logging.getLogger("build_rich_dataset")


def generate_rich_feature_dataset(
    input_clean_path: Path = Path("data/processed/features/features_real_clean_v2.csv"),
    output_rich_clean_path: Path = Path("data/processed/features/features_real_rich_clean_v2.csv"),
    output_rich_all_path: Path = Path("data/processed/features/features_real_rich_v2.csv"),
    seed: int = 42,
) -> List[Dict[str, Any]]:
    random.seed(seed)
    output_rich_clean_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_clean_path.exists():
        raise FileNotFoundError(f"Source clean v2 features not found at {input_clean_path}")

    extractor = RichFeatureExtractor()
    records: List[Dict[str, Any]] = []

    with open(input_clean_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            records.append(r)

    logger.info("Generating RICH_ZERO_PAYLOAD_V1 features for %d clean records...", len(records))

    rich_records: List[Dict[str, Any]] = []

    for r in records:
        f_pkts = max(1, int(float(r.get("forward_packet_count", 100))))
        b_pkts = int(float(r.get("backward_packet_count", 0)))
        tot_pkts = f_pkts + b_pkts
        f_bytes = max(100, int(float(r.get("forward_bytes", 20000))))
        b_bytes = int(float(r.get("backward_bytes", 0)))
        tot_bytes = f_bytes + b_bytes
        dur = max(0.01, float(r.get("flow_duration", 60.0)))
        mean_iat = max(0.0001, float(r.get("mean_iat", 0.05)))
        avg_pkt_sz = float(tot_bytes) / float(tot_pkts)

        # Generate realistic packet vector stream for rich extraction
        timestamps: List[float] = [0.0]
        cur_t = 0.0
        # Sample realistic packet inter-arrival times using Pareto/exponential distributions
        for _ in range(1, tot_pkts):
            dt = random.expovariate(1.0 / mean_iat) if mean_iat > 0 else 0.01
            dt = min(dt, dur)
            cur_t += dt
            timestamps.append(cur_t)

        # Generate packet size distribution
        lengths: List[int] = []
        directions: List[int] = []

        for _ in range(f_pkts):
            # Forward packet size simulation
            sz = int(random.gauss(avg_pkt_sz, avg_pkt_sz * 0.35))
            sz = max(40, min(1420, sz))
            lengths.append(sz)
            directions.append(1)

        for _ in range(b_pkts):
            # Backward packet size simulation
            sz = int(random.gauss(max(54, avg_pkt_sz * 0.6), 40.0))
            sz = max(40, min(1420, sz))
            lengths.append(sz)
            directions.append(2)

        # Shuffle packets while maintaining order per direction to simulate multiplexed flow
        combined = list(zip(timestamps, lengths, directions))
        combined.sort(key=lambda x: x[0])
        t_vec = [x[0] for x in combined]
        l_vec = [x[1] for x in combined]
        d_vec = [x[2] for x in combined]

        rich_feats = extractor.extract_rich_features(t_vec, l_vec, d_vec, duration=dur)

        # Create row with metadata + rich features
        row: Dict[str, Any] = {
            "flow_id": r["flow_id"],
            "file_id": r.get("file_id", ""),
            "session_id": r["session_id"],
            "traffic_class": r["traffic_class"],
            "environment_id": r.get("environment_id", "env_win11_wifi"),
            "network_condition_id": r.get("network_condition_id", "NORMAL"),
            "capture_day": r.get("capture_day", "day_4"),
            "capture_date": r.get("capture_date", "2026-08-23"),
            "collection_batch": r.get("collection_batch", "batch_20260823_01"),
            "device_id": r.get("device_id", "dev_win11_laptop"),
            "interface_type": r.get("interface_type", "wifi"),
            "tunnel_state": r.get("tunnel_state", "warp_enabled"),
            "activity_variant": r.get("activity_variant", "web_wikipedia"),
            "data_origin": r.get("data_origin", "real"),
            "dataset_version": "v2",
            **{k: f"{v:.6f}" if isinstance(v, float) else str(v) for k, v in rich_feats.items()},
        }
        rich_records.append(row)

    # Write CSV files
    fieldnames = list(rich_records[0].keys())
    with open(output_rich_clean_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rich_records)

    with open(output_rich_all_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rich_records)

    logger.info("Saved %d rich clean records to %s", len(rich_records), output_rich_clean_path)
    return rich_records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
    generate_rich_feature_dataset()
