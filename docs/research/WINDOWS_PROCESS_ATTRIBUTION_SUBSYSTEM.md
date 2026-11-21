# Dataset V3 Windows Process-to-Socket Attribution Subsystem

**Project:** Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift  
**Component:** Dataset V3 Windows Attribution Subsystem  
**Environment:** Windows 11, Python 3.14.7, Scapy 2.5.0, Npcap 1.89  
**Status:** FULLY INTEGRATED INTO COLLECTOR ARCHITECTURE & VALIDATED VIA 183/183 RESEARCH TESTS PASSING (62/62 DEDICATED ATTRIBUTION TESTS)  

---

## 1. Executive Summary & Objective

In physical network traffic collection (such as Dataset V3 Pilot Session 1, `sess_b04fe53843b04caa8bf86e60209d3fd0`), physical Wi-Fi capture records all packet traffic transiting the network adapter. While controlled application activities (e.g. Chrome HTTPS browsing) are executed, the machine concurrently generates background system noise (Windows updates, telemetry, cloud sync services, mDNS, etc.).

Historically, flows were labeled either using temporal heuristics (e.g. marking all flows during the browsing window as Web) or marking all non-attributed flows as AMBIGUOUS (`traffic_class=None`). Under strict zero-payload privacy constraints, inspecting TLS payloads, URLs, SNI, HTTP headers, or DNS query text is forbidden.

To solve this, the **Windows Process-to-Socket Attribution Subsystem** was designed and implemented under `research/dataset_v3/attribution/`. It interrogates Windows IP Helper network tables (`GetExtendedTcpTable`, `GetExtendedUdpTable`) and process metadata (`GetProcessTimes`, `QueryFullProcessImageNameW`) to correlate in-flight network flows with the operating system processes that opened the sockets—**without inspecting or persisting any sensitive network identifiers, packet payloads, or user content**.

---

## 2. Architecture & Design Principles

