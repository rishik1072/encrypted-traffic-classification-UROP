"""
Dataset V3 Boundary-Aware Maximum Gap and Sampling-Density Policy Regression Suite.

Validates all 15 required scenarios:
1. Long leading boundary gap.
2. Long trailing boundary gap.
3. Large internal observation gap.
4. Uniform observations spanning the complete flow.
5. Two observations with acceptable internal gap but excessive trailing gap.
6. Two observations with acceptable internal gap but excessive leading gap.
7. No matching observations.
8. Single matching observation.
9. Zero-duration flow.
10. Negative-duration flow.
11. Duplicate timestamps.
12. Out-of-flow observations excluded from all coverage calculations.
13. Exact 0.50-second maximum-gap boundary.
14. Maximum gap slightly greater than 0.50 seconds.
15. Specific adversarial fixture: 10-second flow, 34 covered bins (50.7% coverage), 5.0s trailing gap.

Plus:
- Correct TCP state-dependent quality matrix (ESTABLISHED, SYN_SENT, SYN_RCVD, FIN_WAIT_1, CLOSE_WAIT, TIME_WAIT).
- Listener sockets strictly excluded (LISTEN, CLOSED).
- UDP local endpoint matching strictly ineligible for VERIFIED promotion.
- Canonical traffic-class consistency ("Web" vs "web_traffic").

Uses synthetic fixtures only. No live sockets or physical packet capture.
"""

from __future__ import annotations

import math
from typing import List

import pytest

from research.dataset_v3.attribution.correlator import (
    ProcessSocketCorrelator,
    calculate_sampling_coverage_estimate,
)
from research.dataset_v3.attribution.policy import AttributionEvidencePolicy
from research.dataset_v3.attribution.process_tracker import ProcessTracker
from research.dataset_v3.attribution.schemas import (
    AttributionEvidenceMethod,
    AttributionEvidenceRecord,
    AttributionQuality,
    AttributionRejectionCode,
    TransientSocketEntry,
    canonicalize_traffic_class,
)
from research.dataset_v3.attribution.snapshot_manager import SocketSnapshotManager
from research.dataset_v3.schemas import VALID_TRAFFIC_CLASSES


def _create_controlled_tracker(pid: int = 1004, alias: str = "chrome_controlled") -> ProcessTracker:
    tracker = ProcessTracker(controlled_app_alias=alias)
    tracker.register_controlled_root(pid=1000, create_time_utc="2026-11-21T10:00:00Z")
    tracker.register_controlled_child(pid=pid, parent_pid=1000, create_time_utc="2026-11-21T10:00:01Z")
    return tracker


def _make_tcp_entry(
    ts: float,
    pid: int = 1004,
    state: str = "ESTABLISHED",
    sport: int = 54321,
    dport: int = 443,
) -> TransientSocketEntry:
    return TransientSocketEntry(
        protocol="TCP",
        local_address="192.168.1.50",
        local_port=sport,
        remote_address="93.184.216.34",
        remote_port=dport,
        state=state,
        pid=pid,
        process_create_time_utc="2026-11-21T10:00:01Z",
        process_name="chrome.exe",
        timestamp_utc=ts,
        monotonic_ts=ts,
    )


# ==============================================================================
# 1. Long Leading Boundary Gap
# ==============================================================================

