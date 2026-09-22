"""
Unit and Integration Tests for Live-Npcap Acceptance Contract.

Verifies the strict separation between the three evidence classes:
1. REAL_LIVE_NPCAP (physical adapter capture via Npcap; fail-closed on 0 packets)
2. REAL_RECORDED_CAPTURE (genuine recorded packet replay; never labeled LIVE_MODE)
3. DEMO_SIMULATION (synthetic traffic simulation only)

And asserts the distinction between IMPLEMENTATION READY and LIVE MACHINE VERIFIED.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
import urllib.request
import pytest
from unittest.mock import patch, MagicMock

from capture.packet_capture import LiveSniffer
from dashboard.live_feed import normalize_api_record
from product.event_store import local_event_store, LocalEventStore
from product.local_api import LocalAPIServer
from realtime.events import (
    EVIDENCE_CLASS_MAP,
    OperatingMode,
    PredictionState,
    TrafficPredictionEvent,
)


def test_1_operating_mode_enum_and_evidence_classes():
    """Verify that OperatingMode enum and EVIDENCE_CLASS_MAP define the 3 evidence classes."""
    assert OperatingMode.LIVE_NPCAP.value == "LIVE_NPCAP"
    assert OperatingMode.RECORDED_CAPTURE.value == "RECORDED_CAPTURE"
    assert OperatingMode.DEMO_MODE.value == "DEMO_MODE"
    assert OperatingMode.RESEARCH_MODE.value == "RESEARCH_MODE"

    # Backward compatibility alias
    assert OperatingMode.LIVE_MODE.value == "LIVE_NPCAP"

    assert EVIDENCE_CLASS_MAP[OperatingMode.LIVE_NPCAP.value] == "REAL_LIVE_NPCAP"
    assert EVIDENCE_CLASS_MAP[OperatingMode.RECORDED_CAPTURE.value] == "REAL_RECORDED_CAPTURE"
    assert EVIDENCE_CLASS_MAP[OperatingMode.DEMO_MODE.value] == "DEMO_SIMULATION"
    assert EVIDENCE_CLASS_MAP[OperatingMode.RESEARCH_MODE.value] == "RESEARCH_BENCHMARK"


def test_2_event_schema_evidence_class_property():
    """Verify that TrafficPredictionEvent embeds and serializes evidence_class."""
    ev_live = TrafficPredictionEvent(
        flow_id="live_flow_001",
        operating_mode=OperatingMode.LIVE_NPCAP.value,
        predicted_class="Web",
        confidence=0.92,
        prediction_state=PredictionState.KNOWN_CLASS.value,
    )
    assert ev_live.evidence_class == "REAL_LIVE_NPCAP"
    d_live = ev_live.to_dict()
    assert d_live["evidence_class"] == "REAL_LIVE_NPCAP"
    assert d_live["operating_mode"] == "LIVE_NPCAP"

    ev_rec = TrafficPredictionEvent(
        flow_id="rec_flow_002",
        operating_mode=OperatingMode.RECORDED_CAPTURE.value,
        predicted_class="VoIP",
        confidence=0.88,
        prediction_state=PredictionState.KNOWN_CLASS.value,
    )
    assert ev_rec.evidence_class == "REAL_RECORDED_CAPTURE"
    d_rec = ev_rec.to_dict()
    assert d_rec["evidence_class"] == "REAL_RECORDED_CAPTURE"
    assert d_rec["operating_mode"] == "RECORDED_CAPTURE"

    ev_demo = TrafficPredictionEvent(
        flow_id="demo_flow_003",
        operating_mode=OperatingMode.DEMO_MODE.value,
        predicted_class="Video",
        confidence=0.75,
        prediction_state=PredictionState.KNOWN_CLASS.value,
    )
    assert ev_demo.evidence_class == "DEMO_SIMULATION"
    d_demo = ev_demo.to_dict()
    assert d_demo["evidence_class"] == "DEMO_SIMULATION"
    assert d_demo["operating_mode"] == "DEMO_MODE"


def test_3_event_store_strictly_isolates_evidence_classes():
    """Verify LocalEventStore records evidence_class and enforces strict mode querying."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_store.db"
        store = LocalEventStore(db_path=db_path)

        ev_live = TrafficPredictionEvent(
            flow_id="flow_live",
            operating_mode=OperatingMode.LIVE_NPCAP.value,
            predicted_class="Web",
            confidence=0.95,
            prediction_state=PredictionState.KNOWN_CLASS.value,
        )
        ev_rec = TrafficPredictionEvent(
            flow_id="flow_rec",
            operating_mode=OperatingMode.RECORDED_CAPTURE.value,
            predicted_class="DNS",
            confidence=0.85,
            prediction_state=PredictionState.KNOWN_CLASS.value,
        )
        ev_demo = TrafficPredictionEvent(
            flow_id="flow_demo",
            operating_mode=OperatingMode.DEMO_MODE.value,
            predicted_class="File Transfer",
            confidence=0.70,
            prediction_state=PredictionState.KNOWN_CLASS.value,
        )

        store.record_event(ev_live)
        store.record_event(ev_rec)
        store.record_event(ev_demo)

        # Query LIVE_NPCAP
        live_rows = store.query_events(operating_mode=OperatingMode.LIVE_NPCAP.value)
        assert len(live_rows) == 1
        assert live_rows[0]["flow_id"] == "flow_live"
        assert live_rows[0]["operating_mode"] == "LIVE_NPCAP"
        assert live_rows[0]["evidence_class"] == "REAL_LIVE_NPCAP"

        # Query RECORDED_CAPTURE
        rec_rows = store.query_events(operating_mode=OperatingMode.RECORDED_CAPTURE.value)
        assert len(rec_rows) == 1
        assert rec_rows[0]["flow_id"] == "flow_rec"
        assert rec_rows[0]["operating_mode"] == "RECORDED_CAPTURE"
        assert rec_rows[0]["evidence_class"] == "REAL_RECORDED_CAPTURE"

        # Query DEMO_MODE
        demo_rows = store.query_events(operating_mode=OperatingMode.DEMO_MODE.value)
        assert len(demo_rows) == 1
        assert demo_rows[0]["flow_id"] == "flow_demo"
        assert demo_rows[0]["operating_mode"] == "DEMO_MODE"
        assert demo_rows[0]["evidence_class"] == "DEMO_SIMULATION"


