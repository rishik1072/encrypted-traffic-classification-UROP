"""
Collection Environment Fingerprinting.

Extracts non-sensitive, reproducibility-focused system properties.
Does NOT extract PII, user names, or machine network hostnames.
"""

from __future__ import annotations

import hashlib
import platform
import sys
from pathlib import Path
from typing import Any, Dict


def get_environment_fingerprint(device_id: str = "dev_lab_01") -> Dict[str, Any]:
    # Deterministic non-identifying hash
    raw_sig = f"{platform.system()}_{platform.release()}_{sys.version.split()[0]}"
    sig_hash = hashlib.sha256(raw_sig.encode("utf-8")).hexdigest()[:12]

    return {
        "device_id": device_id,
        "os_name": platform.system(),
        "os_release": platform.release(),
        "os_architecture": platform.machine(),
        "python_version": sys.version.split()[0],
        "system_fingerprint": f"ENV-{sig_hash}",
    }


def save_environment_manifest(
    output_path: str = "results/tables/environment_manifest.csv",
    device_id: str = "dev_lab_01",
) -> None:
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    env = get_environment_fingerprint(device_id=device_id)

    with open(p, "w", encoding="utf-8") as f:
        f.write("key,value\n")
        for k, v in env.items():
            f.write(f"{k},{v}\n")


if __name__ == "__main__":
    save_environment_manifest()
    print("Saved environment manifest to results/tables/environment_manifest.csv")
