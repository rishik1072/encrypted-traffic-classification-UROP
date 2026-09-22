"""
Abstract Base Classifier for Encrypted Traffic Models.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional
import pickle

logger = logging.getLogger(__name__)


class BaseTrafficClassifier(ABC):
    """
    Uniform base interface for lightweight machine learning models.
    Supports fit, predict, predict_proba, save, and load.
    """

    def __init__(self, model_name: str, params: Optional[Dict[str, Any]] = None) -> None:
        self.model_name = model_name
        self.params = params or {}
        self.model: Any = None
        self.classes_: Optional[List[str]] = None

    @abstractmethod
    def build_model(self) -> Any:
        """Instantiates the underlying estimator using configured hyperparameters."""
        raise NotImplementedError

    def fit(self, x: Any, y: Any, classes: Optional[List[str]] = None) -> BaseTrafficClassifier:
        """Trains the model on features X and labels y."""
        if self.model is None:
            self.model = self.build_model()
        self.classes_ = classes
        logger.info("Training %s classifier on %d samples", self.model_name, len(x))
        self.model.fit(x, y)
        return self

    def predict(self, x: Any) -> Any:
        """Predicts class labels for input feature matrix X."""
        if self.model is None:
            raise RuntimeError(f"{self.model_name} is not initialized or trained.")
        return self.model.predict(x)

    def predict_proba(self, x: Any) -> Any:
        """Predicts class probability distributions for input feature matrix X."""
        if self.model is None:
            raise RuntimeError(f"{self.model_name} is not initialized or trained.")
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(x)
        raise NotImplementedError(f"{self.model_name} does not support probability estimation.")

    def save(self, filepath: str | Path) -> None:
        """Saves model state to disk using joblib or pickle fallback."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"model": self.model, "classes_": self.classes_, "params": self.params}
        try:
            import joblib
            joblib.dump(payload, path)
        except ImportError:
            with open(path, "wb") as f:
                pickle.dump(payload, f)
        logger.info("Saved %s model to %s", self.model_name, path)

    def load(self, filepath: str | Path) -> BaseTrafficClassifier:
        """Loads model state from disk."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")
        try:
            import joblib
            data = joblib.load(path)
        except ImportError:
            with open(path, "rb") as f:
                data = pickle.load(f)
        self.model = data["model"]
        self.classes_ = data.get("classes_")
        self.params = data.get("params", {})
        logger.info("Loaded %s model from %s", self.model_name, path)
        return self
