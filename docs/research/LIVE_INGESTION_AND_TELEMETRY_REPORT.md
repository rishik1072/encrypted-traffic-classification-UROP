# LIVE_NPCAP Ingestion and Real-Time Telemetry Engineering Report

**Document:** `docs/research/LIVE_INGESTION_AND_TELEMETRY_REPORT.md`  
**Date:** November 19, 2026  
**System:** Encrypted Traffic Monitor (UROP Project)  
**Operating Mode:** `LIVE_NPCAP` (Evidence Class: `REAL_LIVE_NPCAP`)  
**Target Hardware Interface:** `Wi-Fi — Intel(R) Wi-Fi 6 AX201 160MHz`  
**Model Identifier:** `model_lightgbm_v1` (GradientBoostedDecisionTree, lightweight_10)  

---

## 1. Executive Summary

This engineering investigation targeted the runtime data-flow stagnation issue where the Encrypted Traffic Monitor initialized in `LIVE_NPCAP` mode, bound ports `127.0.0.1:8080` (Local API) and `127.0.0.1:8501` (Streamlit Dashboard), but continuously displayed:
- `Packets Received: 0`
- `Active Flows: 0`
- `Completed Flows: 0`
- Subsystem states: `WAITING FOR TRAFFIC`
- Legacy metrics leakage: `packets_per_second: 512`, `throughput_mbps: 4.6589` alongside `total_packets: 0`
- `live_machine_verified = false`
- Historical rows appearing in the live dashboard prediction feed

Through architectural tracing, runtime stack debugging, and automated regression testing, **six interrelated runtime defects** were uncovered and resolved. No synthetic traffic generation was introduced, no demo simulation was permitted in live mode, zero-payload privacy was rigorously preserved, and the production LightGBM model and preprocessor artifacts were maintained intact.

---

## 2. End-to-End Pipeline Architecture & Runtime Call Graph

The production pipeline executes across nine distinct stages spanning the physical Npcap capture hook to the Streamlit SOC monitoring dashboard:

```
[ Physical Network Interface: Wi-Fi (Intel Wi-Fi 6 AX201 160MHz) ]
                            | (Physical Wire Packets)
                            v
[ Stage 1: Npcap Kernel Driver (npcap.sys) & WinPcap Compatibility (wpcap.dll) ]
                            |
                            v
[ Stage 2: Scapy Sniffer Hook (capture/packet_capture.py: LiveSniffer._packet_handler) ]
                            | (Raw Scapy Packet)
                            v
[ Stage 3: Zero-Payload Extraction (capture/packet_capture.py: parse_scapy_packet) ]
                            | (RawPacketMetadata: IP, Ports, Protocol, Length, Flags)
                            v
[ Stage 4: Ingestion Queue & Consumer (LiveSniffer._packet_queue -> _consumer_loop) ]
                            | (RawPacketMetadata)
                            v
[ Stage 5: Bidirectional Flow Tracking (realtime/flow_tracker.py: RealTimeFlowTracker) ]
                            | (Flow: 5-tuple, Forward/Backward Packet Arrays, Timestamps)
                            v
[ Stage 6: Feature Extraction (preprocessing/feature_extractor.py: FeatureExtractor) ]
                            | (21 Zero-Payload Statistical Features / 10 Canonical Model Features)
                            v
[ Stage 7: Production Inference & Calibration (realtime/classifier.py: RealTimeClassifier) ]
                            | (model_lightgbm_v1, Platt Sigmoid Calibration, 4-State Decision Policy)
                            v
[ Stage 8: Metadata Persistence & Telemetry Logging ]
         |                                         |
         v                                         v
[ LocalEventStore (SQLite) ]              [ MetricsCollector (metrics.json) ]
(data/events/event_store.db)              (results/realtime/metrics.json)
         |                                         |
         +--------------------+--------------------+
                              |
                              v
[ Stage 9: Local REST API Server (product/local_api.py: LocalAPIServer :8080) ]
         |
         |--> GET /status      (OperatingMode, EvidenceClass, Subsystem Diagnostics)
         |--> GET /metrics     (Real-time sliding window rates, queue depths, latencies)
         |--> GET /predictions (Session-isolated live inference stream)
                              |
                              v
[ Stage 10: Streamlit SOC Dashboard (dashboard/app.py :8501) ]
```

---

## 3. Root Cause Analysis & Concrete Code Fixes

### 3.1 Defect 1: Telemetry Counter Wipe on Active Session ID Mismatch
- **Mechanism:** When `product.app` or the Streamlit dashboard started a new monitoring session via `POST /session/start`, `LocalEventStore.start_session()` assigned an active session ID (e.g. `SESS-1795067161-9400`) in SQLite. However, the classifier engine worker running in the child process had been spawned with an earlier session ID (e.g. `SESS-1795066962-1000`).
- When `GET /metrics` was polled, `product/local_api.py:handle_metrics()` checked:
  ```python
  if data.get("session_id") != active_sess_id:
      # Wiped all telemetry to 0 and set:
      data["telemetry_source"] = "SESSION_INITIALIZING"
  ```
  Every time packets were processed in the backend, the REST API wiped them back to zero before returning JSON to the dashboard.
