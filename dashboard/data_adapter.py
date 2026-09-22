"""
Dashboard Data Adapter.

Normalizes raw prediction records from multiple sources (legacy Phase 2-8 CSVs,
Phase 9 production events, JSONL records, and corrupted rows) into canonical
dashboard records.
"""

from __future__ import annotations

from datetime import datetime
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from dashboard.schema import (
    CanonicalPredictionRecord,
    NON_NUMERIC_CLASS_STRINGS,
    VALID_PREDICTION_STATES,
    parse_confidence,
)
from dashboard.streamlit_contract import (
    _clean_value as clean_for_json_serialization,
    prepare_dataframe_for_streamlit as sanitize_dataframe_for_streamlit,
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "" or str(value).strip().lower() in NON_NUMERIC_CLASS_STRINGS:
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def _format_timestamp(raw_ts: Any) -> str:
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


def normalize_prediction_record(
    record: Dict[str, Any],
    is_live_mode: bool = False,
) -> Tuple[Optional[CanonicalPredictionRecord], bool, Optional[str]]:
    """
    Normalizes a dictionary record into a CanonicalPredictionRecord.

    In LIVE_MODE:
    - Rejects malformed records strictly and marks PIPELINE_DEGRADED.

    Returns:
        (canonical_record, is_valid_schema, error_message_if_any)
    """
    # Check if record has legacy header format
    # Legacy fields: event_id, timestamp, flow_id, protocol, source_port, destination_port, packet_count, byte_count, predicted_class, confidence, confidence_level, latency_ms
    is_legacy = "packet_count" in record or ("confidence_level" in record and "family_confidence" not in record)

    first_val = str(record.get("timestamp", ""))
    is_19_col_event = first_val.startswith("EVT-") or "event_id" in record

    if is_19_col_event and first_val.startswith("EVT-"):
        # When read with canonical 14-field header:
        ts_val = record.get("flow_id")
        flow_val = record.get("session_id_hash")
        sess_val = record.get("model_id")
        model_val = record.get("feature_profile")
        feat_val = record.get("predicted_family")
        pkts = _safe_int(record.get("predicted_class"), 0)
        elapsed_val = _safe_float(record.get("family_confidence"), 0.0) or 0.0
        raw_fam = record.get("fine_confidence")
        raw_class = record.get("composed_confidence")
        raw_comp_conf = record.get("prediction_state")
        raw_state = record.get("packets_observed")
        latency_us = _safe_float(record.get("latency_us"), 0.0) or 0.0
        raw_fam_conf = None
        raw_fine_conf = None
    elif is_legacy:
        # Map legacy 12-field layout
        ts_val = record.get("timestamp")
        flow_val = record.get("flow_id")
        sess_val = record.get("session_id_hash", "0000000000000000")
        model_val = record.get("model_id", "model_lightgbm_v1")
        feat_val = record.get("feature_profile", "lightweight_10")
        raw_comp_conf = record.get("confidence")
        raw_class = record.get("predicted_class")
        raw_fam = None
        raw_fam_conf = None
        raw_fine_conf = None
        raw_state = record.get("prediction_state")
        pkts = _safe_int(record.get("packet_count"), 0)
        elapsed_val = 0.0
        latency_us = _safe_float(record.get("latency_ms"), 0.0) * 1000.0 if record.get("latency_ms") else 0.0
    else:
        # Canonical schema fields
        ts_val = record.get("timestamp")
        flow_val = record.get("flow_id")
        sess_val = record.get("session_id_hash", "0000000000000000")
        model_val = record.get("model_id", "model_lightgbm_v1")
        feat_val = record.get("feature_profile", "lightweight_10")
        raw_comp_conf = record.get("composed_confidence")
        if raw_comp_conf is None and "confidence" in record:
            raw_comp_conf = record.get("confidence")
        raw_fam_conf = record.get("family_confidence")
        raw_fine_conf = record.get("fine_confidence")
        raw_class = record.get("predicted_class")
        raw_fam = record.get("predicted_family")
        raw_state = record.get("prediction_state")
        pkts = _safe_int(record.get("packets_observed"), _safe_int(record.get("packet_count"), 0))
        elapsed_val = _safe_float(record.get("elapsed_seconds"), 0.0) or 0.0
        latency_us = _safe_float(record.get("latency_us"), 0.0) or 0.0
        if latency_us == 0.0 and "latency_ms" in record:
            latency_us = (_safe_float(record.get("latency_ms"), 0.0) or 0.0) * 1000.0


    is_malformed = False
    malform_reason = None

    # Check for shifted column where confidence is a class name
    comp_conf_val, comp_conf_valid = parse_confidence(raw_comp_conf)
    if raw_comp_conf is not None and not comp_conf_valid:
        is_malformed = True
        malform_reason = f"Non-numeric confidence: '{raw_comp_conf}'"
        if str(raw_comp_conf).strip().lower() in NON_NUMERIC_CLASS_STRINGS:
            if not raw_class or raw_class in ("—", "", "None"):
                raw_class = str(raw_comp_conf)

    fam_conf_val, _ = parse_confidence(raw_fam_conf)
    fine_conf_val, _ = parse_confidence(raw_fine_conf)

    # Class & Family parsing
    if raw_class and str(raw_class).strip().lower() not in ("none", "null", "nan", "—", ""):
        pred_class = str(raw_class).strip()
    else:
        pred_class = "—"

    if raw_fam and str(raw_fam).strip().lower() not in ("none", "null", "nan", "—", ""):
        pred_fam = str(raw_fam).strip()
    else:
        # Infer family from fine class for legacy records
        if pred_class in ["Web", "Messaging", "VoIP"]:
            pred_fam = "Interactive"
        elif pred_class in ["Video", "File Transfer"]:
            pred_fam = "Bulk_Streaming"
        elif pred_class == "Other":
            pred_fam = "Other"
        else:
            pred_fam = "—"



    pkts = _safe_int(record.get("packets_observed"), _safe_int(record.get("packet_count"), 0))

    # Prediction state
    raw_state = record.get("prediction_state")
    if raw_state and raw_state in VALID_PREDICTION_STATES:
        state = raw_state
    else:
        # Check legacy confidence_level
        conf_level = str(record.get("confidence_level", "")).upper()
        if "HIGH" in conf_level:
            state = "KNOWN_CLASS"
        elif "LOW" in conf_level:
            state = "LOW_CONFIDENCE"
        elif comp_conf_val is not None and comp_conf_val >= 0.70:
            state = "KNOWN_CLASS"
        elif comp_conf_val is not None and comp_conf_val >= 0.35:
            state = "LOW_CONFIDENCE"
        else:
            state = "UNKNOWN"

        if pkts < 5 and pred_class == "—":
            state = "INSUFFICIENT_EVIDENCE"




    latency_us = _safe_float(record.get("latency_us"), 0.0) or 0.0
    if latency_us == 0.0 and "latency_ms" in record:
        latency_us = (_safe_float(record.get("latency_ms"), 0.0) or 0.0) * 1000.0

    # In strict LIVE_MODE, mark degraded if malformed
    if is_live_mode and is_malformed:
        state = "PIPELINE_DEGRADED"

    canonical = CanonicalPredictionRecord(
        timestamp=_format_timestamp(record.get("timestamp")),
        flow_id=str(record.get("flow_id", "UNKNOWN")),
        session_id_hash=str(record.get("session_id_hash", "0000000000000000")),
        model_id=str(record.get("model_id", "model_lightgbm_v1")),
        feature_profile=str(record.get("feature_profile", "lightweight_10")),
        predicted_family=pred_fam,
        predicted_class=pred_class,
        confidence=comp_conf_val,
        family_confidence=fam_conf_val,
        fine_confidence=fine_conf_val,
        composed_confidence=comp_conf_val,
        confidence_valid=comp_conf_valid,
        prediction_state=state,
        packets_observed=pkts,
        elapsed_seconds=_safe_float(record.get("elapsed_seconds"), 0.0) or 0.0,
        latency_us=latency_us,
        raw_data=record,
    )

    return canonical, not is_malformed, malform_reason


def sanitize_dataframe_for_streamlit(
    data: Union[pd.DataFrame, List[Dict[str, Any]], Dict[str, Any], Any],
    placeholder: str = "N/A",
    preserve_none: bool = True,
) -> pd.DataFrame:
    """
    Sanitizes a pandas DataFrame or tabular data structure for safe Streamlit rendering.
    """
    from dashboard.streamlit_contract import prepare_dataframe_for_streamlit
    return prepare_dataframe_for_streamlit(data, na_rep=placeholder)


def fetch_predictions_from_api(
    api_url: str = "http://127.0.0.1:8080/predictions?limit=100",
    timeout: float = 2.0,
    is_live_mode: bool = False,
) -> Tuple[List[CanonicalPredictionRecord], Dict[str, Any]]:
    """
    Queries the authoritative Local REST API (/predictions) and normalizes records into canonical objects.

    Returns:
        (canonical_records, feed_info_dict)
    """
    import json
    import urllib.error
    import urllib.request

    feed_info: Dict[str, Any] = {
        "status": "CONNECTED",
        "count": 0,
        "malformed_count": 0,
        "error": None,
        "source": "LOCAL_API",
        "api_url": api_url,
    }

    try:
        req = urllib.request.Request(
            api_url,
            headers={"User-Agent": "EncryptedTrafficDashboard/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = getattr(response, "status", 200)
            if status_code != 200:
                feed_info["status"] = "DEGRADED"
                feed_info["error"] = f"HTTP {status_code}: {getattr(response, 'reason', 'Non-200 Status')}"
                return [], feed_info

            raw_body = response.read().decode("utf-8")

        try:
            payload = json.loads(raw_body)
        except Exception as json_err:
            feed_info["status"] = "DEGRADED"
            feed_info["error"] = f"Invalid JSON response from API: {str(json_err)}"
            return [], feed_info

        if not isinstance(payload, dict) or "predictions" not in payload:
            feed_info["status"] = "DEGRADED"
            feed_info["error"] = "API response missing 'predictions' field"
            return [], feed_info

        raw_predictions = payload.get("predictions", [])
        if not isinstance(raw_predictions, list):
            feed_info["status"] = "DEGRADED"
            feed_info["error"] = "Field 'predictions' is not a list"
            return [], feed_info

        canonical_records: List[CanonicalPredictionRecord] = []
        malformed_count = 0

        for raw_rec in raw_predictions:
            if not isinstance(raw_rec, dict):
                malformed_count += 1
                continue
            canon, is_valid, err_msg = normalize_prediction_record(raw_rec, is_live_mode=is_live_mode)
            if canon is not None:
                canonical_records.append(canon)
            if not is_valid:
                malformed_count += 1

        feed_info["count"] = len(canonical_records)
        feed_info["malformed_count"] = malformed_count

        if malformed_count > 0:
            feed_info["status"] = "DEGRADED"
            feed_info["error"] = f"{malformed_count} malformed record(s) detected in feed"
        else:
            feed_info["status"] = "CONNECTED"

        # Most recent predictions first
        return list(reversed(canonical_records)), feed_info

    except urllib.error.HTTPError as http_err:
        feed_info["status"] = "DEGRADED"
        feed_info["error"] = f"HTTP {http_err.code}: {http_err.reason}"
        return [], feed_info
    except (urllib.error.URLError, ConnectionRefusedError, TimeoutError, OSError) as net_err:
        feed_info["status"] = "DEGRADED"
        feed_info["error"] = f"API unavailable: {str(net_err)}"
        return [], feed_info
    except Exception as e:
        feed_info["status"] = "DEGRADED"
        feed_info["error"] = f"Unexpected feed error: {str(e)}"
        return [], feed_info


def fetch_subsystem_status(
    api_base_url: str = "http://127.0.0.1:8080",
    timeout: float = 1.5,
) -> Dict[str, Any]:
    """
    Queries local API health and status endpoints to report subsystem health.
    """
    import json
    import urllib.error
    import urllib.request

    status_report = {
        "engine_status": "UNKNOWN",
        "api_status": "OFFLINE",
        "api_healthy": False,
        "details": {},
    }

    try:
        health_req = urllib.request.Request(f"{api_base_url}/health", headers={"Accept": "application/json"})
        with urllib.request.urlopen(health_req, timeout=timeout) as resp:
            if getattr(resp, "status", 200) == 200:
                health_data = json.loads(resp.read().decode("utf-8"))
                status_report["api_healthy"] = health_data.get("overall_status") in ("PASS", "WARNING")
                status_report["api_status"] = "HEALTHY" if status_report["api_healthy"] else "DEGRADED"
                status_report["details"]["health"] = health_data
    except Exception:
        status_report["api_status"] = "OFFLINE"
        status_report["api_healthy"] = False

    try:
        stat_req = urllib.request.Request(f"{api_base_url}/status", headers={"Accept": "application/json"})
        with urllib.request.urlopen(stat_req, timeout=timeout) as resp:
            if getattr(resp, "status", 200) == 200:
                stat_data = json.loads(resp.read().decode("utf-8"))
                status_report["engine_status"] = "RUNNING" if stat_data.get("status") in ("READY", "RUNNING") else "IDLE"
                status_report["details"]["status"] = stat_data
    except Exception:
        if status_report["api_healthy"]:
            status_report["engine_status"] = "RUNNING"
        else:
            status_report["engine_status"] = "STOPPED"

    return status_report


def load_dashboard_feed(
    api_url: str = "http://127.0.0.1:8080/predictions?limit=100",
    fallback_csv_path: Optional[str] = "results/realtime/predictions.csv",
    limit: int = 100,
    is_live_mode: bool = False,
) -> Tuple[List[CanonicalPredictionRecord], Dict[str, Any]]:
    """
    Loads prediction feed from the authoritative Local API.
    Falls back to CSV only if API is completely unavailable and CSV exists.
    """
    records, feed_info = fetch_predictions_from_api(api_url=api_url, is_live_mode=is_live_mode)

    # If API connected (even with 0 count) or returned records, use API
    if feed_info["status"] == "CONNECTED" or records:
        return records[:limit], feed_info

    # If API is unreachable and a fallback CSV exists:
    if fallback_csv_path:
        from pathlib import Path
        p = Path(fallback_csv_path)
        if p.exists():
            try:
                import csv
                with open(p, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    raw_rows = list(reader)

                csv_records: List[CanonicalPredictionRecord] = []
                malformed_count = 0
                for row in raw_rows[-limit:]:
                    canon, is_valid, _ = normalize_prediction_record(row, is_live_mode=is_live_mode)
                    if canon:
                        csv_records.append(canon)
                    if not is_valid:
                        malformed_count += 1

                return list(reversed(csv_records)), {
                    "status": "CONNECTED" if malformed_count == 0 else "DEGRADED",
                    "count": len(csv_records),
                    "malformed_count": malformed_count,
                    "error": None if malformed_count == 0 else f"{malformed_count} malformed records in CSV fallback",
                    "source": "CSV_FALLBACK",
                    "api_url": api_url,
                }
            except Exception:
                pass

    return records, feed_info

