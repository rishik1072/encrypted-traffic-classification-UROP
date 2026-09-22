"""
Master Lightweight Optimization Pipeline Orchestrator.

Sequentially executes:
1. Baseline schema export
2. Multi-method feature ranking & consensus
3. Controlled feature reduction experiments (K=21, 15, 10, 5, 3)
4. Model complexity reduction experiments
5. Pareto frontier analysis & lightweight scoring
6. Real-time feature compatibility and latency cost profiling
7. Configuration locking & single held-out test evaluation
8. Comprehensive Markdown research report generation
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.baseline_schema import export_baseline_feature_schema
from training.feature_ranking import run_feature_ranking
from training.feature_reduction_experiment import run_feature_reduction_experiments
from training.finalize_configuration import finalize_and_evaluate_locked_configuration
from training.generate_optimization_report import generate_optimization_report
from training.model_complexity_experiment import run_model_complexity_experiment
from training.pareto_analysis import run_pareto_analysis
from training.realtime_compatibility import audit_realtime_compatibility, measure_feature_extraction_costs

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("optimization_pipeline")


def run_complete_optimization_pipeline(config_path: str = "config.yaml") -> None:
    logger.info("====================================================================")
    logger.info("STARTING PHASE 5: LIGHTWEIGHT FEATURE SELECTION & MODEL OPTIMIZATION")
    logger.info("====================================================================")

    # Step 1: Export baseline schema
    logger.info(">>> [Step 1/8] Exporting baseline feature schema...")
    export_baseline_feature_schema()

    # Step 2: Feature Ranking & Consensus
    logger.info(">>> [Step 2/8] Computing multi-method feature rankings & consensus...")
    run_feature_ranking(config_path=config_path)

    # Step 3: Feature Reduction Experiments
    logger.info(">>> [Step 3/8] Running controlled feature reduction experiments (K in {21, 15, 10, 5, 3})...")
    run_feature_reduction_experiments(config_path=config_path)

    # Step 4: Model Complexity Experiments
    logger.info(">>> [Step 4/8] Running model complexity reduction experiments...")
    run_model_complexity_experiment(config_path=config_path)

    # Step 5: Pareto Frontier Analysis
    logger.info(">>> [Step 5/8] Performing Pareto optimality and lightweight trade-off scoring...")
    run_pareto_analysis(config_path=config_path)

    # Step 6: Real-Time Compatibility Audit & Feature Extraction Costs
    logger.info(">>> [Step 6/8] Auditing real-time feature compatibility and extraction costs...")
    audit_realtime_compatibility()
    measure_feature_extraction_costs(config_path=config_path)

    # Step 7: Configuration Locking & Final Single Test Set Evaluation
    logger.info(">>> [Step 7/8] Locking optimal lightweight configuration and running final test evaluation...")
    finalize_and_evaluate_locked_configuration(config_path=config_path)

    # Step 8: Comprehensive Research Report Generation
    logger.info(">>> [Step 8/8] Generating lightweight optimization research report...")
    generate_optimization_report()

    logger.info("====================================================================")
    logger.info("PHASE 5 OPTIMIZATION PIPELINE COMPLETED SUCCESSFULLY")
    logger.info("====================================================================")


def main() -> None:
    parser = argparse.ArgumentParser(description="Master Lightweight Optimization and Trade-Off Pipeline.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    args = parser.parse_args()

    run_complete_optimization_pipeline(config_path=args.config)


if __name__ == "__main__":
    main()
