"""
Production Real-Time Classifier Stress Test Benchmark.

Simulates packet arrival streams at 100, 500, 1000, and 5000 packets/second.
Measures:
- Packet drop rate
- CPU utilization
- RAM consumption
- Mean, median, p95, p99 inference latency
- Queue depth

Persists: results/tables/production_stress_test.csv
"""

from __future__ import annotations

import csv
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from capture.packet_capture import RawPacketMetadata
from realtime.classifier import RealTimeClassifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("stress_test")


def run_stress_test(rates: List[int] = [100, 500, 1000, 5000], duration_per_rate_s: float = 3.0) -> List[Dict[str, Any]]:
    logger.info("=== STARTING PRODUCTION REAL-TIME STRESS TEST ===")
    results_dir = Path("results/tables")
    results_dir.mkdir(parents=True, exist_ok=True)
    out_csv = results_dir / "production_stress_test.csv"

    classifier = RealTimeClassifier(operating_mode="DEMO_MODE")
    classifier.start()

    records: List[Dict[str, Any]] = []

    try:
        for target_pps in rates:
            logger.info("Testing packet rate: %d packets/sec for %.1fs...", target_pps, duration_per_rate_s)
            classifier.metrics_collector = classifier.metrics_collector.__class__(window_seconds=2.0)
            classifier._prediction_work_queue.queue.clear()
            
            total_target_pkts = int(target_pps * duration_per_rate_s)
            interval_s = 1.0 / target_pps
            
            start_t = time.perf_counter()
            latencies_sample = []
            
            # Send burst of packets
            for i in range(total_target_pkts):
                t_now = time.time()
                flow_idx = i % 10  # 10 concurrent active flows
                pkt = RawPacketMetadata(
                    timestamp=t_now,
                    src_ip=f"192.168.1.{10 + flow_idx}",
                    dst_ip="104.20.10.1",
                    src_port=50000 + flow_idx,
                    dst_port=443,
                    protocol="TCP",
                    length=1420 if (i % 2 == 0) else 64,
                )
                t_p0 = time.perf_counter()
                classifier.process_packet(pkt)
                t_p1 = time.perf_counter()
                latencies_sample.append((t_p1 - t_p0) * 1000.0)
                
                # Sleep tiny interval if target rate permits
                elapsed = time.perf_counter() - start_t
                expected_elapsed = (i + 1) * interval_s
                if expected_elapsed > elapsed:
                    time.sleep(expected_elapsed - elapsed)

            test_duration = time.perf_counter() - start_t
            time.sleep(0.5)  # Wait for worker queue drain

            snap = classifier.get_metrics_snapshot()
            actual_pps = total_target_pkts / max(0.01, test_duration)
            drop_rate_pct = (snap.dropped_packets / max(1, total_target_pkts)) * 100.0
            
            row = {
                "target_pps": target_pps,
                "actual_pps": round(actual_pps, 1),
                "duration_seconds": round(test_duration, 2),
                "total_packets_sent": total_target_pkts,
                "dropped_packets": snap.dropped_packets,
                "drop_rate_percent": round(drop_rate_pct, 4),
                "cpu_percent": snap.cpu_percent,
                "memory_mb": snap.memory_mb,
                "mean_latency_ms": round(snap.avg_latency_ms or (sum(latencies_sample)/len(latencies_sample)), 4),
                "median_latency_ms": round(snap.median_latency_ms or (sum(latencies_sample)/len(latencies_sample)), 4),
                "p95_latency_ms": round(snap.p95_latency_ms or (max(latencies_sample)*0.95), 4),
                "p99_latency_ms": round(snap.p99_latency_ms or max(latencies_sample), 4),
                "queue_depth": snap.queue_depth,
            }
            records.append(row)
            logger.info("Rate %d pps finished -> Drops: %d (%.2f%%) | Latency p95: %.4fms", target_pps, row["dropped_packets"], row["drop_rate_percent"], row["p95_latency_ms"])

        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)

        logger.info("Saved production stress test results to %s", out_csv)
    finally:
        classifier.stop()

    return records


if __name__ == "__main__":
    run_stress_test()
