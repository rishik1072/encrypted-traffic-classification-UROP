"""
Unit Tests for Phase 4: Dataset Expansion & Cross-Environment Generalization Benchmark.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from capture.expand_dataset_v2 import generate_dataset_v2
from experiments.real_generalization_v2 import (
    FORBIDDEN_METADATA_COLS,
    FROZEN_PHASE3_FEATURES,
    RealGeneralizationV2Pipeline,
)


class TestRealGeneralizationV2(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp())
        self.data_dir = self.test_dir / "data"
        self.processed_dir = self.data_dir / "processed" / "features"
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.v2_dir = self.data_dir / "dataset_versions" / "v2"
        self.v2_dir.mkdir(parents=True, exist_ok=True)

        # Create dummy clean v1 dataset
        self.clean_v1_path = self.processed_dir / "features_real_clean.csv"
        rows = []
        classes = ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"]
        for s_idx in range(60):
            cls = classes[s_idx % len(classes)]
            sess_id = f"sess_real_{cls.lower()}_{s_idx:03d}"
            for f_idx in range(2):
                rows.append({
                    "flow_id": f"{sess_id}_flow_{f_idx:05d}",
                    "file_id": f"real_{sess_id}",
                    "session_id": sess_id,
                    "traffic_class": cls,
                    "flow_duration": "50.0",
                    "forward_packet_count": "100",
                    "backward_packet_count": "50",
                    "total_packet_count": "150",
                    "forward_bytes": "20000",
                    "backward_bytes": "5000",
                    "total_bytes": "25000",
                    "avg_packet_size": "166.67",
                    "min_packet_size": "40.0",
                    "max_packet_size": "1400.0",
                    "packet_size_variance": "5000.0",
                    "mean_iat": "0.02",
                    "median_iat": "0.01",
                    "iat_std": "0.03",
                    "min_iat": "0.0001",
                    "max_iat": "0.5",
                    "fwd_bwd_packet_ratio": "2.0",
                    "fwd_bwd_byte_ratio": "4.0",
                    "burst_count": "4",
                    "avg_burst_bytes": "5000.0",
                    "avg_burst_packets": "25.0",
                    "protocol": "UDP",
                    "dst_port": "443",
                    "tls_version": "UNKNOWN",
                    "tls_cipher_suites_count": "0",
                    "tls_extensions_count": "0",
                    "tls_sni_present": "0",
                })
        with open(self.clean_v1_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        # Create dummy config
        self.config_path = self.test_dir / "config.yaml"
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("""
features:
  numerical_features:
    - avg_packet_size
    - burst_count
    - max_iat
    - min_packet_size
    - forward_packet_count
    - fwd_bwd_byte_ratio
    - fwd_bwd_packet_ratio
    - total_bytes
    - total_packet_count
    - avg_burst_bytes
models:
  decision_tree:
    max_depth: 5
""")

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dataset_v2_expansion_and_provenance(self) -> None:
        clean_v2_path = self.processed_dir / "features_real_clean_v2.csv"
        all_v2_path = self.processed_dir / "features_real_v2.csv"
        records, provenance = generate_dataset_v2(
            base_clean_path=self.clean_v1_path,
            output_dir=self.v2_dir,
            features_out_path=clean_v2_path,
            all_features_out_path=all_v2_path,
        )

        self.assertEqual(provenance["total_sessions"], 150)
        self.assertEqual(len(records), 300)
        self.assertTrue((self.v2_dir / "manifest.csv").exists())
        self.assertTrue((self.v2_dir / "manifest.json").exists())
        self.assertTrue((self.v2_dir / "provenance.json").exists())
        self.assertTrue((self.v2_dir / "hashes.sha256").exists())

    def test_zero_leakage_and_metadata_isolation(self) -> None:
        for feat in FROZEN_PHASE3_FEATURES:
            self.assertNotIn(feat, FORBIDDEN_METADATA_COLS)

    def test_pipeline_execution_all_regimes(self) -> None:
        clean_v2_path = self.processed_dir / "features_real_clean_v2.csv"
        all_v2_path = self.processed_dir / "features_real_v2.csv"
        generate_dataset_v2(
            base_clean_path=self.clean_v1_path,
            output_dir=self.v2_dir,
            features_out_path=clean_v2_path,
            all_features_out_path=all_v2_path,
        )

        pipeline = RealGeneralizationV2Pipeline(
            config_path=str(self.config_path),
            data_path=str(clean_v2_path),
            manifest_path=str(self.v2_dir / "manifest.csv"),
            provenance_path=str(self.v2_dir / "provenance.json"),
            output_dir=str(self.test_dir / "results"),
        )
        summary = pipeline.run()

        self.assertEqual(summary["total_sessions"], 150)
        self.assertEqual(summary["total_flows"], 300)
        self.assertTrue(Path(self.test_dir / "results" / "tables" / "generalization_v2.csv").exists())
        self.assertTrue(Path(self.test_dir / "results" / "tables" / "environment_generalization.csv").exists())
        self.assertTrue(Path(self.test_dir / "results" / "tables" / "temporal_generalization.csv").exists())
        self.assertTrue(Path(self.test_dir / "results" / "tables" / "condition_robustness.csv").exists())
        self.assertTrue(Path(self.test_dir / "results" / "tables" / "activity_variant_generalization.csv").exists())
        self.assertTrue(Path(self.test_dir / "results" / "real_generalization_v2_report.md").exists())


if __name__ == "__main__":
    unittest.main()
