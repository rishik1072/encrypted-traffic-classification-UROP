"""
Inference Latency and Hardware Resource Benchmarking Module.

Measures single-flow and batch inference latency (mean, median, p95, p99),
preprocessing overhead, CPU utilization, and memory footprint.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.base_model import BaseTrafficClassifier

logger = logging.getLogger(__name__)


def benchmark_model_latency(
    model: BaseTrafficClassifier,
    sample_features: Any,
    warmup_runs: int = 50,
    benchmark_runs: int = 500,
    batch_size: int = 32,
    measure_cpu: bool = True,
    measure_memory: bool = True,
) -> Dict[str, Any]:
    """
    Rigorously benchmarks inference latency (single & batch) and hardware utilization.
    """
    try:
        import numpy as np
        single_vec = sample_features[:1]
        batch_vec = (
            np.repeat(single_vec, batch_size, axis=0)
            if hasattr(sample_features, "shape")
            else [sample_features[0]] * batch_size
        )
    except (ImportError, Exception):
        single_vec = [sample_features[0]]
        batch_vec = [sample_features[0]] * batch_size

    # 2. Warmup phase
    for _ in range(warmup_runs):
        _ = model.predict(single_vec)

    # 3. CPU and Memory pre-measurement
    cpu_percent = 0.0
    mem_mb = 0.0
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / (1024.0 * 1024.0)
        psutil.cpu_percent(interval=None)
    except ImportError:
        mem_before = 0.0

    # 4. Single-flow latency measurement
    single_latencies: List[float] = []
    for _ in range(benchmark_runs):
        t0 = time.perf_counter()
        _ = model.predict(single_vec)
        t1 = time.perf_counter()
        single_latencies.append((t1 - t0) * 1000.0)  # ms

    # 5. Batch latency measurement
    batch_runs = max(10, benchmark_runs // 10)
    batch_latencies: List[float] = []
    for _ in range(batch_runs):
        t0 = time.perf_counter()
        _ = model.predict(batch_vec)
        t1 = time.perf_counter()
        batch_latencies.append(((t1 - t0) * 1000.0) / batch_size)  # ms per sample

    # 6. Resource post-measurement
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_after = process.memory_info().rss / (1024.0 * 1024.0)
        cpu_percent = psutil.cpu_percent(interval=None)
        mem_mb = round(mem_after, 2)
    except ImportError:
        cpu_percent = 0.0
        mem_mb = 0.0

    # Statistical metrics
    sorted_lats = sorted(single_latencies)
    avg_lat = sum(sorted_lats) / len(sorted_lats)
    median_lat = sorted_lats[len(sorted_lats) // 2]
    p95_lat = sorted_lats[int(len(sorted_lats) * 0.95)]
    p99_lat = sorted_lats[int(len(sorted_lats) * 0.99)]
    avg_batch_lat = sum(batch_latencies) / len(batch_latencies)

    logger.info(
        "Benchmarked %s: Avg=%.4fms | Median=%.4fms | p95=%.4fms | Batch=%.4fms/pkt | RAM=%.1fMB",
        model.model_name, avg_lat, median_lat, p95_lat, avg_batch_lat, mem_mb
    )

    return {
        "avg_inference_ms": round(avg_lat, 4),
        "median_inference_ms": round(median_lat, 4),
        "p95_inference_ms": round(p95_lat, 4),
        "p99_inference_ms": round(p99_lat, 4),
        "batch_inference_ms_per_flow": round(avg_batch_lat, 4),
        "memory_mb": mem_mb,
        "cpu_percent": round(cpu_percent, 2),
        "benchmark_runs": benchmark_runs,
        "warmup_runs": warmup_runs,
    }


def benchmark_preprocessor_latency(
    preprocessor: Any,
    raw_sample_record: Dict[str, Any],
    runs: int = 500,
) -> float:
    """Measures single-record feature transformation latency in milliseconds."""
    for _ in range(20):
        _ = preprocessor.transform([raw_sample_record])

    latencies = []
    for _ in range(runs):
        t0 = time.perf_counter()
        _ = preprocessor.transform([raw_sample_record])
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    avg_prep_ms = sum(latencies) / len(latencies)
    return round(avg_prep_ms, 4)


def measure_serialized_size(model: BaseTrafficClassifier) -> float:
    """Measures serialized model size in MB."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        model.save(tmp_path)
        size_bytes = tmp_path.stat().st_size
        return round(size_bytes / (1024.0 * 1024.0), 4)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

