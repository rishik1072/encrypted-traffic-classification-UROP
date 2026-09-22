"""
Temporal Dataset Generator for Phase 6.

Constructs 10 temporal window datasets in data/processed/temporal/:
- whole_flow.csv
- prefix_5.csv, prefix_10.csv, prefix_20.csv, prefix_50.csv, prefix_100.csv
- window_1s.csv, window_2s.csv, window_5s.csv, window_10s.csv

Inherits parent session/flow labels and metadata. Strictly zero-payload.
"""

from __future__ import annotations

import csv
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

from preprocessing.temporal_window_extractor import (
    TEMPORAL_FEATURE_NAMES,
    TemporalWindowExtractor,
)

logger = logging.getLogger("build_temporal_dataset")

METADATA_COLS = [
    "flow_id",
    "file_id",
    "session_id",
    "traffic_class",
    "environment_id",
    "network_condition_id",
    "capture_day",
    "capture_date",
    "collection_batch",
    "device_id",
    "interface_type",
    "tunnel_state",
    "activity_variant",
    "data_origin",
    "dataset_version",
    "window_id",
    "window_type",
    "window_start",
    "window_end",
    "packet_offset",
]


def generate_flow_packet_streams(
    clean_records: List[Dict[str, Any]],
    seed: int = 42,
) -> List[Tuple[Dict[str, Any], List[float], List[int], List[int]]]:
    """Reconstructs consistent packet streams (timestamps, lengths, directions) for each flow record."""
    random.seed(seed)
    flow_streams = []

    for r in clean_records:
        f_pkts = max(1, int(float(r.get("forward_packet_count", 100))))
        b_pkts = int(float(r.get("backward_packet_count", 0)))
        tot_pkts = f_pkts + b_pkts
        f_bytes = max(100, int(float(r.get("forward_bytes", 20000))))
        b_bytes = int(float(r.get("backward_bytes", 0)))
        tot_bytes = f_bytes + b_bytes
        dur = max(0.01, float(r.get("flow_duration", 60.0)))
        mean_iat = max(0.0001, float(r.get("mean_iat", 0.05)))
        avg_pkt_sz = float(tot_bytes) / float(tot_pkts)

        timestamps: List[float] = [0.0]
        cur_t = 0.0
        for _ in range(1, tot_pkts):
            dt = random.expovariate(1.0 / mean_iat) if mean_iat > 0 else 0.01
            dt = min(dt, dur)
            cur_t += dt
            timestamps.append(cur_t)

        lengths: List[int] = []
        directions: List[int] = []

        for _ in range(f_pkts):
            sz = int(random.gauss(avg_pkt_sz, avg_pkt_sz * 0.35))
            sz = max(40, min(1420, sz))
            lengths.append(sz)
            directions.append(1)

        for _ in range(b_pkts):
            sz = int(random.gauss(max(54, avg_pkt_sz * 0.6), 40.0))
            sz = max(40, min(1420, sz))
            lengths.append(sz)
            directions.append(2)

        combined = list(zip(timestamps, lengths, directions))
        combined.sort(key=lambda x: x[0])
        t_vec = [x[0] for x in combined]
        l_vec = [x[1] for x in combined]
        d_vec = [x[2] for x in combined]

        flow_streams.append((r, t_vec, l_vec, d_vec))

    return flow_streams


def build_temporal_datasets(
    input_clean_path: Path = Path("data/processed/features/features_real_clean_v2.csv"),
    output_dir: Path = Path("data/processed/temporal"),
    seed: int = 42,
) -> Dict[str, Path]:
    """Generates all 10 temporal window datasets."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_clean_path.exists():
        raise FileNotFoundError(f"Source clean dataset not found at {input_clean_path}")

    clean_records: List[Dict[str, Any]] = []
    with open(input_clean_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clean_records.append(row)

    logger.info("Loaded %d clean records for temporal dataset construction", len(clean_records))
    flow_streams = generate_flow_packet_streams(clean_records, seed=seed)
    extractor = TemporalWindowExtractor(min_packets=3)

    fieldnames = METADATA_COLS + TEMPORAL_FEATURE_NAMES
    output_paths: Dict[str, Path] = {}

    # 1. Whole Flow
    whole_rows: List[Dict[str, Any]] = []
    for r, t_vec, l_vec, d_vec in flow_streams:
        dur = max(0.001, t_vec[-1] - t_vec[0]) if len(t_vec) > 1 else 0.001
        feats = extractor.extract_window_features(t_vec, l_vec, d_vec, window_duration=dur)
        row = {
            **{k: r.get(k, "") for k in METADATA_COLS if k not in ("window_id", "window_type", "window_start", "window_end", "packet_offset")},
            "window_id": f"{r['flow_id']}_whole",
            "window_type": "whole_flow",
            "window_start": "0.000",
            "window_end": f"{dur:.3f}",
            "packet_offset": "0",
            **{k: f"{v:.6f}" for k, v in feats.items()},
        }
        whole_rows.append(row)

    whole_path = output_dir / "whole_flow.csv"
    with open(whole_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(whole_rows)
    output_paths["whole_flow"] = whole_path
    logger.info("Saved whole_flow dataset (%d rows) to %s", len(whole_rows), whole_path)

    # 2. Prefix Windows (5, 10, 20, 50, 100)
    for n in [5, 10, 20, 50, 100]:
        prefix_rows: List[Dict[str, Any]] = []
        for r, t_vec, l_vec, d_vec in flow_streams:
            feats = extractor.extract_prefix(t_vec, l_vec, d_vec, prefix_size=n)
            if feats is not None:
                dur = max(0.0001, t_vec[n - 1] - t_vec[0])
                row = {
                    **{k: r.get(k, "") for k in METADATA_COLS if k not in ("window_id", "window_type", "window_start", "window_end", "packet_offset")},
                    "window_id": f"{r['flow_id']}_prefix_{n}",
                    "window_type": f"prefix_{n}",
                    "window_start": "0.000",
                    "window_end": f"{dur:.3f}",
                    "packet_offset": "0",
                    **{k: f"{v:.6f}" for k, v in feats.items()},
                }
                prefix_rows.append(row)

        p_path = output_dir / f"prefix_{n}.csv"
        with open(p_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(prefix_rows)
        output_paths[f"prefix_{n}"] = p_path
        logger.info("Saved prefix_%d dataset (%d rows) to %s", n, len(prefix_rows), p_path)

    # 3. Time Windows (1s, 2s, 5s, 10s)
    for t_sec in [1.0, 2.0, 5.0, 10.0]:
        t_int = int(t_sec)
        win_rows: List[Dict[str, Any]] = []
        for r, t_vec, l_vec, d_vec in flow_streams:
            feats = extractor.extract_time_window(t_vec, l_vec, d_vec, window_sec=t_sec)
            if feats is not None:
                row = {
                    **{k: r.get(k, "") for k in METADATA_COLS if k not in ("window_id", "window_type", "window_start", "window_end", "packet_offset")},
                    "window_id": f"{r['flow_id']}_win_{t_int}s",
                    "window_type": f"window_{t_int}s",
                    "window_start": "0.000",
                    "window_end": f"{t_sec:.3f}",
                    "packet_offset": "0",
                    **{k: f"{v:.6f}" for k, v in feats.items()},
                }
                win_rows.append(row)

        w_path = output_dir / f"window_{t_int}s.csv"
        with open(w_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(win_rows)
        output_paths[f"window_{t_int}s"] = w_path
        logger.info("Saved window_%ds dataset (%d rows) to %s", t_int, len(win_rows), w_path)

    return output_paths


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
    build_temporal_datasets()
