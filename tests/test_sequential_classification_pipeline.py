"""
Unit Tests for Phase 7: Sequential Subflow Representation, Hierarchical Classification, and Abstention.
"""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from preprocessing.sequential_feature_extractor import (
    WINDOW_BASE_FEATURES,
    SequentialFeatureExtractor,
)
from training.build_sequential_dataset import build_sequential_datasets
from training.sequential_classification_pipeline import (
    METADATA_COLS,
    SequentialClassificationPipeline,
)


class TestSequentialClassificationPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp())
        self.sequential_dir = self.test_dir / "sequential"
        self.output_dir = self.test_dir / "results"
        self.data_dir = self.test_dir / "data"
        self.clean_v2_path = self.data_dir / "processed" / "features" / "features_real_clean_v2.csv"
        self.clean_v2_path.parent.mkdir(parents=True, exist_ok=True)
        self.sequential_dir.mkdir(parents=True, exist_ok=True)

        self.extractor = SequentialFeatureExtractor(min_packets=2)

        # Generate dummy clean dataset
        classes = ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"]
        dummy_rows = []
        for s_idx in range(30):
            cls = classes[s_idx % len(classes)]
            sess_id = f"sess_seq_{cls.lower()}_{s_idx:03d}"
            for f_idx in range(2):
                dummy_rows.append({
                    "flow_id": f"{sess_id}_flow_{f_idx:05d}",
                    "file_id": f"real_{sess_id}",
                    "session_id": sess_id,
                    "traffic_class": cls,
                    "environment_id": "env_win11_wifi" if s_idx < 20 else "env_win11_eth",
                    "network_condition_id": "NORMAL" if s_idx < 22 else "PACKET_LOSS_1PCT",
                    "capture_day": "day_1" if s_idx < 15 else "day_4",
                    "capture_date": "2026-08-20" if s_idx < 15 else "2026-08-23",
                    "collection_batch": "batch_01",
                    "device_id": "dev_01",
                    "interface_type": "wifi",
                    "tunnel_state": "warp_enabled",
                    "activity_variant": f"act_{cls.lower()}_01" if s_idx % 2 == 0 else f"act_{cls.lower()}_02",
                    "data_origin": "real",
                    "dataset_version": "v2",
                    "forward_packet_count": "60",
                    "backward_packet_count": "40",
                    "forward_bytes": "30000",
                    "backward_bytes": "6000",
                    "flow_duration": "20.0",
                    "mean_iat": "0.02",
                })

        with open(self.clean_v2_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(dummy_rows[0].keys()))
            writer.writeheader()
            writer.writerows(dummy_rows)

        self.config_path = self.test_dir / "config.yaml"
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("""
features:
  numerical_features:
    - packet_count
    - byte_count
models:
  decision_tree:
    max_depth: 5
""")

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_window_feature_extraction(self) -> None:
        t_vec = [0.0, 0.05, 0.10, 0.20, 0.50, 1.20, 2.50, 5.00]
        l_vec = [100, 200, 1400, 80, 500, 1200, 60, 900]
        d_vec = [1, 1, 2, 1, 2, 1, 2, 1]

        feats = self.extractor.extract_window_features(t_vec, l_vec, d_vec, window_duration=5.0)
        self.assertEqual(len(feats), len(WINDOW_BASE_FEATURES))
        self.assertEqual(feats["packet_count"], 8.0)
        self.assertIn("direction_switch_count", feats)

    def test_sequence_aggregation(self) -> None:
        t_vec = [0.0, 0.05, 0.10, 0.20, 0.50, 1.20, 2.50, 5.00]
        l_vec = [100, 200, 1400, 80, 500, 1200, 60, 900]
        d_vec = [1, 1, 2, 1, 2, 1, 2, 1]

        sub_windows = self.extractor.generate_sequential_windows(
            t_vec, l_vec, d_vec, window_sec=2.0, stride_sec=1.0, max_windows=5
        )
        self.assertGreaterEqual(len(sub_windows), 1)

        feat_list = [w[2] for w in sub_windows]
        agg_feats = self.extractor.aggregate_sequence_features(feat_list)
        self.assertEqual(len(agg_feats), 193)
        self.assertIn("packet_count_mean", agg_feats)
        self.assertIn("byte_rate_slope", agg_feats)
        self.assertIn("active_window_fraction", agg_feats)

    def test_zero_payload_policy_compliance(self) -> None:
        for feat in WINDOW_BASE_FEATURES:
            self.assertNotIn(feat, METADATA_COLS)
            self.assertNotIn("payload", feat.lower())
            self.assertNotIn("content", feat.lower())

    def test_end_to_end_sequential_pipeline(self) -> None:
        # 1. Build datasets
        build_sequential_datasets(
            input_clean_path=self.clean_v2_path,
            output_dir=self.sequential_dir,
        )

        self.assertTrue((self.sequential_dir / "sequential_windows_2s_1s.csv").exists())
        self.assertTrue((self.sequential_dir / "sequential_aggregated_2s_1s.csv").exists())

        # 2. Run pipeline
        pipeline = SequentialClassificationPipeline(
            config_path=str(self.config_path),
            sequential_dir=str(self.sequential_dir),
            output_dir=str(self.output_dir),
            test_session_ids_path=None,
        )
        summary = pipeline.run()

        self.assertIn("best_model", summary)
        self.assertIn("final_test_macro_f1", summary)
        self.assertTrue((self.output_dir / "tables" / "phase7_leakage_check.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase7_window_ablation.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase7_sequence_ablation.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase7_early_prediction.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase7_prediction_stability.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase7_abstention_policy.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase7_calibration.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase7_cost.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase7_generalization.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase7_final_test.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase_progression_sequential.csv").exists())
        self.assertTrue((self.output_dir / "phase7_sequential_report.md").exists())


if __name__ == "__main__":
    unittest.main()
