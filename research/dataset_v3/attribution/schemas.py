"""
Dataset V3 Process-to-Socket Attribution Schemas.

Defines privacy-preserving evidence records, attribution reports, and controlled
vocabularies for Windows IP Helper socket correlation.
Enforces strict prevention of sensitive data leakage (IPs, ports, PIDs, full paths, URLs).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

ATTRIBUTION_RULE_VERSION = "1.0.0"

# --- PRIVACY AUDIT PATTERNS ---
IPV4_REGEX = re.compile(r"(?<![0-9])(?:\d{1,3}\.){3}\d{1,3}(?![0-9])")
# IPv6: requires either '::' abbreviation or at least 4 colon-separated hex segments (distinguishing from HH:MM:SS timestamps)
IPV6_REGEX = re.compile(
    r"(?<![0-9a-fA-F:])(?:[0-9a-fA-F]{1,4}:){3,7}[0-9a-fA-F]{1,4}(?![0-9a-fA-F:])|"
    r"(?<![0-9a-fA-F:])(?:[0-9a-fA-F]{1,4})?::(?:[0-9a-fA-F]{1,4}:?)*(?![0-9a-fA-F:])"
)
MAC_REGEX = re.compile(r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})(?![0-9A-Fa-f])")
URL_REGEX = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
FILE_PATH_REGEX = re.compile(r"(?:[a-zA-Z]:\\|\b/usr/|\b/home/|\b/etc/|\b/var/|\b/opt/)\S+", re.IGNORECASE)
UNC_PATH_REGEX = re.compile(r"\\\\[a-zA-Z0-9_.-]+\\", re.IGNORECASE)
PID_CANARY_REGEX = re.compile(r"\bpid\s*[:=]\s*\d+|\bpid\s+\d+|[\"']pid[\"']\s*:\s*\d+", re.IGNORECASE)
PORT_CANARY_REGEX = re.compile(r"\bport\s+\d{1,5}\b|(?<!T\d{2})(?<!\d{2}:\d{2})(?<!\s\d{2})(?<![+-]\d{2}):\d{2,5}\b", re.IGNORECASE)
COMMAND_LINE_REGEX = re.compile(r"--[a-zA-Z0-9_-]{2,}", re.IGNORECASE)


class AttributionEvidenceMethod(str, Enum):
    """Controlled evidence classification categories."""
    EXACT_TCP_PROCESS_MATCH = "EXACT_TCP_PROCESS_MATCH"
    UDP_LOCAL_ENDPOINT_PROCESS_MATCH = "UDP_LOCAL_ENDPOINT_PROCESS_MATCH"
    MULTIPLE_PROCESS_MATCH = "MULTIPLE_PROCESS_MATCH"
    PROCESS_NOT_FOUND = "PROCESS_NOT_FOUND"
    STALE_SOCKET_OBSERVATION = "STALE_SOCKET_OBSERVATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


VALID_EVIDENCE_METHODS: Set[str] = {m.value for m in AttributionEvidenceMethod}


class AttributionQuality(str, Enum):
    """Attribution confidence and evidentiary quality rating."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNATTRIBUTED = "UNATTRIBUTED"


VALID_ATTRIBUTION_QUALITIES: Set[str] = {q.value for q in AttributionQuality}


class AttributionRejectionCode(str, Enum):
    """Standardized controlled rejection codes preventing free-form string leakage."""
    NO_CONTEMPORANEOUS_SNAPSHOTS = "NO_CONTEMPORANEOUS_SNAPSHOTS"
    ENDPOINT_NOT_IN_SNAPSHOT = "ENDPOINT_NOT_IN_SNAPSHOT"
    SOCKET_OUTSIDE_FLOW_LIFETIME = "SOCKET_OUTSIDE_FLOW_LIFETIME"
    CONFLICTING_PROCESS_IDENTITIES = "CONFLICTING_PROCESS_IDENTITIES"
    SHARED_UDP_LOCAL_ENDPOINT = "SHARED_UDP_LOCAL_ENDPOINT"
    NON_CONTROLLED_PROCESS = "NON_CONTROLLED_PROCESS"
    UDP_LOCAL_ENDPOINT_UNVERIFIED = "UDP_LOCAL_ENDPOINT_UNVERIFIED"
    LACKS_UNIQUE_PROCESS_OWNER = "LACKS_UNIQUE_PROCESS_OWNER"
    LOW_OBSERVATION_COUNT = "LOW_OBSERVATION_COUNT"
    LOW_COVERAGE_RATIO = "LOW_COVERAGE_RATIO"
    POLICY_REQUIREMENTS_NOT_MET = "POLICY_REQUIREMENTS_NOT_MET"
    OBSERVATION_COUNT_BELOW_MINIMUM = "OBSERVATION_COUNT_BELOW_MINIMUM"
    TRANSITIONAL_STATE_ONLY = "TRANSITIONAL_STATE_ONLY"
    TIME_WAIT_ONLY = "TIME_WAIT_ONLY"
    TEMPORAL_SEPARATION_INSUFFICIENT = "TEMPORAL_SEPARATION_INSUFFICIENT"
    ATTRIBUTION_UNAVAILABLE = "ATTRIBUTION_UNAVAILABLE"
    SINGLE_SNAPSHOT_INSUFFICIENT = "SINGLE_SNAPSHOT_INSUFFICIENT"
    MAX_OBSERVATION_GAP_EXCEEDED = "MAX_OBSERVATION_GAP_EXCEEDED"
    INSUFFICIENT_COVERED_BINS = "INSUFFICIENT_COVERED_BINS"
    ZERO_DURATION_FLOW = "ZERO_DURATION_FLOW"


