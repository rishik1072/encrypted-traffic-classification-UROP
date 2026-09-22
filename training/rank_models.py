"""
Multi-Criteria Model Ranking and Pareto Efficiency Analysis.

Ranks models across performance (Macro F1), inference latency (ms), and model footprint (MB),
identifying non-dominated Pareto-optimal models.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def rank_and_find_pareto_front(
    comparison_records: List[Dict[str, Any]],
    output_dir: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Ranks models using multi-criteria weighted scoring and computes the Pareto frontier
    (maximizing Macro F1, minimizing latency, minimizing model size).
    """
    if not comparison_records:
        return [], []

    # 1. Multi-Criteria Composite Score
    # Normalize objectives: f1 (higher better), latency (lower better), size (lower better)
    f1_vals = [r["f1_macro"] for r in comparison_records]
    lat_vals = [r["avg_inference_ms"] for r in comparison_records]
    size_vals = [r["model_size_mb"] for r in comparison_records]

    max_f1 = max(f1_vals) or 1.0
    min_lat = min(lat_vals) or 0.001
    min_size = min(size_vals) or 0.001

    ranked_records = []
    for r in comparison_records:
        f1_norm = r["f1_macro"] / max_f1
        lat_norm = min_lat / (r["avg_inference_ms"] if r["avg_inference_ms"] > 0 else 0.001)
        size_norm = min_size / (r["model_size_mb"] if r["model_size_mb"] > 0 else 0.001)

        # Composite score: 50% F1, 30% Latency, 20% Model Size
        composite_score = round(0.50 * f1_norm + 0.30 * lat_norm + 0.20 * size_norm, 4)

        ranked_records.append({
            **r,
            "composite_efficiency_score": composite_score,
        })

    # Sort descending by composite score
    ranked_records.sort(key=lambda x: x["composite_efficiency_score"], reverse=True)
    for idx, r in enumerate(ranked_records):
        r["rank"] = idx + 1

    # 2. Pareto Efficiency Check
    pareto_models: List[str] = []
    for i, a in enumerate(comparison_records):
        is_dominated = False
        for j, b in enumerate(comparison_records):
            if i == j:
                continue
            # b dominates a if b is at least as good in all 3 criteria and strictly better in at least one
            better_or_equal = (
                b["f1_macro"] >= a["f1_macro"] and
                b["avg_inference_ms"] <= a["avg_inference_ms"] and
                b["model_size_mb"] <= a["model_size_mb"]
            )
            strictly_better = (
                b["f1_macro"] > a["f1_macro"] or
                b["avg_inference_ms"] < a["avg_inference_ms"] or
                b["model_size_mb"] < a["model_size_mb"]
            )
            if better_or_equal and strictly_better:
                is_dominated = True
                break

        if not is_dominated:
            pareto_models.append(a["model"])

    logger.info("Identified Pareto-optimal models: %s", pareto_models)
    return ranked_records, pareto_models
