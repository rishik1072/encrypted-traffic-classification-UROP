"""
Model Complexity Reduction Experiment.

Evaluates hyperparameter and structural simplifications (shallower trees, fewer estimators)
to quantify latency and model footprint reductions under reduced feature counts.
Saves results to experiments/lightweight_model/complexity_comparison.csv.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List
import yaml

from models.decision_tree import DecisionTreeTrafficClassifier
from models.lightgbm_model import LightGBMTrafficClassifier
from models.random_forest import RandomForestTrafficClassifier
from training.benchmark_inference import benchmark_model_latency, measure_serialized_size
from training.data_loader import DataLoader
from training.evaluate import compute_metrics

logger = logging.getLogger(__name__)


def run_model_complexity_experiment(
    config_path: str | Path = "config.yaml",
) -> List[Dict[str, Any]]:
    """Compares baseline vs reduced complexity architectures."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    loader = DataLoader(config_path=config_path)
    x_train, y_train, x_val, y_val, _, _, _, class_names = loader.prepare_datasets()

    eval_x = x_val if (x_val is not None and len(x_val) > 0) else x_train
    eval_y = y_val if (y_val is not None and len(y_val) > 0) else y_train

    complexity_configs = [
        # Random Forest variants
        ("Random Forest", "Baseline (100 Trees, Depth 15)", RandomForestTrafficClassifier, {"n_estimators": 100, "max_depth": 15}),
        ("Random Forest", "Reduced Estimators (25 Trees, Depth 15)", RandomForestTrafficClassifier, {"n_estimators": 25, "max_depth": 15}),
        ("Random Forest", "Reduced Depth (25 Trees, Depth 6)", RandomForestTrafficClassifier, {"n_estimators": 25, "max_depth": 6}),
        # Decision Tree variants
        ("Decision Tree", "Baseline (Depth 12)", DecisionTreeTrafficClassifier, {"max_depth": 12}),
        ("Decision Tree", "Reduced Depth (Depth 5)", DecisionTreeTrafficClassifier, {"max_depth": 5}),
        # LightGBM variants
        ("LightGBM", "Baseline (100 Trees, 31 Leaves)", LightGBMTrafficClassifier, {"n_estimators": 100, "num_leaves": 31}),
        ("LightGBM", "Reduced Estimators (25 Trees, 31 Leaves)", LightGBMTrafficClassifier, {"n_estimators": 25, "num_leaves": 31}),
        ("LightGBM", "Reduced Leaves (25 Trees, 12 Leaves)", LightGBMTrafficClassifier, {"n_estimators": 25, "num_leaves": 12}),
    ]

    results: List[Dict[str, Any]] = []

    for model_family, variant_name, model_cls, params in complexity_configs:
        clf = model_cls(params=params)
        clf.fit(x_train, y_train, classes=class_names)

        y_pred = clf.predict(eval_x)
        metrics = compute_metrics(eval_y, y_pred, class_names)
        bench = benchmark_model_latency(clf, eval_x, warmup_runs=5, benchmark_runs=30)
        size_mb = measure_serialized_size(clf)

        rec = {
            "model_family": model_family,
            "variant": variant_name,
            "feature_count": len(x_train[0]) if x_train else 21,
            "macro_f1": round(metrics.get("f1_macro", 0.0), 4),
            "accuracy": round(metrics.get("accuracy", 0.0), 4),
            "latency_ms": round(bench.get("mean_latency_ms", 0.0), 4),
            "model_size_mb": round(size_mb, 4),
        }
        results.append(rec)

    # Output table
    out_csv = Path("experiments/lightweight_model/complexity_comparison.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    logger.info("Saved model complexity comparison to %s", out_csv)
    return results


def main() -> None:
    run_model_complexity_experiment()


if __name__ == "__main__":
    main()
