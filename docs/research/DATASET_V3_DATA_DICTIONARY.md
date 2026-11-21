# Dataset V3 Data Dictionary and Schema Reference

**Project**: Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift  
**Document**: Authoritative Field-Level Schema Specification  
**Date**: November 2026  
**Status**: Authoritative Technical Standard (Phase 2A)

---

## 1. Overview and Directory Structure

Every completed Dataset V3 session is persisted in an isolated subdirectory:
`data/research_v3/<session_id>/`

Containing exactly five standardized artifacts:
1. `session_manifest.json`: Top-level session provenance and environmental tags.
2. `packet_metadata.jsonl`: Chronological stream of zero-payload packet arrival records.
3. `flow_index.csv`: Bidirectional flow summary index.
4. `labels.csv`: Ground-truth label assignments.
5. `validation_report.json`: Automated 17-point integrity report.

---

## 2. Packet Metadata Stream (`packet_metadata.jsonl`)

Each line is a self-contained JSON object recording a single packet arrival.

| Field Name | Type | Units / Format | Nullable? | Description | Constraints & Invariants |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `session_id` | `string` | Regex `^sess_v3_.*` | No | Unique session identifier. | Matches directory name and manifest. |
| `flow_id` | `string` | Regex `^flow_[a-f0-9]{32}$` | No | Cryptographically random UUID4. | Assigned upon first packet of 5-tuple. |
| `parent_flow_id`| `string` | Regex `^flow_[a-f0-9]{32}$` | No | Ancestral prototype flow identifier. | **Must equal `flow_id` for physical capture.** |
| `packet_index` | `integer`| 0, 1, 2, ... | No | 0-indexed sequence counter within the flow. | Strictly monotonic consecutive integers. |
| `relative_timestamp_us` | `integer` | Microseconds ($\mu\text{s}$) | No | Time elapsed since packet index 0 of this flow. | Monotonically non-decreasing ($\ge 0$). |
| `inter_arrival_time_us` | `integer` | Microseconds ($\mu\text{s}$) | No | Time elapsed since previous packet in this flow. | $\ge 0$; equals 0 for packet index 0. |
| `packet_length` | `integer`| Bytes | No | Total wire length of the packet frame on the network medium. | In range $[20, 65535]$. |
| `captured_length` | `integer`| Bytes | No | Length captured into user-space volatile memory ($\le$ `packet_length` if snaplen truncated). | In range $[20, \text{packet\_length}]$. |
| `direction` | `integer`| `0` or `1` | No | Direction relative to initial packet. | `0` = forward (same as pkt 0); `1` = reverse. |
| `transport_protocol` | `string` | Categorical | No | Transport layer protocol. | One of `{"TCP", "UDP", "OTHER"}`. |
| `tcp_flags` | `integer`| Bitmask | Yes | TCP header flag byte. | Present only if `transport_protocol == "TCP"`. |
| `is_synthetic` | `boolean`| `false` | No | Synthetic flag. | **Must be strictly `false`.** |

---

## 3. Flow Index Summary (`flow_index.csv`)

CSV table providing aggregated summary statistics for each bidirectional flow.

| Column Header | Type | Description | Invariants |
| :--- | :--- | :--- | :--- |
| `session_id` | `string` | Session identifier. | Matches `packet_metadata.jsonl`. |
| `flow_id` | `string` | Unique flow identifier. | Primary key in flow index. |
| `parent_flow_id` | `string` | Prototype flow identifier. | Equals `flow_id`. |
| `first_packet_timestamp_utc` | `string` (ISO 8601) | Timestamp of first packet in UTC. | e.g., `2026-11-20T12:00:00.123456+00:00`. |
| `last_packet_timestamp_utc` | `string` (ISO 8601) | Timestamp of final packet in UTC. | $\ge$ first packet timestamp. |
| `packet_count` | `integer` | Total packets observed in flow. | $\ge 1$; equals direction_0 + direction_1. |
| `duration_us` | `integer` | Total flow lifespan in microseconds. | Equals last minus first timestamp. |
| `direction_0_packets` | `integer` | Packets in forward direction. | $\ge 1$. |
| `direction_1_packets` | `integer` | Packets in reverse direction. | $\ge 0$. |
| `direction_0_bytes` | `integer` | Bytes transmitted in forward direction. | $\ge 20$. |
| `direction_1_bytes` | `integer` | Bytes transmitted in reverse direction. | $\ge 0$. |
| `transport_protocol` | `string` | Transport protocol (`TCP`, `UDP`, `OTHER`). | Matches packet stream. |
| `termination_reason` | `string` | Reason flow completed (`TCP_FIN`, `TCP_RST`, `IDLE_TIMEOUT`, `ACTIVE_TIMEOUT`, `CAPTURE_END`, `UNKNOWN`). | One of `VALID_TERMINATION_REASONS`. |
| `prefix_3_available` | `boolean` | Flag indicating whether $\ge 3$ packets were observed. | Matches `packet_count >= 3`. |
| `prefix_5_available` | `boolean` | Flag indicating whether $\ge 5$ packets were observed. | Matches `packet_count >= 5`. |
| `prefix_10_available` | `boolean` | Flag indicating whether $\ge 10$ packets were observed. | Matches `packet_count >= 10`. |
| `prefix_20_available` | `boolean` | Flag indicating whether $\ge 20$ packets were observed. | Matches `packet_count >= 20`. |
| `is_synthetic` | `boolean` | Synthetic flag (`False`). | Strictly `False`. |

---

## 4. Ground-Truth Labels (`labels.csv`)

CSV table recording verified ground-truth labels assigned to flows. Decouples label quality (certainty of application origin) from packet prefix depth.

