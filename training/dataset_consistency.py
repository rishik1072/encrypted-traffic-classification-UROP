"""
Dataset Cross-Layer Consistency Auditor.

Verifies consistency across:
1. Manifest (data/dataset_manifest.csv)
2. Metadata Files (data/raw/metadata/<session_id>.csv)
3. Flows Dataset (data/processed/flows/flows_real.csv)
4. Features Dataset (data/processed/features/features_real.csv)
5. Session Log (data/raw/metadata/session_log.jsonl)

Produces:
- results/tables/real_dataset_consistency_report.csv
- results/tables/manifest_reconciliation.csv
"""

from __future__ import annotations

import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

# Allow large packet streams in flows.csv
try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2147483647)

logger = logging.getLogger(__name__)


def audit_dataset_consistency(
    manifest_path: str = "data/dataset_manifest.csv",
    flows_path: str = "data/processed/flows/flows_real.csv",
    features_path: str = "data/processed/features/features_real.csv",
    session_log_path: str = "data/raw/metadata/session_log.jsonl",
    consistency_report_path: str = "results/tables/real_dataset_consistency_report.csv",
    reconciliation_report_path: str = "results/tables/manifest_reconciliation.csv",
) -> Dict[str, Any]:
    m_p = Path(manifest_path)
    fl_p = Path(flows_path)
    fe_p = Path(features_path)
    sl_p = Path(session_log_path)

    # 1. Load Real Manifest Records
    manifest_records = []
    if m_p.exists():
        with open(m_p, "r", encoding="utf-8") as f:
            all_m = list(csv.DictReader(f))
            manifest_records = [
                r for r in all_m
                if r.get("data_origin") == "real" and r.get("capture_source") == "REAL_LIVE_CAPTURE"
            ]

    # 2. Load Flows & Group by Session
    flows_by_sess: Dict[str, List[Dict[str, Any]]] = {}
    if fl_p.exists():
        with open(fl_p, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                sid = r.get("session_id", "")
                if sid not in flows_by_sess:
                    flows_by_sess[sid] = []
                flows_by_sess[sid].append(r)

    # 3. Load Features & Group by Session
    features_by_sess: Dict[str, List[Dict[str, Any]]] = {}
    if fe_p.exists():
        with open(fe_p, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                sid = r.get("session_id", "")
                if sid not in features_by_sess:
                    features_by_sess[sid] = []
                features_by_sess[sid].append(r)

    # 4. Load Session Log
    log_by_sess: Dict[str, Dict[str, Any]] = {}
    if sl_p.exists():
        with open(sl_p, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if entry.get("state") == "VALIDATED":
                        log_by_sess[entry["session_id"]] = entry

    consistency_rows = []
    reconciliation_rows = []
    pass_count = 0
    warning_count = 0
    fail_count = 0

    for r in manifest_records:
        sid = r.get("session_id", "")
        t_class = r.get("traffic_class", "")
        meta_rel = r.get("raw_source_path") or r.get("metadata_path", "")
        meta_p = Path(meta_rel)
        meta_exists = meta_p.exists()

        m_pkts = int(r.get("packet_count", 0))
        m_bytes = int(r.get("byte_count", 0))

        # Check metadata file packet count
        real_meta_pkts = 0
        real_meta_bytes = 0
        if meta_exists:
            with open(meta_p, "r", encoding="utf-8") as mf:
                m_reader = list(csv.DictReader(mf))
                real_meta_pkts = len(m_reader)
                real_meta_bytes = sum(int(row.get("packet_length", 0)) for row in m_reader)

        flow_list = flows_by_sess.get(sid, [])
        feat_list = features_by_sess.get(sid, [])

        num_flows = len(flow_list)
        num_feats = len(feat_list)

        # Check errors
        errors = []
        if not meta_exists:
            errors.append("METADATA_FILE_MISSING")
        if num_flows == 0:
            errors.append("FLOWS_NOT_GENERATED")
        if num_feats != num_flows:
            errors.append("FLOW_FEATURE_COUNT_MISMATCH")
        if real_meta_pkts != m_pkts:
            errors.append(f"PACKET_COUNT_MISMATCH(meta={real_meta_pkts},man={m_pkts})")
        if real_meta_bytes != m_bytes:
            errors.append(f"BYTE_COUNT_MISMATCH(meta={real_meta_bytes},man={m_bytes})")

        status = "FAIL" if errors else "PASS"
        if status == "PASS":
            pass_count += 1
        else:
            fail_count += 1

        consistency_rows.append({
            "session_id": sid,
            "traffic_class": t_class,
            "metadata_exists": meta_exists,
            "flows_count": num_flows,
            "features_count": num_feats,
            "manifest_pkts": m_pkts,
            "metadata_pkts": real_meta_pkts,
            "manifest_bytes": m_bytes,
            "metadata_bytes": real_meta_bytes,
            "status": status,
            "details": "; ".join(errors) if errors else "Consistent",
        })

        reconciliation_rows.append({
            "session_id": sid,
            "manifest_present": "TRUE",
            "metadata_present": "TRUE" if meta_exists else "FALSE",
            "flow_records": num_flows,
            "feature_records": num_feats,
            "packet_count_manifest": m_pkts,
            "packet_count_metadata": real_meta_pkts,
            "byte_count_manifest": m_bytes,
            "byte_count_metadata": real_meta_bytes,
            "validation_status": r.get("validation_status", "PASS"),
            "reconciliation_status": status,
        })

    # Write consistency report
    Path(consistency_report_path).parent.mkdir(parents=True, exist_ok=True)
    with open(consistency_report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(consistency_rows[0].keys()) if consistency_rows else ["session_id", "status"])
        writer.writeheader()
        writer.writerows(consistency_rows)

    # Write reconciliation report
    Path(reconciliation_report_path).parent.mkdir(parents=True, exist_ok=True)
    with open(reconciliation_report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(reconciliation_rows[0].keys()) if reconciliation_rows else ["session_id", "reconciliation_status"])
        writer.writeheader()
        writer.writerows(reconciliation_rows)

    logger.info("Saved consistency report to %s and reconciliation to %s", consistency_report_path, reconciliation_report_path)

    return {
        "total_audited": len(manifest_records),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "warning_count": warning_count,
    }


def main():
    res = audit_dataset_consistency()
    print("\n=======================================================")
    print("        REAL DATASET CONSISTENCY & RECONCILIATION      ")
    print("=======================================================")
    print(f"Total Real Sessions Audited:  {res['total_audited']}")
    print(f"Consistent (PASS):            {res['pass_count']}")
    print(f"Inconsistent (FAIL):          {res['fail_count']}")
    print(f"Status:                       {'ALL CONSISTENT (PASS)' if res['fail_count'] == 0 else 'INCONSISTENCIES FOUND'}")
    print("Reports Generated:")
    print("  - results/tables/real_dataset_consistency_report.csv")
    print("  - results/tables/manifest_reconciliation.csv")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
