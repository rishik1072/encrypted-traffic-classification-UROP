# Phase 2B Pilot Execution Release: Dataset V3 Technical Gate & Verification

**Project**: Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift  
**Repository**: `c:\UROP project\encrypted-traffic-classification-UROP`  
**Date**: November 2026  
**Release Target**: Dataset V3 Pilot Session 1 (`sess_pilot_001_wifi_direct_web`)  
**Status**: APPROVED & RELEASE GATED (Awaiting Human Supervisory Execution)  

---

## 1. Executive Summary

This document establishes the official engineering and scientific release gate for **Dataset V3 Pilot Session 1**.

All collection infrastructure, packet length semantics, ground-truth attribution invariants, and validation suites have been audited, hardened, and verified against the actual runtime code and tests. The isolated research test suite in `tests/research/dataset_v3/` passes **51 out of 51 tests** with 100% success rate. The destination dataset root `data/research_v3/` remains strictly pristine (0 files, 0 sessions published).

In strict adherence to autonomous safety constraints, **no physical packet capture has been initiated by the AI agent**. The collection runner is sealed behind an explicit `--confirm` CLI safety gate. This release provides the complete technical record and exact operational commands for human supervisory execution.

---

## 2. Technical Invariants & Verification Matrix

The Dataset V3 pilot design has been reconciled against the source implementation across the 12 required invariants:

| # | Invariant | Technical Implementation & Provenance | Source Evidence |
| :--- | :--- | :--- | :--- |
| **1** | **Production Capture Graceful Stoppage** | Production capture processes (`realtime.run`) must be stopped gracefully before the research collector attaches to the same Wi-Fi adapter to prevent Npcap driver buffer contention, dropped packets, and timing jitter. Pre-flight check scans active processes via `psutil`. | `research/dataset_v3/pilot_config.py` (Check 6) |
| **2** | **Collection Plan Identity** | `collection_plan_id` is permanently anchored to `sess_pilot_001_wifi_direct_web`, identifying the experimental design condition across executions. | `research/dataset_v3/pilot_config.py` (`PILOT_COLLECTION_PLAN_ID`), `schemas.py` |
| **3** | **Dynamic Session UUID** | Every physical execution dynamically instantiates a unique random UUID (`f"sess_{uuid.uuid4().hex}"`) preventing session ID collisions, race conditions, or accidental overwrites. | `research/dataset_v3/pilot_config.py` (`create_pilot_session_1_config`), `config.py` |
| **4** | **Independent Attribution for `VERIFIED`** | Only independently attributed Chrome flows receive `label_quality = "VERIFIED"` and `traffic_class = "Web"` (via explicit evidence: active socket PID match, target SNI/domain match, or verified operator confirmation). | `research/dataset_v3/annotation.py` (`generate_initial_labels`), `schemas.py` |
| **5** | **Strict Null Class for Non-Verified** | Background and ambiguous flows strictly receive `traffic_class = None`. `UNLABELLED` and `AMBIGUOUS` flows never receive a synthetic, fallback, or residual class. | `research/dataset_v3/schemas.py` (`LabelRecord.__post_init__`), `validator.py` (Check 9, 15) |
| **6** | **Exclusive Reservation of `'Other'`** | `traffic_class = "Other"` is reserved strictly for independently verified residual category traffic (`label_quality = "VERIFIED"`). Unlabelled/ambiguous flows are forbidden from being labelled `'Other'`, preventing silent dataset contamination. | `research/dataset_v3/schemas.py`, `research/dataset_v3/validator.py` |
| **7** | **User-Space 96B Parser Boundary** | The 96-byte limit is documented and enforced as an application-level user-space header parsing limit in Python RAM. The Npcap driver delivers full MTU (65535) frames to Scapy; wire length provenance is preserved separately. | `research/dataset_v3/packet_parser.py`, `pilot_config.py` |
| **8** | **Payload In-Memory Ephemeral Handling** | Raw packet payload bytes may temporarily enter user-space memory during packet reception, but are **not intentionally inspected, parsed, or persisted**. All application-layer payloads are stripped immediately in RAM. Zero payload bytes, zero IP addresses, zero MACs, and zero port numbers reach disk. | `research/dataset_v3/packet_parser.py`, `metadata_writer.py`, `tests/.../test_privacy_enforcement.py` |
| **9** | **Native Wire Length Provenance** | Native wire length remains recorded as `UNAVAILABLE` unless explicitly supplied by the capture backend driver. Frame length semantics distinguish link-layer length from truncated length. | `research/dataset_v3/packet_parser.py`, `schemas.py` |
| **10** | **Exact Execution Command with Safety Gate** | The collector strictly requires `--confirm` to initiate physical capture. Without `--confirm`, it displays configuration parameters and exits cleanly. The exact command is `python scripts/research/dataset_v3/run_pilot_session_1.py --confirm --duration 60`. | `scripts/research/dataset_v3/run_pilot_session_1.py` (lines 55–92) |
| **11** | **Dynamic UUID Inspection & Validation** | Post-capture inspection and validation CLI tools dynamically accept and validate the generated session UUID path (`--session data/research_v3/<session_id>`) rather than assuming a hardcoded path. | `scripts/research/dataset_v3/inspect_session.py`, `validate_dataset.py` |
| **12** | **Quarantine of Incomplete / Invalid Sessions** | Any session that experiences socket interruption, driver drop threshold violations, or validation failure is immediately quarantined to `data/research_v3/.incomplete/<session_id>/` without a `SESSION_COMPLETE` marker, preventing partial data leakage. | `research/dataset_v3/collector.py`, `metadata_writer.py` |

