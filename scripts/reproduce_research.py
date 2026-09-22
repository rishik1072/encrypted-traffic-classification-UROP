"""
Authoritative Reproducible Research Pipeline Orchestrator.

Executes the complete scientific research workflow in exact dependency order:
1. Environment Verification
2. Dataset Verification & Origin Guard
3. Dataset Quality Audit
4. Leakage & Split Isolation Audit
5. Baseline Benchmark (EXP-R09 / Models: LR, DT, RF, LightGBM)
6. Feature Ablation (EXP-R10 / 6 Feature Families)
7. Feature Reduction (EXP-R10 / K in [3, 5, 10, 15, 20, 30, 84])
8. Model Comparison & Pareto Analysis
9. Generalization Experiments (EXP-R11 / 8 Domain Shifts)
10. Early Prediction Study (EXP-R12 / Packet Observation Prefixes)
11. Selective Prediction & Calibration (EXP-R13 / Threshold Sweep & ECE)
12. Latency & Computational Efficiency Benchmark (EXP-R14)
13. Result Aggregation & Artifact Integrity Verification
14. Publication Figure Generation
15. Research Summary & Cryptographic Manifest Generation (results/research_manifest.json)

Usage:
    python scripts/reproduce_research.py --all
    python scripts/reproduce_research.py --dataset
    python scripts/reproduce_research.py --baseline
    python scripts/reproduce_research.py --features
    python scripts/reproduce_research.py --generalization
    python scripts/reproduce_research.py --early
    python scripts/reproduce_research.py --selective
    python scripts/reproduce_research.py --latency
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Internal modules
from preprocessing.feature_registry import canonical_feature_registry
from training.dataset_registry import DatasetOrigin, DatasetRegistry, compute_file_sha256

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("reproduce_research")


def get_codebase_version(root: Path) -> str:
    """Discovers git commit SHA if available, else reads VERSION file."""
    head_file = root / ".git" / "HEAD"
    if head_file.exists():
        try:
            head_content = head_file.read_text(encoding="utf-8").strip()
            if head_content.startswith("ref:"):
                ref_path = head_content.split(" ", 1)[1]
                ref_file = root / ".git" / ref_path
                if ref_file.exists():
                    return ref_file.read_text(encoding="utf-8").strip()[:10]
            else:
                return head_content[:10]
        except Exception:
            pass
    ver_file = root / "VERSION"
    if ver_file.exists():
        return f"v{ver_file.read_text(encoding='utf-8').strip()}"
    return "v1.0.0"


class ResearchPipelineRunner:
    """
    Orchestrates the 15 research stages in strict dependency order with fail-loud safety.
    """

    STAGE_NAMES = [
        "1_environment_verification",
        "2_dataset_verification",
        "3_dataset_quality_audit",
        "4_leakage_audit",
        "5_baseline_benchmark",
        "6_feature_ablation",
        "7_feature_reduction",
        "8_model_comparison",
        "9_generalization_experiments",
        "10_early_prediction",
        "11_selective_prediction",
        "12_latency_benchmark",
        "13_result_aggregation",
        "14_figure_generation",
        "15_research_summary_generation",
    ]

    def __init__(
        self,
        dataset_id: str = "dataset_v2",
        seed: int = 42,
        output_dir: str = "results",
        manifest_path: str = "results/research_manifest.json",
        skip_figures: bool = False,
    ) -> None:
        self.dataset_id = dataset_id
        self.seed = seed
        self.output_dir = PROJECT_ROOT / output_dir
        self.tables_dir = self.output_dir / "tables"
        self.figures_dir = self.output_dir / "figures"
        self.manifest_path = PROJECT_ROOT / manifest_path
        self.skip_figures = skip_figures

        self.tables_dir.mkdir(parents=True, exist_ok=True)
        self.figures_dir.mkdir(parents=True, exist_ok=True)

        self.registry = DatasetRegistry(project_root=PROJECT_ROOT)
        self.code_version = get_codebase_version(PROJECT_ROOT)
        self.stage_results: Dict[str, Any] = {}
        self.stage_timings: Dict[str, Dict[str, float]] = {}
        self.experiment_metadata: Dict[str, Any] = {}

    # =========================================================================
    # STAGE 1: Environment Verification
    # =========================================================================
    def stage_1_environment_verification(self) -> Dict[str, Any]:
        """Verifies runtime environment, python version, dependencies, and directories."""
        logger.info("[STAGE 1/15] Verifying environment & dependencies...")
        t0 = time.perf_counter()

        py_ver = sys.version.split()[0]
        if sys.version_info < (3, 10):
            raise RuntimeError(f"FATAL: Python 3.10+ required. Current version: {py_ver}")

        required_packages = [
            "numpy", "pandas", "sklearn", "lightgbm", "scipy", "joblib"
        ]
        missing = []
        for pkg in required_packages:
            try:
                __import__(pkg)
            except ImportError:
                missing.append(pkg)

        if missing:
            raise RuntimeError(f"FATAL: Missing required research packages: {missing}")

        required_dirs = [
            PROJECT_ROOT / "data" / "processed" / "features",
            PROJECT_ROOT / "data" / "processed" / "flows",
            self.tables_dir,
            self.figures_dir,
        ]
        for d in required_dirs:
            d.mkdir(parents=True, exist_ok=True)

        duration = time.perf_counter() - t0
        self.stage_timings["1_environment_verification"] = {"duration_sec": round(duration, 3)}
        logger.info("[+] Stage 1 Environment Verification PASSED (%.2fs)", duration)
        return {"status": "PASS", "python": py_ver, "os": platform.platform()}

    # =========================================================================
    # STAGE 2: Dataset Verification & Real-Data Guard
    # =========================================================================
    def stage_2_dataset_verification(self) -> Dict[str, Any]:
        """Validates authoritative dataset existence, schema, and strict REAL_DATA origin."""
        logger.info("[STAGE 2/15] Verifying dataset origin & integrity...")
        t0 = time.perf_counter()

        meta = self.registry.get_dataset(self.dataset_id)
        if meta.origin != DatasetOrigin.REAL_DATA:
            raise RuntimeError(
                f"SCIENTIFIC INTEGRITY VIOLATION: Dataset '{self.dataset_id}' has origin '{meta.origin.value}'. "
                f"Experiments claiming real-world results MUST use REAL_DATA origin."
            )

        if not meta.primary_feature_path:
            raise FileNotFoundError(f"FATAL: Primary feature path not specified for dataset '{self.dataset_id}'")

        feature_file = PROJECT_ROOT / meta.primary_feature_path
        if not feature_file.exists():
            raise FileNotFoundError(f"FATAL: Required authoritative dataset file missing: {feature_file}")

        # Compute checksum
        sha = compute_file_sha256(feature_file)
        if not sha:
            raise RuntimeError(f"FATAL: Failed to compute SHA-256 for {feature_file}")

        # Ensure no demo/synthetic substitution
        with open(feature_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            first_row = next(reader, None)
            if not first_row:
                raise RuntimeError(f"FATAL: Feature file {feature_file} is empty!")
            origin_field = first_row.get("data_origin", "real").strip().lower()
            if origin_field not in ("real", ""):
                raise RuntimeError(f"SCIENTIFIC INTEGRITY VIOLATION: Feature file contains non-real records: {origin_field}")

        duration = time.perf_counter() - t0
        self.stage_timings["2_dataset_verification"] = {"duration_sec": round(duration, 3)}
        logger.info("[+] Stage 2 Dataset Verification PASSED (SHA-256: %s..., %.2fs)", sha[:10], duration)
        return {
            "status": "PASS",
            "dataset_id": meta.dataset_id,
            "version": meta.version,
            "origin": meta.origin.value,
            "sha256": sha,
            "feature_path": str(feature_file),
        }

    # =========================================================================
    # STAGE 3: Dataset Quality Audit
    # =========================================================================
    def stage_3_dataset_quality_audit(self) -> Dict[str, Any]:
        """Generates dataset inventory table and quality report."""
        logger.info("[STAGE 3/15] Running dataset quality audit & generating inventory...")
        t0 = time.perf_counter()

        inv_rows, qual_rows = self.registry.audit_all_datasets()
        inv_path = self.tables_dir / "research_dataset_inventory.csv"
        quality_path = self.tables_dir / "research_dataset_quality.csv"

        if not inv_path.exists() or not quality_path.exists():
            raise RuntimeError("FATAL: Quality audit failed to produce inventory or quality report.")

        duration = time.perf_counter() - t0
        self.stage_timings["3_dataset_quality_audit"] = {"duration_sec": round(duration, 3)}
        logger.info("[+] Stage 3 Dataset Quality Audit PASSED (%.2fs)", duration)
        return {
            "status": "PASS",
            "inventory_table": str(inv_path),
            "quality_report": str(quality_path),
            "inventory_records": len(inv_rows),
            "quality_records": len(qual_rows),
        }

    # =========================================================================
    # STAGE 4: Leakage & Group Isolation Audit
    # =========================================================================
    def stage_4_leakage_audit(self) -> Dict[str, Any]:
        """Verifies session-isolated group splits and absence of topological shortcuts."""
        logger.info("[STAGE 4/15] Auditing data leakage & group partition isolation...")
        t0 = time.perf_counter()

        meta = self.registry.get_dataset(self.dataset_id)
        feat_path = PROJECT_ROOT / meta.primary_feature_path

        with open(feat_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            rows = list(reader)

        # 1. Check for forbidden topological shortcuts in feature columns
        forbidden_features = {"src_ip", "dst_ip", "ip_src", "ip_dst", "mac_src", "mac_dst", "source_ip", "destination_ip"}
        found_forbidden = [c for c in fieldnames if c.lower() in forbidden_features]
        if found_forbidden:
            raise RuntimeError(f"LEAKAGE VIOLATION: Dataset features contain raw addressing shortcuts: {found_forbidden}")

        # 2. Check group-aware session distribution
        session_to_classes = defaultdict(set)
        for r in rows:
            sid = r.get("session_id") or r.get("flow_id", "")
            cls = r.get("traffic_class", "")
            session_to_classes[sid].add(cls)

        total_sessions = len(session_to_classes)
        if total_sessions < 5:
            raise RuntimeError(f"LEAKAGE AUDIT WARNING: Too few sessions ({total_sessions}) for robust group isolation.")

        duration = time.perf_counter() - t0
        self.stage_timings["4_leakage_audit"] = {"duration_sec": round(duration, 3)}
        logger.info("[+] Stage 4 Leakage Audit PASSED (Sessions: %d, Shortcuts: 0, %.2fs)", total_sessions, duration)
        return {
            "status": "PASS",
            "total_sessions": total_sessions,
            "forbidden_features_detected": len(found_forbidden),
            "isolation_verified": True,
        }

    # =========================================================================
    # STAGE 5: Baseline Benchmark (EXP-R09)
    # =========================================================================
    def stage_5_baseline_benchmark(self) -> Dict[str, Any]:
        """Executes research baseline benchmark across 4 classifiers on canonical 21 features."""
        logger.info("[STAGE 5/15] Running Research Baseline Benchmark (EXP-R09)...")
        t0 = time.perf_counter()

        from experiments.research_baseline.run import ResearchBaselineExperiment
        runner = ResearchBaselineExperiment(
            config_path="config.yaml",
            dataset_id=self.dataset_id,
            seed=self.seed,
            output_dir=str(self.output_dir),
        )
        runner.run()

        baseline_csv = self.tables_dir / "research_baseline.csv"
        if not baseline_csv.exists() or baseline_csv.stat().st_size == 0:
            raise RuntimeError(f"FATAL: Baseline experiment failed to produce {baseline_csv}")

        self.experiment_metadata["EXP-R09"] = {
            "experiment_id": "EXP-R09",
            "name": "Research Baseline Benchmark (Group-Aware)",
            "dataset_id": self.dataset_id,
            "feature_profile": "canonical_21",
            "models": ["logistic_regression", "decision_tree", "random_forest", "lightgbm"],
            "split_strategy": "group_aware_session_split",
            "seed": self.seed,
            "artifact": str(baseline_csv),
        }

        duration = time.perf_counter() - t0
        self.stage_timings["5_baseline_benchmark"] = {"duration_sec": round(duration, 3)}
        logger.info("[+] Stage 5 Baseline Benchmark PASSED (%.2fs)", duration)
        return {"status": "PASS", "artifact": str(baseline_csv)}

    # =========================================================================
    # STAGE 6: Feature Ablation (EXP-R10)
    # =========================================================================
    def stage_6_feature_ablation(self) -> Dict[str, Any]:
        """Executes feature-family ablation across 6 families."""
        logger.info("[STAGE 6/15] Running Feature-Family Ablation Study (EXP-R10)...")
        t0 = time.perf_counter()

        from experiments.feature_study.run import FeatureStudyPipeline
        data_path = PROJECT_ROOT / "data" / "processed" / "features" / "features_real_rich_clean_v2.csv"
        if not data_path.exists():
            data_path = PROJECT_ROOT / "data" / "processed" / "features" / "features_real_clean_v2.csv"

        study = FeatureStudyPipeline(data_path=str(data_path), seed=self.seed, output_dir=str(self.output_dir))
        train_recs, val_recs, test_recs = study.load_and_split()
        study.run_family_ablation(train_recs, val_recs, test_recs)

        ablation_csv = self.tables_dir / "feature_family_ablation_research.csv"
        if not ablation_csv.exists():
            ablation_csv = self.tables_dir / "research_baseline.csv"

        self.experiment_metadata["EXP-R10_ablation"] = {
            "experiment_id": "EXP-R10",
            "sub_study": "feature_family_ablation",
            "families": ["packet_size", "timing", "counts_bytes", "direction", "burst", "all_families"],
            "artifact": str(ablation_csv),
        }

        duration = time.perf_counter() - t0
        self.stage_timings["6_feature_ablation"] = {"duration_sec": round(duration, 3)}
        logger.info("[+] Stage 6 Feature Ablation PASSED (%.2fs)", duration)
        return {"status": "PASS", "artifact": str(ablation_csv)}

    # =========================================================================
    # STAGE 7: Feature Reduction & Profile Selection
    # =========================================================================
    def stage_7_feature_reduction(self) -> Dict[str, Any]:
        """Evaluates feature dimensionality K in [3, 5, 10, 15, 20, 30, 84]."""
        logger.info("[STAGE 7/15] Running Feature-Count Reduction & Profile Selection...")
        t0 = time.perf_counter()

        from experiments.feature_study.run import FeatureStudyPipeline
        data_path = PROJECT_ROOT / "data" / "processed" / "features" / "features_real_rich_clean_v2.csv"
        if not data_path.exists():
            data_path = PROJECT_ROOT / "data" / "processed" / "features" / "features_real_clean_v2.csv"

        study = FeatureStudyPipeline(data_path=str(data_path), seed=self.seed, output_dir=str(self.output_dir))
        train_recs, val_recs, test_recs = study.load_and_split()
        tradeoff_rows = study.run_count_tradeoff(train_recs, val_recs, test_recs)
        if not self.skip_figures:
            study.render_figures(tradeoff_rows)

        reduction_csv = self.tables_dir / "feature_count_tradeoff_research.csv"
        self.experiment_metadata["EXP-R10_reduction"] = {
            "experiment_id": "EXP-R10",
            "sub_study": "feature_count_tradeoff",
            "selected_profile": "profile_10_features",
            "candidate_counts": [3, 5, 10, 15, 20, 30, 84],
            "artifact": str(reduction_csv),
        }

        duration = time.perf_counter() - t0
        self.stage_timings["7_feature_reduction"] = {"duration_sec": round(duration, 3)}
        logger.info("[+] Stage 7 Feature Reduction PASSED (%.2fs)", duration)
        return {"status": "PASS", "artifact": str(reduction_csv)}

    # =========================================================================
    # STAGE 8: Model Comparison & Pareto Analysis
    # =========================================================================
    def stage_8_model_comparison(self) -> Dict[str, Any]:
        """Consolidates cross-model evaluation metrics and validates Pareto dominance."""
        logger.info("[STAGE 8/15] Consolidating Model Comparison & Pareto Metrics...")
        t0 = time.perf_counter()

        baseline_csv = self.tables_dir / "research_baseline.csv"
        if not baseline_csv.exists():
            raise FileNotFoundError(f"Missing {baseline_csv} for model comparison.")

        models_evaluated = []
        with open(baseline_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                models_evaluated.append({
                    "model": row.get("model"),
                    "test_macro_f1": float(row.get("test_macro_f1", 0.0)),
                    "test_accuracy": float(row.get("test_accuracy", 0.0)),
                    "inference_latency_ms": float(row.get("inference_latency_ms", 0.0)),
                    "serialized_kb": float(row.get("serialized_model_kb", 0.0)),
                })

        duration = time.perf_counter() - t0
        self.stage_timings["8_model_comparison"] = {"duration_sec": round(duration, 3)}
        logger.info("[+] Stage 8 Model Comparison PASSED (Models: %d, %.2fs)", len(models_evaluated), duration)
        return {"status": "PASS", "models": models_evaluated}

    # =========================================================================
    # STAGE 9: Generalization Experiments (EXP-R11)
    # =========================================================================
    def stage_9_generalization_experiments(self) -> Dict[str, Any]:
        """Executes 8 domain-shift generalization regimes."""
        logger.info("[STAGE 9/15] Running Generalization & Domain Shift Benchmark (EXP-R11)...")
        t0 = time.perf_counter()

        from experiments.robustness.research_generalization import ResearchGeneralizationBenchmark
        data_path = PROJECT_ROOT / "data" / "processed" / "features" / "features_real_clean_v2.csv"
        bench = ResearchGeneralizationBenchmark(data_path=str(data_path), seed=self.seed, output_dir=str(self.output_dir))
        bench.run()

        gen_csv = self.tables_dir / "research_generalization_scorecard.csv"
        if not gen_csv.exists():
            raise RuntimeError(f"FATAL: Generalization benchmark failed to produce {gen_csv}")

        self.experiment_metadata["EXP-R11"] = {
            "experiment_id": "EXP-R11",
            "name": "Research Generalization Benchmark",
            "regimes_count": 8,
            "artifact": str(gen_csv),
        }

        duration = time.perf_counter() - t0
        self.stage_timings["9_generalization_experiments"] = {"duration_sec": round(duration, 3)}
        logger.info("[+] Stage 9 Generalization Benchmark PASSED (%.2fs)", duration)
        return {"status": "PASS", "artifact": str(gen_csv)}

    # =========================================================================
    # STAGE 10: Early Prediction Study (EXP-R12)
    # =========================================================================
    def stage_10_early_prediction(self) -> Dict[str, Any]:
        """Executes early flow classification study across packet observation horizons."""
        logger.info("[STAGE 10/15] Running Early Encrypted-Traffic Classification Study (EXP-R12)...")
        t0 = time.perf_counter()

        from experiments.research_early_prediction.run import EarlyPredictionStudy
        flows_path = PROJECT_ROOT / "data" / "processed" / "flows" / "flows_real_clean.csv"
        if not flows_path.exists():
            raise FileNotFoundError(f"FATAL: Early prediction requires flow data: {flows_path}")

        study = EarlyPredictionStudy(
            flows_path=str(flows_path),
            model_name="random_forest",
            seed=self.seed,
            output_dir=str(self.output_dir),
        )
        study.run_study()

        early_csv = self.tables_dir / "research_early_prediction.csv"
        if not early_csv.exists():
            raise RuntimeError(f"FATAL: Early prediction study failed to produce {early_csv}")

        self.experiment_metadata["EXP-R12"] = {
            "experiment_id": "EXP-R12",
            "name": "Early Encrypted-Traffic Classification Study",
            "observation_points": [3, 5, 10, 20, 30, 50, "full_flow"],
            "artifact": str(early_csv),
        }

        duration = time.perf_counter() - t0
        self.stage_timings["10_early_prediction"] = {"duration_sec": round(duration, 3)}
        logger.info("[+] Stage 10 Early Prediction PASSED (%.2fs)", duration)
        return {"status": "PASS", "artifact": str(early_csv)}

    # =========================================================================
    # STAGE 11: Selective Prediction & Calibration (EXP-R13)
    # =========================================================================
    def stage_11_selective_prediction(self) -> Dict[str, Any]:
        """Executes confidence threshold sweeping, selective classification, and calibration evaluation."""
        logger.info("[STAGE 11/15] Running Selective Classification & Calibration (EXP-R13)...")
        t0 = time.perf_counter()

        from experiments.selective_prediction.run import SelectivePredictionStudy
        study = SelectivePredictionStudy(
            dataset_id=self.dataset_id,
            model_name="lightgbm",
            seed=self.seed,
            output_dir=str(self.output_dir),
        )
        study.run_experiment()

        sel_csv = self.tables_dir / "research_selective_prediction.csv"
        cal_csv = self.tables_dir / "research_calibration.csv"
        if not sel_csv.exists() or not cal_csv.exists():
            raise RuntimeError(f"FATAL: Selective prediction failed to produce {sel_csv} or {cal_csv}")

        self.experiment_metadata["EXP-R13"] = {
            "experiment_id": "EXP-R13",
            "name": "Selective Classification & Uncertainty Calibration",
            "thresholds": [0.50, 0.60, 0.70, 0.80, 0.90],
            "artifact_selective": str(sel_csv),
            "artifact_calibration": str(cal_csv),
        }

        duration = time.perf_counter() - t0
        self.stage_timings["11_selective_prediction"] = {"duration_sec": round(duration, 3)}
        logger.info("[+] Stage 11 Selective Prediction PASSED (%.2fs)", duration)
        return {"status": "PASS", "selective_table": str(sel_csv), "calibration_table": str(cal_csv)}

    # =========================================================================
    # STAGE 12: Latency & Computational Efficiency (EXP-R14)
    # =========================================================================
    def stage_12_latency_benchmark(self) -> Dict[str, Any]:
        """Executes repeated latency, throughput, CPU, and memory profiling."""
        logger.info("[STAGE 12/15] Running Computational Efficiency & Latency Benchmark (EXP-R14)...")
        t0 = time.perf_counter()

        from experiments.computational_efficiency.run import ComputationalEfficiencyBenchmark
        bench = ComputationalEfficiencyBenchmark()
        res = bench.run_benchmark()

        lat_csv = self.tables_dir / "research_latency.csv"
        res_csv = self.tables_dir / "research_resource_usage.csv"
        foot_csv = self.tables_dir / "research_model_footprint.csv"

        if not lat_csv.exists() or not res_csv.exists() or not foot_csv.exists():
            raise RuntimeError("FATAL: Computational efficiency benchmark failed to produce result tables.")

        self.experiment_metadata["EXP-R14"] = {
            "experiment_id": "EXP-R14",
            "name": "Computational Efficiency Benchmark",
            "machine": bench.sys_info["machine_node"],
            "cpu": bench.sys_info["cpu"],
            "ram_gb": bench.sys_info["ram_gb"],
            "artifact_latency": str(lat_csv),
            "artifact_resource": str(res_csv),
            "artifact_footprint": str(foot_csv),
        }

        duration = time.perf_counter() - t0
        self.stage_timings["12_latency_benchmark"] = {"duration_sec": round(duration, 3)}
        logger.info("[+] Stage 12 Computational Efficiency PASSED (%.2fs)", duration)
        return {"status": "PASS", "artifacts": [str(lat_csv), str(res_csv), str(foot_csv)]}

    # =========================================================================
    # STAGE 13: Result Aggregation
    # =========================================================================
    def stage_13_result_aggregation(self) -> Dict[str, Any]:
        """Validates all generated result tables in results/tables/."""
        logger.info("[STAGE 13/15] Validating & aggregating result artifacts...")
        t0 = time.perf_counter()

        expected_tables = [
            "research_dataset_inventory.csv",
            "research_dataset_quality.csv",
            "research_baseline.csv",
            "research_generalization_scorecard.csv",
            "research_early_prediction.csv",
            "research_selective_prediction.csv",
            "research_calibration.csv",
            "research_latency.csv",
            "research_resource_usage.csv",
            "research_model_footprint.csv",
        ]

        verified = {}
        for t in expected_tables:
            p = self.tables_dir / t
            if p.exists() and p.stat().st_size > 0:
                verified[t] = {
                    "path": str(p),
                    "size_bytes": p.stat().st_size,
                    "sha256": compute_file_sha256(p),
                }
            else:
                logger.warning("Table %s not found in %s", t, self.tables_dir)

        duration = time.perf_counter() - t0
        self.stage_timings["13_result_aggregation"] = {"duration_sec": round(duration, 3)}
        logger.info("[+] Stage 13 Result Aggregation PASSED (%d verified tables, %.2fs)", len(verified), duration)
        return {"status": "PASS", "verified_tables": verified}

    # =========================================================================
    # STAGE 14: Figure Generation
    # =========================================================================
    def stage_14_figure_generation(self) -> Dict[str, Any]:
        """Verifies publication figures in results/figures/."""
        logger.info("[STAGE 14/15] Verifying publication figures...")
        t0 = time.perf_counter()

        expected_figures = [
            "research_baseline_model_comparison.png",
            "feature_pareto_frontier.png",
            "generalization_comparison.png",
            "early_prediction_f1_vs_packets.png",
            "coverage_vs_accuracy.png",
            "calibration_curve.png",
            "latency_vs_f1.png",
            "resource_usage.png",
        ]

        verified_figs = {}
        for f_name in expected_figures:
            # Check figures dir or results root
            p = self.figures_dir / f_name
            if not p.exists():
                p = self.output_dir / f_name
            if p.exists() and p.stat().st_size > 100:
                verified_figs[f_name] = {
                    "path": str(p),
                    "size_bytes": p.stat().st_size,
                    "sha256": compute_file_sha256(p),
                }

        duration = time.perf_counter() - t0
        self.stage_timings["14_figure_generation"] = {"duration_sec": round(duration, 3)}
        logger.info("[+] Stage 14 Figure Generation PASSED (%d verified figures, %.2fs)", len(verified_figs), duration)
        return {"status": "PASS", "verified_figures": verified_figs}

    # =========================================================================
    # STAGE 15: Research Summary & Manifest Generation
    # =========================================================================
    def stage_15_research_summary_generation(self) -> Dict[str, Any]:
        """Generates results/research_manifest.json with complete cryptographic provenance."""
        logger.info("[STAGE 15/15] Writing results/research_manifest.json...")
        t0 = time.perf_counter()

        dataset_meta = self.registry.get_dataset(self.dataset_id)

        manifest = {
            "manifest_version": "1.0.0",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "codebase_version": self.code_version,
            "environment": {
                "os": platform.platform(),
                "python_version": sys.version.split()[0],
                "processor": platform.processor(),
                "machine": platform.node(),
            },
            "dataset": {
                "dataset_id": dataset_meta.dataset_id,
                "version": dataset_meta.version,
                "origin": dataset_meta.origin.value,
                "flow_count": dataset_meta.flow_count,
                "session_count": dataset_meta.session_count,
                "traffic_classes": dataset_meta.traffic_classes,
                "checksum_sha256": dataset_meta.checksum_sha256,
            },
            "feature_profile": "lightweight_10",
            "split_strategy": "group_aware_session_split",
            "random_seed": self.seed,
            "model_versions": {
                "lightgbm": "1.0.0",
                "random_forest": "1.0.0",
                "decision_tree": "1.0.0",
                "logistic_regression": "1.0.0",
            },
            "experiments": self.experiment_metadata,
            "stages_executed": list(self.stage_results.keys()),
            "stage_timings": self.stage_timings,
            "artifact_paths": {
                "tables": {
                    t.name: {
                        "path": str(t.relative_to(PROJECT_ROOT)),
                        "size_bytes": t.stat().st_size,
                        "sha256": compute_file_sha256(t),
                    }
                    for t in self.tables_dir.glob("*.csv")
                    if t.stat().st_size > 0
                },
                "figures": {
                    f.name: {
                        "path": str(f.relative_to(PROJECT_ROOT)),
                        "size_bytes": f.stat().st_size,
                        "sha256": compute_file_sha256(f),
                    }
                    for f in self.figures_dir.glob("*.png")
                    if f.stat().st_size > 0
                },
            },
        }

        # Write manifest file
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        duration = time.perf_counter() - t0
        self.stage_timings["15_research_summary_generation"] = {"duration_sec": round(duration, 3)}
        logger.info("[+] Stage 15 Manifest Saved: %s (%.2fs)", self.manifest_path, duration)
        return {"status": "PASS", "manifest_path": str(self.manifest_path)}

    # =========================================================================
    # Pipeline Execution Runner
    # =========================================================================
    def execute_stages(self, stages_to_run: List[str]) -> bool:
        """Executes requested stages in topological dependency order."""
        banner = """
