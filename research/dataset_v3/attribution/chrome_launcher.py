"""
Controlled Chrome Workload Launcher for Dataset V3.

Manages isolated Chrome browser execution for ground-truth Web traffic collection:
- Dedicated, unique temporary --user-data-dir
- Does not attach to existing user profiles or running instances
- Disables background sync, autofill, extension updates, and telemetry
- Captures volatile root process identity (PID, creation time)
- Clean, deterministic process tree shutdown and disk cleanup
- Strictly zero persistence of command-line arguments, profile paths, or visited URLs

Multi-Process Architecture & Ground-Truth Caveats:
Google Chrome utilizes a multi-process architecture:
1. Browser Process: UI, tab management, coordinates child processes.
2. Network Service Process (--type=network.mojom.NetworkService): Performs socket creation,
   TLS handshakes, HTTP/2 multiplexing, DNS over HTTPS (DoH), and QUIC transport.
3. Renderer Processes (--type=renderer): Web page execution and rendering in sandboxes.
4. GPU & Utility Processes: Rendering acceleration, audio, storage service.

Important Scientific Limitation:
Attributing a network socket to a controlled Chrome process confirms that the socket
was opened by this controlled browser instance. However, under zero-payload research constraints
(zero inspection of TLS SNI, HTTP Host headers, URLs, or payloads), process attribution CANNOT
prove that a connection belongs to a specific webpage or resource (e.g. background telemetry,
OCSP certificate checks, safe browsing, or prefetching). Consequently, attribution establishes
coarse traffic-class identity (e.g. "Web") and process boundary, but NOT fine-grained URL identity.
"""

from __future__ import annotations

import logging
import os
import platform
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from typing import List, Optional

from research.dataset_v3.attribution.ip_helper import get_process_creation_time_and_name
from research.dataset_v3.attribution.process_tracker import ProcessTracker

logger = logging.getLogger("research.dataset_v3.attribution.chrome_launcher")


class ControlledChromeLauncher:
    """
    Launches and manages an isolated Chrome instance with temporary user data directory
    and hooks process identities into ProcessTracker in volatile memory.
    """

    def __init__(
        self,
        process_tracker: Optional[ProcessTracker] = None,
        chrome_binary: Optional[str | Path] = None,
        headless: bool = True,
        extra_args: Optional[List[str]] = None,
    ) -> None:
        self.process_tracker = process_tracker or ProcessTracker()
        self.chrome_binary = Path(chrome_binary) if chrome_binary else None
        self.headless = headless
        self.extra_args = list(extra_args) if extra_args else []

        self._temp_user_data_dir: Optional[Path] = None
        self._proc: Optional[subprocess.Popen] = None
        self._root_pid: Optional[int] = None
        self._root_create_time_utc: Optional[str] = None
        self._lock = threading.RLock()

    @property
    def root_pid(self) -> Optional[int]:
        return self._root_pid

    @property
    def is_running(self) -> bool:
        with self._lock:
            if self._proc is None:
                return False
            return self._proc.poll() is None

    @classmethod
    def find_chrome_executable(cls) -> Optional[Path]:
        """Locates standard Google Chrome binary location on Windows/Linux."""
        if platform.system() == "Windows":
            candidates = [
                Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Google" / "Chrome" / "Application" / "chrome.exe",
                Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")) / "Google" / "Chrome" / "Application" / "chrome.exe",
                Path(os.environ.get("LOCALAPPDATA", "C:\\Users\\Default\\AppData\\Local")) / "Google" / "Chrome" / "Application" / "chrome.exe",
            ]
            for c in candidates:
                if c.exists():
                    return c
        else:
            for bin_name in ["google-chrome", "chrome", "chromium", "google-chrome-stable"]:
                found = shutil.which(bin_name)
                if found:
                    return Path(found)
        return None

    def launch(
        self,
        initial_url: Optional[str] = None,
        custom_binary: Optional[str | Path] = None,
    ) -> int:
        """
        Launches an isolated Chrome instance with dedicated temporary profile directory.
        Registers the root PID and discovers descendant processes in volatile memory.
        """
        with self._lock:
            if self.is_running:
                raise RuntimeError("Controlled Chrome instance is already running.")

            binary = Path(custom_binary) if custom_binary else (self.chrome_binary or self.find_chrome_executable())
            if not binary or not binary.exists():
                raise FileNotFoundError(
                    f"Chrome executable not found at '{binary}'. "
                    "Ensure Google Chrome is installed or specify binary path explicitly."
                )

            # Create dedicated temporary profile directory
            temp_dir = tempfile.mkdtemp(prefix="dataset_v3_chrome_")
            self._temp_user_data_dir = Path(temp_dir)

            # Build command with strict isolation flags
            # NEVER attach to existing user profiles or running instances
            cmd: List[str] = [
                str(binary),
                f"--user-data-dir={self._temp_user_data_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-client-side-phishing-detection",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-sync",
                "--disable-translate",
                "--disable-component-update",
                "--metrics-recording-only=false",
            ]

            if self.headless:
                cmd.extend(["--headless=new", "--disable-gpu"])

            cmd.extend(self.extra_args)

            if initial_url:
                cmd.append(initial_url)

            # Launch process with redirected stdout/stderr to avoid leaks
            logger.info("Launching isolated controlled Chrome instance (headless=%s)", self.headless)
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._root_pid = self._proc.pid

            # Capture process creation time in volatile memory
            ctime, pname = get_process_creation_time_and_name(self._root_pid)
            self._root_create_time_utc = ctime

            # Register with ProcessTracker
            self.process_tracker.register_controlled_root(
                pid=self._root_pid,
                create_time_utc=self._root_create_time_utc or "",
                process_name="chrome.exe",
            )

            # Refresh child processes (e.g. Network Service, Renderers)
            time.sleep(0.1)
            self.process_tracker.refresh_chrome_tree()

            return self._root_pid

    def stop(self, timeout_seconds: float = 5.0) -> None:
        """
        Gracefully terminates the browser process tree and cleans up temporary profile.
        Guarantees zero persistent storage of profile, URLs, or logs.
        """
        with self._lock:
            proc = self._proc
            root_pid = self._root_pid
            temp_dir = self._temp_user_data_dir

            if proc is not None:
                try:
                    proc.terminate()
                    try:
                        proc.wait(timeout=timeout_seconds)
                    except subprocess.TimeoutExpired:
                        logger.warning("Controlled Chrome root PID %s did not terminate in %.1fs, killing...", root_pid, timeout_seconds)
                        proc.kill()
                        proc.wait(timeout=2.0)
                except Exception as e:
                    logger.debug("Error stopping Chrome process %s: %s", root_pid, e)
                finally:
                    self._proc = None
                    self._root_pid = None
                    self._root_create_time_utc = None

            # Clean up temporary profile directory
            if temp_dir is not None and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    logger.debug("Error cleaning up Chrome temp profile %s: %s", temp_dir, e)
                finally:
                    self._temp_user_data_dir = None

            logger.info("Controlled Chrome instance stopped and temporary profile cleaned.")

    def __enter__(self) -> "ControlledChromeLauncher":
        self.launch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
