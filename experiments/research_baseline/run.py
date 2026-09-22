"""
Research Baseline Benchmark Runner.

Research Question:
"How well can lightweight zero-payload statistical features classify encrypted traffic under group-aware evaluation?"

This module executes an end-to-end, scientifically rigorous, reproducible baseline experiment
evaluating 4 lightweight classifiers (Logistic Regression, Decision Tree, Random Forest, LightGBM)
on the authoritative REAL dataset (dataset_v2) with strict session-level group-aware isolation,
validation-based model selection, and locked held-out test set evaluation.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
import logging
import math
import os
from pathlib import Path
import random
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import yaml

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

# Internal modules
from flows.flow_generator import Direction, Flow, FlowKey
from models.decision_tree import DecisionTreeTrafficClassifier
from models.lightgbm_model import LightGBMTrafficClassifier
from models.logistic_regression import LogisticRegressionClassifier
from models.random_forest import RandomForestTrafficClassifier
from preprocessing.feature_extractor import FeatureExtractor
from preprocessing.preprocessing import FeaturePreprocessor
from training.dataset_registry import DatasetOrigin, DatasetRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("research_baseline")

# Canonical 21 zero-payload statistical features
CANONICAL_21_FEATURES = [
    "flow_duration",
    "forward_packet_count",
    "backward_packet_count",
    "total_packet_count",
    "forward_bytes",
    "backward_bytes",
    "total_bytes",
    "avg_packet_size",
    "min_packet_size",
    "max_packet_size",
    "packet_size_variance",
    "mean_iat",
    "median_iat",
    "iat_std",
    "min_iat",
    "max_iat",
    "fwd_bwd_packet_ratio",
    "fwd_bwd_byte_ratio",
    "burst_count",
    "avg_burst_bytes",
    "avg_burst_packets",
]

CANONICAL_CLASSES = ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"]


def get_git_revision(project_root: Path) -> str:
    """Discovers git commit SHA if available, else returns codebase version."""
    head_file = project_root / ".git" / "HEAD"
    if head_file.exists():
        try:
            head_content = head_file.read_text(encoding="utf-8").strip()
            if head_content.startswith("ref:"):
                ref_path = head_content.split(" ", 1)[1]
                ref_file = project_root / ".git" / ref_path
                if ref_file.exists():
                    return ref_file.read_text(encoding="utf-8").strip()[:10]
            else:
                return head_content[:10]
        except Exception:
            pass
    version_file = project_root / "VERSION"
    if version_file.exists():
        return f"v{version_file.read_text(encoding='utf-8').strip()}"
    return "unknown"


def compute_multiclass_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    classes: List[str],
) -> Dict[str, Any]:
    """Computes multiclass evaluation metrics including balanced accuracy and confusion matrix."""
    n_classes = len(classes)
    matrix = np.zeros((n_classes, n_classes), dtype=int)
    for t, p in zip(y_true, y_pred):
        if 0 <= t < n_classes and 0 <= p < n_classes:
            matrix[t, p] += 1

    total_samples = len(y_true)
    correct = int(np.trace(matrix))
    accuracy = float(correct / total_samples) if total_samples > 0 else 0.0

    per_class: Dict[str, Dict[str, float]] = {}
    recalls: List[float] = []
    precisions: List[float] = []
    f1s: List[float] = []
    supports: List[int] = []

    for i, cls_name in enumerate(classes):
        tp = int(matrix[i, i])
        fp = int(np.sum(matrix[:, i]) - tp)
        fn = int(np.sum(matrix[i, :]) - tp)
        support = int(np.sum(matrix[i, :]))

        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

        per_class[cls_name] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "support": support,
        }
        recalls.append(rec)
        precisions.append(prec)
        f1s.append(f1)
        supports.append(support)

    macro_precision = float(np.mean(precisions)) if precisions else 0.0
    macro_recall = float(np.mean(recalls)) if recalls else 0.0
    macro_f1 = float(np.mean(f1s)) if f1s else 0.0

    # Balanced accuracy equals macro recall across classes with positive support
    classes_with_support = [rec for rec, sup in zip(recalls, supports) if sup > 0]
    balanced_accuracy = float(np.mean(classes_with_support)) if classes_with_support else 0.0

    total_support = sum(supports)
    if total_support > 0:
        weighted_precision = float(sum(p * s for p, s in zip(precisions, supports)) / total_support)
        weighted_recall = float(sum(r * s for r, s in zip(recalls, supports)) / total_support)
        weighted_f1 = float(sum(f * s for f, s in zip(f1s, supports)) / total_support)
    else:
        weighted_precision = 0.0
        weighted_recall = 0.0
        weighted_f1 = 0.0

    return {
        "accuracy": round(accuracy, 4),
        "macro_precision": round(macro_precision, 4),
        "macro_recall": round(macro_recall, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "balanced_accuracy": round(balanced_accuracy, 4),
        "confusion_matrix": matrix.tolist(),
        "per_class": per_class,
    }


def benchmark_inference_latency(
    model: Any,
    x_matrix: np.ndarray,
    warmup_runs: int = 50,
    benchmark_runs: int = 500,
) -> Dict[str, float]:
    """Profiles single-flow inference latency across warmup and benchmark trials."""
    n_samples = len(x_matrix)
    if n_samples == 0:
        return {"mean_ms": 0.0, "median_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0}

    # Warmup
    for i in range(warmup_runs):
        idx = i % n_samples
        _ = model.predict(x_matrix[idx : idx + 1])

    # Timed runs
    durations_ms: List[float] = []
    for i in range(benchmark_runs):
        idx = i % n_samples
        sample = x_matrix[idx : idx + 1]
        t0 = time.perf_counter()
        _ = model.predict(sample)
        t1 = time.perf_counter()
        durations_ms.append((t1 - t0) * 1000.0)

    durations_arr = np.array(durations_ms)
    return {
        "mean_ms": round(float(np.mean(durations_arr)), 4),
        "median_ms": round(float(np.median(durations_arr)), 4),
        "p95_ms": round(float(np.percentile(durations_arr, 95)), 4),
        "p99_ms": round(float(np.percentile(durations_arr, 99)), 4),
    }


def benchmark_feature_extraction_latency(benchmark_runs: int = 500) -> float:
    """Measures latency of FeatureExtractor on representative packet records."""
    key = FlowKey("192.168.1.100", 54321, "1.1.1.1", 443, "UDP")
    flow = Flow(
        key=key,
        initiator_ip="192.168.1.100",
        initiator_port=54321,
        start_time=100.0,
        last_seen=100.0 + (49 * 0.02),
    )
    # Populate with 50 realistic packets
    for i in range(50):
        t = 100.0 + (i * 0.02)
        length = 1200 if i % 2 == 0 else 80
        direction = Direction.FORWARD if i % 2 == 0 else Direction.BACKWARD
        flow.packet_records.append((t, length, direction))

    extractor = FeatureExtractor()

    # Warmup
    for _ in range(50):
        _ = extractor.extract_features(flow)

    t0 = time.perf_counter()
    for _ in range(benchmark_runs):
        _ = extractor.extract_features(flow)
    t1 = time.perf_counter()

    avg_ms = ((t1 - t0) / benchmark_runs) * 1000.0
    return round(avg_ms, 5)


class ResearchBaselineExperiment:
    """Orchestrates the scientific baseline experiment."""

    def __init__(
        self,
        config_path: str = "config.yaml",
        dataset_id: str = "dataset_v2",
        seed: int = 42,
        output_dir: Optional[str] = None,
    ) -> None:
        self.project_root = PROJECT_ROOT
        self.config_path = self.project_root / config_path
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.dataset_id = dataset_id
        self.seed = seed
        self.output_dir = Path(output_dir) if output_dir else self.project_root / "results"
        self.tables_dir = self.output_dir / "tables"
        self.figures_dir = self.output_dir / "figures"
        self.models_dir = self.output_dir / "models" / "research_baseline"

        self.tables_dir.mkdir(parents=True, exist_ok=True)
        self.figures_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.registry = DatasetRegistry(self.project_root)
        self.git_rev = get_git_revision(self.project_root)

    def load_and_validate_dataset(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Loads features from dataset_v2 and enforces real-data integrity verification."""
        meta = self.registry.get_dataset(self.dataset_id)
        if meta.origin != DatasetOrigin.REAL_DATA:
            raise ValueError(f"Scientific integrity violation: {self.dataset_id} is not REAL_DATA.")

        feature_path = self.project_root / meta.primary_feature_path
        if not feature_path.exists():
            raise FileNotFoundError(f"Feature dataset not found: {feature_path}")

        records: List[Dict[str, Any]] = []
        with open(feature_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(dict(row))

        # Enforce registry real-data claim
        self.registry.validate_real_data_claim(self.dataset_id, records)
        logger.info("Loaded and verified %d real flows from %s", len(records), self.dataset_id)
        return records, asdict_meta(meta)

    def split_data_group_aware(
        self, records: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Partitions records by session_id with stratification across traffic classes.
        Train: 70% (~17 sessions/class), Val: 15% (4 sessions/class), Test: 15% (4 sessions/class).
        Guarantees zero session leakage across partitions.
        """
        # Group sessions by traffic class
        class_sessions: Dict[str, List[str]] = defaultdict(list)
        session_to_records: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for r in records:
            s_id = r["session_id"]
            cls = r["traffic_class"]
            session_to_records[s_id].append(r)
            if s_id not in class_sessions[cls]:
                class_sessions[cls].append(s_id)

        rng = random.Random(self.seed)
        train_sessions: Set[str] = set()
        val_sessions: Set[str] = set()
        test_sessions: Set[str] = set()

        for cls, sessions in sorted(class_sessions.items()):
            shuffled = list(sessions)
            rng.shuffle(shuffled)
            n_total = len(shuffled)
            # Stratified 17 train, 4 val, 4 test for 25 sessions
            n_val = max(1, int(round(n_total * 0.16)))
            n_test = max(1, int(round(n_total * 0.16)))
            n_train = n_total - n_val - n_test

            train_sessions.update(shuffled[:n_train])
            val_sessions.update(shuffled[n_train : n_train + n_val])
            test_sessions.update(shuffled[n_train + n_val :])

        # Assert leakage-free invariant
        assert len(train_sessions & val_sessions) == 0, "Leakage between train and val sessions!"
        assert len(train_sessions & test_sessions) == 0, "Leakage between train and test sessions!"
        assert len(val_sessions & test_sessions) == 0, "Leakage between val and test sessions!"

        train_records = [r for s_id in train_sessions for r in session_to_records[s_id]]
        val_records = [r for s_id in val_sessions for r in session_to_records[s_id]]
        test_records = [r for s_id in test_sessions for r in session_to_records[s_id]]

        logger.info(
            "Group-aware split by session_id: Train=%d flows (%d sessions), Val=%d flows (%d sessions), Test=%d flows (%d sessions)",
            len(train_records),
            len(train_sessions),
            len(val_records),
            len(val_sessions),
            len(test_records),
            len(test_sessions),
        )
        return train_records, val_records, test_records

    def build_models(self) -> Dict[str, Any]:
        """Instantiates the 4 benchmark models with standardized hyperparameters."""
        models: Dict[str, Any] = {}

        # 1. Logistic Regression
        lr_cfg = self.config.get("models", {}).get("logistic_regression", {})
        lr_params = {
            "max_iter": lr_cfg.get("max_iter", 1000),
            "solver": lr_cfg.get("solver", "lbfgs"),
            "C": lr_cfg.get("C", 1.0),
            "random_state": self.seed,
        }
        models["logistic_regression"] = LogisticRegressionClassifier(params=lr_params)

        # 2. Decision Tree
        dt_cfg = self.config.get("models", {}).get("decision_tree", {})
        dt_params = {
            "max_depth": dt_cfg.get("max_depth", 12),
            "min_samples_split": dt_cfg.get("min_samples_split", 5),
            "criterion": dt_cfg.get("criterion", "gini"),
            "random_state": self.seed,
        }
        models["decision_tree"] = DecisionTreeTrafficClassifier(params=dt_params)

        # 3. Random Forest
        rf_cfg = self.config.get("models", {}).get("random_forest", {})
        rf_params = {
            "n_estimators": rf_cfg.get("n_estimators", 100),
            "max_depth": rf_cfg.get("max_depth", 15),
            "min_samples_split": rf_cfg.get("min_samples_split", 4),
            "random_state": self.seed,
            "n_jobs": -1,
        }
        models["random_forest"] = RandomForestTrafficClassifier(params=rf_params)

        # 4. LightGBM
        lgb_cfg = self.config.get("models", {}).get("lightgbm", {})
        lgb_params = {
            "n_estimators": lgb_cfg.get("n_estimators", 100),
            "learning_rate": lgb_cfg.get("learning_rate", 0.05),
            "num_leaves": lgb_cfg.get("num_leaves", 31),
            "objective": "multiclass",
            "random_state": self.seed,
            "verbose": -1,
        }
        models["lightgbm"] = LightGBMTrafficClassifier(params=lgb_params)

        return models

    def run(self) -> Dict[str, Any]:
        """Executes the complete baseline benchmark experiment."""
        logger.info("Starting Research Baseline Benchmark Experiment (EXP-R09)...")
        records, meta = self.load_and_validate_dataset()

        # Split data
        train_records, val_records, test_records = self.split_data_group_aware(records)

        # Preprocessing - Strictly fit on train only
        prep_config = dict(self.config)
        prep_config["features"] = {"numerical_features": CANONICAL_21_FEATURES}
        preprocessor = FeaturePreprocessor(prep_config)
        preprocessor.fit(train_records, target_col="traffic_class")

        x_train = preprocessor.transform(train_records)
        y_train = preprocessor.encode_labels(train_records, target_col="traffic_class")

        x_val = preprocessor.transform(val_records)
        y_val = preprocessor.encode_labels(val_records, target_col="traffic_class")

        x_test = preprocessor.transform(test_records)
        y_test = preprocessor.encode_labels(test_records, target_col="traffic_class")

        classes = preprocessor.get_classes()
        logger.info("Identified %d classes: %s", len(classes), classes)

        # Benchmark Feature Extraction Latency
        feat_lat_ms = benchmark_feature_extraction_latency(benchmark_runs=500)
        logger.info("Canonical 21 zero-payload feature extraction latency: %f ms", feat_lat_ms)

        train_dist = dict(Counter([r["traffic_class"] for r in train_records]))
        val_dist = dict(Counter([r["traffic_class"] for r in val_records]))
        test_dist = dict(Counter([r["traffic_class"] for r in test_records]))

        models = self.build_models()
        train_results: Dict[str, Dict[str, Any]] = {}
        val_results: Dict[str, Dict[str, Any]] = {}
        latency_results: Dict[str, Dict[str, float]] = {}
        model_sizes: Dict[str, Dict[str, Any]] = {}

        # STAGE 1: Train & Evaluate on Validation Set
        logger.info("=== STAGE 1: Model Training & Validation Evaluation ===")
        for model_name, model in models.items():
            t0 = time.perf_counter()
            model.fit(x_train, y_train, classes=classes)
            train_time = round(time.perf_counter() - t0, 4)

            # Validation metrics
            val_preds = model.predict(x_val)
            val_metrics = compute_multiclass_metrics(y_val, np.array(val_preds), classes)

            # Profile inference latency
            lat = benchmark_inference_latency(model, x_val, warmup_runs=50, benchmark_runs=500)

            # Model serialization size
            model_path = self.models_dir / f"{model_name}.joblib"
            model.save(model_path)
            size_bytes = model_path.stat().st_size if model_path.exists() else 0

            train_results[model_name] = {"training_time_s": train_time}
            val_results[model_name] = val_metrics
            latency_results[model_name] = lat
            model_sizes[model_name] = {
                "bytes": size_bytes,
                "kb": round(size_bytes / 1024.0, 2),
                "mb": round(size_bytes / (1024.0 * 1024.0), 4),
            }

            logger.info(
                "[%s] Train Time: %.4fs | Val Acc: %.4f | Val Macro-F1: %.4f | Val Bal-Acc: %.4f | Inf Lat: %.4fms | Size: %.2fKB",
                model_name,
                train_time,
                val_metrics["accuracy"],
                val_metrics["macro_f1"],
                val_metrics["balanced_accuracy"],
                lat["mean_ms"],
                model_sizes[model_name]["kb"],
            )

        # STAGE 2: Model Selection (Validation Data Only)
        logger.info("=== STAGE 2: Validation-Based Model Selection ===")
        # Rank by Validation Macro-F1 (primary metric), breaking ties with Balanced Accuracy
        ranked_models = sorted(
            val_results.keys(),
            key=lambda m: (val_results[m]["macro_f1"], val_results[m]["balanced_accuracy"]),
            reverse=True,
        )
        selected_winner = ranked_models[0]
        logger.info(
            "Selected Winner based on Validation Macro-F1: '%s' (Val Macro-F1: %.4f, Val Acc: %.4f)",
            selected_winner,
            val_results[selected_winner]["macro_f1"],
            val_results[selected_winner]["accuracy"],
        )
        logger.info("Configuration is LOCKED for final held-out test evaluation.")

        # STAGE 3: Evaluate on Locked Test Set
        logger.info("=== STAGE 3: Final Locked Test Set Evaluation ===")
        test_results: Dict[str, Dict[str, Any]] = {}
        for model_name, model in models.items():
            test_preds = model.predict(x_test)
            t_metrics = compute_multiclass_metrics(y_test, np.array(test_preds), classes)
            test_results[model_name] = t_metrics
            logger.info(
                "[%s] Test Acc: %.4f | Test Macro-F1: %.4f | Test Bal-Acc: %.4f | Test Weighted-F1: %.4f",
                model_name,
                t_metrics["accuracy"],
                t_metrics["macro_f1"],
                t_metrics["balanced_accuracy"],
                t_metrics["weighted_f1"],
            )

        # STAGE 4: Write Result Tables
        logger.info("=== STAGE 4: Persisting Results & Artifacts ===")
        self._write_summary_table(
            models=models,
            meta=meta,
            classes=classes,
            train_dist=train_dist,
            val_dist=val_dist,
            test_dist=test_dist,
            train_results=train_results,
            val_results=val_results,
            test_results=test_results,
            latency_results=latency_results,
            model_sizes=model_sizes,
            feat_lat_ms=feat_lat_ms,
            selected_winner=selected_winner,
        )

        self._write_per_class_table(
            models=models,
            classes=classes,
            val_results=val_results,
            test_results=test_results,
        )

        # STAGE 5: Render Figures
        self._render_figures(
            classes=classes,
            models=models,
            val_results=val_results,
            test_results=test_results,
            latency_results=latency_results,
            model_sizes=model_sizes,
            selected_winner=selected_winner,
        )

        summary_output = {
            "experiment_id": "EXP-R09",
            "git_version": self.git_rev,
            "dataset_version": meta["version"],
            "selected_winner": selected_winner,
            "val_results": val_results,
            "test_results": test_results,
            "latency": latency_results,
            "model_sizes": model_sizes,
            "feature_extraction_latency_ms": feat_lat_ms,
        }
        logger.info("Research Baseline Benchmark complete. Results written to %s", self.output_dir)
        return summary_output

    def _write_summary_table(
        self,
        models: Dict[str, Any],
        meta: Dict[str, Any],
        classes: List[str],
        train_dist: Dict[str, int],
        val_dist: Dict[str, int],
        test_dist: Dict[str, int],
        train_results: Dict[str, Dict[str, Any]],
        val_results: Dict[str, Dict[str, Any]],
        test_results: Dict[str, Dict[str, Any]],
        latency_results: Dict[str, Dict[str, float]],
        model_sizes: Dict[str, Dict[str, Any]],
        feat_lat_ms: float,
        selected_winner: str,
    ) -> None:
        """Writes results/tables/research_baseline.csv."""
        summary_path = self.tables_dir / "research_baseline.csv"
        fieldnames = [
            "experiment_id",
            "git_version",
            "dataset_version",
            "dataset_origin",
            "feature_profile",
            "model",
            "hyperparameters",
            "random_seed",
            "split_strategy",
            "train_count",
            "validation_count",
            "test_count",
            "train_class_distribution",
            "val_class_distribution",
            "test_class_distribution",
            "training_time_s",
            "val_accuracy",
            "val_macro_precision",
            "val_macro_recall",
            "val_macro_f1",
            "val_weighted_f1",
            "val_balanced_accuracy",
            "test_accuracy",
            "test_macro_precision",
            "test_macro_recall",
            "test_macro_f1",
            "test_weighted_f1",
            "test_balanced_accuracy",
            "mean_inference_latency_ms",
            "median_inference_latency_ms",
            "p95_inference_latency_ms",
            "p99_inference_latency_ms",
            "feature_extraction_latency_ms",
            "model_size_bytes",
            "model_size_kb",
            "model_size_mb",
            "is_selected_winner",
        ]

        rows: List[Dict[str, Any]] = []
        for model_name, model in models.items():
            vr = val_results[model_name]
            tr = test_results[model_name]
            lat = latency_results[model_name]
            ms = model_sizes[model_name]
            is_winner = (model_name == selected_winner)

            rows.append({
                "experiment_id": f"EXP-R09-{model_name.upper()}",
                "git_version": self.git_rev,
                "dataset_version": meta["version"],
                "dataset_origin": meta["origin"],
                "feature_profile": "baseline_21_zero_payload",
                "model": model_name,
                "hyperparameters": json.dumps(model.params, sort_keys=True),
                "random_seed": self.seed,
                "split_strategy": "group_aware_session_stratified_70_15_15",
                "train_count": sum(train_dist.values()),
                "validation_count": sum(val_dist.values()),
                "test_count": sum(test_dist.values()),
                "train_class_distribution": json.dumps(train_dist, sort_keys=True),
                "val_class_distribution": json.dumps(val_dist, sort_keys=True),
                "test_class_distribution": json.dumps(test_dist, sort_keys=True),
                "training_time_s": train_results[model_name]["training_time_s"],
                "val_accuracy": vr["accuracy"],
                "val_macro_precision": vr["macro_precision"],
                "val_macro_recall": vr["macro_recall"],
                "val_macro_f1": vr["macro_f1"],
                "val_weighted_f1": vr["weighted_f1"],
                "val_balanced_accuracy": vr["balanced_accuracy"],
                "test_accuracy": tr["accuracy"],
                "test_macro_precision": tr["macro_precision"],
                "test_macro_recall": tr["macro_recall"],
                "test_macro_f1": tr["macro_f1"],
                "test_weighted_f1": tr["weighted_f1"],
                "test_balanced_accuracy": tr["balanced_accuracy"],
                "mean_inference_latency_ms": lat["mean_ms"],
                "median_inference_latency_ms": lat["median_ms"],
                "p95_inference_latency_ms": lat["p95_ms"],
                "p99_inference_latency_ms": lat["p99_ms"],
                "feature_extraction_latency_ms": feat_lat_ms,
                "model_size_bytes": ms["bytes"],
                "model_size_kb": ms["kb"],
                "model_size_mb": ms["mb"],
                "is_selected_winner": "YES" if is_winner else "NO",
            })

        with open(summary_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        logger.info("Saved summary table to %s", summary_path)

    def _write_per_class_table(
        self,
        models: Dict[str, Any],
        classes: List[str],
        val_results: Dict[str, Dict[str, Any]],
        test_results: Dict[str, Dict[str, Any]],
    ) -> None:
        """Writes results/tables/research_baseline_per_class.csv."""
        per_class_path = self.tables_dir / "research_baseline_per_class.csv"
        fieldnames = [
            "experiment_id",
            "model",
            "split",
            "traffic_class",
            "support",
            "precision",
            "recall",
            "f1_score",
        ]

        rows: List[Dict[str, Any]] = []
        for model_name in models.keys():
            for split_name, res in [("validation", val_results[model_name]), ("test", test_results[model_name])]:
                for cls_name, metrics in res["per_class"].items():
                    rows.append({
                        "experiment_id": f"EXP-R09-{model_name.upper()}",
                        "model": model_name,
                        "split": split_name,
                        "traffic_class": cls_name,
                        "support": metrics["support"],
                        "precision": metrics["precision"],
                        "recall": metrics["recall"],
                        "f1_score": metrics["f1"],
                    })

        with open(per_class_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        logger.info("Saved per-class table to %s", per_class_path)

    def _render_figures(
        self,
        classes: List[str],
        models: Dict[str, Any],
        val_results: Dict[str, Dict[str, Any]],
        test_results: Dict[str, Dict[str, Any]],
        latency_results: Dict[str, Dict[str, float]],
        model_sizes: Dict[str, Dict[str, Any]],
        selected_winner: str,
    ) -> None:
        """Renders confusion matrices and model comparison figures using matplotlib."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # 1. Confusion Matrices (2x2 grid for all models on Test split)
        fig, axes = plt.subplots(2, 2, figsize=(13, 11))
        model_keys = list(models.keys())

        for idx, model_name in enumerate(model_keys):
            ax = axes[idx // 2, idx % 2]
            matrix = np.array(test_results[model_name]["confusion_matrix"])
            im = ax.imshow(matrix, interpolation="nearest", cmap="Blues")

            title_suffix = " (Selected Winner)" if model_name == selected_winner else ""
            ax.set_title(f"{model_name.replace('_', ' ').title()}{title_suffix}\nTest Macro-F1: {test_results[model_name]['macro_f1']:.4f}", fontsize=11, fontweight="bold")
            ax.set_xticks(range(len(classes)))
            ax.set_yticks(range(len(classes)))
            ax.set_xticklabels(classes, rotation=35, ha="right", fontsize=9)
            ax.set_yticklabels(classes, fontsize=9)
            ax.set_xlabel("Predicted Class", fontsize=10)
            ax.set_ylabel("True Class", fontsize=10)

            # Annotate numbers
            thresh = matrix.max() / 2.0 if matrix.max() > 0 else 1
            for i in range(len(classes)):
                for j in range(len(classes)):
                    color = "white" if matrix[i, j] > thresh else "black"
                    ax.text(j, i, str(matrix[i, j]), ha="center", va="center", color=color, fontsize=9)

            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

        plt.suptitle("Research Baseline: Held-Out Test Set Confusion Matrices\n(dataset_v2, Group-Aware Session Split)", fontsize=13, fontweight="bold", y=0.98)
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        cm_path = self.figures_dir / "research_baseline_confusion_matrix.png"
        plt.savefig(cm_path, dpi=300)
        plt.close()
        logger.info("Saved confusion matrix figure to %s", cm_path)

        # 2. Model Comparison Bar Charts (Macro F1, Accuracy, Latency, Footprint)
        fig, axes = plt.subplots(2, 2, figsize=(13, 10))
        names = [m.replace("_", " ").title() for m in model_keys]
        x = np.arange(len(names))
        width = 0.35

        # Panel A: Macro F1 (Val vs Test)
        ax = axes[0, 0]
        val_f1 = [val_results[m]["macro_f1"] for m in model_keys]
        test_f1 = [test_results[m]["macro_f1"] for m in model_keys]
        ax.bar(x - width / 2, val_f1, width, label="Validation (Selection)", color="#2b5c8f", alpha=0.85)
        ax.bar(x + width / 2, test_f1, width, label="Held-Out Test (Locked)", color="#e27c38", alpha=0.85)
        ax.set_ylabel("Macro F1-Score", fontsize=10, fontweight="bold")
        ax.set_title("(a) Macro F1 Generalization Comparison", fontsize=11, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(names, fontsize=9)
        ax.set_ylim(0, max(max(val_f1), max(test_f1), 0.3) * 1.25)
        ax.grid(axis="y", linestyle="--", alpha=0.5)
        ax.legend(loc="upper right", fontsize=8)

        # Panel B: Accuracy (Val vs Test)
        ax = axes[0, 1]
        val_acc = [val_results[m]["accuracy"] for m in model_keys]
        test_acc = [test_results[m]["accuracy"] for m in model_keys]
        ax.bar(x - width / 2, val_acc, width, label="Validation", color="#38761d", alpha=0.85)
        ax.bar(x + width / 2, test_acc, width, label="Test", color="#8f3985", alpha=0.85)
        ax.set_ylabel("Accuracy", fontsize=10, fontweight="bold")
        ax.set_title("(b) Classification Accuracy", fontsize=11, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(names, fontsize=9)
        ax.set_ylim(0, max(max(val_acc), max(test_acc), 0.3) * 1.25)
        ax.grid(axis="y", linestyle="--", alpha=0.5)
        ax.legend(loc="upper right", fontsize=8)

        # Panel C: Inference Latency (Mean, P95, P99)
        ax = axes[1, 0]
        w_sub = 0.25
        mean_lats = [latency_results[m]["mean_ms"] for m in model_keys]
        p95_lats = [latency_results[m]["p95_ms"] for m in model_keys]
        p99_lats = [latency_results[m]["p99_ms"] for m in model_keys]
        ax.bar(x - w_sub, mean_lats, w_sub, label="Mean Latency", color="#4582ec", alpha=0.85)
        ax.bar(x, p95_lats, w_sub, label="P95 Latency", color="#f0ad4e", alpha=0.85)
        ax.bar(x + w_sub, p99_lats, w_sub, label="P99 Latency", color="#d9534f", alpha=0.85)
        ax.set_ylabel("Latency (ms per flow)", fontsize=10, fontweight="bold")
        ax.set_title("(c) Single-Flow Inference Latency", fontsize=11, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(names, fontsize=9)
        ax.grid(axis="y", linestyle="--", alpha=0.5)
        ax.legend(loc="upper left", fontsize=8)

        # Panel D: Serialized Footprint (KB)
        ax = axes[1, 1]
        sizes_kb = [model_sizes[m]["kb"] for m in model_keys]
        bars = ax.bar(x, sizes_kb, width=0.5, color="#5bc0de", alpha=0.85, edgecolor="#2b5c8f")
        ax.set_ylabel("Disk Size (KB)", fontsize=10, fontweight="bold")
        ax.set_title("(d) Serialized Model Footprint", fontsize=11, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(names, fontsize=9)
        ax.grid(axis="y", linestyle="--", alpha=0.5)
        for b in bars:
            h = b.get_height()
            ax.annotate(f"{h:.1f} KB", xy=(b.get_x() + b.get_width() / 2, h), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8)

        plt.suptitle("Research Baseline Model Performance & Efficiency\n(dataset_v2, 21 Zero-Payload Statistical Features)", fontsize=13, fontweight="bold", y=0.98)
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        comp_path = self.figures_dir / "research_baseline_model_comparison.png"
        plt.savefig(comp_path, dpi=300)
        plt.close()
        logger.info("Saved model comparison figure to %s", comp_path)


def asdict_meta(meta: Any) -> Dict[str, Any]:
    """Serializes dataset metadata to dictionary."""
    return {
        "dataset_id": meta.dataset_id,
        "version": meta.version,
        "origin": meta.origin.value if hasattr(meta.origin, "value") else str(meta.origin),
        "source_description": meta.source_description,
        "primary_feature_path": meta.primary_feature_path,
        "session_count": meta.session_count,
        "flow_count": meta.flow_count,
        "traffic_classes": meta.traffic_classes,
        "feature_schema": meta.feature_schema,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reproducible research baseline benchmark.")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--dataset", type=str, default="dataset_v2", help="Registered dataset ID to benchmark")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--output-dir", type=str, default="results", help="Directory for output tables and figures")
    args = parser.parse_args()

    runner = ResearchBaselineExperiment(
        config_path=args.config,
        dataset_id=args.dataset,
        seed=args.seed,
        output_dir=args.output_dir,
    )
    runner.run()


if __name__ == "__main__":
    main()
