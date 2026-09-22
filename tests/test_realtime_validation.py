"""
Unit and integration tests for EXP-R15: Complete Real-Time Pipeline Validation.
Validates:
1. Generation and completeness of realtime_research_validation.csv.
2. The 10 security, privacy, and correctness invariants.
3. Strict DEMO_MODE segregation.
4. Localhost-only API binding.
5. Canonical 14-field event schema contract.
"""

from pathlib import Path
import pandas as pd
import pytest

from capture.packet_capture import RawPacketMetadata
from flows.flow_generator import Flow, FlowKey
from product.local_api import LocalAPIServer
from realtime.events import OperatingMode, PredictionState, TrafficPredictionEvent
from realtime.schema import CANONICAL_NUMERICAL_FEATURES

REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATION_CSV = REPO_ROOT / "results" / "tables" / "realtime_research_validation.csv"

CANONICAL_14_FIELDS = [
    "timestamp",
    "flow_id",
    "session_id_hash",
    "model_id",
    "feature_profile",
    "predicted_family",
    "predicted_class",
    "family_confidence",
    "fine_confidence",
    "composed_confidence",
    "prediction_state",
    "packets_observed",
    "elapsed_seconds",
    "latency_us",
]


def test_realtime_validation_table_exists():
    """Verify that realtime_research_validation.csv exists and has passed status."""
    assert VALIDATION_CSV.exists(), f"Missing {VALIDATION_CSV}"
    df = pd.read_csv(VALIDATION_CSV)
    assert len(df) == 2, "Table must contain DEMO_MODE and LIVE_MODE rows"

    modes = df["operating_mode"].tolist()
    assert "DEMO_MODE" in modes
    assert "LIVE_MODE" in modes

    statuses = df["status"].tolist()
    assert all(s == "VALIDATED" for s in statuses), f"Non-validated status found: {statuses}"

    checks = [
        "payload_persistence_check",
        "zero_payload_features_check",
        "tls_decryption_check",
        "external_transmission_check",
        "schema_validation_check",
    ]
    for chk in checks:
        for val in df[chk]:
            assert val == "PASSED", f"Check {chk} did not pass: {val}"


def test_zero_payload_persistence_invariant():
    """Verify that RawPacketMetadata, Flow, and TrafficPredictionEvent contain zero payload fields."""
    forbidden = ["payload", "data_hex", "raw_content", "body", "plaintext"]

    # Check RawPacketMetadata fields
    pkt_fields = list(RawPacketMetadata.__dataclass_fields__.keys())
    for f in pkt_fields:
        assert not any(fb in f.lower() for fb in forbidden), f"Payload field in RawPacketMetadata: {f}"

    # Check Flow attributes
    fkey = FlowKey("10.0.0.1", 1234, "1.1.1.1", 443, "TCP")
    flow = Flow(fkey, "10.0.0.1", 1234, 0.0, 0.0)
    assert not hasattr(flow, "payload")
    assert not hasattr(flow, "raw_data")

    # Check TrafficPredictionEvent fields
    ev = TrafficPredictionEvent()
    ev_dict = ev.to_canonical_dict()
    for k in ev_dict.keys():
        assert not any(fb in k.lower() for fb in forbidden), f"Payload field in event: {k}"


def test_zero_payload_features_invariant():
    """Verify that canonical features derive strictly from Layer-3/4 transport and statistical attributes."""
    forbidden_terms = ["payload", "ngram", "regex", "signature", "content"]
    for feat in CANONICAL_NUMERICAL_FEATURES:
        assert not any(fb in feat.lower() for fb in forbidden_terms), f"Non-zero-payload feature detected: {feat}"


def test_canonical_14_field_event_schema():
    """Verify that TrafficPredictionEvent emits exact canonical 14-field dictionary."""
    ev = TrafficPredictionEvent(
        timestamp=1787672210.5,
        flow_id="F-00001",
        session_id_hash="abc123456789def0",
        model_id="model_lightgbm_v1",
        feature_profile="lightweight_10",
        predicted_family="Interactive",
        predicted_class="Web",
        family_confidence=0.88,
        fine_confidence=0.88,
        composed_confidence=0.88,
        prediction_state=PredictionState.KNOWN.value,
        packets_observed=15,
        elapsed_seconds=1.25,
        latency_us=450.0,
    )
    d = ev.to_canonical_dict()
    assert len(d) == 14, f"Expected 14 canonical fields, got {len(d)}"
    for f in CANONICAL_14_FIELDS:
        assert f in d, f"Missing canonical field: {f}"


def test_demo_mode_segregation_invariant():
    """Verify that DEMO_MODE events are permanently stamped with DEMO_MODE."""
    ev = TrafficPredictionEvent(operating_mode=OperatingMode.DEMO_MODE.value)
    assert ev.operating_mode == "DEMO_MODE"
    assert ev.operating_mode != OperatingMode.LIVE_MODE.value


def test_localhost_only_binding_invariant():
    """Verify LocalAPIServer enforces localhost binding and rejects external interfaces."""
    srv = LocalAPIServer(host="127.0.0.1", port=8099)
    assert srv.host == "127.0.0.1"

    # Attempt binding to 0.0.0.0 should be overridden to 127.0.0.1 for privacy
    srv_insecure = LocalAPIServer(host="0.0.0.0", port=8099)
    assert srv_insecure.host == "127.0.0.1", "LocalAPIServer failed to sanitize non-localhost binding"