def test_long_leading_boundary_gap():
    """Requirement 1: Leading gap from flow_start to first observation exceeding 0.50s is rejected."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    # Flow lasts 2.0s: [100.00, 102.00] (14 expected bins at 0.15s width)
    # Observations begin only at 101.00 (leading gap = 1.00s > 0.50s)
    # 8 observations from 101.00 to 101.98 every 0.14s (coverage = 8/14 = 57% >= 50%)
    for i in range(8):
        t = round(101.00 + i * 0.14, 6)
        snap_mgr.add_snapshot(t, [_make_tcp_entry(t)], monotonic_ts=t)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker, max_observation_gap_seconds=0.50)
    evidence = correlator.correlate_flow(
        flow_id="flow_leading_gap",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=102.00,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=102.00,
    )

    assert evidence.max_observation_gap_seconds == pytest.approx(1.00, 0.01)
    assert evidence.attribution_coverage_ratio >= 0.50
    assert evidence.evidence_quality == AttributionQuality.MEDIUM.value
    assert evidence.rejection_code == AttributionRejectionCode.MAX_OBSERVATION_GAP_EXCEEDED.value

    policy = AttributionEvidencePolicy()
    tc, qual, _, _ = policy.evaluate_label_recommendation(evidence, "Web")
    assert tc is None
    assert qual == "AMBIGUOUS"


# ==============================================================================
# 2. Long Trailing Boundary Gap
# ==============================================================================

def test_long_trailing_boundary_gap():
    """Requirement 2: Trailing gap from last observation to flow_end exceeding 0.50s is rejected."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    # Flow lasts 2.0s: [100.00, 102.00]
    # Observations from 100.05 to 101.03 every 0.14s (8 observations)
    # Trailing gap = 102.00 - 101.03 = 0.97s > 0.50s
    for i in range(8):
        t = round(100.05 + i * 0.14, 6)
        snap_mgr.add_snapshot(t, [_make_tcp_entry(t)], monotonic_ts=t)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker, max_observation_gap_seconds=0.50)
    evidence = correlator.correlate_flow(
        flow_id="flow_trailing_gap",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=102.00,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=102.00,
    )

    assert evidence.max_observation_gap_seconds == pytest.approx(0.97, 0.01)
    assert evidence.attribution_coverage_ratio >= 0.50
    assert evidence.evidence_quality == AttributionQuality.MEDIUM.value
    assert evidence.rejection_code == AttributionRejectionCode.MAX_OBSERVATION_GAP_EXCEEDED.value


# ==============================================================================
# 3. Large Internal Observation Gap
# ==============================================================================

def test_large_internal_observation_gap():
    """Requirement 3: Internal gap between consecutive observations exceeding 0.50s is rejected."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    # Flow lasts 1.20s: [100.00, 101.20] (8 expected bins)
    # Obs in Bin 0, 1 (100.05, 100.20) and Bin 6, 7 (100.95, 101.10)
    # Internal gap = 100.95 - 100.20 = 0.75s > 0.50s
    for t in (100.05, 100.20, 100.95, 101.10):
        snap_mgr.add_snapshot(t, [_make_tcp_entry(t)], monotonic_ts=t)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker, max_observation_gap_seconds=0.50)
    evidence = correlator.correlate_flow(
        flow_id="flow_internal_gap",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=101.20,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=101.20,
    )

    assert evidence.max_observation_gap_seconds == pytest.approx(0.75, 0.01)
    assert evidence.attribution_coverage_ratio == 0.50
    assert evidence.evidence_quality == AttributionQuality.MEDIUM.value
    assert evidence.rejection_code == AttributionRejectionCode.MAX_OBSERVATION_GAP_EXCEEDED.value


# ==============================================================================
# 4. Uniform Observations Spanning the Complete Flow
# ==============================================================================

def test_uniform_observations_spanning_complete_flow():
    """Requirement 4: Uniform observations spanning complete flow achieve HIGH quality and VERIFIED."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    # Flow lasts 0.60s: [100.00, 100.60] (4 expected bins)
    # Observations at 100.05, 100.20, 100.35, 100.50
    # G_start = 0.05s, G_internal = 0.15s, G_end = 0.10s -> G_max = 0.15s <= 0.50s
    for t in (100.05, 100.20, 100.35, 100.50):
        snap_mgr.add_snapshot(t, [_make_tcp_entry(t)], monotonic_ts=t)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker, max_observation_gap_seconds=0.50)
    evidence = correlator.correlate_flow(
        flow_id="flow_uniform_span",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=100.60,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=100.60,
    )

    assert evidence.expected_bins_count == 4
    assert evidence.observed_bins_count == 4
    assert evidence.attribution_coverage_ratio == 1.00
    assert evidence.max_observation_gap_seconds == pytest.approx(0.15, 0.01)
    assert evidence.evidence_quality == AttributionQuality.HIGH.value
    assert evidence.rejection_code is None
    assert evidence.rejection_reason is None

    policy = AttributionEvidencePolicy()
    tc, qual, src, rej = policy.evaluate_label_recommendation(evidence, "Web")
    assert tc == "Web"
    assert qual == "VERIFIED"
    assert src == "INDEPENDENT_VERIFICATION"


