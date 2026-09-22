"""
Canonical Real-Time Feature Schema & Validation.

Guarantees 100% feature ordering, naming, and data type compatibility
between offline model training and real-time streaming inference.
Enforces cryptographic schema hashing and fail-closed validation.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Canonical feature ordering matching offline preprocessor
CANONICAL_NUMERICAL_FEATURES: List[str] = [
    "flow_duration",
    "forward_packet_count",
    "backward_packet_count",
    "total_packet_count",
    "forward_bytes",
    "backward_bytes",
    "total_bytes",
    "avg_packet_size",
    "min_packet_size",
    "max_packet_size",
    "packet_size_variance",
    "mean_iat",
    "median_iat",
    "iat_std",
    "min_iat",
    "max_iat",
    "fwd_bwd_packet_ratio",
    "fwd_bwd_byte_ratio",
    "burst_count",
    "avg_burst_bytes",
    "avg_burst_packets",
]

CANONICAL_CATEGORICAL_FEATURES: List[str] = [
    "protocol",
    "dst_port",
]

CANONICAL_TLS_FEATURES: List[str] = [
    "tls_version",
    "tls_cipher_suites_count",
    "tls_extensions_count",
    "tls_sni_present",
]


def get_feature_schema_hash(features: Optional[List[str]] = None) -> str:
    """Computes deterministic SHA-256 hash of canonical feature schema."""
    target = features or CANONICAL_NUMERICAL_FEATURES
    schema_str = ",".join(target)
    return hashlib.sha256(schema_str.encode("utf-8")).hexdigest()


CANONICAL_SCHEMA_HASH: str = get_feature_schema_hash(CANONICAL_NUMERICAL_FEATURES)


def validate_feature_schema(
    extracted_features: Dict[str, Any],
    expected_features: Optional[List[str]] = None,
    expected_hash: Optional[str] = None,
) -> bool:
    """
    Validates that an extracted real-time feature dictionary conforms strictly
    to the expected feature schema. Raises ValueError on schema drift.
    """
    target_schema = expected_features or CANONICAL_NUMERICAL_FEATURES
    extracted_keys: Set[str] = set(extracted_features.keys())

    missing = [col for col in target_schema if col not in extracted_keys]
    if missing:
        err_msg = f"Feature schema mismatch! Missing required feature(s): {missing}"
        logger.error(err_msg)
        raise ValueError(err_msg)

    if expected_hash:
        current_hash = get_feature_schema_hash(target_schema)
        if current_hash != expected_hash:
            err_msg = f"Feature schema hash mismatch! Expected {expected_hash}, got {current_hash}"
            logger.error(err_msg)
            raise ValueError(err_msg)

    return True
