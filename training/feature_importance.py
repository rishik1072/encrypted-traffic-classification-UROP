"""
Feature Importance Extraction and Ranking Module.

Computes feature importances (Gini/Tree importances for Random Forest, Decision Tree, LightGBM;
absolute coefficient magnitudes for Logistic Regression) and exports tables and visualizations.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.base_model import BaseTrafficClassifier

logger = logging.getLogger(__name__)


def extract_feature_importances(
    models: Dict[str, BaseTrafficClassifier],
    feature_names: List[str],
    output_dir: Optional[Path] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extracts, normalizes, and ranks feature importances for each trained model.
    Saves tables under results/tables/feature_importance_<model>.csv.
    """
    out_dir = output_dir or Path("results/tables")
    out_dir.mkdir(parents=True, exist_ok=True)
    all_importances: Dict[str, List[Dict[str, Any]]] = {}

    for name, clf in models.items():
        estimator = clf.model
        scores: List[float] = []

        if hasattr(estimator, "feature_importances_"):
            raw_scores = estimator.feature_importances_
            total = sum(raw_scores) or 1.0
            scores = [float(s / total) for s in raw_scores]
        elif hasattr(estimator, "coef_"):
            # Logistic Regression coefficients (sum of absolute magnitudes across classes)
            try:
                import numpy as np
                coefs = np.abs(estimator.coef_)
                agg_scores = np.mean(coefs, axis=0) if coefs.ndim > 1 else coefs
                total = np.sum(agg_scores) or 1.0
                scores = [float(s / total) for s in agg_scores]
            except Exception:
                scores = [1.0 / len(feature_names)] * len(feature_names)
        else:
            # Fallback uniform scores
            scores = [1.0 / len(feature_names)] * len(feature_names)

        # Pair with feature names and sort descending
        paired = sorted(
            zip(feature_names, scores),
            key=lambda item: item[1],
            reverse=True,
        )

        ranked_list = [
            {"rank": idx + 1, "feature_name": feat, "importance": round(score, 6)}
            for idx, (feat, score) in enumerate(paired)
        ]
        all_importances[name] = ranked_list

        # Write to CSV
        csv_path = out_dir / f"feature_importance_{name}.csv"
        real_csv_path = out_dir / f"real_feature_importance_{name}.csv"
        for path in (csv_path, real_csv_path):
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["rank", "feature_name", "importance"])
                writer.writeheader()
                writer.writerows(ranked_list)

        logger.info("Saved feature importances for %s to %s and %s", name, csv_path, real_csv_path)

    return all_importances
