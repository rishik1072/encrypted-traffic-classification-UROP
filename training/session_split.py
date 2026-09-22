"""
Session-Based Splitting and Generalization Evaluation Module.

Ensures that train and test splits strictly share zero session_id values,
evaluating cross-session generalization.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def create_session_splits(
    features_csv_path: str | Path = "data/processed/features/features_cleaned.csv",
    manifest_csv_path: str | Path = "data/dataset_manifest.csv",
    output_dir: str | Path = "data/processed/splits_session",
    train_ratio: float = 0.70,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Partitions flows by session_id."""
    feat_path = Path(features_csv_path)
    man_path = Path(manifest_csv_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(man_path, "r", encoding="utf-8") as f:
        manifest_rows = list(csv.DictReader(f))

    file_to_session = {r["file_id"]: r.get("session_id", f"sess_{r['file_id']}") for r in manifest_rows}

    with open(feat_path, "r", encoding="utf-8") as f:
        feature_rows = list(csv.DictReader(f))

    for r in feature_rows:
        r["session_id"] = file_to_session.get(r.get("file_id", ""), f"sess_{r.get('file_id')}")

    unique_sessions = sorted(list({r["session_id"] for r in feature_rows}))
    n_train = max(1, int(len(unique_sessions) * train_ratio))

    train_sessions = set(unique_sessions[:n_train])
    test_sessions = set(unique_sessions[n_train:])

    train_rows = [r for r in feature_rows if r["session_id"] in train_sessions]
    test_rows = [r for r in feature_rows if r["session_id"] in test_sessions]
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
                f.write("file_id,traffic_class,session_id\n")

    logger.info("Created Session Splits: Train=%d flows (%d sessions), Test=%d flows (%d sessions)",
                len(train_rows), len(train_sessions), len(test_rows), len(test_sessions))

    return train_rows, val_rows, test_rows


if __name__ == "__main__":
    create_session_splits()
