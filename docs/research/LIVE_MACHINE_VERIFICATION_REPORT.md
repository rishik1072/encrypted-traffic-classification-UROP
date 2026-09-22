# Physical Live-Npcap Machine Verification Report

**Authoritative File:** `docs/research/LIVE_MACHINE_VERIFICATION_REPORT.md`  
**Execution Timestamp:** `2026-09-22T21:20:41+05:30`  
**Evaluation Mode:** `LIVE_NPCAP` (Direct Physical Ingestion via Npcap)  
**Required Evidence Class:** `REAL_LIVE_NPCAP`  

---

## 1. Executive Verdict

```
========================================================================================
FINAL VERIFICATION STATUS:
  LIVE MACHINE VERIFICATION FAILED

  live_machine_verified = false
  implementation_status = IMPLEMENTATION READY

EXACT BLOCKING REASON:
  1. Npcap Driver Absent: Npcap packet capture driver was not detected on this system
     (npcap.sys and wpcap.dll are missing from System32).
  2. Insufficient Privileges: Process executed with standard user permissions without
     administrative elevation required for raw network socket binding.

NON-NEGOTIABLE RULE ENFORCED:
  The system strictly failed closed (exit code 1) without falling back to DEMO_MODE,
  without replaying RECORDED_CAPTURE data, and without fabricating live packet captures.
========================================================================================
```

---

## 2. Host Machine Diagnostics & Hardware Telemetry

| Parameter | Workstation Measurement / Value | Status |
| :--- | :--- | :---: |
| **Machine Model** | Windows PC (AMD64 architecture) | PASS |
| **Operating System** | Microsoft Windows 11 Home Single Language (Build 10.0.26200) | PASS |
| **CPU Architecture** | 12th Gen Intel(R) Core(TM) i5-12500H (12 Cores, 16 Threads) | PASS |
| **Total Physical RAM**| 15.69 GB | PASS |
| **Python Version** | Python 3.14.7 (64-bit, CPython) | PASS |
| **Npcap Version** | **NOT INSTALLED** (`npcap.sys`: False, `wpcap.dll`: False) | **FAIL** |
| **Execution Privileges**| Standard User (`is_admin`: False) | **FAIL** |
| **Target Adapter** | `Wi-Fi` (Intel(R) Wi-Fi 6 AX201 160MHz) | PASS |
| **Adapter Status** | Link State: `[UP]` (Active connection) | PASS |
| **Production Model** | `model_lightgbm_v1` (Artifact & SHA-256 hash verified) | PASS |
| **Feature Schema Hash**| `9178786dc46dba8800c66b551c3ebcf78034f357f53405bf6b2ed70b40d88101` | PASS |
| **Local Ports** | Port 8080 (REST API) & Port 8501 (SOC Dashboard) Available | PASS |

---

## 3. Mandatory 10-Point Precheck Audit Matrix

Every mandatory criterion was individually tested against the active system:

| # | Criterion | Verification Command / Target | Ground Truth Result | Evaluation |
| :-: | :--- | :--- | :--- | :---: |
| **1** | Windows 10/11 x64 | `product.environment.get_os_info()` | Windows 11 (10.0.26200 AMD64) | **PASS** |
| **2** | Npcap Installed | `product.environment.check_npcap()` | Driver not detected in System32 | **FAIL** |
| **3** | WinPcap API Compat | Registry & DLL verification | `wpcap.dll` absent | **FAIL** |
| **4** | Admin Privileges | `product.environment.is_admin()` | Standard user execution | **FAIL** |
| **5** | Physical Adapter | `product.adapter_manager.list_adapters()`| `Wi-Fi` adapter detected | **PASS** |
| **6** | Adapter is UP | Adapter query | Status is UP | **PASS** |
| **7** | Production Model | Check `results/models/lightgbm.joblib` | Model & preprocessor present | **PASS** |
| **8** | Model Hash Valid | Check SHA-256 vs `production_registry.json`| Hash verified | **PASS** |
| **9** | Feature Schema Valid | Check `realtime.schema.CANONICAL_SCHEMA_HASH`| Hash matches canonical 21/10 | **PASS** |
| **10**| API & Dash Available | Port check on `127.0.0.1:8080` & `8501` | Sockets bind cleanly | **PASS** |

**Precheck Verdict:** **FAIL** (Criteria 2, 3, and 4 failed).

---

## 4. Live Capture Execution Telemetry

Execution of the authoritative live capture diagnostic:
```powershell
python -m scripts.live_capture_test --duration 15
```

### Raw Console Diagnostic Log
```text
WARNING: No libpcap provider available ! pcap won't be used

======================================================================
  REAL LIVE NETWORK PACKET CAPTURE DIAGNOSTIC
  EVIDENCE CLASS: REAL_LIVE_NPCAP (DIRECT PHYSICAL HARDWARE ADAPTER)
======================================================================
[1/5] Checking Npcap driver and administrative permissions...
      Npcap Status:   FAIL - Npcap packet capture driver was NOT detected on this system.
      Administrator:  NO (Standard User)

[-] CAPTURE DIAGNOSTIC FAILED:
    Npcap packet capture driver was NOT detected on this system.
    Live capture cannot proceed without Npcap.
    Guidance: Install Npcap from https://npcap.com/ with WinPcap API compatibility.
    Rule Enforced: Live mode will NEVER silently fall back to demo mode.
======================================================================
```
*Process Exit Code:* `1`

### Capture Telemetry Data
- **Session Duration Requested:** `15.0` seconds
- **Effective Duration:** `0.0` seconds (Immediate fail-closed abort)
- **Packets Captured:** `0`
- **Bytes Captured:** `0`
- **First Packet Timestamp:** `None`
- **Last Packet Timestamp:** `None`
- **Protocol Distribution:** None
- **Synthetic Contamination:** **0.0% (Zero packets injected)**

