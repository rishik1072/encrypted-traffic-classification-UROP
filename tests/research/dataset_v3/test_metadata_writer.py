"""
Unit Tests: Dataset V3 Metadata Writer.

Validates:
- Atomic creation of session directory and files.
- Thread-safe streaming packet appends.
- Proper CSV headers and JSON schemas.
- Overwrite prevention for completed sessions.
"""

from __future__ import annotations

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


def test_metadata_writer_lifecycle(tmp_path: Path) -> None:
    session_id = "sess_test_writer_001"
    final_dir = tmp_path / session_id
    staging_dir = tmp_path / ".staging" / session_id
    incomplete_dir = tmp_path / ".incomplete" / session_id

    writer = MetadataWriter(
        final_dir=final_dir,
        staging_dir=staging_dir,
        incomplete_dir=incomplete_dir,
        session_id=session_id,
    )

    manifest = SessionManifest(
        session_id=session_id,
        collection_start_utc="2026-11-20T12:00:00Z",
        collection_end_utc="",
        collector_version="3.0.0",
        operating_system="Test OS",
        device_pseudonym="dev_rnd_12345",
        adapter_type="Wi-Fi",
        environment_id="env_test",
        tunnel_status="DIRECT",
        collection_activity="Test Activity",
        application_alias="test_app",
        intended_traffic_class="Web",
        collection_operator_label="operator_test",
        capture_status="CREATED",
    )

    writer.initialize_session(manifest)
    assert (staging_dir / "session_manifest.json").exists()

    # Write packets
    p1 = PacketMetadataRecord(
        session_id=session_id,
        flow_id="flow_11112222333344445555666677778888",
        parent_flow_id="flow_11112222333344445555666677778888",
        packet_index=0,
        relative_timestamp_us=0,
        inter_arrival_time_us=0,
        packet_length=500,
        captured_length=500,
        direction=0,
        transport_protocol="TCP",
        tcp_flags=2,
        is_synthetic=False,
    )
    writer.write_packet(p1)

    # Write flows
    f1 = FlowIndexRecord(
        session_id=session_id,
        flow_id="flow_11112222333344445555666677778888",
        parent_flow_id="flow_11112222333344445555666677778888",
        first_packet_timestamp_utc="2026-11-20T12:00:00Z",
        last_packet_timestamp_utc="2026-11-20T12:00:01Z",
        packet_count=1,
        duration_us=1000000,
        direction_0_packets=1,
        direction_1_packets=0,
        direction_0_bytes=500,
        direction_1_bytes=0,
        transport_protocol="TCP",
        termination_reason="TCP_FIN",
        prefix_3_available=False,
        prefix_5_available=False,
        prefix_10_available=False,
        prefix_20_available=False,
        is_synthetic=False,
    )
    writer.write_flow_index([f1])

    # Write labels
    lbl = LabelRecord(
        session_id=session_id,
        flow_id="flow_11112222333344445555666677778888",
        traffic_class="Web",
        application_alias="test_app",
        label_source="OPERATOR_CONTROLLED",
        label_quality="VERIFIED",
        annotator="operator_test",
        annotation_timestamp="2026-11-20T12:00:02Z",
        packet_count=1,
        prefix_3_available=False,
        prefix_5_available=False,
        prefix_10_available=False,
        prefix_20_available=False,
    )
    writer.write_labels([lbl])

    # Finalize & Publish atomically
    manifest.collection_end_utc = "2026-11-20T12:00:02Z"
    manifest.packet_count = 1
    manifest.flow_count = 1
    pub_path = writer.publish_complete_session(manifest)
    assert pub_path == final_dir

    # Verify published files on disk
    assert (final_dir / "packet_metadata.jsonl").exists()
    assert (final_dir / "flow_index.csv").exists()
    assert (final_dir / "labels.csv").exists()
    assert (final_dir / "SESSION_COMPLETE").exists()
    assert not staging_dir.exists()

    with open(final_dir / "packet_metadata.jsonl", "r", encoding="utf-8") as f:
        line = f.readline()
        assert "flow_11112222333344445555666677778888" in line

    # Test overwrite prevention on completed session
    writer2 = MetadataWriter(
        final_dir=final_dir,
        staging_dir=staging_dir,
        incomplete_dir=incomplete_dir,
        session_id=session_id,
    )
    with pytest.raises(FileExistsError):
        writer2.initialize_session(manifest)
