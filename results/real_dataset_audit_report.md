# Phase 1.5 — Real Dataset Artifact, Contamination, and Label-Leakage Final Decision Report

**Date**: 2026-08-23  
**Project**: Real-Time Encrypted Traffic Classification  
**Status**: Comprehensive Research Audit Complete — **Dataset Approved for ML Training**  
**Audit Target**: 60-Session Real Controlled Dataset (`data/dataset_manifest.csv`, `flows_real.csv`, `features_real.csv`)

---

## 1. Dataset Overview

The real-world traffic benchmark comprises 60 independent controlled capture sessions collected across 6 balanced classes on Windows 11 (`lab_env_win11`).

| Dataset Representation | Sessions | Total Flows | Total Packets | Total Volume | Class Balance |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **All Real (Unfiltered)** | 60 | 189 | 271,487 | 242.98 MB | Web: 32, Video: 26, Msg: 29, VoIP: 29, File: 25, Other: 48 |
| **Clean Real (Filtered)** | 60 | 121 | 270,962 | 242.91 MB | Web: 20, Video: 20, Msg: 20, VoIP: 20, File: 20, Other: 21 |
| **Excluded Artifacts** | 44 | 68 (35.98%) | 525 (0.19%) | 0.07 MB (0.03%) | Discovery, SSDP/mDNS/LLMNR, NetBIOS broadcast |

---

## 2. Flow Artifacts Identification

Deep inspection identified 68 non-application background flows mixed into the live captures. These flows represent local OS discovery mechanisms, multicast address advertisements, and zero-payload keepalives:
- **SSDP (UDP Port 1900)**: 28 flows (including 26 identical 4-packet / 848-byte flows).
- **LLMNR (UDP Port 5355)**: 18 flows (including 17 identical 4-packet / 296-byte flows).
- **mDNS (UDP Port 5353)**: 10 flows (small multicast name queries, 6–84 packets).
- **NetBIOS Name Service (UDP Port 137)**: 6 flows (Windows broadcast name queries, 3–9 packets).
- **Non-IP / Raw Protocol Control (Port 0)**: 6 flows (4–10 packets, 336–768 bytes).

None of these 68 flows contain target application data; they represent ambient operating system network background noise.

---

## 3. Repeated Signature Analysis

Analysis of structural flow signatures (`total_packet_count + total_bytes + protocol + dst_port`) revealed recurring multi-class patterns:

| Signature | Occurrences | Classes Spanned | Specific Classes | Status |
| :--- | :---: | :---: | :--- | :--- |
| `4pkts_848B_UDP_port1900` | 26 | 6 | Web, Video, Messaging, VoIP, File Transfer, Other | **Flagged & Excluded** (SSDP Broadcast) |
| `4pkts_296B_UDP_port5355` | 17 | 4 | Web, Messaging, VoIP, Other | **Flagged & Excluded** (LLMNR Broadcast) |
| `3pkts_276B_UDP_port137` | 5 | 4 | Web, Messaging, VoIP, Other | **Flagged & Excluded** (NetBIOS Name Service) |
| `24pkts_1920B_UDP_port5353` | 4 | 3 | Web, Messaging, VoIP | **Flagged & Excluded** (mDNS Multicast Query) |

All multi-class repeated signatures were successfully categorized as background discovery/control artifacts.

---

## 4. Protocol Distribution & Proxy Audit

The protocol breakdown shows high UDP representation due to modern HTTP/3 QUIC traffic and Cloudflare WARP WireGuard tunnel encapsulation:

| Class | UDP Flows | TCP Flows | OTHER Flows | Dominant Transport |
| :--- | :---: | :---: | :---: | :--- |
| **Web** | 32 (100.0%) | 0 (0.0%) | 0 (0.0%) | UDP (QUIC 443 / Tunnel 52783) |
| **Video** | 26 (100.0%) | 0 (0.0%) | 0 (0.0%) | UDP (QUIC 443 / Tunnel 52783) |
| **Messaging** | 29 (100.0%) | 0 (0.0%) | 0 (0.0%) | UDP (QUIC 443 / Tunnel 52783) |
| **VoIP** | 29 (100.0%) | 0 (0.0%) | 0 (0.0%) | UDP (RTP / Tunnel 52783) |
| **File Transfer**| 25 (100.0%) | 0 (0.0%) | 0 (0.0%) | UDP (Tunnel 52783 / QUIC 443) |
| **Other** | 41 (85.4%) | 1 (2.1%) | 6 (12.5%) | UDP (Tunnel 50468 / mDNS / SSDP) |

