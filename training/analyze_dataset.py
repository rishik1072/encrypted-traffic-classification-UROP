"""
Dataset Balance and Statistical Analysis Module.

Analyzes traffic class balance, packet/byte distributions, and flow durations.
Generates CSV tables in results/tables/ and visual distribution plots in results/figures/.
"""

from __future__ import annotations

import argparse
import csv
import logging
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

logger = logging.getLogger(__name__)


class DatasetAnalyzer:
    """
    Computes class balance, duration, packet, and byte statistics,
    and produces CSV summary tables and visual distribution charts.
    """

    def __init__(self, config_path: str | Path = "config.yaml") -> None:
        self.config_path = Path(config_path)
        self.base_dir = self.config_path.parent
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config: Dict[str, Any] = yaml.safe_load(f)

        dataset_cfg = self.config.get("dataset", {})
        self.input_feature_path = self.base_dir / dataset_cfg.get(
            "cleaned_feature_output_path", "data/processed/features/features_cleaned.csv"
        )
        self.fallback_path = self.base_dir / dataset_cfg.get(
            "feature_output_path", "data/processed/features/features.csv"
        )
        self.class_dist_path = self.base_dir / dataset_cfg.get(
            "class_distribution_path", "results/tables/class_distribution.csv"
        )
        self.feat_stats_path = self.base_dir / dataset_cfg.get(
            "feature_statistics_path", "results/tables/feature_statistics.csv"
        )
        self.figures_dir = self.base_dir / dataset_cfg.get(
            "figures_directory", "results/figures"
        )

    def analyze(
        self,
        input_path: Optional[str | Path] = None,
        save_plots: bool = True,
    ) -> Dict[str, Any]:
        """Runs dataset profiling, writes tables and figures."""
        in_file = Path(input_path) if input_path else (
            self.input_feature_path if self.input_feature_path.exists() else self.fallback_path
        )
        self.class_dist_path.parent.mkdir(parents=True, exist_ok=True)
        self.figures_dir.mkdir(parents=True, exist_ok=True)

        if not in_file.exists():
            raise FileNotFoundError(f"Feature dataset not found at {in_file}")

        logger.info("Analyzing dataset from %s", in_file)
        rows: List[Dict[str, Any]] = []
        with open(in_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            logger.warning("Empty dataset. Skipping analysis.")
            return {}

        total_flows = len(rows)

        # 1. Class-wise statistics
        class_flows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in rows:
            cls_name = r.get("traffic_class", "Unknown")
            class_flows[cls_name].append(r)

        class_dist_rows = []
        for cls_name, flow_list in class_flows.items():
            durations = [float(r["flow_duration"]) for r in flow_list if "flow_duration" in r]
            packets = [float(r["total_packet_count"]) for r in flow_list if "total_packet_count" in r]
            bytes_list = [float(r["total_bytes"]) for r in flow_list if "total_bytes" in r]

            count = len(flow_list)
            pct = (count / total_flows) * 100.0
            avg_dur = sum(durations) / len(durations) if durations else 0.0
            avg_pkts = sum(packets) / len(packets) if packets else 0.0
            avg_bytes = sum(bytes_list) / len(bytes_list) if bytes_list else 0.0

            class_dist_rows.append({
                "traffic_class": cls_name,
                "flow_count": count,
                "percentage": round(pct, 2),
                "avg_duration_seconds": round(avg_dur, 4),
                "avg_packet_count": round(avg_pkts, 2),
                "avg_total_bytes": round(avg_bytes, 2),
            })

        # Save class distribution table
        with open(self.class_dist_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "traffic_class",
                    "flow_count",
                    "percentage",
                    "avg_duration_seconds",
                    "avg_packet_count",
                    "avg_total_bytes",
                ],
            )
            writer.writeheader()
            writer.writerows(class_dist_rows)

        # 2. Overall Numerical Feature Statistics
        num_cols = self.config.get("features", {}).get("numerical_features", [])
        feat_stats_rows = []
        for col in num_cols:
            vals = []
            for r in rows:
                v_str = r.get(col, "")
                try:
                    vals.append(float(v_str))
                except (ValueError, TypeError):
                    pass
            if vals:
                mean_v = sum(vals) / len(vals)
                min_v = min(vals)
                max_v = max(vals)
                variance_v = sum((x - mean_v) ** 2 for x in vals) / len(vals)
                std_v = math.sqrt(variance_v)
                sorted_v = sorted(vals)
                median_v = sorted_v[len(sorted_v) // 2]

                feat_stats_rows.append({
                    "feature_name": col,
                    "count": len(vals),
                    "mean": round(mean_v, 4),
                    "std": round(std_v, 4),
                    "min": round(min_v, 4),
                    "median": round(median_v, 4),
                    "max": round(max_v, 4),
                })

        with open(self.feat_stats_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["feature_name", "count", "mean", "std", "min", "median", "max"],
            )
            writer.writeheader()
            writer.writerows(feat_stats_rows)

        # 3. Generate Visual Distribution Charts (Matplotlib / Fallback)
        if save_plots:
            self._generate_plots(rows, class_dist_rows)

        logger.info(
            "Analysis complete. Tables saved to %s and %s",
            self.class_dist_path,
            self.feat_stats_path,
        )

        return {
            "total_flows": total_flows,
            "class_distribution": class_dist_rows,
            "feature_statistics": feat_stats_rows,
        }

    def _generate_plots(self, rows: List[Dict[str, Any]], class_dist: List[Dict[str, Any]]) -> None:
        """Renders and saves figure artifacts."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            # 1. Class Distribution Bar Chart
            classes = [d["traffic_class"] for d in class_dist]
            counts = [d["flow_count"] for d in class_dist]

            plt.figure(figsize=(8, 4.5))
            plt.bar(classes, counts, color="#2b5c8f", edgecolor="black", alpha=0.85)
            plt.title("Traffic Class Distribution")
            plt.xlabel("Traffic Class")
            plt.ylabel("Number of Flows")
            plt.grid(axis="y", linestyle="--", alpha=0.7)
            plt.tight_layout()
            plt.savefig(self.figures_dir / "class_distribution.png", dpi=150)
            plt.close()

            # 2. Flow Duration Distribution
            durations = [float(r["flow_duration"]) for r in rows if "flow_duration" in r]
            plt.figure(figsize=(8, 4.5))
            plt.hist(durations, bins=20, color="#2ca02c", edgecolor="black", alpha=0.75)
            plt.title("Flow Duration Distribution (Seconds)")
            plt.xlabel("Duration (s)")
            plt.ylabel("Flow Frequency")
            plt.grid(axis="y", linestyle="--", alpha=0.7)
            plt.tight_layout()
            plt.savefig(self.figures_dir / "flow_duration_distribution.png", dpi=150)
            plt.close()

            # 3. Packets Per Flow
            packets = [float(r["total_packet_count"]) for r in rows if "total_packet_count" in r]
            plt.figure(figsize=(8, 4.5))
            plt.hist(packets, bins=20, color="#d62728", edgecolor="black", alpha=0.75)
            plt.title("Packets Per Flow Distribution")
            plt.xlabel("Total Packets")
            plt.ylabel("Flow Frequency")
            plt.grid(axis="y", linestyle="--", alpha=0.7)
            plt.tight_layout()
            plt.savefig(self.figures_dir / "packets_per_flow.png", dpi=150)
            plt.close()

            # 4. Bytes Per Flow
            bytes_list = [float(r["total_bytes"]) for r in rows if "total_bytes" in r]
            plt.figure(figsize=(8, 4.5))
            plt.hist(bytes_list, bins=20, color="#9467bd", edgecolor="black", alpha=0.75)
            plt.title("Total Bytes Per Flow Distribution")
            plt.xlabel("Total Bytes")
            plt.ylabel("Flow Frequency")
            plt.grid(axis="y", linestyle="--", alpha=0.7)
            plt.tight_layout()
            plt.savefig(self.figures_dir / "bytes_per_flow.png", dpi=150)
            plt.close()

            logger.info("Saved 4 statistical charts to %s", self.figures_dir)

        except ImportError:
            logger.info("Matplotlib not available. Chart image rendering skipped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze dataset class balance and statistical profiles.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--input", default=None, help="Path to features.csv")
    args = parser.parse_args()

    analyzer = DatasetAnalyzer(config_path=args.config)
    analyzer.analyze(input_path=args.input)


if __name__ == "__main__":
    main()
