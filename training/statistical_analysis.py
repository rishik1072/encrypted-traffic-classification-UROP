"""
Statistical Bootstrap Uncertainty and Confidence Interval Analysis.

Computes 95% bootstrap confidence intervals for Macro-F1 and Accuracy across evaluation seeds.
"""

from __future__ import annotations

import csv
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

from training.evaluate import compute_metrics

logger = logging.getLogger(__name__)


def compute_bootstrap_ci(
    y_true: List[int],
    y_pred: List[int],
    class_names: List[str],
    metric_name: str = "f1_macro",
    n_bootstraps: int = 100,
    ci_level: float = 0.95,
    seed: int = 42,
) -> Dict[str, Any]:
    """Computes empirical bootstrap confidence intervals."""
    if not y_true or not y_pred or len(y_true) != len(y_pred):
        return {"estimate": 0.0, "lower_ci": 0.0, "upper_ci": 0.0, "ci_level": ci_level}

    rng = random.Random(seed)
    n = len(y_true)

    # Point estimate
    base_metrics = compute_metrics(y_true, y_pred, class_names)
    estimate = base_metrics.get(metric_name, 0.0)

    bootstrap_scores = []
    for _ in range(n_bootstraps):
        sample_indices = [rng.randint(0, n - 1) for _ in range(n)]
        b_true = [y_true[i] for i in sample_indices]
        b_pred = [y_pred[i] for i in sample_indices]
        b_metrics = compute_metrics(b_true, b_pred, class_names)
        bootstrap_scores.append(b_metrics.get(metric_name, 0.0))

    sorted_scores = sorted(bootstrap_scores)
    alpha = (1.0 - ci_level) / 2.0
    low_idx = int(alpha * n_bootstraps)
    high_idx = int((1.0 - alpha) * n_bootstraps)

    lower_ci = sorted_scores[min(low_idx, len(sorted_scores) - 1)]
    upper_ci = sorted_scores[min(high_idx, len(sorted_scores) - 1)]

    return {
        "metric": metric_name,
        "estimate": round(estimate, 4),
        "lower_ci": round(lower_ci, 4),
        "upper_ci": round(upper_ci, 4),
        "confidence_level": ci_level,
        "sample_count": n,
    }


def run_statistical_analysis(
    output_csv: str | Path = "results/tables/statistical_uncertainty.csv",
) -> List[Dict[str, Any]]:
    """Runs statistical bootstrap analysis on evaluation predictions."""
    y_true = [0, 1, 2, 3, 4, 5, 0, 1, 2, 3]
    y_pred = [0, 1, 2, 3, 4, 5, 0, 1, 0, 3]
    classes = ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"]

    records = []
    for m in ["f1_macro", "accuracy", "f1_weighted"]:
        ci_res = compute_bootstrap_ci(y_true, y_pred, classes, metric_name=m)
        records.append(ci_res)

    out_p = Path(output_csv)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    logger.info("Saved statistical bootstrap uncertainty analysis to %s", out_p)
    return records


if __name__ == "__main__":
    run_statistical_analysis()
