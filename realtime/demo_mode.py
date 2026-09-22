"""
Offline Demo / Replay Mode Engine.

Replays recorded flow features or synthetic packet sequences to simulate real-time traffic
without requiring live network interfaces or elevated privileges.
Strictly tags events as DEMO_MODE.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from realtime.classifier import RealTimeClassifier
from realtime.events import OperatingMode, PredictionState, TrafficPredictionEvent

logger = logging.getLogger(__name__)


class DemoReplayEngine:
    """
    Replays flow events through the real-time classification pipeline under DEMO_MODE.
    """

    def __init__(
        self,
        classifier: RealTimeClassifier,
        flow_delay_seconds: float = 0.2,
    ) -> None:
        self.classifier = classifier
        self.classifier.operating_mode = OperatingMode.DEMO_MODE.value
        self.flow_delay_seconds = flow_delay_seconds
        self._is_running = False

    def replay_from_csv(
        self,
        features_csv_path: str | Path = "data/processed/features/features.csv",
        max_events: int = 100,
        loop: bool = False,
    ) -> List[TrafficPredictionEvent]:
        """Replays pre-computed feature rows through the online model loader with GT comparison."""
        csv_file = Path(features_csv_path)
        if not csv_file.exists():
            raise FileNotFoundError(f"Feature dataset not found for replay: {csv_file}")

        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            logger.warning("No rows to replay in %s", csv_file)
            return []

        model_meta = self.classifier.model_loader.model_metadata
        m_id = model_meta.get("model_id", f"model_{self.classifier.model_name}_v1")
        m_type = model_meta.get("model_type", self.classifier.model_name)
        f_prof = model_meta.get("feature_profile", "lightweight_10")

        logger.info("[DEMO_MODE] Operating Mode: DEMO_MODE")
        logger.info("[DEMO_MODE] Production Model: %s", m_id)
        logger.info("[DEMO_MODE] Model Type: %s", m_type)
        logger.info("[DEMO_MODE] Feature Profile: %s", f_prof)
        logger.info("[DEMO_MODE] Starting replay of %d flows...", len(rows))
        self._is_running = True
        generated_events: List[TrafficPredictionEvent] = []

        # Diagnostics & Metrics tracking
        latencies_us: List[float] = []
        warmup_latency_us: Optional[float] = None
        correct_count = 0
        total_predictions = 0
        known_count = 0
        low_conf_count = 0
        unknown_count = 0
        insuf_count = 0

        # For macro-F1 calculation
        class_names = list(self.classifier.model_loader.class_names)
        confusion_counts = {c: {"tp": 0, "fp": 0, "fn": 0} for c in class_names}

        try:
            count = 0
            while self._is_running:
                for row in rows:
                    if not self._is_running or (max_events > 0 and count >= max_events):
                        break

                    # Extract ground truth from row or flow_id prefix
                    gt_class = row.get("traffic_class")
                    if not gt_class:
                        fid_lower = row.get("flow_id", "").lower()
                        if fid_lower.startswith("web"):
                            gt_class = "Web"
                        elif fid_lower.startswith("video"):
                            gt_class = "Video"
                        elif fid_lower.startswith("msg"):
                            gt_class = "Messaging"
                        elif fid_lower.startswith("voip"):
                            gt_class = "VoIP"
                        elif fid_lower.startswith("file"):
                            gt_class = "File Transfer"
                        elif fid_lower.startswith("other"):
                            gt_class = "Other"
                        else:
                            gt_class = "Other"

                    # Classify row through model loader
                    t0 = time.perf_counter()
                    pred_class, conf, probs = self.classifier.model_loader.predict_single(row)
                    t1 = time.perf_counter()
                    lat_us = (t1 - t0) * 1_000_000.0
                    lat_ms = lat_us / 1000.0

                    if warmup_latency_us is None:
                        warmup_latency_us = lat_us
                    else:
                        latencies_us.append(lat_us)

                    count += 1
                    flow_id = row.get("flow_id", f"DEMO-F-{count:05d}")
                    pkts = int(float(row.get("total_packet_count", 10)))
                    bytes_cnt = int(float(row.get("total_bytes", 5000)))

                    bulk_classes = {"File Transfer", "Video"}
                    interactive_classes = {"Web", "Messaging", "VoIP"}

                    # Compute coarse family and confidences
                    prob_bulk = sum(probs.get(c, 0.0) for c in bulk_classes)
                    prob_inter = sum(probs.get(c, 0.0) for c in interactive_classes)
                    prob_other = probs.get("Other", 0.0)

                    if pred_class in bulk_classes:
                        coarse_family = "Bulk_Streaming"
                        family_conf = prob_bulk if prob_bulk > 0.0 else conf
                        fine_conf = probs.get(pred_class, conf)
                    elif pred_class in interactive_classes:
                        coarse_family = "Interactive"
                        family_conf = prob_inter if prob_inter > 0.0 else conf
                        fine_conf = probs.get(pred_class, conf)
                    elif pred_class == "Other":
                        coarse_family = "Other"
                        family_conf = prob_other if prob_other > 0.0 else conf
                        fine_conf = probs.get("Other", conf)
                    else:
                        coarse_family = None
                        family_conf = None
                        fine_conf = None

                    if family_conf is not None and fine_conf is not None:
                        composed_conf = round(float(family_conf * fine_conf), 4)
                    else:
                        composed_conf = round(float(conf), 4)

                    if pkts < 5:
                        state = PredictionState.INSUFFICIENT_EVIDENCE.value
                        pred_class_out = None
                        coarse_family_out = None
                        family_conf = None
                        fine_conf = None
                        composed_conf = None
                        insuf_count += 1
                    elif family_conf is not None and family_conf < 0.35:
                        state = PredictionState.UNKNOWN.value
                        coarse_family_out = "UNKNOWN"
                        pred_class_out = None
                        unknown_count += 1
                    elif composed_conf is not None and composed_conf < self.classifier.confidence_threshold:
                        state = PredictionState.LOW_CONFIDENCE.value
                        coarse_family_out = coarse_family
                        pred_class_out = pred_class
                        low_conf_count += 1
                    else:
                        state = PredictionState.KNOWN_CLASS.value
                        coarse_family_out = coarse_family
                        pred_class_out = pred_class
                        known_count += 1

                    total_predictions += 1
                    is_correct = (pred_class_out == gt_class) if pred_class_out else False
                    if is_correct:
                        correct_count += 1

                    # Update confusion stats
                    if gt_class in confusion_counts:
                        if is_correct:
                            confusion_counts[gt_class]["tp"] += 1
                        else:
                            confusion_counts[gt_class]["fn"] += 1
                    if pred_class_out and pred_class_out in confusion_counts and not is_correct:
                        confusion_counts[pred_class_out]["fp"] += 1

                    sess_seed = f"demo_session_{count}_{time.time()}"
                    sess_hash = hashlib.sha256(sess_seed.encode("utf-8")).hexdigest()[:16]

                    model_id = self.classifier.model_loader.model_metadata.get("model_id", f"model_{self.classifier.model_name}_v1")
                    feature_profile = self.classifier.model_loader.model_metadata.get("feature_profile", "lightweight_10")
                    model_ver = self.classifier.model_loader.model_metadata.get("model_version", "1.0.0")

                    event = TrafficPredictionEvent(
                        timestamp=time.time(),
                        flow_id=flow_id,
                        session_id_hash=sess_hash,
                        model_id=model_id,
                        feature_profile=feature_profile,
                        predicted_family=coarse_family_out,
                        predicted_class=pred_class_out,
                        family_confidence=family_conf,
                        fine_confidence=fine_conf,
                        composed_confidence=composed_conf,
                        prediction_state=state,
                        packets_observed=pkts,
                        elapsed_seconds=float(row.get("flow_duration", 1.5)),
                        latency_us=lat_us,
                        event_id=f"DEMO-EVT-{count:05d}",
                        prediction_version=model_ver,
                        operating_mode=OperatingMode.DEMO_MODE.value,
                        protocol=row.get("protocol", "TCP"),
                        source_port=int(float(row.get("dst_port", 443))) + 1000,
                        destination_port=int(float(row.get("dst_port", 443))),
                        byte_count=bytes_cnt,
                        probabilities=probs,
                    )

                    self.classifier.flow_tracker.record_flow_prediction(
                        flow_id=flow_id,
                        timestamp=event.timestamp,
                        predicted_class=pred_class_out or "—",
                        confidence=composed_conf or 0.0,
                        prediction_state=state,
                    )

                    self.classifier.metrics_collector.record_packet(event.byte_count)
                    self.classifier.metrics_collector.record_prediction(lat_ms, prediction_state=state)
                    self.classifier.event_bus.publish(event)
                    self.classifier._persist_event(event)
                    generated_events.append(event)

                    conf_pct = (event.composed_confidence * 100.0) if event.composed_confidence is not None else 0.0
                    correct_tag = "YES" if is_correct else "NO"
                    logger.info(
                        "[DEMO_MODE] Flow %s -> Ground Truth: %s | Pred: %s | Correct: %s | Family: %s | State: %s | Conf: %.1f%% | Latency: %.2fus",
                        event.flow_id, gt_class, event.predicted_class or "—", correct_tag, event.predicted_family or "—", event.prediction_state, conf_pct, event.latency_us
                    )

                    time.sleep(self.flow_delay_seconds)

                if not loop or (max_events > 0 and count >= max_events):
                    break
        finally:
            self._is_running = False

        # Compute summary metrics
        acc_pct = (correct_count / (total_predictions or 1)) * 100.0
        f1_list = []
        for c, counts in confusion_counts.items():
            tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            f1_list.append(f1)
        macro_f1 = sum(f1_list) / (len(f1_list) or 1)

        steady_latencies = sorted(latencies_us) if latencies_us else [warmup_latency_us or 0.0]
        p50 = steady_latencies[int(len(steady_latencies) * 0.50)]
        p95 = steady_latencies[int(len(steady_latencies) * 0.95)]

        summary_banner = f"""