# ==============================================================================
# 5. Two observations: acceptable internal gap, excessive trailing gap
# ==============================================================================

def test_two_observations_acceptable_internal_excessive_trailing_gap():
    """Requirement 5: Acceptable internal gap (0.15s) but trailing gap (1.30s > 0.50s) is rejected."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    # Flow lasts 1.50s: [100.00, 101.50]
    # Obs at 100.05 and 100.20 (internal gap = 0.15s)
    # Trailing gap = 101.50 - 100.20 = 1.30s > 0.50s
    snap_mgr.add_snapshot(100.05, [_make_tcp_entry(100.05)], monotonic_ts=100.05)
    snap_mgr.add_snapshot(100.20, [_make_tcp_entry(100.20)], monotonic_ts=100.20)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker, max_observation_gap_seconds=0.50)
    evidence = correlator.correlate_flow(
        flow_id="flow_two_obs_trailing_gap",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=101.50,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=101.50,
    )

    assert evidence.max_observation_gap_seconds == pytest.approx(1.30, 0.01)
    assert evidence.evidence_quality == AttributionQuality.MEDIUM.value
    assert evidence.rejection_code in (
        AttributionRejectionCode.MAX_OBSERVATION_GAP_EXCEEDED.value,
        AttributionRejectionCode.LOW_COVERAGE_RATIO.value,
    )


# ==============================================================================
# 6. Two observations: acceptable internal gap, excessive leading gap
# ==============================================================================

def test_two_observations_acceptable_internal_excessive_leading_gap():
    """Requirement 6: Acceptable internal gap (0.15s) but leading gap (1.30s > 0.50s) is rejected."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    # Flow lasts 1.50s: [100.00, 101.50]
    # Obs at 101.30 and 101.45 (internal gap = 0.15s)
    # Leading gap = 101.30 - 100.00 = 1.30s > 0.50s
    snap_mgr.add_snapshot(101.30, [_make_tcp_entry(101.30)], monotonic_ts=101.30)
    snap_mgr.add_snapshot(101.45, [_make_tcp_entry(101.45)], monotonic_ts=101.45)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker, max_observation_gap_seconds=0.50)
    evidence = correlator.correlate_flow(
        flow_id="flow_two_obs_leading_gap",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=101.50,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=101.50,
    )

    assert evidence.max_observation_gap_seconds == pytest.approx(1.30, 0.01)
    assert evidence.evidence_quality == AttributionQuality.MEDIUM.value
    assert evidence.rejection_code in (
        AttributionRejectionCode.MAX_OBSERVATION_GAP_EXCEEDED.value,
        AttributionRejectionCode.LOW_COVERAGE_RATIO.value,
    )


# ==============================================================================
# 7. No Matching Observations
# ==============================================================================

def test_no_matching_observations():
    """Requirement 7: Zero matching observations yield coverage 0, gap None, and UNATTRIBUTED."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_no_obs",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=100.50,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=100.50,
    )

    assert evidence.matched_observation_count == 0
    assert evidence.attribution_coverage_ratio == 0.0
    assert evidence.max_observation_gap_seconds is None  # Unavailable
    assert evidence.evidence_quality == AttributionQuality.UNATTRIBUTED.value
    assert evidence.rejection_code in (
        AttributionRejectionCode.NO_CONTEMPORANEOUS_SNAPSHOTS.value,
        AttributionRejectionCode.ENDPOINT_NOT_IN_SNAPSHOT.value,
    )


# ==============================================================================
# 8. Single Matching Observation
# ==============================================================================

def test_single_matching_observation():
    """Requirement 8: Single matching observation calculates boundary gaps but rejects HIGH quality."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    # Flow lasts 0.30s: [100.00, 100.30]
    # Single obs at 100.15 (G_start = 0.15s, G_end = 0.15s -> G_max = 0.15s)
    snap_mgr.add_snapshot(100.15, [_make_tcp_entry(100.15)], monotonic_ts=100.15)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_single_obs",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=100.30,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=100.30,
    )

    assert evidence.matched_observation_count == 1
    assert evidence.max_observation_gap_seconds == pytest.approx(0.15, 0.01)
    assert evidence.evidence_quality == AttributionQuality.MEDIUM.value
    assert evidence.rejection_code == AttributionRejectionCode.OBSERVATION_COUNT_BELOW_MINIMUM.value