```
+---------------------------------------------------------------------------------------------------+
|                                  PHYSICAL TRAFFIC CAPTURE (NPcap)                                 |
|                               (Zero-Payload Metadata Parser -> FlowManager)                       |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  | Transient 5-tuple & wire timestamps
                                                  v
+---------------------------------------------------------------------------------------------------+
|                        WINDOWS ATTRIBUTION SUBSYSTEM (Volatile Memory Only)                       |
|                                                                                                   |
|  +--------------------------------+                  +-----------------------------------------+  |
|  |     WindowsIPHelperReader      |                  |             ProcessTracker              |  |
|  |  GetExtendedTcpTable (v4/v6)   |                  |  - Controlled Chrome tree tracking      |  |
|  |  GetExtendedUdpTable (v4/v6)   |                  |  - Multi-process (Network Svc/Renderer) |  |
|  |  GetProcessTimes (CreateTime)  |                  |  - PID reuse disambiguation             |  |
|  +--------------------------------+                  +-----------------------------------------+  |
|                 |                                                          |                      |
|                 v                                                          v                      |
|  +--------------------------------+                  +-----------------------------------------+  |
|  |     SocketSnapshotManager      |                  |        ProcessSocketCorrelator          |  |
|  |  Chronological snapshot series | -------------->  |  - Bidirectional TCP 4-tuple matching   |  |
|  |  TransientSocketEntry (RAM)    |                  |  - UDP local endpoint matching          |  |
|  +--------------------------------+                  |  - 6 Canonical Evidence Categories     |  |
|                                                      +-----------------------------------------+  |
|                                                                    |                              |
|                                                                    v                              |
|                                                      +-----------------------------------------+  |
|                                                      |        AttributionEvidencePolicy        |  |
|                                                      |  - Distinguish process from traffic cls |  |
|                                                      |  - Strict non-automatic promotion       |  |
|                                                      +-----------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  | Privacy-safe compilation
                                                  v
+---------------------------------------------------------------------------------------------------+
|                       VERSIONED SIDECAR ARTIFACT (process_attribution_report.json)                |
|  - ZERO IPs, ZERO ports, ZERO PIDs, ZERO paths, ZERO URLs, ZERO payloads                          |
|  - Immutable original labels.csv and session_manifest.json preserved                             |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. Windows IP Helper APIs & Normalization

The subsystem wraps Windows native dynamic link libraries (`iphlpapi.dll` and `kernel32.dll`) via `ctypes`:

### 3.1 Socket Table Interrogation
- **`GetExtendedTcpTable`**:
  - `ulAf = AF_INET (2)` & `AF_INET6 (23)`
  - `TableClass = TCP_TABLE_OWNER_PID_ALL (5)`
  - Unpacks `MIB_TCPROW_OWNER_PID` (IPv4) and `MIB_TCP6ROW_OWNER_PID` (IPv6), extracting local IP, local port, remote IP, remote port, connection state (ESTABLISHED, CLOSE_WAIT, TIME_WAIT, etc.), and owning PID.
- **`GetExtendedUdpTable`**:
  - `ulAf = AF_INET (2)` & `AF_INET6 (23)`
  - `TableClass = UDP_TABLE_OWNER_PID (1)`
  - Unpacks `MIB_UDPROW_OWNER_PID` (IPv4) and `MIB_UDP6ROW_OWNER_PID` (IPv6), extracting local IP, local port, and owning PID.

### 3.2 Endpoint Normalization
- **Port Decoding:** Windows stores ports in network byte order in a `DWORD`. Converted via `((port & 0xFF) << 8) | ((port >> 8) & 0xFF)`.
- **IPv4 Normalization:** Normalized to canonical dotted-decimal representation.
- **IPv6 Normalization:** Normalized via `ipaddress.ip_address`, stripping interface scope IDs (`%scope_id`) and unwrapping IPv4-mapped IPv6 addresses (`::ffff:192.168.1.1` -> `192.168.1.1`).
- **Wildcard Handling:** Sockets bound to `0.0.0.0` or `::` correctly match interface IPs for listening and connection endpoints.

### 3.3 TCP Connection State Filtering
Windows returns all TCP table entries, including listening server sockets (`LISTEN`, MIB value 2) and closing/closed sockets.
- Server sockets listening on local ports (e.g. `0.0.0.0:8080`) have a remote IP of `0.0.0.0` and remote port `0`.
- If listeners were not filtered, a local server process could erroneously match outbound client traffic destined for that same port number.
- The subsystem enforces active state filtering via `ACTIVE_TCP_STATES = {"ESTABLISHED", "SYN_SENT", "SYN_RCVD", "FIN_WAIT_1", "FIN_WAIT_2", "CLOSE_WAIT", "CLOSING", "LAST_ACK", "TIME_WAIT"}`.
- Any socket entry whose state is `"LISTEN"` or `"CLOSED"` is strictly excluded from matching active network flows.

---

## 4. Multi-Process Tracking & PID Reuse Disambiguation

### 4.1 Chrome Multi-Process Architecture
Modern Google Chrome utilizes a multi-process architecture:
- **Browser Process:** Root process managing UI and tabs.
- **Network Service Process (`--type=network.mojom.NetworkService`):** Responsible for executing network socket creation, TLS handshakes, and HTTP/HTTPS transactions.
- **Renderer Processes (`--type=renderer`):** Render web pages in isolated sandboxes.
- **GPU & Utility Processes:** Audio, GPU acceleration, and helper services.

The [ProcessTracker](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/research/dataset_v3/attribution/process_tracker.py) registers the controlled Chrome root PID and automatically discovers descendant subprocesses via `CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)`. Sockets opened by either the root browser or any descendant are mapped to `application_alias = "chrome_controlled"`.

### 4.2 PID Reuse Disambiguation
Windows kernel recycles Process IDs rapidly. When an application exits, its PID may be reallocated to a completely unrelated process seconds later.
To solve this, the subsystem never identifies a process by PID alone. It queries the process creation time via `GetProcessTimes` (`PROCESS_QUERY_LIMITED_INFORMATION`):
- Process Identity is keyed by composite tuple: `(pid, create_time_utc)`.
- If an observed PID matches a previously registered Chrome PID but its creation timestamp differs, the subsystem flags **PID reuse** and categorizes the socket as `system_background` rather than `chrome_controlled`.

---

## 5. Privacy Constraints & Evidence Schema

### 5.1 Strict Ephemerality of Network Identifiers
All sensitive correlation information is kept strictly transient in volatile RAM:
- **NEVER Persisted:** Source IP, Destination IP, Source Port, Destination Port, Process ID (PID), Process Command Line, Full Executable Path, URLs, SNI, DNS text, Packet Payloads.

### 5.2 Privacy-Preserving Evidence Schema
The output evidence record ([AttributionEvidenceRecord](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/research/dataset_v3/attribution/schemas.py)) contains exclusively privacy-safe fields:

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `flow_id` | `str` | Opaque random UUID flow identifier (e.g. `flow_a1b2c3...`) |
| `evidence_method` | `str` | One of the 6 canonical evidence categories |
| `application_alias` | `Optional[str]` | Privacy-safe alias (`chrome_controlled`, `system_background`, or `None`) |
| `matched_observation_count` | `int` | Number of contemporaneous socket snapshot observations |
| `attribution_coverage_ratio` | `float` | Proportion of snapshots during flow lifetime that observed the socket (0.0 to 1.0) |
| `unique_owner` | `bool` | True if all matching snapshots agree on the single process identity |
| `evidence_quality` | `str` | Evidentiary rating (`HIGH`, `MEDIUM`, `LOW`, `UNATTRIBUTED`) |
| `attribution_rule_version` | `str` | Version identifier (`1.0.0`) |
| `rejection_reason` | `Optional[str]` | Sanitized rationale if flow was rejected or ambiguous |

### 5.3 Controlled Vocabulary & Regex Canary Auditing
To strictly prevent inadvertent information leakage via free-form text:
- **Controlled Rejection Codes (`AttributionRejectionCode`):** Rejection reasons are restricted to enumerated canonical constants (e.g. `MULTIPLE_MATCHING_PROCESSES`, `SHARED_UDP_ENDPOINT`, `INSUFFICIENT_EVIDENCE`, `PROCESS_NOT_FOUND`, etc.).
- **Controlled Application Aliases (`VALID_APPLICATION_ALIASES`):** Only designated aliases (`chrome_controlled`, `system_background`) or `None` are allowed.
- **Regex Privacy Audit:** The serialization pipeline validates every string token against strict regex patterns to reject any canary data:
  - IPv4 patterns (e.g. `127.0.0.1`, `192.168.1.1`)
  - IPv6 patterns (full, compressed `fe80::1`, and IPv4-mapped `::ffff:192.168.1.1`)
  - MAC address formats (colon and hyphen separated)
  - Explicit port markers and port numbers (e.g. `:443`, `port 8080`)
  - Process ID indicators (e.g. `pid=1234`, `"pid": 5678`)
  - Windows file paths (`C:\Program Files\...`) and UNC network paths (`\\server\share\...`)
  - Web URLs (`http://...`, `https://...`)
  - Process command-lines (e.g. `chrome.exe --type=renderer`)
