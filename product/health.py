"""
Comprehensive Product Health & Diagnostic Module.

Performs structured diagnostic checks on OS, runtime, Npcap driver, network adapters,
filesystem, model registry & artifact hashes, feature schema, permissions, and ports.
Returns PASS, WARNING, or FAIL with human-readable and machine-readable output.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import socket
import sys
from typing import Any, Dict, List, Optional

from product.adapter_manager import get_default_adapter, list_adapters
from product.config import product_config
from product.environment import check_npcap, get_os_info, is_admin, is_windows
from product.security import validate_security_boundary
from realtime.schema import CANONICAL_NUMERICAL_FEATURES, CANONICAL_SCHEMA_HASH, get_feature_schema_hash

logger = logging.getLogger(__name__)


def check_port_availability(host: str = "127.0.0.1", port: int = 8501) -> Dict[str, Any]:
    """Tests if a localhost TCP port is available or already occupied."""
    is_available = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        sock.bind((host, port))
        is_available = True
    except OSError:
        is_available = False
    finally:
        sock.close()

    return {
        "host": host,
        "port": port,
        "available": is_available,
        "status": "PASS" if is_available else "WARNING",
        "message": f"Port {port} is available" if is_available else f"Port {port} is currently in use (dashboard may already be running)",
    }


def run_product_health_check(
    registry_path: str | Path = "results/models/production_registry.json",
    models_dir: str | Path = "results/models",
) -> Dict[str, Any]:
    """
    Executes all system, security, environment, and model checks.

    Returns:
        Structured dictionary containing overall status ('PASS', 'WARNING', 'FAIL')
        and individual check results.
    """
    reg_path = Path(registry_path)
    m_dir = Path(models_dir)
    results: Dict[str, Any] = {}
    fail_count = 0
    warning_count = 0

    # 1. OS & Architecture Check
    os_info = get_os_info()
    os_pass = os_info["is_windows"] and os_info["is_64bit"]
    results["os"] = {
        "status": "PASS" if os_pass else ("WARNING" if not os_info["is_windows"] else "FAIL"),
        "display_name": os_info["display_name"],
        "is_64bit": os_info["is_64bit"],
        "is_windows": os_info["is_windows"],
    }
    if results["os"]["status"] == "FAIL":
        fail_count += 1
    elif results["os"]["status"] == "WARNING":
        warning_count += 1

    # 2. Python Runtime Check
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_pass = sys.version_info >= (3, 9)
    results["runtime"] = {
        "status": "PASS" if py_pass else "FAIL",
        "python_version": py_ver,
        "is_64bit": sys.maxsize > 2**32,
    }
    if results["runtime"]["status"] == "FAIL":
        fail_count += 1

    # 3. Npcap / Capture Driver Check
    npcap_res = check_npcap()
    results["npcap"] = npcap_res
    if npcap_res["status"] == "FAIL":
        fail_count += 1
    elif npcap_res["status"] == "WARNING":
        warning_count += 1

    # 4. Network Adapter Check
    adapters = list_adapters()
    default_ad = get_default_adapter()
    active_count = sum(1 for a in adapters if a["status"] == "UP")
    if adapters:
        ad_status = "PASS" if active_count > 0 else "WARNING"
        ad_msg = f"{len(adapters)} adapter(s) found ({active_count} active)"
    else:
        ad_status = "FAIL" if is_windows() else "WARNING"
        ad_msg = "No network adapters detected by capture engine"

    results["adapters"] = {
        "status": ad_status,
        "count": len(adapters),
        "active_count": active_count,
        "default_adapter": default_ad["friendly_name"] if default_ad else None,
        "message": ad_msg,
    }
    if ad_status == "FAIL":
        fail_count += 1
    elif ad_status == "WARNING":
        warning_count += 1

    # 5. Filesystem Layout Check
    required_dirs = [
        Path("data/local/logs"),
        Path("data/local/events"),
        Path("data/local/metrics"),
        Path("data/local/reports"),
        Path("config"),
        Path("results/models"),
    ]
    fs_ok = True
    for d in required_dirs:
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            fs_ok = False

    results["filesystem"] = {
        "status": "PASS" if fs_ok else "FAIL",
        "message": "Local directories ready and writable" if fs_ok else "Filesystem permission error",
    }
    if not fs_ok:
        fail_count += 1

    # 6. Configuration Schema Validation Check
    cfg_res = product_config.validate()
    results["configuration"] = {
        "status": cfg_res["status"],
        "message": cfg_res["message"],
        "errors": cfg_res.get("errors", []),
        "warnings": cfg_res.get("warnings", []),
    }
    if cfg_res["status"] == "FAIL":
        fail_count += 1

    # 7. Model Registry & Checksum Verification
    model_ok = False
    model_msg = ""
    default_model_id = "unknown"
    if reg_path.exists():
        try:
            with open(reg_path, "r", encoding="utf-8") as f:
                reg_data = json.load(f)
            default_model_id = reg_data.get("default_model_id", "model_lightgbm_v1")
            m_info = reg_data.get("registered_models", {}).get(default_model_id, {})
            m_name = m_info.get("model_name", "lightgbm")
            m_file = m_dir / f"{m_name}.joblib"
            p_file = m_dir / "preprocessor.joblib"

            if m_file.exists() and p_file.exists():
                m_hash = hashlib.sha256(m_file.read_bytes()).hexdigest()
                p_hash = hashlib.sha256(p_file.read_bytes()).hexdigest()

                exp_m_hash = m_info.get("model_hash")
                exp_p_hash = m_info.get("preprocessor_hash")

                if (not exp_m_hash or m_hash == exp_m_hash) and (not exp_p_hash or p_hash == exp_p_hash):
                    model_ok = True
                    model_msg = f"Model {default_model_id} and preprocessor verified"
                else:
                    model_msg = f"Model hash mismatch (expected {exp_m_hash[:8]}, got {m_hash[:8]})"
            else:
                model_msg = f"Artifacts missing: {m_file} or {p_file}"
        except Exception as e:
            model_msg = f"Registry load error: {e}"
    else:
        model_msg = f"Registry missing at {reg_path}"

    results["model"] = {
        "status": "PASS" if model_ok else "FAIL",
        "default_model_id": default_model_id,
        "message": model_msg,
    }
    if not model_ok:
        fail_count += 1

    # 8. Feature Schema Hash Verification
    schema_hash = get_feature_schema_hash(CANONICAL_NUMERICAL_FEATURES)
    schema_ok = schema_hash == CANONICAL_SCHEMA_HASH
    results["feature_schema"] = {
        "status": "PASS" if schema_ok else "FAIL",
        "hash": schema_hash,
        "feature_count": len(CANONICAL_NUMERICAL_FEATURES),
        "message": "Canonical feature schema verified" if schema_ok else "Feature schema mismatch",
    }
    if not schema_ok:
        fail_count += 1

    # 9. Security & Privacy Boundary Check
    sec_res = validate_security_boundary()
    results["security"] = sec_res
    if sec_res["status"] == "FAIL":
        fail_count += 1

    # 10. Local API Port Availability Check
    api_port_val = product_config.local_api_config.get("port", 8080)
    api_port_res = check_port_availability(port=api_port_val)
    results["api_port"] = api_port_res

    # 11. Dashboard Port Availability Check
    port_res = check_port_availability(port=product_config.dashboard_port)
    results["dashboard_port"] = port_res

    # Overall Summary
    if fail_count > 0:
        overall = "FAIL"
    elif warning_count > 0:
        overall = "WARNING"
    else:
        overall = "PASS"

    return {
        "overall_status": overall,
        "checks_passed": sum(1 for c in results.values() if isinstance(c, dict) and c.get("status") == "PASS"),
        "total_checks": len(results),
        "checks": results,
    }


def print_health_report(report: Optional[Dict[str, Any]] = None) -> None:
    """Prints a clean CLI health report banner."""
    if report is None:
        report = run_product_health_check()

    print("\n" + "=" * 50)
    print("ENCRYPTED TRAFFIC MONITOR — HEALTH DIAGNOSTICS")
    print("=" * 50)
    print(f"Overall Status:    {report['overall_status']}")
    print("-" * 50)

    checks = report.get("checks", {})
    for name, data in checks.items():
        status = data.get("status", "UNKNOWN")
        msg = data.get("message", "")
        print(f"[{status:7s}] {name:16s} : {msg}")

    print("=" * 50 + "\n")


if __name__ == "__main__":
    print_health_report()

