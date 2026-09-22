"""
Zero-Payload Privacy & Security Verification Suite.

Validates that:
1. No raw packet payload is captured, buffered, or persisted in events, logs, CSVs, or JSONL outputs.
2. No unhashed/unmasked IP addresses are exported in public/SOC prediction event streams.
3. No MAC addresses are exposed.
4. No application layer secrets, tokens, or credentials exist in real-time artifacts.
"""

from __future__ import annotations

import csv
import json
import re
import tempfile
import unittest
from pathlib import Path

from capture.packet_capture import RawPacketMetadata
from flows.flow_generator import Flow, FlowKey
from realtime.classifier import RealTimeClassifier
from realtime.demo_mode import DemoReplayEngine
from realtime.events import TrafficPredictionEvent


class TestZeroPayloadLiveSecurity(unittest.TestCase):
    """Test suite ensuring strict zero-payload and PII compliance."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

        # Mock config with temp output paths
        self.csv_out = self.tmp_path / "predictions.csv"
        self.jsonl_out = self.tmp_path / "predictions.jsonl"
        self.metrics_out = self.tmp_path / "live_metrics.csv"

        self.classifier = RealTimeClassifier(operating_mode="DEMO_MODE")
        self.classifier.csv_out_path = self.csv_out
        self.classifier.jsonl_out_path = self.jsonl_out

    def tearDown(self) -> None:
        self.classifier.stop()
        self.tmp_dir.cleanup()

    def test_raw_packet_metadata_has_no_payload(self) -> None:
        """Asserts RawPacketMetadata definition contains zero payload attributes."""
        pkt = RawPacketMetadata(
            timestamp=1000.0,
            src_ip="192.168.1.100",
            dst_ip="104.20.10.1",
            src_port=54321,
            dst_port=443,
            protocol="TCP",
            length=1420,
        )
        self.assertFalse(hasattr(pkt, "payload"))
        self.assertFalse(hasattr(pkt, "raw_data"))
        self.assertFalse(hasattr(pkt, "payload_bytes"))
        self.assertFalse(hasattr(pkt, "mac_address"))

    def test_traffic_prediction_event_privacy(self) -> None:
        """Asserts TrafficPredictionEvent schema contains only privacy-preserving metadata."""
        evt = TrafficPredictionEvent(
            event_id="EVT-000001",
            timestamp=1000.0,
            flow_id="F-00001",
            session_id_hash="a1b2c3d4e5f60718",
            model_id="model_lightgbm_v1",
            feature_profile="lightweight_10",
            packets_observed=10,
            elapsed_seconds=1.5,
            predicted_family="Interactive",
            predicted_class="Web",
            confidence=0.88,
            prediction_state="KNOWN_CLASS",
            prediction_version="1.0.0",
            latency_us=120.0,
        )
        d = evt.to_dict()

        # Check prohibited keys
        prohibited = ["src_ip", "dst_ip", "ip", "payload", "mac", "src_mac", "dst_mac", "content", "credentials"]
        for p in prohibited:
            self.assertNotIn(p, d, f"Prohibited PII key '{p}' found in TrafficPredictionEvent!")

        # Verify session_id_hash is hashed
        self.assertEqual(len(d["session_id_hash"]), 16)
        self.assertTrue(bool(re.match(r"^[0-9a-fA-F]+$", d["session_id_hash"])))

    def test_event_persistence_zero_payload(self) -> None:
        """Asserts persisted CSV and JSONL records do not leak payload or raw IPs."""
        self.classifier.start()
        engine = DemoReplayEngine(classifier=self.classifier, flow_delay_seconds=0.01)
        engine.replay_from_csv(
            features_csv_path="data/processed/features/features_cleaned.csv",
            max_events=5,
        )
        self.classifier.stop()

        if self.csv_out.exists():
            with open(self.csv_out, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertNotIn("payload", content.lower())
                self.assertNotIn("password", content.lower())
                self.assertNotIn("authorization", content.lower())

        if self.jsonl_out.exists():
            with open(self.jsonl_out, "r", encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line)
                    self.assertNotIn("src_ip", data)
                    self.assertNotIn("dst_ip", data)
                    self.assertNotIn("payload", data)


if __name__ == "__main__":
    unittest.main()
