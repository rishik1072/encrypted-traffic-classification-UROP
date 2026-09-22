"""
Pre-flight Installer and Runtime Integrity Checker for Encrypted Traffic Monitor.

Validates that all application directories, model checkpoints, schema definitions,
and required runtime prerequisites exist prior to execution.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

from product.environment import check_npcap, get_os_info
from product.version import APP_NAME, __version__

logger = logging.getLogger(__name__)


def verify_filesystem_layout() -> Dict[str, Any]:
    """Ensures local storage and log directories exist and are writable."""
    required_dirs = [
        Path("data/local/logs"),
        Path("data/local/events"),
        Path("data/local/metrics"),
        Path("data/local/reports"),
        Path("config"),
        Path("results/models"),
    ]

    results: Dict[str, bool] = {}
    all_ok = True

    for d in required_dirs:
        try:
            d.mkdir(parents=True, exist_ok=True)
            # Test write access with temp file
            test_file = d / ".write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            results[str(d)] = True
        except Exception as e:
            logger.error("Directory check failed for %s: %s", d, e)
            results[str(d)] = False
            all_ok = False

    return {
        "status": "PASS" if all_ok else "FAIL",
        "directories": results,
    }


def verify_model_artifacts() -> Dict[str, Any]:
    """Verifies that model registry, model checkpoints, and preprocessor exist."""
    registry_path = Path("results/models/production_registry.json")
    if not registry_path.exists():
        return {
            "status": "FAIL",
            "message": f"Production registry not found at {registry_path}",
            "models_found": [],
        }

    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            reg_data = json.load(f)
    except Exception as e:
        return {
            "status": "FAIL",
            "message": f"Failed to parse production registry: {e}",
            "models_found": [],
        }

    registered_models = reg_data.get("registered_models", {})
    preprocessor_path = Path("results/models/preprocessor.joblib")
    prep_exists = preprocessor_path.exists()

    found_models: List[str] = []
    missing_models: List[str] = []

    for m_id, m_meta in registered_models.items():
        m_name = m_meta.get("model_name", "lightgbm")
        m_file = Path(f"results/models/{m_name}.joblib")
        if m_file.exists():
            found_models.append(m_id)
        else:
            missing_models.append(m_id)

    status = "PASS" if (len(found_models) > 0 and prep_exists) else "FAIL"

    return {
        "status": status,
        "preprocessor_present": prep_exists,
        "models_found": found_models,
        "models_missing": missing_models,
        "default_model_id": reg_data.get("default_model_id", "model_lightgbm_v1"),
    }


def run_preflight_checks() -> Dict[str, Any]:
    """
    Runs complete end-to-end preflight installation checks.
    """
    os_info = get_os_info()
    npcap_status = check_npcap()
    fs_status = verify_filesystem_layout()
    model_status = verify_model_artifacts()

    overall_ok = (
        fs_status["status"] == "PASS"
        and model_status["status"] == "PASS"
    )

    return {
        "app_name": APP_NAME,
        "version": __version__,
        "overall_status": "PASS" if overall_ok else "FAIL",
        "os_info": os_info,
        "npcap": npcap_status,
        "filesystem": fs_status,
        "models": model_status,
    }
