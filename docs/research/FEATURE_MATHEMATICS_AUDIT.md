# Feature Mathematics and Streaming Algorithmic Audit

**Repository**: `encrypted-traffic-classification-UROP`  
**Audit Date**: November 2026  
**Auditor**: Independent ML & Systems Research Audit  
**Status**: Authoritative Forensic Evidence Document

---

## 1. Executive Summary

Previous research documentation for this repository asserted two significant algorithmic claims regarding real-time feature extraction:
1. *"Flow statistics are calculated via Welford's streaming one-pass algorithm in $O(1)$ memory."*
2. *"Streaming median IAT is computed in constant memory across arbitrary flow horizons."*

Forensic inspection of the canonical feature extraction implementation in `preprocessing/feature_extractor.py` (lines 30–128) reveals that **both claims are factually contradicted**:
- **No Welford Recurrence**: Feature extraction operates on `flow.packet_records`, a dynamic Python list that appends every packet received ($O(N)$ memory). Variance and standard deviation are computed via multi-pass list comprehensions: `sum((x - mean)**2 for x in lengths)`.
- **In-Memory Exact Sorting**: The median inter-arrival time (`median_iat`) is computed by accumulating all inter-arrival times in memory and calling Python's built-in `sorted(iats)` ($O(N)$ space, $O(N \log N)$ time).

This document audits the exact mathematical definitions, boundary conditions, and algorithmic complexities implemented in production.

---

## 2. Canonical 21-Feature Mathematical Inventory

The following table details the exact implementation of the 21 canonical features in `preprocessing/feature_extractor.py`:

| # | Feature Name | Implemented Code Expression | Mathematical Definition | Space Complexity | Time Complexity |
| :---: | :--- | :--- | :--- | :---: | :---: |
| **1** | `flow_duration` | `timestamps[-1] - timestamps[0]` | $t_N - t_1$ | $O(N)$ | $O(1)$ |
| **2** | `forward_packet_count` | `len(fwd_lengths)` | $N_{\text{fwd}} = \sum_{i=1}^N \mathbb{I}(d_i = \text{FWD})$ | $O(N)$ | $O(N)$ |
| **3** | `backward_packet_count`| `len(bwd_lengths)` | $N_{\text{bwd}} = \sum_{i=1}^N \mathbb{I}(d_i = \text{BWD})$ | $O(N)$ | $O(N)$ |
| **4** | `total_packet_count` | `len(records)` | $N = N_{\text{fwd}} + N_{\text{bwd}}$ | $O(N)$ | $O(1)$ |
| **5** | `forward_bytes` | `sum(fwd_lengths)` | $B_{\text{fwd}} = \sum_{i \in \text{FWD}} L_i$ | $O(N)$ | $O(N)$ |
| **6** | `backward_bytes` | `sum(bwd_lengths)` | $B_{\text{bwd}} = \sum_{i \in \text{BWD}} L_i$ | $O(N)$ | $O(N)$ |
| **7** | `total_bytes` | `fwd_bytes + bwd_bytes` | $B = B_{\text{fwd}} + B_{\text{bwd}}$ | $O(N)$ | $O(1)$ |
| **8** | `avg_packet_size` | `sum(lengths) / total_packet_count` | $\bar{L} = \frac{1}{N} \sum_{i=1}^N L_i$ | $O(N)$ | $O(N)$ |
| **9** | `min_packet_size` | `float(min(lengths))` | $\min_{i} L_i$ | $O(N)$ | $O(N)$ |
| **10**| `max_packet_size` | `float(max(lengths))` | $\max_{i} L_i$ | $O(N)$ | $O(N)$ |
| **11**| `packet_size_variance`| `sum((x - avg)**2 for x in lengths) / N` | $\sigma_L^2 = \frac{1}{N} \sum_{i=1}^N (L_i - \bar{L})^2$ | $O(N)$ | $O(N)$ |
| **12**| `mean_iat` | `sum(iats) / len(iats)` | $\overline{\Delta t} = \frac{1}{N-1} \sum_{i=2}^N \Delta t_i$ | $O(N)$ | $O(N)$ |
| **13**| `median_iat` | `sorted_iats[mid]` | $\operatorname{Median}(\{\Delta t_i\})$ | $O(N)$ | $O(N \log N)$ |
| **14**| `iat_std` | `sqrt(sum((x - mean)**2 for x in iats) / M)` | $\sigma_{\Delta t} = \sqrt{\frac{1}{M} \sum_{i=1}^M (\Delta t_i - \overline{\Delta t})^2}$ | $O(N)$ | $O(N)$ |
| **15**| `min_iat` | `float(min(iats))` | $\min_{i} \Delta t_i$ | $O(N)$ | $O(N)$ |
| **16**| `max_iat` | `float(max(iats))` | $\max_{i} \Delta t_i$ | $O(N)$ | $O(N)$ |
| **17**| `fwd_bwd_packet_ratio`| `fwd_pkts / bwd_pkts if bwd > 0 else fwd` | $\frac{N_{\text{fwd}}}{\max(1, N_{\text{bwd}})}$ | $O(N)$ | $O(1)$ |
| **18**| `fwd_bwd_byte_ratio` | `fwd_bytes / bwd_bytes if bwd > 0 else fwd`| $\frac{B_{\text{fwd}}}{\max(1, B_{\text{bwd}})}$ | $O(N)$ | $O(1)$ |
| **19**| `burst_count` | `len(bursts_packets)` ($\Delta t < 0.05\,\text{s}$) | $\sum_{i=2}^N \mathbb{I}(\Delta t_i \ge 0.05) + 1$ | $O(N)$ | $O(N)$ |
| **20**| `avg_burst_bytes` | `sum(bursts_bytes) / burst_count` | $\frac{1}{K} \sum_{k=1}^K B_{\text{burst}, k}$ | $O(N)$ | $O(N)$ |
| **21**| `avg_burst_packets` | `sum(bursts_packets) / burst_count` | $\frac{1}{K} \sum_{k=1}^K N_{\text{burst}, k}$ | $O(N)$ | $O(N)$ |

