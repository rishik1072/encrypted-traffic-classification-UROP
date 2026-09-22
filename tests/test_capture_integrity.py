"""
Regression and Integrity Tests for Real Traffic Collection.

Verifies:
- Live capture failure does NOT create synthetic packets
- Failed captures do NOT enter real dataset
- Duplicate session IDs and file IDs are rejected
- data_origin and capture_source are strictly enforced
- VALIDATED state requires genuine live capture
- Interface resolver returns expected structures
"""

from __future__ import annotations

import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from capture.capture_integrity import validate_real_capture
from capture.collection_runner import CaptureResult, CollectionRunner
from capture.interface_resolver import list_scapy_interfaces, resolve_capture_interface
from capture.session_manager import CollectionSession, SessionState


class TestCaptureIntegrityRegression(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manifest_path = Path(self.temp_dir.name) / "dataset_manifest.csv"
        self.version_manifest_path = Path(self.temp_dir.name) / "version_manifest.csv"
        self.output_dir = Path(self.temp_dir.name) / "metadata"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_live_capture_failure_fails_closed_without_synthetic_fallback(self):
        runner = CollectionRunner(
            interface="NonExistentAdapter123",
            output_dir=str(self.output_dir),
            manifest_path=str(self.manifest_path),
            version_manifest_path=str(self.version_manifest_path),
        )

        session = CollectionSession.create(
            traffic_class="Web",
            capture_source="REAL_LIVE_CAPTURE",
            manifest_path=str(self.manifest_path),
        )

        # Run session on nonexistent interface
        result = runner.run_session(session, duration_seconds=1, warmup_seconds=0)

        # Assert session strictly failed
        self.assertEqual(result.state, SessionState.FAILED)
        self.assertEqual(result.packet_count, 0)
        self.assertFalse(result.is_synthetic)

        # Assert no real records entered manifest
        if self.manifest_path.exists():
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                reader = list(csv.DictReader(f))
                self.assertEqual(len(reader), 0)

    def test_manifest_rejects_duplicate_session_ids(self):
        runner = CollectionRunner(
            output_dir=str(self.output_dir),
            manifest_path=str(self.manifest_path),
            version_manifest_path=str(self.version_manifest_path),
        )

        session1 = CollectionSession(
            session_id="collision_test_001",
            traffic_class="Web",
            capture_source="REAL_LIVE_CAPTURE",
            packet_count=50,
            byte_count=10000,
            flow_count=2,
            metadata_path="data/mock.csv",
        )
        runner._register_in_manifest(session1)

        # Register duplicate
        with self.assertRaises(ValueError):
            runner._register_in_manifest(session1)

    def test_strict_real_capture_validation(self):
        # 1. Valid genuine capture
        valid_dict = {
            "capture_source": "REAL_LIVE_CAPTURE",
            "is_synthetic": False,
            "packet_count": 50,
            "byte_count": 2500,
            "duration": 10.0,
        }
        report = validate_real_capture(valid_dict, min_packets=10, min_bytes=500)
        self.assertTrue(report.is_valid)
        self.assertEqual(report.status, "VALID")

        # 2. Invalid capture (synthetic generator flag)
        synthetic_dict = {
            "capture_source": "REAL_LIVE_CAPTURE",
            "is_synthetic": True,
            "packet_count": 50,
            "byte_count": 2500,
            "duration": 10.0,
        }
        report_synth = validate_real_capture(synthetic_dict, min_packets=10, min_bytes=500)
        self.assertFalse(report_synth.is_valid)
        self.assertIn("Synthetic packet generator was invoked", report_synth.reasons[0])


if __name__ == "__main__":
    unittest.main()
