# Research Benchmark Report: Real-Time Encrypted Traffic Classification

**Generated on:** 2026-08-23 07:36:07 UTC  
**Experiment Seed:** 42  
**Project Version:** 0.1.0  

---

## 1. Executive Summary & Research Question

This experiment investigates how accurately encrypted network traffic can be classified using lightweight machine-learning models without inspecting or decrypting packet payloads, while quantifying the trade-offs between classification accuracy, model footprint, and inference latency.

### Key Findings
- **Best Overall Accuracy / Macro-F1 Model:** `lightgbm`
- **Fastest Inference Model:** `decision_tree`
- **Most Compact Footprint:** `random_forest`
- **Pareto-Efficient Models:** `decision_tree, random_forest, lightgbm`

---

## 2. Experimental Setup & Dataset Summary

- **Total Training Samples:** 6
- **Total Validation Samples:** 0
- **Total Held-out Test Samples:** 5
- **Input Feature Dimensions:** 21
- **Target Classes (6):** `File Transfer, Messaging, Other, Video, VoIP, Web`
- **Feature Engineering Strategy:** Pure zero-payload statistical distributions (packet timing, packet size, burst metrics, flow symmetry, port/protocol headers, TLS metadata).
- **Data Leakage Safeguard:** Group-aware splitting on source PCAP (`file_id`) to ensure distinct sessions do not leak between train and test.

---

## 3. Master Empirical Model Comparison

| Model | Accuracy | Macro F1 | Weighted F1 | Latency (ms) | Batch (ms/pkt) | Size (MB) | Train Time (s) | RAM (MB) | CPU % |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **logistic_regression** | 0.0000 | 0.0000 | 0.0000 | 0.0149 | 0.0149 | 0.0014 | 0.0006 | 0.0 | 0.0% |
| **decision_tree** | 0.0000 | 0.0000 | 0.0000 | 0.0028 | 0.0030 | 0.0007 | 0.0004 | 0.0 | 0.0% |
| **random_forest** | 0.0000 | 0.0000 | 0.0000 | 0.0032 | 0.0032 | 0.0005 | 0.0005 | 0.0 | 0.0% |
| **lightgbm** | 0.4000 | 0.3333 | 0.4000 | 0.0033 | 0.0029 | 0.0005 | 0.0005 | 0.0 | 0.0% |

---

## 4. Multi-Criteria Trade-Off & Pareto Frontier Analysis

In production edge networks and line-rate classification appliances, raw accuracy alone is insufficient. Models must balance latency constraints and memory consumption.

- **Non-Dominated (Pareto-Optimal) Models:** `decision_tree, random_forest, lightgbm`
- These models form the empirical efficiency frontier where no alternative is simultaneously higher in Macro-F1, faster in latency, and smaller in storage size.

---

## 5. Top Discriminative Features (Feature Importance)

- **logistic_regression:** `flow_duration` (0.0476), `forward_packet_count` (0.0476), `backward_packet_count` (0.0476), `total_packet_count` (0.0476), `forward_bytes` (0.0476)
- **decision_tree:** `flow_duration` (0.0476), `forward_packet_count` (0.0476), `backward_packet_count` (0.0476), `total_packet_count` (0.0476), `forward_bytes` (0.0476)
- **random_forest:** `flow_duration` (0.0476), `forward_packet_count` (0.0476), `backward_packet_count` (0.0476), `total_packet_count` (0.0476), `forward_bytes` (0.0476)
- **lightgbm:** `flow_duration` (0.0476), `forward_packet_count` (0.0476), `backward_packet_count` (0.0476), `total_packet_count` (0.0476), `forward_bytes` (0.0476)

---

## 6. Error Analysis & Class Ambiguities

| Model | Total Errors | Error Rate | Top Confused Class Pairs | Low-Confidence Predictions |
| :--- | :--- | :--- | :--- | :--- |
| **logistic_regression** | 5 | 1.0000 | Web -> File Transfer (1); Video -> Web (1); Messaging -> File Transfer (1) | 0 |
| **decision_tree** | 5 | 1.0000 | Web -> Other (1); Video -> Messaging (1); Messaging -> Video (1) | 0 |
| **random_forest** | 5 | 1.0000 | Web -> VoIP (1); Video -> Messaging (1); Messaging -> File Transfer (1) | 0 |
| **lightgbm** | 3 | 0.6000 | Video -> Messaging (1); Messaging -> VoIP (1); Other -> Video (1) | 0 |

---

## 7. Threats to Validity & Limitations
1. **Synthetic vs Real Traffic Variability:** Initial baselines were benchmarked against sample captures; real-world environments introduce jitter, TCP packet loss, and dynamic MTUs.
2. **Zero-Day TLS Padding / ESNI:** Advanced encrypted traffic utilizing uniform packet padding (e.g. Tor or padded TLS 1.3) reduces the discriminative power of packet length statistics.
3. **Inference Benchmarking Overhead:** Single-flow micro-benchmarks are subject to OS thread scheduling variances; warmups and repetition averaging are utilized to mitigate measurement noise.

---

## 8. Reproducibility Statement
All data transformations, feature scalers, model weights, and split partitions are version-controlled and deterministically reproducible via:
```bash
python -m training.ml_pipeline
```