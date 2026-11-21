"""
Dataset V3 Windows Process-to-Socket Attribution Subsystem.

Provides privacy-preserving correlation of network flows with operating system
processes via Windows IP Helper APIs, without inspecting payloads, URLs, SNI, or DNS.
"""

from __future__ import annotations

from research.dataset_v3.attribution.chrome_launcher import ControlledChromeLauncher
from research.dataset_v3.attribution.correlator import ProcessSocketCorrelator
from research.dataset_v3.attribution.ip_helper import (
    WindowsIPHelperReader,
    get_process_creation_time_and_name,
    normalize_ip_address,
    normalize_port,
)
from research.dataset_v3.attribution.policy import AttributionEvidencePolicy
from research.dataset_v3.attribution.process_tracker import ProcessTracker
from research.dataset_v3.attribution.report import AttributionReportGenerator
from research.dataset_v3.attribution.schemas import (
    ATTRIBUTION_RULE_VERSION,
    AttributionEvidenceMethod,
    AttributionEvidenceRecord,
    AttributionQuality,
    AttributionReport,
    TransientProcessIdentity,
    TransientSocketEntry,
    verify_privacy_safe_string,
)
from research.dataset_v3.attribution.snapshot_manager import SocketSnapshotManager

__all__ = [
    "ATTRIBUTION_RULE_VERSION",
    "AttributionEvidenceMethod",
    "AttributionEvidenceRecord",
    "AttributionQuality",
    "AttributionReport",
    "TransientSocketEntry",
    "TransientProcessIdentity",
    "verify_privacy_safe_string",
    "normalize_ip_address",
    "normalize_port",
    "get_process_creation_time_and_name",
    "WindowsIPHelperReader",
    "ProcessTracker",
    "SocketSnapshotManager",
    "ProcessSocketCorrelator",
    "AttributionEvidencePolicy",
    "AttributionReportGenerator",
    "ControlledChromeLauncher",
]
