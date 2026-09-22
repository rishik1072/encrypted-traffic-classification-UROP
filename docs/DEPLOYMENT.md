# Windows Deployment Guide

## Production Architecture

The Windows Encrypted Traffic Classification product is structured into two decoupled, robust subsystems operating entirely on `localhost`:

```text
       ┌─────────────────────────────────────────────────────────────┐
       │               Windows Host Machine (x64)                    │
       │                                                             │
       │   [Npcap / Raw Socket]  (or Simulated Replay)               │
       │             │                                               │
       │             ▼                                               │
       │   ┌─────────────────────────────────────────────────────┐   │
       │   │  EncryptedTrafficMonitor.exe / realtime.run         │   │
       │   │  - Layer 3/4 Packet Sniffer (Zero Payload)          │   │
       │   │  - Flow Tracker (5-tuple, Timeout, Directionality)  │   │
       │   │  - Feature Extractor (10 Canonical Features)        │   │
       │   │  - Model Inference Engine (LightGBM / Calibrated)   │   │
       │   │  - Abstention & Confidence Gating Policy            │   │
       │   │  - Local REST API Server (127.0.0.1:8080)           │   │
       │   └──────────────────────────┬──────────────────────────┘   │
       │                              │ JSON Events via HTTP         │
       │                              ▼ (Loopback Only)              │
       │   ┌─────────────────────────────────────────────────────┐   │
       │   │  EncryptedTrafficDashboard.exe / dashboard.app      │   │
       │   │  - Streamlit SOC Analytics Console (127.0.0.1:8501) │   │
       │   │  - Real-time KPI Tiles (TPS, P95, Abstention Rate)  │   │
       │   │  - Interactive Flow Table & PII-masked Inspector    │   │
       │   │  - Security Alert Rules & Telemetry Gauges          │   │
       │   └─────────────────────────────────────────────────────┘   │
       └─────────────────────────────────────────────────────────────┘
```

---

## Security Invariants & Isolation Controls

1. **Localhost-Only Network Binding:**
   - The REST API server rejects any non-loopback bind address. Attempts to bind to `0.0.0.0` or external network adapters are automatically intercepted and constrained to `127.0.0.1`.
   - Security headers enforced on every API response:
     - `X-Content-Type-Options: nosniff`
     - `X-Frame-Options: DENY`
     - `Cache-Control: no-store`

2. **Zero-Payload Memory & Disk Policy:**
   - The capture filter extracts packet length, direction, TCP flags, and timestamp metadata exclusively.
   - Application-layer payload bytes (TLS records, HTTP headers, DNS queries) are dropped immediately at the driver boundary.
   - The configuration flag `save_raw_packets` is hard-locked to `False`.

3. **No Raw IP or MAC Address Persistence:**
   - Event records and log entries replace physical addresses with truncated SHA-256 session identifiers (e.g., `session_id_hash: "a4f81c9b..."`).
   - The security guard `assert_zero_payload_record()` and `sanitize_event_record()` inspect every emitted event.

4. **Zero Credential & Cloud Telemetry Footprint:**
   - No external API keys, tokens, or telemetry reporting endpoints are configured or permitted.
   - `assert_no_credentials()` and `assert_no_external_telemetry()` scan runtime dictionaries and environment variables at startup.

---

## Configuration & Schema Validation

Configuration is defined in `config.yaml` or managed via `product/config.py`:

```yaml
app_name: "Encrypted Traffic Classifier"
version: "1.0.0"
local_only: true
save_raw_packets: false
minimum_packets: 5

local_api:
  host: "127.0.0.1"
  port: 8080
  workers: 1

dashboard_port: 8501
default_model: "lightgbm"
```

The system runs `validate_config_schema(cfg)` on startup. If invalid port ranges (< 1024 or > 65535), non-localhost IP bindings, or packet persistence flags are set, startup halts immediately with diagnostic errors.

---

## Process Supervision & Lifecycle Management

Process lifecycle is managed by `product.lifecycle.ProductLifecycleManager`:
- **Graceful Shutdown:** Subscribes to Windows `SIGINT`, `SIGTERM`, and `atexit`.
- **Termination Hierarchy:**
  1. Sends standard termination request (`proc.terminate()`) with a 5.0-second grace period.
  2. If a process fails to terminate, it invokes Windows `taskkill /F /T /PID <pid>` to terminate the process tree, preventing orphaned processes.
- **Immediate Restart:** Port probing confirms socket release prior to spawning replacement processes.

---

## Deployment Modes

### Mode 1: Interactive Windows Console
Open two PowerShell terminals:
```powershell
# Terminal 1: Monitor & API
python -m realtime.run --mode demo --port 8080

# Terminal 2: SOC Dashboard
streamlit run dashboard/app.py --server.port 8501 --server.address 127.0.0.1
```

### Mode 2: Headless Windows Service / Scheduled Task
For background monitoring, register a scheduled task using PowerShell:
```powershell
$action = New-ScheduledTaskAction -Execute "python.exe" -Argument "-m realtime.run --mode live --interface 'Wi-Fi'" -WorkingDirectory "C:\UROP project\encrypted-traffic-classification-UROP"
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "EncryptedTrafficMonitor" -Action $action -Trigger $trigger -Principal $principal
```

---

## Health & Status Monitoring

Query the local REST API health endpoint from any local tool:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8080/health"
```

Response schema:
```json
{
  "status": "PASS",
  "app_name": "Encrypted Traffic Classifier",
  "version": "1.0.0",
  "operating_mode": "DEMO_MODE",
  "checks": {
    "os": {"status": "PASS", "is_windows": true},
    "runtime": {"status": "PASS", "python_version": "3.14.7"},
    "model": {"status": "PASS", "model_id": "lightgbm_v1"},
    "feature_schema": {"status": "PASS"},
    "security": {"status": "PASS"}
  }
}
```
If any hardware or model integrity check fails, the API reports HTTP 503 (`Service Unavailable`) with actionable diagnostic error details.
