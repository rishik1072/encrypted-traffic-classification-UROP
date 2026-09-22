"""
Real-Time Continuous Metrics and System Resource Telemetry Collector.

Tracks throughput, packets/sec, predictions/sec, latency quantiles (p95/p99),
CPU utilization, memory usage, and prediction state distribution (KNOWN, LOW_CONF, UNKNOWN).
Persists live metrics to CSV.
"""

from __future__ import annotations

import csv
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SystemMetricsSnapshot:
    """Represents a point-in-time snapshot of system metrics."""
    timestamp: float
    active_flows: int
    completed_flows: int
    expired_flows: int
    total_packets: int
    total_bytes: int
    packets_per_sec: float
    throughput_mbps: float
    predictions_per_sec: float
    avg_latency_ms: float
    median_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    cpu_percent: float
    memory_mb: float
    dropped_packets: int = 0
    queue_depth: int = 0
    known_class_count: int = 0
    low_confidence_count: int = 0
    unknown_count: int = 0
    insufficient_evidence_count: int = 0

    @property
    def known_class_rate(self) -> float:
        total = self.known_class_count + self.low_confidence_count + self.unknown_count + self.insufficient_evidence_count
        return (self.known_class_count / total) if total > 0 else 0.0

    @property
    def low_confidence_rate(self) -> float:
        total = self.known_class_count + self.low_confidence_count + self.unknown_count + self.insufficient_evidence_count
        return (self.low_confidence_count / total) if total > 0 else 0.0

    @property
    def unknown_rate(self) -> float:
        total = self.known_class_count + self.low_confidence_count + self.unknown_count + self.insufficient_evidence_count
        return (self.unknown_count / total) if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": round(self.timestamp, 4),
            "active_flows": self.active_flows,
            "completed_flows": self.completed_flows,
            "expired_flows": self.expired_flows,
            "total_packets": self.total_packets,
            "total_bytes": self.total_bytes,
            "packets_per_sec": round(self.packets_per_sec, 2),
            "throughput_mbps": round(self.throughput_mbps, 4),
            "predictions_per_sec": round(self.predictions_per_sec, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 4),
            "median_latency_ms": round(self.median_latency_ms, 4),
            "p95_latency_ms": round(self.p95_latency_ms, 4),
            "p99_latency_ms": round(self.p99_latency_ms, 4),
            "cpu_percent": round(self.cpu_percent, 1),
            "memory_mb": round(self.memory_mb, 1),
            "dropped_packets": self.dropped_packets,
            "queue_depth": self.queue_depth,
            "known_class_rate": round(self.known_class_rate, 4),
            "low_confidence_rate": round(self.low_confidence_rate, 4),
            "unknown_rate": round(self.unknown_rate, 4),
        }