def test_4_rest_status_endpoint_evidence_and_implementation_status():
    """Verify REST /status reports evidence_class and IMPLEMENTATION READY vs LIVE MACHINE VERIFIED."""
    test_port = 18881
    server = LocalAPIServer(host="127.0.0.1", port=test_port)
    assert server.start() is True
    time.sleep(0.3)

    try:
        from unittest.mock import patch
        with patch("product.local_api.get_default_adapter", return_value={"friendly_name": "Wi-Fi"}), \
             patch("product.environment.check_npcap", return_value={"status": "PASS"}):
            url = f"http://127.0.0.1:{test_port}/status"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            assert "evidence_class" in data
            assert "implementation_status" in data
            assert "live_machine_verified" in data
            assert "npcap_detected" in data

            assert data["implementation_status"] == "IMPLEMENTATION READY"
            # Unless physical Npcap capture has captured actual packets on host, live_machine_verified must be False
            assert data["live_machine_verified"] is False
    finally:
        server.stop()


def test_5_rest_predictions_endpoint_no_recorded_or_demo_in_live():
    """Verify REST /predictions never returns recorded or demo events when mode=LIVE_NPCAP."""
    test_port = 18882
    server = LocalAPIServer(host="127.0.0.1", port=test_port)
    assert server.start() is True
    time.sleep(0.3)

    try:
        # Clear existing events in local_event_store
        local_event_store.clear_session()

        # Seed only recorded and demo events
        local_event_store.record_event(TrafficPredictionEvent(
            flow_id="rec_01",
            operating_mode=OperatingMode.RECORDED_CAPTURE.value,
            predicted_class="Web",
        ))
        local_event_store.record_event(TrafficPredictionEvent(
            flow_id="demo_01",
            operating_mode=OperatingMode.DEMO_MODE.value,
            predicted_class="Video",
        ))

        # Request LIVE_NPCAP
        req_live = urllib.request.Request(f"http://127.0.0.1:{test_port}/predictions?mode=LIVE_NPCAP&limit=50")
        with urllib.request.urlopen(req_live, timeout=2.0) as resp:
            live_res = json.loads(resp.read().decode("utf-8"))

        assert live_res["evidence_class"] == "REAL_LIVE_NPCAP"
        assert live_res["mode"] == "LIVE_NPCAP"
        # Zero live events recorded; MUST NOT fall back to recorded or demo!
        assert len(live_res["predictions"]) == 0

        # Request RECORDED_CAPTURE
        req_rec = urllib.request.Request(f"http://127.0.0.1:{test_port}/predictions?mode=RECORDED_CAPTURE&limit=50")
        with urllib.request.urlopen(req_rec, timeout=2.0) as resp:
            rec_res = json.loads(resp.read().decode("utf-8"))

        assert rec_res["evidence_class"] == "REAL_RECORDED_CAPTURE"
        assert rec_res["mode"] == "RECORDED_CAPTURE"
        assert len(rec_res["predictions"]) == 1
        assert rec_res["predictions"][0]["flow_id"] == "rec_01"
    finally:
        server.stop()