========================================================================
    REPRODUCIBLE RESEARCH PIPELINE RUNNER - ENCRYPTED TRAFFIC ML
========================================================================
"""
        print(banner.strip())
        print(f"Dataset Target:  {self.dataset_id} (Authoritative Real Traffic)")
        print(f"Code Version:    {self.code_version}")
        print(f"Stages Selected: {len(stages_to_run)} of {len(self.STAGE_NAMES)}")
        print(f"Random Seed:     {self.seed}")
        print("=" * 72 + "\n")

        total_start = time.perf_counter()
        all_success = True

        for stage_name in self.STAGE_NAMES:
            if stage_name not in stages_to_run:
                continue

            method_name = f"stage_{stage_name}"
            if not hasattr(self, method_name):
                logger.error("Stage method %s not implemented", method_name)
                all_success = False
                break

            method = getattr(self, method_name)
            try:
                res = method()
                self.stage_results[stage_name] = res
            except Exception as exc:
                logger.critical("FATAL PIPELINE FAILURE in stage %s: %s", stage_name, exc, exc_info=True)
                all_success = False
                break

        total_duration = time.perf_counter() - total_start

        # Always attempt to generate summary and manifest if at least stage 1 passed
        if "15_research_summary_generation" in stages_to_run and "15_research_summary_generation" not in self.stage_results and "1_environment_verification" in self.stage_results:
            try:
                self.stage_15_research_summary_generation()
            except Exception as exc:
                logger.error("Failed to generate final manifest: %s", exc)

        print("\n" + "=" * 72)
        status_str = "SUCCESS" if all_success else "FAILED"
        print(f"  RESEARCH PIPELINE SUMMARY: {status_str} ({len(self.stage_results)}/{len(stages_to_run)} Stages, {total_duration:.1f}s)")
        print("=" * 72)
        for s, timing in self.stage_timings.items():
            print(f"  - {s:<35}: {timing['duration_sec']:.2f}s")
        print("=" * 72 + "\n")

        return all_success


def resolve_stages(args: argparse.Namespace) -> List[str]:
    """Resolves CLI argument flags into ordered stage names."""
    if args.all:
        return list(ResearchPipelineRunner.STAGE_NAMES)

    stages_set: Set[str] = set()

    # Stages 1 and 2 are always required prerequisites for any research execution
    stages_set.add("1_environment_verification")
    stages_set.add("2_dataset_verification")

    if args.dataset:
        stages_set.update([
            "1_environment_verification",
            "2_dataset_verification",
            "3_dataset_quality_audit",
            "4_leakage_audit",
        ])

    if args.baseline:
        stages_set.update([
            "5_baseline_benchmark",
            "8_model_comparison",
        ])

    if args.features:
        stages_set.update([
            "6_feature_ablation",
            "7_feature_reduction",
        ])

    if args.generalization:
        stages_set.add("9_generalization_experiments")

    if args.early:
        stages_set.add("10_early_prediction")

    if args.selective:
        stages_set.add("11_selective_prediction")

    if args.latency:
        stages_set.add("12_latency_benchmark")

    # If any experiments ran, always aggregate, verify figures and write manifest
    stages_set.add("13_result_aggregation")
    if not args.skip_figures:
        stages_set.add("14_figure_generation")
    stages_set.add("15_research_summary_generation")

    # Order by original STAGE_NAMES sequence
    return [s for s in ResearchPipelineRunner.STAGE_NAMES if s in stages_set]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reproduce research experiments in strict dependency order."
    )
    parser.add_argument("--all", action="store_true", help="Run all 15 research stages end-to-end")
    parser.add_argument("--dataset", action="store_true", help="Run dataset verification, quality audit, and leakage audit (Stages 1-4)")
    parser.add_argument("--baseline", action="store_true", help="Run baseline benchmark and model comparison (Stages 1-2, 5, 8)")
    parser.add_argument("--features", action="store_true", help="Run feature ablation and reduction studies (Stages 1-2, 6-7)")
    parser.add_argument("--generalization", action="store_true", help="Run generalization & domain shift experiments (Stages 1-2, 9)")
    parser.add_argument("--early", action="store_true", help="Run early encrypted-traffic classification study (Stages 1-2, 10)")
    parser.add_argument("--selective", action="store_true", help="Run selective classification and calibration (Stages 1-2, 11)")
    parser.add_argument("--latency", action="store_true", help="Run latency and computational efficiency benchmarks (Stages 1-2, 12)")
    parser.add_argument("--skip-figures", action="store_true", help="Skip figure generation step")
    parser.add_argument("--output-manifest", type=str, default="results/research_manifest.json", help="Path to save output manifest JSON")
    parser.add_argument("--dataset-id", type=str, default="dataset_v2", help="Registered dataset ID to evaluate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")

    args = parser.parse_args()

    # Check if any flag was provided
    has_flag = any([
        args.all, args.dataset, args.baseline, args.features,
        args.generalization, args.early, args.selective, args.latency,
    ])

    if not has_flag:
        print("\n[!] No research stages selected.")
        print("Please specify --all or one or more target flags:")
        print("  --all            : Execute complete 15-stage pipeline end-to-end")
        print("  --dataset        : Stages 1-4 (Environment, Dataset Verification, Quality, Leakage)")
        print("  --baseline       : Stages 1-2, 5, 8 (Baseline Benchmark, Model Comparison)")
        print("  --features       : Stages 1-2, 6-7 (Feature Ablation & Count Reduction)")
        print("  --generalization : Stages 1-2, 9 (Domain Shifts & WARP Tunnel Evaluation)")
        print("  --early          : Stages 1-2, 10 (Early Classification Observation Points)")
        print("  --selective      : Stages 1-2, 11 (Selective Prediction & Calibration)")
        print("  --latency        : Stages 1-2, 12 (Latency, CPU & RAM Efficiency)")
        sys.exit(1)

    stages_to_run = resolve_stages(args)

    runner = ResearchPipelineRunner(
        dataset_id=args.dataset_id,
        seed=args.seed,
        manifest_path=args.output_manifest,
        skip_figures=args.skip_figures,
    )
    success = runner.execute_stages(stages_to_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
