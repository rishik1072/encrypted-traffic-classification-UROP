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
        session_id: Optional[str] = None,
    ) -> None:
        self.idle_timeout = idle_timeout
        self.active_timeout = active_timeout
        self.min_packets = min_packets_for_classification
        self.min_bytes = min_bytes_for_classification
        self.prediction_interval = prediction_interval_seconds
        self.lifecycle_callback = lifecycle_callback
        self.session_id = session_id

        # Diagnostic counters
        self.flows_created = 0
        self.flows_updated = 0
        self.flows_eligible_for_prediction = 0

        self.active_flows: Dict[FlowKey, Flow] = {}
        self.flow_last_predicted: Dict[FlowKey, float] = {}
        self.flow_ids: Dict[FlowKey, str] = {}
        self.flow_stability_map: Dict[str, FlowPredictionHistory] = {}
        self._completed_flow_details: Dict[str, Dict[str, Any]] = {}
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
                self.flows_updated += 1
                self._notify_lifecycle(FlowLifecycleState.FLOW_UPDATED, flow)
        else:
            flow = self._create_flow(key, pkt)

        # Check prediction eligibility:
        # 1. Require at least min_packets (e.g. 3) to satisfy evidence requirements
        # 2. Trigger immediately upon achieving minimum packet evidence
        # 3. For subsequent updates, trigger periodically after prediction_interval
        last_pred_time = self.flow_last_predicted.get(key, 0.0)
        time_since_pred = now - last_pred_time

        is_first_sufficient = (flow.total_packets == self.min_packets)
        interval_elapsed = (last_pred_time == 0.0) or (time_since_pred >= self.prediction_interval)

        if flow.total_packets >= self.min_packets:
            if is_first_sufficient or interval_elapsed:
                should_predict = True
                self.flow_last_predicted[key] = now
                self.flows_eligible_for_prediction += 1

        return key, flow, should_predict

    def _create_flow(self, key: FlowKey, pkt: RawPacketMetadata) -> Flow:
        self._flow_counter += 1
        self.flows_created += 1
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
                # Cache final flow details before removal
                self._completed_flow_details[flow_id] = {
                    "flow_id": flow_id,
                    "packet_count": flow.total_packets,
                    "byte_count": sum(r[1] for r in flow.packet_records),
                    "start_time": round(flow.start_time, 4),
                    "end_time": round(flow.last_seen, 4),
                    "duration": round(flow.duration, 4),
                    "direction": {
                        "forward_packets": flow.fwd_packets,
                        "backward_packets": flow.bwd_packets,
                        "is_bidirectional": flow.fwd_packets > 0 and flow.bwd_packets > 0,
                    },
                    "protocol": flow.key.protocol,
                    "feature_readiness": flow.total_packets >= self.min_packets,
                }
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

    def get_flow_details(self, key_or_id: FlowKey | str) -> Optional[Dict[str, Any]]:
        """
        Exposes structured metadata for an active or recorded flow:
        flow_id, packet count, byte count, start time, end time, duration, direction counts, protocol, feature readiness.
        """
        target_flow: Optional[Flow] = None
        target_id: Optional[str] = None

        if isinstance(key_or_id, FlowKey):
            target_flow = self.active_flows.get(key_or_id)
            target_id = self.flow_ids.get(key_or_id)
        else:
            target_id = str(key_or_id)
            for k, fid in self.flow_ids.items():
                if fid == target_id:
                    target_flow = self.active_flows.get(k)
                    break

        if target_flow is None:
            if target_id and target_id in self._completed_flow_details:
                return self._completed_flow_details[target_id]
            return None

        flow_id = target_id or self.get_flow_id(target_flow.key)

        total_bytes = sum(r[1] for r in target_flow.packet_records)
        start_t = target_flow.start_time
        end_t = target_flow.last_seen
        dur = max(0.0, end_t - start_t)

        fwd_count = target_flow.fwd_packets
        bwd_count = target_flow.bwd_packets
        direction_summary = {
            "forward_packets": fwd_count,
            "backward_packets": bwd_count,
            "is_bidirectional": fwd_count > 0 and bwd_count > 0,
        }

        # Feature readiness: flow meets minimum statistical sample requirements
        is_ready = target_flow.total_packets >= self.min_packets or total_bytes >= self.min_bytes

        return {
            "flow_id": flow_id,
            "packet_count": target_flow.total_packets,
            "byte_count": total_bytes,
            "start_time": round(start_t, 4),
            "end_time": round(end_t, 4),
            "duration": round(dur, 4),
            "direction": direction_summary,
            "protocol": target_flow.key.protocol,
            "feature_readiness": is_ready,
        }

    def has_observed_flow(self, flow_id: str) -> bool:
        """Returns True if the flow_id corresponds to a verified observed flow."""
        return flow_id in self.flow_stability_map

    def get_flow_by_id(self, flow_id: str) -> Optional[Flow]:
        """Returns the active Flow instance corresponding to flow_id, if still active."""
        for k, fid in self.flow_ids.items():
            if fid == flow_id:
                return self.active_flows.get(k)
        return None

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

