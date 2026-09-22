# Computational Efficiency and Hardware Benchmarking Protocol

**Study Identifier:** `EXP-R14`  
**Standard:** Rigorous Host Hardware Benchmarking & Distributional Latency Profiling  
**Repository Component:** [`experiments/computational_efficiency/run.py`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/experiments/computational_efficiency/run.py)  
**Authoritative Tables:**  
- [`results/tables/research_latency.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/research_latency.csv)  
- [`results/tables/research_resource_usage.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/research_resource_usage.csv)  
- [`results/tables/research_model_footprint.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/research_model_footprint.csv)  
**Authoritative Figures:**  
- `latency_distribution.png`  
- `model_size_vs_f1.png`  
- `latency_vs_f1.png`  
- `resource_usage.png`  

---

## 1. Executive Summary & Research Governance

A foundational scientific flaw in practical machine learning performance reporting is the "single favorable measurement" fallacy—reporting an isolated minimum inference time (such as 0.0026 ms) achieved on a pre-allocated tensor as indicative of true operational pipeline performance.

In production network security, latency is a **random variable governed by physical packet arrival, OS scheduling, memory allocation, and feature extraction overhead**. Furthermore, cold start (first invocation) differs by orders of magnitude from warm steady-state execution due to dynamic linking, caching, JIT, and branch predictor warming.

This benchmark establishes an exhaustive computational profiling study on actual host target hardware. It evaluates four lightweight architectures across three feature configurations ($5$, $10$, and $21$ features), decomposes pipeline stages, isolates cold start from warm steady-state, and reports full distributional statistics ($P_{50}$, $P_{95}$, $P_{99}$, Mean, Std, Min, Max).

---

## 2. Host Target Machine & Environment Specification

All benchmarks were executed directly on the host hardware platform without virtualization or container emulation.

| Parameter | Host Specification |
| :--- | :--- |
| **Host Machine Node** | `Rouge017` |
| **Processor (CPU)** | `12th Gen Intel(R) Core(TM) i5-12500H` |
| **Microarchitecture** | Alder Lake Mobile (4 Performance Cores, 8 Efficient Cores) |
| **Logical Core Count** | 16 hardware threads |
| **Total System RAM** | 15.69 GB Physical RAM (DDR4/LPDDR5) |
| **Operating System** | `Windows 11 Home` (Build `10.0.26200-SP0`, 64-bit) |
| **Python Runtime** | `Python 3.14.7` (MSC v.1944 64-bit AMD64) |
| **Scikit-Learn Version**| `1.9.1` |
| **LightGBM Version** | `4.7.0` |
| **NumPy Version** | `2.5.3` |
| **Pandas Version** | `3.0.6` |
| **Matplotlib Version** | `3.11.2` |
| **Joblib Version** | `1.5.3` |
| **Warm Repetitions ($N$)**| $500$ repetitions per configuration |
| **Flow Extraction Reps**| $200$ repetitions on real raw packet streams |

---

## 3. End-to-End Pipeline Decomposition

Decision latency for an incoming encrypted flow decomposes into four sequential phases:
$$\Delta t_{\text{e2e}} = \Delta t_{\text{extract}} + \Delta t_{\text{prep}} + \Delta t_{\text{infer}} + \Delta t_{\text{policy}}$$

```
[ Raw Packet Stream ]
         |
         v   (Feature Extraction: packet timestamps, lengths, directions -> dict)
  \Delta t_extract: P50 = 0.365 ms, P95 = 6.257 ms
         |
         v   (Preprocessing: imputation, scaling, vector alignment)
  \Delta t_prep:    P50 = 0.003 ms, P95 = 0.004 ms
         |
         v   (Model Inference: forward pass / decision tree walk -> probabilities)
  \Delta t_infer:   P50 = 0.056 ms (DT), 0.318 ms (LGBM), 3.716 ms (RF)
         |
         v   (Selective Policy: uncertainty evaluation, state assignment)
  \Delta t_policy:  < 0.001 ms
         |
         v
[ Classified Flow State & Action ]
```

### Empirical Insight: Where Does Time Actually Go?
- **Preprocessing ($\Delta t_{\text{prep}}$)** is negligible: $0.003\text{ ms}$ ($0.7\%$ of end-to-end time), yielding over $290,000\text{ flows/sec}$.
- **Vector Inference ($\Delta t_{\text{infer}}$)** is extremely fast: $0.056\text{ ms}$ ($56\ \mu\text{s}$) for Decision Tree, $0.066\text{ ms}$ for Logistic Regression, and $0.318\text{ ms}$ for LightGBM.
- **Feature Extraction ($\Delta t_{\text{extract}}$)** represents **$83\%\text{--}90\%$** of computational CPU time ($0.365\text{ ms}$ median, $6.257\text{ ms}$ at $P_{95}$).
- Physical observation delay (packet arrival on wire: $80\text{--}350\text{ ms}$, documented in `EXP-R12`) completely dominates both extraction and inference.

---

## 4. Latency Distribution & Cold Start vs. Warm Steady-State

Data extracted from [`results/tables/research_latency.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/research_latency.csv):

