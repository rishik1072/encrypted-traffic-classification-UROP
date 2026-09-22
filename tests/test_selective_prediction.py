"""
Unit and integration tests for EXP-R13: Selective Classification & Uncertainty Evaluation.
Validates:
1. Artifact and table generation schemas.
2. Monotonic risk-coverage trade-offs.
3. Validation-only threshold selection protocol.
4. 4-state assignment logic (KNOWN, LOW_CONFIDENCE, UNKNOWN, INSUFFICIENT_EVIDENCE).
5. Disambiguation between legitimate class "Other" and uncertainty state "UNKNOWN".
"""

from pathlib import Path
import pandas as pd
import pytest

from realtime.events import PredictionState
from realtime.classifier import RealTimeClassifier
from experiments.selective_prediction.run import (
    determine_prediction_state,
    calculate_ece,
    calculate_multiclass_brier_score
)
import numpy as np


REPO_ROOT = Path(__file__).resolve().parent.parent
SELECTIVE_CSV = REPO_ROOT / "results" / "tables" / "research_selective_prediction.csv"
CALIBRATION_CSV = REPO_ROOT / "results" / "tables" / "research_calibration.csv"
FIGURES_DIR = REPO_ROOT / "results" / "figures"
RESULTS_DIR = REPO_ROOT / "results"


def test_selective_prediction_tables_exist():
    """Verify that the required CSV tables are generated and non-empty."""
    assert SELECTIVE_CSV.exists(), f"Missing {SELECTIVE_CSV}"
    assert CALIBRATION_CSV.exists(), f"Missing {CALIBRATION_CSV}"

    df_sel = pd.read_csv(SELECTIVE_CSV)
    assert len(df_sel) >= 12, "Selective prediction table must contain validation and test sweeps"
    required_cols = [
        "split", "threshold", "coverage", "coverage_pct", "rejected_flow_pct",
        "selective_accuracy", "error_rate_accepted", "selective_macro_f1",
        "average_confidence", "is_selected_threshold"
    ]
    for col in required_cols:
        assert col in df_sel.columns, f"Missing required column {col} in selective table"

    df_cal = pd.read_csv(CALIBRATION_CSV)
    assert len(df_cal) == 10, "Calibration table should contain 10 reliability bins"
    cal_cols = [
        "bin_index", "bin_range", "sample_count", "avg_confidence",
        "empirical_accuracy", "calibration_gap", "overall_ece", "overall_brier"
    ]
    for col in cal_cols:
        assert col in df_cal.columns, f"Missing required column {col} in calibration table"


def test_selective_prediction_figures_exist():
    """Verify that all four required figures exist."""
    figure_names = [
        "coverage_vs_accuracy.png",
        "coverage_vs_error.png",
        "confidence_distribution.png",
        "calibration_curve.png"
    ]
    for fname in figure_names:
        fig_path = FIGURES_DIR / fname
        res_path = RESULTS_DIR / fname
        assert fig_path.exists() or res_path.exists(), f"Figure {fname} not found in {FIGURES_DIR} or {RESULTS_DIR}"


def test_monotonic_risk_coverage_tradeoff():
    """Verify that coverage decreases monotonically and selective accuracy improves with higher thresholds on test data."""
    df_sel = pd.read_csv(SELECTIVE_CSV)
    df_test = df_sel[df_sel["split"] == "test"].sort_values("threshold")

    coverages = df_test["coverage"].tolist()
    accuracies = df_test["selective_accuracy"].tolist()
    error_rates = df_test["error_rate_accepted"].tolist()

    # Coverage must be non-increasing with threshold
    for i in range(len(coverages) - 1):
        assert coverages[i] >= coverages[i + 1] - 1e-6, f"Coverage not monotonic: {coverages}"

    # Error rate at highest threshold (0.9) must be substantially lower than unconstrained (0.0)
    assert error_rates[-1] < error_rates[0], "Error rate should decrease at high confidence threshold"
    assert accuracies[-1] > accuracies[0], "Selective accuracy should increase at high confidence threshold"


def test_validation_only_threshold_selection():
    """Verify threshold selection rule operates on validation split and is recorded consistently."""
    df_sel = pd.read_csv(SELECTIVE_CSV)
    df_val = df_sel[df_sel["split"] == "validation"]
    df_test = df_sel[df_sel["split"] == "test"]

    val_selected = df_val[df_val["is_selected_threshold"] == "YES"]
    test_selected = df_test[df_test["is_selected_threshold"] == "YES"]

    assert len(val_selected) == 1, "Exactly one threshold should be selected on validation set"
    assert len(test_selected) == 1, "Selected threshold marker should be unique in test set"
    assert val_selected.iloc[0]["threshold"] == test_selected.iloc[0]["threshold"]


def test_prediction_state_assignment_logic():
    """Verify the 4-state assignment logic function."""
    # 1. Insufficient evidence (N < 3)
    state, cls_out = determine_prediction_state(
        packet_count=2, max_conf=0.95, candidate_class="Streaming",
        min_evidence_packets=3, unknown_threshold=0.30, confidence_threshold=0.50
    )
    assert state == PredictionState.INSUFFICIENT_EVIDENCE
    assert cls_out is None

    # 2. Unknown (N >= 3, conf < 0.30)
    state, cls_out = determine_prediction_state(
        packet_count=10, max_conf=0.25, candidate_class="Streaming",
        min_evidence_packets=3, unknown_threshold=0.30, confidence_threshold=0.50
    )
    assert state == PredictionState.UNKNOWN
    assert cls_out is None

    # 3. Low confidence (0.30 <= conf < 0.50)
    state, cls_out = determine_prediction_state(
        packet_count=10, max_conf=0.45, candidate_class="Streaming",
        min_evidence_packets=3, unknown_threshold=0.30, confidence_threshold=0.50
    )
    assert state == PredictionState.LOW_CONFIDENCE
    assert cls_out == "Streaming"

    # 4. Known (conf >= 0.50)
    state, cls_out = determine_prediction_state(
        packet_count=10, max_conf=0.85, candidate_class="Streaming",
        min_evidence_packets=3, unknown_threshold=0.30, confidence_threshold=0.50
    )
    assert state == PredictionState.KNOWN
    assert cls_out == "Streaming"


def test_other_class_is_legitimate_known_class():
    """
    Verify that class 'Other' is a legitimate labeled class and can achieve state KNOWN,
    distinguishing it from the epistemic uncertainty state UNKNOWN.
    """
    state, cls_out = determine_prediction_state(
        packet_count=15, max_conf=0.78, candidate_class="Other",
        min_evidence_packets=3, unknown_threshold=0.30, confidence_threshold=0.50
    )
    assert state == PredictionState.KNOWN
    assert cls_out == "Other", "Legitimate 'Other' class must not be overridden to UNKNOWN when confident"


def test_calibration_metrics_math():
    """Verify ECE and Brier score implementations with synthetic sanity values."""
    # Perfect calibration test
    y_true = np.array([0, 1])
    y_prob = np.array([[1.0, 0.0], [0.0, 1.0]])
    brier = calculate_multiclass_brier_score(y_true, y_prob)
    assert np.isclose(brier, 0.0), f"Perfect predictions must have 0 Brier score, got {brier}"

    ece, mce, _ = calculate_ece(y_true, y_prob, n_bins=10)
    assert np.isclose(ece, 0.0), f"Perfect predictions must have 0 ECE, got {ece}"
