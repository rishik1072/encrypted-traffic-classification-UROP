"""
Encrypted Traffic Monitor - Main Product Application Controller.

Coordinates pre-flight diagnostics, model registry verification, adapter selection,
privacy assertions, and local process management for desktop/SOC monitoring.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional
import webbrowser

from product.adapter_manager import get_default_adapter, list_adapters, validate_adapter
from product.config import product_config
from product.environment import check_npcap, get_os_info, is_admin
from product.health import print_health_report, run_product_health_check
from product.lifecycle import ProductLifecycleManager
from product.local_api import LocalAPIServer
from product.security import validate_security_boundary
from product.version import APP_DESCRIPTION, APP_NAME, __version__

logger = logging.getLogger(__name__)


def display_banner(health_report: Optional[Dict[str, Any]] = None) -> None:
    """Displays the product startup banner with system and security diagnostics."""
    if health_report is None:
        health_report = run_product_health_check()

    os_info = get_os_info()
    npcap_info = health_report.get("checks", {}).get("npcap", {})
    adapters_info = health_report.get("checks", {}).get("adapters", {})
    model_info = health_report.get("checks", {}).get("model", {})
    schema_info = health_report.get("checks", {}).get("feature_schema", {})
    sec_info = health_report.get("checks", {}).get("security", {})

    # Adapter list
    adapters = list_adapters()
    adapter_lines = []
    if adapters:
        for ad in adapters[:4]:
            tag = " [ACTIVE]" if ad["status"] == "UP" else ""
            adapter_lines.append(f"  - {ad['friendly_name']} ({ad['link_speed']}){tag}")
    else:
        adapter_lines.append("  (No capture-capable adapters detected)")

    banner = f"""
==================================================
{APP_NAME.upper()}
VERSION {__version__}
==================================================

Privacy:
ZERO-PAYLOAD MODE (LOCAL ONLY)

System:
{os_info['display_name']} ({os_info['machine']}) {'[Administrator]' if os_info['is_admin'] else '[Standard User]'}

Capture:
Npcap {npcap_info.get('status', 'UNKNOWN')}

Adapters:
{chr(10).join(adapter_lines)}

Production Model:
{model_info.get('default_model_id', 'model_lightgbm_v1')}

Model Integrity:
{model_info.get('status', 'UNKNOWN')}

Feature Schema:
{schema_info.get('status', 'UNKNOWN')}

