# Real Live-Npcap Acceptance Validation Specification

**Document Reference:** `docs/REAL_LIVE_NPCAP_ACCEPTANCE.md`  
**System Name:** Encrypted Traffic Monitor & Cybersecurity SOC Console  
**Classification Protocol:** Zero-Payload Statistical & Metadata Traffic Inference  
**Target Operating Environment:** Windows 10/11 x64 with Npcap Driver  

---

## 1. Executive Summary & Evidence Classification

To preserve scientific rigor and engineering honesty, this system strictly and explicitly distinguishes **three completely different evidence classes**:

| Evidence Class | Operating Mode Enum | Data Origin | Replay / Synthetic Permitted? | Displayed Banner |
| :--- | :--- | :--- | :--- | :--- |
| **`REAL_LIVE_NPCAP`** | `LIVE_NPCAP` *(alias `LIVE_MODE`)* | Physical Wi-Fi / Ethernet adapter directly via Npcap driver | **STRICTLY PROHIBITED**<br>(Zero-packet capture is an explicit failure; zero synthetic fallback, zero PCAP replay, zero CSV cache replay, zero demo events) | `🟢 EVIDENCE CLASS: REAL_LIVE_NPCAP (PHYSICAL HARDWARE CAPTURE)` |
| **`REAL_RECORDED_CAPTURE`** | `RECORDED_CAPTURE` | Genuine recorded physical packet flow recordings (`flows_real_clean.csv`) | Replay allowed for deterministic regression and parity verification; **NEVER** displayed or served as `LIVE_NPCAP` | `🔵 EVIDENCE CLASS: REAL_RECORDED_CAPTURE (DETERMINISTIC OFFLINE REPLAY)` |
| **`DEMO_SIMULATION`** | `DEMO_MODE` *(alias `DEMO_SIMULATION`)* | Synthetic traffic generator / demo flow replay stream | Isolated simulation stream for operator demonstration and UI validation | `🟠 EVIDENCE CLASS: DEMO_SIMULATION (SYNTHETIC TRAFFIC SIMULATION)` |

Additionally, offline research benchmarks evaluate frozen datasets under `RESEARCH_MODE` with evidence class `RESEARCH_BENCHMARK` (`🟣 EVIDENCE CLASS: RESEARCH_BENCHMARK`).

---

## 2. Distinction: IMPLEMENTATION READY vs. LIVE MACHINE VERIFIED

A core requirement of this acceptance validation is that **`REAL_LIVE_NPCAP` must not be marked as PASS merely because the code correctly fails closed when Npcap is missing**, nor may offline recordings of real packets be passed off as proof of live physical capture.

The system distinguishes two distinct operational evaluation statuses:

### Status Definition

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          OPERATIONAL STATUS TAXONOMY                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [ IMPLEMENTATION READY ]                                                   │
│  The live Npcap capture subsystem, packet ingestion loop, Layer-3/4 zero-   │
│  payload feature extractor, model inference engine, local SQLite event      │
│  store, REST API, dashboard banner, and fail-closed mechanisms are          │
│  completely implemented, hardened, and verified via automated test suites.   │
│  When Npcap is absent, the system correctly fails closed with code 1        │
│  without falling back to synthetic, recorded, or demo data.                 │
│                                                                             │
│  [ LIVE MACHINE VERIFIED ]                                                  │
│  Requires physical execution on an actual Windows machine with:             │
│    1. Npcap driver installed and active service running                     │
│    2. Administrator privileges (or Npcap non-admin access group configured) │
│    3. Active physical Wi-Fi or Ethernet adapter connected to a live network │
│    4. >0 actual packets sniffed off the physical wire                       │
│    5. Actual packet arrival timestamps                                      │
│    6. Actual bidirectional network flows created                            │
│    7. Actual 10-feature zero-payload feature vectors extracted              │
│    8. Actual ML model predictions computed                                  │
│    9. Actual live prediction event stored in LocalEventStore                │
│   10. Actual live prediction event served via REST API and dashboard        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Current Workstation Audit Status

- **Host Environment:** Windows 11 Enterprise (x64), Build 26100, AMD64.
- **Npcap Driver Detection:** `FAIL - Npcap packet capture driver was NOT detected on this system.`
- **Execution Privileges:** Standard User (Non-Elevated).
- **Automated Live Capture Execution (`python scripts/live_capture_test.py`):**
  - Result: Failed closed with exit code `1`.
  - Behavior: Refused to capture; refused to fall back to demo data; printed explicit Npcap installation requirements.
- **Automated Contract Tests (`tests/test_live_npcap_contract.py`):**
  - Result: `7 passed in 1.51s` (100% PASS).
- **Authoritative Determination:**
  - `REAL_LIVE_NPCAP`: **`IMPLEMENTATION READY`**  
    *(Fail-closed verified on host workstation; Live Machine Verification requires physical deployment on a machine with the Npcap driver installed).*
  - `REAL_RECORDED_CAPTURE`: **`VERIFIED PASS`**  
    *(Deterministic verification passing on genuine recorded packets).*
  - `DEMO_SIMULATION`: **`VERIFIED PASS`**  
    *(Isolated simulation passing cleanly).*

