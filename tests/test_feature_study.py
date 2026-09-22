"""
Unit and Integration Tests for Zero-Payload Feature Study and Registry.

Verifies canonical feature definitions, family assignments, zero-payload validation guards,
experimental result table schemas, and generated figure artifacts.
"""

from __future__ import annotations

import csv
from pathlib import Path
import pytest

from preprocessing.feature_registry import (
    FeatureDefinition,
    FeatureFamily,
    FeatureRegistry,
    canonical_feature_registry,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_feature_registry_total_count():
    """Verifies that all 84 rich statistical features are registered."""
    all_feats = canonical_feature_registry.list_all_features()
    assert len(all_feats) == 84
    assert len(set(all_feats)) == 84  # Unique names


def test_feature_registry_family_breakdown():
    """Verifies counts for each of the 7 explicit feature families."""
    counts = canonical_feature_registry.get_family_breakdown()
    assert counts[FeatureFamily.PACKET_SIZE.value] == 30
    assert counts[FeatureFamily.TIMING.value] == 30
    assert counts[FeatureFamily.PACKET_COUNTS.value] == 7
    assert counts[FeatureFamily.BYTE_COUNTS.value] == 5
    assert counts[FeatureFamily.DIRECTIONALITY.value] == 3
    assert counts[FeatureFamily.BURST.value] == 8
    assert counts[FeatureFamily.FLOW_DURATION.value] == 1


def test_feature_registry_zero_payload_enforcement():
    """Verifies that zero-payload check passes for all features."""
    assert canonical_feature_registry.verify_zero_payload() is True


def test_feature_registry_rejects_payload_features():
    """Ensures attempting to register a payload-dependent feature raises ValueError."""
    with pytest.raises(ValueError, match="zero-payload"):
        FeatureDefinition(
            name="forbidden_payload_len",
            family=FeatureFamily.PACKET_SIZE,
            definition="Payload length",
            units="bytes",
            required_packet_info=["packet_length"],
            is_zero_payload=False,
            missing_value_behavior="impute_zero",
            mathematical_formula="N/A",
        )

    with pytest.raises(ValueError, match="Security/Privacy violation"):
        FeatureDefinition(
            name="forbidden_sni_string",
            family=FeatureFamily.PACKET_SIZE,
            definition="Extracted SNI",
            units="string",
            required_packet_info=["sni"],
            is_zero_payload=True,
            missing_value_behavior="impute_zero",
            mathematical_formula="N/A",
        )


def test_family_ablation_table_schema():
    """Verifies schema and contents of results/tables/feature_family_ablation_research.csv."""
    table_path = PROJECT_ROOT / "results" / "tables" / "feature_family_ablation_research.csv"
    assert table_path.exists(), f"Missing ablation table: {table_path}"

    with open(table_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 6, f"Expected 6 ablation rows, got {len(rows)}"

    configs = [r["configuration"] for r in rows]
    assert any("Packet-size" in c for c in configs)
    assert any("Timing" in c for c in configs)
    assert any("Counts/bytes" in c for c in configs)
    assert any("Direction" in c for c in configs)
    assert any("Burst" in c for c in configs)
    assert any("All feature" in c for c in configs)

    for r in rows:
        assert int(r["feature_count"]) > 0
        assert 0.0 <= float(r["val_macro_f1"]) <= 1.0
        assert 0.0 <= float(r["test_macro_f1"]) <= 1.0
        assert float(r["mean_inference_latency_ms"]) > 0.0


def test_count_tradeoff_table_schema():
    """Verifies schema and contents of results/tables/feature_count_tradeoff_research.csv."""
    table_path = PROJECT_ROOT / "results" / "tables" / "feature_count_tradeoff_research.csv"
    assert table_path.exists(), f"Missing tradeoff table: {table_path}"

    with open(table_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 7, f"Expected 7 K-subset rows, got {len(rows)}"

    ks = [int(r["feature_count_k"]) for r in rows]
    assert ks == [3, 5, 10, 15, 20, 30, 84]

    # Verify that a lightweight profile is selected
    selected = [r for r in rows if r["is_selected_lightweight_profile"] == "YES"]
    assert len(selected) == 1, "Exactly one profile should be selected"
    assert selected[0]["feature_count_k"] == "3"


def test_feature_study_figures_validity():
    """Verifies that all 4 figures were generated and are non-empty."""
    fig_names = [
        "feature_vs_f1.png",
        "feature_vs_latency.png",
        "feature_vs_model_size.png",
        "feature_pareto_frontier.png",
    ]
    for fname in fig_names:
        fig_path = PROJECT_ROOT / "results" / "figures" / fname
        assert fig_path.exists(), f"Missing figure: {fig_path}"
        assert fig_path.stat().st_size > 10000, f"Figure {fname} appears truncated or empty"
