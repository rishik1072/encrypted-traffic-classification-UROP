"""
Tests for CESNET DataZoo Adapter.
"""

from pathlib import Path
import json
import gzip
import pytest
import numpy as np

from research.external_datasets.adapters.cesnet import CesnetAdapter
from research.external_datasets.schemas import FeatureProfileType


@pytest.fixture
def synthetic_cesnet_jsonl(tmp_path: Path) -> Path:
    """Creates a temporary synthetic CESNET JSONL fixture."""
    data = [
        {
            "FLOW_ID": "flow_001",
            "APP": "web",
            "CATEGORY": "browsing",
            "COLLECTION_PERIOD": "W-2022-44",
            "DIR": [0, 1, 0, 1, 0, 0, 1],
            "IPT": [0.0, 0.005, 0.012, 0.003, 0.040, 0.001, 0.015],
            "SIZE": [250, 1420, 120, 1420, 310, 45, 800],
            "TLS_SNI": "forbidden-leakage.example.org",  # Should be purged
            "DST_IP": "192.0.2.1",                      # Should be purged
        },
        {
            "FLOW_ID": "flow_002",
            "APP": "video",
            "CATEGORY": "streaming",
            "COLLECTION_PERIOD": "W-2022-44",
            "DIR": [0, 1, 1, 1, 0],
            "IPT": [0.0, 0.002, 0.001, 0.001, 0.030],
            "SIZE": [180, 1440, 1440, 1440, 60],
            "USER_AGENT": "Mozilla/5.0 Leak",          # Should be purged
        },
        {
            "FLOW_ID": "flow_003",
            "APP": "dns",
            "CATEGORY": "system",
            "COLLECTION_PERIOD": "W-2022-45",
            "DIR": [0, 1],
            "IPT": [0.0, 0.015],
            "SIZE": [85, 210],
        },
    ]

    p = tmp_path / "cesnet_sample.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")
    return p


def test_cesnet_adapter_ingestion_and_shortcut_purging(tmp_path: Path, synthetic_cesnet_jsonl: Path):
    adapter = CesnetAdapter(
        dataset_id="cesnet-tls22",
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
        size="XS",
    )

    count = adapter.ingest(synthetic_cesnet_jsonl)
    assert count == 3
    assert len(adapter.flows) == 3

    # Verify Profile Type
    assert adapter.get_feature_profile_type() == FeatureProfileType.PROFILE_B_CESNET_PPI

    # Verify shortcut fields were purged from metadata
    for flow in adapter.flows:
        assert "TLS_SNI" not in flow.auxiliary_metadata
        assert "DST_IP" not in flow.auxiliary_metadata
        assert "USER_AGENT" not in flow.auxiliary_metadata
        # Check payload size semantics
        assert flow.auxiliary_metadata.get("length_semantics") == "Transport-layer payload size (bytes)"


def test_cesnet_prefix_feature_extraction(tmp_path: Path, synthetic_cesnet_jsonl: Path):
    adapter = CesnetAdapter(
        dataset_id="cesnet-tls22",
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
    )
    adapter.ingest(synthetic_cesnet_jsonl)

    for k in (3, 5):
        X, y, feature_names = adapter.extract_prefix_features(k=k)
        assert X.shape[0] == 3  # All 3 flows have at least 2 packets
        assert X.shape[1] == len(feature_names)
        assert len(y) == 3
        assert f"k{k}_fwd_payload_bytes" in feature_names
        assert f"k{k}_bwd_payload_bytes" in feature_names


def test_cesnet_temporal_and_open_world_partitioning(tmp_path: Path, synthetic_cesnet_jsonl: Path):
    adapter = CesnetAdapter(
        dataset_id="cesnet-tls22",
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
    )
    adapter.ingest(synthetic_cesnet_jsonl)

    # Standard split
    parts = adapter.get_partitions(temporal=True, open_world=False)
    assert "train" in parts
    assert "val" in parts
    assert "test" in parts

    # Open-world split
    ow_parts = adapter.get_partitions(temporal=False, open_world=True, known_ratio=0.5)
    test_flows = ow_parts["test"]
    unknown_flows = [f for f in test_flows if not f.is_known_class]
    assert len(unknown_flows) >= 1


def test_cesnet_validation_report(tmp_path: Path, synthetic_cesnet_jsonl: Path):
    adapter = CesnetAdapter(
        dataset_id="cesnet-tls22",
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
    )
    adapter.ingest(synthetic_cesnet_jsonl)

    report = adapter.validate()
    assert report.total_flows == 3
    assert report.leakage_checks.get("zero_payload_persistence") is True
    assert report.leakage_checks.get("no_sni_leak") is True
    assert "prefix_3" in report.prefix_availability