# ==============================================================================
# 9. Zero-Duration Flow
# ==============================================================================

def test_zero_duration_flow():
    """Requirement 9: Single-packet zero-duration flow receives 0 coverage, gap None, and rejects HIGH."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    snap_mgr.add_snapshot(100.00, [_make_tcp_entry(100.00)], monotonic_ts=100.00)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_zero_dur",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=100.00,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=100.00,
    )

    assert evidence.attribution_coverage_ratio == 0.0
    assert evidence.max_observation_gap_seconds is None
    assert evidence.evidence_quality != AttributionQuality.HIGH.value
    assert evidence.rejection_code in (
        AttributionRejectionCode.ZERO_DURATION_FLOW.value,
        AttributionRejectionCode.OBSERVATION_COUNT_BELOW_MINIMUM.value,
    )


# ==============================================================================
# 10. Negative-Duration Flow
# ==============================================================================

def test_negative_duration_flow():
    """Requirement 10: Inverted timestamp flow receives 0 coverage, gap None, and rejects HIGH."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    snap_mgr.add_snapshot(100.00, [_make_tcp_entry(100.00)], monotonic_ts=100.00)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_neg_dur",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.50,
        last_packet_wire_ts=100.00,
        first_packet_mono_ts=100.50,
        last_packet_mono_ts=100.00,
    )

    assert evidence.attribution_coverage_ratio == 0.0
    assert evidence.max_observation_gap_seconds is None
    assert evidence.evidence_quality != AttributionQuality.HIGH.value
    assert evidence.rejection_code in (
        AttributionRejectionCode.ZERO_DURATION_FLOW.value,
        AttributionRejectionCode.OBSERVATION_COUNT_BELOW_MINIMUM.value,
    )


# ==============================================================================
# 11. Duplicate Timestamps
# ==============================================================================

def test_duplicate_timestamps():
    """Requirement 11: Duplicate snapshot timestamps at same instant do not create spurious 0.0 gaps."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    # Flow lasts 0.30s: [100.00, 100.30]
    # Two snapshots at 100.05, two at 100.20
    snap_mgr.add_snapshot(100.05, [_make_tcp_entry(100.05)], monotonic_ts=100.05)
    snap_mgr.add_snapshot(100.05, [_make_tcp_entry(100.05)], monotonic_ts=100.05)
    snap_mgr.add_snapshot(100.20, [_make_tcp_entry(100.20)], monotonic_ts=100.20)
    snap_mgr.add_snapshot(100.20, [_make_tcp_entry(100.20)], monotonic_ts=100.20)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_duplicates",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=100.30,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=100.30,
    )

    # Distinct timestamps: [100.05, 100.20]
    # G_start = 0.05, G_internal = 0.15, G_end = 0.10 -> G_max = 0.15s
    assert evidence.max_observation_gap_seconds == pytest.approx(0.15, 0.01)
    assert evidence.evidence_quality == AttributionQuality.HIGH.value
    assert evidence.rejection_code is None


# ==============================================================================
# 12. Out-of-Flow Observations Excluded from Gap and Coverage
# ==============================================================================

def test_out_of_flow_observations_excluded_from_all_coverage_calculations():
    """Requirement 12: Supplementary margin observations outside flow do not affect in-flow gap or coverage."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    # Flow lasts 0.30s: [100.00, 100.30]
    # Snapshots exist at 99.50 and 100.80 (in +-1.0s window margin, but OUTSIDE flow interval)
    snap_mgr.add_snapshot(99.50, [_make_tcp_entry(99.50)], monotonic_ts=99.50)
    snap_mgr.add_snapshot(100.80, [_make_tcp_entry(100.80)], monotonic_ts=100.80)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker, window_margin_seconds=1.0)
    evidence = correlator.correlate_flow(
        flow_id="flow_out_of_interval",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=100.30,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=100.30,
    )

    assert evidence.matched_observation_count == 0
    assert evidence.observed_bins_count == 0
    assert evidence.attribution_coverage_ratio == 0.0
    assert evidence.max_observation_gap_seconds is None  # Unavailable for in-flow
    assert evidence.evidence_quality in (AttributionQuality.MEDIUM.value, AttributionQuality.UNATTRIBUTED.value)


