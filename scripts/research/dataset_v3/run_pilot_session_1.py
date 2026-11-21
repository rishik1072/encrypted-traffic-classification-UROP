"""
Dataset V3 Pilot Session 1 Collection Script.

Executes controlled physical traffic collection for Pilot Session 1:
- Wi-Fi Interface: "Wi-Fi" (Intel(R) Wi-Fi 6 AX201 160MHz)
- Activity: Active Chrome Web Browsing
- Duration: 60.0 seconds
- Snaplen: 96 bytes

Safety Guardrails:
- Requires explicit '--confirm' CLI argument to start physical capture.
- Verifies that existing production capture processes do not run concurrently on the same interface.
- Refuses to start if pre-flight checks fail.
- Supports '--dry-run' for non-capturing pipeline verification (does not sniff wire or publish data).
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research.dataset_v3.collector import PhysicalTrafficCollector
from research.dataset_v3.pilot_config import create_pilot_session_1_config, validate_pilot_preflight

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_pilot_session_1")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dataset V3 Pilot Session 1 Physical Traffic Collector"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Explicit operator confirmation to initiate physical capture.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute lifecycle verification without starting physical Npcap sniffer.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="Capture duration in seconds (default: 60.0).",
    )
    args = parser.parse_args()

    cfg = create_pilot_session_1_config(duration_seconds=args.duration)
    logger.info("Initializing Pilot Session 1: Plan=%s, ExecutionUUID=%s", cfg.collection_plan_id, cfg.session_id)

    # 1. Pre-flight verification
    ready, issues = validate_pilot_preflight(cfg)
    if not ready:
        logger.error("Pre-flight checks FAILED. Cannot proceed:")
        for issue in issues:
            logger.error("  - %s", issue)
        sys.exit(1)

    logger.info("Pre-flight validation PASSED.")

    # 2. Safety confirmation gate
    if not args.confirm and not args.dry_run:
        print("\n" + "=" * 70)
        print("SAFETY GATE: Physical network traffic capture is NOT started.")
        print(f"Collection Plan ID: {cfg.collection_plan_id}")
        print(f"Session ID (UUID):  {cfg.session_id}")
        print(f"Interface:          {cfg.interface} ({cfg.adapter_type})")
        print(f"Activity:           {cfg.collection_activity}")
        print(f"Duration:           {cfg.duration_seconds} seconds")
        print(f"User-space Limit:   {cfg.snaplen}B (user-space parser limit, NOT Npcap kernel snaplen)")
        print(f"Native Wire Length: UNAVAILABLE unless supplied by backend")
        print("\nTo execute this session, supervisory authorization is required.")
        print("Once authorized, run:")
        print("  python scripts/research/dataset_v3/run_pilot_session_1.py --confirm")
        print("Or test with:")
        print("  python scripts/research/dataset_v3/run_pilot_session_1.py --dry-run")
        print("=" * 70 + "\n")
        sys.exit(0)

    # 3. Collector initialization
    collector = PhysicalTrafficCollector(config=cfg)
    collector.initialize(bypass_prerequisites=args.dry_run)

    if args.dry_run:
        logger.info("DRY RUN: Testing collector lifecycle without starting sniffer or publishing dataset...")
        collector.start_capture(dry_run=True)
        time.sleep(1.0)
        collector.stop_capture(status="INTERRUPTED", notes="Dry-run lifecycle test; publication suppressed.")
        # Ensure zero publication or residue for this dry-run session
        import shutil
        if cfg.staging_session_dir and cfg.staging_session_dir.exists():
            shutil.rmtree(cfg.staging_session_dir, ignore_errors=True)
        if cfg.incomplete_session_dir and cfg.incomplete_session_dir.exists():
            shutil.rmtree(cfg.incomplete_session_dir, ignore_errors=True)
        if cfg.final_session_dir.exists():
            shutil.rmtree(cfg.final_session_dir, ignore_errors=True)
        logger.info("Dry run completed successfully with zero published datasets.")
        return

    # 4. Live Physical Capture
    logger.info("Starting physical capture initialization for %.1f seconds...", cfg.duration_seconds)

    try:
        collector.start_capture(dry_run=False)
    except Exception as e:
        logger.error("Physical capture initialization failed: %s", e)
        print(f"\n[FATAL] Physical capture failed to initialize: {e}\n")
        sys.exit(1)

    if collector.lifecycle_state != "COLLECTOR_ACTIVE":
        logger.error(
            "Collector did not enter ACTIVE state (state=%s): %s",
            collector.lifecycle_state,
            collector.last_error,
        )
        print(f"\n[FATAL] Collector failed to start: {collector.last_error}\n")
        sys.exit(1)

    logger.info("Physical capture successfully initialized and verified active.")
    print("\n>>> CAPTURE ACTIVE. Please open Chrome and browse target pages now. <<<")
    print(f">>> Capture will automatically stop after {cfg.duration_seconds} seconds. <<<\n")

    try:
        # Wait for duration timer to finish while actively monitoring worker thread
        while collector.lifecycle_state == "COLLECTOR_ACTIVE":
            if not collector.is_worker_alive():
                logger.error("Capture worker thread died prematurely during active collection!")
                collector.fail_capture(
                    reason="Capture worker thread died prematurely during active collection.",
                    stage="CAPTURE_WORKER_DIED",
                )
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.warning("Interrupted by operator (Ctrl+C). Finalizing gracefully...")
        collector.stop_capture(status="INTERRUPTED", notes="Manually interrupted by operator.")

    logger.info("Pilot Session 1 finalized with state: %s", collector.lifecycle_state)
    if collector.lifecycle_state != "COLLECTOR_COMPLETED":
        print(f"\n[WARNING] Pilot session did NOT complete successfully (state: {collector.lifecycle_state}).")
        if collector.last_error:
            print(f"Failure reason: {collector.last_error}")
        print(f"Quarantine location: {cfg.incomplete_session_dir}\n")
        sys.exit(1)
    else:
        print(f"\n[SUCCESS] Pilot session completed and validated: {cfg.final_session_dir}\n")


if __name__ == "__main__":
    main()