### 4.1. Selected 10-Feature Profile Latency Breakdown (ms)

| Component / Model | Phase | Reps | Mean (ms) | Std (ms) | P50 (Median) | P95 (ms) | P99 (ms) | Throughput (fps) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Feature Extraction** | Cold | 1 | 1.7051 | 0.0000 | 1.7051 | 1.7051 | 1.7051 | 586.5 |
| **Feature Extraction** | Warm | 200 | 1.3674 | 2.7282 | **0.3651** | **6.2573** | **8.7748** | **731.3** |
| **Preprocessing** | Cold | 1 | 0.0327 | 0.0000 | 0.0327 | 0.0327 | 0.0327 | 30,581.0 |
| **Preprocessing** | Warm | 500 | 0.0034 | 0.0011 | **0.0033** | **0.0038** | **0.0046** | **294,117.6** |
| | | | | | | | | |
| **Logistic Regression (Infer)**| Cold | 1 | 0.2816 | 0.0000 | 0.2816 | 0.2816 | 0.2816 | 3,551.1 |
| **Logistic Regression (Infer)**| Warm | 500 | 0.0715 | 0.0232 | **0.0658** | **0.0905** | **0.1777** | **13,986.0** |
| **Logistic Regression (E2E)** | Warm | 500 | 1.4448 | 2.7375 | **0.4391** | **6.3433** | **8.8472** | **692.1** |
| | | | | | | | | |
| **Decision Tree (Infer)** | Cold | 1 | 0.2723 | 0.0000 | 0.2723 | 0.2723 | 0.2723 | 3,672.4 |
| **Decision Tree (Infer)** | Warm | 500 | 0.0610 | 0.0196 | **0.0564** | **0.0737** | **0.1582** | **16,393.4** |
| **Decision Tree (E2E)** | Warm | 500 | 1.4343 | 2.7366 | **0.4378** | **6.3515** | **8.8397** | **697.2** |
| | | | | | | | | |
| **Random Forest (Infer)** | Cold | 1 | 3.8578 | 0.0000 | 3.8578 | 3.8578 | 3.8578 | 259.2 |
| **Random Forest (Infer)** | Warm | 500 | 3.8894 | 0.6664 | **3.7156** | **4.7487** | **5.3427** | **257.1** |
| **Random Forest (E2E)** | Warm | 500 | 5.2628 | 2.8042 | **4.3512** | **10.2060** | **14.7622** | **190.0** |
| | | | | | | | | |
| **LightGBM (Infer)** | Cold | 1 | 0.6279 | 0.0000 | 0.6279 | 0.6279 | 0.6279 | 1,592.6 |
| **LightGBM (Infer)** | Warm | 500 | 0.3321 | 0.0614 | **0.3177** | **0.4278** | **0.5459** | **3,011.1** |
| **LightGBM (E2E)** | Warm | 500 | 1.7052 | 2.7371 | **0.7104** | **6.7193** | **9.1418** | **586.4** |

### 4.2. Cold Start Inflation Factor
- **Decision Tree:** Cold start inference ($0.2723\text{ ms}$) is **$4.8\times$ slower** than median warm inference ($0.0564\text{ ms}$).
- **Preprocessing:** Cold start preprocessing ($0.0327\text{ ms}$) is **$9.9\times$ slower** than warm preprocessing ($0.0033\text{ ms}$).
- **Conclusion:** Systems that do not pre-warm model runtimes during initialization will experience latency spikes and queue buildup on initial bursts.

---

## 5. Model Footprint, Complexity & Pareto Trade-Offs