- **Label Leakage Check**: Mutual Information between `protocol` and `traffic_class` is **0.0763 bits** (against total class entropy of $2.5456\text{ bits}$).
- **Verdict**: Transport protocol is **NOT** a proxy for the class label.

---

## 5. Feature Leakage & ML Schema Audit

- **Schema Isolation**: Verified in `results/tables/ml_feature_schema_audit.csv`. All identifiers (`session_id`, `file_id`, `data_origin`, timestamps, `environment_id`, `device_id`, paths) are strictly excluded from model feature matrices.
- **Statistical Leakage Analysis** (`results/tables/feature_leakage_audit.csv`):
  - Highest informative features are temporal dynamics: `max_iat` (0.6215 bits), `mean_iat` (0.5085 bits), `avg_burst_packets` (0.4850 bits), `forward_packet_count` (0.4789 bits).
  - No single feature possesses deterministic 100% predictive power over the classes.

---

## 6. Collection Bias & Procedure Audit

- **Environment Uniformity**: All 60 sessions were collected on `lab_env_win11` with identical hardware and OS configurations (10 sessions per class across all 6 classes).
- **Confounder Risk**: Tested metadata parameters against class labels (`results/tables/collection_bias.csv`):
  - `capture_duration`: MI = 0.2265 bits (benign, near-constant 60s per session).
  - `packet_count`: MI = 0.5714 bits (benign reflection of application throughput).
  - `session_sequence_index`: Identified as potential confounder if leaked, confirmed strictly excluded.

---

## 7. Environment Bias Audit

Audited via `results/tables/environment_class_distribution.csv`:
- Environment distribution is perfectly uniform (100% balanced at 10 sessions per class). Zero cross-environment confounding exists.

---

## 8. Tiny/Control-Flow Analysis

Detailed investigation of the recurring ~4-packet / 848-byte flows revealed:
- **Root Cause**: Windows SSDP `M-SEARCH` broadcast queries sent periodically to `239.255.255.250:1900` across all sessions.
- **Payload Safety**: Confirmed zero user payload inspected. Analysis performed purely on packet size, IAT, and port headers.
- **Treatment**: Excluded from training set under explicit rule `RULE_MULTICLASS_CONTROL_TRAFFIC`.

---

## 9. UDP / QUIC Observations

- Extensive UDP usage is a valid reflection of contemporary encrypted web traffic (QUIC/HTTP3) and VPN tunnel encapsulation.
- Documented in full in `docs/protocol_observation.md`.

---

## 10. Clean Dataset Definition & Quality

The clean dataset is defined as:
$$\text{Clean Dataset} = \text{Original Flows} \setminus (\text{Control Broadcasts} \cup \text{Tiny Noise Flows})$$

- **Original Flows**: 189
- **Clean Flows**: 121
- **Clean Split Generation** (`data/processed/splits/real_clean/`):
  - **Train**: 85 flows (42 sessions, balanced across 6 classes)
  - **Validation**: 24 flows (12 sessions, balanced across 6 classes)
  - **Test**: 12 flows (6 sessions, balanced across 6 classes)

---

## 11. Excluded Samples & Logging

All 68 excluded flows are recorded in `results/tables/flow_exclusion_log.csv` with fields:
- `flow_id`
- `session_id`
- `class`
- `reason`
- `rule`
- `packet_count`
- `byte_count`

---

## 12. Remaining Limitations

1. **Single OS / Testbed Environment**: Real data was collected on Windows 11. Testing on Linux/macOS captures will form future work.
2. **Tunnel Dominance**: Because WireGuard/WARP encapsulated majority traffic, features rely predominantly on packet timing and burst statistics rather than TLS SNI headers.

---

## 13. Recommendation for ML Training

> [!IMPORTANT]
> **Final Recommendation**: The dataset has passed all integrity, leakage, bias, and artifact checks. It is **READY FOR MACHINE LEARNING TRAINING** using `data/processed/splits/real_clean/`.
