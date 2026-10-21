"""
Deterministic Unit and Regression Tests for Dataset Split Leakage Audit.

Tests all required failure, unverified, and clean isolation cases:
1. Valid, non-overlapping partitions.
2. A session appearing in both train and test.
3. A flow appearing in multiple partitions.
4. A capture appearing in multiple partitions when capture isolation is required.
5. Duplicate membership records within partitions.
6. Incorrect reported partition counts.
7. Missing group identifiers.
8. Missing temporal timestamps when temporal isolation is required.
9. Incorrect chronological ordering (temporal inversion).
10. Missing split artifacts on disk.
11. A valid split under a protocol that does not require capture isolation.
12. An audit that must return UNVERIFIED because evidence is insufficient.
13. Integration: Repository on-disk split artifacts pass audit.
14. Integration: reproduce_research.py stage 4 leakage audit passes cleanly.
"""

from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from training.split_leakage_audit import (
    AuditStatus,
    PartitionAuditResult,
    SplitIsolationStrategy,
    audit_partition_records,
    audit_split_directory,
    audit_all_on_disk_splits,
    audit_experiment_splits,
)


class TestSplitLeakageAudit(unittest.TestCase):
    """Comprehensive test suite for dataset partition membership audit."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # 1. Valid, non-overlapping partitions
    def test_valid_non_overlapping_partitions(self) -> None:
        train = [
            {"flow_id": "f1", "session_id": "s1", "file_id": "cap1", "feature1": 10},
            {"flow_id": "f2", "session_id": "s2", "file_id": "cap2", "feature1": 20},
        ]
        val = [
            {"flow_id": "f3", "session_id": "s3", "file_id": "cap3", "feature1": 30},
        ]
        test = [
            {"flow_id": "f4", "session_id": "s4", "file_id": "cap4", "feature1": 40},
        ]

        res = audit_partition_records(
            artifact_name="test_clean",
            train_records=train,
            val_records=val,
            test_records=test,
            strategy=SplitIsolationStrategy.SESSION_ISOLATED,
        )
        self.assertEqual(res.status, AuditStatus.PASS)
        self.assertTrue(res.is_clean)
        self.assertEqual(len(res.violations), 0)

    # 2. A session appearing in both train and test
    def test_session_appearing_in_both_train_and_test(self) -> None:
        train = [
            {"flow_id": "f1", "session_id": "shared_sess_99", "file_id": "cap1"},
            {"flow_id": "f2", "session_id": "sess_unique_1", "file_id": "cap2"},
        ]
        test = [
            {"flow_id": "f3", "session_id": "shared_sess_99", "file_id": "cap3"},
        ]

        res = audit_partition_records(
            artifact_name="test_session_leak",
            train_records=train,
            test_records=test,
            strategy=SplitIsolationStrategy.SESSION_ISOLATED,
        )
        self.assertEqual(res.status, AuditStatus.FAIL)
        self.assertFalse(res.is_clean)
        self.assertTrue(any("Session leakage" in v and "shared_sess_99" in v for v in res.violations))

    # 3. A flow appearing in multiple partitions
    def test_flow_appearing_in_multiple_partitions(self) -> None:
        train = [
            {"flow_id": "flow_leak_42", "session_id": "s1", "file_id": "cap1"},
        ]
        test = [
            {"flow_id": "flow_leak_42", "session_id": "s2", "file_id": "cap2"},
        ]

        res = audit_partition_records(
            artifact_name="test_flow_leak",
            train_records=train,
            test_records=test,
            strategy=SplitIsolationStrategy.SESSION_ISOLATED,
        )
        self.assertEqual(res.status, AuditStatus.FAIL)
        self.assertTrue(any("Flow leakage" in v and "flow_leak_42" in v for v in res.violations))

    # 4. A capture appearing in multiple partitions when capture isolation is required
    def test_capture_appearing_in_multiple_partitions_when_capture_isolation_required(self) -> None:
        train = [
            {"flow_id": "f1", "file_id": "shared_capture.pcap", "session_id": "s1"},
        ]
        test = [
            {"flow_id": "f2", "file_id": "shared_capture.pcap", "session_id": "s2"},
        ]

        res = audit_partition_records(
            artifact_name="test_capture_leak",
            train_records=train,
            test_records=test,
            strategy=SplitIsolationStrategy.CAPTURE_ISOLATED,
            file_key="file_id",
        )
        self.assertEqual(res.status, AuditStatus.FAIL)
        self.assertTrue(any("Capture leakage" in v and "shared_capture.pcap" in v for v in res.violations))

    # 5. Duplicate membership records
    def test_duplicate_membership_records(self) -> None:
        # Same flow_id twice in train
        train = [
            {"flow_id": "dup_flow", "session_id": "s1", "file_id": "c1"},
            {"flow_id": "dup_flow", "session_id": "s1", "file_id": "c1"},
        ]
        test = [
            {"flow_id": "f2", "session_id": "s2", "file_id": "c2"},
        ]

        res = audit_partition_records(
            artifact_name="test_dups",
            train_records=train,
            test_records=test,
            strategy=SplitIsolationStrategy.SESSION_ISOLATED,
        )
        self.assertEqual(res.status, AuditStatus.FAIL)
        self.assertTrue(any("Duplicate flow_id records within train" in v for v in res.violations))

    # 6. Incorrect reported partition counts
    def test_incorrect_reported_partition_counts(self) -> None:
        train = [{"flow_id": f"f{i}", "session_id": f"s{i}"} for i in range(10)]
        test = [{"flow_id": f"t{i}", "session_id": f"st{i}"} for i in range(5)]

        # Reported count claims 12 train and 5 test
        res = audit_partition_records(
            artifact_name="test_count_mismatch",
            train_records=train,
            test_records=test,
            strategy=SplitIsolationStrategy.SESSION_ISOLATED,
            reported_counts={"train": 12, "test": 5},
        )
        self.assertEqual(res.status, AuditStatus.FAIL)
        self.assertTrue(any("Reported train count mismatch" in v and "expected 12, found 10" in v for v in res.violations))

    # 7. Missing group identifiers
    def test_missing_group_identifiers(self) -> None:
        train = [{"flow_id": "f1", "file_id": "c1"}]
        test = [{"flow_id": "f2", "file_id": "c2"}]

        # Strategy expects session_id, but records lack it
        res = audit_partition_records(
            artifact_name="test_missing_id",
            train_records=train,
            test_records=test,
            strategy=SplitIsolationStrategy.SESSION_ISOLATED,
            group_key="session_id",
        )
        self.assertEqual(res.status, AuditStatus.UNVERIFIED)
        self.assertTrue(any("Group identifier 'session_id' missing" in r for r in res.unverified_reasons))

    # 8. Missing temporal timestamps when temporal isolation is required
    def test_missing_temporal_timestamps_when_temporal_isolation_required(self) -> None:
        train = [{"flow_id": "f1", "session_id": "s1"}]
        test = [{"flow_id": "f2", "session_id": "s2"}]

        res = audit_partition_records(
            artifact_name="test_missing_time",
            train_records=train,
            test_records=test,
            strategy=SplitIsolationStrategy.TEMPORAL_ISOLATED,
            time_key="capture_date",
        )
        self.assertEqual(res.status, AuditStatus.UNVERIFIED)
        self.assertTrue(any("Temporal timestamp/date column 'capture_date' missing" in r for r in res.unverified_reasons))

    # 9. Incorrect chronological ordering (temporal inversion)
    def test_incorrect_chronological_ordering(self) -> None:
        train = [
            {"flow_id": "f1", "capture_date": "2026-08-25"},  # Future date in train!
        ]
        test = [
            {"flow_id": "f2", "capture_date": "2026-08-10"},  # Past date in test!
        ]

        res = audit_partition_records(
            artifact_name="test_temporal_inversion",
            train_records=train,
            test_records=test,
            strategy=SplitIsolationStrategy.TEMPORAL_ISOLATED,
            time_key="capture_date",
        )
        self.assertEqual(res.status, AuditStatus.FAIL)
        self.assertTrue(any("Chronological ordering violation" in v for v in res.violations))

    # 10. Missing split artifacts
    def test_missing_split_artifacts(self) -> None:
        missing_dir = self.temp_path / "nonexistent_splits"
        res = audit_split_directory(
            missing_dir,
            strategy=SplitIsolationStrategy.SESSION_ISOLATED,
        )
        self.assertEqual(res.status, AuditStatus.FAIL)
        self.assertTrue(any("does not exist" in v for v in res.violations))

    # 11. Valid split under a protocol that does not require capture isolation
    def test_valid_split_protocol_not_requiring_capture_isolation(self) -> None:
        # Train and test share a capture file, but have strictly disjoint sessions
        train = [
            {"flow_id": "f1", "session_id": "sess_A", "file_id": "pcap_batch_01.pcap"},
        ]
        test = [
            {"flow_id": "f2", "session_id": "sess_B", "file_id": "pcap_batch_01.pcap"},
        ]

        res = audit_partition_records(
            artifact_name="test_session_split_shared_capture",
            train_records=train,
            test_records=test,
            strategy=SplitIsolationStrategy.SESSION_ISOLATED,
            file_key="file_id",
        )
        # Session isolation passes! (It emits a warning notice about shared capture, but does NOT fail)
        self.assertEqual(res.status, AuditStatus.PASS)
        self.assertEqual(len(res.violations), 0)
        self.assertTrue(any("Partitions share 1 capture file(s), but session isolation is verified" in w for w in res.warnings))

    # 12. Audit that must return UNVERIFIED because evidence is insufficient
    def test_audit_returns_unverified_when_evidence_insufficient(self) -> None:
        train = [{"flow_id": "f1"}]
        test = [{"flow_id": "f2"}]

        res = audit_partition_records(
            artifact_name="test_unverified_evidence",
            train_records=train,
            test_records=test,
            strategy=SplitIsolationStrategy.ENVIRONMENT_ISOLATED,
            group_key="environment_id",
        )
        self.assertEqual(res.status, AuditStatus.UNVERIFIED)
        self.assertTrue(any("Domain identifier 'environment_id' missing" in r for r in res.unverified_reasons))

    # 13. Integration: Repository on-disk split artifacts pass audit
    def test_on_disk_splits_audit_passes(self) -> None:
        results = audit_all_on_disk_splits()
        self.assertGreaterEqual(len(results), 5)
        for r in results:
            self.assertEqual(
                r.status,
                AuditStatus.PASS,
                f"On-disk split {r.artifact_name} failed: {r.violations}",
            )

    # 14. Integration: reproduce_research.py stage 4 leakage audit passes cleanly
    def test_reproduce_research_stage_4_audit_end_to_end(self) -> None:
        from scripts.reproduce_research import ResearchPipelineRunner
        runner = ResearchPipelineRunner(dataset_id="dataset_v2")
        out = runner.stage_4_leakage_audit()

        self.assertEqual(out["status"], "PASS")
        self.assertEqual(out["failed_partitions"], 0)
        self.assertEqual(out["forbidden_features_detected"], 0)
        self.assertGreaterEqual(out["audited_partitions"], 15)
        self.assertTrue(out["isolation_verified"])
        self.assertTrue(Path(out["audit_table"]).exists())


if __name__ == "__main__":
    unittest.main()
