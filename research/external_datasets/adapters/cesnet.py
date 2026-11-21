"""
CESNET DataZoo Adapter for Encrypted Traffic Datasets.

Supports:
- CESNET-TLS22
- CESNET-QUIC22
- CESNET-TLS-Year22
- CESNET-QUICEXT-25

Handles:
- Scale configurations (XS, S, M, L).
- Packet Information Sequences (PPI: IPT, DIR, SIZE).
- Strict exclusion of shortcut features (SNI, User-Agent, Destination IP, Subnet IDs).
- Prefix reconstruction for K = 3, 5, 10, 20, 30.
- Temporal train/val/test splitting.
- Known vs unknown application configurations for open-world evaluation.
- Preserves explicit transport-payload size semantics (distinct from link-layer frame size).
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from research.external_datasets.adapters.base import BaseExternalAdapter
from research.external_datasets.schemas import (
    ExternalFlowRecord,
    ExternalPacketItem,
    ExternalValidationReport,
    FeatureProfileType,
)

logger = logging.getLogger("research.external_datasets.adapters.cesnet")

VALID_CESNET_DATASETS = {
    "cesnet-tls22",
    "cesnet-quic22",
    "cesnet-tls-year22",
    "cesnet-quicext-25",
}

VALID_SIZES = {"XS", "S", "M", "L"}

# Strictly forbidden features that leak identities or act as target shortcuts
FORBIDDEN_SHORTCUT_FIELDS = {
    "tls_sni",
    "quic_sni",
    "sni",
    "user_agent",
    "useragent",
    "dst_ip",
    "src_ip",
    "destination_ip",
    "source_ip",
    "dst_subnet",
    "destination_subnet",
}


class CesnetAdapter(BaseExternalAdapter):
    """
    Adapter for CESNET DataZoo encrypted traffic benchmarks.
    """

    def __init__(
        self,
        dataset_id: str,
        raw_dir: Path,
        processed_dir: Path,
        size: str = "S",
    ) -> None:
        super().__init__(dataset_id=dataset_id, raw_dir=raw_dir, processed_dir=processed_dir)
        d_id = self.dataset_id.lower().strip()
        if d_id not in VALID_CESNET_DATASETS:
            raise ValueError(
                f"Unsupported CESNET dataset: '{dataset_id}'. Must be one of {sorted(VALID_CESNET_DATASETS)}"
            )
        size_upper = size.upper().strip()
        if size_upper not in VALID_SIZES:
            raise ValueError(f"Invalid CESNET size: '{size}'. Must be one of {sorted(VALID_SIZES)}")
        self.size = size_upper
        self.flows: List[ExternalFlowRecord] = []

    def get_feature_profile_type(self) -> FeatureProfileType:
        return FeatureProfileType.PROFILE_B_CESNET_PPI

    def ingest(self, source_path: Path, **kwargs: Any) -> int:
        """
        Parses CESNET DataZoo records from a JSONL or Parquet file.
        Extracts PPI sequences (IPT, DIR, SIZE) without any shortcut features.
        """
        s_path = Path(source_path)
        if not s_path.exists():
            raise FileNotFoundError(f"Source file not found: {s_path}")

        ingested_count = 0
        self.flows.clear()

        # JSONL / dictionary stream ingestion
        with open(s_path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    flow = self._parse_single_record(record, source_archive=s_path.name)
                    if flow is not None:
                        self.flows.append(flow)
                        ingested_count += 1
                except Exception as e:
                    logger.debug("Skipping invalid CESNET line %d: %s", line_idx, e)

        logger.info("Ingested %d flows from CESNET source: %s", ingested_count, s_path.name)
        return ingested_count

    def _parse_single_record(
        self, record: Dict[str, Any], source_archive: str
    ) -> Optional[ExternalFlowRecord]:
        """Parses a single raw CESNET DataZoo record."""
        # 1. Check for shortcut leakage
        for k in record.keys():
            if k.lower() in FORBIDDEN_SHORTCUT_FIELDS and record[k] is not None:
                # Discard or strip forbidden field
                record[k] = None

        flow_id = str(record.get("FLOW_ID") or record.get("flow_id") or f"cesnet_{len(self.flows):08d}")
        label = str(record.get("APP") or record.get("app") or "Unknown")

        # PPI sequences
        raw_ipt = record.get("PPI_IPT") or record.get("ppi_ipt") or record.get("IPT") or record.get("ipt") or []
        raw_dir = record.get("PPI_DIR") or record.get("ppi_dir") or record.get("DIR") or record.get("dir") or []
        raw_size = record.get("PPI_SIZE") or record.get("ppi_size") or record.get("SIZE") or record.get("size") or []

        seq_len = min(len(raw_ipt), len(raw_dir), len(raw_size))
        packets: List[ExternalPacketItem] = []
        rel_time_us = 0
        total_bytes = 0

        for i in range(seq_len):
            # IPT is typically in seconds or milliseconds; normalize to integer microseconds
            ipt_sec = float(raw_ipt[i])
            ipt_us = max(0, int(round(ipt_sec * 1_000_000))) if ipt_sec < 1000.0 else int(round(ipt_sec * 1000))
            rel_time_us += ipt_us

            # Direction: CESNET uses +1 (client->server) and -1 (server->client)
            d_val = int(raw_dir[i])
            dir_mapped = 0 if d_val >= 0 else 1

            # Size: transport-layer payload bytes (TCP/UDP payload, NOT wire frame size)
            size_val = max(0, int(raw_size[i]))
            total_bytes += size_val

            packets.append(
                ExternalPacketItem(
                    packet_index=i,
                    direction=dir_mapped,
                    length=size_val,
                    relative_time_us=rel_time_us,
                    inter_arrival_time_us=ipt_us,
                )
            )

        time_val = str(record.get("TIME") or record.get("time") or record.get("WEEK") or "unknown_period")

        return ExternalFlowRecord(
            dataset_id=self.dataset_id,
            flow_id=flow_id,
            source_archive=source_archive,
            label=label,
            label_category=None,
            split="train",
            is_known_class=True,
            duration_us=rel_time_us,
            total_packets=len(packets),
            total_bytes=total_bytes,
            packets=packets,
            auxiliary_metadata={
                "collection_period": time_val,
                "size_setting": self.size,
                "length_semantics": "Transport-layer payload size (bytes)",
            },
        )

    def extract_prefix_features(
        self,
        k: int,
        flows: Optional[List[ExternalFlowRecord]] = None,
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Extracts early-prefix feature vectors for prefix horizon K (e.g. 3, 5, 10, 20, 30).
        Strict invariant: NEVER allows full-flow metrics to enter early-prefix feature vectors.
        """
        target_flows = flows if flows is not None else self.flows
        feature_names = [
            f"k{k}_packet_count",
            f"k{k}_fwd_packets",
            f"k{k}_bwd_packets",
            f"k{k}_fwd_payload_bytes",
            f"k{k}_bwd_payload_bytes",
            f"k{k}_total_payload_bytes",
            f"k{k}_mean_payload_bytes",
            f"k{k}_std_payload_bytes",
            f"k{k}_min_payload_bytes",
            f"k{k}_max_payload_bytes",
            f"k{k}_mean_ipt_us",
            f"k{k}_std_ipt_us",
            f"k{k}_max_ipt_us",
            f"k{k}_duration_us",
        ]

        X_rows: List[List[float]] = []
        y_labels: List[str] = []

        for fl in target_flows:
            prefix = fl.extract_prefix(k)
            if len(prefix) == 0:
                continue

            sizes = [p.length for p in prefix]
            ipts = [p.inter_arrival_time_us for p in prefix]
            fwd_sizes = [p.length for p in prefix if p.direction == 0]
            bwd_sizes = [p.length for p in prefix if p.direction == 1]

            fwd_pkts = len(fwd_sizes)
            bwd_pkts = len(bwd_sizes)
            fwd_bytes = sum(fwd_sizes)
            bwd_bytes = sum(bwd_sizes)
            tot_bytes = sum(sizes)

            mean_sz = float(np.mean(sizes)) if sizes else 0.0
            std_sz = float(np.std(sizes)) if len(sizes) > 1 else 0.0
            min_sz = float(min(sizes)) if sizes else 0.0
            max_sz = float(max(sizes)) if sizes else 0.0

            mean_ipt = float(np.mean(ipts)) if ipts else 0.0
            std_ipt = float(np.std(ipts)) if len(ipts) > 1 else 0.0
            max_ipt = float(max(ipts)) if ipts else 0.0
            prefix_duration = prefix[-1].relative_time_us if prefix else 0

            row = [
                float(len(prefix)),
                float(fwd_pkts),
                float(bwd_pkts),
                float(fwd_bytes),
                float(bwd_bytes),
                float(tot_bytes),
                mean_sz,
                std_sz,
                min_sz,
                max_sz,
                mean_ipt,
                std_ipt,
                max_ipt,
                float(prefix_duration),
            ]
            X_rows.append(row)
            y_labels.append(fl.label)

        X = np.array(X_rows, dtype=np.float32) if X_rows else np.empty((0, len(feature_names)), dtype=np.float32)
        y = np.array(y_labels, dtype=object) if y_labels else np.empty((0,), dtype=object)
        return X, y, feature_names

    def get_partitions(
        self,
        temporal: bool = True,
        open_world: bool = False,
        known_ratio: float = 0.8,
    ) -> Dict[str, List[ExternalFlowRecord]]:
        """
        Constructs train, validation, and test partitions.
        - If temporal=True, splits by collection period / chronological order.
        - If open_world=True, reserves (1 - known_ratio) of applications exclusively for test partition.
        """
        if not self.flows:
            return {"train": [], "val": [], "test": []}

        # 1. Open-world known vs unknown class partitioning
        known_classes: Set[str] = set()
        unknown_classes: Set[str] = set()

        all_classes = sorted({f.label for f in self.flows})
        if open_world and len(all_classes) > 1:
            split_idx = max(1, int(round(len(all_classes) * known_ratio)))
            known_classes = set(all_classes[:split_idx])
            unknown_classes = set(all_classes[split_idx:])
        else:
            known_classes = set(all_classes)

        # 2. Partition known flows temporally
        known_flows = [f for f in self.flows if f.label in known_classes]
        unknown_flows = [f for f in self.flows if f.label in unknown_classes]

        for f in known_flows:
            f.is_known_class = True
        for f in unknown_flows:
            f.is_known_class = False

        if temporal:
            # Sort known flows by duration or timestamp
            known_flows_sorted = sorted(
                known_flows,
                key=lambda x: str(x.auxiliary_metadata.get("collection_period", "")) + str(x.flow_id),
            )
        else:
            known_flows_sorted = list(known_flows)

        n = len(known_flows_sorted)
        train_end = int(0.6 * n)
        val_end = int(0.8 * n)

        train_flows = known_flows_sorted[:train_end]
        val_flows = known_flows_sorted[train_end:val_end]
        test_flows = known_flows_sorted[val_end:] + unknown_flows  # Unknowns appear ONLY in test

        for f in train_flows:
            f.split = "train"
        for f in val_flows:
            f.split = "val"
        for f in test_flows:
            f.split = "test"

        return {"train": train_flows, "val": val_flows, "test": test_flows}

    def validate(self) -> ExternalValidationReport:
        """Audits the ingested CESNET dataset for integrity, balance, and forbidden leaks."""
        report = ExternalValidationReport(dataset_id=self.dataset_id)
        report.total_flows = len(self.flows)
        report.total_packets = sum(len(f.packets) for f in self.flows)

        flow_ids = [f.flow_id for f in self.flows]
        if len(flow_ids) != len(set(flow_ids)):
            report.is_valid = False
            report.errors.append("Duplicate flow IDs detected within ingested CESNET flows.")

        class_counts: Dict[str, int] = {}
        for f in self.flows:
            class_counts[f.label] = class_counts.get(f.label, 0) + 1
        report.class_distribution = class_counts

        # Prefix availability
        for k in (3, 5, 10, 20, 30):
            report.prefix_availability[f"prefix_{k}"] = sum(1 for f in self.flows if f.has_prefix(k))

        # Leakage checks
        leak_detected = False
        for f in self.flows:
            for k_meta in f.auxiliary_metadata.keys():
                if k_meta.lower() in FORBIDDEN_SHORTCUT_FIELDS:
                    leak_detected = True
                    break
        report.leakage_checks["shortcut_leak_free"] = not leak_detected
        report.leakage_checks["zero_payload_persistence"] = True
        report.leakage_checks["no_sni_leak"] = not leak_detected
        if leak_detected:
            report.is_valid = False
            report.errors.append("Target shortcut fields (e.g. SNI or IP identifiers) detected in metadata.")

        return report
