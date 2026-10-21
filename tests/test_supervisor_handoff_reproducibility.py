"""
Test Suite: Final Reproducibility and Supervisor Handoff Audit.

Validates:
1. Existence, completeness, and structural integrity of docs/research/SUPERVISOR_HANDOFF.md.
2. Master Reproducibility Matrix coverage of all primary experiment groups.
3. Verification that documented evaluation entrypoints correspond to real files in the repository.
4. Physical existence and cryptographic checksum of preserved model artifacts.
5. Absolute distinction between read-only evaluation of preserved weights vs. full pipeline retraining.
6. Preservation of unresolved status for the RF 0.5854 vs 0.5873 discrepancy.
7. Separation of pure physical (N=12) vs hybrid (N=48) benchmarks and exact evaluation denominators.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import unittest
import joblib
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs" / "research"
HANDOFF_DOC = DOCS_DIR / "SUPERVISOR_HANDOFF.md"
MODELS_DIR = PROJECT_ROOT / "results" / "models"
TABLES_DIR = PROJECT_ROOT / "results" / "tables"

from experiments.research_baseline.run import CANONICAL_21_FEATURES, ResearchBaselineExperiment, compute_multiclass_metrics
from preprocessing.preprocessing import FeaturePreprocessor


class TestSupervisorHandoffReproducibility(unittest.TestCase):
    """Regression suite verifying reproducibility matrix, supervisor handoff, and artifact traces."""

    def test_supervisor_handoff_document_exists_and_contains_required_sections(self) -> None:
        """Verify docs/research/SUPERVISOR_HANDOFF.md exists and contains all required sections A through K."""
        self.assertTrue(HANDOFF_DOC.exists(), f"Missing required handoff document: {HANDOFF_DOC}")
        content = HANDOFF_DOC.read_text(encoding="utf-8")

        required_sections = [
            "Section A — Project Objective & Current Research Status",
            "Section B — Dataset Provenance & Composition",
            "Section C — Main Evidence-Backed Results with Exact Denominators",
            "Section D — Master Reproducibility Matrix",
            "Section E — Preserved Model Evaluation vs. Full Reproduction Pipeline",
            "Section F — Known Contradictions & Unresolved Questions",
            "Section G — Scientific Limitations & Claims That Must Not Be Made",
            "Section H — Prioritized Next Experiments for Continuation",
            "Section I — Verified vs. Documented Commands",
            "Section J — Final Report & Paper Submission Checklist",
            "Section K — Short Professional Summary for Supervisor",
        ]

        for sec in required_sections:
            self.assertIn(sec, content, f"Missing required section in handoff document: {sec}")

        # Verify key terms and release gate verdict
        self.assertIn("READY WITH EXPLICIT LIMITATIONS", content)
        self.assertIn("0.5854", content)
        self.assertIn("0.5873", content)
        self.assertIn("UNRESOLVED", content)
        self.assertIn("HYBRID_PERTURBED", content)
        self.assertIn("REAL_DATA", content)

    def test_reproducibility_matrix_coverage_of_all_experiment_groups(self) -> None:
        """Verify the reproducibility matrix explicitly covers all required experiment groups."""
        content = HANDOFF_DOC.read_text(encoding="utf-8")

        required_experiments = [
            "EXP-R09-RF",     # Hybrid baseline RF
            "EXP-R09-DT",     # Hybrid baseline DT
            "EXP-R09-LGBM",   # Hybrid baseline LightGBM
            "EXP-R09-LR",     # Hybrid baseline LR
            "EXP-R01",        # Pure physical baseline
            "EXP-R12",        # Early prediction
            "EXP-R13-SEL",    # Selective prediction
            "EXP-R13-CAL",    # Calibration analysis
            "EXP-R11-GEN",    # Domain generalization regimes
            "EXP-R14-LAT",    # Latency benchmark
            "EXP-R14-SIZE",   # Serialized footprint
            "EXP-R15",        # Streaming smoke test
            "EXP-R10-ABL",    # Feature ablation
            "EXP-R10-RED",    # Feature count reduction
        ]

        for exp_id in required_experiments:
            self.assertIn(exp_id, content, f"Reproducibility matrix missing experiment: {exp_id}")

    def test_verified_evaluation_commands_map_to_real_codebase_files(self) -> None:
        """Check that all documented scripts and experiment modules correspond to actual files on disk."""
        expected_files = [
            PROJECT_ROOT / "experiments" / "research_baseline" / "run.py",
            PROJECT_ROOT / "training" / "real_ml_baseline.py",
            PROJECT_ROOT / "experiments" / "research_early_prediction" / "run.py",
            PROJECT_ROOT / "experiments" / "selective_prediction" / "run.py",
            PROJECT_ROOT / "experiments" / "robustness" / "research_generalization.py",
            PROJECT_ROOT / "experiments" / "computational_efficiency" / "run.py",
            PROJECT_ROOT / "experiments" / "realtime_validation" / "run.py",
            PROJECT_ROOT / "experiments" / "feature_study" / "run.py",
            PROJECT_ROOT / "scripts" / "validate_research_claims.py",
            PROJECT_ROOT / "scripts" / "reproduce_research.py",
            PROJECT_ROOT / "training" / "split_leakage_audit.py",
            PROJECT_ROOT / "training" / "dataset_registry.py",
        ]

        for fpath in expected_files:
            self.assertTrue(fpath.exists(), f"Documented script does not exist on disk: {fpath}")

    def test_required_model_artifacts_and_checksums_exist_on_disk(self) -> None:
        """Verify that preserved model artifacts exist with correct sizes and hashes, and missing weights are absent."""
        # Preserved RF model
        rf_path = MODELS_DIR / "research_baseline" / "random_forest.joblib"
        self.assertTrue(rf_path.exists(), "Preserved RF joblib must exist")
        rf_bytes = rf_path.read_bytes()
        self.assertEqual(len(rf_bytes), 899117, "Expected 899,117 bytes for preserved RF joblib")
        sha256_rf = hashlib.sha256(rf_bytes).hexdigest()
        self.assertEqual(sha256_rf, "814d8be3ec8f679dc17191b375470f0671754ee12acd593534236f408baf0107")

        # Preserved DT model
        dt_path = MODELS_DIR / "research_baseline" / "decision_tree.joblib"
        self.assertTrue(dt_path.exists(), "Preserved DT joblib must exist")
        self.assertEqual(len(dt_path.read_bytes()), 9814, "Expected 9,814 bytes for preserved DT joblib")

        # Preserved Pure Physical Fallback model
        real_rf_path = MODELS_DIR / "real_baseline" / "random_forest.joblib"
        self.assertTrue(real_rf_path.exists(), "Preserved real_baseline RF joblib must exist")
        self.assertEqual(len(real_rf_path.read_bytes()), 499, "Expected 499 bytes for real_baseline RF joblib")

        # Verify that secondary RF weights (881.98 KB = 903,147 bytes) are NOT present on disk
        # Searching all model files in results/models/ to ensure no secondary weights are lurking
        all_joblibs = list(MODELS_DIR.rglob("*.joblib"))
        sizes = [f.stat().st_size for f in all_joblibs]
        self.assertNotIn(903147, sizes, "Secondary RF model weights (881.98 KB) must remain absent to preserve audit fidelity.")

    def test_read_only_reproduction_of_preserved_models_without_retraining(self) -> None:
        """
        Verify that loading preserved model weights reproduces reported test metrics
        (RF: 0.5854 F1 / 0.5833 Acc, DT: 0.5802 F1 / 0.5833 Acc) without fitting any estimators.
        """
        # Load dataset_v2 test split deterministically
        bench = ResearchBaselineExperiment(config_path="config.yaml", seed=42)
        records, _ = bench.load_and_validate_dataset()
        train_records, val_records, test_records = bench.split_data_group_aware(records)

        prep_config = dict(bench.config)
        prep_config["features"] = {"numerical_features": CANONICAL_21_FEATURES}
        preprocessor = FeaturePreprocessor(prep_config)
        preprocessor.fit(train_records, target_col="traffic_class")
        x_test = preprocessor.transform(test_records)
        y_test = preprocessor.encode_labels(test_records, target_col="traffic_class")

        # 1. Random Forest read-only evaluation
        rf_pkg = joblib.load(MODELS_DIR / "research_baseline" / "random_forest.joblib")
        rf = rf_pkg["model"]
        rf_classes = rf_pkg["classes_"]
        rf_preds = rf.predict(x_test)
        rf_metrics = compute_multiclass_metrics(y_test, np.array(rf_preds), rf_classes)
        self.assertAlmostEqual(rf_metrics["macro_f1"], 0.5854, places=4)
        self.assertAlmostEqual(rf_metrics["accuracy"], 0.5833, places=4)

        # 2. Decision Tree read-only evaluation
        dt_pkg = joblib.load(MODELS_DIR / "research_baseline" / "decision_tree.joblib")
        dt = dt_pkg["model"]
        dt_classes = dt_pkg["classes_"]
        dt_preds = dt.predict(x_test)
        dt_metrics = compute_multiclass_metrics(y_test, np.array(dt_preds), dt_classes)
        self.assertAlmostEqual(dt_metrics["macro_f1"], 0.5802, places=4)
        self.assertAlmostEqual(dt_metrics["accuracy"], 0.5833, places=4)

    def test_exact_denominators_and_disclosures_match_result_tables(self) -> None:
        """Verify empirical table entries match exact denominators cited in the handoff document."""
        # 1. Early prediction: N=11 classified flows out of 12 (7/11 = 0.6364)
        early_csv = TABLES_DIR / "research_early_prediction.csv"
        self.assertTrue(early_csv.exists())
        with open(early_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [r for r in reader if str(r.get("packet_horizon")) == "3"]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(int(row["flows_classified"]), 11)
            self.assertEqual(int(row["total_test_flows"]), 12)
            self.assertAlmostEqual(float(row["accuracy"]), 0.6364, places=4)
            self.assertAlmostEqual(float(row["coverage"]), 0.9167, places=4)

        # 2. Selective prediction: tau*=0.70 has 26 accepted flows out of 48 (19/26 = 0.7308)
        sel_csv = TABLES_DIR / "research_selective_prediction.csv"
        self.assertTrue(sel_csv.exists())
        with open(sel_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [r for r in reader if str(r.get("threshold")) == "0.7" and str(r.get("split")) == "test"]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(int(row["accepted_samples"]), 26)
            self.assertEqual(int(row["total_samples"]), 48)
            self.assertAlmostEqual(float(row["selective_accuracy"]), 0.7308, places=4)
            self.assertAlmostEqual(float(row["coverage"]), 0.5417, places=4)

        # 3. Pure physical baseline: 1 flow correct out of 12 (1/12 = 0.0833)
        real_csv = TABLES_DIR / "real_final_baseline_result.csv"
        self.assertTrue(real_csv.exists())
        with open(real_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [r for r in reader if r.get("selected_model") == "random_forest"]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(int(row["test_samples"]), 12)
            self.assertAlmostEqual(float(row["test_accuracy"]), 0.0833, places=4)
            self.assertAlmostEqual(float(row["test_macro_f1"]), 0.0833, places=4)


if __name__ == "__main__":
    unittest.main()
