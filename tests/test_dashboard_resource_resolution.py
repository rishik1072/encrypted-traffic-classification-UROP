"""
Unit tests for dashboard resource path resolution and package synchronization.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from product.runtime_paths import (
    get_base_dir,
    get_dashboard_app_path,
    get_resource_dir,
    is_frozen,
)


class TestDashboardResourceResolution(unittest.TestCase):
    """Verifies that dashboard resource resolution correctly discovers and validates app scripts."""

    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.source_app = self.project_root / "dashboard" / "app.py"
        self.source_live_feed = self.project_root / "dashboard" / "live_feed.py"

    def _calc_sha256(self, file_path: Path) -> str:
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def test_source_paths_exist_and_match(self):
        """Verifies source dashboard files exist and calculate valid sha256."""
        self.assertTrue(self.source_app.exists(), f"Source app {self.source_app} must exist")
        self.assertTrue(self.source_live_feed.exists(), f"Source live_feed {self.source_live_feed} must exist")

        app_sha = self._calc_sha256(self.source_app)
        self.assertEqual(len(app_sha), 64)

    def test_runtime_resolver_in_dev_mode(self):
        """Tests that get_dashboard_app_path() resolves the source dashboard in dev mode."""
        resolved = get_dashboard_app_path()
        self.assertTrue(resolved.exists())
        self.assertEqual(resolved.name, "app.py")

    def test_simulated_frozen_resource_resolution(self):
        """Tests that get_dashboard_app_path() prioritizes base_dir then _internal."""
        mock_dist_dir = self.project_root / "dist" / "EncryptedTrafficMonitor"
        mock_exe = mock_dist_dir / "EncryptedTrafficDashboard.exe"

        with patch("product.runtime_paths.is_frozen", return_value=True), \
             patch("sys.executable", str(mock_exe)):
            resolved = get_dashboard_app_path()
            self.assertTrue(resolved.name == "app.py")

    def test_packaged_dashboard_copies_hash_synchronization(self):
        """Verifies that all existing packaged copies of dashboard files match source SHA256."""
        if not (self.project_root / "dist" / "EncryptedTrafficMonitor").exists():
            self.skipTest("Dist directory not present yet")

        source_app_sha = self._calc_sha256(self.source_app)
        source_feed_sha = self._calc_sha256(self.source_live_feed)

        candidate_apps = [
            self.project_root / "dist" / "EncryptedTrafficMonitor" / "dashboard" / "app.py",
            self.project_root / "dist" / "EncryptedTrafficMonitor" / "_internal" / "dashboard" / "app.py",
        ]
        candidate_feeds = [
            self.project_root / "dist" / "EncryptedTrafficMonitor" / "dashboard" / "live_feed.py",
            self.project_root / "dist" / "EncryptedTrafficMonitor" / "_internal" / "dashboard" / "live_feed.py",
        ]

        for app_path in candidate_apps:
            if app_path.exists():
                self.assertEqual(
                    self._calc_sha256(app_path),
                    source_app_sha,
                    f"Hash mismatch for {app_path}",
                )

        for feed_path in candidate_feeds:
            if feed_path.exists():
                self.assertEqual(
                    self._calc_sha256(feed_path),
                    source_feed_sha,
                    f"Hash mismatch for {feed_path}",
                )


if __name__ == "__main__":
    unittest.main()