class MetricsCollector:
    """
    Accumulates continuous traffic and prediction telemetry in rolling sliding windows.
    """

    def __init__(
        self,
        window_seconds: float = 5.0,
        metrics_csv_path: str | Path = "results/realtime/live_metrics.csv",
    ) -> None:
        self.window_seconds = window_seconds
        self.metrics_csv_path = Path(metrics_csv_path)
        self.start_time = time.time()
        self.last_snapshot_time = time.time()

        # Cumulative counters
        self.total_packets = 0
        self.total_bytes = 0
        self.total_predictions = 0
        self.completed_flows = 0
        self.expired_flows = 0
        self.dropped_packets = 0

        # State counters
        self.known_class_count = 0
        self.low_confidence_count = 0
        self.unknown_count = 0
        self.insufficient_evidence_count = 0

        # Rolling buffers (timestamp, value)
        self._packet_window: deque = deque()
        self._byte_window: deque = deque()
        self._prediction_window: deque = deque()
        self._latency_window: deque = deque(maxlen=1000)

        self._init_csv()

    def _init_csv(self) -> None:
        self.metrics_csv_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.metrics_csv_path.exists():
            with open(self.metrics_csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "timestamp",
                        "active_flows",
                        "completed_flows",
                        "expired_flows",
                        "total_packets",
                        "total_bytes",
                        "packets_per_sec",
                        "throughput_mbps",
                        "predictions_per_sec",
                        "avg_latency_ms",
                        "median_latency_ms",
                        "p95_latency_ms",
                        "p99_latency_ms",
                        "cpu_percent",
                        "memory_mb",
                        "dropped_packets",
                        "queue_depth",
                        "known_class_rate",
                        "low_confidence_rate",
                        "unknown_rate",
                    ],
                )
                writer.writeheader()

    def record_packet(self, length: int) -> None:
        """Records packet arrival."""
        now = time.time()
        self.total_packets += 1
        self.total_bytes += length
        self._packet_window.append((now, 1))
        self._byte_window.append((now, length))
        self._prune_windows(now)

    def record_prediction(self, latency_ms: float, prediction_state: str = "KNOWN_CLASS") -> None:
        """Records a prediction event, its latency, and state classification."""
        now = time.time()
        self.total_predictions += 1
        self._prediction_window.append((now, 1))
        self._latency_window.append(latency_ms)

        if prediction_state == "KNOWN_CLASS":
            self.known_class_count += 1
        elif prediction_state == "LOW_CONFIDENCE":
            self.low_confidence_count += 1
        elif prediction_state == "UNKNOWN":
            self.unknown_count += 1
        elif prediction_state == "INSUFFICIENT_EVIDENCE":
            self.insufficient_evidence_count += 1

        self._prune_windows(now)

    def record_flow_completed(self) -> None:
        self.completed_flows += 1

    def record_flow_expired(self) -> None:
        self.expired_flows += 1

    def _prune_windows(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._packet_window and self._packet_window[0][0] < cutoff:
            self._packet_window.popleft()
        while self._byte_window and self._byte_window[0][0] < cutoff:
            self._byte_window.popleft()
        while self._prediction_window and self._prediction_window[0][0] < cutoff:
            self._prediction_window.popleft()

    def get_snapshot(self, active_flows_count: int = 0, queue_depth: int = 0, persist: bool = True) -> SystemMetricsSnapshot:
        """Computes rate metrics over the active sliding window and optionally appends to CSV."""
        now = time.time()
        self._prune_windows(now)

        dt = max(0.1, self.window_seconds)

        # Rates
        recent_pkts = sum(v for _, v in self._packet_window)
        recent_bytes = sum(v for _, v in self._byte_window)
        recent_preds = sum(v for _, v in self._prediction_window)

        pkts_per_sec = recent_pkts / dt
        throughput_mbps = (recent_bytes * 8.0) / (dt * 1_000_000.0)
        preds_per_sec = recent_preds / dt

        # Latency statistics
        if self._latency_window:
            lats = sorted(list(self._latency_window))
            avg_lat = sum(lats) / len(lats)
            median_lat = lats[len(lats) // 2]
            p95_lat = lats[int(len(lats) * 0.95)]
            p99_lat = lats[int(len(lats) * 0.99)]
        else:
            avg_lat = median_lat = p95_lat = p99_lat = 0.0

        # CPU & Memory
        cpu_val = 0.0
        mem_val = 0.0
        try:
            import psutil
            cpu_val = psutil.cpu_percent(interval=None)
            process = psutil.Process(os.getpid())
            mem_val = process.memory_info().rss / (1024.0 * 1024.0)
        except Exception:
            pass

        snap = SystemMetricsSnapshot(
            timestamp=now,
            active_flows=active_flows_count,
            completed_flows=self.completed_flows,
            expired_flows=self.expired_flows,
            total_packets=self.total_packets,
            total_bytes=self.total_bytes,
            packets_per_sec=pkts_per_sec,
            throughput_mbps=throughput_mbps,
            predictions_per_sec=preds_per_sec,
            avg_latency_ms=avg_lat,
            median_latency_ms=median_lat,
            p95_latency_ms=p95_lat,
            p99_latency_ms=p99_lat,
            cpu_percent=cpu_val,
            memory_mb=mem_val,
            dropped_packets=self.dropped_packets,
            queue_depth=queue_depth,
            known_class_count=self.known_class_count,
            low_confidence_count=self.low_confidence_count,
            unknown_count=self.unknown_count,
            insufficient_evidence_count=self.insufficient_evidence_count,
        )

        if persist and (now - self.last_snapshot_time) >= 1.0:
            self.last_snapshot_time = now
            try:
                with open(self.metrics_csv_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=list(snap.to_dict().keys()))
                    writer.writerow(snap.to_dict())
            except Exception as e:
                logger.error("Failed to append metrics snapshot: %s", e)

        return snap
