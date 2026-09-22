import sys
import unittest
from pathlib import Path

# Ensure project root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from capture.packet_capture import RawPacketMetadata
from flows.flow_generator import Flow, FlowKey
from preprocessing.feature_extractor import FeatureExtractor


class TestFeatureExtractor(unittest.TestCase):
    def test_feature_extractor_no_payload(self):
        extractor = FeatureExtractor()

        key = FlowKey("192.168.1.5", 55555, "8.8.8.8", 53, "UDP")
        flow = Flow(
            key=key,
            initiator_ip="192.168.1.5",
            initiator_port=55555,
            start_time=1.0,
            last_seen=1.0,
        )

        flow.add_packet(
            RawPacketMetadata(1.0, "192.168.1.5", "8.8.8.8", 55555, 53, "UDP", 80)
        )
        flow.add_packet(
            RawPacketMetadata(1.1, "8.8.8.8", "192.168.1.5", 53, 55555, "UDP", 240)
        )
        flow.add_packet(
            RawPacketMetadata(1.3, "192.168.1.5", "8.8.8.8", 55555, 53, "UDP", 100)
        )

        feats = extractor.extract_features(flow)

        self.assertEqual(feats["forward_packet_count"], 2)
        self.assertEqual(feats["backward_packet_count"], 1)
        self.assertEqual(feats["total_packet_count"], 3)
        self.assertEqual(feats["forward_bytes"], 180)
        self.assertEqual(feats["backward_bytes"], 240)
        self.assertEqual(feats["total_bytes"], 420)
        self.assertAlmostEqual(feats["avg_packet_size"], 140.0)
        self.assertEqual(feats["min_packet_size"], 80.0)
        self.assertEqual(feats["max_packet_size"], 240.0)
        self.assertGreater(feats["mean_iat"], 0)
        self.assertEqual(feats["protocol"], "UDP")
        self.assertEqual(feats["tls_version"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
