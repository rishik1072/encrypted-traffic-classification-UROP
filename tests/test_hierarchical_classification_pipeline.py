"""
Unit Tests for Phase 8: Hierarchical Classification, Selective Prediction, and Unknown-Traffic Detection.
"""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from models.hierarchical_classifier import HierarchicalTrafficClassifier
from training.discover_traffic_hierarchy import (
    evaluate_hierarchy_candidates,
    get_selected_hierarchy,
    map_fine_to_coarse,
)
from training.hierarchical_classification_pipeline import (
    HierarchicalClassificationPipeline,
)


class TestHierarchicalClassificationPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.test_dir / "results"
        self.data_dir = self.test_dir / "data"
        self.clean_v2_path = self.data_dir / "processed" / "features" / "features_real_clean_v2.csv"
        self.clean_v2_path.parent.mkdir(parents=True, exist_ok=True)

        self.hierarchy = get_selected_hierarchy()

        # Generate dummy clean dataset (6 balanced classes)
        classes = ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"]
        dummy_rows = []
        for s_idx in range(30):
            cls = classes[s_idx % len(classes)]
            sess_id = f"sess_hier_{cls.lower()}_{s_idx:03d}"
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
                    "mean_iat": "0.03",
                    "total_packet_count": "80",
                    "total_bytes": "30000",
                    "avg_packet_size": "375.0",
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
    - forward_packet_count
    - backward_packet_count
    - forward_bytes
    - backward_bytes
models:
  decision_tree:
    max_depth: 5
""")

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_hierarchy_mapping(self) -> None:
        self.assertEqual(map_fine_to_coarse("File Transfer", self.hierarchy), "Bulk_Streaming")
        self.assertEqual(map_fine_to_coarse("Video", self.hierarchy), "Bulk_Streaming")
        self.assertEqual(map_fine_to_coarse("Web", self.hierarchy), "Interactive")
        self.assertEqual(map_fine_to_coarse("Messaging", self.hierarchy), "Interactive")
        self.assertEqual(map_fine_to_coarse("VoIP", self.hierarchy), "Interactive")
        self.assertEqual(map_fine_to_coarse("Other", self.hierarchy), "Other")

    def test_hierarchy_discovery(self) -> None:
        with open(self.clean_v2_path, "r", encoding="utf-8") as f:
            dev_recs = list(csv.DictReader(f))

        candidates = evaluate_hierarchy_candidates(
            dev_recs,
            output_table_path=self.output_dir / "tables" / "hierarchy_candidates.csv"
        )
        self.assertGreaterEqual(len(candidates), 3)
        self.assertTrue((self.output_dir / "tables" / "hierarchy_candidates.csv").exists())

    def test_hierarchical_composed_confidence(self) -> None:
        with open(self.clean_v2_path, "r", encoding="utf-8") as f:
            dev_recs = list(csv.DictReader(f))

        features = ["forward_packet_count", "backward_packet_count", "forward_bytes", "backward_bytes"]
        hier = HierarchicalTrafficClassifier(base_model_name="decision_tree", hierarchy=self.hierarchy)
        hier.fit(dev_recs, features)

        test_record = dict(dev_recs[0])
        res = hier.predict_composed_proba_single(test_record)

        self.assertIn("predicted_fine_class", res)
        self.assertIn("predicted_coarse_family", res)
        self.assertIn("final_confidence", res)
        self.assertAlmostEqual(sum(res["fine_probabilities"].values()), 1.0, places=4)

    def test_selective_prediction_states(self) -> None:
        with open(self.clean_v2_path, "r", encoding="utf-8") as f:
            dev_recs = list(csv.DictReader(f))

        features = ["forward_packet_count", "backward_packet_count", "forward_bytes", "backward_bytes"]
        hier = HierarchicalTrafficClassifier(
            base_model_name="decision_tree",
            hierarchy=self.hierarchy,
            confidence_threshold=0.70,
            min_packets=10,
        )
        hier.fit(dev_recs, features)

        # 1. Insufficient packets
        insufficient_rec = dict(dev_recs[0], forward_packet_count="2", backward_packet_count="1", total_packet_count="3")
        res1 = hier.predict_selective(insufficient_rec, packet_count=3)
        self.assertEqual(res1["status"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(res1["is_accepted"])

        # 2. Standard flow
        std_rec = dict(dev_recs[0])
        res2 = hier.predict_selective(std_rec, packet_count=50)
        self.assertIn(res2["status"], ["KNOWN_CLASS", "LOW_CONFIDENCE", "UNKNOWN"])

    def test_end_to_end_hierarchical_pipeline(self) -> None:
        pipeline = HierarchicalClassificationPipeline(
            config_path=str(self.config_path),
            clean_v2_path=str(self.clean_v2_path),
            output_dir=str(self.output_dir),
            test_session_ids_path=None,
        )
        summary = pipeline.run()

        self.assertIn("stage1_coarse_macro_f1", summary)
        self.assertIn("flat_macro_f1", summary)
        self.assertIn("hierarchical_macro_f1", summary)
        self.assertIn("selective_precision", summary)

        self.assertTrue((self.output_dir / "tables" / "hierarchy_candidates.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase8_stage1_coarse_cv.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase8_stage2_fine_cv.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "flat_vs_hierarchical.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase8_abstention_policy.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase8_open_set_detection.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "risk_coverage.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase8_calibration.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase8_cost.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase8_early_prediction.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase8_generalization.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase8_final_test.csv").exists())
        self.assertTrue((self.output_dir / "tables" / "phase_progression_hierarchical.csv").exists())
        self.assertTrue((self.output_dir / "phase8_hierarchical_report.md").exists())


if __name__ == "__main__":
    unittest.main()
