# Zero-Payload Feature Engineering & Dimensionality Study

**Document Type:** Scientific Research Monograph  
**Repository:** Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models  
**Evaluation Scope:** Multi-Environment Real Encrypted Traffic (`dataset_v2`)  
**Canonical Registry:** `preprocessing/feature_registry.py`  
**Date:** September 2026  

---

## 1. Executive Summary

This study establishes the canonical feature engineering foundations for zero-payload encrypted traffic classification. When network traffic is encapsulated within modern encrypted tunnels (such as Cloudflare WARP / WireGuard, TLS 1.3, or QUIC), payload contents, Server Name Indication (SNI), and application layer headers are cryptographically obscured. Classification must operate exclusively on transport-layer observable dynamics.

We systematically organize **84 zero-payload statistical features** across **7 explicit behavioral families**, catalog them in `preprocessing/feature_registry.py`, and evaluate them under strict group-aware session isolation on physical network captures.

### Key Empirical Takeaways
1. **Directionality is the Dominant Standalone Family:** Directional features alone (`packet_ratio`, `byte_ratio`, `direction_switch_count`) achieve **0.4643 Validation F1 (0.4265 Test F1)**, outperforming 30 packet-size features ($0.3120$) and 30 timing features ($0.2690$).
2. **Feature Dilution / Dimensionality Curse:** Increasing feature dimensionality from $K=3$ to $K=84$ reduces test performance from **0.6708 down to 0.3359 Macro-F1**. High-dimensional percentiles introduce noise that fragments tree partition criteria under tunnel encapsulation.
3. **The Optimal Lightweight Profile:** A compact subset of $K=3$ features (`packet_ratio`, `fwd_packet_count`, `total_packets`) achieves the global Pareto optimum (**0.7572 Validation F1, 0.6708 Test F1, 15.1 ms latency, 10.2 KB footprint**).

---

## 2. Canonical Feature Families & Mathematical Formulations

Every registered feature is mathematically derived strictly from three observable packet properties: arrival timestamp $t_i$, wire length $L_i$ (bytes), and directional flag $d_i \in \{\text{FORWARD}, \text{BACKWARD}\}$.

```
+-----------------------------------------------------------------------------------------+
|                                7 FEATURE FAMILIES                                       |
+-----------------------------------------------------------------------------------------+
| 1. Packet Size       | Moments & percentiles of packet wire lengths (overall, fwd, bwd)|
| 2. Timing / IAT      | Moments & percentiles of inter-arrival times (overall, fwd, bwd)|
| 3. Packet Counts     | Unidirectional, bidirectional, and rate counters                |
| 4. Byte Counts       | Volumetric byte totals, forward/backward bytes, throughput rates|
| 5. Directionality    | Ratios of forward-to-backward traffic and conversational turns  |
| 6. Burst Behavior    | Clustered packet transmissions delineated by IAT thresholds     |
| 7. Flow Duration     | Total temporal persistence of the bidirectional connection     |
+-----------------------------------------------------------------------------------------+
```

### Family 1: Packet Size ($K=30$)
Measures the discrete distribution of packet wire lengths across three scopes: bidirectional ($\mathbf{L}$), forward ($\mathbf{L}_{fwd}$), and backward ($\mathbf{L}_{bwd}$).
- **Mean & Standard Deviation:**
  $$\mu_L = \frac{1}{N}\sum_{i=1}^N L_i, \quad \sigma_L = \sqrt{\frac{1}{N}\sum_{i=1}^N (L_i - \mu_L)^2}$$
- **Extreme Moments:** $\min(L) = \min_{i} L_i$, $\max(L) = \max_{i} L_i$.
- **Quantiles ($P_{10}, P_{25}, P_{50}, P_{75}, P_{90}, P_{95}$):**
  $$P_k(L) = L_{(\lfloor k \cdot (N-1) \rfloor)}$$
*Physical Meaning:* Captures protocol MTU boundaries, TCP MSS negotiation, interactive keystroke packets ($40\text{--}80$ bytes), and bulk data MTU fills ($1280\text{--}1500$ bytes).

### Family 2: Timing & Inter-Arrival Time ($K=30$)
Measures elapsed durations between consecutive packet arrivals: $\Delta t_i = t_i - t_{i-1}$ for bidirectional, forward-only, and backward-only sub-sequences.
- **Mean & Variance:**
  $$\mu_{\Delta t} = \frac{1}{N-1}\sum_{i=2}^N \Delta t_i, \quad \sigma_{\Delta t} = \sqrt{\frac{1}{N-1}\sum_{i=2}^N (\Delta t_i - \mu_{\Delta t})^2}$$
- **Percentiles ($P_{10}, P_{25}, P_{50}, P_{75}, P_{90}, P_{95}$):**
  Identifies burst periodicity, client request pacing, and jitter.
*Physical Meaning:* Distinguishes periodic human speech (VoIP: strictly paced $20\text{ ms}$ packet cadences) from irregular human typing (Messaging) and asynchronous media buffer chunking (Video).

