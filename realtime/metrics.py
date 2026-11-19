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
import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SystemMetricsSnapshot:
    """Represents a point-in-time snapshot of system metrics and Phase 4 telemetry counters."""
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
    session_id: Optional[str] = None
    live_packets_received: int = 0
    packets_forwarded_to_flow_tracker: int = 0
    flows_created: int = 0
    flows_updated: int = 0
    flows_eligible_for_prediction: int = 0
    feature_vectors_created: int = 0
    predictions_created: int = 0
    events_stored: int = 0

    # Phase 4 exact canonical telemetry counters
    capture_packets_received: int = 0
    packets_forwarded_to_processor: int = 0
    packets_processed: int = 0
    packets_dropped: int = 0
    processing_errors: int = 0

    features_extracted: int = 0
    feature_extraction_failures: int = 0

    predictions_generated: int = 0
    known_predictions: int = 0
    low_confidence_predictions: int = 0
    unknown_predictions: int = 0
    insufficient_evidence_predictions: int = 0

    events_created: int = 0
    event_storage_failures: int = 0

    worker_alive: bool = True
    capture_thread_alive: bool = True
    capture_state: str = "CAPTURE_IDLE"
    last_capture_error: Optional[str] = None
    last_capture_error_stage: Optional[str] = None

    # Last-activity timestamps (UTC wall-clock epoch)
    last_packet_at: Optional[float] = None
    last_packet_processed_at: Optional[float] = None
    last_flow_created_at: Optional[float] = None
    last_feature_extracted_at: Optional[float] = None
    last_prediction_at: Optional[float] = None
    last_event_stored_at: Optional[float] = None

    @property
    def packets_per_second(self) -> float:
        """Alias for packets_per_sec to satisfy API and telemetry contract."""
        return self.packets_per_sec

    @property
    def bytes_per_second(self) -> float:
        """Throughput converted to bytes per second."""
        return (self.throughput_mbps * 1_000_000.0) / 8.0

    @property
    def known_class_rate(self) -> float:
        total = self.known_predictions or (self.known_class_count + self.low_confidence_count + self.unknown_count + self.insufficient_evidence_count)
        return (self.known_predictions / total) if total > 0 else 0.0

    @property
    def low_confidence_rate(self) -> float:
        total = self.known_class_count + self.low_confidence_count + self.unknown_count + self.insufficient_evidence_count
        return (self.low_confidence_count / total) if total > 0 else 0.0

    @property
    def unknown_rate(self) -> float:
        total = self.known_class_count + self.low_confidence_count + self.unknown_count + self.insufficient_evidence_count
        return (self.unknown_count / total) if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        now = time.time()
        age = lambda ts: round(max(0.0, now - ts), 2) if ts is not None else None

        return {
            "timestamp": round(self.timestamp, 4),
            "session_id": self.session_id,
            "pipeline_status": "HEALTHY",
            "active_flows": self.active_flows,
            "completed_flows": self.completed_flows,
            "expired_flows": self.expired_flows,
            "total_packets": self.total_packets,
            "total_bytes": self.total_bytes,
            "packets_per_second": round(self.packets_per_sec, 2),
            "packets_per_sec": round(self.packets_per_sec, 2),
            "bytes_per_second": round(self.bytes_per_second, 2),
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
            "live_packets_received": self.live_packets_received,
            "packets_forwarded_to_flow_tracker": self.packets_forwarded_to_flow_tracker,
            "flows_created": self.flows_created,
            "flows_updated": self.flows_updated,
            "flows_eligible_for_prediction": self.flows_eligible_for_prediction,
            "feature_vectors_created": self.feature_vectors_created,
            "predictions_created": self.predictions_created,
            "events_stored": self.events_stored,

            # Phase 4 exact canonical telemetry counters
            "capture_packets_received": self.capture_packets_received,
            "packets_forwarded_to_processor": self.packets_forwarded_to_processor,
            "packets_processed": self.packets_processed,
            "packets_dropped": self.packets_dropped,
            "processing_errors": self.processing_errors,
            "features_extracted": self.features_extracted,
            "feature_extraction_failures": self.feature_extraction_failures,
            "predictions_generated": self.predictions_generated,
            "known_predictions": self.known_predictions,
            "low_confidence_predictions": self.low_confidence_predictions,
            "unknown_predictions": self.unknown_predictions,
            "insufficient_evidence_predictions": self.insufficient_evidence_predictions,
            "events_created": self.events_created,
            "event_storage_failures": self.event_storage_failures,
            "worker_alive": self.worker_alive,
            "capture_thread_alive": self.capture_thread_alive,
            "capture_state": self.capture_state,
            "last_capture_error": self.last_capture_error,
            "last_capture_error_stage": self.last_capture_error_stage,

            # Timestamps
            "last_packet_at": self.last_packet_at,
            "last_packet_processed_at": self.last_packet_processed_at,
            "last_flow_created_at": self.last_flow_created_at,
            "last_feature_extracted_at": self.last_feature_extracted_at,
            "last_prediction_at": self.last_prediction_at,
            "last_event_stored_at": self.last_event_stored_at,

            # Activity Age in Seconds
            "last_packet_age_seconds": age(self.last_packet_at),
            "last_packet_processed_age_seconds": age(self.last_packet_processed_at),
            "last_flow_created_age_seconds": age(self.last_flow_created_at),
            "last_feature_extracted_age_seconds": age(self.last_feature_extracted_at),
            "last_prediction_age_seconds": age(self.last_prediction_at),
            "last_event_stored_age_seconds": age(self.last_event_stored_at),
        }


