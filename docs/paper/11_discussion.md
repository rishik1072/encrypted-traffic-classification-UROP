# Chapter 11: Discussion & Analytical Interpretation

To ensure scientific integrity, this chapter explicitly categorizes our analytical findings into:
- **Measured Results:** Objective empirical data recorded in `results/final/*.csv`.
- **Observations:** Empirically verified trends, error distributions, and relative performance differentials.
- **Interpretations:** Hypothesized causal mechanisms, theoretical deductions, and architectural implications.
- **Related-Work Context:** Comparative analysis against prior literature.

---

## 11.1 Why Shallow Decision Trees Match Complex Ensembles

### Measured Results:
On the locked test set (`dataset_v2`), the single CART Decision Tree achieved **0.5802 Macro-F1** and 0.5833 Accuracy, while the 100-tree Random Forest ensemble achieved **0.5873 Macro-F1** and 0.5833 Accuracy (`EXP-R09`). The Decision Tree required **0.0579 ms** median inference latency ($15,600\text{ flows/sec}$) with a **3.11 KB** serialized disk footprint, compared to **4.2476 ms** ($213\text{ flows/sec}$) and **175.41 KB** for Random Forest (`EXP-R14`).

### Observation:
Ensembling 100 trees provided an absolute gain of only **+0.0071 Macro-F1** (+1.2% relative improvement), at the cost of a **$73\times$ latency penalty** and an **$56\times$ storage expansion**.

### Interpretation:
In tabular network metadata spaces governed by strong physical invariants, the discriminative signal is concentrated in a small number of orthogonal feature dimensions—primarily directionality ratios (`packet_ratio`, `byte_ratio`) and coarse volume metrics (`total_bytes`). When feature boundaries are approximately axis-aligned (e.g., distinguishing bulk download from interactive messaging by checking if byte ratio exceeds a threshold), a single shallow decision tree captures the primary decision boundaries effectively. The variance-reduction properties of bootstrap aggregation provide diminishing returns when the primary source of classification error is class-intrinsic overlap rather than high model variance.

### Practical Engineering Implication:
For wire-speed edge deployments (e.g., intermediate programmable routers or Wi-Fi AP firmware), deploying a single 3.11 KB Decision Tree is vastly superior to deploying large ensembles or deep neural networks, delivering wire-speed performance with virtually zero accuracy degradation.

---

## 11.2 The Physical Mechanism of WireGuard Tunnel Degradation

### Measured Results:
In the generalization benchmark (`EXP-R11`), transferring a model trained on unencapsulated traffic to WireGuard-tunneled traffic (Cloudflare WARP, `REG-08b`) caused test Macro-F1 to collapse from **0.6001** to **0.3407** ($\Delta\text{F1} = -0.2594$, Severe Degradation). Conversely, transferring a model trained on WireGuard traffic to unencapsulated traffic (`REG-08a`) achieved **1.0000 Macro-F1**.

### Observation:
The vulnerability of statistical traffic classifiers to VPN/tunnel distribution shift is fundamentally asymmetric:
$$\text{Performance}(\text{Direct} \rightarrow \text{Tunneled}) \ll \text{Performance}(\text{Tunneled} \rightarrow \text{Direct})$$

### Interpretation:
This asymmetry is directly explained by the protocol mechanics of WireGuard:
1. **Packet Size Standardization & MTU Clamping:** Standard direct traffic exhibits a rich, multi-modal packet length distribution reflecting diverse application protocols (e.g., small 60–120 byte TCP ACKs, 300–800 byte TLS handshakes, and 1460-byte payload segments). WireGuard encapsulates all transport traffic within outer UDP packets, enforces a constrained MTU (typically 1280 bytes on mobile and IPv6 paths), and appends fixed-size cryptographic authentication tags (Poly1305, 16 bytes) and standardized 32-byte headers. This compresses the packet length spectrum, destroying the fine-grained variance that direct-trained models depend on.
2. **Tunnel Handshake Invariance:** Because WireGuard standardizes packet lengths, models trained on tunneled traffic are forced to rely primarily on directionality asymmetry and coarse burst dynamics. Because directionality ratios (upstream vs. downstream volume) remain largely preserved through tunnel encapsulation, tunnel-trained models transfer robustly to direct traffic.

### Related-Work Comparison:
Prior literature often claims that statistical features are universally "VPN-agnostic." Our empirical results directly refute this assumption, demonstrating that unadapted classifiers cannot be deployed on encrypted tunnel overlays without explicit re-training on padded tunnel data.

