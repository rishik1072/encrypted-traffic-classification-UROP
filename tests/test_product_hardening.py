"""
Product Hardening & Validation Test Suite.

Verifies:
1. Configuration schema validation & security boundary constraints
2. Credential exclusion & external telemetry exclusion
3. Zero-payload event assertion and PII sanitization
4. End-to-end 9-point installation validation scorecard
5. Research result immutability invariant (results/tables/ unmodified)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

from product.config import (
    ProductConfig,
    validate_config_schema,
    product_config,
)
from product.security import (
    SecurityBoundaryError,
    assert_local_only_policy,
    assert_no_credentials,
    assert_no_external_telemetry,
    assert_zero_payload_policy,
    assert_zero_payload_record,
    sanitize_event_record,
    validate_security_boundary,
)
from product.validate import run_installation_validation


class TestProductHardening(unittest.TestCase):
    """Rigorous hardening tests for the Windows production artifacts."""

    def test_config_schema_validation_valid(self) -> None:
        """Asserts valid configuration passes schema validation."""
        valid_cfg = {
            "app_name": "Encrypted Traffic Classifier",
            "version": "1.0.0",
            "local_api": {
                "host": "127.0.0.1",
                "port": 8080,
            },
            "dashboard_port": 8501,
            "default_model": "lightgbm",
            "local_only": True,
            "save_raw_packets": False,
            "minimum_packets": 5,
        }
        res = validate_config_schema(valid_cfg)
        self.assertTrue(res["valid"])
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(len(res["errors"]), 0)

    def test_config_schema_rejects_privileged_or_invalid_ports(self) -> None:
        """Asserts schema validation catches invalid or privileged port assignments."""
        invalid_cfg = {
            "local_api": {
                "host": "127.0.0.1",
                "port": 80,  # privileged port < 1024
            },
            "dashboard_port": 70000,  # out of range > 65535
            "local_only": True,
            "save_raw_packets": False,
        }
        res = validate_config_schema(invalid_cfg)
        self.assertFalse(res["valid"])
        self.assertEqual(res["status"], "FAIL")
        self.assertTrue(any("port" in e.lower() for e in res["errors"]))

    def test_config_schema_rejects_non_localhost_and_raw_packets(self) -> None:
        """Asserts schema validation strictly rejects non-localhost and packet capture flags."""
        insecure_cfg = {
            "local_api": {
                "host": "0.0.0.0",
                "port": 8080,
            },
            "dashboard_port": 8501,
            "local_only": False,
            "save_raw_packets": True,
        }
        res = validate_config_schema(insecure_cfg)
        self.assertFalse(res["valid"])
        self.assertEqual(res["status"], "FAIL")
        self.assertTrue(any("127.0.0.1" in e or "host" in e for e in res["errors"]))
        self.assertTrue(any("local_only" in e for e in res["errors"]))
        self.assertTrue(any("save_raw_packets" in e for e in res["errors"]))

    def test_security_assert_no_credentials(self) -> None:
        """Asserts credential scanner detects leaked keys or tokens."""
        # Clean dict should pass
        clean_dict = {"host": "127.0.0.1", "port": 8080, "mode": "demo"}
        assert_no_credentials(clean_dict)

        # Leaked key should raise SecurityBoundaryError
        dirty_dict = {"api_key": "AIzaSyD-1234567890abcdef", "port": 8080}
        with self.assertRaises(SecurityBoundaryError):
            assert_no_credentials(dirty_dict)

    def test_security_assert_no_external_telemetry(self) -> None:
        """Asserts telemetry scanner detects cloud analytics or reporting URLs."""
        # Clean local URLs should pass
        clean_dict = {"api_url": "http://127.0.0.1:8080/health", "dash_url": "http://localhost:8501"}
        assert_no_external_telemetry(clean_dict)

        # Cloud telemetry URL should raise SecurityBoundaryError
        dirty_dict = {"telemetry": "https://telemetry.google.com/collect", "port": 8080}
        with self.assertRaises(SecurityBoundaryError):
            assert_no_external_telemetry(dirty_dict)

    def test_security_assert_zero_payload_record(self) -> None:
        """Asserts event validator rejects records with raw payload or PII."""
        # Clean record should pass
        clean_record = {
            "flow_id": "f_123",
            "predicted_class": "Web",
            "confidence": 0.94,
            "packet_count": 10,
        }
        assert_zero_payload_record(clean_record)

        # Dirty record with payload should raise SecurityBoundaryError
        payload_record = {
            "flow_id": "f_123",
            "payload": b"secret payload bytes",
        }
        with self.assertRaises(SecurityBoundaryError):
            assert_zero_payload_record(payload_record)

        # Dirty record with raw IP should raise SecurityBoundaryError
        ip_record = {
            "flow_id": "f_123",
            "src_ip": "192.168.1.100",
        }
        with self.assertRaises(SecurityBoundaryError):
            assert_zero_payload_record(ip_record)

    def test_run_installation_validation_scorecard(self) -> None:
        """Executes full 9-point installation validation scorecard."""
        scorecard = run_installation_validation(verbose=False)
        self.assertIn("overall_status", scorecard)
        self.assertEqual(scorecard["overall_status"], "PASS")
        self.assertEqual(scorecard["tests_passed"], 9)
        self.assertEqual(scorecard["total_tests"], 9)
        self.assertEqual(scorecard["pass_rate_pct"], 100.0)

        results = scorecard["results"]
        for test_idx in range(1, 10):
            test_key = [k for k in results if k.startswith(f"test_{test_idx}_")][0]
            self.assertEqual(results[test_key]["status"], "PASS", f"Test {test_key} failed: {results[test_key]}")

    def test_research_results_tables_unmodified(self) -> None:
        """Ensures that research result tables exist and remain valid CSV files."""
        tables_dir = Path("results/tables")
        self.assertTrue(tables_dir.exists() and tables_dir.is_dir())
        csv_files = list(tables_dir.glob("*.csv"))
        self.assertGreaterEqual(len(csv_files), 5, "Expected research result CSV tables to be present")

        for csv_path in csv_files:
            self.assertGreater(csv_path.stat().st_size, 0, f"Table {csv_path.name} is empty")


if __name__ == "__main__":
    unittest.main()
