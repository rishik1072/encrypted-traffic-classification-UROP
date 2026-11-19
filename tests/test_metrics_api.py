"""
Unit and Integration Tests for Product Local REST API /metrics Endpoint.

Verifies:
1. GET /metrics returns HTTP 200.
2. Response contains valid JSON.
3. time.time() references execute correctly.
4. Repeated metrics requests do not crash.
5. Current session ID is included.
6. Counters come from actual runtime telemetry.
7. Stale metrics are correctly identified.
8. API remains available after a failed request.
"""

from __future__ import annotations

import json
from pathlib import Path
import time
import urllib.error
import urllib.request
from unittest.mock import patch
import pytest

from product.event_store import local_event_store
from product.local_api import LocalAPIServer


def test_metrics_api_comprehensive():
    """Verifies all 8 requirements for /metrics stability and telemetry accuracy."""
    test_session_id = f"SESS_METRICS_TEST_{int(time.time())}"
    local_event_store.start_session(session_name="Metrics_Test_Session", operating_mode="LIVE_NPCAP")
    local_event_store.set_active_session_id(test_session_id)

    server = LocalAPIServer(host="127.0.0.1", port=8091)
    assert server.start(), "Failed to start LocalAPIServer on 8091"

    metrics_file = Path("results/realtime/metrics.json")
    metrics_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Create genuine telemetry fixture
        now_ts = time.time()
        telemetry_payload = {
            "timestamp": now_ts,
            "session_id": test_session_id,
            "pipeline_status": "HEALTHY",
            "active_flows": 3,
            "completed_flows": 1,
            "expired_flows": 0,
            "total_packets": 142,
            "total_bytes": 65400,
            "packets_per_second": 28.4,
            "packets_per_sec": 28.4,
            "bytes_per_second": 13080.0,
            "throughput_mbps": 0.1046,
            "predictions_per_sec": 2.0,
            "avg_latency_ms": 1.25,
            "median_latency_ms": 1.20,
            "p95_latency_ms": 1.80,
            "p99_latency_ms": 2.10,
            "dropped_packets": 0,
            "queue_depth": 0,
            "capture_packets_received": 142,
            "packets_forwarded_to_processor": 142,
            "packets_processed": 142,
            "packets_dropped": 0,
            "processing_errors": 0,
            "flows_created": 4,
            "flows_updated": 138,
            "flows_eligible_for_prediction": 3,
            "features_extracted": 3,
            "feature_extraction_failures": 0,
            "predictions_generated": 3,
            "known_predictions": 3,
            "low_confidence_predictions": 0,
            "unknown_predictions": 0,
            "insufficient_evidence_predictions": 0,
            "events_created": 3,
            "events_stored": 3,
            "event_storage_failures": 0,
            "worker_alive": True,
            "capture_thread_alive": True,
            "last_packet_at": now_ts - 0.5,
            "last_packet_processed_at": now_ts - 0.4,
            "last_flow_created_at": now_ts - 10.0,
            "last_feature_extracted_at": now_ts - 1.0,
            "last_prediction_at": now_ts - 1.0,
            "last_event_stored_at": now_ts - 1.0,
        }
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(telemetry_payload, f)

        # 1. GET /metrics returns HTTP 200
        req = urllib.request.Request("http://127.0.0.1:8091/metrics")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            assert resp.status == 200

            # 2. Response contains valid JSON
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            assert isinstance(data, dict)

        # 3. time.time() references execute correctly
        assert "last_packet_age_seconds" in data
        assert data["last_packet_age_seconds"] is not None
        assert data["last_packet_age_seconds"] >= 0.0

        # 4. Repeated metrics requests do not crash
        for _ in range(15):
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                assert resp.status == 200
                d = json.loads(resp.read().decode("utf-8"))
                assert d["session_id"] == test_session_id

        # 5. Current session ID is included
        assert data["session_id"] == test_session_id

        # 6. Counters come from actual runtime telemetry
        assert data["capture_packets_received"] == 142
        assert data["packets_processed"] == 142
        assert data["active_flows"] == 3
        assert data["predictions_generated"] == 3
        assert data["telemetry_available"] is True
        assert data["is_stale"] is False
        assert data["metrics_status"] == "ACTIVE"

        # 7. Stale metrics are correctly identified
        stale_payload = dict(telemetry_payload)
        stale_payload["timestamp"] = time.time() - 20.0  # 20 seconds old
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(stale_payload, f)

        with urllib.request.urlopen(req, timeout=3.0) as resp:
            assert resp.status == 200
            stale_data = json.loads(resp.read().decode("utf-8"))
            assert stale_data["is_stale"] is True
            assert stale_data["metrics_status"] == "STALE"
            assert stale_data["telemetry_age_seconds"] >= 19.0

        # 8. API remains available after a failed request
        with patch.object(Path, "exists", side_effect=RuntimeError("Simulated disk error")):
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen("http://127.0.0.1:8091/metrics", timeout=3.0)
            assert exc_info.value.code == 500
            err_body = json.loads(exc_info.value.read().decode("utf-8"))
            assert err_body["error"] == "Metrics Collection Failed"
            assert err_body["pipeline_status"] == "DEGRADED"

        # Verify API remains available and recovers on subsequent request
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            assert resp.status == 200
            recovered_data = json.loads(resp.read().decode("utf-8"))
            assert recovered_data["session_id"] == test_session_id

    finally:
        server.stop()
        local_event_store.stop_session(test_session_id)
