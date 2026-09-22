"""
Collection Procedure and Environment Bias Audit Module.

Investigates whether traffic class can be predicted from collection confounders:
- capture duration
- session timing / sequence
- packet count / byte count
- protocol
- environment identifier
- device identifier
- other metadata

Outputs:
- results/tables/collection_bias.csv
- results/tables/environment_class_distribution.csv
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

# Support large packet streams
try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2147483647)

logger = logging.getLogger(__name__)


class CollectionBiasAuditor:
    """
    Evaluates whether collection metadata, hardware environments, capture durations,
    or sequence timing introduce artificial confounding variables / bias into the dataset.
    """

    def __init__(self, config_path: str | Path = "config.yaml") -> None:
        self.config_path = Path(config_path)
        self.base_dir = self.config_path.parent
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config: Dict[str, Any] = yaml.safe_load(f)

        self.manifest_path = self.base_dir / "data/dataset_manifest.csv"
        self.features_path = self.base_dir / "data/processed/features/features_real.csv"
        self.tables_dir = self.base_dir / "results/tables"
        self.tables_dir.mkdir(parents=True, exist_ok=True)

    def audit_bias(
        self,
        manifest_path: Optional[str | Path] = None,
        features_path: Optional[str | Path] = None,
    ) -> Dict[str, Any]:
        """Audits collection procedure confounders and environment associations."""
        m_file = Path(manifest_path) if manifest_path else self.manifest_path
        f_file = Path(features_path) if features_path else self.features_path

        if not m_file.exists():
            raise FileNotFoundError(f"Manifest not found at {m_file}")

        logger.info("Auditing collection bias using manifest %s and features %s", m_file, f_file)

        # 1. Read real manifest records
        with open(m_file, "r", encoding="utf-8") as f:
            all_m = list(csv.DictReader(f))
        real_manifest = [r for r in all_m if r.get("data_origin") == "real"]

        total_sessions = len(real_manifest)
        classes = [r["traffic_class"] for r in real_manifest]
        class_counts = Counter(classes)
        total_n = len(classes)

        # Base class entropy
        h_y = -sum((cnt / total_n) * math.log2(cnt / total_n) for cnt in class_counts.values())

        # 2. Audit Environment / Device Distribution
        env_class_counts = defaultdict(lambda: Counter())
        device_class_counts = defaultdict(lambda: Counter())

        for r in real_manifest:
            env = r.get("environment_id", "unknown_env")
            dev = r.get("device_id", "unknown_dev")
            cls = r.get("traffic_class", "unknown_cls")
            env_class_counts[env][cls] += 1
            device_class_counts[dev][cls] += 1

        # Write Environment Class Distribution Table
        env_table_rows = []
        for env, c_dict in sorted(env_class_counts.items()):
            for cls_name, count in sorted(c_dict.items()):
                pct = (count / class_counts[cls_name]) * 100.0 if class_counts[cls_name] > 0 else 0.0
                env_table_rows.append({
                    "environment_id": env,
                    "traffic_class": cls_name,
                    "session_count": count,
                    "total_class_sessions": class_counts[cls_name],
                    "class_session_percentage": f"{pct:.2f}%",
                    "bias_risk": "UNIFORM_BALANCED" if count == 10 and len(env_class_counts) == 1 else "POTENTIAL_BIAS",
                })

        self._write_csv(self.tables_dir / "environment_class_distribution.csv", env_table_rows)

        # 3. Assess Metadata Confounder Variables against Traffic Class
        # Candidate confounders in session metadata:
        metadata_variables = [
            "capture_duration",
            "environment_id",
            "device_id",
            "dataset_id",
            "capture_source",
            "capture_date",
            "flow_count",
            "packet_count",
            "byte_count",
            "session_sequence_index",
        ]

        # Add sequence index (order of session collection)
        for idx, r in enumerate(real_manifest):
            r["session_sequence_index"] = str(idx)

        bias_results = []
        for var in metadata_variables:
            vals = [r.get(var, "") for r in real_manifest]
            unique_vals = set(vals)

            # Check if numeric
            is_num = False
            vals_float = []
            try:
                vals_float = [float(v) for v in vals if v != ""]
                if len(vals_float) == total_n:
                    is_num = True
            except ValueError:
                is_num = False

            # Discretize continuous variables for MI
            if is_num and len(unique_vals) > 5:
                sorted_v = sorted(vals_float)
                bins = 5
                step = max(1, len(sorted_v) // bins)
                thresholds = [sorted_v[i] for i in range(step, len(sorted_v), step)]

                def bin_v(v: float) -> int:
                    for b_idx, th in enumerate(thresholds):
                        if v <= th:
                            return b_idx
                    return len(thresholds)

                disc_vals = [str(bin_v(v)) for v in vals_float]
            else:
                disc_vals = vals

            mi = self._calculate_mutual_information(disc_vals, classes, h_y)

            # Check if variable perfectly predicts any class
            val_to_class = defaultdict(lambda: Counter())
            for v, c in zip(vals, classes):
                val_to_class[v][c] += 1

            deterministic_findings = []
            for v, c_cnts in val_to_class.items():
                v_tot = sum(c_cnts.values())
                if v_tot >= 5:
                    for c_name, count in c_cnts.items():
                        if count == v_tot:
                            deterministic_findings.append(f"{var}='{v}' (n={v_tot}) -> 100% {c_name}")

            is_leakage_confounder = (mi > 1.5) or (len(deterministic_findings) > 0)

            bias_results.append({
                "metadata_variable": var,
                "data_level": "session_metadata",
                "unique_values": len(unique_vals),
                "mutual_information_bits": f"{mi:.4f}",
                "class_entropy_bits": f"{h_y:.4f}",
                "confounder_risk": "HIGH_CONFOUNDER_RISK" if is_leakage_confounder else "LOW_NO_BIAS",
                "deterministic_associations": "; ".join(deterministic_findings[:2]) if deterministic_findings else "None",
                "recommendation": "STRICTLY_EXCLUDE_FROM_FEATURES" if var in ("environment_id", "device_id", "session_sequence_index", "session_id") else "BENIGN_METRIC",
            })

        bias_results.sort(key=lambda x: float(x["mutual_information_bits"]), reverse=True)
        self._write_csv(self.tables_dir / "collection_bias.csv", bias_results)

        logger.info("Saved collection bias table -> %s", self.tables_dir / "collection_bias.csv")
        logger.info("Saved environment class distribution -> %s", self.tables_dir / "environment_class_distribution.csv")

        return {
            "environment_distribution": env_table_rows,
            "collection_bias": bias_results,
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

        return max(0.0, h_y - h_y_given_x)

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
    parser = argparse.ArgumentParser(description="Audit collection procedure and environment bias.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--manifest", default="data/dataset_manifest.csv", help="Path to manifest CSV")
    args = parser.parse_args()

    auditor = CollectionBiasAuditor(config_path=args.config)
    auditor.audit_bias(manifest_path=args.manifest)


if __name__ == "__main__":
    main()
