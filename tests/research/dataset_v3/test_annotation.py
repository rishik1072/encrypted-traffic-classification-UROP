"""
Unit Tests: Dataset V3 Ground-Truth Annotation Engine and Label Semantics.

Validates the Phase 2A.3 label semantics and primary flow attribution lifecycle:
1. VERIFIED: traffic_class contains one of the six validated classes.
2. UNLABELLED: traffic_class = None, label_quality = UNLABELLED.
3. AMBIGUOUS: traffic_class = None, label_quality = AMBIGUOUS.
4. 'Other' is reserved exclusively for verified residual traffic.
5. Temporal overlap without explicit attribution evidence receives AMBIGUOUS (not VERIFIED).
6. Decoupling of packet count prefix eligibility from ground-truth quality.
7. Manual operator overrides adhere to invariants.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from research.dataset_v3.annotation import GroundTruthAnnotator
from research.dataset_v3.config import DatasetV3Config
from research.dataset_v3.schemas import FlowIndexRecord, LabelRecord, VALID_TRAFFIC_CLASSES


def test_ground_truth_annotation_rules() -> None:
    config = DatasetV3Config(
        session_id="sess_test_annot_001",
        intended_traffic_class="Video",
        application_alias="youtube_stream",
        collection_operator_label="annotator_rishi",
    )
    annotator = GroundTruthAnnotator(config=config)

    # Flow 1: Substantial video stream (100 packets)
    f1 = FlowIndexRecord(
        session_id="sess_test_annot_001",
        flow_id="flow_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        parent_flow_id="flow_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        first_packet_timestamp_utc="2026-11-20T12:00:00Z",
        last_packet_timestamp_utc="2026-11-20T12:00:30Z",
        packet_count=100,
        duration_us=30000000,
        direction_0_packets=30,
        direction_1_packets=70,
        direction_0_bytes=3000,
        direction_1_bytes=90000,
        transport_protocol="TCP",
        is_synthetic=False,
    )

    # Flow 2: Ambiguous short flow (2 packets)
    f2 = FlowIndexRecord(
        session_id="sess_test_annot_001",
        flow_id="flow_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        parent_flow_id="flow_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        first_packet_timestamp_utc="2026-11-20T12:00:05Z",
        last_packet_timestamp_utc="2026-11-20T12:00:05Z",
        packet_count=2,
        duration_us=50000,
        direction_0_packets=2,
        direction_1_packets=0,
        direction_0_bytes=120,
        direction_1_bytes=0,
        transport_protocol="UDP",
        is_synthetic=False,
    )

    # Flow 3: Background OS telemetry (10 packets, not target)
    f3 = FlowIndexRecord(
        session_id="sess_test_annot_001",
        flow_id="flow_cccccccccccccccccccccccccccccccc",
        parent_flow_id="flow_cccccccccccccccccccccccccccccccc",
        first_packet_timestamp_utc="2026-11-20T12:00:10Z",
        last_packet_timestamp_utc="2026-11-20T12:00:12Z",
        packet_count=10,
        duration_us=2000000,
        direction_0_packets=5,
        direction_1_packets=5,
        direction_0_bytes=500,
        direction_1_bytes=500,
        transport_protocol="TCP",
        is_synthetic=False,
    )

    # Case A: Unspecified attribution (no explicit evidence supplied)
    # Temporal overlap only: flows MUST NOT automatically receive VERIFIED status!
    labels_auto = annotator.generate_initial_labels([f1, f2, f3])
    lbl_map = {lbl.flow_id: lbl for lbl in labels_auto}

    assert lbl_map[f1.flow_id].traffic_class is None
    assert lbl_map[f1.flow_id].label_quality == "AMBIGUOUS"
    assert lbl_map[f1.flow_id].label_source == "TEMPORAL_HEURISTIC"
    assert lbl_map[f1.flow_id].prefix_3_available is True

    assert lbl_map[f2.flow_id].traffic_class is None
    assert lbl_map[f2.flow_id].label_quality == "AMBIGUOUS"
    assert lbl_map[f2.flow_id].prefix_3_available is False

    # Case B: Explicit operator verification (f1 has explicit evidence; f2 and f3 are background)
    labels_scoped = annotator.generate_initial_labels(
        [f1, f2, f3],
        verified_flow_ids={f1.flow_id},
    )
    scoped_map = {lbl.flow_id: lbl for lbl in labels_scoped}

    # Target flow with explicit evidence -> VERIFIED with intended class
    assert scoped_map[f1.flow_id].traffic_class == "Video"
    assert scoped_map[f1.flow_id].label_quality == "VERIFIED"
    assert scoped_map[f1.flow_id].label_source == "OPERATOR_CONTROLLED"

    # Background flows -> UNLABELLED with traffic_class = None
    assert scoped_map[f2.flow_id].traffic_class is None
    assert scoped_map[f2.flow_id].label_quality == "UNLABELLED"
    assert scoped_map[f2.flow_id].label_source == "BACKGROUND_UNLABELLED"

    assert scoped_map[f3.flow_id].traffic_class is None
    assert scoped_map[f3.flow_id].label_quality == "UNLABELLED"
    assert scoped_map[f3.flow_id].label_source == "BACKGROUND_UNLABELLED"

    # Case C: Explicit multi-state attribution (verified, ambiguous, and residual other)
    labels_multi = annotator.generate_initial_labels(
        [f1, f2, f3],
        verified_flow_ids={f1.flow_id},
        ambiguous_flow_ids={f2.flow_id},
        residual_other_flow_ids={f3.flow_id},
    )
    multi_map = {lbl.flow_id: lbl for lbl in labels_multi}

    # f1 is verified Video
    assert multi_map[f1.flow_id].traffic_class == "Video"
    assert multi_map[f1.flow_id].label_quality == "VERIFIED"

    # f2 is ambiguous with traffic_class = None
    assert multi_map[f2.flow_id].traffic_class is None
    assert multi_map[f2.flow_id].label_quality == "AMBIGUOUS"
    assert multi_map[f2.flow_id].label_source == "TEMPORAL_HEURISTIC"

    # f3 is independently verified residual 'Other'
    assert multi_map[f3.flow_id].traffic_class == "Other"
    assert multi_map[f3.flow_id].label_quality == "VERIFIED"
    assert multi_map[f3.flow_id].label_source == "INDEPENDENT_VERIFICATION"


def test_label_record_semantic_invariants() -> None:
    """Verifies that LabelRecord strictly enforces semantic invariants upon instantiation."""

    # 1. VERIFIED must have non-None valid traffic class
    with pytest.raises(ValueError, match="VERIFIED label must specify a valid traffic_class"):
        LabelRecord(
            session_id="s1",
            flow_id="f1",
            traffic_class=None,
            application_alias="app",
            label_source="OPERATOR_CONTROLLED",
            label_quality="VERIFIED",
            annotator="op",
            annotation_timestamp="2026-11-20T12:00:00Z",
        )

    # 2. VERIFIED must have class from VALID_TRAFFIC_CLASSES
    with pytest.raises(ValueError, match="invalid traffic class"):
        LabelRecord(
            session_id="s1",
            flow_id="f1",
            traffic_class="IllegalClass",
            application_alias="app",
            label_source="OPERATOR_CONTROLLED",
            label_quality="VERIFIED",
            annotator="op",
            annotation_timestamp="2026-11-20T12:00:00Z",
        )

    # 3. UNLABELLED must have traffic_class = None
    with pytest.raises(ValueError, match="UNLABELLED flow must have traffic_class=None"):
        LabelRecord(
            session_id="s1",
            flow_id="f1",
            traffic_class="Web",  # Contamination!
            application_alias="app",
            label_source="BACKGROUND_UNLABELLED",
            label_quality="UNLABELLED",
            annotator="op",
            annotation_timestamp="2026-11-20T12:00:00Z",
        )

    # 4. AMBIGUOUS must have traffic_class = None
    with pytest.raises(ValueError, match="AMBIGUOUS flow must have traffic_class=None"):
        LabelRecord(
            session_id="s1",
            flow_id="f1",
            traffic_class="Web",  # Contamination!
            application_alias="app",
            label_source="TEMPORAL_HEURISTIC",
            label_quality="AMBIGUOUS",
            annotator="op",
            annotation_timestamp="2026-11-20T12:00:00Z",
        )

    # 5. 'Other' is reserved exclusively for VERIFIED
    with pytest.raises(ValueError, match="'Other' traffic class is reserved exclusively for VERIFIED"):
        LabelRecord(
            session_id="s1",
            flow_id="f1",
            traffic_class="Other",
            application_alias="app",
            label_source="BACKGROUND_UNLABELLED",
            label_quality="UNLABELLED",
            annotator="op",
            annotation_timestamp="2026-11-20T12:00:00Z",
        )

    # 6. Valid records roundtrip cleanly through serialization
    valid_unlabelled = LabelRecord(
        session_id="s1",
        flow_id="f1",
        traffic_class=None,
        application_alias="background_unattributed",
        label_source="BACKGROUND_UNLABELLED",
        label_quality="UNLABELLED",
        annotator="op",
        annotation_timestamp="2026-11-20T12:00:00Z",
    )
    d = valid_unlabelled.to_dict()
    assert d["traffic_class"] is None
    assert d["label_quality"] == "UNLABELLED"

    restored = LabelRecord.from_dict(d)
    assert restored.traffic_class is None
    assert restored.label_quality == "UNLABELLED"


def test_temporal_overlap_without_evidence_refuses_verified() -> None:
    """
    Verifies that temporal overlap with the browsing window alone CANNOT grant VERIFIED status.
    Attribution uncertainty is preserved.
    """
    config = DatasetV3Config(
        session_id="sess_temporal_01",
        intended_traffic_class="Web",
        application_alias="chrome_browsing",
    )
    annotator = GroundTruthAnnotator(config=config)

    # 5 flows that occurred during a 60-second Chrome browsing session
    flows = [
        FlowIndexRecord(
            session_id="sess_temporal_01",
            flow_id=f"flow_{i:04d}",
            parent_flow_id=f"flow_{i:04d}",
            first_packet_timestamp_utc="2026-11-20T12:00:00Z",
            last_packet_timestamp_utc="2026-11-20T12:00:10Z",
            packet_count=10,
            duration_us=10000000,
            direction_0_packets=5,
            direction_1_packets=5,
            direction_0_bytes=500,
            direction_1_bytes=500,
            transport_protocol="TCP",
        )
        for i in range(5)
    ]

    # Operator did not have socket/PID corroboration or explicit proof for any flow
    # Case 1: passing primary_flow_ids with has_explicit_evidence=False
    labels_heuristic = annotator.generate_initial_labels(
        flows,
        primary_flow_ids={f.flow_id for f in flows},
        has_explicit_evidence=False,
    )
    for lbl in labels_heuristic:
        assert lbl.label_quality == "AMBIGUOUS"
        assert lbl.traffic_class is None
        assert lbl.label_source == "TEMPORAL_HEURISTIC"

    # Case 2: Only 1 flow has socket corroboration (flow_0002)
    labels_partial = annotator.generate_initial_labels(
        flows,
        verified_flow_ids={"flow_0002"},
        ambiguous_flow_ids={"flow_0001", "flow_0003"},
    )
    part_map = {lbl.flow_id: lbl for lbl in labels_partial}

    # Only flow_0002 can enter supervised evaluation
    assert part_map["flow_0002"].traffic_class == "Web"
    assert part_map["flow_0002"].label_quality == "VERIFIED"

    # flow_0001 and flow_0003 remain ambiguous (excluded from training)
    assert part_map["flow_0001"].traffic_class is None
    assert part_map["flow_0001"].label_quality == "AMBIGUOUS"
    assert part_map["flow_0003"].traffic_class is None
    assert part_map["flow_0003"].label_quality == "AMBIGUOUS"

    # flow_0000 and flow_0004 are unattributed background
    assert part_map["flow_0000"].traffic_class is None
    assert part_map["flow_0000"].label_quality == "UNLABELLED"
    assert part_map["flow_0004"].traffic_class is None
    assert part_map["flow_0004"].label_quality == "UNLABELLED"
