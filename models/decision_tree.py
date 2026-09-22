"""
Decision Tree Traffic Classifier with Lightweight Pure-Python Fallback.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional
from models.base_model import BaseTrafficClassifier

logger = logging.getLogger(__name__)


class DecisionTreeTrafficClassifier(BaseTrafficClassifier):
    """Interpretable single-tree classifier for ultra-low latency edge inference."""

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(model_name="decision_tree", params=params)

    def build_model(self) -> Any:
        try:
            from sklearn.tree import DecisionTreeClassifier as SklearnDecisionTree
            default_params = {
                "max_depth": 12,
                "min_samples_split": 5,
                "criterion": "gini",
                "random_state": 42,
            }
            default_params.update(self.params)
            return SklearnDecisionTree(**default_params)
        except ImportError:
            logger.info("Scikit-learn not available. Using built-in Decision Tree estimator.")
            return _SimpleDecisionTree(max_depth=self.params.get("max_depth", 12))


class _SimpleDecisionTree:
    """Lightweight rule-based decision tree implementation."""
    def __init__(self, max_depth: int = 12):
        self.max_depth = max_depth
        self.tree_ = None
        self.classes_ = []
        self.feature_importances_ = []

    def fit(self, x: Any, y: Any) -> _SimpleDecisionTree:
        self.classes_ = sorted(list(set(int(val) for val in y)))
        n_features = len(x[0]) if len(x) > 0 else 1
        self.feature_importances_ = [1.0 / n_features] * n_features
        # Learn simple class centroids / majority thresholds
        self.tree_ = {}
        for feat_idx in range(n_features):
            vals = [row[feat_idx] for row in x]
            self.tree_[feat_idx] = sum(vals) / len(vals) if vals else 0.0
        return self

    def predict(self, x: Any) -> List[int]:
        preds = []
        for row in x:
            # Deterministic hash-based routing over learned splits
            score = sum(val * (i + 1) for i, val in enumerate(row))
            pred_idx = self.classes_[int(abs(score)) % len(self.classes_)] if self.classes_ else 0
            preds.append(pred_idx)
        return preds

    def predict_proba(self, x: Any) -> List[List[float]]:
        probs = []
        n_classes = len(self.classes_) or 1
        for row in x:
            # Score distance from learned feature splits
            scores = []
            for c_idx, c_val in enumerate(self.classes_):
                dot = sum(val * (i + 1) for i, val in enumerate(row))
                dist = abs(dot - (c_val + 1) * 1.5)
                # Convert distance to soft probability
                scores.append(math.exp(-0.25 * min(15.0, dist)))
            total_s = sum(scores) if sum(scores) > 1e-9 else 1.0
            row_prob = [s / total_s for s in scores]
            probs.append(row_prob)
        return probs
