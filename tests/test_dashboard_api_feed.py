"""
Unit tests for Dashboard API Feed integration, parsing, normalization, error handling, and connection status.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
import threading
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from dashboard.data_adapter import (
    fetch_predictions_from_api,
    fetch_subsystem_status,
    load_dashboard_feed,
    normalize_prediction_record,
)
from dashboard.schema import CanonicalPredictionRecord


class TestDashboardAPIFeed(unittest.TestCase):
    """Test suite for Dashboard Live API feed consumption and normalization."""

    def _create_sample_predictions(self, count: int = 20):
        classes = ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"]
        families = ["Interactive", "Bulk_Streaming", "Interactive", "Interactive", "Bulk_Streaming", "Other"]
        predictions = []
        for i in range(count):
            cls_idx = i % len(classes)
            predictions.append({
                "timestamp": f"17876722{10+i:02d}.500",
                "flow_id": f"F-{i:05d}",
                "session_id_hash": f"sess_{i:04d}",
                "model_id": "model_lightgbm_v1",
                "feature_profile": "lightweight_10",
                "predicted_family": families[cls_idx],
                "predicted_class": classes[cls_idx],
                "composed_confidence": 0.85 + (i % 10) * 0.01,
                "prediction_state": "KNOWN_CLASS",
                "packets_observed": 10 + i,
                "elapsed_seconds": 1.5 + (i * 0.1),
                "latency_us": 1250.0 + i,
            })
        return predictions

    def test_a_api_returns_20_valid_predictions(self):
        """A. API returns 20 valid predictions and parser produces canonical records."""
        sample_preds = self._create_sample_predictions(20)
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "count": 20,
            "limit": 20,
            "predictions": sample_preds,
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            records, feed_info = fetch_predictions_from_api("http://127.0.0.1:8080/predictions?limit=20")

        self.assertEqual(len(records), 20)
        self.assertEqual(feed_info["status"], "CONNECTED")
        self.assertEqual(feed_info["count"], 20)
        self.assertEqual(feed_info["malformed_count"], 0)
        self.assertIsNone(feed_info["error"])

        # Validate canonical fields of first record
        first_rec = records[0]  # note: reversed chronological
        self.assertIsInstance(first_rec, CanonicalPredictionRecord)
        self.assertTrue(first_rec.confidence_valid)
        self.assertEqual(first_rec.model_id, "model_lightgbm_v1")

    def test_b_dashboard_parser_extracts_response_predictions(self):
        """B. Dashboard parser properly extracts the response['predictions'] array."""
        payload = {
            "count": 2,
            "limit": 100,
            "status": "OK",
            "server_timestamp": "2026-08-26T14:30:00Z",
            "predictions": [
                {
                    "flow_id": "F-AAA",
                    "predicted_family": "Interactive",
                    "predicted_class": "Web",
                    "composed_confidence": 0.92,
                    "prediction_state": "KNOWN_CLASS",
                    "latency_us": 800.0,
                },
                {
                    "flow_id": "F-BBB",
                    "predicted_family": "Bulk_Streaming",
                    "predicted_class": "Video",
                    "composed_confidence": 0.88,
                    "prediction_state": "KNOWN_CLASS",
                    "latency_us": 1100.0,
                },
            ],
        }
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(payload).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            records, feed_info = fetch_predictions_from_api("http://127.0.0.1:8080/predictions")

        self.assertEqual(len(records), 2)
        flow_ids = [r.flow_id for r in records]
        self.assertIn("F-AAA", flow_ids)
        self.assertIn("F-BBB", flow_ids)

    def test_c_empty_response(self):
        """C. Handles empty API predictions response cleanly without errors."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "count": 0,
            "limit": 100,
            "predictions": [],
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            records, feed_info = fetch_predictions_from_api("http://127.0.0.1:8080/predictions")

        self.assertEqual(len(records), 0)
        self.assertEqual(feed_info["status"], "CONNECTED")
        self.assertEqual(feed_info["count"], 0)
        self.assertIsNone(feed_info["error"])

    def test_d_api_unavailable(self):
        """D. Handles API connection refused/timeout gracefully without crashing."""
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            records, feed_info = fetch_predictions_from_api("http://127.0.0.1:8080/predictions")

        self.assertEqual(len(records), 0)
        self.assertEqual(feed_info["status"], "DEGRADED")
        self.assertIsNotNone(feed_info["error"])
        self.assertIn("API unavailable", feed_info["error"])

    def test_e_malformed_event(self):
        """E. Safely normalizes malformed events and flags DEGRADED feed status."""
        malformed_preds = [
            {
                "flow_id": "F-GOOD",
                "predicted_family": "Interactive",
                "predicted_class": "Web",
                "confidence": 0.90,
                "prediction_state": "KNOWN_CLASS",
            },
            {
                "flow_id": "F-BAD-CONF",
                "predicted_family": "Interactive",
                "predicted_class": "—",
                "composed_confidence": "Messaging",  # shifted string
                "prediction_state": "KNOWN_CLASS",
            },
            "not_even_a_dictionary",  # severe corruption
        ]
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "count": 3,
            "limit": 100,
            "predictions": malformed_preds,
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            records, feed_info = fetch_predictions_from_api("http://127.0.0.1:8080/predictions")

        self.assertEqual(len(records), 2)  # both valid and shifted normalized
        self.assertEqual(feed_info["status"], "DEGRADED")
        self.assertGreater(feed_info["malformed_count"], 0)
        self.assertIsNotNone(feed_info["error"])

    def test_f_duplicate_flow_ids(self):
        """F. Supports duplicate flow IDs (early flow prefix updates) preserving order."""
        duplicate_flow_events = [
            {
                "flow_id": "F-00100",
                "packets_observed": 3,
                "predicted_class": "—",
                "composed_confidence": 0.40,
                "prediction_state": "INSUFFICIENT_EVIDENCE",
            },
            {
                "flow_id": "F-00100",
                "packets_observed": 10,
                "predicted_class": "Web",
                "composed_confidence": 0.75,
                "prediction_state": "LOW_CONFIDENCE",
            },
            {
                "flow_id": "F-00100",
                "packets_observed": 25,
                "predicted_class": "Web",
                "composed_confidence": 0.96,
                "prediction_state": "KNOWN_CLASS",
            },
        ]
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "count": 3,
            "limit": 100,
            "predictions": duplicate_flow_events,
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            records, feed_info = fetch_predictions_from_api("http://127.0.0.1:8080/predictions")

        self.assertEqual(len(records), 3)
        self.assertEqual(feed_info["status"], "CONNECTED")
        # Reversed chronological order: latest update is records[0]
        self.assertEqual(records[0].packets_observed, 25)
        self.assertEqual(records[0].prediction_state, "KNOWN_CLASS")
        self.assertEqual(records[2].packets_observed, 3)

    def test_g_confidence_normalization(self):
        """G. Normalizes float, string, composed_confidence, and confidence fields accurately."""
        # 1. Float confidence
        rec1, valid1, _ = normalize_prediction_record({"flow_id": "F1", "confidence": 0.88, "predicted_class": "Web"})
        self.assertTrue(valid1)
        self.assertAlmostEqual(rec1.confidence, 0.88)
        self.assertTrue(rec1.confidence_valid)

        # 2. String confidence
        rec2, valid2, _ = normalize_prediction_record({"flow_id": "F2", "confidence": "0.915", "predicted_class": "Web"})
        self.assertTrue(valid2)
        self.assertAlmostEqual(rec2.confidence, 0.915)
        self.assertTrue(rec2.confidence_valid)

        # 3. Composed confidence
        rec3, valid3, _ = normalize_prediction_record({
            "flow_id": "F3",
            "composed_confidence": 0.94,
            "confidence": 0.70,
            "predicted_class": "Web",
        })
        self.assertTrue(valid3)
        self.assertAlmostEqual(rec3.confidence, 0.94)
        self.assertAlmostEqual(rec3.composed_confidence, 0.94)

        # 4. Latency in ms converted to us
        rec4, valid4, _ = normalize_prediction_record({"flow_id": "F4", "latency_ms": 2.5, "predicted_class": "Web"})
        self.assertTrue(valid4)
        self.assertAlmostEqual(rec4.latency_us, 2500.0)

    def test_h_live_feed_connection_status(self):
        """H. Verifies subsystem and live feed connection status reporting."""
        # Test HTTP error status
        mock_http_err = urllib.error.HTTPError(
            url="http://127.0.0.1:8080/predictions",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=io.BytesIO(b"{}"),
        )
        with patch("urllib.request.urlopen", side_effect=mock_http_err):
            records, feed_info = fetch_predictions_from_api("http://127.0.0.1:8080/predictions")
        self.assertEqual(feed_info["status"], "DEGRADED")
        self.assertIn("500", feed_info["error"])

        # Test invalid non-JSON payload
        mock_invalid_json = MagicMock()
        mock_invalid_json.status = 200
        mock_invalid_json.read.return_value = b"<html>502 Bad Gateway</html>"
        mock_invalid_json.__enter__.return_value = mock_invalid_json
        with patch("urllib.request.urlopen", return_value=mock_invalid_json):
            records, feed_info = fetch_predictions_from_api("http://127.0.0.1:8080/predictions")
        self.assertEqual(feed_info["status"], "DEGRADED")
        self.assertIn("Invalid JSON", feed_info["error"])


if __name__ == "__main__":
    unittest.main()