> [!IMPORTANT]
> This project refuses to fabricate or mock live packet capture results. The status `LIVE MACHINE VERIFIED` will be attained upon running the validation protocol below on a physical Windows machine with Npcap installed.

---

## 3. The 10 Mandatory Criteria for LIVE MACHINE VERIFICATION

When conducting live physical validation on an end-user Windows machine, all 10 of the following criteria must be affirmatively satisfied:

| Item | Acceptance Criterion | Required Evidence | Verification Method |
| :---: | :--- | :--- | :--- |
| **1** | **Npcap Driver Installed** | Npcap v1.70+ present in `C:\Windows\System32\Npcap` with WinPcap-compatible mode | `product.environment.check_npcap()` returns `status: "PASS"` |
| **2** | **Elevated Privileges** | Process running with administrative privileges or Npcap group rights | `product.environment.is_admin()` returns `True` |
| **3** | **Physical Network Adapter** | Real Wi-Fi or Ethernet adapter with link state `[UP]` and assigned IP | `product.adapter_manager.list_adapters()` returns active adapter |
| **4** | **>0 Actual Packets Captured** | Packets must be ingested directly from physical NIC; count must be $> 0$ | `LiveSniffer.packets_captured_count > 0` |
| **5** | **Actual Packet Timestamps** | Non-zero, monotonic Unix epoch timestamps corresponding to wall-clock time | `RawPacketMetadata.timestamp` matches current time ($\pm 5$s) |
| **6** | **Actual Flows Created** | 5-tuple aggregation (`src_ip`, `dst_ip`, `src_port`, `dst_port`, `proto`) | `FlowTracker.active_flows > 0` |
| **7** | **Zero-Payload Features** | Canonical 10 statistical distribution features computed from packet sizes/times | `FeatureExtractor.extract_features(flow)` succeeds without payload bytes |
| **8** | **Actual ML Inference** | Model output generated from registered LightGBM/RandomForest artifact | `RealTimeClassifier.predict()` produces class and confidence |
| **9** | **Actual API Event** | Event stored in SQLite database with `evidence_class == "REAL_LIVE_NPCAP"` | `GET /predictions?mode=LIVE_NPCAP` returns genuine record |
| **10**| **Actual Dashboard Row** | Live record rendered in Streamlit console under `LIVE_NPCAP ACTIVE` banner | SOC Console table displays green row with real timestamp |

---

## 4. Physical Machine Acceptance Runbook

Follow these step-by-step instructions on the target Windows physical workstation:

