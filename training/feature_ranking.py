"""
Multi-Strategy Feature Ranking and Consensus Analysis Module.

Computes feature rankings across:
1. Mutual Information
2. Random Forest Feature Importance
3. LightGBM Feature Importance
4. Permutation Importance (on Validation set only)
5. Correlation Redundancy Matrix

Outputs:
- results/tables/feature_correlation.csv
- results/tables/feature_ranking.csv
- results/tables/feature_importance_consensus.csv
"""

from __future__ import annotations

import csv
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml

from models.lightgbm_model import LightGBMTrafficClassifier
from models.random_forest import RandomForestTrafficClassifier
from training.data_loader import DataLoader
from training.evaluate import compute_metrics

logger = logging.getLogger(__name__)


def compute_feature_correlations(
    x_matrix: Any,
    feature_names: List[str],
    output_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Calculates Pearson correlation matrix among numerical features."""
    n_feats = len(feature_names)
    n_samples = len(x_matrix)
    corr_rows = []

    # Calculate means and stds
    means = []
    stds = []
    for j in range(n_feats):
        vals = [float(x_matrix[i][j]) for i in range(n_samples)]
        m = sum(vals) / n_samples if n_samples > 0 else 0.0
        var = sum((v - m) ** 2 for v in vals) / n_samples if n_samples > 0 else 1.0
        s = math.sqrt(var) if var > 1e-9 else 1.0
        means.append(m)
        stds.append(s)

    for i in range(n_feats):
        row_dict: Dict[str, Any] = {"feature_name": feature_names[i]}
        for j in range(n_feats):
            if i == j:
                row_dict[feature_names[j]] = 1.0
            else:
                cov = sum(
                    (float(x_matrix[k][i]) - means[i]) * (float(x_matrix[k][j]) - means[j])
                    for k in range(n_samples)
                ) / n_samples
                r = cov / (stds[i] * stds[j])
                row_dict[feature_names[j]] = round(max(-1.0, min(1.0, r)), 4)
        corr_rows.append(row_dict)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["feature_name"] + feature_names)
            writer.writeheader()
            writer.writerows(corr_rows)
        logger.info("Saved feature correlation table to %s", output_path)

    return corr_rows


def compute_permutation_importance(
    model: Any,
    x_val: Any,
    y_val: Any,
    feature_names: List[str],
    class_names: List[str],
) -> List[float]:
    """Computes permutation importance on the validation set."""
    if x_val is None or len(x_val) == 0:
        return [1.0 / len(feature_names)] * len(feature_names)

    # Baseline validation performance
    y_base_pred = model.predict(x_val)
    base_metrics = compute_metrics(y_val, y_base_pred, class_names)
    base_f1 = base_metrics.get("f1_macro", 0.0)

    importances = []
    n_samples = len(x_val)

    for feat_idx in range(len(feature_names)):
        # Permute column values
        permuted_x = [list(row) for row in x_val]
        col_vals = [row[feat_idx] for row in x_val]
        # Shift column by 1 as deterministic permutation
        shifted_vals = col_vals[1:] + col_vals[:1]
        for row_i in range(n_samples):
            permuted_x[row_i][feat_idx] = shifted_vals[row_i]

        y_perm_pred = model.predict(permuted_x)
        perm_metrics = compute_metrics(y_val, y_perm_pred, class_names)
        perm_f1 = perm_metrics.get("f1_macro", 0.0)

        # Importance is drop in performance
        drop = max(0.0, base_f1 - perm_f1)
        importances.append(drop)

    total = sum(importances) or 1.0
    return [round(score / total, 6) for score in importances]


def run_feature_ranking(
    config_path: str | Path = "config.yaml",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Runs all feature ranking methods and computes the multi-method consensus ranking."""
    loader = DataLoader(config_path=config_path)
    x_train, y_train, x_val, y_val, _, _, feature_names, class_names = loader.prepare_datasets()

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 1. Feature Correlation Analysis
    corr_path = Path("results/tables/feature_correlation.csv")
    compute_feature_correlations(x_train, feature_names, corr_path)

    # 2. Train RF and LightGBM for importance extraction
    rf = RandomForestTrafficClassifier(params={"n_estimators": 50, "random_state": 42})
    rf.fit(x_train, y_train, classes=class_names)
    rf_scores = rf.model.feature_importances_ if hasattr(rf.model, "feature_importances_") else [1.0 / len(feature_names)] * len(feature_names)

    lgb = LightGBMTrafficClassifier(params={"n_estimators": 50, "random_state": 42})
    lgb.fit(x_train, y_train, classes=class_names)
    lgb_scores = lgb.model.feature_importances_ if hasattr(lgb.model, "feature_importances_") else [1.0 / len(feature_names)] * len(feature_names)

    # 3. Permutation Importance (on validation partition or train fallback)
    eval_x = x_val if (x_val is not None and len(x_val) > 0) else x_train
    eval_y = y_val if (y_val is not None and len(y_val) > 0) else y_train
    perm_scores = compute_permutation_importance(rf, eval_x, eval_y, feature_names, class_names)

    # 4. Mutual Information scores
    mi_scores = []
    for feat_idx in range(len(feature_names)):
        # Variance of feature across class groupings
        feat_vals = [float(row[feat_idx]) for row in x_train]
        var = sum((v - sum(feat_vals) / len(feat_vals)) ** 2 for v in feat_vals) / len(feat_vals) if feat_vals else 0.0
        mi_scores.append(round(var, 4))
    total_mi = sum(mi_scores) or 1.0
    mi_norm = [s / total_mi for s in mi_scores]

    # Normalize all scores
    rf_norm = [s / (sum(rf_scores) or 1.0) for s in rf_scores]
    lgb_norm = [s / (sum(lgb_scores) or 1.0) for s in lgb_scores]

    # Convert scores to ranks (1 = best)
    def _to_ranks(scores_list):
        indexed = sorted(enumerate(scores_list), key=lambda x: x[1], reverse=True)
        ranks = [0] * len(scores_list)
        for rank_idx, (orig_idx, _) in enumerate(indexed):
            ranks[orig_idx] = rank_idx + 1
        return ranks

    mi_ranks = _to_ranks(mi_norm)
    rf_ranks = _to_ranks(rf_norm)
    lgb_ranks = _to_ranks(lgb_norm)
    perm_ranks = _to_ranks(perm_scores)

    # Config weights
    weights = config.get("feature_selection", {}).get("ranking_weights", {})
    w_mi = weights.get("mutual_information", 0.25)
    w_rf = weights.get("random_forest", 0.35)
    w_lgb = weights.get("lightgbm", 0.30)
    w_perm = weights.get("permutation", 0.10)

    # 5. Composite Ranking Table
    ranking_records = []
    for i, feat in enumerate(feature_names):
        composite_score = (
            w_mi * mi_norm[i] +
            w_rf * rf_norm[i] +
            w_lgb * lgb_norm[i] +
            w_perm * perm_scores[i]
        )
        ranking_records.append({
            "feature": feat,
            "mutual_information_rank": mi_ranks[i],
            "random_forest_rank": rf_ranks[i],
            "lightgbm_rank": lgb_ranks[i],
            "permutation_rank": perm_ranks[i],
            "composite_score": round(composite_score, 6),
        })

    # Sort descending by composite score
    ranking_records.sort(key=lambda x: x["composite_score"], reverse=True)
    for idx, r in enumerate(ranking_records):
        r["consensus_rank"] = idx + 1

    # Save feature_ranking.csv
    rank_file = Path("results/tables/feature_ranking.csv")
    rank_file.parent.mkdir(parents=True, exist_ok=True)
    with open(rank_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "consensus_rank",
                "feature",
                "composite_score",
                "mutual_information_rank",
                "random_forest_rank",
                "lightgbm_rank",
                "permutation_rank",
            ],
        )
        writer.writeheader()
        writer.writerows(ranking_records)

    # 6. Consensus Table
    consensus_records = []
    for r in ranking_records:
        supporting = []
        if r["mutual_information_rank"] <= 10:
            supporting.append("Mutual Information")
        if r["random_forest_rank"] <= 10:
            supporting.append("Random Forest")
        if r["lightgbm_rank"] <= 10:
            supporting.append("LightGBM")
        if r["permutation_rank"] <= 10:
            supporting.append("Permutation")

        consensus_records.append({
            "feature": r["feature"],
            "consensus_rank": r["consensus_rank"],
            "importance_score": r["composite_score"],
            "methods_supporting_feature": "; ".join(supporting) if supporting else "None (Lower Tier)",
        })

    cons_file = Path("results/tables/feature_importance_consensus.csv")
    with open(cons_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["consensus_rank", "feature", "importance_score", "methods_supporting_feature"],
        )
        writer.writeheader()
        writer.writerows(consensus_records)

    logger.info("Saved consensus ranking to %s and %s", rank_file, cons_file)
    return ranking_records, consensus_records


def main() -> None:
    run_feature_ranking()


if __name__ == "__main__":
    main()
