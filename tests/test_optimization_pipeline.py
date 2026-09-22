import csv
import sys
import tempfile
import unittest
from pathlib import Path
import yaml

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from realtime.schema import CANONICAL_NUMERICAL_FEATURES, validate_feature_schema
from training.baseline_schema import export_baseline_feature_schema
from training.feature_ranking import compute_feature_correlations
from training.pareto_analysis import is_pareto_dominant, run_pareto_analysis
from training.realtime_compatibility import audit_realtime_compatibility


class TestOptimizationPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_baseline_schema_export(self):
        out_csv = self.base_path / "baseline_schema.csv"
        records = export_baseline_feature_schema(output_path=out_csv)
        self.assertEqual(len(records), 21)
        self.assertTrue(out_csv.exists())

    def test_feature_correlation_computation(self):
        mock_x = [
            [1.0, 10.0],
            [2.0, 20.0],
            [3.0, 30.0],
        ]
        feats = ["feat_a", "feat_b"]
        corr_rows = compute_feature_correlations(mock_x, feats)
        self.assertEqual(len(corr_rows), 2)
        # feat_a and feat_b are perfectly correlated (r = 1.0)
        self.assertAlmostEqual(corr_rows[0]["feat_b"], 1.0, places=2)

    def test_pareto_dominance_logic(self):
        # Candidate A: F1=0.90, Latency=1.0ms, Size=0.5MB
        cand_a = {"macro_f1": 0.90, "latency_ms": 1.0, "model_size_mb": 0.5}
        # Candidate B: F1=0.95, Latency=0.8ms, Size=0.4MB (Strictly better in all)
        cand_b = {"macro_f1": 0.95, "latency_ms": 0.8, "model_size_mb": 0.4}
        # Candidate C: F1=0.85, Latency=1.2ms, Size=0.6MB (Strictly worse)
        cand_c = {"macro_f1": 0.85, "latency_ms": 1.2, "model_size_mb": 0.6}

        # B dominates A
        self.assertTrue(is_pareto_dominant(cand_a, cand_b))
        # A does NOT dominate B
        self.assertFalse(is_pareto_dominant(cand_b, cand_a))
        # A dominates C
        self.assertTrue(is_pareto_dominant(cand_c, cand_a))

    def test_realtime_feature_compatibility_audit(self):
        out_csv = self.base_path / "compat.csv"
        records = audit_realtime_compatibility(output_csv=out_csv)
        self.assertEqual(len(records), 21)
        for r in records:
            self.assertEqual(r["compatible"], "YES")


if __name__ == "__main__":
    unittest.main()
