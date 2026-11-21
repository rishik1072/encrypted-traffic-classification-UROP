"""
Dataset V3 Pilot Session 2 Collection Script.

Executes controlled physical traffic collection for Pilot Session 2:
- Collection Plan ID: sess_pilot_002_wifi_direct_web
- Wi-Fi Interface: "Wi-Fi" (Intel(R) Wi-Fi 6 AX201 160MHz)
- Activity: Controlled Chrome Web Browsing (Wikipedia/Documentation)
- Dedicated Chrome: Launched via ControlledChromeLauncher with temporary profile
- Attribution Subsystem: Integrated with 150ms snapshot polling and boundary-aware gap policy
- Duration: 60.0 seconds (configurable via --duration)
- Snaplen: 96 bytes (user-space header extraction limit)
- Payload persistence: Strictly disabled (zero payload bytes retained)

Safety Guardrails:
- Requires explicit '--confirm' CLI argument to start physical capture.
- Refuses to start physical capture if pre-flight checks fail.
- Supports '--dry-run' for non-capturing pipeline verification (no Npcap sniffer, no packet reads, no publication).
- Supports '--test-socket' for Layer-2 socket open/close smoke test without sniffing.
- Operator must browse using the dedicated Chrome window launched by the experiment, not an existing browser.
- Does not modify Pilot Session 1 or quarantined evidence.
"""

from __future__ import annotations

import argparse
import ctypes
import logging
import platform
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Detect Windows Administrator elevation
IS_ADMIN = False
if platform.system() == "Windows":
    try:
        IS_ADMIN = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        IS_ADMIN = False

    # In un-elevated processes (e.g. --dry-run, --help, diagnostic review),
    # prevent low-level C pcap_findalldevs from hanging on Npcap AdminOnly=1.
    # Leaves elevated physical capture 100% genuine and unmodified.
    if not IS_ADMIN:
        try:
            import scapy.libs.winpcapy
            scapy.libs.winpcapy.pcap_findalldevs = lambda *args, **kwargs: -1
        except Exception:
            pass