### Family 3: Packet Counts ($K=7$)
Tracks discrete transmission volume and rates:
- Forward packets: $N_{fwd} = \sum [d_i = \text{FWD}]$
- Backward packets: $N_{bwd} = \sum [d_i = \text{BWD}]$
- Total packets: $N = N_{fwd} + N_{bwd}$
- Packet rates: $R_N = \frac{N}{\max(D, 10^{-6})}, \quad R_{N, fwd} = \frac{N_{fwd}}{\max(D, 10^{-6})}, \quad R_{N, bwd} = \frac{N_{bwd}}{\max(D, 10^{-6})}$
*Physical Meaning:* Reflects conversational transaction size and protocol verbosity.

### Family 4: Byte Counts ($K=5$)
Tracks cumulative data volumes:
- Forward bytes: $B_{fwd} = \sum_{d_i=\text{FWD}} L_i$
- Backward bytes: $B_{bwd} = \sum_{d_i=\text{BWD}} L_i$
- Total volume: $B = B_{fwd} + B_{bwd}$
- Throughput: $R_B = \frac{B}{\max(D, 10^{-6})}$
*Physical Meaning:* Separates heavy downstream media streams ($B > 10\text{ MB}$) from lightweight command/control or chat telemetry ($B < 50\text{ KB}$).

### Family 5: Directionality ($K=3$)
Captures conversational asymmetry and turn-taking behavior:
- **Packet Ratio:**
  $$\text{Ratio}_N = \frac{N_{fwd}}{\max(N_{bwd}, 1)}$$
- **Byte Ratio:**
  $$\text{Ratio}_B = \frac{B_{fwd}}{\max(B_{bwd}, 1)}$$
- **Direction Switches ($S_d$):**
  Counts transitions between forward and backward packet arrivals:
  $$S_d = \sum_{i=2}^N \mathbf{1}[d_i \neq d_{i-1}]$$
*Physical Meaning:* Highly informative for encrypted traffic. In File Transfer (SFTP/HTTPS upload), $\text{Ratio}_B \gg 1$. In Video streaming, $\text{Ratio}_B \ll 1$. In VoIP and Messaging, $S_d$ is high due to rapid request-response handshakes.

### Family 6: Burst Behavior ($K=8$)
Groups packets into discrete bursts when consecutive packets arrive within an inter-burst threshold $\tau = 1.0\text{ s}$:
$$\text{Burst } k \text{ terminates when } t_{i} - t_{i-1} \ge 1.0\text{ s}$$
- **Burst Count ($K_{burst}$):** Number of active transmission bursts.
- **Mean & Max Burst Packets:** $\bar{N}_{burst} = \frac{N}{K_{burst}}$, $\max_k N_{burst, k}$.
- **Mean & Max Burst Bytes:** $\bar{B}_{burst} = \frac{B}{K_{burst}}$, $\max_k B_{burst, k}$.
- **Mean & Max Burst Duration:** $\bar{D}_{burst}$, $\max_k D_{burst, k}$.
- **Burst Density:** $\rho_{burst} = \frac{N}{\sum_k D_{burst, k}}$ (transmission intensity during active bursts).
*Physical Meaning:* Captures user interaction dynamics (e.g. clicking hyperlinks, video players fetching chunks every $2\text{--}5$ seconds).

### Family 7: Flow Duration ($K=1$)
- **Duration:** $D = t_{last} - t_{first}$ (seconds).
*Physical Meaning:* Separates short ephemeral queries (DNS/DoH, telemetry: $D < 2\text{ s}$) from persistent streaming sessions (VoIP, Video: $D > 60\text{ s}$).

---

## 3. Zero-Payload & Privacy Governance

All 84 features satisfy strict privacy constraints:
1. **Zero Application Payload:** Only L3/L4 wire lengths and timing headers are read. Zero bits of decrypted text, application data, or SNI extensions are inspected.
2. **Deterministic Imputation:** Single-packet or unidirectional flows are handled cleanly: backward moments are imputed with $0.0$, preventing runtime exceptions or NaN leakage.
3. **No Deep Packet Inspection (DPI):** Compatible with any standard socket tap, eBPF filter, or hardware NIC counter without requiring SSL/TLS key disclosure.

---

## 4. Feature-Family Ablation Study

Evaluated on `dataset_v2` under group-aware session splitting (Train: 205 flows, Val: 48 flows, Test: 48 flows; 6 balanced classes):

