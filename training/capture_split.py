"""
Capture-Based (File-Level Isolation) Splitting Protocol.

Guarantees that the held-out test split consists entirely of previously unseen PCAP capture files.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def create_capture_splits(
    features_csv_path: str | Path = "data/processed/features/features_cleaned.csv",
    output_dir: str | Path = "data/processed/splits_capture",
    train_ratio: float = 0.70,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Partitions flows by file_id."""
    feat_path = Path(features_csv_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(feat_path, "r", encoding="utf-8") as f:
        feature_rows = list(csv.DictReader(f))

    unique_files = sorted(list({r["file_id"] for r in feature_rows}))
    n_train = max(1, int(len(unique_files) * train_ratio))

    train_files = set(unique_files[:n_train])
    test_files = set(unique_files[n_train:])

    train_rows = [r for r in feature_rows if r["file_id"] in train_files]
    test_rows = [r for r in feature_rows if r["file_id"] in test_files]
    val_rows: List[Dict[str, Any]] = []

    for name, rows in [("train", train_rows), ("validation", val_rows), ("test", test_rows)]:
        file_p = out_dir / f"{name}.csv"
        if rows:
            with open(file_p, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
        else:
            with open(file_p, "w", newline="", encoding="utf-8") as f:
                f.write("file_id,traffic_class\n")

    logger.info("Created Capture Splits: Train=%d flows (%d captures), Test=%d flows (%d captures)",
                len(train_rows), len(train_files), len(test_rows), len(test_files))

    return train_rows, val_rows, test_rows


if __name__ == "__main__":
    create_capture_splits()
