# Chapter 10: Empirical Results

This chapter presents the complete empirical results addressing Research Questions RQ1 through RQ6. Every reported metric corresponds strictly to verified measurements recorded in `results/final/*.csv` without extrapolation or data modification.

---

## 10.1 In-Domain Baseline Benchmark Results (RQ1, EXP-R09)

To establish true baseline classification fidelity on real encrypted traffic, all four candidate models were evaluated under uniform canonical 21-feature representations (`baseline_21_zero_payload`) using group-aware stratified session splitting on `dataset_v2`.

### Table 10.1: In-Domain Baseline Performance Matrix (`results/final/baseline_results.csv`)

| Estimator Architecture | Validation Macro-F1 | Test Accuracy | Test Macro-Precision | Test Macro-Recall | Test Macro-F1 | Test Balanced Accuracy | Single-Flow Median Latency | Single-Flow P95 Latency | Serialized Model Footprint | Selected Winner |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Random Forest** | **0.5984** | **0.5833** | 0.5999 | 0.5833 | **0.5873** | 0.5833 | 17.2884 ms | 31.7871 ms | 881.98 KB | **YES** |
| **Decision Tree** | 0.5382 | **0.5833** | 0.6657 | 0.5833 | **0.5802** | 0.5833 | **0.0694 ms** | **0.1893 ms** | **9.58 KB** | NO |
| **LightGBM** | 0.5664 | 0.5417 | 0.5579 | 0.5417 | **0.5474** | 0.5417 | 1.4520 ms | 1.7393 ms | 689.33 KB | NO |
| **Logistic Regression** | 0.3684 | 0.3333 | 0.3327 | 0.3333 | **0.3240** | 0.3333 | 0.0842 ms | 0.1487 ms | 2.00 KB | NO |

