"""
Dashboard Live Prediction Feed Loader.

Authoritative loader connecting the Streamlit SOC Console to the Local REST API (http://127.0.0.1:8080/predictions).
Supports normalized canonical schema extraction, mode-specific filtering, fail-safe degradation, and detailed audit logging.
"""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import urllib.error
import urllib.request

import pandas as pd

from dashboard.schema import (
    CanonicalPredictionRecord,
    NON_NUMERIC_CLASS_STRINGS,
    VALID_PREDICTION_STATES,
    parse_confidence,
)
from dashboard.value_normalizer import safe_float, safe_int

logger = logging.getLogger("dashboard_live_feed")


def _format_timestamp(raw_ts: Any) -> str:
    """Safely converts epoch timestamp or string to HH:MM:SS format."""
    if raw_ts is None or raw_ts == "":
        return datetime.now().strftime("%H:%M:%S")
    try:
        epoch = float(raw_ts)
        return datetime.fromtimestamp(epoch).strftime("%H:%M:%S")
    except (ValueError, TypeError, OverflowError):
        raw_str = str(raw_ts).strip()
        if len(raw_str) >= 8 and ":" in raw_str:
            return raw_str[-8:]
        return datetime.now().strftime("%H:%M:%S")


def normalize_api_record(
    record: Dict[str, Any],
    target_mode: str = "DEMO_MODE",
) -> Tuple[Optional[CanonicalPredictionRecord], bool, Optional[str]]:
    """
    Normalizes a raw API prediction dictionary into a CanonicalPredictionRecord.

    Maps:
    - Time                  <- timestamp
    - Flow ID               <- flow_id
    - Family                <- predicted_family
    - Predicted Class       <- predicted_class
    - Confidence            <- composed_confidence (or confidence)
    - State                 <- prediction_state
    - Latency (µs)          <- latency_us
    - Packets               <- packets_observed
    - Elapsed (s)           <- elapsed_seconds
    - Mode                  <- operating_mode
    - Event ID              <- event_id
    """
    if not isinstance(record, dict):
        return None, False, "record is not a dictionary"

    # Mode validation
    rec_mode = str(record.get("operating_mode", "")).upper()
    target_mode_norm = target_mode.upper()

    if "LIVE" in target_mode_norm and "DEMO" in rec_mode:
        return None, False, f"wrong operating mode: {rec_mode} in LIVE_MODE"

    # Extract raw fields without assuming CSV positions
    raw_ts = record.get("timestamp")
    flow_id = str(record.get("flow_id", "UNKNOWN")).strip()
    session_id_hash = str(record.get("session_id_hash", "0000000000000000")).strip()
    model_id = str(record.get("model_id", "model_lightgbm_v1")).strip()
    feature_profile = str(record.get("feature_profile", "lightweight_10")).strip()
    predicted_family = str(record.get("predicted_family", "")).strip()
    predicted_class = str(record.get("predicted_class", "")).strip()

    # Confidence parsing: composed_confidence -> confidence -> 0.0
    raw_comp_conf = record.get("composed_confidence")
    if raw_comp_conf is None:
        raw_comp_conf = record.get("confidence")

    raw_fam_conf = record.get("family_confidence")
    raw_fine_conf = record.get("fine_confidence")

    comp_conf_val, comp_conf_valid = parse_confidence(raw_comp_conf)
    fam_conf_val, _ = parse_confidence(raw_fam_conf)
    fine_conf_val, _ = parse_confidence(raw_fine_conf)

    # State
    raw_state = str(record.get("prediction_state", "")).strip()
    if raw_state in VALID_PREDICTION_STATES:
        state = raw_state
    elif comp_conf_val is not None and comp_conf_val >= 0.70:
        state = "KNOWN_CLASS"
    elif comp_conf_val is not None and comp_conf_val >= 0.35:
        state = "LOW_CONFIDENCE"
    else:
        state = "UNKNOWN"

    # Infer family if missing
    if not predicted_family or predicted_family in ("—", "None", "null", "nan", ""):
        if predicted_class in ["Web", "Messaging", "VoIP"]:
            predicted_family = "Interactive"
        elif predicted_class in ["Video", "File Transfer"]:
            predicted_family = "Bulk_Streaming"
        elif predicted_class == "Other":
            predicted_family = "Other"
        else:
            predicted_family = "—"

    if not predicted_class or predicted_class in ("None", "null", "nan"):
        predicted_class = "—"

    # Latency parsing
    latency_us = safe_float(record.get("latency_us"), default=0.0) or 0.0
    if latency_us == 0.0 and "latency_ms" in record:
        latency_us = (safe_float(record.get("latency_ms"), default=0.0) or 0.0) * 1000.0

    pkts = safe_int(record.get("packets_observed"), default=safe_int(record.get("packet_count"), default=0))
    elapsed_sec = safe_float(record.get("elapsed_seconds"), default=0.0) or 0.0

    canonical = CanonicalPredictionRecord(
        timestamp=_format_timestamp(raw_ts),
        flow_id=flow_id,
        session_id_hash=session_id_hash,
        model_id=model_id,
        feature_profile=feature_profile,
        predicted_family=predicted_family,
        predicted_class=predicted_class,
        confidence=comp_conf_val,
        family_confidence=fam_conf_val,
        fine_confidence=fine_conf_val,
        composed_confidence=comp_conf_val,
        confidence_valid=comp_conf_valid,
        prediction_state=state,
        packets_observed=pkts,
        elapsed_seconds=elapsed_sec,
        latency_us=latency_us,
        raw_data=record,
    )

    return canonical, comp_conf_valid, None


