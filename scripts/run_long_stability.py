"""
Production Real-Time Classifier Long-Run Stability Test.

Runs extended streaming benchmarks (e.g. 10 minutes scaled) to monitor:
- Memory leak detection (RSS growth)
- In-memory event queue bounding
- Garbage collection stability
- Active flow table pruning efficiency
- Crash-free continuous operation

Persists: results/tables/long_run_stability.csv
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
logger = logging.getLogger("stability_test")


def run_long_stability(duration_seconds: float = 120.0, rate_pps: int = 250) -> List[Dict[str, Any]]:
    logger.info("=== STARTING LONG-RUN STABILITY TEST (%.1fs @ %d pps) ===", duration_seconds, rate_pps)
    results_dir = Path("results/tables")
    results_dir.mkdir(parents=True, exist_ok=True)
    out_csv = results_dir / "long_run_stability.csv"

    classifier = RealTimeClassifier(operating_mode="DEMO_MODE")
    classifier.start()

    records: List[Dict[str, Any]] = []
    interval_s = 1.0 / rate_pps
    checkpoint_interval_s = 15.0
    start_time = time.perf_counter()
    last_checkpoint = start_time
    packet_seq = 0

    try:
        while (time.perf_counter() - start_time) < duration_seconds:
            packet_seq += 1
            t_now = time.time()
            flow_idx = packet_seq % 25  # 25 active concurrent flows rotating
            pkt = RawPacketMetadata(
                timestamp=t_now,
                src_ip=f"10.0.0.{10 + flow_idx}",
                dst_ip="104.20.10.1",
                src_port=40000 + flow_idx,
                dst_port=443,
                protocol="TCP",
                length=1420 if (packet_seq % 3 == 0) else 64,
            )
            classifier.process_packet(pkt)

            # Periodically prune stale flows
            if packet_seq % 500 == 0:
                classifier.flow_tracker.clean_stale_flows(t_now)

            now_perf = time.perf_counter()
            if (now_perf - last_checkpoint) >= checkpoint_interval_s:
                last_checkpoint = now_perf
                elapsed = now_perf - start_time
                snap = classifier.get_metrics_snapshot()
                
                row = {
                    "elapsed_seconds": round(elapsed, 1),
                    "total_packets": packet_seq,
                    "active_flows": snap.active_flows,
                    "completed_flows": snap.completed_flows,
                    "expired_flows": snap.expired_flows,
                    "dropped_packets": snap.dropped_packets,
                    "queue_depth": snap.queue_depth,
                    "avg_latency_ms": round(snap.avg_latency_ms, 4),
                    "p95_latency_ms": round(snap.p95_latency_ms, 4),
                    "known_class_rate": round(snap.known_class_rate, 4),
                    "low_conf_rate": round(snap.low_confidence_rate, 4),
                    "unknown_rate": round(snap.unknown_rate, 4),
                }
                records.append(row)
                logger.info(
                    "Checkpoint [%.1fs]: Flows=%d, Pkts=%d, Latency p95=%.4fms, Drops=%d, Mem=%.1fMB",
                    elapsed, row["active_flows"], row["total_packets"], row["p95_latency_ms"], row["dropped_packets"], snap.memory_mb
                )

            # Throttle rate
            expected_elapsed = packet_seq * interval_s
            actual_elapsed = time.perf_counter() - start_time
            if expected_elapsed > actual_elapsed:
                time.sleep(expected_elapsed - actual_elapsed)

        if records:
            with open(out_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
                writer.writeheader()
                writer.writerows(records)
            logger.info("Saved long-run stability test records to %s", out_csv)
    finally:
        classifier.stop()

    return records


if __name__ == "__main__":
    run_long_stability(duration_seconds=30.0, rate_pps=300)