def test_6_dashboard_normalizer_rejects_cross_mode_pollution():
    """Verify normalize_api_record strictly rejects records from foreign operating modes."""
    rec_event = {
        "flow_id": "rec_f1",
        "operating_mode": "RECORDED_CAPTURE",
        "predicted_class": "Web",
        "confidence": 0.90,
    }
    demo_event = {
        "flow_id": "demo_f1",
        "operating_mode": "DEMO_MODE",
        "predicted_class": "Web",
        "confidence": 0.90,
    }
    live_event = {
        "flow_id": "live_f1",
        "operating_mode": "LIVE_NPCAP",
        "predicted_class": "Web",
        "confidence": 0.90,
    }

    # In LIVE_NPCAP mode: must reject rec_event and demo_event
    canon, valid, reason = normalize_api_record(rec_event, target_mode="LIVE_NPCAP")
    assert canon is None
    assert "wrong operating mode" in reason

    canon, valid, reason = normalize_api_record(demo_event, target_mode="LIVE_NPCAP")
    assert canon is None
    assert "wrong operating mode" in reason

    canon, valid, reason = normalize_api_record(live_event, target_mode="LIVE_NPCAP")
    assert canon is not None
    assert canon.flow_id == "live_f1"

    # In RECORDED_CAPTURE mode: must reject live_event and demo_event
    canon, valid, reason = normalize_api_record(live_event, target_mode="RECORDED_CAPTURE")
    assert canon is None
    assert "wrong operating mode" in reason


def test_7_zero_packet_live_capture_fails_closed():
    """Verify that 0-packet capture in live mode is a failure and fails closed without synthetic fallback."""
    sniffer = LiveSniffer(interface="Wi-Fi")
    captured = []

    def mock_sniff(*args, **kwargs):
        # Emulate zero packets captured by sniffer
        return []

    with patch("capture.packet_capture._default_sniff", side_effect=mock_sniff), \
         patch("capture.interface_resolver.resolve_capture_interface", return_value={"friendly_name": "Wi-Fi", "network_name": r"\Device\NPF_Test", "scapy_object": "Wi-Fi"}), \
         patch.object(sniffer, "check_capture_prerequisites", return_value=None):
        sniffer.start_sniffing(callback=lambda p: captured.append(p), duration_seconds=0.1)

    # 0 packets captured
    assert sniffer.packets_captured_count == 0
    assert len(captured) == 0
    # Must NOT have fallen back to synthetic or demo data
    assert len(captured) == 0
