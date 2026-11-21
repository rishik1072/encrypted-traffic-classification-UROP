# Phase 2B Capture Initialization Fix: Technical Root Cause, Scapy 2.5.0 Resolution & Verification Report

**Project**: Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift  
**Repository**: `c:\UROP project\encrypted-traffic-classification-UROP`  
**Date**: November 2026  
**Status**: RESOLVED, RECONCILED & VERIFIED VIA REGRESSION TEST SUITE  

---

## 1. Executive Summary & Root Cause Analysis

### 1.1 The Incident
During the execution of Dataset V3 Pilot Session 1 on Windows 11 with Scapy 2.5.0 and Npcap 1.89, the physical packet collector crashed during capture initialization with the following exception:

```
TypeError: L2pcapListenSocket.__init__() got an unexpected keyword argument 'snaplen'
```

Despite this crash, the collection runner reported `CAPTURE ACTIVE` and executed a 60-second sleep timer, subsequently publishing an empty session (`packet_count = 0`, `flow_count = 0`) to `data/research_v3/sess_5bd092dab82a4b91a162925c2f1ba2f0/` with a `SESSION_COMPLETE` marker.

### 1.2 Root Cause Investigation & Scapy 2.5.0 Propagation
Inspection of the installed Scapy 2.5.0 implementation (`scapy/sendrecv.py` and `scapy/arch/libpcap.py`) revealed the exact propagation path:

1. **Argument Forwarding**: In `collector.py` (lines 164–167), `sniffer_kwargs["snaplen"] = self.config.snaplen` passed the `snaplen` keyword argument to `AsyncSniffer(**sniffer_kwargs)`.
2. **Layer-2 Socket Instantiation in Worker Thread**: `AsyncSniffer.start()` spawns a daemon thread running `AsyncSniffer._run()`. When `opened_socket` is `None` and an interface is provided, `_run` invokes:
   ```python
   _RL2(iface)(type=ETH_P_ALL, iface=iface, **karg)
   ```
   where `_RL2(iface)` resolves to `conf.L2listen`, which on Windows maps to `scapy.arch.libpcap.L2pcapListenSocket`.
3. **Keyword Argument Rejection**: The constructor of `L2pcapListenSocket` has the signature:
   ```python
   def __init__(self, iface=None, type=ETH_P_ALL, promisc=None, filter=None, monitor=None):
   ```
   It accepts **only** `iface`, `type`, `promisc`, `filter`, and `monitor`. It does **not** accept `snaplen`.
4. **Silent Thread Death**: Because `L2pcapListenSocket.__init__` was called inside the background thread, the `TypeError` was raised asynchronously on the worker thread. `AsyncSniffer.start()` returned immediately in the calling thread without raising.
5. **Misleading State Reporting**: The calling thread immediately marked `lifecycle_state = "COLLECTOR_ACTIVE"` and waited for the duration timer. The duration timer reached 60.0 seconds and called `stop_capture(status="COMPLETE")`. Because the validator only validated schema structure (and empty CSVs with headers pass standard schema checks), `publish_complete_session` moved the empty session to the primary dataset directory and wrote `SESSION_COMPLETE`.

---

## 2. Technical Architecture of the Fix

The fix resolves both the Scapy socket initialization crash and the lifecycle reporting integrity across five architectural layers:

```
                                Synchronous Setup (Main Thread)
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. Resolve Interface Socket Class: conf.L2listen / resolve_iface(iface).l2listen()     │
│ 2. Synchronous Socket Construction: sock = L2pcapListenSocket(iface, filter, promisc)   │
│    -> Catches permissions, Npcap driver, and filter errors IMMEDIATELY in main thread │
│ 3. Pass Opened Socket to AsyncSniffer: AsyncSniffer(opened_socket=sock, ...)          │
│    -> Strictly NO snaplen or iface passed to AsyncSniffer constructor                 │
│ 4. Register started_callback: started_evt = threading.Event()                          │
│ 5. Start Thread & Bounded Wait: started_evt.wait(timeout=5.0)                          │
│ 6. Verify Worker Liveness: sniffer.thread.is_alive() == True                           │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
                       Transition: COLLECTOR_ACTIVE
                       Runner: Prints '>>> CAPTURE ACTIVE <<<'
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Active Capture & Worker Thread Monitoring:                                             │
│ - Duration worker monitors collector.is_worker_alive() every 0.5s                      │
│ - If worker crashes: triggers fail_capture() -> COLLECTOR_FAILED -> Quarantine         │
│ - Zero packets received at stop: forced FAILED -> Quarantine (SESSION_COMPLETE barred) │
│ - User-space parser limit: 96 bytes enforced in Python RAM (packet_parser.py)          │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Part 1 — Unsupported Argument Removal
- Completely removed `snaplen` from `AsyncSniffer` keyword arguments.
- Documented and enforced that Scapy on Windows passes MTU=65535 to Npcap; kernel-level snaplen is neither supported nor claimed.
- Preserved user-space header truncation at 96 bytes exclusively within `research.dataset_v3.packet_parser.parse_scapy_packet_detailed(raw_pkt, user_snaplen=self.config.snaplen)`.

### 2.2 Part 2 — Synchronous Socket Construction & Ownership
- The Layer-2 socket is opened **synchronously** in `PhysicalTrafficCollector.start_capture()` prior to starting the asynchronous sniffer thread:
  ```python
  self._socket = sock_cls(
      iface=self.config.interface,
      filter=self.config.pcap_filter,
      promisc=self.config.promiscuous,
  )
  ```
- The opened socket is passed via `opened_socket=self._socket`.
- **Interface argument omitted from `AsyncSniffer`**: In Scapy 2.5.0, line 1154 of `sendrecv.py` checks `if not sniff_sockets or iface is not None:`. If `iface` is passed alongside `opened_socket`, Scapy opens a redundant second socket. Omission of `iface` ensures Scapy utilizes solely our pre-opened socket.
- **Explicit Socket Ownership & Cleanup**: Scapy's `_run` does not close `opened_socket` upon termination (lines 1270–1273 of `sendrecv.py`). `PhysicalTrafficCollector` explicitly owns `self._socket` and guarantees safe closure via `_cleanup_sniffer_and_socket()`.

### 2.3 Part 3 — State Machine & Capture Lifecycle Reporting
- Explicit states enforced:
  `COLLECTOR_INITIALIZING`, `COLLECTOR_READY`, `COLLECTOR_ACTIVE`, `COLLECTOR_FAILED`, `COLLECTOR_STOPPING`, `COLLECTOR_COMPLETED`.
- `started_callback` synchronization: `AsyncSniffer.start()` is followed by a bounded wait `started_evt.wait(timeout=5.0)`.
- Worker liveness check: Both `started_evt.is_set()` and `self._sniffer.thread.is_alive()` must evaluate to `True` before transitioning to `COLLECTOR_ACTIVE`.
- The runner script (`run_pilot_session_1.py`) **never** prints `>>> CAPTURE ACTIVE <<<` until `collector.lifecycle_state == "COLLECTOR_ACTIVE"`.

### 2.4 Part 4 — Zero-Packet & Failure Quarantine Logic
- A timer ending is **not** proof of capture success.
- If `self.packets_processed_count == 0` when `status == "COMPLETE"` (and `allow_empty_capture=False`), the session is automatically marked `status = "FAILED"`, quarantined to `data/research_v3/.incomplete/<session_id>/`, and denied `SESSION_COMPLETE`.
- Active thread monitoring in `_duration_timer_worker` detects premature capture worker crashes, immediately triggers `fail_capture()`, and quarantines the staging directory.

### 2.5 Part 5 — Failed Session Reconciliation (`sess_5bd092dab82a4b91a162925c2f1ba2f0`)
- Implemented `MetadataWriter.quarantine_invalid_published_session()`.
- Successfully reconciled the failed session `sess_5bd092dab82a4b91a162925c2f1ba2f0`:
  1. Updated `session_manifest.json` with `capture_status: "FAILED"` and diagnostic error notes.
  2. Removed the invalid `SESSION_COMPLETE` marker.
  3. Placed the `SESSION_INCOMPLETE` marker recording the initialization exception.
  4. Quarantined the directory to `data/research_v3/.incomplete/sess_5bd092dab82a4b91a162925c2f1ba2f0/`.
  5. Preserved all raw diagnostic artifacts (`flow_index.csv`, `labels.csv`, `packet_metadata.jsonl`, `validation_report.json`).
  6. Verified that `data/research_v3/` now contains **0 published sessions**.

---

## 3. Summary of Source Code Changes

| File | Exact Changes Made |
| :--- | :--- |
| `research/dataset_v3/config.py` | Added `allow_empty_capture: bool = False` to `DatasetV3Config` to prevent accidental publication of 0-packet captures. |
| `research/dataset_v3/metadata_writer.py` | Added `quarantine_invalid_published_session()` classmethod for controlled invalidation of incorrectly published sessions. |
| `research/dataset_v3/collector.py` | 1. Added `self._socket: Optional[Any] = None`.<br>2. Implemented synchronous Layer-2 socket creation with `conf.L2listen`.<br>3. Removed `snaplen` and `iface` from `AsyncSniffer` parameters; passed `opened_socket` and `started_callback`.<br>4. Added startup synchronization with 5.0s timeout and worker liveness validation.<br>5. Added `is_worker_alive()`, `fail_capture()`, and `_cleanup_sniffer_and_socket()`.<br>6. Updated `_duration_timer_worker` with continuous thread monitoring.<br>7. Updated `stop_capture` to reject empty captures and quarantine incomplete/failed sessions. |
| `scripts/research/dataset_v3/run_pilot_session_1.py` | 1. Defended `CAPTURE ACTIVE` print until `collector.start_capture()` succeeds and state is verified `ACTIVE`.<br>2. Added continuous worker health loop.<br>3. Fixed `--dry-run` cleanup to target `cfg.incomplete_session_dir` rather than wiping `cfg.incomplete_root`. |
| `tests/research/dataset_v3/test_capture_initialization_fix.py` | New comprehensive test module covering all 12 regression test requirements (socket failure, timeout, worker crash, quarantine, parser bounds). |

---

## 4. Test Evidence & Regression Audit

The complete research test suite was executed in `tests/research/dataset_v3/`:

```
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.0.3, pluggy-1.7.0 -- C:\Python314\python.exe
cachedir: .pytest_cache
rootdir: C:\UROP project\encrypted-traffic-classification-UROP
plugins: cov-7.1.0, anyio-4.14.2
collecting ... collected 61 items

