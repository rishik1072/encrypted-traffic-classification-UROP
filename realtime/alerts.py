"""
Security Alert Generation & Telemetry Policy.

Defines alert rules for real-time cybersecurity operations:
- LOW_CONFIDENCE_SPIKE
- UNKNOWN_TRAFFIC_SPIKE
- LATENCY_ANOMALY
- PACKET_DROP_SPIKE
- PIPELINE_HEALTH_FAILURE
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SecurityAlert:
    alert_id: str
    alert_type: str
    severity: str  # INFO, LOW, MEDIUM, HIGH, CRITICAL
    timestamp: float
    reason: str
    evidence: Dict[str, Any]
    flow_id: Optional[str] = None
    flow_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "type": self.alert_type,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "timestamp": round(self.timestamp, 4),
            "flow_id": self.flow_id or "AGGREGATE",
            "reason": self.reason,
            "evidence": self.evidence,
            "metadata": self.evidence,
            "flow_count": self.flow_count,
        }


class AlertEvaluator:
    """
    Evaluates real-time streaming telemetry and prediction distribution to fire actionable alerts.
    Implements neutral, non-alarmist terminology ('Unusual traffic pattern', 'Classification uncertainty').
    """

    def __init__(
        self,
        traffic_rate_threshold: float = 1000.0,
        uncertainty_streak_threshold: int = 3,
    ) -> None:
        self.traffic_rate_threshold = traffic_rate_threshold
        self.uncertainty_streak_threshold = uncertainty_streak_threshold
        self._alert_counter = 0
        self.alerts_history: List[SecurityAlert] = []
        self._last_alert_time: Dict[str, float] = {}
        self._consecutive_uncertain = 0

    def evaluate_event(self, event: Any) -> List[SecurityAlert]:
        """
        Evaluates an individual TrafficPredictionEvent for per-flow alert triggers.
        """
        alerts: List[SecurityAlert] = []
        state = getattr(event, "prediction_state", "")
        flow_id = getattr(event, "flow_id", "UNKNOWN_FLOW")
        conf = getattr(event, "composed_confidence", None)
        if conf is None:
            conf = getattr(event, "confidence", 0.0)

        # 1. UNKNOWN prediction alert
        if state == "UNKNOWN":
            self._consecutive_uncertain += 1
            alert = self._create_alert(
                alert_type="UNKNOWN_PREDICTION",
                severity="MEDIUM",
                reason="Unusual traffic pattern: flow rejected as UNKNOWN (out-of-distribution traffic).",
                evidence={
                    "flow_id": flow_id,
                    "prediction_state": state,
                    "confidence": conf,
                    "packets_observed": getattr(event, "packets_observed", 0),
                    "protocol": getattr(event, "protocol", "UNKNOWN"),
                },
                flow_id=flow_id,
                flow_count=1,
                cooldown_seconds=5.0,
            )
            if alert:
                alerts.append(alert)

        # 2. LOW_CONFIDENCE prediction alert
        elif state == "LOW_CONFIDENCE":
            self._consecutive_uncertain += 1
            alert = self._create_alert(
                alert_type="LOW_CONFIDENCE_PREDICTION",
                severity="LOW",
                reason="Classification uncertainty: flow confidence below selective acceptance threshold.",
                evidence={
                    "flow_id": flow_id,
                    "prediction_state": state,
                    "candidate_class": getattr(event, "predicted_class", "—"),
                    "confidence": conf,
                    "packets_observed": getattr(event, "packets_observed", 0),
                },
                flow_id=flow_id,
                flow_count=1,
                cooldown_seconds=5.0,
            )
            if alert:
                alerts.append(alert)
        else:
            self._consecutive_uncertain = 0

        # 3. Repeated classification uncertainty alert
        if self._consecutive_uncertain >= self.uncertainty_streak_threshold:
            alert = self._create_alert(
                alert_type="REPEATED_UNCERTAINTY",
                severity="MEDIUM",
                reason=f"Unusual traffic pattern: repeated classification uncertainty observed ({self._consecutive_uncertain} consecutive flows).",
                evidence={
                    "consecutive_uncertain_flows": self._consecutive_uncertain,
                    "trigger_flow_id": flow_id,
                    "latest_state": state,
                },
                flow_id=flow_id,
                flow_count=self._consecutive_uncertain,
                cooldown_seconds=15.0,
            )
            if alert:
                alerts.append(alert)

        return alerts

    def evaluate_telemetry(
        self,
        recent_events: List[Any],
        dropped_packets: int = 0,
        p99_latency_ms: float = 0.0,
        packet_rate: float = 0.0,
        pipeline_status: str = "HEALTHY",
    ) -> List[SecurityAlert]:
        alerts: List[SecurityAlert] = []

        if not recent_events and pipeline_status == "HEALTHY" and packet_rate == 0.0:
            return alerts

        # 4. Configurable traffic-rate anomaly alert
        if packet_rate > self.traffic_rate_threshold:
            alert = self._create_alert(
                alert_type="TRAFFIC_RATE_ANOMALY",
                severity="HIGH",
                reason=f"Unusual traffic pattern: traffic rate of {packet_rate:.1f} pkts/s exceeds threshold ({self.traffic_rate_threshold:.1f} pkts/s).",
                evidence={
                    "packet_rate": round(packet_rate, 2),
                    "threshold": self.traffic_rate_threshold,
                },
                flow_id="AGGREGATE",
                flow_count=len(recent_events),
                cooldown_seconds=20.0,
            )
            if alert:
                alerts.append(alert)

        # Pipeline Health Failure
        if pipeline_status in ("PIPELINE_DEGRADED", "FAIL_CLOSED"):
            alert = self._create_alert(
                alert_type="PIPELINE_HEALTH_FAILURE",
                severity="CRITICAL",
                reason="Classification pipeline failed closed or degraded.",
                evidence={"status": pipeline_status},
                flow_id="SYSTEM",
                flow_count=0,
                cooldown_seconds=10.0,
            )
            if alert:
                alerts.append(alert)

        # Packet Drop Spike
        if dropped_packets > 10:
            alert = self._create_alert(
                alert_type="PACKET_DROP_SPIKE",
                severity="HIGH",
                reason=f"Unusual traffic pattern: high packet drop rate observed ({dropped_packets} dropped).",
                evidence={"dropped_packets": dropped_packets},
                flow_id="AGGREGATE",
                flow_count=len(recent_events),
                cooldown_seconds=15.0,
            )
            if alert:
                alerts.append(alert)

        # Latency Anomaly
        if p99_latency_ms > 50.0:
            alert = self._create_alert(
                alert_type="LATENCY_ANOMALY",
                severity="MEDIUM",
                reason=f"P99 inference latency anomaly: {p99_latency_ms:.2f}ms exceeds operational threshold.",
                evidence={"p99_latency_ms": p99_latency_ms},
                flow_id="SYSTEM",
                flow_count=len(recent_events),
                cooldown_seconds=20.0,
            )
            if alert:
                alerts.append(alert)

        return alerts

    def get_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent alerts as dictionaries."""
        return [a.to_dict() for a in self.alerts_history[-limit:]]

    def _create_alert(
        self,
        alert_type: str,
        severity: str,
        reason: str,
        evidence: Dict[str, Any],
        flow_id: Optional[str] = None,
        flow_count: int = 1,
        cooldown_seconds: float = 15.0,
    ) -> Optional[SecurityAlert]:
        now = time.time()
        last_t = self._last_alert_time.get(alert_type, 0.0)
        if (now - last_t) < cooldown_seconds:
            return None

        self._alert_counter += 1
        self._last_alert_time[alert_type] = now
        alert = SecurityAlert(
            alert_id=f"ALT-{self._alert_counter:05d}",
            alert_type=alert_type,
            severity=severity,
            timestamp=now,
            reason=reason,
            evidence=evidence,
            flow_id=flow_id,
            flow_count=flow_count,
        )
        self.alerts_history.append(alert)
        if len(self.alerts_history) > 100:
            self.alerts_history.pop(0)
        return alert


# Global singleton instance for cross-subsystem query
global_alert_evaluator = AlertEvaluator()

