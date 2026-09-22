# Windows Installation & Setup Guide

## Target Platform
- **Operating System:** Windows 10 / Windows 11 (64-bit Architecture, x64 / AMD64)
- **Runtime Environment:** Python 3.10+ (64-bit) or Pre-packaged Windows Executables (`dist/` binaries)
- **Privilege Level:**
  - Standard User: Sufficient for `DEMO_MODE`, Local REST API (`127.0.0.1:8080`), SOC Dashboard (`127.0.0.1:8501`), model evaluation, and installation validation.
  - Elevated Administrator: Required for `LIVE_MODE` packet sniffing via Npcap / raw sockets.

---

## Packaged Components
1. **`EncryptedTrafficMonitor.exe`**: Real-time traffic sniffer, flow tracker, zero-payload feature extractor, model inference engine, and localhost-only REST API server (`127.0.0.1:8080`).
2. **`EncryptedTrafficDashboard.exe`**: SOC Web Console running on Streamlit (`127.0.0.1:8501`), providing live telemetry, flow inspection, latency metrics, and cybersecurity alerts.
3. **`validate_installation.py`**: End-to-end automated 9-point installation and health validation test runner.

---

## Prerequisites & Driver Setup

### 1. Npcap Packet Capture Driver (Required for LIVE_MODE)
To capture live packets on Windows network adapters, Npcap must be installed:
1. Download the official installer from [Npcap.com](https://npcap.com/#download) (Version 1.70 or newer).
2. Run the installer with administrator privileges.
3. **Crucial Installation Options:**
   - Check: `Install Npcap in WinPcap API-compatible Mode` (installs `Packet.dll` into `System32`).
   - Check: `Automatically start the Npcap driver at boot time`.
   - Optional: `Restrict Npcap driver's access to Administrators only` (if required by enterprise policy).
4. Verify service status in administrative PowerShell:
   ```powershell
   Get-Service npcap
   ```

*Note: If Npcap is not installed or the user is not elevated, the system strictly enforces fail-closed behavior, refusing live capture and falling back to `DEMO_MODE` without crashing.*

### 2. Python Dependencies (Source / Developer Installation)
Install all verified production dependencies:
```powershell
pip install -r requirements.txt
```

Core dependencies verified by validation suite:
- `numpy`
- `pandas`
- `scipy`
- `scikit-learn`
- `lightgbm`
- `joblib`
- `scapy`
- `streamlit`

---

## Quickstart & Verification Command

To verify complete end-to-end system readiness, run the automated installation validation command:

```powershell
python scripts/validate_installation.py
```

The validator executes 9 comprehensive checks:
1. **Clean Installation & Filesystem Layout:** Validates runtime directories (`data/`, `models/`, `logs/`, `config/`), configuration files, and write permissions.
2. **Runtime Dependencies:** Validates availability of all 8 core packages.
3. **Model & Feature Schema Integrity:** Loads `results/models/production_registry.json`, validates SHA-256 hashes against disk weights, and performs a dry-run inference.
4. **Network Adapter Enumeration:** Discovers available physical and virtual adapters and queries Npcap service status.
5. **Local REST API (Port 8080):** Verifies socket availability and tests `127.0.0.1` binding and security headers (`X-Content-Type-Options: nosniff`).
6. **Streamlit Dashboard (Port 8501):** Validates app script syntax, port availability, and data adapter normalization contracts.
7. **DEMO Mode Execution:** Executes synthetic flows through `DemoReplayEngine` and validates the 14-field event schema and `DEMO_MODE` tag.
8. **LIVE Mode Privilege Boundary:** Probes capture driver readiness and verifies fail-closed safety under standard user permissions.
9. **Supervision, Shutdown & Restart:** Tests process startup, clean signal handling, termination of child processes, and immediate restart.

### Expected Output:
```text
========================================================================
  ENCRYPTED TRAFFIC CLASSIFIER – WINDOWS PRODUCT VALIDATION
========================================================================
[TEST 1/9] Verifying Clean Installation & Filesystem Layout...
  -> PASS: All runtime directories, config files, and write permissions verified.
[TEST 2/9] Verifying Runtime Dependency Availability...
  -> PASS: All 8 core dependencies available.
[TEST 3/9] Verifying Model Registry & Cryptographic Hash Integrity...
  -> PASS: Registered model weights & preprocessor verified; dry-run inference succeeded.
[TEST 4/9] Verifying Network Adapter Detection & Capture Readiness...
  -> PASS: 40 adapter(s) detected (Default: 'Wi-Fi').
[TEST 5/9] Verifying Local REST API Server (Port 8080)...
  -> PASS: Local REST API responds with security headers and localhost restriction.
[TEST 6/9] Verifying Streamlit SOC Dashboard Port & Contract...
  -> PASS: Dashboard app script, port binding checks, and data adapter contracts verified.
[TEST 7/9] Verifying DEMO Mode Synthetic Flow Execution...
  -> PASS: DEMO mode generated 5 events with valid 14-field schema & DEMO_MODE stamp.
[TEST 8/9] Verifying LIVE Mode Capture & Privilege Boundaries...
  -> PASS: Live capture interface & fail-closed permission boundary verified.
[TEST 9/9] Verifying Clean Process Supervision, Shutdown & Restart...
  -> PASS: Clean child process termination, PID cleanup, and rapid service restart verified.
========================================================================
  VALIDATION SUMMARY: PASS (9/9 Tests Passed - 100.0%)
========================================================================
```

---

## Running the Product

### Running in DEMO Mode (Safe, Unprivileged, Immediate Simulation)
```powershell
python -m realtime.run --mode demo --delay 0.1
```
In a separate terminal, launch the dashboard:
```powershell
streamlit run dashboard/app.py
```

### Running in LIVE Mode (Administrator Required)
Launch an elevated PowerShell (`Run as Administrator`):
```powershell
python -m realtime.run --mode live --interface "Wi-Fi"
```
And launch the dashboard:
```powershell
streamlit run dashboard/app.py
```
Open your browser at `http://127.0.0.1:8501`.