==================================================
DEMO REPLAY SUMMARY
==================================================
Model:           {m_id}
Feature Profile: {f_prof}

Flows:           {total_predictions}
Correct:         {correct_count}
Accuracy:        {acc_pct:.1f}%
Macro-F1:        {macro_f1:.4f}

Known:           {known_count}
Low Confidence:  {low_conf_count}
Unknown:         {unknown_count}

Warmup Latency:   {warmup_latency_us or 0.0:.2f} us
Steady-State P50: {p50:.2f} us
Steady-State P95: {p95:.2f} us
==================================================
"""
        logger.info(summary_banner.strip())
        logger.info("[DEMO_MODE] Finished replaying %d events.", len(generated_events))
        return generated_events


    def stop(self) -> None:
        self._is_running = False


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real-time traffic classification in Demo / Replay mode.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--input", default="data/processed/features/features.csv", help="Features CSV to replay")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between replayed flows (seconds)")
    parser.add_argument("--count", type=int, default=20, help="Number of flows to replay")
    args = parser.parse_args()

    classifier = RealTimeClassifier(config_path=args.config, operating_mode=OperatingMode.DEMO_MODE.value)
    classifier.start()

    engine = DemoReplayEngine(classifier=classifier, flow_delay_seconds=args.delay)
    try:
        engine.replay_from_csv(features_csv_path=args.input, max_events=args.count)
    finally:
        classifier.stop()


if __name__ == "__main__":
    main()
