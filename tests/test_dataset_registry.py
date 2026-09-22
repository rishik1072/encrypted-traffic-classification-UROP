"""
Unit Tests for Authoritative Dataset Registry and Scientific Integrity Guards.
"""

from __future__ import annotations

import csv
from pathlib import Path
import unittest

from training.dataset_registry import DatasetOrigin, DatasetRegistry


class TestDatasetRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = DatasetRegistry()

    def test_registry_contains_core_datasets(self) -> None:
        """Verifies that all 5 cataloged datasets are registered."""
        ds_ids = [d.dataset_id for d in self.registry.list_datasets()]
        self.assertIn("dataset_v1", ds_ids)
        self.assertIn("dataset_real_v1", ds_ids)
        self.assertIn("dataset_v2", ds_ids)
        self.assertIn("demo_data", ds_ids)
        self.assertIn("external_benchmarks", ds_ids)

    def test_origin_classification_accuracy(self) -> None:
        """Asserts that synthetic and real datasets are strictly differentiated."""
        v1 = self.registry.get_dataset("dataset_v1")
        self.assertEqual(v1.origin, DatasetOrigin.SYNTHETIC_FIXTURE)
        self.assertFalse(v1.is_real_data)

        real_v1 = self.registry.get_dataset("dataset_real_v1")
        self.assertEqual(real_v1.origin, DatasetOrigin.REAL_DATA)
        self.assertTrue(real_v1.is_real_data)

        v2 = self.registry.get_dataset("dataset_v2")
        self.assertEqual(v2.origin, DatasetOrigin.REAL_DATA)
        self.assertTrue(v2.is_real_data)

        demo = self.registry.get_dataset("demo_data")
        self.assertEqual(demo.origin, DatasetOrigin.DEMO_DATA)
        self.assertFalse(demo.is_real_data)

    def test_validate_real_data_claim_guard(self) -> None:
        """Tests that validate_real_data_claim strictly rejects synthetic and demo data."""
        # 1. dataset_v2 is valid
        self.registry.validate_real_data_claim("dataset_v2")

        # 2. dataset_v1 (synthetic) must be rejected
        with self.assertRaises(ValueError) as ctx1:
            self.registry.validate_real_data_claim("dataset_v1")
        self.assertIn("SCIENTIFIC INTEGRITY VIOLATION", str(ctx1.exception))

        # 3. demo_data must be rejected
        with self.assertRaises(ValueError) as ctx2:
            self.registry.validate_real_data_claim("demo_data")
        self.assertIn("SCIENTIFIC INTEGRITY VIOLATION", str(ctx2.exception))

    def test_record_level_integrity_guard(self) -> None:
        """Tests that validate_real_data_claim rejects corrupted record lists."""
        valid_records = [
            {"flow_id": "f1", "data_origin": "real", "capture_source": "REAL_LIVE_CAPTURE"},
            {"flow_id": "f2", "data_origin": "real", "capture_source": "REAL_LIVE_CAPTURE"},
        ]
        self.registry.validate_real_data_claim("dataset_v2", records=valid_records)

        corrupted_records = [
            {"flow_id": "f1", "data_origin": "real", "capture_source": "REAL_LIVE_CAPTURE"},
            {"flow_id": "f2", "data_origin": "synthetic", "capture_source": "SYNTHETIC_TEST"},
        ]
        with self.assertRaises(ValueError) as ctx:
            self.registry.validate_real_data_claim("dataset_v2", records=corrupted_records)
        self.assertIn("SCIENTIFIC INTEGRITY VIOLATION", str(ctx.exception))

    def test_audit_execution_and_output_artifacts(self) -> None:
        """Verifies audit_all_datasets generates valid CSV reports."""
        inv, qual = self.registry.audit_all_datasets()
        self.assertGreaterEqual(len(inv), 4)
        self.assertGreaterEqual(len(qual), 3)

        inv_path = Path("results/tables/research_dataset_inventory.csv")
        qual_path = Path("results/tables/research_dataset_quality.csv")
        self.assertTrue(inv_path.exists())
        self.assertTrue(qual_path.exists())

        with open(qual_path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            v2_row = next(r for r in rows if r["dataset_id"] == "dataset_v2")
            self.assertEqual(v2_row["origin_classification"], "REAL_DATA")
            self.assertEqual(v2_row["data_leakage_detected"], "False")
            self.assertEqual(v2_row["train_test_group_overlap"], "0")


if __name__ == "__main__":
    unittest.main()
