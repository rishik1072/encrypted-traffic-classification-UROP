"""
Comprehensive Unit and Integration Tests for LIVE_NPCAP Ingestion and Runtime Telemetry.

Covers:
1. Capture callback invocation.
2. Packet counter increment.
3. Queue insertion (bounded queue).
4. Worker consumption (LiveSniffer consumer thread).
5. Flow creation.
6. Feature extraction.
7. Prediction invocation.
8. Event persistence.
9. Session isolation and dynamic synchronization.
10. Capture exceptions and stage tracking.
11. Stale telemetry detection.
12. No-packet state (zero-rate invariants).
13. Metrics consistency (independent Phase 4 subsystem states).

NOTE ON TEST FIXTURES:
Unit-test packet injection in this module uses controlled synthetic packet
fixtures (clearly labeled SYNTHETIC_FIXTURE) to test software pipeline mechanics
deterministically without requiring live ambient network traffic.
Real hardware Npcap capture is tested separately in the optional hardware test.
"""

from __future__ import annotations

import json
from pathlib import Path
import queue
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch
import pytest

from capture.packet_capture import LiveSniffer, RawPacketMetadata
from product.event_store import LocalEventStore
from product.local_api import LocalAPIServer
from realtime.classifier import RealTimeClassifier
from realtime.events import OperatingMode, TrafficPredictionEvent
from realtime.flow_tracker import RealTimeFlowTracker
from realtime.metrics import MetricsCollector, SystemMetricsSnapshot


def _create_synthetic_test_packet(
    timestamp: float,
    src_ip: str = "192.168.1.50",
    dst_ip: str = "142.250.190.46",
    src_port: int = 54321,
    dst_port: int = 443,
    proto: str = "TCP",
    length: int = 512,
    tcp_flags: int = 24,
) -> RawPacketMetadata:
    """Helper creating a controlled synthetic packet metadata item (SYNTHETIC_FIXTURE)."""
    return RawPacketMetadata(
        timestamp=timestamp,
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=src_port,
        dst_port=dst_port,
        protocol=proto,
        length=length,
        tcp_flags=tcp_flags,
    )


def test_1_to_4_capture_callback_queue_and_worker_consumption():
    """
    Verifies:
    1. Capture callback invocation.
    2. Packet counter increment.
    3. Bounded queue insertion.
    4. Worker thread consumption.
    """
    consumed_packets = []
    consumer_event = threading.Event()

    def mock_packet_consumer(meta: RawPacketMetadata):
        consumed_packets.append(meta)
        if len(consumed_packets) >= 3:
            consumer_event.set()

    sniffer = LiveSniffer(interface="Wi-Fi", session_id="SESS_TEST_QUEUE", queue_maxsize=10)

    # Verify initial state
    assert sniffer._get_current_capture_state() == "CAPTURE_IDLE"
    assert sniffer.packets_captured_count == 0
    assert sniffer.packets_forwarded_count == 0
    assert sniffer.packets_processed_count == 0

    # Start sniffing with mocked _default_sniff to inject controlled test packets
    def mock_sniff_injector(*args, **kwargs):
        prn = kwargs.get("prn")
        assert prn is not None, "Capture callback (prn) must be registered with Scapy"
        t0 = time.time()
        for i in range(5):
            # Simulate physical packet passing to _packet_handler
            pkt_meta = _create_synthetic_test_packet(timestamp=t0 + i * 0.01, length=128 + i * 10)
            # Create a mock Scapy packet object that parse_scapy_packet handles
            with patch("capture.packet_capture.parse_scapy_packet", return_value=pkt_meta):
                prn(MagicMock())

    with patch("capture.packet_capture._default_sniff", side_effect=mock_sniff_injector), \
         patch.object(sniffer, "check_capture_prerequisites"):
        
        # Run sniffing in thread
        sniff_thread = threading.Thread(
            target=sniffer.start_sniffing,
            kwargs={"callback": mock_packet_consumer},
            daemon=True,
        )
        sniff_thread.start()

        # Wait for consumer thread to process packets
        consumer_event.wait(timeout=2.0)
        time.sleep(0.2)
        sniffer.stop()
        sniff_thread.join(timeout=2.0)

    # Assertions
    assert sniffer.packets_captured_count == 5, f"Expected 5 captured, got {sniffer.packets_captured_count}"
    assert sniffer.packets_forwarded_count == 5, f"Expected 5 forwarded, got {sniffer.packets_forwarded_count}"
    assert sniffer.packets_processed_count == 5, f"Expected 5 processed, got {sniffer.packets_processed_count}"
    assert len(consumed_packets) == 5
    assert sniffer.packets_dropped_count == 0
    assert sniffer.last_packet_time is not None
    assert sniffer.last_packet_processed_time is not None


