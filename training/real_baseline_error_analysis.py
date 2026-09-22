"""
Real Baseline Error Analysis Module.

Provides detailed sample-level error breakdowns for held-out test predictions:
- Identifies misclassified flows, true labels, predicted labels, confidence scores, and sessions
- Analyzes class confusion matrices and failure modes
- Exports results/tables/real_baseline_error_analysis.csv
"""

from __future__ import annotations

import csv
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from models.base_model import BaseTrafficClassifier

logger = logging.getLogger(__name__)


def perform_real_baseline_error_analysis(
    models: Dict[str, BaseTrafficClassifier],
    test_records: List[Dict[str, Any]],
    x_test: Any,
    y_test: Any,
    class_names: List[str],
    output_path: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Performs detailed error analysis on the held-out test set for every model.
    """
    out_file = output_path or Path("results/tables/real_baseline_error_analysis.csv")
    out_file.parent.mkdir(parents=True, exist_ok=True)

    misclassifications: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {}

    for model_name, clf in models.items():
        preds = clf.predict(x_test)
        has_proba = hasattr(clf, "predict_proba")
        probs = clf.predict_proba(x_test) if has_proba else None

        model_errors = 0
        confused_pairs = Counter()

        for idx, (t, p, record) in enumerate(zip(y_test, preds, test_records)):
            t_idx = int(t)
            p_idx = int(p)
            true_label = class_names[t_idx] if t_idx < len(class_names) else str(t_idx)
            pred_label = class_names[p_idx] if p_idx < len(class_names) else str(p_idx)

            confidence = 1.0
            if probs is not None:
                try:
                    confidence = float(max(probs[idx]))
                except Exception:
                    confidence = 1.0

            if t_idx != p_idx:
                model_errors += 1
                confused_pairs[f"{true_label} -> {pred_label}"] += 1
                misclassifications.append({
                    "flow_id": record.get("flow_id", f"test_flow_{idx}"),
                    "true_class": true_label,
                    "predicted_class": pred_label,
                    "confidence_if_available": f"{confidence:.4f}",
                    "confidence": f"{confidence:.4f}",
                    "model": model_name,
                    "session_id": record.get("session_id", "unknown_session"),
                    "dst_port": record.get("dst_port", ""),
                    "protocol": record.get("protocol", ""),
                    "total_packets": record.get("total_packet_count", ""),
                    "total_bytes": record.get("total_bytes", ""),
                })

        summary[model_name] = {
            "total_samples": len(y_test),
            "errors": model_errors,
            "error_rate": model_errors / len(y_test) if len(y_test) > 0 else 0.0,
            "confused_pairs": dict(confused_pairs),
        }

    # Aggregate cross-model insights
    flow_mistake_counts = Counter(m["flow_id"] for m in misclassifications)
    repeated_mistakes = {f_id: count for f_id, count in flow_mistake_counts.items() if count > 1}
    difficult_classes = Counter(m["true_class"] for m in misclassifications)

    summary["cross_model_analysis"] = {
        "repeated_mistakes": repeated_mistakes,
        "difficult_classes": dict(difficult_classes),
        "total_misclassifications": len(misclassifications),
    }

    # Save detailed misclassification CSV
    fieldnames = [
        "flow_id",
        "true_class",
        "predicted_class",
        "confidence_if_available",
        "confidence",
        "model",
        "session_id",
        "dst_port",
        "protocol",
        "total_packets",
        "total_bytes",
    ]
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(misclassifications)

    logger.info("Saved real baseline error analysis to %s (%d total error events across all models)", out_file, len(misclassifications))
    return misclassifications, summary