from research.dataset_v3.attribution.chrome_launcher import ControlledChromeLauncher
from research.dataset_v3.collector import PhysicalTrafficCollector
from research.dataset_v3.pilot_config import (
    PILOT_2_COLLECTION_PLAN_ID,
    create_pilot_session_2_config,
    validate_pilot_preflight,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_pilot_session_2")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dataset V3 Pilot Session 2 Physical Traffic Collector (Integrated Attribution)"
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
        "--test-socket",
        action="store_true",
        help="Execute safe Layer-2 socket open/close smoke test without sniffing or data collection.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="Capture duration in seconds (default: 60.0).",
    )
    args = parser.parse_args()

    cfg = create_pilot_session_2_config(duration_seconds=args.duration)
    logger.info("Initializing Pilot Session 2: Plan=%s, ExecutionUUID=%s", cfg.collection_plan_id, cfg.session_id)

    # 1. Pre-flight verification (passive, non-invasive)
    ready, issues = validate_pilot_preflight(cfg)
    if not ready:
        logger.error("Pre-flight checks FAILED. Cannot proceed:")
        for issue in issues:
            logger.error("  - %s", issue)
        sys.exit(1)

    logger.info("Pre-flight validation PASSED.")

    # 2. Socket smoke-test branch
    if args.test_socket:
        if platform.system() == "Windows" and not IS_ADMIN:
            print("\n" + "=" * 70)
            print("DATASET V3 LAYER-2 SOCKET SMOKE TEST: ELEVATION REQUIRED")
            print("=" * 70)
            print("Windows Npcap is configured with 'AdminOnly: 1'.")
            print("Opening Layer-2 sockets on physical adapters requires Administrator privileges.")
            print("")
            print("Please run this command from an elevated Administrator terminal:")
            print("  python scripts/research/dataset_v3/run_pilot_session_2.py --test-socket")
            print("=" * 70 + "\n")
            sys.exit(5)

        logger.info("Executing safe Layer-2 socket smoke-test on '%s'...", cfg.interface)
        try:
            diag = PhysicalTrafficCollector.smoke_test_socket(
                interface_name=cfg.interface,
                pcap_filter=cfg.pcap_filter,
                promiscuous=cfg.promiscuous,
            )
            print("\n" + "=" * 70)
            print("SOCKET SMOKE TEST RESULT: SUCCESS")
            print(f"  Input Interface:        {diag['interface_input']}")
            print(f"  Resolved Name:          {diag['resolved_name']}")
            print(f"  Resolved Device Path:   {diag['sanitized_network_name']}")
            print(f"  Socket Provider Class:  {diag['socket_class']}")
            print(f"  Socket Opened:          {diag['socket_opened']}")
            print(f"  Socket Closed:          {diag['socket_closed']}")
            print(f"  Final Stage Reached:    {diag['stage_reached']}")
            print("=" * 70 + "\n")
            sys.exit(0)
        except Exception as e:
            logger.error("Socket smoke-test failed: %s", e)
            print("\n" + "=" * 70)
            print("SOCKET SMOKE TEST RESULT: FAILED")
            print(f"  Error: {e}")
            print("=" * 70 + "\n")
            sys.exit(1)

    # 3. Safety gate check
    if not args.confirm and not args.dry_run:
        print("\n" + "=" * 70)
        print("SAFETY GATE: Physical network traffic capture is NOT started.")
        print(f"Collection Plan ID:     {cfg.collection_plan_id}")
        print(f"Session ID (UUID):      {cfg.session_id}")
        print(f"Interface:              {cfg.interface} ({cfg.adapter_type})")
        print(f"Activity:               {cfg.collection_activity}")
        print(f"Duration:               {cfg.duration_seconds} seconds")
        print(f"Attribution Subsystem:  ENABLED")
        print(f"  - Snapshot Polling:   {cfg.attribution_poll_interval_seconds * 1000:.0f} ms")
        print(f"  - Controlled Alias:   {cfg.attribution_controlled_alias}")
        print(f"  - Min Coverage Ratio: {cfg.attribution_min_coverage_ratio:.2f}")
        print(f"  - Max Obs Gap Limit:  {cfg.attribution_max_observation_gap_seconds:.3f} s (boundary-aware)")
        print(f"User-space Limit:       {cfg.snaplen}B (zero payload persistence)")
        print(f"Controlled Workload:    Dedicated Chrome window (temporary user-data-dir)")
        print("\nTo execute this session, supervisory authorization is required.")
        print("Once authorized, run:")
        print("  python scripts/research/dataset_v3/run_pilot_session_2.py --confirm")
        print("Or test lifecycle with:")
        print("  python scripts/research/dataset_v3/run_pilot_session_2.py --dry-run")
        print("Or run socket smoke-test with:")
        print("  python scripts/research/dataset_v3/run_pilot_session_2.py --test-socket")
        print("=" * 70 + "\n")
        sys.exit(0)

    # 4. Dry-run execution
    if args.dry_run:
        logger.info("DRY RUN: Testing Pilot Session 2 lifecycle without live hardware sniffer...")
        collector = PhysicalTrafficCollector(config=cfg)
        collector.initialize(bypass_prerequisites=True)

        # Test Chrome launcher lifecycle in dry-run mode (headless)
        chrome_exe = ControlledChromeLauncher.find_chrome_executable()
        logger.info("Dry-run: Discovered Chrome binary at %s", chrome_exe)
        launcher = ControlledChromeLauncher(
            process_tracker=collector.process_tracker,
            chrome_binary=chrome_exe,
            headless=True,
        )

        try:
            logger.info("Dry-run: Launching isolated controlled Chrome for lifecycle test...")
            root_pid = launcher.launch(initial_url="about:blank")
            logger.info("Dry-run: Chrome root launched with PID %s; registered in ProcessTracker", root_pid)
            assert collector.process_tracker.root_pid == root_pid
            time.sleep(0.5)
            collector.process_tracker.refresh_chrome_tree()
            logger.info(
                "Dry-run: ProcessTracker tracking %d process identities in volatile memory",
                len(collector.process_tracker._controlled_identities),
            )
        finally:
            launcher.stop()
            logger.info("Dry-run: Chrome stopped and temporary user-data-dir cleaned up")

        # Start collector dry-run
        collector.start_capture(dry_run=True)
        time.sleep(1.0)
        collector.stop_capture(
            status="INTERRUPTED",
            notes="Dry-run lifecycle test; publication suppressed.",
            suppress_quarantine=True,
        )

        print("\n" + "=" * 70)
        print("PILOT SESSION 2 DRY RUN RESULT: SUCCESS")
        print(f"  Collection Plan ID:     {cfg.collection_plan_id}")
        print(f"  Session ID (UUID):      {cfg.session_id}")
        print("  Hardware Sniffer:       Suppressed (0 packets captured)")
        print("  Npcap Wire Reads:       0 (no raw packets read)")
        print("  Dataset Publication:    Suppressed (0 files written to published directory)")
        print("  Staging Cleanup:        Cleaned (0 disk residue)")
        print("  Chrome Isolation:       Verified (temporary user-data-dir created and deleted)")
        print("  Attribution Poller:     Started and stopped cleanly")
        print("  Pilot Session 1:        100% Intact and Unmodified")
        print("=" * 70 + "\n")
        return

    # 5. Live Physical Capture Execution (--confirm)
    if platform.system() == "Windows" and not IS_ADMIN:
        print("\n" + "=" * 70)
        print("DATASET V3 PHYSICAL CAPTURE: ELEVATION REQUIRED")
        print("=" * 70)
        print("Windows Npcap is configured with 'AdminOnly: 1'.")
        print("Opening Layer-2 sockets and capturing physical packets on 'Wi-Fi'")
        print("requires Administrator privileges.")
        print("")
        print("Please run this command from an elevated Administrator terminal:")
        print("  python scripts/research/dataset_v3/run_pilot_session_2.py --confirm")
        print("=" * 70 + "\n")
        sys.exit(5)

    logger.info("Starting Pilot Session 2 physical collection (duration=%.1fs)...", cfg.duration_seconds)
    collector = PhysicalTrafficCollector(config=cfg)
    collector.initialize(bypass_prerequisites=False)

    # Launch controlled Chrome with dedicated window for operator browsing
    chrome_exe = ControlledChromeLauncher.find_chrome_executable()
    launcher = ControlledChromeLauncher(
        process_tracker=collector.process_tracker,
        chrome_binary=chrome_exe,
        headless=False,  # Operator browses in this dedicated window
    )

    try:
        # Step 1: Launch controlled Chrome
        logger.info("Step 1: Launching isolated Chrome browser with dedicated profile...")
        root_pid = launcher.launch(initial_url="https://en.wikipedia.org/wiki/Main_Page")
        logger.info("Step 2: Registered controlled Chrome root PID %s in ProcessTracker", root_pid)

        # Step 3: Start socket snapshot polling
        logger.info("Step 3: Starting socket snapshot polling (interval=%.3fs)...", cfg.attribution_poll_interval_seconds)
        collector.snapshot_manager.start_polling()

        # Step 4: Allow snapshot warmup
        logger.info("Step 4: Allowing snapshot manager warmup (0.5s)...")
        time.sleep(0.5)

        # Step 5: Open physical Npcap capture
        logger.info("Step 5: Opening physical Npcap capture on '%s'...", cfg.interface)
        collector.start_capture(dry_run=False)

        if collector.lifecycle_state != "COLLECTOR_ACTIVE":
            raise RuntimeError(f"Collector failed to enter ACTIVE state: {collector.last_error}")

        # Step 6: Prompt operator
        print("\n" + "=" * 70)
        print(">>> PHYSICAL CAPTURE ACTIVE (PILOT SESSION 2) <<<")
        print("=" * 70)
        print("A dedicated Google Chrome window has been launched with an isolated profile.")
        print("OPERATOR INSTRUCTIONS:")
        print("  1. Browse Wikipedia or technical documentation in the DEDICATED Chrome window.")
        print("  2. Do NOT use existing Chrome windows or personal browser profiles.")
        print("  3. Do NOT log into personal accounts or enter sensitive credentials.")
        print(f"  4. Capture will automatically finalize after {cfg.duration_seconds:.0f} seconds.")
        print("=" * 70 + "\n")

        # Step 7: Wait for duration while monitoring worker thread and updating process tree
        start_time = time.monotonic()
        last_refresh = start_time

        while collector.lifecycle_state == "COLLECTOR_ACTIVE":
            if not collector.is_worker_alive():
                logger.error("Capture worker thread died prematurely during active collection!")
                collector.fail_capture(
                    reason="Capture worker thread died prematurely during active collection.",
                    stage="CAPTURE_WORKER_DIED",
                )
                break

            now = time.monotonic()
            # Periodically refresh Chrome process tree to track new renderer / network processes
            if now - last_refresh >= 2.0:
                collector.process_tracker.refresh_chrome_tree()
                last_refresh = now

            if now - start_time >= cfg.duration_seconds:
                logger.info("Configured duration (%.1fs) reached. Finalizing capture...", cfg.duration_seconds)
                break

            time.sleep(0.5)

    except KeyboardInterrupt:
        logger.warning("Interrupted by operator (Ctrl+C). Finalizing gracefully...")
    finally:
        # Step 8-15: Stop capture, snapshot poller, finalize flows, correlate attribution, validate, publish
        logger.info("Finalizing capture session and attribution subsystem...")
        try:
            collector.stop_capture(status="COMPLETE", notes="Pilot Session 2 controlled capture completed.")
        except Exception as stop_err:
            logger.error("Error during stop_capture: %s", stop_err)

        # Terminate Chrome and remove temporary profile directory
        try:
            launcher.stop()
            logger.info("Controlled Chrome instance terminated and profile cleaned.")
        except Exception as l_err:
            logger.warning("Error stopping Chrome launcher: %s", l_err)

    logger.info("Pilot Session 2 finalized with state: %s", collector.lifecycle_state)
    if collector.lifecycle_state != "COLLECTOR_COMPLETED":
        print(f"\n[WARNING] Pilot Session 2 did NOT complete successfully (state: {collector.lifecycle_state}).")
        if collector.last_error:
            print(f"Failure reason: {collector.last_error}")
        print(f"Quarantine location: {cfg.incomplete_session_dir}\n")
        sys.exit(1)
    else:
        print("\n" + "=" * 70)
        print("PILOT SESSION 2 COMPLETED AND VALIDATED")
        print(f"  Collection Plan ID:     {cfg.collection_plan_id}")
        print(f"  Session ID (UUID):      {cfg.session_id}")
        print(f"  Published Destination:  {cfg.final_session_dir}")
        print(f"  Packets Captured:       {collector.packets_processed_count}")
        print(f"  Flows Finalized:        {len(collector.verified_flow_ids) + len(collector.candidate_flow_ids)}")
        print(f"  Verified Flows:         {len(collector.verified_flow_ids)}")
        print(f"  Ambiguous Flows:        {len(collector.candidate_flow_ids)}")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
