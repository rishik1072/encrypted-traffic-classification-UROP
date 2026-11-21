# Phase 2A Implementation Report: Dataset V3 Collection Infrastructure

**Project**: Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift  
**Repository**: `c:\UROP project\encrypted-traffic-classification-UROP`  
**Phase**: 2A — Dataset V3 Collection Infrastructure  
**Date**: November 2026  
**Status**: Implementation Complete; Zero Physical Captures Run; Awaiting Supervisory Review  

---

## 1. Executive Summary

Phase 2A delivers a complete, isolated, privacy-preserving, and mathematically reproducible physical traffic collection infrastructure for **Dataset V3**.

All code has been developed in a dedicated research namespace (`research/dataset_v3/`) without modifying a single line of production source code or disturbing the active live monitor processes (PIDs `23516`, `17132`, `21544`).

Key achievements of Phase 2A:
1. **Isolated Research Architecture**: Implemented 10 core modules in `research/dataset_v3/`, 3 operational CLI tools in `scripts/research/dataset_v3/`, and 14 passing unit tests in `tests/research/dataset_v3/`.
2. **Strict Physical-Only Capture Engine**: Built `PhysicalTrafficCollector`, strictly enforcing physical Npcap capture, Windows administrator permissions, and interface resolution, while explicitly barring fallback to demo, recorded, or synthetic modes.
3. **Guaranteed Zero-PII Persistence**: Architected in-memory volatile flow tracking that discards all packet payloads, MAC addresses, and IP/port strings before writing records to disk.
4. **Early-Prefix Data Preservation**: Serializes granular chronological packet metadata (`packet_metadata.jsonl`) enabling offline feature reconstruction for horizons $K \in \{1, 3, 5, 10, 20\}$.
5. **17-Point Automated Validator**: Implemented `DatasetV3Validator` enforcing schema completeness, UUID flow formatting, chronological monotonicity, synthetic exclusion, and cross-partition parent-flow isolation.
6. **Zero Disruption to Active Monitor**: Verified that running processes remain completely operational on the host adapter.

---

## 2. System Architecture and Component Inventory

```
encrypted-traffic-classification-UROP/
├── research/
│   └── dataset_v3/
│       ├── __init__.py               # Namespace exports and versioning (v3.0.0)
│       ├── schemas.py                # Strongly-typed dataclasses and controlled vocabularies
│       ├── config.py                 # Configuration dataclass and environment prerequisite validator
│       ├── packet_parser.py          # Zero-payload packet extraction and transient 5-tuple parsing
│       ├── flow_manager.py           # In-memory bidirectional flow aggregation and timeout manager
│       ├── metadata_writer.py        # Thread-safe atomic file writer (JSON, JSONL, CSV)
│       ├── manifest.py               # Session manifest builder and provenance tracker
│       ├── annotation.py             # Ground-truth labeling and background separation engine
│       ├── validator.py              # Automated 17-point scientific and privacy validator
│       └── collector.py              # Physical Npcap collection engine with lifecycle state machine
├── scripts/
│   └── research/
│       └── dataset_v3/
│           ├── validate_dataset.py           # CLI tool to audit sessions and cross-partition leakage
│           ├── inspect_session.py            # CLI tool to inspect metadata and early-prefix coverage
│           └── generate_collection_report.py # CLI tool to generate markdown progress matrices
├── tests/
│   └── research/
│       └── dataset_v3/
│           ├── test_packet_parser.py         # Tests payload stripping, headers, and protocol parsing
│           ├── test_flow_manager.py          # Tests bidirectional grouping, UUIDs, and timeouts
│           ├── test_metadata_writer.py       # Tests atomic writes and overwrite protection
│           ├── test_annotation.py            # Tests target vs. background labeling logic
│           ├── test_validator.py             # Tests 17 integrity checks and leakage detection
│           ├── test_collector_lifecycle.py   # Tests state machine, dry-run, and interface checks
│           ├── test_prefix_reconstruction.py # Tests temporal isolation across horizons K in {1, 3, 5, 10, 20}
│           └── test_privacy_enforcement.py   # Tests complete absence of IPs, MACs, and payloads on disk
└── docs/
    └── research/
        ├── DATASET_V3_COLLECTION_PROTOCOL.md   # Step-by-step physical capture protocol across 3 environments
        ├── DATASET_V3_DATA_DICTIONARY.md       # Comprehensive field-level schema reference
        ├── DATASET_V3_PRIVACY_SPECIFICATION.md # Privacy guarantees and GDPR compliance analysis
        ├── DATASET_V3_ANNOTATION_GUIDE.md      # Ground-truth labeling and noise rejection guidelines
        └── PHASE2A_IMPLEMENTATION_REPORT.md    # This authoritative report
```

---

## 3. Data Schemas and Artifact Layout

