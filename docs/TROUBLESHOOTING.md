# Windows Troubleshooting Guide

This guide details common operational issues, diagnostics, and remediation procedures for the Encrypted Traffic Classification product on Windows 10/11 x64.

---

## 1. Npcap Driver & Capture Errors

### Symptom: `WARNING: No libpcap provider available ! pcap won't be used` or `Npcap driver service is not running`
- **Root Cause:** The Npcap capture driver (`npcap.sys`) is not installed, the Npcap service is stopped, or the driver was installed without "WinPcap API-compatible Mode".
- **Diagnosis:**
  Run the automated diagnostic check:
  ```powershell
  python -c "from product.environment import check_npcap; import json; print(json.dumps(check_npcap(), indent=2))"
  ```
  Or check the Windows service state in PowerShell:
  ```powershell
  Get-Service npcap
  ```
- **Remediation:**
  1. If service is stopped, start it from an elevated PowerShell:
     ```powershell
     Start-Service npcap
     ```
  2. If Npcap is missing, download and install [Npcap](https://npcap.com/#download) with the **"Install Npcap in WinPcap API-compatible Mode"** checkbox checked.
  3. Verify `Packet.dll` exists in `C:\Windows\System32\Packet.dll` or `C:\Windows\SysWOW64\Packet.dll`.

---

## 2. Administrator Elevation & Raw Socket Permissions

### Symptom: `OSError: Windows native L3 Raw sockets are only usable as administrator`
- **Root Cause:** On Windows, raw network socket operations (fallback when Npcap is not present) strictly require administrative privileges.
- **Diagnosis:**
  ```powershell
  python -c "from product.environment import is_admin; print('Is Administrator:', is_admin())"
  ```
- **Remediation:**
  - Open PowerShell with **"Run as Administrator"**.
  - Or use **`DEMO_MODE`** (`python -m realtime.run --mode demo`), which replays synthetic packet flows in unprivileged user space.

---

## 3. Port Conflicts (Port 8080 or Port 8501)

### Symptom: `Port 8080 is currently occupied by another process` or `Address already in use`
- **Root Cause:** A prior instance of `EncryptedTrafficMonitor` or another local service (e.g., IIS, Tomcat, proxy) is using port 8080 or 8501.
- **Diagnosis:**
  Check which PID is listening on the port:
  ```powershell
  netstat -ano | findstr :8080
  netstat -ano | findstr :8501
  ```
- **Remediation:**
  1. Identify and cleanly terminate the conflicting process:
     ```powershell
     taskkill /PID <PID> /F
     ```
  2. If another legitimate service requires port 8080 or 8501, adjust the port in `config.yaml`:
     ```yaml
     local_api:
       port: 8088
     dashboard_port: 8510
     ```

---

## 4. Model Integrity & Cryptographic Hash Verification Failure

### Symptom: `Model checksum mismatch: expected <hash>, got <hash>` or `PIPELINE_DEGRADED`
- **Root Cause:** The serialized model file in `results/models/` has been altered, corrupted, or replaced with an unverified checkpoint.
- **Diagnosis:**
  Run the validation tool:
  ```powershell
  python scripts/validate_installation.py
  ```
  Inspect check 3 output for the expected vs. actual SHA-256 hash.
- **Remediation:**
  1. Inspect `results/models/production_registry.json` to verify the registered hash.
  2. Restore the authoritative model checkpoint from source control or regenerate via:
     ```powershell
     python -m experiments.research_baseline.run
     ```
  3. Re-run `python scripts/validate_installation.py` to confirm the model passes integrity verification.

---

## 5. Dashboard SOC Console Shows "API Unavailable"

### Symptom: Red status badge on dashboard header: `API Unavailable (Offline)`
- **Root Cause:** The Streamlit dashboard (`EncryptedTrafficDashboard`) cannot reach the REST API server at `http://127.0.0.1:8080/health`.
- **Diagnosis:**
  1. Test API reachability from PowerShell:
     ```powershell
     curl -i http://127.0.0.1:8080/health
     ```
  2. Check if the monitor process is running:
     ```powershell
     Get-Process -Name "*python*" | Select-Object Id, ProcessName, MainWindowTitle
     ```
- **Remediation:**
  1. Start the monitor process first:
     ```powershell
     python -m realtime.run --mode demo
     ```
  2. Once the monitor logs `[REST API] Listening on http://127.0.0.1:8080`, launch the dashboard:
     ```powershell
     streamlit run dashboard/app.py
     ```

---

## 6. Inspecting Diagnostic Logs

All runtime events, socket operations, and errors are written to rotating log files under `logs/`:
- `logs/monitor.log`: Monitor engine, packet sniffer, flow tracker, and classification logs.
- `logs/api.log`: REST API request logs, client endpoints, and health check calls.
- `logs/dashboard.log`: Streamlit supervisor, port bindings, and UI adapter errors.

To view live log output in PowerShell:
```powershell
Get-Content -Path logs/monitor.log -Wait -Tail 30
```

---

## 7. Fast Diagnostic Command

To perform a complete environment and product health check in a single command:
```powershell
python scripts/validate_installation.py
```
If all 9 tests show `PASS`, the installation and runtime boundaries are 100% healthy.
