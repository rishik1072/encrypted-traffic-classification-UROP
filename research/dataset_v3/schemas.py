"""
Dataset V3 Data Schemas and Controlled Vocabularies.

Defines strongly-typed dataclasses for packet-level metadata, flow indexes,
session manifests, ground-truth annotations, and validation reports.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

# --- CONTROLLED VOCABULARIES ---

VALID_TRAFFIC_CLASSES: Set[str] = {
    "Web",
    "Video",
    "Messaging",
    "VoIP",
    "File Transfer",
    "Other",
}

VALID_ADAPTER_TYPES: Set[str] = {
    "Wi-Fi",
    "Ethernet",
    "Cellular",
}

VALID_TUNNEL_STATES: Set[str] = {
    "DIRECT",
    "VPN",
    "UNKNOWN",
}

VALID_CAPTURE_STATUSES: Set[str] = {
    "CREATED",
    "CAPTURING",
    "FINALIZING",
    "VALIDATING",
    "COMPLETE",
    "COMPLETED",
    "INTERRUPTED",
    "FAILED",
    "INVALID",
}

VALID_TERMINATION_REASONS: Set[str] = {
    "TCP_FIN",
    "TCP_RST",
    "IDLE_TIMEOUT",
    "ACTIVE_TIMEOUT",
    "CAPTURE_END",
    "UNKNOWN",
}

VALID_LABEL_QUALITIES: Set[str] = {
    "VERIFIED",
    "AMBIGUOUS",
    "UNLABELLED",
    "EXCLUDED",
}

VALID_LABEL_SOURCES: Set[str] = {
    "OPERATOR_CONTROLLED",
    "INDEPENDENT_VERIFICATION",
    "BACKGROUND_UNLABELLED",
    "MANUAL_AUDIT",
    "TEMPORAL_HEURISTIC",
}

VALID_TRANSPORT_PROTOCOLS: Set[str] = {
    "TCP",
    "UDP",
    "OTHER",
}


def _parse_bool(val: Any) -> bool:
    """Robust string-to-bool parser preventing 'False' becoming True."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes")
    return bool(val)


