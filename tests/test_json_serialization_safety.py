"""
Tests for JSON Serialization Safety against NaN/Inf.
"""

import json
import math
import unittest

from dashboard.data_adapter import clean_for_json_serialization


class TestJsonSerializationSafety(unittest.TestCase):
    def test_json_dumps_allow_nan_false_with_nones(self):
        record = {
            "name": None,
            "confidence": None,
            "latency_us": 123.4,
        }
        # Must succeed without throwing ValueError
        serialized = json.dumps(record, allow_nan=False)
        self.assertIn('"confidence": null', serialized)
        self.assertIn('"name": null', serialized)

    def test_clean_for_json_serialization_converts_nan_and_inf(self):
        record = {
            "name": "flow_01",
            "confidence": float("nan"),
            "inf_stat": float("inf"),
            "neg_inf_stat": float("-inf"),
            "nested": {
                "metric_nan": float("nan"),
                "clean_val": 42.0,
            },
            "list_values": [1.0, float("nan"), float("inf"), "safe_str"],
        }
        cleaned = clean_for_json_serialization(record)
        self.assertIsNone(cleaned["confidence"])
        self.assertIsNone(cleaned["inf_stat"])
        self.assertIsNone(cleaned["neg_inf_stat"])
        self.assertIsNone(cleaned["nested"]["metric_nan"])
        self.assertEqual(cleaned["nested"]["clean_val"], 42.0)
        self.assertEqual(cleaned["list_values"], [1.0, None, None, "safe_str"])

        # Strict JSON dump must now succeed with allow_nan=False
        serialized = json.dumps(cleaned, allow_nan=False)
        self.assertNotIn("NaN", serialized)
        self.assertNotIn("Infinity", serialized)
        self.assertIn('"confidence": null', serialized)


if __name__ == "__main__":
    unittest.main()
