"""
Unit and regression tests for Dashboard KPI calculation and live prediction rendering directly from records.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List
import unittest
from unittest.mock import MagicMock, patch

from dashboard.live_feed import load_live_predictions
from dashboard.schema import CanonicalPredictionRecord


class TestDashboardKpiFromLiveRecords(unittest.TestCase):
    """Test suite verifying dashboard KPI computation and non-empty rendering directly from records."""

    def _create_mock_live_payload(self, count: int = 59) -> Dict[str, Any]:
        """Generates 59 LIVE_MODE records matching live traffic structure."""
        predictions = []
        classes = ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"]
        families = ["Interactive", "Bulk_Streaming", "Interactive", "Interactive", "Bulk_Streaming", "Other"]
        
        for i in range(count):
            flow_idx = i % 15  # 15 distinct unique flows
            cls_idx = i % len(classes)
            predictions.append({
                "timestamp": 1787735596.0 + (i * 0.2),
                "flow_id": f"live_flow_{flow_idx:03d}",
                "session_id_hash": f"sess_live_{flow_idx:04x}",
                "model_id": "model_lightgbm_v1",
                "feature_profile": "lightweight_10",
                "predicted_family": families[cls_idx],
                "predicted_class": classes[cls_idx],
                "family_confidence": 0.95,
                "fine_confidence": 0.92,
                "composed_confidence": 0.9125,
                "prediction_state": "KNOWN_CLASS" if (i % 7 != 0) else "LOW_CONFIDENCE",
                "packets_observed": 10 + (i % 20),
                "elapsed_seconds": 0.45 + (i * 0.05),
                "latency_us": 165.0 + (i % 30),
                "event_id": f"LIVE-EVT-{i:05d}",
                "operating_mode": "LIVE_MODE",
            })
        return {
            "count": count,
            "limit": 100,
            "predictions": predictions,
        }

    def test_kpi_calculations_from_59_live_records(self):
        """Tests that 59 LIVE_MODE records yield positive active streams, known classes, and avg latency."""
        payload = self._create_mock_live_payload(count=59)
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            records, meta = load_live_predictions(limit=100, mode="LIVE_MODE")

        self.assertEqual(len(records), 59)
        self.assertTrue(meta["connected"])
        self.assertEqual(meta["event_count"], 59)

        # KPI calculations directly from records
        unique_flows = {r.flow_id for r in records if r.flow_id}
        active_streams = len(unique_flows)
        known_classes = sum(1 for r in records if r.prediction_state == "KNOWN_CLASS")
        low_confidence = sum(1 for r in records if r.prediction_state == "LOW_CONFIDENCE")
        unknown = sum(1 for r in records if r.prediction_state == "UNKNOWN")
        latencies = [r.latency_us for r in records if r.latency_us > 0]
        avg_latency = (sum(latencies) / len(latencies) / 1000.0) if latencies else 0.0

        self.assertGreater(active_streams, 0)
        self.assertEqual(active_streams, 15)  # 15 unique flows
        self.assertGreater(known_classes, 0)
        self.assertGreaterEqual(low_confidence, 0)
        self.assertGreaterEqual(unknown, 0)
        self.assertGreater(avg_latency, 0.0)

    def test_live_feed_never_produces_waiting_condition_when_count_positive(self):
        """Tests that when records are present (> 0), waiting message is never triggered."""
        payload = self._create_mock_live_payload(count=59)
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            records, meta = load_live_predictions(limit=100, mode="LIVE_MODE")

        # The render condition logic in app.py
        should_render_table = len(records) > 0
        should_show_waiting = (not meta["connected"] and meta.get("error")) or len(records) == 0

        self.assertTrue(should_render_table)
        self.assertFalse(should_show_waiting)


if __name__ == "__main__":
    unittest.main()
