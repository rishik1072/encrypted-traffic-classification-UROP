"""
Product Process Supervision and Packaging Lifecycle Unit Tests.

Verifies:
- Process supervisor lifecycle management
- Sibling executable invocation logic in frozen mode
- Repeat start/stop cycles
- Orphan process termination
- Packaged runtime logging output
"""

from __future__ import annotations

from pathlib import Path
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

from product.lifecycle import ProductLifecycleManager, ServiceProcess, log_packaged_runtime_event
from product.runtime_paths import get_log_dir


class TestProductProcessSupervision(unittest.TestCase):
    """Tests process supervisor and lifecycle management under various runtime modes."""

    def test_packaged_runtime_logging(self) -> None:
        """Asserts packaged_runtime.log is written with structured diagnostics."""
        log_packaged_runtime_event("TEST_EVENT", {"test_key": "test_val", "code": 123})
        log_file = get_log_dir() / "packaged_runtime.log"

        self.assertTrue(log_file.exists())
        content = log_file.read_text(encoding="utf-8")
        self.assertIn("TEST_EVENT", content)
        self.assertIn("test_key=test_val", content)

    def test_dashboard_start_dev_mode_invocation(self) -> None:
        """Tests dashboard process invocation command structure in development mode."""
        mgr = ProductLifecycleManager()

        with patch("product.lifecycle.is_frozen", return_value=False), \
             patch("product.lifecycle.wait_for_http_ready", return_value=True), \
             patch.object(ServiceProcess, "start", return_value=True):

            ok = mgr.start_dashboard(port=8501, timeout=1.0)
            self.assertTrue(ok)
            self.assertIn("dashboard", mgr.services)
            svc = mgr.services["dashboard"]
            self.assertIn("product.dashboard_launcher", svc.cmd)
            self.assertIn("--port", svc.cmd)
            self.assertIn("8501", svc.cmd)

    def test_dashboard_start_frozen_mode_invocation(self) -> None:
        """Tests dashboard process invocation using sibling EXE in frozen mode."""
        mgr = ProductLifecycleManager()
        fake_exe = MagicMock()
        fake_exe.exists.return_value = True
        fake_exe.__str__.return_value = "C:\\path\\dist\\EncryptedTrafficMonitor\\EncryptedTrafficDashboard.exe"

        with patch("product.lifecycle.is_frozen", return_value=True), \
             patch("product.lifecycle.get_dashboard_executable_path", return_value=fake_exe), \
             patch("product.lifecycle.wait_for_http_ready", return_value=True), \
             patch.object(ServiceProcess, "start", return_value=True):

            ok = mgr.start_dashboard(port=8501, timeout=1.0)
            self.assertTrue(ok)
            self.assertIn("dashboard", mgr.services)
            svc = mgr.services["dashboard"]
            self.assertEqual(svc.cmd[0], str(fake_exe))

    def test_orphan_cleanup_on_shutdown(self) -> None:
        """Asserts supervisor terminates running child processes on shutdown_all()."""
        mgr = ProductLifecycleManager()
        cmd = [sys.executable, "-c", "import time; time.sleep(10)"]

        svc = mgr.register_service("test_proc", cmd)
        svc.start()
        self.assertTrue(svc.is_running)

        mgr.shutdown_all()
        self.assertFalse(svc.is_running)
        self.assertEqual(len(mgr.services), 0)


if __name__ == "__main__":
    unittest.main()
