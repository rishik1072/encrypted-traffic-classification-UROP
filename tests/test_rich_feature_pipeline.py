"""
Unit Tests for Phase 5: Rich Zero-Payload Feature Representation & Selection Pipeline.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from preprocessing.rich_feature_extractor import FEATURE_FAMILIES_MAP, RichFeatureExtractor
from training.rich_feature_pipeline import (
    FORBIDDEN_METADATA_COLS,
    RichFeaturePipeline,
)


class TestRichFeaturePipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp())
        self.data_dir = self.test_dir / "data"
        self.processed_dir = self.data_dir / "processed" / "features"
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        self.extractor = RichFeatureExtractor()

        # Create dummy rich feature dataset
        self.rich_csv_path = self.processed_dir / "features_real_rich_clean_v2.csv"
        rows = []
        classes = ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"]

        for s_idx in range(60):
            cls = classes[s_idx % len(classes)]
            sess_id = f"sess_rich_{cls.lower()}_{s_idx:03d}"
            for f_idx in range(2):
                t_vec = [0.0, 0.02, 0.05, 0.1, 0.2]
                l_vec = [120, 500, 1400, 80, 900]
                d_vec = [1, 1, 2, 1, 2]
                feats = self.extractor.extract_rich_features(t_vec, l_vec, d_vec, duration=0.2)
                row = {
                    "flow_id": f"{sess_id}_flow_{f_idx:05d}",
                    "file_id": f"real_{sess_id}",
                    "session_id": sess_id,
                    "traffic_class": cls,
                    "environment_id": "env_win11_wifi" if s_idx < 40 else "env_win11_eth",
                    "network_condition_id": "NORMAL" if s_idx < 45 else "HIGH_LATENCY",
                    "capture_day": "day_1" if s_idx < 30 else "day_4",
                    "capture_date": "2026-08-20" if s_idx < 30 else "2026-08-23",
                    "collection_batch": "batch_01",
                    "device_id": "dev_01",
                    "interface_type": "wifi",
                    "tunnel_state": "warp_enabled",
                    "activity_variant": f"act_{cls.lower()}_01" if s_idx % 2 == 0 else f"act_{cls.lower()}_02",
                    "data_origin": "real",
                    "dataset_version": "v2",
                    **{k: f"{v:.6f}" for k, v in feats.items()},
                }
                rows.append(row)

        with open(self.rich_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        self.config_path = self.test_dir / "config.yaml"
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("""
features:
  numerical_features:
    - pkt_size_mean
    - pkt_size_std
    - iat_mean
    - iat_std
    - burst_count
    - total_bytes
models:
  decision_tree:
    max_depth: 5
""")

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_rich_feature_extractor_validity(self) -> None:
        t_vec = [0.0, 0.01, 0.03, 0.06, 0.10]
        l_vec = [100, 200, 1400, 60, 800]
        d_vec = [1, 1, 2, 1, 2]
        feats = self.extractor.extract_rich_features(t_vec, l_vec, d_vec, duration=0.1)

        self.assertGreaterEqual(len(feats), 60)
        self.assertIn("pkt_size_mean", feats)
        self.assertIn("pkt_size_p95", feats)
        self.assertIn("iat_median", feats)
        self.assertIn("direction_switch_count", feats)
        self.assertEqual(feats["direction_switch_count"], 3.0)
        self.assertIn("burst_density", feats)

    def test_zero_payload_policy_compliance(self) -> None:
        for feat in FEATURE_FAMILIES_MAP.keys():
            self.assertNotIn(feat, FORBIDDEN_METADATA_COLS)
            # Ensure no payload/decryption terms in feature names
            self.assertNotIn("payload", feat.lower())
            self.assertNotIn("content", feat.lower())
            self.assertNotIn("decrypt", feat.lower())

    def test_end_to_end_rich_pipeline(self) -> None:
        pipeline = RichFeaturePipeline(
            config_path=str(self.config_path),
            data_path=str(self.rich_csv_path),
            output_dir=str(self.test_dir / "results"),
        )
        summary = pipeline.run()

        self.assertIn("rich_feature_count", summary)
        self.assertGreaterEqual(summary["rich_feature_count"], 60)
        self.assertIn("best_K", summary)
        self.assertTrue(Path(self.test_dir / "results" / "tables" / "rich_feature_schema.csv").exists())
        self.assertTrue(Path(self.test_dir / "results" / "tables" / "rich_feature_quality.csv").exists())
        self.assertTrue(Path(self.test_dir / "results" / "tables" / "rich_feature_correlation.csv").exists())
        self.assertTrue(Path(self.test_dir / "results" / "tables" / "rich_feature_ranking.csv").exists())
        self.assertTrue(Path(self.test_dir / "results" / "tables" / "feature_family_ablation.csv").exists())
        self.assertTrue(Path(self.test_dir / "results" / "tables" / "rich_feature_reduction_cv.csv").exists())
        self.assertTrue(Path(self.test_dir / "results" / "tables" / "rich_feature_cost.csv").exists())
        self.assertTrue(Path(self.test_dir / "results" / "tables" / "rich_final_test.csv").exists())
        self.assertTrue(Path(self.test_dir / "results" / "tables" / "phase_progression.csv").exists())
        self.assertTrue(Path(self.test_dir / "results" / "rich_feature_report.md").exists())


if __name__ == "__main__":
    unittest.main()