@dataclass(frozen=True)
class PacketMetadataRecord:
    """
    Granular packet-level record preserving chronological sequence for early prefix experimentation.
    Contains ZERO payload bytes, ZERO IP addresses, ZERO MAC addresses, and ZERO ports.

    Packet Length Semantics:
    - captured_link_layer_length_bytes: Length of complete Scapy-delivered frame before user-space truncation.
    - captured_length_bytes: Number of bytes available to metadata parser after user-space truncation.
    - wire_frame_length_bytes: Native pcap_pkthdr.len when genuinely available, otherwise None (UNAVAILABLE).
    - ip_total_length_bytes: Length obtained from IPv4/IPv6 headers when valid.
    - packet_length: Canonical feature length equal to captured_link_layer_length_bytes (production len(pkt) parity).
    """
    session_id: str
    flow_id: str
    parent_flow_id: str
    packet_index: int
    relative_timestamp_us: int
    inter_arrival_time_us: int
    packet_length: int  # Canonical feature length matching production len(pkt)
    direction: int  # 0: first observed direction; 1: reverse direction
    transport_protocol: str  # TCP, UDP, OTHER
    tcp_flags: Optional[int] = None
    captured_length: Optional[int] = None  # Backward-compatible alias for captured_length_bytes
    captured_link_layer_length_bytes: Optional[int] = None  # Complete delivered frame length
    captured_length_bytes: Optional[int] = None  # Bytes in memory after truncation
    wire_frame_length_bytes: Optional[int] = None  # Native pcap_pkthdr.len (None / UNAVAILABLE under standard Scapy)
    ip_total_length_bytes: Optional[int] = None  # Layer 3 IP Total Length from IP header
    is_synthetic: bool = False

    def __post_init__(self) -> None:
        # Canonical packet_length represents captured_link_layer_length_bytes (production len(pkt) parity)
        if self.captured_link_layer_length_bytes is None:
            object.__setattr__(self, "captured_link_layer_length_bytes", self.packet_length)
        if self.captured_length_bytes is None:
            c_len = self.captured_length if self.captured_length is not None else self.captured_link_layer_length_bytes
            object.__setattr__(self, "captured_length_bytes", c_len)
        if self.captured_length is None:
            object.__setattr__(self, "captured_length", self.captured_length_bytes)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PacketMetadataRecord":
        pkt_len = int(data["packet_length"])
        link_len = (
            int(data["captured_link_layer_length_bytes"])
            if data.get("captured_link_layer_length_bytes") is not None
            else pkt_len
        )
        cap_len = int(data.get("captured_length", pkt_len))
        wire_f_len = (
            int(data["wire_frame_length_bytes"])
            if data.get("wire_frame_length_bytes") is not None
            else None
        )
        cap_f_len = (
            int(data["captured_length_bytes"])
            if data.get("captured_length_bytes") is not None
            else cap_len
        )
        ip_tot_len = (
            int(data["ip_total_length_bytes"])
            if data.get("ip_total_length_bytes") is not None
            else None
        )
        return cls(
            session_id=str(data["session_id"]),
            flow_id=str(data["flow_id"]),
            parent_flow_id=str(data["parent_flow_id"]),
            packet_index=int(data["packet_index"]),
            relative_timestamp_us=int(data["relative_timestamp_us"]),
            inter_arrival_time_us=int(data["inter_arrival_time_us"]),
            packet_length=pkt_len,
            captured_link_layer_length_bytes=link_len,
            captured_length_bytes=cap_f_len,
            wire_frame_length_bytes=wire_f_len,
            ip_total_length_bytes=ip_tot_len,
            captured_length=cap_len,
            direction=int(data["direction"]),
            transport_protocol=str(data["transport_protocol"]),
            tcp_flags=int(data["tcp_flags"]) if data.get("tcp_flags") is not None else None,
            is_synthetic=_parse_bool(data.get("is_synthetic", False)),
        )


@dataclass(frozen=True)
class FlowIndexRecord:
    """
    Summary index of an aggregated bidirectional flow within a session.
    """
    session_id: str
    flow_id: str
    parent_flow_id: str
    first_packet_timestamp_utc: str
    last_packet_timestamp_utc: str
    packet_count: int
    duration_us: int
    direction_0_packets: int
    direction_1_packets: int
    direction_0_bytes: int
    direction_1_bytes: int
    transport_protocol: str
    termination_reason: str = "UNKNOWN"
    prefix_3_available: bool = False
    prefix_5_available: bool = False
    prefix_10_available: bool = False
    prefix_20_available: bool = False
    is_synthetic: bool = False

    def __post_init__(self) -> None:
        if not self.prefix_3_available and self.packet_count >= 3:
            object.__setattr__(self, "prefix_3_available", True)
        if not self.prefix_5_available and self.packet_count >= 5:
            object.__setattr__(self, "prefix_5_available", True)
        if not self.prefix_10_available and self.packet_count >= 10:
            object.__setattr__(self, "prefix_10_available", True)
        if not self.prefix_20_available and self.packet_count >= 20:
            object.__setattr__(self, "prefix_20_available", True)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlowIndexRecord":
        pkt_cnt = int(data["packet_count"])
        return cls(
            session_id=str(data["session_id"]),
            flow_id=str(data["flow_id"]),
            parent_flow_id=str(data["parent_flow_id"]),
            first_packet_timestamp_utc=str(data["first_packet_timestamp_utc"]),
            last_packet_timestamp_utc=str(data["last_packet_timestamp_utc"]),
            packet_count=pkt_cnt,
            duration_us=int(data["duration_us"]),
            direction_0_packets=int(data["direction_0_packets"]),
            direction_1_packets=int(data["direction_1_packets"]),
            direction_0_bytes=int(data["direction_0_bytes"]),
            direction_1_bytes=int(data["direction_1_bytes"]),
            transport_protocol=str(data["transport_protocol"]),
            termination_reason=str(data.get("termination_reason", "UNKNOWN")),
            prefix_3_available=_parse_bool(data.get("prefix_3_available", pkt_cnt >= 3)),
            prefix_5_available=_parse_bool(data.get("prefix_5_available", pkt_cnt >= 5)),
            prefix_10_available=_parse_bool(data.get("prefix_10_available", pkt_cnt >= 10)),
            prefix_20_available=_parse_bool(data.get("prefix_20_available", pkt_cnt >= 20)),
            is_synthetic=_parse_bool(data.get("is_synthetic", False)),
        )


