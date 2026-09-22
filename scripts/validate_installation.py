#!/usr/bin/env python3
"""
Encrypted Traffic Monitor - Automated Windows Installation & Runtime Validation CLI.

Runs the complete 9-point end-to-end verification:
1. Clean installation & filesystem layout
2. Dependency availability
3. Model loading & cryptographic integrity
4. Network adapter detection
5. Local REST API (Port 8080)
6. Streamlit SOC Dashboard readiness (Port 8501)
7. DEMO mode execution
8. LIVE mode capture & privilege boundary
9. Clean process shutdown & restart

Usage:
    python scripts/validate_installation.py
    python scripts/validate_installation.py --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Ensure repository root is on Python path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from product.validate import run_installation_validation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Encrypted Traffic Monitor - Windows Installation & Runtime Validation"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON scorecard instead of human-readable text",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress verbose progress printouts",
    )
    args = parser.parse_args()

    verbose = not args.quiet and not args.json
    scorecard = run_installation_validation(verbose=verbose)

    if args.json:
        print(json.dumps(scorecard, indent=2))

    sys.exit(0 if scorecard["overall_status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
