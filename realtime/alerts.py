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
    flow_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "timestamp": round(self.timestamp, 4),
            "reason": self.reason,
            "evidence": self.evidence,
            "flow_count": self.flow_count,
        }


class AlertEvaluator:
    """
    Evaluates real-time streaming telemetry and prediction distribution to fire actionable alerts.
    """

    def __init__(self) -> None:
        self._alert_counter = 0
        self.alerts_history: List[SecurityAlert] = []
        self._last_alert_time: Dict[str, float] = {}

    def evaluate_telemetry(
        self,
        recent_events: List[Any],
        dropped_packets: int = 0,
        p99_latency_ms: float = 0.0,
        pipeline_status: str = "HEALTHY",
    ) -> List[SecurityAlert]:
        alerts: List[SecurityAlert] = []
        now = time.time()

        if not recent_events and pipeline_status == "HEALTHY":
            return alerts

        # 1. Pipeline Health Failure
        if pipeline_status in ("PIPELINE_DEGRADED", "FAIL_CLOSED"):
            alert = self._create_alert(
                alert_type="PIPELINE_HEALTH_FAILURE",
                severity="CRITICAL",
                reason="Classification pipeline failed closed or degraded.",
                evidence={"status": pipeline_status},
                flow_count=0,
                cooldown_seconds=10.0,
            )
            if alert:
                alerts.append(alert)

        # 2. Packet Drop Spike
        if dropped_packets > 10:
            alert = self._create_alert(
                alert_type="PACKET_DROP_SPIKE",
                severity="HIGH",
                reason=f"High packet drop rate observed: {dropped_packets} packets dropped.",
                evidence={"dropped_packets": dropped_packets},
                flow_count=len(recent_events),
                cooldown_seconds=15.0,
            )
            if alert:
                alerts.append(alert)

        # 3. Latency Anomaly
        if p99_latency_ms > 50.0:  # > 50ms p99 is anomalous for sub-millisecond classifier
            alert = self._create_alert(
                alert_type="LATENCY_ANOMALY",
                severity="MEDIUM",
                reason=f"P99 inference latency anomaly: {p99_latency_ms:.2f}ms exceeds threshold.",
                evidence={"p99_latency_ms": p99_latency_ms},
                flow_count=len(recent_events),
                cooldown_seconds=20.0,
            )
            if alert:
                alerts.append(alert)

        # 4. Low-Confidence Spike & Unknown Traffic Spike
        if recent_events:
            total = len(recent_events)
            low_conf_count = sum(1 for e in recent_events if getattr(e, "prediction_state", "") == "LOW_CONFIDENCE")
            unknown_count = sum(1 for e in recent_events if getattr(e, "prediction_state", "") == "UNKNOWN")

            if (low_conf_count / total) > 0.60 and total >= 10:
                alert = self._create_alert(
                    alert_type="LOW_CONFIDENCE_SPIKE",
                    severity="MEDIUM",
                    reason=f"Ambiguous traffic surge: {low_conf_count}/{total} flows ({low_conf_count/total*100:.1f}%) in LOW_CONFIDENCE.",
                    evidence={"low_conf_ratio": round(low_conf_count / total, 3), "sample_size": total},
                    flow_count=low_conf_count,
                    cooldown_seconds=30.0,
                )
                if alert:
                    alerts.append(alert)

            if (unknown_count / total) > 0.30 and total >= 10:
                alert = self._create_alert(
                    alert_type="UNKNOWN_TRAFFIC_SPIKE",
                    severity="HIGH",
                    reason=f"Novel or out-of-distribution traffic burst: {unknown_count}/{total} flows rejected as UNKNOWN.",
                    evidence={"unknown_ratio": round(unknown_count / total, 3), "sample_size": total},
                    flow_count=unknown_count,
                    cooldown_seconds=30.0,
                )
                if alert:
                    alerts.append(alert)

        return alerts

    def _create_alert(
        self,
        alert_type: str,
        severity: str,
        reason: str,
        evidence: Dict[str, Any],
        flow_count: int,
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
            flow_count=flow_count,
        )
        self.alerts_history.append(alert)
        if len(self.alerts_history) > 100:
            self.alerts_history.pop(0)
        return alert
