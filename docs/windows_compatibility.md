# Windows Platform Compatibility Matrix

This document outlines the verified compatibility, operating requirements, driver dependencies, and tested network adapters for **Encrypted Traffic Monitor (v1.0.0)** on Microsoft Windows systems.

---

## 💻 Operating System Support

| OS Version | Build / Edition | Architecture | Status | Capture Backend | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Windows 11** | 22H2 / 23H2 / 24H2 (Home/Pro/Enterprise) | x64 | **Verified / Recommended** | Npcap (OEM / Free) | Full Live & Demo Mode Support |
| **Windows 10** | 21H2 / 22H2 (Home/Pro/Enterprise) | x64 | **Verified / Supported** | Npcap (OEM / Free) | Full Live & Demo Mode Support |
| **Windows Server** | 2019 / 2022 / 2025 | x64 | **Supported** | Npcap OEM | Headless & Dashboard SOC monitoring |
| **Windows ARM64** | Windows 11 on ARM (Snapdragon X) | ARM64 | **Experimental** | Npcap ARM64 | Requires x64 emulation or ARM64 Python |
| **Windows 7/8/8.1** | All | x86 / x64 | **Unsupported** | N/A | End-of-life OS; Python 3.9+ unavailable |

---

## 🔌 Packet Capture Driver Compatibility (Npcap)

Live packet capture requires the **Npcap kernel driver** (`npcap.sys` and `wpcap.dll`).

| Driver Version | Compatible | Recommended Mode | Notes |
| :--- | :--- | :--- | :--- |
| **Npcap 1.79+** | Yes | WinPcap API-compatible Mode | Default for modern Windows 11/10 |
| **Npcap 1.70 – 1.78** | Yes | WinPcap API-compatible Mode | Verified operational |
| **Npcap < 1.70** | Warning | Upgrade recommended | May experience timestamp jitter |
| **WinPcap 4.1.3** | Deprecated | Legacy only | Lacks Windows 11 WFP support |
| **No Capture Driver** | Demo Only | DEMO_MODE | Live capture fail-closed |

> [!IMPORTANT]
> When installing Npcap, you **must enable** the checkbox:
> `[X] Install Npcap in WinPcap API-compatible Mode`

---

## 📶 Network Adapter Compatibility

| Adapter Type | Hardware / Controller Examples | Capture Support | Auto-Resolution |
| :--- | :--- | :--- | :--- |
| **Wi-Fi (802.11ax/ac/n)** | Intel Wi-Fi 6 AX200/AX201/AX210/BE200, Realtek RTL8852/8821, Qualcomm FastConnect, MediaTek MT7921 | **Full** | Auto-selected by default |
| **Ethernet (GbE / 2.5GbE / 10GbE)** | Intel I219/I225/I226, Realtek PCIe GbE/2.5GbE, Broadcom NetXtreme | **Full** | Auto-selected if Wi-Fi inactive |
| **USB Wi-Fi / Ethernet Dongles** | TP-Link, Realtek USB NICs, ASIX USB Ethernet | **Full** | Dynamic hotplug detection |
| **Virtual VPN / Tunnel NICs** | Cloudflare WARP, WireGuard Tunnel, OpenVPN TAP | **Filtered** | Skipped by default to capture pre-tunnel or outer tunnel traffic correctly |
| **Virtual Loopback** | Npcap Loopback Adapter, Microsoft KM-TEST Loopback | **Supported** | Used for local synthetic test streams |

---

## 🚀 Execution Modes Comparison

| Feature | Developer Python Mode | Standalone Executable (EXE) |
| :--- | :--- | :--- |
| **Target User** | Data Scientists, ML Engineers, Researchers | SOC Analysts, System Administrators, End Users |
| **Entry Point** | `python -m product` or `python scripts/start_local.py` | `EncryptedTrafficMonitor.exe` |
| **Prerequisites** | Python 3.9+, virtualenv, dependencies | Npcap only |
| **Startup UI** | Rich CLI Banner & Diagnostics | Interactive Console & Auto-Dashboard |
| **Model Registry** | Verifies `results/models/production_registry.json` | Embedded cryptographic registry check |
| **Dashboard** | Streamlit at `http://127.0.0.1:8501` | Streamlit child process auto-opened in browser |
| **Local API** | REST on `http://127.0.0.1:8080` | REST on `http://127.0.0.1:8080` |

---

## ⚠️ Known Boundaries & Honest Limitations

1. **Administrator Elevation**: Capturing raw network packets via Npcap may require administrative privileges depending on local Npcap security options (`Restrict Npcap driver's access to Administrators only`).
2. **Encapsulated Tunnels (WARP / WireGuard)**: Fine-grained intra-application classification under outer tunnel encapsulation exhibits known homogenization (Bulk vs Interactive coarse families remain reliable).
3. **Fail-Closed Safety**: If Npcap or adapters are not available during LIVE mode, the engine reports degraded state and does not inject synthetic traffic.
