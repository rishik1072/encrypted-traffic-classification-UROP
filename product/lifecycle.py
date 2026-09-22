"""
Service Lifecycle and Subprocess Manager for Encrypted Traffic Monitor.

Supervises the Real-Time Classification Engine and the Streamlit SOC Dashboard.
Supports frozen split-executable invocation (EncryptedTrafficDashboard.exe) and dev mode,
handles HTTP readiness probing on port 8501, tracks PIDs, and guarantees clean orphan-free shutdowns.
"""

from __future__ import annotations

import atexit
from datetime import datetime
import http.client
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from product.config import product_config
from product.runtime_paths import (
    get_base_dir,
    get_dashboard_executable_path,
    get_log_dir,
    is_frozen,
)

logger = logging.getLogger(__name__)


def log_packaged_runtime_event(event_type: str, details: Dict[str, Any]) -> None:
    """Writes structured lifecycle diagnostics to data/local/logs/packaged_runtime.log."""
    try:
        log_file = get_log_dir() / "packaged_runtime.log"
        entry = {
            "timestamp": datetime.now().isoformat(),
            "main_pid": os.getpid(),
            "event_type": event_type,
            "working_directory": str(get_base_dir()),
            "frozen": is_frozen(),
            **details,
        }
        with open(log_file, "a", encoding="utf-8") as f:
            formatted_details = " | ".join(f"{k}={v}" for k, v in entry.items())
            f.write(formatted_details + "\n")
    except Exception as e:
        logger.debug("Failed to write to packaged_runtime.log: %s", e)


def wait_for_http_ready(url: str = "http://127.0.0.1:8501", timeout: float = 30.0) -> bool:
    """
    Polls an HTTP endpoint until it returns a valid HTTP response or times out.
    """
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"

    start_time = time.time()
    logger.info("Awaiting HTTP readiness on %s (timeout: %.1fs)...", url, timeout)

    while time.time() - start_time < timeout:
        try:
            conn = http.client.HTTPConnection(host, port, timeout=1.0)
            conn.request("GET", path)
            resp = conn.getresponse()
            # Any HTTP status (200, 302, 404, etc.) indicates the HTTP server is listening and answering
            if resp.status > 0:
                conn.close()
                elapsed = time.time() - start_time
                logger.info("HTTP endpoint %s is READY in %.2fs (HTTP %d).", url, elapsed, resp.status)
                return True
        except (OSError, http.client.HTTPException):
            pass
        time.sleep(0.5)

    elapsed = time.time() - start_time
    logger.warning("HTTP endpoint %s timed out after %.2fs without responding.", url, elapsed)
    return False