---

## 3. Discrepancy Analysis

### 3.1 Population Variance vs. Sample Variance
In `preprocessing/feature_extractor.py` (line 67 and line 78):
- Packet size variance divides by $N$ rather than applying Bessel's correction ($N - 1$):
  ```python
  packet_size_variance = sum((x - avg_packet_size) ** 2 for x in lengths) / total_packet_count
  ```
- Similarly, `iat_std` divides by $M = \text{len}(iats)$ rather than $M - 1$.
- **Finding**: The extractor computes the **population variance and standard deviation**, not the unbiased sample estimators. While mathematically consistent across train and inference, academic documentation should specify population statistics ($\sigma^2$) rather than sample statistics ($s^2$).

### 3.2 Ratio Fallbacks for Asymmetric Flows
When a flow contains zero backward packets ($N_{\text{bwd}} = 0$):
```python
fwd_bwd_packet_ratio = (
    float(fwd_packet_count) / float(bwd_packet_count) if bwd_packet_count > 0 else float(fwd_packet_count)
)
```
- If a flow has $500$ forward packets and $0$ backward packets, `fwd_bwd_packet_ratio` evaluates to `500.0`.
- If a flow has $500$ forward packets and $1$ backward packet, `fwd_bwd_packet_ratio` also evaluates to `500.0`.
- This avoids `ZeroDivisionError` or infinite values, providing numeric stability for tree models without requiring sentinel masking.

### 3.3 Inter-Arrival Time Non-Negativity Clamping
Line 73:
```python
iats = [max(0.0, timestamps[i] - timestamps[i - 1]) for i in range(1, total_packet_count)]
```
- Network interface drivers and multi-threaded packet capture can occasionally deliver out-of-order timestamps or microscopic negative deltas due to clock jitter. The explicit `max(0.0, ...)` clamp ensures all $\Delta t \ge 0.0$, preventing negative variance or math domain exceptions.

---

## 4. Algorithmic Memory Footprint in High-Throughput Scenarios

Because `flow.packet_records` retains all packet records:
- Each packet record in Python is a 3-element tuple: `(timestamp: float, length: int, direction: Direction)`.
- In CPython 64-bit, a 3-element tuple plus wrapped primitive objects consumes approximately **112 bytes** of heap memory.
- For a small flow of 10 packets: $\approx 1.1\,\text{KB}$.
- For a high-bandwidth video or file-transfer flow of $100,000$ packets: $\approx \mathbf{11.2\,\text{MB}}$ per active flow.

At 10,000 concurrent active flows, unconstrained in-memory packet buffering would consume over **100 GB** of RAM. This confirms that the current implementation is suited for real-time edge monitoring of moderate-volume flows, but requires a true streaming architecture for core network line-rate deployment.

---

## 5. Phase 1 Upgrade Roadmap: True $O(1)$ Streaming Feature Extraction

For Phase 1, the research platform will replace list buffering with online one-pass streaming accumulators:

### 5.1 Online Welford Recurrence for Lengths and IATs
Maintain state vector: $(k, M_{1, k}, M_{2, k}, \min_x, \max_x)$:
$$M_{1, k} = M_{1, k-1} + \frac{x_k - M_{1, k-1}}{k}$$
$$M_{2, k} = M_{2, k-1} + (x_k - M_{1, k-1})(x_k - M_{1, k})$$
$$\sigma_k^2 = \frac{M_{2, k}}{k}$$
- **Space Complexity**: Exactly $O(1)$ (5 floating-point numbers per flow).
- **Time Complexity**: Exactly $O(1)$ per packet arrival.

### 5.2 Constant-Memory Quantile Estimation
Replace `sorted(iats)` with the **$P^2$ Algorithm (Piecewise Parabolic)** or **t-digest**:
- Tracks 5 marker positions dynamically with each incoming $\Delta t$.
- Accurately estimates the 50th percentile (median) with bounded relative error in $O(1)$ space and $O(1)$ update time.
