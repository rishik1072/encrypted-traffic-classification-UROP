"""
Process-to-Socket Attribution Correlator for Dataset V3.

Correlates in-flight or completed flow 5-tuples against time-stamped socket table
snapshots and process tree identities. Classifies evidence into the 6 canonical categories:
- EXACT_TCP_PROCESS_MATCH
- UDP_LOCAL_ENDPOINT_PROCESS_MATCH
- MULTIPLE_PROCESS_MATCH
- PROCESS_NOT_FOUND
- STALE_SOCKET_OBSERVATION
- INSUFFICIENT_EVIDENCE

Strengthened Evidence Policy & Sampling Coverage Estimate:
- ESTABLISHED state is required for HIGH-quality exact TCP matching.
- Transitional connection states (SYN_SENT, FIN_WAIT, CLOSE_WAIT, etc.) receive MEDIUM quality.
- TIME_WAIT state is treated as stale unless supported by valid earlier ESTABLISHED evidence.
- LISTEN and CLOSED sockets are strictly excluded from active connection matching.
- Sampling Density Estimate: Flow interval is divided into bins of width equal to polling interval.
  Coverage = observed_bins / expected_bins (clamped to [0, 1]).
  Only in-flow matching observations contribute to coverage.
- Zero-duration or invalid-duration flows receive 0.0 coverage and never qualify for HIGH quality.
- HIGH-quality rating requires:
  1. Unique owner & controlled alias
  2. Positive flow duration (delta_t > 0)
  3. In-flow observation count >= min_observation_count (>= 2)
  4. Distinct in-flow monotonic timestamps >= min_observation_count
  5. Temporal separation >= min_observation_separation_seconds (>= 0.10s)
  6. Covered sampling bins >= min_covered_bins (>= 2)
  7. Sampling coverage ratio >= min_tcp_coverage_ratio (>= 0.50)
  8. Maximum gap between observations <= max_observation_gap_seconds (<= 0.50s)
  9. At least one ESTABLISHED observation in-flow.
- Single snapshot observations yield at most MEDIUM quality and never qualify for VERIFIED promotion.
- UDP local endpoint matching yields at most MEDIUM/LOW and never qualifies for VERIFIED promotion.

Strictly outputs only privacy-preserving AttributionEvidenceRecord instances.
"""

from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional, Set, Tuple

from research.dataset_v3.attribution.ip_helper import normalize_ip_address, normalize_port
from research.dataset_v3.attribution.process_tracker import ProcessTracker
from research.dataset_v3.attribution.schemas import (
    ATTRIBUTION_RULE_VERSION,
    AttributionEvidenceMethod,
    AttributionEvidenceRecord,
    AttributionQuality,
    AttributionRejectionCode,
    TransientSocketEntry,
)
from research.dataset_v3.attribution.snapshot_manager import SocketSnapshotManager

logger = logging.getLogger("research.dataset_v3.attribution.correlator")


# Active TCP states representing live connection lifecycle (RFC 793)
# Listeners and closed sockets are strictly excluded from matching active traffic
ESTABLISHED_STATE: str = "ESTABLISHED"
TRANSITIONAL_TCP_STATES: Set[str] = {
    "SYN_SENT",
    "SYN_RCVD",
    "FIN_WAIT_1",
    "FIN_WAIT_2",
    "CLOSE_WAIT",
    "CLOSING",
    "LAST_ACK",
}
TIME_WAIT_STATE: str = "TIME_WAIT"
ACTIVE_TCP_STATES: Set[str] = {ESTABLISHED_STATE} | TRANSITIONAL_TCP_STATES | {TIME_WAIT_STATE}


