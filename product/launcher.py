"""
Encrypted Traffic Monitor - Desktop Launcher Entry Point.

Provides a user-friendly terminal interface for Windows users (double-click EXE / desktop shortcut)
with adapter selection, start/stop monitoring, demo replay, and diagnostics.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import time

# Ensure application root directory is on Python path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from product.adapter_manager import get_default_adapter, list_adapters
from product.app import ProductApplication, display_banner
from product.health import print_health_report, run_product_health_check
from product.version import APP_DESCRIPTION, APP_NAME, __version__


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def show_privacy_policy() -> None:
    clear_screen()
    print("=" * 60)
    print("ENCRYPTED TRAFFIC MONITOR — LOCAL PRIVACY POLICY")
    print("=" * 60)
    print("""
1. ZERO-PAYLOAD INSPECTION:
   Only packet lengths, directions, and inter-arrival timing
   are extracted. Application payloads are never read or stored.

2. LOCAL-ONLY OPERATION:
   All machine learning and dashboard visualization happen on
   your computer (127.0.0.1). No data is sent to the cloud.

3. NO RAW IP OR MAC PERSISTENCE:
   Network flow logs store ephemeral flow hashes, never raw IP
   addresses or hardware MAC addresses.

4. FAIL-CLOSED ARCHITECTURE:
   Live capture stops cleanly on error without synthetic injection.
""")
    print("=" * 60)
    input("\nPress Enter to return to main menu...")


def run_interactive_menu() -> None:
    app = ProductApplication()

    while True:
        clear_screen()
        display_banner()

        default_ad = get_default_adapter()
        def_name = default_ad["friendly_name"] if default_ad else "None detected"

        print("==================================================")
        print("MAIN MENU")
        print("==================================================")
        print(f"  [1] START LIVE MONITORING (Adapter: {def_name})")
        print("  [2] SELECT ADAPTER & START LIVE MONITORING")
        print("  [3] START DEMO REPLAY MODE (Synthetic Traffic)")
        print("  [4] RUN DETAILED SYSTEM HEALTH CHECK")
        print("  [5] VIEW PRIVACY GUARANTEES")
        print("  [6] EXIT")
        print("==================================================")

        try:
            choice = input("\nEnter choice [1-6] > ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == "1":
            clear_screen()
            print("[*] Launching Live Monitoring...\n")
            success = app.start(mode="live", interface=def_name)
            if success:
                try:
                    while True:
                        time.sleep(1.0)
                except KeyboardInterrupt:
                    app.stop()
                    input("\nMonitoring stopped. Press Enter to return to menu...")
            else:
                input("\nPress Enter to return to menu...")

        elif choice == "2":
            clear_screen()
            chosen_ad = app.select_adapter_interactive()
            if chosen_ad:
                print(f"\n[*] Starting Live Monitoring on {chosen_ad}...\n")
                success = app.start(mode="live", interface=chosen_ad)
                if success:
                    try:
                        while True:
                            time.sleep(1.0)
                    except KeyboardInterrupt:
                        app.stop()
                        input("\nMonitoring stopped. Press Enter to return to menu...")
                else:
                    input("\nPress Enter to return to menu...")

        elif choice == "3":
            clear_screen()
            print("==================================================")
            print("DEMO / REPLAY MODE (OFFLINE SIMULATION)")
            print("==================================================")
            print("Replaying pre-recorded research traffic flows.")
            print("Zero live packets will be captured.\n")
            success = app.start(mode="demo")
            if success:
                try:
                    while True:
                        time.sleep(1.0)
                except KeyboardInterrupt:
                    app.stop()
                    input("\nDemo stopped. Press Enter to return to menu...")
            else:
                input("\nPress Enter to return to menu...")

        elif choice == "4":
            clear_screen()
            print_health_report()
            input("Press Enter to return to menu...")

        elif choice == "5":
            show_privacy_policy()

        elif choice == "6":
            print("\nGoodbye!")
            break


def main() -> None:
    # If args passed, pass directly to app.main(), else show interactive menu
    if len(sys.argv) > 1:
        from product.app import main as app_main
        app_main()
    else:
        run_interactive_menu()


if __name__ == "__main__":
    main()
