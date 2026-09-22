"""
Tests for Phase 1.5 Real Dataset Artifact, Contamination, and Leakage Auditing.
"""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path
import yaml

from training.audit_flow_artifacts import FlowArtifactAuditor
from training.feature_leakage_audit import FeatureLeakageAuditor, FORBIDDEN_METADATA_COLS
from training.collection_bias_audit import CollectionBiasAuditor
from training.create_splits import GroupAwareDatasetSplitter


class TestAuditFlowArtifacts(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

        # Create config.yaml
        self.config_file = self.base_path / "config.yaml"
        config_data = {
            "traffic_classes": ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"],
            "dataset_quality": {
                "minimum_packets_for_training": 3,
                "minimum_bytes_for_training": 128,
                "artifact_review_enabled": True,
            },
            "features": {
                "numerical_features": ["flow_duration", "total_packet_count", "total_bytes", "mean_iat"],
                "categorical_features": ["protocol", "dst_port"],
                "tls_features": ["tls_version"],
            },
            "splitting": {
                "train_ratio": 0.70,
                "validation_ratio": 0.15,
                "test_ratio": 0.15,
                "group_column": "session_id",
                "random_seed": 42,
            },
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        # Create mock flows and features
        self.flows_file = self.base_path / "flows.csv"
        self.features_file = self.base_path / "features.csv"

        flows = [
            # Legitimate app flow
            {"flow_id": "f1", "session_id": "s1", "traffic_class": "Web", "protocol": "UDP", "total_packets": 100, "total_bytes": 50000},
            # SSDP artifact flow
            {"flow_id": "f2", "session_id": "s1", "traffic_class": "Web", "protocol": "UDP", "total_packets": 4, "total_bytes": 848},
            # Legitimate Video flow
            {"flow_id": "f3", "session_id": "s2", "traffic_class": "Video", "protocol": "UDP", "total_packets": 200, "total_bytes": 100000},
            # SSDP artifact in video session
            {"flow_id": "f4", "session_id": "s2", "traffic_class": "Video", "protocol": "UDP", "total_packets": 4, "total_bytes": 848},
        ]
        features = [
            {"flow_id": "f1", "session_id": "s1", "traffic_class": "Web", "protocol": "UDP", "dst_port": "443", "flow_duration": "10.0", "total_packet_count": "100", "total_bytes": "50000", "mean_iat": "0.1", "tls_version": "UNKNOWN"},
            {"flow_id": "f2", "session_id": "s1", "traffic_class": "Web", "protocol": "UDP", "dst_port": "1900", "flow_duration": "3.0", "total_packet_count": "4", "total_bytes": "848", "mean_iat": "0.5", "tls_version": "UNKNOWN"},
            {"flow_id": "f3", "session_id": "s2", "traffic_class": "Video", "protocol": "UDP", "dst_port": "443", "flow_duration": "15.0", "total_packet_count": "200", "total_bytes": "100000", "mean_iat": "0.05", "tls_version": "UNKNOWN"},
            {"flow_id": "f4", "session_id": "s2", "traffic_class": "Video", "protocol": "UDP", "dst_port": "1900", "flow_duration": "3.0", "total_packet_count": "4", "total_bytes": "848", "mean_iat": "0.5", "tls_version": "UNKNOWN"},
        ]

        with open(self.flows_file, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(flows[0].keys()))
            w.writeheader()
            w.writerows(flows)

        with open(self.features_file, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(features[0].keys()))
            w.writeheader()
            w.writerows(features)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_artifact_detection_and_exclusion(self):
        auditor = FlowArtifactAuditor(config_path=self.config_file)
        res = auditor.audit_and_clean(
            flows_input_path=self.flows_file,
            features_input_path=self.features_file,
        )
        self.assertEqual(res["total_flows"], 4)
        self.assertEqual(res["excluded_flows"], 2)
        self.assertEqual(res["clean_flows"], 2)

        # Check exclusion log
        log_path = self.base_path / "results/tables/flow_exclusion_log.csv"
        self.assertTrue(log_path.exists())
        with open(log_path, "r", encoding="utf-8") as f:
            log_entries = list(csv.DictReader(f))
        self.assertEqual(len(log_entries), 2)
        self.assertTrue(all(r["rule"] == "RULE_MULTICLASS_CONTROL_TRAFFIC" for r in log_entries))

    def test_feature_leakage_and_metadata_exclusion(self):
        auditor = FeatureLeakageAuditor(config_path=self.config_file)
        res = auditor.audit_features(
            features_path=self.features_file,
            output_schema_path=self.base_path / "schema.csv",
            output_leakage_path=self.base_path / "leak.csv",
        )
        schema = res["schema_audit"]
        session_col = [r for r in schema if r["column_name"] == "session_id"][0]
        self.assertEqual(session_col["ml_inclusion_allowed"], "NO")
        self.assertEqual(session_col["status"], "EXCLUDED_METADATA")

    def test_clean_split_group_isolation(self):
        # Test clean group-aware splitting
        clean_features_path = self.base_path / "clean_feats.csv"
        rows = [
            {"session_id": "sess_1", "traffic_class": "Web", "val": "1"},
            {"session_id": "sess_2", "traffic_class": "Web", "val": "2"},
            {"session_id": "sess_3", "traffic_class": "Video", "val": "3"},
            {"session_id": "sess_4", "traffic_class": "Video", "val": "4"},
        ]
        with open(clean_features_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["session_id", "traffic_class", "val"])
            w.writeheader()
            w.writerows(rows)

        splitter = GroupAwareDatasetSplitter(config_path=self.config_file)
        tr, va, te = splitter.split_dataset(
            input_path=clean_features_path,
            split_dir=self.base_path / "splits",
            origin_filter="all",
        )
        tr_sess = set(r["session_id"] for r in tr)
        te_sess = set(r["session_id"] for r in te)
        self.assertTrue(tr_sess.isdisjoint(te_sess))


if __name__ == "__main__":
    unittest.main()