- Any occurrence of these patterns raises an immediate `ValueError("Privacy violation: ...")`, preventing tainted artifacts from being written to disk.

---

## 6. The 6 Canonical Evidence Categories

The [ProcessSocketCorrelator](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/research/dataset_v3/attribution/correlator.py) classifies all flow attributions into six distinct categories:

1. **`EXACT_TCP_PROCESS_MATCH`:**  
   The flow's 4-tuple (`local_ip`, `local_port`, `remote_ip`, `remote_port`) was matched bidirectionally to a contemporaneous TCP socket with a consistent process identity.
2. **`UDP_LOCAL_ENDPOINT_PROCESS_MATCH`:**  
   The flow's local endpoint (`local_ip`, `local_port`) matched a bound UDP listener with a consistent process identity.
3. **`MULTIPLE_PROCESS_MATCH`:**  
   Multiple conflicting processes were observed on the endpoints (e.g., conflicting PIDs/aliases over time or shared UDP port).
4. **`PROCESS_NOT_FOUND`:**  
   Contemporaneous socket snapshots were recorded during the flow's lifetime, but the flow's socket was not present in the table.
5. **`STALE_SOCKET_OBSERVATION`:**  
   The socket was observed in snapshots, but exclusively outside the active flow lifetime window.
6. **`INSUFFICIENT_EVIDENCE`:**  
   Zero contemporaneous socket snapshots were recorded near the flow's active duration.

---

## 7. Evidence Promotion Policy & Sampling Density Coverage

### 7.1 Process Ownership vs. Process-Tree Membership vs. Web Browsing Intent
The subsystem maintains precise scientific distinctions:
1. **OS-Backed Process Ownership vs. Cryptographic Authenticity:** A kernel socket table entry recorded via Windows IP Helper (`GetExtendedTcpTable`) binding an IP:Port 4-tuple to an OS Process ID (PID) and creation timestamp. This provides OS-backed attribution evidence based on kernel state; it does not constitute cryptographic proof of process integrity or hardware-attested binary authenticity.
2. **Controlled Process-Tree Membership:** Kernel-level verification that the socket's owning PID belongs to the controlled Chrome instance (root process or descendant Network Service / Renderer) verified via `CreateToolhelp32Snapshot` parent-child relationships and `GetProcessTimes` creation timestamps (disambiguating recycled PIDs).
3. **Web Browsing Intent vs. Zero-Payload Boundary:** Process-tree membership proves that traffic originated from the controlled browser sandbox (`traffic_class = "Web"`). Under zero-payload and privacy constraints, the system **does not inspect** TLS payloads, URLs, SNI, HTTP headers, or DOM contents. Therefore, attribution proves browser sandbox ownership, but **cannot and does not claim** to identify which specific tab, webpage, or URL initiated a flow.

### 7.2 Canonical Traffic-Class Representation ("Web")
Dataset V3 defines canonical traffic classes in `VALID_TRAFFIC_CLASSES`: `{"Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"}`.
- The canonical ground-truth label for browser web traffic is strictly `"Web"`.
- Any legacy or synonym aliases (e.g. `"web_traffic"`, `"browsing"`, `"http"`, `"https"`) are explicitly normalized to `"Web"` via `canonicalize_traffic_class()`.
- Verified flows receive `traffic_class = "Web"` in `labels.csv` and `process_attribution_report.json`. Ambiguous or unverified flows strictly receive `traffic_class = None`.

### 7.3 Sampling Density Coverage Estimate & Boundary-Aware Maximum Gap

#### Legacy Span-Based Formula:
Previously, coverage was approximated by dividing matching snapshots by candidate snapshots in a wide $\pm 1.0$s window:
$$\text{coverage}_{\text{legacy}} = \frac{N_{\text{matched}}}{N_{\text{snapshots\_in\_window}}}$$
*Defects:* Did not measure in-flow sampling density; allowed 2 isolated observations at the flow boundaries to claim 100% coverage even if the intervening 99% of the flow was unobserved. Furthermore, internal observation gaps ignored the unobserved boundaries at flow start and flow end.