- **Fix:** 
  1. In `realtime/classifier.py`, implemented `sync_session_if_needed()`, allowing the running classifier to dynamically read and adopt the latest active session ID from `LocalEventStore` upon each telemetry snapshot and packet burst.
  2. In `product/app.py`, explicitly propagated `self.current_session_id` into `start_realtime_engine()`.

### 3.2 Defect 2: Stale Legacy Metrics Leakage (512 pkts/s, 4.6589 Mbps)
- **Mechanism:** In `handle_metrics()`, when zeroing out uninitialized telemetry, the code reset `total_packets`, `total_bytes`, `flows_created`, etc., but **omitted** `packets_per_second`, `throughput_mbps`, `predictions_per_sec`, and `known_class_rate`. As a result, stale values from prior sessions or historical CSV rows stayed in memory, creating the contradictory state of `total_packets: 0` with `packets_per_second: 512`.
- **Fix:**
  1. In `realtime/metrics.py`, hardened sliding window calculations: if `self.total_packets == 0` or no packets fall within the current sliding window, `packets_per_sec`, `throughput_mbps`, `predictions_per_sec`, and `known_class_rate` are strictly clamped to `0.0`.
  2. In `product/local_api.py`, enforced zero-rate invariants across all rate fields whenever telemetry is uninitialized or `total_packets == 0`.

### 3.3 Defect 3: REST API Crash on `GET /metrics` (`NameError: name 'time' is not defined`)
- **Mechanism:** Line 320 of `product/local_api.py` called `now = time.time()` to compute metric age, but `import time` was absent from module imports. This threw repeated unhandled exceptions on every dashboard refresh.
- **Fix:** Added `import time` and `import traceback` to `product/local_api.py`, and wrapped request dispatching in a top-level try/except block that logs the full stack trace and returns a structured HTTP 500 JSON response instead of aborting the socket.

### 3.4 Defect 4: Cross-Session Data Leakage in Live Prediction Feed
- **Mechanism:** `GET /predictions` with `mode=LIVE_NPCAP` queried SQLite without filtering by `session_id`. Stale events from historical runs, previous days, or unit test fixtures appeared in the live table.
- **Fix:** Updated `product/local_api.py:handle_predictions()` to resolve `active_sess_id = local_event_store.get_active_session_id()` and enforce `session_id=active_sess_id` for all `LIVE_NPCAP` queries. If zero events have occurred in the active live session, the endpoint returns an empty array `[]` with `evidence_class: "REAL_LIVE_NPCAP"`.

### 3.5 Defect 5: Hardcoded `live_machine_verified = false`
- **Mechanism:** `product/local_api.py` line 201 previously had `"live_machine_verified": False` hardcoded.
- **Fix:** Replaced with a dynamic verification check:
  ```python
  live_machine_verified = False
  if active_sess_id:
      # Check metrics.json for genuine packet traversal in active session
      if m_data.get("session_id") == active_sess_id:
          if m_data.get("capture_packets_received", 0) > 0 and m_data.get("packets_processed", 0) > 0:
              live_machine_verified = True
      # Also check SQLite prediction events for active session
      if not live_machine_verified:
          cur = conn.execute(
              "SELECT COUNT(*) FROM prediction_events WHERE session_id = ? AND operating_mode = 'LIVE_NPCAP' AND packets_observed > 0",
              (active_sess_id,),
          )
          if cur.fetchone()[0] > 0:
              live_machine_verified = True
  ```

### 3.6 Defect 6: Pipeline Health Decoupling & Granular Capture States
- **Mechanism:** The system used a single monolithic `pipeline_status` boolean that marked the entire pipeline degraded if anything stalled.
- **Fix:** Introduced independent telemetry booleans for every pipeline stage:
  - `actual_packets_received`
  - `packets_processed_status`
  - `flows_created_status`
  - `features_extracted_status`
  - `predictions_generated_status`
  - `events_persisted_status`
- Added explicit capture lifecycle states to `LiveSniffer`:
  - `CAPTURE_STARTING`
  - `CAPTURE_ACTIVE`
  - `CAPTURE_RECEIVING`
  - `CAPTURE_IDLE`
  - `CAPTURE_FAILED`
  With `last_capture_error` and `last_capture_error_stage` (`PREREQUISITES`, `SCAPY_INIT`, `CONSUMER_WORKER`, `INTERFACE_RESOLUTION`, `SNIFF_LOOP`, `PERMISSION`).

---

## 4. Summary of Files Modified

