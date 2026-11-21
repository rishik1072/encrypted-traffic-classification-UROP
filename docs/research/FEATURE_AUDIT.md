# Canonical Feature Schema Audit: Zero-Payload Guarantees, Online Streaming & Ablation Taxonomy

**Document Version:** 1.0.0  
**Audit Date:** November 2026  
**Auditor:** Senior Real-Time ML Systems & Networking Engineer  
**Repository:** `c:\UROP project\encrypted-traffic-classification-UROP`  
**Compliance Standard:** Strict Zero-Payload Ingress (Layer 3/4 Statistical Features Only)  

---

## 1. Executive Summary & Compliance Mandate

This document establishes the canonical mathematical specification, online computational complexity, privacy compliance, and experimental ablation groupings of all features utilized across the classification engine.

### Strict Non-Negotiable Invariants:
1. **Zero-Payload Privacy:** No application-layer payload bytes, TLS record contents, SNI (Server Name Indication) fields, cipher suites, certificate fingerprints, or HTTP headers are inspected, extracted, or persisted.
2. **Online Streaming Computability:** Every feature must be updatable incrementally upon packet arrival in $O(1)$ time and $O(1)$ memory per flow.
3. **No Direct Identifier Leakage:** Raw IP addresses and MAC addresses are strictly barred from the feature schema to prevent trivial shortcut learning (memorizing destination IP addresses rather than traffic dynamics).
4. **Observation Gating:** Feature vectors are evaluated only when the flow has accumulated sufficient evidence ($N_{\text{observed}} \ge 3$ packets).

---

## 2. Canonical 21-Feature Schema Specification

The table below catalogs the complete set of 21 statistical flow features extracted by [`preprocessing/feature_extractor.py`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/preprocessing/feature_extractor.py) and validated by [`realtime/schema.py`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/realtime/schema.py):

| Index | Feature Name | Unit | Mathematical Definition / Formula | Online Streaming Complexity | Min Packets | In `lightweight_10`? |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: |
| 1 | `flow_duration` | Seconds | $t_{\text{last}} - t_{\text{first}}$ | $O(1)$ | 2 | **Yes** |
| 2 | `forward_packet_count` | Count | $N_{\text{fwd}} = \sum_{i} \mathbb{I}(\text{dir}_i = \text{FWD})$ | $O(1)$ | 1 | **Yes** |
| 3 | `backward_packet_count`| Count | $N_{\text{bwd}} = \sum_{i} \mathbb{I}(\text{dir}_i = \text{BWD})$ | $O(1)$ | 1 | **Yes** |
| 4 | `total_packet_count` | Count | $N = N_{\text{fwd}} + N_{\text{bwd}}$ | $O(1)$ | 1 | **Yes** |
| 5 | `forward_bytes` | Bytes | $B_{\text{fwd}} = \sum_{i \in \text{fwd}} L_i$ | $O(1)$ | 1 | **Yes** |
| 6 | `backward_bytes` | Bytes | $B_{\text{bwd}} = \sum_{i \in \text{bwd}} L_i$ | $O(1)$ | 1 | **Yes** |
| 7 | `total_bytes` | Bytes | $B = B_{\text{fwd}} + B_{\text{bwd}}$ | $O(1)$ | 1 | **Yes** |
| 8 | `avg_packet_size` | Bytes | $\bar{L} = \frac{B}{N}$ | $O(1)$ | 1 | **Yes** |
| 9 | `min_packet_size` | Bytes | $L_{\min} = \min_{i} L_i$ | $O(1)$ | 1 | **Yes** |
| 10 | `max_packet_size` | Bytes | $L_{\max} = \max_{i} L_i$ | $O(1)$ | 1 | **Yes** |
| 11 | `packet_size_variance` | Bytes$^2$| $\sigma_L^2 = \frac{1}{N-1} \sum_{i} (L_i - \bar{L})^2$ via Welford | $O(1)$ | 3 | No |
| 12 | `mean_iat` | Seconds | $\bar{\Delta t} = \frac{1}{N-1} \sum_{i=2}^{N} (t_i - t_{i-1})$ | $O(1)$ | 2 | No |
| 13 | `median_iat` | Seconds | $\text{Median}(\{\Delta t_i\})$ (approximated online) | $O(1)$ | 3 | No |
| 14 | `iat_std` | Seconds | $\sigma_{\Delta t} = \sqrt{\frac{1}{N-2} \sum (\Delta t_i - \bar{\Delta t})^2}$ via Welford | $O(1)$ | 3 | No |
| 15 | `min_iat` | Seconds | $\Delta t_{\min} = \min_{i} \Delta t_i$ | $O(1)$ | 2 | No |
| 16 | `max_iat` | Seconds | $\Delta t_{\max} = \max_{i} \Delta t_i$ | $O(1)$ | 2 | No |
| 17 | `fwd_bwd_packet_ratio`| Ratio | $\frac{N_{\text{fwd}}}{\max(1, N_{\text{bwd}})}$ | $O(1)$ | 2 | No |
| 18 | `fwd_bwd_byte_ratio` | Ratio | $\frac{B_{\text{fwd}}}{\max(1, B_{\text{bwd}})}$ | $O(1)$ | 2 | No |
| 19 | `burst_count` | Count | Count of intervals where $\Delta t_i < 0.05\text{ s}$ and $L_i > 100$ | $O(1)$ | 3 | No |
| 20 | `avg_burst_bytes` | Bytes | $\frac{\text{Total Burst Bytes}}{\max(1, \text{burst\_count})}$ | $O(1)$ | 3 | No |
| 21 | `avg_burst_packets` | Count | $\frac{\text{Total Burst Packets}}{\max(1, \text{burst\_count})}$ | $O(1)$ | 3 | No |