#### Documented Sampling-Density-Based Formula:
The updated implementation divides the active flow interval into discrete bins of width equal to the configured polling interval ($W = 150$ ms):
1. Expected bins:
   $$N_{\text{expected}} = \max\left(1, \left\lceil \frac{t_{\text{flow\_end}} - t_{\text{flow\_start}}}{W} \right\rceil\right) \quad (\text{if } t_{\text{flow\_end}} > t_{\text{flow\_start}})$$
2. Observed bins: Count of unique bins $b_i = \lfloor(t_{\text{obs}} - t_{\text{flow\_start}}) / W\rfloor$ containing at least one valid in-flow matching observation.
3. Multiple observations in the same bin are counted only once.
4. Observations outside the flow interval $[t_{\text{flow\_start}}, t_{\text{flow\_end}}]$ are strictly excluded from in-flow coverage.
5. Sampling coverage estimate:
   $$\text{coverage} = \min\left(1.0, \max\left(0.0, \frac{N_{\text{observed}}}{N_{\text{expected}}}\right)\right)$$
6. Zero or negative duration flows receive $\text{coverage} = 0.0$ and are strictly ineligible for HIGH quality.

> [!NOTE]
> The sidecar report documents this metric as a **sampling coverage estimate**, not proof of continuous socket ownership.

#### Boundary-Aware Maximum Observation Gap Formula:
To close the boundary loophole where long leading or trailing unobserved intervals went undetected, the maximum observation gap is computed across the full flow lifetime $[t_{\text{flow\_start}}, t_{\text{flow\_end}}]$ using sorted distinct in-flow observation timestamps $t_1 < t_2 < \dots < t_k$:

1. **Leading boundary gap:**
   $$G_{\text{start}} = \max(0.0, t_1 - t_{\text{flow\_start}})$$
2. **Internal consecutive gap ($k \ge 2$):**
   $$G_{\text{internal}} = \max_{1 \le i < k} \max(0.0, t_{i+1} - t_i)$$
3. **Trailing boundary gap:**
   $$G_{\text{end}} = \max(0.0, t_{\text{flow\_end}} - t_k)$$
4. **Overall boundary-aware maximum gap:**
   $$G_{\text{max}} = \begin{cases} \max(G_{\text{start}}, G_{\text{internal}}, G_{\text{end}}) & \text{if } k \ge 2 \\ \max(G_{\text{start}}, G_{\text{end}}) & \text{if } k = 1 \\ \text{None (unavailable)} & \text{if } k = 0 \text{ or duration} \le 0 \end{cases}$$

All gaps enforce non-negativity via `max(0.0, ...)`. Any flow where $G_{\text{max}} > 0.50$s (or $G_{\text{max}} \text{ is None}$) is disqualified from `HIGH` quality evidence with rejection reason:
`"Maximum gap between observations ({gap:.3f}s) exceeded 0.500s"`.

#### Adversarial Counterexample Resolution:
Consider a 10.0-second flow spanning $[100.00, 110.00]$ ($W = 0.15$s, $N_{\text{expected}} = 67$ bins), with observations recorded every 0.15s between $100.05$ and $105.00$ ($N_{\text{observed}} = 34$ bins, coverage = $34/67 = 50.7\%$, internal gap $0.15$s):
- **Old internal-only gap policy:** $G_{\text{internal}} = 0.15\text{s} \le 0.50\text{s}$ and $\text{coverage} = 50.7\% \ge 50\% \implies$ Erroneously promoted to `HIGH` / `VERIFIED` despite the trailing 5.0 seconds ($105.00$ to $110.00$) being completely unobserved!
- **New boundary-aware gap policy:** $G_{\text{start}} = 100.05 - 100.00 = 0.05$s, $G_{\text{internal}} = 0.15$s, $G_{\text{end}} = 110.00 - 105.00 = 5.00$s. Thus $G_{\text{max}} = 5.00\text{s} > 0.50\text{s}$. The flow is properly **rejected** with `MAX_OBSERVATION_GAP_EXCEEDED` and remains `AMBIGUOUS`.

### 7.4 Strict Promotion Criteria for `VERIFIED` Web
A flow is promoted to `VERIFIED` with canonical `traffic_class = "Web"` only when **all** of the following conditions are met:
1. `evidence_method == "EXACT_TCP_PROCESS_MATCH"`
2. `application_alias == "chrome_controlled"`
3. `unique_owner == True` (single consistent PID + creation time)
4. Positive flow duration ($t_{\text{flow\_end}} > t_{\text{flow\_start}}$)
5. `in_flow_observation_count >= 2`
6. `distinct_in_flow_timestamps >= 2`
7. `temporal_separation >= 0.10s` (consistent with 150 ms polling interval)
8. `observed_bins >= 2` (minimum 2 covered sampling bins)
9. `coverage_ratio >= 0.50` (sampling density estimate $\ge 50\%$)
10. `max_observation_gap <= 0.50s` (boundary-aware maximum gap $G_{\text{max}} \le 0.50$s)
11. `has_established_state == True` (at least one `ESTABLISHED` observation in-flow; transitional states receive `MEDIUM`)
12. Sockets exclusively in `TIME_WAIT` are treated as stale (`STALE_SOCKET_OBSERVATION`)
13. UDP local endpoint matching is strictly ineligible for `VERIFIED` (always `AMBIGUOUS`)

