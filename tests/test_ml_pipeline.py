import sys
import tempfile
import unittest
from pathlib import Path

# Ensure project root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from preprocessing.preprocessing import FeaturePreprocessor
from training.evaluate import compute_metrics
from training.rank_models import rank_and_find_pareto_front


class TestMLPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

        self.config = {
            "traffic_classes": ["Web", "Video", "Messaging"],
            "features": {
                "numerical_features": ["f1", "f2", "f3"],
                "categorical_features": ["protocol"],
                "tls_features": ["tls_version"],
            },
            "models": {
                "logistic_regression": {"max_iter": 100},
                "decision_tree": {"max_depth": 5},
                "random_forest": {"n_estimators": 10},
            },
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_preprocessor_fitting_and_transformation(self):
        preprocessor = FeaturePreprocessor(self.config)
        train_records = [
            {"f1": "10.0", "f2": "20.0", "f3": "30.0", "traffic_class": "Web"},
            {"f1": "15.0", "f2": "25.0", "f3": "35.0", "traffic_class": "Video"},
            {"f1": "20.0", "f2": "30.0", "f3": "40.0", "traffic_class": "Messaging"},
        ]
        preprocessor.fit(train_records)
        self.assertTrue(preprocessor.is_fitted)

        # Test transform output
        x_mat = preprocessor.transform(train_records)
        self.assertEqual(len(x_mat), 3)

        # Test encoding
        y_enc = preprocessor.encode_labels(train_records)
        self.assertEqual(len(y_enc), 3)
        self.assertEqual(set(y_enc), {0, 1, 2})

        # Test decoding
        decoded = preprocessor.decode_labels(y_enc)
        self.assertEqual(decoded, ["Web", "Video", "Messaging"])

    def test_multiclass_metrics_computation(self):
        y_true = [0, 1, 2, 0, 1, 2]
        y_pred = [0, 1, 2, 0, 2, 1]  # 4 correct, 2 swapped
        class_names = ["Web", "Video", "Messaging"]

        metrics = compute_metrics(y_true, y_pred, class_names)
        self.assertAlmostEqual(metrics["accuracy"], 4 / 6, places=3)
        self.assertIn("f1_macro", metrics)
        self.assertIn("precision_weighted", metrics)
        self.assertIn("per_class", metrics)

    def test_pareto_ranking(self):
        comparison = [
            {"model": "model_A", "f1_macro": 0.95, "avg_inference_ms": 1.0, "model_size_mb": 5.0},
            {"model": "model_B", "f1_macro": 0.90, "avg_inference_ms": 0.2, "model_size_mb": 0.1},
            {"model": "model_C", "f1_macro": 0.80, "avg_inference_ms": 2.0, "model_size_mb": 10.0},  # Dominated
        ]
        ranked, pareto = rank_and_find_pareto_front(comparison)
        self.assertEqual(len(ranked), 3)
        self.assertIn("model_A", pareto)
        self.assertIn("model_B", pareto)
        self.assertNotIn("model_C", pareto)


if __name__ == "__main__":
    unittest.main()
