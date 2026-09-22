"""
Dataset Cleaning and Data Quality Assurance Module.

Detects and resolves missing values, duplicates, infinite numbers, invalid types,
and inconsistent traffic labels. Produces results/tables/dataset_cleaning_report.csv.
"""

from __future__ import annotations

import argparse
import csv
import logging
import math
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import yaml

logger = logging.getLogger(__name__)


class DatasetCleaner:
    """
    Cleans raw tabular feature datasets and produces an audit report of dropped/fixed rows.
    """

    def __init__(self, config_path: str | Path = "config.yaml") -> None:
        self.config_path = Path(config_path)
        self.base_dir = self.config_path.parent
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config: Dict[str, Any] = yaml.safe_load(f)

        dataset_cfg = self.config.get("dataset", {})
        self.raw_feature_path = self.base_dir / dataset_cfg.get(
            "feature_output_path", "data/processed/features/features.csv"
        )
        self.clean_feature_path = self.base_dir / dataset_cfg.get(
            "cleaned_feature_output_path", "data/processed/features/features_cleaned.csv"
        )
        self.report_path = self.base_dir / dataset_cfg.get(
            "cleaning_report_path", "results/tables/dataset_cleaning_report.csv"
        )
        self.traffic_classes: Set[str] = set(self.config.get("traffic_classes", []))
        self.numerical_cols: List[str] = self.config.get("features", {}).get("numerical_features", [])

    def clean_dataset(
        self,
        input_path: Optional[str | Path] = None,
        output_path: Optional[str | Path] = None,
        report_path: Optional[str | Path] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Cleans dataset and writes cleaned feature file and cleaning report."""
        in_file = Path(input_path) if input_path else self.raw_feature_path
        out_file = Path(output_path) if output_path else self.clean_feature_path
        rep_file = Path(report_path) if report_path else self.report_path

        out_file.parent.mkdir(parents=True, exist_ok=True)
        rep_file.parent.mkdir(parents=True, exist_ok=True)

        if not in_file.exists():
            raise FileNotFoundError(f"Feature dataset not found at {in_file}")

        logger.info("Cleaning feature dataset from %s", in_file)
        rows: List[Dict[str, Any]] = []
        with open(in_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total_flows = len(rows)
        duplicate_flows = 0
        missing_value_rows = 0
        invalid_value_rows = 0
        removed_flows = 0

        seen_signatures: Set[str] = set()
        clean_rows: List[Dict[str, Any]] = []
        class_counts: Counter[str] = Counter()

        for row in rows:
            is_valid = True
            reasons = []

            # 1. Label Validation
            label = row.get("traffic_class", "").strip()
            if not label or label not in self.traffic_classes:
                is_valid = False
                reasons.append("invalid_label")
                invalid_value_rows += 1

            # 2. Duplicate Flow Identification (based on feature signature)
            # Create a signature excluding flow_id
            sig_items = [f"{k}:{row[k]}" for k in sorted(row.keys()) if k not in ("flow_id", "file_id")]
            sig = "|".join(sig_items)
            if sig in seen_signatures:
                duplicate_flows += 1
                is_valid = False
                reasons.append("duplicate")
            else:
                seen_signatures.add(sig)

            # 3. Numeric and Infinite Value Checks
            has_missing = False
            has_invalid_num = False
            cleaned_row = dict(row)

            for col in self.numerical_cols:
                val_str = row.get(col, "")
                if val_str is None or val_str == "":
                    has_missing = True
                    # Impute default 0.0 for missing
                    cleaned_row[col] = "0.0"
                else:
                    try:
                        val = float(val_str)
                        if math.isnan(val) or math.isinf(val):
                            has_invalid_num = True
                            cleaned_row[col] = "0.0"
                    except (ValueError, TypeError):
                        has_invalid_num = True
                        cleaned_row[col] = "0.0"

            if has_missing:
                missing_value_rows += 1
            if has_invalid_num:
                invalid_value_rows += 1

            # Decision: Keep if valid label and not an exact duplicate
            if is_valid:
                clean_rows.append(cleaned_row)
                class_counts[label] += 1
            else:
                removed_flows += 1

        # Write Cleaned Dataset
        if clean_rows:
            fieldnames = list(clean_rows[0].keys())
            with open(out_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(clean_rows)

        # Write Cleaning Report
        report_data = [
            {"metric": "total_flows", "value": total_flows},
            {"metric": "valid_flows", "value": len(clean_rows)},
            {"metric": "removed_flows", "value": removed_flows},
            {"metric": "duplicate_flows", "value": duplicate_flows},
            {"metric": "missing_value_rows", "value": missing_value_rows},
            {"metric": "invalid_value_rows", "value": invalid_value_rows},
        ]
        for cls_name in sorted(self.traffic_classes):
            report_data.append(
                {"metric": f"class_count_{cls_name}", "value": class_counts.get(cls_name, 0)}
            )

        with open(rep_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["metric", "value"])
            writer.writeheader()
            writer.writerows(report_data)

        logger.info(
            "Dataset cleaned: %d valid flows saved to %s (Report: %s)",
            len(clean_rows),
            out_file,
            rep_file,
        )

        metrics_dict = {r["metric"]: r["value"] for r in report_data}
        return clean_rows, metrics_dict


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean feature dataset and generate quality report.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--input", default=None, help="Path to raw features.csv")
    parser.add_argument("--output", default=None, help="Path to cleaned features.csv")
    parser.add_argument("--report", default=None, help="Path to cleaning report CSV")
    args = parser.parse_args()

    cleaner = DatasetCleaner(config_path=args.config)
    cleaner.clean_dataset(
        input_path=args.input,
        output_path=args.output,
        report_path=args.report,
    )


if __name__ == "__main__":
    main()
