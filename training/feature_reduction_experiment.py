"""
Controlled Feature Reduction Experiments Module.

Evaluates feature subsets K in {21, 15, 10, 5, 3} across all baseline models
strictly using Training / Validation splits.
Calculates performance degradation, resource improvements, saves subset CSVs,
stores models in results/models/lightweight_<K>/, and exports experiment manifests.
"""

from __future__ import annotations

import csv
import logging
import pickle
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
import yaml

from models.decision_tree import DecisionTreeTrafficClassifier
from models.lightgbm_model import LightGBMTrafficClassifier
from models.logistic_regression import LogisticRegressionClassifier
from models.random_forest import RandomForestTrafficClassifier
from preprocessing.preprocessing import FeaturePreprocessor
from training.benchmark_inference import benchmark_model_latency, measure_serialized_size
from training.data_loader import DataLoader
from training.evaluate import compute_metrics
from training.feature_ranking import run_feature_ranking

logger = logging.getLogger(__name__)


def run_feature_reduction_experiments(
    config_path: str | Path = "config.yaml",
) -> List[Dict[str, Any]]:
    """Runs controlled evaluation across K in {21, 15, 10, 5, 3}."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 1. Obtain ranked feature list
    ranking_records, _ = run_feature_ranking(config_path=config_path)
    ranked_feature_names = [r["feature"] for r in ranking_records]

    k_subsets: List[int] = config.get("feature_selection", {}).get("candidate_k_subsets", [21, 15, 10, 5, 3])
    traffic_classes = list(config.get("traffic_classes", []))

    loader = DataLoader(config_path=config_path)
    train_records = loader.load_raw_split("train")
    val_records = loader.load_raw_split("validation")
    target_col = loader.target_col

    models_factory = {
        "logistic_regression": LogisticRegressionClassifier,
        "decision_tree": DecisionTreeTrafficClassifier,
        "random_forest": RandomForestTrafficClassifier,
        "lightgbm": LightGBMTrafficClassifier,
    }

    all_experiment_records: List[Dict[str, Any]] = []
    baseline_metrics: Dict[str, Dict[str, float]] = {}

    for k in k_subsets:
        selected_k_features = ranked_feature_names[:k]
        logger.info("=== Running Feature Reduction Experiment for K = %d ===", k)

        # Save selected_features_<K>.csv
        k_table_path = Path(f"results/tables/selected_features_{k}.csv")
        k_table_path.parent.mkdir(parents=True, exist_ok=True)
        with open(k_table_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["rank", "feature_name"])
            writer.writeheader()
            for r_idx, f_name in enumerate(selected_k_features, start=1):
                writer.writerow({"rank": r_idx, "feature_name": f_name})

        # Fit preprocessor on Train ONLY for this subset
        k_config = dict(config)
        k_config["features"] = dict(config.get("features", {}))
        k_config["features"]["numerical_features"] = selected_k_features

        preprocessor = FeaturePreprocessor(k_config)
        preprocessor.fit(train_records, target_col=target_col)

        x_train = preprocessor.transform(train_records)
        y_train = preprocessor.encode_labels(train_records, target_col=target_col)

        x_val = preprocessor.transform(val_records) if val_records else []
        y_val = preprocessor.encode_labels(val_records, target_col=target_col) if val_records else []

        # Subdirectory for this model profile
        profile_dir = Path(f"results/models/lightweight_{k}" if k < 21 else "results/models/baseline")
        profile_dir.mkdir(parents=True, exist_ok=True)

        # Save fitted preprocessor
        with open(profile_dir / "preprocessor.joblib", "wb") as f:
            pickle.dump(preprocessor, f)

        # Evaluate each model on Validation set
        for model_name, model_cls in models_factory.items():
            model = model_cls(params=config.get("models", {}).get(model_name, {}))
            model.fit(x_train, y_train, classes=traffic_classes)

            # Save model artifact
            model.save(profile_dir / f"{model_name}.joblib")

            # Evaluate on validation (or fallback to train if val is tiny)
            eval_x = x_val if len(x_val) > 0 else x_train
            eval_y = y_val if len(y_val) > 0 else y_train
            y_pred = model.predict(eval_x)
            metrics = compute_metrics(eval_y, y_pred, traffic_classes)

            # Measure latency & size
            bench_res = benchmark_model_latency(model, eval_x, warmup_runs=10, benchmark_runs=50)
            model_size_mb = measure_serialized_size(model)

            macro_f1 = metrics.get("f1_macro", 0.0)
            accuracy = metrics.get("accuracy", 0.0)
            weighted_f1 = metrics.get("f1_weighted", 0.0)
            latency_ms = bench_res.get("mean_latency_ms", 0.0)

            # Track baseline (K=21) for degradation comparison
            if k == 21:
                baseline_metrics[model_name] = {
                    "macro_f1": macro_f1,
                    "accuracy": accuracy,
                    "weighted_f1": weighted_f1,
                    "latency_ms": latency_ms,
                    "model_size_mb": model_size_mb,
                }

            base_m = baseline_metrics.get(model_name, {
                "macro_f1": macro_f1,
                "accuracy": accuracy,
                "latency_ms": latency_ms,
                "model_size_mb": model_size_mb,
            })

            delta_f1 = macro_f1 - base_m["macro_f1"]
            delta_acc = accuracy - base_m["accuracy"]
            lat_red = ((base_m["latency_ms"] - latency_ms) / (base_m["latency_ms"] or 1.0)) * 100.0
            size_red = ((base_m["model_size_mb"] - model_size_mb) / (base_m["model_size_mb"] or 1.0)) * 100.0

            rec = {
                "model": model_name,
                "feature_count": k,
                "macro_f1": round(macro_f1, 4),
                "delta_macro_f1": round(delta_f1, 4),
                "accuracy": round(accuracy, 4),
                "delta_accuracy": round(delta_acc, 4),
                "weighted_f1": round(weighted_f1, 4),
                "latency_ms": round(latency_ms, 4),
                "latency_reduction_percent": round(lat_red, 2),
                "model_size_mb": round(model_size_mb, 4),
                "model_size_reduction_percent": round(size_red, 2),
            }
            all_experiment_records.append(rec)

    # Save performance degradation table
    deg_file = Path("results/tables/feature_reduction_performance.csv")
    with open(deg_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_experiment_records[0].keys()))
        writer.writeheader()
        writer.writerows(all_experiment_records)

    # Save experiment manifest
    manifest_file = Path("results/tables/feature_experiment_manifest.csv")
    manifest_records = []
    for r in all_experiment_records:
        manifest_records.append({
            "run_id": f"RUN-{r['model'][:3].upper()}-K{r['feature_count']}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": r["model"],
            "feature_count": r["feature_count"],
            "macro_f1": r["macro_f1"],
            "latency_ms": r["latency_ms"],
            "model_size_mb": r["model_size_mb"],
        })
    with open(manifest_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(manifest_records[0].keys()))
        writer.writeheader()
        writer.writerows(manifest_records)

    logger.info("Completed feature reduction experiments. Saved results to %s", deg_file)
    return all_experiment_records


def main() -> None:
    run_feature_reduction_experiments()


if __name__ == "__main__":
    main()
