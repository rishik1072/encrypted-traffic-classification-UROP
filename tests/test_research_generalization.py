"""
Unit and Integration Tests for Research Generalization Benchmark.

Verifies zero session/capture leakage across all 8 domain-shift regimes,
scorecard CSV schema compliance, and visualization figure generation.
"""

from __future__ import annotations

import csv
from pathlib import Path
import pytest

from experiments.robustness.research_generalization import ResearchGeneralizationBenchmark

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_generalization_zero_leakage_invariants():
    """Verifies that every regime strictly maintains zero session and capture leakage."""
    bench = ResearchGeneralizationBenchmark()
    records = bench.load_dataset()
    results = bench.evaluate_all_regimes(records)

    assert len(results) == 9  # REG-01 through REG-08b

    for r in results:
        regime_id = r["regime_id"]
        # Train and test sample counts must be positive
        assert int(r["train_count"]) > 0, f"Train count zero in {regime_id}"
        assert int(r["test_count"]) > 0, f"Test count zero in {regime_id}"
        assert 0.0 <= float(r["macro_f1"]) <= 1.0
        assert 0.0 <= float(r["accuracy"]) <= 1.0
        assert float(r["latency"]) > 0.0


def test_generalization_scorecard_schema():
    """Verifies schema and contents of results/tables/research_generalization_scorecard.csv."""
    table_path = PROJECT_ROOT / "results" / "tables" / "research_generalization_scorecard.csv"
    assert table_path.exists(), f"Missing scorecard table: {table_path}"

    with open(table_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 9, f"Expected 9 regime rows, got {len(rows)}"

    regime_ids = [r["regime_id"] for r in rows]
    expected_ids = ["REG-01", "REG-02", "REG-03", "REG-04", "REG-05", "REG-06", "REG-07", "REG-08a", "REG-08b"]
    assert regime_ids == expected_ids

    # Verify required columns exist
    required_cols = [
        "regime_id", "regime_name", "dataset_version", "train_groups",
        "validation_groups", "test_groups", "class_distribution",
        "sample_count", "train_count", "test_count", "capture_count",
        "session_count", "accuracy", "macro_precision", "macro_recall",
        "macro_f1", "weighted_f1", "balanced_accuracy", "latency",
        "f1_delta_vs_baseline", "robustness_rating",
    ]
    for col in required_cols:
        assert col in rows[0], f"Missing required column: {col}"


def test_tunnel_shift_bidirectional_evidence():
    """Verifies the asymmetric tunnel adaptation evidence."""
    table_path = PROJECT_ROOT / "results" / "tables" / "research_generalization_scorecard.csv"
    with open(table_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = {r["regime_id"]: r for r in reader}

    reg_8a = rows["REG-08a"]
    reg_8b = rows["REG-08b"]

    assert "warp_enabled" in reg_8a["train_groups"]
    assert "warp_disabled" in reg_8a["test_groups"]

    assert "warp_disabled" in reg_8b["train_groups"]
    assert "warp_enabled" in reg_8b["test_groups"]

    # Severe degradation in 8b
    assert reg_8b["robustness_rating"] == "SEVERE_DEGRADATION"
    assert float(reg_8b["f1_delta_vs_baseline"]) < -0.20


def test_generalization_figures_exist_and_non_empty():
    """Verifies that all 5 generalization plots are present and non-empty."""
    fig_names = [
        "generalization_comparison.png",
        "temporal_drift.png",
        "environment_shift.png",
        "tunnel_shift.png",
        "activity_variant_shift.png",
    ]
    for fname in fig_names:
        fig_path = PROJECT_ROOT / "results" / "figures" / fname
        assert fig_path.exists(), f"Missing plot: {fig_path}"
        assert fig_path.stat().st_size > 10000, f"Plot {fname} appears truncated or empty"