# ==============================================================================
# 13. Exact 0.50-Second Maximum-Gap Boundary
# ==============================================================================

def test_exact_0_50_second_maximum_gap_boundary():
    """Requirement 13: G_max == 0.50s exactly meets the max gap boundary condition."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    # Flow lasts 1.00s: [100.00, 101.00] (7 expected bins)
    # Snapshots at 100.50 and 101.00
    # G_start = 100.50 - 100.00 = 0.50s (exact boundary)
    # G_internal = 101.00 - 100.50 = 0.50s (exact boundary)
    # G_end = 101.00 - 101.00 = 0.00s
    # G_max = 0.50s <= 0.50s
    snap_mgr.add_snapshot(100.50, [_make_tcp_entry(100.50)], monotonic_ts=100.50)
    snap_mgr.add_snapshot(101.00, [_make_tcp_entry(101.00)], monotonic_ts=101.00)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker, max_observation_gap_seconds=0.50)
    evidence = correlator.correlate_flow(
        flow_id="flow_exact_boundary",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=101.00,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=101.00,
    )

    assert evidence.max_observation_gap_seconds == pytest.approx(0.50, 0.001)
    # G_max <= 0.50s condition is satisfied; does not reject for MAX_OBSERVATION_GAP_EXCEEDED
    assert evidence.rejection_code != AttributionRejectionCode.MAX_OBSERVATION_GAP_EXCEEDED.value


# ==============================================================================
# 14. Maximum Gap Precision Tests (0.500s accepted, 0.5000001s & 0.501s rejected)
# ==============================================================================

def test_maximum_gap_exact_0_500_seconds_accepted():
    """Policy Precision: Exact 0.500s maximum gap is accepted and qualifies for HIGH quality."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    # Flow lasts 1.00s: [100.00, 101.00] (7 expected bins, 4 covered bins -> 57.1% coverage)
    # Snapshots at: 100.50, 100.65, 100.80, 100.95, 101.00
    # G_start = 100.50 - 100.00 = 0.500s, G_internal <= 0.15s, G_end = 0.0s -> G_max = 0.500s <= 0.500s
    for t in (100.50, 100.65, 100.80, 100.95, 101.00):
        snap_mgr.add_snapshot(t, [_make_tcp_entry(t)], monotonic_ts=t)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker, max_observation_gap_seconds=0.50)
    evidence = correlator.correlate_flow(
        flow_id="flow_exact_0_500",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=101.00,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=101.00,
    )

    assert evidence.max_observation_gap_seconds == pytest.approx(0.500, 0.0001)
    assert evidence.attribution_coverage_ratio >= 0.50
    assert evidence.evidence_quality == AttributionQuality.HIGH.value
    assert evidence.rejection_reason is None
    assert evidence.rejection_code is None