| Column Header | Type | Permitted Values | Description |
| :--- | :--- | :--- | :--- |
| `session_id` | `string` | Text | Session identifier. |
| `flow_id` | `string` | `flow_[a-f0-9]{32}` | References `flow_index.csv`. |
| `traffic_class` | `string` | `Web`, `Video`, `Messaging`, `VoIP`, `File Transfer`, `Other` | Controlled traffic class. |
| `application_alias` | `string` | e.g., `chrome_browsing`, `discord_voice` | Generating application software. |
| `label_source` | `string` | `OPERATOR_CONTROLLED`, `INDEPENDENT_VERIFICATION`, `BACKGROUND_UNLABELLED`, `MANUAL_AUDIT` | Attribution mechanism. |
| `label_quality` | `string` | `VERIFIED`, `AMBIGUOUS`, `UNLABELLED`, `EXCLUDED` | Data quality status (origin certainty). |
| `annotator` | `string` | Operator identifier | Identity of human researcher. |
| `annotation_timestamp` | `string` | ISO 8601 UTC timestamp | Date and time label was assigned. |
| `packet_count` | `integer` | $\ge 1$ | Total flow packet count. |
| `prefix_3_available` | `boolean` | `true`, `false` | Availability of $\ge 3$ packets for prefix model. |
| `prefix_5_available` | `boolean` | `true`, `false` | Availability of $\ge 5$ packets for prefix model. |
| `prefix_10_available` | `boolean` | `true`, `false` | Availability of $\ge 10$ packets for prefix model. |
| `prefix_20_available` | `boolean` | `true`, `false` | Availability of $\ge 20$ packets for prefix model. |

---

## 5. Session Manifest (`session_manifest.json`)

Top-level metadata document serialized as formatted JSON.

```json
{
  "session_id": "sess_v3_20261120_143000_web_a1b2c3",
  "collection_start_utc": "2026-11-20T14:30:00.100000+00:00",
  "collection_end_utc": "2026-11-20T14:31:30.500000+00:00",
  "collector_version": "3.0.0",
  "operating_system": "Windows 11 (AMD64)",
  "device_pseudonym": "dev_pseudonym_9a8b7c6d",
  "adapter_type": "Wi-Fi",
  "environment_id": "env_phys_wifi_01",
  "tunnel_status": "DIRECT",
  "collection_activity": "Controlled Alexa top 50 browsing",
  "application_alias": "chrome_browsing",
  "intended_traffic_class": "Web",
  "collection_operator_label": "operator_rishi",
  "capture_status": "COMPLETE",
  "packet_count": 1420,
  "flow_count": 12,
  "label_quality": "VERIFIED",
  "collection_day": "2026-11-20",
  "snaplen": 128,
  "kernel_buffer_drops": 0,
  "interface_drops": 0,
  "queue_drops": 0,
  "parsing_failures": 0,
  "processing_failures": 0,
  "notes": "Clean session, no background streaming."
}
```

---

## 6. Mathematical Early-Prefix Horizon Reconstruction

Because `packet_metadata.jsonl` preserves raw packet lengths, directions, and microsecond timestamps without pre-aggregating full flows, any early prefix $K \in \{1, 3, 5, 10, 20\}$ can be reconstructed by filtering:
$$\mathcal{P}_K = \{p \in \text{Flow} \mid p.\text{packet\_index} < K\}$$

### Available Mathematical Features by Prefix Horizon

| Feature Description | Mathematical Formula | $K=1$ | $K=3$ | $K=5$ | $K=10$ |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Prefix Packet Count** | $|\mathcal{P}_K|$ | Available ($1$) | Available ($3$) | Available ($5$) | Available ($10$) |
| **Prefix Duration ($\mu\text{s}$)** | $p_{K-1}.\text{relative\_timestamp\_us}$ | $0.0$ | Available | Available | Available |
| **Forward Packet Count** | $\sum_{p \in \mathcal{P}_K} \mathbb{I}(p.\text{direction} == 0)$ | Available ($1$) | Available | Available | Available |
| **Backward Packet Count** | $\sum_{p \in \mathcal{P}_K} \mathbb{I}(p.\text{direction} == 1)$ | $0$ | Available | Available | Available |
| **Forward Bytes** | $\sum_{p \in \mathcal{P}_K, d=0} p.\text{packet\_length}$ | Available | Available | Available | Available |
| **Backward Bytes** | $\sum_{p \in \mathcal{P}_K, d=1} p.\text{packet\_length}$ | $0$ | Available | Available | Available |
| **Min / Max Packet Size** | $\min / \max_{p \in \mathcal{P}_K} p.\text{packet\_length}$ | Degenerate ($L_0$) | Available | Available | Available |
| **Average Packet Size** | $\frac{1}{K} \sum_{p \in \mathcal{P}_K} p.\text{packet\_length}$ | Available ($L_0$) | Available | Available | Available |
| **Packet Size Variance** | $\frac{1}{K} \sum (L_i - \bar{L})^2$ | Undefined ($0$) | Available | Available | Available |
| **Mean Inter-Arrival Time**| $\frac{1}{K-1} \sum_{i=1}^{K-1} p_i.\text{iat\_us}$ | Undefined ($0$) | Available | Available | Available |
| **Burst Statistics** | Sequence of IATs $< 50\text{ ms}$ | Undefined ($0$) | Preliminary | Available | Available |

> [!WARNING]
> Under no circumstances may features computed across $p \ge K$ (such as total flow duration or full-flow byte sum) be injected into prefix $K$ feature vectors. The validator audits feature builders to ensure zero temporal leakage.