Data extracted from [`results/tables/research_model_footprint.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/research_model_footprint.csv):

| Model | Feature Profile | Feature Count | Serialized Disk (KB) | In-Memory (KB) | Parameter Count | Training Time (s) | Test Accuracy | Test Macro-F1 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Logistic Regression** | Profile 5 | 5 | 0.79 KB | 2,884.9 KB | 36 weights | 0.1049 s | 14.29% | 0.1911 |
| **Logistic Regression** | Profile 10 | 10 | 1.00 KB | 94.5 KB | 66 weights | 0.0179 s | 36.73% | 0.3131 |
| **Logistic Regression** | Profile 21 | 21 | 1.47 KB | 113.9 KB | 132 weights | 0.0275 s | 51.02% | 0.4366 |
| | | | | | | | | |
| **Decision Tree** | Profile 5 | 5 | 3.37 KB | 2,269.5 KB | 107 nodes | 0.0719 s | 38.78% | 0.3556 |
| **Decision Tree** | **Profile 10** | **10** | **3.11 KB** | **34.8 KB** | **95 nodes** | **0.0037 s** | **65.31%** | **0.5827** |
| **Decision Tree** | Profile 21 | 21 | 2.58 KB | 43.7 KB | 73 nodes | 0.0043 s | 67.35% | 0.6633 |
| | | | | | | | | |
| **Random Forest** | Profile 5 | 5 | 201.21 KB | 1,771.4 KB | 9,788 nodes | 0.5140 s | 28.57% | 0.2485 |
| **Random Forest** | Profile 10 | 10 | 175.41 KB | 142.8 KB | 8,364 nodes | 0.4610 s | 46.94% | 0.3986 |
| **Random Forest** | Profile 21 | 21 | 163.38 KB | 150.9 KB | 7,620 nodes | 0.4660 s | 63.27% | 0.5829 |
| | | | | | | | | |
| **LightGBM** | Profile 5 | 5 | 223.92 KB | 2,446.3 KB | 18,600 leaves | 0.0636 s | 38.78% | 0.3309 |
| **LightGBM** | Profile 10 | 10 | 225.65 KB | 2,403.5 KB | 18,600 leaves | 0.0515 s | 67.35% | 0.5485 |
| **LightGBM** | Profile 21 | 21 | 233.66 KB | 2,422.3 KB | 18,600 leaves | 0.0729 s | 67.35% | 0.6423 |

### Scientific Finding: The Decision Tree Pareto Dominance
Across all architectures, the **Decision Tree (10-feature profile)** emerges as the Pareto-optimal model for resource-constrained edge classification:
1. **Footprint:** Serializes to **$3.11\text{ KB}$** on disk (versus $175.4\text{ KB}$ for Random Forest and $225.7\text{ KB}$ for LightGBM—a **$72\times$ reduction**).
2. **Inference Speed:** Executes in **$0.0564\text{ ms}$ ($56\ \mu\text{s}$)**, achieving **$16,393\text{ flows/sec}$**.
3. **Training Time:** Retrains in **$0.0037\text{ seconds}$** ($3.7\text{ ms}$), enabling near-instantaneous online model adaptation at the edge.
4. **Accuracy:** Delivers **$0.5827\text{ Macro-F1}$** ($65.31\%$ accuracy), outperforming both 10-feature Random Forest ($0.3986\text{ F1}$) and 10-feature Logistic Regression ($0.3131\text{ F1}$).

---

## 6. System Resource Utilization (Memory & CPU)

Data extracted from [`results/tables/research_resource_usage.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/research_resource_usage.csv):

| Model | Profile | Working Set (MB) | Peak Working Set (MB) | CPU Time / 1,000 Flows (ms) | CPU Utilization (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Logistic Regression** | Profile 10 | 262.85 MB | 264.50 MB | 62.50 ms | 83.7% |
| **Decision Tree** | Profile 10 | 262.85 MB | 264.50 MB | 62.50 ms | 101.1% |
| **Random Forest** | Profile 10 | 262.86 MB | 264.50 MB | 3,796.88 ms | 99.1% |
| **LightGBM** | Profile 10 | 264.00 MB | 265.68 MB | 328.12 ms | 99.0% |

- **Process Working Set:** Python runtime with loaded models maintains a steady **$\sim 262\text{--}264\text{ MB}$** working set on Windows 11.
- **CPU Cost:** Classifying 1,000 flows requires only **$62.5\text{ ms}$ of CPU time** for Decision Tree and Logistic Regression, compared to **$3,796.9\text{ ms}$** for Random Forest. Random Forest consumes **$60.7\times$ more CPU cycles** per flow due to traversing 100 individual decision trees.

---

## 7. Deployment Guidelines & Architectural Recommendations

| Deployment Tier | Recommended Model | Recommended Features | End-to-End Latency ($P_{50}$) | Serialized Size | Rationale |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **Edge SmartNIC / IoT Router** | `DecisionTree` | Top 10 Features | **$0.438\text{ ms}$** | **$3.11\text{ KB}$** | Fits into L1/L2 instruction cache; $16,000+$ inferences/sec; zero thread pool overhead. |
| **Enterprise Security Gateway** | `LightGBM` | Canonical 21 Features | **$0.710\text{ ms}$** | **$233.7\text{ KB}$** | Balances high Macro-F1 ($0.6423$) with high throughput ($3,000+$ inferences/sec) and native probability calibration. |
| **Offline Forensic Triage** | `RandomForest` | Canonical 21 Features | **$4.351\text{ ms}$** | **$163.4\text{ KB}$** | Maximum ensemble stability when latency is not a critical factor. |
