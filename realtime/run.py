"""
Unified CLI Entry Point for Real-Time Traffic Classification.

Explicitly supports:
- LIVE_MODE: actual Wi-Fi/Ethernet capture (--mode live --interface "Wi-Fi")
- DEMO_MODE: offline simulated replay (--mode demo)
- RESEARCH_MODE: frozen dataset evaluation & experiment replay (--mode research-replay)
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from capture.packet_capture import LiveSniffer
from realtime.classifier import RealTimeClassifier
from realtime.demo_mode import DemoReplayEngine
from realtime.events import OperatingMode

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("realtime_runner")


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-Time Encrypted Traffic Classification Runner.")
    parser.add_argument(
        "--mode",
        default="demo",
        choices=["live", "demo", "research-replay"],
        help="Operating mode: live (NIC capture), demo (synthetic replay), research-replay (frozen dataset)",
    )
    parser.add_argument("--interface", default=None, help="Live network interface (e.g. Wi-Fi, Ethernet)")
    parser.add_argument(
        "--model",
        default="lightgbm",
        choices=["logistic_regression", "decision_tree", "random_forest", "lightgbm"],
    )
    parser.add_argument("--duration", type=float, default=None, help="Capture duration in seconds")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.getLogger().setLevel(getattr(logging, args.log_level))

    mode_map = {
        "live": OperatingMode.LIVE_MODE.value,
        "demo": OperatingMode.DEMO_MODE.value,
        "research-replay": OperatingMode.RESEARCH_MODE.value,
    }
    op_mode = mode_map.get(args.mode, OperatingMode.DEMO_MODE.value)

    logger.info("=== INITIALIZING REAL-TIME ENCRYPTED TRAFFIC CLASSIFIER ===")
    logger.info("Operating Mode: [%s] | Inference Model: %s", op_mode, args.model)

    classifier = RealTimeClassifier(config_path=args.config, operating_mode=op_mode)
    classifier.model_name = args.model
    classifier.start()

    def _shutdown_handler(sig, frame):
        logger.info("Shutdown signal received. Stopping classifier...")
        classifier.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown_handler)

    try:
        if args.mode == "demo":
            logger.info("Starting in [DEMO_MODE] replay stream...")
            engine = DemoReplayEngine(classifier=classifier, flow_delay_seconds=0.15)
            engine.replay_from_csv(max_events=50, loop=False)
        elif args.mode == "research-replay":
            logger.info("Starting in [RESEARCH_MODE] benchmark replay...")
            engine = DemoReplayEngine(classifier=classifier, flow_delay_seconds=0.05)
            engine.replay_from_csv(
                features_csv_path="data/processed/features/features_cleaned.csv",
                max_events=60,
                loop=False,
            )
        elif args.mode == "live":
            logger.info("Starting in [LIVE_MODE] on interface: %s...", args.interface)
            sniffer = LiveSniffer(interface=args.interface)
            try:
                sniffer.start_sniffing(
                    callback=classifier.process_packet,
                    duration_seconds=args.duration,
                )
            except PermissionError:
                logger.error("[PERMISSION ERROR] Live packet sniffing requires administrator/root privileges.")
                logger.info("Hint: Run in Demo Mode using: python -m realtime.run --mode demo")
            except Exception as e:
                logger.error("Live capture failed: %s", e)
    finally:
        classifier.stop()
        logger.info("Classifier terminated cleanly.")


if __name__ == "__main__":
    main()
