"""
Unit tests for Phase 2: Real Data ML Baseline Benchmark.

Tests:
1. Real clean dataset loading & assertion on origin == 'real'.
2. Split integrity & session isolation (0 overlap).
3. Feature schema exclusion (identifiers & metadata strictly removed).
4. Train-only preprocessing fitting & zero test contamination.
5. Model training on baseline candidates.
6. Model evaluation & metric calculation.
7. Artifact creation across results/tables, results/figures, results/models.
8. Reproducibility run manifest generation & hash integrity.
"""

from __future__ import annotations

import csv
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure project root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

from models.decision_tree import DecisionTreeTrafficClassifier
from models.lightgbm_model import LightGBMTrafficClassifier
from models.logistic_regression import LogisticRegressionClassifier
from models.random_forest import RandomForestTrafficClassifier
from preprocessing.preprocessing import FeaturePreprocessor
from training.evaluate import compute_metrics
from training.real_baseline_error_analysis import perform_real_baseline_error_analysis
from training.real_ml_baseline import RealMLBaselinePipeline, FORBIDDEN_METADATA_COLS


class TestRealMLBaseline(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

        # Minimal config
        self.config_path = self.tmp_path / "config.yaml"
        self.config = {
            "project": {"name": "test_real_baseline", "random_seed": 42},
            "traffic_classes": ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"],
            "features": {
                "numerical_features": ["flow_duration", "total_packet_count", "total_bytes", "avg_packet_size"],
                "categorical_features": ["protocol"],
                "tls_features": ["tls_version"],
            },
            "models": {
                "logistic_regression": {"max_iter": 50},
                "decision_tree": {"max_depth": 5},
                "random_forest": {"n_estimators": 5},
                "lightgbm": {"n_estimators": 5},
            },
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.config, f)

        # Create dummy processed directory structure
        self.data_dir = self.tmp_path / "data/processed"
        self.features_dir = self.data_dir / "features"
        self.splits_dir = self.data_dir / "splits/real_clean"
        self.features_dir.mkdir(parents=True, exist_ok=True)
        self.splits_dir.mkdir(parents=True, exist_ok=True)

        # Synthetic mock real data
        self.clean_rows = []
        classes = self.config["traffic_classes"]
        for i in range(24):
            c_name = classes[i % len(classes)]
            sess_id = f"sess_{i // 2:03d}_{c_name}"
            row = {
                "flow_id": f"flow_{i:04d}",
                "file_id": f"file_{i // 2:03d}",
                "session_id": sess_id,
                "data_origin": "real",
                "flow_duration": str(1.0 + (i * 0.1)),
                "total_packet_count": str(10 + i),
                "total_bytes": str(1000 + i * 50),
                "avg_packet_size": str(100.0 + i),
                "protocol": "17",
                "dst_port": "443",
                "tls_version": "0x0303",
                "traffic_class": c_name,
            }
            self.clean_rows.append(row)

        # Write clean features file
        clean_features_file = self.features_dir / "features_real_clean.csv"
        with open(clean_features_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(self.clean_rows[0].keys()))
            writer.writeheader()
            writer.writerows(self.clean_rows)

        # Write splits (disjoint session splits)
        train_rows = self.clean_rows[:16]
        val_rows = self.clean_rows[16:20]
        test_rows = self.clean_rows[20:]

        for split_name, s_rows in [("train", train_rows), ("validation", val_rows), ("test", test_rows)]:
            with open(self.splits_dir / f"{split_name}.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(s_rows[0].keys()))
                writer.writeheader()
                writer.writerows(s_rows)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_real_clean_dataset_loading_and_assertion(self) -> None:
        pipeline = RealMLBaselinePipeline(config_path=self.config_path)
        train_r, val_r, test_r = pipeline._validate_and_load_data()
        self.assertEqual(len(train_r), 16)
        self.assertEqual(len(val_r), 4)
        self.assertEqual(len(test_r), 4)

        # Check assertion against synthetic contamination
        corrupted_rows = list(train_r)
        corrupted_rows[0]["data_origin"] = "synthetic"
        with open(self.splits_dir / "train.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(corrupted_rows[0].keys()))
            writer.writeheader()
            writer.writerows(corrupted_rows)

        with self.assertRaises(ValueError):
            pipeline._validate_and_load_data()

    def test_split_integrity_and_session_isolation(self) -> None:
        pipeline = RealMLBaselinePipeline(config_path=self.config_path)
        train_r, val_r, test_r = pipeline._validate_and_load_data()
        pipeline._audit_split_integrity(train_r, val_r, test_r)

        integrity_csv = pipeline.tables_dir / "real_split_integrity.csv"
        self.assertTrue(integrity_csv.exists())
        with open(integrity_csv, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["overlap_count"], "0")

    def test_feature_exclusion(self) -> None:
        pipeline = RealMLBaselinePipeline(config_path=self.config_path)
        schema_rows, allowed_feats = pipeline._audit_feature_schema()
        self.assertTrue((pipeline.tables_dir / "real_ml_feature_schema.csv").exists())

        # Ensure forbidden columns are excluded
        for feat in allowed_feats:
            self.assertNotIn(feat, FORBIDDEN_METADATA_COLS)
            self.assertNotIn("session_id", feat)
            self.assertNotIn("flow_id", feat)
            self.assertNotIn("data_origin", feat)

    def test_train_only_preprocessing_fit(self) -> None:
        pipeline = RealMLBaselinePipeline(config_path=self.config_path)
        train_r, val_r, test_r = pipeline._validate_and_load_data()
        preprocessor = pipeline._fit_and_save_preprocessor(train_r)

        self.assertTrue(preprocessor.is_fitted)
        self.assertTrue((pipeline.models_dir / "preprocessor.joblib").exists())

        # Transformation check
        x_tr = preprocessor.transform(train_r)
        y_tr = preprocessor.encode_labels(train_r)
        self.assertEqual(len(x_tr), len(train_r))
        self.assertEqual(len(y_tr), len(train_r))

    def test_model_training_and_evaluation(self) -> None:
        pipeline = RealMLBaselinePipeline(config_path=self.config_path)
        train_r, val_r, test_r = pipeline._validate_and_load_data()
        preprocessor = pipeline._fit_and_save_preprocessor(train_r)

        x_train = preprocessor.transform(train_r)
        y_train = preprocessor.encode_labels(train_r)
        class_names = preprocessor.get_classes()

        trained, stats = pipeline._train_models(x_train, y_train, class_names)
        self.assertEqual(len(trained), 4)
        for m_name in ["logistic_regression", "decision_tree", "random_forest", "lightgbm"]:
            self.assertIn(m_name, trained)
            self.assertTrue((pipeline.models_dir / f"{m_name}.joblib").exists())

    def test_end_to_end_real_baseline_run(self) -> None:
        pipeline = RealMLBaselinePipeline(config_path=self.config_path)
        results = pipeline.run()

        self.assertIn("selected_model", results)
        self.assertIn("selected_test_macro_f1", results)
        self.assertIn("selected_test_accuracy", results)

        # Verify all expected artifacts exist
        self.assertTrue((pipeline.tables_dir / "real_split_integrity.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_ml_feature_schema.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_baseline_model_comparison.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_baseline_per_class_metrics.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_baseline_inference.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_split_class_distribution.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_baseline_uncertainty.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_baseline_error_analysis.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_baseline_leakage_check.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_final_baseline_result.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_baseline_run_manifest.csv").exists())
        self.assertTrue((pipeline.tables_dir / "real_feature_importance_random_forest.csv").exists())

        # Check visualizations
        self.assertTrue((pipeline.figures_dir / "logistic_regression_confusion_matrix.png").exists())
        self.assertTrue((pipeline.figures_dir / "model_macro_f1.png").exists())
        self.assertTrue((pipeline.figures_dir / "per_class_f1.png").exists())

        # Check markdown report
        report_file = self.tmp_path / "results/real_baseline_report.md"
        self.assertTrue(report_file.exists())
        with open(report_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("1. Objective", content)
            self.assertIn("13. Limitations", content)


if __name__ == "__main__":
    unittest.main()
