"""
Unit Tests for Authoritative Dataset Registry and Scientific Integrity Guards.
"""

from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from training.dataset_registry import DatasetMetadata, DatasetOrigin, DatasetRegistry


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
        """Asserts that synthetic, real, and hybrid datasets are strictly differentiated."""
        v1 = self.registry.get_dataset("dataset_v1")
        self.assertEqual(v1.origin, DatasetOrigin.SYNTHETIC_FIXTURE)
        self.assertFalse(v1.is_real_data)
        self.assertFalse(v1.allows_benchmark_use)

        real_v1 = self.registry.get_dataset("dataset_real_v1")
        self.assertEqual(real_v1.origin, DatasetOrigin.REAL_DATA)
        self.assertTrue(real_v1.is_real_data)
        self.assertFalse(real_v1.is_hybrid)
        self.assertTrue(real_v1.allows_benchmark_use)
        self.assertEqual(real_v1.physical_flow_count, 121)
        self.assertEqual(real_v1.synthetic_flow_count, 0)

        v2 = self.registry.get_dataset("dataset_v2")
        self.assertEqual(v2.origin, DatasetOrigin.HYBRID_PERTURBED)
        self.assertFalse(v2.is_real_data)
        self.assertTrue(v2.is_hybrid)
        self.assertTrue(v2.allows_benchmark_use)
        self.assertEqual(v2.physical_flow_count, 121)
        self.assertEqual(v2.synthetic_flow_count, 180)

        demo = self.registry.get_dataset("demo_data")
        self.assertEqual(demo.origin, DatasetOrigin.DEMO_DATA)
        self.assertFalse(demo.is_real_data)
        self.assertFalse(demo.allows_benchmark_use)

    def test_validate_real_data_claim_guard(self) -> None:
        """Tests that validate_real_data_claim permits only pure REAL_DATA and rejects hybrid/synthetic/demo."""
        # 1. dataset_real_v1 (pure physical) is valid
        self.registry.validate_real_data_claim("dataset_real_v1")

        # 2. dataset_v2 (hybrid perturbed) must be rejected for pure real-data claim
        with self.assertRaises(ValueError) as ctx_v2:
            self.registry.validate_real_data_claim("dataset_v2")
        self.assertIn("SCIENTIFIC INTEGRITY VIOLATION", str(ctx_v2.exception))

        # 3. dataset_v1 (synthetic) must be rejected
        with self.assertRaises(ValueError) as ctx1:
            self.registry.validate_real_data_claim("dataset_v1")
        self.assertIn("SCIENTIFIC INTEGRITY VIOLATION", str(ctx1.exception))

        # 4. demo_data must be rejected
        with self.assertRaises(ValueError) as ctx2:
            self.registry.validate_real_data_claim("demo_data")
        self.assertIn("SCIENTIFIC INTEGRITY VIOLATION", str(ctx2.exception))

    def test_validate_benchmark_claim_guard(self) -> None:
        """Tests that validate_benchmark_claim permits REAL_DATA and HYBRID_PERTURBED, rejecting synthetic fixtures and demo data."""
        # 1. Both dataset_real_v1 and dataset_v2 are eligible for benchmarking
        self.registry.validate_benchmark_claim("dataset_real_v1")
        self.registry.validate_benchmark_claim("dataset_v2")

        # 2. dataset_v1 (synthetic fixture) must be rejected
        with self.assertRaises(ValueError) as ctx1:
            self.registry.validate_benchmark_claim("dataset_v1")
        self.assertIn("SCIENTIFIC INTEGRITY VIOLATION", str(ctx1.exception))

        # 3. demo_data must be rejected
        with self.assertRaises(ValueError) as ctx2:
            self.registry.validate_benchmark_claim("demo_data")
        self.assertIn("SCIENTIFIC INTEGRITY VIOLATION", str(ctx2.exception))

    def test_record_level_integrity_guard(self) -> None:
        """Tests that validate_real_data_claim rejects corrupted record lists."""
        valid_records = [
            {"flow_id": "f1", "data_origin": "real", "capture_source": "REAL_LIVE_CAPTURE"},
            {"flow_id": "f2", "data_origin": "real", "capture_source": "REAL_LIVE_CAPTURE"},
        ]
        self.registry.validate_real_data_claim("dataset_real_v1", records=valid_records)

        corrupted_records = [
            {"flow_id": "f1", "data_origin": "real", "capture_source": "REAL_LIVE_CAPTURE"},
            {"flow_id": "f2", "data_origin": "synthetic", "capture_source": "SYNTHETIC_TEST"},
        ]
        with self.assertRaises(ValueError) as ctx:
            self.registry.validate_real_data_claim("dataset_real_v1", records=corrupted_records)
        self.assertIn("SCIENTIFIC INTEGRITY VIOLATION", str(ctx.exception))

    def test_audit_execution_and_output_artifacts(self) -> None:
        """Verifies audit_all_datasets generates valid CSV reports in an isolated temp directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            inv, qual = self.registry.audit_all_datasets(output_dir=tmp_path)
            self.assertGreaterEqual(len(inv), 4)
            self.assertGreaterEqual(len(qual), 3)

            inv_path = tmp_path / "research_dataset_inventory.csv"
            qual_path = tmp_path / "research_dataset_quality.csv"
            self.assertTrue(inv_path.exists())
            self.assertTrue(qual_path.exists())

            with open(qual_path, "r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
                v2_row = next(r for r in rows if r["dataset_id"] == "dataset_v2")
                self.assertEqual(v2_row["origin_classification"], "HYBRID_PERTURBED")
                self.assertEqual(v2_row["data_leakage_detected"], "False")
                self.assertEqual(v2_row["train_test_group_overlap"], "0")

    def test_metadata_invariants_validation(self) -> None:
        """Verifies flow count arithmetic and provenance consistency in DatasetMetadata."""
        def make_meta(origin: DatasetOrigin, flow_count: int, physical: int = 0, synthetic: int = 0) -> DatasetMetadata:
            return DatasetMetadata(
                dataset_id="test_meta",
                version="1.0.0",
                origin=origin,
                source_description="Test metadata",
                manifest_path=None,
                primary_feature_path=None,
                collection_dates=["2026-08-23"],
                traffic_classes=["Web", "Video"],
                session_count=10,
                flow_count=flow_count,
                environments=["env1"],
                network_types=["wifi"],
                tunnel_states=["direct"],
                activity_variants=["test_variant"],
                cleaning_policy="test",
                exclusion_policy="test",
                feature_schema="test",
                checksum_sha256="",
                physical_flow_count=physical,
                synthetic_flow_count=synthetic,
            )

        # 1. REAL_DATA: must not contain synthetic flows
        meta_real = make_meta(DatasetOrigin.REAL_DATA, flow_count=100, physical=100, synthetic=0)
        self.assertTrue(meta_real.is_real_data)
        with self.assertRaises(ValueError) as ctx:
            make_meta(DatasetOrigin.REAL_DATA, flow_count=100, physical=100, synthetic=10)
        self.assertIn("cannot contain synthetic flows", str(ctx.exception))

        # 2. HYBRID_PERTURBED: must contain both physical and synthetic flows
        meta_hybrid = make_meta(DatasetOrigin.HYBRID_PERTURBED, flow_count=300, physical=120, synthetic=180)
        self.assertTrue(meta_hybrid.is_hybrid)
        with self.assertRaises(ValueError) as ctx:
            make_meta(DatasetOrigin.HYBRID_PERTURBED, flow_count=300, physical=0, synthetic=300)
        self.assertIn("must contain both physical and synthetic flows", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            make_meta(DatasetOrigin.HYBRID_PERTURBED, flow_count=300, physical=300, synthetic=0)
        self.assertIn("must contain both physical and synthetic flows", str(ctx.exception))

        # 3. HYBRID_PERTURBED: physical + synthetic must equal flow_count
        with self.assertRaises(ValueError) as ctx:
            make_meta(DatasetOrigin.HYBRID_PERTURBED, flow_count=301, physical=120, synthetic=180)
        self.assertIn("flow count mismatch", str(ctx.exception))

        # 4. SYNTHETIC_FIXTURE and DEMO_DATA: legitimate metadata without physical/synthetic constraints
        synth = make_meta(DatasetOrigin.SYNTHETIC_FIXTURE, flow_count=12)
        self.assertEqual(synth.origin, DatasetOrigin.SYNTHETIC_FIXTURE)
        demo = make_meta(DatasetOrigin.DEMO_DATA, flow_count=20)
        self.assertEqual(demo.origin, DatasetOrigin.DEMO_DATA)


if __name__ == "__main__":
    unittest.main()
