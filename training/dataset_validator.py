"""
Dataset Manifest Validator Module.

Validates integrity, file existence, traffic class compliance, uniqueness,
and completeness of records in dataset_manifest.csv.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("dataset_validator")


@dataclass
class ManifestValidationResult:
    """Encapsulates validation outcome for the dataset manifest."""
    is_valid: bool
    total_records: int
    valid_records: int
    invalid_records: int
    class_counts: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def summary_text(self) -> str:
        lines = [
            "## Dataset Validation",
            "",
            f"PCAP files: {self.total_records}",
            f"Valid: {self.valid_records}",
            f"Invalid: {self.invalid_records}",
            "",
        ]
        for cls_name, count in sorted(self.class_counts.items()):
            lines.append(f"{cls_name}: {count}")
        if self.errors:
            lines.append("\nErrors:")
            for err in self.errors:
                lines.append(f"  - {err}")
        return "\n".join(lines)


class DatasetValidator:
    """
    Validates manifest structure, file existence, and label consistency
    against project configuration.
    """

    REQUIRED_FIELDS = {
        "file_id",
        "pcap_path",
        "traffic_class",
        "source",
        "capture_date",
        "duration_seconds",
    }

    def __init__(
        self,
        manifest_path: str | Path,
        allowed_classes: Optional[List[str]] = None,
        base_dir: Optional[str | Path] = None,
    ) -> None:
        self.manifest_path = Path(manifest_path)
        self.base_dir = Path(base_dir) if base_dir else self.manifest_path.parent.parent
        self.allowed_classes = set(allowed_classes) if allowed_classes else self._load_classes_from_config()

    def _load_classes_from_config(self) -> Set[str]:
        cfg_path = self.base_dir / "config.yaml"
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                return set(cfg.get("traffic_classes", []))
        return {"Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"}

    def validate(self, check_file_existence: bool = True) -> ManifestValidationResult:
        """Performs comprehensive validation of the manifest file."""
        if not self.manifest_path.exists():
            return ManifestValidationResult(
                is_valid=False,
                total_records=0,
                valid_records=0,
                invalid_records=0,
                errors=[f"Manifest file not found: {self.manifest_path}"],
            )

        total = 0
        valid = 0
        invalid = 0
        errors: List[str] = []
        warnings: List[str] = []
        class_counts: Dict[str, int] = Counter()
        seen_file_ids: Set[str] = set()

        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = set(reader.fieldnames or [])
                missing_cols = self.REQUIRED_FIELDS - fieldnames
                if missing_cols:
                    errors.append(f"Manifest missing required column(s): {', '.join(sorted(missing_cols))}")
                    return ManifestValidationResult(
                        is_valid=False,
                        total_records=0,
                        valid_records=0,
                        invalid_records=0,
                        errors=errors,
                    )

                for row_idx, row in enumerate(reader, start=2):
                    total += 1
                    row_errors: List[str] = []
                    file_id = row.get("file_id", "").strip()
                    pcap_rel = row.get("pcap_path", "").strip()
                    traffic_class = row.get("traffic_class", "").strip()

                    # 1. Check blank values
                    if not file_id:
                        row_errors.append(f"Row {row_idx}: 'file_id' is empty")
                    if not pcap_rel:
                        row_errors.append(f"Row {row_idx}: 'pcap_path' is empty")
                    if not traffic_class:
                        row_errors.append(f"Row {row_idx}: 'traffic_class' is empty")

                    # 2. Duplicate file ID check
                    if file_id in seen_file_ids:
                        row_errors.append(f"Row {row_idx}: duplicate file_id '{file_id}'")
                    seen_file_ids.add(file_id)

                    # 3. Traffic class membership check
                    if traffic_class and traffic_class not in self.allowed_classes:
                        row_errors.append(
                            f"Row {row_idx}: traffic_class '{traffic_class}' is invalid. "
                            f"Must be one of {sorted(self.allowed_classes)}"
                        )

                    # 4. File existence check
                    if check_file_existence and pcap_rel:
                        full_pcap_path = self.base_dir / pcap_rel
                        if not full_pcap_path.exists():
                            row_errors.append(f"Row {row_idx} ({file_id}): PCAP not found at '{pcap_rel}'")

                    if row_errors:
                        invalid += 1
                        errors.extend(row_errors)
                    else:
                        valid += 1
                        class_counts[traffic_class] += 1

        except Exception as exc:
            errors.append(f"Failed to read manifest file: {exc}")
            return ManifestValidationResult(
                is_valid=False,
                total_records=total,
                valid_records=valid,
                invalid_records=invalid,
                errors=errors,
            )

        is_valid = len(errors) == 0 and total > 0
        return ManifestValidationResult(
            is_valid=is_valid,
            total_records=total,
            valid_records=valid,
            invalid_records=invalid,
            class_counts=dict(class_counts),
            errors=errors,
            warnings=warnings,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate dataset manifest.")
    parser.add_argument(
        "--manifest",
        default="data/dataset_manifest.csv",
        help="Path to dataset_manifest.csv",
    )
    parser.add_argument(
        "--ignore-missing-pcaps",
        action="store_true",
        help="Validate metadata only without checking if PCAP files exist on disk",
    )
    args = parser.parse_args()

    validator = DatasetValidator(manifest_path=args.manifest)
    res = validator.validate(check_file_existence=not args.ignore_missing_pcaps)
    print(res.summary_text())

    if not res.is_valid:
        sys.exit(1)


if __name__ == "__main__":
    main()
