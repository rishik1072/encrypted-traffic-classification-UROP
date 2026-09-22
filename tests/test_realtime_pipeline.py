import sys
import tempfile
import time
import unittest
from pathlib import Path
import yaml

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from capture.packet_capture import RawPacketMetadata
from flows.flow_generator import FlowKey
from realtime.classifier import RealTimeClassifier
from realtime.demo_mode import DemoReplayEngine
from realtime.events import EventBus, FlowLifecycleEvent, FlowLifecycleState, TrafficPredictionEvent
from realtime.flow_tracker import RealTimeFlowTracker
from realtime.metrics import MetricsCollector
from realtime.model_loader import ModelLoader
from realtime.schema import CANONICAL_NUMERICAL_FEATURES, validate_feature_schema


class TestRealTimePipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

        # Config
        self.config = {
            "traffic_classes": ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"],
            "features": {
                "numerical_features": CANONICAL_NUMERICAL_FEATURES,
                "categorical_features": ["protocol", "dst_port"],
                "tls_features": ["tls_version"],
            },
            "models": {
                "lightgbm": {},
                "decision_tree": {},
            },
            "realtime": {
                "model": "lightgbm",
                "idle_timeout_seconds": 2.0,
                "flow_timeout_seconds": 10.0,
                "minimum_packets": 2,
                "minimum_bytes": 100,
                "prediction_interval_seconds": 0.1,
                "confidence_threshold": 0.70,
                "predictions_csv_path": str(self.base_path / "predictions.csv"),
                "predictions_jsonl_path": str(self.base_path / "predictions.jsonl"),
            },
        }

        self.config_path = self.base_path / "config.yaml"
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.config, f)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_feature_schema_validation(self):
        valid_dict = {k: 1.0 for k in CANONICAL_NUMERICAL_FEATURES}
        self.assertTrue(validate_feature_schema(valid_dict))

        # Missing feature should fail
        invalid_dict = {"flow_duration": 1.0}
        with self.assertRaises(ValueError):
            validate_feature_schema(invalid_dict)

    def test_flow_tracker_lifecycle_and_triggers(self):
        lifecycle_events = []

        def _on_event(evt: FlowLifecycleEvent):
            lifecycle_events.append(evt.event_type)

        tracker = RealTimeFlowTracker(
            idle_timeout=1.0,
            active_timeout=5.0,
            min_packets_for_classification=2,
            min_bytes_for_classification=100,
            prediction_interval_seconds=0.05,
            lifecycle_callback=_on_event,
        )

        pkt1 = RawPacketMetadata(100.0, "192.168.1.10", "1.1.1.1", 50001, 443, "TCP", 60)
        pkt2 = RawPacketMetadata(100.1, "1.1.1.1", "192.168.1.10", 443, 50001, "TCP", 200)

        # 1st packet: flow started, not enough packets for prediction
        _, flow, should_pred1 = tracker.update(pkt1)
        self.assertFalse(should_pred1)
        self.assertEqual(tracker.get_active_flow_count(), 1)
        self.assertIn(FlowLifecycleState.FLOW_STARTED, lifecycle_events)

        # 2nd packet: meets packet & byte thresholds, trigger prediction
        _, flow, should_pred2 = tracker.update(pkt2)
        self.assertTrue(should_pred2)
        self.assertEqual(flow.total_packets, 2)

        # Flow expiration
        expired = tracker.clean_stale_flows(current_time=105.0)
        self.assertEqual(len(expired), 1)
        self.assertEqual(tracker.get_active_flow_count(), 0)
        self.assertIn(FlowLifecycleState.FLOW_EXPIRED, lifecycle_events)

    def test_event_bus_publish_and_subscribe(self):
        bus = EventBus()
        received = []

        bus.subscribe(lambda evt: received.append(evt))

        sample_event = TrafficPredictionEvent(
            event_id="EVT-001",
            timestamp=100.0,
            flow_id="F-001",
            session_id_hash="0123456789abcdef",
            model_id="model_lightgbm_v1",
            feature_profile="lightweight_10",
            packets_observed=10,
            elapsed_seconds=1.5,
            predicted_family="Interactive",
            predicted_class="Web",
            confidence=0.92,
            prediction_state="KNOWN_CLASS",
            prediction_version="1.0.0",
            latency_us=500.0,
            protocol="TCP",
            source_port=50000,
            destination_port=443,
            byte_count=1500,
        )

        bus.publish(sample_event)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].predicted_class, "Web")
        self.assertEqual(len(bus.get_recent_events()), 1)

    def test_metrics_collector(self):
        metrics = MetricsCollector(window_seconds=1.0)
        metrics.record_packet(500)
        metrics.record_packet(1500)
        metrics.record_prediction(latency_ms=1.2)

        snap = metrics.get_snapshot(active_flows_count=2, queue_depth=0)
        self.assertEqual(snap.total_packets, 2)
        self.assertEqual(snap.total_bytes, 2000)
        self.assertEqual(snap.active_flows, 2)
        self.assertAlmostEqual(snap.avg_latency_ms, 1.2)

    def test_realtime_classifier_integration(self):
        classifier = RealTimeClassifier(config_path=self.config_path)
        classifier.start()

        pkt1 = RawPacketMetadata(1.0, "10.0.0.1", "10.0.0.2", 5001, 443, "TCP", 100)
        pkt2 = RawPacketMetadata(1.1, "10.0.0.2", "10.0.0.1", 443, 5001, "TCP", 300)

        classifier.process_packet(pkt1)
        classifier.process_packet(pkt2)

        # Allow worker thread to process
        time.sleep(0.3)
        classifier.stop()

        snap = classifier.get_metrics_snapshot()
        self.assertEqual(snap.total_packets, 2)
        self.assertTrue(Path(self.config["realtime"]["predictions_csv_path"]).exists())


if __name__ == "__main__":
    unittest.main()
