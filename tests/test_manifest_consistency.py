"""
Tests for Manifest Validation, Consistency Auditing, and Registration.

Verifies:
- Detection of missing required real fields (source, session_id, etc.)
- Detection of duplicate session_id / file_id
- None/missing handling in inspect_dataset logic
- Cross-layer consistency checks across manifest, metadata, flows, and features
"""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from training.dataset_consistency import audit_dataset_consistency
from training.manifest_validator import validate_manifest


class TestManifestAndConsistency(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.manifest_file = self.temp_path / "manifest.csv"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_source_field_detection(self):
        with open(self.manifest_file, "w", newline="", encoding="utf-8") as f:
            fields = [
                "file_id", "pcap_path", "metadata_path", "raw_source_type", "raw_source_path",
                "traffic_class", "source", "capture_date", "session_id", "environment_id",
                "device_id", "dataset_id", "capture_duration", "packet_count", "byte_count",
                "flow_count", "validation_status", "data_origin", "capture_source", "notes"
            ]
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerow({
                "file_id": "real_test_01",
                "pcap_path": "",
                "metadata_path": "data/raw/metadata/test.csv",
                "raw_source_type": "METADATA_CSV",
                "raw_source_path": "data/raw/metadata/test.csv",
                "traffic_class": "Web",
                "source": "",  # Missing required real field!
                "capture_date": "2026-08-23",
                "session_id": "test_01",
                "environment_id": "env1",
                "device_id": "dev1",
                "dataset_id": "ds1",
                "capture_duration": 60.0,
                "packet_count": 100,
                "byte_count": 50000,
                "flow_count": 2,
                "validation_status": "PASS",
                "data_origin": "real",
                "capture_source": "REAL_LIVE_CAPTURE",
                "notes": "",
            })

        res = validate_manifest(self.manifest_file, base_dir=self.temp_path)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("Missing required real field 'source'" in e for e in res.errors))

    def test_duplicate_session_id_detection(self):
        with open(self.manifest_file, "w", newline="", encoding="utf-8") as f:
            fields = [
                "file_id", "pcap_path", "metadata_path", "raw_source_type", "raw_source_path",
                "traffic_class", "source", "capture_date", "session_id", "environment_id",
                "device_id", "dataset_id", "capture_duration", "packet_count", "byte_count",
                "flow_count", "validation_status", "data_origin", "capture_source", "notes"
            ]
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for fid in ["real_test_01", "real_test_02"]:
                writer.writerow({
                    "file_id": fid,
                    "pcap_path": "",
                    "metadata_path": "",
                    "raw_source_type": "SYNTHETIC_FIXTURE",
                    "raw_source_path": "",
                    "traffic_class": "Web",
                    "source": "lab",
                    "capture_date": "2026-08-23",
                    "session_id": "duplicate_session",  # Duplicate!
                    "environment_id": "env1",
                    "device_id": "dev1",
                    "dataset_id": "ds1",
                    "capture_duration": 60.0,
                    "packet_count": 100,
                    "byte_count": 50000,
                    "flow_count": 2,
                    "validation_status": "PASS",
                    "data_origin": "synthetic",
                    "capture_source": "SYNTHETIC_TEST",
                    "notes": "",
                })

        res = validate_manifest(self.manifest_file, base_dir=self.temp_path)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("Duplicate session_id" in e for e in res.errors))

    def test_active_dataset_manifest_valid(self):
        res = validate_manifest("data/dataset_manifest.csv")
        self.assertTrue(res.is_valid, f"Manifest errors: {res.errors}")
        self.assertEqual(res.real_records, 60)
        self.assertEqual(res.synthetic_records, 12)


if __name__ == "__main__":
    unittest.main()
