"""
Master One-Command Reproduction Pipeline.

Supports:
- python scripts/reproduce.py --all
- python scripts/reproduce.py --dataset
- python scripts/reproduce.py --training
- python scripts/reproduce.py --optimization
- python scripts/reproduce.py --robustness
- python scripts/reproduce.py --report
- python scripts/reproduce.py --force
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("reproduce")


def run_command(cmd: List[str]) -> None:
    logger.info("Executing: %s", " ".join(cmd))
    res = subprocess.run([sys.executable] + cmd, check=True)
    if res.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {res.returncode}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Master Reproduction Orchestrator.")
    parser.add_argument("--all", action="store_true", help="Execute complete reproduction workflow")
    parser.add_argument("--dataset", action="store_true", help="Repackage PCAP datasets and splits")
    parser.add_argument("--training", action="store_true", help="Retrain baseline ML models")
    parser.add_argument("--optimization", action="store_true", help="Rerun feature reduction & Pareto analysis")
    parser.add_argument("--robustness", action="store_true", help="Rerun robustness & generalization suite")
    parser.add_argument("--report", action="store_true", help="Regenerate all markdown research reports")
    parser.add_argument("--force", action="store_true", help="Force overwrite of existing results")
    args = parser.parse_args()

    run_all = args.all or (not any([args.dataset, args.training, args.optimization, args.robustness, args.report]))

    logger.info("=== STARTING EXPERIMENTAL REPRODUCTION PIPELINE ===")

    try:
        if run_all or args.dataset:
            logger.info(">>> Stage 1: Dataset Validation & Preparation")
            run_command(["-m", "training.pipeline"])

        if run_all or args.training:
            logger.info(">>> Stage 2: ML Baseline Model Training & Benchmarking")
            run_command(["-m", "training.ml_pipeline"])

        if run_all or args.optimization:
            logger.info(">>> Stage 3: Lightweight Feature Selection & Pareto Optimization")
            run_command(["-m", "training.optimization_pipeline"])

        if run_all or args.robustness:
            logger.info(">>> Stage 4: Dataset Expansion & Robustness Evaluation")
            run_command(["-m", "experiments.robustness.run", "--all"])

        if run_all or args.report:
            logger.info(">>> Stage 5: Research Claim Validation")
            run_command(["scripts/validate_research_claims.py"])

        logger.info("=== REPRODUCTION COMPLETED SUCCESSFULLY ===")
    except Exception as e:
        logger.error("Reproduction failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
