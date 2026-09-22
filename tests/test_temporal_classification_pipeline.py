"""
Unit Tests for Phase 6: Temporal Windowed Real-Time Encrypted Traffic Classification.
"""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from preprocessing.temporal_window_extractor import (
    TEMPORAL_FEATURE_NAMES,
    TemporalWindowExtractor,
)
from training.build_temporal_dataset import build_temporal_datasets
from training.temporal_classification_pipeline import (
    METADATA_EXCLUSION_COLS,
    TemporalClassificationPipeline,
)


class TestTemporalClassificationPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp())
        self.temporal_dir = self.test_dir / "temporal"
        self.output_dir = self.test_dir / "results"
        self.data_dir = self.test_dir / "data"
        self.clean_v2_path = self.data_dir / "processed" / "features" / "features_real_clean_v2.csv"
        self.clean_v2_path.parent.mkdir(parents=True, exist_ok=True)
        self.temporal_dir.mkdir(parents=True, exist_ok=True)

        self.extractor = TemporalWindowExtractor(min_packets=3)

        # Generate dummy clean dataset
        classes = ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"]
        dummy_rows = []
        for s_idx in range(30):
            cls = classes[s_idx % len(classes)]
            sess_id = f"sess_temp_{cls.lower()}_{s_idx:03d}"
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
                    "forward_packet_count": "50",
                    "backward_packet_count": "30",
                    "forward_bytes": "25000",
                    "backward_bytes": "5000",
                    "flow_duration": "15.0",
                    "mean_iat": "0.02",
                })

        with open(self.clean_v2_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(dummy_rows[0].keys()))
            writer.writeheader()
            writer.writerows(dummy_rows)

        self.config_path = self.test_dir / "temporal_windows.yaml"
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("""
temporal_windows:
  min_packets: 3
  prefix_sizes: [5, 10, 20, 50, 100]
  window_sizes_sec: [1.0, 2.0, 5.0, 10.0]
  confidence_thresholds: [0.60, 0.70, 0.80, 0.90]
  low_confidence_label: "LOW_CONFIDENCE"
""")

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_window_extractor_prefix_and_time(self) -> None:
        t_vec = [0.0, 0.05, 0.10, 0.20, 0.50, 1.20, 2.50, 5.00]
        l_vec = [100, 200, 1400, 80, 500, 1200, 60, 900]
        d_vec = [1, 1, 2, 1, 2, 1, 2, 1]

        # Prefix 5
        feats_p5 = self.extractor.extract_prefix(t_vec, l_vec, d_vec, prefix_size=5)
        self.assertIsNotNone(feats_p5)
        self.assertEqual(feats_p5["packet_count"], 5.0)
        self.assertEqual(len(feats_p5), 20)

        # Prefix too large
        feats_p100 = self.extractor.extract_prefix(t_vec, l_vec, d_vec, prefix_size=100)
        self.assertIsNone(feats_p100)

        # Time window 1s
        feats_1s = self.extractor.extract_time_window(t_vec, l_vec, d_vec, window_sec=1.0)
        self.assertIsNotNone(feats_1s)
        self.assertEqual(feats_1s["packet_count"], 5.0)

        # Sliding windows
        sliding = self.extractor.extract_sliding_windows(t_vec, l_vec, d_vec, window_sec=2.0, stride_sec=1.0)
        self.assertGreaterEqual(len(sliding), 1)

    def test_zero_payload_policy_compliance(self) -> None:
        for feat in TEMPORAL_FEATURE_NAMES:
            self.assertNotIn(feat, METADATA_EXCLUSION_COLS)
            self.assertNotIn("payload", feat.lower())
            self.assertNotIn("content", feat.lower())
            self.assertNotIn("sni", feat.lower())

    def test_end_to_end_temporal_pipeline(self) -> None:
        # Build temporal datasets
        build_temporal_datasets(
            input_clean_path=self.clean_v2_path,
            output_dir=self.temporal_dir,
        )

        self.assertTrue((self.temporal_dir / "prefix_5.csv").exists())
        self.assertTrue((self.temporal_dir / "window_1s.csv").exists())

        # Run pipeline
        pipeline = TemporalClassificationPipeline(
            config_path=str(self.config_path),
            temporal_dir=str(self.temporal_dir),
            output_dir=str(self.output_dir),
            test_session_ids_path=None,
        )
        summary = pipeline.run()

        self.assertIn("best_model", summary)
        self.assertIn("final_macro_f1", summary)
        self.assertTrue((self.output_dir / "tables" / "window_ablation.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "temporal_early_prediction.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "prediction_stability.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "temporal_inference_cost.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "temporal_memory_cost.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "early_prediction_policy.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "temporal_final_test.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase_progression_temporal.csv").exists())
        self.assertTrue((self.output_dir / "temporal_classification_report.md").exists())


if __name__ == "__main__":
    unittest.main()