def load_live_predictions(
    limit: int = 100,
    mode: str = "DEMO_MODE",
    api_url: str = "http://127.0.0.1:8080/predictions",
    timeout: float = 2.0,
) -> Tuple[List[CanonicalPredictionRecord], Dict[str, Any]]:
    """
    Authoritative function for loading live prediction records from the Local REST API.

    Returns:
        (normalized_canonical_records_list, metadata_dict)
    """
    req_url = f"{api_url}?limit={limit}"
    source = "LOCAL_API"
    http_status: Optional[int] = None
    connected = False
    error: Optional[str] = None
    raw_count = 0
    normalized_count = 0
    dropped_count = 0
    drop_reasons: List[str] = []

    canonical_records: List[CanonicalPredictionRecord] = []

    try:
        req = urllib.request.Request(
            req_url,
            headers={"User-Agent": "EncryptedTrafficSOCDashboard/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            http_status = getattr(response, "status", 200)
            if http_status == 200:
                connected = True
                body = response.read().decode("utf-8")
            else:
                error = f"HTTP {http_status}: {getattr(response, 'reason', 'Non-200 Status')}"

        if connected:
            try:
                payload = json.loads(body)
                raw_predictions = payload.get("predictions", [])
                if isinstance(raw_predictions, list):
                    raw_count = len(raw_predictions)
                    for raw_rec in raw_predictions:
                        canon, is_valid, drop_reason = normalize_api_record(raw_rec, target_mode=mode)
                        if canon is not None:
                            canonical_records.append(canon)
                            normalized_count += 1
                        else:
                            dropped_count += 1
                            if drop_reason:
                                drop_reasons.append(drop_reason)
                else:
                    error = "API 'predictions' payload is not a list"
                    connected = False
            except Exception as json_err:
                error = f"Failed to parse API JSON response: {str(json_err)}"
                connected = False

    except urllib.error.HTTPError as http_err:
        http_status = http_err.code
        error = f"HTTP {http_err.code}: {http_err.reason}"
        connected = False
    except (urllib.error.URLError, ConnectionRefusedError, TimeoutError, OSError) as net_err:
        error = f"API connection unavailable: {str(net_err)}"
        connected = False
    except Exception as e:
        error = f"Unexpected feed error: {str(e)}"
        connected = False

    # Fallback to CSV if API is completely offline (e.g. offline research viewing)
    if not connected:
        fallback_csv = Path("results/realtime/predictions.csv")
        if fallback_csv.exists():
            try:
                import csv
                with open(fallback_csv, "r", encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
                raw_count = len(rows)
                for r in rows[-limit:]:
                    canon, is_valid, drop_reason = normalize_api_record(r, target_mode=mode)
                    if canon is not None:
                        canonical_records.append(canon)
                        normalized_count += 1
                    else:
                        dropped_count += 1
                source = "CSV_FALLBACK"
                # If CSV has records, consider feed degraded rather than dead while preserving original error
                if canonical_records:
                    if error:
                        error = f"{error} (Loaded {normalized_count} records from CSV cache)"
                    else:
                        error = f"Local API offline; loaded {normalized_count} records from CSV cache."
            except Exception:
                pass

    event_count = len(canonical_records)
    last_update = datetime.now().strftime("%H:%M:%S")

    # Logging as required by Section 1 & Section 8
    print(f"LIVE_FEED_SOURCE = {source}")
    print(f"LIVE_FEED_URL = {req_url}")
    print(f"LIVE_FEED_HTTP_STATUS = {http_status}")
    print(f"LIVE_FEED_EVENT_COUNT = {event_count}")
    if dropped_count > 0:
        print(f"LIVE_FEED_DROPPED_COUNT = {dropped_count} (Reasons: {', '.join(set(drop_reasons))})")

    logger.info(
        "LIVE_FEED_SOURCE: %s | URL: %s | HTTP: %s | EVENTS: %d (raw: %d, norm: %d, dropped: %d)",
        source,
        req_url,
        http_status,
        event_count,
        raw_count,
        normalized_count,
        dropped_count,
    )

    metadata = {
        "connected": connected,
        "event_count": event_count,
        "raw_count": raw_count,
        "normalized_count": normalized_count,
        "dropped_count": dropped_count,
        "drop_reasons": drop_reasons,
        "last_update": last_update,
        "error": error,
        "source": source,
        "http_status": http_status,
        "url": req_url,
    }

    # Chronological newest first for SOC table
    return list(reversed(canonical_records)), metadata
