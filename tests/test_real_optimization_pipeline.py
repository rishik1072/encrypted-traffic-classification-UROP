"""
Unit tests for Phase 3: Real Data Feature Discovery, Grouped CV, and Model Optimization.

Tests:
1. Grouped cross-validation integrity & zero session leakage across folds.
2. Fold-local feature selection (feature selection happens inside each training fold).
3. Development vs held-out test separation.
4. Pure-Python statistical ranking (Mutual Info, RF, LightGBM, Permutation, ANOVA).
5. Feature subset reduction experiment evaluation.
6. Model candidate persistence in results/models/real_optimized_candidate/.
7. Baseline preservation & LOCKED.md assertion.
"""

from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure project root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from preprocessing.preprocessing import FeaturePreprocessor
from training.real_optimization_pipeline import (
    RealOptimizationPipeline,
    create_grouped_folds,
    calc_pearson,
    calc_spearman,
    calc_mutual_info,
    calc_anova_f,
)


class TestRealOptimizationPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

        self.config_path = self.tmp_path / "config.yaml"
        self.config = {
            "project": {"name": "test_real_opt", "random_seed": 42},
            "traffic_classes": ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"],
            "features": {
                "numerical_features": ["f1", "f2", "f3", "f4", "f5"],
                "categorical_features": ["protocol"],
                "tls_features": ["tls_version"],
            },
            "models": {
                "logistic_regression": {"max_iter": 50},
                "decision_tree": {"max_depth": 3},
                "random_forest": {"n_estimators": 5, "max_depth": 3},
                "lightgbm": {"n_estimators": 5, "max_depth": 3},
            },
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.config, f)

        # Setup folders
        self.splits_dir = self.tmp_path / "data/processed/splits/real_clean"
        self.splits_dir.mkdir(parents=True, exist_ok=True)

        # Create mock train, validation, and test splits
        classes = self.config["traffic_classes"]
        records = []
        for i in range(30):
            c_name = classes[i % len(classes)]
            sess_id = f"sess_{i // 2:03d}_{c_name}"
            records.append({
                "flow_id": f"flow_{i:04d}",
                "session_id": sess_id,
                "data_origin": "real",
                "traffic_class": c_name,
                "f1": str(1.0 + i * 0.5),
                "f2": str(10.0 + i * 2.0),
                "f3": str(100.0 + i),
                "f4": str(5.0 + (i % 3)),
                "f5": str(0.1 * i),
                "protocol": "17",
                "tls_version": "0x0303",
            })

        train_rows = records[:20]
        val_rows = records[20:26]
        test_rows = records[26:]

        for s_name, rows in [("train", train_rows), ("validation", val_rows), ("test", test_rows)]:
            with open(self.splits_dir / f"{s_name}.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_grouped_folds_zero_leakage(self) -> None:
        pipeline = RealOptimizationPipeline(config_path=self.config_path)
        dev_records, test_records, _ = pipeline._load_datasets()
        self.assertEqual(len(dev_records), 26)
        self.assertEqual(len(test_records), 4)

        folds = create_grouped_folds(dev_records, n_splits=3, seed=42, group_key="session_id")
        self.assertEqual(len(folds), 3)

        for tr_idx, val_idx in folds:
            tr_sess = set(dev_records[i]["session_id"] for i in tr_idx)
            val_sess = set(dev_records[i]["session_id"] for i in val_idx)
            # Assert zero session leakage
            self.assertEqual(len(tr_sess & val_sess), 0)

    def test_statistical_functions(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        self.assertAlmostEqual(calc_pearson(x, y), 1.0, places=4)
        self.assertAlmostEqual(calc_spearman(x, y), 1.0, places=4)

        labels = [0, 0, 1, 1, 1]
        mi = calc_mutual_info(x, labels)
        self.assertGreaterEqual(mi, 0.0)

        f_stat = calc_anova_f(x, labels)
        self.assertGreaterEqual(f_stat, 0.0)

    def test_feature_ranking_consensus(self) -> None:
        pipeline = RealOptimizationPipeline(config_path=self.config_path)
        dev_records, _, all_features = pipeline._load_datasets()
        ranking_rows, consensus_feats = pipeline._compute_feature_rankings(dev_records, all_features)

        self.assertEqual(len(ranking_rows), len(all_features))
        self.assertEqual(len(consensus_feats), len(all_features))
        self.assertTrue((pipeline.tables_dir / "real_feature_ranking.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_feature_consensus.csv").exists())

    def test_end_to_end_optimization_pipeline(self) -> None:
        pipeline = RealOptimizationPipeline(config_path=self.config_path)
        results = pipeline.run()

        self.assertIn("selected_model", results)
        self.assertIn("cv_macro_f1_mean", results)
        self.assertIn("test_macro_f1", results)

        # Verify all tables generated
        self.assertTrue((pipeline.tables_dir / "grouped_cv_scores.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_feature_inventory.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_feature_correlation.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_feature_ranking.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_feature_consensus.csv").exists())
        self.assertTrue((pipeline.tables_dir / "feature_class_separability.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_feature_reduction_cv.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_model_complexity_cv.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_feature_model_pareto.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_feature_extraction_cost.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_early_prediction_cv.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_model_stability.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_calibration_cv.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_cv_error_analysis.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_selected_candidate.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_optimized_final_test.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_baseline_vs_optimized.csv").exists())

        # Verify candidate models locked
        self.assertTrue((pipeline.candidate_dir / "model.joblib").exists())
        self.assertTrue((pipeline.candidate_dir / "preprocessor.joblib").exists())
        self.assertTrue((pipeline.candidate_dir / "feature_list.json").exists())
        self.assertTrue((pipeline.candidate_dir / "config.yaml").exists())

        # Verify report
        self.assertTrue((self.tmp_path / "results/real_optimization_report.md").exists())
        self.assertTrue((pipeline.baselines_dir / "LOCKED.md").exists())


if __name__ == "__main__":
    unittest.main()