Every completed session writes into an isolated directory: `data/research_v3/<session_id>/`:

### 3.1 `packet_metadata.jsonl`
Preserves chronological packet arrival sequence for early-prefix research without persisting PII:
- `session_id: str`
- `flow_id: str` (Session-scoped random UUID4: `flow_[a-f0-9]{32}`)
- `parent_flow_id: str` (Equals `flow_id` for physical capture)
- `packet_index: int` (0-indexed sequence counter within the flow)
- `relative_timestamp_us: int` (Microseconds elapsed since flow start)
- `inter_arrival_time_us: int` (Microseconds elapsed since previous packet)
- `packet_length: int` (Wire bytes, $[20, 65535]$)
- `direction: int` (0 = first observed direction; 1 = reverse)
- `transport_protocol: str` (`TCP`, `UDP`, `OTHER`)
- `tcp_flags: Optional[int]` (TCP bitmask; null for UDP)
- `is_synthetic: bool` (Strictly `false`)

### 3.2 `flow_index.csv`
Summary index of bidirectional flow records:
`session_id, flow_id, parent_flow_id, first_packet_timestamp_utc, last_packet_timestamp_utc, packet_count, duration_us, direction_0_packets, direction_1_packets, direction_0_bytes, direction_1_bytes, transport_protocol, is_synthetic`

### 3.3 `labels.csv`
Ground-truth activity attribution:
`session_id, flow_id, traffic_class, application_alias, label_source, label_quality, annotator, annotation_timestamp`

### 3.4 `session_manifest.json`
Session-level provenance, hardware adapter tags, and environmental parameters (no hardware MACs, SSIDs, or public IPs).

### 3.5 `validation_report.json`
Automated output of `DatasetV3Validator` recording the pass/fail status of all 17 research integrity checks.

---

## 4. Packet Lifecycle and In-Memory Volatile Processing

```
[ Physical Wire: Wi-Fi / Ethernet Adapter ]
      │ Raw Ethernet Frame (MACs, IPs, Ports, Payload)
      ▼
[ packet_parser.py: parse_scapy_packet() ]
      │ Immediately strips payload bytes and MAC addresses.
      │ Produces transient in-memory tuple: (src_ip, src_port, dst_ip, dst_port, protocol)
      ▼
[ flow_manager.py: process_packet() ]
      │ Matches canonical 5-tuple: (min(ep_a, ep_b), max(ep_a, ep_b), protocol)
      │ Assigns random UUID4 flow_id (no network encoding).
      │ Calculates microsecond relative timestamp and IAT.
      │ Determines direction (0 or 1).
      ▼
[ metadata_writer.py: write_packet() ]
      │ Streams zero-PII PacketMetadataRecord to packet_metadata.jsonl.
      │ ZERO IPs, ZERO MACs, ZERO Ports written to disk.
      ▼
[ Flow Termination & Memory Wipe ]
      │ Flow times out (idle/active) or capture completes.
      │ FlowIndexRecord written to flow_index.csv.
      │ Transient 5-tuple key deleted from RAM dictionary.
      │ Full volatile wipe.
```

---

## 5. Automated 17-Point Validator Specification

The `DatasetV3Validator` evaluates all 17 research integrity checks:

| Check # | Verification Scope | Enforcement Mechanism |
| :---: | :--- | :--- |
| **1** | Missing Fields & Schema Invariants | Validates required fields across all 5 JSON/CSV artifacts. |
| **2** | Flow ID Format | Verifies regex `^flow_[a-f0-9]{32}$`. |
| **3** | Duplicate Flow IDs | Ensures complete uniqueness of flow IDs within session. |
| **4** | Parent-Flow Lineage | Asserts `parent_flow_id == flow_id` for physical capture. |
| **5** | Duplicate Packet Indices | Ensures no duplicate packet indices within any flow. |
| **6** | Monotonic Packet Ordering | Enforces consecutive packet indices and non-decreasing relative timestamps. |
| **7** | Direction Validity | Strictly enforces direction $\in \{0, 1\}$. |
| **8** | Transport Protocol Validity | Enforces protocol $\in \{\text{TCP}, \text{UDP}, \text{OTHER}\}$. |
| **9** | Traffic Class & Quality Vocabularies | Enforces 6 controlled classes and 4 label qualities. |
| **10** | Session ID Consistency | Confirms all records reference the parent session manifest ID. |
| **11** | Artifact Completeness | Checks for all 5 required session files. |
| **12** | Synthetic Sample Rejection | Strictly asserts `is_synthetic == False`. |
| **13** | Parent-Flow Partition Isolation | Asserts `train_parents & test_parents == \emptyset` across splits. |
| **14** | Session Partition Isolation | Asserts `train_sessions & test_sessions == \emptyset` across splits. |
| **15** | Supervised Label Purity | Confirms only `VERIFIED` labels enter supervised training sets. |
| **16** | Forbidden Identifier Audit | Regex scan for IPv4, IPv6, MACs, URLs in output files. |
| **17** | Accidental Payload Audit | Asserts zero payload objects or byte-dumps exist on disk. |