VALID_REJECTION_CODES: Set[str] = {c.value for c in AttributionRejectionCode}

VALID_APPLICATION_ALIASES: Set[str] = {
    "chrome_controlled",
    "system_background",
    "residual_other",
    "unknown",
}


def verify_privacy_safe_string(field_name: str, value: Optional[str]) -> None:
    """
    Verifies that a string field contains zero sensitive identifying data.
    Audits against IPv4, IPv6, MAC, URL, file paths, UNC paths, PIDs, ports, and command lines.
    """
    if not value:
        return
    if IPV4_REGEX.search(value):
        raise ValueError(f"Privacy violation in '{field_name}': contains raw IPv4 pattern ({value})")
    if IPV6_REGEX.search(value):
        raise ValueError(f"Privacy violation in '{field_name}': contains raw IPv6 pattern ({value})")
    if MAC_REGEX.search(value):
        raise ValueError(f"Privacy violation in '{field_name}': contains MAC address pattern ({value})")
    if URL_REGEX.search(value):
        raise ValueError(f"Privacy violation in '{field_name}': contains URL pattern ({value})")
    if FILE_PATH_REGEX.search(value):
        raise ValueError(f"Privacy violation in '{field_name}': contains full file path ({value})")
    if UNC_PATH_REGEX.search(value):
        raise ValueError(f"Privacy violation in '{field_name}': contains UNC network path ({value})")
    if PID_CANARY_REGEX.search(value):
        raise ValueError(f"Privacy violation in '{field_name}': contains PID reference ({value})")
    if PORT_CANARY_REGEX.search(value):
        raise ValueError(f"Privacy violation in '{field_name}': contains port reference ({value})")
    if COMMAND_LINE_REGEX.search(value):
        raise ValueError(f"Privacy violation in '{field_name}': contains command-line arguments ({value})")


@dataclass(frozen=True)
class AttributionEvidenceRecord:
    """
    Privacy-preserving record of process-to-socket attribution evidence for a flow.

    Guarantees:
    - ZERO source or destination IP addresses.
    - ZERO source or destination ports.
    - ZERO process IDs (PIDs).
    - ZERO process command lines or full paths.
    - ZERO packet payloads, URLs, SNI, or DNS queries.
    """
    flow_id: str
    evidence_method: str
    application_alias: Optional[str]
    matched_observation_count: int
    attribution_coverage_ratio: float
    unique_owner: bool
    evidence_quality: str
    attribution_rule_version: str = ATTRIBUTION_RULE_VERSION
    rejection_reason: Optional[str] = None
    rejection_code: Optional[str] = None
    observed_bins_count: int = 0
    expected_bins_count: int = 0
    max_observation_gap_seconds: Optional[float] = None

    def __post_init__(self) -> None:
        if self.evidence_method not in VALID_EVIDENCE_METHODS:
            raise ValueError(
                f"Invalid evidence_method: '{self.evidence_method}'. Must be one of {VALID_EVIDENCE_METHODS}"
            )
        if self.evidence_quality not in VALID_ATTRIBUTION_QUALITIES:
            raise ValueError(
                f"Invalid evidence_quality: '{self.evidence_quality}'. Must be one of {VALID_ATTRIBUTION_QUALITIES}"
            )
        if not (0.0 <= self.attribution_coverage_ratio <= 1.0):
            raise ValueError(
                f"attribution_coverage_ratio must be between 0.0 and 1.0 (got {self.attribution_coverage_ratio})"
            )
        if self.matched_observation_count < 0:
            raise ValueError(
                f"matched_observation_count cannot be negative (got {self.matched_observation_count})"
            )
        if self.max_observation_gap_seconds is not None and self.max_observation_gap_seconds < 0.0:
            raise ValueError(
                f"max_observation_gap_seconds cannot be negative (got {self.max_observation_gap_seconds})"
            )
        if self.rejection_code is not None and self.rejection_code not in VALID_REJECTION_CODES:
            raise ValueError(
                f"Invalid rejection_code: '{self.rejection_code}'. Must be one of {VALID_REJECTION_CODES}"
            )

        # Enforce privacy constraints on text fields
        verify_privacy_safe_string("application_alias", self.application_alias)
        verify_privacy_safe_string("rejection_reason", self.rejection_reason)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if data.get("max_observation_gap_seconds") is not None:
            data["max_observation_gap_seconds"] = round(data["max_observation_gap_seconds"], 6)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AttributionEvidenceRecord":
        return cls(
            flow_id=str(data["flow_id"]),
            evidence_method=str(data["evidence_method"]),
            application_alias=str(data["application_alias"]) if data.get("application_alias") else None,
            matched_observation_count=int(data["matched_observation_count"]),
            attribution_coverage_ratio=float(data["attribution_coverage_ratio"]),
            unique_owner=bool(data["unique_owner"]),
            evidence_quality=str(data["evidence_quality"]),
            attribution_rule_version=str(data.get("attribution_rule_version", ATTRIBUTION_RULE_VERSION)),
            rejection_reason=str(data["rejection_reason"]) if data.get("rejection_reason") else None,
        )


