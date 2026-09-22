"""
Model Training Orchestrator.

Trains Logistic Regression, Decision Tree, Random Forest, and LightGBM models on training splits,
measures training times and model serialization footprints, and persists model artifacts to results/models/.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml

from models.base_model import BaseTrafficClassifier
from models.decision_tree import DecisionTreeTrafficClassifier
from models.lightgbm_model import LightGBMTrafficClassifier
from models.logistic_regression import LogisticRegressionClassifier
from models.random_forest import RandomForestTrafficClassifier
from training.data_loader import DataLoader

logger = logging.getLogger(__name__)


def train_all_baseline_models(
    x_train: Any,
    y_train: Any,
    class_names: List[str],
    config: Dict[str, Any],
    models_dir: Optional[Path] = None,
) -> Tuple[Dict[str, BaseTrafficClassifier], Dict[str, Dict[str, Any]]]:
    """
    Instantiates and trains all 4 baseline classifiers.
    Measures training duration and physical serialized artifact sizes.
    """
    dest_dir = models_dir or Path("results/models")
    dest_dir.mkdir(parents=True, exist_ok=True)

    models_cfg = config.get("models", {})
    lr_params = models_cfg.get("logistic_regression", {})
    dt_params = models_cfg.get("decision_tree", {})
    rf_params = models_cfg.get("random_forest", {})
    lgb_params = models_cfg.get("lightgbm", {})

    classifiers: Dict[str, BaseTrafficClassifier] = {
        "logistic_regression": LogisticRegressionClassifier(params=lr_params),
        "decision_tree": DecisionTreeTrafficClassifier(params=dt_params),
        "random_forest": RandomForestTrafficClassifier(params=rf_params),
        "lightgbm": LightGBMTrafficClassifier(params=lgb_params),
    }

    trained_models: Dict[str, BaseTrafficClassifier] = {}
    training_metrics: Dict[str, Dict[str, Any]] = {}

    for name, clf in classifiers.items():
        logger.info("--- Training model: %s ---", name)
        save_path = dest_dir / f"{name}.joblib"

        start_time = time.perf_counter()
        try:
            clf.fit(x_train, y_train, classes=class_names)
            train_duration = time.perf_counter() - start_time
            clf.save(save_path)

            file_size_bytes = os.path.getsize(save_path) if save_path.exists() else 0
            file_size_kb = file_size_bytes / 1024.0
            file_size_mb = file_size_bytes / (1024.0 * 1024.0)

            trained_models[name] = clf
            training_metrics[name] = {
                "training_time_seconds": round(train_duration, 4),
                "model_size_bytes": file_size_bytes,
                "model_size_kb": round(file_size_kb, 2),
                "model_size_mb": round(file_size_mb, 4),
                "model_path": str(save_path),
            }
            logger.info(
                "Trained %s in %.4fs | Size: %.2f KB (%.4f MB)",
                name, train_duration, file_size_kb, file_size_mb
            )
        except Exception as e:
            logger.error("Failed to train %s: %s", name, e)

    return trained_models, training_metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train baseline ML models.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--output-dir", default="results/models", help="Directory for model checkpoints")
    args = parser.parse_args()

    loader = DataLoader(config_path=args.config)
    x_train, y_train, _, _, _, _, _, class_names = loader.prepare_datasets()

    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    train_all_baseline_models(
        x_train=x_train,
        y_train=y_train,
        class_names=class_names,
        config=config,
        models_dir=Path(args.output_dir),
    )


if __name__ == "__main__":
    main()
