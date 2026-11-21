"""
Attribution Report Generator and Versioned Sidecar Persistence.

Compiles operator review metrics and serializes privacy-preserving attribution reports
as separate sidecar artifacts without modifying existing immutable labels.csv.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from research.dataset_v3.attribution.schemas import (
    ATTRIBUTION_RULE_VERSION,
    AttributionEvidenceMethod,
    AttributionEvidenceRecord,
    AttributionReport,
    verify_privacy_safe_string,
)

logger = logging.getLogger("research.dataset_v3.attribution.report")


class AttributionReportGenerator:
    """
    Compiles attribution metrics and exports sidecar reports.
    """

    def __init__(self, attribution_rule_version: str = ATTRIBUTION_RULE_VERSION) -> None:
        self.attribution_rule_version = attribution_rule_version

    def generate_report(
        self,
        session_id: str,
        evidence_records: List[AttributionEvidenceRecord],
    ) -> AttributionReport:
        """
        Compiles summary metrics across all flow attribution records.
        """
        total_flows = len(evidence_records)
        unique_matches = 0
        ambiguous_matches = 0
        unmatched = 0
        tcp_count = 0
        udp_count = 0
        coverage_sum = 0.0
        rejection_reasons: Dict[str, int] = {}

        for rec in evidence_records:
            coverage_sum += rec.attribution_coverage_ratio

            method = rec.evidence_method
            if method == AttributionEvidenceMethod.EXACT_TCP_PROCESS_MATCH.value:
                tcp_count += 1
                if rec.unique_owner:
                    unique_matches += 1
                else:
                    ambiguous_matches += 1
            elif method == AttributionEvidenceMethod.UDP_LOCAL_ENDPOINT_PROCESS_MATCH.value:
                udp_count += 1
                if rec.unique_owner:
                    unique_matches += 1
                else:
                    ambiguous_matches += 1
            elif method == AttributionEvidenceMethod.MULTIPLE_PROCESS_MATCH.value:
                ambiguous_matches += 1
            elif method in (
                AttributionEvidenceMethod.PROCESS_NOT_FOUND.value,
                AttributionEvidenceMethod.STALE_SOCKET_OBSERVATION.value,
                AttributionEvidenceMethod.INSUFFICIENT_EVIDENCE.value,
            ):
                unmatched += 1

            if rec.rejection_reason:
                rejection_reasons[rec.rejection_reason] = rejection_reasons.get(rec.rejection_reason, 0) + 1

        mean_coverage = (coverage_sum / float(total_flows)) if total_flows > 0 else 0.0

        return AttributionReport(
            session_id=session_id,
            attribution_rule_version=self.attribution_rule_version,
            total_flows=total_flows,
            unique_process_matches=unique_matches,
            ambiguous_process_matches=ambiguous_matches,
            unmatched_flows=unmatched,
            tcp_evidence_count=tcp_count,
            udp_evidence_count=udp_count,
            mean_attribution_coverage=round(mean_coverage, 4),
            rejection_reasons=rejection_reasons,
            flow_attributions=list(evidence_records),
            created_at_utc=datetime.now(timezone.utc).isoformat(),
        )

    def save_sidecar_report(
        self,
        report: AttributionReport,
        session_dir: Path | str,
        filename: str = "process_attribution_report.json",
    ) -> Path:
        """
        Saves the attribution report as a versioned sidecar artifact in the session directory.

        Guarantees:
        - NEVER overwrites or modifies labels.csv.
        - NEVER overwrites original session manifests.
        - Audits output payload to confirm zero private IP/port/PID leakage.
        """
        s_dir = Path(session_dir)
        if not s_dir.exists():
            s_dir.mkdir(parents=True, exist_ok=True)

        # Audit all records prior to serialization
        for fa in report.flow_attributions:
            verify_privacy_safe_string("application_alias", fa.application_alias)
            verify_privacy_safe_string("rejection_reason", fa.rejection_reason)

        out_path = s_dir / filename
        data = report.to_dict()

        # Serialize to formatted JSON string
        json_str = json.dumps(data, indent=2)

        # Privacy Audit on serialized text
        verify_privacy_safe_string("serialized_report", json_str)

        out_path.write_text(json_str, encoding="utf-8")
        logger.info(
            "Saved process attribution sidecar report: %s (%d flows evaluated)",
            out_path,
            report.total_flows,
        )
        return out_path
