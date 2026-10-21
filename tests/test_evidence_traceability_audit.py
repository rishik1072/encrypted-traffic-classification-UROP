"""
Test Suite: Empirical Results Reconciliation and Evidence Traceability Audit.

Validates:
1. Reconciled and unresolved tracking of hybrid baseline metrics (0.5854/0.5857 vs 0.5873).
2. Pure physical baseline metrics (0.0833) mathematical and error-analysis verification ($N=12$).
3. Dataset origin labels agreement between dataset registry, inventory, and baseline result tables.
4. Metric denominators matching source result artifacts (Early prediction 7/11, Selective prediction 19/26).
5. Completeness and validity of evidence matrix entries in docs/research/EMPIRICAL_EVIDENCE_TRACEABILITY.md.
6. Guard preventing missing prediction files or manifests from silently producing VERIFIED status.
"""

from __future__ import annotations

import csv
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TABLES_DIR = PROJECT_ROOT / "results" / "tables"
FINAL_DIR = PROJECT_ROOT / "results" / "final"
RESEARCH_DOCS_DIR = PROJECT_ROOT / "docs" / "research"

from training.dataset_registry import DatasetOrigin, DatasetRegistry


class TestEvidenceTraceabilityAudit(unittest.TestCase):
    """Rigorous audit checks for Task 7 empirical evidence traceability."""

    def setUp(self) -> None:
        self.registry = DatasetRegistry(PROJECT_ROOT)
        self.matrix_path = RESEARCH_DOCS_DIR / "EMPIRICAL_EVIDENCE_TRACEABILITY.md"
        self.assertTrue(self.matrix_path.exists(), "EMPIRICAL_EVIDENCE_TRACEABILITY.md must exist.")

    def test_hybrid_baseline_scores_tracked_and_unresolved(self) -> None:
        """
        Verify that both 0.5854/0.5857 and 0.5873 are preserved in their respective files,
        deterministic models are identical, and the relationship is explicitly classified as UNRESOLVED.
        """
        research_base_path = TABLES_DIR / "research_baseline.csv"
        final_base_path = FINAL_DIR / "baseline_results.csv"
        self.assertTrue(research_base_path.exists())
        self.assertTrue(final_base_path.exists())

        with open(research_base_path, "r", encoding="utf-8") as f:
            res_rows = {r["model"]: r for r in csv.DictReader(f)}
        with open(final_base_path, "r", encoding="utf-8") as f:
            fin_rows = {r["model"]: r for r in csv.DictReader(f)}

        # Deterministic models must have identical test macro F1 and test accuracy across files
        for m in ["logistic_regression", "decision_tree", "lightgbm"]:
            self.assertIn(m, res_rows)
            self.assertIn(m, fin_rows)
            self.assertAlmostEqual(float(res_rows[m]["test_macro_f1"]), float(fin_rows[m]["test_macro_f1"]), places=4)
            self.assertAlmostEqual(float(res_rows[m]["test_accuracy"]), float(fin_rows[m]["test_accuracy"]), places=4)

        # Random Forest scores differ: 0.5854 in research_baseline.csv vs 0.5873 in baseline_results.csv
        rf_res_f1 = float(res_rows["random_forest"]["test_macro_f1"])
        rf_fin_f1 = float(fin_rows["random_forest"]["test_macro_f1"])
        self.assertAlmostEqual(rf_res_f1, 0.5854, places=4)
        self.assertAlmostEqual(rf_fin_f1, 0.5873, places=4)

        # The traceability matrix must explicitly mark this divergence as UNRESOLVED
        matrix_text = self.matrix_path.read_text(encoding="utf-8")
        self.assertIn("UNRESOLVED", matrix_text)
        self.assertIn("0.5854", matrix_text)
        self.assertIn("0.5873", matrix_text)

    def test_physical_baseline_metrics_and_error_breakdown(self) -> None:
        """
        Verify physical baseline Macro-F1 = 0.0833 on dataset_real_v1 test partition (N=12).
        Trace the score mathematically to exactly 1 correct flow out of 12.
        """
        phys_result_path = TABLES_DIR / "real_final_baseline_result.csv"
        comparison_path = TABLES_DIR / "real_baseline_model_comparison.csv"
        error_path = TABLES_DIR / "real_baseline_error_analysis.csv"

        self.assertTrue(phys_result_path.exists())
        self.assertTrue(comparison_path.exists())
        self.assertTrue(error_path.exists())

        with open(phys_result_path, "r", encoding="utf-8") as f:
            res_rows = list(csv.DictReader(f))
        self.assertEqual(len(res_rows), 1)
        row = res_rows[0]
        self.assertEqual(row["selected_model"], "random_forest")
        self.assertEqual(int(row["test_samples"]), 12)
        self.assertAlmostEqual(float(row["test_accuracy"]), 0.0833, places=4)
        self.assertAlmostEqual(float(row["test_macro_f1"]), 0.0833, places=4)

        # Audit error analysis file: exactly 11 misclassifications for random_forest out of 12 test flows
        with open(error_path, "r", encoding="utf-8") as f:
            err_rows = list(csv.DictReader(f))
        rf_errors = [r for r in err_rows if r["model"] == "random_forest"]
        self.assertEqual(len(rf_errors), 11, "Random Forest must have exactly 11 misclassifications out of 12 flows.")

        # Exactly 1 flow is correct: 1 / 12 = 0.08333...
        correct_count = 12 - len(rf_errors)
        self.assertEqual(correct_count, 1)
        expected_accuracy = round(1.0 / 12.0, 4)
        self.assertAlmostEqual(float(row["test_accuracy"]), expected_accuracy, places=4)

    def test_dataset_origin_labels_agree_with_registry(self) -> None:
        """Verify that dataset origin labels in inventory and baseline tables match DatasetRegistry."""
        inv_path = TABLES_DIR / "research_dataset_inventory.csv"
        self.assertTrue(inv_path.exists())

        with open(inv_path, "r", encoding="utf-8") as f:
            inv_rows = {r["dataset_id"]: r for r in csv.DictReader(f)}

        for meta in self.registry.list_datasets():
            ds_id = meta.dataset_id
            if ds_id in inv_rows:
                self.assertEqual(
                    inv_rows[ds_id]["origin_type"],
                    meta.origin.value,
                    f"Inventory origin mismatch for {ds_id}",
                )

        # Baseline table dataset origin check
        base_path = TABLES_DIR / "research_baseline.csv"
        with open(base_path, "r", encoding="utf-8") as f:
            base_rows = list(csv.DictReader(f))
        for r in base_rows:
            ds_ver = r["dataset_version"]
            # dataset_v2 is registered as 2.0.0
            if ds_ver == "2.0.0":
                v2_meta = self.registry.get_dataset("dataset_v2")
                self.assertEqual(v2_meta.origin, DatasetOrigin.HYBRID_PERTURBED)

    def test_metric_denominators_match_result_artifacts(self) -> None:
        """
        Verify that reported metrics match exact sample denominators in underlying CSVs:
        - Early prediction N=3: 11 flows classified (7 correct), coverage 11/12
        - Selective prediction tau=0.70: 26 flows accepted (19 correct), coverage 26/48
        - REG-05: 120 test flows (112 correct)
        """
        # 1. Early prediction
        early_path = TABLES_DIR / "research_early_prediction.csv"
        self.assertTrue(early_path.exists())
        with open(early_path, "r", encoding="utf-8") as f:
            early_rows = {r["packet_horizon"]: r for r in csv.DictReader(f)}
        h3 = early_rows["3"]
        self.assertEqual(int(h3["total_test_flows"]), 12)
        self.assertEqual(int(h3["flows_classified"]), 11)
        self.assertAlmostEqual(float(h3["coverage"]), 11.0 / 12.0, places=4)
        self.assertAlmostEqual(float(h3["accuracy"]), 7.0 / 11.0, places=4)

        # 2. Selective prediction
        sel_path = TABLES_DIR / "research_selective_prediction.csv"
        self.assertTrue(sel_path.exists())
        with open(sel_path, "r", encoding="utf-8") as f:
            sel_rows = [r for r in csv.DictReader(f) if r["split"] == "test" and float(r["threshold"]) == 0.7]
        self.assertEqual(len(sel_rows), 1)
        s7 = sel_rows[0]
        self.assertEqual(int(s7["total_samples"]), 48)
        self.assertEqual(int(s7["accepted_samples"]), 26)
        self.assertAlmostEqual(float(s7["coverage"]), 26.0 / 48.0, places=4)
        self.assertAlmostEqual(float(s7["selective_accuracy"]), 19.0 / 26.0, places=4)
        self.assertAlmostEqual(float(s7["error_rate_accepted"]), 7.0 / 26.0, places=4)

        # 3. REG-05 Generalization
        gen_path = TABLES_DIR / "research_generalization_scorecard.csv"
        self.assertTrue(gen_path.exists())
        with open(gen_path, "r", encoding="utf-8") as f:
            gen_rows = {r["regime_id"]: r for r in csv.DictReader(f)}
        reg05 = gen_rows["REG-05"]
        self.assertEqual(int(reg05["train_count"]), 181)
        self.assertEqual(int(reg05["test_count"]), 120)
        self.assertAlmostEqual(float(reg05["accuracy"]), 112.0 / 120.0, places=4)
        self.assertAlmostEqual(float(reg05["macro_f1"]), 0.9325, places=4)

    def test_every_primary_claim_has_traceable_evidence_matrix_entry(self) -> None:
        """Verify that every primary experimental claim is documented with a valid status in the matrix."""
        content = self.matrix_path.read_text(encoding="utf-8")
        valid_statuses = {
            "VERIFIED",
            "PARTIALLY VERIFIED",
            "UNVERIFIED",
            "CONTRADICTED",
            "HISTORICAL",
            "RETRACTED",
            "UNRESOLVED",
        }

        required_claim_ids = [
            "EXP-01",
            "EXP-R09-RF",
            "EXP-R09-DT",
            "EXP-R09-LGBM",
            "EXP-R09-LR",
            "EXP-R01",
            "EXP-R11-EARLY",
            "EXP-R12-SELECT",
            "EXP-R13-REG05",
            "EXP-R13-REG08A",
            "EXP-R13-REG08B",
            "EXP-R14-LAT",
            "EXP-R14-SIZE",
            "EXP-R15-SMOKE",
            "EXP-R16-CALIB",
            "EXP-R17-SEC",
        ]

        for claim_id in required_claim_ids:
            self.assertIn(claim_id, content, f"Claim ID '{claim_id}' must be present in traceability matrix.")

        # Check that table contains only authorized verification statuses
        lines = content.splitlines()
        matrix_table_lines = [l for l in lines if l.startswith("| **EXP-")]
        self.assertGreaterEqual(len(matrix_table_lines), len(required_claim_ids))
        for line in matrix_table_lines:
            cols = [c.strip() for c in line.split("|")]
            # Verification status is column index 8 (1-based index 8 in table: Claim, Sci Claim, Metric, Dataset, Artifact, Split, Repro, Status, Limitations, Action)
            status_found = False
            for col in cols:
                # Strip markdown bolding if present
                clean_col = col.replace("**", "").strip()
                if clean_col in valid_statuses:
                    status_found = True
                    break
            self.assertTrue(status_found, f"Table row missing valid verification status: {line}")

    def test_missing_prediction_files_prevent_silent_verified(self) -> None:
        """
        Verify that missing prediction or split manifests cannot silently yield VERIFIED status.
        Specifically, baseline Run 2 (0.5873) lacks a saved raw prediction artifact, so its
        exact numerical divergence with Run 1 cannot be marked VERIFIED.
        """
        content = self.matrix_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        rf_entry = [l for l in lines if "| **EXP-R09-RF**" in l]
        self.assertEqual(len(rf_entry), 1)
        self.assertIn("UNRESOLVED", rf_entry[0], "Random Forest divergence must be marked UNRESOLVED.")
        self.assertNotIn("VERIFIED", rf_entry[0].split("|")[8], "RF divergence must NOT be marked VERIFIED in status column.")


if __name__ == "__main__":
    unittest.main()