### Empirical Observations:
1. **Ensemble Accuracy Ceiling:** Random Forest achieves the highest in-domain test fidelity (**0.5873 Macro-F1** and 0.5833 Accuracy). However, this is far below legacy synthetic claims of >0.95 F1, demonstrating the true difficulty of discriminating real encrypted traffic under strict session isolation.
2. **The Pareto Efficiency of Decision Trees:** The single CART Decision Tree achieves **0.5802 Macro-F1** (98.8% of Random Forest's performance) while executing in **0.0694 ms** ($249\times$ faster) and requiring only **9.58 KB** of storage ($92\times$ smaller than Random Forest).
3. **Failure of Linear Boundaries:** Multinomial Logistic Regression collapses to **0.3240 Macro-F1**, establishing that transport metadata distributions across 6 application classes are non-linearly separable.

---

## 10.2 Feature Family Ablation & Dimensionality Trade-offs (RQ2, EXP-R10)

### A. Feature Family Ablation
To determine the independent discriminative power of each feature group, models were trained strictly on individual feature families.

### Table 10.2: Feature Family Ablation Scorecard (`results/final/feature_ablation.csv`)

| Feature Family | Feature Count ($K$) | Validation Macro-F1 | Validation Accuracy | Test Macro-F1 | Test Accuracy | P95 Inference Latency | Serialized Model Size | Core Empirical Finding |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **D. Direction Only** | 3 | **0.4803** | 0.5000 | **0.4241** | 0.4167 | 27.15 ms | 10.16 KB | Asymmetry ratios carry dense discriminative signal. |
| **B. Timing Only** | 30 | 0.3094 | 0.3333 | 0.3438 | 0.3333 | 28.81 ms | 10.16 KB | Highly vulnerable to network jitter and queuing. |
| **C. Counts / Bytes Only** | 12 | 0.3368 | 0.3333 | 0.3375 | 0.3333 | 31.42 ms | 10.16 KB | Distinguishes bulk transfer from interactive signaling. |
| **A. Packet Size Only** | 30 | 0.3233 | 0.3542 | 0.2949 | 0.3125 | 31.32 ms | 10.16 KB | Degraded under fixed-MTU tunnel encapsulation. |
| **E. Burst Only** | 8 | 0.4075 | 0.4167 | 0.2100 | 0.2292 | 30.15 ms | 10.16 KB | Overfits validation split; poor test generalization. |
| **F. All Families Combined**| 84 | 0.3741 | 0.3750 | 0.2931 | 0.2917 | 28.92 ms | 10.16 KB | Dimensionality curse; excessive noisy features. |

### B. Feature-Count Tradeoff
Evaluating feature counts from $K=3$ to $K=84$ reveals a clear Pareto frontier.

### Table 10.3: Feature Dimensionality vs. Generalization (`results/final/feature_ablation.csv`)

| Feature Count ($K$) | Validation Macro-F1 | Validation Accuracy | Test Macro-F1 | Test Accuracy | P95 Inference Latency | Model Disk Size | Selection Decision |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **$K=3$** | **0.7572** | **0.7708** | **0.6708** | **0.6667** | 28.32 ms | 10.16 KB | **Selected Ultra-Lightweight Profile** |
| **$K=5$** | 0.3324 | 0.3333 | 0.4073 | 0.4167 | 30.04 ms | 10.16 KB | Intermediate candidate |
| **$K=10$** | 0.2531 | 0.2708 | 0.3444 | 0.3750 | 30.29 ms | 10.16 KB | Production multi-environment profile |
| **$K=15$** | 0.3365 | 0.3542 | 0.3591 | 0.3750 | 31.11 ms | 10.16 KB | Diminishing returns |
| **$K=20$** | 0.3422 | 0.3542 | 0.3689 | 0.3750 | 29.57 ms | 10.16 KB | Performance plateau |
| **$K=30$** | 0.3489 | 0.3542 | 0.3775 | 0.3750 | 31.19 ms | 10.16 KB | Marginal gain |
| **$K=84$** | 0.3435 | 0.3333 | 0.2857 | 0.2917 | 31.16 ms | 10.16 KB | Degraded test accuracy due to noise |

---

## 10.3 Domain-Shift Generalization Benchmark Results (RQ3, EXP-R11)

To evaluate operational robustness, models trained on baseline traffic were evaluated across eight distinct distribution-shift regimes without retraining.

### Table 10.4: Domain-Shift Generalization Scorecard (`results/final/generalization.csv`)

| Regime ID | Distribution Shift Evaluated | Test Flows | Accuracy | Macro-Precision | Macro-Recall | Macro-F1 | Balanced Accuracy | Latency (ms) | $\Delta$ F1 vs. Baseline | Robustness Verdict |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **REG-01** | In-Domain Group Baseline | 48 | 0.6042 | 0.6168 | 0.6042 | **0.6001** | 0.6042 | 16.95 | 0.0000 | **ROBUST** |
| **REG-02** | Unseen Capture Split | 60 | 0.7500 | 0.7831 | 0.7738 | **0.7719** | 0.7738 | 20.75 | +0.1718 | **ROBUST** |
| **REG-03** | Unseen Session Split | 60 | 0.7833 | 0.8234 | 0.8333 | **0.7967** | 0.8333 | 17.30 | +0.1966 | **ROBUST** |
| **REG-04** | Temporal Chronological Split | 157 | 0.5350 | 0.5851 | 0.5349 | **0.5437** | 0.5349 | 19.00 | -0.0564 | **MODERATE_DEGRADATION** |
| **REG-05** | Unseen Environment (Eth + Cell) | 120 | **0.9333** | 0.9371 | 0.9333 | **0.9325** | 0.9333 | 18.10 | +0.3324 | **ROBUST** |
| **REG-06** | Unseen Network Condition (Impaired) | 96 | **0.9062** | 0.9210 | 0.9062 | **0.9030** | 0.9062 | 19.21 | +0.3029 | **ROBUST** |
| **REG-07** | Unseen Activity Variants | 46 | 0.8261 | 0.8573 | 0.8361 | **0.8335** | 0.8361 | 18.10 | +0.2334 | **ROBUST** |
| **REG-08a**| Tunnel: Tunneled $\rightarrow$ Direct | 36 | **1.0000** | 1.0000 | 1.0000 | **1.0000** | 1.0000 | 18.65 | +0.3999 | **ROBUST** |
| **REG-08b**| Tunnel: Direct $\rightarrow$ Tunneled (WARP) | 265 | 0.3585 | 0.3658 | 0.3584 | **0.3407** | 0.3584 | 17.87 | **-0.2594** | **SEVERE_DEGRADATION** |

### Key Generalization Findings:
1. **Physical Medium Invariance (REG-05):** Zero-payload statistical features exhibit exceptional transferability across physical Layer-1/2 media. Models trained on Wi-Fi achieved **0.9325 Macro-F1** when tested on unseen Gigabit Ethernet and Cellular LTE streams.
2. **Asymmetric Tunnel Generalization (REG-08a vs. REG-08b):** Models trained on WireGuard traffic transfer to direct unencapsulated traffic with **1.0000 Macro-F1**. Conversely, models trained on unencapsulated traffic collapse to **0.3407 Macro-F1** ($\Delta\text{F1} = -0.2594$) when tested on WireGuard traffic due to MTU padding (1280 bytes) and standardized tunnel handshakes.

---

## 10.4 Early Encrypted-Traffic Classification (RQ4, EXP-R12)

To evaluate how early an accurate decision can be delivered, feature extraction was constrained to packet observation prefixes ($N \in \{3, 5, 10, 20, 30, 50, \text{full}\}$).

### Table 10.5: Early Prediction Horizons & Physical Latency Decomposition (`results/final/early_prediction.csv`)

| Observation Horizon | Packet Count ($N$) | Flow Coverage | Accuracy | Macro-Precision | Macro-Recall | Macro-F1 | Median Decision Latency | Observation Delay | Algorithmic Inference Latency | Retrospective Speedup |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **3 Packets** | 3 | **91.67%** (11/12) | **0.6364** | 0.6667 | 0.6667 | **0.6111** | **79.94 ms** | 64.04 ms | 16.53 ms | **$746\times$ Faster** |
| **5 Packets** | 5 | **100.0%** (12/12) | 0.4167 | 0.3389 | 0.4167 | **0.3643** | 348.89 ms | 331.38 ms | 16.51 ms | $171\times$ Faster |
| **10 Packets** | 10 | 41.67% (5/12) | **0.8000** | 0.5000 | 0.5000 | 0.5000 | 1329.18 ms | 1312.08 ms | 19.13 ms | $45\times$ Faster |
| **20 Packets** | 20 | 58.33% (7/12) | 0.4286 | 0.3333 | 0.2500 | 0.2778 | 3954.60 ms | 3938.44 ms | 16.43 ms | $15\times$ Faster |
| **30 Packets** | 30 | 100.0% (12/12) | 0.3333 | 0.2500 | 0.3333 | 0.2778 | 4893.25 ms | 4877.01 ms | 17.39 ms | $12\times$ Faster |
| **50 Packets** | 50 | 50.00% (6/12) | 0.5000 | 0.3000 | 0.3000 | 0.3000 | 9282.92 ms | 9265.80 ms | 17.30 ms | $6\times$ Faster |
| **Full Flow** | Full | 33.33% (4/12) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | **59,668.15 ms** | 59,650.29 ms | 16.92 ms | Baseline (Post-Mortem) |

### Empirical Insights on Early Triage:
1. **Physical Delay Dominance:** At $N=3$, the physical arrival delay on the wire is **64.04 ms**, whereas feature computation and model inference require **16.53 ms**. Physical transmission delay accounts for **79.5%** to **99.8%** of real-time latency across horizons.
2. **Early Triage Superiority:** Observing only the first 3 packets achieves the highest classification fidelity (**0.6111 Macro-F1** and 0.6364 Accuracy) with **91.67% coverage** in **79.94 ms**. 
3. **Failure of Retrospective Full-Flow Analysis:** Waiting for flow termination incurs a median delay of **59.7 seconds** and results in complete classification failure (0.0000 Macro-F1) because prolonged idle periods and keep-alives dilute the initial distinctive handshake signatures.

---

## 10.5 Selective Classification & Confidence Calibration (RQ5, EXP-R13)

### Table 10.6: Selective Prediction Performance on Locked Test Set (`results/final/selective_prediction.csv`)

| Rejection Threshold ($\tau$) | Test Coverage | Accepted Flows | Selective Accuracy | Error Rate Among Accepted | Selective Macro-F1 | Balanced Accuracy | Average Confidence | Test ECE | Selected Threshold |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| $\tau = 0.00$ (No Rejection) | 100.0% | 48 / 48 | 0.5417 | 45.83% | 0.5474 | 0.5417 | 0.7412 | 0.1996 | NO |
| $\tau = 0.50$ | 91.67% | 44 / 48 | 0.5909 | 40.91% | 0.6012 | 0.5972 | 0.7690 | 0.1781 | NO |
| $\tau = 0.60$ | 75.00% | 36 / 48 | 0.6389 | 36.11% | 0.6110 | 0.6208 | 0.8189 | 0.1800 | NO |
| $\tau = 0.70$ (**Optimal $\tau^*$**) | **54.17%** | **26 / 48** | **0.7308** | **26.92%** | **0.6515** | **0.6556** | **0.8818** | **0.1510** | **YES** |
| $\tau = 0.80$ | 43.75% | 21 / 48 | 0.8571 | 14.29% | 0.8752 | 0.8800 | 0.9112 | 0.0541 | NO |
| $\tau = 0.90$ (High Security) | 20.83% | 10 / 48 | **0.9000** | **10.00%** | **0.9000** | **0.9167** | **0.9658** | **0.0658** | NO |

### Calibration Statistics (`results/final/calibration.csv`):
- **Expected Calibration Error (ECE):** **0.1996**
- **Maximum Calibration Error (MCE):** **0.5581**
- **Multiclass Brier Score:** **0.6061**
- **Negative Log-Likelihood (NLL):** **1.4153**

### Risk-Coverage Synthesis:
Threshold $\tau^* = 0.70$ (selected on validation data) successfully reduces decision error on accepted test flows from **45.83%** down to **26.92%** at **54.17% coverage**, achieving **0.6515 Selective Macro-F1**. In strict high-security applications, setting $\tau = 0.90$ achieves **90.00% Selective Accuracy** (10.0% error) at 20.83% coverage.

---

## 10.6 Real-Time Latency & Edge Computational Efficiency (RQ6, EXP-R14 & EXP-R15)

### Table 10.7: Stage-by-Stage Latency Breakdown (Warm Steady-State, 10 Features) (`results/final/latency.csv`)

| Subsystem Stage | Evaluated Component | P50 (Median) | P95 Latency | P99 Latency | Max Latency | Throughput (FPS) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Feature Extraction** | Statistical Engine | 0.3856 ms | 7.1524 ms | 9.4675 ms | 26.80 ms | 667.6 flows/s |
| **Preprocessing / Scaling** | FeaturePreprocessor | 0.0035 ms | 0.0040 ms | 0.0215 ms | 0.0697 ms | 243,902 flows/s |
| **Model Inference** | **Decision Tree** | **0.0579 ms** | **0.0860 ms** | **0.1982 ms** | 0.4916 ms | **15,600.6 flows/s** |
| **Model Inference** | Logistic Regression | 0.0695 ms | 0.1642 ms | 0.2656 ms | 0.3945 ms | 12,224.9 flows/s |
| **Model Inference** | LightGBM | 0.3520 ms | 0.7419 ms | 0.9477 ms | 1.2387 ms | 2,307.3 flows/s |
| **Model Inference** | Random Forest | 4.2476 ms | 7.8099 ms | 9.5337 ms | 10.2371 ms | 213.3 flows/s |
| **End-to-End Pipeline** | **Decision Tree** | **0.4491 ms** | **7.2144 ms** | **9.5481 ms** | 26.8656 ms | **638.9 flows/s** |
| **End-to-End Pipeline** | Logistic Regression | 0.4714 ms | 7.2310 ms | 9.5484 ms | 27.0171 ms | 631.7 flows/s |
| **End-to-End Pipeline** | LightGBM | 0.8700 ms | 7.7095 ms | 9.9364 ms | 27.1473 ms | 516.9 flows/s |
| **End-to-End Pipeline** | Random Forest | 5.1343 ms | 11.3575 ms | 14.4031 ms | 34.8385 ms | 161.6 flows/s |

### Operational Live-Pipeline Smoke Test (EXP-R15):
The complete physical pipeline (Npcap $\rightarrow$ FlowTracker $\rightarrow$ Zero-Payload Extractor $\rightarrow$ Preprocessing $\rightarrow$ Decision Tree $\rightarrow$ REST API $\rightarrow$ Streamlit Dashboard) was validated under live traffic. The system ingested 142 packets across 15 flows at **81.78 predictions/sec** with **0.072 ms** median decision latency, 0 dropped flows, and 0 processing failures under strict localhost isolation.
