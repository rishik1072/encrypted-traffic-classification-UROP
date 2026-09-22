import csv
import sys
import tempfile
import unittest
from pathlib import Path
import yaml

# Ensure project root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from capture.packet_capture import RawPacketMetadata
from training.build_feature_dataset import FeatureDatasetBuilder
from training.build_flow_dataset import FlowDatasetBuilder
from training.create_splits import GroupAwareDatasetSplitter
from training.dataset_cleaner import DatasetCleaner


class TestDatasetPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

        # Build config
        self.config = {
            "traffic_classes": ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"],
            "flows": {
                "idle_timeout_seconds": 5.0,
                "active_timeout_seconds": 30.0,
                "min_packets_for_classification": 2,
            },
            "dataset": {
                "manifest_path": "manifest.csv",
                "flow_output_path": "flows.csv",
                "feature_output_path": "features.csv",
                "cleaned_feature_output_path": "features_cleaned.csv",
                "split_directory": "splits",
                "cleaning_report_path": "cleaning_report.csv",
                "class_distribution_path": "class_distribution.csv",
                "feature_statistics_path": "feature_stats.csv",
                "figures_directory": "figures",
            },
            "splitting": {
                "train_ratio": 0.70,
                "validation_ratio": 0.15,
                "test_ratio": 0.15,
                "group_column": "file_id",
                "random_seed": 42,
            },
            "features": {
                "numerical_features": [
                    "flow_duration",
                    "forward_packet_count",
                    "backward_packet_count",
                    "total_packet_count",
                    "forward_bytes",
                    "backward_bytes",
                    "total_bytes",
                    "avg_packet_size",
                    "min_packet_size",
                    "max_packet_size",
                    "packet_size_variance",
                    "mean_iat",
                    "median_iat",
                    "iat_std",
                    "min_iat",
                    "max_iat",
                    "fwd_bwd_packet_ratio",
                    "fwd_bwd_byte_ratio",
                    "burst_count",
                    "avg_burst_bytes",
                    "avg_burst_packets",
                ],
                "categorical_features": ["protocol", "dst_port"],
                "tls_features": ["tls_version", "tls_cipher_suites_count", "tls_extensions_count", "tls_sni_present"],
            },
        }

        self.config_path = self.base_path / "config.yaml"
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.config, f)

        # Create synthetic manifest
        self.manifest_path = self.base_path / "manifest.csv"
        with open(self.manifest_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "file_id",
                    "pcap_path",
                    "traffic_class",
                    "source",
                    "capture_date",
                    "duration_seconds",
                ],
            )
            writer.writeheader()
            writer.writerows([
                {
                    "file_id": "pcap_web_01",
                    "pcap_path": "web_01.pcap",
                    "traffic_class": "Web",
                    "source": "Lab",
                    "capture_date": "2026-08-23",
                    "duration_seconds": "30",
                },
                {
                    "file_id": "pcap_web_02",
                    "pcap_path": "web_02.pcap",
                    "traffic_class": "Web",
                    "source": "Lab",
                    "capture_date": "2026-08-23",
                    "duration_seconds": "30",
                },
                {
                    "file_id": "pcap_video_01",
                    "pcap_path": "video_01.pcap",
                    "traffic_class": "Video",
                    "source": "Lab",
                    "capture_date": "2026-08-23",
                    "duration_seconds": "30",
                },
                {
                    "file_id": "pcap_video_02",
                    "pcap_path": "video_02.pcap",
                    "traffic_class": "Video",
                    "source": "Lab",
                    "capture_date": "2026-08-23",
                    "duration_seconds": "30",
                },
            ])

        # Prepare synthetic packets
        self.synthetic_packets = {
            "pcap_web_01": [
                RawPacketMetadata(1.0, "192.168.1.1", "1.1.1.1", 50001, 443, "TCP", 100),
                RawPacketMetadata(1.2, "1.1.1.1", "192.168.1.1", 443, 50001, "TCP", 500),
                RawPacketMetadata(1.4, "192.168.1.1", "1.1.1.1", 50001, 443, "TCP", 150),
            ],
            "pcap_web_02": [
                RawPacketMetadata(2.0, "192.168.1.2", "1.1.1.1", 50002, 443, "TCP", 120),
                RawPacketMetadata(2.1, "1.1.1.1", "192.168.1.2", 443, 50002, "TCP", 600),
            ],
            "pcap_video_01": [
                RawPacketMetadata(10.0, "192.168.1.3", "2.2.2.2", 50003, 443, "UDP", 1200),
                RawPacketMetadata(10.1, "2.2.2.2", "192.168.1.3", 443, 50003, "UDP", 1400),
                RawPacketMetadata(10.2, "2.2.2.2", "192.168.1.3", 443, 50003, "UDP", 1400),
            ],
            "pcap_video_02": [
                RawPacketMetadata(20.0, "192.168.1.4", "2.2.2.2", 50004, 443, "UDP", 1100),
                RawPacketMetadata(20.1, "2.2.2.2", "192.168.1.4", 443, 50004, "UDP", 1300),
            ],
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_pipeline_flow_to_features_and_splits(self):
        # 1. Generate Flows
        flow_builder = FlowDatasetBuilder(config_path=self.config_path)
        flow_records = flow_builder.build_dataset_from_manifest(
            manifest_path=self.manifest_path,
            output_path=self.base_path / "flows.csv",
            synthetic_packet_source=self.synthetic_packets,
        )
        self.assertEqual(len(flow_records), 4)
        for r in flow_records:
            self.assertIn(r["traffic_class"], ["Web", "Video"])

        # 2. Extract Features
        feat_builder = FeatureDatasetBuilder(config_path=self.config_path)
        feature_rows = feat_builder.build_features_from_flows(
            flow_input_path=self.base_path / "flows.csv",
            feature_output_path=self.base_path / "features.csv",
        )
        self.assertEqual(len(feature_rows), 4)
        # Verify no raw sensitive source/dest IPs leak into the feature table
        for r in feature_rows:
            self.assertNotIn("src_ip", r)
            self.assertNotIn("dst_ip", r)
            self.assertIn("file_id", r)
            self.assertIn("traffic_class", r)
            self.assertIn("flow_duration", r)

        # 3. Clean Dataset
        cleaner = DatasetCleaner(config_path=self.config_path)
        clean_rows, metrics = cleaner.clean_dataset(
            input_path=self.base_path / "features.csv",
            output_path=self.base_path / "features_cleaned.csv",
            report_path=self.base_path / "cleaning_report.csv",
        )
        self.assertEqual(len(clean_rows), 4)
        self.assertEqual(metrics["valid_flows"], 4)

        # 4. Group-Aware Split
        splitter = GroupAwareDatasetSplitter(config_path=self.config_path)
        train_s, val_s, test_s = splitter.split_dataset(
            input_path=self.base_path / "features_cleaned.csv",
            split_dir=self.base_path / "splits",
        )

        train_groups = {r["file_id"] for r in train_s}
        val_groups = {r["file_id"] for r in val_s}
        test_groups = {r["file_id"] for r in test_s}

        # Check total flow count matches
        self.assertEqual(len(train_s) + len(val_s) + len(test_s), 4)

        # Verify zero group leakage between splits
        self.assertTrue(train_groups.isdisjoint(val_groups))
        self.assertTrue(train_groups.isdisjoint(test_groups))
        self.assertTrue(val_groups.isdisjoint(test_groups))


if __name__ == "__main__":
    unittest.main()
