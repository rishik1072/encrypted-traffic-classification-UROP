"""
Group-Aware Train / Validation / Test Dataset Splitting.

Splits traffic flow datasets into Train (70%), Validation (15%), and Test (15%) partitions.
CRITICAL RESEARCH DESIGN: Employs Group-Aware splitting by session_id/file_id to prevent
near-duplicate session traffic leakage between training and testing splits.
Supports --origin {real, synthetic, all}.
"""

from __future__ import annotations

import argparse
import csv
import logging
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import yaml

logger = logging.getLogger(__name__)


class GroupAwareDatasetSplitter:
    """
    Partitions datasets into train, validation, and test sets using group identifiers (session_id / file_id)
    to guarantee zero intra-capture data leakage.
    """

    def __init__(self, config_path: str | Path = "config.yaml") -> None:
        self.config_path = Path(config_path)
        self.base_dir = self.config_path.parent
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config: Dict[str, Any] = yaml.safe_load(f)

        dataset_cfg = self.config.get("dataset", {})
        split_cfg = self.config.get("splitting", {})

        self.input_feature_path = self.base_dir / dataset_cfg.get(
            "cleaned_feature_output_path", "data/processed/features/features_cleaned.csv"
        )
        self.fallback_input_path = self.base_dir / dataset_cfg.get(
            "feature_output_path", "data/processed/features/features.csv"
        )
        self.split_dir = self.base_dir / dataset_cfg.get("split_directory", "data/processed/splits")

        self.train_ratio = float(split_cfg.get("train_ratio", 0.70))
        self.val_ratio = float(split_cfg.get("validation_ratio", 0.15))
        self.test_ratio = float(split_cfg.get("test_ratio", 0.15))
        self.group_col = split_cfg.get("group_column", "session_id")
        self.random_seed = int(split_cfg.get("random_seed", 42))

    def split_dataset(
        self,
        input_path: Optional[str | Path] = None,
        split_dir: Optional[str | Path] = None,
        origin_filter: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Loads feature rows, groups by session_id / file_id, and assigns entire captures
        to Train, Validation, or Test sets.
        """
        if origin_filter is None:
            origin_filter = "all" if input_path else "real"
        if input_path:
            in_file = Path(input_path)
        else:
            if origin_filter == "real":
                in_file = self.base_dir / "data/processed/features/features_real.csv"
            elif origin_filter == "synthetic":
                in_file = self.base_dir / "data/processed/features/features_synthetic.csv"
            else:
                in_file = self.input_feature_path if self.input_feature_path.exists() else self.fallback_input_path

        if split_dir:
            out_dir = Path(split_dir)
        else:
            if origin_filter == "real":
                out_dir = self.split_dir / "real"
            elif origin_filter == "synthetic":
                out_dir = self.split_dir / "synthetic"
            else:
                out_dir = self.split_dir

        out_dir.mkdir(parents=True, exist_ok=True)

        if not in_file.exists():
            raise FileNotFoundError(f"Feature dataset not found at {in_file}")

        logger.info("Reading feature rows for group-aware splitting from %s -> %s (origin=%s)", in_file, out_dir, origin_filter)
        rows: List[Dict[str, Any]] = []
        with open(in_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            logger.warning("No rows found in feature dataset %s.", in_file)
            return [], [], []

        # Enforce hard research isolation guarantee if data_origin column exists
        if origin_filter == "real":
            for r in rows:
                if "data_origin" in r and r.get("data_origin") != "real":
                    raise ValueError(f"Research integrity violation: Synthetic record '{r.get('flow_id')}' found in real dataset split!")

        # Group rows by session_id / file_id
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        group_to_class: Dict[str, str] = {}

        for r in rows:
            g_val = r.get(self.group_col) or r.get("session_id") or r.get("file_id", "default_group")
            groups[g_val].append(r)
            if g_val not in group_to_class:
                group_to_class[g_val] = r.get("traffic_class", "Unknown")

        rng = random.Random(self.random_seed)

        # Stratified allocation of groups by traffic class
        class_to_groups: Dict[str, List[str]] = defaultdict(list)
        for g_val, cls_name in group_to_class.items():
            class_to_groups[cls_name].append(g_val)

        train_groups: Set[str] = set()
        val_groups: Set[str] = set()
        test_groups: Set[str] = set()

        for cls_name, grp_list in class_to_groups.items():
            shuffled = list(grp_list)
            rng.shuffle(shuffled)
            n = len(shuffled)

            if n == 1:
                train_groups.add(shuffled[0])
            elif n == 2:
                train_groups.add(shuffled[0])
                test_groups.add(shuffled[1])
            else:
                n_train = max(1, int(round(n * self.train_ratio)))
                n_val = max(1, int(round(n * self.val_ratio))) if n >= 3 else 0
                if n_train + n_val >= n:
                    n_train = n - 2
                    n_val = 1

                tr = shuffled[:n_train]
                va = shuffled[n_train : n_train + n_val]
                te = shuffled[n_train + n_val :]

                train_groups.update(tr)
                val_groups.update(va)
                test_groups.update(te)

        # Build final row splits
        train_rows = [r for r in rows if (r.get(self.group_col) or r.get("session_id") or r.get("file_id")) in train_groups]
        val_rows = [r for r in rows if (r.get(self.group_col) or r.get("session_id") or r.get("file_id")) in val_groups]
        test_rows = [r for r in rows if (r.get(self.group_col) or r.get("session_id") or r.get("file_id")) in test_groups]

        # Verify zero group leakage
        assert train_groups.isdisjoint(val_groups), "Data Leakage: Train and Validation share groups!"
        assert train_groups.isdisjoint(test_groups), "Data Leakage: Train and Test share groups!"
        assert val_groups.isdisjoint(test_groups), "Data Leakage: Validation and Test share groups!"

        # Save to disk
        fieldnames = list(rows[0].keys())
        self._write_split_csv(out_dir / "train.csv", train_rows, fieldnames)
        self._write_split_csv(out_dir / "validation.csv", val_rows, fieldnames)
        self._write_split_csv(out_dir / "test.csv", test_rows, fieldnames)

        logger.info(
            "Group-aware split complete (Seed=%d, Origin=%s):\n"
            "  Train: %d flows (%d groups)\n"
            "  Validation: %d flows (%d groups)\n"
            "  Test: %d flows (%d groups)",
            self.random_seed,
            origin_filter,
            len(train_rows),
            len(train_groups),
            len(val_rows),
            len(val_groups),
            len(test_rows),
            len(test_groups),
        )

        return train_rows, val_rows, test_rows

    @staticmethod
    def _write_split_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            if rows:
                writer.writerows(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
    parser = argparse.ArgumentParser(description="Create leakage-free group-aware train/val/test splits.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--input", default=None, help="Path to features CSV")
    parser.add_argument("--output-dir", default=None, help="Directory to save splits")
    parser.add_argument("--origin", default="real", choices=["real", "synthetic", "all"], help="Dataset origin filter (default: real)")
    args = parser.parse_args()

    splitter = GroupAwareDatasetSplitter(config_path=args.config)
    splitter.split_dataset(
        input_path=args.input,
        split_dir=args.output_dir,
        origin_filter=args.origin,
    )


if __name__ == "__main__":
    main()
