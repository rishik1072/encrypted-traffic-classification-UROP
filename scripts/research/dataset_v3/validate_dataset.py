"""
CLI Tool: Validate Dataset V3 Sessions and Partitions.

Executes all 17 research and privacy validation checks.
Usage:
    python scripts/research/dataset_v3/validate_dataset.py --session data/research_v3/sess_xxx
    python scripts/research/dataset_v3/validate_dataset.py --root data/research_v3
    python scripts/research/dataset_v3/validate_dataset.py --partitions --train s1 s2 --val s3 --test s4
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research.dataset_v3.validator import DatasetV3Validator


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Dataset V3 Sessions and Partitions")
    parser.add_argument("--session", type=str, help="Path to single session directory to validate")
    parser.add_argument("--root", type=str, help="Path to dataset root containing multiple session directories")
    parser.add_argument("--train", nargs="*", help="Train session directories for partition validation")
    parser.add_argument("--val", nargs="*", help="Validation session directories for partition validation")
    parser.add_argument("--test", nargs="*", help="Test session directories for partition validation")
    parser.add_argument(
        "--enforce-device-disjoint",
        action="store_true",
        help="Enforce zero device pseudonym overlap across train, val, and test partitions",
    )
    parser.add_argument(
        "--enforce-application-disjoint",
        action="store_true",
        help="Enforce zero application alias overlap between train and test partitions",
    )

    args = parser.parse_args()
    validator = DatasetV3Validator()
    has_errors = False

    if args.session:
        s_path = Path(args.session)
        print(f"--- Validating Session: {s_path} ---")
        report = validator.validate_session(s_path)
        print(json.dumps(report.to_dict(), indent=2))
        if not report.is_valid:
            has_errors = True

    elif args.root:
        r_path = Path(args.root)
        print(f"--- Validating All Sessions in Root: {r_path} ---")
        if not r_path.exists():
            print(f"Root directory '{r_path}' does not exist.")
            return 1

        sessions = [p for p in r_path.iterdir() if p.is_dir()]
        if not sessions:
            print("No session directories found in root.")
            return 0

        valid_count = 0
        for s in sorted(sessions):
            rep = validator.validate_session(s)
            status_str = "PASS" if rep.is_valid else "FAIL"
            print(f"Session {s.name:45s} -> {status_str} ({rep.passed_checks}/{rep.total_checks_run} checks passed)")
            if not rep.is_valid:
                has_errors = True
                for err in rep.errors:
                    print(f"  [ERROR] {err}")
            else:
                valid_count += 1
        print(f"\nSummary: {valid_count}/{len(sessions)} sessions valid.")

    elif args.train and args.val and args.test:
        tr_paths = [Path(p) for p in args.train]
        val_paths = [Path(p) for p in args.val]
        te_paths = [Path(p) for p in args.test]
        print("--- Validating Partition Isolation ---")
        is_valid, errors = validator.validate_partitions(
            tr_paths,
            val_paths,
            te_paths,
            enforce_device_disjoint=args.enforce_device_disjoint,
            enforce_application_disjoint=args.enforce_application_disjoint,
        )
        if is_valid:
            print("Partition Isolation Check: PASSED (Zero session and parent-flow overlap)")
        else:
            print("Partition Isolation Check: FAILED")
            for err in errors:
                print(f"  [ERROR] {err}")
            has_errors = True
    else:
        parser.print_help()
        return 1

    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