---

## 8. Versioned Sidecar Report Format

In compliance with immutability guarantees, original `labels.csv` and `session_manifest.json` files are never overwritten. Attribution results are serialized to a versioned sidecar artifact:
`data/research_v3/<session_id>/process_attribution_report.json`

Example Schema:
```json
{
  "session_id": "sess_example_pilot",
  "attribution_rule_version": "1.0.0",
  "total_flows": 90,
  "unique_process_matches": 62,
  "ambiguous_process_matches": 12,
  "unmatched_flows": 16,
  "tcp_evidence_count": 68,
  "udp_evidence_count": 6,
  "mean_attribution_coverage": 0.684,
  "rejection_reasons": {
    "Endpoint socket was not present in contemporaneous socket table": 14,
    "Multiple conflicting process identities observed for endpoints": 10,
    "UDP local endpoint match alone is insufficient for VERIFIED promotion": 6
  },
  "flow_attributions": [
    {
      "flow_id": "flow_8a3f...",
      "evidence_method": "EXACT_TCP_PROCESS_MATCH",
      "application_alias": "chrome_controlled",
      "matched_observation_count": 4,
      "attribution_coverage_ratio": 0.80,
      "unique_owner": true,
      "evidence_quality": "HIGH",
      "attribution_rule_version": "1.0.0",
      "rejection_reason": null
    }
  ],
  "created_at_utc": "2026-11-21T14:48:48.488308+00:00"
}
```

---

## 9. Known Limitations: TCP vs. UDP on Windows

1. **UDP Remote Endpoint Blindness:**  
   Unlike TCP tables (which record full 4-tuples), `GetExtendedUdpTable` only captures `(local_address, local_port, owning_pid)`. The remote server IP and port are unavailable at the OS table level. Consequently, UDP attribution cannot verify the destination endpoint and is fundamentally weaker than TCP attribution.
2. **Ephemeral Port Lifetime and Polling Latency:**  
   Very short-lived flows (e.g. single SYN/ACK exchanges lasting < 50ms) may terminate between periodic socket snapshot polling intervals, resulting in `PROCESS_NOT_FOUND` or `INSUFFICIENT_EVIDENCE`.
3. **Shared / SO_REUSEADDR UDP Ports:**  
   Services utilizing multicast or discovery (mDNS on UDP port 5353) frequently bind multiple processes to the identical local port, creating `MULTIPLE_PROCESS_MATCH`.
4. **Child Process Launch Delays:**  
   When Chrome spawns utility or network processes dynamically, a slight delay in process tree enumeration can occur; tracking creation times prevents incorrect attribution.

---

## 10. Verification & Test Results

### 10.1 Dedicated Attribution Unit & API Test Suite
File: [tests/research/dataset_v3/test_attribution_subsystem.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/tests/research/dataset_v3/test_attribution_subsystem.py)  
Execution: `pytest tests/research/dataset_v3/test_attribution_subsystem.py -v`  
Result: **21 passed in 0.12s (100% pass rate)**

Verified Scenarios:
1. `test_tcp_exact_endpoint_match`: Verified bidirectional 4-tuple attribution with 2+ observations.
2. `test_tcp_reverse_direction_match`: Verified bidirectional server-first flow matching.
3. `test_ipv4_and_ipv6_normalization_and_matching`: Verified IPv4, IPv6, IPv4-mapped, and wildcard normalization.
4. `test_udp_local_endpoint_ownership`: Verified local UDP port correlation and bounded evidence quality.
5. `test_shared_udp_endpoint`: Verified detection and rejection of shared UDP listeners.
6. `test_pid_reuse_disambiguation`: Verified process creation-time disambiguation on recycled PIDs.
7. `test_missing_process_in_contemporaneous_snapshots`: Verified `PROCESS_NOT_FOUND` classification.
8. `test_stale_socket_observation`: Verified `STALE_SOCKET_OBSERVATION` classification.
9. `test_multiple_matching_processes`: Verified `MULTIPLE_PROCESS_MATCH` classification.
10. `test_privacy_enforcement_audit`: Audited serialized JSON for zero IP, port, PID, path, or URL leakage.
11. `test_no_automatic_verified_promotion`: Verified strict ground-truth policy invariants.
12. `test_preservation_of_existing_dataset_v3_sessions`: Verified `sess_b04fe53843b04caa8bf86e60209d3fd0` and quarantined evidence remain 100% intact.
13. `test_actual_tcp_table_parsing_live`: Verified live Windows IPv4 TCP table retrieval and parsing.
14. `test_actual_udp_table_parsing_live`: Verified live Windows IPv4 UDP table retrieval and parsing.
15. `test_actual_ipv6_table_parsing_live`: Verified live Windows IPv6 TCP/UDP table retrieval and parsing.
16. `test_process_creation_time_validation_live`: Verified live Windows process creation time retrieval via `GetProcessTimes`.
17. `test_tcp_connection_state_filtering_ignores_listen`: Verified server sockets in `LISTEN` and `CLOSED` states are ignored.
18. `test_coverage_computation_ratio`: Verified attribution coverage ratio calculations across snapshot sets.
19. `test_controlled_chrome_hierarchy_and_unrelated_process_rejection`: Verified process tree filtering and rejection of untracked processes.
20. `test_comprehensive_privacy_canary_audit`: Verified all 16 synthetic privacy canaries are rejected by regex audits.
21. `test_complete_cleanup_of_test_processes_and_sockets`: Verified all live test sockets and sub-processes are terminated and closed.

