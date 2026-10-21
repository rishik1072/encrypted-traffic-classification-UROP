"""
Test Suite: Random Forest Baseline Forensics and Artifact Reconciliation.

Validates:
1. Integrity and structural properties of the preserved Random Forest model artifact.
2. Read-only reproduction of exact headline test metrics (0.5854 Macro-F1, 0.5833 Accuracy) from saved model weights.
3. Detection and tracking of conflicting baseline Random Forest values (0.5854 vs 0.5873).
4. Parity and consistency of non-RF models (LR, DT, LGBM) across baseline result tables.
5. Structural identity of the 499-byte _SimpleRandomForest fallback artifacts.
6. Prevention of silent VERIFIED claims when underlying prediction logs are absent.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import unittest
import joblib
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TABLES_DIR = PROJECT_ROOT / "results" / "tables"
FINAL_DIR = PROJECT_ROOT / "results" / "final"
MODELS_DIR = PROJECT_ROOT / "results" / "models"
RESEARCH_DOCS_DIR = PROJECT_ROOT / "docs" / "research"

from experiments.research_baseline.run import CANONICAL_21_FEATURES, ResearchBaselineExperiment, compute_multiclass_metrics
from preprocessing.preprocessing import FeaturePreprocessor


class TestRFForensicsAudit(unittest.TestCase):
    """Forensic regression tests for Random Forest baseline reconciliation."""

    def test_saved_rf_model_artifact_integrity(self) -> None:
        """Verify the preserved Random Forest artifact exists with correct hash, size, and structure."""
        model_path = MODELS_DIR / "research_baseline" / "random_forest.joblib"
        self.assertTrue(model_path.exists(), "research_baseline random_forest.joblib must exist.")

        raw_bytes = model_path.read_bytes()
        self.assertEqual(len(raw_bytes), 899117, "Expected model file size to be exactly 899,117 bytes (878.04 KB).")
        sha256 = hashlib.sha256(raw_bytes).hexdigest()
        self.assertEqual(
            sha256,
            "814d8be3ec8f679dc17191b375470f0671754ee12acd593534236f408baf0107",
            "SHA256 hash mismatch for preserved Random Forest model.",
        )

        pkg = joblib.load(model_path)
        self.assertIn("model", pkg)
        self.assertIn("classes_", pkg)
        self.assertIn("params", pkg)

        rf = pkg["model"]
        self.assertEqual(rf.__class__.__name__, "RandomForestClassifier")
        self.assertEqual(len(rf.estimators_), 100)
        self.assertEqual(rf.n_features_in_, 21)
        self.assertEqual(rf.max_depth, 15)
        self.assertEqual(rf.min_samples_split, 4)
        self.assertEqual(rf.random_state, 42)

    def test_saved_rf_model_reproduces_05854_test_metrics(self) -> None:
        """
        Verify that read-only evaluation of the preserved model reproduces 0.5854 Test Macro-F1
        and exact per-class metrics without retraining.
        """
        model_path = MODELS_DIR / "research_baseline" / "random_forest.joblib"
        pkg = joblib.load(model_path)
        rf = pkg["model"]
        classes = pkg["classes_"]

        # Partition dataset_v2 deterministically with seed=42
        bench = ResearchBaselineExperiment(config_path="config.yaml", seed=42)
        records, meta = bench.load_and_validate_dataset()
        train_records, val_records, test_records = bench.split_data_group_aware(records)

        prep_config = dict(bench.config)
        prep_config["features"] = {"numerical_features": CANONICAL_21_FEATURES}
        preprocessor = FeaturePreprocessor(prep_config)
        preprocessor.fit(train_records, target_col="traffic_class")

        x_val = preprocessor.transform(val_records)
        y_val = preprocessor.encode_labels(val_records, target_col="traffic_class")

        x_test = preprocessor.transform(test_records)
        y_test = preprocessor.encode_labels(test_records, target_col="traffic_class")

        # Validation set evaluation
        val_preds = rf.predict(x_val)
        val_metrics = compute_multiclass_metrics(y_val, np.array(val_preds), classes)
        self.assertAlmostEqual(val_metrics["accuracy"], 0.5625, places=4)
        self.assertAlmostEqual(val_metrics["macro_f1"], 0.5582, places=4)

        # Held-out test set evaluation
        test_preds = rf.predict(x_test)
        test_metrics = compute_multiclass_metrics(y_test, np.array(test_preds), classes)
        self.assertAlmostEqual(test_metrics["accuracy"], 0.5833, places=4)
        self.assertAlmostEqual(test_metrics["macro_f1"], 0.5854, places=4)
        self.assertAlmostEqual(test_metrics["macro_precision"], 0.5989, places=4)
        self.assertAlmostEqual(test_metrics["macro_recall"], 0.5833, places=4)

        # Check per-class F1 against research_baseline_per_class.csv
        per_class_csv = TABLES_DIR / "research_baseline_per_class.csv"
        with open(per_class_csv, "r", encoding="utf-8") as f:
            rf_test_rows = {
                r["traffic_class"]: r
                for r in csv.DictReader(f)
                if r["model"] == "random_forest" and r["split"] == "test"
            }
        for cls_name, expected_row in rf_test_rows.items():
            actual_f1 = test_metrics["per_class"][cls_name]["f1"]
            self.assertAlmostEqual(
                actual_f1,
                float(expected_row["f1_score"]),
                places=4,
                msg=f"Per-class F1 mismatch for {cls_name}",
            )

    def test_conflicting_baseline_values_flagged_as_unresolved(self) -> None:
        """Verify that conflicting RF values across tables are detected and flagged as UNRESOLVED in docs."""
        research_csv = TABLES_DIR / "research_baseline.csv"
        final_csv = FINAL_DIR / "baseline_results.csv"

        with open(research_csv, "r", encoding="utf-8") as f:
            res_rf = [r for r in csv.DictReader(f) if r["model"] == "random_forest"][0]
        with open(final_csv, "r", encoding="utf-8") as f:
            fin_rf = [r for r in csv.DictReader(f) if r["model"] == "random_forest"][0]

        # Metric values must differ: 0.5854 vs 0.5873
        self.assertNotEqual(float(res_rf["test_macro_f1"]), float(fin_rf["test_macro_f1"]))
        self.assertAlmostEqual(float(res_rf["test_macro_f1"]), 0.5854, places=4)
        self.assertAlmostEqual(float(fin_rf["test_macro_f1"]), 0.5873, places=4)

        # Both forensic and traceability reports must document this as UNRESOLVED
        forensic_doc = RESEARCH_DOCS_DIR / "RF_BASELINE_RECONCILIATION.md"
        trace_doc = RESEARCH_DOCS_DIR / "EMPIRICAL_EVIDENCE_TRACEABILITY.md"
        self.assertTrue(forensic_doc.exists())
        self.assertTrue(trace_doc.exists())

        for doc in [forensic_doc, trace_doc]:
            text = doc.read_text(encoding="utf-8")
            self.assertIn("UNRESOLVED", text)
            self.assertIn("0.5854", text)
            self.assertIn("0.5873", text)

    def test_non_rf_models_identical_across_tables(self) -> None:
        """Verify that Logistic Regression, Decision Tree, and LightGBM are identical across baseline tables."""
        research_csv = TABLES_DIR / "research_baseline.csv"
        final_csv = FINAL_DIR / "baseline_results.csv"

        with open(research_csv, "r", encoding="utf-8") as f:
            res_models = {r["model"]: r for r in csv.DictReader(f)}
        with open(final_csv, "r", encoding="utf-8") as f:
            fin_models = {r["model"]: r for r in csv.DictReader(f)}

        for m in ["logistic_regression", "decision_tree", "lightgbm"]:
            self.assertEqual(float(res_models[m]["val_macro_f1"]), float(fin_models[m]["val_macro_f1"]))
            self.assertEqual(float(res_models[m]["test_macro_f1"]), float(fin_models[m]["test_macro_f1"]))
            self.assertEqual(float(res_models[m]["test_accuracy"]), float(fin_models[m]["test_accuracy"]))
            self.assertEqual(float(res_models[m]["model_size_kb"]), float(fin_models[m]["model_size_kb"]))

    def test_simple_random_forest_fallback_artifact_identity(self) -> None:
        """Verify the 499-byte fallback model used for pure physical baseline."""
        real_rf_path = MODELS_DIR / "real_baseline" / "random_forest.joblib"
        root_rf_path = MODELS_DIR / "random_forest.joblib"

        self.assertTrue(real_rf_path.exists())
        self.assertTrue(root_rf_path.exists())

        real_bytes = real_rf_path.read_bytes()
        root_bytes = root_rf_path.read_bytes()

        self.assertEqual(len(real_bytes), 499)
        self.assertEqual(real_bytes, root_bytes)
        sha = hashlib.sha256(real_bytes).hexdigest()
        self.assertEqual(sha, "9440e23ce67f94cef07ef0d779568e50faba23b4ada61ac91573bf77dd4d6ad9")

        pkg = joblib.load(real_rf_path)
        self.assertEqual(pkg["model"].__class__.__name__, "_SimpleRandomForest")

    def test_missing_prediction_manifests_prevent_silent_verified(self) -> None:
        """Verify that absent prediction files for secondary RF run prevent claiming VERIFIED."""
        report = (RESEARCH_DOCS_DIR / "RF_BASELINE_RECONCILIATION.md").read_text(encoding="utf-8")
        # Ensure that baseline_results.csv (0.5873) is not labeled as VERIFIED
        lines = [l for l in report.splitlines() if "0.5873" in l and "VERIFIED" in l]
        for line in lines:
            self.assertIn("UNRESOLVED", line, f"Row with 0.5873 must specify UNRESOLVED: {line}")


if __name__ == "__main__":
    unittest.main()
