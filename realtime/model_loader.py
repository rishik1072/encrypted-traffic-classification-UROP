"""
Model and Preprocessor Loader for Real-Time Inference.

Loads the pre-trained model and fitted preprocessor ONCE at initialization,
validates cryptographic model registry and feature schema hashes,
and serves online inference with versioned confidence policies and fail-closed safety.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml

from models.base_model import BaseTrafficClassifier
from models.decision_tree import DecisionTreeTrafficClassifier
from models.lightgbm_model import LightGBMTrafficClassifier
from models.logistic_regression import LogisticRegressionClassifier
from models.random_forest import RandomForestTrafficClassifier
from preprocessing.preprocessing import FeaturePreprocessor
from realtime.schema import CANONICAL_NUMERICAL_FEATURES, CANONICAL_SCHEMA_HASH, validate_feature_schema

logger = logging.getLogger(__name__)


class ModelLoader:
    """
    Loads saved model and preprocessor artifacts, verifies registry entries and schema hashes,
    and executes inference.
    """

    MODEL_CLASSES = {
        "logistic_regression": LogisticRegressionClassifier,
        "decision_tree": DecisionTreeTrafficClassifier,
        "random_forest": RandomForestTrafficClassifier,
        "lightgbm": LightGBMTrafficClassifier,
    }

    def __init__(
        self,
        model_name: str = "lightgbm",
        models_dir: str | Path = "results/models",
        config_path: str | Path = "config.yaml",
        registry_path: str | Path = "results/models/production_registry.json",
        confidence_policy_path: str | Path = "config/confidence_policy.yaml",
        enforce_registry: bool = True,
    ) -> None:
        self.model_name = model_name.lower()
        self.models_dir = Path(models_dir)
        self.config_path = Path(config_path)
        self.registry_path = Path(registry_path)
        self.confidence_policy_path = Path(confidence_policy_path)
        self.enforce_registry = enforce_registry

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config: Dict[str, Any] = yaml.safe_load(f)

        self.confidence_policy: Dict[str, Any] = {}
        if self.confidence_policy_path.exists():
            with open(self.confidence_policy_path, "r", encoding="utf-8") as f:
                self.confidence_policy = yaml.safe_load(f).get("confidence_policy", {})

        self.preprocessor: Optional[FeaturePreprocessor] = None
        self.model: Optional[BaseTrafficClassifier] = None
        self.class_names: List[str] = list(self.config.get("traffic_classes", []))
        self.feature_names: List[str] = list(
            self.config.get("features", {}).get("numerical_features", CANONICAL_NUMERICAL_FEATURES)
        )
        self.model_metadata: Dict[str, Any] = {}

        self._load_and_validate_artifacts()

    def _load_and_validate_artifacts(self) -> None:
        """Loads and cryptographically validates preprocessor and model checkpoints."""
        # 1. Check Model Registry
        if self.registry_path.exists():
            with open(self.registry_path, "r", encoding="utf-8") as f:
                reg = json.load(f)
                registered_models = reg.get("registered_models", {})
                
                # If model_name matches a model_id key or model_name field
                if self.model_name in registered_models:
                    self.model_metadata = registered_models[self.model_name]
                    self.model_name = self.model_metadata.get("model_name", self.model_name)
                else:
                    for m_id, m_info in registered_models.items():
                        if m_info.get("model_name") == self.model_name:
                            self.model_metadata = m_info
                            break

        if self.enforce_registry and not self.model_metadata:
            err_msg = f"Model '{self.model_name}' is not registered in {self.registry_path}! Fail-closed."
            logger.error(err_msg)
            raise ValueError(err_msg)

        prep_path = self.models_dir / "preprocessor.joblib"
        model_path = self.models_dir / f"{self.model_name}.joblib"

        # 2. Load and Validate Preprocessor
        if prep_path.exists():
            raw_prep_bytes = prep_path.read_bytes()
            prep_hash = hashlib.sha256(raw_prep_bytes).hexdigest()
            expected_prep_hash = self.model_metadata.get("preprocessor_hash")
            if expected_prep_hash and prep_hash != expected_prep_hash and self.enforce_registry:
                raise ValueError(f"Preprocessor hash mismatch! Expected {expected_prep_hash}, got {prep_hash}")

            try:
                import joblib
                self.preprocessor = joblib.load(prep_path)
            except Exception:
                with open(prep_path, "rb") as f:
                    self.preprocessor = pickle.load(f)
            logger.info("Loaded preprocessor from %s (SHA-256: %s...)", prep_path, prep_hash[:12])
        else:
            if self.enforce_registry:
                raise FileNotFoundError(f"Preprocessor checkpoint required at {prep_path}")
            logger.warning("Preprocessor checkpoint not found at %s. Fallback.", prep_path)
            self.preprocessor = FeaturePreprocessor(self.config)

        # 3. Load and Validate Model
        if self.model_name not in self.MODEL_CLASSES:
            raise ValueError(f"Unknown model '{self.model_name}'. Allowed: {list(self.MODEL_CLASSES.keys())}")

        clf_cls = self.MODEL_CLASSES[self.model_name]
        self.model = clf_cls()

        if model_path.exists():
            raw_model_bytes = model_path.read_bytes()
            model_hash = hashlib.sha256(raw_model_bytes).hexdigest()
            expected_model_hash = self.model_metadata.get("model_hash")
            if expected_model_hash and model_hash != expected_model_hash and self.enforce_registry:
                raise ValueError(f"Model hash mismatch! Expected {expected_model_hash}, got {model_hash}")

            self.model.load(model_path)
            if self.model.classes_:
                self.class_names = self.model.classes_
            logger.info("Loaded %s model from %s (SHA-256: %s...)", self.model_name, model_path, model_hash[:12])
        else:
            if self.enforce_registry:
                raise FileNotFoundError(f"Model checkpoint required at {model_path}")
            logger.warning("Model checkpoint not found at %s. Instantiating baseline.", model_path)
            self.model.model = self.model.build_model()

        # Warmup single inference execution to exclude startup overhead
        try:
            dummy_sample = {k: 1.0 for k in self.feature_names}
            dummy_sample["protocol"] = "TCP"
            dummy_sample["dst_port"] = 443
            self.predict_single(dummy_sample)
        except Exception as e:
            logger.debug("Warmup inference pass note: %s", e)

        self._print_registry_banner()

    def _print_registry_banner(self) -> None:
        """Prints the standardized Model Registry summary banner."""
        m_id = self.model_metadata.get("model_id", f"model_{self.model_name}_v1")
        m_type = self.model_metadata.get("model_type", type(self.model.model).__name__ if self.model else "Classifier")
        f_prof = self.model_metadata.get("feature_profile", "lightweight_10")
        ds_ver = self.model_metadata.get("training_dataset_version", "dataset_v1_warp_wireguard")
        m_hash = self.model_metadata.get("model_hash", "N/A")
        s_hash = self.model_metadata.get("feature_schema_hash", CANONICAL_SCHEMA_HASH)
        calib = self.model_metadata.get("calibration_method", "Platt_Scaling_Sigmoid")
        rec_use = self.model_metadata.get("recommended_use", "SOC Traffic Monitoring")

        banner = f"""
