# Dataset V3 Pilot Session 1: Controlled Wi-Fi Execution Plan

**Project**: Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift  
**Repository**: `c:\UROP project\encrypted-traffic-classification-UROP`  
**Date**: November 2026  
**Collection Plan ID**: `sess_pilot_001_wifi_direct_web`  
**Execution Session ID**: Dynamic fresh random UUID per run (e.g., `sess_<uuid4_hex>`)  
**Status**: APPROVED EXECUTION PLAN (Awaiting Human Supervisory Execution)  

---

## 1. Objective and Scientific Scope

The purpose of Pilot Session 1 is to execute the first controlled physical network packet collection under the Dataset V3 infrastructure, verifying real-world operation of:
1. Physical packet capture on live Wi-Fi using the verified Npcap capture backend.
2. In-memory zero-payload packet metadata parsing and immediate payload disposal.
3. Accurate frame and IP length provenance, distinguishing wire length from user-space truncated capture length.
4. Bidirectional flow aggregation and microsecond relative timestamp tracking.
5. Strict ground-truth attribution distinguishing verified target Web browsing from unlabelled background OS traffic.
6. Multi-stage atomic session publication and automated validation with automatic quarantine of incomplete or invalid sessions.

> [!IMPORTANT]
> This document is an operational execution plan. **Physical capture must NOT be started autonomously by AI agents. Capture requires explicit human supervisory execution via the `--confirm` CLI flag.**

---

## 2. Experimental Environment & Target Activity

| Configuration Parameter | Value | Scientific Rationale |
| :--- | :--- | :--- |
| **Collection Plan ID** | `sess_pilot_001_wifi_direct_web` | Fixed experimental design identifier specifying the pilot test conditions. |
| **Execution Session ID** | `sess_<uuid>` (Dynamic UUID) | Unique random UUID generated per execution (e.g., `sess_f47ac10b...`) preventing collisions and replay conflicts. |
| **Physical Interface** | `Wi-Fi` | Active physical wireless adapter (`Intel(R) Wi-Fi 6 AX201 160MHz`). |
| **Adapter Type** | `Wi-Fi` | Group-disjoint splitting dimension for adapter shift studies. |
| **Tunnel Status** | `DIRECT` | Baseline un-encapsulated network traffic (no VPN tunnel active). |
| **Intended Class** | `Web` | Baseline primary traffic class for initial classifier evaluation. |
| **Application Alias** | `chrome_browsing` | Chrome web browser navigating standard HTTPS web pages. |
| **Collection Activity** | `Active Web Browsing (Wikipedia/Python Docs)` | Controlled, documented human browsing activity. |
| **Duration** | `60.0 seconds` | Controlled, reproducible duration sufficient for 10–50 flows. |
| **User-Space Parser Limit** | `96 bytes` | Application-level header truncation boundary in RAM. **(Note: Scapy on Windows uses MTU=65535 at the Npcap socket; the 96B limit is enforced in Python user-space parsing, NOT as an Npcap kernel snaplen).** |
| **Native Wire Length** | `UNAVAILABLE` | Wire length is recorded as `UNAVAILABLE` unless explicitly supplied by the capture backend driver. |
| **Payload Memory Handling** | Ephemeral RAM only | Payload bytes may temporarily enter user-space memory during packet reception, but are **not intentionally inspected, parsed, or persisted**. |
| **Promiscuous Mode** | `False` | Only sniffs packets addressed to/from this host; avoids capturing local network peers. |
| **Synthetic Allowed** | `False` | Strictly enforced invariant: zero synthetic traffic allowed in Dataset V3. |
| **Operator Label** | `operator_rishi` | Human operator responsible for controlled session execution. |

---

## 3. Production Capture & Non-Interference Guardrails

The host environment contains both production components and the new Dataset V3 research infrastructure.

