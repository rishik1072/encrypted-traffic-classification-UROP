"""
Local-Only REST API Server for Encrypted Traffic Monitor.

Binds exclusively to 127.0.0.1 (localhost) and exposes monitoring endpoints:
- GET /health
- GET /status
- GET /adapters
- GET /model
- GET /metrics
- GET /predictions
"""

from __future__ import annotations

import csv
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import threading
import time
import traceback
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from product.adapter_manager import get_default_adapter, list_adapters
from product.config import product_config
from product.event_store import local_event_store
from product.health import run_product_health_check
from product.version import APP_NAME, __version__
from realtime.alerts import global_alert_evaluator

logger = logging.getLogger(__name__)


class LocalAPIHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests strictly from localhost."""

    def address_string(self) -> str:
        """Avoids slow DNS resolution on localhost connections."""
        return str(self.client_address[0])

    def log_message(self, format: str, *args: Any) -> None:
        # Route to application logger
        logger.debug("%s - - [%s] %s", self.client_address[0], self.log_date_time_string(), format % args)

    def _send_json_response(self, data: Any, status_code: int = 200) -> None:
        """Sends a JSON formatted HTTP response with security headers."""
        try:
            body = json.dumps(data, indent=2, default=str).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8501")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self) -> None:
        """Dispatches GET requests to appropriate local endpoint handlers."""
        # Enforce localhost origin check
        client_ip = self.client_address[0]
        if client_ip not in ("127.0.0.1", "::1", "localhost"):
            self._send_json_response({"error": "Forbidden: Local-only API"}, status_code=403)
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if not path:
            path = "/"

        try:
            if path == "/health":
                self.handle_health()
            elif path == "/status":
                self.handle_status()
            elif path == "/adapters":
                self.handle_adapters()
            elif path == "/model":
                self.handle_model()
            elif path == "/metrics":
                self.handle_metrics()
            elif path == "/predictions":
                self.handle_predictions(parsed.query)
            elif path == "/events":
                self.handle_events(parsed.query)
            elif path == "/alerts":
                self.handle_alerts(parsed.query)
            elif path == "/session/export":
                self.handle_session_export(parsed.query)
            elif path == "/":
                self.handle_root()
            else:
                self._send_json_response({"error": "Not Found", "endpoint": path}, status_code=404)
        except Exception as e:
            logger.error("Unhandled error processing GET %s: %s\n%s", path, e, traceback.format_exc())
            self._send_json_response(
                {
                    "error": "Internal Server Error",
                    "endpoint": path,
                    "message": str(e),
                    "pipeline_status": "DEGRADED",
                },
                status_code=500,
            )

    def do_POST(self) -> None:
        """Dispatches POST requests for session management and configuration."""
        client_ip = self.client_address[0]
        if client_ip not in ("127.0.0.1", "::1", "localhost"):
            self._send_json_response({"error": "Forbidden: Local-only API"}, status_code=403)
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        content_len = int(self.headers.get("Content-Length", 0))
        body_data: Dict[str, Any] = {}
        if content_len > 0:
            try:
                body_bytes = self.rfile.read(content_len)
                body_data = json.loads(body_bytes.decode("utf-8"))
            except Exception as e:
                logger.warning("Failed to parse POST JSON body: %s", e)

        if path == "/session/start":
            self.handle_session_start(body_data)
        elif path == "/session/stop":
            self.handle_session_stop(body_data)
        elif path == "/session/clear":
            self.handle_session_clear(body_data)
        elif path == "/session/export":
            self.handle_session_export_post(body_data)
        else:
            self._send_json_response({"error": "Not Found", "endpoint": path}, status_code=404)

    def handle_root(self) -> None:
        """Returns API overview."""
        self._send_json_response({
            "app_name": APP_NAME,
            "version": __version__,
            "privacy_mode": "LOCAL ONLY",
            "zero_payload": "PASS",
            "endpoints": [
                "/health",
                "/status",
                "/adapters",
                "/model",
                "/metrics",
                "/predictions",
                "/events",
                "/alerts",
                "/session/start",
                "/session/stop",
                "/session/clear",
                "/session/export",
            ],
        })

    def handle_health(self) -> None:
        """Returns comprehensive health check report."""
        report = run_product_health_check()
        status_code = 200 if report["overall_status"] in ("PASS", "WARNING") else 503
        self._send_json_response(report, status_code=status_code)

    def handle_status(self) -> None:
        """Returns product runtime and privacy state distinguishing evidence classes."""
        def_ad = get_default_adapter()
        from product.environment import check_npcap
        npcap_res = check_npcap()
        is_npcap_present = npcap_res.get("status") == "PASS"

        raw_mode = product_config.default_mode.upper()
        if raw_mode in ("LIVE", "LIVE_MODE"):
            canonical_mode = "LIVE_NPCAP"
        elif raw_mode in ("RECORDED", "RECORDED_CAPTURE"):
            canonical_mode = "RECORDED_CAPTURE"
        elif raw_mode in ("DEMO", "DEMO_MODE"):
            canonical_mode = "DEMO_MODE"
        else:
            canonical_mode = raw_mode

        from realtime.events import EVIDENCE_CLASS_MAP
        evidence_class = EVIDENCE_CLASS_MAP.get(canonical_mode, "UNKNOWN_EVIDENCE")
        active_sess_id = local_event_store.get_active_session_id()

        # Phase 4: verified live capture evidence check
        live_machine_verified = False
        capture_state = "IDLE" if not active_sess_id else "UNKNOWN"
        packets_captured_total = 0
        if active_sess_id:
            try:
                metrics_file = Path("results/realtime/metrics.json")
                if metrics_file.exists():
                    with open(metrics_file, "r", encoding="utf-8") as f:
                        m_data = json.load(f)
                    if m_data.get("session_id") == active_sess_id:
                        capture_state = m_data.get("capture_state", "UNKNOWN")
                        packets_captured_total = m_data.get("capture_packets_received", 0)
                        if packets_captured_total > 0 and m_data.get("packets_processed", 0) > 0:
                            live_machine_verified = True
            except Exception as e:
                logger.debug("Live machine verification check note: %s", e)

        self._send_json_response({
            "app_name": APP_NAME,
            "version": __version__,
            "status": "READY",
            "session_id": active_sess_id,
            "mode": canonical_mode,
            "evidence_class": evidence_class,
            "adapter": def_ad["friendly_name"] if def_ad else "None",
            "model_id": "model_lightgbm_v1",
            "npcap_detected": is_npcap_present,
            "npcap_status": npcap_res.get("status"),
            "capture_state": capture_state,
            "live_machine_verified": live_machine_verified,
            "implementation_status": "IMPLEMENTATION READY",
            "privacy": "LOCAL ONLY",
            "zero_payload": "PASS",
            "save_raw_packets": False,
        })

    def handle_adapters(self) -> None:
        """Returns detected network adapters."""
        adapters = list_adapters()
        clean_adapters = [
            {k: v for k, v in a.items() if k != "scapy_object"}
            for a in adapters
        ]
        self._send_json_response({
            "count": len(clean_adapters),
            "adapters": clean_adapters,
        })

    def handle_model(self) -> None:
        """Returns model registry details."""
        reg_path = Path("results/models/production_registry.json")
        if reg_path.exists():
            try:
                with open(reg_path, "r", encoding="utf-8") as f:
                    reg_data = json.load(f)
                self._send_json_response(reg_data)
                return
            except Exception as e:
                logger.error("Failed to load model registry for API: %s", e)

        self._send_json_response({"error": "Model registry unavailable"}, status_code=500)

    def handle_metrics(self) -> None:
        """Returns latest telemetry and performance metrics including all diagnostic counters."""
        try:
            active_sess_id = local_event_store.get_active_session_id()
            metrics_file = Path("results/realtime/metrics.json")
            data: Dict[str, Any] = {}
            telemetry_available = False
            telemetry_source = "UNAVAILABLE"

            from product.environment import check_npcap
            npcap_res = check_npcap()
            is_npcap_present = npcap_res.get("status") == "PASS"

            if metrics_file.exists():
                try:
                    with open(metrics_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    telemetry_available = True
                    telemetry_source = "REALTIME_FILE"
                except Exception as read_err:
                    logger.error("Failed to read metrics file %s: %s\n%s", metrics_file, read_err, traceback.format_exc())
                    telemetry_available = False
                    telemetry_source = "READ_ERROR"

            # Avoid leaking counters from an old completed session if a new session is active
            if active_sess_id and data.get("session_id") and data.get("session_id") != active_sess_id:
                for k in [
                    "total_packets", "total_bytes", "live_packets_received", "packets_forwarded_to_flow_tracker",
                    "flows_created", "flows_updated", "active_flows", "completed_flows", "expired_flows",
                    "predictions_created", "feature_vectors_created", "flows_eligible_for_prediction",
                    "capture_packets_received", "packets_forwarded_to_processor", "packets_processed",
                    "packets_dropped", "processing_errors", "features_extracted", "feature_extraction_failures",
                    "predictions_generated", "known_predictions", "low_confidence_predictions",
                    "unknown_predictions", "insufficient_evidence_predictions", "events_created",
                    "events_stored", "event_storage_failures",
                    "packets_per_second", "packets_per_sec", "bytes_per_second", "throughput_mbps",
                    "predictions_per_sec", "known_class_rate", "low_confidence_rate", "unknown_rate",
                ]:
                    data[k] = 0.0 if ("rate" in k or "sec" in k or "mbps" in k or "second" in k) else 0
                for ts_k in [
                    "last_packet_at", "last_packet_processed_at", "last_flow_created_at",
                    "last_feature_extracted_at", "last_prediction_at", "last_event_stored_at",
                    "last_packet_age_seconds", "last_packet_processed_age_seconds",
                    "last_flow_created_age_seconds", "last_feature_extracted_age_seconds",
                    "last_prediction_age_seconds", "last_event_stored_age_seconds",
                ]:
                    data[ts_k] = None
                data["session_id"] = active_sess_id
                telemetry_source = "SESSION_INITIALIZING"

            # Freshness and staleness evaluation
            now = time.time()
            metric_ts = data.get("timestamp")
            if telemetry_available and isinstance(metric_ts, (int, float)):
                telemetry_age_seconds = round(max(0.0, now - float(metric_ts)), 2)
                is_stale = telemetry_age_seconds > 5.0
            else:
                telemetry_age_seconds = None
                is_stale = not telemetry_available

            defaults = {
                "session_id": active_sess_id,
                "packets_per_second": 0.0,
                "packets_per_sec": 0.0,
                "bytes_per_second": 0.0,
                "throughput_mbps": 0.0,
                "predictions_per_sec": 0.0,
                "active_flows": 0,
                "completed_flows": 0,
                "expired_flows": 0,
                "total_packets": 0,
                "total_bytes": 0,
                "dropped_packets": 0,
                "queue_depth": 0,
                "p95_latency_ms": 0.0,
                "p99_latency_ms": 0.0,
                "avg_latency_ms": 0.0,
                "median_latency_ms": 0.0,
                "pipeline_status": "WAITING_FOR_TRAFFIC",
                "live_packets_received": 0,
                "packets_forwarded_to_flow_tracker": 0,
                "flows_created": 0,
                "flows_updated": 0,
                "flows_eligible_for_prediction": 0,
                "feature_vectors_created": 0,
                "predictions_created": 0,
                "events_stored": local_event_store.events_stored_count,

                # Phase 4 exact canonical telemetry counters
                "capture_packets_received": 0,
                "packets_forwarded_to_processor": 0,
                "packets_processed": 0,
                "packets_dropped": 0,
                "processing_errors": 0,
                "features_extracted": 0,
                "feature_extraction_failures": 0,
                "predictions_generated": 0,
                "known_predictions": 0,
                "low_confidence_predictions": 0,
                "unknown_predictions": 0,
                "insufficient_evidence_predictions": 0,
                "events_created": 0,
                "event_storage_failures": 0,
                "worker_alive": True,
                "capture_thread_alive": True,
                "capture_state": "CAPTURE_ACTIVE",
                "last_capture_error": None,
                "last_capture_error_stage": None,

                # Timestamps
                "last_packet_at": None,
                "last_packet_processed_at": None,
                "last_flow_created_at": None,
                "last_feature_extracted_at": None,
                "last_prediction_at": None,
                "last_event_stored_at": None,
                "last_packet_age_seconds": None,
                "last_packet_processed_age_seconds": None,
                "last_flow_created_age_seconds": None,
                "last_feature_extracted_age_seconds": None,
                "last_prediction_age_seconds": None,
                "last_event_stored_age_seconds": None,
            }

            for k, v in defaults.items():
                if k not in data or data[k] is None:
                    data[k] = v

            if active_sess_id:
                data["session_id"] = active_sess_id

            # Invariant: Never report nonzero performance when actual counters show no activity
            if data.get("total_packets", 0) == 0 or data.get("capture_packets_received", 0) == 0:
                data["packets_per_second"] = 0.0
                data["packets_per_sec"] = 0.0
                data["bytes_per_second"] = 0.0
                data["throughput_mbps"] = 0.0

            if data.get("predictions_generated", 0) == 0 or data.get("predictions_created", 0) == 0:
                data["predictions_per_sec"] = 0.0
                data["known_class_rate"] = 0.0
                data["low_confidence_rate"] = 0.0
                data["unknown_rate"] = 0.0

            # Independent Phase 4 subsystem verification booleans
            pkts_rcvd = data.get("capture_packets_received", 0)
            pkts_proc = data.get("packets_processed", 0)
            feats_ext = data.get("features_extracted", 0)
            preds_gen = data.get("predictions_generated", 0)
            evts_stored = data.get("events_stored", 0)
            cap_thread = bool(data.get("capture_thread_alive", True))
            work_alive = bool(data.get("worker_alive", True))

            data["api_responding"] = True
            data["npcap_available"] = is_npcap_present
            data["actual_packets_received"] = pkts_rcvd > 0
            data["packets_processed_status"] = pkts_proc > 0
            data["flows_created_status"] = data.get("flows_created", 0) > 0
            data["features_extracted_status"] = feats_ext > 0
            data["predictions_generated_status"] = preds_gen > 0
            data["events_persisted_status"] = evts_stored > 0

            # Distinguish actual zero vs unavailable metric vs stale metric vs degraded
            if not telemetry_available:
                metrics_status = "UNAVAILABLE"
                pipeline_status = "INITIALIZING"
            elif is_stale or not cap_thread or not work_alive:
                metrics_status = "STALE" if is_stale else "DEGRADED"
                pipeline_status = "DEGRADED"
            elif pkts_rcvd == 0 and data.get("pipeline_status") not in ("PIPELINE_DEGRADED", "DEGRADED"):
                metrics_status = "ACTIVE"
                pipeline_status = "WAITING_FOR_TRAFFIC"
            elif feats_ext == 0 and data.get("pipeline_status") not in ("PIPELINE_DEGRADED", "DEGRADED"):
                metrics_status = "ACTIVE"
                pipeline_status = "ACCUMULATING_EVIDENCE"
            else:
                metrics_status = "ACTIVE"
                pipeline_status = data.get("pipeline_status", "HEALTHY")

            # Compute dynamic activity age in seconds for all last-activity timestamps
            for field in ("last_packet", "last_packet_processed", "last_flow_created", "last_feature_extracted", "last_prediction", "last_event_stored"):
                ts = data.get(f"{field}_at")
                if ts is not None and isinstance(ts, (int, float)):
                    data[f"{field}_age_seconds"] = round(max(0.0, now - float(ts)), 2)
                else:
                    data[f"{field}_age_seconds"] = None

            # Add status descriptors
            data["telemetry_available"] = telemetry_available
            data["telemetry_source"] = telemetry_source
            data["is_stale"] = is_stale
            data["telemetry_age_seconds"] = telemetry_age_seconds
            data["metrics_status"] = metrics_status
            data["pipeline_status"] = pipeline_status

            self._send_json_response(data, status_code=200)
        except Exception as e:
            logger.error("Unexpected error in handle_metrics(): %s\n%s", e, traceback.format_exc())
            self._send_json_response(
                {
                    "error": "Metrics Collection Failed",
                    "message": str(e),
                    "pipeline_status": "DEGRADED",
                    "telemetry_available": False,
                    "is_stale": True,
                    "timestamp": time.time(),
                },
                status_code=500,
            )

    def handle_predictions(self, query_string: str) -> None:
        """Returns recent prediction records with strict mode segregation."""
        from product.security import sanitize_event_record

        qs = parse_qs(query_string)
        limit = int(qs.get("limit", [20])[0])
        limit = min(max(1, limit), 200)
        mode = qs.get("mode", qs.get("operating_mode", [None]))[0]
        if mode:
            mode = mode.upper()
            if mode in ("LIVE", "LIVE_MODE"):
                mode = "LIVE_NPCAP"
            elif mode in ("RECORDED", "RECORDED_CAPTURE"):
                mode = "RECORDED_CAPTURE"
            elif mode in ("DEMO", "DEMO_MODE"):
                mode = "DEMO_MODE"

        from realtime.events import EVIDENCE_CLASS_MAP
        evidence_class = EVIDENCE_CLASS_MAP.get(mode, "ALL_EVIDENCE") if mode else "ALL_EVIDENCE"
        query_sess = qs.get("session_id", [None])[0]
        active_sess_id = local_event_store.get_active_session_id()
        sess_filter = query_sess or (active_sess_id if mode in ("LIVE_NPCAP", "LIVE_MODE") else None)

        # 1. First check LocalEventStore (Strictly scoped by session for live capture)
        try:
            stored_events = local_event_store.query_events(
                limit=limit,
                operating_mode=mode if mode else None,
                session_id=sess_filter,
            )
            if stored_events:
                clean_records = []
                for ev in stored_events:
                    rec = sanitize_event_record(ev)
                    if not rec.get("predicted_class") and rec.get("prediction"):
                        rec["predicted_class"] = rec["prediction"]
                    if not rec.get("prediction") and rec.get("predicted_class"):
                        rec["prediction"] = rec["predicted_class"]
                    clean_records.append(rec)
                self._send_json_response({
                    "count": len(clean_records),
                    "limit": limit,
                    "mode": mode or "ALL",
                    "session_id": sess_filter,
                    "evidence_class": evidence_class,
                    "source": "EVENT_STORE",
                    "predictions": clean_records,
                })
                return
        except Exception as e:
            logger.warning("LocalEventStore query in API failed: %s", e)

        # 2. Strict live npcap rule: If LIVE_NPCAP requested and 0 live events exist, return empty list!
        # Do NOT leak past sessions, demo, or recorded data into live view!
        if mode in ("LIVE_NPCAP", "LIVE_MODE"):
            self._send_json_response({
                "count": 0,
                "limit": limit,
                "mode": "LIVE_NPCAP",
                "session_id": sess_filter,
                "evidence_class": "REAL_LIVE_NPCAP",
                "source": "EVENT_STORE",
                "predictions": [],
            })
            return

        # 3. For DEMO_MODE or unspecified mode, check candidate jsonl / csv files
        from product.runtime_paths import get_base_dir, get_writable_data_dir
        base_dir = get_base_dir()
        data_dir = get_writable_data_dir()

        candidate_jsonl = [
            base_dir / "results" / "realtime" / "predictions.jsonl",
            data_dir / "events" / "predictions.jsonl",
            Path("results/realtime/predictions.jsonl"),
        ]
        candidate_csv = [
            base_dir / "results" / "realtime" / "predictions.csv",
            data_dir / "events" / "predictions.csv",
            Path("results/realtime/predictions.csv"),
        ]

        records: List[Dict[str, Any]] = []

        for jsonl_path in candidate_jsonl:
            if jsonl_path.exists():
                try:
                    with open(jsonl_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    for line in lines[-limit * 2:]:
                        line = line.strip()
                        if line:
                            rec = json.loads(line)
                            rec_mode = str(rec.get("operating_mode", "")).upper()
                            if mode and rec_mode != mode:
                                continue
                            records.append(rec)
                    if records:
                        records = records[-limit:]
                        break
                except Exception as e:
                    logger.warning("Error reading predictions JSONL (%s): %s", jsonl_path, e)

        if not records:
            for csv_path in candidate_csv:
                if csv_path.exists():
                    try:
                        with open(csv_path, "r", encoding="utf-8") as f:
                            reader = csv.DictReader(f)
                            all_rows = list(reader)
                        for r in all_rows[-limit * 2:]:
                            rec_mode = str(r.get("operating_mode", "")).upper()
                            if mode and rec_mode != mode:
                                continue
                            records.append(r)
                        if records:
                            records = records[-limit:]
                            break
                    except Exception as e:
                        logger.warning("Error reading predictions CSV (%s): %s", csv_path, e)

        clean_records = []
        for r in records:
            rec = sanitize_event_record(r)
            if not rec.get("predicted_class") and rec.get("prediction"):
                rec["predicted_class"] = rec["prediction"]
            if not rec.get("prediction") and rec.get("predicted_class"):
                rec["prediction"] = rec["predicted_class"]
            clean_records.append(rec)

        self._send_json_response({
            "count": len(clean_records),
            "limit": limit,
            "mode": mode or "ALL",
            "source": "FILE_LOG",
            "predictions": clean_records,
        })

    def handle_events(self, query_string: str) -> None:
        """Queries local event store for indexed prediction/telemetry metadata."""
        qs = parse_qs(query_string)
        limit = min(max(1, int(qs.get("limit", [50])[0])), 1000)
        offset = max(0, int(qs.get("offset", [0])[0]))
        session_id = qs.get("session_id", [None])[0]
        operating_mode = qs.get("operating_mode", qs.get("mode", [None]))[0]
        prediction_state = qs.get("prediction_state", [None])[0]
        flow_id = qs.get("flow_id", [None])[0]

        events = local_event_store.query_events(
            limit=limit,
            offset=offset,
            session_id=session_id,
            operating_mode=operating_mode,
            prediction_state=prediction_state,
            flow_id=flow_id,
        )
        clean_events = []
        for ev in events:
            rec = sanitize_event_record(ev)
            if not rec.get("predicted_class") and rec.get("prediction"):
                rec["predicted_class"] = rec["prediction"]
            if not rec.get("prediction") and rec.get("predicted_class"):
                rec["prediction"] = rec["predicted_class"]
            clean_events.append(rec)

        self._send_json_response({
            "count": len(clean_events),
            "limit": limit,
            "offset": offset,
            "events": clean_events,
        })

    def handle_alerts(self, query_string: str) -> None:
        """Returns recent cybersecurity and traffic alerts."""
        qs = parse_qs(query_string)
        limit = min(max(1, int(qs.get("limit", [50])[0])), 200)
        alerts = global_alert_evaluator.get_alerts(limit=limit)
        self._send_json_response({
            "count": len(alerts),
            "alerts": alerts,
        })

    def handle_session_start(self, data: Dict[str, Any]) -> None:
        """Starts a new monitoring session."""
        session_name = data.get("session_name")
        mode = data.get("operating_mode", "LIVE_MODE")
        sess_id = local_event_store.start_session(session_name=session_name, operating_mode=mode)
        self._send_json_response({
            "status": "STARTED",
            "session_id": sess_id,
            "session_name": session_name,
            "operating_mode": mode,
        })

    def handle_session_stop(self, data: Dict[str, Any]) -> None:
        """Stops the active monitoring session and returns session summary."""
        session_id = data.get("session_id")
        summary = local_event_store.stop_session(session_id=session_id)
        self._send_json_response(summary)

    def handle_session_clear(self, data: Dict[str, Any]) -> None:
        """Clears events for a specific session or all sessions."""
        session_id = data.get("session_id")
        deleted = local_event_store.clear_session(session_id=session_id)
        self._send_json_response({
            "status": "CLEARED",
            "deleted_events": deleted,
            "session_id": session_id or "ALL",
        })

    def handle_session_export(self, query_string: str) -> None:
        """Exports event metadata to CSV via GET."""
        qs = parse_qs(query_string)
        session_id = qs.get("session_id", [None])[0]
        mode = qs.get("operating_mode", qs.get("mode", [None]))[0]
        target = qs.get("target_path", ["data/events/exported_events.csv"])[0]

        out_path = local_event_store.export_csv(
            target_path=target,
            session_id=session_id,
            operating_mode=mode,
        )
        self._send_json_response({
            "status": "EXPORTED",
            "path": str(out_path),
            "target": target,
        })

    def handle_session_export_post(self, data: Dict[str, Any]) -> None:
        """Exports event metadata to CSV via POST."""
        session_id = data.get("session_id")
        mode = data.get("operating_mode", data.get("mode"))
        target = data.get("target_path", "data/events/exported_events.csv")

        out_path = local_event_store.export_csv(
            target_path=target,
            session_id=session_id,
            operating_mode=mode,
        )
        self._send_json_response({
            "status": "EXPORTED",
            "path": str(out_path),
        })


class LocalAPIServer:
    """Manages the local HTTP server lifecycle."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8080) -> None:
        # Enforce localhost binding
        if host not in ("127.0.0.1", "localhost"):
            logger.warning("Attempted to bind API to %s. Enforcing 127.0.0.1 for local privacy.", host)
            host = "127.0.0.1"

        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        """Starts server in background daemon thread."""
        try:
            self.server = ThreadingHTTPServer((self.host, self.port), LocalAPIHandler)
            self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self._thread.start()
            logger.info("Local API server listening on http://%s:%d", self.host, self.port)
            return True
        except Exception as e:
            logger.error("Failed to start Local API Server: %s", e)
            return False

    def stop(self) -> None:
        """Stops the local server."""
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception as e:
                logger.debug("Local API server shutdown note: %s", e)
            self.server = None
            self._thread = None
            logger.info("Local API server stopped.")
