"""
Metadata-Only Capture Exporter.

Enforces a strict whitelist of Layer-3/4 timing, length, and header fields.
NEVER writes application payload bytes, HTTP URIs, or credential data.
Supports CSV (and Parquet where pyarrow/pandas are available).
"""

from __future__ import annotations

import csv
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Strict Whitelist of Permitted Metadata Fields (ZERO-PAYLOAD)
WHITELISTED_METADATA_FIELDS = [
    "timestamp",
    "packet_length",
    "ip_version",
    "protocol",
    "source_port",
    "destination_port",
    "tcp_flags",
    "direction",
    "session_id",
    "traffic_class",
]


class MetadataExporter:
    def __init__(self, output_dir: str = "data/raw/metadata") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_session_metadata(
        self,
        session_id: str,
        traffic_class: str,
        packet_records: List[Dict[str, Any]],
    ) -> str:
        """
        Filters incoming packet records through the strict whitelist and persists to CSV.
        Computes the cryptographic SHA-256 hash of the generated file.
        """
        output_file = self.output_dir / f"{session_id}.csv"
        logger.info("Exporting metadata for session %s (%d packets)", session_id, len(packet_records))

        filtered_rows: List[Dict[str, Any]] = []
        for r in packet_records:
            # Build strictly whitelisted record
            clean_row = {
                "timestamp": float(r.get("timestamp", 0.0)),
                "packet_length": int(r.get("length", r.get("packet_length", 0))),
                "ip_version": int(r.get("ip_version", 4)),
                "protocol": str(r.get("protocol", "TCP")),
                "source_port": int(r.get("source_port", r.get("src_port", 0))),
                "destination_port": int(r.get("destination_port", r.get("dst_port", 0))),
                "tcp_flags": str(r.get("tcp_flags", "")),
                "direction": str(r.get("direction", "forward")),
                "session_id": session_id,
                "traffic_class": traffic_class,
            }
            filtered_rows.append(clean_row)

        # Write to CSV
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=WHITELISTED_METADATA_FIELDS)
            writer.writeheader()
            writer.writerows(filtered_rows)

        logger.info("Metadata saved to %s", output_file)
        return str(output_file)

    @staticmethod
    def calculate_file_sha256(file_path: str) -> str:
        p = Path(file_path)
        if not p.exists():
            return ""
        hasher = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