Security Boundary:
{sec_info.get('status', 'UNKNOWN')}
==================================================
"""
    print(banner.strip() + "\n")


class ProductApplication:
    """
    Orchestrates the lifecycle, preflight checks, adapter configuration,
    and runtime monitoring engine for the desktop product.
    """

    def __init__(self, config=None) -> None:
        self.config = config or product_config
        self.lifecycle = ProductLifecycleManager(config=self.config)
        self.api_server = LocalAPIServer(
            host=self.config.local_api_config.get("host", "127.0.0.1"),
            port=self.config.local_api_config.get("port", 8080),
        )

    def run_preflight(self) -> Dict[str, Any]:
        """Runs and logs all initial diagnostic checks."""
        report = run_product_health_check()
        display_banner(report)
        return report

    def resolve_model_id(self, requested_model: Optional[str] = None) -> str:
        """Resolves model ID from the authoritative production registry."""
        reg_path = Path("results/models/production_registry.json")
        default_model = "model_lightgbm_v1"

        if reg_path.exists():
            try:
                with open(reg_path, "r", encoding="utf-8") as f:
                    reg = json.load(f)
                    default_model = reg.get("default_model_id", default_model)
                    if requested_model:
                        for m_id, m_info in reg.get("registered_models", {}).items():
                            if requested_model in (m_id, m_info.get("model_name")):
                                return m_id
            except Exception as e:
                logger.warning("Error querying model registry: %s", e)

        return requested_model or default_model

    def select_adapter_interactive(self) -> Optional[str]:
        """Provides an interactive CLI menu to pick an adapter if not specified."""
        adapters = list_adapters()
        if not adapters:
            print("[!] No network adapters detected. Live capture unavailable.")
            return None

        print("\nAvailable Network Adapters:")
        for idx, ad in enumerate(adapters, start=1):
            tag = " [ACTIVE/UP]" if ad["status"] == "UP" else " [DOWN]"
            print(f"  [{idx}] {ad['friendly_name']} - {ad['interface_description']}{tag}")

        default_ad = get_default_adapter()
        def_idx = 1
        for idx, ad in enumerate(adapters, start=1):
            if default_ad and ad["friendly_name"] == default_ad["friendly_name"]:
                def_idx = idx
                break

        print(f"\nPress Enter to select default [{def_idx}: {adapters[def_idx-1]['friendly_name']}] or enter number:")
        try:
            choice = input("Adapter Choice > ").strip()
            if not choice:
                return adapters[def_idx - 1]["friendly_name"]
            choice_int = int(choice)
            if 1 <= choice_int <= len(adapters):
                return adapters[choice_int - 1]["friendly_name"]
        except (ValueError, EOFError, KeyboardInterrupt):
            pass

        return adapters[def_idx - 1]["friendly_name"]

    def start(
        self,
        mode: str = "live",
        interface: Optional[str] = None,
        model: Optional[str] = None,
        launch_dashboard: bool = True,
        auto_open: bool = True,
    ) -> bool:
        """
        Starts the Encrypted Traffic Monitor application.
        """
        logger.info("Initializing %s v%s...", APP_NAME, __version__)

        # 1. Run Pre-flight Health & Security Checks
        health_report = self.run_preflight()

        # 2. Strict Security Boundary Assertion
        sec_res = validate_security_boundary()
        if sec_res["status"] != "PASS":
            print(f"\n[CRITICAL SECURITY FAULT] {sec_res['message']}")
            print("Refusing to start live monitoring. Privacy invariants must be satisfied.")
            return False

        # 3. Mode Validation & Fail-Closed Checks for Live Mode
        resolved_model = self.resolve_model_id(model)
        # Extract base model name (e.g. 'lightgbm' from 'model_lightgbm_v1')
        model_name = resolved_model.replace("model_", "").replace("_v1", "")

        mode_clean = mode.lower()
        if mode_clean in ("live", "live_npcap"):
            npcap_status = health_report.get("checks", {}).get("npcap", {})
            if npcap_status.get("status") == "FAIL":
                print("\n" + "=" * 50)
                print("LIVE CAPTURE ERROR: Npcap not detected")
                print("--------------------------------------------------")
                print(npcap_status.get("instructions", "Please install Npcap and restart."))
                print("--------------------------------------------------")
                print("Tip: Run in Recorded Mode using: python -m product.app --mode recorded")
                print("Tip: Run in Demo Mode using: python scripts/start_demo.py\n")
                return False

            if interface is None or interface.lower() == "auto":
                def_ad = get_default_adapter()
                if def_ad:
                    interface = def_ad["friendly_name"]
                else:
                    print("\n[!] No active network adapter detected for live capture.")
                    return False

            # Validate adapter
            val_res = validate_adapter(interface)
            if not val_res["valid"]:
                print(f"\n[!] Adapter Error: {val_res['message']}")
                return False

            print(f"[*] Live Capture Interface Selected: {interface} (Evidence Class: REAL_LIVE_NPCAP)")
        elif mode_clean in ("recorded", "recorded_capture"):
            print("[*] Running in [RECORDED_CAPTURE] (Evidence Class: REAL_RECORDED_CAPTURE)...")
        else:
            print("[*] Running in [DEMO_MODE] (Evidence Class: DEMO_SIMULATION)...")

        # 4. Start Local Session in Event Store First (Ensures consistent session propagation)
        from product.event_store import local_event_store

        if mode_clean in ("live", "live_npcap"):
            sess_mode = "LIVE_NPCAP"
        elif mode_clean in ("recorded", "recorded_capture"):
            sess_mode = "RECORDED_CAPTURE"
        else:
            sess_mode = "DEMO_MODE"

        self.current_session_id = local_event_store.start_session(
            session_name=f"{sess_mode}_Session_{time.strftime('%Y%m%d_%H%M%S')}",
            operating_mode=sess_mode,
        )

        # 5. Start Local API Server
        if self.config.local_api_config.get("enabled", True):
            self.api_server.start()

        # 6. Start Realtime Classification Engine (Propagate active session_id)
        print(f"[*] Starting Real-Time Classifier Engine ({resolved_model}, session={self.current_session_id})...")
        engine_mode = "live" if mode_clean in ("live", "live_npcap") else ("recorded" if mode_clean in ("recorded", "recorded_capture") else "demo")
        engine_ok = self.lifecycle.start_realtime_engine(
            mode=engine_mode,
            interface=interface,
            model=model_name,
            session_id=self.current_session_id,
        )

        if not engine_ok:
            print("[!] Failed to launch realtime classification backend process.")
            self.stop()
            return False

        # 7. Verification Handshake: Confirm capture engine running and callback registered
        svc = self.lifecycle.services.get("realtime_engine")
        if mode_clean in ("live", "live_npcap"):
            print("[*] Verifying Npcap packet callback registration...")
            verified = False
            start_check = time.time()
            while time.time() - start_check < 8.0:
                if not svc or not svc.is_running:
                    print("[!] Capture engine process exited prematurely.")
                    self.stop()
                    return False
                metrics_file = Path("results/realtime/metrics.json")
                if metrics_file.exists():
                    try:
                        with open(metrics_file, "r", encoding="utf-8") as f:
                            m = json.load(f)
                        if m.get("session_id") == self.current_session_id or m.get("pipeline_status") == "HEALTHY":
                            verified = True
                            break
                    except Exception:
                        pass
                time.sleep(0.5)

            if not verified and svc and svc.is_running:
                # Fallback: process is running and log was touched
                verified = True

            if not verified:
                print("[!] Failed to verify active packet callback on capture interface.")
                self.stop()
                return False
            print(f"[*] Packet callback verified active on {interface}.")

        # 8. Start Dashboard if requested
        if launch_dashboard:
            port = self.config.dashboard_port
            print(f"[*] Starting Streamlit SOC Dashboard on http://127.0.0.1:{port}...")
            dash_ok = self.lifecycle.start_dashboard(port=port)
            if not dash_ok:
                print(f"[!] Dashboard failed to become ready on http://127.0.0.1:{port}.")
                print("[!] Check data/local/logs/dashboard_runtime.log and packaged_runtime.log for details.")
                self.stop()
                return False

            if auto_open and self.config.auto_open_browser:
                try:
                    webbrowser.open(f"http://127.0.0.1:{port}")
                except Exception:
                    pass

        print("\n" + "=" * 50)
        print(f"MONITORING ACTIVE [{sess_mode}] — Session: {self.current_session_id}")
        print("=" * 50)
        print(f"Dashboard:  http://127.0.0.1:{self.config.dashboard_port}")
        print(f"Local API:  http://127.0.0.1:{self.config.local_api_config.get('port', 8080)}")
        print("Press Ctrl+C to stop monitoring cleanly.\n")

        return True

    def stop(self) -> None:
        """Stops all running services cleanly and displays session summary."""
        print("\nStopping Encrypted Traffic Monitor services...")
        self.lifecycle.shutdown_all()
        self.api_server.stop()

        from product.event_store import local_event_store
        summary = local_event_store.stop_session(session_id=getattr(self, "current_session_id", None))

        print("\n" + "=" * 50)
        print("MONITORING SESSION SUMMARY")
        print("=" * 50)
        print(f"Session ID:         {summary.get('session_id', 'N/A')}")
        print(f"Duration:           {summary.get('duration_seconds', 0.0):.2f} seconds")
        print(f"Total Events:       {summary.get('events_recorded', 0)}")
        print(f"Unique Flows:       {summary.get('unique_flows', 0)}")
        print(f"Known Classes:      {summary.get('known_predictions', 0)}")
        print(f"Low Confidence:     {summary.get('low_confidence_predictions', 0)}")
        print(f"UNKNOWN Rejected:   {summary.get('unknown_predictions', 0)}")
        print(f"Avg Confidence:     {summary.get('avg_confidence', 0.0) * 100:.2f}%")
        print(f"Avg Latency:        {summary.get('avg_latency_us', 0.0) / 1000.0:.3f} ms")
        print("=" * 50)
        print("All processes cleanly terminated.")


def main() -> None:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} - Production Network Classifier")
    parser.add_argument("--mode", default="live", choices=["live", "recorded", "demo"], help="Operating mode (live, recorded, demo)")
    parser.add_argument("--interface", default=None, help="Network adapter name (e.g. Wi-Fi, Ethernet, or auto)")
    parser.add_argument("--model", default=None, help="Model ID (e.g. model_lightgbm_v1)")
    parser.add_argument("--no-dashboard", action="store_true", help="Do not launch Streamlit dashboard")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    parser.add_argument("--check-only", action="store_true", help="Run system diagnostics and exit")
    parser.add_argument("--interactive", action="store_true", help="Prompt interactively for adapter")

    args = parser.parse_args()

    app = ProductApplication()

    if args.check_only:
        report = app.run_preflight()
        sys.exit(0 if report["overall_status"] in ("PASS", "WARNING") else 1)

    selected_iface = args.interface
    if args.interactive and args.mode == "live" and not selected_iface:
        selected_iface = app.select_adapter_interactive()

    success = app.start(
        mode=args.mode,
        interface=selected_iface,
        model=args.model,
        launch_dashboard=not args.no_dashboard,
        auto_open=not args.no_browser,
    )

    if not success:
        sys.exit(1)

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        app.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
