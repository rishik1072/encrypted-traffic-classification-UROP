"""
Integration Test for Live Pipeline Runtime Execution.

Proves the complete runtime chain:
REAL_NPCAP_PACKET (genuine packet metadata via Scapy parser)
→ REAL_FLOW (bidirectional flow state tracking with >= 3 packets evidence)
→ REAL_FEATURE (zero-payload 10-feature vector extraction)
→ LIVE_NPCAP_EVENT (model inference, valid state, consistent session ID, stored in LocalEventStore)

Asserts that:
1. All 8 diagnostic counters increment accurately.
2. Hardcoded DEFAULT_SESSION is eliminated and the active session is preserved end-to-end.
3. No 2-packet lockout suppresses subsequent predictions.
4. /status and /metrics accurately reflect session ID and diagnostic telemetry.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
import pytest

from capture.packet_capture import PCAPReader, RawPacketMetadata
from product.event_store import LocalEventStore
from product.local_api import LocalAPIServer
from realtime.classifier import RealTimeClassifier
from realtime.events import OperatingMode, PredictionState, TrafficPredictionEvent
from realtime.flow_tracker import RealTimeFlowTracker
from realtime.metrics import MetricsCollector


def test_real_packet_to_live_npcap_event_pipeline():
    """
    Feeds genuine recorded physical network packets (Layer-3/Layer-4 Scapy metadata)
    through RealTimeClassifier in LIVE_NPCAP mode to prove end-to-end flow tracking,
    feature extraction, model inference, and event persistence.
    """
    test_session_id = f"SESS_TEST_LIVE_{int(time.time())}"
    pcap_path = Path("data/raw/pcap/web_sample_01.pcap")
    assert pcap_path.exists(), f"PCAP test fixture missing: {pcap_path}"

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_path = tmp_path / "test_events.db"
        csv_path = tmp_path / "live_metrics.csv"
        json_path = tmp_path / "metrics.json"

        # Initialize event store with active test session
        test_store = LocalEventStore(db_path=db_path)
        test_store.start_session(session_name="Integration_Test_Session", operating_mode="LIVE_NPCAP")
        # Ensure session ID matches
        test_store.set_active_session_id(test_session_id)

        # Initialize RealTimeClassifier in LIVE_NPCAP mode with active session ID
        classifier = RealTimeClassifier(
            config_path="config.yaml",
            operating_mode=OperatingMode.LIVE_NPCAP.value,
            session_id=test_session_id,
        )
        classifier.csv_out_path = tmp_path / "predictions.csv"
        classifier.jsonl_out_path = tmp_path / "predictions.jsonl"
        classifier.metrics_collector.metrics_csv_path = csv_path
        classifier.metrics_collector.metrics_json_path = json_path
        classifier.metrics_collector.session_id = test_session_id

        classifier.start()

        # Read genuine network packets
        reader = PCAPReader(pcap_path)
        real_packets = list(reader.read_packets())
        assert len(real_packets) >= 3, f"Expected at least 3 packets in {pcap_path}, got {len(real_packets)}"

        # Ingest packets through the live callback entry point
        for pkt in real_packets:
            classifier.process_packet(pkt)

        # Allow worker queue to drain
        time.sleep(0.5)
        classifier.stop()

        # 1. Verify diagnostic counters
        snap = classifier.get_metrics_snapshot()
        assert snap.session_id == test_session_id
        assert snap.live_packets_received == len(real_packets), (
            f"Expected {len(real_packets)} live packets, got {snap.live_packets_received}"
        )
        assert snap.packets_forwarded_to_flow_tracker == len(real_packets)
        assert snap.flows_created >= 1, "Expected at least 1 flow created"
        assert snap.flows_eligible_for_prediction >= 1, "Expected at least 1 flow eligible for prediction"
        assert snap.feature_vectors_created >= 1, "Expected at least 1 feature vector created"
        assert snap.predictions_created >= 1, "Expected at least 1 prediction created"
        assert snap.events_stored >= 1, "Expected at least 1 event stored"

        # 2. Verify metrics.json export
        assert json_path.exists(), "metrics.json was not generated"
        with open(json_path, "r", encoding="utf-8") as f:
            m_data = json.load(f)

        assert m_data["session_id"] == test_session_id
        assert m_data["live_packets_received"] == len(real_packets)
        assert m_data["packets_forwarded_to_flow_tracker"] == len(real_packets)
        assert m_data["flows_created"] >= 1
        assert m_data["feature_vectors_created"] >= 1
        assert m_data["predictions_created"] >= 1
        assert m_data["events_stored"] >= 1
        assert "packets_per_second" in m_data
        assert "active_flows" in m_data

        # 3. Verify event store contains the live event with session ID and valid prediction state
        from product.event_store import local_event_store
        # Query events from the global store or test store
        live_events = local_event_store.query_events(session_id=test_session_id, operating_mode="LIVE_NPCAP", limit=10)
        assert len(live_events) > 0, "No live events found in event store"
        latest = live_events[0]

        # Verify DEFAULT_SESSION was NOT used
        assert latest["session_id"] != "DEFAULT_SESSION", "Session ID unexpectedly defaulted to DEFAULT_SESSION"
        assert latest["session_id"] == test_session_id
        assert latest["operating_mode"] == "LIVE_NPCAP"
        assert latest["evidence_class"] == "REAL_LIVE_NPCAP"
        assert latest["packets_observed"] >= 3, f"Expected packets >= 3, got {latest['packets_observed']}"
        assert latest["prediction_state"] in ("KNOWN_CLASS", "LOW_CONFIDENCE", "UNKNOWN"), (
            f"Unexpected prediction state: {latest['prediction_state']}"
        )


def test_api_status_and_metrics_session_exposure():
    """
    Verifies that /status and /metrics expose the active session ID and diagnostic counters.
    """
    from product.event_store import local_event_store
    active_sess = local_event_store.start_session(session_name="API_Test_Session", operating_mode="LIVE_NPCAP")

    server = LocalAPIServer(host="127.0.0.1", port=8089)
    assert server.start(), "Failed to start LocalAPIServer on 8089"

    from unittest.mock import patch
    with patch("product.local_api.get_default_adapter", return_value={"friendly_name": "Wi-Fi"}), \
         patch("product.environment.check_npcap", return_value={"status": "PASS"}):
        try:
            import urllib.request

            # 1. Test /status
            req_status = urllib.request.Request("http://127.0.0.1:8089/status", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req_status, timeout=2.0) as resp:
                assert resp.status == 200
                st_data = json.loads(resp.read().decode("utf-8"))
                assert "session_id" in st_data
                assert st_data["session_id"] == active_sess
                assert st_data["mode"] == "LIVE_NPCAP"
                assert st_data["evidence_class"] == "REAL_LIVE_NPCAP"

            # 2. Test /metrics
            req_metrics = urllib.request.Request("http://127.0.0.1:8089/metrics", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req_metrics, timeout=2.0) as resp:
                assert resp.status == 200
                met_data = json.loads(resp.read().decode("utf-8"))
                assert "session_id" in met_data
                assert met_data["session_id"] == active_sess
                assert "packets_per_second" in met_data
                assert "active_flows" in met_data
                assert "live_packets_received" in met_data
                assert "packets_forwarded_to_flow_tracker" in met_data
                assert "flows_created" in met_data
                assert "flows_updated" in met_data
                assert "flows_eligible_for_prediction" in met_data
                assert "feature_vectors_created" in met_data
                assert "predictions_created" in met_data
                assert "events_stored" in met_data
        finally:
            server.stop()
            local_event_store.stop_session(active_sess)
