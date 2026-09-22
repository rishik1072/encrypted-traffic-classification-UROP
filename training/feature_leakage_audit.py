"""
Feature Leakage and Schema Audit Module.

Analyzes dataset features for:
- Correlation / association with class encoding
- Mutual Information / Information Gain
- Class-conditional distribution overlap & determinism
- Near-zero variance / constant values
- Strict ML Schema compliance (verifying metadata exclusion)

Outputs:
- results/tables/ml_feature_schema_audit.csv
- results/tables/feature_leakage_audit.csv
"""

from __future__ import annotations

import argparse
import csv
import logging
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import yaml

# Support large packet streams in flows.csv
try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2147483647)

logger = logging.getLogger(__name__)

# Forbidden metadata columns that must NEVER enter ML models
FORBIDDEN_METADATA_COLS: Set[str] = {
    "session_id",
    "file_id",
    "data_origin",
    "traffic_class",
    "environment_id",
    "device_id",
    "dataset_id",
    "metadata_path",
    "pcap_path",
    "raw_source_path",
    "capture_source",
    "capture_sequence",
    "capture_date",
    "notes",
    "source",
    "packet_timestamps_json",
    "packet_lengths_json",
    "packet_directions_json",
    "start_time",
    "last_seen",
}


class FeatureLeakageAuditor:
    """
    Evaluates features against class labels to uncover deterministic proxies,
    near-zero variance, or metadata leakage.
    """

    def __init__(self, config_path: str | Path = "config.yaml") -> None:
        self.config_path = Path(config_path)
        self.base_dir = self.config_path.parent
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config: Dict[str, Any] = yaml.safe_load(f)

        self.numerical_cols: List[str] = self.config.get("features", {}).get("numerical_features", [])
        self.categorical_cols: List[str] = self.config.get("features", {}).get("categorical_features", [])
        self.tls_cols: List[str] = self.config.get("features", {}).get("tls_features", [])
        self.intended_features: List[str] = self.numerical_cols + self.categorical_cols + self.tls_cols

        self.tables_dir = self.base_dir / "results/tables"
        self.tables_dir.mkdir(parents=True, exist_ok=True)

    def audit_features(
        self,
        features_path: Optional[str | Path] = None,
        output_schema_path: Optional[str | Path] = None,
        output_leakage_path: Optional[str | Path] = None,
    ) -> Dict[str, Any]:
        """Runs schema audit and statistical feature leakage calculations."""
        feat_file = Path(features_path) if features_path else (self.base_dir / "data/processed/features/features_real.csv")
        out_schema = Path(output_schema_path) if output_schema_path else (self.tables_dir / "ml_feature_schema_audit.csv")
        out_leak = Path(output_leakage_path) if output_leakage_path else (self.tables_dir / "feature_leakage_audit.csv")

        if not feat_file.exists():
            raise FileNotFoundError(f"Feature dataset not found at {feat_file}")

        logger.info("Auditing feature leakage and schema on %s", feat_file)
        with open(feat_file, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        if not rows:
            raise ValueError(f"No records found in {feat_file}")

        total_samples = len(rows)
        all_columns = list(rows[0].keys())

        # 1. Schema & Exclusion Audit
        schema_audit_rows = []
        for col in all_columns:
            is_forbidden = col in FORBIDDEN_METADATA_COLS or "id" in col.lower() or "path" in col.lower() or "session" in col.lower() or "file" in col.lower()
            is_intended = col in self.intended_features
            
            status = "EXCLUDED_METADATA" if is_forbidden else ("VALID_ML_FEATURE" if is_intended else "LABEL" if col == "traffic_class" else "UNEXPECTED_COLUMN")
            
            schema_audit_rows.append({
                "column_name": col,
                "feature_type": "intended_ml_feature" if is_intended else ("label" if col == "traffic_class" else "excluded_metadata"),
                "status": status,
                "leakage_risk": "CRITICAL_IF_INCLUDED" if is_forbidden else "NONE",
                "ml_inclusion_allowed": "NO" if (is_forbidden or col == "traffic_class") else "YES",
            })

        self._write_csv(out_schema, schema_audit_rows)

        # 2. Statistical Leakage & Variance Audit on Intended Features
        labels = [r["traffic_class"] for r in rows]
        class_counts = Counter(labels)
        total_n = len(labels)

        # Base Shannon Entropy of Class Distribution H(Y)
        h_y = -sum((cnt / total_n) * math.log2(cnt / total_n) for cnt in class_counts.values())

        leakage_results = []

        for feat in self.intended_features:
            values_str = [r.get(feat, "") for r in rows]
            
            # Check if numeric
            is_numeric = feat in self.numerical_cols
            
            # Calculate variance & distinct values
            unique_vals = set(values_str)
            num_unique = len(unique_vals)
            
            variance = 0.0
            is_zero_variance = (num_unique <= 1)
            is_near_zero_variance = False

            if is_numeric:
                try:
                    vals_float = [float(v) if v != "" else 0.0 for v in values_str]
                    mean_val = sum(vals_float) / total_n
                    variance = sum((v - mean_val) ** 2 for v in vals_float) / total_n
                    std_val = math.sqrt(variance)
                    if variance < 1e-6:
                        is_near_zero_variance = True
                except ValueError:
                    vals_float = []
            
            # Mutual Information I(X; Y)
            # For categorical / binned continuous:
            if is_numeric and num_unique > 10:
                # Discretize into up to 10 quantile / uniform bins for robust MI calculation
                sorted_vals = sorted(vals_float)
                bins = 10
                step = max(1, len(sorted_vals) // bins)
                thresholds = [sorted_vals[i] for i in range(step, len(sorted_vals), step)]
                
                def bin_val(v: float) -> int:
                    for idx, th in enumerate(thresholds):
                        if v <= th:
                            return idx
                    return len(thresholds)
                
                discretized = [str(bin_val(v)) for v in vals_float]
            else:
                discretized = values_str

            mi = self._calculate_mutual_information(discretized, labels, h_y)

            # Check single-value determinism: does any single value uniquely associate 100% with one class?
            val_to_classes = defaultdict(lambda: Counter())
            for val, cls in zip(values_str, labels):
                val_to_classes[val][cls] += 1

            deterministic_flags = []
            for val, cls_cnts in val_to_classes.items():
                val_total = sum(cls_cnts.values())
                # If a value occurs >= 5 times and is 100% one class
                if val_total >= 5:
                    for cls_name, count in cls_cnts.items():
                        if count == val_total:
                            deterministic_flags.append(f"Val '{val}' (n={val_total}) -> 100% {cls_name}")

            is_deterministic_proxy = len(deterministic_flags) > 0
            leakage_flag = "SUSPICIOUS_DETERMINISTIC_LEAK" if is_deterministic_proxy else ("HIGH_MI_CANDIDATE" if mi > 1.8 else "NORMAL")

            leakage_results.append({
                "feature_name": feat,
                "feature_group": "numerical" if is_numeric else ("categorical" if feat in self.categorical_cols else "tls"),
                "unique_values": num_unique,
                "variance": f"{variance:.4f}" if is_numeric else "N/A",
                "near_zero_variance": "YES" if (is_zero_variance or is_near_zero_variance) else "NO",
                "mutual_information_bits": f"{mi:.4f}",
                "max_possible_entropy": f"{h_y:.4f}",
                "deterministic_associations": "; ".join(deterministic_flags[:2]) if deterministic_flags else "None",
                "leakage_flag": leakage_flag,
            })

        # Sort by MI descending
        leakage_results.sort(key=lambda x: float(x["mutual_information_bits"]), reverse=True)
        self._write_csv(out_leak, leakage_results)

        logger.info("Saved ML feature schema audit -> %s", out_schema)
        logger.info("Saved feature leakage audit -> %s", out_leak)

        return {
            "schema_audit": schema_audit_rows,
            "leakage_audit": leakage_results,
            "class_entropy": h_y,
        }

    @staticmethod
    def _calculate_mutual_information(feature_vals: List[str], labels: List[str], h_y: float) -> float:
        """Calculates I(X; Y) = H(Y) - H(Y|X) in bits."""
        total = len(feature_vals)
        if total == 0:
            return 0.0

        val_counts = Counter(feature_vals)
        val_label_counts = defaultdict(lambda: Counter())
        for v, l in zip(feature_vals, labels):
            val_label_counts[v][l] += 1

        # Calculate conditional entropy H(Y|X) = sum_x P(x) * H(Y|X=x)
        h_y_given_x = 0.0
        for v, count_v in val_counts.items():
            p_v = count_v / total
            cls_cnts = val_label_counts[v]
            h_y_given_v = 0.0
            for cnt in cls_cnts.values():
                p_c_given_v = cnt / count_v
                if p_c_given_v > 0:
                    h_y_given_v -= p_c_given_v * math.log2(p_c_given_v)
            h_y_given_x += p_v * h_y_given_v

        mi = max(0.0, h_y - h_y_given_x)
        return mi

    @staticmethod
    def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        fieldnames = list(rows[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
    parser = argparse.ArgumentParser(description="Audit feature leakage and ML schema.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--features", default="data/processed/features/features_real.csv", help="Path to features CSV")
    args = parser.parse_args()

    auditor = FeatureLeakageAuditor(config_path=args.config)
    auditor.audit_features(features_path=args.features)


if __name__ == "__main__":
    main()