def calculate_sampling_coverage_estimate(
    flow_start: float,
    flow_end: float,
    observation_timestamps: List[float],
    bin_width: float = 0.15,
) -> Tuple[float, int, int, Optional[float], List[float]]:
    """
    Computes a documented sampling-density-based coverage estimate and
    boundary-aware maximum observation gap for a flow.

    1. Divides the observed flow interval into bins of width equal to bin_width.
    2. Counts only bins containing at least one valid matching observation.
    3. Multiple observations in the same bin are counted only once.
    4. Excludes observations outside the actual flow interval [flow_start, flow_end].
    5. Calculates coverage = observed_bins / expected_bins clamped to [0, 1].
    6. Returns 0.0 coverage and max_gap = None for zero or negative duration flows.
    7. Calculates boundary-aware maximum gap:
       G_start = t_1 - flow_start
       G_internal = max(t_{i+1} - t_i) for sorted distinct in-flow timestamps
       G_end = flow_end - t_k
       G_max = max(G_start, G_internal, G_end)
       For no valid observations, max_gap is None (unavailable).

    Returns:
        (coverage_ratio, observed_bins_count, expected_bins_count, max_observation_gap, in_flow_timestamps)
    """
    duration = round(flow_end - flow_start, 6)
    if duration <= 0.0 or bin_width <= 0.0:
        return (0.0, 0, 0, None, [])

    # Filter observations strictly within actual flow boundaries
    in_flow_ts = sorted([t for t in observation_timestamps if flow_start <= t <= flow_end])
    expected_bins = max(1, math.ceil(round(duration / bin_width, 6)))

    if not in_flow_ts:
        return (0.0, 0, expected_bins, None, [])

    covered_bins: Set[int] = set()
    for t in in_flow_ts:
        offset = t - flow_start
        bin_idx = int(offset / bin_width)
        bin_idx = min(expected_bins - 1, max(0, bin_idx))
        covered_bins.add(bin_idx)

    observed_bins = len(covered_bins)
    coverage = observed_bins / float(expected_bins)
    coverage = max(0.0, min(1.0, coverage))

    # Boundary-aware maximum gap calculation using distinct sorted timestamps (raw unrounded)
    distinct_ts = sorted(list(set(in_flow_ts)))
    k = len(distinct_ts)

    g_start = max(0.0, distinct_ts[0] - flow_start)
    g_end = max(0.0, flow_end - distinct_ts[-1])

    if k >= 2:
        g_internal = max(
            max(0.0, distinct_ts[i + 1] - distinct_ts[i])
            for i in range(k - 1)
        )
        max_gap = max(g_start, g_internal, g_end)
    else:
        # Single observation: gap is the larger of the two boundary intervals
        max_gap = max(g_start, g_end)

    return (coverage, observed_bins, expected_bins, max_gap, in_flow_ts)


