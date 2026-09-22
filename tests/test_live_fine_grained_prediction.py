"""
Regression Tests for Live Fine-Grained Class Prediction.

Verifies the 7 mandatory requirements:
1. family + fine class known prediction
2. family-only prediction handling
3. UNKNOWN prediction
4. INSUFFICIENT_EVIDENCE
5. event-store round trip
6. REST serialization
7. dashboard rendering
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dashboard.live_feed import normalize_api_record
from dashboard.schema import CanonicalPredictionRecord
from product.event_store import LocalEventStore
from product.security import sanitize_event_record
from realtime.event_validator import validate_traffic_prediction_event
from realtime.events import OperatingMode, PredictionState, TrafficPredictionEvent


class TestLiveFineGrainedPrediction(unittest.TestCase):
    """Full regression suite for live fine-grained class prediction."""

    def test_1_known_prediction_family_and_fine_class(self):
        """1. family + fine class known prediction."""
        # Valid known prediction: Bulk_Streaming + File Transfer
        evt = TrafficPredictionEvent(
            timestamp=1790098501.0,
            flow_id="F-00312",
            session_id_hash="4686212b3aec7624",
            model_id="model_lightgbm_v1",
            feature_profile="lightweight_10",
            predicted_family="Bulk_Streaming",
            predicted_class="File Transfer",
            family_confidence=0.96,
            fine_confidence=0.95,
            composed_confidence=0.912,
            prediction_state=PredictionState.KNOWN_CLASS.value,
            packets_observed=229,
            elapsed_seconds=41.4,
            latency_us=509.1,
            operating_mode=OperatingMode.LIVE_NPCAP.value,
        )

        is_valid, errors = validate_traffic_prediction_event(evt)
        self.assertTrue(is_valid, f"Validation failed: {errors}")
        self.assertEqual(evt.predicted_family, "Bulk_Streaming")
        self.assertEqual(evt.predicted_class, "File Transfer")
        self.assertEqual(evt.evidence_class, "REAL_LIVE_NPCAP")

        # Validation MUST reject known-class events when predicted_class is missing
        bad_evt_missing_class = TrafficPredictionEvent(
            timestamp=1790098501.0,
            flow_id="F-00312",
            predicted_family="Bulk_Streaming",
            predicted_class=None,  # Missing!
            composed_confidence=0.912,
            prediction_state=PredictionState.KNOWN_CLASS.value,
            packets_observed=25,
        )
        is_val, errs = validate_traffic_prediction_event(bad_evt_missing_class)
        self.assertFalse(is_val)
        self.assertTrue(any("requires valid fine-grained predicted_class" in e for e in errs))

        # Rejection on silent dash
        bad_evt_dash = TrafficPredictionEvent(
            timestamp=1790098501.0,
            flow_id="F-00312",
            predicted_family="Bulk_Streaming",
            predicted_class="—",  # Silent dash!
            composed_confidence=0.912,
            prediction_state=PredictionState.KNOWN_CLASS.value,
            packets_observed=25,
        )
        is_val_d, errs_d = validate_traffic_prediction_event(bad_evt_dash)
        self.assertFalse(is_val_d)

    def test_2_family_only_prediction_handling(self):
        """2. family-only prediction handling."""
        # When coarse family is identified (e.g. Interactive) but fine classification
        # is abstained or below selective threshold, predicted_class must explicitly
        # represent the abstention state, never an empty string or silent dash.
        rec = {
            "timestamp": 1790098502.0,
            "flow_id": "F-00313",
            "operating_mode": "LIVE_NPCAP",
            "predicted_family": "Interactive",
            "predicted_class": "LOW_CONFIDENCE",
            "composed_confidence": 0.55,
            "prediction_state": "LOW_CONFIDENCE",
            "packets_observed": 12,
            "latency_us": 200.0,
            "fine_classification_reason": "Confidence (0.55) below selective acceptance threshold (0.70)",
        }

        canon, is_valid, err = normalize_api_record(rec, target_mode="LIVE_NPCAP")
        self.assertTrue(is_valid, f"Normalization error: {err}")
        self.assertIsNotNone(canon)
        self.assertEqual(canon.predicted_family, "Interactive")
        self.assertEqual(canon.predicted_class, "LOW_CONFIDENCE")
        self.assertNotEqual(canon.predicted_class, "")
        self.assertNotEqual(canon.predicted_class, "—")

    def test_3_unknown_prediction(self):
        """3. UNKNOWN prediction."""
        # Diffuse posterior / out-of-distribution traffic
        rec = {
            "timestamp": 1790098503.0,
            "flow_id": "F-00314",
            "operating_mode": "LIVE_NPCAP",
            "predicted_family": "UNKNOWN",
            "predicted_class": "UNKNOWN",
            "composed_confidence": 0.22,
            "prediction_state": "UNKNOWN",
            "packets_observed": 15,
            "latency_us": 180.0,
            "fine_classification_reason": "Posterior probability (0.22) below unknown threshold (0.35)",
        }

        canon, is_valid, err = normalize_api_record(rec, target_mode="LIVE_NPCAP")
        self.assertTrue(is_valid, f"Normalization error: {err}")
        self.assertIsNotNone(canon)
        self.assertEqual(canon.predicted_family, "UNKNOWN")
        self.assertEqual(canon.predicted_class, "UNKNOWN")
        self.assertNotEqual(canon.predicted_class, "")
        self.assertNotEqual(canon.predicted_class, "—")

    def test_4_insufficient_evidence(self):
        """4. INSUFFICIENT_EVIDENCE."""
        # Nascent flow lacking minimum packet threshold (N < 3)
        rec = {
            "timestamp": 1790098504.0,
            "flow_id": "F-00315",
            "operating_mode": "LIVE_NPCAP",
            "predicted_family": "INSUFFICIENT_EVIDENCE",
            "predicted_class": "INSUFFICIENT_EVIDENCE",
            "composed_confidence": 0.0,
            "prediction_state": "INSUFFICIENT_EVIDENCE",
            "packets_observed": 2,
            "latency_us": 95.0,
            "fine_classification_reason": "Lacking minimum packet evidence (2 < 3)",
        }

        canon, is_valid, err = normalize_api_record(rec, target_mode="LIVE_NPCAP")
        self.assertTrue(is_valid, f"Normalization error: {err}")
        self.assertIsNotNone(canon)
        self.assertEqual(canon.prediction_state, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(canon.predicted_class, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(canon.predicted_family, "INSUFFICIENT_EVIDENCE")
        self.assertNotEqual(canon.predicted_class, "")
        self.assertNotEqual(canon.predicted_class, "—")

    def test_5_event_store_round_trip(self):
        """5. event-store round trip."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_events.db"
            store = LocalEventStore(db_path=db_path)
            sess_id = store.start_session(operating_mode="LIVE_NPCAP")

            event_payload = {
                "event_id": "EVT-TEST-001",
                "session_id": sess_id,
                "timestamp": 1790098505.0,
                "flow_id": "F-00316",
                "model_id": "model_lightgbm_v1",
                "feature_profile": "lightweight_10",
                "predicted_family": "Interactive",
                "predicted_class": "Web",
                "confidence": 0.9215,
                "composed_confidence": 0.9215,
                "prediction_state": "KNOWN_CLASS",
                "packets_observed": 18,
                "elapsed_seconds": 3.4,
                "latency_us": 115.3,
                "operating_mode": "LIVE_NPCAP",
                "evidence_class": "REAL_LIVE_NPCAP",
                "protocol": "TCP",
                "session_id_hash": "0cb2c5f0883da1cd",
                "fine_classification_reason": "Nominal fine-grained classification",
            }

            store.record_event(event_payload)
            events = store.query_events(operating_mode="LIVE_NPCAP")

            self.assertEqual(len(events), 1)
            stored = events[0]
            self.assertEqual(stored["flow_id"], "F-00316")
            self.assertEqual(stored["predicted_family"], "Interactive")
            self.assertEqual(stored["predicted_class"], "Web")
            self.assertEqual(stored["prediction"], "Web")
            self.assertAlmostEqual(stored["confidence"], 0.9215, places=4)
            self.assertEqual(stored["prediction_state"], "KNOWN_CLASS")
            self.assertEqual(stored["evidence_class"], "REAL_LIVE_NPCAP")

    def test_6_rest_serialization(self):
        """6. REST serialization."""
        raw_event = {
            "event_id": "EVT-TEST-002",
            "session_id": "SESS-100",
            "timestamp": 1790098506.0,
            "flow_id": "F-00317",
            "predicted_family": "Bulk_Streaming",
            "predicted_class": "Video",
            "prediction": "Video",
            "composed_confidence": 0.912,
            "prediction_state": "KNOWN_CLASS",
            "packets_observed": 181,
            "elapsed_seconds": 82.5,
            "latency_us": 1101.1,
            "operating_mode": "LIVE_NPCAP",
            "evidence_class": "REAL_LIVE_NPCAP",
            "protocol": "TCP",
            "session_id_hash": "5f12af8803172fe2",
        }

        # Sanitize record as done in API handler
        sanitized = sanitize_event_record(raw_event)

        # Confirm non-empty prediction and predicted_class
        self.assertIn("predicted_class", sanitized)
        self.assertEqual(sanitized["predicted_class"], "Video")
        self.assertIn("predicted_family", sanitized)
        self.assertEqual(sanitized["predicted_family"], "Bulk_Streaming")
        self.assertEqual(sanitized["evidence_class"], "REAL_LIVE_NPCAP")
        self.assertEqual(sanitized["operating_mode"], "LIVE_NPCAP")

        # Zero-payload check: assert no raw payload / IP fields
        for forbidden in ("payload", "raw_ip", "src_ip", "dst_ip", "mac"):
            self.assertNotIn(forbidden, sanitized)

    def test_7_dashboard_rendering(self):
        """7. dashboard rendering."""
        # Simulate record coming from /predictions API
        api_record = {
            "timestamp": 1790098507.0,
            "flow_id": "F-00318",
            "session_id_hash": "4686212b3aec7624",
            "model_id": "model_lightgbm_v1",
            "feature_profile": "lightweight_10",
            "predicted_family": "Bulk_Streaming",
            "predicted_class": "File Transfer",
            "composed_confidence": 0.912,
            "prediction_state": "KNOWN_CLASS",
            "packets_observed": 229,
            "elapsed_seconds": 41.4,
            "latency_us": 509.1,
            "operating_mode": "LIVE_NPCAP",
        }

        canon, is_valid, err = normalize_api_record(api_record, target_mode="LIVE_NPCAP")
        self.assertTrue(is_valid, f"Normalization error: {err}")
        self.assertIsNotNone(canon)

        # Construct row as dashboard/app.py does
        row = {
            "Time": canon.timestamp,
            "Flow ID": canon.flow_id,
            "Family": canon.predicted_family,
            "Predicted Class": canon.predicted_class,
            "Confidence": f"{canon.confidence * 100:.2f}%",
            "State": canon.prediction_state,
            "Latency (µs)": f"{canon.latency_us:.1f}",
            "Packets": canon.packets_observed,
            "Elapsed (s)": f"{canon.elapsed_seconds:.2f}",
        }

        self.assertEqual(row["Family"], "Bulk_Streaming")
        self.assertEqual(row["Predicted Class"], "File Transfer")
        self.assertNotEqual(row["Predicted Class"], "—")
        self.assertNotEqual(row["Predicted Class"], "")
        self.assertEqual(row["State"], "KNOWN_CLASS")
        self.assertEqual(row["Packets"], 229)


if __name__ == "__main__":
    unittest.main()
