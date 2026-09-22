"""
Unit and integration tests for EXP-R14: Complete Computational-Efficiency Benchmark.
Validates:
1. Generation and integrity of latency, resource usage, and model footprint tables.
2. Distributional latency invariants (P50 <= P95 <= P99, min <= P50 <= max).
3. Cold start vs. warm steady-state latency invariants.
4. Model footprint constraints (Decision Tree and Logistic Regression <= 10 KB).
5. Existence and validity of all 4 generated research figures.
6. Target host hardware and runtime environment capture.
"""

from pathlib import Path
import pandas as pd
import pytest

from experiments.computational_efficiency.run import (
    get_system_environment_info,
    compute_distribution,
    get_process_memory_mb,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
LATENCY_CSV = REPO_ROOT / "results" / "tables" / "research_latency.csv"
RESOURCE_CSV = REPO_ROOT / "results" / "tables" / "research_resource_usage.csv"
FOOTPRINT_CSV = REPO_ROOT / "results" / "tables" / "research_model_footprint.csv"
FIGURES_DIR = REPO_ROOT / "results" / "figures"
RESULTS_DIR = REPO_ROOT / "results"


def test_computational_efficiency_tables_exist():
    """Verify that all 3 required CSV result tables exist and are non-empty."""
    assert LATENCY_CSV.exists(), f"Missing {LATENCY_CSV}"
    assert RESOURCE_CSV.exists(), f"Missing {RESOURCE_CSV}"
    assert FOOTPRINT_CSV.exists(), f"Missing {FOOTPRINT_CSV}"

    df_lat = pd.read_csv(LATENCY_CSV)
    assert len(df_lat) >= 30, "Latency table should contain full model and stage sweeps"
    required_lat_cols = [
        "model", "feature_profile", "feature_count", "stage",
        "execution_phase", "repetitions", "mean_ms", "std_ms",
        "p50_ms", "p95_ms", "p99_ms", "min_ms", "max_ms", "throughput_fps"
    ]
    for col in required_lat_cols:
        assert col in df_lat.columns, f"Missing column {col} in research_latency.csv"

    df_res = pd.read_csv(RESOURCE_CSV)
    assert len(df_res) >= 12, "Resource usage table should cover all model-profile pairs"
    required_res_cols = [
        "model", "feature_profile", "feature_count", "working_set_mb",
        "peak_working_set_mb", "heap_allocated_mb", "cpu_time_per_1k_flows_ms",
        "cpu_utilization_pct"
    ]
    for col in required_res_cols:
        assert col in df_res.columns, f"Missing column {col} in research_resource_usage.csv"

    df_foot = pd.read_csv(FOOTPRINT_CSV)
    assert len(df_foot) >= 12, "Footprint table should cover all model-profile pairs"
    required_foot_cols = [
        "model", "feature_profile", "feature_count", "in_memory_bytes",
        "serialized_disk_kb", "parameter_count", "training_time_sec",
        "test_accuracy", "test_macro_f1"
    ]
    for col in required_foot_cols:
        assert col in df_foot.columns, f"Missing column {col} in research_model_footprint.csv"


def test_computational_efficiency_figures_exist():
    """Verify that all 4 required figures exist and have non-zero file sizes."""
    figure_names = [
        "latency_distribution.png",
        "model_size_vs_f1.png",
        "latency_vs_f1.png",
        "resource_usage.png"
    ]
    for fname in figure_names:
        fig_path = FIGURES_DIR / fname
        res_path = RESULTS_DIR / fname
        target = fig_path if fig_path.exists() else res_path
        assert target.exists(), f"Figure {fname} not found in {FIGURES_DIR} or {RESULTS_DIR}"
        assert target.stat().st_size > 1000, f"Figure {fname} is too small or corrupt"


def test_latency_distribution_statistics():
    """Verify mathematical consistency of percentile distributions (P50 <= P95 <= P99, min <= P50 <= max)."""
    df_lat = pd.read_csv(LATENCY_CSV)
    df_warm = df_lat[df_lat["execution_phase"] == "warm"]

    for _, row in df_warm.iterrows():
        p50 = row["p50_ms"]
        p95 = row["p95_ms"]
        p99 = row["p99_ms"]
        min_v = row["min_ms"]
        max_v = row["max_ms"]

        assert min_v <= p50 <= max_v, f"P50 {p50} out of range [{min_v}, {max_v}] for {row['model']} {row['stage']}"
        assert p50 <= p95 <= p99, f"Percentile ordering violation: {p50} <= {p95} <= {p99} for {row['model']} {row['stage']}"
        assert row["throughput_fps"] > 0, f"Throughput must be positive: {row['throughput_fps']}"


def test_cold_start_vs_warm_invariants():
    """Verify that cold start latency exhibits initialization inflation relative to warm steady-state."""
    df_lat = pd.read_csv(LATENCY_CSV)

    # Preprocessing cold vs warm
    prep_cold = df_lat[(df_lat["stage"] == "preprocessing") & (df_lat["execution_phase"] == "cold")]["mean_ms"].mean()
    prep_warm = df_lat[(df_lat["stage"] == "preprocessing") & (df_lat["execution_phase"] == "warm")]["p50_ms"].mean()
    assert prep_cold >= prep_warm, f"Cold preprocessing ({prep_cold}) should be >= warm median ({prep_warm})"

    # Decision tree inference cold vs warm
    dt_cold = df_lat[(df_lat["model"] == "decision_tree") & (df_lat["stage"] == "inference") & (df_lat["execution_phase"] == "cold")]["mean_ms"].mean()
    dt_warm = df_lat[(df_lat["model"] == "decision_tree") & (df_lat["stage"] == "inference") & (df_lat["execution_phase"] == "warm")]["p50_ms"].mean()
    assert dt_cold >= dt_warm, f"Cold Decision Tree inference ({dt_cold}) should be >= warm median ({dt_warm})"


def test_model_footprint_invariants():
    """Verify serialized model footprint invariants."""
    df_foot = pd.read_csv(FOOTPRINT_CSV)

    # Decision Tree footprint must be extremely lightweight (< 10 KB)
    dt_sizes = df_foot[df_foot["model"] == "decision_tree"]["serialized_disk_kb"].tolist()
    for s in dt_sizes:
        assert s < 10.0, f"Decision Tree footprint {s} KB exceeded 10 KB threshold"

    # Logistic Regression footprint must be < 5 KB
    lr_sizes = df_foot[df_foot["model"] == "logistic_regression"]["serialized_disk_kb"].tolist()
    for s in lr_sizes:
        assert s < 5.0, f"Logistic Regression footprint {s} KB exceeded 5 KB threshold"

    # All models must have non-zero parameters and positive training time
    assert (df_foot["parameter_count"] > 0).all()
    assert (df_foot["training_time_sec"] > 0.0).all()


def test_system_environment_profiling():
    """Verify system info collection captures host target hardware details."""
    info = get_system_environment_info()
    assert "cpu" in info and len(info["cpu"]) > 0
    assert "os" in info and len(info["os"]) > 0
    assert "python_version" in info and len(info["python_version"]) > 0
    assert info["ram_gb"] > 1.0, f"RAM {info['ram_gb']} GB should be positive"
    assert info["cpu_cores_logical"] >= 1

    # Windows memory helper test
    ws, peak = get_process_memory_mb()
    assert ws > 0.0, f"Working set memory should be positive, got {ws}"
    assert peak >= ws, f"Peak working set {peak} should be >= working set {ws}"
