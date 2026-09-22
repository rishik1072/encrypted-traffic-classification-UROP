import sys
import unittest
from pathlib import Path

# Ensure project root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from capture.packet_capture import RawPacketMetadata
from flows.flow_generator import Direction, Flow, FlowGenerator, FlowKey


class TestFlows(unittest.TestCase):
    def test_flow_key_derivation(self):
        pkt1 = RawPacketMetadata(
            timestamp=100.0,
            src_ip="192.168.1.10",
            dst_ip="104.244.42.1",
            src_port=54321,
            dst_port=443,
            protocol="TCP",
            length=120,
        )
        pkt2 = RawPacketMetadata(
            timestamp=100.1,
            src_ip="104.244.42.1",
            dst_ip="192.168.1.10",
            src_port=443,
            dst_port=54321,
            protocol="TCP",
            length=1400,
        )

        key1, dir1 = FlowKey.from_packet(pkt1)
        key2, dir2 = FlowKey.from_packet(pkt2)

        # Key must be canonical (identical 5-tuple regardless of direction)
        self.assertEqual(key1, key2)
        self.assertNotEqual(dir1, dir2)

    def test_flow_aggregation_and_duration(self):
        generator = FlowGenerator(idle_timeout=5.0, active_timeout=30.0)

        pkt1 = RawPacketMetadata(
            timestamp=10.0,
            src_ip="10.0.0.1",
            dst_ip="10.0.0.2",
            src_port=50000,
            dst_port=443,
            protocol="TCP",
            length=200,
        )
        pkt2 = RawPacketMetadata(
            timestamp=12.5,
            src_ip="10.0.0.2",
            dst_ip="10.0.0.1",
            src_port=443,
            dst_port=50000,
            protocol="TCP",
            length=500,
        )

        generator.process_packet(pkt1)
        generator.process_packet(pkt2)

        flows = generator.flush_all()
        self.assertEqual(len(flows), 1)

        flow = flows[0]
        self.assertEqual(flow.total_packets, 2)
        self.assertEqual(flow.duration, 2.5)


if __name__ == "__main__":
    unittest.main()
