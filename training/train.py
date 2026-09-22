"""
Model Training Script Interface.

Coordinates data loading, feature preprocessing, cross-validation, and model persistence.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional
import pandas as pd
import yaml

from models.base_model import BaseTrafficClassifier
from preprocessing.preprocessing import FeaturePreprocessor

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Loads configuration yaml file."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def train_model(
    model: BaseTrafficClassifier,
    train_df: pd.DataFrame,
    target_col: str,
    config: Dict[str, Any],
    save_path: Optional[Path] = None,
) -> BaseTrafficClassifier:
    """Trains and persists a traffic classifier on preprocessed features."""
    preprocessor = FeaturePreprocessor(config)
    x_train, y_train = preprocessor.fit_transform(train_df, target_col=target_col)
    
    classes = list(train_df[target_col].astype(str).unique())
    model.fit(x_train, y_train, classes=classes)
    
    if save_path:
        model.save(save_path)
    return model
