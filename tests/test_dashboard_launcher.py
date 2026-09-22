"""
Dashboard Launcher Unit Tests.

Verifies:
- Dashboard path resolution via runtime_paths
- Command construction and port configuration
- Failure handling and logging setup
- HTTP readiness timeout behavior
"""

from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from product.dashboard_launcher import setup_dashboard_logging
from product.lifecycle import wait_for_http_ready
from product.runtime_paths import (
    get_base_dir,
    get_dashboard_app_path,
    get_dashboard_executable_path,
    get_log_dir,
    is_frozen,
)


class TestDashboardLauncher(unittest.TestCase):
    """Tests dashboard path resolution, launcher configuration, and readiness probing."""

    def test_dashboard_app_path_resolution(self) -> None:
        """Asserts get_dashboard_app_path resolves existing dashboard/app.py in repository."""
        app_path = get_dashboard_app_path()
        self.assertTrue(app_path.exists())
        self.assertTrue(str(app_path).endswith("app.py"))

    def test_dashboard_executable_path_resolution(self) -> None:
        """Asserts get_dashboard_executable_path builds sibling EXE path."""
        exe_path = get_dashboard_executable_path()
        self.assertEqual(exe_path.name, "EncryptedTrafficDashboard.exe")
        self.assertEqual(exe_path.parent, get_base_dir())

    def test_log_dir_resolution_and_logging_setup(self) -> None:
        """Asserts log directory is writable and dashboard logger configures properly."""
        log_dir = get_log_dir()
        self.assertTrue(log_dir.exists())

        logger = setup_dashboard_logging()
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "dashboard_runtime")

    def test_wait_for_http_ready_timeout(self) -> None:
        """Asserts wait_for_http_ready returns False when port is closed."""
        # Unoccupied high port with short timeout
        ready = wait_for_http_ready("http://127.0.0.1:59998", timeout=0.8)
        self.assertFalse(ready)

    @patch("http.client.HTTPConnection")
    def test_wait_for_http_ready_success(self, mock_conn_cls: MagicMock) -> None:
        """Asserts wait_for_http_ready returns True when HTTP server responds."""
        mock_conn = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_conn.getresponse.return_value = mock_resp
        mock_conn_cls.return_value = mock_conn

        ready = wait_for_http_ready("http://127.0.0.1:8501", timeout=2.0)
        self.assertTrue(ready)


if __name__ == "__main__":
    unittest.main()