class ServiceProcess:
    """Represents a managed child process."""

    def __init__(
        self,
        name: str,
        cmd: List[str],
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        stdout_log: Optional[Path] = None,
        stderr_log: Optional[Path] = None,
    ) -> None:
        self.name = name
        self.cmd = cmd
        self.cwd = cwd or Path.cwd()
        self.env = env
        self.stdout_log = stdout_log
        self.stderr_log = stderr_log
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self.start_time: Optional[float] = None
        self._out_file = None
        self._err_file = None

    @property
    def is_running(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    def poll_exit_code(self) -> Optional[int]:
        if self.process is None:
            return None
        return self.process.poll()

    def start(self) -> bool:
        """Launches the managed child process."""
        if self.is_running:
            logger.info("Service %s is already running (PID: %s)", self.name, self.pid)
            return True

        try:
            logger.info("Starting service %s: %s", self.name, " ".join(self.cmd))
            
            # Setup log redirect targets if provided
            out_dest = subprocess.DEVNULL
            err_dest = subprocess.DEVNULL

            if self.stdout_log:
                self.stdout_log.parent.mkdir(parents=True, exist_ok=True)
                self._out_file = open(self.stdout_log, "a", encoding="utf-8")
                out_dest = self._out_file
            if self.stderr_log:
                self.stderr_log.parent.mkdir(parents=True, exist_ok=True)
                self._err_file = open(self.stderr_log, "a", encoding="utf-8")
                err_dest = self._err_file

            proc_env = dict(os.environ) if self.env is None else dict(self.env)
            proc_env["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
            proc_env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

            self.process = subprocess.Popen(
                self.cmd,
                cwd=str(self.cwd),
                env=proc_env,
                stdout=out_dest,
                stderr=err_dest,
            )
            self.pid = self.process.pid
            self.start_time = time.time()
            logger.info("Service %s started successfully with PID %s", self.name, self.pid)
            return True
        except Exception as e:
            logger.error("Failed to start service %s: %s", self.name, e)
            self.process = None
            self.pid = None
            return False

    def stop(self, timeout: float = 3.0) -> bool:
        """Cleanly stops the process, escalating to kill if needed."""
        if not self.is_running or self.process is None:
            self.process = None
            self.pid = None
            return True

        logger.info("Stopping service %s (PID: %s)...", self.name, self.pid)
        try:
            self.process.terminate()
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning("Service %s did not terminate in %.1fs. Forcing kill...", self.name, timeout)
            try:
                self.process.kill()
                self.process.wait(timeout=2.0)
            except Exception as e:
                logger.error("Error killing service %s: %s", self.name, e)
        except Exception as e:
            logger.error("Error stopping service %s: %s", self.name, e)
        finally:
            self.process = None
            self.pid = None
            if self._out_file:
                try:
                    self._out_file.close()
                except Exception:
                    pass
                self._out_file = None
            if self._err_file:
                try:
                    self._err_file.close()
                except Exception:
                    pass
                self._err_file = None

        logger.info("Service %s stopped.", self.name)
        return True


class ProductLifecycleManager:
    """
    Orchestrates the lifecycle of all Encrypted Traffic Monitor product components.
    """

    def __init__(self, config=None) -> None:
        self.config = config or product_config
        self.services: Dict[str, ServiceProcess] = {}
        self._is_shutting_down = False

        # Register atexit handler for crash and exit protection
        atexit.register(self.shutdown_all)

    def register_service(
        self,
        name: str,
        cmd: List[str],
        cwd: Optional[Path] = None,
        stdout_log: Optional[Path] = None,
        stderr_log: Optional[Path] = None,
    ) -> ServiceProcess:
        """Registers a service for managed lifecycle."""
        svc = ServiceProcess(
            name=name,
            cmd=cmd,
            cwd=cwd,
            stdout_log=stdout_log,
            stderr_log=stderr_log,
        )
        self.services[name] = svc
        return svc

    def start_realtime_engine(
        self,
        mode: str = "live",
        interface: Optional[str] = None,
        model: str = "lightgbm",
    ) -> bool:
        """Starts the realtime classification backend."""
        log_dir = get_log_dir()
        capture_log = log_dir / "capture.log"

        if is_frozen():
            # In frozen mode, run with python flag or subprocess
            cmd = [
                str(sys.executable),
                "-m",
                "realtime.run",
                "--mode",
                mode,
                "--model",
                model,
            ]
        else:
            cmd = [
                sys.executable,
                "-m",
                "realtime.run",
                "--mode",
                mode,
                "--model",
                model,
            ]

        if interface and mode == "live":
            cmd.extend(["--interface", interface])

        svc = self.register_service(
            "realtime_engine",
            cmd,
            cwd=get_base_dir(),
            stdout_log=capture_log,
            stderr_log=capture_log,
        )
        ok = svc.start()
        log_packaged_runtime_event(
            "ENGINE_STARTED" if ok else "ENGINE_START_FAILED",
            {"engine_pid": svc.pid, "mode": mode, "model": model},
        )
        return ok

    def start_dashboard(self, port: Optional[int] = None, timeout: float = 30.0) -> bool:
        """
        Starts the Streamlit SOC dashboard.
        In frozen mode, invokes sibling EncryptedTrafficDashboard.exe.
        In developer mode, invokes python -m product.dashboard_launcher.
        Waits for HTTP readiness on http://127.0.0.1:<port>.
        """
        dashboard_port = port or self.config.dashboard_port
        log_dir = get_log_dir()
        dash_log = log_dir / "dashboard_runtime.log"

        if is_frozen():
            dash_exe = get_dashboard_executable_path()
            if not dash_exe.exists():
                logger.error("Dashboard executable not found at %s", dash_exe)
                log_packaged_runtime_event(
                    "DASHBOARD_EXE_NOT_FOUND",
                    {"expected_path": str(dash_exe)},
                )
                return False
            cmd = [str(dash_exe), "--port", str(dashboard_port)]
            dash_exe_str = str(dash_exe)
        else:
            cmd = [
                sys.executable,
                "-m",
                "product.dashboard_launcher",
                "--port",
                str(dashboard_port),
            ]
            dash_exe_str = sys.executable

        svc = self.register_service(
            "dashboard",
            cmd,
            cwd=get_base_dir(),
            stdout_log=dash_log,
            stderr_log=dash_log,
        )
        started = svc.start()

        log_packaged_runtime_event(
            "DASHBOARD_PROCESS_LAUNCHED" if started else "DASHBOARD_LAUNCH_FAILED",
            {
                "dashboard_pid": svc.pid,
                "dashboard_exe": dash_exe_str,
                "port": dashboard_port,
            },
        )

        if not started:
            return False

        # Supervised readiness check
        dash_url = f"http://127.0.0.1:{dashboard_port}"
        ready = wait_for_http_ready(dash_url, timeout=timeout)

        # Check if process crashed during wait
        exit_code = svc.poll_exit_code()
        if exit_code is not None and exit_code != 0:
            logger.critical("Dashboard process died unexpectedly with exit code %s", exit_code)
            log_packaged_runtime_event(
                "DASHBOARD_PROCESS_DIED",
                {
                    "dashboard_pid": svc.pid,
                    "exit_code": exit_code,
                    "dashboard_exe": dash_exe_str,
                },
            )
            return False

        log_packaged_runtime_event(
            "DASHBOARD_READY" if ready else "DASHBOARD_READINESS_TIMEOUT",
            {
                "dashboard_pid": svc.pid,
                "port_ready": ready,
                "dashboard_url": dash_url,
            },
        )

        return ready

    def stop_service(self, name: str) -> bool:
        """Stops a specific service by name."""
        if name in self.services:
            res = self.services[name].stop()
            log_packaged_runtime_event("SERVICE_STOPPED", {"service_name": name})
            return res
        return True

    def stop_realtime_engine(self) -> bool:
        return self.stop_service("realtime_engine")

    def stop_dashboard(self) -> bool:
        return self.stop_service("dashboard")

    def shutdown_all(self) -> None:
        """Shuts down all managed child processes cleanly."""
        if self._is_shutting_down:
            return
        self._is_shutting_down = True

        for name, svc in list(self.services.items()):
            if svc.is_running:
                try:
                    svc.stop(timeout=2.0)
                except Exception as e:
                    logger.debug("Shutdown note for %s: %s", name, e)

        log_packaged_runtime_event("ALL_SERVICES_SHUTDOWN", {"count": len(self.services)})
        self.services.clear()
        self._is_shutting_down = False

    def get_status(self) -> Dict[str, Any]:
        """Returns the current running status of all managed services."""
        status_map: Dict[str, Any] = {}
        for name, svc in self.services.items():
            status_map[name] = {
                "running": svc.is_running,
                "pid": svc.pid,
                "uptime_seconds": round(time.time() - svc.start_time, 2) if svc.start_time and svc.is_running else 0,
                "exit_code": svc.poll_exit_code(),
            }
        return {
            "services": status_map,
            "all_healthy": all(s["running"] for s in status_map.values()) if status_map else False,
        }
