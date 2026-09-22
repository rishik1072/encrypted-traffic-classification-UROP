"""
Runtime Paths and Packaging Resolver for Encrypted Traffic Monitor.

Provides environment-aware path resolution for frozen (PyInstaller) and developer modes,
ensuring log directories, resource bundles, sibling executables, and config files resolve correctly.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Optional


def is_frozen() -> bool:
    """Returns True if the application is running inside a PyInstaller frozen bundle."""
    return bool(getattr(sys, "frozen", False))


def get_base_dir() -> Path:
    """
    Returns the persistent application root directory.
    - Frozen EXE: The directory containing the executable.
    - Dev Python: The project repository root.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def get_resource_dir() -> Path:
    """
    Returns the directory where packaged internal assets reside.
    - Frozen EXE: sys._MEIPASS (temporary extraction or internal bundle directory)
    - Dev Python: The project repository root.
    """
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return get_base_dir()


def get_dashboard_executable_path() -> Path:
    """
    Returns the path to the sibling EncryptedTrafficDashboard.exe executable.
    """
    base_dir = get_base_dir()
    return base_dir / "EncryptedTrafficDashboard.exe"


def get_writable_data_dir() -> Path:
    """
    Returns a guaranteed writable local data directory outside _internal.
    """
    base_dir = get_base_dir()
    data_dir = base_dir / "data" / "local"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_log_dir() -> Path:
    """
    Returns the runtime logs directory. Guaranteed to exist and be writable.
    """
    log_dir = get_writable_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_dashboard_app_path() -> Path:
    """
    Resolves dashboard/app.py path from base directory, resource bundle, or local filesystem.
    """
    # 1. Try base dir (where distribution dashboard folder sits next to EXE)
    base_path = get_base_dir() / "dashboard" / "app.py"
    if base_path.exists():
        return base_path

    # 2. Try resource dir (sys._MEIPASS / _internal if frozen)
    res_path = get_resource_dir() / "dashboard" / "app.py"
    if res_path.exists():
        return res_path

    # 3. Fallback relative
    return Path("dashboard/app.py").resolve()
