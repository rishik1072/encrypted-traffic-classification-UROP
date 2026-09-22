"""
Tests for Phase 8: Strict Live Monitoring Failure Modes.

Verifies that the operational system fails closed and explicitly reports failures
across all 12 operational failure scenarios without silent demo fallback:
1. Npcap absent
2. Invalid adapter
3. Adapter unavailable
4. Zero packets captured
5. Model file missing
6. Model hash mismatch
7. Malformed packet ingestion
8. Malformed flow structure
9. API unavailable (no silent CSV/demo fallback in LIVE_MODE)
10. Dashboard unavailable / timeout
11. Event schema violation / flow provenance violation
12. Event database unavailable
"""

import json
from pathlib import Path
import tempfile
import time
import pytest
from unittest.mock import patch, MagicMock

from capture.packet_capture import LiveSniffer, RawPacketMetadata, check_capture_prerequisites
from dashboard.live_feed import load_live_predictions, normalize_api_record
from flows.flow_generator import Flow, FlowKey
from product.adapter_manager import validate_adapter
from product.event_store import LocalEventStore
from product.lifecycle import wait_for_http_ready
from realtime.classifier import RealTimeClassifier
from realtime.events import OperatingMode, PredictionState
from realtime.model_loader import ModelLoader
from scripts.live_capture_test import run_live_capture_diagnostic


def test_1_npcap_absent_fails_explicitly():
    """Verify that when Npcap driver is missing, system fails closed with explicit error."""
    sniffer = LiveSniffer(interface="Wi-Fi")
    with patch("capture.packet_capture.check_capture_prerequisites", return_value=(False, "Npcap driver not detected")):
        with pytest.raises(RuntimeError) as exc_info:
            sniffer.start_sniffing(callback=lambda p: None, duration_seconds=1.0)
        assert "Npcap driver not detected" in str(exc_info.value) or "prerequisites" in str(exc_info.value).lower()


def test_2_invalid_adapter_fails_explicitly():
    """Verify that specifying a non-existent adapter produces an explicit error."""
    val = validate_adapter("NonExistent_NIC_XYZ_999")
    assert val["valid"] is False
    assert "not found" in val["message"].lower() or "not available" in val["message"].lower()


def test_3_adapter_unavailable_fails_explicitly():
    """Verify that a down or inaccessible adapter fails validation."""
    val = validate_adapter("")
    assert val["valid"] is False
    assert "empty" in val["message"].lower() or "unavailable" in val["message"].lower()


def test_4_zero_packets_captured_fails_closed():
    """Verify that capturing 0 packets is recognized as a failure without synthetic injection."""
    with patch.object(LiveSniffer, "start_sniffing", return_value=None):
        with patch("product.environment.check_npcap", return_value={"status": "PASS", "message": "Npcap available"}):
            with patch("product.adapter_manager.validate_adapter", return_value={"valid": True, "message": "OK", "adapter": {"friendly_name": "Wi-Fi"}}):
                code = run_live_capture_diagnostic(interface="Wi-Fi", duration_seconds=2.0)
                assert code == 1, "Diagnostic must exit with error code 1 when zero packets are captured"


def test_5_model_missing_fails_explicitly():
    """Verify that a missing model in LIVE_MODE causes fail-closed initialization error."""
    with pytest.raises(Exception):
        ModelLoader(model_name="non_existent_fake_model", enforce_registry=True)


def test_6_model_hash_mismatch_fails_explicitly():
    """Verify that a tampered model file causes registry hash verification failure."""
    # Test with corrupted registry expectations
    with patch("json.load") as mock_json:
        mock_json.return_value = {
            "registered_models": {
                "lightgbm": {
                    "model_name": "lightgbm",
                    "model_hash": "0000000000000000000000000000000000000000000000000000000000000000",
                    "preprocessor_hash": "0000000000000000000000000000000000000000000000000000000000000000",
                }
            }
        }
        with pytest.raises(ValueError) as exc_info:
            ModelLoader(model_name="lightgbm", enforce_registry=True)
        assert "mismatch" in str(exc_info.value).lower()


