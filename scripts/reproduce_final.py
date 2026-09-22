"""
Master Reproducibility Script for Encrypted Traffic Classification.

Executes and verifies:
1. Dataset & artifact integrity
2. Model registry & feature schema SHA-256 hashes
3. Offline benchmark test vector parity
4. Zero-payload privacy & security invariants
5. Production diagnostic health check
6. Real-time stress and stability benchmarks
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("reproduce_final")


def main() -> None:
    print("=" * 80)
    print("ENCRYPTED TRAFFIC CLASSIFIER - MASTER REPRODUCIBILITY SUITE")
    print("=" * 80)

    steps = [
        ("Health & Diagnostic Check", [sys.executable, "scripts/production_health_check.py"]),
        ("Full Test Suite (76 Tests)", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]),
        ("Offline-Realtime Parity", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_offline_realtime_parity.py"]),
        ("Zero-Payload Privacy Check", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_zero_payload_live.py"]),
        ("Stress Test Benchmark", [sys.executable, "scripts/run_stress_test.py"]),
    ]

    all_passed = True

    for name, cmd in steps:
        print(f"\n[*] Executing: {name}...", flush=True)
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"[+] {name}: SUCCESS", flush=True)
        else:
            print(f"[-] {name}: FAILED\n{res.stderr}\n{res.stdout}", flush=True)
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("ALL VERIFICATION GATES PASSED! SYSTEM REPRODUCIBILITY 100% CONFIRMED.")
    else:
        print("SOME REPRODUCIBILITY GATES FAILED. Review errors above.")
    print("=" * 80)

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