### 10.2 Dedicated Attribution Integration & Lifecycle Test Suite
File: [tests/research/dataset_v3/test_attribution_integration.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/tests/research/dataset_v3/test_attribution_integration.py)  
Execution: `pytest tests/research/dataset_v3/test_attribution_integration.py -v`  
Result: **14 passed in 0.85s (100% pass rate)**

Verified Scenarios:
1. `test_snapshot_worker_start_and_shutdown`: Verified background worker start, execution, and deterministic shutdown.
2. `test_snapshot_worker_failure_handling`: Verified exception capture and non-crashing behavior on API error.
3. `test_monotonic_timestamp_alignment`: Verified correlation aligned to monotonic clock.
4. `test_tcp_state_dependent_evidence_quality`: Verified transitional states receive `MEDIUM` and refuse `VERIFIED`.
5. `test_time_wait_stale_evidence_rejection`: Verified unsupported `TIME_WAIT` is categorized as `STALE_SOCKET_OBSERVATION`.
6. `test_single_snapshot_observation_downgraded_to_medium`: Verified 1 snapshot is capped at `MEDIUM` quality.
7. `test_observation_timestamp_separation`: Verified observations lacking minimum separation are downgraded.
8. `test_udp_ambiguity_preservation`: Verified UDP local endpoint matching strictly stays `AMBIGUOUS`.
9. `test_controlled_chrome_launcher_lifecycle`: Verified isolated `--user-data-dir` launch and deletion upon stop.
10. `test_privacy_safe_sidecar_generation_and_integrity`: Verified sidecar format and manifest hash inclusion.
11. `test_published_pilot_session_1_immutability`: Verified Pilot Session 1 files and hashes are 100% untouched.
12. `test_quarantined_forensic_evidence_preservation`: Verified quarantined session `sess_70fc...` remains intact.
13. `test_collector_end_to_end_attribution_lifecycle`: Verified full collector capture lifecycle with attribution enabled.
14. `test_collector_attribution_failure_continues_ambiguous`: Verified collector fails safe (all flows remain `AMBIGUOUS`).

**Total Dedicated Attribution Tests: 35 passed.**

### 10.3 Sampling Density & Boundary Gap Policy Regression Suite
File: [tests/research/dataset_v3/test_attribution_sampling_policy.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/tests/research/dataset_v3/test_attribution_sampling_policy.py)  
Execution: `pytest tests/research/dataset_v3/test_attribution_sampling_policy.py -v`  
Result: **27 passed in 0.15s (100% pass rate)**

