"""
Hierarchical Traffic Classifier for Encrypted Network Flows (Phase 8).
Implements a two-stage coarse-to-fine classifier with composed Bayesian confidence
and selective prediction (KNOWN_CLASS, LOW_CONFIDENCE, UNKNOWN, INSUFFICIENT_EVIDENCE).
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Set, Tuple

from models.base_model import BaseTrafficClassifier
from models.decision_tree import DecisionTreeTrafficClassifier
from models.lightgbm_model import LightGBMTrafficClassifier
from models.logistic_regression import LogisticRegressionClassifier
from models.random_forest import RandomForestTrafficClassifier
from preprocessing.preprocessing import FeaturePreprocessor
from training.discover_traffic_hierarchy import get_selected_hierarchy, map_fine_to_coarse

logger = logging.getLogger("hierarchical_classifier")


def create_base_estimator(model_name: str, params: Optional[Dict[str, Any]] = None) -> BaseTrafficClassifier:
    """Factory creating individual base classifiers."""
    m = model_name.lower()
    if m == "decision_tree":
        return DecisionTreeTrafficClassifier(params=params)
    elif m == "random_forest":
        return RandomForestTrafficClassifier(params=params)
    elif m == "lightgbm":
        return LightGBMTrafficClassifier(params=params)
    elif m == "logistic_regression":
        return LogisticRegressionClassifier(params=params)
    else:
        return DecisionTreeTrafficClassifier(params=params)


class HierarchicalTrafficClassifier:
    """
    Two-stage hierarchical classifier:
    Stage 1: Coarse traffic family classification (e.g. Bulk_Streaming, Interactive, Other).
    Stage 2: Specialized child class classification within each parent family.
    """

    def __init__(
        self,
        base_model_name: str = "decision_tree",
        hierarchy: Optional[Dict[str, List[str]]] = None,
        confidence_threshold: float = 0.60,
        min_packets: int = 10,
        model_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.base_model_name = base_model_name
        self.hierarchy = hierarchy or get_selected_hierarchy()
        self.confidence_threshold = confidence_threshold
        self.min_packets = min_packets
        self.model_params = model_params or {"max_depth": 5}

        # Stage 1: Coarse model
        self.stage1_model: Optional[BaseTrafficClassifier] = None
        self.stage1_preprocessor: Optional[FeaturePreprocessor] = None

        # Stage 2: Specialized fine models
        self.stage2_models: Dict[str, BaseTrafficClassifier] = {}
        self.stage2_preprocessors: Dict[str, FeaturePreprocessor] = {}

        self.all_classes: List[str] = sorted(list(set(c for children in self.hierarchy.values() for c in children)))
        self.feature_names: List[str] = []

    def fit(self, records: List[Dict[str, Any]], feature_names: List[str]) -> HierarchicalTrafficClassifier:
        """Fits both Stage 1 and Stage 2 models on training records."""
        self.feature_names = list(feature_names)

        # 1. Fit Stage 1 (Coarse Model)
        stage1_records = []
        for r in records:
            r_copy = dict(r)
            r_copy["traffic_class"] = map_fine_to_coarse(r["traffic_class"], self.hierarchy)
            stage1_records.append(r_copy)

        self.stage1_preprocessor = FeaturePreprocessor(
            config={"features": {"numerical_features": self.feature_names}}
        )
        self.stage1_preprocessor.numerical_cols = list(self.feature_names)
        self.stage1_preprocessor.feature_names_ = list(self.feature_names)

        X_coarse, y_coarse = self.stage1_preprocessor.fit_transform(stage1_records)
        self.stage1_model = create_base_estimator(self.base_model_name, self.model_params)
        self.stage1_model.fit(X_coarse, y_coarse)

        # 2. Fit Stage 2 (Child Models for families with > 1 class)
        for parent_group, child_classes in self.hierarchy.items():
            if len(child_classes) > 1:
                child_records = [r for r in records if r.get("traffic_class") in child_classes]
                if len(child_records) > 0:
                    prep = FeaturePreprocessor(
                        config={"features": {"numerical_features": self.feature_names}}
                    )
                    prep.numerical_cols = list(self.feature_names)
                    prep.feature_names_ = list(self.feature_names)

                    X_fine, y_fine = prep.fit_transform(child_records)
                    m = create_base_estimator(self.base_model_name, self.model_params)
                    m.fit(X_fine, y_fine)

                    self.stage2_models[parent_group] = m
                    self.stage2_preprocessors[parent_group] = prep
                    logger.debug("Trained Stage 2 classifier for family '%s' on %d samples across %s",
                                 parent_group, len(child_records), child_classes)

        return self

    def predict_composed_proba_single(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Computes composed probabilities:
        P(fine = c | x) = P(coarse = k | x) * P(fine = c | coarse = k, x)
        """
        if not self.stage1_model or not self.stage1_preprocessor:
            raise RuntimeError("Hierarchical classifier is not fitted.")

        # Stage 1: Coarse Probabilities
        X_stage1 = self.stage1_preprocessor.transform([record])
        coarse_probs = self.stage1_model.predict_proba(X_stage1)[0]
        coarse_labels = self.stage1_preprocessor.get_label_classes()
        coarse_prob_map = {lbl: coarse_probs[i] if i < len(coarse_probs) else 0.0 for i, lbl in enumerate(coarse_labels)}

        # Stage 2: Fine Probabilities per Coarse Group
        fine_prob_map: Dict[str, float] = {c: 0.0 for c in self.all_classes}
        stage2_prob_maps: Dict[str, Dict[str, float]] = {}

        for parent_group, child_classes in self.hierarchy.items():
            p_parent = coarse_prob_map.get(parent_group, 0.0)

            if len(child_classes) == 1:
                child = child_classes[0]
                fine_prob_map[child] = p_parent
                stage2_prob_maps[parent_group] = {child: 1.0}
            elif parent_group in self.stage2_models:
                prep = self.stage2_preprocessors[parent_group]
                model = self.stage2_models[parent_group]
                X_stage2 = prep.transform([record])
                child_probs = model.predict_proba(X_stage2)[0]
                child_labels = prep.get_label_classes()

                s2_map = {lbl: child_probs[i] if i < len(child_probs) else 0.0 for i, lbl in enumerate(child_labels)}
                stage2_prob_maps[parent_group] = s2_map

                for child, p_child in s2_map.items():
                    fine_prob_map[child] = p_parent * p_child
            else:
                for child in child_classes:
                    fine_prob_map[child] = p_parent / len(child_classes)

        # Normalize fine probability distribution
        total_p = sum(fine_prob_map.values())
        if total_p > 1e-9:
            fine_prob_map = {c: p / total_p for c, p in fine_prob_map.items()}

        # Determine best predictions
        best_fine_class = max(fine_prob_map.keys(), key=lambda k: fine_prob_map[k])
        final_confidence = fine_prob_map[best_fine_class]
        predicted_coarse_family = map_fine_to_coarse(best_fine_class, self.hierarchy)

        return {
            "predicted_fine_class": best_fine_class,
            "predicted_coarse_family": predicted_coarse_family,
            "final_confidence": float(final_confidence),
            "stage1_probability": float(coarse_prob_map.get(predicted_coarse_family, 0.0)),
            "stage2_probability": float(stage2_prob_maps.get(predicted_coarse_family, {}).get(best_fine_class, 1.0)),
            "fine_probabilities": fine_prob_map,
            "coarse_probabilities": coarse_prob_map,
        }

    def predict_selective(
        self,
        record: Dict[str, Any],
        packet_count: Optional[int] = None,
        confidence_threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Executes selective prediction with state classification:
        - INSUFFICIENT_EVIDENCE: if packet count < min_packets
        - UNKNOWN: if coarse confidence is too ambiguous (< 0.35)
        - LOW_CONFIDENCE: if confidence < threshold
        - KNOWN_CLASS: if confidence >= threshold
        """
        thresh = confidence_threshold if confidence_threshold is not None else self.confidence_threshold
        pkts = packet_count
        if pkts is None:
            try:
                pkts = int(record.get("forward_packet_count", 0) or 0) + int(record.get("backward_packet_count", 0) or 0)
                if pkts == 0:
                    pkts = int(record.get("total_packet_count", 0) or 0)
            except Exception:
                pkts = 100

        res = self.predict_composed_proba_single(record)

        if pkts < self.min_packets:
            status = "INSUFFICIENT_EVIDENCE"
        elif res["stage1_probability"] < 0.35:
            status = "UNKNOWN"
        elif res["final_confidence"] < thresh:
            status = "LOW_CONFIDENCE"
        else:
            status = "KNOWN_CLASS"

        res["status"] = status
        res["is_accepted"] = (status == "KNOWN_CLASS")
        return res
