"""
Dataset Preparation Reproducibility Script.

Executes the complete dataset workflow from configuration and generates an execution log.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.pipeline import DatasetPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("prepare_dataset")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare dataset reproducibly from manifest.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--manifest", default="data/dataset_manifest.csv", help="Path to manifest")
    parser.add_argument("--ignore-missing-pcaps", action="store_true", help="Skip physical file check")
    args = parser.parse_args()

    logger.info("Starting reproducible dataset preparation at %s", datetime.utcnow().isoformat())
    pipeline = DatasetPipeline(config_path=args.config)
    success = pipeline.run(manifest_path=args.manifest, ignore_missing_pcaps=args.ignore_missing_pcaps)

    if success:
        logger.info("Dataset preparation finished successfully.")
    else:
        logger.error("Dataset preparation failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
