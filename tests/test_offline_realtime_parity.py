"""
Golden Test Vector Parity Test.

Verifies that:
1. Feature extraction on offline flow records
2. Offline model inference
3. Real-time streaming feature extraction and inference
produce identical numerical vectors and prediction outcomes for the same packet metadata stream.
"""

from __future__ import annotations

import unittest

from capture.packet_capture import RawPacketMetadata
from flows.flow_generator import Flow, FlowKey
from preprocessing.feature_extractor import FeatureExtractor
from realtime.classifier import RealTimeClassifier
from realtime.model_loader import ModelLoader


class TestOfflineRealtimeParity(unittest.TestCase):
    """Test suite ensuring bitwise / numerical feature parity across pipelines."""

    def setUp(self) -> None:
        self.extractor = FeatureExtractor()
        self.model_loader = ModelLoader(model_name="lightgbm", enforce_registry=False)
        self.classifier = RealTimeClassifier(operating_mode="DEMO_MODE")

        # Construct deterministic golden packet stream (10 packets)
        self.golden_packets = []
        t0 = 1000.0
        # Alternating forward/backward traffic with precise lengths and IATs
        records = [
            (t0 + 0.00, 192, 168, 1, 10, 104, 20, 10, 1, 443, 60, "TCP"),
            (t0 + 0.02, 104, 20, 10, 1, 192, 168, 1, 10, 443, 60, "TCP"),
            (t0 + 0.05, 192, 168, 1, 10, 104, 20, 10, 1, 443, 512, "TCP"),
            (t0 + 0.09, 104, 20, 10, 1, 192, 168, 1, 10, 443, 1420, "TCP"),
            (t0 + 0.12, 104, 20, 10, 1, 192, 168, 1, 10, 443, 1420, "TCP"),
            (t0 + 0.15, 192, 168, 1, 10, 104, 20, 10, 1, 443, 64, "TCP"),
            (t0 + 0.18, 104, 20, 10, 1, 192, 168, 1, 10, 443, 1420, "TCP"),
            (t0 + 0.22, 192, 168, 1, 10, 104, 20, 10, 1, 443, 64, "TCP"),
            (t0 + 0.26, 104, 20, 10, 1, 192, 168, 1, 10, 443, 1420, "TCP"),
            (t0 + 0.30, 192, 168, 1, 10, 104, 20, 10, 1, 443, 64, "TCP"),
        ]

        for r in records:
            src_ip = f"{r[1]}.{r[2]}.{r[3]}.{r[4]}"
            dst_ip = f"{r[5]}.{r[6]}.{r[7]}.{r[8]}"
            self.golden_packets.append(
                RawPacketMetadata(
                    timestamp=r[0],
                    src_ip=src_ip,
                    dst_ip=dst_ip,
                    src_port=54321 if src_ip.startswith("192") else 443,
                    dst_port=443 if src_ip.startswith("192") else 54321,
                    protocol=r[11],
                    length=r[10],
                )
            )

    def test_feature_extraction_parity(self) -> None:
        """Offline Flow extraction vs Online Flow extraction produces exact feature equality."""
        flow_offline = Flow(
            key=FlowKey.from_packet(self.golden_packets[0])[0],
            initiator_ip=self.golden_packets[0].src_ip,
            initiator_port=self.golden_packets[0].src_port,
            start_time=self.golden_packets[0].timestamp,
            last_seen=self.golden_packets[0].timestamp,
        )
        for pkt in self.golden_packets:
            flow_offline.add_packet(pkt)

        offline_feats = self.extractor.extract_features(flow_offline)

        # Online tracker simulation
        flow_online = None
        for pkt in self.golden_packets:
            _, flow_online, _ = self.classifier.flow_tracker.update(pkt)

        online_feats = self.extractor.extract_features(flow_online)

        for key in offline_feats:
            self.assertIn(key, online_feats, f"Missing feature in online extraction: {key}")
            val_off = offline_feats[key]
            val_on = online_feats[key]
            if isinstance(val_off, (int, float)):
                self.assertAlmostEqual(
                    float(val_off),
                    float(val_on),
                    places=5,
                    msg=f"Feature disparity for {key}: offline={val_off}, online={val_on}",
                )
            else:
                self.assertEqual(val_off, val_on, f"Categorical feature disparity for {key}")

    def test_inference_outcome_parity(self) -> None:
        """Inference from model_loader directly matches classifier._classify_flow_instance."""
        flow = Flow(
            key=FlowKey.from_packet(self.golden_packets[0])[0],
            initiator_ip=self.golden_packets[0].src_ip,
            initiator_port=self.golden_packets[0].src_port,
            start_time=self.golden_packets[0].timestamp,
            last_seen=self.golden_packets[0].timestamp,
        )
        for pkt in self.golden_packets:
            flow.add_packet(pkt)

        raw_feats = self.extractor.extract_features(flow)
        pred_class_direct, conf_direct, probs_direct = self.model_loader.predict_single(raw_feats)

        event = self.classifier._classify_flow_instance(flow)
        self.assertIsNotNone(event)
        self.assertEqual(event.predicted_class, pred_class_direct)
        self.assertAlmostEqual(event.fine_confidence, conf_direct, places=4)



if __name__ == "__main__":
    unittest.main()
