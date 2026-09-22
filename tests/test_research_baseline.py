"""
Unit and Integration Tests for Research Baseline Experiment (EXP-R09).

Verifies group-aware session splitting, data integrity assertions, output table schemas,
metric computation, and visual figure generation.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import pytest
import numpy as np

from experiments.research_baseline.run import (
    CANONICAL_21_FEATURES,
    CANONICAL_CLASSES,
    ResearchBaselineExperiment,
    compute_multiclass_metrics,
)
from training.dataset_registry import DatasetOrigin, DatasetRegistry

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_baseline_dataset_registry_origin():
    """Ensures dataset_v2 is verified as REAL_DATA origin."""
    registry = DatasetRegistry(PROJECT_ROOT)
    meta = registry.get_dataset("dataset_v2")
    assert meta.origin == DatasetOrigin.REAL_DATA
    assert meta.version == "2.0.0"
    assert meta.flow_count == 301
    assert meta.session_count == 150


def test_baseline_group_aware_split_integrity():
    """Verifies that session splitting guarantees zero session leakage across splits."""
    exp = ResearchBaselineExperiment(config_path="config.yaml", dataset_id="dataset_v2", seed=42)
    records, _ = exp.load_and_validate_dataset()

    train_recs, val_recs, test_recs = exp.split_data_group_aware(records)

    train_sessions = {r["session_id"] for r in train_recs}
    val_sessions = {r["session_id"] for r in val_recs}
    test_sessions = {r["session_id"] for r in test_recs}

    # Verify zero session leakage
    assert len(train_sessions & val_sessions) == 0, "Leakage detected between train and val sessions!"
    assert len(train_sessions & test_sessions) == 0, "Leakage detected between train and test sessions!"
    assert len(val_sessions & test_sessions) == 0, "Leakage detected between val and test sessions!"

    # Verify all 150 sessions are partitioned
    total_sessions = len(train_sessions) + len(val_sessions) + len(test_sessions)
    assert total_sessions == 150
    assert len(train_sessions) == 102
    assert len(val_sessions) == 24
    assert len(test_sessions) == 24


def test_baseline_metrics_computation():
    """Verifies that multiclass metrics and balanced accuracy compute accurately."""
    y_true = np.array([0, 0, 1, 1, 2, 2])
    y_pred = np.array([0, 1, 1, 1, 2, 0])
    classes = ["A", "B", "C"]

    metrics = compute_multiclass_metrics(y_true, y_pred, classes)

    assert "accuracy" in metrics
    assert "macro_f1" in metrics
    assert "balanced_accuracy" in metrics
    assert "confusion_matrix" in metrics
    assert "per_class" in metrics

    # Accuracy: 4/6 = 0.6667
    assert metrics["accuracy"] == pytest.approx(0.6667, rel=1e-3)
    # Balanced accuracy: mean of recalls for class 0 (1/2), class 1 (2/2), class 2 (1/2) = (0.5 + 1.0 + 0.5)/3 = 0.6667
    assert metrics["balanced_accuracy"] == pytest.approx(0.6667, rel=1e-3)


def test_baseline_summary_table_schema():
    """Verifies schema and integrity of results/tables/research_baseline.csv."""
    table_path = PROJECT_ROOT / "results" / "tables" / "research_baseline.csv"
    assert table_path.exists(), f"Missing baseline table: {table_path}"

    with open(table_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 4, f"Expected 4 models in baseline table, got {len(rows)}"

    models_found = {r["model"] for r in rows}
    expected_models = {"logistic_regression", "decision_tree", "random_forest", "lightgbm"}
    assert models_found == expected_models

    # Verify winning model is marked
    winners = [r for r in rows if r["is_selected_winner"] == "YES"]
    assert len(winners) == 1, "Exactly one winner should be selected based on validation data"

    for r in rows:
        assert r["feature_profile"] == "baseline_21_zero_payload"
        assert r["dataset_origin"] == "REAL_DATA"
        assert int(r["train_count"]) > 0
        assert int(r["validation_count"]) > 0
        assert int(r["test_count"]) > 0
        assert float(r["val_macro_f1"]) > 0.0
        assert float(r["test_macro_f1"]) > 0.0
        assert float(r["mean_inference_latency_ms"]) > 0.0
        assert float(r["feature_extraction_latency_ms"]) > 0.0


def test_baseline_per_class_table_schema():
    """Verifies schema and class coverage in results/tables/research_baseline_per_class.csv."""
    table_path = PROJECT_ROOT / "results" / "tables" / "research_baseline_per_class.csv"
    assert table_path.exists(), f"Missing per-class table: {table_path}"

    with open(table_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # 4 models * 2 splits (val, test) * 6 classes = 48 rows
    assert len(rows) == 48, f"Expected 48 rows, found {len(rows)}"

    classes_found = {r["traffic_class"] for r in rows}
    assert classes_found == set(CANONICAL_CLASSES)

    for r in rows:
        assert int(r["support"]) == 8  # 8 flows per class in val and test splits
        assert 0.0 <= float(r["precision"]) <= 1.0
        assert 0.0 <= float(r["recall"]) <= 1.0
        assert 0.0 <= float(r["f1_score"]) <= 1.0


def test_baseline_figures_validity():
    """Verifies that figures are generated and have valid file sizes."""
    cm_fig = PROJECT_ROOT / "results" / "figures" / "research_baseline_confusion_matrix.png"
    comp_fig = PROJECT_ROOT / "results" / "figures" / "research_baseline_model_comparison.png"

    assert cm_fig.exists(), f"Missing figure: {cm_fig}"
    assert comp_fig.exists(), f"Missing figure: {comp_fig}"

    assert cm_fig.stat().st_size > 10000, "Confusion matrix figure appears truncated or empty"
    assert comp_fig.stat().st_size > 10000, "Model comparison figure appears truncated or empty"
