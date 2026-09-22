"""
Environment and Dependency Verification Script.

Checks Python runtime, required packages, directory structure, config integrity,
and trained model checkpoints.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
import yaml

REQUIRED_DIRS = [
    "data/raw/pcap",
    "data/processed/flows",
    "data/processed/features",
    "data/processed/splits",
    "results/models",
    "results/tables",
    "results/realtime",
]

CORE_PACKAGES = [
    "yaml",
    "csv",
    "json",
    "pickle",
    "math",
]

OPTIONAL_ML_PACKAGES = [
    "numpy",
    "pandas",
    "sklearn",
    "lightgbm",
    "streamlit",
    "scapy",
    "psutil",
]


def check_environment() -> bool:
    print("\n=======================================================")
    print("      ENVIRONMENT & DEPENDENCY DIAGNOSTIC REPORT      ")
    print("=======================================================\n")

    # 1. Python Version
    py_ver = sys.version.split()[0]
    print(f"[*] Python Runtime: {py_ver} ({sys.platform}) -> OK")

    # 2. Config File
    cfg_p = Path("config.yaml")
    if cfg_p.exists():
        with open(cfg_p, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        classes_count = len(cfg.get("traffic_classes", []))
        print(f"[*] Configuration: config.yaml present ({classes_count} classes configured) -> OK")
    else:
        print("[!] Configuration: config.yaml MISSING -> FAIL")
        return False

    # 3. Directories
    missing_dirs = [d for d in REQUIRED_DIRS if not Path(d).exists()]
    if not missing_dirs:
        print(f"[*] Directory Tree: All {len(REQUIRED_DIRS)} required directories exist -> OK")
    else:
        print(f"[!] Directory Tree: Missing {missing_dirs} -> WARN (creating)")
        for d in missing_dirs:
            Path(d).mkdir(parents=True, exist_ok=True)

    # 4. Core Standard Modules
    for pkg in CORE_PACKAGES:
        try:
            importlib.import_module(pkg)
            print(f"[*] Core Library '{pkg}': Available -> OK")
        except ImportError:
            print(f"[!] Core Library '{pkg}': MISSING -> FAIL")
            return False

    # 5. Scientific & Capture Extensions (with pure-python fallback status)
    print("\n[*] Checking ML & Network Packages (with Pure-Python fallback readiness):")
    for pkg in OPTIONAL_ML_PACKAGES:
        try:
            importlib.import_module(pkg)
            print(f"    - {pkg:15s}: Installed (Native Acceleration Active)")
        except ImportError:
            print(f"    - {pkg:15s}: Not Installed (Pure-Python Fallback Active)")

    # 6. Check Model Checkpoints
    models_dir = Path("results/models")
    prep_file = models_dir / "preprocessor.joblib"
    if prep_file.exists():
        print(f"[*] Fitted Preprocessor: Found at {prep_file} -> OK")
    else:
        print(f"[!] Fitted Preprocessor: Not found at {prep_file} -> WARN")

    print("\n=======================================================")
    print("      ENVIRONMENT DIAGNOSIS: READY FOR EXECUTION      ")
    print("=======================================================\n")
    return True


if __name__ == "__main__":
    check_environment()