| Configuration | Feature Count | Description | Val Macro-F1 | Val Acc | Test Macro-F1 | Test Acc | Mean Latency | Footprint |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **D. Direction only** | **3** | Packet ratio, byte ratio, direction switches | **0.4643** | **0.4792** | **0.4265** | **0.4167** | 16.16 ms | 10.2 KB |
| **E. Burst only** | 8 | Burst counts, sizes, durations, density | 0.4073 | 0.4167 | 0.2588 | 0.2708 | 15.21 ms | 10.2 KB |
| **F. All feature families**| 84 | Combined zero-payload feature set | 0.3966 | 0.4167 | 0.3724 | 0.3750 | 15.35 ms | 10.2 KB |
| **C. Counts/bytes only** | 12 | Volume counters and flow rates | 0.3890 | 0.3958 | 0.3375 | 0.3333 | 16.79 ms | 10.2 KB |
| **A. Packet-size only** | 30 | Packet size moments (overall, fwd, bwd) | 0.3120 | 0.3333 | 0.3498 | 0.3542 | 16.32 ms | 10.2 KB |
| **B. Timing only** | 30 | Inter-arrival time moments | 0.2690 | 0.2917 | 0.3007 | 0.2917 | 16.60 ms | 10.2 KB |

### Analysis of Family Utility
- **Why Directionality Wins:** Tunneling through Cloudflare WARP wraps payloads in uniform WireGuard packets, obscuring packet size variations. However, the *ratio of client uploads to server downloads* and the *frequency of conversational turn-taking* remain completely preserved through the tunnel.
- **Why Timing Struggles Alone:** WAN jitter, wireless channel contention, and tunnel aggregation introduce substantial variance into raw inter-arrival times, making raw timing distributions alone insufficient for high-precision separation ($0.3007$ Test F1).

---

## 5. Feature-Count Scalability & Pareto Efficiency

Features were ranked strictly on the **Train set** using Gini impurity reduction from a 100-tree Random Forest ensemble. The top-ranked features were:
1. `packet_ratio` (Directionality)
2. `fwd_packet_count` (Packet Counts)
3. `total_packets` (Packet Counts)
4. `iat_p95` (Timing)
5. `fwd_byte_count` (Byte Counts)

Subsets were evaluated on the independent Validation set to select the optimal operating profile, followed by locked evaluation on the held-out Test set:

| Subset | Top Features Included | Val Macro-F1 | Val Acc | Test Macro-F1 | Test Acc | Mean Latency | Ext Latency | Selected Profile? |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Top-3** | `packet_ratio`, `fwd_packet_count`, `total_packets` | **0.7572** | **0.7708** | **0.6708** | **0.6667** | **15.10 ms** | **0.0148 ms** | **YES (OPTIMAL)** |
| **Top-5** | Above + `iat_p95`, `fwd_byte_count` | 0.4530 | 0.4792 | 0.4761 | 0.4583 | 15.18 ms | 0.0168 ms | NO |
| **Top-10** | Above + 5 additional moments | 0.3668 | 0.3958 | 0.3413 | 0.3333 | 15.17 ms | 0.0215 ms | NO |
| **Top-15** | Above + 5 additional moments | 0.3694 | 0.3958 | 0.3560 | 0.3542 | 16.01 ms | 0.0263 ms | NO |
| **Top-20** | Above + 5 additional moments | 0.3653 | 0.3958 | 0.3476 | 0.3542 | 15.28 ms | 0.0310 ms | NO |
| **Top-30** | Above + 10 additional moments | 0.3750 | 0.3958 | 0.3325 | 0.3333 | 15.32 ms | 0.0405 ms | NO |
| **All (84)**| Full canonical feature catalog | 0.3579 | 0.3750 | 0.3359 | 0.3333 | 15.17 ms | 0.0918 ms | NO |

### The "Curse of Dimensionality" in Encrypted Traffic
As demonstrated in [feature_vs_f1.png](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/figures/feature_vs_f1.png), expanding the feature set from $K=3$ to $K=84$ causes severe performance degradation:
- With $K=3$, decision trees split on high-signal directional asymmetry and transaction volume, achieving **0.6708 Test Macro-F1**.
- With $K=84$, hundreds of correlated percentile moments dilute tree candidate split selections. The model splits on noisy quantile fluctuations specific to individual capture conditions, resulting in severe overfitting to the training split and poor generalization.
- The Pareto frontier ([feature_pareto_frontier.png](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/figures/feature_pareto_frontier.png)) identifies **$K=3$ as the strictly dominant configuration**.

---

## 6. The Fallacy of In-Sample Correlation

> [!WARNING]
> **Methodological Warning:** A feature must NEVER be claimed as useful solely because it correlates with class labels on unpartitioned data.

In network traffic analysis, naive Pearson or Spearman correlation between a feature and class labels is frequently corrupted by **session confounding**:
1. If all VoIP captures in a dataset originate from a specific user workstation, features like TCP window size or specific ephemeral port ranges will show $r > 0.90$ correlation with the VoIP label.
2. In-sample correlation measures host identity rather than traffic category.
3. When evaluated under group-aware session isolation, these correlated features fail completely because the test sessions run on different hardware with different background traffic.
4. Only held-out, session-isolated validation provides an unbiased evaluation of true zero-payload feature utility.