---

## 11.3 The Physical Delay Hierarchy: Why Full-Flow Analysis Fails

### Measured Results:
In `EXP-R12`, early prediction at $N=3$ packets achieved **0.6111 Macro-F1** with **91.67% coverage** at a median total latency of **79.94 ms** (comprising **64.04 ms** observation delay and **16.53 ms** inference). Full-flow retrospective evaluation incurred a median latency of **59,668.15 ms** (~59.7 seconds) and completely failed (**0.0000 Macro-F1**, 0.0% accuracy).

### Observation:
Physical packet observation delay constitutes **80.1% to 99.8%** of total real-time latency across all observation horizons. Waiting for full flow completion increases latency by **$746\times$** while degrading classification accuracy to zero.

### Interpretation:
1. **Physical Latency Dominance:** In production networks, packets cannot be classified before they physically arrive at the capture interface. While ML inference executes in microseconds, the inter-arrival time between physical packets on real WAN connections is governed by network round-trip times (RTTs), client processing delays, and TCP three-way handshake intervals. Equating algorithmic inference time with "real-time classification" is a fundamental category error.
2. **Temporal Signature Dilution:** The opening packets of a connection (TCP SYN, SYN-ACK, TLS ClientHello, ServerHello) carry dense behavioral intent. Once a flow transitions into steady state, periodic keep-alive pings, TCP window acknowledgments, and idle timeouts homogenize aggregate statistical moments (e.g., mean IAT converges toward keep-alive intervals), obliterating the distinctive statistical signatures present during session initiation.

---

## 11.4 Forensic Reconciliations: Explaining Discrepancies with Prior Work

Table 11.1 formalizes the forensic reconciliation between legacy synthetic claims and authoritative empirical results.

### Table 11.1: Forensic Discrepancy Reconciliation Matrix

| Research Question | Legacy / Literature Claim | Empirical Finding | Forensic Diagnosis & Root Cause |
| :--- | :--- | :--- | :--- |
| **Baseline Accuracy** | 0.9500 Macro-F1 (`EXP-01`) | **0.5873 Macro-F1** (`EXP-R09`) | Legacy 0.95 F1 was derived from an early 12-flow Scapy loopback fixture (`dataset_v1`). Real physical network traffic evaluated under group-isolated session splitting exhibits substantial inter-class overlap, establishing 0.5873 as the true empirical baseline. |
| **Selective Classification**| 0.9500 Macro-F1 (`EXP-R08`) | **0.6515 Macro-F1** at 54.2% Cov (`EXP-R13`) | Legacy `phase8_final_test.csv` reported 0.95 F1 because the model abstained on 100% of test flows (0.0% coverage). EXP-R13 calibrates $\tau^*=0.70$ strictly on validation data, achieving 0.6515 F1 on accepted test flows. |
| **Operational Latency** | < 0.003 ms real-time | **79.94 ms total triage** (`EXP-R12`) | Microbenchmarks measure isolated CPU `predict()` instructions. In physical reality, packet arrival on the wire requires 64.04 ms, dominating total classification latency by two orders of magnitude. |
| **Tunnel Transfer** | Universal VPN robustness | **0.3407 Macro-F1** ($\Delta\text{F1} = -0.2594$) | Prior works tested unpadded OpenVPN or simulated tunnels. WireGuard's 1280-byte MTU clamping and padding severely mask packet length distributions. |

---

## 11.5 Operational Deployment Guidelines for Network Engineers

Based on our empirical findings, we recommend the following deployment principles:
1. **Deploy Shallow Decision Trees at the Edge:** For switch or router firmware, a single CART Decision Tree ($K=10$, depth $\le 12$) provides optimal throughput ($15,600\text{ fps}$) with negligible accuracy loss relative to large ensembles.
2. **Execute Triage at Packet 3:** Do not wait for flow termination. Extract features from the first 3 packets to achieve **0.6111 Macro-F1** in under **80 ms**.
3. **Enforce Calibrated Rejection ($\tau^* = 0.70$):** In security-critical filtering, enforce $\tau^* = 0.70$ to reduce false positive error rates from 45.8% to 26.9%.
4. **Train Separate Models for Encrypted Tunnels:** Classifiers must be trained on tunnel-encapsulated data if deployed on VPN concentrators or overlay networks.
