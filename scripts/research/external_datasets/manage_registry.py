"""
CLI Tool: Manage External Dataset Registry.

Usage:
    python scripts/research/external_datasets/manage_registry.py --list
    python scripts/research/external_datasets/manage_registry.py --info cesnet-tls22
    python scripts/research/external_datasets/manage_registry.py --export data/external_manifests/registry.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research.external_datasets.registry import (
    export_registry_to_json,
    get_dataset_metadata,
    list_registered_datasets,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="External Encrypted Traffic Dataset Registry Manager")
    parser.add_argument("--list", action="store_true", help="List all registered external datasets.")
    parser.add_argument("--info", type=str, help="Show detailed metadata for a specific dataset ID.")
    parser.add_argument("--export", type=str, help="Export entire registry to a JSON manifest file.")
    args = parser.parse_args()

    if args.list:
        datasets = list_registered_datasets()
        print("=" * 80)
        print(f"REGISTERED EXTERNAL DATASETS ({len(datasets)} datasets)")
        print("=" * 80)
        print(f"{'Dataset ID':<20} {'Format':<15} {'Version':<10} {'Est. Samples':<15} {'Official Name'}")
        print("-" * 80)
        for ds in datasets:
            samples_str = f"{ds.sample_count_estimate:,}" if ds.sample_count_estimate else "N/A"
            print(f"{ds.dataset_id:<20} {ds.file_format:<15} {ds.dataset_version:<10} {samples_str:<15} {ds.official_name[:30]}")
        print("=" * 80)
        return

    if args.info:
        ds = get_dataset_metadata(args.info)
        if not ds:
            print(f"Error: Dataset '{args.info}' not found in registry.")
            sys.exit(1)
        print("=" * 80)
        print(f"DATASET METADATA: {ds.dataset_id.upper()}")
        print("=" * 80)
        for k, v in ds.to_dict().items():
            if isinstance(v, (dict, list)):
                print(f"  {k}:")
                print(json.dumps(v, indent=4))
            else:
                print(f"  {k:<28}: {v}")
        print("=" * 80)
        return

    if args.export:
        export_registry_to_json(Path(args.export))
        print(f"Registry successfully exported to: {args.export}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
