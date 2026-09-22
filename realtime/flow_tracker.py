"""
Real-Time Bidirectional Flow Tracker and Prediction Stability State Machine.

Maintains live flow state tables, detects bidirectional packet sequences,
tracks prediction evolution over time (number of changes, time to stable prediction),
and handles flow lifecycle transitions.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from capture.packet_capture import RawPacketMetadata
from flows.flow_generator import Flow, FlowKey
from realtime.events import FlowLifecycleEvent, FlowLifecycleState

logger = logging.getLogger(__name__)


@dataclass
class FlowPredictionHistory:
    """Tracks chronological prediction stability for a flow."""
    flow_id: str
    session_id_hash: str
    created_at: float
    history: List[Tuple[float, str, float, str]] = field(default_factory=list)  # (timestamp, class, conf, state)
    changes_count: int = 0
    time_to_first_prediction: Optional[float] = None
    time_to_stable_prediction: Optional[float] = None
    stable_prediction_class: Optional[str] = None
    final_state: str = "INSUFFICIENT_EVIDENCE"

    def record_prediction(
        self,
        timestamp: float,
        predicted_class: str,
        confidence: float,
        prediction_state: str,
    ) -> None:
        if not self.history:
            self.time_to_first_prediction = max(0.001, timestamp - self.created_at)
        else:
            prev_pred = self.history[-1][1]
            if prev_pred != predicted_class and prediction_state != "INSUFFICIENT_EVIDENCE":
                self.changes_count += 1

        self.history.append((timestamp, predicted_class, confidence, prediction_state))
        self.final_state = prediction_state

        # Check stability (e.g. 2 consecutive predictions of same class with KNOWN_CLASS)
        if prediction_state == "KNOWN_CLASS":
            if self.stable_prediction_class == predicted_class:
                if self.time_to_stable_prediction is None:
                    self.time_to_stable_prediction = max(0.001, timestamp - self.created_at)
            else:
                self.stable_prediction_class = predicted_class
        elif prediction_state in ("LOW_CONFIDENCE", "UNKNOWN"):
            self.stable_prediction_class = None

    def get_summary(self) -> Dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "session_id_hash": self.session_id_hash,
            "number_of_changes": self.changes_count,
            "time_to_first_prediction": round(self.time_to_first_prediction or 0.0, 4),
            "time_to_stable_prediction": round(self.time_to_stable_prediction or 0.0, 4),
            "final_state": self.final_state,
            "history_length": len(self.history),
        }


class RealTimeFlowTracker:
    """
    Tracks concurrent bidirectional flows in real-time, enforces timeouts,
    tracks prediction stability history, and notifies lifecycle listeners.
    """

    def __init__(
        self,
        idle_timeout: float = 60.0,
        active_timeout: float = 1800.0,
        min_packets_for_classification: int = 3,
        min_bytes_for_classification: int = 128,
        prediction_interval_seconds: float = 1.0,
        lifecycle_callback: Optional[Callable[[FlowLifecycleEvent], None]] = None,
    ) -> None:
        self.idle_timeout = idle_timeout
        self.active_timeout = active_timeout
        self.min_packets = min_packets_for_classification
        self.min_bytes = min_bytes_for_classification
        self.prediction_interval = prediction_interval_seconds
        self.lifecycle_callback = lifecycle_callback

        self.active_flows: Dict[FlowKey, Flow] = {}
        self.flow_last_predicted: Dict[FlowKey, float] = {}
        self.flow_ids: Dict[FlowKey, str] = {}
        self.flow_stability_map: Dict[str, FlowPredictionHistory] = {}
        self._flow_counter = 0

    def update(self, pkt: RawPacketMetadata) -> Tuple[FlowKey, Flow, bool]:
        """
        Updates the flow table with an incoming packet metadata item.
        """
        key, _ = FlowKey.from_packet(pkt)
        now = pkt.timestamp
        should_predict = False

        if key in self.active_flows:
            flow = self.active_flows[key]
            # Check timeout before adding
            if flow.is_expired(now, self.idle_timeout, self.active_timeout):
                self._notify_lifecycle(FlowLifecycleState.FLOW_EXPIRED, flow)
                flow = self._create_flow(key, pkt)
            else:
                flow.add_packet(pkt)
                self._notify_lifecycle(FlowLifecycleState.FLOW_UPDATED, flow)
        else:
            flow = self._create_flow(key, pkt)

        # Check early prediction triggers
        last_pred_time = self.flow_last_predicted.get(key, 0.0)
        time_since_pred = now - last_pred_time
        total_bytes = sum(r[1] for r in flow.packet_records)

        has_min_stats = flow.total_packets >= self.min_packets or total_bytes >= self.min_bytes
        interval_elapsed = time_since_pred >= self.prediction_interval

        if has_min_stats and interval_elapsed:
            should_predict = True
            self.flow_last_predicted[key] = now

        return key, flow, should_predict

    def _create_flow(self, key: FlowKey, pkt: RawPacketMetadata) -> Flow:
        self._flow_counter += 1
        flow_id = f"F-{self._flow_counter:05d}"
        self.flow_ids[key] = flow_id

        # Generate hashed session ID for zero-PII privacy
        session_seed = f"{pkt.src_ip}_{pkt.dst_ip}_{pkt.src_port}_{pkt.dst_port}_{pkt.timestamp}"
        sess_hash = hashlib.sha256(session_seed.encode("utf-8")).hexdigest()[:16]

        history = FlowPredictionHistory(
            flow_id=flow_id,
            session_id_hash=sess_hash,
            created_at=pkt.timestamp,
        )
        self.flow_stability_map[flow_id] = history

        flow = Flow(
            key=key,
            initiator_ip=pkt.src_ip,
            initiator_port=pkt.src_port,
            start_time=pkt.timestamp,
            last_seen=pkt.timestamp,
        )
        flow.add_packet(pkt)
        self.active_flows[key] = flow
        self._notify_lifecycle(FlowLifecycleState.FLOW_STARTED, flow)
        return flow

    def record_flow_prediction(
        self,
        flow_id: str,
        timestamp: float,
        predicted_class: str,
        confidence: float,
        prediction_state: str,
    ) -> None:
        if flow_id in self.flow_stability_map:
            self.flow_stability_map[flow_id].record_prediction(
                timestamp=timestamp,
                predicted_class=predicted_class,
                confidence=confidence,
                prediction_state=prediction_state,
            )

    def clean_stale_flows(self, current_time: Optional[float] = None) -> List[Flow]:
        """Purges and returns expired flows."""
        now = current_time or time.time()
        expired = []
        stale_keys = []

        for key, flow in self.active_flows.items():
            if flow.is_expired(now, self.idle_timeout, self.active_timeout):
                stale_keys.append(key)
                expired.append(flow)
                flow_id = self.flow_ids.get(key, "F-00000")
                if flow_id in self.flow_stability_map:
                    self.flow_stability_map[flow_id].final_state = "FLOW_COMPLETED"
                self._notify_lifecycle(FlowLifecycleState.FLOW_EXPIRED, flow)

        for k in stale_keys:
            del self.active_flows[k]
            self.flow_last_predicted.pop(k, None)
            self.flow_ids.pop(k, None)

        return expired

    def get_flow_id(self, key: FlowKey) -> str:
        return self.flow_ids.get(key, "F-00000")

    def get_session_id_hash(self, key: FlowKey) -> str:
        flow_id = self.get_flow_id(key)
        hist = self.flow_stability_map.get(flow_id)
        return hist.session_id_hash if hist else "0000000000000000"

    def get_stability_summary(self, flow_id: str) -> Dict[str, Any]:
        if flow_id in self.flow_stability_map:
            return self.flow_stability_map[flow_id].get_summary()
        return {
            "flow_id": flow_id,
            "session_id_hash": "unknown",
            "number_of_changes": 0,
            "time_to_first_prediction": 0.0,
            "time_to_stable_prediction": 0.0,
            "final_state": "UNKNOWN",
            "history_length": 0,
        }

    def get_active_flow_count(self) -> int:
        return len(self.active_flows)

    def _notify_lifecycle(self, state: FlowLifecycleState, flow: Flow) -> None:
        if self.lifecycle_callback:
            event = FlowLifecycleEvent(
                event_type=state,
                flow_id=self.flow_ids.get(flow.key, "F-00000"),
                timestamp=flow.last_seen,
                protocol=flow.key.protocol,
                total_packets=flow.total_packets,
                total_bytes=sum(r[1] for r in flow.packet_records),
                duration=flow.duration,
            )
            try:
                self.lifecycle_callback(event)
            except Exception as e:
                logger.error("Lifecycle callback error: %s", e)
