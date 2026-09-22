"""
Sequential Subflow Dataset Generator for Phase 7.

Generates window-level and sequence-aggregated datasets in data/processed/sequential/:
- sequential_windows_1s_0.5s.csv (1s window, 0.5s stride)
- sequential_windows_2s_1s.csv (2s window, 1.0s stride)
- sequential_windows_5s_2s.csv (5s window, 2.0s stride)
- sequential_aggregated_2s_1s.csv (Full sequence-level flow aggregation)
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from preprocessing.sequential_feature_extractor import (
    WINDOW_BASE_FEATURES,
    SequentialFeatureExtractor,
)
from training.build_temporal_dataset import generate_flow_packet_streams

logger = logging.getLogger("build_sequential_dataset")

WINDOW_METADATA_COLS = [
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
    "window_index",
    "window_start",
    "window_end",
]

SEQUENCE_METADATA_COLS = [
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
    "sequence_length",
    "flow_duration",
]


def build_sequential_datasets(
    input_clean_path: Path = Path("data/processed/features/features_real_clean_v2.csv"),
    output_dir: Path = Path("data/processed/sequential"),
    seed: int = 42,
) -> Dict[str, Path]:
    """Builds multi-scale window-level and sequence-aggregated datasets."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_clean_path.exists():
        raise FileNotFoundError(f"Source clean dataset not found at {input_clean_path}")

    clean_records: List[Dict[str, Any]] = []
    with open(input_clean_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clean_records.append(row)

    logger.info("Loaded %d clean records for sequential dataset generation", len(clean_records))
    flow_streams = generate_flow_packet_streams(clean_records, seed=seed)
    extractor = SequentialFeatureExtractor(min_packets=2)

    output_paths: Dict[str, Path] = {}

    # Window configurations
    win_configs = [
        (1.0, 0.5, "1s_0.5s"),
        (2.0, 1.0, "2s_1s"),
        (5.0, 2.0, "5s_2s"),
    ]

    for win_sec, stride_sec, name_tag in win_configs:
        window_rows: List[Dict[str, Any]] = []
        for r, t_vec, l_vec, d_vec in flow_streams:
            sub_windows = extractor.generate_sequential_windows(
                t_vec, l_vec, d_vec, window_sec=win_sec, stride_sec=stride_sec, max_windows=20
            )
            for w_idx, (w_start, w_end, feats) in enumerate(sub_windows):
                row = {
                    **{k: r.get(k, "") for k in WINDOW_METADATA_COLS if k not in ("window_id", "window_index", "window_start", "window_end")},
                    "window_id": f"{r['flow_id']}_w{w_idx:03d}",
                    "window_index": str(w_idx),
                    "window_start": f"{w_start:.3f}",
                    "window_end": f"{w_end:.3f}",
                    **{k: f"{v:.6f}" for k, v in feats.items()},
                }
                window_rows.append(row)

        w_csv = output_dir / f"sequential_windows_{name_tag}.csv"
        fieldnames = WINDOW_METADATA_COLS + WINDOW_BASE_FEATURES
        with open(w_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(window_rows)
        output_paths[f"windows_{name_tag}"] = w_csv
        logger.info("Saved %d subflow windows to %s", len(window_rows), w_csv)

    # Sequence-aggregated dataset (using 2s/1s base windows)
    seq_rows: List[Dict[str, Any]] = []
    for r, t_vec, l_vec, d_vec in flow_streams:
        sub_windows = extractor.generate_sequential_windows(
            t_vec, l_vec, d_vec, window_sec=2.0, stride_sec=1.0, max_windows=30
        )
        feat_list = [w[2] for w in sub_windows]
        agg_feats = extractor.aggregate_sequence_features(feat_list)
        dur = max(0.01, t_vec[-1] - t_vec[0]) if len(t_vec) > 1 else 0.01

        row = {
            **{k: r.get(k, "") for k in SEQUENCE_METADATA_COLS if k not in ("sequence_length", "flow_duration")},
            "sequence_length": str(len(sub_windows)),
            "flow_duration": f"{dur:.3f}",
            **{k: f"{v:.6f}" for k, v in agg_feats.items()},
        }
        seq_rows.append(row)

    seq_csv = output_dir / "sequential_aggregated_2s_1s.csv"
    seq_fieldnames = SEQUENCE_METADATA_COLS + list(agg_feats.keys())
    with open(seq_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=seq_fieldnames)
        writer.writeheader()
        writer.writerows(seq_rows)
    output_paths["aggregated_2s_1s"] = seq_csv
    logger.info("Saved %d sequence-aggregated flows (193 features) to %s", len(seq_rows), seq_csv)

    return output_paths


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
    build_sequential_datasets()
