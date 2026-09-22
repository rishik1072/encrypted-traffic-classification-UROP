"""
Pareto Frontier and Multi-Objective Trade-Off Analysis.

Identifies non-dominated Pareto-efficient model-feature configurations across:
1. Macro-F1 (higher is better)
2. Inference Latency (lower is better)
3. Model Footprint (lower is better)

Computes configurable project-specific Lightweight Score.
Outputs:
- results/tables/feature_model_pareto_frontier.csv
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List
import yaml

logger = logging.getLogger(__name__)


def is_pareto_dominant(candidate: Dict[str, Any], other: Dict[str, Any]) -> bool:
    """
    Returns True if 'other' strictly dominates 'candidate'.
    A point is dominated if another point is at least as good in all objectives
    and strictly better in at least one.
    Objectives:
    - macro_f1: Higher is better
    - latency_ms: Lower is better
    - model_size_mb: Lower is better
    """
    f1_cand, f1_oth = float(candidate["macro_f1"]), float(other["macro_f1"])
    lat_cand, lat_oth = float(candidate["latency_ms"]), float(other["latency_ms"])
    sz_cand, sz_oth = float(candidate["model_size_mb"]), float(other["model_size_mb"])

    better_or_equal = (f1_oth >= f1_cand) and (lat_oth <= lat_cand) and (sz_oth <= sz_cand)
    strictly_better = (f1_oth > f1_cand) or (lat_oth < lat_cand) or (sz_oth < sz_cand)

    return better_or_equal and strictly_better


def run_pareto_analysis(
    input_csv: str | Path = "results/tables/feature_reduction_performance.csv",
    config_path: str | Path = "config.yaml",
) -> List[Dict[str, Any]]:
    """Analyzes all model-feature configurations and extracts Pareto frontier."""
    csv_file = Path(input_csv)
    if not csv_file.exists():
        raise FileNotFoundError(f"Feature reduction performance table not found: {csv_file}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        records = list(reader)

    if not records:
        return []

    # Calculate Lightweight Score using min-max normalization
    max_f1 = max(float(r["macro_f1"]) for r in records) or 1.0
    min_lat = min(float(r["latency_ms"]) for r in records) or 0.001
    max_lat = max(float(r["latency_ms"]) for r in records) or 1.0
    min_sz = min(float(r["model_size_mb"]) for r in records) or 0.001
    max_sz = max(float(r["model_size_mb"]) for r in records) or 1.0

    weights = config.get("lightweight_score_weights", {})
    w_f1 = weights.get("macro_f1", 0.45)
    w_lat = weights.get("latency", 0.25)
    w_sz = weights.get("model_size", 0.20)
    w_mem = weights.get("memory", 0.10)

    for r in records:
        f1_val = float(r["macro_f1"])
        lat_val = float(r["latency_ms"])
        sz_val = float(r["model_size_mb"])

        # Normalized components (1.0 = best)
        norm_f1 = f1_val / max_f1
        norm_lat = (max_lat - lat_val) / (max_lat - min_lat) if max_lat > min_lat else 1.0
        norm_sz = (max_sz - sz_val) / (max_sz - min_sz) if max_sz > min_sz else 1.0

        lw_score = (w_f1 * norm_f1) + (w_lat * norm_lat) + (w_sz * norm_sz) + (w_mem * 1.0)
        r["lightweight_score"] = round(lw_score, 4)

    # Determine Pareto optimality
    pareto_records: List[Dict[str, Any]] = []
    for cand in records:
        dominated = False
        for other in records:
            if cand is not other and is_pareto_dominant(cand, other):
                dominated = True
                break
        cand["is_pareto_optimal"] = "YES" if not dominated else "NO"
        if not dominated:
            pareto_records.append(cand)

    # Save Pareto frontier table
    out_path = Path("results/tables/feature_model_pareto_frontier.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "model",
            "feature_count",
            "macro_f1",
            "accuracy",
            "latency_ms",
            "model_size_mb",
            "lightweight_score",
            "is_pareto_optimal",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    logger.info("Saved Pareto frontier table (%d Pareto-optimal configurations) to %s", len(pareto_records), out_path)
    return pareto_records


def main() -> None:
    run_pareto_analysis()


if __name__ == "__main__":
    main()
