"""
Base Adapter Interface for External Encrypted Traffic Datasets.

Defines the contract for ingesting, parsing, prefix extraction, and partitioning
external datasets into normalized ExternalFlowRecords while strictly preserving
privacy, zero-payload constraints, and length semantics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from research.external_datasets.schemas import (
    DatasetMetadataRecord,
    ExternalFlowRecord,
    ExternalValidationReport,
    FeatureProfileType,
)


class BaseExternalAdapter(ABC):
    """
    Abstract Base Class for External Dataset Adapters.
    """

    def __init__(self, dataset_id: str, raw_dir: Path, processed_dir: Path) -> None:
        self.dataset_id = dataset_id.lower().strip()
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def get_feature_profile_type(self) -> FeatureProfileType:
        """Returns the specific feature profile type supported by this adapter."""
        pass

    @abstractmethod
    def ingest(self, source_path: Path, **kwargs: Any) -> int:
        """
        Parses raw external files (e.g. PCAP or Parquet) into normalized ExternalFlowRecords.
        Returns the total number of ingested flows.
        """
        pass

    @abstractmethod
    def extract_prefix_features(
        self,
        k: int,
        flows: Optional[List[ExternalFlowRecord]] = None,
    ) -> Tuple[Any, Any]:
        """
        Extracts feature vectors and labels for early packet prefix horizon K.
        Returns (X, y, feature_names).
        """
        pass

    @abstractmethod
    def get_partitions(
        self,
        temporal: bool = True,
        open_world: bool = False,
        known_ratio: float = 0.8,
    ) -> Dict[str, List[ExternalFlowRecord]]:
        """
        Splits ingested flows into train, val, and test partitions (optionally open-world).
        """
        pass

    @abstractmethod
    def validate(self) -> ExternalValidationReport:
        """Validates the processed dataset for schema compliance, leaks, and integrity."""
        pass
