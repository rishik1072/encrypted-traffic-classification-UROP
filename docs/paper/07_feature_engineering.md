# Chapter 7: Feature Engineering & Canonical Registry

## 7.1 Zero-Payload Feature Extraction Paradigm

To ensure compliance with strict privacy regulations and maintain line-rate processing efficiency, the system operates exclusively on Layer-3 and Layer-4 transport dynamics. Feature extraction operates entirely on packet headers without:
- Inspecting application-layer payload data units (PDUs).
- Parsing unencrypted TLS handshakes (e.g., ClientHello SNI or cipher suite lists).
- Harvesting certificate chains or X.509 subject names.
- Attempting payload entropy analysis or partial decryption.

Every feature is derived from four basic packet attributes: arrival timestamp $t_i$, frame length $L_i$, transmission direction $d_i \in \{\text{fwd}, \text{bwd}\}$, and TCP header flags.

---

## 7.2 The Canonical 84-Feature Registry

We formalized a comprehensive feature registry ([`preprocessing/feature_registry.py`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/preprocessing/feature_registry.py)) consisting of 84 statistical metrics categorized into seven explicit families.

### Table 7.1: Canonical Feature Families Breakdown

| Family Identifier | Family Name | Feature Count ($K$) | Primary Statistical Metrics | Units |
| :--- | :--- | :---: | :--- | :--- |
| **Family 1** | **Packet Size** | 30 | Min, max, mean, median, standard deviation, variance, skewness, kurtosis (computed for total, forward, and backward flows) | Bytes |
| **Family 2** | **Timing / Inter-Arrival Time (IAT)** | 30 | Min, max, mean, median, standard deviation, variance, skewness, kurtosis (computed for total, forward, and backward flows) | Milliseconds |
| **Family 3** | **Packet Counts** | 6 | Total packets, forward packets, backward packets, forward-to-backward packet ratio, packet arrival rate | Count, Count/sec |
| **Family 4** | **Byte Counts** | 6 | Total bytes, forward bytes, backward bytes, forward-to-backward byte ratio, byte transmission rate | Bytes, Bytes/sec |
| **Family 5** | **Directionality** | 3 | Packet ratio ($\frac{N_{\text{fwd}}}{N_{\text{tot}}}$), Byte ratio ($\frac{B_{\text{fwd}}}{B_{\text{tot}}}$), Direction switch count ($\sum \mathbb{I}(d_i \ne d_{i-1})$) | Dimensionless ratio, Count |
| **Family 6** | **Burst Behavior** | 8 | Total burst count, mean burst size, max burst size, mean burst duration, burst packet density | Bytes, Milliseconds, Count |
| **Family 7** | **Flow Duration** | 1 | Total elapsed time ($t_{\text{last}} - t_{\text{first}}$) | Seconds |
| **Total** | **All Families** | **84** | Complete zero-payload representation | Mixed |

---

## 7.3 Canonical 21 Feature Profile (`baseline_21_zero_payload`)

While 84 features provide an exhaustive behavioral representation, higher moments (skewness, kurtosis) are computationally expensive and sensitive to outliers. We defined a canonical 21-feature subset that balances statistical coverage and computational cost:

1. `flow_duration`: Total active session duration ($s$).
2. `total_packets`: Aggregate bidirectional packet count.
3. `fwd_packets`: Number of packets transmitted by client.
4. `bwd_packets`: Number of packets transmitted by server.
5. `total_bytes`: Aggregate bidirectional volume ($B$).
6. `fwd_bytes`: Upstream byte volume ($B$).
7. `bwd_bytes`: Downstream byte volume ($B$).
8. `min_packet_size`: Minimum observed frame length ($B$).
9. `max_packet_size`: Maximum observed frame length ($B$).
10. `mean_packet_size`: Mean frame length ($B$).
11. `std_packet_size`: Standard deviation of frame lengths ($B$).
12. `min_iat`: Minimum inter-arrival time ($ms$).
13. `max_iat`: Maximum inter-arrival time ($ms$).
14. `mean_iat`: Mean inter-arrival time ($ms$).
15. `std_iat`: Standard deviation of inter-arrival times ($ms$).
16. `packet_rate`: Bidirectional throughput ($\text{packets/sec}$).
17. `byte_rate`: Bidirectional data rate ($\text{bytes/sec}$).
18. `packet_ratio`: Ratio of forward to total packets ($\frac{N_{\text{fwd}}}{N}$).
19. `byte_ratio`: Ratio of forward to total bytes ($\frac{B_{\text{fwd}}}{B}$).
20. `burst_count`: Number of distinct unidirectional packet bursts.
21. `mean_burst_bytes`: Average byte volume per unidirectional burst ($B$).

---

## 7.4 Feature Reduction & Pareto-Optimal Lightweight Profiles

To identify the optimal trade-off between computational overhead and classification fidelity, we evaluated feature subsets of size $K \in \{3, 5, 10, 15, 20, 30, 84\}$ using validation-data feature importance ranking:

- **Ultra-Lightweight 3-Feature Profile (`top_3_features`):**
  - Features: `packet_ratio`, `byte_ratio`, `fwd_packet_count`.
  - Characteristics: Requires only basic packet and byte counters; zero floating-point variance or inter-arrival time calculation. Enables ultra-fast evaluation in hardware-constrained environments.
- **Production Lightweight 10-Feature Profile (`profile_10_features`):**
  - Features: `fwd_packet_count`, `bwd_packet_count`, `total_bytes`, `avg_packet_size`, `max_packet_size`, `mean_iat`, `fwd_bwd_byte_ratio`, `fwd_bwd_packet_ratio`, `packet_ratio`, `packets_per_sec`.
  - Characteristics: Captures packet volume, asymmetry, average size, and first-order timing dynamics. Achieves robust generalization across variable network conditions while maintaining sub-millisecond inference.

---

## 7.5 Online Streaming Computation (Welford's Algorithm)

To support real-time streaming traffic without buffering arbitrary packet histories, running statistical moments (mean, variance, standard deviation) are updated online in $O(1)$ time and $O(1)$ space using Welford's algorithm:

$$\mu_n = \mu_{n-1} + \frac{x_n - \mu_{n-1}}{n}$$
$$M_{2,n} = M_{2,n-1} + (x_n - \mu_{n-1})(x_n - \mu_n)$$
$$\sigma_n^2 = \frac{M_{2,n}}{n - 1}$$

This ensures that per-flow memory consumption remains strictly bounded (< 256 bytes per active flow state), preventing memory exhaustion under high concurrent flow volumes.