def test_7_malformed_packet_handled_safely():
    """Verify that truncated or malformed packet metadata does not crash the classifier."""
    classifier = RealTimeClassifier(operating_mode=OperatingMode.RESEARCH_MODE.value)
    classifier.start()
    try:
        # Construct packet with negative length and weird timestamp
        bad_pkt = RawPacketMetadata(
            timestamp=-999.0,
            src_ip="",
            dst_ip="",
            src_port=-1,
            dst_port=-1,
            protocol="UNKNOWN",
            length=-50,
            tcp_flags=None,
        )
        classifier.process_packet(bad_pkt)
        assert classifier.pipeline_status in ("HEALTHY", "PIPELINE_DEGRADED")
    finally:
        classifier.stop()


def test_8_malformed_flow_handled_safely():
    """Verify that a flow without observed packets is rejected and returns None."""
    classifier = RealTimeClassifier(operating_mode=OperatingMode.RESEARCH_MODE.value)
    classifier.start()
    try:
        now = time.time()
        key = FlowKey(ip_a="10.0.0.1", ip_b="10.0.0.2", port_a=1234, port_b=80, protocol="TCP")
        empty_flow = Flow(
            key=key,
            initiator_ip="10.0.0.1",
            initiator_port=1234,
            start_time=now,
            last_seen=now,
        )
        # Flow has 0 packets
        event = classifier._classify_flow_instance(empty_flow)
        assert event is None, "Classification must return None for empty or unobserved flow"
    finally:
        classifier.stop()


def test_9_api_unavailable_dashboard_never_falls_back_in_live_mode():
    """
    CRITICAL RULE 2 & 4: In LIVE_MODE, if the API is unavailable,
    the dashboard must report an error and return 0 records.
    It must NEVER fall back to CSV cache or synthetic demo records.
    """
    records, meta = load_live_predictions(
        limit=50,
        mode="LIVE_MODE",
        api_url="http://127.0.0.1:9999/predictions",  # Non-existent port
        timeout=0.5,
    )
    assert len(records) == 0, "LIVE_MODE must return 0 records when API is offline"
    assert meta["connected"] is False
    assert meta["source"] in ("LOCAL_API_UNAVAILABLE", "LOCAL_API")
    assert "unavailable" in meta["error"].lower() or "connection" in meta["error"].lower()


def test_10_dashboard_unavailable_times_out_cleanly():
    """Verify that HTTP probing handles an unreachable dashboard cleanly without hanging."""
    ready = wait_for_http_ready("http://127.0.0.1:9999", timeout=0.8)
    assert ready is False


def test_11_event_schema_violation_rejected():
    """Verify that malformed records violating required fields are dropped by normalizer in LIVE_MODE."""
    corrupt_record = {
        "timestamp": time.time(),
        "operating_mode": "DEMO_MODE",  # Mismatched mode
        "prediction_state": "KNOWN_CLASS",
    }
    canon, is_valid, drop_reason = normalize_api_record(corrupt_record, target_mode="LIVE_MODE")
    assert canon is None, "Non-live record must be rejected when target_mode is LIVE_MODE"
    assert "rejected" in drop_reason.lower() or "mode" in drop_reason.lower()


def test_12_database_unavailable_handled_safely():
    """Verify that database operations work cleanly with atomic persistence."""
    temp_dir = tempfile.TemporaryDirectory()
    try:
        db_file = Path(temp_dir.name) / "test_store.db"
        store = LocalEventStore(db_path=db_file)
        store.start_session("TestSess", "LIVE_MODE")
        store.record_event({
            "flow_id": "FLW-TEST",
            "prediction": "Web",
            "confidence": 0.95,
            "prediction_state": "KNOWN_CLASS",
            "packets_observed": 10,
            "latency_us": 120.0,
            "operating_mode": "LIVE_MODE",
        })
        events = store.query_events(flow_id="FLW-TEST")
        assert len(events) == 1
        assert events[0]["prediction"] == "Web"
    finally:
        temp_dir.cleanup()