def test_maximum_gap_0_5000001_seconds_rejected():
    """Policy Precision: Raw gap of 0.5000001s strictly exceeds 0.500s and is rejected."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    # Flow lasts 1.00s: [100.00, 101.00] (7 expected bins, 4 covered bins -> 57.1% coverage)
    # Snapshot at 100.5000001 creates a leading boundary gap of 0.5000001s > 0.500s
    for t in (100.5000001, 100.65, 100.80, 100.95, 101.00):
        snap_mgr.add_snapshot(t, [_make_tcp_entry(t)], monotonic_ts=t)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker, max_observation_gap_seconds=0.50)
    evidence = correlator.correlate_flow(
        flow_id="flow_gap_0_5000001",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=101.00,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=101.00,
    )

    # Raw unrounded comparison strictly rejects 0.5000001s > 0.500s
    assert evidence.attribution_coverage_ratio >= 0.50
    assert evidence.evidence_quality == AttributionQuality.MEDIUM.value
    assert evidence.rejection_code == AttributionRejectionCode.MAX_OBSERVATION_GAP_EXCEEDED.value
    assert "exceeded limit" in (evidence.rejection_reason or "")
    # Serialized dictionary rounds the value for clean reporting
    assert evidence.to_dict()["max_observation_gap_seconds"] == 0.5


def test_maximum_gap_0_501_seconds_rejected():
    """Policy Precision: Raw gap of 0.501s strictly exceeds 0.500s and is rejected."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    # Flow lasts 1.00s: [100.00, 101.00] (7 expected bins, 4 covered bins -> 57.1% coverage)
    # Snapshot at 100.501 creates a leading boundary gap of 0.501s > 0.500s
    for t in (100.501, 100.65, 100.80, 100.95, 101.00):
        snap_mgr.add_snapshot(t, [_make_tcp_entry(t)], monotonic_ts=t)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker, max_observation_gap_seconds=0.50)
    evidence = correlator.correlate_flow(
        flow_id="flow_gap_0_501",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=101.00,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=101.00,
    )

    assert evidence.attribution_coverage_ratio >= 0.50
    assert evidence.evidence_quality == AttributionQuality.MEDIUM.value
    assert evidence.rejection_code == AttributionRejectionCode.MAX_OBSERVATION_GAP_EXCEEDED.value
    assert "exceeded limit" in (evidence.rejection_reason or "")
    assert evidence.max_observation_gap_seconds == pytest.approx(0.501, 0.0001)


