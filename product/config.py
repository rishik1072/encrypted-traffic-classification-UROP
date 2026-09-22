"""
Product Configuration Manager for Encrypted Traffic Monitor.

Loads and enforces configuration invariants, such as strict local-only execution
and immutable zero-payload raw packet persistence policies.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

from product.version import APP_NAME, __version__

logger = logging.getLogger(__name__)


class ProductConfig:
    """
    Manages product configuration loaded from config/product.yaml.
    Guarantees privacy invariants and local execution rules.
    """

    DEFAULT_CONFIG_PATH = Path("config/product.yaml")

    def __init__(self, config_path: Optional[str | Path] = None) -> None:
        self.config_path = Path(config_path or self.DEFAULT_CONFIG_PATH)
        self._raw_config: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Loads configuration from YAML with built-in safe defaults."""
        defaults: Dict[str, Any] = {
            "app_name": APP_NAME,
            "version": __version__,
            "local_only": True,
            "default_mode": "LIVE_MODE",
            "default_interface": "auto",
            "minimum_packets": 5,
            "dashboard_port": 8501,
            "auto_open_browser": True,
            "log_level": "INFO",
            "log_directory": "data/local/logs",
            "max_log_size_mb": 10,
            "log_backup_count": 5,
            "save_prediction_logs": True,
            "save_metrics_logs": True,
            "save_raw_packets": False,
            "local_api": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 8080,
            },
        }

        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f) or {}
                    defaults.update(loaded)
            except Exception as e:
                logger.warning("Error reading %s: %s. Using default product settings.", self.config_path, e)

        # Enforce Critical Security & Privacy Invariants
        if defaults.get("save_raw_packets") is not False:
            logger.critical("Security violation detected: save_raw_packets cannot be True. Enforcing False.")
            defaults["save_raw_packets"] = False

        if not defaults.get("local_only", True):
            logger.warning("local_only was disabled in config. Enforcing True for privacy compliance.")
            defaults["local_only"] = True

        # Restrict API Host to Localhost only
        local_api_cfg = defaults.get("local_api", {})
        if local_api_cfg.get("host") not in ("127.0.0.1", "localhost"):
            logger.warning("Binding API to non-local address '%s' blocked. Restricting to 127.0.0.1.", local_api_cfg.get("host"))
            local_api_cfg["host"] = "127.0.0.1"

        self._raw_config = defaults

    @property
    def app_name(self) -> str:
        return str(self._raw_config.get("app_name", APP_NAME))

    @property
    def version(self) -> str:
        return str(self._raw_config.get("version", __version__))

    @property
    def local_only(self) -> bool:
        return True  # Invariant

    @property
    def default_mode(self) -> str:
        return str(self._raw_config.get("default_mode", "LIVE_MODE"))

    @property
    def default_interface(self) -> str:
        return str(self._raw_config.get("default_interface", "auto"))

    @property
    def minimum_packets(self) -> int:
        return int(self._raw_config.get("minimum_packets", 5))

    @property
    def dashboard_port(self) -> int:
        return int(self._raw_config.get("dashboard_port", 8501))

    @property
    def auto_open_browser(self) -> bool:
        return bool(self._raw_config.get("auto_open_browser", True))

    @property
    def log_level(self) -> str:
        return str(self._raw_config.get("log_level", "INFO")).upper()

    @property
    def log_directory(self) -> Path:
        return Path(self._raw_config.get("log_directory", "data/local/logs"))

    @property
    def max_log_size_mb(self) -> int:
        return int(self._raw_config.get("max_log_size_mb", 10))

    @property
    def log_backup_count(self) -> int:
        return int(self._raw_config.get("log_backup_count", 5))

    @property
    def save_prediction_logs(self) -> bool:
        return bool(self._raw_config.get("save_prediction_logs", True))

    @property
    def save_raw_packets(self) -> bool:
        return False  # Strict security invariant

    @property
    def local_api_config(self) -> Dict[str, Any]:
        return dict(self._raw_config.get("local_api", {"enabled": True, "host": "127.0.0.1", "port": 8080}))

    def setup_logging(self, log_name: str = "application") -> logging.Logger:
        """Configures rotating file logging and console logging."""
        log_dir = self.log_directory
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"{log_name}.log"
        target_logger = logging.getLogger(log_name)
        target_logger.setLevel(getattr(logging, self.log_level, logging.INFO))

        # Check if handler already attached
        has_file_handler = any(isinstance(h, RotatingFileHandler) for h in target_logger.handlers)
        if not has_file_handler:
            max_bytes = self.max_log_size_mb * 1024 * 1024
            rfh = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=self.log_backup_count,
                encoding="utf-8",
            )
            formatter = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
            rfh.setFormatter(formatter)
            target_logger.addHandler(rfh)

        return target_logger


# Global singleton instance
product_config = ProductConfig()
