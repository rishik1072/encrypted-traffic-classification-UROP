"""
One-Command Developer and User Live Startup Script.

Runs health checks, automatically resolves the active Wi-Fi or Ethernet adapter,
and launches the live realtime engine and local SOC dashboard.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from product.adapter_manager import get_default_adapter
from product.app import ProductApplication


def main() -> None:
    parser = argparse.ArgumentParser(description="Start Live Encrypted Traffic Monitoring")
    parser.add_argument("--interface", default=None, help="Network adapter (default: auto)")
    parser.add_argument("--model", default="model_lightgbm_v1", help="Production model ID")
    parser.add_argument("--no-dashboard", action="store_true", help="Run headlessly without dashboard")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    args = parser.parse_args()

    app = ProductApplication()
    chosen_iface = args.interface
    if not chosen_iface or chosen_iface.lower() == "auto":
        default_ad = get_default_adapter()
        if default_ad:
            chosen_iface = default_ad["friendly_name"]

    print("=" * 60)
    print("STARTING LOCAL LIVE ENCRYPTED TRAFFIC MONITOR")
    print("=" * 60)

    success = app.start(
        mode="live",
        interface=chosen_iface,
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
        print("\nShutdown complete.")
        sys.exit(0)


if __name__ == "__main__":
    main()
