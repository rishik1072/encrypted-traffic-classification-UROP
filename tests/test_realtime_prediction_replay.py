"""
Live Replay Test for Real-Time Traffic Prediction Pipeline.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from realtime.classifier import RealTimeClassifier
from realtime.demo_mode import DemoReplayEngine
from realtime.events import OperatingMode, PredictionState
from realtime.event_validator import validate_traffic_prediction_event


class TestRealtimePredictionReplay(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.csv_path = Path(self.temp_dir) / "predictions.csv"
        self.jsonl_path = Path(self.temp_dir) / "predictions.jsonl"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_replay_emits_valid_canonical_events(self):
        classifier = RealTimeClassifier(operating_mode=OperatingMode.DEMO_MODE.value)
        classifier.csv_out_path = self.csv_path
        classifier.jsonl_out_path = self.jsonl_path
        classifier.start()

        engine = DemoReplayEngine(classifier=classifier, flow_delay_seconds=0.0)
        try:
            events = engine.replay_from_csv(
                features_csv_path="data/processed/features/features.csv",
                max_events=20,
                loop=False,
            )
        finally:
            classifier.stop()

        self.assertGreater(len(events), 0)

        # Validate every emitted event
        for evt in events:
            is_valid, errors = validate_traffic_prediction_event(evt)
            self.assertTrue(is_valid, f"Event {evt.flow_id} failed validation: {errors}")

            # Verify numeric types
            self.assertIsInstance(evt.packets_observed, int)
            self.assertIsInstance(evt.elapsed_seconds, float)
            self.assertIsInstance(evt.latency_us, float)
            self.assertGreaterEqual(evt.latency_us, 0.0)

            # Confidence integrity
            if evt.prediction_state == PredictionState.KNOWN_CLASS.value:
                self.assertIsNotNone(evt.composed_confidence)
                self.assertGreaterEqual(evt.composed_confidence, 0.0)
                self.assertLessEqual(evt.composed_confidence, 1.0)
                self.assertIsNotNone(evt.predicted_family)
                self.assertIsNotNone(evt.predicted_class)
                self.assertNotIn(evt.composed_confidence, ["Messaging", "Video", "Web", "VoIP", "Other"])

            elif evt.prediction_state == PredictionState.INSUFFICIENT_EVIDENCE.value:
                self.assertIsNone(evt.predicted_class)

            elif evt.prediction_state == PredictionState.UNKNOWN.value:
                self.assertIsNone(evt.predicted_class)

        # Verify disk persistence CSV format
        self.assertTrue(self.csv_path.exists())
        with open(self.csv_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        header = lines[0].split(",")
        self.assertEqual(header, classifier.CANONICAL_CSV_FIELDS)


if __name__ == "__main__":
    unittest.main()
