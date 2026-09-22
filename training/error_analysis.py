"""
Error Analysis and Weakness Identification Module.

Identifies the most frequently confused traffic class pairs, analyzes prediction confidence,
and highlights feature-level ambiguities in results/tables/error_analysis.csv.
"""

from __future__ import annotations

import csv
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.base_model import BaseTrafficClassifier

logger = logging.getLogger(__name__)


def perform_error_analysis(
    models: Dict[str, BaseTrafficClassifier],
    x_test: Any,
    y_test: Any,
    class_names: List[str],
    output_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Performs error analysis across all evaluated models, identifying confused pairs and confidence scores.
    """
    out_file = output_path or Path("results/tables/error_analysis.csv")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    error_records: List[Dict[str, Any]] = []

    for name, clf in models.items():
        y_pred = clf.predict(x_test)
        has_proba = hasattr(clf.model, "predict_proba")
        probs = clf.predict_proba(x_test) if has_proba else None

        confused_pairs = defaultdict(int)
        low_confidence_count = 0
        total_errors = 0

        for idx, (t, p) in enumerate(zip(y_test, y_pred)):
            t_idx = int(t)
            p_idx = int(p)

            if t_idx != p_idx:
                total_errors += 1
                t_label = class_names[t_idx] if t_idx < len(class_names) else str(t_idx)
                p_label = class_names[p_idx] if p_idx < len(class_names) else str(p_idx)
                pair_key = f"{t_label} -> {p_label}"
                confused_pairs[pair_key] += 1

            if probs is not None:
                try:
                    max_prob = float(max(probs[idx]))
                    if max_prob < 0.60:
                        low_confidence_count += 1
                except Exception:
                    pass

        top_confusion = sorted(confused_pairs.items(), key=lambda x: x[1], reverse=True)
        top_confusion_str = "; ".join([f"{k} ({v})" for k, v in top_confusion[:3]]) if top_confusion else "None"

        error_records.append({
            "model": name,
            "total_test_samples": len(y_test),
            "total_misclassifications": total_errors,
            "error_rate": round(total_errors / len(y_test), 4) if len(y_test) > 0 else 0.0,
            "top_confused_pairs": top_confusion_str,
            "low_confidence_predictions": low_confidence_count,
        })

    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "model",
                "total_test_samples",
                "total_misclassifications",
                "error_rate",
                "top_confused_pairs",
                "low_confidence_predictions",
            ],
        )
        writer.writeheader()
        writer.writerows(error_records)

    logger.info("Saved error analysis report to %s", out_file)
    return error_records
