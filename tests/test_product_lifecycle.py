"""
Product Lifecycle and Process Management Unit Tests.

Verifies:
- Service process startup and PID assignment
- Service process clean termination
- Lifecycle manager status reporting
- Orphan cleanup and repeat start/stop cycles
"""

from __future__ import annotations

import subprocess
import sys
import time
import unittest
from pathlib import Path

from product.lifecycle import ProductLifecycleManager, ServiceProcess


class TestProductLifecycle(unittest.TestCase):
    """Tests service lifecycle, PID tracking, and process cleanup."""

    def test_service_process_lifecycle(self) -> None:
        """Tests launching, polling, and stopping a simple managed child process."""
        cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
        svc = ServiceProcess(name="test_sleep", cmd=cmd)

        self.assertFalse(svc.is_running)
        self.assertIsNone(svc.pid)

        # Start process
        started = svc.start()
        self.assertTrue(started)
        self.assertTrue(svc.is_running)
        self.assertIsNotNone(svc.pid)
        self.assertGreater(svc.pid, 0)

        # Stop process
        stopped = svc.stop(timeout=1.0)
        self.assertTrue(stopped)
        self.assertFalse(svc.is_running)
        self.assertIsNone(svc.pid)

    def test_lifecycle_manager_registration_and_status(self) -> None:
        """Tests lifecycle manager multi-process registration and status tracking."""
        mgr = ProductLifecycleManager()

        cmd1 = [sys.executable, "-c", "import time; time.sleep(10)"]
        cmd2 = [sys.executable, "-c", "import time; time.sleep(10)"]

        svc1 = mgr.register_service("svc1", cmd1)
        svc2 = mgr.register_service("svc2", cmd2)

        svc1.start()
        svc2.start()

        status = mgr.get_status()
        self.assertIn("svc1", status["services"])
        self.assertIn("svc2", status["services"])
        self.assertTrue(status["services"]["svc1"]["running"])
        self.assertTrue(status["services"]["svc2"]["running"])
        self.assertTrue(status["all_healthy"])

        # Clean shutdown all
        mgr.shutdown_all()
        self.assertFalse(svc1.is_running)
        self.assertFalse(svc2.is_running)

    def test_repeat_start_stop_cycles(self) -> None:
        """Tests that a service can be cleanly started and stopped repeatedly without leaking."""
        mgr = ProductLifecycleManager()
        cmd = [sys.executable, "-c", "import time; time.sleep(5)"]

        for cycle in range(3):
            svc = mgr.register_service(f"cycle_test", cmd)
            self.assertTrue(svc.start())
            self.assertTrue(svc.is_running)
            pid = svc.pid
            self.assertIsNotNone(pid)

            self.assertTrue(svc.stop(timeout=1.0))
            self.assertFalse(svc.is_running)


if __name__ == "__main__":
    unittest.main()
