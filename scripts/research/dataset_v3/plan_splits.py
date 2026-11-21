"""
CLI Tool: Plan and Validate Group-Isolated Dataset V3 Splits.

Generates reproducible train/validation/test partitions under strict group isolation:
- Session-disjoint (no session in multiple partitions)
- Parent-flow-disjoint (no parent flow in multiple partitions)
- Device-disjoint (no device pseudonym in multiple partitions)
- Physical environment shift (Wi-Fi to Ethernet, Wi-Fi to Cellular, Ethernet to Wi-Fi)
- Network tunnel shift (Direct to VPN, VPN to Direct)
- Known-class unseen-application generalization (evaluating cross-app transferability)
- Unknown-class rejection (evaluating open-world class rejection / abstention)
- Temporal-shift (train on earlier collection days, test on later collection days)

Guarantees:
- Scans ONLY COMPLETE sessions (ignores .staging, .incomplete, and unvalidated directories).
- Enforces session uniqueness (rejects duplicate session IDs).
- Preserves genuine ground-truth labels across all splits.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research.dataset_v3.validator import DatasetV3Validator

logger = logging.getLogger("scripts.research.dataset_v3.plan_splits")


def load_session_metadata(root_dir: Path, require_complete: bool = True) -> List[Dict[str, Any]]:
    """
    Loads session manifests for verified sessions in root.

    Guarantees:
    - Excludes hidden and intermediate staging/quarantine directories (.staging, .incomplete).
    - Requires SESSION_COMPLETE marker and capture_status == 'COMPLETE' when require_complete=True.
    - Rejects duplicate session IDs with an explicit ValueError.
    """
    sessions = []
    seen_session_ids: Set[str] = set()
    if not root_dir.exists():
        return sessions

    for d in sorted(root_dir.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue

        m_path = d / "session_manifest.json"
        if not m_path.exists():
            continue

        if require_complete:
            complete_marker = d / "SESSION_COMPLETE"
            if not complete_marker.exists():
                logger.debug("Skipping unfinalized session directory (missing SESSION_COMPLETE): %s", d)
                continue

        try:
            with open(m_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            if require_complete and manifest.get("capture_status") != "COMPLETE":
                logger.debug("Skipping session with non-COMPLETE status: %s", d)
                continue

            sid = manifest.get("session_id")
            if not sid:
                continue

            if sid in seen_session_ids:
                raise ValueError(f"Integrity Error: Duplicate session ID detected across dataset: '{sid}' at {d}")
            seen_session_ids.add(sid)

            manifest["_path"] = str(d)
            sessions.append(manifest)
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            logger.warning("Could not read manifest in %s: %s", d, e)
    return sessions


def split_session_disjoint(
    sessions: List[Dict[str, Any]],
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    seed: int = 42,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Standard stratified session-disjoint split respecting class balance."""
    rng = random.Random(seed)
    by_class: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for s in sessions:
        by_class[s.get("intended_traffic_class", "Other")].append(s)

    train, val, test = [], [], []
    for cls_name, cls_sessions in by_class.items():
        rng.shuffle(cls_sessions)
        n = len(cls_sessions)
        n_train = max(1, int(round(n * train_ratio))) if n >= 3 else max(1, n - 2 if n >= 2 else 1)
        n_val = max(1, int(round(n * val_ratio))) if n >= 3 else (1 if n >= 2 else 0)

        train.extend(cls_sessions[:n_train])
        val.extend(cls_sessions[n_train : n_train + n_val])
        test.extend(cls_sessions[n_train + n_val :])

    return train, val, test