def test_maximum_gap_slightly_greater_than_0_50_seconds():
    """Requirement 14: G_max == 0.51s (> 0.50s) triggers MAX_OBSERVATION_GAP_EXCEEDED rejection."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    # Flow lasts 1.01s: [100.00, 101.01] (7 expected bins)
    # Snapshots: 100.51, 100.66, 100.81, 100.96 (4 bins observed / 7 = 57% coverage)
    # G_start = 100.51 - 100.00 = 0.51s > 0.50s!
    # G_internal = 0.15s, G_end = 101.01 - 100.96 = 0.05s
    # G_max = 0.51s > 0.50s!
    for t in (100.51, 100.66, 100.81, 100.96):
        snap_mgr.add_snapshot(t, [_make_tcp_entry(t)], monotonic_ts=t)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker, max_observation_gap_seconds=0.50)
    evidence = correlator.correlate_flow(
        flow_id="flow_slightly_greater_gap",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=101.01,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=101.01,
    )

    assert evidence.max_observation_gap_seconds == pytest.approx(0.51, 0.001)
    assert evidence.attribution_coverage_ratio >= 0.50
    assert evidence.evidence_quality == AttributionQuality.MEDIUM.value
    assert evidence.rejection_code == AttributionRejectionCode.MAX_OBSERVATION_GAP_EXCEEDED.value


# ==============================================================================
# 15. Adversarial Counterexample: 10-Second Flow, 34 Covered Bins (50.7% Coverage)
# ==============================================================================

def test_ten_second_34_bin_counterexample():
    """
    Requirement 15: Adversarial Counterexample Fixture.

    Flow interval: [100.00, 110.00] (10.0s duration)
    Polling interval: 0.15s
    Expected bins: 67
    Observations: 100.05, 100.20, 100.35, ... through 105.00 (34 observations)
    Expected result:
    - 34 occupied bins.
    - Coverage approximately 0.507.
    - Internal maximum gap approximately 0.15s.
    - Trailing boundary gap approximately 5.0s (110.00 - 105.00).
    - HIGH-quality attribution rejected with MAX_OBSERVATION_GAP_EXCEEDED.
    """
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager(snapshot_interval_seconds=0.15)

    # Populate 34 snapshots from 100.05 through 105.00 every 0.15s
    # (105.00 - 100.05) / 0.15 = 33 step intervals -> 34 snapshots
    obs_timestamps: List[float] = []
    for i in range(34):
        t = round(100.05 + i * 0.15, 6)
        obs_timestamps.append(t)
        snap_mgr.add_snapshot(t, [_make_tcp_entry(t)], monotonic_ts=t)

    assert len(obs_timestamps) == 34
    assert obs_timestamps[-1] == 105.00

    correlator = ProcessSocketCorrelator(
        snap_mgr,
        tracker,
        max_observation_gap_seconds=0.50,
        min_tcp_coverage_ratio=0.50,
        min_covered_bins=2,
    )
    evidence = correlator.correlate_flow(
        flow_id="flow_adversarial_counterexample",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=110.00,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=110.00,
    )

    # 1. 34 occupied bins
    assert evidence.observed_bins_count == 34

    # 2. 67 expected bins
    assert evidence.expected_bins_count == 67

    # 3. Coverage approximately 0.507 (34 / 67 = 0.50746...)
    assert evidence.attribution_coverage_ratio == pytest.approx(34 / 67, 0.001)
    assert evidence.attribution_coverage_ratio >= 0.50

    # 4. Trailing boundary gap is 5.0 seconds (110.00 - 105.00)
    assert evidence.max_observation_gap_seconds == pytest.approx(5.00, 0.01)

    # 5. HIGH-quality attribution rejected
    assert evidence.evidence_quality == AttributionQuality.MEDIUM.value

    # 6. Rejection reason is MAX_OBSERVATION_GAP_EXCEEDED
    assert evidence.rejection_code == AttributionRejectionCode.MAX_OBSERVATION_GAP_EXCEEDED.value
    assert "Maximum gap between observations" in (evidence.rejection_reason or "")

    # 7. Policy recommendation remains AMBIGUOUS
    policy = AttributionEvidencePolicy()
    tc, qual, src, rej = policy.evaluate_label_recommendation(evidence, "Web")
    assert tc is None
    assert qual == "AMBIGUOUS"
    assert "Maximum gap between observations" in (rej or "")


# ==============================================================================
# 16. Correct TCP State-Dependent Quality Matrix
# ==============================================================================

@pytest.mark.parametrize("state,expected_quality,expected_code", [
    ("ESTABLISHED", AttributionQuality.HIGH.value, None),
    ("SYN_SENT", AttributionQuality.MEDIUM.value, AttributionRejectionCode.TRANSITIONAL_STATE_ONLY.value),
    ("SYN_RCVD", AttributionQuality.MEDIUM.value, AttributionRejectionCode.TRANSITIONAL_STATE_ONLY.value),
    ("FIN_WAIT_1", AttributionQuality.MEDIUM.value, AttributionRejectionCode.TRANSITIONAL_STATE_ONLY.value),
    ("CLOSE_WAIT", AttributionQuality.MEDIUM.value, AttributionRejectionCode.TRANSITIONAL_STATE_ONLY.value),
    ("TIME_WAIT", AttributionQuality.UNATTRIBUTED.value, AttributionRejectionCode.TIME_WAIT_ONLY.value),
])
def test_correct_tcp_state_dependent_quality(state: str, expected_quality: str, expected_code: str | None):
    """TCP state matrix enforces ESTABLISHED for HIGH, transitional for MEDIUM, TIME_WAIT for UNATTRIBUTED."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    # Flow lasting 0.30s (2 bins) with 2 observations
    snap_mgr.add_snapshot(100.05, [_make_tcp_entry(100.05, state=state)], monotonic_ts=100.05)
    snap_mgr.add_snapshot(100.20, [_make_tcp_entry(100.20, state=state)], monotonic_ts=100.20)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id=f"flow_state_{state}",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=100.30,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=100.30,
    )

    assert evidence.evidence_quality == expected_quality
    assert evidence.rejection_code == expected_code


