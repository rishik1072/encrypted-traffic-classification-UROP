"""
Unit Tests for Streamlit DataFrame Contract & Value Normalizer.
"""

import json
import math
import unittest
import numpy as np
import pandas as pd

from dashboard.streamlit_contract import (
    prepare_dataframe_for_streamlit,
    create_safe_styler,
)
from dashboard.value_normalizer import safe_float, safe_int, is_class_label


class TestStreamlitContract(unittest.TestCase):
    def test_value_normalizer_numeric_and_strings(self):
        self.assertEqual(safe_float(123.45), 123.45)
        self.assertEqual(safe_float("45.67"), 45.67)
        self.assertEqual(safe_int("100"), 100)
        self.assertIsNone(safe_float(float("nan")))
        self.assertIsNone(safe_float(float("inf")))
        self.assertIsNone(safe_float(float("-inf")))
        self.assertIsNone(safe_float("nan"))
        self.assertIsNone(safe_float("Infinity"))
        self.assertIsNone(safe_int("nan"))
        self.assertIsNone(safe_int(np.nan))

    def test_value_normalizer_class_labels_protected(self):
        # Class labels must NEVER be converted to numeric floats/ints
        self.assertTrue(is_class_label("Messaging"))
        self.assertTrue(is_class_label("Video"))
        self.assertTrue(is_class_label("Web"))
        self.assertTrue(is_class_label("VoIP"))
        self.assertTrue(is_class_label("File Transfer"))
        self.assertTrue(is_class_label("Other"))

        self.assertIsNone(safe_float("Messaging"))
        self.assertIsNone(safe_float("Video"))
        self.assertIsNone(safe_int("Messaging"))

    def test_prepare_dataframe_no_nan_no_inf(self):
        raw_data = [
            {"flow_id": "F-001", "confidence": 0.95, "latency_us": 120.0, "status": "KNOWN_CLASS"},
            {"flow_id": "F-002", "confidence": float("nan"), "latency_us": float("inf"), "status": "UNKNOWN"},
            {"flow_id": "F-003", "confidence": np.nan, "latency_us": -np.inf, "status": "LOW_CONFIDENCE"},
        ]
        df = prepare_dataframe_for_streamlit(raw_data)
        self.assertEqual(len(df), 3)
        self.assertEqual(df.loc[0, "confidence"], 0.95)
        self.assertIsNone(df.loc[1, "confidence"])
        self.assertIsNone(df.loc[2, "confidence"])
        self.assertIsNone(df.loc[1, "latency_us"])
        self.assertIsNone(df.loc[2, "latency_us"])

        # Validate JSON serialization with allow_nan=False
        records = df.to_dict(orient="records")
        json_output = json.dumps(records, allow_nan=False)
        self.assertNotIn("NaN", json_output)
        self.assertNotIn("Infinity", json_output)
        self.assertIn('"confidence": null', json_output)

    def test_prepare_dataframe_ragged_and_none_keys(self):
        raw_data = [
            {"a": 1, "b": "ok"},
            {"a": 2, "b": None, None: ["extra_val"]},
        ]
        df = prepare_dataframe_for_streamlit(raw_data)
        self.assertIn("extra_fields", df.columns)
        self.assertIsNone(df.loc[1, "b"])
        # JSON dump must succeed
        json_output = json.dumps(df.to_dict(orient="records"), allow_nan=False)
        self.assertIn('"b": null', json_output)

    def test_create_safe_styler_no_nan(self):
        df = pd.DataFrame([
            {"flow_id": "F-01", "score": 10.5},
            {"flow_id": "F-02", "score": np.nan},
        ])
        styler = create_safe_styler(df, na_rep="N/A")
        self.assertIsNotNone(styler)
        html = styler.to_html() if hasattr(styler, "to_html") else str(styler)
        self.assertIn("N/A", html)

    def test_prepare_dataframe_empty_and_all_null(self):
        empty_df = prepare_dataframe_for_streamlit([])
        self.assertTrue(empty_df.empty)

        all_null = prepare_dataframe_for_streamlit([{"col_a": np.nan, "col_b": float("nan")}])
        self.assertIsNone(all_null.loc[0, "col_a"])
        self.assertIsNone(all_null.loc[0, "col_b"])
        json.dumps(all_null.to_dict(orient="records"), allow_nan=False)


if __name__ == "__main__":
    unittest.main()