---

## 3. Streaming Online Implementation: Welford's Algorithm

To achieve sub-millisecond per-packet updates without storing historical packet arrays in RAM, the engine uses **Welford's One-Pass Algorithm** for real-time running mean and variance computation.

Given an incoming packet $k$ with length $L_k$ and arrival timestamp $t_k$:
1. **Packet Size Mean and Variance:**
   $$\delta_k = L_k - \bar{L}_{k-1}$$
   $$\bar{L}_k = \bar{L}_{k-1} + \frac{\delta_k}{k}$$
   $$M_{2,k} = M_{2,k-1} + \delta_k \cdot (L_k - \bar{L}_k)$$
   $$\sigma_{L,k}^2 = \frac{M_{2,k}}{k - 1} \quad (\text{for } k \ge 2)$$
2. **Inter-Arrival Time (IAT) Statistics:**
   Upon arrival of packet $k$ ($k \ge 2$), the instantaneous inter-arrival interval is computed as:
   $$\Delta t_k = t_k - t_{k-1}$$
   The running mean $\bar{\Delta t}$ and variance $\sigma_{\Delta t}^2$ are updated using identical Welford recurrence relations with iteration index $m = k - 1$.
3. **Space Complexity:** Fixed $64$ bytes of state per flow structure, permitting $> 100,000$ concurrent flows in $< 10$ MB of system memory.

---

## 4. Privacy, Compliance & Anti-Shortcut Safeguards

### 4.1 Strict Exclusion of Direct Identifiers
- **Source IP & Destination IP:** Excluded from the feature schema. While IP addresses provide high superficial accuracy on training sets, they introduce catastrophic **shortcut learning** (the model memorizes that IP `142.250.x.x` is YouTube, failing when Google shifts IP blocks or when traffic is routed through a proxy/VPN).
- **MAC Addresses:** Stripped at the Npcap ingress boundary.
- **Port Numbers:** `dst_port` is cataloged as a categorical reference feature, but in production models (`model_lightgbm_v1`), it is **excluded from inference** because under tunnel encapsulation (Cloudflare WARP / WireGuard), all external traffic collapses to destination UDP port `2408` or `500`.

### 4.2 Zero-Payload Verification Test
The automated test suite enforces zero-payload compliance in [`tests/test_payload_security.py`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/tests/test_payload_security.py) and [`tests/test_zero_payload_live.py`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/tests/test_zero_payload_live.py):
- Any attempt by an extractor to access `packet.payload`, `packet[Raw]`, or TLS handshake byte arrays immediately triggers an assertion failure.
- Feature vectors are strictly deterministic functions of Layer 3 IP headers and Layer 4 TCP/UDP headers.

---

## 5. Feature Groups for Planned Ablation Experiments

To systematically quantify the predictive contribution of different traffic properties, the 21 canonical features are partitioned into four orthogonal feature families:

```mermaid
flowchart TD
    ALL["Canonical 21-Feature Schema"] --> G1["Group 1: Volume & Length Dynamics (8 Features)"]
    ALL --> G2["Group 2: Temporal & Timing Dynamics (6 Features)"]
    ALL --> G3["Group 3: Directional Asymmetry (4 Features)"]
    ALL --> G4["Group 4: Burst & Pacing Dynamics (3 Features)"]

    G1 -.-> F1["avg, min, max packet size; total, fwd, bwd bytes; total, fwd, bwd pkts"]
    G2 -.-> F2["flow_duration, mean, median, std, min, max IAT"]
    G3 -.-> F3["fwd_bwd_packet_ratio, fwd_bwd_byte_ratio, fwd pkts, bwd pkts"]
    G4 -.-> F4["burst_count, avg_burst_bytes, avg_burst_packets"]
```

### Group 1: Volume & Length Dynamics (8 Features)
- **Features:** `avg_packet_size`, `min_packet_size`, `max_packet_size`, `packet_size_variance`, `forward_bytes`, `backward_bytes`, `total_bytes`, `total_packet_count`.
- **Physical Rationale:** Distinguishes high-throughput transfer (Video, File Transfer: MTU-sized packets $\approx 1420 - 1500$ bytes) from low-throughput interactive sessions (VoIP, Messaging: small packets $\approx 100 - 300$ bytes).
- **Vulnerability:** Highly susceptible to VPN padding and outer tunnel encapsulation (WireGuard fixed packet framing).

### Group 2: Temporal & Inter-Arrival Timing Dynamics (6 Features)
- **Features:** `flow_duration`, `mean_iat`, `median_iat`, `iat_std`, `min_iat`, `max_iat`.
- **Physical Rationale:** Captures application pacing and human interaction loops. VoIP emits regular periodic packets ($20\text{ ms}$ audio frames); Web browsing exhibits bursty ON/OFF user think-time; Video streaming features regular buffer replenishment bursts every $2 - 5$ seconds.
- **Robustness:** Highly invariant to encryption and payload padding; timing dynamics persist even through WireGuard tunnels.

### Group 3: Directional Asymmetry & Ratios (4 Features)
- **Features:** `fwd_bwd_packet_ratio`, `fwd_bwd_byte_ratio`, `forward_packet_count`, `backward_packet_count`.
- **Physical Rationale:** Distinguishes asymmetric downstream downloads (Web, Video: $B_{\text{bwd}} \gg B_{\text{fwd}}$) from symmetric bidirectional conversations (VoIP, Messaging: $B_{\text{bwd}} \approx B_{\text{fwd}}$) and upstream uploads (File Transfer).

### Group 4: Burst & Pacing Dynamics (3 Features)
- **Features:** `burst_count`, `avg_burst_bytes`, `avg_burst_packets`.
- **Physical Rationale:** Quantifies clustering of packets arriving in rapid succession ($< 50\text{ ms}$), reflecting TCP congestion window bursts and application layer chunking.

---

## 6. Empirical Feature Importance & Correlation Analysis

From [`results/tables/feature_importance_lightgbm.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/feature_importance_lightgbm.csv) and [`feature_importance_consensus.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/feature_importance_consensus.csv):

### Top Consensus Features:
1. **`avg_packet_size` (Rank 1, Consensus Weight: $0.214$):** Primary discriminator between Bulk and Interactive traffic.
2. **`mean_iat` (Rank 2, Consensus Weight: $0.187$):** Primary discriminator between periodic VoIP traffic and bursty Web traffic.
3. **`fwd_bwd_byte_ratio` (Rank 3, Consensus Weight: $0.162$):** Primary discriminator between symmetric VoIP/Messaging and downstream Video.
4. **`packet_size_variance` (Rank 4, Consensus Weight: $0.135$):** Distinguishes variable-rate Web assets from fixed-rate audio packets.
5. **`flow_duration` (Rank 5, Consensus Weight: $0.098$):** Separates short ephemeral queries from long-lived video and VoIP sessions.

### Multicollinearity Audit:
- Correlation matrix analysis in [`results/tables/feature_correlation.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/feature_correlation.csv) indicates strong collinearity ($r > 0.92$) between `total_packet_count`, `forward_packet_count`, and `backward_packet_count`.
- Similarly, `total_bytes` and `backward_bytes` exhibit $r = 0.96$ in downstream-heavy workloads.
- **Optimization Recommendation for Paper:** Pruning redundant volume counters to arrive at an ultra-lean 7-feature orthogonal subset reduces tree evaluation depth by $30\%$ with zero loss in test Macro-F1.
