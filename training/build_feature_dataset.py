"""
Tabular Feature Dataset Builder.

Processes extracted flow records or PCAPs directly through the FeatureExtractor,
producing a clean zero-payload statistical feature matrix for machine learning models.
Supports --origin {real, synthetic, all}.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

# Support high-volume flow packet arrays
try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2147483647)

from flows.flow_generator import Direction, Flow, FlowKey
from preprocessing.feature_extractor import FeatureExtractor
from training.build_flow_dataset import FlowDatasetBuilder

logger = logging.getLogger(__name__)


class FeatureDatasetBuilder:
    """
    Coordinates statistical feature extraction across flows and writes
    the zero-payload tabular ML dataset.
    """

    def __init__(self, config_path: str | Path = "config.yaml") -> None:
        self.config_path = Path(config_path)
        self.base_dir = self.config_path.parent
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config: Dict[str, Any] = yaml.safe_load(f)

        dataset_cfg = self.config.get("dataset", {})
        self.flow_input_path = self.base_dir / dataset_cfg.get("flow_output_path", "data/processed/flows/flows.csv")
        self.feature_output_path = self.base_dir / dataset_cfg.get("feature_output_path", "data/processed/features/features.csv")
        self.extractor = FeatureExtractor()

    def build_features_from_flows(
        self,
        flow_input_path: Optional[str | Path] = None,
        feature_output_path: Optional[str | Path] = None,
        origin_filter: str = "real",
    ) -> List[Dict[str, Any]]:
        """Reads flows CSV and extracts tabular zero-payload features."""
        if flow_input_path:
            in_path = Path(flow_input_path)
        else:
            if origin_filter == "real":
                in_path = self.base_dir / "data/processed/flows/flows_real.csv"
            elif origin_filter == "synthetic":
                in_path = self.base_dir / "data/processed/flows/flows_synthetic.csv"
            else:
                in_path = self.flow_input_path

        if feature_output_path:
            out_path = Path(feature_output_path)
        else:
            if origin_filter == "real":
                out_path = self.base_dir / "data/processed/features/features_real.csv"
            elif origin_filter == "synthetic":
                out_path = self.base_dir / "data/processed/features/features_synthetic.csv"
            else:
                out_path = self.feature_output_path

        out_path.parent.mkdir(parents=True, exist_ok=True)

        if not in_path.exists():
            raise FileNotFoundError(f"Flow dataset not found: {in_path}. Run build_flow_dataset first.")

        logger.info("Extracting tabular features from %s -> %s (origin=%s)", in_path, out_path, origin_filter)
        feature_rows: List[Dict[str, Any]] = []

        with open(in_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                flow = self._reconstruct_flow_from_row(row)
                feats = self.extractor.extract_features(flow)

                feature_row = {
                    "flow_id": row["flow_id"],
                    "file_id": row.get("file_id", row.get("session_id", "")),
                    "session_id": row.get("session_id", row.get("file_id", "")),
                    "data_origin": row.get("data_origin", origin_filter),
                    **feats,
                    "traffic_class": row["traffic_class"],
                }
                feature_rows.append(feature_row)

        if feature_rows:
            fieldnames = list(feature_rows[0].keys())
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(feature_rows)
            logger.info("Saved %d feature records to %s", len(feature_rows), out_path)
        else:
            logger.warning("No feature records generated for %s.", in_path)

        return feature_rows

    @staticmethod
    def _reconstruct_flow_from_row(row: Dict[str, Any]) -> Flow:
        """Reconstructs a Flow instance from serialized flow dataset row."""
        key = FlowKey(
            ip_a="0.0.0.0",  # Masked canonical dummy IP
            port_a=int(row["port_a"]),
            ip_b="0.0.0.0",
            port_b=int(row["port_b"]),
            protocol=row["protocol"],
        )
        flow = Flow(
            key=key,
            initiator_ip="0.0.0.0",
            initiator_port=int(row["initiator_port"]),
            start_time=float(row["start_time"]),
            last_seen=float(row["last_seen"]),
            tls_version=row.get("tls_version"),
            tls_cipher_suites_count=int(row.get("tls_cipher_suites_count", 0)),
            tls_extensions_count=int(row.get("tls_extensions_count", 0)),
        )

        timestamps = json.loads(row["packet_timestamps_json"])
        lengths = json.loads(row["packet_lengths_json"])
        directions_str = json.loads(row["packet_directions_json"])

        for t, l, d_name in zip(timestamps, lengths, directions_str):
            direction = Direction.FORWARD if d_name == "FORWARD" else Direction.BACKWARD
            flow.packet_records.append((float(t), int(l), direction))

        return flow


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
    parser = argparse.ArgumentParser(description="Generate tabular feature dataset.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--flow-input", default=None, help="Path to flows CSV")
    parser.add_argument("--output", default=None, help="Path to output features CSV")
    parser.add_argument("--origin", default="real", choices=["real", "synthetic", "all"], help="Dataset origin filter (default: real)")
    args = parser.parse_args()

    builder = FeatureDatasetBuilder(config_path=args.config)
    builder.build_features_from_flows(
        flow_input_path=args.flow_input,
        feature_output_path=args.output,
        origin_filter=args.origin,
    )


if __name__ == "__main__":
    main()
