"""
Schemas and Data Models for External Encrypted Traffic Datasets.

Defines:
- Dataset registry metadata records.
- External flow records and packet-prefix sequence models.
- Separate feature profiles (Profile A: Dataset V3, Profile B: CESNET PPI, Profile C: CipherSpectrum).
- External dataset validation report and benchmark evaluation models.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ExtractionStatus(str, Enum):
    NOT_DOWNLOADED = "NOT_DOWNLOADED"
    DOWNLOADED_RAW = "DOWNLOADED_RAW"
    PROCESSED = "PROCESSED"
    VALIDATED = "VALIDATED"
    QUARANTINED = "QUARANTINED"


class FeatureProfileType(str, Enum):
    PROFILE_A_DATASET_V3 = "PROFILE_A_DATASET_V3"  # Captured link-layer frame lengths (Ethernet wire size)
    PROFILE_B_CESNET_PPI = "PROFILE_B_CESNET_PPI"  # Transport payload sizes, directions (+1/-1), IPT
    PROFILE_C_CIPHER_SPECTRUM = "PROFILE_C_CIPHER_SPECTRUM"  # PCAP-reconstructed TLS 1.3 frame sequences
    COMMON_HARMONIZED_SUBSET = "COMMON_HARMONIZED_SUBSET"  # Minimal mathematically justified intersection


@dataclass
class DatasetMetadataRecord:
    """
    Formal metadata record for an external public encrypted traffic dataset.
    All fields are documented strictly from official sources without extrapolation.
    """
    dataset_id: str
    official_name: str
    original_source_url: str
    download_url: str
    original_publisher: str
    publication_reference: str
    doi: Optional[str]
    license: str
    collection_period: str
    file_format: str
    dataset_version: str
    download_checksum: Optional[str]
    extraction_status: ExtractionStatus = ExtractionStatus.NOT_DOWNLOADED
    dataset_size_bytes_estimate: int = 0
    sample_count_estimate: int = 0
    label_taxonomy: Dict[str, Any] = field(default_factory=dict)
    feature_schema: Dict[str, Any] = field(default_factory=dict)
    known_limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["extraction_status"] = self.extraction_status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DatasetMetadataRecord:
        data_copy = dict(data)
        if "extraction_status" in data_copy:
            data_copy["extraction_status"] = ExtractionStatus(data_copy["extraction_status"])
        return cls(**data_copy)


@dataclass
class ExternalPacketItem:
    """A single packet observation in an external flow sequence."""
    packet_index: int
    direction: int  # 0 for forward/client->server, 1 for backward/server->client (or +1/-1 mapped)
    length: int  # Profile-specific packet size (link-layer frame bytes, or transport payload bytes)
    relative_time_us: int  # Microseconds relative to flow start
    inter_arrival_time_us: int  # Microseconds since previous packet


@dataclass
class ExternalFlowRecord:
    """
    Normalized metadata and prefix sequences for an external dataset flow.
    Strictly zero payload bytes are persisted or passed into model features.
    """
    dataset_id: str
    flow_id: str
    source_archive: str
    label: str  # Primary task label
    label_category: Optional[str] = None  # Secondary / family category (e.g., VPN vs Non-VPN, 40-domain, etc.)
    split: str = "train"  # train, val, test, or open_world_unknown
    is_known_class: bool = True
    duration_us: int = 0
    total_packets: int = 0
    total_bytes: int = 0
    packets: List[ExternalPacketItem] = field(default_factory=list)
    auxiliary_metadata: Dict[str, Any] = field(default_factory=dict)

    def extract_prefix(self, k: int) -> List[ExternalPacketItem]:
        """Returns the first K packets of the flow."""
        return self.packets[:k]

    def has_prefix(self, k: int) -> bool:
        """Returns True if the flow contains at least K packets."""
        return len(self.packets) >= k

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "flow_id": self.flow_id,
            "source_archive": self.source_archive,
            "label": self.label,
            "label_category": self.label_category,
            "split": self.split,
            "is_known_class": self.is_known_class,
            "duration_us": self.duration_us,
            "total_packets": self.total_packets,
            "total_bytes": self.total_bytes,
            "packet_count": len(self.packets),
            "auxiliary_metadata": self.auxiliary_metadata,
        }


@dataclass
class ExternalValidationReport:
    """Validation report ensuring integrity and leak-prevention across an external dataset."""
    dataset_id: str
    validator_version: str = "1.0.0"
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_valid: bool = True
    total_flows: int = 0
    total_packets: int = 0
    class_distribution: Dict[str, int] = field(default_factory=dict)
    partition_distribution: Dict[str, int] = field(default_factory=dict)
    prefix_availability: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    leakage_checks: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BenchmarkModelResult:
    """Evaluation metrics for a single model on an external benchmark dataset."""
    model_name: str
    dataset_id: str
    feature_profile: FeatureProfileType
    prefix_k: int
    train_sample_count: int
    test_sample_count: int
    macro_f1: float
    balanced_accuracy: float
    accuracy: float
    brier_score: Optional[float] = None
    expected_calibration_error: Optional[float] = None
    inference_latency_p50_us: float = 0.0
    inference_latency_p95_us: float = 0.0
    inference_latency_p99_us: float = 0.0
    per_class_precision: Dict[str, float] = field(default_factory=dict)
    per_class_recall: Dict[str, float] = field(default_factory=dict)
    per_class_f1: Dict[str, float] = field(default_factory=dict)
    selective_risk_coverage_curve: List[Tuple[float, float, float]] = field(default_factory=list)  # (threshold, coverage, risk)
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["feature_profile"] = self.feature_profile.value
        return d
