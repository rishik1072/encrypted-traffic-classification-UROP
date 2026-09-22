"""
Unit tests for dashboard/live_feed.py against the exact local API schema and payload.
"""

from __future__ import annotations

import io
import json
from typing import Any, Dict, List, Optional
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from dashboard.live_feed import load_live_predictions, normalize_api_record
from dashboard.schema import CanonicalPredictionRecord


class TestDashboardLiveFeed(unittest.TestCase):
    """Test suite for the authoritative Dashboard Live Feed loader."""

    def _create_sample_api_payload(self, count: int = 20, mode: str = "DEMO_MODE") -> Dict[str, Any]:
        """Creates a payload matching the exact Local API response format."""
        classes = ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"]
        families = ["Interactive", "Bulk_Streaming", "Interactive", "Interactive", "Bulk_Streaming", "Other"]
        predictions = []
        for i in range(count):
            idx = i % len(classes)
            predictions.append({
                "timestamp": 1787735596.0 + (i * 0.15),
                "flow_id": f"flow_{i:03d}_flow_00000",
                "session_id_hash": f"sess_{i:08x}",
                "model_id": "model_lightgbm_v1",
                "feature_profile": "lightweight_10",
                "predicted_family": families[idx],
                "predicted_class": classes[idx],
                "family_confidence": 0.97,
                "fine_confidence": 0.95,
                "composed_confidence": 0.9215,
                "prediction_state": "KNOWN_CLASS",
                "packets_observed": 8 + i,
                "elapsed_seconds": 0.35 + (i * 0.1),
                "latency_us": 175.5 + i,
                "event_id": f"DEMO-EVT-{i:05d}",
                "confidence": 0.9215,
                "prediction_version": "1.0.0",
                "operating_mode": mode,
                "protocol": "TCP" if idx % 2 == 0 else "UDP",
                "source_port": 1443 + i,
                "destination_port": 443,
                "byte_count": 1112 + (i * 50),
            })
        return {
            "count": count,
            "limit": 100,
            "predictions": predictions,
        }

    def test_20_records_loaded_successfully(self):
        """1. Tests that 20 records returned from the API are parsed into canonical records."""
        payload = self._create_sample_api_payload(20, mode="DEMO_MODE")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            records, meta = load_live_predictions(limit=20, mode="DEMO_MODE")

        self.assertEqual(len(records), 20)
        self.assertTrue(meta["connected"])
        self.assertEqual(meta["event_count"], 20)
        self.assertEqual(meta["raw_count"], 20)
        self.assertEqual(meta["normalized_count"], 20)
        self.assertEqual(meta["dropped_count"], 0)
        self.assertIsNone(meta["error"])

        # Check canonical record types & properties
        first = records[0]
        self.assertIsInstance(first, CanonicalPredictionRecord)
        self.assertTrue(first.confidence_valid)
        self.assertAlmostEqual(first.confidence, 0.9215)
        self.assertIn(first.predicted_class, ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"])
        self.assertIn(first.predicted_family, ["Interactive", "Bulk_Streaming", "Other"])

    def test_demo_mode_filtering(self):
        """2. Tests that DEMO_MODE events are accepted when dashboard is in DEMO_MODE."""
        payload = self._create_sample_api_payload(5, mode="DEMO_MODE")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            records, meta = load_live_predictions(limit=5, mode="DEMO_MODE")

        self.assertEqual(len(records), 5)
        self.assertEqual(meta["normalized_count"], 5)
        self.assertEqual(meta["dropped_count"], 0)

    def test_live_mode_filtering_drops_demo_records(self):
        """3. Tests that LIVE_MODE safely rejects DEMO_MODE records to prevent false live telemetry."""
        payload = self._create_sample_api_payload(5, mode="DEMO_MODE")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            records, meta = load_live_predictions(limit=5, mode="LIVE_MODE")

        self.assertEqual(len(records), 0)
        self.assertEqual(meta["dropped_count"], 5)
        self.assertIn("wrong operating mode", meta["drop_reasons"][0])

    def test_empty_response(self):
        """4. Tests handling of empty API predictions array."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"count": 0, "limit": 100, "predictions": []}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            records, meta = load_live_predictions(limit=100, mode="DEMO_MODE")

        self.assertEqual(len(records), 0)
        self.assertTrue(meta["connected"])
        self.assertEqual(meta["event_count"], 0)
        self.assertIsNone(meta["error"])

    def test_malformed_response_resilience(self):
        """5. Tests handling of malformed records within API predictions list."""
        corrupt_payload = {
            "count": 3,
            "limit": 100,
            "predictions": [
                {
                    "flow_id": "valid_flow_01",
                    "predicted_family": "Interactive",
                    "predicted_class": "Web",
                    "composed_confidence": 0.95,
                    "operating_mode": "DEMO_MODE",
                },
                "not_a_dictionary_corrupted_entry",
                {
                    "flow_id": "valid_flow_02",
                    "predicted_family": "Bulk_Streaming",
                    "predicted_class": "Video",
                    "composed_confidence": 0.88,
                    "operating_mode": "DEMO_MODE",
                },
            ],
        }
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(corrupt_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            records, meta = load_live_predictions(limit=100, mode="DEMO_MODE")

        self.assertEqual(len(records), 2)
        self.assertEqual(meta["raw_count"], 3)
        self.assertEqual(meta["normalized_count"], 2)
        self.assertEqual(meta["dropped_count"], 1)

    def test_http_failure_handling(self):
        """6. Tests handling of non-200 HTTP status and network errors."""
        # 500 error
        mock_err = urllib.error.HTTPError(
            url="http://127.0.0.1:8080/predictions",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=io.BytesIO(b"{}"),
        )
        with patch("urllib.request.urlopen", side_effect=mock_err):
            records, meta = load_live_predictions(limit=100, mode="DEMO_MODE")

        self.assertFalse(meta["connected"])
        self.assertIsNotNone(meta["error"])
        self.assertIn("500", meta["error"])

    def test_confidence_and_latency_mapping(self):
        """7. Tests exact normalization of composed_confidence and latency."""
        rec = {
            "timestamp": 1787735596.5,
            "flow_id": "test_flow_001",
            "predicted_family": "Interactive",
            "predicted_class": "Messaging",
            "composed_confidence": 0.912,
            "latency_us": 184.5,
            "operating_mode": "DEMO_MODE",
        }
        canon, is_valid, err = normalize_api_record(rec, target_mode="DEMO_MODE")
        self.assertTrue(is_valid)
        self.assertIsNotNone(canon)
        self.assertEqual(canon.predicted_family, "Interactive")
        self.assertEqual(canon.predicted_class, "Messaging")
        self.assertAlmostEqual(canon.confidence, 0.912)
        self.assertAlmostEqual(canon.latency_us, 184.5)

    def test_timestamp_handling_does_not_treat_demo_as_stale(self):
        """8. Tests that epoch timestamps from demo datasets are preserved without clock-drift drops."""
        historical_epoch = 1787734878.123
        rec = {
            "timestamp": historical_epoch,
            "flow_id": "demo_flow_historical",
            "predicted_class": "Web",
            "composed_confidence": 0.90,
            "operating_mode": "DEMO_MODE",
        }
        canon, is_valid, _ = normalize_api_record(rec, target_mode="DEMO_MODE")
        self.assertTrue(is_valid)
        self.assertIsNotNone(canon)
        self.assertIn(":", canon.timestamp)  # Formatted as HH:MM:SS

    def test_duplicate_flow_ids_with_unique_event_ids(self):
        """9. Tests that multiple updates to the same flow ID are preserved in chronological order."""
        events = [
            {
                "timestamp": 1787735596.0,
                "flow_id": "flow_shared_001",
                "event_id": "EVT-001",
                "packets_observed": 3,
                "composed_confidence": 0.60,
                "operating_mode": "DEMO_MODE",
            },
            {
                "timestamp": 1787735596.5,
                "flow_id": "flow_shared_001",
                "event_id": "EVT-002",
                "packets_observed": 10,
                "composed_confidence": 0.85,
                "operating_mode": "DEMO_MODE",
            },
            {
                "timestamp": 1787735597.0,
                "flow_id": "flow_shared_001",
                "event_id": "EVT-003",
                "packets_observed": 25,
                "composed_confidence": 0.95,
                "operating_mode": "DEMO_MODE",
            },
        ]
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"count": 3, "limit": 100, "predictions": events}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            records, meta = load_live_predictions(limit=100, mode="DEMO_MODE")

        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].packets_observed, 25)
        self.assertEqual(records[2].packets_observed, 3)


if __name__ == "__main__":
    unittest.main()
