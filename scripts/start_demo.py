"""
One-Command Demo Replay Startup Script.

Launches the offline demo simulation replay engine and Streamlit SOC dashboard.
Visibly labels DEMO / REPLAY MODE without capturing live packets.
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

from product.app import ProductApplication


def main() -> None:
    parser = argparse.ArgumentParser(description="Start Encrypted Traffic Monitor in Demo Replay Mode")
    parser.add_argument("--model", default="model_lightgbm_v1", help="Production model ID")
    parser.add_argument("--no-dashboard", action="store_true", help="Run headlessly without dashboard")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    args = parser.parse_args()

    print("=" * 60)
    print("DEMO / REPLAY MODE (SYNTHETIC FLOW SIMULATION)")
    print("=" * 60)
    print("[*] Replaying pre-recorded research traffic flows.")
    print("[*] No live network packets will be inspected.")
    print("[*] Zero live capture drivers required.")
    print("=" * 60 + "\n")

    app = ProductApplication()
    success = app.start(
        mode="demo",
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
        print("\nDemo session ended.")
        sys.exit(0)


if __name__ == "__main__":
    main()
