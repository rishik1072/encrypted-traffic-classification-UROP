"""
Real-Time Streaming Traffic Classifier Engine.

Coordinates packet ingestion, flow tracking, online feature calculation,
asynchronous model inference, deterministic state machine evaluation,
telemetry persistence, fail-closed safety, and event broadcasting.
"""

from __future__ import annotations

import csv
import json
import logging
import queue
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from capture.packet_capture import RawPacketMetadata
from flows.flow_generator import Flow
from preprocessing.feature_extractor import FeatureExtractor
from realtime.alerts import AlertEvaluator, SecurityAlert
from realtime.events import (
    EventBus,
    FlowLifecycleEvent,
    FlowLifecycleState,
    OperatingMode,
    PredictionState,
    TrafficPredictionEvent,
)
from realtime.flow_tracker import RealTimeFlowTracker
from realtime.metrics import MetricsCollector, SystemMetricsSnapshot
from realtime.model_loader import ModelLoader

logger = logging.getLogger(__name__)


class RealTimeClassifier:
    """
    Asynchronous real-time traffic classification engine supporting LIVE_MODE,
    RESEARCH_MODE, and DEMO_MODE with fail-closed safety.
    """

    def __init__(
        self,
        config_path: str | Path = "config.yaml",
        operating_mode: str = "LIVE_MODE",
    ) -> None:
        self.config_path = Path(config_path)
        self.base_dir = self.config_path.parent
        self.operating_mode = operating_mode.upper()
        self.pipeline_status = "HEALTHY"

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config: Dict[str, Any] = yaml.safe_load(f)

        realtime_cfg = self.config.get("realtime", {})
        self.model_name = realtime_cfg.get("model", "lightgbm")
        self.confidence_threshold = float(realtime_cfg.get("confidence_threshold", 0.70))
        self.csv_out_path = self.base_dir / realtime_cfg.get("predictions_csv_path", "results/realtime/predictions.csv")
        self.jsonl_out_path = self.base_dir / realtime_cfg.get("predictions_jsonl_path", "results/realtime/predictions.jsonl")

        # 1. Initialize Subsystems
        self.extractor = FeatureExtractor()
        self.event_bus = EventBus()
        self.metrics_collector = MetricsCollector(
            metrics_csv_path=self.base_dir / "results/realtime/live_metrics.csv"
        )
        self.alert_evaluator = AlertEvaluator()

        try:
            self.model_loader = ModelLoader(
                model_name=self.model_name,
                config_path=self.config_path,
                enforce_registry=(self.operating_mode == OperatingMode.LIVE_MODE.value),
            )
        except Exception as e:
            logger.error("[FAIL-CLOSED] ModelLoader initialization failed: %s", e)
            self.pipeline_status = "PIPELINE_DEGRADED"
            if self.operating_mode == OperatingMode.LIVE_MODE.value:
                raise

        self.flow_tracker = RealTimeFlowTracker(
            idle_timeout=float(realtime_cfg.get("idle_timeout_seconds", 60.0)),
            active_timeout=float(realtime_cfg.get("flow_timeout_seconds", 120.0)),
            min_packets_for_classification=int(realtime_cfg.get("minimum_packets", 3)),
            min_bytes_for_classification=int(realtime_cfg.get("minimum_bytes", 128)),
            prediction_interval_seconds=float(realtime_cfg.get("prediction_interval_seconds", 1.0)),
            lifecycle_callback=self._on_flow_lifecycle,
        )

        # 2. Worker Queues & Threads
        self._prediction_work_queue: queue.Queue[Flow] = queue.Queue(maxsize=10000)
        self._is_running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._prediction_count = 0
        self._file_lock = threading.Lock()

        # Initialize CSV header matching canonical schema exactly:
        # timestamp,flow_id,session_id_hash,model_id,feature_profile,predicted_family,predicted_class,family_confidence,fine_confidence,composed_confidence,prediction_state,packets_observed,elapsed_seconds,latency_us
        self.CANONICAL_CSV_FIELDS = [
            "timestamp",
            "flow_id",
            "session_id_hash",
            "model_id",
            "feature_profile",
            "predicted_family",
            "predicted_class",
            "family_confidence",
            "fine_confidence",
            "composed_confidence",
            "prediction_state",
            "packets_observed",
            "elapsed_seconds",
            "latency_us",
        ]
        self.csv_out_path.parent.mkdir(parents=True, exist_ok=True)
        self.jsonl_out_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.csv_out_path.exists():
            with open(self.csv_out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=self.CANONICAL_CSV_FIELDS,
                )
                writer.writeheader()


    def start(self) -> None:
        """Starts asynchronous prediction worker."""
        if self.pipeline_status == "PIPELINE_DEGRADED" and self.operating_mode == OperatingMode.LIVE_MODE.value:
            raise RuntimeError("Cannot start LIVE_MODE while pipeline is PIPELINE_DEGRADED. Fail-closed.")

        self._is_running = True
        self._worker_thread = threading.Thread(target=self._prediction_worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info(
            "RealTimeClassifier started in [%s] mode with model '%s'",
            self.operating_mode,
            self.model_name,
        )

    def stop(self) -> None:
        """Stops classification worker gracefully."""
        self._is_running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        logger.info("RealTimeClassifier stopped")

    def process_packet(self, pkt: RawPacketMetadata) -> None:
        """
        Main packet ingress point. Enqueues flows for inference without blocking packet capture.
        """
        if self.pipeline_status == "PIPELINE_DEGRADED" and self.operating_mode == OperatingMode.LIVE_MODE.value:
            return

        self.metrics_collector.record_packet(pkt.length)
        _, flow, should_predict = self.flow_tracker.update(pkt)

        if should_predict:
            try:
                self._prediction_work_queue.put_nowait(flow)
            except queue.Full:
                self.metrics_collector.dropped_packets += 1
                logger.warning("Prediction queue full! Dropped prediction trigger.")

    def _prediction_worker_loop(self) -> None:
        """Worker thread processing queued flows for inference."""
        while self._is_running:
            try:
                flow = self._prediction_work_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            self._classify_flow_instance(flow)
            self._prediction_work_queue.task_done()

    def _classify_flow_instance(self, flow: Flow) -> Optional[TrafficPredictionEvent]:
        """Runs online feature extraction and deterministic state machine classification."""
        try:
            t0 = time.perf_counter()
            raw_feats = self.extractor.extract_features(flow)
            pred_class, confidence, prob_map = self.model_loader.predict_single(raw_feats)
            t1 = time.perf_counter()
            latency_us = (t1 - t0) * 1_000_000.0
            latency_ms = latency_us / 1000.0

            self._prediction_count += 1
            event_id = f"EVT-{self._prediction_count:06d}"
            flow_id = self.flow_tracker.get_flow_id(flow.key)
            session_hash = self.flow_tracker.get_session_id_hash(flow.key)
            total_bytes = sum(r[1] for r in flow.packet_records)

            # Hierarchical coarse family & confidence mapping
            bulk_classes = {"File Transfer", "Video"}
            interactive_classes = {"Web", "Messaging", "VoIP"}

            # Compute coarse family and probabilities from prob_map
            prob_bulk = sum(prob_map.get(c, 0.0) for c in bulk_classes)
            prob_inter = sum(prob_map.get(c, 0.0) for c in interactive_classes)
            prob_other = prob_map.get("Other", 0.0)

            if pred_class in bulk_classes:
                coarse_family = "Bulk_Streaming"
                family_conf = prob_bulk if prob_bulk > 0.0 else confidence
                fine_conf = prob_map.get(pred_class, confidence)
            elif pred_class in interactive_classes:
                coarse_family = "Interactive"
                family_conf = prob_inter if prob_inter > 0.0 else confidence
                fine_conf = prob_map.get(pred_class, confidence)
            elif pred_class == "Other":
                coarse_family = "Other"
                family_conf = prob_other if prob_other > 0.0 else confidence
                fine_conf = prob_map.get("Other", confidence)
            else:
                coarse_family = None
                family_conf = None
                fine_conf = None

            # Calculate composed confidence: P(family) * P(class|family)
            if family_conf is not None and fine_conf is not None:
                composed_conf = round(float(family_conf * fine_conf), 4)
            else:
                composed_conf = round(float(confidence), 4)

            # Deterministic Prediction State Machine
            if flow.total_packets < 5:
                state = PredictionState.INSUFFICIENT_EVIDENCE.value
                pred_class_out = None
                coarse_family_out = None
                family_conf = None
                fine_conf = None
                composed_conf = None
            elif family_conf is not None and family_conf < 0.35:
                # Family confidence below unknown threshold
                state = PredictionState.UNKNOWN.value
                coarse_family_out = "UNKNOWN"
                pred_class_out = None
            elif composed_conf is not None and composed_conf < self.confidence_threshold:
                state = PredictionState.LOW_CONFIDENCE.value
                coarse_family_out = coarse_family
                pred_class_out = pred_class
            else:
                state = PredictionState.KNOWN_CLASS.value
                coarse_family_out = coarse_family
                pred_class_out = pred_class

            # Record stability
            self.flow_tracker.record_flow_prediction(
                flow_id=flow_id,
                timestamp=time.time(),
                predicted_class=pred_class_out or "—",
                confidence=composed_conf or 0.0,
                prediction_state=state,
            )

            model_id = self.model_loader.model_metadata.get("model_id", f"model_{self.model_name}_v1")
            feature_profile = self.model_loader.model_metadata.get("feature_profile", "lightweight_10")
            model_ver = self.model_loader.model_metadata.get("model_version", "1.0.0")

            event = TrafficPredictionEvent(
                timestamp=time.time(),
                flow_id=flow_id,
                session_id_hash=session_hash,
                model_id=model_id,
                feature_profile=feature_profile,
                predicted_family=coarse_family_out,
                predicted_class=pred_class_out,
                family_confidence=family_conf,
                fine_confidence=fine_conf,
                composed_confidence=composed_conf,
                prediction_state=state,
                packets_observed=flow.total_packets,
                elapsed_seconds=flow.duration,
                latency_us=latency_us,
                event_id=event_id,
                prediction_version=model_ver,
                operating_mode=self.operating_mode,
                protocol=flow.key.protocol,
                source_port=flow.initiator_port,
                destination_port=flow.key.port_b if flow.initiator_port == flow.key.port_a else flow.key.port_a,
                byte_count=total_bytes,
                probabilities=prob_map,
            )

            # 1. Update Metrics
            self.metrics_collector.record_prediction(latency_ms, prediction_state=state)

            # 2. Publish to In-Memory Event Bus
            self.event_bus.publish(event)

            # 3. Persist to CSV / JSONL
            self._persist_event(event)

            # 4. Evaluate Security Alerts
            recent_events = self.event_bus.get_recent_events(limit=20)
            snap = self.metrics_collector.get_snapshot(persist=False)
            self.alert_evaluator.evaluate_telemetry(
                recent_events=recent_events,
                dropped_packets=snap.dropped_packets,
                p99_latency_ms=snap.p99_latency_ms,
                pipeline_status=self.pipeline_status,
            )

            return event
        except Exception as e:
            logger.error("[PIPELINE DEGRADED] Classification error: %s", e)
            self.pipeline_status = "PIPELINE_DEGRADED"
            return None

    def _persist_event(self, event: TrafficPredictionEvent) -> None:
        """Appends prediction event to disk in exact canonical format."""
        with self._file_lock:
            try:
                csv_data = event.to_canonical_dict()
                full_dict = event.to_dict()

                # Clean any NaN/Inf for JSON safety
                clean_json_dict = {
                    k: (None if isinstance(v, (float, int)) and (v != v or v == float("inf") or v == float("-inf")) else v)
                    for k, v in full_dict.items()
                }

                write_header = not self.csv_out_path.exists() or self.csv_out_path.stat().st_size == 0
                with open(self.csv_out_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=self.CANONICAL_CSV_FIELDS)
                    if write_header:
                        writer.writeheader()
                    writer.writerow(csv_data)

                with open(self.jsonl_out_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(clean_json_dict, allow_nan=False) + "\n")
            except Exception as e:
                logger.error("Failed to write prediction event to disk: %s", e)



    def _on_flow_lifecycle(self, event: FlowLifecycleEvent) -> None:
        if event.event_type == FlowLifecycleState.FLOW_COMPLETED:
            self.metrics_collector.record_flow_completed()
        elif event.event_type == FlowLifecycleState.FLOW_EXPIRED:
            self.metrics_collector.record_flow_expired()

    def get_metrics_snapshot(self) -> SystemMetricsSnapshot:
        active_flows = self.flow_tracker.get_active_flow_count()
        q_depth = self._prediction_work_queue.qsize()
        return self.metrics_collector.get_snapshot(active_flows_count=active_flows, queue_depth=q_depth, persist=True)
