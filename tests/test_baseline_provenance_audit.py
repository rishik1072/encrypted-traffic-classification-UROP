"""
Deterministic Unit and Regression Tests for Baseline Provenance and Split Consistency.

Tests all requirements from Task 5:
1. Baseline dataset identity and provenance in DatasetRegistry.
2. Dataset and split count consistency (301-flow hybrid dataset_v2 vs 121-flow physical dataset_real_v1).
3. Incorrect dataset-origin labels (detecting and failing contradictory 'REAL_DATA' labels on dataset_v2).
4. Missing or inconsistent provenance evidence (producing UNVERIFIED).
5. The distinction between historical metric tables and reproduced evaluation metrics.
6. Claims that remain UNVERIFIED when pure real-data reproduction evidence is absent.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from scripts.validate_research_claims import (
    ValidationStatus,
    validate_baseline_table,
    validate_claims_ledger,
)
from training.dataset_registry import DatasetOrigin, DatasetRegistry

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestBaselineProvenanceAudit(unittest.TestCase):
    """Audits dataset identity, provenance truth, and split consistency for the baseline benchmark."""

    def setUp(self) -> None:
        self.registry = DatasetRegistry(PROJECT_ROOT)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # 1. Baseline dataset identity and provenance
    def test_baseline_dataset_identity_and_provenance(self) -> None:
        """Verifies authoritative origin and composition of dataset_v2 and dataset_real_v1."""
        meta_v2 = self.registry.get_dataset("dataset_v2")
        self.assertEqual(meta_v2.origin, DatasetOrigin.HYBRID_PERTURBED)
        self.assertFalse(meta_v2.is_real_data)
        self.assertTrue(meta_v2.is_hybrid)
        self.assertEqual(meta_v2.physical_flow_count, 121)
        self.assertEqual(meta_v2.synthetic_flow_count, 180)
        self.assertEqual(meta_v2.flow_count, 301)
        self.assertEqual(meta_v2.session_count, 150)
        self.assertTrue(meta_v2.allows_benchmark_use)

        meta_real = self.registry.get_dataset("dataset_real_v1")
        self.assertEqual(meta_real.origin, DatasetOrigin.REAL_DATA)
        self.assertTrue(meta_real.is_real_data)
        self.assertFalse(meta_real.is_hybrid)
        self.assertEqual(meta_real.physical_flow_count, 121)
        self.assertEqual(meta_real.synthetic_flow_count, 0)
        self.assertEqual(meta_real.flow_count, 121)
        self.assertEqual(meta_real.session_count, 60)

    # 2. Dataset and split count consistency
    def test_dataset_and_split_count_consistency(self) -> None:
        """Verifies count consistency between dataset_v2 (301 flows) and splits/real_clean (121 flows)."""
        baseline_csv = PROJECT_ROOT / "results" / "tables" / "research_baseline.csv"
        self.assertTrue(baseline_csv.exists())

        with open(baseline_csv, "r", encoding="utf-8") as f:
            baseline_rows = list(csv.DictReader(f))

        # research_baseline.csv has 205 train, 48 val, 48 test = 301 flows
        first_row = baseline_rows[0]
        n_train = int(first_row["train_count"])
        n_val = int(first_row["validation_count"])
        n_test = int(first_row["test_count"])
        total_baseline_flows = n_train + n_val + n_test

        self.assertEqual(n_train, 205)
        self.assertEqual(n_val, 48)
        self.assertEqual(n_test, 48)
        self.assertEqual(total_baseline_flows, 301)

        # On-disk splits in data/processed/splits/real_clean/ have 85 train, 24 val, 12 test = 121 flows
        splits_dir = PROJECT_ROOT / "data" / "processed" / "splits" / "real_clean"
        with open(splits_dir / "train.csv", "r", encoding="utf-8") as f:
            tr_disk = sum(1 for _ in f) - 1
        with open(splits_dir / "validation.csv", "r", encoding="utf-8") as f:
            val_disk = sum(1 for _ in f) - 1
        with open(splits_dir / "test.csv", "r", encoding="utf-8") as f:
            te_disk = sum(1 for _ in f) - 1
        total_disk_flows = tr_disk + val_disk + te_disk

        self.assertEqual(tr_disk, 85)
        self.assertEqual(val_disk, 24)
        self.assertEqual(te_disk, 12)
        self.assertEqual(total_disk_flows, 121)

        # Confirm the discrepancy: research_baseline.csv does NOT match splits/real_clean on disk
        self.assertNotEqual(total_baseline_flows, total_disk_flows)
        self.assertEqual(total_baseline_flows, 301)  # dataset_v2
        self.assertEqual(total_disk_flows, 121)      # dataset_real_v1

    # 3. Incorrect dataset-origin labels
    def test_incorrect_dataset_origin_labels(self) -> None:
        """Asserts that research_baseline.csv's contradictory 'REAL_DATA' label fails validation."""
        baseline_csv = PROJECT_ROOT / "results" / "tables" / "research_baseline.csv"
        res = validate_baseline_table(baseline_csv, project_root=PROJECT_ROOT)

        # The historical table claims dataset_origin=REAL_DATA for dataset_v2 -> Must return FAIL
        self.assertEqual(res.status, ValidationStatus.FAIL)
        self.assertIn("Provenance contradiction", res.reason)
        self.assertIn("HYBRID_PERTURBED", res.reason)

        # Now test that a corrected copy stating HYBRID_PERTURBED truthfully passes validation
        with open(baseline_csv, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        corrected_csv = self.temp_path / "research_baseline_corrected.csv"
        fieldnames = list(rows[0].keys())
        for r in rows:
            r["dataset_origin"] = "HYBRID_PERTURBED"

        with open(corrected_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        res_corrected = validate_baseline_table(corrected_csv, project_root=PROJECT_ROOT)
        self.assertEqual(res_corrected.status, ValidationStatus.PASS)
        self.assertIn("hybrid benchmark", res_corrected.reason)

    # 4. Missing or inconsistent provenance evidence
    def test_missing_or_inconsistent_provenance_evidence(self) -> None:
        """Asserts that unknown dataset versions or missing provenance return UNVERIFIED."""
        baseline_csv = PROJECT_ROOT / "results" / "tables" / "research_baseline.csv"
        with open(baseline_csv, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        # Modify dataset version to unknown version
        unknown_csv = self.temp_path / "research_baseline_unknown.csv"
        for r in rows:
            r["dataset_version"] = "99.9.9"
            r["dataset_origin"] = "HYBRID_PERTURBED"

        with open(unknown_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        res_unknown = validate_baseline_table(unknown_csv, project_root=PROJECT_ROOT)
        self.assertEqual(res_unknown.status, ValidationStatus.UNVERIFIED)
        self.assertIn("not cataloged in DatasetRegistry", res_unknown.reason)

    # 5. Distinction between historical metric and reproduced metric
    def test_distinction_between_historical_metric_and_reproduced_metric(self) -> None:
        """Verifies separation between static historical CSV artifacts and empirical code reproduction."""
        # 1. Historical result table on dataset_v2
        baseline_csv = PROJECT_ROOT / "results" / "tables" / "research_baseline.csv"
        with open(baseline_csv, "r", encoding="utf-8") as f:
            rows = {r["model"]: r for r in csv.DictReader(f)}

        rf_hist_f1 = float(rows["random_forest"]["test_macro_f1"])
        rf_hist_acc = float(rows["random_forest"]["test_accuracy"])
        self.assertAlmostEqual(rf_hist_f1, 0.5857, places=3)
        self.assertAlmostEqual(rf_hist_acc, 0.5833, places=3)

        # 2. Historical physical baseline result on dataset_real_v1 (Phase 2, N=12)
        real_phys_csv = PROJECT_ROOT / "results" / "tables" / "real_final_baseline_result.csv"
        self.assertTrue(real_phys_csv.exists())
        with open(real_phys_csv, "r", encoding="utf-8") as f:
            real_phys_rows = list(csv.DictReader(f))
        first_phys = real_phys_rows[0]
        phys_f1 = float(first_phys["test_macro_f1"])
        phys_samples = int(first_phys["test_samples"])

        # The pure physical traffic test achieved 0.0833 on 12 test samples, NOT ~0.58
        self.assertEqual(phys_samples, 12)
        self.assertAlmostEqual(phys_f1, 0.0833, places=3)
        self.assertNotEqual(rf_hist_f1, phys_f1)

    # 6. Claims that remain UNVERIFIED when reproduction evidence is absent
    def test_claims_remain_unverified_when_reproduction_evidence_is_absent(self) -> None:
        """Asserts that claims asserting pure REAL_DATA on dataset_v2 remain UNVERIFIED."""
        ledger_path = PROJECT_ROOT / "docs" / "research" / "CLAIMS_LEDGER.md"
        results = validate_claims_ledger(ledger_path, project_root=PROJECT_ROOT)

        r09_results = [r for r in results if "R09" in r.claim_id]
        self.assertTrue(len(r09_results) > 0)
        for r in r09_results:
            # Must be UNVERIFIED because pure physical evidence is absent for dataset_v2
            self.assertEqual(r.status, ValidationStatus.UNVERIFIED)
            self.assertIn("UNVERIFIED", r.reason)


if __name__ == "__main__":
    unittest.main()