class MetricsCollector:
    """
    Accumulates continuous traffic and prediction telemetry in rolling sliding windows.
    """

    def __init__(
        self,
        window_seconds: float = 5.0,
        metrics_csv_path: str | Path = "results/realtime/live_metrics.csv",
        metrics_json_path: str | Path = "results/realtime/metrics.json",
        session_id: Optional[str] = None,
    ) -> None:
        self.window_seconds = window_seconds
        self.metrics_csv_path = Path(metrics_csv_path)
        self.metrics_json_path = Path(metrics_json_path)
        self.session_id = session_id
        self.start_time = time.time()
        self.last_snapshot_time = time.time()

        # Cumulative counters
        self.total_packets = 0
        self.total_bytes = 0
        self.total_predictions = 0
        self.completed_flows = 0
        self.expired_flows = 0
        self.dropped_packets = 0

        # Phase 4 exact canonical telemetry counters
        self.capture_packets_received = 0
        self.packets_forwarded_to_processor = 0
        self.packets_processed = 0
        self.packets_dropped = 0
        self.processing_errors = 0

        self.live_packets_received = 0
        self.packets_forwarded_to_flow_tracker = 0
        self.flows_created = 0
        self.flows_updated = 0
        self.flows_eligible_for_prediction = 0

        self.features_extracted = 0
        self.feature_extraction_failures = 0
        self.feature_vectors_created = 0

        self.predictions_generated = 0
        self.predictions_created = 0
        self.known_predictions = 0
        self.low_confidence_predictions = 0
        self.unknown_predictions = 0
        self.insufficient_evidence_predictions = 0

        self.events_created = 0
        self.events_stored = 0
        self.event_storage_failures = 0

        self.worker_alive = True
        self.capture_thread_alive = True
        self.capture_state = "CAPTURE_IDLE"
        self.last_capture_error: Optional[str] = None
        self.last_capture_error_stage: Optional[str] = None

        # Last-activity timestamps
        self.last_packet_at: Optional[float] = None
        self.last_packet_processed_at: Optional[float] = None
        self.last_flow_created_at: Optional[float] = None
        self.last_feature_extracted_at: Optional[float] = None
        self.last_prediction_at: Optional[float] = None
        self.last_event_stored_at: Optional[float] = None

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
        self.capture_packets_received += 1
        self.live_packets_received += 1
        self.packets_forwarded_to_processor += 1
        self.packets_forwarded_to_flow_tracker += 1
        self.total_bytes += length
        self.last_packet_at = now
        self._packet_window.append((now, 1))
        self._byte_window.append((now, length))
        self._prune_windows(now)

    def record_packet_processed(self) -> None:
        """Records packet consumption by the processing worker."""
        now = time.time()
        self.packets_processed += 1
        self.last_packet_processed_at = now

    def record_flow_created(self) -> None:
        """Records flow creation."""
        now = time.time()
        self.flows_created += 1
        self.last_flow_created_at = now

    def record_feature_extracted(self, success: bool = True) -> None:
        """Records feature extraction result."""
        now = time.time()
        if success:
            self.features_extracted += 1
            self.feature_vectors_created += 1
            self.last_feature_extracted_at = now
        else:
            self.feature_extraction_failures += 1

    def record_prediction(self, latency_ms: float, prediction_state: str = "KNOWN_CLASS") -> None:
        """Records a prediction event, its latency, and state classification."""
        now = time.time()
        self.total_predictions += 1
        self.predictions_created += 1
        self.predictions_generated += 1
        self.last_prediction_at = now
        self._prediction_window.append((now, 1))
        self._latency_window.append(latency_ms)

        if prediction_state == "KNOWN_CLASS":
            self.known_class_count += 1
            self.known_predictions += 1
        elif prediction_state == "LOW_CONFIDENCE":
            self.low_confidence_count += 1
            self.low_confidence_predictions += 1
        elif prediction_state == "UNKNOWN":
            self.unknown_count += 1
            self.unknown_predictions += 1
        elif prediction_state == "INSUFFICIENT_EVIDENCE":
            self.insufficient_evidence_count += 1
            self.insufficient_evidence_predictions += 1

        self._prune_windows(now)

    def record_event_stored(self, success: bool = True) -> None:
        """Records SQLite/disk event storage result."""
        now = time.time()
        self.events_created += 1
        if success:
            self.events_stored += 1
            self.last_event_stored_at = now
        else:
            self.event_storage_failures += 1

    def record_flow_completed(self) -> None:
        self.completed_flows += 1

    def record_flow_expired(self) -> None:
        self.expired_flows += 1

    def sync_from_sniffer(self, sniffer_telemetry: Dict[str, Any]) -> None:
        """Synchronizes ingestion telemetry directly from LiveSniffer."""
        if not sniffer_telemetry:
            return
        if "capture_packets_received" in sniffer_telemetry and sniffer_telemetry["capture_packets_received"] > 0:
            self.capture_packets_received = sniffer_telemetry["capture_packets_received"]
            self.total_packets = self.capture_packets_received
            self.live_packets_received = self.capture_packets_received
        if "packets_forwarded_to_processor" in sniffer_telemetry:
            self.packets_forwarded_to_processor = sniffer_telemetry["packets_forwarded_to_processor"]
            self.packets_forwarded_to_flow_tracker = self.packets_forwarded_to_processor
        if "packets_processed" in sniffer_telemetry and sniffer_telemetry["packets_processed"] > 0:
            self.packets_processed = sniffer_telemetry["packets_processed"]
        if "packets_dropped" in sniffer_telemetry:
            self.packets_dropped = sniffer_telemetry["packets_dropped"]
            self.dropped_packets = self.packets_dropped
        if "processing_errors" in sniffer_telemetry:
            self.processing_errors = sniffer_telemetry["processing_errors"]
        if "capture_thread_alive" in sniffer_telemetry:
            self.capture_thread_alive = bool(sniffer_telemetry["capture_thread_alive"])
        if "worker_alive" in sniffer_telemetry:
            self.worker_alive = bool(sniffer_telemetry["worker_alive"])
        if sniffer_telemetry.get("last_packet_at"):
            self.last_packet_at = sniffer_telemetry["last_packet_at"]
        if sniffer_telemetry.get("last_packet_processed_at"):
            self.last_packet_processed_at = sniffer_telemetry["last_packet_processed_at"]
        if "capture_state" in sniffer_telemetry:
            self.capture_state = sniffer_telemetry["capture_state"]
        if "last_capture_error" in sniffer_telemetry:
            self.last_capture_error = sniffer_telemetry["last_capture_error"]
        if "last_capture_error_stage" in sniffer_telemetry:
            self.last_capture_error_stage = sniffer_telemetry["last_capture_error_stage"]

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

        # Rates - strictly 0.0 if no packets/preds in session or window
        recent_pkts = sum(v for _, v in self._packet_window)
        recent_bytes = sum(v for _, v in self._byte_window)
        recent_preds = sum(v for _, v in self._prediction_window)

        if self.total_packets == 0 or recent_pkts == 0:
            pkts_per_sec = 0.0
            throughput_mbps = 0.0
        else:
            pkts_per_sec = recent_pkts / dt
            throughput_mbps = (recent_bytes * 8.0) / (dt * 1_000_000.0)

        if self.predictions_generated == 0 or recent_preds == 0:
            preds_per_sec = 0.0
        else:
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
            session_id=self.session_id,
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
            live_packets_received=self.live_packets_received,
            packets_forwarded_to_flow_tracker=self.packets_forwarded_to_flow_tracker,
            flows_created=self.flows_created,
            flows_updated=self.flows_updated,
            flows_eligible_for_prediction=self.flows_eligible_for_prediction,
            feature_vectors_created=self.feature_vectors_created,
            predictions_created=self.predictions_created,
            events_stored=self.events_stored,

            # Phase 4 exact canonical telemetry counters
            capture_packets_received=self.capture_packets_received,
            packets_forwarded_to_processor=self.packets_forwarded_to_processor,
            packets_processed=self.packets_processed,
            packets_dropped=self.packets_dropped,
            processing_errors=self.processing_errors,
            features_extracted=self.features_extracted,
            feature_extraction_failures=self.feature_extraction_failures,
            predictions_generated=self.predictions_generated,
            known_predictions=self.known_predictions,
            low_confidence_predictions=self.low_confidence_predictions,
            unknown_predictions=self.unknown_predictions,
            insufficient_evidence_predictions=self.insufficient_evidence_predictions,
            events_created=self.events_created,
            event_storage_failures=self.event_storage_failures,
            worker_alive=self.worker_alive,
            capture_thread_alive=self.capture_thread_alive,
            capture_state=self.capture_state,
            last_capture_error=self.last_capture_error,
            last_capture_error_stage=self.last_capture_error_stage,

            # Timestamps
            last_packet_at=self.last_packet_at,
            last_packet_processed_at=self.last_packet_processed_at,
            last_flow_created_at=self.last_flow_created_at,
            last_feature_extracted_at=self.last_feature_extracted_at,
            last_prediction_at=self.last_prediction_at,
            last_event_stored_at=self.last_event_stored_at,
        )

        if persist:
            self.export_metrics_json(snap)

        if persist and (now - self.last_snapshot_time) >= 1.0:
            self.last_snapshot_time = now
            try:
                with open(self.metrics_csv_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=list(snap.to_dict().keys()))
                    writer.writerow(snap.to_dict())
            except Exception as e:
                logger.error("Failed to append metrics snapshot: %s", e)

        return snap

    def export_metrics_json(self, snap: SystemMetricsSnapshot) -> None:
        """Atomically writes current telemetry metrics snapshot to results/realtime/metrics.json."""
        try:
            self.metrics_json_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.metrics_json_path.with_name(f"{self.metrics_json_path.name}.tmp")
            data = snap.to_dict()
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            tmp_path.replace(self.metrics_json_path)
        except Exception as e:
            logger.debug("Failed to write metrics.json: %s", e)

