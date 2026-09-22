"""
Bidirectional Flow Dataset Builder.

Processes raw inputs (PCAPs, metadata CSVs, or synthetic fixtures) registered in
data/dataset_manifest.csv via PacketSource abstractions, aggregates packets into
bidirectional 5-tuple flows, and exports intermediate flow datasets.
Supports --origin {real, synthetic, all}.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from capture.packet_source import PacketSource, create_packet_source
from flows.flow_generator import Flow, FlowGenerator

logger = logging.getLogger(__name__)


class FlowDatasetBuilder:
    """
    Ingests packet sources from dataset manifest, processes them with FlowGenerator,
    and assigns authoritative labels to all child flows.
    """

    def __init__(self, config_path: str | Path = "config.yaml") -> None:
        self.config_path = Path(config_path)
        self.base_dir = self.config_path.parent
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config: Dict[str, Any] = yaml.safe_load(f)

        flow_cfg = self.config.get("flows", {})
        self.idle_timeout = float(flow_cfg.get("idle_timeout_seconds", 120.0))
        self.active_timeout = float(flow_cfg.get("active_timeout_seconds", 1800.0))
        self.min_packets = int(flow_cfg.get("min_packets_for_classification", 3))

        dataset_cfg = self.config.get("dataset", {})
        self.manifest_path = self.base_dir / dataset_cfg.get("manifest_path", "data/dataset_manifest.csv")
        self.default_output_path = self.base_dir / dataset_cfg.get("flow_output_path", "data/processed/flows/flows.csv")

    def build_dataset_from_manifest(
        self,
        manifest_path: Optional[str | Path] = None,
        output_path: Optional[str | Path] = None,
        origin_filter: str = "real",  # "real" | "synthetic" | "all"
        synthetic_packet_source: Optional[Dict[str, List[Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Processes registered records matching origin_filter and exports tabular flow dataset.
        """
        manifest_file = Path(manifest_path) if manifest_path else self.manifest_path
        
        # Determine output destination based on origin
        if output_path:
            dest_file = Path(output_path)
        else:
            if origin_filter == "real":
                dest_file = self.base_dir / "data/processed/flows/flows_real.csv"
            elif origin_filter == "synthetic":
                dest_file = self.base_dir / "data/processed/flows/flows_synthetic.csv"
            else:
                dest_file = self.default_output_path

        dest_file.parent.mkdir(parents=True, exist_ok=True)

        if not manifest_file.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_file}")

        logger.info("Building flow dataset from manifest: %s (origin_filter=%s)", manifest_file, origin_filter)
        all_flow_records: List[Dict[str, Any]] = []

        with open(manifest_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                file_id = row.get("file_id", "")
                session_id = row.get("session_id", file_id)
                traffic_class = row.get("traffic_class", "")
                data_origin = row.get("data_origin", "synthetic")
                capture_source = row.get("capture_source", "SYNTHETIC_TEST")
                val_status = row.get("validation_status", "PASS")

                # Filter by origin if no explicit synthetic_packet_source provided
                if not synthetic_packet_source and origin_filter != "all" and data_origin != origin_filter:
                    continue

                # For real data, enforce PASS status
                if not synthetic_packet_source and origin_filter == "real" and val_status != "PASS":
                    logger.warning("Skipping unvalidated real session: %s", session_id)
                    continue

                # Determine raw source type & path
                raw_type = row.get("raw_source_type")
                raw_path = row.get("raw_source_path") or row.get("metadata_path") or row.get("pcap_path")

                if not raw_type:
                    if row.get("metadata_path"):
                        raw_type = "METADATA_CSV"
                        raw_path = row.get("metadata_path")
                    elif row.get("pcap_path"):
                        raw_type = "PCAP"
                        raw_path = row.get("pcap_path")
                    else:
                        raw_type = "SYNTHETIC_FIXTURE"

                # Validate label
                if not traffic_class or traffic_class not in self.config.get("traffic_classes", []):
                    logger.warning("Skipping %s with unconfigured traffic class '%s'", file_id, traffic_class)
                    continue

                # Check if injected synthetic packet source provided (for tests)
                if synthetic_packet_source and file_id in synthetic_packet_source:
                    class DirectSyntheticSource(PacketSource):
                        def __init__(self, pkts): self.pkts = pkts
                        def read_packets(self): yield from self.pkts

                    source = DirectSyntheticSource(synthetic_packet_source[file_id])
                else:
                    try:
                        source = create_packet_source(
                            raw_source_type=raw_type,
                            raw_source_path=str(self.base_dir / raw_path) if raw_path else "",
                            traffic_class=traffic_class,
                        )
                    except Exception as e:
                        logger.error("Source validation failed for file_id=%s, path=%s: %s", file_id, raw_path, e)
                        continue

                flows_for_file = self.process_source(
                    file_id=file_id,
                    session_id=session_id,
                    packet_source=source,
                    traffic_class=traffic_class,
                    data_origin=data_origin,
                )
                all_flow_records.extend(flows_for_file)

        # Write to CSV
        if all_flow_records:
            fieldnames = list(all_flow_records[0].keys())
            with open(dest_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_flow_records)
            logger.info("Saved %d flow records to %s", len(all_flow_records), dest_file)
        else:
            logger.warning("No flow records generated for origin_filter=%s.", origin_filter)

        return all_flow_records

    def process_source(
        self,
        file_id: str,
        session_id: str,
        packet_source: PacketSource,
        traffic_class: str,
        data_origin: str = "real",
    ) -> List[Dict[str, Any]]:
        """Processes one PacketSource, aggregates packets into bidirectional flows, and assigns labels."""
        generator = FlowGenerator(
            idle_timeout=self.idle_timeout,
            active_timeout=self.active_timeout,
        )

        completed_flows: List[Flow] = []

        try:
            for pkt in packet_source.read_packets():
                expired = generator.process_packet(pkt)
                if expired:
                    completed_flows.append(expired)
        finally:
            packet_source.close()

        # Flush remaining active flows
        completed_flows.extend(generator.flush_all())

        flow_records: List[Dict[str, Any]] = []
        for idx, flow in enumerate(completed_flows):
            if flow.total_packets < self.min_packets:
                continue

            flow_id = f"{session_id}_flow_{idx:05d}"
            timestamps = [r[0] for r in flow.packet_records]
            lengths = [r[1] for r in flow.packet_records]
            directions = [r[2].name for r in flow.packet_records]
            byte_count = sum(lengths)

            record = {
                "flow_id": flow_id,
                "file_id": file_id,
                "session_id": session_id,
                "data_origin": data_origin,
                "start_time": flow.start_time,
                "last_seen": flow.last_seen,
                "duration": round(flow.duration, 4),
                "protocol": flow.key.protocol,
                "initiator_port": flow.initiator_port,
                "port_a": flow.key.port_a,
                "port_b": flow.key.port_b,
                "total_packets": flow.total_packets,
                "total_bytes": byte_count,
                "packet_timestamps_json": json.dumps(timestamps),
                "packet_lengths_json": json.dumps(lengths),
                "packet_directions_json": json.dumps(directions),
                "tls_version": flow.tls_version or "UNKNOWN",
                "tls_cipher_suites_count": flow.tls_cipher_suites_count or 0,
                "tls_extensions_count": flow.tls_extensions_count or 0,
                "tls_sni_present": 1 if flow.tls_sni else 0,
                "traffic_class": traffic_class,
            }
            flow_records.append(record)

        return flow_records


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
    parser = argparse.ArgumentParser(description="Generate flow dataset from dataset manifest.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--manifest", default=None, help="Optional custom manifest path")
    parser.add_argument("--output", default=None, help="Optional custom flow output path")
    parser.add_argument("--origin", default="real", choices=["real", "synthetic", "all"], help="Dataset origin filter (default: real)")
    args = parser.parse_args()

    builder = FlowDatasetBuilder(config_path=args.config)
    builder.build_dataset_from_manifest(
        manifest_path=args.manifest,
        output_path=args.output,
        origin_filter=args.origin,
    )


if __name__ == "__main__":
    main()
