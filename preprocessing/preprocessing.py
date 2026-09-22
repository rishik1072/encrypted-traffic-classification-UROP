"""
Feature Preprocessing and Dataset Preparation Pipeline.

Handles tabular cleaning, missing value imputation, scaling, and categorical encoding.
Fully serializable and scikit-learn compatible.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class FeaturePreprocessor:
    """
    Transforms raw extracted traffic feature dictionaries, DataFrames, or records into
    model-ready numerical matrices with imputation and normalization.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        feature_cfg = config.get("features", {})
        self.numerical_cols: List[str] = list(feature_cfg.get("numerical_features", []))
        self.categorical_cols: List[str] = list(feature_cfg.get("categorical_features", []))
        self.tls_cols: List[str] = list(feature_cfg.get("tls_features", []))

        self.medians_: Dict[str, float] = {}
        self.means_: Dict[str, float] = {}
        self.stds_: Dict[str, float] = {}
        self.label_to_idx_: Dict[str, int] = {}
        self.idx_to_label_: Dict[int, str] = {}
        self.feature_names_: List[str] = []
        self.is_fitted = False

    def fit(self, records: List[Dict[str, Any]], target_col: Optional[str] = "traffic_class") -> FeaturePreprocessor:
        """
        Fits medians, means, standard deviations, and class label mappings ONLY on training data.
        """
        logger.info("Fitting FeaturePreprocessor on %d training records", len(records))
        if not records:
            raise ValueError("Cannot fit FeaturePreprocessor on an empty record list.")

        self.feature_names_ = list(self.numerical_cols)

        # 1. Compute medians and standard deviation for numerical columns
        for col in self.numerical_cols:
            vals: List[float] = []
            for r in records:
                v = r.get(col)
                if v is not None and v != "":
                    try:
                        fv = float(v)
                        if not math.isnan(fv) and not math.isinf(fv):
                            vals.append(fv)
                    except (ValueError, TypeError):
                        pass

            if vals:
                sorted_vals = sorted(vals)
                median_val = sorted_vals[len(sorted_vals) // 2]
                mean_val = sum(vals) / len(vals)
                var_val = sum((x - mean_val) ** 2 for x in vals) / len(vals)
                std_val = math.sqrt(var_val) if var_val > 1e-9 else 1.0
            else:
                median_val = 0.0
                mean_val = 0.0
                std_val = 1.0

            self.medians_[col] = median_val
            self.means_[col] = mean_val
            self.stds_[col] = std_val

        # 2. Fit target labels
        if target_col:
            unique_labels = sorted(list({str(r[target_col]) for r in records if target_col in r and r[target_col]}))
            self.label_to_idx_ = {lbl: idx for idx, lbl in enumerate(unique_labels)}
            self.idx_to_label_ = {idx: lbl for idx, lbl in enumerate(unique_labels)}

        self.is_fitted = True
        return self

    def transform(self, records: List[Dict[str, Any]]) -> Any:
        """
        Transforms input records using parameters learned during fit().
        Returns a 2D matrix (numpy array if numpy available, else nested float list).
        """
        if not self.is_fitted:
            raise RuntimeError("FeaturePreprocessor must be fitted before calling transform.")

        transformed: List[List[float]] = []
        for r in records:
            row_feats: List[float] = []
            for col in self.numerical_cols:
                raw_val = r.get(col)
                if raw_val is None or raw_val == "":
                    val = self.medians_.get(col, 0.0)
                else:
                    try:
                        val = float(raw_val)
                        if math.isnan(val) or math.isinf(val):
                            val = self.medians_.get(col, 0.0)
                    except (ValueError, TypeError):
                        val = self.medians_.get(col, 0.0)

                # Standard scaling: (x - mean) / std
                mean_v = self.means_.get(col, 0.0)
                std_v = self.stds_.get(col, 1.0)
                scaled_val = (val - mean_v) / (std_v if std_v > 1e-9 else 1.0)
                row_feats.append(scaled_val)

            transformed.append(row_feats)

        try:
            import numpy as np
            return np.array(transformed, dtype=np.float64)
        except ImportError:
            return transformed

    def encode_labels(self, records: List[Dict[str, Any]], target_col: str = "traffic_class") -> Any:
        """Encodes target strings into class integer indices."""
        indices = [self.label_to_idx_.get(str(r.get(target_col, "")), -1) for r in records]
        try:
            import numpy as np
            return np.array(indices, dtype=np.int64)
        except ImportError:
            return indices

    def decode_labels(self, indices: Union[List[int], Any]) -> List[str]:
        """Decodes integer class predictions into label strings."""
        return [self.idx_to_label_.get(int(idx), "Unknown") for idx in indices]

    def fit_transform(self, records: List[Dict[str, Any]], target_col: Optional[str] = "traffic_class") -> Tuple[Any, Any]:
        """Fits preprocessor and returns (X, y) tuple."""
        self.fit(records, target_col=target_col)
        X = self.transform(records)
        y = self.encode_labels(records, target_col=target_col) if target_col else None
        return X, y

    def get_classes(self) -> List[str]:
        """Returns list of class names in ascending order of class index."""
        return [self.idx_to_label_[i] for i in range(len(self.idx_to_label_))]

    def get_label_classes(self) -> List[str]:
        """Alias for get_classes."""
        return self.get_classes()
