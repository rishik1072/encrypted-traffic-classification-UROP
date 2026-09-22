"""
Capture Quality & Integrity Validator.

Evaluates captured sessions against minimum packet, byte, timing, and protocol constraints.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    is_valid: bool
    status: str  # "PASS" | "FAIL"
    reasons: List[str]
    packet_count: int
    byte_count: int
    flow_count: int
    duration: float


class CaptureValidator:
    def __init__(self, min_packets: int = 10, min_bytes: int = 500) -> None:
        self.min_packets = min_packets
        self.min_bytes = min_bytes

    def validate_metadata_file(self, metadata_path: str) -> ValidationResult:
        p = Path(metadata_path)
        if not p.exists():
            return ValidationResult(
                is_valid=False,
                status="FAIL",
                reasons=[f"Metadata file does not exist: {metadata_path}"],
                packet_count=0,
                byte_count=0,
                flow_count=0,
                duration=0.0,
            )

        with open(p, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))

        packet_count = len(reader)
        reasons: List[str] = []

        if packet_count < self.min_packets:
            reasons.append(f"Insufficient packet count: {packet_count} < {self.min_packets}")

        total_bytes = sum(int(r.get("packet_length", 0)) for r in reader)
        if total_bytes < self.min_bytes:
            reasons.append(f"Insufficient total bytes: {total_bytes} < {self.min_bytes}")

        # Timestamps
        timestamps = [float(r.get("timestamp", 0.0)) for r in reader if r.get("timestamp")]
        duration = 0.0
        if timestamps:
            duration = max(timestamps) - min(timestamps)
            if duration < 0:
                reasons.append("Negative capture duration observed (timestamp anomaly)")

        # Unique 5-tuple flow approximation
        flows = set()
        for r in reader:
            flows.add((r.get("protocol"), r.get("source_port"), r.get("destination_port")))
        flow_count = len(flows)

        is_valid = len(reasons) == 0
        return ValidationResult(
            is_valid=is_valid,
            status="PASS" if is_valid else "FAIL",
            reasons=reasons,
            packet_count=packet_count,
            byte_count=total_bytes,
            flow_count=flow_count,
            duration=duration,
        )