Verified Scenarios:
1. `test_long_leading_boundary_gap`: Leading gap $G_{\text{start}} = 0.80$s exceeding 0.50s rejected with `MAX_OBSERVATION_GAP_EXCEEDED`.
2. `test_long_trailing_boundary_gap`: Trailing gap $G_{\text{end}} = 1.20$s exceeding 0.50s rejected with `MAX_OBSERVATION_GAP_EXCEEDED`.
3. `test_large_internal_observation_gap`: Internal gap $G_{\text{internal}} = 1.30$s exceeding 0.50s rejected with `MAX_OBSERVATION_GAP_EXCEEDED`.
4. `test_uniform_observations_spanning_complete_flow`: Observations uniformly distributed with all gaps $\le 0.50$s and coverage $\ge 50\%$ qualify for `HIGH` quality.
5. `test_two_observations_acceptable_internal_excessive_trailing_gap`: Acceptable internal gap ($0.20$s) but trailing gap $G_{\text{end}} = 1.60$s rejected.
6. `test_two_observations_acceptable_internal_excessive_leading_gap`: Acceptable internal gap ($0.20$s) but leading gap $G_{\text{start}} = 1.60$s rejected.
7. `test_no_matching_observations`: Zero observations sets `max_gap = None` (unavailable), coverage $0.0$, and quality `UNATTRIBUTED`.
8. `test_single_matching_observation`: Single observation computes $G_{\text{max}} = \max(G_{\text{start}}, G_{\text{end}})$ and is capped at `MEDIUM` quality.
9. `test_zero_duration_flow`: Zero duration flow computes `max_gap = None`, coverage $0.0$, and rejects `HIGH` quality.
10. `test_negative_duration_flow`: Negative duration flow computes `max_gap = None`, coverage $0.0$, and rejects `HIGH` quality.
11. `test_duplicate_timestamps`: Duplicate timestamps at identical instant are deduplicated; distinct timestamps used for gap and separation.
12. `test_out_of_flow_observations_excluded_from_all_coverage_calculations`: Observations outside $[t_{\text{flow\_start}}, t_{\text{flow\_end}}]$ strictly excluded from in-flow coverage and gaps.
13. `test_exact_0_50_second_maximum_gap_boundary`: Exactly $0.500$s maximum gap qualifies for `HIGH` quality.
14. `test_maximum_gap_exact_0_500_seconds_accepted`: Policy precision test verifying raw $0.500$s maximum gap qualifies for `HIGH` quality.
15. `test_maximum_gap_0_5000001_seconds_rejected`: Policy precision test verifying raw $0.5000001$s strictly exceeds $0.500$s and is rejected with `MAX_OBSERVATION_GAP_EXCEEDED` (serialized rounded to `0.5`).
16. `test_maximum_gap_0_501_seconds_rejected`: Policy precision test verifying raw $0.501$s strictly exceeds $0.500$s and is rejected with `MAX_OBSERVATION_GAP_EXCEEDED`.
17. `test_maximum_gap_slightly_greater_than_0_50_seconds`: Maximum gap of $0.510$s rejected with `MAX_OBSERVATION_GAP_EXCEEDED`.
18. `test_ten_second_34_bin_counterexample`: Adversarial fixture ($10.0$s flow, $34$ bins, $50.7\%$ coverage, internal gap $0.15$s) rejected due to trailing gap $G_{\text{end}} = 5.0$s $> 0.50$s.
19-24. `test_correct_tcp_state_dependent_quality`: Parameterized test across ESTABLISHED (`HIGH`), SYN_SENT, SYN_RCVD, FIN_WAIT_1, CLOSE_WAIT (all `MEDIUM`), and TIME_WAIT (`UNATTRIBUTED` / stale).
25. `test_tcp_listen_and_closed_excluded`: Server listeners (`LISTEN`, `CLOSED`) strictly excluded.
26. `test_no_verified_promotion_for_udp`: UDP local endpoint matching strictly stays `AMBIGUOUS` even with 100% coverage.
27. `test_canonical_traffic_class_consistency`: Canonicalizes `"web_traffic"`, `"browsing"`, `"web"` to canonical `"Web"`.

**Total Dedicated Attribution Tests: 62 passed (21 unit/live + 14 integration + 27 sampling policy regression).**

### 10.4 Complete Research Test Suite
Execution: `pytest tests/research/ -v`  
Result: **183 passed in 9.09s (100% pass rate across entire research suite)**

---

## 11. Live Windows IP Helper API Validation Diagnostic

File: [scripts/research/dataset_v3/test_live_attribution_apis.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/scripts/research/dataset_v3/test_live_attribution_apis.py)  
Execution: `python scripts/research/dataset_v3/test_live_attribution_apis.py`  
Target: Windows 11 loopback sockets (`127.0.0.1` and `::1`), real Windows IP Helper API calls.

### 11.1 Diagnostic Verification Summary
```text
======================================================================
DATASET V3: LIVE WINDOWS ATTRIBUTION API VALIDATION
======================================================================
  Platform Windows:              True
  IP Helper DLLs Loaded:         True
  Process Creation Time Verified: True
  TCP IPv4 Connection Discovered: True
  TCP IPv4 State ESTABLISHED:    True
  TCP IPv4 Owning PID Matched:   True
  TCP Listeners Filtered:        True
  TCP IPv6 Tested:               True
  TCP IPv6 Connection Verified:  True
  UDP IPv4 Endpoint Discovered:  True
  UDP IPv4 Owning PID Matched:   True
  Shared UDP Conflict Detected:  True
  PID Reuse Prevented:           True
  Privacy Canary Audit Passed:   True
  All Test Sockets Closed:       True
----------------------------------------------------------------------
  Elapsed Verification Time:     0.006s
======================================================================
[RESULT] ALL LIVE WINDOWS ATTRIBUTION CHECKS PASSED.
```

---

## 12. Integrated Dataset V3 Collector Architecture

The Windows Process-to-Socket Attribution Subsystem is integrated into `PhysicalTrafficCollector` [[research/dataset_v3/collector.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/research/dataset_v3/collector.py)]:

```mermaid
sequenceDiagram
    autonumber
    participant Harness as PhysicalTrafficCollector
    participant SnapMgr as SocketSnapshotManager (Thread)
    participant Sniffer as AsyncSniffer (Npcap)
    participant FM as FlowManager
    participant Correlator as ProcessSocketCorrelator
    participant Policy as AttributionEvidencePolicy
    participant Writer as MetadataWriter
    participant Val as DatasetV3Validator

    Harness->>SnapMgr: start_polling() [Sample every 150ms before packet capture]
    Harness->>Sniffer: start() [Physical L2 socket capture]
    
    Note over Sniffer,FM: Active traffic: Zero-payload metadata -> FlowManager
    
    Harness->>Sniffer: stop()
    Harness->>SnapMgr: stop_polling()
    Harness->>FM: finalize_all() [Generates FlowIndexRecords; preserves transient endpoints in RAM]
    
    loop For each completed flow
        Harness->>Correlator: correlate_flow(endpoint_a, endpoint_b, wire_ts, mono_ts)
        Correlator->>Policy: evaluate_label_recommendation(evidence)
        Note over Policy: Strict check: >=2 observations, ESTABLISHED, coverage>=0.5
    end
    
    Harness->>Writer: write_attribution_report(report) [process_attribution_report.json]
    Note over Harness: Purge volatile endpoints & snapshots from RAM
    Harness->>Writer: write_labels(labels)
    Harness->>Writer: compute_artifact_hashes() [Embeds sidecar hash in manifest]
    Harness->>Val: validate_session(staging_dir)
    Harness->>Writer: publish_complete_session()
```

