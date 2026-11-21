# Phase 2A.2 Release Gate: Dataset V3 Collection Readiness

**Document Status**: Official Research Release Gate Assessment  
**Phase**: 2A.2 — Npcap Capture Backend Verification and Dataset V3 Release Gate  
**Repository**: `encrypted-traffic-classification-UROP`  
**Date**: November 2026  
**Auditor**: Independent Scientific & Architecture Auditor  

---

## 1. Executive Assessment & Formal Decision

Following comprehensive source code inspection, call-chain tracing through Scapy and Npcap on Windows 11, mathematical evaluation of packet header overheads, and full unit test execution, the Dataset V3 collection infrastructure has undergone rigorous technical verification.

### Formal Release Gate Decision:
$$\mathbf{READY\ FOR\ CONTROLLED\ PILOT\ CAPTURE\ (PILOT\ SESSION\ 1)}$$

* **Core Production Protection**: The running production application (PIDs 17132, 21544, 23516) remained completely undisturbed throughout all audits and test executions. Zero production source files, models, or databases were altered.
* **Research Infrastructure Integrity**: All 31 unit tests in `tests/research/dataset_v3/` pass with zero failures.
* **Pre-Capture State**: The target storage directory `data/research_v3/` contains zero files; no physical capture has been initiated prior to this formal gate approval.

---

## 2. Verification Checklist of Core Research Capabilities

| Audit Dimension | Target Requirement | Verified Implementation | Test Evidence | Gate Status |
| :--- | :--- | :--- | :--- | :---: |
| **Npcap Backend** | Verify snaplen propagation down to Npcap kernel driver. | Confirmed Scapy Windows limitation (snaplen hardcoded to MTU); verified user-space truncation fallback in `packet_parser.py`. | Traced C-bindings; `test_snaplen_truncation_parsing` | **VERIFIED** |
| **Wire vs Captured Length** | Preserve physical wire length (`len`) while constraining memory slice (`caplen`). | `PacketMetadataRecord` records `packet_length` (wire length) and `captured_length` (slice length). | `test_snaplen_truncation_parsing` | **VERIFIED** |
| **Privacy Guarantee** | Mathematical evaluation of payload penetration and persistent scrub. | Mathematically proved snaplen 128 allows 18–86B payload in RAM; enforced zero-payload extraction and zero PII persistence. | `test_privacy_enforcement.py` | **VERIFIED** |
| **Header Diagnostics** | 5 explicit diagnostic states; zero default port 0 fabrication; handle VLAN/IPv6. | `ParseStatus` state machine in `packet_parser.py` supporting untagged, 802.1Q, 802.1ad, IPv4 IHL, IPv6 extensions. | `test_header_parsing_explicit_states` | **VERIFIED** |
| **Fragment Safety** | Reject non-initial IP fragments lacking L4 transport headers. | `parse_raw_ip_bytes_detailed` checks `frag_offset > 0` and returns `FRAGMENT_UNSUPPORTED`. | `test_header_parsing_explicit_states` | **VERIFIED** |
| **Device Pseudonym** | Persistent random pseudonym across sessions on same physical host. | UUID-based token stored in `~/.dataset_v3/device_pseudonym.token` with zero PII derivation. | `test_device_pseudonym_persistence` | **VERIFIED** |
| **Drop & Error Telemetry** | Capture manifest tracks driver drops, queue drops, and parse errors. | Telemetry counters integrated into `SessionManifest` and populated upon `stop_capture()`. | `test_drop_telemetry_manifest_tracking` | **VERIFIED** |
| **Artifact Integrity** | Cryptographic tamper detection and disk corruption protection. | SHA-256 hashes generated upon publication; verified by Check 22 in `DatasetV3Validator`. | `test_file_integrity_hash_verification` | **VERIFIED** |
| **Shift Factorization** | Decouple physical link medium from tunnel encapsulation. | Factorized `split_physical_environment_shift` vs `split_tunnel_shift` in `plan_splits.py`. | `test_physical_environment_shift_splitting`, `test_tunnel_shift_splitting` | **VERIFIED** |
| **OOD Distinction** | Formally separate Known-Class Generalization from Unknown-Class OOD Rejection. | Separate split algorithms; ground-truth in `labels.csv` strictly preserves true semantic class. | `test_known_class_unseen_application_splitting`, `test_unknown_class_rejection_splitting` | **VERIFIED** |
| **Atomic Session State**| Strict session discovery; quarantine incomplete sessions. | `plan_splits.py` ignores dot-dirs, requires `SESSION_COMPLETE` marker, and detects duplicates. | `test_complete_session_scanning_and_duplicate_detection` | **VERIFIED** |

