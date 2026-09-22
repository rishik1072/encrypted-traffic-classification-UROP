"""
Dataset SHA-256 Hashing and Version Manifest Generator.

Computes cryptographic checksums for raw and processed dataset artifacts.
Outputs:
- results/tables/dataset_version_manifest.csv
"""

from __future__ import annotations

import csv
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def compute_file_sha256(file_path: str | Path) -> str:
    """Computes SHA-256 hex digest for a file."""
    p = Path(file_path)
    if not p.exists():
        return "FILE_NOT_FOUND"
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def generate_dataset_version_manifest(
    manifest_csv: str | Path = "data/dataset_manifest.csv",
    output_csv: str | Path = "results/tables/dataset_version_manifest.csv",
) -> List[Dict[str, Any]]:
    """Generates cryptographic manifest for all PCAP files and dataset tables."""
    m_path = Path(manifest_csv)
    out_path = Path(output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    if m_path.exists():
        with open(m_path, "r", encoding="utf-8") as f:
            manifest_rows = list(csv.DictReader(f))

        for r in manifest_rows:
            pcap_p = Path(r.get("pcap_path", ""))
            sha = compute_file_sha256(pcap_p) if pcap_p.exists() else "LOCAL_SYNTHETIC"
            rows.append({
                "dataset_id": r.get("dataset_id", "dataset_v1"),
                "file_id": r.get("file_id", "unknown"),
                "source": r.get("source", "local_controlled"),
                "hash_sha256": sha,
                "capture_date": r.get("capture_date", "2026-01-01"),
                "traffic_class": r.get("traffic_class", "Other"),
                "session_id": r.get("session_id", "sess_01"),
                "dataset_version": "v1.0.0",
            })

    if rows:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    logger.info("Saved dataset version manifest (%d records) to %s", len(rows), out_path)
    return rows


if __name__ == "__main__":
    generate_dataset_version_manifest()
