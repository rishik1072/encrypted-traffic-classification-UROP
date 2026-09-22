# Encrypted Traffic Monitor — Windows Installation & User Guide

**Version**: 1.0.0  
**Target Platform**: Windows 10 / Windows 11 (64-bit)  
**Security Architecture**: Zero-Payload, Local-Only Machine Learning Classifier  

---

## 1. System Requirements

- **Operating System**: Windows 10 (64-bit) or Windows 11 (64-bit)
- **Processor**: Intel Core i3 / AMD Ryzen 3 or higher (x64)
- **Memory (RAM)**: Minimum 4 GB RAM (8 GB recommended)
- **Disk Space**: 500 MB free storage
- **Network Interface**: Active Wi-Fi (802.11ax/ac/n) or Ethernet adapter
- **Driver Prerequisite**: Npcap (Free or OEM edition)

---

## 2. Npcap Installation

Live packet capture on Windows requires the Npcap packet capture driver.

1. Download the latest Npcap installer from the official portal:
   👉 **https://npcap.com/#download**
2. Run `npcap-x.xx.exe`.
3. During the installation wizard, **ensure the following options are checked**:
   - `[X] Automatically start the Npcap driver at boot time`
   - `[X] Install Npcap in WinPcap API-compatible Mode` *(CRITICAL)*
4. Click **Install** and complete the wizard.
5. *(Optional)* If prompted, reboot your computer.

> [!NOTE]
> If you only wish to test the system in **DEMO MODE** (offline synthetic flow replay), Npcap is **not required**.

---

## 3. Installation

### Method A: Standalone Executable (Recommended for End Users)
1. Download the release package `EncryptedTrafficMonitor-v1.0.0-win64.zip`.
2. Extract the folder to your preferred directory (e.g. `C:\Program Files\EncryptedTrafficMonitor\` or `C:\Tools\EncryptedTrafficMonitor\`).
3. Locate `EncryptedTrafficMonitor.exe`.

### Method B: Developer Mode (From Source)
1. Ensure Python 3.9+ (64-bit) is installed.
2. Clone the repository and navigate to the project directory:
   ```cmd
   git clone https://github.com/organization/encrypted-traffic-classification.git
   cd encrypted-traffic-classification
   ```
3. Install dependencies:
   ```cmd
   pip install -r requirements.txt
   ```

---

## 4. Starting the Application

### For Standalone Executable Users:
- Double-click **`EncryptedTrafficMonitor.exe`** or run from PowerShell:
  ```powershell
  .\EncryptedTrafficMonitor.exe
  ```

### For Python Developers:
- Launch the unified product orchestrator:
  ```powershell
  python -m product
  ```
- Or run the one-command quickstart script:
  ```powershell
  python scripts/start_local.py
  ```

The application will display the startup banner:
```
==================================================
ENCRYPTED TRAFFIC MONITOR
VERSION 1.0.0
==================================================

Privacy:
ZERO-PAYLOAD MODE (LOCAL ONLY)

System:
Windows 11 (AMD64) [Administrator]

Capture:
Npcap PASS

Adapters:
  - Wi-Fi (Wi-Fi 802.11ax) [ACTIVE]
  - Ethernet (Ethernet 1 Gbps)

Production Model:
model_lightgbm_v1

Model Integrity:
PASS

Feature Schema:
PASS

Security Boundary:
PASS
==================================================
```

---

## 5. Selecting a Network Adapter

By default, Encrypted Traffic Monitor auto-detects and selects your primary active **Wi-Fi** or **Ethernet** adapter.

To explicitly select a specific adapter:
```powershell
python -m product --interface "Wi-Fi"
```
Or use the interactive selection menu by choosing **Option [2]** in the launcher.

---

## 6. Starting Monitoring

Monitoring starts automatically upon choosing Live Mode.
1. The Real-Time Classifier engine initializes the background flow tracker.
2. It verifies the cryptographic SHA-256 hash of `model_lightgbm_v1` and `preprocessor.joblib`.
3. Statistical flow features (packet size distribution, inter-arrival times, burst ratios) are calculated on-the-fly without reading payload bytes.
4. Asynchronous model inference predicts traffic categories (Web, Video, Messaging, VoIP, File Transfer, Other) with confidence gating.

---

## 7. Opening the Dashboard

The local SOC console will automatically launch in your default web browser at:
👉 **http://127.0.0.1:8501**

### Dashboard Capabilities:
- **System Status**: Shows adapter name, Npcap state, loaded model ID, and integrity hashes.
- **Live Traffic Telemetry**: Displays Packets/sec, Throughput (kbps/Mbps), Active Flows, and Queue Depth.
- **Classification Feed**: Real-time table of flows with Predicted Class, Family (Bulk/Interactive), Confidence %, and Latency (µs).
- **Abstention & Confidence**: Displays KNOWN_CLASS, LOW_CONFIDENCE, UNKNOWN, and INSUFFICIENT_EVIDENCE breakdowns.
- **Privacy Indicators**: Displays green badges for `Zero Payload: PASS` and `Local Only: PASS`.

---

## 8. Stopping Monitoring

To stop monitoring:
- In the console window, press **Ctrl + C**.
- The lifecycle manager will cleanly terminate the background packet capture engine and Streamlit dashboard child processes.
- No orphaned background processes will remain running.

---

## 9. Troubleshooting

### Issue 1: "Npcap not detected"
- **Cause**: Npcap is missing or was installed without WinPcap compatibility.
- **Fix**: Re-run the Npcap installer from https://npcap.com and verify `Install Npcap in WinPcap API-compatible Mode` is checked.

### Issue 2: "Permission Denied / Admin privileges required"
- **Cause**: Windows security policies restrict raw packet capture to elevated processes.
- **Fix**: Right-click `EncryptedTrafficMonitor.exe` (or your terminal) and select **Run as administrator**.

### Issue 3: "Port 8501 is currently in use"
- **Cause**: A previous dashboard instance is running or port 8501 is occupied.
- **Fix**: Stop the previous instance, or configure a different port in `config/product.yaml` (`dashboard_port: 8502`).

### Issue 4: Zero Packets Observed
- **Cause**: Incorrect adapter selected (e.g. inactive Ethernet instead of Wi-Fi).
- **Fix**: Run `python -m product --interactive` and choose your active internet-connected adapter.

---

## 10. Privacy Policy

- **No Payload Inspection**: The application never decodes or stores packet content.
- **No Cloud Upload**: All inference and dashboard visualization run on `127.0.0.1`.
- **No Raw IP / MAC Persistence**: Flow identifiers are anonymized hashes; IP addresses are never written to disk.
- **Immutable Safeguards**: `save_raw_packets` is hard-locked to `false`.

---

## 11. Uninstalling

### Standalone Executable:
- Simply delete the `EncryptedTrafficMonitor/` directory.

### Npcap Driver:
- Open Windows **Settings** > **Apps** > **Installed apps**.
- Find **Npcap**, click **Uninstall**, and follow the on-screen prompts.
