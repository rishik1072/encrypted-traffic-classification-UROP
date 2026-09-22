import sys
import unittest
from pathlib import Path

# Ensure project root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestModels(unittest.TestCase):
    def test_models_fit_and_predict(self):
        try:
            import numpy as np
            from models.decision_tree import DecisionTreeTrafficClassifier
            from models.logistic_regression import LogisticRegressionClassifier
            from models.random_forest import RandomForestTrafficClassifier
        except ImportError:
            self.skipTest("NumPy / Scikit-learn not installed in current environment.")

        np.random.seed(42)
        x_train = np.random.randn(20, 5)
        y_train = np.random.choice([0, 1, 2], size=20)
        x_test = np.random.randn(5, 5)

        classifiers = [
            LogisticRegressionClassifier(),
            DecisionTreeTrafficClassifier(),
            RandomForestTrafficClassifier(),
        ]

        for clf in classifiers:
            clf.fit(x_train, y_train)
            preds = clf.predict(x_test)
            self.assertEqual(len(preds), 5)
            probs = clf.predict_proba(x_test)
            if hasattr(probs, "shape"):
                self.assertEqual(probs.shape, (5, 3))
            else:
                self.assertEqual(len(probs), 5)
                self.assertEqual(len(probs[0]), 3)


if __name__ == "__main__":
    unittest.main()