---

## 5. End-to-End Chain Verification

The contract requires proving this unbroken chain of physical capture:

```
PHYSICAL Wi-Fi/Ethernet
      │  [PASS: Wi-Fi adapter detected & UP]
      ▼
    Npcap
      │  [FAIL: Driver not installed on workstation]
      ▼
ACTUAL PACKETS
      │  [FAIL: 0 packets captured; closed with code 1]
      ▼
ACTUAL FLOWS
      │  [BLOCKED: Zero flows created; no synthetic fallback]
      ▼
ACTUAL ZERO-PAYLOAD FEATURES
      │  [BLOCKED: Zero features computed]
      ▼
ACTUAL ML INFERENCE
      │  [BLOCKED: RealTimeClassifier emitted zero live predictions]
      ▼
ACTUAL LIVE API EVENT
      │  [BLOCKED: /predictions?mode=LIVE_NPCAP returned count=0]
      ▼
ACTUAL SQLITE EVENT
      │  [BLOCKED: 0 live events recorded in event_store.db]
      ▼
ACTUAL DASHBOARD ROW
         [BLOCKED: No live rows rendered; demo rows excluded]
```

### Verification Findings for Subsystems:

1. **Real Flow Test (`FlowTracker`):**
   - Packets Ingested: `0`
   - Active Flows Created: `0`
   - Completed Flows: `0`
   - Feature Vectors Extracted: `0`
   - Invariant: No recorded flows or synthetic flows were substituted.

2. **Real ML Test (`RealTimeClassifier`):**
   - Model ID: `model_lightgbm_v1`
   - Feature Profile: `lightweight_10`
   - Predictions Generated: `0`
   - Invariant: Zero predictions were generated without live flow provenance.

3. **REST API Verification (`product.local_api`):**
   - `GET /status`:
     ```json
     {
       "mode": "LIVE_NPCAP",
       "evidence_class": "REAL_LIVE_NPCAP",
       "npcap_detected": false,
       "live_machine_verified": false,
       "implementation_status": "IMPLEMENTATION READY"
     }
     ```
   - `GET /predictions?mode=LIVE_NPCAP`:
     Returned `count: 0`, `evidence_class: "REAL_LIVE_NPCAP"`.
     Refused to fall back to CSV cache or demo rows.
   - `GET /events?mode=LIVE_NPCAP`: Returned `count: 0`.
   - `GET /alerts`: Returned `count: 0`.

4. **Event Store Verification (`LocalEventStore`):**
   - Total Live Events Stored: `0`
   - SQLite Database Schema: Verified (`evidence_class` column present).
   - Raw Packet Payload Stored: `0 bytes` (Zero-payload privacy preserved).
   - Unhashed IP Addresses Stored: `0` (Scrubbed pseudonymization preserved).

5. **Live Dashboard Verification (`Streamlit SOC Console`):**
   - Mode Selector: `LIVE_NPCAP (Live Physical Network Capture)`.
   - Prominent Mode Banner:
     `🟢 EVIDENCE CLASS: REAL_LIVE_NPCAP (PHYSICAL HARDWARE CAPTURE)`
   - Cross-Mode Isolation: Verified. Demo simulation records (`🟠 DEMO SIMULATION`) and recorded replay records (`🔵 RECORDED CAPTURE`) were excluded from the live feed.

---

## 6. Generated Evidence Package

The following artifacts have been authored and archived under [`results/live_machine_verification/`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/live_machine_verification/):

1. [`environment.json`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/live_machine_verification/environment.json): Complete machine, OS, hardware, Python runtime, privilege, and driver audit.
2. [`live_capture_summary.json`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/live_machine_verification/live_capture_summary.json): Complete live capture diagnostic logs, failure code, and blocking reasons.
3. [`live_flow_summary.json`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/live_machine_verification/live_flow_summary.json): Flow tracking ingress metrics and zero-synthetic assertion.
4. [`live_prediction_summary.json`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/live_machine_verification/live_prediction_summary.json): ML prediction state and provenance isolation audit.
5. [`live_api_summary.json`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/live_machine_verification/live_api_summary.json): Local REST API response verification across all endpoints.
6. [`live_session_summary.json`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/live_machine_verification/live_session_summary.json): LocalEventStore session tracking and privacy assertions.
7. [`verification_manifest.json`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/live_machine_verification/verification_manifest.json): Authoritative criteria manifest and final verdict ledger.

---

## 7. Remediation Protocol to Achieve LIVE MACHINE VERIFIED

To convert the status from `IMPLEMENTATION READY` to `LIVE MACHINE VERIFIED`, an operator must perform the following three steps on this physical Windows machine:

1. **Install Npcap Driver:**
   - Download the official installer from [https://npcap.com/#download](https://npcap.com/#download).
   - Execute the installer and ensure **"Install Npcap in WinPcap API-compatible Mode"** is checked.
2. **Launch with Administrator Privileges:**
   - Open PowerShell or Command Prompt with **"Run as administrator"**.
3. **Execute Physical Wire Validation:**
   ```powershell
   # 1. Run live hardware capture verification (15 seconds)
   python -m scripts.live_capture_test --interface "Wi-Fi" --duration 15

   # 2. Launch live desktop monitor
   python -m product.app --mode live --interface "Wi-Fi"
   ```
4. **Confirm Actual Packets on Wire:**
   - Open a web browser and visit several HTTPS endpoints.
   - Confirm that the dashboard and API show $> 0$ live packets, flows, and predictions.
   - Rerun this verification report; `live_machine_verified` will update to `true`.
