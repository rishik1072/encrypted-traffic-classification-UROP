"""
Tests for External Dataset Scientific Validator.
"""

import pytest
from research.external_datasets.validator import ExternalDatasetValidator
from research.external_datasets.schemas import ExternalFlowRecord, ExternalPacketItem


def make_sample_flow(flow_id: str, label: str, duration_us: int = 1000, num_pkts: int = 5) -> ExternalFlowRecord:
    packets = []
    for i in range(num_pkts):
        packets.append(
            ExternalPacketItem(
                packet_index=i,
                direction=i % 2,
                length=100 + i * 50,
                relative_time_us=i * 200,
                inter_arrival_time_us=200 if i > 0 else 0,
            )
        )
    return ExternalFlowRecord(
        dataset_id="test_ds",
        flow_id=flow_id,
        source_archive="archive.pcap",
        label=label,
        label_category="test_cat",
        split="train",
        is_known_class=True,
        duration_us=duration_us,
        total_packets=num_pkts,
        total_bytes=sum(p.length for p in packets),
        packets=packets,
    )


def test_validator_valid_dataset():
    validator = ExternalDatasetValidator(dataset_id="test_ds")
    flows = [
        make_sample_flow("f1", "class_A"),
        make_sample_flow("f2", "class_B"),
        make_sample_flow("f3", "class_A"),
        make_sample_flow("f4", "class_B"),
    ]
    partitions = {
        "train": [flows[0], flows[1]],
        "val": [flows[2]],
        "test": [flows[3]],
    }
    report = validator.validate_dataset(flows, partitions)
    assert report.is_valid is True
    assert len(report.errors) == 0
    assert report.total_flows == 4
    assert report.total_packets == 20
    assert report.leakage_checks["cross_partition_disjoint"] is True


def test_validator_duplicate_flow_ids():
    validator = ExternalDatasetValidator(dataset_id="test_ds")
    flows = [
        make_sample_flow("f1", "class_A"),
        make_sample_flow("f1", "class_A"),  # Duplicate
    ]
    report = validator.validate_dataset(flows)
    assert report.is_valid is False
    assert any("Duplicate flow IDs" in err for err in report.errors)


def test_validator_missing_label():
    validator = ExternalDatasetValidator(dataset_id="test_ds")
    f_missing = make_sample_flow("f1", "")
    report = validator.validate_dataset([f_missing])
    assert report.is_valid is False
    assert any("missing or empty" in err for err in report.errors)


def test_validator_non_monotonic_timing():
    validator = ExternalDatasetValidator(dataset_id="test_ds")
    flow = make_sample_flow("f1", "class_A")
    # Invert timestamps on last packet
    flow.packets[-1].relative_time_us = 50  # Less than preceding 600
    report = validator.validate_dataset([flow])
    assert report.is_valid is False
    assert any("monotonic" in err.lower() or "ordering" in err.lower() for err in report.errors)


def test_validator_negative_packet_length():
    validator = ExternalDatasetValidator(dataset_id="test_ds")
    flow = make_sample_flow("f1", "class_A")
    flow.packets[0].length = -50
    report = validator.validate_dataset([flow])
    assert report.is_valid is False
    assert any("negative packet lengths" in err for err in report.errors)


def test_validator_partition_overlap():
    validator = ExternalDatasetValidator(dataset_id="test_ds")
    f1 = make_sample_flow("f1", "class_A")
    f2 = make_sample_flow("f2", "class_B")
    flows = [f1, f2]
    # f1 appears in both train and test
    partitions = {
        "train": [f1, f2],
        "val": [],
        "test": [f1],
    }
    report = validator.validate_dataset(flows, partitions)
    assert report.is_valid is False
    assert any("Cross-partition flow overlap" in err for err in report.errors)


def test_validator_open_world_leakage_in_train():
    validator = ExternalDatasetValidator(dataset_id="test_ds")
    f_known = make_sample_flow("f1", "known_class")
    f_unknown = make_sample_flow("f2", "unknown_class")
    f_unknown.is_known_class = False

    partitions = {
        "train": [f_known, f_unknown],  # Leaked!
        "val": [],
        "test": [],
    }
    report = validator.validate_dataset([f_known, f_unknown], partitions)
    assert report.is_valid is False
    assert any("Open-world unknown class flows leaked into train" in err for err in report.errors)
