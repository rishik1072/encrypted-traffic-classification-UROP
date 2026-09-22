"""
Explicit Synthetic Capture Generator for Tests and CI.

Creates synthetic test fixtures for unit tests and pipeline validation.
Clearly marks all records with data_origin = "synthetic" and capture_source = "SYNTHETIC_TEST".
NEVER modifies or increments the real dataset collection counts.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from capture.metadata_exporter import MetadataExporter
from capture.session_manager import CollectionSession, SessionState

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("generate_synthetic")


def generate_synthetic_capture(
    traffic_class: str = "Web",
    packet_count: int = 50,
    output_dir: str = "data/raw/metadata",
    manifest_path: str = "data/dataset_manifest.csv",
) -> str:
    session = CollectionSession.create(
        traffic_class=traffic_class,
        capture_source="SYNTHETIC_TEST",
        notes="Synthetic test fixture for CI validation",
        manifest_path=manifest_path,
    )
    session.is_synthetic = True

    # Generate synthetic zero-payload packets
    base_t = time.time()
    packets = [
        {
            "timestamp": base_t + i * 0.1,
            "length": 500 + (i * 10),
            "ip_version": 4,
            "protocol": "TCP",
            "source_port": 50000 + (i % 5),
            "destination_port": 443,
            "tcp_flags": "ACK",
            "direction": "forward" if i % 2 == 0 else "backward",
        }
        for i in range(packet_count)
    ]

    exporter = MetadataExporter(output_dir=output_dir)
    meta_file = exporter.export_session_metadata(session.session_id, traffic_class, packets)
    session.metadata_path = meta_file
    session.sha256 = exporter.calculate_file_sha256(meta_file)
    session.packet_count = len(packets)
    session.byte_count = sum(p["length"] for p in packets)
    session.flow_count = 5
    session.transition_to(SessionState.VALIDATED)

    # Register in manifest as SYNTHETIC_TEST
    with open(manifest_path, "a", newline="", encoding="utf-8") as f:
        fields = [
            "file_id", "pcap_path", "metadata_path", "traffic_class", "source", "capture_date",
            "session_id", "environment_id", "device_id", "dataset_id", "capture_duration",
            "packet_count", "byte_count", "flow_count", "validation_status", "data_origin",
            "capture_source", "notes"
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writerow({
            "file_id": f"synth_{session.session_id}",
            "pcap_path": "",
            "metadata_path": session.metadata_path,
            "traffic_class": session.traffic_class,
            "source": "synthetic_generator",
            "capture_date": time.strftime("%Y-%m-%d"),
            "session_id": session.session_id,
            "environment_id": session.environment_id,
            "device_id": session.device_id,
            "dataset_id": session.dataset_id,
            "capture_duration": 5.0,
            "packet_count": session.packet_count,
            "byte_count": session.byte_count,
            "flow_count": session.flow_count,
            "validation_status": "PASS",
            "data_origin": "synthetic",
            "capture_source": "SYNTHETIC_TEST",
            "notes": session.notes,
        })

    logger.info("Generated synthetic test fixture: %s (%s)", session.session_id, meta_file)
    return meta_file


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic test fixtures.")
    parser.add_argument("--class", dest="traffic_class", default="Web", choices=["Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"])
    parser.add_argument("--packets", type=int, default=50)
    args = parser.parse_args()

    generate_synthetic_capture(traffic_class=args.traffic_class, packet_count=args.packets)


if __name__ == "__main__":
    main()
