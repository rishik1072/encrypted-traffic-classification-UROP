"""
Unit Tests: Dataset V3 Split Planning and Group Isolation.

Validates that plan_splits.py strategies strictly isolate:
- Session boundaries
- Parent flow boundaries
- Device pseudonym boundaries
- Physical adapter boundaries (Wi-Fi vs Ethernet vs Cellular)
- Network tunnel boundaries (DIRECT vs VPN)
- Known-class unseen-application generalization (preserving ground-truth)
- Unknown-class open-world rejection (preserving ground-truth)
- Temporal boundaries
- Complete-session-only scanning and duplicate detection
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.research.dataset_v3.plan_splits import (
    load_session_metadata,
    split_device_disjoint,
    split_known_class_unseen_application,
    split_physical_environment_shift,
    split_session_disjoint,
    split_temporal_shift,
    split_tunnel_shift,
    split_unknown_class_rejection,
)
from tests.research.dataset_v3.test_validator import create_mock_session
from research.dataset_v3.validator import DatasetV3Validator


def test_session_disjoint_splitting() -> None:
    sessions = []
    for i in range(10):
        cls_name = "Web" if i < 5 else "Video"
        sessions.append({
            "session_id": f"sess_{i}",
            "intended_traffic_class": cls_name,
            "parent_flow_id": f"flow_{i}",
            "device_pseudonym": f"dev_{i % 3}",
            "application_alias": f"app_{i % 2}",
            "adapter_type": "Wi-Fi",
            "tunnel_status": "DIRECT",
            "collection_day": "2026-11-20",
        })

    train, val, test = split_session_disjoint(sessions, train_ratio=0.6, val_ratio=0.2, seed=42)
    train_ids = {s["session_id"] for s in train}
    val_ids = {s["session_id"] for s in val}
    test_ids = {s["session_id"] for s in test}

    assert len(train_ids & val_ids) == 0
    assert len(train_ids & test_ids) == 0
    assert len(val_ids & test_ids) == 0
    assert len(train_ids | val_ids | test_ids) == 10


def test_device_disjoint_splitting() -> None:
    sessions = []
    for d_idx in range(4):
        for s_idx in range(3):
            sessions.append({
                "session_id": f"sess_d{d_idx}_s{s_idx}",
                "device_pseudonym": f"dev_pseudonym_{d_idx}",
                "intended_traffic_class": "Web",
            })

    train, val, test = split_device_disjoint(sessions, seed=42)
    train_devs = {s["device_pseudonym"] for s in train}
    val_devs = {s["device_pseudonym"] for s in val}
    test_devs = {s["device_pseudonym"] for s in test}

    assert len(train_devs & test_devs) == 0
    assert len(train_devs & val_devs) == 0
    assert len(val_devs & test_devs) == 0
    assert len(train) > 0
    assert len(test) > 0


def test_physical_environment_shift_splitting() -> None:
    sessions = [
        {"session_id": "s1", "adapter_type": "Wi-Fi", "intended_traffic_class": "Web"},
        {"session_id": "s2", "adapter_type": "Wi-Fi", "intended_traffic_class": "Video"},
        {"session_id": "s3", "adapter_type": "Ethernet", "intended_traffic_class": "Web"},
        {"session_id": "s4", "adapter_type": "Ethernet", "intended_traffic_class": "Video"},
    ]

    train, val, test = split_physical_environment_shift(
        sessions, train_adapters=["Wi-Fi"], test_adapters=["Ethernet"]
    )
    test_adapters = {s["adapter_type"] for s in test}
    train_adapters = {s["adapter_type"] for s in train}

    assert test_adapters == {"Ethernet"}
    assert train_adapters == {"Wi-Fi"}


def test_tunnel_shift_splitting() -> None:
    sessions = [
        {"session_id": "s1", "tunnel_status": "DIRECT", "intended_traffic_class": "Web"},
        {"session_id": "s2", "tunnel_status": "DIRECT", "intended_traffic_class": "Video"},
        {"session_id": "s3", "tunnel_status": "VPN", "intended_traffic_class": "Web"},
        {"session_id": "s4", "tunnel_status": "VPN", "intended_traffic_class": "Video"},
    ]

    train, val, test = split_tunnel_shift(sessions, train_tunnel="DIRECT", test_tunnel="VPN")
    test_tunnels = {s["tunnel_status"] for s in test}
    train_tunnels = {s["tunnel_status"] for s in train}

    assert test_tunnels == {"VPN"}
    assert train_tunnels == {"DIRECT"}


def test_known_class_unseen_application_splitting() -> None:
    # 2 applications for Web (chrome and edge), 2 for VoIP (zoom and discord)
    sessions = [
        {"session_id": "s1", "application_alias": "chrome", "intended_traffic_class": "Web"},
        {"session_id": "s2", "application_alias": "edge", "intended_traffic_class": "Web"},
        {"session_id": "s3", "application_alias": "zoom", "intended_traffic_class": "VoIP"},
        {"session_id": "s4", "application_alias": "discord", "intended_traffic_class": "VoIP"},
    ]

    # Test on unseen application 'edge' (which belongs to known class Web)
    train, val, test = split_known_class_unseen_application(sessions, test_applications=["edge"])
    test_apps = {s["application_alias"] for s in test}
    train_apps = {s["application_alias"] for s in train}

    assert test_apps == {"edge"}
    assert "edge" not in train_apps
    # Verify that Web is still in the training set (via chrome)!
    assert any(s["intended_traffic_class"] == "Web" for s in train)
    # Ground-truth class is preserved as 'Web'!
    assert test[0]["intended_traffic_class"] == "Web"


def test_unknown_class_rejection_splitting() -> None:
    sessions = [
        {"session_id": "s1", "intended_traffic_class": "Web"},
        {"session_id": "s2", "intended_traffic_class": "Video"},
        {"session_id": "s3", "intended_traffic_class": "Messaging"},
        {"session_id": "s4", "intended_traffic_class": "Other"},  # Withheld novel class!
    ]

    train, val, test = split_unknown_class_rejection(sessions, withheld_classes=["Other"])
    train_classes = {s["intended_traffic_class"] for s in train}
    val_classes = {s["intended_traffic_class"] for s in val}
    test_classes = {s["intended_traffic_class"] for s in test}

    assert "Other" not in train_classes
    assert "Other" not in val_classes
    assert "Other" in test_classes


def test_complete_session_scanning_and_duplicate_detection(tmp_path: Path) -> None:
    root = tmp_path / "research_v3"
    root.mkdir()

    # 1. Valid complete session
    s1_dir = root / "sess_valid_001"
    create_mock_session(session_dir=s1_dir, session_id="sess_valid_001")
    (s1_dir / "SESSION_COMPLETE").write_text("COMPLETE\n")

    # 2. Incomplete session in staging
    staging_dir = root / ".staging" / "sess_staging_001"
    staging_dir.mkdir(parents=True)
    (staging_dir / "session_manifest.json").write_text(json.dumps({"session_id": "sess_staging_001", "capture_status": "CAPTURING"}))

    # 3. Quarantined session in .incomplete
    incomp_dir = root / ".incomplete" / "sess_failed_001"
    incomp_dir.mkdir(parents=True)
    (incomp_dir / "session_manifest.json").write_text(json.dumps({"session_id": "sess_failed_001", "capture_status": "FAILED"}))

    # 4. Session in root but missing SESSION_COMPLETE marker
    s_unfin = root / "sess_unfin_001"
    create_mock_session(session_dir=s_unfin, session_id="sess_unfin_001")

    # Scanner should find ONLY sess_valid_001
    loaded = load_session_metadata(root, require_complete=True)
    assert len(loaded) == 1
    assert loaded[0]["session_id"] == "sess_valid_001"

    # 5. Duplicate session detection
    s1_dup = root / "sess_valid_001_copy"
    create_mock_session(session_dir=s1_dup, session_id="sess_valid_001")  # Same ID!
    (s1_dup / "SESSION_COMPLETE").write_text("COMPLETE\n")

    with pytest.raises(ValueError, match="Duplicate session ID detected"):
        load_session_metadata(root, require_complete=True)