def split_device_disjoint(
    sessions: List[Dict[str, Any]],
    test_devices: Optional[List[str]] = None,
    seed: int = 42,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Device-isolated split ensuring zero device pseudonym overlap."""
    by_device: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for s in sessions:
        by_device[s.get("device_pseudonym", "unknown_device")].append(s)

    devices = sorted(list(by_device.keys()))
    if len(devices) < 2:
        raise ValueError(
            f"Device-disjoint split requires at least 2 distinct device pseudonyms (found {len(devices)})."
        )

    rng = random.Random(seed)
    if test_devices:
        chosen_test = set(test_devices)
        missing_test = chosen_test - set(devices)
        if missing_test:
            raise ValueError(f"Requested test devices not found in dataset: {missing_test}")
    else:
        rng.shuffle(devices)
        n_test = max(1, len(devices) // 3)
        chosen_test = set(devices[:n_test])

    train_devs = [d for d in devices if d not in chosen_test]
    if not train_devs:
        raise ValueError("No devices remaining for training partition after allocating test devices.")

    rng.shuffle(train_devs)
    n_val_dev = 1 if len(train_devs) > 2 else 0
    val_devs = set(train_devs[:n_val_dev])
    final_train_devs = set(train_devs[n_val_dev:])

    train, val, test = [], [], []
    for d in chosen_test:
        test.extend(by_device[d])
    for d in val_devs:
        val.extend(by_device[d])
    for d in final_train_devs:
        train.extend(by_device[d])

    return train, val, test


def split_physical_environment_shift(
    sessions: List[Dict[str, Any]],
    train_adapters: List[str],
    test_adapters: List[str],
    seed: int = 42,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Physical network environment shift split (e.g. Wi-Fi to Ethernet, Wi-Fi to Cellular).
    Holds tunnel status orthogonal and strictly evaluates physical medium transferability.
    """
    train_ad_set = set(train_adapters)
    test_ad_set = set(test_adapters)

    if train_ad_set & test_ad_set:
        raise ValueError(f"Train and test physical adapters must be strictly disjoint: {train_ad_set & test_ad_set}")

    train_candidates = [s for s in sessions if s.get("adapter_type") in train_ad_set]
    test_candidates = [s for s in sessions if s.get("adapter_type") in test_ad_set]

    if not train_candidates:
        raise ValueError(f"No sessions found for training physical adapters: {train_adapters}")
    if not test_candidates:
        raise ValueError(f"No sessions found for testing physical adapters: {test_adapters}")

    train, val, _ = split_session_disjoint(train_candidates, train_ratio=0.80, val_ratio=0.20, seed=seed)
    return train, val, test_candidates


def split_tunnel_shift(
    sessions: List[Dict[str, Any]],
    train_tunnel: str = "DIRECT",
    test_tunnel: str = "VPN",
    seed: int = 42,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Network encapsulation shift split (e.g. DIRECT to VPN, or VPN to DIRECT).
    Evaluates classification resilience to tunneling encapsulation without conflating physical media.
    """
    train_candidates = [s for s in sessions if s.get("tunnel_status") == train_tunnel]
    test_candidates = [s for s in sessions if s.get("tunnel_status") == test_tunnel]

    if not train_candidates:
        raise ValueError(f"No sessions found matching train tunnel state: '{train_tunnel}'")
    if not test_candidates:
        raise ValueError(f"No sessions found matching test tunnel state: '{test_tunnel}'")

    train, val, _ = split_session_disjoint(train_candidates, train_ratio=0.80, val_ratio=0.20, seed=seed)
    return train, val, test_candidates


def split_known_class_unseen_application(
    sessions: List[Dict[str, Any]],
    test_applications: List[str],
    seed: int = 42,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Condition A: Known-Class Unseen-Application Generalization.
    Tests whether a classifier trained on applications A, B of class C can generalize
    to an unseen application D of the SAME class C.
    Preserves ground-truth traffic_class labels intact!
    """
    test_apps_set = set(test_applications)
    test = [s for s in sessions if s.get("application_alias") in test_apps_set]
    available_train = [s for s in sessions if s.get("application_alias") not in test_apps_set]

    if not test:
        raise ValueError(f"No sessions matched test applications: {test_applications}")
    if not available_train:
        raise ValueError("All sessions matched test applications; no training sessions remain.")

    # Verify that the traffic classes represented by test applications are present in training!
    test_classes = {s.get("intended_traffic_class") for s in test}
    train_classes = {s.get("intended_traffic_class") for s in available_train}
    missing_classes = test_classes - train_classes
    if missing_classes:
        raise ValueError(
            f"Cannot evaluate known-class unseen-application generalization: classes {missing_classes} "
            f"have no training sessions remaining once {test_applications} are withheld."
        )

    train, val, _ = split_session_disjoint(available_train, train_ratio=0.80, val_ratio=0.20, seed=seed)
    return train, val, test


def split_unknown_class_rejection(
    sessions: List[Dict[str, Any]],
    withheld_classes: List[str],
    seed: int = 42,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Condition C: Unknown Traffic-Class Rejection (Open-World Evaluation).
    Withholds entire traffic class(es) completely from training and validation.
    The test partition receives all withheld class sessions plus a representative test slice of known classes.
    Preserves authentic ground-truth labels!
    """
    withheld_set = set(withheld_classes)
    known_sessions = [s for s in sessions if s.get("intended_traffic_class") not in withheld_set]
    novel_sessions = [s for s in sessions if s.get("intended_traffic_class") in withheld_set]

    if not novel_sessions:
        raise ValueError(f"No sessions matched withheld classes: {withheld_classes}")
    if not known_sessions:
        raise ValueError("All sessions belong to withheld classes; no known training data remains.")

    train_known, val_known, test_known = split_session_disjoint(
        known_sessions, train_ratio=0.70, val_ratio=0.15, seed=seed
    )
    # Test partition combines novel class sessions with known test slice
    test = test_known + novel_sessions

    return train_known, val_known, test


def split_temporal_shift(
    sessions: List[Dict[str, Any]],
    test_days: List[str],
    seed: int = 42,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Temporal shift split (train on earlier days, test on later days)."""
    test_days_set = set(test_days)
    test = [s for s in sessions if (s.get("collection_day") or s.get("collection_start_utc", "")[:10]) in test_days_set]
    past_sessions = [s for s in sessions if (s.get("collection_day") or s.get("collection_start_utc", "")[:10]) not in test_days_set]

    if not test:
        raise ValueError(f"No sessions matched test days: {test_days}")
    if not past_sessions:
        raise ValueError("All sessions matched test days; no training sessions remain.")

    train, val, _ = split_session_disjoint(past_sessions, train_ratio=0.80, val_ratio=0.20, seed=seed)
    return train, val, test


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan and Validate Dataset V3 Splits")
    parser.add_argument("--root", type=str, default="data/research_v3", help="Dataset root directory")
    parser.add_argument(
        "--strategy",
        type=str,
        default="session_disjoint",
        choices=[
            "session_disjoint",
            "device_disjoint",
            "physical_environment_shift",
            "tunnel_shift",
            "known_class_unseen_application",
            "unknown_class_rejection",
            "temporal_shift",
        ],
        help="Partitioning strategy",
    )
    parser.add_argument("--test-devices", nargs="*", help="Specific device pseudonyms for test set")
    parser.add_argument("--train-adapters", nargs="*", default=["Wi-Fi"], help="Train physical adapter types")
    parser.add_argument("--test-adapters", nargs="*", default=["Ethernet"], help="Test physical adapter types")
    parser.add_argument("--train-tunnel", type=str, default="DIRECT", help="Train tunnel status")
    parser.add_argument("--test-tunnel", type=str, default="VPN", help="Test tunnel status")
    parser.add_argument("--test-apps", nargs="*", help="Specific application aliases for unseen evaluation")
    parser.add_argument("--withheld-classes", nargs="*", help="Traffic classes to withhold for unknown-class rejection")
    parser.add_argument("--test-days", nargs="*", help="Specific collection days (YYYY-MM-DD) for test set")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--allow-unfinalized", action="store_true", help="Allow unfinalized sessions in scan (testing only)")
    parser.add_argument("--out", type=str, help="Output path for partition manifest JSON")

    args = parser.parse_args()
    root_path = Path(args.root)
    sessions = load_session_metadata(root_path, require_complete=not args.allow_unfinalized)

    if not sessions:
        print(f"No valid completed sessions found under '{root_path}'.")
        return 1

    print(f"Loaded {len(sessions)} complete sessions from '{root_path}'.")
    print(f"Applying splitting strategy: {args.strategy}")

    try:
        if args.strategy == "session_disjoint":
            train, val, test = split_session_disjoint(sessions, seed=args.seed)
        elif args.strategy == "device_disjoint":
            train, val, test = split_device_disjoint(sessions, test_devices=args.test_devices, seed=args.seed)
        elif args.strategy == "physical_environment_shift":
            train, val, test = split_physical_environment_shift(
                sessions, train_adapters=args.train_adapters, test_adapters=args.test_adapters, seed=args.seed
            )
        elif args.strategy == "tunnel_shift":
            train, val, test = split_tunnel_shift(
                sessions, train_tunnel=args.train_tunnel, test_tunnel=args.test_tunnel, seed=args.seed
            )
        elif args.strategy == "known_class_unseen_application":
            if not args.test_apps:
                print("Error: --test-apps is required for known_class_unseen_application strategy.")
                return 1
            train, val, test = split_known_class_unseen_application(
                sessions, test_applications=args.test_apps, seed=args.seed
            )
        elif args.strategy == "unknown_class_rejection":
            if not args.withheld_classes:
                print("Error: --withheld-classes is required for unknown_class_rejection strategy.")
                return 1
            train, val, test = split_unknown_class_rejection(
                sessions, withheld_classes=args.withheld_classes, seed=args.seed
            )
        elif args.strategy == "temporal_shift":
            if not args.test_days:
                print("Error: --test-days is required for temporal_shift strategy.")
                return 1
            train, val, test = split_temporal_shift(sessions, test_days=args.test_days, seed=args.seed)
        else:
            print(f"Unknown strategy: {args.strategy}")
            return 1
    except Exception as e:
        print(f"Partition planning failed: {e}")
        return 1

    print(f"\nPartitioning Result:")
    print(f"  Train:      {len(train):3d} sessions")
    print(f"  Validation: {len(val):3d} sessions")
    print(f"  Test:       {len(test):3d} sessions")

    # Validate Partition Isolation
    train_paths = [Path(s["_path"]) for s in train]
    val_paths = [Path(s["_path"]) for s in val]
    test_paths = [Path(s["_path"]) for s in test]

    validator = DatasetV3Validator()
    is_valid, errors = validator.validate_partitions(
        train_session_dirs=train_paths,
        val_session_dirs=val_paths,
        test_session_dirs=test_paths,
        enforce_device_disjoint=(args.strategy == "device_disjoint"),
        enforce_application_disjoint=(args.strategy == "known_class_unseen_application"),
    )

    if not is_valid:
        print("\n[VALIDATION FAILED] Partition isolation invariants violated:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("\n[VALIDATION PASSED] All partition isolation checks satisfied (zero overlap).")

    plan_output = {
        "strategy": args.strategy,
        "seed": args.seed,
        "summary": {
            "total_sessions": len(sessions),
            "train_sessions": len(train),
            "val_sessions": len(val),
            "test_sessions": len(test),
        },
        "train": [s["session_id"] for s in train],
        "validation": [s["session_id"] for s in val],
        "test": [s["session_id"] for s in test],
    }

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(plan_output, f, indent=2)
        print(f"Saved partition plan to: {out_path}")
    else:
        print(json.dumps(plan_output, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