---

## 6. Test Suite Verification Results

All 14 unit tests in `tests/research/dataset_v3/` execute against temporary synthetic fixtures (`tmp_path`) and pass with 100% success:

```
tests/research/dataset_v3/test_annotation.py::test_ground_truth_annotation_rules PASSED [  7%]
tests/research/dataset_v3/test_collector_lifecycle.py::test_collector_dry_run_lifecycle PASSED [ 14%]
tests/research/dataset_v3/test_collector_lifecycle.py::test_collector_refuses_missing_interface PASSED [ 21%]
tests/research/dataset_v3/test_flow_manager.py::test_bidirectional_association_and_direction_assignment PASSED [ 28%]
tests/research/dataset_v3/test_flow_manager.py::test_flow_timeouts PASSED [ 35%]
tests/research/dataset_v3/test_metadata_writer.py::test_metadata_writer_lifecycle PASSED [ 42%]
tests/research/dataset_v3/test_packet_parser.py::test_parse_raw_ip_bytes_strips_payload PASSED [ 50%]
tests/research/dataset_v3/test_packet_parser.py::test_parse_scapy_packet_fixture PASSED [ 57%]
tests/research/dataset_v3/test_prefix_reconstruction.py::test_prefix_feature_isolation PASSED [ 64%]
tests/research/dataset_v3/test_privacy_enforcement.py::test_zero_pii_persistence_guarantee PASSED [ 71%]
tests/research/dataset_v3/test_validator.py::test_validator_clean_session_passes PASSED [ 78%]
tests/research/dataset_v3/test_validator.py::test_validator_detects_synthetic_contamination PASSED [ 85%]
tests/research/dataset_v3/test_validator.py::test_validator_detects_forbidden_ip_leak PASSED [ 92%]
tests/research/dataset_v3/test_validator.py::test_validator_detects_parent_flow_partition_leakage PASSED [100%]

============================= 14 passed in 0.47s ==============================
```

---

## 7. Operational Status of Running Production Monitor

The production live monitor remains active on the host and has not been interrupted:

| Process ID (PID) | Process Name | Memory (WS) | Status | Telemetry Role |
| :---: | :---: | :---: | :---: | :--- |
| **`17132`** | `python.exe` (`realtime.run`) | 88.0 MB | **ACTIVE** | Npcap physical packet capture and real-time inference on Wi-Fi adapter. |
| **`21544`** | `python.exe` (`dashboard_launcher`) | 10.5 MB | **ACTIVE** | Streamlit SOC dashboard server (`localhost:8501`). |
| **`23516`** | `python.exe` (`product.app`) | 5.6 MB | **ACTIVE** | Local REST API service (`localhost:8080`). |

---

## 8. Exact Command Sequence for Future Physical Collection (Phase 2B)

When authorized to begin actual physical traffic collection, the operator will execute the following commands in an elevated prompt:

```powershell
# Navigate to repository root
cd "C:\UROP project\encrypted-traffic-classification-UROP"
$env:PYTHONPATH="."

# 1. Capture Web traffic over Wi-Fi (60 seconds)
python -m research.dataset_v3.collector `
    --interface "Wi-Fi" `
    --adapter-type "Wi-Fi" `
    --environment "env_phys_wifi_01" `
    --class "Web" `
    --app "chrome_browsing" `
    --activity "Browsing Tranco top 50 informational websites" `
    --duration 60.0 `
    --tunnel "DIRECT" `
    --operator "operator_rishi"

# 2. Inspect the captured session
python scripts/research/dataset_v3/inspect_session.py --session "data/research_v3/<session_id>"

# 3. Validate session integrity against all 17 checks
python scripts/research/dataset_v3/validate_dataset.py --session "data/research_v3/<session_id>"

# 4. Generate collection progress summary across all environments
python scripts/research/dataset_v3/generate_collection_report.py --root "data/research_v3"
```

---

## 9. Remaining Limitations and Next Steps

1. **Hardware Host Scope**: All physical collection is presently scheduled on the development workstation. Multi-host collection across distinct hardware platforms (e.g., secondary laptops or embedded boards) remains desirable for post-pilot expansion.
2. **Pilot Dataset Objective**: The initial collection target (300–600 physical flows) serves as a **pilot calibration benchmark**. Full paper publication will require post-pilot sample size variance analysis.
3. **Phase 2A Completion**: **No physical collection was executed during this phase.** The repository is in an implementation freeze pending supervisory review.
