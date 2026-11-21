"""
Feature Harmonization Module for Multi-Dataset Benchmarking.

Formulates and validates:
- PROFILE A: Dataset V3 link-layer wire frame lengths and physical timing.
- PROFILE B: CESNET DataZoo PPI transport-payload sizes, direction, and IPTs.
- PROFILE C: PCAP-reconstructed CipherSpectrum TLS 1.3 frame sequences.
- COMMON HARMONIZED SUBSET: Minimal mathematically justified common features.

Enforces:
- NEVER silently convert transport payload size into Ethernet frame length.
- Strictly prohibits adding hardcoded header estimates (e.g., +54 bytes).
- Preserves explicit provenance of length semantics across external models.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from research.external_datasets.schemas import (
    ExternalFlowRecord,
    FeatureProfileType,
)

logger = logging.getLogger("research.external_datasets.harmonization")


@dataclass
class ProfileSpecification:
    profile_type: FeatureProfileType
    description: str
    packet_length_semantics: str
    base_semantic: str
    excludes_zero_payload_packets: bool
    timing_semantics: str
    feature_keys: List[str]


PROFILE_SPECS: Dict[FeatureProfileType, ProfileSpecification] = {
    FeatureProfileType.PROFILE_A_DATASET_V3: ProfileSpecification(
        profile_type=FeatureProfileType.PROFILE_A_DATASET_V3,
        description="Dataset V3 physical capture features using link-layer wire frame lengths.",
        packet_length_semantics="Link-layer wire frame length (Ethernet II header + IP + L4 + payload)",
        base_semantic="wire_frame_length",
        excludes_zero_payload_packets=False,
        timing_semantics="Monotonic hardware arrival timestamps (microsecond resolution)",
        feature_keys=[
            "packet_length",
            "captured_link_layer_length_bytes",
            "direction",
            "relative_timestamp_us",
            "inter_arrival_time_us",
        ],
    ),
    FeatureProfileType.PROFILE_B_CESNET_PPI: ProfileSpecification(
        profile_type=FeatureProfileType.PROFILE_B_CESNET_PPI,
        description="CESNET DataZoo PPI features using transport payload sizes.",
        packet_length_semantics="Transport-layer payload size (excludes TCP/UDP/IP/Ethernet headers)",
        base_semantic="transport_payload",
        excludes_zero_payload_packets=True,
        timing_semantics="Inter-packet arrival times (seconds/milliseconds normalized to microseconds)",
        feature_keys=[
            "ppi_size",
            "ppi_dir",
            "ppi_ipt",
        ],
    ),
    FeatureProfileType.PROFILE_C_CIPHER_SPECTRUM: ProfileSpecification(
        profile_type=FeatureProfileType.PROFILE_C_CIPHER_SPECTRUM,
        description="CipherSpectrum PCAP-derived packet metadata.",
        packet_length_semantics="Link-layer wire frame length parsed from PCAP headers (zero payload retained)",
        base_semantic="wire_frame_length",
        excludes_zero_payload_packets=False,
        timing_semantics="PCAP arrival timestamps relative to flow start (microseconds)",
        feature_keys=[
            "frame_length",
            "direction",
            "relative_time_us",
            "inter_arrival_time_us",
        ],
    ),
    FeatureProfileType.COMMON_HARMONIZED_SUBSET: ProfileSpecification(
        profile_type=FeatureProfileType.COMMON_HARMONIZED_SUBSET,
        description="Minimal mathematically justified common feature subset.",
        packet_length_semantics="Dimensionless / sequence-normalized direction and inter-arrival timing patterns",
        base_semantic="dimensionless",
        excludes_zero_payload_packets=False,
        timing_semantics="Normalized inter-arrival time fractions",
        feature_keys=[
            "prefix_k_packets",
            "direction_sequence",
            "normalized_iat_sequence",
            "direction_transition_count",
            "forward_packet_ratio",
        ],
    ),
}


class FeatureHarmonizer:
    """
    Manages feature profile validation, extraction, and safe common subset generation.
    """

    @classmethod
    def get_profile_spec(cls, profile: FeatureProfileType) -> ProfileSpecification:
        return PROFILE_SPECS[profile]

    @classmethod
    def check_profile_compatibility(
        cls, profile_a: FeatureProfileType, profile_b: FeatureProfileType
    ) -> Tuple[bool, str]:
        """
        Validates whether two feature profiles can be directly compared without conversion error.
        """
        if profile_a == profile_b:
            return True, "Profiles are identical."

        spec_a = PROFILE_SPECS[profile_a]
        spec_b = PROFILE_SPECS[profile_b]

        if spec_a.base_semantic != spec_b.base_semantic:
            return (
                False,
                f"Incompatible packet length semantics: '{profile_a.value}' uses "
                f"'{spec_a.packet_length_semantics}', whereas '{profile_b.value}' uses "
                f"'{spec_b.packet_length_semantics}'. Never silently convert or equate these features.",
            )

        if spec_a.excludes_zero_payload_packets != spec_b.excludes_zero_payload_packets:
            return (
                False,
                f"Incompatible packet inclusion: '{profile_a.value}' excludes zero-payload "
                f"packets={spec_a.excludes_zero_payload_packets}, whereas '{profile_b.value}' "
                f"excludes zero-payload packets={spec_b.excludes_zero_payload_packets}.",
            )

        return True, "Profiles are compatible."

    @classmethod
    def extract_common_harmonized_features(
        cls, flows: List[ExternalFlowRecord], k: int
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Extracts ONLY the mathematically justified common feature subset across heterogeneous datasets:
        1. Directional sequence (0 = client->server, 1 = server->client).
        2. Normalized inter-arrival times (IAT_i / sum(IAT)).
        3. Forward packet ratio (count(fwd) / K).
        4. Direction transitions (count of direction changes).
        5. Total duration in microseconds.

        Strict invariant: Does NOT include absolute packet sizes when cross-evaluating
        Profile A (frame lengths) against Profile B (transport payload bytes).
        """
        feature_names = [
            f"k{k}_fwd_ratio",
            f"k{k}_direction_transitions",
            f"k{k}_mean_normalized_iat",
            f"k{k}_std_normalized_iat",
            f"k{k}_duration_us",
        ]
        # Add per-packet directional indicator features up to K
        for i in range(k):
            feature_names.append(f"k{k}_pkt_{i}_dir")

        X_rows: List[List[float]] = []
        y_labels: List[str] = []

        for fl in flows:
            prefix = fl.extract_prefix(k)
            if len(prefix) < k:
                continue

            dirs = [p.direction for p in prefix]
            iats = [float(p.inter_arrival_time_us) for p in prefix]
            tot_iat = sum(iats)

            fwd_ratio = float(sum(1 for d in dirs if d == 0)) / float(k)
            dir_transitions = float(sum(1 for i in range(len(dirs) - 1) if dirs[i] != dirs[i + 1]))

            norm_iats = [(t / tot_iat) if tot_iat > 0 else 0.0 for t in iats]
            mean_norm_iat = float(np.mean(norm_iats)) if norm_iats else 0.0
            std_norm_iat = float(np.std(norm_iats)) if len(norm_iats) > 1 else 0.0
            dur_us = float(prefix[-1].relative_time_us) if prefix else 0.0

            row = [
                fwd_ratio,
                dir_transitions,
                mean_norm_iat,
                std_norm_iat,
                dur_us,
            ]
            # Add directions (pad with -1.0 if prefix < k)
            for i in range(k):
                row.append(float(dirs[i]) if i < len(dirs) else -1.0)

            X_rows.append(row)
            y_labels.append(fl.label)

        X = np.array(X_rows, dtype=np.float32) if X_rows else np.empty((0, len(feature_names)), dtype=np.float32)
        y = np.array(y_labels, dtype=object) if y_labels else np.empty((0,), dtype=object)
        return X, y, feature_names
