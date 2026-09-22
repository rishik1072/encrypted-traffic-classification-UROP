"""
Dataset Manifest Validator.

Performs strict, comprehensive schema and integrity verification on data/dataset_manifest.csv:
- Checks required columns across records
- Validates strict real vs synthetic enum constraints
- Enforces uniqueness of file_id and session_id
- Validates file paths and completeness of session metadata
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "file_id",
    "traffic_class",
    "data_origin",
    "capture_source",
    "raw_source_type",
    "raw_source_path",
    "validation_status",
]

REQUIRED_REAL_COLUMNS = [
    "session_id",
    "capture_date",
    "source",
    "environment_id",
    "device_id",
    "dataset_id",
    "capture_duration",
    "packet_count",
    "byte_count",
    "flow_count",
]


@dataclass
class ManifestValidationResult:
    is_valid: bool
    total_records: int
    real_records: int
    synthetic_records: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def validate_manifest(
    manifest_path: str | Path = "data/dataset_manifest.csv",
    base_dir: Optional[str | Path] = None,
) -> ManifestValidationResult:
    m_path = Path(manifest_path)
    root = Path(base_dir) if base_dir else m_path.parent.parent

    if not m_path.exists():
        return ManifestValidationResult(
            is_valid=False, total_records=0, real_records=0, synthetic_records=0,
            errors=[f"Manifest file not found: {m_path}"]
        )

    with open(m_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    errors: List[str] = []
    warnings: List[str] = []

    # Check header
    for req in REQUIRED_COLUMNS:
        if req not in fieldnames:
            errors.append(f"Manifest missing required column: '{req}'")

    seen_file_ids = set()
    seen_session_ids = set()
    real_count = 0
    synthetic_count = 0

    for idx, row in enumerate(rows, start=1):
        file_id = row.get("file_id", "")
        session_id = row.get("session_id", "")
        data_origin = row.get("data_origin", "")
        capture_source = row.get("capture_source", "")
        raw_source_type = row.get("raw_source_type", "")
        raw_source_path = row.get("raw_source_path", "")
        val_status = row.get("validation_status", "")
        source = row.get("source", "")

        # 1. file_id uniqueness and non-empty
        if not file_id:
            errors.append(f"Row {idx}: Missing file_id")
        elif file_id in seen_file_ids:
            errors.append(f"Row {idx}: Duplicate file_id '{file_id}'")
        else:
            seen_file_ids.add(file_id)

        # 2. session_id uniqueness
        if session_id:
            if session_id in seen_session_ids:
                errors.append(f"Row {idx}: Duplicate session_id '{session_id}'")
            else:
                seen_session_ids.add(session_id)

        # 3. Enum validations
        if data_origin not in ["real", "synthetic"]:
            errors.append(f"Row {idx} ({file_id}): Invalid data_origin '{data_origin}' (must be 'real' or 'synthetic')")

        if capture_source not in ["REAL_LIVE_CAPTURE", "SYNTHETIC_TEST"]:
            errors.append(f"Row {idx} ({file_id}): Invalid capture_source '{capture_source}'")

        if raw_source_type not in ["PCAP", "METADATA_CSV", "METADATA_PARQUET", "SYNTHETIC_FIXTURE"]:
            errors.append(f"Row {idx} ({file_id}): Invalid raw_source_type '{raw_source_type}'")

        if val_status not in ["PASS", "FAIL", "INVALID"]:
            errors.append(f"Row {idx} ({file_id}): Invalid validation_status '{val_status}'")

        # 4. Real capture specific strict checks
        if data_origin == "real":
            real_count += 1
            if capture_source != "REAL_LIVE_CAPTURE":
                errors.append(f"Row {idx} ({file_id}): Real origin must have capture_source=REAL_LIVE_CAPTURE, got '{capture_source}'")

            for req_field in REQUIRED_REAL_COLUMNS:
                val = row.get(req_field)
                if val is None or str(val).strip() == "":
                    errors.append(f"Row {idx} ({file_id}): Missing required real field '{req_field}'")

            if not raw_source_path:
                errors.append(f"Row {idx} ({file_id}): Missing raw_source_path")
            else:
                full_path = root / raw_source_path
                if not full_path.exists():
                    errors.append(f"Row {idx} ({file_id}): raw_source_path does not exist on disk: {raw_source_path}")

        elif data_origin == "synthetic":
            synthetic_count += 1

    is_valid = len(errors) == 0
    return ManifestValidationResult(
        is_valid=is_valid,
        total_records=len(rows),
        real_records=real_count,
        synthetic_records=synthetic_count,
        errors=errors,
        warnings=warnings,
    )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validate dataset manifest.")
    parser.add_argument("--manifest", default="data/dataset_manifest.csv", help="Path to manifest CSV")
    args = parser.parse_args()

    res = validate_manifest(args.manifest)
    print("\n=======================================================")
    print("             DATASET MANIFEST VALIDATION               ")
    print("=======================================================")
    print(f"Total Records:      {res.total_records}")
    print(f"Real Records:       {res.real_records}")
    print(f"Synthetic Records:  {res.synthetic_records}")
    print(f"Validation Status:  {'PASS' if res.is_valid else 'FAIL'}")
    print("-------------------------------------------------------")
    if res.errors:
        print("ERRORS FOUND:")
        for err in res.errors:
            print(f"  [X] {err}")
    else:
        print("All manifest records passed schema and integrity verification.")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