| File Path | Description of Changes |
| :--- | :--- |
| `product/local_api.py` | Added `time` and `traceback` imports; added 500 error boundary; scoped `/predictions` strictly by `session_id`; implemented dynamic `live_machine_verified`; decoupled pipeline health flags; enforced zero rates when inactive. |
| `product/event_store.py` | Added `import uuid`; hardened `start_session` session ID uniqueness; updated `get_active_session_id` with `ORDER BY start_time DESC, rowid DESC`; reset in-memory active session in `clear_session`. |
| `product/app.py` | Fail-closed verification on API port 8080 binding; propagated `current_session_id` into `start_realtime_engine`. |
| `product/runtime_paths.py` | Hardened `get_base_dir()` so dev mode checks `(repo_root / "config.yaml").exists()`, resolving identically regardless of caller working directory. |
| `realtime/metrics.py` | Ingested `capture_state` and capture error stages; clamped sliding window rates to `0.0` when packets or predictions are zero. |
| `realtime/classifier.py` | Added dynamic session synchronization `sync_session_if_needed()`; linked `record_flow_created` to metrics collector. |
| `capture/packet_capture.py` | Added explicit capture states (`CAPTURE_STARTING`, `CAPTURE_ACTIVE`, etc.); added `last_capture_error` and `last_capture_error_stage` tracking; added safe Scapy initialization. |
| `tests/test_live_ingestion_and_telemetry.py` | **New comprehensive test suite** covering all 13 Phase 5 requirements, session isolation, and hardware Npcap capture validation. |
| `tests/test_metrics_api.py` | **New test suite** covering `/metrics` endpoint stability, JSON schema, and exception resilience. |

---

## 5. Automated Verification & Test Suite Results

All automated test suites execute with a **100% pass rate**:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.0.3, pluggy-1.7.0
rootdir: C:\UROP project\encrypted-traffic-classification-UROP
collected 16 items

tests/test_live_ingestion_and_telemetry.py::test_1_to_4_capture_callback_queue_and_worker_consumption PASSED [  6%]
tests/test_live_ingestion_and_telemetry.py::test_5_to_8_flow_creation_features_predictions_and_persistence PASSED [ 12%]
tests/test_live_ingestion_and_telemetry.py::test_9_session_isolation_and_dynamic_synchronization PASSED [ 18%]
tests/test_live_ingestion_and_telemetry.py::test_10_capture_exception_tracking PASSED [ 25%]
tests/test_live_ingestion_and_telemetry.py::test_11_to_13_no_packet_state_stale_telemetry_and_metrics_consistency PASSED [ 31%]
tests/test_live_ingestion_and_telemetry.py::test_hardware_npcap_capture_live_adapter PASSED [ 37%]
tests/test_live_npcap_contract.py::test_1_operating_mode_enum_and_evidence_classes PASSED [ 43%]
tests/test_live_npcap_contract.py::test_2_event_schema_evidence_class_property PASSED [ 50%]
tests/test_live_npcap_contract.py::test_3_event_store_strictly_isolates_evidence_classes PASSED [ 56%]
tests/test_live_npcap_contract.py::test_4_rest_status_endpoint_evidence_and_implementation_status PASSED [ 62%]
tests/test_live_npcap_contract.py::test_5_rest_predictions_endpoint_no_recorded_or_demo_in_live PASSED [ 68%]
tests/test_live_npcap_contract.py::test_6_dashboard_normalizer_rejects_cross_mode_pollution PASSED [ 75%]
tests/test_live_npcap_contract.py::test_7_zero_packet_live_capture_fails_closed PASSED [ 81%]
tests/test_metrics_api.py::test_metrics_api_comprehensive PASSED         [ 87%]
tests/test_live_pipeline_integration.py::test_real_packet_to_live_npcap_event_pipeline PASSED [ 93%]
tests/test_live_pipeline_integration.py::test_api_status_and_metrics_session_exposure PASSED [100%]

============================= 16 passed in 11.63s =============================
```

---

## 6. Windows Security Boundary & Npcap Runbook

### 6.1 Npcap Driver Privilege Analysis
On this workstation, the Npcap kernel driver parameters in the Windows Registry:
`HKLM\SYSTEM\CurrentControlSet\Services\npcap\Parameters`
contain:
```text
AdminOnly    REG_DWORD    0x1
```
- **Standard User (`Medium Mandatory Level`):** Windows blocks raw driver access (`CreateFile \\.\npcap` returns Win32 Error 5: `ERROR_ACCESS_DENIED`).
- **Elevated Administrator (`High Mandatory Level`):** Npcap opens `\Device\NPF_{B383A2A4-A634-4F0D-89E5-5A56CBCB9A0B}` directly, allowing physical Wi-Fi packet capture.

### 6.2 Operational Command to Run Live Monitoring
To start the application with full live physical packet ingestion:

1. Open PowerShell or Command Prompt as **Administrator** ("Run as Administrator").
2. Navigate to the repository root:
   ```powershell
   cd "c:\UROP project\encrypted-traffic-classification-UROP"
   ```
3. Start the production application:
   ```powershell
   python -m product.app --mode live --interface Wi-Fi
   ```
4. Access the SOC Console:
   - **Dashboard:** `http://127.0.0.1:8501`
   - **REST API:** `http://127.0.0.1:8080`

The system will capture live Wi-Fi packets, reconstruct flows, extract zero-payload features, run LightGBM inference, log predictions in SQLite, and continuously update live telemetry metrics without counter wipes, rate leakage, or cross-mode pollution.