@dataclass
class AttributionReport:
    """
    Comprehensive operator review report for process-to-socket attribution.
    Persisted as a versioned sidecar artifact alongside Dataset V3 sessions.
    """
    session_id: str
    attribution_rule_version: str
    total_flows: int
    unique_process_matches: int
    ambiguous_process_matches: int
    unmatched_flows: int
    tcp_evidence_count: int
    udp_evidence_count: int
    mean_attribution_coverage: float
    rejection_reasons: Dict[str, int]
    flow_attributions: List[AttributionEvidenceRecord] = field(default_factory=list)
    created_at_utc: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["flow_attributions"] = [fa.to_dict() for fa in self.flow_attributions]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AttributionReport":
        return cls(
            session_id=str(data["session_id"]),
            attribution_rule_version=str(data["attribution_rule_version"]),
            total_flows=int(data["total_flows"]),
            unique_process_matches=int(data["unique_process_matches"]),
            ambiguous_process_matches=int(data["ambiguous_process_matches"]),
            unmatched_flows=int(data["unmatched_flows"]),
            tcp_evidence_count=int(data["tcp_evidence_count"]),
            udp_evidence_count=int(data["udp_evidence_count"]),
            mean_attribution_coverage=float(data["mean_attribution_coverage"]),
            rejection_reasons=dict(data.get("rejection_reasons", {})),
            flow_attributions=[
                AttributionEvidenceRecord.from_dict(fa) for fa in data.get("flow_attributions", [])
            ],
            created_at_utc=str(data.get("created_at_utc", "")),
        )


# --- VOLATILE / IN-MEMORY ONLY STRUCTURES (NEVER PERSISTED TO DISK) ---

@dataclass(frozen=True)
class TransientSocketEntry:
    """
    Volatile in-memory snapshot entry for a single TCP or UDP socket.
    Strictly ephemeral: used only during correlation and wiped immediately.
    """
    protocol: str  # "TCP" or "UDP"
    local_address: str
    local_port: int
    remote_address: Optional[str] = None
    remote_port: Optional[int] = None
    state: Optional[str] = None  # e.g., "ESTABLISHED", "TIME_WAIT", "LISTEN"
    pid: int = 0
    process_create_time_utc: Optional[str] = None
    process_name: Optional[str] = None
    timestamp_utc: float = 0.0
    monotonic_ts: Optional[float] = None


@dataclass(frozen=True)
class TransientProcessIdentity:
    """
    Volatile in-memory process identity resolving PID reuse via creation time.
    """
    pid: int
    create_time_utc: str
    process_name: str
    application_alias: str
    parent_pid: Optional[int] = None
    is_controlled: bool = False


def canonicalize_traffic_class(name: Optional[str]) -> Optional[str]:
    """
    Normalizes application or network activity names to canonical Dataset V3 traffic class.
    Maps aliases ('web_traffic', 'browsing', 'http', 'https') to canonical 'Web'.
    Returns None if input is None.
    """
    if name is None:
        return None
    clean = name.strip()
    mapping = {
        "web": "Web",
        "web_traffic": "Web",
        "browsing": "Web",
        "http": "Web",
        "https": "Web",
        "video": "Video",
        "streaming": "Video",
        "messaging": "Messaging",
        "chat": "Messaging",
        "voip": "VoIP",
        "voice": "VoIP",
        "file transfer": "File Transfer",
        "file_transfer": "File Transfer",
        "download": "File Transfer",
        "other": "Other",
    }
    return mapping.get(clean.lower(), clean)

