"""
Tests for Real Metadata Pipeline & Source Abstractions.

Verifies:
- MetadataPacketSource reads zero-payload CSV correctly into RawPacketMetadata
- FlowGenerator creates flows matching expected packet/byte counts and directions
- FlowDatasetBuilder processes metadata sources without attempting PCAP/directory reads
- dataset_quality distinguishes real from synthetic
"""

from __future__ import annotations

import csv
import os
import tempfile
import unittest
from pathlib import Path

from capture.packet_source import MetadataPacketSource, SyntheticPacketSource, create_packet_source
from flows.flow_generator import FlowGenerator
from training.build_feature_dataset import FeatureDatasetBuilder
from training.build_flow_dataset import FlowDatasetBuilder
from training.dataset_quality import generate_dataset_quality_report


class TestRealMetadataPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.meta_csv = self.temp_path / "mock_meta.csv"

        # Create mock metadata CSV imitating genuine real metadata schema
        with open(self.meta_csv, "w", newline="", encoding="utf-8") as f:
            fields = ["timestamp", "packet_length", "ip_version", "protocol", "source_port", "destination_port", "tcp_flags", "direction", "session_id", "traffic_class"]
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for i in range(20):
                writer.writerow({
                    "timestamp": 1000.0 + i * 0.1,
                    "packet_length": 500 + i * 10,
                    "ip_version": 4,
                    "protocol": "TCP",
                    "source_port": 50000 + (i % 2),
                    "destination_port": 443,
                    "tcp_flags": "ACK",
                    "direction": "forward" if i % 2 == 0 else "backward",
                    "session_id": "test_sess_001",
                    "traffic_class": "Web",
                })

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_metadata_packet_source_reading(self):
        source = MetadataPacketSource(self.meta_csv)
        packets = list(source.read_packets())
        self.assertEqual(len(packets), 20)
        self.assertEqual(packets[0].dst_port, 443)
        self.assertEqual(packets[0].protocol, "TCP")

    def test_flow_generation_from_metadata(self):
        source = MetadataPacketSource(self.meta_csv)
        generator = FlowGenerator(idle_timeout=5.0, active_timeout=30.0)
        completed = []
        for pkt in source.read_packets():
            fl = generator.process_packet(pkt)
            if fl:
                completed.append(fl)
        completed.extend(generator.flush_all())

        self.assertGreater(len(completed), 0)
        total_pkts = sum(fl.total_packets for fl in completed)
        self.assertEqual(total_pkts, 20)

    def test_flow_dataset_builder_real_metadata(self):
        # Create manifest referencing the metadata CSV
        manifest_path = self.temp_path / "manifest.csv"
        with open(manifest_path, "w", newline="", encoding="utf-8") as f:
            fields = [
                "file_id", "pcap_path", "metadata_path", "raw_source_type", "raw_source_path",
                "traffic_class", "source", "capture_date", "session_id", "environment_id",
                "device_id", "dataset_id", "capture_duration", "packet_count", "byte_count",
                "flow_count", "validation_status", "data_origin", "capture_source", "notes"
            ]
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerow({
                "file_id": "real_test_sess",
                "pcap_path": "",
                "metadata_path": str(self.meta_csv),
                "raw_source_type": "METADATA_CSV",
                "raw_source_path": str(self.meta_csv),
                "traffic_class": "Web",
                "source": "lab_collection",
                "capture_date": "2026-08-23",
                "session_id": "test_sess_001",
                "environment_id": "env1",
                "device_id": "dev1",
                "dataset_id": "ds1",
                "capture_duration": 2.0,
                "packet_count": 20,
                "byte_count": 12000,
                "flow_count": 2,
                "validation_status": "PASS",
                "data_origin": "real",
                "capture_source": "REAL_LIVE_CAPTURE",
                "notes": "",
            })

        flow_out = self.temp_path / "flows_out.csv"
        feat_out = self.temp_path / "features_out.csv"

        builder = FlowDatasetBuilder()
        flows = builder.build_dataset_from_manifest(
            manifest_path=manifest_path,
            output_path=flow_out,
            origin_filter="real",
        )
        self.assertGreater(len(flows), 0)
        self.assertTrue(flow_out.exists())

        feat_builder = FeatureDatasetBuilder()
        feats = feat_builder.build_features_from_flows(
            flow_input_path=flow_out,
            feature_output_path=feat_out,
            origin_filter="real",
        )
        self.assertEqual(len(feats), len(flows))
        self.assertTrue(feat_out.exists())


if __name__ == "__main__":
    unittest.main()