@dataclass
class SessionManifest:
    """
    Top-level provenance metadata for a physical capture session.
    Guarantees no hardware identifiers (MACs, SSIDs, public IPs) are stored.
    """
    session_id: str
    collection_start_utc: str
    collection_end_utc: str
    collector_version: str
    operating_system: str
    device_pseudonym: str
    adapter_type: str  # Wi-Fi, Ethernet, Cellular
    environment_id: str
    tunnel_status: str  # DIRECT, VPN, UNKNOWN
    collection_activity: str
    application_alias: str
    intended_traffic_class: str
    collection_operator_label: str
    capture_status: str  # CREATED, CAPTURING, FINALIZING, VALIDATING, COMPLETE, INTERRUPTED, FAILED, INVALID
    collection_plan_id: Optional[str] = None
    packet_count: int = 0
    flow_count: int = 0
    label_quality: str = "VERIFIED"
    collection_day: str = ""
    snaplen: Optional[int] = None
    kernel_buffer_drops: Optional[int] = None
    interface_drops: Optional[int] = None
    queue_drops: int = 0
    parsing_failures: int = 0
    processing_failures: int = 0
    file_integrity_hashes: Dict[str, str] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionManifest":
        return cls(
            session_id=str(data["session_id"]),
            collection_start_utc=str(data["collection_start_utc"]),
            collection_end_utc=str(data["collection_end_utc"]),
            collector_version=str(data["collector_version"]),
            operating_system=str(data["operating_system"]),
            device_pseudonym=str(data["device_pseudonym"]),
            adapter_type=str(data["adapter_type"]),
            environment_id=str(data["environment_id"]),
            tunnel_status=str(data["tunnel_status"]),
            collection_activity=str(data["collection_activity"]),
            application_alias=str(data["application_alias"]),
            intended_traffic_class=str(data["intended_traffic_class"]),
            collection_operator_label=str(data["collection_operator_label"]),
            capture_status=str(data["capture_status"]),
            collection_plan_id=str(data["collection_plan_id"]) if data.get("collection_plan_id") else None,
            packet_count=int(data.get("packet_count", 0)),
            flow_count=int(data.get("flow_count", 0)),
            label_quality=str(data.get("label_quality", "VERIFIED")),
            collection_day=str(data.get("collection_day", "")),
            snaplen=int(data["snaplen"]) if data.get("snaplen") is not None else None,
            kernel_buffer_drops=int(data["kernel_buffer_drops"]) if data.get("kernel_buffer_drops") is not None else None,
            interface_drops=int(data["interface_drops"]) if data.get("interface_drops") is not None else None,
            queue_drops=int(data.get("queue_drops", 0)),
            parsing_failures=int(data.get("parsing_failures", 0)),
            processing_failures=int(data.get("processing_failures", 0)),
            file_integrity_hashes=dict(data.get("file_integrity_hashes", {})),
            notes=str(data.get("notes", "")),
        )