### Step 1: Install Npcap
1. Download official installer from [https://npcap.com/dist/npcap-1.80.exe](https://npcap.com/dist/npcap-1.80.exe).
2. During installation, select:
   - ✅ **"Install Npcap in WinPcap API-compatible Mode"** *(MANDATORY)*
   - ✅ **"Support raw 802.11 traffic (and monitor mode) for wireless adapters"**
3. Complete installation and restart if prompted.

### Step 2: Open Elevated PowerShell
Open PowerShell as Administrator:
```powershell
Start-Process powershell -Verb runAs
cd "C:\UROP project\encrypted-traffic-classification-UROP"
```

### Step 3: Run Hardware Packet Sniffing Diagnostic
Verify the physical driver and network interface:
```powershell
python scripts/live_capture_test.py --interface "Wi-Fi" --duration 5 --max-packets 50
```
*Expected Output:*
```text
======================================================================
  REAL LIVE NETWORK PACKET CAPTURE DIAGNOSTIC
  EVIDENCE CLASS: REAL_LIVE_NPCAP (DIRECT PHYSICAL HARDWARE ADAPTER)
======================================================================
[1/5] Checking Npcap driver and administrative permissions...
      Npcap Status:   PASS - Npcap packet capture driver detected
      Administrator:  YES (Elevated)
[2/5] Identifying network adapter for capture...
      Selected Adapter: 'Wi-Fi' (Intel(R) Wi-Fi 6 AX201 160MHz)
      Link Status:      UP | IP: 192.168.1.105
[3/5] Initializing LiveSniffer on 'Wi-Fi' (Timeout: 5.0s)...
[4/5] Sniffing live packets on the wire (Listening for 5.0s)...
      [PKT #0001] Time: 1787673412.1042 | 192.168.1.105:54210 -> 142.250.190.46:443 | Proto: TCP  | Len:   54 bytes
      [PKT #0002] Time: 1787673412.1048 | 142.250.190.46:443 -> 192.168.1.105:54210 | Proto: TCP  | Len: 1420 bytes
...
======================================================================
  LIVE CAPTURE DIAGNOSTIC: PASS (SUCCESS)
======================================================================
  Target Interface:     Wi-Fi
  Observed Packets:     48
  Protocols Present:    TCP, UDP
  Data Integrity:       VALID LAYER-3/4 TRANSPORT METADATA
  Synthetic Contam:     NONE (100% Real Live Packets)
======================================================================
```

### Step 4: Launch Real-Time Desktop Monitor
Start the end-to-end monitoring service:
```powershell
python -m product.app --mode live --interface "Wi-Fi"
```
The application will:
1. Validate Npcap and the Wi-Fi adapter.
2. Initialize Local REST API on `http://127.0.0.1:8080`.
3. Launch Streamlit SOC Dashboard on `http://127.0.0.1:8501`.
4. Begin live zero-payload packet capture and ML inference.

### Step 5: Verify REST API Contract
In a separate terminal, test the local REST endpoints:

```powershell
# Verify system status
Invoke-RestMethod http://127.0.0.1:8080/status | ConvertTo-Json
```
*Expected JSON:*
```json
{
  "app_name": "Encrypted Traffic Monitor",
  "version": "1.0.0",
  "status": "READY",
  "mode": "LIVE_NPCAP",
  "evidence_class": "REAL_LIVE_NPCAP",
  "adapter": "Wi-Fi",
  "npcap_detected": true,
  "npcap_status": "PASS",
  "live_machine_verified": true,
  "implementation_status": "IMPLEMENTATION READY",
  "privacy": "LOCAL ONLY",
  "zero_payload": "PASS",
  "save_raw_packets": false
}
```

Query the live predictions:
```powershell
Invoke-RestMethod "http://127.0.0.1:8080/predictions?mode=LIVE_NPCAP&limit=5" | ConvertTo-Json
```
*Expected JSON:*
```json
{
  "count": 5,
  "limit": 5,
  "mode": "LIVE_NPCAP",
  "evidence_class": "REAL_LIVE_NPCAP",
  "source": "EVENT_STORE",
  "predictions": [
    {
      "event_id": "EVT-1787673420000-0012",
      "timestamp": "14:23:40",
      "flow_id": "192.168.1.105:54210-142.250.190.46:443-6",
      "predicted_family": "Interactive",
      "predicted_class": "Web",
      "composed_confidence": 0.942,
      "prediction_state": "KNOWN_CLASS",
      "operating_mode": "LIVE_NPCAP",
      "evidence_class": "REAL_LIVE_NPCAP",
      "packets_observed": 14,
      "elapsed_seconds": 1.42,
      "latency_us": 128.4
    }
  ]
}
```

### Step 6: Verify Streamlit Dashboard
Navigate to `http://127.0.0.1:8501`:
1. Ensure the sidebar has selected: `LIVE_NPCAP (Live Physical Network Capture)`.
2. Inspect the prominent top banner:
   ```
   🟢 EVIDENCE CLASS: REAL_LIVE_NPCAP (PHYSICAL HARDWARE CAPTURE)
   Npcap physical packet capture • Direct NIC ingestion • Online zero-payload feature extraction • Real ML inference • Zero synthetic or recorded fallback
   ```
3. Verify that the table updates with live rows bearing current wall-clock timestamps.
4. Verify that no synthetic demo badge (`🟠 DEMO SIMULATION`) or recorded capture badge (`🔵 RECORDED CAPTURE`) appears in live mode.

---

## 5. Acceptance Verification Log & Sign-Off

| Verification Check | Required Result | Verified on Current Machine? | Status |
| :--- | :--- | :---: | :---: |
| **Operating Mode Enum & Schema** | `LIVE_NPCAP`, `RECORDED_CAPTURE`, `DEMO_MODE` explicit | YES | **PASS** |
| **Evidence Class Property** | `REAL_LIVE_NPCAP`, `REAL_RECORDED_CAPTURE`, `DEMO_SIMULATION` | YES | **PASS** |
| **Event Store Mode Segregation** | Zero recorded/demo leakage into `LIVE_NPCAP` queries | YES | **PASS** |
| **REST `/status` Evidence Class** | Returns canonical mode and evidence class | YES | **PASS** |
| **REST `/predictions` Segregation**| Never falls back to CSV cache in `LIVE_NPCAP` | YES | **PASS** |
| **Dashboard Banners & Filtering** | Explicit 3-class banners and cross-mode rejection | YES | **PASS** |
| **Zero-Packet Live Sniff Failure**| Fails closed without synthetic fallback | YES | **PASS** |
| **Npcap Missing Driver Defense** | Exits with error code 1, prints install guidance | YES | **PASS** |
| **Physical Packets Captured on Wire**| $> 0$ physical packets sniffed via Npcap driver | NO *(Driver not installed)* | **PENDING LIVE NPCAP INSTALL** |

### Final Acceptance Sign-Off

```
========================================================================================
SYSTEM STATUS SUMMARY:
  • REAL_LIVE_NPCAP:       IMPLEMENTATION READY (FAIL-CLOSED VERIFIED ON HOST WORKSTATION)
  • REAL_RECORDED_CAPTURE: VERIFIED PASS (DETERMINISTIC TESTING ON RECORDED PACKETS)
  • DEMO_SIMULATION:       VERIFIED PASS (ISOLATED SYNTHETIC PLAYBACK)

ACCEPTANCE DECISION:
  IMPLEMENTATION READY — SOFTWARE IS PRODUCTION-HARDENED AND PREPARED FOR NPCAP DEPLOYMENT.
========================================================================================
```
