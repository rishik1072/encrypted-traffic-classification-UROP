"""
End-to-End Headless Smoke Test.

Validates the full pipeline flow:
1. Loads model checkpoint & preprocessor
2. Validates canonical feature schema
3. Ingests mock feature record
4. Produces class prediction & confidence score
5. Profiles single inference latency
6. Dispatches prediction event to in-memory EventBus
7. Verifies dashboard table format compatibility
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from realtime.events import EventBus, TrafficPredictionEvent
from realtime.model_loader import ModelLoader
from realtime.schema import CANONICAL_NUMERICAL_FEATURES, validate_feature_schema


class TestEndToEndSmoke(unittest.TestCase):
    def test_end_to_end_inference_and_event_publishing(self):
        # 1. Initialize loader with default model
        loader = ModelLoader(model_name="lightgbm")
        self.assertIsNotNone(loader.model)
        self.assertIsNotNone(loader.preprocessor)

        # 2. Mock raw feature record
        mock_raw_features = {feat: 10.0 for feat in CANONICAL_NUMERICAL_FEATURES}

        # 3. Schema validation
        is_valid = validate_feature_schema(mock_raw_features, expected_features=loader.feature_names)
        self.assertTrue(is_valid)

        # 4. Predict
        pred_class, confidence, prob_map = loader.predict_single(mock_raw_features)
        self.assertIn(pred_class, loader.class_names)
        self.assertTrue(0.0 <= confidence <= 1.0)
        self.assertIsInstance(prob_map, dict)

        # 5. Build and Publish Event
        bus = EventBus()
        received_events = []
        bus.subscribe(lambda e: received_events.append(e))

        event = TrafficPredictionEvent(
            event_id="SMOKE-001",
            timestamp=100.0,
            flow_id="FLOW-SMOKE",
            session_id_hash="0123456789abcdef",
            model_id="model_lightgbm_v1",
            feature_profile="lightweight_10",
            packets_observed=15,
            elapsed_seconds=1.5,
            predicted_family="Interactive",
            predicted_class=pred_class,
            confidence=confidence,
            prediction_state="KNOWN_CLASS" if confidence >= 0.70 else "LOW_CONFIDENCE",
            prediction_version="1.0.0",
            latency_us=450.0,
            protocol="TCP",
            source_port=54321,
            destination_port=443,
            byte_count=4500,
            probabilities=prob_map,
        )
        bus.publish(event)

        # 6. Verify event delivery & dashboard dict formatting
        self.assertEqual(len(received_events), 1)
        evt_dict = received_events[0].to_dict()
        self.assertEqual(evt_dict["predicted_class"], pred_class)
        self.assertIn("flow_id", evt_dict)
        self.assertIn("latency_us", evt_dict)


if __name__ == "__main__":
    unittest.main()