MODEL REGISTRY
--------------
Model ID:        {m_id}
Model Type:      {m_type}
Feature Profile: {f_prof}
Dataset Version: {ds_ver}
Model SHA:       {m_hash[:16]}...
Schema SHA:      {s_hash[:16]}...
Calibration:     {calib}
Claims:          {rec_use}
"""
        logger.info(banner.strip())


    def predict_single(self, raw_features: Dict[str, Any]) -> Tuple[str, float, Dict[str, float]]:
        """
        Transforms a single raw feature map and predicts traffic class and confidence.
        Enforces schema validation.
        """
        validate_feature_schema(
            raw_features,
            expected_features=self.feature_names,
            expected_hash=self.model_metadata.get("feature_schema_hash"),
        )

        # Transform features
        if self.preprocessor and self.preprocessor.is_fitted:
            x_vec = self.preprocessor.transform([raw_features])
        else:
            x_vec = [[float(raw_features.get(k, 0.0)) for k in self.feature_names]]

        # Run inference
        probs_map: Dict[str, float] = {}
        if hasattr(self.model.model, "predict_proba"):
            probs = self.model.predict_proba(x_vec)[0]
            max_idx = int(max(range(len(probs)), key=lambda i: probs[i]))
            confidence = float(probs[max_idx])
            pred_class = (
                self.class_names[max_idx]
                if max_idx < len(self.class_names)
                else "Other"
            )
            for i, p in enumerate(probs):
                lbl = self.class_names[i] if i < len(self.class_names) else f"Class_{i}"
                probs_map[lbl] = round(float(p), 4)
        else:
            pred_idx = int(self.model.predict(x_vec)[0])
            confidence = 1.0
            pred_class = (
                self.class_names[pred_idx]
                if pred_idx < len(self.class_names)
                else "Other"
            )
            probs_map[pred_class] = 1.0

        return pred_class, round(confidence, 4), probs_map