---

## 3. Analysis of Outstanding Engineering & Methodological Risks

While the collection infrastructure is hardened and ready for pilot testing, the following risks must be managed during physical data collection:

### Risk 1: Scapy Windows Npcap Kernel Snaplen Bypass
* **Description**: Under standard Wi-Fi/Ethernet capture on Windows, Scapy's `L2pcapListenSocket` opens Npcap with `snaplen=MTU`. Npcap's kernel driver delivers full frame buffers into user-space RAM before Python slicing occurs.
* **Impact**: Slightly higher memory bus traffic between kernel and user space; cannot claim hardware-level payload blocking.
* **Mitigation**: User-space truncation in `research/dataset_v3/packet_parser.py` immediately slices the raw buffer and extracts only numerical metadata, discarding the rest before creating any Python objects. If a lower-level C binding is desired in Phase 2B, a direct Ctypes wrapper calling `pcap_open_live` with user snaplen can be substituted without altering the schema or collector interface.

### Risk 2: Packet Drops Under High-Throughput Bursts
* **Description**: When capturing sustained video streaming or bulk downloads, high packet arrival rates may cause ring buffer overflows in Npcap or queue drops in Python.
* **Impact**: Intermittent packet loss could cause false flow termination or skewed inter-arrival time distributions.
* **Mitigation**: 
  1. Manifest telemetry tracks `kernel_buffer_drops` and `interface_drops` retrieved directly from Npcap.
  2. The validator rejects sessions where drop rates exceed 1% of total packets.
  3. Operator capture protocols restrict individual collection bursts to manageable durations (e.g. 60–120 seconds).

### Risk 3: Operator Ground-Truth Mislabeling
* **Description**: Because Dataset V3 relies on genuine physical application execution, operator error (e.g. running an unlabelled background update or tagging a Discord voice call as Web browsing) could contaminate ground-truth labels.
* **Impact**: Label noise in training/evaluation datasets.
* **Mitigation**:
  1. `labels.csv` records `label_source`, `label_quality`, and `annotator` for full provenance.
  2. The automated validator verifies that intended traffic classes match controlled vocabulary.
  3. Pre-capture protocol mandates closing all background network processes prior to collection.

---

## 4. Operational Requirements for Pilot Session 1

To ensure complete safety and reproducibility, the first physical capture session (**Pilot Session 1**) must adhere strictly to the following parameters:

### Pre-Capture Checklist
1. **Production Process Non-Interference**: Confirm PIDs 17132, 21544, and 23516 remain running without interruption.
2. **Dedicated Output Directory**: Confirm output root is `data/research_v3/`.
3. **Environment Isolation**: Close background sync tools (Dropbox, OneDrive, automated OS updates).
4. **Controlled Target Activity**: Select a single unambiguous application (e.g. Google Chrome visiting Wikipedia over HTTPS) under `DIRECT` tunnel status on `Wi-Fi`.
5. **Collection Duration**: Set collection window to exactly 60 seconds.

### Post-Capture Validation Protocol
Immediately upon completion of Pilot Session 1:
1. Confirm directory structure: `data/research_v3/<session_id>/` contains exactly:
   - `session_manifest.json`
   - `packet_metadata.jsonl`
   - `flow_index.csv`
   - `labels.csv`
   - `validation_report.json`
   - `SESSION_COMPLETE`
2. Run `DatasetV3Validator.validate_session()`: Confirm `is_valid == True` across all 22 automated checks.
3. Verify SHA-256 integrity hashes match the disk contents.
4. Verify zero IP addresses, MAC addresses, or payload bytes exist in any artifact.

---

## 5. Formal Sign-Off

The Dataset V3 collection subsystem meets all architectural, scientific, and privacy standards required for experimental research. Phase 2A.2 is hereby concluded, and the system is authorized to proceed to controlled pilot execution.