### Production Capture Stoppage Rule
> [!WARNING]
> **Production capture processes (`realtime.run`) must be stopped gracefully before the research collector uses the same Wi-Fi adapter.**  
> Running concurrent packet sniffing handles on the same Npcap adapter induces driver buffer contention, dropped packets, and non-deterministic timing jitter. If `realtime.run` is active, the operator must terminate it gracefully (e.g., `Ctrl+C` in its terminal or `Stop-Process -Id <pid>`) prior to launching the research collector.

### Production Preservation Guardrails
1. **Production Services**: Non-capturing product services (e.g., REST API `product.app`, dashboard `product.dashboard_launcher`) do not hold Npcap capture handles and may remain running.
2. **Never modify production source code**: `capture/`, `flows/`, `models/`, `product/`, `preprocessing/` are frozen.
3. **Never modify production data or models**: `data/events/event_store.db`, `data/processed/`, and `models/` must not be touched.
4. **Isolated Research Output**: All Dataset V3 outputs are strictly isolated to `data/research_v3/` and temporary staging `.staging/`.

---

## 4. Pre-Capture Operator Protocol & Checklist

Before executing Pilot Session 1, the human operator must execute and verify every item on this checklist:

```
[ ] 1. Production Capture Graceful Stoppage:
       Verify no production capture process (realtime.run) is actively sniffing the Wi-Fi adapter:
       Get-Process | Where-Object { $_.CommandLine -like "*realtime.run*" }
       If running, stop it gracefully before proceeding.

[ ] 2. Wi-Fi Status: Verify Wi-Fi adapter is connected and active:
       Get-NetAdapter -Name "Wi-Fi" | Select-Object Status, LinkSpeed

[ ] 3. VPN Inactive: Verify no VPN or TUN/TAP tunnels are routing default traffic:
       Get-NetAdapter | Where-Object Status -eq "Up"

[ ] 4. Silence Heavy Apps: Close heavy background downloads, torrent clients,
       cloud file sync (OneDrive/Dropbox syncing), and streaming video.

[ ] 5. Run Pre-Flight Validation CLI:
       python -m research.dataset_v3.pilot_config
       Ensure output reports: "Ready for capture: True" and "All pre-flight safety and integrity checks PASSED."

[ ] 6. Run Dry-Run Pipeline Test:
       python scripts/research/dataset_v3/run_pilot_session_1.py --dry-run
       Ensure dry-run passes cleanly with 0 published datasets and 0 files remaining in data/research_v3/.

[ ] 7. Destination Cleanliness: Verify data/research_v3 is clean of partial residue:
       Get-ChildItem -Path "data/research_v3"
```

---

## 5. Capture Execution Protocol (Human Supervisory Execution)

When pre-flight checks are verified, the operator executes the pilot session using the dedicated collection script.

### Step 5.1: Exact Execution Command
The runner script strictly requires `--confirm` to initiate physical capture. Without `--confirm`, it displays configuration parameters and exits cleanly with return code 0.

The exact physical capture command for the 60-second pilot is:
```powershell
python scripts/research/dataset_v3/run_pilot_session_1.py --confirm --duration 60
```

### Step 5.2: In-Memory Zero-Payload Privacy Boundary
During live capture:
- **Volatile In-Memory Processing**: Raw packet bytes and transient 5-tuples exist only in volatile Python objects during parsing.
- **Payload Bytes Ephemeral Handling**: Payload bytes may temporarily enter user-space memory during packet reception, but are **not intentionally inspected, parsed, or persisted**. All application-layer payloads are stripped immediately in RAM.
- **Zero Disk PII Guarantee**: Zero payload bytes, zero IP addresses, zero MAC addresses, and zero port numbers reach disk.
- **Non-Reversible Cryptographic Pseudonyms**: Client IPs are hashed using BLAKE2b with an ephemeral per-session salt.

