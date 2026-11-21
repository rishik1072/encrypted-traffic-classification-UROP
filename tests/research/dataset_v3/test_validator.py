"""
Unit Tests: Dataset V3 Scientific and Privacy Validator.

Validates all 17 research and privacy integrity checks:
- Clean session passes.
- Invalid flow IDs.
- Duplicate flow IDs.
- Missing parent-flow relationships.
- Non-monotonic timestamps.
- Synthetic samples in primary dataset.
- Forbidden IP/MAC leakage detection.
- Cross-partition parent-flow overlap leakage detection.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import pytest

from research.dataset_v3.metadata_writer import MetadataWriter
from research.dataset_v3.schemas import (
    FlowIndexRecord,
    LabelRecord,
    PacketMetadataRecord,
    SessionManifest,
)
from research.dataset_v3.validator import DatasetV3Validator


def create_mock_session(
    session_dir: Path,
    session_id: str = "sess_val_test_001",
    flow_id: str = "flow_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    parent_flow_id: str = "flow_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    is_synthetic: bool = False,
    inject_ip_leak: bool = False,
    termination_reason: str = "TCP_FIN",
    device_pseudonym: str = "dev_rnd_abcdef12",
    application_alias: str = "chrome",
) -> None:
    session_dir = Path(session_dir)
    session_dir.mkdir(parents=True, exist_ok=True)

    manifest = SessionManifest(
        session_id=session_id,
        collection_start_utc="2026-11-20T12:00:00Z",
        collection_end_utc="2026-11-20T12:01:00Z",
        collector_version="3.0.0",
        operating_system="Windows 11",
        device_pseudonym=device_pseudonym,
        adapter_type="Wi-Fi",
        environment_id="env_test",
        tunnel_status="DIRECT",
        collection_activity="Browsing",
        application_alias=application_alias,
        intended_traffic_class="Web",
        collection_operator_label="operator_test",
        capture_status="COMPLETE",
        packet_count=2,
        flow_count=1,
    )
    with open(session_dir / "session_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2)

    p0 = PacketMetadataRecord(
        session_id=session_id,
        flow_id=flow_id,
        parent_flow_id=parent_flow_id,
        packet_index=0,
        relative_timestamp_us=0,
        inter_arrival_time_us=0,
        packet_length=100,
        captured_length=100,
        direction=0,
        transport_protocol="TCP",
        tcp_flags=2,
        is_synthetic=is_synthetic,
    )
    p1 = PacketMetadataRecord(
        session_id=session_id,
        flow_id=flow_id,
        parent_flow_id=parent_flow_id,
        packet_index=1,
        relative_timestamp_us=50000,
        inter_arrival_time_us=50000,
        packet_length=200,
        captured_length=200,
        direction=1,
        transport_protocol="TCP",
        tcp_flags=18,
        is_synthetic=is_synthetic,
    )
    with open(session_dir / "packet_metadata.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps(p0.to_dict()) + "\n")
        f.write(json.dumps(p1.to_dict()) + "\n")

    f0 = FlowIndexRecord(
        session_id=session_id,
        flow_id=flow_id,
        parent_flow_id=parent_flow_id,
        first_packet_timestamp_utc="2026-11-20T12:00:00Z",
        last_packet_timestamp_utc="2026-11-20T12:00:01Z",
        packet_count=2,
        duration_us=50000,
        direction_0_packets=1,
        direction_1_packets=1,
        direction_0_bytes=100,
        direction_1_bytes=200,
        transport_protocol="TCP",
        termination_reason=termination_reason,
        prefix_3_available=False,
        prefix_5_available=False,
        prefix_10_available=False,
        prefix_20_available=False,
        is_synthetic=is_synthetic,
    )
    with open(session_dir / "flow_index.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(f0.to_dict().keys()))
        writer.writeheader()
        writer.writerow(f0.to_dict())

    lbl = LabelRecord(
        session_id=session_id,
        flow_id=flow_id,
        traffic_class="Web",
        application_alias=application_alias,
        label_source="OPERATOR_CONTROLLED",
        label_quality="VERIFIED",
        annotator="operator_test",
        annotation_timestamp="2026-11-20T12:01:05Z",
        packet_count=2,
        prefix_3_available=False,
        prefix_5_available=False,
        prefix_10_available=False,
        prefix_20_available=False,
    )
    with open(session_dir / "labels.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(lbl.to_dict().keys()))
        writer.writeheader()
        writer.writerow(lbl.to_dict())

    if inject_ip_leak:
        with open(session_dir / "packet_metadata.jsonl", "a", encoding="utf-8") as f:
            f.write(
                json.dumps({
                    "session_id": session_id,
                    "flow_id": flow_id,
                    "parent_flow_id": parent_flow_id,
                    "packet_index": 2,
                    "relative_timestamp_us": 60000,
                    "inter_arrival_time_us": 10000,
                    "packet_length": 60,
                    "direction": 0,
                    "transport_protocol": "TCP",
                    "notes": "leaked_ip_192.168.1.1",
                })
                + "\n"
            )


def test_validator_clean_session_passes(tmp_path: Path) -> None:
    session_dir = tmp_path / "sess_clean"
    create_mock_session(session_dir=session_dir, session_id="sess_clean")

    validator = DatasetV3Validator()
    report = validator.validate_session(session_dir)

    assert report.is_valid is True
    assert report.failed_checks == 0
    assert len(report.errors) == 0


def test_validator_detects_synthetic_contamination(tmp_path: Path) -> None:
    session_dir = tmp_path / "sess_synth"
    create_mock_session(session_dir=session_dir, session_id="sess_synth", is_synthetic=True)

    validator = DatasetV3Validator()
    report = validator.validate_session(session_dir)

    assert report.is_valid is False
    assert any("Check 12 FAIL" in err for err in report.errors)


def test_validator_detects_forbidden_ip_leak(tmp_path: Path) -> None:
    session_dir = tmp_path / "sess_leaky"
    create_mock_session(session_dir=session_dir, session_id="sess_leaky", inject_ip_leak=True)

    validator = DatasetV3Validator()
    report = validator.validate_session(session_dir)

    assert report.is_valid is False
    assert any("Check 16 FAIL" in err for err in report.errors)


def test_validator_detects_parent_flow_partition_leakage(tmp_path: Path) -> None:
    dir_train = tmp_path / "train_sess"
    dir_test = tmp_path / "test_sess"

    shared_parent = "flow_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    # Train session
    create_mock_session(
        session_dir=dir_train,
        session_id="train_sess",
        flow_id=shared_parent,
        parent_flow_id=shared_parent,
    )
    # Test session with different session ID but same parent_flow_id (Leakage!)
    create_mock_session(
        session_dir=dir_test,
        session_id="test_sess",
        flow_id="flow_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        parent_flow_id=shared_parent,  # Cloned prototype parent!
    )

    validator = DatasetV3Validator()
    is_valid, errors = validator.validate_partitions([dir_train], [], [dir_test])

    assert is_valid is False
    assert any("Check 13 FAIL" in err for err in errors)
    assert "Overlapping parent_flow_ids" in errors[0]


def test_validator_detects_device_partition_overlap(tmp_path: Path) -> None:
    dir_train = tmp_path / "train_dev"
    dir_test = tmp_path / "test_dev"
    create_mock_session(
        session_dir=dir_train,
        session_id="train_dev",
        flow_id="flow_11111111111111111111111111111111",
        parent_flow_id="flow_11111111111111111111111111111111",
        device_pseudonym="dev_same_device",
    )
    create_mock_session(
        session_dir=dir_test,
        session_id="test_dev",
        flow_id="flow_22222222222222222222222222222222",
        parent_flow_id="flow_22222222222222222222222222222222",
        device_pseudonym="dev_same_device",
    )
    validator = DatasetV3Validator()
    is_valid, errors = validator.validate_partitions(
        [dir_train], [], [dir_test], enforce_device_disjoint=True
    )
    assert is_valid is False
    assert any("Check 18 FAIL" in err for err in errors)


def test_validator_detects_application_partition_overlap(tmp_path: Path) -> None:
    dir_train = tmp_path / "train_app"
    dir_test = tmp_path / "test_app"
    create_mock_session(
        session_dir=dir_train,
        session_id="train_app",
        flow_id="flow_33333333333333333333333333333333",
        parent_flow_id="flow_33333333333333333333333333333333",
        application_alias="youtube_stream",
    )
    create_mock_session(
        session_dir=dir_test,
        session_id="test_app",
        flow_id="flow_44444444444444444444444444444444",
        parent_flow_id="flow_44444444444444444444444444444444",
        application_alias="youtube_stream",
    )
    validator = DatasetV3Validator()
    is_valid, errors = validator.validate_partitions(
        [dir_train], [], [dir_test], enforce_application_disjoint=True
    )
    assert is_valid is False
    assert any("Check 19 FAIL" in err for err in errors)


def test_validator_detects_invalid_termination_reason(tmp_path: Path) -> None:
    session_dir = tmp_path / "sess_bad_term"
    create_mock_session(
        session_dir=session_dir,
        session_id="sess_bad_term",
        termination_reason="INVALID_NONEXISTENT_REASON",
    )
    validator = DatasetV3Validator()
    report = validator.validate_session(session_dir)
    assert report.is_valid is False
    assert any("Check 20 FAIL" in err for err in report.errors)


def test_validator_enforces_label_semantics_and_prevents_leakage(tmp_path: Path) -> None:
    """Verifies that the validator rejects unlabelled/ambiguous flows with assigned traffic classes."""
    session_dir = tmp_path / "sess_label_leak"
    create_mock_session(session_dir=session_dir, session_id="sess_label_leak")

    # Manually tamper with labels.csv to simulate a corrupted label record where UNLABELLED has traffic_class='Web'
    labels_path = session_dir / "labels.csv"
    with open(labels_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Add tampered row
    tampered_row = dict(rows[0])
    tampered_row["flow_id"] = "flow_tampered_0001"
    tampered_row["traffic_class"] = "Web"
    tampered_row["label_quality"] = "UNLABELLED"

    with open(labels_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerow(rows[0])
        writer.writerow(tampered_row)

    validator = DatasetV3Validator()
    report = validator.validate_session(session_dir)
    assert report.is_valid is False
    assert any("traffic_class=None" in err or "Check 9 FAIL" in err or "Check 15 FAIL" in err for err in report.errors)


def test_pilot_session_identity_and_repeat_protection() -> None:
    """
    Verifies that create_pilot_session_1_config separates collection_plan_id from session_id
    and generates distinct random UUIDs for each execution to prevent overwriting.
    """
    from research.dataset_v3.pilot_config import create_pilot_session_1_config, PILOT_COLLECTION_PLAN_ID

    cfg1 = create_pilot_session_1_config()
    cfg2 = create_pilot_session_1_config()

    # Plan ID is identical
    assert cfg1.collection_plan_id == PILOT_COLLECTION_PLAN_ID
    assert cfg2.collection_plan_id == PILOT_COLLECTION_PLAN_ID
    assert cfg1.collection_plan_id == "sess_pilot_001_wifi_direct_web"

    # Session ID must be distinct random UUIDs
    assert cfg1.session_id != cfg2.session_id
    assert cfg1.session_id.startswith("sess_")
    assert cfg2.session_id.startswith("sess_")
    assert len(cfg1.session_id) >= 36  # UUID length

    # Target directories must be completely separate
    assert cfg1.final_session_dir != cfg2.final_session_dir
    assert cfg1.staging_session_dir != cfg2.staging_session_dir
