"""
Unit and Integration Tests for Week 1 Traffic Collection Lab.
"""

from __future__ import annotations

import csv
import os
import tempfile
import unittest
from pathlib import Path

from capture.capture_validator import CaptureValidator
from capture.duplicate_detector import DuplicateDetector
from capture.metadata_exporter import MetadataExporter
from capture.session_manager import CollectionSession, SessionState


class TestCollectionLab(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.meta_dir = Path(self.temp_dir.name) / "metadata"
        self.meta_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_session_lifecycle(self):
        session = CollectionSession.create(traffic_class="Web", seq_num=1)
        self.assertEqual(session.state, SessionState.PREPARING)
        self.assertIn("web", session.session_id)

        session.transition_to(SessionState.WARMUP)
        self.assertEqual(session.state, SessionState.WARMUP)

        session.transition_to(SessionState.CAPTURING)
        self.assertEqual(session.state, SessionState.CAPTURING)

        session.transition_to(SessionState.VALIDATED)
        self.assertEqual(session.state, SessionState.VALIDATED)

    def test_metadata_exporter_whitelisting(self):
        exporter = MetadataExporter(output_dir=str(self.meta_dir))
        mock_packets = [
            {
                "timestamp": 100.0,
                "length": 500,
                "ip_version": 4,
                "protocol": "TCP",
                "source_port": 1234,
                "destination_port": 443,
                "tcp_flags": "SYN",
                "secret_payload_bytes": b"SENSITIVE_DATA",  # Should be omitted
            }
        ]
        meta_file = exporter.export_session_metadata("sess_001", "Web", mock_packets)
        self.assertTrue(Path(meta_file).exists())

        with open(meta_file, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            self.assertEqual(len(reader), 1)
            row = reader[0]
            self.assertIn("timestamp", row)
            self.assertIn("packet_length", row)
            self.assertNotIn("secret_payload_bytes", row)
            self.assertEqual(row["traffic_class"], "Web")

    def test_capture_validator(self):
        exporter = MetadataExporter(output_dir=str(self.meta_dir))
        validator = CaptureValidator(min_packets=5, min_bytes=100)

        # 1. Valid session
        valid_pkts = [
            {"timestamp": 100.0 + i * 0.1, "length": 100, "protocol": "TCP", "source_port": 5000 + i, "destination_port": 443}
            for i in range(10)
        ]
        val_file = exporter.export_session_metadata("valid_sess", "Web", valid_pkts)
        res = validator.validate_metadata_file(val_file)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.status, "PASS")

        # 2. Invalid session (insufficient packets)
        short_pkts = [{"timestamp": 100.0, "length": 10, "protocol": "TCP", "source_port": 5000, "destination_port": 443}]
        short_file = exporter.export_session_metadata("short_sess", "Web", short_pkts)
        res_short = validator.validate_metadata_file(short_file)
        self.assertFalse(res_short.is_valid)
        self.assertEqual(res_short.status, "FAIL")


if __name__ == "__main__":
    unittest.main()