class ProcessSocketCorrelator:
    """
    Correlates flow endpoints and timing against volatile socket table snapshots.
    """

    def __init__(
        self,
        snapshot_manager: SocketSnapshotManager,
        process_tracker: ProcessTracker,
        window_margin_seconds: float = 1.0,
        stale_threshold_seconds: float = 5.0,
        min_observation_separation_seconds: float = 0.10,
        min_tcp_coverage_ratio: float = 0.5,
        min_observation_count: int = 2,
        max_observation_gap_seconds: float = 0.50,
        min_covered_bins: int = 2,
        sampling_bin_width_seconds: Optional[float] = None,
    ) -> None:
        self.snapshot_manager = snapshot_manager
        self.process_tracker = process_tracker
        self.window_margin_seconds = window_margin_seconds
        self.stale_threshold_seconds = stale_threshold_seconds
        self.min_observation_separation_seconds = min_observation_separation_seconds
        self.min_tcp_coverage_ratio = min_tcp_coverage_ratio
        self.min_observation_count = min_observation_count
        self.max_observation_gap_seconds = max_observation_gap_seconds
        self.min_covered_bins = min_covered_bins
        self.sampling_bin_width_seconds = (
            sampling_bin_width_seconds
            if sampling_bin_width_seconds is not None
            else getattr(snapshot_manager, "snapshot_interval_seconds", 0.15)
        )

    def correlate_flow(
        self,
        flow_id: str,
        protocol: str,
        endpoint_a: Tuple[str, int],  # (src_ip, src_port)
        endpoint_b: Tuple[str, int],  # (dst_ip, dst_port)
        first_packet_wire_ts: float,
        last_packet_wire_ts: float,
        first_packet_mono_ts: Optional[float] = None,
        last_packet_mono_ts: Optional[float] = None,
    ) -> AttributionEvidenceRecord:
        """
        Correlates a flow against socket snapshots in volatile memory.

        Guarantees:
        - Evaluates TCP 4-tuples bidirectionally.
        - Evaluates UDP local endpoint ownership.
        - Enforces monotonic timestamp alignment when provided.
        - Computes sampling density estimate across configured polling interval bins.
        - Excludes observations outside the flow interval from coverage.
        - Enforces minimum observation count, distinct timestamps, separation, and max gap.
        - Strictly filters out LISTEN and CLOSED connection states.
        - Treats TIME_WAIT as stale unless preceded by ESTABLISHED.
        - Wipes all IP and port strings from output evidence records.
        """
        proto_clean = protocol.upper()
        norm_ip_a = normalize_ip_address(endpoint_a[0])
        norm_p_a = normalize_port(endpoint_a[1])
        norm_ip_b = normalize_ip_address(endpoint_b[0])
        norm_p_b = normalize_port(endpoint_b[1])

        # Determine alignment mode (monotonic when available)
        use_mono = (first_packet_mono_ts is not None and last_packet_mono_ts is not None)
        start_t = first_packet_mono_ts if use_mono else first_packet_wire_ts
        end_t = last_packet_mono_ts if use_mono else last_packet_wire_ts

        flow_duration = end_t - start_t
        is_zero_or_invalid_duration = (flow_duration <= 0.0)

        # Query contemporaneous snapshots (with correlation margin for context)
        snapshots_in_window = self.snapshot_manager.get_snapshots_in_window(
            start_ts=start_t,
            end_ts=end_t,
            margin_seconds=self.window_margin_seconds,
            use_monotonic=use_mono,
        )

        total_cand_snapshots = len(snapshots_in_window)

        # Helper to check if socket was observed outside contemporaneous window
        def _check_distant_match() -> bool:
            with self.snapshot_manager._lock:
                all_records = list(self.snapshot_manager._snapshots)
            w_start = start_t - self.window_margin_seconds
            w_end = end_t + self.window_margin_seconds

            for s in all_records:
                snap_time = s.mono_ts if use_mono else s.wall_ts
                if snap_time < w_start or snap_time > w_end:
                    for entry in s.entries:
                        if entry.protocol != proto_clean:
                            continue
                        if proto_clean == "TCP":
                            if (entry.local_port in (norm_p_a, norm_p_b)) and (entry.remote_port in (norm_p_a, norm_p_b)):
                                return True
                        elif proto_clean == "UDP":
                            if entry.local_port in (norm_p_a, norm_p_b):
                                return True
            return False

        # Case 1: No snapshots in contemporaneous window
        if total_cand_snapshots == 0:
            if _check_distant_match():
                return AttributionEvidenceRecord(
                    flow_id=flow_id,
                    evidence_method=AttributionEvidenceMethod.STALE_SOCKET_OBSERVATION.value,
                    application_alias=None,
                    matched_observation_count=0,
                    attribution_coverage_ratio=0.0,
                    unique_owner=False,
                    evidence_quality=AttributionQuality.UNATTRIBUTED.value,
                    attribution_rule_version=ATTRIBUTION_RULE_VERSION,
                    rejection_reason="Socket observed only outside active flow lifetime boundaries",
                    rejection_code=AttributionRejectionCode.SOCKET_OUTSIDE_FLOW_LIFETIME.value,
                    observed_bins_count=0,
                    expected_bins_count=0,
                    max_observation_gap_seconds=None,
                )

            return AttributionEvidenceRecord(
                flow_id=flow_id,
                evidence_method=AttributionEvidenceMethod.INSUFFICIENT_EVIDENCE.value,
                application_alias=None,
                matched_observation_count=0,
                attribution_coverage_ratio=0.0,
                unique_owner=False,
                evidence_quality=AttributionQuality.UNATTRIBUTED.value,
                attribution_rule_version=ATTRIBUTION_RULE_VERSION,
                rejection_reason="No contemporaneous socket table snapshots captured during flow lifetime",
                rejection_code=AttributionRejectionCode.NO_CONTEMPORANEOUS_SNAPSHOTS.value,
                observed_bins_count=0,
                expected_bins_count=0,
                max_observation_gap_seconds=None,
            )

        # Collect matching observations in the queried window
        # Format: (snap_ts, pid, ctime, pname, app_alias, is_ctrl, state, obs_mono)
        matched_observations: List[Tuple[float, int, Optional[str], Optional[str], Optional[str], bool, Optional[str], float]] = []

        for snap_ts, entries in snapshots_in_window:
            for entry in entries:
                if entry.protocol != proto_clean:
                    continue

                is_match = False
                if proto_clean == "TCP":
                    # Connection state filtering: Listeners and closed sockets are strictly excluded
                    if entry.state and entry.state not in ACTIVE_TCP_STATES:
                        continue

                    # Bidirectional 4-tuple matching
                    fwd_match = (
                        (entry.local_address == norm_ip_a or entry.local_address in ("0.0.0.0", "::"))
                        and entry.local_port == norm_p_a
                        and (entry.remote_address == norm_ip_b or entry.remote_address in ("0.0.0.0", "::"))
                        and entry.remote_port == norm_p_b
                    )
                    rev_match = (
                        (entry.local_address == norm_ip_b or entry.local_address in ("0.0.0.0", "::"))
                        and entry.local_port == norm_p_b
                        and (entry.remote_address == norm_ip_a or entry.remote_address in ("0.0.0.0", "::"))
                        and entry.remote_port == norm_p_a
                    )
                    is_match = fwd_match or rev_match

                elif proto_clean == "UDP":
                    # UDP Local Endpoint Ownership matching
                    match_a = (
                        (entry.local_address == norm_ip_a or entry.local_address in ("0.0.0.0", "::"))
                        and entry.local_port == norm_p_a
                    )
                    match_b = (
                        (entry.local_address == norm_ip_b or entry.local_address in ("0.0.0.0", "::"))
                        and entry.local_port == norm_p_b
                    )
                    is_match = match_a or match_b

                if is_match:
                    alias, is_ctrl = self.process_tracker.resolve_application_alias(
                        pid=entry.pid,
                        create_time_utc=entry.process_create_time_utc,
                        process_name=entry.process_name,
                    )
                    entry_mono = getattr(entry, "monotonic_ts", None)
                    obs_mono = entry_mono if entry_mono is not None else snap_ts
                    matched_observations.append(
                        (snap_ts, entry.pid, entry.process_create_time_utc, entry.process_name, alias, is_ctrl, entry.state, obs_mono)
                    )

        # Case 2: Zero matches contemporaneous with flow
        if not matched_observations:
            if _check_distant_match():
                return AttributionEvidenceRecord(
                    flow_id=flow_id,
                    evidence_method=AttributionEvidenceMethod.STALE_SOCKET_OBSERVATION.value,
                    application_alias=None,
                    matched_observation_count=0,
                    attribution_coverage_ratio=0.0,
                    unique_owner=False,
                    evidence_quality=AttributionQuality.UNATTRIBUTED.value,
                    attribution_rule_version=ATTRIBUTION_RULE_VERSION,
                    rejection_reason="Socket observed only outside active flow lifetime boundaries",
                    rejection_code=AttributionRejectionCode.SOCKET_OUTSIDE_FLOW_LIFETIME.value,
                    observed_bins_count=0,
                    expected_bins_count=0,
                    max_observation_gap_seconds=None,
                )

            return AttributionEvidenceRecord(
                flow_id=flow_id,
                evidence_method=AttributionEvidenceMethod.PROCESS_NOT_FOUND.value,
                application_alias=None,
                matched_observation_count=0,
                attribution_coverage_ratio=0.0,
                unique_owner=False,
                evidence_quality=AttributionQuality.UNATTRIBUTED.value,
                attribution_rule_version=ATTRIBUTION_RULE_VERSION,
                rejection_reason="Endpoint socket was not present in contemporaneous socket table",
                rejection_code=AttributionRejectionCode.ENDPOINT_NOT_IN_SNAPSHOT.value,
                observed_bins_count=0,
                expected_bins_count=0,
                max_observation_gap_seconds=None,
            )

        # Filter observations strictly within actual flow boundaries for in-flow coverage
        all_obs_ts = [obs[7] if use_mono else obs[0] for obs in matched_observations]
        coverage_ratio, observed_bins, expected_bins, max_gap, in_flow_ts = calculate_sampling_coverage_estimate(
            flow_start=start_t,
            flow_end=end_t,
            observation_timestamps=all_obs_ts,
            bin_width=self.sampling_bin_width_seconds,
        )

        in_flow_observations = [
            obs for obs in matched_observations
            if start_t <= (obs[7] if use_mono else obs[0]) <= end_t
        ]

        # Case 3: Matches found — Check TCP state-dependent stale condition
        if proto_clean == "TCP":
            observed_states = {obs[6] for obs in matched_observations if obs[6]}
            if observed_states == {TIME_WAIT_STATE}:
                # Only TIME_WAIT observed without preceding ESTABLISHED connection
                return AttributionEvidenceRecord(
                    flow_id=flow_id,
                    evidence_method=AttributionEvidenceMethod.STALE_SOCKET_OBSERVATION.value,
                    application_alias=None,
                    matched_observation_count=len(in_flow_observations),
                    attribution_coverage_ratio=coverage_ratio,
                    unique_owner=False,
                    evidence_quality=AttributionQuality.UNATTRIBUTED.value,
                    attribution_rule_version=ATTRIBUTION_RULE_VERSION,
                    rejection_reason="TCP socket observed only in TIME_WAIT state without preceding active connection",
                    rejection_code=AttributionRejectionCode.TIME_WAIT_ONLY.value,
                    observed_bins_count=observed_bins,
                    expected_bins_count=expected_bins,
                    max_observation_gap_seconds=max_gap,
                )

        # Ownership consistency analysis across matched observations
        distinct_pids = {obs[1] for obs in matched_observations}
        distinct_proc_keys = {(obs[1], obs[2]) for obs in matched_observations}  # (pid, ctime)
        distinct_aliases = {obs[4] for obs in matched_observations if obs[4] is not None}

        if proto_clean == "UDP" and len(distinct_pids) > 1:
            # Multiple processes sharing same UDP port (e.g. SO_REUSEADDR or mDNS)
            return AttributionEvidenceRecord(
                flow_id=flow_id,
                evidence_method=AttributionEvidenceMethod.MULTIPLE_PROCESS_MATCH.value,
                application_alias=None,
                matched_observation_count=len(in_flow_observations),
                attribution_coverage_ratio=coverage_ratio,
                unique_owner=False,
                evidence_quality=AttributionQuality.LOW.value,
                attribution_rule_version=ATTRIBUTION_RULE_VERSION,
                rejection_reason="Shared UDP local endpoint bound by multiple distinct processes",
                rejection_code=AttributionRejectionCode.SHARED_UDP_LOCAL_ENDPOINT.value,
                observed_bins_count=observed_bins,
                expected_bins_count=expected_bins,
                max_observation_gap_seconds=max_gap,
            )

        # Check for multiple conflicting processes
        if len(distinct_proc_keys) > 1 and len(distinct_aliases) > 1:
            return AttributionEvidenceRecord(
                flow_id=flow_id,
                evidence_method=AttributionEvidenceMethod.MULTIPLE_PROCESS_MATCH.value,
                application_alias=None,
                matched_observation_count=len(in_flow_observations),
                attribution_coverage_ratio=coverage_ratio,
                unique_owner=False,
                evidence_quality=AttributionQuality.LOW.value,
                attribution_rule_version=ATTRIBUTION_RULE_VERSION,
                rejection_reason="Multiple conflicting process identities observed for endpoints",
                rejection_code=AttributionRejectionCode.CONFLICTING_PROCESS_IDENTITIES.value,
                observed_bins_count=observed_bins,
                expected_bins_count=expected_bins,
                max_observation_gap_seconds=max_gap,
            )

        # Single consistent owner evaluation
        dominant_alias = next(iter(distinct_aliases)) if distinct_aliases else "system_background"
        any_controlled = any(obs[5] for obs in matched_observations)
        unique_owner = (len(distinct_proc_keys) <= 1 and len(distinct_aliases) <= 1)
        in_flow_count = len(in_flow_observations)

        # Monotonic timestamps for separation analysis (strictly in-flow)
        distinct_in_flow_mono_ts = len(set(in_flow_ts))
        ts_separation = (max(in_flow_ts) - min(in_flow_ts)) if in_flow_ts else 0.0

        if proto_clean == "TCP":
            method = AttributionEvidenceMethod.EXACT_TCP_PROCESS_MATCH.value
            has_established_in_flow = any(obs[6] == ESTABLISHED_STATE for obs in in_flow_observations)

            # Strict HIGH-quality requirements:
            # 1. Unique process owner
            # 2. Controlled application alias
            # 3. Not zero or invalid duration (delta_t > 0)
            # 4. In-flow observation count >= min_observation_count (default >= 2)
            # 5. Distinct in-flow monotonic timestamps >= min_observation_count
            # 6. Minimum temporal separation (default >= 0.10s)
            # 7. Covered sampling bins >= min_covered_bins (default >= 2)
            # 8. Sampling density coverage ratio >= min_tcp_coverage_ratio (default >= 0.50)
            # 9. Maximum observation gap <= max_observation_gap_seconds (default <= 0.50s)
            # 10. At least one ESTABLISHED observation in-flow
            is_high_candidate = (
                unique_owner
                and any_controlled
                and dominant_alias == self.process_tracker.controlled_app_alias
                and not is_zero_or_invalid_duration
                and in_flow_count >= self.min_observation_count
                and distinct_in_flow_mono_ts >= self.min_observation_count
                and ts_separation >= self.min_observation_separation_seconds
                and observed_bins >= self.min_covered_bins
                and coverage_ratio >= self.min_tcp_coverage_ratio
                and (max_gap is not None and max_gap <= self.max_observation_gap_seconds)
                and has_established_in_flow
            )

            if is_high_candidate:
                quality = AttributionQuality.HIGH.value
                rejection_reason = None
                rejection_code = None
            else:
                quality = AttributionQuality.MEDIUM.value
                if is_zero_or_invalid_duration:
                    rejection_reason = "Zero or invalid flow duration cannot receive HIGH-quality attribution"
                    rejection_code = AttributionRejectionCode.ZERO_DURATION_FLOW.value
                elif in_flow_count < self.min_observation_count:
                    rejection_reason = f"Observation count ({in_flow_count}) below minimum requirement ({self.min_observation_count})"
                    rejection_code = AttributionRejectionCode.OBSERVATION_COUNT_BELOW_MINIMUM.value
                elif not has_established_in_flow:
                    rejection_reason = "TCP socket observed only in transitional connection states without ESTABLISHED"
                    rejection_code = AttributionRejectionCode.TRANSITIONAL_STATE_ONLY.value
                elif ts_separation < self.min_observation_separation_seconds:
                    rejection_reason = f"Observations lack minimum required temporal separation ({ts_separation:.3f}s < {self.min_observation_separation_seconds:.3f}s)"
                    rejection_code = AttributionRejectionCode.TEMPORAL_SEPARATION_INSUFFICIENT.value
                elif observed_bins < self.min_covered_bins:
                    rejection_reason = f"Covered sampling bins ({observed_bins}) below minimum requirement ({self.min_covered_bins})"
                    rejection_code = AttributionRejectionCode.INSUFFICIENT_COVERED_BINS.value
                elif coverage_ratio < self.min_tcp_coverage_ratio:
                    rejection_reason = f"Coverage ratio ({coverage_ratio:.2f}) below threshold ({self.min_tcp_coverage_ratio:.2f})"
                    rejection_code = AttributionRejectionCode.LOW_COVERAGE_RATIO.value
                elif max_gap is None or max_gap > self.max_observation_gap_seconds:
                    gap_str = f"{round(max_gap, 7)}s" if max_gap is not None else "unavailable"
                    rejection_reason = f"Maximum gap between observations ({gap_str}) exceeded limit ({self.max_observation_gap_seconds:.3f}s)"
                    rejection_code = AttributionRejectionCode.MAX_OBSERVATION_GAP_EXCEEDED.value
                elif not unique_owner:
                    rejection_reason = "TCP connection lacks unique process owner"
                    rejection_code = AttributionRejectionCode.LACKS_UNIQUE_PROCESS_OWNER.value
                elif not any_controlled:
                    rejection_reason = f"Attributed to non-controlled process ({dominant_alias})"
                    rejection_code = AttributionRejectionCode.NON_CONTROLLED_PROCESS.value
                else:
                    rejection_reason = "Policy requirements not met for HIGH quality evidence"
                    rejection_code = AttributionRejectionCode.POLICY_REQUIREMENTS_NOT_MET.value

        else:  # UDP
            method = AttributionEvidenceMethod.UDP_LOCAL_ENDPOINT_PROCESS_MATCH.value
            quality = (
                AttributionQuality.MEDIUM.value
                if (any_controlled and coverage_ratio >= 0.75 and not is_zero_or_invalid_duration)
                else AttributionQuality.LOW.value
            )
            rejection_reason = "UDP local endpoint match alone is insufficient for VERIFIED promotion"
            rejection_code = AttributionRejectionCode.UDP_LOCAL_ENDPOINT_UNVERIFIED.value

        return AttributionEvidenceRecord(
            flow_id=flow_id,
            evidence_method=method,
            application_alias=dominant_alias,
            matched_observation_count=in_flow_count,
            attribution_coverage_ratio=coverage_ratio,
            unique_owner=unique_owner,
            evidence_quality=quality,
            attribution_rule_version=ATTRIBUTION_RULE_VERSION,
            rejection_reason=rejection_reason,
            rejection_code=rejection_code,
            observed_bins_count=observed_bins,
            expected_bins_count=expected_bins,
            max_observation_gap_seconds=max_gap,
        )