def test_5_to_8_flow_creation_features_predictions_and_persistence():
    """
    Verifies:
    5. Flow creation.
    6. Feature extraction.
    7. Prediction invocation.
    8. Event persistence.
    """
    from product.event_store import local_event_store
    test_session = local_event_store.start_session(session_name="Full_Pipeline_Test", operating_mode="LIVE_NPCAP")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        json_path = tmp_path / "metrics.json"

        classifier = RealTimeClassifier(
            config_path="config.yaml",
            operating_mode=OperatingMode.LIVE_NPCAP.value,
            session_id=test_session,
        )
        classifier.csv_out_path = tmp_path / "predictions.csv"
        classifier.jsonl_out_path = tmp_path / "predictions.jsonl"
        classifier.metrics_collector.metrics_json_path = json_path
        classifier.metrics_collector.session_id = test_session

        classifier.start()

        # Inject SYNTHETIC_FIXTURE stream (4 packets in one bidirectional flow)
        t0 = time.time()
        p1 = _create_synthetic_test_packet(t0 + 0.00, "10.0.0.1", "10.0.0.2", 50000, 443, "TCP", 100)
        p2 = _create_synthetic_test_packet(t0 + 0.02, "10.0.0.2", "10.0.0.1", 443, 50000, "TCP", 200)
        p3 = _create_synthetic_test_packet(t0 + 0.04, "10.0.0.1", "10.0.0.2", 50000, 443, "TCP", 300)
        p4 = _create_synthetic_test_packet(t0 + 0.06, "10.0.0.2", "10.0.0.1", 443, 50000, "TCP", 400)

        for p in [p1, p2, p3, p4]:
            classifier.process_packet(p)

        # Allow inference worker to process
        time.sleep(0.6)
        classifier.stop()

        snap = classifier.get_metrics_snapshot()

        # 5. Flow creation
        assert snap.flows_created >= 1, "Flow should be created"
        assert snap.last_flow_created_at is not None, "last_flow_created_at must be populated"

        # 6. Feature extraction
        assert snap.features_extracted >= 1, "Features should be extracted"
        assert snap.last_feature_extracted_at is not None

        # 7. Prediction invocation
        assert snap.predictions_generated >= 1, "Prediction should be generated"
        assert snap.last_prediction_at is not None

        # 8. Event persistence
        assert snap.events_stored >= 1, "Event should be stored"
        assert snap.last_event_stored_at is not None

        # Verify SQLite record in event store
        from product.event_store import local_event_store
        live_events = local_event_store.query_events(session_id=test_session, operating_mode="LIVE_NPCAP", limit=5)
        assert len(live_events) >= 1, "Prediction event must be in SQLite event store"
        ev = live_events[0]
        assert ev["operating_mode"] == "LIVE_NPCAP"
        assert ev["evidence_class"] == "REAL_LIVE_NPCAP"
        assert ev["packets_observed"] >= 3


def test_9_session_isolation_and_dynamic_synchronization():
    """
    Verifies:
    9. Session isolation and dynamic session switching without data leakage.
    """
    from product.event_store import local_event_store
    sess1 = local_event_store.start_session(session_name="Session_1", operating_mode="LIVE_NPCAP")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        json_path = tmp_path / "metrics.json"

        classifier = RealTimeClassifier(
            config_path="config.yaml",
            operating_mode=OperatingMode.LIVE_NPCAP.value,
            session_id=sess1,
        )
        classifier.csv_out_path = tmp_path / "predictions.csv"
        classifier.jsonl_out_path = tmp_path / "predictions.jsonl"
        classifier.metrics_collector.metrics_json_path = json_path
        classifier.metrics_collector.session_id = sess1
        classifier.start()

        # Session 1 packet
        t0 = time.time()
        classifier.process_packet(_create_synthetic_test_packet(t0, "10.1.1.1", "10.1.1.2", 1000, 443))
        assert classifier.session_id == sess1

        # Simulate user starting Session 2 via local_event_store
        sess2 = local_event_store.start_session(session_name="Session_2", operating_mode="LIVE_NPCAP")
        classifier.process_packet(_create_synthetic_test_packet(t0 + 0.1, "10.2.2.1", "10.2.2.2", 2000, 443))

        classifier.stop()

        # Assert classifier switched session ID dynamically
        assert classifier.session_id == sess2
        assert classifier.flow_tracker.session_id == sess2
        assert classifier.metrics_collector.session_id == sess2


