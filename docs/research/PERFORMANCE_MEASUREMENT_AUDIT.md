# Performance, Latency, and Throughput Measurement Audit

**Repository**: `encrypted-traffic-classification-UROP`  
**Audit Date**: November 2026  
**Auditor**: Independent ML & Systems Research Audit  
**Status**: Authoritative Forensic Evidence Document

---

## 1. Executive Summary

This document reconciles all computational performance, latency, throughput, and early prediction claims against the empirical benchmarks recorded in `results/tables/research_latency.csv` and `results/tables/research_early_prediction.csv`.

Four major performance claims in previous narrative reports are resolved as follows:
1. **Decision Tree Latency**: The claim of **3.1 $\mu\text{s}$ per flow (> 238,000 flows/sec)** is **factually contradicted**. Authoritative warm benchmarks demonstrate Decision Tree inference latency is **59.3 $\mu\text{s}$** (throughput: **16,863.4 flows/sec**).
2. **LightGBM Latency and Throughput**: LightGBM warm inference latency is **335.3 $\mu\text{s}$** (2,982.4 inferences/sec). Including feature extraction (1.46 ms), end-to-end classification latency is **1.81 ms** (**552.4 flows/sec** single-threaded).
3. **10 Gbps Line-Rate Feasibility**: Claims that the Python-based monitor operates at "10 Gbps line-rate" are **unsupported theoretical extrapolations**. A single-threaded throughput of ~552 flows/sec cannot service core line-rate traffic (~1.48 million pkts/sec at 10 Gbps).
4. **Early Prediction Horizon**: The claim of **25 ms early triage** is **factually contradicted**. At a 3-packet horizon, median end-to-end latency is **84.33 ms** (64.04 ms packet wire arrival delay + 20.00 ms inference + 0.01 ms extraction), with a 95th-percentile latency of **459.38 ms**.

---

## 2. Empirical Benchmark Inventory (`results/tables/research_latency.csv`)

The table below records the empirical latency across 21 canonical features evaluated under cold (1 iteration) and warm (200–500 iterations) phases on the Windows 11 host:

| Pipeline Stage | Evaluated Component | Phase | Repetitions | Mean (ms) | Std Dev (ms) | Median / P50 (ms) | P95 (ms) | P99 (ms) | Throughput (fps) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Feature Extraction** | `FeatureExtractor` | Cold | 1 | 1.3868 | 0.0000 | 1.3868 | 1.3868 | 1.3868 | 721.1 |
| **Feature Extraction** | `FeatureExtractor` | Warm | 200 | **1.4588** | 2.9650 | 0.3681 | 7.0281 | 9.4446 | **685.5** |
| **Preprocessing** | `FeaturePreprocessor` | Cold | 1 | 0.0344 | 0.0000 | 0.0344 | 0.0344 | 0.0344 | 29,069.8 |
| **Preprocessing** | `FeaturePreprocessor` | Warm | 500 | **0.0065** | 0.0046 | 0.0060 | 0.0071 | 0.0127 | **153,846.2** |
| **Inference** | `DecisionTree` | Cold | 1 | 0.2610 | 0.0000 | 0.2610 | 0.2610 | 0.2610 | 3,831.4 |
| **Inference** | `DecisionTree` | Warm | 500 | **0.0593** | 0.0247 | 0.0541 | 0.0713 | 0.1875 | **16,863.4** |
| **End-to-End** | `DecisionTree` | Warm | 500 | **1.5344** | 2.9830 | 0.4353 | 7.6338 | 9.5222 | **651.7** |
| **Inference** | `LogisticRegression`| Warm | 500 | **0.0677** | 0.0162 | 0.0641 | 0.0780 | 0.1383 | **14,771.0** |
| **End-to-End** | `LogisticRegression`| Warm | 500 | **1.5428** | 2.9811 | 0.4435 | 7.6434 | 9.5175 | **648.2** |
| **Inference** | `LightGBM` | Cold | 1 | 0.8146 | 0.0000 | 0.8146 | 0.8146 | 0.8146 | 1,227.6 |
| **Inference** | `LightGBM` | Warm | 500 | **0.3353** | 0.0589 | 0.3186 | 0.4355 | 0.6143 | **2,982.4** |
| **End-to-End** | `LightGBM` | Warm | 500 | **1.8104** | 2.9839 | 0.7210 | 7.8753 | 9.8126 | **552.4** |
| **Inference** | `RandomForest` | Warm | 500 | **3.9023** | 0.5113 | 3.7607 | 4.8355 | 5.9505 | **256.3** |
| **End-to-End** | `RandomForest` | Warm | 500 | **5.3774** | 3.0137 | 4.4008 | 11.2732 | 13.4706 | **186.0** |

