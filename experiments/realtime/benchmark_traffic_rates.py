"""
Real-Time Traffic Rate and System Resource Benchmark Experiment.

Evaluates throughput, CPU usage, memory consumption, latency quantiles (p95/p99),
and packet drop rates across Low, Moderate, and High traffic loads.
Saves results to results/tables/realtime_performance.csv.
"""

from __future__ import annotations

import csv
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from capture.packet_capture import RawPacketMetadata
from realtime.classifier import RealTimeClassifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("realtime_benchmark")


def run_traffic_rate_benchmark(
    config_path: str = "config.yaml",
    output_csv_path: str = "results/tables/realtime_performance.csv",
) -> List[Dict[str, Any]]:
    """
    Simulates three distinct traffic rates:
    - Low (50 packets/sec)
    - Moderate (250 packets/sec)
    - High (1000 packets/sec)
    Measures processing latency, throughput, CPU, and RAM.
    """
    logger.info("Initializing RealTimeClassifier for multi-rate benchmarking...")
    classifier = RealTimeClassifier(config_path=config_path)
    classifier.start()

    benchmark_scenarios = [
        ("Low Traffic", 50, 4.0),
        ("Moderate Traffic", 250, 4.0),
        ("High Traffic", 1000, 4.0),
    ]

    performance_records: List[Dict[str, Any]] = []

    try:
        for scenario_name, target_pps, duration_sec in benchmark_scenarios:
            logger.info("--- Starting Scenario: %s (%d pkts/sec for %.1fs) ---", scenario_name, target_pps, duration_sec)
            start_t = time.time()
            packet_interval = 1.0 / target_pps
            pkt_counter = 0

            while (time.time() - start_t) < duration_sec:
                pkt_counter += 1
                flow_idx = pkt_counter % 10
                # Generate synthetic packet
                pkt = RawPacketMetadata(
                    timestamp=time.time(),
                    src_ip=f"192.168.1.{10 + flow_idx}",
                    dst_ip="104.244.42.1",
                    src_port=50000 + flow_idx,
                    dst_port=443,
                    protocol="TCP",
                    length=64 + (pkt_counter % 500),
                )
                classifier.process_packet(pkt)
                time.sleep(packet_interval * 0.8)  # Rate pacing

            # Allow queue to settle
            time.sleep(0.5)

            snapshot = classifier.get_metrics_snapshot()
            rec = {
                "timestamp": datetime.utcnow().isoformat(),
                "model": classifier.model_name,
                "scenario": scenario_name,
                "traffic_rate": f"{target_pps} pkts/s",
                "packet_rate": snapshot.packets_per_sec,
                "throughput_mbps": snapshot.throughput_mbps,
                "active_flows": snapshot.active_flows,
                "predictions_per_second": snapshot.predictions_per_sec,
                "avg_latency_ms": snapshot.avg_latency_ms,
                "median_latency_ms": snapshot.median_latency_ms,
                "p95_latency_ms": snapshot.p95_latency_ms,
                "p99_latency_ms": snapshot.p99_latency_ms,
                "cpu_percent": snapshot.cpu_percent,
                "memory_mb": snapshot.memory_mb,
                "dropped_packets": snapshot.dropped_packets,
                "classification_count": classifier.metrics_collector.total_predictions,
            }
            performance_records.append(rec)
            logger.info(
                "Completed %s: Latency=%.4fms | Preds/s=%.1f | RAM=%.1fMB | Drops=%d",
                scenario_name, rec["avg_latency_ms"], rec["predictions_per_second"], rec["memory_mb"], rec["dropped_packets"]
            )
    finally:
        classifier.stop()

    # Save to CSV
    out_file = Path(output_csv_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    if performance_records:
        with open(out_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(performance_records[0].keys()))
            writer.writeheader()
            writer.writerows(performance_records)
        logger.info("Saved real-time performance benchmark results to %s", out_file)

    return performance_records


def main() -> None:
    run_traffic_rate_benchmark()


if __name__ == "__main__":
    main()
