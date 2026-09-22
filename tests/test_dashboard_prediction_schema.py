"""
Tests for Dashboard Prediction Schema Contract and Robust Data Normalization.
"""

from __future__ import annotations

import unittest
from dashboard.data_adapter import normalize_prediction_record
from dashboard.schema import (
    CanonicalPredictionRecord,
    parse_confidence,
    validate_prediction_record,
)


class TestDashboardPredictionSchema(unittest.TestCase):
    def test_parse_confidence_valid(self):
        # Floats and ints
        self.assertEqual(parse_confidence(0.84), (0.84, True))
        self.assertEqual(parse_confidence(1.0), (1.0, True))
        self.assertEqual(parse_confidence(0), (0.0, True))
        self.assertEqual(parse_confidence("0.84"), (0.84, True))
        self.assertEqual(parse_confidence("0.9500"), (0.95, True))

    def test_parse_confidence_malformed_and_class_strings(self):
        # Non-numeric strings should NOT crash and should return (0.0, False)
        self.assertEqual(parse_confidence("Messaging"), (0.0, False))
        self.assertEqual(parse_confidence("Video"), (0.0, False))
        self.assertEqual(parse_confidence("Web"), (0.0, False))
        self.assertEqual(parse_confidence("File Transfer"), (0.0, False))
        self.assertEqual(parse_confidence("VoIP"), (0.0, False))
        self.assertEqual(parse_confidence(""), (0.0, False))
        self.assertEqual(parse_confidence(None), (0.0, False))
        self.assertEqual(parse_confidence("invalid_str"), (0.0, False))

    def test_valid_record_normalization(self):
        valid_rec = {
            "timestamp": "1787672210.7782",
            "flow_id": "F-00081",
            "session_id_hash": "1954c02d3eeebc26",
            "model_id": "model_lightgbm_v1",
            "feature_profile": "lightweight_10",
            "packets_observed": "3390",
            "elapsed_seconds": "6.0661",
            "predicted_family": "Interactive",
            "predicted_class": "Web",
            "confidence": "0.95",
            "prediction_state": "KNOWN_CLASS",
            "prediction_version": "1.0.0",
            "latency_us": "5887.5",
        }
        canon, is_valid, err = normalize_prediction_record(valid_rec)
        self.assertTrue(is_valid)
        self.assertIsNone(err)
        self.assertIsNotNone(canon)
        self.assertEqual(canon.predicted_class, "Web")
        self.assertEqual(canon.predicted_family, "Interactive")
        self.assertAlmostEqual(canon.confidence, 0.95)
        self.assertTrue(canon.confidence_valid)
        self.assertEqual(canon.prediction_state, "KNOWN_CLASS")
        self.assertEqual(canon.packets_observed, 3390)

    def test_messaging_with_valid_confidence(self):
        rec = {
            "flow_id": "F-001",
            "predicted_class": "Messaging",
            "confidence": "0.84",
            "prediction_state": "KNOWN_CLASS",
        }
        canon, is_valid, err = normalize_prediction_record(rec)
        self.assertTrue(is_valid)
        self.assertEqual(canon.predicted_class, "Messaging")
        self.assertAlmostEqual(canon.confidence, 0.84)
        self.assertTrue(canon.confidence_valid)

    def test_shifted_malformed_record_confidence_is_messaging(self):
        # The exact bug: confidence = "Messaging"
        bad_rec = {
            "flow_id": "F-002",
            "predicted_class": "—",
            "confidence": "Messaging",
            "prediction_state": "KNOWN_CLASS",
        }
        # Must NOT raise ValueError
        canon, is_valid, err = normalize_prediction_record(bad_rec)
        self.assertFalse(is_valid)
        self.assertIsNotNone(err)
        self.assertIsNotNone(canon)
        self.assertEqual(canon.confidence, 0.0)
        self.assertFalse(canon.confidence_valid)
        self.assertEqual(canon.predicted_class, "Messaging")

    def test_all_prediction_states(self):
        states = [
            "KNOWN_CLASS",
            "LOW_CONFIDENCE",
            "UNKNOWN",
            "INSUFFICIENT_EVIDENCE",
            "FLOW_COMPLETED",
        ]
        for st in states:
            rec = {
                "flow_id": f"FLOW-{st}",
                "confidence": 0.75,
                "prediction_state": st,
                "predicted_class": "Web" if st == "KNOWN_CLASS" else "—",
            }
            canon, is_valid, err = normalize_prediction_record(rec)
            self.assertTrue(is_valid)
            self.assertEqual(canon.prediction_state, st)

    def test_legacy_schema_adaptation(self):
        # Legacy Phase 2-8 CSV record
        legacy_rec = {
            "event_id": "EVT-000001",
            "timestamp": "1787470778.7168822",
            "flow_id": "F-00001",
            "protocol": "TCP",
            "source_port": "50001",
            "destination_port": "443",
            "packet_count": "15",
            "byte_count": "3450",
            "predicted_class": "Web",
            "confidence": "0.89",
            "confidence_level": "HIGH",
            "latency_ms": "1.25",
        }
        canon, is_valid, err = normalize_prediction_record(legacy_rec)
        self.assertTrue(is_valid)
        self.assertEqual(canon.predicted_class, "Web")
        self.assertEqual(canon.predicted_family, "Interactive")
        self.assertEqual(canon.confidence, 0.89)
        self.assertEqual(canon.latency_us, 1250.0)
        self.assertEqual(canon.packets_observed, 15)
        self.assertEqual(canon.prediction_state, "KNOWN_CLASS")

    def test_schema_validator(self):
        v1 = validate_prediction_record({"prediction_state": "KNOWN_CLASS", "confidence": 0.8})
        self.assertTrue(v1.is_valid)

        v2 = validate_prediction_record({"prediction_state": "INVALID_STATE", "confidence": 0.8})
        self.assertFalse(v2.is_valid)


if __name__ == "__main__":
    unittest.main()
