"""
Real-Time Event Definitions, Deterministic Prediction State Machine,
and In-Memory Event Stream.
"""

from __future__ import annotations

import enum
import logging
import queue
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class FlowLifecycleState(str, enum.Enum):
    FLOW_STARTED = "FLOW_STARTED"
    FLOW_UPDATED = "FLOW_UPDATED"
    FLOW_COMPLETED = "FLOW_COMPLETED"
    FLOW_EXPIRED = "FLOW_EXPIRED"


class PredictionState(str, enum.Enum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    KNOWN = "KNOWN"
    KNOWN_CLASS = "KNOWN_CLASS"
    UNKNOWN = "UNKNOWN"
    FLOW_COMPLETED = "FLOW_COMPLETED"
    PIPELINE_DEGRADED = "PIPELINE_DEGRADED"


class OperatingMode(str, enum.Enum):
    LIVE_NPCAP = "LIVE_NPCAP"
    RECORDED_CAPTURE = "RECORDED_CAPTURE"
    DEMO_MODE = "DEMO_MODE"
    RESEARCH_MODE = "RESEARCH_MODE"

    # Backward-compatible aliases
    LIVE_MODE = "LIVE_NPCAP"
    DEMO_SIMULATION = "DEMO_MODE"
    REAL_LIVE_NPCAP = "LIVE_NPCAP"
    REAL_RECORDED_CAPTURE = "RECORDED_CAPTURE"


EVIDENCE_CLASS_MAP = {
    OperatingMode.LIVE_NPCAP.value: "REAL_LIVE_NPCAP",
    "LIVE_MODE": "REAL_LIVE_NPCAP",
    OperatingMode.RECORDED_CAPTURE.value: "REAL_RECORDED_CAPTURE",
    OperatingMode.DEMO_MODE.value: "DEMO_SIMULATION",
    "DEMO_SIMULATION": "DEMO_SIMULATION",
    OperatingMode.RESEARCH_MODE.value: "RESEARCH_BENCHMARK",
}


@dataclass
class FlowLifecycleEvent:
    """Represents a flow state transition in real-time."""
    event_type: FlowLifecycleState
    flow_id: str
    timestamp: float
    protocol: str
    total_packets: int
    total_bytes: int
    duration: float


@dataclass
class TrafficPredictionEvent:
    """
    Represents a classified flow event for the real-time stream.
    Strictly zero-payload: contains no raw payloads, unhashed IPs, MACs, or credentials.

    Canonical Fields (Exact Ordering):
    - timestamp: float epoch or iso string
    - flow_id: string
    - session_id_hash: string (hashed pseudonym)
    - model_id: string
    - feature_profile: string
    - predicted_family: string or None
    - predicted_class: string or None
    - family_confidence: float or None
    - fine_confidence: float or None
    - composed_confidence: float or None
    - prediction_state: PredictionState string
    - packets_observed: int
    - elapsed_seconds: float
    - latency_us: float
    """
    timestamp: float = 0.0
    flow_id: str = ""
    session_id_hash: str = "0000000000000000"
    model_id: str = "model_lightgbm_v1"
    feature_profile: str = "lightweight_10"
    predicted_family: Optional[str] = None
    predicted_class: Optional[str] = None
    family_confidence: Optional[float] = None
    fine_confidence: Optional[float] = None
    composed_confidence: Optional[float] = None
    prediction_state: str = PredictionState.KNOWN_CLASS.value
    packets_observed: int = 0
    elapsed_seconds: float = 0.0
    latency_us: float = 0.0
    event_id: str = ""
    prediction_version: str = "1.0.0"
    operating_mode: str = OperatingMode.LIVE_NPCAP.value
    probabilities: Dict[str, float] = field(default_factory=dict)
    protocol: str = "TCP"
    source_port: int = 0
    destination_port: int = 443
    byte_count: int = 0
    confidence: Optional[float] = None
    session_id: Optional[str] = None
    fine_classification_reason: Optional[str] = None

    def __post_init__(self):
        # Sync confidence alias with composed_confidence
        if self.confidence is not None and self.composed_confidence is None:
            self.composed_confidence = self.confidence
        elif self.composed_confidence is not None and self.confidence is None:
            self.confidence = self.composed_confidence

    @property
    def evidence_class(self) -> str:
        return EVIDENCE_CLASS_MAP.get(self.operating_mode, "UNKNOWN_EVIDENCE")

    def to_canonical_dict(self) -> Dict[str, Any]:
        """
        Returns the exact canonical 14-field dictionary matching production CSV specification:
        timestamp,flow_id,session_id_hash,model_id,feature_profile,predicted_family,predicted_class,family_confidence,fine_confidence,composed_confidence,prediction_state,packets_observed,elapsed_seconds,latency_us
        """
        return {
            "timestamp": self.timestamp,
            "flow_id": self.flow_id,
            "session_id_hash": self.session_id_hash,
            "model_id": self.model_id,
            "feature_profile": self.feature_profile,
            "predicted_family": self.predicted_family or "",
            "predicted_class": self.predicted_class or "",
            "family_confidence": self.family_confidence if self.family_confidence is not None else "",
            "fine_confidence": self.fine_confidence if self.fine_confidence is not None else "",
            "composed_confidence": self.composed_confidence if self.composed_confidence is not None else "",
            "prediction_state": self.prediction_state,
            "packets_observed": self.packets_observed,
            "elapsed_seconds": self.elapsed_seconds,
            "latency_us": self.latency_us,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Returns comprehensive event dictionary including network and security attributes."""
        import time
        eid = self.event_id
        if not eid or eid == "EVT-000000":
            eid = f"EVT-{int(time.time() * 1000)}-{time.perf_counter_ns() % 10000:04d}"
        return {
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "flow_id": self.flow_id,
            "session_id_hash": self.session_id_hash,
            "model_id": self.model_id,
            "feature_profile": self.feature_profile,
            "predicted_family": self.predicted_family,
            "predicted_class": self.predicted_class,
            "prediction": self.predicted_class,
            "family_confidence": self.family_confidence,
            "fine_confidence": self.fine_confidence,
            "composed_confidence": self.composed_confidence,
            "confidence": self.composed_confidence if self.composed_confidence is not None else self.confidence,
            "prediction_state": self.prediction_state,
            "packets_observed": self.packets_observed,
            "elapsed_seconds": self.elapsed_seconds,
            "latency_us": self.latency_us,
            "event_id": eid,
            "prediction_version": self.prediction_version,
            "operating_mode": self.operating_mode,
            "evidence_class": self.evidence_class,
            "protocol": self.protocol,
            "source_port": self.source_port,
            "destination_port": self.destination_port,
            "byte_count": self.byte_count,
            "fine_classification_reason": self.fine_classification_reason,
        }


class EventBus:
    """
    Thread-safe in-memory publish/subscribe event bus for real-time monitoring.
    """

    def __init__(self, maxsize: int = 10000) -> None:
        self._prediction_queue: queue.Queue[TrafficPredictionEvent] = queue.Queue(maxsize=maxsize)
        self._history: List[TrafficPredictionEvent] = []
        self._history_max = 500
        self._subscribers: List[Callable[[TrafficPredictionEvent], None]] = []

    def publish(self, event: TrafficPredictionEvent) -> None:
        """Publishes an event to subscribers and buffers."""
        try:
            self._prediction_queue.put_nowait(event)
        except queue.Full:
            try:
                _ = self._prediction_queue.get_nowait()
                self._prediction_queue.put_nowait(event)
            except Exception:
                pass

        self._history.append(event)
        if len(self._history) > self._history_max:
            self._history.pop(0)

        for sub in self._subscribers:
            try:
                sub(event)
            except Exception as e:
                logger.error("Subscriber error: %s", e)

    def subscribe(self, callback: Callable[[TrafficPredictionEvent], None]) -> None:
        self._subscribers.append(callback)

    def get_recent_events(self, limit: int = 50) -> List[TrafficPredictionEvent]:
        return list(reversed(self._history[-limit:]))

    def get_queue(self) -> queue.Queue[TrafficPredictionEvent]:
        return self._prediction_queue
