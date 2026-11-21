"""
Tests for Feature Harmonization and Cross-Dataset Profile Compatibility.
"""

import pytest
import numpy as np

from research.external_datasets.harmonization import (
    FeatureHarmonizer,
    FeatureProfileType,
    PROFILE_SPECS,
)
from research.external_datasets.schemas import ExternalFlowRecord, ExternalPacketItem


def test_profile_specifications_completeness():
    for prof in FeatureProfileType:
        spec = FeatureHarmonizer.get_profile_spec(prof)
        assert spec.profile_type == prof
        assert len(spec.description) > 0
        assert len(spec.packet_length_semantics) > 0
        assert len(spec.feature_keys) > 0


def test_profile_a_and_b_incompatibility():
    # Profile A: Dataset V3 link-layer wire frame length
    # Profile B: CESNET DataZoo transport payload size
    compat, reason = FeatureHarmonizer.check_profile_compatibility(
        FeatureProfileType.PROFILE_A_DATASET_V3,
        FeatureProfileType.PROFILE_B_CESNET_PPI,
    )
    assert compat is False
    assert "Incompatible packet length semantics" in reason
    assert "Never silently convert" in reason


def test_profile_a_and_c_compatibility():
    # Both Profile A and Profile C use link-layer wire frame lengths and include zero-payload packets
    compat, reason = FeatureHarmonizer.check_profile_compatibility(
        FeatureProfileType.PROFILE_A_DATASET_V3,
        FeatureProfileType.PROFILE_C_CIPHER_SPECTRUM,
    )
    assert compat is True
    assert "compatible" in reason.lower()


def test_extract_common_harmonized_features():
    # Create sample flows with diverse packet sizes
    flows = []
    for f_idx, label in enumerate(["video", "web"]):
        packets = []
        for p_idx in range(5):
            packets.append(
                ExternalPacketItem(
                    packet_index=p_idx,
                    direction=0 if p_idx % 2 == 0 else 1,
                    length=200 * (p_idx + 1),  # Packet sizes should NOT appear in common features
                    relative_time_us=p_idx * 1000,
                    inter_arrival_time_us=1000 if p_idx > 0 else 0,
                )
            )
        flows.append(
            ExternalFlowRecord(
                dataset_id="test_ds",
                flow_id=f"flow_{f_idx}",
                source_archive="test.pcap",
                label=label,
                label_category="cat",
                split="train",
                is_known_class=True,
                duration_us=4000,
                total_packets=5,
                total_bytes=sum(p.length for p in packets),
                packets=packets,
            )
        )

    X, y, feature_names = FeatureHarmonizer.extract_common_harmonized_features(flows, k=5)
    assert X.shape[0] == 2
    assert X.shape[1] == len(feature_names)
    assert len(y) == 2

    # Check common feature properties
    assert "k5_fwd_ratio" in feature_names
    assert "k5_direction_transitions" in feature_names
    assert "k5_mean_normalized_iat" in feature_names

    # Crucial Invariant: Absolute packet byte lengths or sums must NOT be in common features
    for col in feature_names:
        assert "byte" not in col.lower()
        assert "frame" not in col.lower()
        assert "payload" not in col.lower()