@dataclass(frozen=True)
class LabelRecord:
    """
    Ground-truth label assignment for an individual flow.
    Enforces clear separation between verified application traffic and background noise.

    Label Invariants (Phase 2A.3):
    - VERIFIED: traffic_class contains one of the six validated classes.
    - UNLABELLED: traffic_class = None, label_quality = UNLABELLED.
    - AMBIGUOUS: traffic_class = None, label_quality = AMBIGUOUS.
    - 'Other' is reserved exclusively for flows independently verified to belong to residual traffic.
    - Unlabelled and ambiguous flows must have traffic_class=None to prevent silent training leakage.
    """
    session_id: str
    flow_id: str
    traffic_class: Optional[str]  # None for UNLABELLED and AMBIGUOUS; one of VALID_TRAFFIC_CLASSES for VERIFIED
    application_alias: Optional[str]
    label_source: str  # OPERATOR_CONTROLLED, INDEPENDENT_VERIFICATION, BACKGROUND_UNLABELLED, MANUAL_AUDIT, TEMPORAL_HEURISTIC
    label_quality: str  # VERIFIED, AMBIGUOUS, UNLABELLED, EXCLUDED
    annotator: str
    annotation_timestamp: str
    packet_count: int = 0
    prefix_3_available: bool = False
    prefix_5_available: bool = False
    prefix_10_available: bool = False
    prefix_20_available: bool = False

    def __post_init__(self) -> None:
        if self.traffic_class == "Other" and self.label_quality != "VERIFIED":
            raise ValueError(
                f"'Other' traffic class is reserved exclusively for VERIFIED residual flows (got quality '{self.label_quality}')"
            )
        if self.label_quality == "VERIFIED":
            if self.traffic_class is None:
                raise ValueError("VERIFIED label must specify a valid traffic_class, not None.")
            if self.traffic_class not in VALID_TRAFFIC_CLASSES:
                raise ValueError(f"VERIFIED label has invalid traffic class: '{self.traffic_class}'")
        elif self.label_quality in ("UNLABELLED", "AMBIGUOUS"):
            if self.traffic_class is not None:
                raise ValueError(
                    f"{self.label_quality} flow must have traffic_class=None to prevent silent "
                    f"supervised training contamination. Found: '{self.traffic_class}'"
                )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LabelRecord":
        cnt = int(data.get("packet_count") or 0)
        raw_tc = data.get("traffic_class")
        traffic_class = str(raw_tc) if raw_tc not in (None, "", "None") else None
        raw_app = data.get("application_alias")
        application_alias = str(raw_app) if raw_app not in (None, "", "None") else None
        return cls(
            session_id=str(data["session_id"]),
            flow_id=str(data["flow_id"]),
            traffic_class=traffic_class,
            application_alias=application_alias,
            label_source=str(data["label_source"]),
            label_quality=str(data["label_quality"]),
            annotator=str(data["annotator"]),
            annotation_timestamp=str(data["annotation_timestamp"]),
            packet_count=cnt,
            prefix_3_available=_parse_bool(data.get("prefix_3_available", cnt >= 3)),
            prefix_5_available=_parse_bool(data.get("prefix_5_available", cnt >= 5)),
            prefix_10_available=_parse_bool(data.get("prefix_10_available", cnt >= 10)),
            prefix_20_available=_parse_bool(data.get("prefix_20_available", cnt >= 20)),
        )


@dataclass
class ValidationReport:
    """
    Comprehensive verification report outputted by the Dataset V3 Validator.
    """
    session_id: str
    validator_version: str
    validation_timestamp_utc: str
    is_valid: bool
    total_checks_run: int
    passed_checks: int
    failed_checks: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationReport":
        return cls(
            session_id=str(data["session_id"]),
            validator_version=str(data["validator_version"]),
            validation_timestamp_utc=str(data["validation_timestamp_utc"]),
            is_valid=bool(data["is_valid"]),
            total_checks_run=int(data["total_checks_run"]),
            passed_checks=int(data["passed_checks"]),
            failed_checks=int(data["failed_checks"]),
            errors=list(data.get("errors", [])),
            warnings=list(data.get("warnings", [])),
            metrics=dict(data.get("metrics", {})),
        )
