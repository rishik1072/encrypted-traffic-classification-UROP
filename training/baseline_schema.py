"""
Baseline Feature Schema Exporter.

Programmatically reads the active 21-feature schema from realtime.schema and config.yaml
and generates results/tables/baseline_feature_schema.csv.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List
import yaml

from realtime.schema import CANONICAL_NUMERICAL_FEATURES

logger = logging.getLogger(__name__)

FEATURE_DESCRIPTIONS: Dict[str, str] = {
    "flow_duration": "Total active duration of bidirectional session in seconds",
    "forward_packet_count": "Total packet count transmitted from initiator to receiver",
    "backward_packet_count": "Total packet count transmitted from receiver to initiator",
    "total_packet_count": "Sum of forward and backward packets in flow",
    "forward_bytes": "Total payload and header bytes in forward direction",
    "backward_bytes": "Total payload and header bytes in backward direction",
    "total_bytes": "Sum of bidirectional transmitted bytes",
    "avg_packet_size": "Mean size of all packets in the flow in bytes",
    "min_packet_size": "Minimum packet size observed in flow in bytes",
    "max_packet_size": "Maximum packet size observed in flow in bytes",
    "packet_size_variance": "Statistical variance of packet sizes",
    "mean_iat": "Mean inter-arrival time between consecutive packets (seconds)",
    "median_iat": "Median inter-arrival time between consecutive packets",
    "iat_std": "Standard deviation of packet inter-arrival times",
    "min_iat": "Minimum observed inter-arrival time (seconds)",
    "max_iat": "Maximum observed inter-arrival time (seconds)",
    "fwd_bwd_packet_ratio": "Ratio of forward packet count to backward packet count",
    "fwd_bwd_byte_ratio": "Ratio of forward byte volume to backward byte volume",
    "burst_count": "Number of consecutive transmission bursts (IAT < threshold)",
    "avg_burst_bytes": "Mean volume in bytes per transmission burst",
    "avg_burst_packets": "Mean packet count per transmission burst",
}


def export_baseline_feature_schema(
    output_path: str | Path = "results/tables/baseline_feature_schema.csv",
) -> List[Dict[str, Any]]:
    """Exports the authoritative 21 baseline feature schema table."""
    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    records: List[Dict[str, Any]] = []
    for feat in CANONICAL_NUMERICAL_FEATURES:
        rec = {
            "feature_name": feat,
            "feature_type": "Numerical (float/int)",
            "description": FEATURE_DESCRIPTIONS.get(feat, "Statistical traffic metadata"),
            "available_realtime": "YES",
            "source_module": "preprocessing.feature_extractor",
        }
        records.append(rec)

    with open(dest, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["feature_name", "feature_type", "description", "available_realtime", "source_module"],
        )
        writer.writeheader()
        writer.writerows(records)

    logger.info("Saved baseline feature schema table (%d features) to %s", len(records), dest)
    return records


if __name__ == "__main__":
    export_baseline_feature_schema()
