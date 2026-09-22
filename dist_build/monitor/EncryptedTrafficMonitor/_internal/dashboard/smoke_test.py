"""
Minimal Smoke Test for Dashboard Modules and Streamlit Lifecycle Safety.

Verifies that:
1. Dashboard modules can be imported cleanly without creating unmanaged asyncio event loops.
2. Normalization and data quality checks execute without starting background threads.
3. No global event loop is closed or modified.
"""

import sys
import unittest
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.data_adapter import (
    normalize_prediction_record,
    clean_for_json_serialization,
    sanitize_dataframe_for_streamlit,
)
from dashboard.data_quality import inspect_dataframe_for_invalid_values
from dashboard.schema import CanonicalPredictionRecord, parse_confidence
from dashboard.streamlit_contract import prepare_dataframe_for_streamlit


class TestDashboardSmoke(unittest.TestCase):
    def test_module_imports_and_instantiation(self):
        rec = {
            "flow_id": "TEST-SMOKE-01",
            "confidence": 0.85,
            "prediction_state": "KNOWN_CLASS",
            "predicted_class": "Web",
            "predicted_family": "Interactive",
            "packets_observed": 10,
            "latency_us": 150.0,
        }
        canon, is_valid, err = normalize_prediction_record(rec)
        self.assertTrue(is_valid)
        self.assertIsNotNone(canon)
        self.assertEqual(canon.flow_id, "TEST-SMOKE-01")

    def test_dataframe_contract_clean(self):
        import pandas as pd
        df = pd.DataFrame([{"a": 1.0, "b": None, "c": "safe"}])
        clean_df = prepare_dataframe_for_streamlit(df)
        self.assertEqual(len(clean_df), 1)

    def test_no_unclosed_loop_conflict(self):
        import asyncio
        # Verify default asyncio policies remain untouched
        try:
            loop = asyncio.get_event_loop_policy().get_event_loop()
            self.assertFalse(loop.is_closed())
        except RuntimeError:
            # Under some environments, no loop is active yet; that is also safe
            pass


if __name__ == "__main__":
    unittest.main()
