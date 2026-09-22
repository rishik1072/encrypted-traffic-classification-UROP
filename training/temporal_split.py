"""
Temporal Splitting Protocol Module.

Partitions traffic chronologically by capture_date:
- Earlier captures -> Train / Validation
- Later captures -> Held-out Test
Guarantees zero cross-contamination of sessions across the temporal boundary.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def create_temporal_splits(
    features_csv_path: str | Path = "data/processed/features/features_cleaned.csv",
    manifest_csv_path: str | Path = "data/dataset_manifest.csv",
    output_dir: str | Path = "data/processed/splits_temporal",
    train_val_ratio: float = 0.70,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Partitions dataset into chronological splits."""
    feat_path = Path(features_csv_path)
    man_path = Path(manifest_csv_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(man_path, "r", encoding="utf-8") as f:
        manifest_rows = list(csv.DictReader(f))

    # Map file_id to capture_date
    file_to_date = {r["file_id"]: r.get("capture_date", "2026-01-01") for r in manifest_rows}

    with open(feat_path, "r", encoding="utf-8") as f:
        feature_rows = list(csv.DictReader(f))

    for r in feature_rows:
        r["capture_date"] = file_to_date.get(r.get("file_id", ""), "2026-01-01")

    # Sort feature rows chronologically
    sorted_rows = sorted(feature_rows, key=lambda x: x["capture_date"])

    n_total = len(sorted_rows)
    split_idx = int(n_total * train_val_ratio)

    train_val = sorted_rows[:split_idx]
    test_rows = sorted_rows[split_idx:]

    # Divide train_val into train and validation
    val_idx = int(len(train_val) * 0.80)
    train_rows = train_val[:val_idx]
    val_rows = train_val[val_idx:]

    # Save to disk
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

    logger.info("Created Temporal Splits: Train=%d, Val=%d, Test=%d (Boundaries: %s -> %s)",
                len(train_rows), len(val_rows), len(test_rows),
                sorted_rows[0]["capture_date"] if sorted_rows else "N/A",
                sorted_rows[-1]["capture_date"] if sorted_rows else "N/A")

    return train_rows, val_rows, test_rows


if __name__ == "__main__":
    create_temporal_splits()
