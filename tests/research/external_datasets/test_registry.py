"""
Tests for External Dataset Registry and Metadata Management.
"""

from pathlib import Path
import json
import pytest

from research.external_datasets.registry import (
    _DATASET_REGISTRY,
    get_dataset_metadata,
    list_registered_datasets,
    register_external_dataset,
    export_registry_to_json,
)
from research.external_datasets.schemas import DatasetMetadataRecord, ExtractionStatus


def test_registry_contains_six_core_datasets():
    datasets = list_registered_datasets()
    assert len(datasets) == 6
    expected_ids = {
        "cesnet-tls22",
        "cesnet-quic22",
        "cesnet-tls-year22",
        "cesnet-quicext-25",
        "cipherspectrum",
        "iscxvpn2016",
    }
    registered_ids = {d.dataset_id for d in datasets}
    assert registered_ids == expected_ids


def test_get_dataset_metadata_completeness():
    for dataset_id in ["cesnet-tls22", "cipherspectrum", "iscxvpn2016"]:
        meta = get_dataset_metadata(dataset_id)
        assert meta is not None
        assert isinstance(meta, DatasetMetadataRecord)
        assert meta.dataset_id == dataset_id
        assert len(meta.official_name) > 0
        assert len(meta.publication_reference) > 0
        assert len(meta.license) > 0
        assert len(meta.label_taxonomy) > 0


def test_cesnet_metadata_scale_options():
    meta = get_dataset_metadata("cesnet-tls22")
    assert meta is not None
    assert meta.feature_schema.get("type") == "flow_and_ppi"
    assert "TLS_SNI" in meta.feature_schema.get("forbidden_features", [])


def test_get_invalid_dataset_returns_none():
    meta = get_dataset_metadata("non_existent_dataset_xyz")
    assert meta is None


def test_dynamic_dataset_registration(tmp_path: Path):
    new_record = DatasetMetadataRecord(
        dataset_id="custom-quic-2026",
        official_name="Custom QUIC Benchmark 2026",
        original_source_url="https://example.org/quic-2026",
        download_url="https://example.org/download",
        original_publisher="Test Publisher",
        publication_reference="Author et al., 2026",
        doi="10.1234/test",
        license="CC-BY-4.0",
        collection_period="2026",
        file_format="pcap",
        dataset_version="1.0.0",
        download_checksum="abc123checksum",
        dataset_size_bytes_estimate=1024 * 1024 * 50,
        sample_count_estimate=5000,
        label_taxonomy={"classes": ["Web", "Video", "DNS"]},
        feature_schema={"profile": "PROFILE_C_CIPHER_SPECTRUM"},
        known_limitations=["Synthetically generated in sandbox environment."],
    )

    register_external_dataset(new_record)
    assert any(d.dataset_id == "custom-quic-2026" for d in list_registered_datasets())

    fetched = get_dataset_metadata("custom-quic-2026")
    assert fetched is not None
    assert fetched.official_name == "Custom QUIC Benchmark 2026"

    # Cleanup registry
    del _DATASET_REGISTRY["custom-quic-2026"]


def test_export_registry_to_json(tmp_path: Path):
    out_file = tmp_path / "registry_export.json"
    export_registry_to_json(out_file)
    assert out_file.exists()

    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "cesnet-tls22" in data
    assert "cipherspectrum" in data
    assert data["cesnet-tls22"]["extraction_status"] == ExtractionStatus.NOT_DOWNLOADED.value
