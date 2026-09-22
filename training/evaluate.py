"""
Comprehensive Model Evaluation and Metrics Computation.

Calculates Accuracy, Macro/Weighted Precision, Recall, F1, Per-Class Breakdown,
Confusion Matrix heatmaps, and persists metrics to results/tables/ and results/figures/.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import yaml

from models.base_model import BaseTrafficClassifier

logger = logging.getLogger(__name__)


def compute_metrics(
    y_true: Any,
    y_pred: Any,
    class_names: List[str],
) -> Dict[str, Any]:
    """
    Computes comprehensive multiclass metrics without requiring scikit-learn.
    Supports pure Python list / numpy formats.
    """
    n_samples = len(y_true)
    if n_samples == 0:
        return {}

    n_classes = len(class_names)
    matrix = [[0 for _ in range(n_classes)] for _ in range(n_classes)]

    for t, p in zip(y_true, y_pred):
        t_idx = int(t)
        p_idx = int(p)
        if 0 <= t_idx < n_classes and 0 <= p_idx < n_classes:
            matrix[t_idx][p_idx] += 1

    # Total correct
    correct = sum(matrix[i][i] for i in range(n_classes))
    accuracy = correct / n_samples

    per_class_precision = []
    per_class_recall = []
    per_class_f1 = []
    class_support = []

    for i in range(n_classes):
        tp = matrix[i][i]
        fp = sum(matrix[r][i] for r in range(n_classes) if r != i)
        fn = sum(matrix[i][c] for c in range(n_classes) if c != i)
        support = sum(matrix[i])
        class_support.append(support)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        per_class_precision.append(prec)
        per_class_recall.append(rec)
        per_class_f1.append(f1)

    # Macro Averages
    macro_precision = sum(per_class_precision) / n_classes if n_classes > 0 else 0.0
    macro_recall = sum(per_class_recall) / n_classes if n_classes > 0 else 0.0
    macro_f1 = sum(per_class_f1) / n_classes if n_classes > 0 else 0.0

    # Weighted Averages
    total_support = sum(class_support)
    if total_support > 0:
        weighted_precision = sum(p * s for p, s in zip(per_class_precision, class_support)) / total_support
        weighted_recall = sum(r * s for r, s in zip(per_class_recall, class_support)) / total_support
        weighted_f1 = sum(f * s for f, s in zip(per_class_f1, class_support)) / total_support
    else:
        weighted_precision = 0.0
        weighted_recall = 0.0
        weighted_f1 = 0.0

    return {
        "accuracy": round(accuracy, 4),
        "precision_macro": round(macro_precision, 4),
        "recall_macro": round(macro_recall, 4),
        "f1_macro": round(macro_f1, 4),
        "precision_weighted": round(weighted_precision, 4),
        "recall_weighted": round(weighted_recall, 4),
        "f1_weighted": round(weighted_f1, 4),
        "confusion_matrix": matrix,
        "per_class": {
            class_names[i]: {
                "precision": round(per_class_precision[i], 4),
                "recall": round(per_class_recall[i], 4),
                "f1": round(per_class_f1[i], 4),
                "support": class_support[i],
            }
            for i in range(n_classes)
        },
    }


def plot_confusion_matrix(
    matrix: List[List[int]],
    class_names: List[str],
    output_path: Path,
    model_name: str,
) -> None:
    """Renders confusion matrix heatmap using matplotlib if available."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(6.5, 5.5))
        cax = ax.matshow(matrix, cmap="Blues", alpha=0.85)

        for i in range(len(class_names)):
            for j in range(len(class_names)):
                ax.text(
                    j, i, str(matrix[i][j]),
                    va="center", ha="center",
                    color="black" if matrix[i][j] < (max(map(max, matrix)) / 2 or 1) else "white",
                    fontweight="bold",
                )

        fig.colorbar(cax)
        ax.set_xticks(range(len(class_names)))
        ax.set_yticks(range(len(class_names)))
        ax.set_xticklabels(class_names, rotation=45, ha="left")
        ax.set_yticklabels(class_names)
        ax.set_xlabel("Predicted Label", fontweight="bold", labelpad=10)
        ax.set_ylabel("True Label", fontweight="bold")
        ax.set_title(f"Confusion Matrix: {model_name}", fontweight="bold", pad=20)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()
    except ImportError:
        logger.info("Matplotlib not installed. Confusion matrix figure generation skipped.")


def evaluate_trained_models(
    models: Dict[str, BaseTrafficClassifier],
    x_test: Any,
    y_test: Any,
    class_names: List[str],
    figures_dir: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    """Evaluates multiple trained models on the test set and exports confusion matrices."""
    results = {}
    fig_dir = figures_dir or Path("results/figures/confusion_matrices")

    for name, model in models.items():
        y_pred = model.predict(x_test)
        metrics = compute_metrics(y_test, y_pred, class_names)
        results[name] = metrics

        plot_path = fig_dir / f"confusion_matrix_{name}.png"
        plot_confusion_matrix(metrics["confusion_matrix"], class_names, plot_path, name)
        logger.info(
            "Model %s Test Evaluation: Acc=%.4f, Macro-F1=%.4f, Weighted-F1=%.4f",
            name, metrics["accuracy"], metrics["f1_macro"], metrics["f1_weighted"]
        )

    return results
