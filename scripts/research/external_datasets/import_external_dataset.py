"""
CLI Tool: Ingest and Validate External Encrypted Traffic Datasets.

Usage:
    python scripts/research/external_datasets/import_external_dataset.py --dataset cesnet-tls22 --source data/external_raw/cesnet-tls22/data.jsonl
    python scripts/research/external_datasets/import_external_dataset.py --dataset cipherspectrum --source data/external_raw/cipherspectrum/
    python scripts/research/external_datasets/import_external_dataset.py --dataset iscxvpn2016 --source data/external_raw/iscxvpn2016/
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research.external_datasets.adapters.cesnet import CesnetAdapter
from research.external_datasets.adapters.cipherspectrum import CipherSpectrumAdapter
from research.external_datasets.adapters.iscxvpn2016 import IscxVpn2016Adapter
from research.external_datasets.registry import get_dataset_metadata
from research.external_datasets.validator import ExternalDatasetValidator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("import_external_dataset")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest and Validate External Dataset")
    parser.add_argument("--dataset", type=str, required=True, help="Dataset ID (e.g. cesnet-tls22, cipherspectrum, iscxvpn2016)")
    parser.add_argument("--source", type=str, required=True, help="Path to raw source file or directory")
    parser.add_argument("--size", type=str, default="S", help="Scale setting for CESNET datasets (XS, S, M, L)")
    parser.add_argument("--raw-dir", type=str, default="data/external_raw", help="Directory for raw archives")
    parser.add_argument("--processed-dir", type=str, default="data/external_processed", help="Directory for processed output")
    args = parser.parse_args()

    d_id = args.dataset.lower().strip()
    meta = get_dataset_metadata(d_id)
    if not meta:
        logger.error("Unknown dataset ID: '%s'. Check registry.", d_id)
        sys.exit(1)

    raw_path = Path(args.raw_dir) / d_id
    proc_path = Path(args.processed_dir) / d_id
    src_path = Path(args.source)

    if not src_path.exists():
        logger.error("Source path does not exist: %s", src_path)
        sys.exit(1)

    # Select adapter
    if d_id.startswith("cesnet"):
        adapter = CesnetAdapter(dataset_id=d_id, raw_dir=raw_path, processed_dir=proc_path, size=args.size)
    elif d_id == "cipherspectrum":
        adapter = CipherSpectrumAdapter(raw_dir=raw_path, processed_dir=proc_path)
    elif d_id == "iscxvpn2016":
        adapter = IscxVpn2016Adapter(raw_dir=raw_path, processed_dir=proc_path)
    else:
        logger.error("No adapter available for dataset: %s", d_id)
        sys.exit(1)

    logger.info("Ingesting %s using %s...", d_id, adapter.__class__.__name__)
    count = adapter.ingest(src_path)
    logger.info("Ingestion completed: %d flows parsed.", count)

    # Partitioning & Validation
    partitions = adapter.get_partitions()
    validator = ExternalDatasetValidator(dataset_id=d_id)
    report = validator.validate_dataset(flows=adapter.flows, partitions=partitions)

    print("\n" + "=" * 70)
    print(f"VALIDATION REPORT: {d_id.upper()}")
    print("=" * 70)
    print(f"  Valid Dataset      : {report.is_valid}")
    print(f"  Total Flows        : {report.total_flows}")
    print(f"  Total Packets      : {report.total_packets}")
    print(f"  Classes ({len(report.class_distribution)})   : {dict(list(report.class_distribution.items())[:5])}...")
    print(f"  Prefix Availability: {report.prefix_availability}")
    print(f"  Leakage Checks     : {report.leakage_checks}")
    if report.warnings:
        print("  Warnings:")
        for w in report.warnings:
            print(f"    - [WARN] {w}")
    if report.errors:
        print("  Errors:")
        for e in report.errors:
            print(f"    - [ERROR] {e}")
    print("=" * 70 + "\n")

    # Save validation report
    val_out = proc_path / "validation_report.json"
    val_out.parent.mkdir(parents=True, exist_ok=True)
    with open(val_out, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)
    logger.info("Saved validation report to: %s", val_out)


if __name__ == "__main__":
    main()
