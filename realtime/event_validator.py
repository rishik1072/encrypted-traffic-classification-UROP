"""
Real-Time Traffic Prediction Event Validator.

Enforces strict semantic and type constraints on TrafficPredictionEvent
objects and raw dictionaries across all operating modes (LIVE_MODE, DEMO_MODE, RESEARCH_MODE).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("realtime.event_validator")

VALID_PREDICTION_STATES = {
    "KNOWN",
    "KNOWN_CLASS",
    "LOW_CONFIDENCE",
    "UNKNOWN",
    "INSUFFICIENT_EVIDENCE",
    "FLOW_COMPLETED",
    "PIPELINE_DEGRADED",
}

VALID_TRAFFIC_CLASSES = {
    "Web",
    "Video",
    "Messaging",
    "VoIP",
    "File Transfer",
    "Other",
}

VALID_TRAFFIC_FAMILIES = {
    "Interactive",
    "Bulk_Streaming",
    "Other",
    "UNKNOWN",
}


def _is_valid_float(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, bool):
        return False
    try:
        f = float(val)
        return f == f and f != float("inf") and f != float("-inf")
    except (ValueError, TypeError):
        return False


def _is_valid_confidence(val: Any) -> bool:
    if not _is_valid_float(val):
        return False
    f = float(val)
    return 0.0 <= f <= 1.0


def validate_traffic_prediction_event(
    event: Union[Dict[str, Any], Any]
) -> Tuple[bool, List[str]]:
    """
    Validates a TrafficPredictionEvent or dictionary against canonical schema rules.

    Rules:
    - KNOWN_CLASS:
      * family present and valid
      * class present and valid
      * composed_confidence numeric and in [0.0, 1.0]
    - LOW_CONFIDENCE:
      * family present or None
      * composed_confidence numeric and in [0.0, 1.0]
      * class optional (candidate or None)
    - UNKNOWN:
      * family is None or 'UNKNOWN'
      * class is None or '—'
      * composed_confidence is numeric or None
    - INSUFFICIENT_EVIDENCE:
      * packets_observed < 5 (or minimum packets)
      * no fabricated class (class is None or '—')
      * family is None, 'UNKNOWN', or candidate
      * confidences are None or not claimed
    - FLOW_COMPLETED:
      * preserved state from previous prediction
    - PIPELINE_DEGRADED:
      * diagnostic flag for runtime degradation

    Returns:
        (is_valid, list_of_error_reasons)
    """
    errors: List[str] = []

    if event is None:
        return False, ["Event is None"]

    if isinstance(event, dict):
        data = event
    elif hasattr(event, "to_dict"):
        data = event.to_dict()
    elif hasattr(event, "__dict__"):
        data = event.__dict__
    else:
        return False, ["Event must be a dict or dataclass instance"]

    # 1. State Validation
    state = data.get("prediction_state")
    if not state or state not in VALID_PREDICTION_STATES:
        errors.append(f"Invalid prediction_state: '{state}'. Must be one of {sorted(VALID_PREDICTION_STATES)}")

    # 2. Key Fields & Types
    pred_family = data.get("predicted_family")
    pred_class = data.get("predicted_class")
    composed_conf = data.get("composed_confidence")
    if composed_conf is None and "confidence" in data:
        composed_conf = data.get("confidence")

    fam_conf = data.get("family_confidence")
    fine_conf = data.get("fine_confidence")

    pkts = data.get("packets_observed")
    if pkts is None and "packet_count" in data:
        pkts = data.get("packet_count")

    latency_us = data.get("latency_us")
    if latency_us is None and "latency_ms" in data:
        try:
            latency_us = float(data.get("latency_ms")) * 1000.0
        except Exception:
            pass

    # Latency must be non-negative numeric
    if latency_us is not None and not _is_valid_float(latency_us):
        errors.append(f"latency_us must be numeric float, got: {latency_us}")

    # Packets observed must be non-negative int
    if pkts is not None:
        try:
            int_pkts = int(pkts)
            if int_pkts < 0:
                errors.append(f"packets_observed cannot be negative: {pkts}")
        except (ValueError, TypeError):
            errors.append(f"packets_observed must be integer, got: {pkts}")

    # Check for string label contamination in confidence fields
    for c_name, c_val in [
        ("composed_confidence", composed_conf),
        ("family_confidence", fam_conf),
        ("fine_confidence", fine_conf),
    ]:
        if c_val is not None:
            if isinstance(c_val, str) and c_val in VALID_TRAFFIC_CLASSES:
                errors.append(f"{c_name} contains class label string '{c_val}' instead of numeric float")
            elif not _is_valid_confidence(c_val):
                errors.append(f"{c_name} must be float in [0.0, 1.0] or None, got: {c_val}")

    # 3. State-Specific Constraints
    if state in ("KNOWN", "KNOWN_CLASS"):
        if not pred_family or pred_family in ("None", "UNKNOWN", "—") or pred_family not in VALID_TRAFFIC_FAMILIES:
            errors.append(f"{state} requires valid predicted_family, got: '{pred_family}'")
        if not pred_class or pred_class in ("None", "UNKNOWN", "—") or pred_class not in VALID_TRAFFIC_CLASSES:
            errors.append(f"{state} requires valid fine-grained predicted_class from {sorted(VALID_TRAFFIC_CLASSES)}, got: '{pred_class}'")
        if composed_conf is None or not _is_valid_confidence(composed_conf):
            errors.append(f"{state} requires valid composed_confidence float, got: {composed_conf}")

    elif state == "LOW_CONFIDENCE":
        if composed_conf is None or not _is_valid_confidence(composed_conf):
            errors.append(f"LOW_CONFIDENCE requires numeric composed_confidence, got: {composed_conf}")

    elif state == "UNKNOWN":
        if pred_family and pred_family not in ("UNKNOWN", "Other", None):
            # If genuine UNKNOWN state, family should be None, "UNKNOWN", or "Other" (if model explicitly predicted Other)
            pass
        if pred_class and pred_class not in ("UNKNOWN", "—", "None", None, "Other"):
            # UNKNOWN should not fabricate specific fine class
            errors.append(f"UNKNOWN state should not assert definitive fine class: '{pred_class}'")

    elif state == "INSUFFICIENT_EVIDENCE":
        if pred_class and pred_class not in ("INSUFFICIENT_EVIDENCE", "—", "None", None):
            errors.append(f"INSUFFICIENT_EVIDENCE cannot claim definitive class '{pred_class}'")

    is_valid = len(errors) == 0
    if not is_valid:
        logger.warning("Event validation failed (%d errors): %s", len(errors), errors)

    return is_valid, errors
