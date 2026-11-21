"""
CLI Tool: Run Benchmark Model Evaluation on External Datasets.

Usage:
    python scripts/research/external_datasets/run_external_benchmark.py --dataset cesnet-tls22 --model lightgbm --prefix 5
    python scripts/research/external_datasets/run_external_benchmark.py --dataset cipherspectrum --model rf --prefix 10
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research.external_datasets.adapters.cesnet import CesnetAdapter
from research.external_datasets.adapters.cipherspectrum import CipherSpectrumAdapter
from research.external_datasets.adapters.iscxvpn2016 import IscxVpn2016Adapter
from research.external_datasets.benchmark_engine import ExternalBenchmarkEngine
from research.external_datasets.registry import get_dataset_metadata

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("run_external_benchmark")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run External Benchmark Evaluation")
    parser.add_argument("--dataset", type=str, required=True, help="Dataset ID (e.g. cesnet-tls22, cipherspectrum, iscxvpn2016)")
    parser.add_argument("--source", type=str, help="Path to raw source file if not already ingested")
    parser.add_argument("--model", type=str, default="rf", choices=["lr", "dt", "rf", "lgbm", "seq"], help="Model to evaluate")
    parser.add_argument("--prefix", type=int, default=5, choices=[3, 5, 10, 20, 30], help="Early prefix horizon K")
    parser.add_argument("--results-dir", type=str, default="results/external_benchmarks", help="Output directory for benchmark results")
    args = parser.parse_args()

    d_id = args.dataset.lower().strip()
    meta = get_dataset_metadata(d_id)
    if not meta:
        logger.error("Unknown dataset ID: '%s'", d_id)
        sys.exit(1)

    raw_path = Path("data/external_raw") / d_id
    proc_path = Path("data/external_processed") / d_id

    # Select adapter
    if d_id.startswith("cesnet"):
        adapter = CesnetAdapter(dataset_id=d_id, raw_dir=raw_path, processed_dir=proc_path)
    elif d_id == "cipherspectrum":
        adapter = CipherSpectrumAdapter(raw_dir=raw_path, processed_dir=proc_path)
    elif d_id == "iscxvpn2016":
        adapter = IscxVpn2016Adapter(raw_dir=raw_path, processed_dir=proc_path)
    else:
        logger.error("No adapter available for dataset: %s", d_id)
        sys.exit(1)

    if args.source:
        adapter.ingest(Path(args.source))

    if not adapter.flows:
        logger.error("No flows available in adapter. Ingest a dataset first using --source.")
        sys.exit(1)

    partitions = adapter.get_partitions()
    train_flows = partitions["train"]
    test_flows = partitions["test"]

    logger.info("Extracting prefix K=%d features for %s...", args.prefix, d_id)
    X_train, y_train, feature_names = adapter.extract_prefix_features(args.prefix, flows=train_flows)
    X_test, y_test, _ = adapter.extract_prefix_features(args.prefix, flows=test_flows)

    if len(X_train) == 0 or len(X_test) == 0:
        logger.error("Insufficient samples for prefix K=%d (Train: %d, Test: %d)", args.prefix, len(X_train), len(X_test))
        sys.exit(1)

    engine = ExternalBenchmarkEngine(results_root=Path(args.results_dir))
    result = engine.evaluate_model(
        model_name=args.model,
        dataset_id=d_id,
        feature_profile=adapter.get_feature_profile_type(),
        prefix_k=args.prefix,
        X_train=X_train,
        y_train=y_train,
        X_test=X_test,
        y_test=y_test,
    )

    print("\n" + "=" * 70)
    print(f"BENCHMARK RESULT: {d_id.upper()} | Model: {args.model.upper()} | K={args.prefix}")
    print("=" * 70)
    print(f"  Macro-F1          : {result.macro_f1:.4f}")
    print(f"  Balanced Accuracy : {result.balanced_accuracy:.4f}")
    print(f"  Accuracy          : {result.accuracy:.4f}")
    if result.expected_calibration_error is not None:
        print(f"  Calibration (ECE) : {result.expected_calibration_error:.4f}")
    if result.brier_score is not None:
        print(f"  Brier Score       : {result.brier_score:.4f}")
    print(f"  Latency (p50)     : {result.inference_latency_p50_us:.1f} us")
    print(f"  Latency (p95)     : {result.inference_latency_p95_us:.1f} us")
    print(f"  Latency (p99)     : {result.inference_latency_p99_us:.1f} us")
    print(f"  Train Samples     : {result.train_sample_count}")
    print(f"  Test Samples      : {result.test_sample_count}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