def test_tcp_listen_and_closed_excluded():
    """Server listeners (LISTEN, CLOSED) are strictly excluded from active connection matching."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    listen_entry = TransientSocketEntry(
        protocol="TCP",
        local_address="0.0.0.0",
        local_port=54321,
        remote_address="0.0.0.0",
        remote_port=0,
        state="LISTEN",
        pid=1004,
        timestamp_utc=100.10,
    )
    snap_mgr.add_snapshot(100.10, [listen_entry])

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_listen_check",
        protocol="TCP",
        endpoint_a=("192.168.1.50", 54321),
        endpoint_b=("93.184.216.34", 443),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=100.30,
    )

    assert evidence.evidence_method == AttributionEvidenceMethod.PROCESS_NOT_FOUND.value
    assert evidence.evidence_quality == AttributionQuality.UNATTRIBUTED.value


# ==============================================================================
# 17. No VERIFIED Promotion for UDP
# ==============================================================================

def test_no_verified_promotion_for_udp():
    """UDP local endpoint match is strictly ineligible for VERIFIED promotion even with 100% coverage."""
    tracker = _create_controlled_tracker()
    snap_mgr = SocketSnapshotManager()

    udp_entry_1 = TransientSocketEntry(
        protocol="UDP",
        local_address="192.168.1.50",
        local_port=53535,
        pid=1004,
        process_create_time_utc="2026-11-21T10:00:01Z",
        process_name="chrome.exe",
        timestamp_utc=100.05,
        monotonic_ts=100.05,
    )
    udp_entry_2 = TransientSocketEntry(
        protocol="UDP",
        local_address="192.168.1.50",
        local_port=53535,
        pid=1004,
        process_create_time_utc="2026-11-21T10:00:01Z",
        process_name="chrome.exe",
        timestamp_utc=100.20,
        monotonic_ts=100.20,
    )
    snap_mgr.add_snapshot(100.05, [udp_entry_1], monotonic_ts=100.05)
    snap_mgr.add_snapshot(100.20, [udp_entry_2], monotonic_ts=100.20)

    correlator = ProcessSocketCorrelator(snap_mgr, tracker)
    evidence = correlator.correlate_flow(
        flow_id="flow_udp_verified_test",
        protocol="UDP",
        endpoint_a=("192.168.1.50", 53535),
        endpoint_b=("8.8.8.8", 53),
        first_packet_wire_ts=100.00,
        last_packet_wire_ts=100.30,
        first_packet_mono_ts=100.00,
        last_packet_mono_ts=100.30,
    )

    assert evidence.evidence_method == AttributionEvidenceMethod.UDP_LOCAL_ENDPOINT_PROCESS_MATCH.value
    assert evidence.attribution_coverage_ratio == 1.00
    assert evidence.evidence_quality == AttributionQuality.MEDIUM.value
    assert evidence.rejection_code == AttributionRejectionCode.UDP_LOCAL_ENDPOINT_UNVERIFIED.value

    policy = AttributionEvidencePolicy()
    tc, qual, src, rej = policy.evaluate_label_recommendation(evidence, "Web")
    assert tc is None
    assert qual == "AMBIGUOUS"
    assert "UDP local endpoint match alone is insufficient" in (rej or "")


# ==============================================================================
# 18. Canonical Traffic-Class Consistency ("Web" vs "web_traffic")
# ==============================================================================

def test_canonical_traffic_class_consistency():
    """Traffic class aliases (web_traffic, browsing, web) strictly canonicalize to 'Web'."""
    assert canonicalize_traffic_class("web_traffic") == "Web"
    assert canonicalize_traffic_class("web") == "Web"
    assert canonicalize_traffic_class("browsing") == "Web"
    assert canonicalize_traffic_class("http") == "Web"
    assert canonicalize_traffic_class("https") == "Web"
    assert canonicalize_traffic_class("Web") == "Web"
    assert canonicalize_traffic_class("Video") == "Video"
    assert canonicalize_traffic_class("streaming") == "Video"
    assert canonicalize_traffic_class("Messaging") == "Messaging"
    assert canonicalize_traffic_class(None) is None

    assert canonicalize_traffic_class("web_traffic") in VALID_TRAFFIC_CLASSES

    policy = AttributionEvidencePolicy()
    rec = AttributionEvidenceRecord(
        flow_id="flow_canonical_check",
        evidence_method="EXACT_TCP_PROCESS_MATCH",
        application_alias="chrome_controlled",
        matched_observation_count=3,
        attribution_coverage_ratio=0.85,
        unique_owner=True,
        evidence_quality="HIGH",
    )

    tc, qual, src, rej = policy.evaluate_label_recommendation(
        rec,
        intended_traffic_class="web_traffic",
        controlled_app_alias="chrome_controlled",
    )

    assert tc == "Web"  # Canonicalized from 'web_traffic' to 'Web'
    assert qual == "VERIFIED"
    assert tc in VALID_TRAFFIC_CLASSES
