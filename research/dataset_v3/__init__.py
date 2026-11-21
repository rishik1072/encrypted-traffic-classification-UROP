"""
Dataset V3 Isolated Research Namespace.

Design and implementation of an isolated, privacy-preserving, reproducible
physical network traffic collection system for Dataset V3.

Preserves packet-level metadata for early-prefix experimentation while strictly
enforcing zero-payload privacy, zero IP/MAC/port persistence, and complete
parent-flow provenance tracking.
"""

from __future__ import annotations

__version__ = "3.0.0"

from research.dataset_v3.config import DatasetV3Config
from research.dataset_v3.schemas import (
    FlowIndexRecord,
    LabelRecord,
    PacketMetadataRecord,
    SessionManifest,
    ValidationReport,
)

__all__ = [
    "__version__",
    "DatasetV3Config",
    "PacketMetadataRecord",
    "FlowIndexRecord",
    "SessionManifest",
    "LabelRecord",
    "ValidationReport",
]
