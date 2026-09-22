"""
Master Dataset Preparation Pipeline Orchestrator.

Executes all dataset preparation stages in sequence:
1. Manifest Validation
2. Flow Dataset Generation
3. Tabular Feature Extraction
4. Dataset Cleaning & Quality Reporting
5. Group-Aware Train / Val / Test Splitting
6. Balance & Statistical Analysis
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

from training.analyze_dataset import DatasetAnalyzer
from training.build_feature_dataset import FeatureDatasetBuilder
from training.build_flow_dataset import FlowDatasetBuilder
from training.create_splits import GroupAwareDatasetSplitter
from training.dataset_cleaner import DatasetCleaner
from training.dataset_validator import DatasetValidator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("dataset_pipeline")


class DatasetPipeline:
    """End-to-end dataset preparation pipeline manager."""

    def __init__(self, config_path: str | Path = "config.yaml") -> None:
        self.config_path = Path(config_path)
        self.base_dir = self.config_path.parent
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config: Dict[str, Any] = yaml.safe_load(f)

    def run(
        self,
        manifest_path: Optional[str | Path] = None,
        ignore_missing_pcaps: bool = False,
        synthetic_packet_source: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Executes the complete dataset preparation pipeline."""
        dataset_cfg = self.config.get("dataset", {})
        man_path = Path(manifest_path) if manifest_path else self.base_dir / dataset_cfg.get(
            "manifest_path", "data/dataset_manifest.csv"
        )

        logger.info("=== STAGE 1: DATASET MANIFEST VALIDATION ===")
        validator = DatasetValidator(manifest_path=man_path, base_dir=self.base_dir)
        val_res = validator.validate(check_file_existence=not ignore_missing_pcaps)
        print(val_res.summary_text())

        if not val_res.is_valid and not ignore_missing_pcaps:
            logger.error("Pipeline stopped due to manifest validation errors.")
            return False

        logger.info("=== STAGE 2: FLOW DATASET GENERATION ===")
        flow_builder = FlowDatasetBuilder(config_path=self.config_path)
        flows = flow_builder.build_dataset_from_manifest(
            manifest_path=man_path,
            synthetic_packet_source=synthetic_packet_source,
        )
        if not flows:
            logger.warning("No flows extracted. If PCAP files are empty or missing, provide synthetic fixtures.")
            return False

        logger.info("=== STAGE 3: ZERO-PAYLOAD FEATURE EXTRACTION ===")
        feat_builder = FeatureDatasetBuilder(config_path=self.config_path)
        features = feat_builder.build_features_from_flows()
        logger.info("Extracted %d feature rows.", len(features))

        logger.info("=== STAGE 4: DATASET CLEANING & QUALITY REPORTING ===")
        cleaner = DatasetCleaner(config_path=self.config_path)
        clean_features, cleaning_metrics = cleaner.clean_dataset()
        logger.info("Cleaning completed. %d valid flows retained.", len(clean_features))

        logger.info("=== STAGE 5: GROUP-AWARE LEAKAGE-FREE SPLITTING ===")
        splitter = GroupAwareDatasetSplitter(config_path=self.config_path)
        train_s, val_s, test_s = splitter.split_dataset()
        logger.info("Splits created: Train=%d, Validation=%d, Test=%d", len(train_s), len(val_s), len(test_s))

        logger.info("=== STAGE 6: DATASET BALANCE & STATISTICAL ANALYSIS ===")
        analyzer = DatasetAnalyzer(config_path=self.config_path)
        analyzer.analyze()
        logger.info("=== DATASET PIPELINE COMPLETED SUCCESSFULLY ===")

        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the end-to-end dataset preparation pipeline.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--manifest", default=None, help="Optional custom manifest path")
    parser.add_argument(
        "--ignore-missing-pcaps",
        action="store_true",
        help="Run pipeline even if physical PCAPs are not on disk",
    )
    args = parser.parse_args()

    pipeline = DatasetPipeline(config_path=args.config)
    success = pipeline.run(manifest_path=args.manifest, ignore_missing_pcaps=args.ignore_missing_pcaps)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
