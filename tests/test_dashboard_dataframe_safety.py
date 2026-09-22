"""
Tests for Dashboard DataFrame Safety and Sanitization against NaN/Inf.
"""

import math
import unittest
import numpy as np
import pandas as pd

from dashboard.data_adapter import (
    sanitize_dataframe_for_streamlit,
    clean_for_json_serialization,
)
from dashboard.data_quality import inspect_dataframe_for_invalid_values


class TestDashboardDataFrameSafety(unittest.TestCase):
    def test_dataframe_containing_nan(self):
        df = pd.DataFrame({
            "flow_id": ["F-1", "F-2"],
            "confidence": [0.95, float("nan")],
            "latency": [np.nan, 120.5],
        })
        clean = sanitize_dataframe_for_streamlit(df)
        self.assertIsNone(clean.loc[1, "confidence"])
        self.assertIsNone(clean.loc[0, "latency"])
        self.assertEqual(clean.loc[0, "confidence"], 0.95)
        self.assertEqual(clean.loc[1, "latency"], 120.5)

    def test_dataframe_containing_pos_inf(self):
        df = pd.DataFrame({
            "flow_id": ["F-1"],
            "throughput": [float("inf")],
            "ratio": [np.inf],
        })
        clean = sanitize_dataframe_for_streamlit(df)
        self.assertIsNone(clean.loc[0, "throughput"])
        self.assertIsNone(clean.loc[0, "ratio"])

    def test_dataframe_containing_neg_inf(self):
        df = pd.DataFrame({
            "flow_id": ["F-1"],
            "score": [float("-inf")],
            "delta": [-np.inf],
        })
        clean = sanitize_dataframe_for_streamlit(df)
        self.assertIsNone(clean.loc[0, "score"])
        self.assertIsNone(clean.loc[0, "delta"])

    def test_mixed_numeric_and_string_columns(self):
        df = pd.DataFrame({
            "flow_id": ["F-001", "F-002"],
            "predicted_class": ["Messaging", "Video"],
            "confidence": [0.88, np.nan],
            "is_vpn": [True, False],
        })
        clean = sanitize_dataframe_for_streamlit(df)
        self.assertEqual(clean.loc[0, "predicted_class"], "Messaging")
        self.assertEqual(clean.loc[1, "predicted_class"], "Video")
        self.assertEqual(clean.loc[0, "confidence"], 0.88)
        self.assertIsNone(clean.loc[1, "confidence"])
        self.assertTrue(clean.loc[0, "is_vpn"])

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        clean = sanitize_dataframe_for_streamlit(df)
        self.assertTrue(clean.empty)

    def test_all_null_column(self):
        df = pd.DataFrame({
            "flow_id": ["F-1", "F-2"],
            "empty_metrics": [np.nan, np.nan],
        })
        clean = sanitize_dataframe_for_streamlit(df)
        self.assertIsNone(clean.loc[0, "empty_metrics"])
        self.assertIsNone(clean.loc[1, "empty_metrics"])

    def test_confidence_nan_and_latency_nan(self):
        df = pd.DataFrame([{
            "flow_id": "F-001",
            "confidence": float("nan"),
            "latency_us": float("nan"),
            "packets_observed": 10,
        }])
        clean = sanitize_dataframe_for_streamlit(df)
        self.assertIsNone(clean.loc[0, "confidence"])
        self.assertIsNone(clean.loc[0, "latency_us"])
        self.assertEqual(clean.loc[0, "packets_observed"], 10)

    def test_class_label_strings_preserved(self):
        labels = ["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other", "—"]
        df = pd.DataFrame({"class_label": labels})
        clean = sanitize_dataframe_for_streamlit(df)
        self.assertEqual(list(clean["class_label"]), labels)

    def test_styled_dataframe_safety(self):
        df = pd.DataFrame({
            "flow_id": ["F-1", "F-2"],
            "score": [1.0, np.nan],
        })
        clean = sanitize_dataframe_for_streamlit(df)
        # Verify Styler builds without crashing
        styler = clean.style.format(precision=2, na_rep="N/A")
        html = styler.to_html()
        self.assertIn("N/A", html)

    def test_inspector_diagnostic_counts(self):
        df = pd.DataFrame({
            "col_nan": [1.0, np.nan, 3.0],
            "col_inf": [10.0, np.inf, -np.inf],
            "col_clean": ["a", "b", "c"],
        })
        report = inspect_dataframe_for_invalid_values(df)
        self.assertEqual(report["total_invalid_count"], 3)
        self.assertEqual(report["columns"]["col_nan"]["nan_count"], 1)
        self.assertEqual(report["columns"]["col_inf"]["inf_count"], 1)
        self.assertEqual(report["columns"]["col_inf"]["neg_inf_count"], 1)
        self.assertEqual(report["columns"]["col_clean"]["total_invalid"], 0)


if __name__ == "__main__":
    unittest.main()
