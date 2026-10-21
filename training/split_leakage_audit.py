"""
Authoritative Dataset Split Leakage and Partition Isolation Auditor.

Performs rigorous audit of dataset partition integrity:
- Genuine partition membership isolation (pairwise disjoint intersections)
- Group-aware session isolation
- Capture-file isolation
- Temporal chronological ordering and boundary integrity
- Domain-shift attribute isolation (environment, condition, variant, tunnel)
- Duplicate record and flow identifier detection
- Reported partition count verification
- Explicit UNVERIFIED reporting when evidence is missing or ambiguous

Follows the standards defined in:
- docs/research/DATASET_PROTOCOL.md
- docs/research/EXPERIMENT_INTEGRITY_AUDIT.md
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("split_leakage_audit")


class AuditStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNVERIFIED = "UNVERIFIED"


class SplitIsolationStrategy(str, Enum):
    SESSION_ISOLATED = "session_isolated"
    CAPTURE_ISOLATED = "capture_isolated"
    TEMPORAL_ISOLATED = "temporal_isolated"
    ENVIRONMENT_ISOLATED = "environment_isolated"
    CONDITION_ISOLATED = "condition_isolated"
    ACTIVITY_ISOLATED = "activity_isolated"
    TUNNEL_ISOLATED = "tunnel_isolated"
    FLOW_DISJOINT_ONLY = "flow_disjoint_only"


@dataclass
class PartitionAuditResult:
    """Detailed audit report for a specific split configuration or artifact."""

    artifact_name: str
    strategy: SplitIsolationStrategy
    status: AuditStatus
    train_count: int = 0
    val_count: int = 0
    test_count: int = 0
    reported_counts: Optional[Dict[str, int]] = None
    train_groups_count: int = 0
    val_groups_count: int = 0
    test_groups_count: int = 0
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    unverified_reasons: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_clean(self) -> bool:
        return self.status == AuditStatus.PASS and len(self.violations) == 0


def _parse_date_or_timestamp(val: Any) -> Optional[datetime]:
    """Attempts to parse ISO date, datetime, or unix timestamp."""
    if val is None:
        return None
    val_str = str(val).strip()
    if not val_str:
        return None

    # Check unix timestamp
    try:
        ts_float = float(val_str)
        return datetime.fromtimestamp(ts_float)
    except (ValueError, OverflowError, OSError):
        pass

    # Standard date/datetime formats
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y%m%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(val_str, fmt)
        except ValueError:
            continue

    # Capture day format: day_1, day_2, etc.
    if val_str.startswith("day_"):
        try:
            day_num = int(val_str.split("_")[1])
            return datetime(2026, 1, day_num)
        except (IndexError, ValueError):
            pass

    return None


def audit_partition_records(
    artifact_name: str,
    train_records: List[Dict[str, Any]],
    test_records: List[Dict[str, Any]],
    val_records: Optional[List[Dict[str, Any]]] = None,
    strategy: SplitIsolationStrategy = SplitIsolationStrategy.SESSION_ISOLATED,
    group_key: Optional[str] = None,
    flow_key: str = "flow_id",
    file_key: str = "file_id",
    time_key: str = "capture_date",
    reported_counts: Optional[Dict[str, int]] = None,
) -> PartitionAuditResult:
    """
    Rigorously audits train, validation, and test partition records.

    Enforces:
    1. Positive, non-empty partition records (for train and test).
    2. Exact matching against reported partition counts if provided.
    3. Absence of duplicate flow identifiers within any partition.
    4. Absence of identical duplicate records across partitions.
    5. Zero pairwise flow leakage across all partition boundaries.
    6. Strategy-specific group isolation (session, capture, temporal, environment, etc.).
    7. Explicit UNVERIFIED if required identifiers are absent or ambiguous.
    """
    val_records = val_records or []
    violations: List[str] = []
    warnings: List[str] = []
    unverified_reasons: List[str] = []

    n_train = len(train_records)
    n_val = len(val_records)
    n_test = len(test_records)

    # 1. Basic sanity: Train and Test must have records
    if n_train == 0:
        violations.append(f"[{artifact_name}] Train partition is completely empty (0 records).")
    if n_test == 0:
        violations.append(f"[{artifact_name}] Test partition is completely empty (0 records).")

    # 2. Verify reported partition counts
    if reported_counts:
        if "train" in reported_counts and reported_counts["train"] != n_train:
            violations.append(
                f"[{artifact_name}] Reported train count mismatch: expected {reported_counts['train']}, found {n_train}."
            )
        if "val" in reported_counts and reported_counts["val"] != n_val:
            violations.append(
                f"[{artifact_name}] Reported validation count mismatch: expected {reported_counts['val']}, found {n_val}."
            )
        if "test" in reported_counts and reported_counts["test"] != n_test:
            violations.append(
                f"[{artifact_name}] Reported test count mismatch: expected {reported_counts['test']}, found {n_test}."
            )

    # 3. Check duplicate flow IDs within partitions
    partitions_to_check = [("train", train_records), ("val", val_records), ("test", test_records)]
    for part_name, recs in partitions_to_check:
        if not recs:
            continue
        flow_ids = [r.get(flow_key) for r in recs if r.get(flow_key)]
        if len(flow_ids) != len(set(flow_ids)):
            from collections import Counter
            dups = [k for k, v in Counter(flow_ids).items() if v > 1]
            violations.append(
                f"[{artifact_name}] Duplicate {flow_key} records within {part_name} partition: {len(dups)} duplicate(s) (e.g. {dups[:3]})."
            )

    # 4. Check for exact duplicate records across partitions
    # Hash records based on non-transient features
    def record_signature(r: Dict[str, Any]) -> str:
        # Exclude synthetic partition tags if any
        sig_items = sorted((str(k), str(v)) for k, v in r.items() if k not in ("split", "partition"))
        return str(sig_items)

    tr_sigs = set(record_signature(r) for r in train_records)
    val_sigs = set(record_signature(r) for r in val_records)
    te_sigs = set(record_signature(r) for r in test_records)

    dup_tr_te = tr_sigs & te_sigs
    if dup_tr_te:
        violations.append(
            f"[{artifact_name}] Exact duplicate records found across Train and Test partitions: {len(dup_tr_te)} identical record(s)."
        )
    dup_tr_val = tr_sigs & val_sigs
    if dup_tr_val:
        violations.append(
            f"[{artifact_name}] Exact duplicate records found across Train and Validation partitions: {len(dup_tr_val)} identical record(s)."
        )
    dup_val_te = val_sigs & te_sigs
    if dup_val_te:
        violations.append(
            f"[{artifact_name}] Exact duplicate records found across Validation and Test partitions: {len(dup_val_te)} identical record(s)."
        )

    # 5. Check pairwise Flow ID leakage across partitions
    tr_flows = set(r.get(flow_key) for r in train_records if r.get(flow_key))
    val_flows = set(r.get(flow_key) for r in val_records if r.get(flow_key))
    te_flows = set(r.get(flow_key) for r in test_records if r.get(flow_key))

    overlap_flow_tr_te = tr_flows & te_flows
    if overlap_flow_tr_te:
        violations.append(
            f"[{artifact_name}] Flow leakage: Train and Test share {len(overlap_flow_tr_te)} flow ID(s): {list(overlap_flow_tr_te)[:5]}."
        )
    overlap_flow_tr_val = tr_flows & val_flows
    if overlap_flow_tr_val:
        violations.append(
            f"[{artifact_name}] Flow leakage: Train and Validation share {len(overlap_flow_tr_val)} flow ID(s): {list(overlap_flow_tr_val)[:5]}."
        )
    overlap_flow_val_te = val_flows & te_flows
    if overlap_flow_val_te:
        violations.append(
            f"[{artifact_name}] Flow leakage: Validation and Test share {len(overlap_flow_val_te)} flow ID(s): {list(overlap_flow_val_te)[:5]}."
        )

    # 6. Strategy-specific group isolation verification
    tr_groups: Set[Any] = set()
    val_groups: Set[Any] = set()
    te_groups: Set[Any] = set()

    if strategy == SplitIsolationStrategy.SESSION_ISOLATED:
        target_key = group_key or "session_id"
        # Check presence of group key
        has_train_key = any(target_key in r for r in train_records)
        has_test_key = any(target_key in r for r in test_records)

        if not has_train_key or not has_test_key:
            unverified_reasons.append(
                f"[{artifact_name}] Group identifier '{target_key}' missing from records. Session isolation cannot be verified."
            )
        else:
            tr_groups = set(r.get(target_key) for r in train_records if r.get(target_key))
            val_groups = set(r.get(target_key) for r in val_records if r.get(target_key))
            te_groups = set(r.get(target_key) for r in test_records if r.get(target_key))

            # Intersections
            ov_tr_te = tr_groups & te_groups
            if ov_tr_te:
                violations.append(
                    f"[{artifact_name}] Session leakage: Train and Test share {len(ov_tr_te)} session(s): {list(ov_tr_te)[:5]}."
                )
            ov_tr_val = tr_groups & val_groups
            if ov_tr_val:
                violations.append(
                    f"[{artifact_name}] Session leakage: Train and Validation share {len(ov_tr_val)} session(s): {list(ov_tr_val)[:5]}."
                )
            ov_val_te = val_groups & te_groups
            if ov_val_te:
                violations.append(
                    f"[{artifact_name}] Session leakage: Validation and Test share {len(ov_val_te)} session(s): {list(ov_val_te)[:5]}."
                )

            # Legitimate non-leakage check: repeated capture metadata is permissible under session protocol
            tr_files = set(r.get(file_key) for r in train_records if r.get(file_key))
            te_files = set(r.get(file_key) for r in test_records if r.get(file_key))
            if tr_files and te_files and (tr_files & te_files):
                warnings.append(
                    f"[{artifact_name}] Notice: Partitions share {len(tr_files & te_files)} capture file(s), but session isolation is verified (disjoint sessions confirmed)."
                )

    elif strategy == SplitIsolationStrategy.CAPTURE_ISOLATED:
        target_key = group_key or file_key or "file_id"
        has_train_key = any(target_key in r for r in train_records)
        has_test_key = any(target_key in r for r in test_records)

        if not has_train_key or not has_test_key:
            unverified_reasons.append(
                f"[{artifact_name}] Capture identifier '{target_key}' missing from records. Capture isolation cannot be verified."
            )
        else:
            tr_groups = set(r.get(target_key) for r in train_records if r.get(target_key))
            val_groups = set(r.get(target_key) for r in val_records if r.get(target_key))
            te_groups = set(r.get(target_key) for r in test_records if r.get(target_key))

            ov_tr_te = tr_groups & te_groups
            if ov_tr_te:
                violations.append(
                    f"[{artifact_name}] Capture leakage: Train and Test share {len(ov_tr_te)} capture file(s): {list(ov_tr_te)[:5]}."
                )
            ov_tr_val = tr_groups & val_groups
            if ov_tr_val:
                violations.append(
                    f"[{artifact_name}] Capture leakage: Train and Validation share {len(ov_tr_val)} capture file(s): {list(ov_tr_val)[:5]}."
                )
            ov_val_te = val_groups & te_groups
            if ov_val_te:
                violations.append(
                    f"[{artifact_name}] Capture leakage: Validation and Test share {len(ov_val_te)} capture file(s): {list(ov_val_te)[:5]}."
                )

    elif strategy == SplitIsolationStrategy.TEMPORAL_ISOLATED:
        target_key = group_key or time_key or "capture_date"
        has_train_key = any(target_key in r for r in train_records)
        has_test_key = any(target_key in r for r in test_records)

        if not has_train_key or not has_test_key:
            unverified_reasons.append(
                f"[{artifact_name}] Temporal timestamp/date column '{target_key}' missing. Chronological ordering cannot be verified."
            )
        else:
            # Parse dates
            train_dates = [(_parse_date_or_timestamp(r.get(target_key)), r.get(target_key)) for r in train_records]
            val_dates = [(_parse_date_or_timestamp(r.get(target_key)), r.get(target_key)) for r in val_records]
            test_dates = [(_parse_date_or_timestamp(r.get(target_key)), r.get(target_key)) for r in test_records]

            # Check for unparseable dates
            unparsed_tr = [orig for dt, orig in train_dates if dt is None]
            unparsed_te = [orig for dt, orig in test_dates if dt is None]
            if unparsed_tr or unparsed_te:
                violations.append(
                    f"[{artifact_name}] Malformed or unparseable temporal values detected: {unparsed_tr[:2] + unparsed_te[:2]}."
                )
            else:
                tr_dt_list = [dt for dt, _ in train_dates if dt]
                val_dt_list = [dt for dt, _ in val_dates if dt]
                te_dt_list = [dt for dt, _ in test_dates if dt]

                tr_groups = set(orig for _, orig in train_dates)
                val_groups = set(orig for _, orig in val_dates)
                te_groups = set(orig for _, orig in test_dates)

                max_train_dt = max(tr_dt_list) if tr_dt_list else None
                min_test_dt = min(te_dt_list) if te_dt_list else None

                if max_train_dt and min_test_dt and max_train_dt > min_test_dt:
                    violations.append(
                        f"[{artifact_name}] Chronological ordering violation: Train contains timestamp ({max_train_dt}) occurring after Test timestamp ({min_test_dt})."
                    )

                if val_dt_list:
                    min_val_dt = min(val_dt_list)
                    max_val_dt = max(val_dt_list)
                    if max_train_dt and min_val_dt and max_train_dt > min_val_dt:
                        violations.append(
                            f"[{artifact_name}] Chronological ordering violation: Train contains timestamp ({max_train_dt}) after Validation ({min_val_dt})."
                        )
                    if max_val_dt and min_test_dt and max_val_dt > min_test_dt:
                        violations.append(
                            f"[{artifact_name}] Chronological ordering violation: Validation contains timestamp ({max_val_dt}) after Test ({min_test_dt})."
                        )

    elif strategy in (
        SplitIsolationStrategy.ENVIRONMENT_ISOLATED,
        SplitIsolationStrategy.CONDITION_ISOLATED,
        SplitIsolationStrategy.ACTIVITY_ISOLATED,
        SplitIsolationStrategy.TUNNEL_ISOLATED,
    ):
        domain_key_map = {
            SplitIsolationStrategy.ENVIRONMENT_ISOLATED: "environment_id",
            SplitIsolationStrategy.CONDITION_ISOLATED: "network_condition_id",
            SplitIsolationStrategy.ACTIVITY_ISOLATED: "activity_variant",
            SplitIsolationStrategy.TUNNEL_ISOLATED: "tunnel_state",
        }
        target_key = group_key or domain_key_map[strategy]
        has_train_key = any(target_key in r for r in train_records)
        has_test_key = any(target_key in r for r in test_records)

        if not has_train_key or not has_test_key:
            unverified_reasons.append(
                f"[{artifact_name}] Domain identifier '{target_key}' missing from records. {strategy.value} isolation cannot be verified."
            )
        else:
            tr_groups = set(r.get(target_key) for r in train_records if r.get(target_key))
            val_groups = set(r.get(target_key) for r in val_records if r.get(target_key))
            te_groups = set(r.get(target_key) for r in test_records if r.get(target_key))

            ov_tr_te = tr_groups & te_groups
            if ov_tr_te:
                violations.append(
                    f"[{artifact_name}] {strategy.value} leakage: Train and Test share prohibited domain values: {ov_tr_te}."
                )

    # 7. Final status resolution
    if violations:
        final_status = AuditStatus.FAIL
    elif unverified_reasons:
        final_status = AuditStatus.UNVERIFIED
    else:
        final_status = AuditStatus.PASS

    return PartitionAuditResult(
        artifact_name=artifact_name,
        strategy=strategy,
        status=final_status,
        train_count=n_train,
        val_count=n_val,
        test_count=n_test,
        reported_counts=reported_counts,
        train_groups_count=len(tr_groups),
        val_groups_count=len(val_groups),
        test_groups_count=len(te_groups),
        violations=violations,
        warnings=warnings,
        unverified_reasons=unverified_reasons,
        details={
            "train_groups": list(tr_groups)[:10],
            "test_groups": list(te_groups)[:10],
        },
    )


def audit_split_directory(
    split_dir: Path | str,
    strategy: SplitIsolationStrategy,
    group_key: Optional[str] = None,
    reported_counts: Optional[Dict[str, int]] = None,
) -> PartitionAuditResult:
    """Loads CSV splits from disk directory and audits membership isolation."""
    s_dir = Path(split_dir)
    if not s_dir.exists():
        return PartitionAuditResult(
            artifact_name=str(s_dir),
            strategy=strategy,
            status=AuditStatus.FAIL,
            violations=[f"Split directory does not exist: {s_dir}"],
        )

    tr_path = s_dir / "train.csv"
    val_path = s_dir / "validation.csv"
    te_path = s_dir / "test.csv"

    if not tr_path.exists():
        return PartitionAuditResult(
            artifact_name=str(s_dir),
            strategy=strategy,
            status=AuditStatus.FAIL,
            violations=[f"Missing required train partition file: {tr_path}"],
        )
    if not te_path.exists():
        return PartitionAuditResult(
            artifact_name=str(s_dir),
            strategy=strategy,
            status=AuditStatus.FAIL,
            violations=[f"Missing required test partition file: {te_path}"],
        )

    def read_csv(p: Path) -> List[Dict[str, Any]]:
        with open(p, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    tr_records = read_csv(tr_path)
    val_records = read_csv(val_path) if val_path.exists() else []
    te_records = read_csv(te_path)

    return audit_partition_records(
        artifact_name=str(s_dir.as_posix()),
        train_records=tr_records,
        val_records=val_records,
        test_records=te_records,
        strategy=strategy,
        group_key=group_key,
        reported_counts=reported_counts,
    )


def audit_all_on_disk_splits(project_root: Optional[Path] = None) -> List[PartitionAuditResult]:
    """
    Audits all pre-generated split artifacts located under data/processed/ in the repository.
    """
    root = project_root or Path(__file__).resolve().parent.parent
    results: List[PartitionAuditResult] = []

    # 1. Real Clean (Baseline benchmark splits: 85 train, 24 val, 12 test)
    p_clean = root / "data" / "processed" / "splits" / "real_clean"
    if p_clean.exists():
        results.append(
            audit_split_directory(
                p_clean,
                strategy=SplitIsolationStrategy.SESSION_ISOLATED,
                group_key="session_id",
                reported_counts={"train": 85, "val": 24, "test": 12},
            )
        )

    # 2. Real Raw (128 train, 36 val, 25 test)
    p_real = root / "data" / "processed" / "splits" / "real"
    if p_real.exists():
        results.append(
            audit_split_directory(
                p_real,
                strategy=SplitIsolationStrategy.SESSION_ISOLATED,
                group_key="session_id",
                reported_counts={"train": 128, "val": 36, "test": 25},
            )
        )

    # 3. Session Splits (7 train, 4 test)
    p_sess = root / "data" / "processed" / "splits_session"
    if p_sess.exists():
        results.append(
            audit_split_directory(
                p_sess,
                strategy=SplitIsolationStrategy.SESSION_ISOLATED,
                group_key="session_id",
                reported_counts={"train": 7, "test": 4},
            )
        )

    # 4. Capture Splits (7 train, 4 test)
    p_cap = root / "data" / "processed" / "splits_capture"
    if p_cap.exists():
        results.append(
            audit_split_directory(
                p_cap,
                strategy=SplitIsolationStrategy.CAPTURE_ISOLATED,
                group_key="file_id",
                reported_counts={"train": 7, "test": 4},
            )
        )

    # 5. Temporal Splits (5 train, 2 val, 4 test)
    p_temp = root / "data" / "processed" / "splits_temporal"
    if p_temp.exists():
        results.append(
            audit_split_directory(
                p_temp,
                strategy=SplitIsolationStrategy.TEMPORAL_ISOLATED,
                group_key="capture_date",
                reported_counts={"train": 5, "val": 2, "test": 4},
            )
        )

    return results


def audit_experiment_splits(
    project_root: Optional[Path] = None,
    dataset_id: str = "dataset_v2",
    seed: int = 42,
) -> List[PartitionAuditResult]:
    """
    Audits actual membership partitions generated in-memory during research experiments:
    - EXP-R09 / Baseline group-aware session split (70/15/15)
    - EXP-R11 / Generalization benchmark regimes (REG-01 through REG-08b)
    """
    root = project_root or Path(__file__).resolve().parent.parent
    results: List[PartitionAuditResult] = []

    # 1. Audit Baseline Benchmark Splitter (EXP-R09)
    try:
        from experiments.research_baseline.run import ResearchBaselineExperiment
        base_exp = ResearchBaselineExperiment(seed=seed, config_path=str(root / "config.yaml"))
        records, _ = base_exp.load_and_validate_dataset()
        tr, val, te = base_exp.split_data_group_aware(records)
        res_base = audit_partition_records(
            artifact_name="EXP-R09_baseline_group_split",
            train_records=tr,
            val_records=val,
            test_records=te,
            strategy=SplitIsolationStrategy.SESSION_ISOLATED,
            group_key="session_id",
            reported_counts={"train": 205, "val": 48, "test": 48},
        )
        results.append(res_base)
    except Exception as exc:
        results.append(
            PartitionAuditResult(
                artifact_name="EXP-R09_baseline_group_split",
                strategy=SplitIsolationStrategy.SESSION_ISOLATED,
                status=AuditStatus.FAIL,
                violations=[f"Failed to execute baseline split audit: {exc}"],
            )
        )

    # 2. Audit Generalization Regimes (EXP-R11)
    try:
        from experiments.robustness.research_generalization import ResearchGeneralizationBenchmark
        bench = ResearchGeneralizationBenchmark(seed=seed)
        records = bench.load_dataset()

        # Regime 1: Stratified Session Split
        import random
        from collections import defaultdict
        class_sessions = defaultdict(list)
        session_to_recs = defaultdict(list)
        for r in records:
            s = r["session_id"]
            c = r["traffic_class"]
            session_to_recs[s].append(r)
            if s not in class_sessions[c]:
                class_sessions[c].append(s)

        rng = random.Random(seed)
        tr_s, val_s, te_s = set(), set(), set()
        for c, s_list in sorted(class_sessions.items()):
            shuffled = list(s_list)
            rng.shuffle(shuffled)
            n = len(shuffled)
            n_v = max(1, int(round(n * 0.16)))
            n_t = max(1, int(round(n * 0.16)))
            tr_s.update(shuffled[: n - n_v - n_t])
            val_s.update(shuffled[n - n_v - n_t : n - n_t])
            te_s.update(shuffled[n - n_t :])

        tr1 = [r for s in tr_s for r in session_to_recs[s]]
        val1 = [r for s in val_s for r in session_to_recs[s]]
        te1 = [r for s in te_s for r in session_to_recs[s]]
        results.append(
            audit_partition_records(
                artifact_name="REG-01_random_group_baseline",
                train_records=tr1,
                val_records=val1,
                test_records=te1,
                strategy=SplitIsolationStrategy.SESSION_ISOLATED,
                group_key="session_id",
            )
        )

        # Regime 2: Unseen Capture Split
        file_sessions = defaultdict(list)
        for r in records:
            file_sessions[r["file_id"]].append(r)
        all_files = sorted(list(file_sessions.keys()))
        rng_files = random.Random(seed + 1)
        rng_files.shuffle(all_files)
        n_te_files = int(round(len(all_files) * 0.20))
        te_files = set(all_files[:n_te_files])
        tr_files = set(all_files[n_te_files:])
        tr2 = [r for f in tr_files for r in file_sessions[f]]
        te2 = [r for f in te_files for r in file_sessions[f]]
        results.append(
            audit_partition_records(
                artifact_name="REG-02_unseen_capture",
                train_records=tr2,
                test_records=te2,
                strategy=SplitIsolationStrategy.CAPTURE_ISOLATED,
                group_key="file_id",
            )
        )

        # Regime 3: Unseen Session Split
        all_sessions = sorted(list(session_to_recs.keys()))
        rng_sess = random.Random(seed + 2)
        rng_sess.shuffle(all_sessions)
        n_te_sess = int(round(len(all_sessions) * 0.20))
        te_s_un = set(all_sessions[:n_te_sess])
        tr_s_un = set(all_sessions[n_te_sess:])
        tr3 = [r for s in tr_s_un for r in session_to_recs[s]]
        te3 = [r for s in te_s_un for r in session_to_recs[s]]
        results.append(
            audit_partition_records(
                artifact_name="REG-03_unseen_session",
                train_records=tr3,
                test_records=te3,
                strategy=SplitIsolationStrategy.SESSION_ISOLATED,
                group_key="session_id",
            )
        )

        # Regime 4: Temporal Split
        tr4 = [r for r in records if r["capture_day"] in {"day_1", "day_2", "day_3"}]
        te4 = [r for r in records if r["capture_day"] == "day_4"]
        results.append(
            audit_partition_records(
                artifact_name="REG-04_temporal",
                train_records=tr4,
                test_records=te4,
                strategy=SplitIsolationStrategy.TEMPORAL_ISOLATED,
                group_key="capture_day",
            )
        )

        # Regime 5: Unseen Environment
        tr5 = [r for r in records if r["environment_id"] == "env_win11_wifi"]
        te5 = [r for r in records if r["environment_id"] in {"env_win11_eth", "env_win11_cellular"}]
        results.append(
            audit_partition_records(
                artifact_name="REG-05_unseen_environment",
                train_records=tr5,
                test_records=te5,
                strategy=SplitIsolationStrategy.ENVIRONMENT_ISOLATED,
                group_key="environment_id",
            )
        )

        # Regime 6: Unseen Network Condition
        tr6 = [r for r in records if r["network_condition_id"] == "NORMAL"]
        te6 = [r for r in records if r["network_condition_id"] != "NORMAL"]
        results.append(
            audit_partition_records(
                artifact_name="REG-06_unseen_network_condition",
                train_records=tr6,
                test_records=te6,
                strategy=SplitIsolationStrategy.CONDITION_ISOLATED,
                group_key="network_condition_id",
            )
        )

        # Regime 7: Unseen Activity Variant
        unseen_variants = {
            "ft_sftp_sync",
            "msg_whatsapp_web",
            "oth_telemetry_heartbeat",
            "vid_youtube_1080p",
            "voip_zoom_audio",
            "web_wikipedia",
        }
        tr7 = [r for r in records if r["activity_variant"] not in unseen_variants]
        te7 = [r for r in records if r["activity_variant"] in unseen_variants]
        results.append(
            audit_partition_records(
                artifact_name="REG-07_unseen_activity_variant",
                train_records=tr7,
                test_records=te7,
                strategy=SplitIsolationStrategy.ACTIVITY_ISOLATED,
                group_key="activity_variant",
            )
        )

        # Regime 8a: Tunneled -> Direct
        tr8a = [r for r in records if r["tunnel_state"] == "warp_enabled"]
        te8a = [r for r in records if r["tunnel_state"] == "warp_disabled"]
        results.append(
            audit_partition_records(
                artifact_name="REG-08a_tunnel_tunneled_to_direct",
                train_records=tr8a,
                test_records=te8a,
                strategy=SplitIsolationStrategy.TUNNEL_ISOLATED,
                group_key="tunnel_state",
            )
        )

        # Regime 8b: Direct -> Tunneled
        tr8b = [r for r in records if r["tunnel_state"] == "warp_disabled"]
        te8b = [r for r in records if r["tunnel_state"] == "warp_enabled"]
        results.append(
            audit_partition_records(
                artifact_name="REG-08b_tunnel_direct_to_tunneled",
                train_records=tr8b,
                test_records=te8b,
                strategy=SplitIsolationStrategy.TUNNEL_ISOLATED,
                group_key="tunnel_state",
            )
        )

    except Exception as exc:
        results.append(
            PartitionAuditResult(
                artifact_name="EXP-R11_generalization_regimes",
                strategy=SplitIsolationStrategy.SESSION_ISOLATED,
                status=AuditStatus.FAIL,
                violations=[f"Failed to execute generalization regime audit: {exc}"],
            )
        )

    return results


def save_leakage_audit_table(results: List[PartitionAuditResult], output_path: Path | str) -> None:
    """Saves structured leakage audit table to CSV."""
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "artifact_name",
        "strategy",
        "status",
        "train_samples",
        "val_samples",
        "test_samples",
        "train_groups",
        "val_groups",
        "test_groups",
        "violations_count",
        "violations",
        "unverified_reasons",
    ]

    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "artifact_name": r.artifact_name,
                "strategy": r.strategy.value,
                "status": r.status.value,
                "train_samples": r.train_count,
                "val_samples": r.val_count,
                "test_samples": r.test_count,
                "train_groups": r.train_groups_count,
                "val_groups": r.val_groups_count,
                "test_groups": r.test_groups_count,
                "violations_count": len(r.violations),
                "violations": " | ".join(r.violations) if r.violations else "NONE",
                "unverified_reasons": " | ".join(r.unverified_reasons) if r.unverified_reasons else "NONE",
            })
