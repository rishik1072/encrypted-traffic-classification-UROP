"""
Dashboard Schema & Prediction Data Normalizer / Validator.

Provides canonical prediction record schema, type casting, legacy record
adapters, and robust confidence parsing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import time
from typing import Any, Dict, List, Optional, Tuple, Union

VALID_PREDICTION_STATES = {
    "KNOWN_CLASS",
    "LOW_CONFIDENCE",
    "UNKNOWN",
    "INSUFFICIENT_EVIDENCE",
    "FLOW_COMPLETED",
    "PIPELINE_DEGRADED",
}

NON_NUMERIC_CLASS_STRINGS = {
    "web",
    "video",
    "messaging",
    "voip",
    "file transfer",
    "other",
    "bulk_streaming",
    "interactive",
    "unknown",
    "—",
    "-",
    "none",
    "null",
    "nan",
}


@dataclass
class CanonicalPredictionRecord:
    """
    Canonical dashboard prediction record schema matching real-time architecture.
    """
    timestamp: str  # string formatted or iso datetime
    flow_id: str
    model_id: str
    feature_profile: str
    predicted_family: str  # Interactive, Bulk_Streaming, Other, UNKNOWN, or "—"
    predicted_class: str   # Messaging, Video, Web, VoIP, File Transfer, Other, or "—"
    confidence: Optional[float]  # [0.0, 1.0] or None
    prediction_state: str  # KNOWN_CLASS, LOW_CONFIDENCE, UNKNOWN, INSUFFICIENT_EVIDENCE, etc.
    packets_observed: int
    elapsed_seconds: float
    latency_us: float
    confidence_valid: bool = True
    session_id_hash: str = "0000000000000000"
    family_confidence: Optional[float] = None
    fine_confidence: Optional[float] = None
    composed_confidence: Optional[float] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "flow_id": self.flow_id,
            "session_id_hash": self.session_id_hash,
            "model_id": self.model_id,
            "feature_profile": self.feature_profile,
            "predicted_family": self.predicted_family,
            "predicted_class": self.predicted_class,
            "confidence": self.confidence,
            "family_confidence": self.family_confidence,
            "fine_confidence": self.fine_confidence,
            "composed_confidence": self.composed_confidence,
            "confidence_valid": self.confidence_valid,
            "prediction_state": self.prediction_state,
            "packets_observed": self.packets_observed,
            "elapsed_seconds": self.elapsed_seconds,
            "latency_us": self.latency_us,
        }


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    normalized_record: Optional[CanonicalPredictionRecord] = None


def parse_confidence(value: Any) -> Tuple[float, bool]:
    """
    Safely parses confidence value into (float_val, is_valid).

    Rules:
    - If int/float: clamp [0.0, 1.0] and return (val, True)
    - If numeric string: float(str) clamped, return (val, True)
    - If None or empty: return (0.0, False)
    - If non-numeric string (e.g. 'Messaging', 'Video', 'Web'): return (0.0, False)
    """
    if value is None:
        return 0.0, False

    if isinstance(value, (int, float)):
        try:
            val_float = float(value)
            if val_float != val_float:  # NaN check
                return 0.0, False
            return max(0.0, min(1.0, val_float)), True
        except (ValueError, OverflowError):
            return 0.0, False

    if isinstance(value, str):
        val_clean = value.strip()
        if not val_clean or val_clean.lower() in NON_NUMERIC_CLASS_STRINGS:
            return 0.0, False
        try:
            val_float = float(val_clean)
            if val_float != val_float:
                return 0.0, False
            return max(0.0, min(1.0, val_float)), True
        except (ValueError, TypeError):
            return 0.0, False

    return 0.0, False



def validate_prediction_record(record: Dict[str, Any]) -> ValidationResult:
    """
    Validates a raw dictionary record against prediction schema requirements.
    """
    errors = []
    if not isinstance(record, dict):
        return ValidationResult(is_valid=False, errors=["Record must be a dictionary"])

    # Check state
    state = record.get("prediction_state", "KNOWN_CLASS")
    if state not in VALID_PREDICTION_STATES:
        errors.append(f"Invalid prediction_state: '{state}'")

    # Check numeric fields
    raw_conf = record.get("composed_confidence", record.get("confidence"))
    conf, conf_valid = parse_confidence(raw_conf)
    if raw_conf is not None and not conf_valid and str(raw_conf).strip().lower() not in NON_NUMERIC_CLASS_STRINGS:
        errors.append(f"Invalid non-numeric confidence: '{raw_conf}'")

    return ValidationResult(is_valid=(len(errors) == 0), errors=errors)