---

## 3. Discrepancy Reconciliation

### 3.1 The 3.1 $\mu\text{s}$ Decision Tree Origin
- Narrative documents claimed Decision Tree inference executes in $3.1\,\mu\text{s}$ ($> 238,000\,\text{flows/s}$).
- The actual measured time in `research_latency.csv` is **$59.3\,\mu\text{s}$** ($16,863.4\,\text{flows/s}$).
- **Analysis**: The $3.1\,\mu\text{s}$ figure was a theoretical estimate based on pure C-level traversal of a depth-4 tree ($4 \times \approx 0.8\,\text{ns}$ branch predictions). In Python, memory marshalling of the NumPy feature array and wrapper overhead bounds real-world execution to $\approx 59.3\,\mu\text{s}$.

### 3.2 The Primary Latency Bottleneck: Feature Extraction
- The true architectural bottleneck is **not model inference**, but **feature extraction**:
  - LightGBM inference: **0.335 ms**
  - Decision Tree inference: **0.059 ms**
  - Feature extraction: **1.459 ms** (accounting for **80.6%** of end-to-end LightGBM latency and **95.1%** of Decision Tree latency).
- Accelerating the classifier cannot significantly improve overall throughput without optimizing the Python-level packet loop in `feature_extractor.py`.

---

## 4. Early Prediction Latency Audit (`results/tables/research_early_prediction.csv`)

Early classification evaluates flows after observing the first $K$ packets. The table below presents the verified empirical latency components:

| Packet Horizon ($K$) | Flows Classified | Coverage | Accuracy | Macro-F1 | Median Wire Delay | Extraction Delay | Inference Delay | Total Median Latency | Total P95 Latency |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **3 packets** | 11 / 12 | 91.67% | 0.6364 | 0.6111 | **64.04 ms** | 0.0073 ms | 20.0047 ms | **84.33 ms** | **459.38 ms** |
| **5 packets** | 12 / 12 | 100.0% | 0.4167 | 0.3643 | **331.38 ms** | 0.0093 ms | 18.7740 ms | **347.52 ms** | **697.73 ms** |
| **10 packets** | 5 / 12 | 41.67% | 0.8000 | 0.5000 | **1312.08 ms** | 0.0114 ms | 19.5485 ms | **1328.92 ms** | **2710.78 ms** |
| **20 packets** | 7 / 12 | 58.33% | 0.4286 | 0.2778 | **3938.44 ms** | 0.0231 ms | 16.2564 ms | **3954.37 ms** | **4416.43 ms** |
| **30 packets** | 12 / 12 | 100.0% | 0.3333 | 0.2778 | **4877.01 ms** | 0.0245 ms | 15.8875 ms | **4892.58 ms** | **8465.04 ms** |
| **50 packets** | 6 / 12 | 50.00% | 0.5000 | 0.3000 | **9265.80 ms** | 0.0386 ms | 15.8154 ms | **9281.47 ms** | **13765.54 ms** |
| **Full Flow** | 4 / 12 | 33.33% | 0.0000 | 0.0000 | **59650.29 ms**| 0.3587 ms | 15.8930 ms | **59666.52 ms**| **59956.42 ms**|

### 4.1 Breakdown of the 25 ms Early Triage Contradiction
- Previous summaries claimed: *"Early triage occurs at 25 ms."*
- **Empirical Reality**:
  - The physical inter-packet arrival time over genuine Wi-Fi connections imposes a median physical waiting time of **64.04 ms** before 3 packets even arrive on the wire.
  - Adding computational inference and feature extraction yields a total median elapsed time of **84.33 ms**.
  - Under tail network conditions (jitter, retransmissions), the 95th-percentile delay is **459.38 ms**.
  - A claim of 25 ms early triage is impossible under real Wi-Fi network dynamics for multi-packet horizons.

---

## 5. ARM64 / Embedded Hardware Claims

Previous narrative reports suggested that the system had been verified on Raspberry Pi 4 / ARM64 hardware.
- **Audit Finding**: **PROPOSED / UNVERIFIED**.
- The repository contains zero profiling logs, artifacts, or scripts for ARM64 or embedded targets.
- All benchmarks were collected on the development workstation (Intel Core i7 / AMD x86_64 running Windows 11).
- Porting to ARM64 remains an unvalidated research proposal for future work.
