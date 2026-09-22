"""
Data Loading and Split Management Module.

Loads train, validation, and test datasets, manages feature isolation, target label separation,
and serializes the fitted FeaturePreprocessor artifact.
"""

from __future__ import annotations

import csv
import logging
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import yaml

from preprocessing.preprocessing import FeaturePreprocessor

logger = logging.getLogger(__name__)


class DataLoader:
    """
    Loads train.csv, validation.csv, and test.csv from data/processed/splits/.
    Enforces that FeaturePreprocessor is fitted STRICTLY on the training split.
    """

    def __init__(self, config_path: str | Path = "config.yaml") -> None:
        self.config_path = Path(config_path)
        self.base_dir = self.config_path.parent
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config: Dict[str, Any] = yaml.safe_load(f)

        dataset_cfg = self.config.get("dataset", {})
        self.split_dir = self.base_dir / dataset_cfg.get("split_directory", "data/processed/splits")
        self.preprocessor_path = self.base_dir / "results/models/preprocessor.joblib"
        self.target_col = "traffic_class"
        self.preprocessor = FeaturePreprocessor(self.config)

    def load_raw_split(self, split_name: str) -> List[Dict[str, Any]]:
        """Reads a split CSV into a list of row dictionaries."""
        file_path = self.split_dir / f"{split_name}.csv"
        if not file_path.exists():
            raise FileNotFoundError(f"Split file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def prepare_datasets(
        self,
        save_preprocessor: bool = True,
    ) -> Tuple[Any, Any, Any, Any, Any, Any, List[str], List[str]]:
        """
        Loads train, val, and test splits.
        Fits preprocessor ONLY on train, then transforms train, val, and test partitions.
        Returns:
            X_train, y_train, X_val, y_val, X_test, y_test, feature_names, class_names
        """
        logger.info("Loading dataset splits from %s", self.split_dir)
        train_records = self.load_raw_split("train")
        val_records = self.load_raw_split("validation")
        test_records = self.load_raw_split("test")

        if not train_records:
            raise ValueError("Training split is empty. Cannot train models.")

        # 1. Fit preprocessor strictly on train
        self.preprocessor.fit(train_records, target_col=self.target_col)
        if save_preprocessor:
            self.preprocessor_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                import joblib
                joblib.dump(self.preprocessor, self.preprocessor_path)
            except ImportError:
                with open(self.preprocessor_path, "wb") as f:
                    pickle.dump(self.preprocessor, f)
            logger.info("Saved fitted preprocessor to %s", self.preprocessor_path)

        # 2. Transform partitions
        x_train = self.preprocessor.transform(train_records)
        y_train = self.preprocessor.encode_labels(train_records, target_col=self.target_col)

        x_val = self.preprocessor.transform(val_records) if val_records else None
        y_val = self.preprocessor.encode_labels(val_records, target_col=self.target_col) if val_records else None

        x_test = self.preprocessor.transform(test_records) if test_records else None
        y_test = self.preprocessor.encode_labels(test_records, target_col=self.target_col) if test_records else None

        feature_names = self.preprocessor.feature_names_
        class_names = self.preprocessor.get_classes()

        logger.info(
            "Prepared datasets: Train=%d samples, Val=%d samples, Test=%d samples, Features=%d, Classes=%d",
            len(train_records),
            len(val_records) if val_records else 0,
            len(test_records) if test_records else 0,
            len(feature_names),
            len(class_names),
        )

        return x_train, y_train, x_val, y_val, x_test, y_test, feature_names, class_names
