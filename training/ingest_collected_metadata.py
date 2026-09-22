"""
Metadata Dataset Ingestion Pipeline.

Bridges collected real metadata files to the existing FlowGenerator and FeatureExtractor.
Ensures zero duplication of feature calculation logic.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List

from capture.packet_capture import RawPacketMetadata
from flows.flow_generator import FlowGenerator
from preprocessing.feature_extractor import FeatureExtractor

logger = logging.getLogger(__name__)


def ingest_metadata_file(
    metadata_csv_path: str,
    output_flows_csv: str = "data/processed/flows/flows_real.csv",
    output_features_csv: str = "data/processed/features/features_real.csv",
) -> int:
    meta_p = Path(metadata_csv_path)
    if not meta_p.exists():
        logger.error("Metadata file not found: %s", metadata_csv_path)
        return 0

    with open(meta_p, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    if not reader:
        return 0

    traffic_class = reader[0].get("traffic_class", "Other")

    # 1. Feed packets to existing FlowGenerator
    generator = FlowGenerator(idle_timeout=5.0, active_timeout=30.0)
    completed_flows = []

    for r in reader:
        pkt = RawPacketMetadata(
            timestamp=float(r.get("timestamp", 0.0)),
            src_ip="192.168.1.100",  # Anonymized synthetic endpoint
            dst_ip="1.1.1.1",
            src_port=int(r.get("source_port", 0)),
            dst_port=int(r.get("destination_port", 0)),
            protocol=r.get("protocol", "TCP"),
            length=int(r.get("packet_length", 0)),
        )
        flushed = generator.process_packet(pkt)
        if flushed:
            completed_flows.append(flushed)

    completed_flows.extend(generator.flush_all())

    # 2. Extract features using existing FeatureExtractor
    extractor = FeatureExtractor()
    feature_records: List[Dict[str, Any]] = []

    for flow in completed_flows:
        row = extractor.extract_features(flow)
        row["traffic_class"] = traffic_class
        feature_records.append(row)

    # 3. Append to real features CSV
    out_feat_p = Path(output_features_csv)
    out_feat_p.parent.mkdir(parents=True, exist_ok=True)
    file_exists = out_feat_p.exists()

    if feature_records:
        with open(out_feat_p, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(feature_records[0].keys()))
            if not file_exists:
                writer.writeheader()
            writer.writerows(feature_records)

    logger.info("Ingested %d flows / %d feature records from %s", len(completed_flows), len(feature_records), metadata_csv_path)
    return len(feature_records)
