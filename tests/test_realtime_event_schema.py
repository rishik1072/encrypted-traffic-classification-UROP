"""
Unit Tests for Real-Time Prediction Event Schema & Validator.
"""

import unittest
from realtime.events import OperatingMode, PredictionState, TrafficPredictionEvent
from realtime.event_validator import validate_traffic_prediction_event


class TestRealTimeEventSchema(unittest.TestCase):
    def test_case_a_interactive_messaging_known_class(self):
        """Case A: Interactive + Messaging + 0.74 + KNOWN_CLASS -> VALID."""
        evt = TrafficPredictionEvent(
            timestamp=1787670000.0,
            flow_id="F-00101",
            session_id_hash="a1b2c3d4e5f60718",
            model_id="model_lightgbm_v1",
            feature_profile="lightweight_10",
            predicted_family="Interactive",
            predicted_class="Messaging",
            family_confidence=0.82,
            fine_confidence=0.91,
            composed_confidence=0.7462,
            prediction_state=PredictionState.KNOWN_CLASS.value,
            packets_observed=25,
            elapsed_seconds=12.5,
            latency_us=180.5,
        )
        is_valid, errors = validate_traffic_prediction_event(evt)
        self.assertTrue(is_valid, f"Validation failed with errors: {errors}")
        self.assertEqual(len(errors), 0)

        # Check dictionary serialization
        d = evt.to_canonical_dict()
        self.assertEqual(d["predicted_family"], "Interactive")
        self.assertEqual(d["predicted_class"], "Messaging")
        self.assertEqual(d["composed_confidence"], 0.7462)

    def test_case_b_interactive_low_confidence(self):
        """Case B: Interactive + candidate/None + 0.42 + LOW_CONFIDENCE -> VALID."""
        evt = TrafficPredictionEvent(
            timestamp=1787670001.0,
            flow_id="F-00102",
            session_id_hash="b2c3d4e5f60718a1",
            model_id="model_lightgbm_v1",
            feature_profile="lightweight_10",
            predicted_family="Interactive",
            predicted_class="Web",
            family_confidence=0.70,
            fine_confidence=0.60,
            composed_confidence=0.42,
            prediction_state=PredictionState.LOW_CONFIDENCE.value,
            packets_observed=15,
            elapsed_seconds=8.0,
            latency_us=195.2,
        )
        is_valid, errors = validate_traffic_prediction_event(evt)
        self.assertTrue(is_valid, f"Validation failed: {errors}")

    def test_case_c_none_none_unknown(self):
        """Case C: None/UNKNOWN + None + UNKNOWN -> VALID."""
        evt = TrafficPredictionEvent(
            timestamp=1787670002.0,
            flow_id="F-00103",
            session_id_hash="c3d4e5f60718a1b2",
            model_id="model_lightgbm_v1",
            feature_profile="lightweight_10",
            predicted_family="UNKNOWN",
            predicted_class=None,
            family_confidence=0.25,
            fine_confidence=None,
            composed_confidence=0.25,
            prediction_state=PredictionState.UNKNOWN.value,
            packets_observed=18,
            elapsed_seconds=9.2,
            latency_us=160.0,
        )
        is_valid, errors = validate_traffic_prediction_event(evt)
        self.assertTrue(is_valid, f"Validation failed: {errors}")

    def test_case_d_insufficient_evidence(self):
        """Case D: None + None + INSUFFICIENT_EVIDENCE -> VALID."""
        evt = TrafficPredictionEvent(
            timestamp=1787670003.0,
            flow_id="F-00104",
            session_id_hash="d4e5f60718a1b2c3",
            model_id="model_lightgbm_v1",
            feature_profile="lightweight_10",
            predicted_family=None,
            predicted_class=None,
            family_confidence=None,
            fine_confidence=None,
            composed_confidence=None,
            prediction_state=PredictionState.INSUFFICIENT_EVIDENCE.value,
            packets_observed=2,
            elapsed_seconds=0.4,
            latency_us=120.0,
        )
        is_valid, errors = validate_traffic_prediction_event(evt)
        self.assertTrue(is_valid, f"Validation failed: {errors}")

    def test_case_e_other_other_known_class(self):
        """Case E: Other + Other + 0.91 + KNOWN_CLASS -> VALID."""
        evt = TrafficPredictionEvent(
            timestamp=1787670004.0,
            flow_id="F-00105",
            session_id_hash="e5f60718a1b2c3d4",
            model_id="model_lightgbm_v1",
            feature_profile="lightweight_10",
            predicted_family="Other",
            predicted_class="Other",
            family_confidence=0.95,
            fine_confidence=0.95,
            composed_confidence=0.9025,
            prediction_state=PredictionState.KNOWN_CLASS.value,
            packets_observed=30,
            elapsed_seconds=20.0,
            latency_us=175.0,
        )
        is_valid, errors = validate_traffic_prediction_event(evt)
        self.assertTrue(is_valid, f"Validation failed: {errors}")

    def test_case_f_confidence_is_string_label_rejected(self):
        """Case F: confidence = 'Messaging' -> INVALID."""
        bad_dict = {
            "timestamp": 1787670005.0,
            "flow_id": "F-00106",
            "session_id_hash": "f60718a1b2c3d4e5",
            "model_id": "model_lightgbm_v1",
            "feature_profile": "lightweight_10",
            "predicted_family": "Interactive",
            "predicted_class": "Messaging",
            "composed_confidence": "Messaging",  # ILLEGAL class string
            "prediction_state": "KNOWN_CLASS",
            "packets_observed": 10,
            "elapsed_seconds": 5.0,
            "latency_us": 150.0,
        }
        is_valid, errors = validate_traffic_prediction_event(bad_dict)
        self.assertFalse(is_valid)
        self.assertTrue(any("contains class label string" in e for e in errors))

    def test_case_g_unknown_with_fabricated_class_rejected(self):
        """Case G: UNKNOWN state cannot assert definitive fine class."""
        bad_dict = {
            "timestamp": 1787670006.0,
            "flow_id": "F-00107",
            "session_id_hash": "0718a1b2c3d4e5f6",
            "model_id": "model_lightgbm_v1",
            "feature_profile": "lightweight_10",
            "predicted_family": "UNKNOWN",
            "predicted_class": "Web",  # Contradicts UNKNOWN state
            "composed_confidence": 0.20,
            "prediction_state": "UNKNOWN",
            "packets_observed": 10,
            "elapsed_seconds": 4.0,
            "latency_us": 140.0,
        }
        is_valid, errors = validate_traffic_prediction_event(bad_dict)
        self.assertFalse(is_valid)
        self.assertTrue(any("UNKNOWN state should not assert definitive fine class" in e for e in errors))

    def test_case_h_latency_us_must_be_numeric(self):
        """Case H: latency_us must remain numeric."""
        bad_dict = {
            "timestamp": 1787670007.0,
            "flow_id": "F-00108",
            "session_id_hash": "18a1b2c3d4e5f607",
            "model_id": "model_lightgbm_v1",
            "feature_profile": "lightweight_10",
            "predicted_family": "Interactive",
            "predicted_class": "Messaging",
            "composed_confidence": 0.85,
            "prediction_state": "KNOWN_CLASS",
            "packets_observed": 12,
            "elapsed_seconds": 6.0,
            "latency_us": "N/A",  # Invalid string latency
        }
        is_valid, errors = validate_traffic_prediction_event(bad_dict)
        self.assertFalse(is_valid)
        self.assertTrue(any("latency_us must be numeric" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