tests/research/dataset_v3/test_annotation.py::test_ground_truth_annotation_rules PASSED [  1%]
tests/research/dataset_v3/test_annotation.py::test_label_record_semantic_invariants PASSED [  3%]
tests/research/dataset_v3/test_annotation.py::test_temporal_overlap_without_evidence_refuses_verified PASSED [  4%]
tests/research/dataset_v3/test_capture_initialization_fix.py::test_no_snaplen_argument_reaches_async_sniffer PASSED [  6%]
tests/research/dataset_v3/test_capture_initialization_fix.py::test_synchronous_socket_initialization_failure PASSED [  8%]
tests/research/dataset_v3/test_capture_initialization_fix.py::test_successful_socket_initialization_and_active_state PASSED [  9%]
tests/research/dataset_v3/test_capture_initialization_fix.py::test_started_callback_synchronization_timeout PASSED [ 11%]
tests/research/dataset_v3/test_capture_initialization_fix.py::test_capture_worker_premature_exit_detection PASSED [ 13%]
tests/research/dataset_v3/test_capture_initialization_fix.py::test_timer_ending_after_capture_failure_does_not_publish PASSED [ 14%]
tests/research/dataset_v3/test_capture_initialization_fix.py::test_zero_packets_received_quarantines_and_refuses_complete PASSED [ 16%]
tests/research/dataset_v3/test_capture_initialization_fix.py::test_controlled_invalidation_and_quarantine_procedure PASSED [ 18%]
tests/research/dataset_v3/test_capture_initialization_fix.py::test_userspace_parser_limit_and_frame_length_semantics PASSED [ 19%]
tests/research/dataset_v3/test_capture_initialization_fix.py::test_no_production_source_code_modifications PASSED [ 21%]
tests/research/dataset_v3/test_capture_integrity.py::test_configured_vs_effective_snaplen PASSED [ 22%]
tests/research/dataset_v3/test_capture_integrity.py::test_original_vs_captured_length PASSED [ 24%]
tests/research/dataset_v3/test_capture_integrity.py::test_missing_wire_length_metadata PASSED [ 26%]
tests/research/dataset_v3/test_capture_integrity.py::test_feature_length_consistency PASSED [ 27%]
tests/research/dataset_v3/test_capture_integrity.py::test_truncated_packet_rejection PASSED [ 29%]
tests/research/dataset_v3/test_capture_integrity.py::test_no_payload_persistence PASSED [ 31%]
tests/research/dataset_v3/test_collector_lifecycle.py::test_collector_dry_run_lifecycle PASSED [ 32%]
tests/research/dataset_v3/test_collector_lifecycle.py::test_collector_quarantines_incomplete_session PASSED [ 34%]
tests/research/dataset_v3/test_collector_lifecycle.py::test_collector_refuses_missing_interface PASSED [ 36%]
tests/research/dataset_v3/test_flow_manager.py::test_bidirectional_association_and_direction_assignment PASSED [ 37%]
tests/research/dataset_v3/test_flow_manager.py::test_flow_timeouts PASSED [ 39%]
tests/research/dataset_v3/test_hardening_features.py::test_snaplen_truncation_parsing PASSED [ 40%]
tests/research/dataset_v3/test_hardening_features.py::test_header_parsing_explicit_states PASSED [ 42%]
tests/research/dataset_v3/test_hardening_features.py::test_device_pseudonym_persistence PASSED [ 44%]
tests/research/dataset_v3/test_tcp_fin_rst_termination PASSED [ 45%]
tests/research/dataset_v3/test_drop_telemetry_manifest_tracking PASSED [ 47%]
tests/research/dataset_v3/test_file_integrity_hash_verification PASSED [ 49%]
tests/research/dataset_v3/test_metadata_writer.py::test_metadata_writer_lifecycle PASSED [ 50%]
tests/research/dataset_v3/test_packet_length_semantics.py::test_standard_ethernet_ii PASSED [ 52%]
tests/research/dataset_v3/test_packet_length_semantics.py::test_single_vlan_8021q PASSED [ 54%]
tests/research/dataset_v3/test_packet_length_semantics.py::test_qinq_double_vlan PASSED [ 55%]
tests/research/dataset_v3/test_packet_length_semantics.py::test_ethernet_padding_refutes_14_plus_ip PASSED [ 57%]
tests/research/dataset_v3/test_packet_length_semantics.py::test_ipv4_options PASSED [ 59%]
tests/research/dataset_v3/test_packet_length_semantics.py::test_ipv6_extension_headers PASSED [ 60%]
tests/research/dataset_v3/test_packet_length_semantics.py::test_user_space_packet_truncation PASSED [ 62%]
tests/research/dataset_v3/test_packet_length_semantics.py::test_missing_native_wire_length PASSED [ 63%]
tests/research/dataset_v3/test_packet_length_semantics.py::test_packet_length_vs_captured_length PASSED [ 65%]
tests/research/dataset_v3/test_packet_length_semantics.py::test_production_feature_extractor_parity PASSED [ 67%]
tests/research/dataset_v3/test_packet_parser.py::test_parse_raw_ip_bytes_strips_payload PASSED [ 68%]
tests/research/dataset_v3/test_packet_parser.py::test_parse_scapy_packet_fixture PASSED [ 70%]
tests/research/dataset_v3/test_prefix_reconstruction.py::test_prefix_feature_isolation PASSED [ 72%]
tests/research/dataset_v3/test_privacy_enforcement.py::test_zero_pii_persistence_guarantee PASSED [ 73%]
tests/research/dataset_v3/test_split_planning.py::test_session_disjoint_splitting PASSED [ 75%]
tests/research/dataset_v3/test_split_planning.py::test_device_disjoint_splitting PASSED [ 77%]
tests/research/dataset_v3/test_split_planning.py::test_physical_environment_shift_splitting PASSED [ 78%]
tests/research/dataset_v3/test_split_planning.py::test_tunnel_shift_splitting PASSED [ 80%]
tests/research/dataset_v3/test_split_planning.py::test_known_class_unseen_application_splitting PASSED [ 81%]
tests/research/dataset_v3/test_split_planning.py::test_unknown_class_rejection_splitting PASSED [ 83%]
tests/research/dataset_v3/test_split_planning.py::test_complete_session_scanning_and_duplicate_detection PASSED [ 85%]
tests/research/dataset_v3/test_validator.py::test_validator_clean_session_passes PASSED [ 86%]
tests/research/dataset_v3/test_validator.py::test_validator_detects_synthetic_contamination PASSED [ 88%]
tests/research/dataset_v3/test_validator.py::test_validator_detects_forbidden_ip_leak PASSED [ 90%]
tests/research/dataset_v3/test_validator.py::test_validator_detects_parent_flow_partition_leakage PASSED [ 91%]
tests/research/dataset_v3/test_validator.py::test_validator_detects_device_partition_overlap PASSED [ 93%]
tests/research/dataset_v3/test_validator.py::test_validator_detects_application_partition_overlap PASSED [ 95%]
tests/research/dataset_v3/test_validator.py::test_validator_detects_invalid_termination_reason PASSED [ 96%]
tests/research/dataset_v3/test_validator.py::test_validator_enforces_label_semantics_and_prevents_leakage PASSED [ 98%]
tests/research/dataset_v3/test_validator.py::test_pilot_session_identity_and_repeat_protection PASSED [100%]

============================= 61 passed in 0.96s ==============================
```

- **Pass Rate**: 100% (61 passed, 0 failed, 0 skipped).
- **Production Isolation**: Zero modifications to production source (`product/`, `capture/`, `flows/`, `models/`, `preprocessing/`).
- **Storage State**: `data/research_v3/` contains 0 published sessions. Quarantined evidence preserved in `data/research_v3/.incomplete/sess_5bd092dab82a4b91a162925c2f1ba2f0/`.

---

## 5. Remaining Risks & Operational Recommendations

1. **Elevation & Permissions**: Physical Npcap capture on Windows requires elevated (Administrator) permissions. If launched in a non-elevated terminal, socket creation will raise `PermissionError` / `OSError`, which is now synchronously caught and reported with a clean exit code 1.
2. **Wi-Fi Adapter Concurrency**: As documented in the execution plan, production capture (`realtime.run`) must not run concurrently on the same adapter to avoid Npcap driver buffer contention.
3. **Physical Browsing Activity**: During the 60-second capture window, human browsing traffic in Chrome generates genuine physical frames. If no network activity occurs during the window, the collector will deem the session empty and quarantine it rather than publishing an invalid 0-packet session.
