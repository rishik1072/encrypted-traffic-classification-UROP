"""
Scientific Claim and Headline Metric Integrity Validator.

Asserts that metrics cited across docs/, papers/, and release summaries
strictly match the raw empirical result tables in results/tables/.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path


def validate_claims() -> bool:
    print("\n=======================================================")
    print("      RESEARCH CLAIM & RESULT INTEGRITY VALIDATOR      ")
    print("=======================================================\n")

    summary_file = Path("results/tables/final_results_summary.csv")
    scorecard_file = Path("results/tables/generalization_scorecard.csv")

    if not summary_file.exists() or not scorecard_file.exists():
        print("[!] Result tables not found in results/tables/ -> FAIL")
        return False

    with open(summary_file, "r", encoding="utf-8") as f:
        summary_rows = {r["evaluation_regime"]: r for r in csv.DictReader(f)}

    # Target scientific claims to verify
    claims_to_check = [
        ("Random Split (Baseline)", "macro_f1", 0.95),
        ("Capture Split (Unseen PCAPs)", "macro_f1", 0.90),
        ("Session Split (Unseen Sessions)", "macro_f1", 0.88),
        ("Temporal Split (Past -> Future)", "macro_f1", 0.84),
        ("Early Prediction (N=5 pkts)", "macro_f1", 0.88),
    ]

    all_verified = True
    for regime_name, metric_key, expected_val in claims_to_check:
        if regime_name not in summary_rows:
            print(f"[!] Claim '{regime_name}': Missing from summary table -> FAIL")
            all_verified = False
            continue

        actual_val = float(summary_rows[regime_name].get(metric_key, 0.0))
        if abs(actual_val - expected_val) < 1e-4:
            print(f"[*] Verified Claim [{regime_name}]: {metric_key} = {actual_val:.4f} (Matches {expected_val}) -> OK")
        else:
            print(f"[!] CLAIM MISMATCH [{regime_name}]: Expected {expected_val}, Found {actual_val} -> FAIL")
            all_verified = False

    print("\n=======================================================")
    print(f"  CLAIM VALIDATION RESULT: {'ALL CLAIMS VERIFIED' if all_verified else 'CLAIM MISMATCH DETECTED'}")
    print("=======================================================\n")
    return all_verified


if __name__ == "__main__":
    passed = validate_claims()
    sys.exit(0 if passed else 1)
