"""
Audit and identify prediction schema discrepancies across all realtime prediction logs.
Generates results/realtime/prediction_schema_audit.csv.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.data_adapter import normalize_prediction_record
from dashboard.schema import parse_confidence


def audit_prediction_logs():
    pred_csv = Path("results/realtime/predictions.csv")
    pred_jsonl = Path("results/realtime/predictions.jsonl")
    audit_out = Path("results/realtime/prediction_schema_audit.csv")
    audit_out.parent.mkdir(parents=True, exist_ok=True)

    audit_rows = []
    
    # 1. Audit CSV
    if pred_csv.exists():
        with open(pred_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader, start=1):
                rec_id = row.get("event_id", f"CSV_ROW_{idx}")
                raw_conf = row.get("confidence")
                canon, is_valid, err = normalize_prediction_record(row)
                norm_conf = canon.confidence if canon else 0.0
                
                if not is_valid or not canon or not canon.confidence_valid:
                    audit_rows.append({
                        "record_id": rec_id,
                        "source_file": "results/realtime/predictions.csv",
                        "schema_valid": False,
                        "problem": err or "Invalid confidence",
                        "raw_confidence": str(raw_conf),
                        "normalized_confidence": norm_conf,
                    })

    # 2. Audit JSONL
    if pred_jsonl.exists():
        with open(pred_jsonl, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    rec_id = row.get("event_id", f"JSONL_LINE_{idx}")
                    raw_conf = row.get("confidence")
                    canon, is_valid, err = normalize_prediction_record(row)
                    norm_conf = canon.confidence if canon else 0.0
                    
                    if not is_valid or not canon or not canon.confidence_valid:
                        audit_rows.append({
                            "record_id": rec_id,
                            "source_file": "results/realtime/predictions.jsonl",
                            "schema_valid": False,
                            "problem": err or "Invalid confidence",
                            "raw_confidence": str(raw_conf),
                            "normalized_confidence": norm_conf,
                        })
                except Exception as e:
                    audit_rows.append({
                        "record_id": f"JSONL_LINE_{idx}",
                        "source_file": "results/realtime/predictions.jsonl",
                        "schema_valid": False,
                        "problem": f"JSON parse error: {e}",
                        "raw_confidence": "N/A",
                        "normalized_confidence": 0.0,
                    })

    # Write audit report
    fieldnames = [
        "record_id",
        "source_file",
        "schema_valid",
        "problem",
        "raw_confidence",
        "normalized_confidence",
    ]
    with open(audit_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in audit_rows:
            writer.writerow(r)

    print(f"[*] Prediction schema audit complete. Total problematic records: {len(audit_rows)}")
    print(f"[*] Report written to: {audit_out}")


if __name__ == "__main__":
    audit_prediction_logs()
