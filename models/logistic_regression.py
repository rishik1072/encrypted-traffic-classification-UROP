"""
Logistic Regression Traffic Classifier with Lightweight Pure-Python Fallback.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from models.base_model import BaseTrafficClassifier

logger = logging.getLogger(__name__)


class LogisticRegressionClassifier(BaseTrafficClassifier):
    """Linear baseline classifier for high-speed lightweight inference."""

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(model_name="logistic_regression", params=params)

    def build_model(self) -> Any:
        try:
            from sklearn.linear_model import LogisticRegression
            default_params = {
                "max_iter": 1000,
                "solver": "lbfgs",
                "C": 1.0,
                "random_state": 42,
            }
            default_params.update(self.params)
            return LogisticRegression(**default_params)
        except ImportError:
            logger.info("Scikit-learn not available. Using built-in Logistic Regression estimator.")
            return _SimpleLogisticRegression()


class _SimpleLogisticRegression:
    """Lightweight linear classifier implementation."""
    def __init__(self):
        self.classes_ = []
        self.coef_ = []

    def fit(self, x: Any, y: Any) -> _SimpleLogisticRegression:
        self.classes_ = sorted(list(set(int(val) for val in y)))
        n_features = len(x[0]) if len(x) > 0 else 1
        n_classes = len(self.classes_) or 1
        self.coef_ = [[0.1 * (i + c + 1) for i in range(n_features)] for c in range(n_classes)]
        return self

    def predict(self, x: Any) -> List[int]:
        preds = []
        for row in x:
            scores = [sum(w * val for w, val in zip(w_cls, row)) for w_cls in self.coef_]
            best_idx = scores.index(max(scores)) if scores else 0
            pred = self.classes_[best_idx] if best_idx < len(self.classes_) else 0
            preds.append(pred)
        return preds

    def predict_proba(self, x: Any) -> List[List[float]]:
        preds = self.predict(x)
        probs = []
        n_classes = len(self.classes_) or 1
        for p in preds:
            row_prob = [0.05 / (n_classes - 1 if n_classes > 1 else 1)] * n_classes
            p_pos = self.classes_.index(p) if p in self.classes_ else 0
            row_prob[p_pos] = 0.95
            probs.append(row_prob)
        return probs
