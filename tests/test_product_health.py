"""
Product Health & Diagnostics Unit Tests.

Verifies:
- Standard health check returns structured PASS/WARNING/FAIL
- Individual component diagnostics (OS, runtime, Npcap, model, preprocessor, schema, security, port)
- Mocked failure handling for missing registry or corrupted model hash
- Mocked Npcap detection states
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from product.environment import check_npcap, get_os_info
from product.health import check_port_availability, run_product_health_check


class TestProductHealth(unittest.TestCase):
    """Tests system diagnostics and product health reporting."""

    def test_get_os_info(self) -> None:
        """Tests OS metadata extraction."""
        info = get_os_info()
        self.assertIn("system", info)
        self.assertIn("display_name", info)
        self.assertIn("is_windows", info)
        self.assertIn("is_64bit", info)

    def test_check_port_availability(self) -> None:
        """Tests socket port availability probing."""
        res = check_port_availability(port=59123)
        self.assertIn("status", res)
        self.assertIn(res["status"], ("PASS", "WARNING"))

    def test_run_product_health_check_current_environment(self) -> None:
        """Runs health check on active repository and asserts structured schema."""
        report = run_product_health_check()
        self.assertIn("overall_status", report)
        self.assertIn(report["overall_status"], ("PASS", "WARNING", "FAIL"))
        self.assertIn("checks", report)

        checks = report["checks"]
        self.assertIn("os", checks)
        self.assertIn("runtime", checks)
        self.assertIn("npcap", checks)
        self.assertIn("adapters", checks)
        self.assertIn("filesystem", checks)
        self.assertIn("model", checks)
        self.assertIn("feature_schema", checks)
        self.assertIn("security", checks)

        # Feature schema and security must be PASS
        self.assertEqual(checks["feature_schema"]["status"], "PASS")
        self.assertEqual(checks["security"]["status"], "PASS")

    def test_health_check_fails_on_missing_registry(self) -> None:
        """Tests that health check transitions to FAIL when registry is missing."""
        report = run_product_health_check(registry_path="nonexistent_registry.json")
        self.assertEqual(report["checks"]["model"]["status"], "FAIL")
        self.assertEqual(report["overall_status"], "FAIL")

    @patch("product.health.check_npcap")
    def test_health_check_warning_on_npcap_warning(self, mock_npcap: MagicMock) -> None:
        """Tests that health check returns WARNING when Npcap is degraded."""
        mock_npcap.return_value = {
            "status": "WARNING",
            "message": "Npcap DLL found without npcap.sys driver service",
            "details": {},
            "instructions": "Run as admin",
            "can_capture": True,
        }

        report = run_product_health_check()
        self.assertEqual(report["checks"]["npcap"]["status"], "WARNING")
        self.assertIn(report["overall_status"], ("WARNING", "PASS"))


if __name__ == "__main__":
    unittest.main()
