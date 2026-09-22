"""
Unit Test Suite for Early Encrypted-Traffic Classification Study (EXP-R12).

Verifies:
1. Prefix extraction invariants (packet bounds, no future packet lookahead).
2. Missing-evidence handling (no forced imputation on incomplete flows).
3. Group-aware session isolation (zero session leakage).
4. Physical latency decomposition (Total Latency >= Observation Delay).
5. Output table schema, required columns, and metric bounds.
6. Generated figures existence and file integrity.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from experiments.research_early_prediction.run import (
    CANONICAL_21_FEATURES,
    OBSERVATION_POINTS,
    EarlyPredictionStudy,
)
from flows.flow_generator import Direction, Flow, FlowKey
from preprocessing.feature_extractor import FeatureExtractor


class TestEarlyPredictionStudy(unittest.TestCase):
    """Test suite for research early prediction protocol."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parent.parent
        cls.flows_path = cls.project_root / "data" / "processed" / "flows" / "flows_real_clean.csv"
        cls.splits_dir = cls.project_root / "data" / "processed" / "splits" / "real_clean"
        cls.tables_dir = cls.project_root / "results" / "tables"
        cls.figures_dir = cls.project_root / "results" / "figures"
        cls.results_csv = cls.tables_dir / "research_early_prediction.csv"

    def test_prefix_extraction_packet_bounds(self) -> None:
        """Verifies that flows with fewer than N packets are strictly excluded."""
        study = EarlyPredictionStudy()
        dummy_flows = [
            {
                "flow_id": "short_flow_4pkts",
                "traffic_class": "Web",
                "initiator_port": 5000,
                "port_b": 443,
                "protocol": "TCP",
                "packet_timestamps_json": json.dumps([100.0, 100.1, 100.2, 100.3]),
                "packet_lengths_json": json.dumps([100, 200, 300, 400]),
                "packet_directions_json": json.dumps(["FORWARD", "FORWARD", "BACKWARD", "FORWARD"]),
            }
        ]

        # Should succeed for N=3
        feats_3, labels_3, obs_3, _ = study.extract_prefix_features(dummy_flows, 3)
        self.assertEqual(len(feats_3), 1)
        self.assertEqual(feats_3[0]["total_packet_count"], 3)
        self.assertAlmostEqual(obs_3[0], 200.0, delta=1.0)  # (100.2 - 100.0) * 1000 = 200ms

        # Must NOT force flow into N=5 or N=10
        feats_5, labels_5, _, _ = study.extract_prefix_features(dummy_flows, 5)
        self.assertEqual(len(feats_5), 0, "Flow with 4 pkts was illegally forced into N=5!")

        feats_10, labels_10, _, _ = study.extract_prefix_features(dummy_flows, 10)
        self.assertEqual(len(feats_10), 0, "Flow with 4 pkts was illegally forced into N=10!")

    def test_prefix_no_lookahead(self) -> None:
        """Verifies no future packet information leaks into prefix features."""
        study = EarlyPredictionStudy()
        # Create 10-packet flow where packets 0..4 have size 100, and packets 5..9 have size 1500
        timestamps = [100.0 + (i * 0.1) for i in range(10)]
        lengths = [100] * 5 + [1500] * 5
        directions = ["FORWARD"] * 10

        flow_record = [
            {
                "flow_id": "lookahead_test_flow",
                "traffic_class": "Video",
                "initiator_port": 5000,
                "port_b": 443,
                "protocol": "TCP",
                "packet_timestamps_json": json.dumps(timestamps),
                "packet_lengths_json": json.dumps(lengths),
                "packet_directions_json": json.dumps(directions),
            }
        ]

        feats_5, _, _, _ = study.extract_prefix_features(flow_record, 5)
        self.assertEqual(len(feats_5), 1)
        # Sliced features at N=5 must see only sizes of 100 bytes
        self.assertEqual(feats_5[0]["max_packet_size"], 100.0)
        self.assertEqual(feats_5[0]["avg_packet_size"], 100.0)
        self.assertEqual(feats_5[0]["total_packet_count"], 5)
        self.assertAlmostEqual(feats_5[0]["flow_duration"], 0.4, delta=0.01)

    def test_group_aware_split_isolation(self) -> None:
        """Verifies strict session isolation across Train, Val, and Test splits."""
        study = EarlyPredictionStudy(flows_path=str(self.flows_path), splits_dir=str(self.splits_dir))
        _, tr_flows, val_flows, te_flows = study.load_flows_and_splits()

        tr_sessions = {r["session_id"] for r in tr_flows}
        val_sessions = {r["session_id"] for r in val_flows}
        te_sessions = {r["session_id"] for r in te_flows}

        self.assertEqual(len(tr_sessions & val_sessions), 0, "Session leakage between Train and Val!")
        self.assertEqual(len(tr_sessions & te_sessions), 0, "Session leakage between Train and Test!")
        self.assertEqual(len(val_sessions & te_sessions), 0, "Session leakage between Val and Test!")

    def test_results_csv_structure_and_metrics(self) -> None:
        """Verifies that research_early_prediction.csv exists and satisfies all required metrics."""
        self.assertTrue(self.results_csv.exists(), f"Missing result table: {self.results_csv}")
        df = pd.read_csv(self.results_csv)

        # Check required observation points
        required_obs = ["3 packets", "5 packets", "10 packets", "20 packets", "30 packets", "50 packets", "full flow"]
        self.assertEqual(df["observation_point"].tolist(), required_obs)

        # Check required columns per user request
        required_cols = [
            "observation_point",
            "packet_horizon",
            "is_full_flow",
            "coverage",
            "accuracy",
            "macro_precision",
            "macro_recall",
            "macro_f1",
            "balanced_accuracy",
            "average_confidence",
            "median_latency_ms",
            "p95_latency_ms",
            "median_observation_delay_ms",
            "p95_observation_delay_ms",
            "feature_extraction_latency_ms",
            "inference_latency_ms",
            "decision_threshold",
        ]
        for col in required_cols:
            self.assertIn(col, df.columns, f"Required column {col} missing from CSV table!")

        # Metric value bounds
        for _, row in df.iterrows():
            self.assertGreaterEqual(row["coverage"], 0.0)
            self.assertLessEqual(row["coverage"], 1.0)
            self.assertGreaterEqual(row["accuracy"], 0.0)
            self.assertLessEqual(row["accuracy"], 1.0)
            self.assertGreaterEqual(row["macro_f1"], 0.0)
            self.assertLessEqual(row["macro_f1"], 1.0)
            self.assertGreaterEqual(row["average_confidence"], 0.0)
            self.assertLessEqual(row["average_confidence"], 1.0)

            # End-to-end latency must be greater than observation delay alone
            self.assertGreater(
                row["median_latency_ms"],
                row["median_observation_delay_ms"],
                "Total latency must exceed observation delay by extraction + inference overhead!",
            )

    def test_partial_vs_full_flow_demarcation(self) -> None:
        """Verifies clear distinction between partial flow prediction and retrospective full flow."""
        df = pd.read_csv(self.results_csv)

        partial_rows = df[~df["is_full_flow"]]
        full_rows = df[df["is_full_flow"]]

        self.assertEqual(len(partial_rows), 6)
        self.assertEqual(len(full_rows), 1)

        # Full flow observation delay must be orders of magnitude larger than N=3 or N=5
        full_obs = full_rows["median_observation_delay_ms"].values[0]
        n3_obs = df[df["packet_horizon"] == "3"]["median_observation_delay_ms"].values[0]
        self.assertGreater(full_obs, 50000.0, "Full flow observation delay should be ~60 seconds!")
        self.assertLess(n3_obs, 200.0, "N=3 observation delay should be < 200 ms!")

    def test_generated_figures_exist(self) -> None:
        """Verifies that all 3 requested research figures were generated."""
        fig_names = [
            "early_prediction_f1_vs_packets.png",
            "early_prediction_coverage_vs_packets.png",
            "early_prediction_latency_vs_packets.png",
        ]
        for name in fig_names:
            fig_path = self.figures_dir / name
            self.assertTrue(fig_path.exists(), f"Missing required figure: {fig_path}")
            self.assertGreater(fig_path.stat().st_size, 10000, f"Figure file too small: {fig_path}")


if __name__ == "__main__":
    unittest.main()
