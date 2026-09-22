"""
Research-Integrity Verification Module.

Enforces strict empirical standards for genuine live traffic captures:
- Live sniff actually executed without adapter errors
- Packet count >= configured minimum
- Non-zero capture duration
- Zero synthetic packet generation
- capture_source == REAL_LIVE_CAPTURE
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class IntegrityReport:
    is_valid: bool
    status: str  # "VALID" | "INVALID"
    reasons: List[str]


def validate_real_capture(
    session_data: Dict[str, Any],
    min_packets: int = 10,
    min_bytes: int = 500,
) -> IntegrityReport:
    reasons: List[str] = []

    # 1. Verify Capture Source
    capture_source = session_data.get("capture_source", "")
    if capture_source != "REAL_LIVE_CAPTURE":
        reasons.append(f"Invalid capture source: '{capture_source}' (Must be 'REAL_LIVE_CAPTURE')")

    # 2. Check for synthetic markers
    if session_data.get("is_synthetic", False) or session_data.get("synthetic_fallback", False):
        reasons.append("Synthetic packet generator was invoked during a real collection session")

    # 3. Check for adapter error codes
    error_code = session_data.get("error_code")
    if error_code:
        reasons.append(f"Capture encountered adapter error: {error_code} ({session_data.get('error_message')})")

    # 4. Packet & Byte Thresholds
    packet_count = int(session_data.get("packet_count", 0))
    if packet_count < min_packets:
        reasons.append(f"Packet count below minimum threshold: {packet_count} < {min_packets}")

    byte_count = int(session_data.get("byte_count", 0))
    if byte_count < min_bytes:
        reasons.append(f"Byte count below minimum threshold: {byte_count} < {min_bytes}")

    # 5. Duration
    duration = float(session_data.get("duration", 0.0))
    if duration <= 0.0:
        reasons.append(f"Invalid capture duration: {duration:.2f}s")

    is_valid = len(reasons) == 0
    return IntegrityReport(
        is_valid=is_valid,
        status="VALID" if is_valid else "INVALID",
        reasons=reasons,
    )
