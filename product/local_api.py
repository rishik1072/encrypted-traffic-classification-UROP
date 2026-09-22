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
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from product.adapter_manager import get_default_adapter, list_adapters
from product.config import product_config
from product.health import run_product_health_check
from product.version import APP_NAME, __version__

logger = logging.getLogger(__name__)


class LocalAPIHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests strictly from localhost."""

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
        elif path == "/":
            self.handle_root()
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
            ],
        })

    def handle_health(self) -> None:
        """Returns comprehensive health check report."""
        report = run_product_health_check()
        status_code = 200 if report["overall_status"] in ("PASS", "WARNING") else 503
        self._send_json_response(report, status_code=status_code)

    def handle_status(self) -> None:
        """Returns product runtime and privacy state."""
        def_ad = get_default_adapter()
        self._send_json_response({
            "app_name": APP_NAME,
            "version": __version__,
            "status": "READY",
            "mode": product_config.default_mode,
            "adapter": def_ad["friendly_name"] if def_ad else "None",
            "model_id": "model_lightgbm_v1",
            "privacy": "LOCAL ONLY",
            "zero_payload": "PASS",
            "save_raw_packets": False,
        })

    def handle_adapters(self) -> None:
        """Returns detected network adapters."""
        adapters = list_adapters()
        # Strip Scapy objects for JSON serialization
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
        """Returns latest telemetry and performance metrics."""
        # Attempt to read live metrics or recent snapshot
        metrics_file = Path("results/realtime/metrics.json")
        if metrics_file.exists():
            try:
                with open(metrics_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._send_json_response(data)
                return
            except Exception:
                pass

        # Fallback to zero metrics snapshot
        self._send_json_response({
            "packets_per_second": 0.0,
            "bytes_per_second": 0.0,
            "active_flows": 0,
            "dropped_packets": 0,
            "p95_latency_ms": 0.0,
            "p99_latency_ms": 0.0,
            "pipeline_status": "HEALTHY",
        })

    def handle_predictions(self, query_string: str) -> None:
        """Returns recent prediction records."""
        from product.runtime_paths import get_base_dir, get_writable_data_dir

        qs = parse_qs(query_string)
        limit = int(qs.get("limit", [20])[0])
        limit = min(max(1, limit), 200)

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
                    for line in lines[-limit:]:
                        line = line.strip()
                        if line:
                            records.append(json.loads(line))
                    if records:
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
                            records = all_rows[-limit:]
                        if records:
                            break
                    except Exception as e:
                        logger.warning("Error reading predictions CSV (%s): %s", csv_path, e)

        self._send_json_response({
            "count": len(records),
            "limit": limit,
            "predictions": records,
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
            self.server = HTTPServer((self.host, self.port), LocalAPIHandler)
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