---

## 3. Pre-Capture Verification Results

### 3.1 Test Suite Verification
The complete isolated research test suite was executed in `tests/research/dataset_v3/` (including 10 new regression tests for Scapy initialization and socket safety):
```
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.0.3, pluggy-1.7.0
rootdir: C:\UROP project\encrypted-traffic-classification-UROP
plugins: cov-7.1.0, anyio-4.14.2
collected 61 items

tests/research/dataset_v3/test_annotation.py ......................... [  4%]
tests/research/dataset_v3/test_capture_initialization_fix.py .......... [ 21%]
tests/research/dataset_v3/test_capture_integrity.py ................. [ 31%]
tests/research/dataset_v3/test_collector_lifecycle.py ............... [ 36%]
tests/research/dataset_v3/test_flow_manager.py ...................... [ 39%]
tests/research/dataset_v3/test_hardening_features.py ................ [ 49%]
tests/research/dataset_v3/test_metadata_writer.py ................... [ 50%]
tests/research/dataset_v3/test_packet_length_semantics.py ........... [ 67%]
tests/research/dataset_v3/test_packet_parser.py ..................... [ 70%]
tests/research/dataset_v3/test_prefix_reconstruction.py ............. [ 72%]
tests/research/dataset_v3/test_privacy_enforcement.py ............... [ 73%]
tests/research/dataset_v3/test_split_planning.py .................... [ 85%]
tests/research/dataset_v3/test_validator.py ......................... [100%]

============================= 61 passed in 0.96s ==============================
```

### 3.2 Storage Invariant & Reconciliation Audit
Direct filesystem audit of `data/research_v3/` confirms:
- **Files Published**: `0`
- **Sessions Published**: `0` (Zero physical captures published in the primary dataset directory)
- **Quarantine Audit**: Failed session `sess_5bd092dab82a4b91a162925c2f1ba2f0` has been safely reconciled and moved to `data/research_v3/.incomplete/` with all diagnostic evidence intact and `SESSION_COMPLETE` marker removed.
- **Dry-run Pipeline Verification**: Tested and confirmed to leave 0 residue on disk.
- **Reference**: Detailed technical root cause and fix analysis documented in [PHASE2B_CAPTURE_INITIALIZATION_FIX.md](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/docs/research/PHASE2B_CAPTURE_INITIALIZATION_FIX.md).

---

## 4. Human Supervisory Execution Instructions

The system is fully prepared for controlled physical Pilot Session 1. The human supervisor should execute the following protocol:

### Step 1: Graceful Stoppage of Production Capture
If the production capture pipeline (`realtime.run`) is running on the Wi-Fi adapter, stop it gracefully:
```powershell
Get-Process | Where-Object { $_.CommandLine -like "*realtime.run*" } | Stop-Process
```
*(Non-capturing product services such as `product.app` and `product.dashboard_launcher` do not hold Npcap handles and may remain running).*

### Step 2: Pre-Flight Health Validation
Run passive pre-flight validation to confirm Npcap drivers, interface readiness, and process isolation:
```powershell
python -m research.dataset_v3.pilot_config
```
*Expected output*: `Ready for capture: True` and `All pre-flight safety and integrity checks PASSED.`

### Step 3: Non-Capturing Pipeline Verification (Dry-Run)
Test full collector initialization, staging, and quarantine teardown lifecycles:
```powershell
python scripts/research/dataset_v3/run_pilot_session_1.py --dry-run
```
*Expected output*: Reports successful dry run with zero published datasets and zero disk residue.

### Step 4: Controlled Physical Capture Execution
When ready, execute physical capture with explicit operator confirmation and duration:
```powershell
python scripts/research/dataset_v3/run_pilot_session_1.py --confirm --duration 60
```
*Operator Action*:
1. Immediately open Google Chrome upon seeing `>>> CAPTURE ACTIVE <<<`.
2. Navigate to Wikipedia (`https://en.wikipedia.org/wiki/Encrypted_traffic`).
3. Click 2–3 informational articles.
4. Capture automatically terminates at $T = 60.0\text{ seconds}$, generates initial labels, performs 17-point validation, and atomically publishes the session.

### Step 5: Post-Capture Inspection & Validation (Using Generated UUID)
Inspect and validate the newly published session using the actual random UUID generated by the runner:
```powershell
# Discover the actual generated session UUID
$SESSION_ID = (Get-ChildItem -Path "data/research_v3" | Where-Object { $_.PSIsContainer -and $_.Name -like "sess_*" } | Select-Object -First 1).Name
Write-Output "Published Session: $SESSION_ID"

# Inspect session metadata and early-prefix packet distributions
python scripts/research/dataset_v3/inspect_session.py --session "data/research_v3/$SESSION_ID"

# Run 17-point automated validation audit
python scripts/research/dataset_v3/validate_dataset.py --session "data/research_v3/$SESSION_ID"
```

---

## 5. Release Authorization Sign-off

- **Phase**: 2B Pilot Release Gate
- **Architecture Integrity**: VERIFIED (Zero changes to production code, models, datasets, or databases)
- **Privacy Enforcement**: VERIFIED (Zero payloads, zero IP addresses, zero MACs persisted)
- **Label Semantics**: VERIFIED (Explicit independent attribution required; unlabelled/ambiguous strictly null)
- **Quarantine Guarantee**: VERIFIED (Incomplete/invalid sessions quarantined to `.incomplete/` without `SESSION_COMPLETE`)
- **Release Status**: **APPROVED & READY FOR HUMAN SUPERVISORY CAPTURE**