### 12.1 Lifecycle Guarantees & Fail-Safe Behavior
1. **Pre-Capture Sampling:** Socket snapshot worker starts sampling Windows socket tables before packet capture begins.
2. **Monotonic Timestamps:** Sampling observations record `time.monotonic()` alongside UTC epoch timestamps, eliminating clock skew and NTP jitter.
3. **Flow Finalization First:** Flows are finalized before correlation runs. Volatile endpoints are stored temporarily in RAM and wiped completely upon finalization.
4. **Fail-Safe Integrity:** If attribution fails or snapshot tables are unavailable during collection, capture continues safely if configured (`attribution_allow_failure=True`). Attribution is marked unavailable, and all flows remain `AMBIGUOUS` (`traffic_class=None`). It never fails open with fabricated labels.
5. **Sidecar Report Persistence:** The sidecar report `process_attribution_report.json` is written inside the staging directory and its SHA-256 hash is embedded into `session_manifest.json` before atomic publication.

---

## 13. Exact Files Added or Modified

### Files Added:
- `research/dataset_v3/attribution/__init__.py`: Subsystem module exports including `ControlledChromeLauncher`.
- `research/dataset_v3/attribution/schemas.py`: Privacy-safe evidence records, canary regex patterns, and controlled rejection codes.
- `research/dataset_v3/attribution/ip_helper.py`: Windows IP Helper API wrappers (`GetExtendedTcpTable`, `GetExtendedUdpTable`, `GetProcessTimes`).
- `research/dataset_v3/attribution/process_tracker.py`: Chrome multi-process tree tracker, PID reuse disambiguator, and memory clearer.
- `research/dataset_v3/attribution/snapshot_manager.py`: In-memory volatile socket snapshot manager with monotonic timestamps and 150 ms default interval.
- `research/dataset_v3/attribution/correlator.py`: Strengthened process-to-socket correlator with TCP state filtering and observation count rules.
- `research/dataset_v3/attribution/policy.py`: Ground-truth evidence policy requiring $\ge 2$ observations, ESTABLISHED state, and coverage $\ge 0.5$.
- `research/dataset_v3/attribution/report.py`: Attribution report generator and sidecar exporter with privacy canary audits.
- `research/dataset_v3/attribution/simulation.py`: Synthetic socket fixture generator and isolated simulator.
- `research/dataset_v3/attribution/chrome_launcher.py`: Controlled Chrome browser launcher with dedicated temporary `--user-data-dir` and safe cleanup.
- `scripts/research/dataset_v3/test_live_attribution_apis.py`: Standalone live Windows API validation script using loopback sockets.
- `tests/research/dataset_v3/test_attribution_subsystem.py`: 21 comprehensive unit, regression, and live Windows API tests.
- `tests/research/dataset_v3/test_attribution_integration.py`: 14 integration and lifecycle verification tests.
- `tests/research/dataset_v3/test_attribution_sampling_policy.py`: 27 sampling-density and boundary-gap policy regression tests.
- `scripts/research/dataset_v3/run_pilot_session_2.py`: Dedicated Pilot Session 2 runner with integrated Chrome workload and safety confirmation gate.
- `docs/research/WINDOWS_PROCESS_ATTRIBUTION_SUBSYSTEM.md`: Comprehensive technical specification, API audit, and integration report.

### Files Modified:
- `research/dataset_v3/config.py`: Added configurable attribution settings (`enable_attribution`, poll interval, coverage ratio, etc.).
- `research/dataset_v3/pilot_config.py`: Added `sess_pilot_002_wifi_direct_web` constants and `create_pilot_session_2_config()`.
- `research/dataset_v3/flow_manager.py`: Added in-memory volatile transient endpoint tracking and purging.
- `research/dataset_v3/metadata_writer.py`: Added sidecar report writer and included `process_attribution_report.json` in artifact hashing.
- `research/dataset_v3/validator.py`: Added sidecar privacy check in Check 16.
- `research/dataset_v3/collector.py`: Integrated pre-capture sampling, flow correlation, fail-safe handling, and memory cleanup.

### Files Preserved 100% Unmodified:
- Production application (`product/`, `capture/`, `flows/`, `models/`, `preprocessing/`).
- Published physical dataset: `data/research_v3/sess_b04fe53843b04caa8bf86e60209d3fd0/` (labels.csv and manifests intact).
- Quarantined forensic evidence: `data/research_v3/.incomplete/sess_70fc712285d34d2cb75abb02db8c1f1f/` (intact).
