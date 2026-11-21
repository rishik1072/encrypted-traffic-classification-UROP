"""
External Benchmark Engine for Encrypted Traffic Models.

Evaluates:
- Logistic Regression
- Decision Tree
- Random Forest
- LightGBM
- Sequence Baseline (N-gram Sequence Classifier)

Computes:
- Macro-F1 and Balanced Accuracy.
- Per-class Precision, Recall, and F1.
- Calibration: Brier Score and Expected Calibration Error (ECE).
- Selective Classification: Risk-Coverage curves under confidence thresholds.
- Early Prefix Degradation: Performance across K = 3, 5, 10, 20, 30.
- Inference Latency: p50, p95, p99 microsecond measurements per prediction.
- Saves separated evaluation artifacts under results/external_benchmarks/<dataset_id>/.
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    classification_report,
    f1_score,
)
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier

from research.external_datasets.schemas import (
    BenchmarkModelResult,
    FeatureProfileType,
)

logger = logging.getLogger("research.external_datasets.benchmark_engine")


class SequenceNgramClassifier:
    """Lightweight sequence n-gram baseline for directional packet sequences."""

    def __init__(self, ngram_range: Tuple[int, int] = (1, 3)) -> None:
        self.ngram_range = ngram_range
        self.vocab: Dict[str, int] = {}
        self.clf = LogisticRegression(max_iter=500, random_state=42)
        self.classes_: np.ndarray = np.array([])

    def _seq_to_ngrams(self, seq_row: np.ndarray) -> str:
        tokens = [str(int(x)) for x in seq_row if not np.isnan(x)]
        return " ".join(tokens)

    def fit(self, X: np.ndarray, y: np.ndarray) -> SequenceNgramClassifier:
        from sklearn.feature_extraction.text import CountVectorizer

        corpus = [self._seq_to_ngrams(row) for row in X]
        self.vectorizer = CountVectorizer(ngram_range=self.ngram_range, token_pattern=r"\S+")
        X_vec = self.vectorizer.fit_transform(corpus)
        self.clf.fit(X_vec, y)
        self.classes_ = self.clf.classes_
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        corpus = [self._seq_to_ngrams(row) for row in X]
        X_vec = self.vectorizer.transform(corpus)
        return self.clf.predict(X_vec)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        corpus = [self._seq_to_ngrams(row) for row in X]
        X_vec = self.vectorizer.transform(corpus)
        return self.clf.predict_proba(X_vec)


class ExternalBenchmarkEngine:
    """
    Standardized benchmark evaluation runner across external datasets.
    """

    def __init__(self, results_root: Path = Path("results/external_benchmarks")) -> None:
        self.results_root = Path(results_root)
        self.results_root.mkdir(parents=True, exist_ok=True)

    def get_model(self, model_name: str) -> Any:
        """Instantiates supported baseline models with reproducible random states."""
        name_lower = model_name.lower().strip()
        if name_lower in ("lr", "logistic_regression"):
            return LogisticRegression(max_iter=500, random_state=42)
        elif name_lower in ("dt", "decision_tree"):
            return DecisionTreeClassifier(max_depth=12, random_state=42)
        elif name_lower in ("rf", "random_forest"):
            return RandomForestClassifier(n_estimators=100, max_depth=16, random_state=42, n_jobs=-1)
        elif name_lower in ("lgbm", "lightgbm"):
            try:
                import lightgbm as lgb
                return lgb.LGBMClassifier(
                    n_estimators=100,
                    max_depth=8,
                    random_state=42,
                    verbose=-1,
                    n_jobs=-1,
                )
            except ImportError:
                logger.warning("LightGBM not available, falling back to RandomForest.")
                return RandomForestClassifier(n_estimators=100, random_state=42)
        elif name_lower in ("seq", "sequence_ngram", "fasttext_proxy"):
            return SequenceNgramClassifier()
        else:
            raise ValueError(f"Unsupported benchmark model: '{model_name}'")

    @classmethod
    def compute_calibration_ece(
        cls, probs: np.ndarray, y_true: np.ndarray, classes: np.ndarray, n_bins: int = 10
    ) -> float:
        """Computes Expected Calibration Error (ECE) across confidence bins."""
        if len(probs) == 0:
            return 0.0

        confidences = np.max(probs, axis=1)
        pred_indices = np.argmax(probs, axis=1)
        predicted_classes = classes[pred_indices]
        accuracies = (predicted_classes == y_true).astype(float)

        bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
        ece = 0.0
        n_samples = len(confidences)

        for i in range(n_bins):
            bin_lower = bin_boundaries[i]
            bin_upper = bin_boundaries[i + 1]
            in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
            prop_in_bin = np.mean(in_bin)

            if prop_in_bin > 0:
                acc_in_bin = np.mean(accuracies[in_bin])
                conf_in_bin = np.mean(confidences[in_bin])
                ece += np.abs(acc_in_bin - conf_in_bin) * (np.sum(in_bin) / n_samples)

        return float(ece)

    @classmethod
    def compute_selective_risk_coverage(
        cls, probs: np.ndarray, y_true: np.ndarray, classes: np.ndarray, n_thresholds: int = 21
    ) -> List[Tuple[float, float, float]]:
        """
        Computes (threshold, coverage, empirical_risk) points across confidence thresholds.
        Empirical risk = 1.0 - accuracy on the accepted (confidence >= threshold) subset.
        """
        confidences = np.max(probs, axis=1)
        pred_indices = np.argmax(probs, axis=1)
        predicted_classes = classes[pred_indices]
        correct = (predicted_classes == y_true)

        thresholds = np.linspace(0.0, 1.0, n_thresholds)
        curve: List[Tuple[float, float, float]] = []

        total_samples = len(confidences)
        for tau in thresholds:
            accepted = confidences >= tau
            coverage = float(np.sum(accepted)) / float(total_samples) if total_samples > 0 else 0.0

            if np.sum(accepted) > 0:
                acc_accepted = float(np.mean(correct[accepted]))
                risk = 1.0 - acc_accepted
            else:
                risk = 0.0

            curve.append((float(tau), coverage, risk))

        return curve

    def evaluate_model(
        self,
        model_name: str,
        dataset_id: str,
        feature_profile: FeatureProfileType,
        prefix_k: int,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
    ) -> BenchmarkModelResult:
        """
        Fits the model and computes full benchmark evaluation metrics.
        """
        model = self.get_model(model_name)
        logger.info("Training %s on %s (K=%d, samples=%d)...", model_name, dataset_id, prefix_k, len(X_train))

        model.fit(X_train, y_train)

        # 1. Inference Latency Measurement (microsecond resolution)
        latencies_us: List[float] = []
        n_eval = min(500, len(X_test))
        for i in range(n_eval):
            sample = X_test[i : i + 1]
            t0 = time.perf_counter()
            _ = model.predict(sample)
            t1 = time.perf_counter()
            latencies_us.append((t1 - t0) * 1_000_000)

        p50 = float(np.percentile(latencies_us, 50)) if latencies_us else 0.0
        p95 = float(np.percentile(latencies_us, 95)) if latencies_us else 0.0
        p99 = float(np.percentile(latencies_us, 99)) if latencies_us else 0.0

        # 2. Complete Predictions & Probabilities
        y_pred = model.predict(X_test)
        probs = model.predict_proba(X_test) if hasattr(model, "predict_proba") else None
        classes = model.classes_ if hasattr(model, "classes_") else np.unique(y_train)

        # 3. Macro and Balanced Accuracy
        macro_f1 = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
        balanced_acc = float(balanced_accuracy_score(y_test, y_pred))
        acc = float(accuracy_score(y_test, y_pred))

        # 4. Detailed Per-Class Precision, Recall, F1
        report_dict = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
        per_class_p: Dict[str, float] = {}
        per_class_r: Dict[str, float] = {}
        per_class_f1: Dict[str, float] = {}

        for cls_label, metrics in report_dict.items():
            if isinstance(metrics, dict) and cls_label not in ("macro avg", "weighted avg"):
                per_class_p[str(cls_label)] = float(metrics.get("precision", 0.0))
                per_class_r[str(cls_label)] = float(metrics.get("recall", 0.0))
                per_class_f1[str(cls_label)] = float(metrics.get("f1-score", 0.0))

        # 5. Calibration & Selective Risk
        ece = None
        brier = None
        selective_curve: List[Tuple[float, float, float]] = []

        if probs is not None:
            ece = self.compute_calibration_ece(probs, y_test, classes)
            selective_curve = self.compute_selective_risk_coverage(probs, y_test, classes)

            # Multiclass Brier score approximation: mean squared error between one-hot true and probs
            try:
                y_true_indices = np.array([np.where(classes == y)[0][0] for y in y_test])
                one_hot = np.zeros_like(probs)
                one_hot[np.arange(len(y_test)), y_true_indices] = 1.0
                brier = float(np.mean(np.sum((probs - one_hot) ** 2, axis=1)))
            except Exception:
                brier = None

        result = BenchmarkModelResult(
            model_name=model_name,
            dataset_id=dataset_id,
            feature_profile=feature_profile,
            prefix_k=prefix_k,
            train_sample_count=len(X_train),
            test_sample_count=len(X_test),
            macro_f1=macro_f1,
            balanced_accuracy=balanced_acc,
            accuracy=acc,
            brier_score=brier,
            expected_calibration_error=ece,
            inference_latency_p50_us=p50,
            inference_latency_p95_us=p95,
            inference_latency_p99_us=p99,
            per_class_precision=per_class_p,
            per_class_recall=per_class_r,
            per_class_f1=per_class_f1,
            selective_risk_coverage_curve=selective_curve,
        )

        # Save result to isolated output path
        self._save_result(result)
        return result

    def _save_result(self, result: BenchmarkModelResult) -> Path:
        """Saves evaluation results in dataset-isolated directory."""
        ds_dir = self.results_root / result.dataset_id
        ds_dir.mkdir(parents=True, exist_ok=True)
        ts_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_file = ds_dir / f"{result.model_name}_k{result.prefix_k}_{ts_slug}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2)
        logger.info("Saved benchmark evaluation to: %s", out_file)
        return out_file