### Step 5.3: Controlled Operator Browsing Activity
During the 60-second capture window:
1. Open Google Chrome.
2. Navigate to Wikipedia (`https://en.wikipedia.org/wiki/Encrypted_traffic`).
3. Click 2–3 related informational links (e.g. `Transport Layer Security`, `LightGBM`).
4. Keep the browsing natural and continuous until the collector timer signals completion.

### Step 5.4: Ground-Truth Label Semantics
At capture completion ($T = 60.0\text{ seconds}$):
1. **Target Web Browsing Flows**:
   - Receive `traffic_class = "Web"`, `label_quality = "VERIFIED"`, `label_source = "OPERATOR_CONTROLLED"` **ONLY when independently attributed Chrome flows** (via explicit evidence: active socket PID match, target SNI/domain match, or verified operator confirmation).
2. **Background OS Traffic (Telemetry, DNS, NTP, SSDP)**:
   - Flows lacking independent attribution evidence strictly receive:
     - `traffic_class = None`
     - `label_quality = "UNLABELLED"`
     - `label_source = "BACKGROUND_UNLABELLED"`
3. **Ambiguous / Temporal Overlap Flows**:
   - Flows active during the browsing window lacking independent attribution evidence receive:
     - `traffic_class = None`
     - `label_quality = "AMBIGUOUS"`
     - `label_source = "TEMPORAL_HEURISTIC"`
4. **Exclusive Reservation of 'Other'**:
   - `traffic_class = "Other"` is reserved **exclusively** for independently verified residual category traffic (`label_quality = "VERIFIED"`). Unlabelled or ambiguous background flows must **never** be assigned `'Other'`, preventing silent contamination of supervised training sets.
5. **Atomic Publication vs Quarantine**:
   - Manifest is finalized with kernel drop statistics and SHA-256 integrity hashes.
   - `DatasetV3Validator` automatically inspects `.staging/<session_id>/`.
   - **Upon validation pass**: Atomic rename publishes the directory to `data/research_v3/<session_id>/` with a `SESSION_COMPLETE` marker.
   - **Upon validation failure or interruption**: The session is immediately **quarantined** to `data/research_v3/.incomplete/<session_id>/` without a `SESSION_COMPLETE` marker, and the error reason is recorded.

---

## 6. Post-Capture Verification Protocol

Immediately after publication, the operator verifies session completeness using the actual random UUID generated by the runner:

```powershell
# 1. Discover the actual generated session UUID
$SESSION_ID = (Get-ChildItem -Path "data/research_v3" | Where-Object { $_.PSIsContainer -and $_.Name -like "sess_*" } | Select-Object -First 1).Name
Write-Output "Published Session UUID: $SESSION_ID"

# 2. Inspect session metadata and early-prefix distributions using actual UUID
python scripts/research/dataset_v3/inspect_session.py --session "data/research_v3/$SESSION_ID"

# 3. Run full 17-point validation suite on published session using actual UUID
python scripts/research/dataset_v3/validate_dataset.py --session "data/research_v3/$SESSION_ID"

# 4. Confirm all 5 canonical files and completion marker exist
Get-ChildItem -Path "data/research_v3/$SESSION_ID"
# Expected files:
# - session_manifest.json
# - packet_metadata.jsonl
# - flow_index.csv
# - labels.csv
# - validation_report.json
# - SESSION_COMPLETE

# 5. Confirm zero PII leaks across the research test suite
python -m pytest tests/research/dataset_v3/test_privacy_enforcement.py -v
```

---

## 7. Quarantine and Failure Handling

If network interruption, socket error, or validation failure occurs during capture:
1. The collector halts immediately.
2. The partial or invalid session is **quarantined** to `data/research_v3/.incomplete/<session_id>/`.
3. No `SESSION_COMPLETE` marker is placed in the quarantine directory.
4. The staging directory `.staging/<session_id>/` is cleaned up.
5. The production application remains untouched.
6. The quarantine log records the exact error details for diagnostic review.
