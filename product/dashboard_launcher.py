"""
Encrypted Traffic Dashboard — Standalone Executable Entry Point.

Dedicated launcher for EncryptedTrafficDashboard.exe that programmatically boots
Streamlit on http://127.0.0.1:8501 with local-only binding, headless execution,
disabled telemetry, and structured runtime error logging.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import traceback

# Enforce developmentMode=false in environment immediately
os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

# Ensure project root is on sys.path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from product.runtime_paths import get_dashboard_app_path, get_log_dir, get_resource_dir, is_frozen


def setup_dashboard_logging() -> logging.Logger:
    """Configures structured runtime logging to data/local/logs/dashboard_runtime.log."""
    log_dir = get_log_dir()
    log_file = log_dir / "dashboard_runtime.log"

    dash_logger = logging.getLogger("dashboard_runtime")
    dash_logger.setLevel(logging.INFO)

    # Attach rotating handler if not present
    if not any(isinstance(h, RotatingFileHandler) for h in dash_logger.handlers):
        rfh = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] [dashboard_launcher]: %(message)s")
        rfh.setFormatter(formatter)
        dash_logger.addHandler(rfh)

    return dash_logger


def run_dashboard(
    port: int = 8501,
    host: str = "127.0.0.1",
) -> int:
    """
    Launches the Streamlit SOC dashboard application.
    """
    logger = setup_dashboard_logging()
    logger.info("Initializing EncryptedTrafficDashboard...")
    logger.info("Frozen: %s | Host: %s | Port: %d", is_frozen(), host, port)

    # Enforce environment configuration for Streamlit
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    os.environ["STREAMLIT_SERVER_PORT"] = str(port)
    os.environ["STREAMLIT_SERVER_ADDRESS"] = host
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    # Reconfigure stdout/stderr for UTF-8 on Windows
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.debug("Encoding reconfigure note: %s", e)

    app_path = get_dashboard_app_path()
    res_dir = get_resource_dir()
    live_feed_path = app_path.parent / "live_feed.py"
    meipass = getattr(sys, "_MEIPASS", "None")

    logger.info("sys.executable: %s", sys.executable)
    logger.info("sys._MEIPASS: %s", meipass)
    logger.info("Dashboard resource dir: %s", res_dir)
    logger.info("Actual app.py path: %s (exists=%s)", app_path, app_path.exists())
    logger.info("Actual live_feed.py path: %s (exists=%s)", live_feed_path, live_feed_path.exists())

    if not app_path.exists():
        err_msg = f"Dashboard script not found at {app_path}"
        logger.critical(err_msg)
        print(f"[CRITICAL] {err_msg}", file=sys.stderr)
        return 1

    # Ensure working directory allows relative asset imports
    base_dir = app_path.parent.parent
    if base_dir.exists():
        try:
            os.chdir(str(base_dir))
        except Exception:
            pass

    # Build Streamlit CLI arguments
    args = [
        "run",
        str(app_path),
        "--global.developmentMode",
        "false",
        "--server.address",
        host,
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
        "--server.enableCORS",
        "false",
        "--server.enableXsrfProtection",
        "true",
    ]

    logger.info("Invoking Streamlit CLI with args: %s", " ".join(args))

    try:
        try:
            from streamlit.web import cli as stcli
        except ImportError:
            from streamlit import cli as stcli

        sys.argv = ["streamlit"] + args
        stcli.main(args=args, standalone_mode=False)
        return 0
    except SystemExit as se:
        code = se.code if isinstance(se.code, int) else 0
        logger.info("Streamlit exited with code %s", code)
        return code
    except Exception as exc:
        err_trace = traceback.format_exc()
        logger.critical("Unhandled dashboard startup exception: %s\n%s", exc, err_trace)
        print(f"[CRITICAL] Dashboard runtime error: {exc}", file=sys.stderr)
        return 1


def main() -> None:
    port = 8501
    host = "127.0.0.1"

    # Allow overriding port via CLI if provided
    for i, arg in enumerate(sys.argv):
        if arg in ("--port", "-p") and i + 1 < len(sys.argv):
            try:
                port = int(sys.argv[i + 1])
            except ValueError:
                pass

    exit_code = run_dashboard(port=port, host=host)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
