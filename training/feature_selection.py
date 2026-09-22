"""
Feature Selection and Dimensionality Reduction Module.

Identifies minimal feature subsets for high-throughput edge deployment using Mutual Information
and Tree-based feature importances.
"""

from __future__ import annotations

import logging
from typing import List, Tuple
import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_classif

logger = logging.getLogger(__name__)


def compute_mutual_information(
    x: np.ndarray, y: np.ndarray, feature_names: List[str]
) -> List[Tuple[str, float]]:
    """Calculates mutual information scores for features against class labels."""
    logger.info("Computing mutual information for %d features", len(feature_names))
    mi_scores = mutual_info_classif(x, y, random_state=42)
    ranked = sorted(zip(feature_names, mi_scores), key=lambda item: item[1], reverse=True)
    return [(name, float(score)) for name, score in ranked]
