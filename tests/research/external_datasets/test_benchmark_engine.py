"""
Tests for External Benchmark Engine.
"""

from pathlib import Path
import json
import pytest
import numpy as np

from research.external_datasets.benchmark_engine import (
    ExternalBenchmarkEngine,
    SequenceNgramClassifier,
)
from research.external_datasets.schemas import FeatureProfileType


def test_get_supported_models():
    engine = ExternalBenchmarkEngine()
    for name in ["lr", "dt", "rf", "lightgbm", "sequence_ngram"]:
        model = engine.get_model(name)
        assert model is not None

    with pytest.raises(ValueError):
        engine.get_model("unsupported_model_abc")


def test_ece_computation():
    # Perfect calibration test
    classes = np.array(["A", "B"])
    # 4 samples: class A with 1.0 confidence, class B with 1.0 confidence
    probs = np.array([
        [1.0, 0.0],
        [1.0, 0.0],
        [0.0, 1.0],
        [0.0, 1.0],
    ])
    y_true = np.array(["A", "A", "B", "B"])
    ece = ExternalBenchmarkEngine.compute_calibration_ece(probs, y_true, classes, n_bins=10)
    assert abs(ece - 0.0) < 1e-6


def test_selective_risk_coverage():
    classes = np.array(["A", "B"])
    probs = np.array([
        [0.9, 0.1],  # Correct (A)
        [0.8, 0.2],  # Correct (A)
        [0.6, 0.4],  # Incorrect (B true, predicted A)
        [0.95, 0.05], # Correct (B true, predicted B -> wait, predicted A, incorrect!)
    ])
    y_true = np.array(["A", "A", "B", "B"])
    curve = ExternalBenchmarkEngine.compute_selective_risk_coverage(probs, y_true, classes, n_thresholds=5)
    assert len(curve) == 5
    for tau, cov, risk in curve:
        assert 0.0 <= tau <= 1.0
        assert 0.0 <= cov <= 1.0
        assert 0.0 <= risk <= 1.0


def test_sequence_ngram_classifier():
    clf = SequenceNgramClassifier()
    # Sequence of direction tokens (0, 1)
    X = np.array([
        [0, 1, 0, 1],
        [0, 1, 0, 1],
        [1, 1, 1, 1],
        [1, 1, 1, 1],
    ])
    y = np.array(["class1", "class1", "class2", "class2"])
    clf.fit(X, y)
    preds = clf.predict(X)
    assert len(preds) == 4
    assert preds[0] == "class1"
    assert preds[2] == "class2"
    probs = clf.predict_proba(X)
    assert probs.shape == (4, 2)


def test_evaluate_model_end_to_end(tmp_path: Path):
    engine = ExternalBenchmarkEngine(results_root=tmp_path / "benchmarks")

    # Synthetic training & test data (2 classes, 8 features)
    rng = np.random.RandomState(42)
    X_train = rng.randn(40, 8).astype(np.float32)
    y_train = np.array(["class_A" if i % 2 == 0 else "class_B" for i in range(40)])

    X_test = rng.randn(20, 8).astype(np.float32)
    y_test = np.array(["class_A" if i % 2 == 0 else "class_B" for i in range(20)])

    result = engine.evaluate_model(
        model_name="lr",
        dataset_id="test_dataset",
        feature_profile=FeatureProfileType.PROFILE_A_DATASET_V3,
        prefix_k=5,
        X_train=X_train,
        y_train=y_train,
        X_test=X_test,
        y_test=y_test,
    )

    assert result.model_name == "lr"
    assert result.dataset_id == "test_dataset"
    assert result.prefix_k == 5
    assert result.train_sample_count == 40
    assert result.test_sample_count == 20
    assert 0.0 <= result.macro_f1 <= 1.0
    assert 0.0 <= result.balanced_accuracy <= 1.0
    assert result.inference_latency_p50_us > 0.0
    assert result.expected_calibration_error is not None
    assert len(result.selective_risk_coverage_curve) > 0

    # Verify result file was saved in isolated folder
    saved_files = list((tmp_path / "benchmarks" / "test_dataset").glob("*.json"))
    assert len(saved_files) == 1
    with open(saved_files[0], "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["model_name"] == "lr"
    assert data["dataset_id"] == "test_dataset"
