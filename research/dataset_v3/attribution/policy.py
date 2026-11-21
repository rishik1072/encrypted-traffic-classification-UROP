"""
Dataset V3 Process Attribution Ground-Truth Evidence Policy.

Enforces strict distinction between operating system process ownership and
scientific traffic-class identity.
Guarantees that flows are never automatically promoted to VERIFIED based solely on
temporal overlap, process name heuristics, or unverified UDP endpoints.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from research.dataset_v3.attribution.schemas import (
    AttributionEvidenceMethod,
    AttributionEvidenceRecord,
    AttributionQuality,
    canonicalize_traffic_class,
)
from research.dataset_v3.schemas import VALID_TRAFFIC_CLASSES, LabelRecord

logger = logging.getLogger("research.dataset_v3.attribution.policy")


class AttributionEvidencePolicy:
    """
    Evaluates attribution evidence records against strict scientific label invariants.
    """

    def __init__(
        self,
        min_tcp_coverage_ratio: float = 0.5,
        min_observation_count: int = 2,
        allow_strict_udp_promotion: bool = False,
    ) -> None:
        self.min_tcp_coverage_ratio = min_tcp_coverage_ratio
        self.min_observation_count = min_observation_count
        self.allow_strict_udp_promotion = allow_strict_udp_promotion

    def evaluate_label_recommendation(
        self,
        evidence: AttributionEvidenceRecord,
        intended_traffic_class: str = "Web",
        controlled_app_alias: str = "chrome_controlled",
    ) -> Tuple[Optional[str], str, str, Optional[str]]:
        """
        Determines the appropriate label recommendation based on attribution evidence.

        Returns:
            (recommended_traffic_class, label_quality, label_source, rejection_reason)

        Label Invariants (Phase 2A.3 & 2B):
        - VERIFIED: traffic_class in VALID_TRAFFIC_CLASSES, quality = 'VERIFIED'.
        - AMBIGUOUS: traffic_class = None, quality = 'AMBIGUOUS'.
        - UNLABELLED: traffic_class = None, quality = 'UNLABELLED'.
        """
        # Rule 1: Insufficient Evidence or Socket Missing
        if evidence.evidence_method in (
            AttributionEvidenceMethod.INSUFFICIENT_EVIDENCE.value,
            AttributionEvidenceMethod.PROCESS_NOT_FOUND.value,
        ):
            return (
                None,
                "AMBIGUOUS",
                "TEMPORAL_HEURISTIC",
                "Flow lacks contemporaneous socket attribution evidence",
            )

        # Rule 2: Stale Socket Observation
        if evidence.evidence_method == AttributionEvidenceMethod.STALE_SOCKET_OBSERVATION.value:
            return (
                None,
                "AMBIGUOUS",
                "TEMPORAL_HEURISTIC",
                "Socket was observed only outside flow lifetime boundaries",
            )

        # Rule 3: Multiple Matching Processes
        if evidence.evidence_method == AttributionEvidenceMethod.MULTIPLE_PROCESS_MATCH.value:
            return (
                None,
                "AMBIGUOUS",
                "TEMPORAL_HEURISTIC",
                "Multiple conflicting or shared process endpoints observed",
            )

        # Rule 4: Background System Traffic
        if evidence.application_alias != controlled_app_alias:
            return (
                None,
                "UNLABELLED",
                "BACKGROUND_UNLABELLED",
                f"Attributed to non-controlled process ({evidence.application_alias})",
            )

        # Rule 5: UDP Local Endpoint Strict Policy
        # UDP local endpoint match does NOT automatically qualify as VERIFIED
        # because local UDP ports may be ephemeral or bound for background services.
        if evidence.evidence_method == AttributionEvidenceMethod.UDP_LOCAL_ENDPOINT_PROCESS_MATCH.value:
            if not self.allow_strict_udp_promotion:
                return (
                    None,
                    "AMBIGUOUS",
                    "TEMPORAL_HEURISTIC",
                    "UDP local endpoint match alone is insufficient for VERIFIED promotion",
                )

        # Rule 6: Controlled TCP Exact Match Verification
        if evidence.evidence_method == AttributionEvidenceMethod.EXACT_TCP_PROCESS_MATCH.value:
            if evidence.evidence_quality != AttributionQuality.HIGH.value:
                return (
                    None,
                    "AMBIGUOUS",
                    "TEMPORAL_HEURISTIC",
                    evidence.rejection_reason or "Evidence quality is insufficient for VERIFIED promotion",
                )
            if not evidence.unique_owner:
                return (
                    None,
                    "AMBIGUOUS",
                    "TEMPORAL_HEURISTIC",
                    "TCP connection lacks unique process owner",
                )
            if evidence.matched_observation_count < self.min_observation_count:
                return (
                    None,
                    "AMBIGUOUS",
                    "TEMPORAL_HEURISTIC",
                    f"Observation count ({evidence.matched_observation_count}) below threshold ({self.min_observation_count})",
                )
            if evidence.attribution_coverage_ratio < self.min_tcp_coverage_ratio:
                return (
                    None,
                    "AMBIGUOUS",
                    "TEMPORAL_HEURISTIC",
                    f"Coverage ratio ({evidence.attribution_coverage_ratio:.2f}) below threshold ({self.min_tcp_coverage_ratio:.2f})",
                )

            # Meets all strict verification criteria
            canonical_class = canonicalize_traffic_class(intended_traffic_class)
            if canonical_class not in VALID_TRAFFIC_CLASSES:
                canonical_class = "Web"

            return (
                canonical_class,
                "VERIFIED",
                "INDEPENDENT_VERIFICATION",
                None,
            )

        # Fallback for unhandled edge cases
        return (
            None,
            "AMBIGUOUS",
            "TEMPORAL_HEURISTIC",
            "Did not meet documented verification policy requirements",
        )
