"""
Master Machine Learning Baseline Pipeline Orchestrator.

Executes end-to-end ML benchmarking:
1. Data Validation & Loading
2. Leakage-free Feature Preprocessing
3. Model Training (LR, DT, RF, LightGBM)
4. Comprehensive Evaluation on Held-out Test Set
5. Latency & Resource Benchmarking
6. Feature Importance Extraction
7. Multi-Criteria Ranking & Pareto Frontier Analysis
8. Error Analysis & Confusion Matrix Heatmaps
9. Research Benchmark Report Generation
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from training.benchmark_inference import benchmark_model_latency, benchmark_preprocessor_latency
from training.data_loader import DataLoader
from training.error_analysis import perform_error_analysis
from training.evaluate import evaluate_trained_models
from training.feature_importance import extract_feature_importances
from training.generate_benchmark_report import generate_markdown_report
from training.rank_models import rank_and_find_pareto_front
from training.train_models import train_all_baseline_models
from training.visualize_comparison import generate_comparison_plots

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("ml_pipeline")


class MLPipeline:
    """Orchestrates baseline training, empirical benchmarking, and reporting."""

    def __init__(self, config_path: str | Path = "config.yaml") -> None:
        self.config_path = Path(config_path)
        self.base_dir = self.config_path.parent
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config: Dict[str, Any] = yaml.safe_load(f)

    def run(
        self,
        skip_benchmark: bool = False,
        skip_plots: bool = False,
    ) -> bool:
        """Executes the complete baseline ML pipeline."""
        logger.info("=== STEP 1: LOADING DATASETS & FITTING PREPROCESSOR ===")
        loader = DataLoader(config_path=self.config_path)
        try:
            x_train, y_train, x_val, y_val, x_test, y_test, feature_names, class_names = (
                loader.prepare_datasets(save_preprocessor=True)
            )
        except Exception as e:
            logger.error("Failed to load dataset splits: %s. Run dataset preparation first.", e)
            return False

        if x_test is None or len(x_test) == 0:
            logger.warning("Test set is empty. Using validation or train partition as test fallback for demo.")
            x_test = x_val if (x_val is not None and len(x_val) > 0) else x_train
            y_test = y_val if (y_val is not None and len(y_val) > 0) else y_train

        logger.info("=== STEP 2: TRAINING BASELINE LIGHTWEIGHT MODELS ===")
        models_dir = self.base_dir / "results/models"
        trained_models, training_metrics = train_all_baseline_models(
            x_train=x_train,
            y_train=y_train,
            class_names=class_names,
            config=self.config,
            models_dir=models_dir,
        )

        if not trained_models:
            logger.error("No models were trained successfully.")
            return False

        logger.info("=== STEP 3: EVALUATION & METRICS COMPUTATION ===")
        fig_dir = self.base_dir / "results/figures/confusion_matrices"
        eval_results = evaluate_trained_models(
            models=trained_models,
            x_test=x_test,
            y_test=y_test,
            class_names=class_names,
            figures_dir=fig_dir,
        )

        logger.info("=== STEP 4: LATENCY & RESOURCE BENCHMARKING ===")
        bench_cfg = self.config.get("benchmark", {})
        warmup = int(bench_cfg.get("warmup_runs", 30))
        runs = int(bench_cfg.get("benchmark_runs", 200))
        batch_size = int(bench_cfg.get("batch_size", 16))

        comparison_records: List[Dict[str, Any]] = []

        for name, clf in trained_models.items():
            ev = eval_results.get(name, {})
            tr = training_metrics.get(name, {})

            if not skip_benchmark:
                lat_stats = benchmark_model_latency(
                    model=clf,
                    sample_features=x_test,
                    warmup_runs=warmup,
                    benchmark_runs=runs,
                    batch_size=batch_size,
                )
            else:
                lat_stats = {
                    "avg_inference_ms": 0.0,
                    "median_inference_ms": 0.0,
                    "p95_inference_ms": 0.0,
                    "p99_inference_ms": 0.0,
                    "batch_inference_ms_per_flow": 0.0,
                    "memory_mb": 0.0,
                    "cpu_percent": 0.0,
                }

            record = {
                "model": name,
                "accuracy": ev.get("accuracy", 0.0),
                "precision_macro": ev.get("precision_macro", 0.0),
                "recall_macro": ev.get("recall_macro", 0.0),
                "f1_macro": ev.get("f1_macro", 0.0),
                "f1_weighted": ev.get("f1_weighted", 0.0),
                "training_time_seconds": tr.get("training_time_seconds", 0.0),
                "model_size_mb": tr.get("model_size_mb", 0.0),
                "model_size_kb": tr.get("model_size_kb", 0.0),
                **lat_stats,
            }
            comparison_records.append(record)

        # Save Master Comparison Table
        table_path = self.base_dir / "results/tables/model_comparison.csv"
        table_path.parent.mkdir(parents=True, exist_ok=True)
        if comparison_records:
            with open(table_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(comparison_records[0].keys()))
                writer.writeheader()
                writer.writerows(comparison_records)
            logger.info("Saved master benchmark table to %s", table_path)

        logger.info("=== STEP 5: FEATURE IMPORTANCE EXTRACTION ===")
        feat_importances = extract_feature_importances(
            models=trained_models,
            feature_names=feature_names,
            output_dir=self.base_dir / "results/tables",
        )

        logger.info("=== STEP 6: ERROR ANALYSIS ===")
        error_records = perform_error_analysis(
            models=trained_models,
            x_test=x_test,
            y_test=y_test,
            class_names=class_names,
            output_path=self.base_dir / "results/tables/error_analysis.csv",
        )

        logger.info("=== STEP 7: MULTI-CRITERIA RANKING & PARETO ANALYSIS ===")
        ranked_records, pareto_models = rank_and_find_pareto_front(
            comparison_records=comparison_records,
            output_dir=self.base_dir / "results/tables",
        )

        if not skip_plots:
            logger.info("=== STEP 8: GENERATING VISUAL COMPARISON CHARTS ===")
            generate_comparison_plots(
                comparison_records=comparison_records,
                output_dir=self.base_dir / "results/figures/model_comparison",
            )

        logger.info("=== STEP 9: GENERATING RESEARCH BENCHMARK REPORT ===")
        # Identify best models
        best_f1_rec = max(comparison_records, key=lambda x: x["f1_macro"]) if comparison_records else {}
        fastest_rec = min(comparison_records, key=lambda x: x["avg_inference_ms"]) if comparison_records else {}
        smallest_rec = min(comparison_records, key=lambda x: x["model_size_mb"]) if comparison_records else {}

        metadata = {
            "version": self.config.get("project", {}).get("version", "0.1.0"),
            "random_seed": self.config.get("project", {}).get("random_seed", 42),
            "train_samples": len(x_train),
            "val_samples": len(x_val) if x_val is not None else 0,
            "test_samples": len(x_test),
            "feature_count": len(feature_names),
            "class_count": len(class_names),
            "classes": class_names,
            "best_f1_model": best_f1_rec.get("model", "None"),
            "fastest_model": fastest_rec.get("model", "None"),
            "smallest_model": smallest_rec.get("model", "None"),
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Save Experiment Metadata
        meta_path = self.base_dir / "results/tables/experiment_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        generate_markdown_report(
            metadata=metadata,
            comparison_records=comparison_records,
            pareto_models=pareto_models,
            error_analysis_records=error_records,
            feature_importances=feat_importances,
            output_path=self.base_dir / "results/model_benchmark_report.md",
        )

        logger.info("=== PHASE 3 ML BENCHMARKING COMPLETED SUCCESSFULLY ===")
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Master ML training & benchmarking pipeline.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--skip-benchmark", action="store_true", help="Skip timing benchmarks")
    parser.add_argument("--skip-plots", action="store_true", help="Skip plot rendering")
    args = parser.parse_args()

    pipeline = MLPipeline(config_path=args.config)
    success = pipeline.run(
        skip_benchmark=args.skip_benchmark,
        skip_plots=args.skip_plots,
    )
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
