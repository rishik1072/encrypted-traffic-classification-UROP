"""
Master Real Data Pipeline Orchestrator.

Executes the complete offline real data workflow:
1. Manifest & Real-Source Validation
2. Metadata Ingestion & Packet Parsing
3. Flow Generation (FlowGenerator)
4. Feature Extraction (FeatureExtractor)
5. Quality Analysis & Class Distribution Reporting
6. Leakage-Free Group-Aware Dataset Splitting
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.build_feature_dataset import FeatureDatasetBuilder
from training.build_flow_dataset import FlowDatasetBuilder
from training.create_splits import GroupAwareDatasetSplitter
from training.dataset_quality import generate_dataset_quality_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("real_data_pipeline")


def run_real_data_pipeline(rebuild: bool = True) -> None:
    print("\n=======================================================")
    print("        REAL ENCRYPTED TRAFFIC DATASET PIPELINE        ")
    print("=======================================================\n")

    # 1. Flow Generation
    logger.info(">>> Stage 1: Building Real Flow Dataset from Metadata Sources")
    flow_builder = FlowDatasetBuilder()
    flows = flow_builder.build_dataset_from_manifest(origin_filter="real")
    print(f"[*] Real Flows Generated: {len(flows)} flows")

    # 2. Feature Extraction
    logger.info(">>> Stage 2: Extracting Statistical Tabular Features")
    feature_builder = FeatureDatasetBuilder()
    features = feature_builder.build_features_from_flows(origin_filter="real")
    print(f"[*] Real Feature Records: {len(features)} records")

    # 3. Quality Analysis
    logger.info(">>> Stage 3: Generating Real Dataset Quality & Distribution Reports")
    quality = generate_dataset_quality_report(origin_filter="real")
    print(f"[*] Quality Audit: {quality['total_sessions']} sessions, {quality['total_packets']:,} packets, {quality['total_traffic_volume_mb']} MB")

    # 4. Group-Aware Splitting
    logger.info(">>> Stage 4: Creating Leakage-Free Real Dataset Splits")
    splitter = GroupAwareDatasetSplitter()
    tr, va, te = splitter.split_dataset(origin_filter="real")
    print(f"[*] Real Splits Created: Train={len(tr)}, Val={len(va)}, Test={len(te)}")

    print("\n=======================================================")
    print("       REAL DATASET PIPELINE EXECUTION: SUCCESS        ")
    print("=======================================================\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run complete real traffic dataset preparation pipeline.")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild of real flows and features")
    args = parser.parse_args()

    run_real_data_pipeline(rebuild=args.rebuild)


if __name__ == "__main__":
    main()