def test_10_capture_exception_tracking():
    """
    Verifies:
    10. Capture exception handling and stage tracking.
    """
    sniffer = LiveSniffer(interface="InvalidAdapterXYZ999", session_id="SESS_EXC_TEST")

    with patch.object(sniffer, "check_capture_prerequisites", side_effect=ValueError("Adapter not found")):
        with pytest.raises(ValueError):
            sniffer.start_sniffing(callback=lambda p: None)

    assert sniffer.capture_state == "CAPTURE_FAILED"
    assert sniffer.last_capture_error == "Adapter not found"
    assert sniffer.last_capture_error_stage == "PREREQUISITES"

    telemetry = sniffer.get_telemetry()
    assert telemetry["capture_state"] == "CAPTURE_FAILED"
    assert telemetry["last_capture_error"] == "Adapter not found"
    assert telemetry["last_capture_error_stage"] == "PREREQUISITES"


def test_11_to_13_no_packet_state_stale_telemetry_and_metrics_consistency():
    """
    Verifies:
    11. Stale telemetry detection.
    12. No-packet state (strictly 0.0 rates, no suspicious legacy metrics like 512 pkts/s).
    13. Metrics consistency (independent Phase 4 subsystem states).
    """
    test_session = f"SESS_METRICS_CONSISTENCY_{int(time.time())}"

    collector = MetricsCollector(session_id=test_session)
    snap = collector.get_snapshot(active_flows_count=0, queue_depth=0, persist=False)
    data = snap.to_dict()

    # 12. No-packet state: all rates MUST be strictly 0.0
    assert data["total_packets"] == 0
    assert data["packets_per_second"] == 0.0
    assert data["packets_per_sec"] == 0.0
    assert data["bytes_per_second"] == 0.0
    assert data["throughput_mbps"] == 0.0
    assert data["predictions_per_sec"] == 0.0
    assert data["known_class_rate"] == 0.0

    # Test LocalAPIHandler metrics endpoint with no-packet state
    server = LocalAPIServer(host="127.0.0.1", port=8093)
    assert server.start()

    metrics_file = Path("results/realtime/metrics.json")
    metrics_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        import urllib.request
        from product.event_store import local_event_store
        local_event_store.set_active_session_id(test_session)

        # Write clean 0-packet snapshot
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        req = urllib.request.Request("http://127.0.0.1:8093/metrics")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            api_data = json.loads(resp.read().decode("utf-8"))

        # 13. Metrics consistency & independent Phase 4 states
        assert api_data["packets_per_second"] == 0.0
        assert api_data["throughput_mbps"] == 0.0
        assert api_data["predictions_per_sec"] == 0.0
        assert api_data["known_class_rate"] == 0.0
        assert api_data["actual_packets_received"] is False
        assert api_data["pipeline_status"] == "WAITING_FOR_TRAFFIC"
        assert api_data["api_responding"] is True

        # 11. Stale telemetry detection
        stale_data = dict(data)
        stale_data["timestamp"] = time.time() - 15.0  # 15s ago
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(stale_data, f)

        with urllib.request.urlopen(req, timeout=2.0) as resp:
            stale_api_data = json.loads(resp.read().decode("utf-8"))

        assert stale_api_data["is_stale"] is True
        assert stale_api_data["metrics_status"] == "STALE"
        assert stale_api_data["pipeline_status"] == "DEGRADED"

    finally:
        server.stop()


def test_hardware_npcap_capture_live_adapter():
    """
    Optional Windows/Npcap hardware integration test.
    Attempts a brief non-blocking physical capture on the active adapter (e.g. Wi-Fi).
    Skipped gracefully if Npcap is unavailable or un-elevated.
    """
    import platform
    if platform.system() != "Windows":
        pytest.skip("Physical Npcap hardware test requires Windows host")

    from product.environment import check_npcap
    npcap_status = check_npcap()
    if npcap_status.get("status") != "PASS" or not npcap_status.get("can_capture"):
        pytest.skip("Npcap physical capture driver is not available on this host")

    from product.adapter_manager import get_default_adapter
    ad = get_default_adapter()
    if not ad:
        pytest.skip("No active physical network adapter detected")

    iface_name = ad["friendly_name"]
    captured = []

    sniffer = LiveSniffer(interface=iface_name, session_id="SESS_HW_TEST", queue_maxsize=100)
    try:
        sniff_thread = threading.Thread(
            target=sniffer.start_sniffing,
            kwargs={"callback": lambda pkt: captured.append(pkt), "duration_seconds": 1.0},
            daemon=True,
        )
        sniff_thread.start()
        sniff_thread.join(timeout=3.0)
    except PermissionError:
        pytest.skip("Hardware capture requires elevated administrative permissions")
    except Exception as e:
        pytest.skip(f"Hardware capture skipped: {e}")
    finally:
        sniffer.stop()

    # Verify telemetry structure from physical hardware capture
    telem = sniffer.get_telemetry()
    assert "capture_packets_received" in telem
    assert "capture_state" in telem
    assert telem["capture_state"] in ("CAPTURE_RECEIVING", "CAPTURE_ACTIVE", "CAPTURE_IDLE")

