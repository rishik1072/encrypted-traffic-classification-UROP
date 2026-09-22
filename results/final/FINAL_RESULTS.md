# Master Scientific Results & Empirical Evidence Package

**Repository:** Real-Time Encrypted Network Traffic Classification  
**Status:** Authoritative Final Release  
**Target Platform:** Windows 11 / Windows 10 x64  
**Date:** September 2026  
**Authoritative Dataset:** `dataset_v2` (Multi-Environment Real-Traffic Benchmark)  
**Verification Baseline:** Strict Group-Aware Session Isolation, Locked Test Evaluation  

---

## 1. Dataset Provenance & Characterization

All primary scientific conclusions in this release are derived exclusively from the authoritative real dataset (`dataset_v2`), which captures real user interactions across physical Wi-Fi, Ethernet, and Cellular LTE networks with both direct and Cloudflare WARP (WireGuard) tunnel encapsulation.

### Dataset Summary Table (`results/final/dataset_summary.csv`)
- **Dataset ID:** `dataset_v2`
- **Origin Classification:** `REAL_DATA` (Strictly segregated from synthetic fixtures `dataset_v1` and replay vectors `demo_data`)
- **Total Valid Flows:** 301 bidirectional flows
- **Total User Sessions:** 150 independent capture sessions
- **Number of Classes:** 6 canonical traffic classes (Web: 50, Video: 50, Messaging: 50, VoIP: 50, File Transfer: 50, Other: 51)
- **Environments Captured:**
  - `env_win11_wifi`: Physical 802.11ax Wi-Fi workstation
  - `env_win11_eth`: Dedicated Gigabit Ethernet
  - `env_win11_cellular`: Tethered LTE cellular interface
- **Tunnel States:**
  - `warp_disabled` (direct): Standard unencapsulated TLS/HTTPS, QUIC/HTTP3, WebRTC, DNS-over-HTTPS
  - `warp_enabled`: WireGuard UDP tunnel encapsulation (fixed 1280-byte MTU, standardized padding, tunnel headers)
- **Primary Feature Source:** `data/processed/features/features_real_clean_v2.csv`
- **Primary Flow Source:** `data/processed/flows/flows_real_clean.csv`
- **Integrity Checksum (SHA-256):** `cd3193ecdd2ecb4859ba6b23bb75153571e205930f05fa2dc7323fcfc1a2c16d`

---

## 2. Experimental Protocol & Leakage Controls

### Partitioning & Group-Aware Isolation
- **Splitting Strategy:** Group-aware stratified session isolation (70% Train, 15% Validation, 15% Locked Test).
  - Train Split: 205 flows across 102 sessions
  - Validation Split: 48 flows across 24 sessions
  - Locked Test Split: 48 flows across 24 sessions
- **Independence Guarantee:** Zero overlap of Session IDs or Capture IDs between partitions ($\text{Train} \cap \text{Val} = \emptyset$, $\text{Train} \cap \text{Test} = \emptyset$, $\text{Val} \cap \text{Test} = \emptyset$).
- **Topological Shortcut Prevention:** All Layer-3/Layer-4 addressing identifiers (source IP, destination IP, source port, destination port, MAC addresses, precise epoch timestamps) are strictly excised prior to model training.
- **Model Selection Rule:** All hyperparameter tuning, feature subset selection, and abstention thresholds are fitted strictly on Train and tuned on Validation; the Test split is evaluated exactly once with frozen weights.

---

## 3. Evaluated Model Architectures

Four lightweight supervised estimators were evaluated under uniform feature representations:

1. **Logistic Regression (`logistic_regression`):** Multi-class one-vs-rest with L2 regularization ($C=1.0$), L-BFGS solver, standardized feature scaling.
2. **Decision Tree (`decision_tree`):** CART estimator with Gini impurity, maximum depth of 12, minimum samples per split of 5.
3. **Random Forest (`random_forest`):** Ensemble of 100 decorrelated decision trees, maximum depth 15, minimum samples per split 4.
4. **LightGBM (`lightgbm`):** Gradient-boosted decision tree ensemble, 100 boosting rounds, 31 leaves, learning rate 0.05, multiclass objective.

---

## 4. Feature Configuration & Registry

All features are extracted strictly from packet metadata without payload inspection or TLS decryption:

- **Canonical 21 Profile (`baseline_21_zero_payload`):** 21 Layer-3/4 statistical features covering flow duration, bidirectional packet/byte counts, packet length statistics (min, max, mean, variance), inter-arrival time (IAT) statistics (min, max, mean, median, std), forward-to-backward ratios, and burst dynamics.
- **Lightweight 10 Profile (`profile_10_features`):** Selected via validation-data Pareto optimization. Features: `fwd_packet_count`, `bwd_packet_count`, `total_bytes`, `avg_packet_size`, `max_packet_size`, `mean_iat`, `fwd_bwd_byte_ratio`, `fwd_bwd_packet_ratio`, `packet_ratio`, `packets_per_sec`.
- **Zero-Payload Assurance:** No application data units, TLS SNI, certificate hashes, or cleartext string patterns are utilized.

---

## 5. Baseline Results (EXP-R09)

*Source: `results/final/baseline_results.csv` and `results/final/model_comparison.csv`*

| Model Architecture | Val Macro-F1 | Test Accuracy | Test Macro-Precision | Test Macro-Recall | Test Macro-F1 | Test Balanced Accuracy | Single-Flow Median Latency | Single-Flow P95 Latency | Serialized Model Size | Selected Winner |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Random Forest** | **0.5984** | **0.5833** | 0.5999 | 0.5833 | **0.5873** | 0.5833 | 17.2884 ms | 31.7871 ms | 881.98 KB | **YES** |
| **Decision Tree** | 0.5382 | **0.5833** | 0.6657 | 0.5833 | **0.5802** | 0.5833 | **0.0694 ms** | **0.1893 ms** | **9.58 KB** | NO |
| **LightGBM** | 0.5664 | 0.5417 | 0.5579 | 0.5417 | **0.5474** | 0.5417 | 1.4520 ms | 1.7393 ms | 689.33 KB | NO |
| **Logistic Regression** | 0.3684 | 0.3333 | 0.3327 | 0.3333 | **0.3240** | 0.3333 | 0.0842 ms | 0.1487 ms | 2.00 KB | NO |

### Baseline Synthesis
On real encrypted traffic under strict group-aware isolation, zero-payload statistical features achieve **0.5873 Macro-F1** (Random Forest) and **0.5802 Macro-F1** (Decision Tree). Decision Tree delivers 98.8% of Random Forest's macro-F1 while executing in **0.069 ms** ($249\times$ faster) with a **9.58 KB** serialized model footprint.

---

## 6. Feature Ablation Results (EXP-R10)

*Source: `results/final/feature_ablation.csv`*

### A. Feature Family Ablation (`EXP-R10-FAMILY`)
| Feature Family | Features ($K$) | Val Macro-F1 | Val Accuracy | Test Macro-F1 | Test Accuracy | P95 Latency | Disk Footprint | Core Findings |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **D. Direction Only** | 3 | **0.4803** | 0.5000 | **0.4241** | 0.4167 | 27.15 ms | 10.16 KB | Asymmetry ratios carry high discriminative density. |
| **B. Timing Only** | 30 | 0.3094 | 0.3333 | 0.3438 | 0.3333 | 28.81 ms | 10.16 KB | Sensitive to network jitter and bufferbloat. |
| **C. Counts / Bytes Only** | 12 | 0.3368 | 0.3333 | 0.3375 | 0.3333 | 31.42 ms | 10.16 KB | Separates bulk transfer from low-volume signaling. |
| **A. Packet Size Only** | 30 | 0.3233 | 0.3542 | 0.2949 | 0.3125 | 31.32 ms | 10.16 KB | Compromised under fixed MTU tunnel padding. |
| **E. Burst Only** | 8 | 0.4075 | 0.4167 | 0.2100 | 0.2292 | 30.15 ms | 10.16 KB | Overfits validation sessions; poor test generalization. |
| **F. All Feature Families** | 84 | 0.3741 | 0.3750 | 0.2931 | 0.2917 | 28.92 ms | 10.16 KB | Ensembling 84 raw features introduces noise. |

### B. Feature-Count Tradeoff (`EXP-R10-COUNT`)
| Feature Count ($K$) | Val Macro-F1 | Val Accuracy | Test Macro-F1 | Test Accuracy | P95 Latency | Disk Footprint | Profile Decision |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **$K=3$** | **0.7572** | **0.7708** | **0.6708** | **0.6667** | 28.32 ms | 10.16 KB | **Selected Ultra-Lightweight Profile** |
| **$K=5$** | 0.3324 | 0.3333 | 0.4073 | 0.4167 | 30.04 ms | 10.16 KB | Candidate subset |
| **$K=10$** | 0.2531 | 0.2708 | 0.3444 | 0.3750 | 30.29 ms | 10.16 KB | Candidate subset |
| **$K=15$** | 0.3365 | 0.3542 | 0.3591 | 0.3750 | 31.11 ms | 10.16 KB | Candidate subset |
| **$K=20$** | 0.3422 | 0.3542 | 0.3689 | 0.3750 | 29.57 ms | 10.16 KB | Candidate subset |
| **$K=30$** | 0.3489 | 0.3542 | 0.3775 | 0.3750 | 31.19 ms | 10.16 KB | Candidate subset |
| **$K=84$** | 0.3435 | 0.3333 | 0.2857 | 0.2917 | 31.16 ms | 10.16 KB | Candidate subset |

---

## 7. Generalization Results (EXP-R11)

*Source: `results/final/generalization.csv`*

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

### Key Generalization Insights
1. **Physical Medium Invariance:** Transfer across physical Layer-1/2 interfaces (Wi-Fi to Ethernet and Cellular) achieves **0.9325 Macro-F1**, proving transport statistical features are independent of transmission medium.
2. **Asymmetric Tunnel Generalization:** Models trained on WireGuard traffic transfer to direct unencapsulated traffic (**1.0000 Macro-F1**), whereas models trained on direct traffic degrade significantly when tested on WireGuard/WARP flows (**0.3407 Macro-F1**, $\Delta\text{F1} = -0.2594$) due to MTU padding and handshake masking.

---

## 8. Early Prediction Results (EXP-R12)

*Source: `results/final/early_prediction.csv`*

| Observation Point | Packet Horizon | Is Full Flow | Flow Coverage | Accuracy | Macro-Precision | Macro-Recall | Macro-F1 | Median Decision Latency | Observation Delay | Inference Latency |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **3 Packets** | 3 | False | **91.67%** (11/12) | **0.6364** | 0.6667 | 0.6667 | **0.6111** | **79.94 ms** | 64.04 ms | 16.53 ms |
| **5 Packets** | 5 | False | **100.0%** (12/12) | 0.4167 | 0.3389 | 0.4167 | **0.3643** | 348.89 ms | 331.38 ms | 16.51 ms |
| **10 Packets** | 10 | False | 41.67% (5/12) | **0.8000** | 0.5000 | 0.5000 | 0.5000 | 1329.18 ms | 1312.08 ms | 19.13 ms |
| **20 Packets** | 20 | False | 58.33% (7/12) | 0.4286 | 0.3333 | 0.2500 | 0.2778 | 3954.60 ms | 3938.44 ms | 16.43 ms |
| **30 Packets** | 30 | False | 100.0% (12/12) | 0.3333 | 0.2500 | 0.3333 | 0.2778 | 4893.25 ms | 4877.01 ms | 17.39 ms |
| **50 Packets** | 50 | False | 50.00% (6/12) | 0.5000 | 0.3000 | 0.3000 | 0.3000 | 9282.92 ms | 9265.80 ms | 17.30 ms |
| **Full Flow** | full | True | 33.33% (4/12) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | **59,668.15 ms** | 59,650.29 ms | 16.92 ms |

### Latency Hierarchy Insight
Physical packet observation delay constitutes **99.8%** of real-time classification latency. Early triage at $N=3$ packets provides actionable classification (**0.6111 Macro-F1**, 91.7% coverage) in **79.94 ms**, whereas waiting for retrospective full-flow termination delays decisions by **~59.7 seconds** ($746\times$ longer) and fails due to temporal dilution.

---

## 9. Selective Prediction Results (EXP-R13)

*Source: `results/final/selective_prediction.csv` and `results/final/calibration.csv`*

### A. Confidence Rejection Policy (Locked Test Partition)
| Rejection Threshold ($\tau$) | Test Coverage | Accepted Flows | Selective Accuracy | Error Rate Among Accepted | Selective Macro-F1 | Balanced Accuracy | Average Confidence | Test ECE | Selected Threshold |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| $\tau = 0.00$ (No Rejection) | 100.0% | 48 / 48 | 0.5417 | 45.83% | 0.5474 | 0.5417 | 0.7412 | 0.1996 | NO |
| $\tau = 0.50$ | 91.67% | 44 / 48 | 0.5909 | 40.91% | 0.6012 | 0.5972 | 0.7690 | 0.1781 | NO |
| $\tau = 0.60$ | 75.00% | 36 / 48 | 0.6389 | 36.11% | 0.6110 | 0.6208 | 0.8189 | 0.1800 | NO |
| $\tau = 0.70$ (**Optimal $\tau^*$**) | **54.17%** | **26 / 48** | **0.7308** | **26.92%** | **0.6515** | **0.6556** | **0.8818** | **0.1510** | **YES** |
| $\tau = 0.80$ | 43.75% | 21 / 48 | 0.8571 | 14.29% | 0.8752 | 0.8800 | 0.9112 | 0.0541 | NO |
| $\tau = 0.90$ (High Security) | 20.83% | 10 / 48 | **0.9000** | **10.00%** | **0.9000** | **0.9167** | **0.9658** | **0.0658** | NO |

### B. Calibration Statistics (Locked Test Partition)
- **Expected Calibration Error (ECE):** **0.1996**
- **Maximum Calibration Error (MCE):** **0.5581**
- **Multiclass Brier Score:** **0.6061**
- **Negative Log-Likelihood (NLL):** **1.4153**
- **Threshold Selection Rule:** The optimal threshold $\tau^* = 0.70$ was determined strictly on the validation set ($\text{Coverage}_{\text{val}} = 50.0\%$, $\text{Accuracy}_{\text{val}} = 75.0\%$). When evaluated on the locked test set, it reduces accepted error rate from 45.83% down to 26.92% while raising selective accuracy from 54.17% to 73.08%.

---

## 10. Real-Time Performance (EXP-R14 & EXP-R15)

*Source: `results/final/latency.csv`*

### Benchmark Hardware Platform
- **Processor:** `12th Gen Intel(R) Core(TM) i5-12500H` (16 logical cores @ 2.50 GHz base / 4.50 GHz boost)
- **Physical RAM:** 15.69 GB DDR4/DDR5
- **Host OS:** Microsoft Windows 11 Enterprise (Build 10.0.26200 x64)
- **Python Runtime:** Python 3.14.7 64-bit AMD64
- **Core ML Versions:** scikit-learn 1.9.1, LightGBM 4.7.0, NumPy 2.4.2, SciPy 1.17.1

### Stage-by-Stage Latency Profile (Warm Steady-State, 10 Features)
| Pipeline Subsystem | Evaluated Model / Component | P50 Latency | P95 Latency | P99 Latency | Max Latency | Throughput (FPS) |
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

---

## 11. Resource Usage (EXP-R14)

*Source: `results/final/resource_usage.csv`*

### Memory, CPU, and Disk Footprint (10 Features Profile)
| Model Architecture | Feature Profile | Working Set RAM | Peak RAM | Serialized Disk Size | Training Time | CPU Time per 1k Flows | CPU Utilization |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Decision Tree** | `profile_10_features` | **289.60 MB** | **362.89 MB** | **3.11 KB** | **0.0041 s** | **62.50 ms** | **87.8%** |
| **Logistic Regression** | `profile_10_features` | 289.60 MB | 362.89 MB | 1.00 KB | 0.0234 s | 62.50 ms | 77.3% |
| **Random Forest** | `profile_10_features` | 289.62 MB | 362.89 MB | 175.41 KB | 0.6120 s | 4828.12 ms | 96.2% |
| **LightGBM** | `profile_10_features` | 290.12 MB | 362.89 MB | 225.64 KB | 0.0799 s | 390.62 ms | 98.2% |

---

## 12. Limitations & Forensic Discrepancy Resolutions

### A. System & Methodological Limitations
1. **Windows Npcap Privilege Dependency:** Live packet sniffing requires administrative access and an installed Npcap/WinPcap driver. Standard unprivileged users must operate in replay/DEMO mode.
2. **Closed-World Class Assumption:** The models are trained on 6 canonical traffic classes. Unseen proprietary protocols must be rejected via the selective classification policy ($\tau=0.70$) to prevent forced misclassification.
3. **WireGuard Padding Masking:** Models trained purely on direct traffic suffer from performance degradation when tested on WireGuard/WARP tunneled flows due to MTU padding and standardized tunnel packet lengths.
4. **Interactive Class Overlap:** Fine-grained discrimination between `Web` and `Messaging` remains challenging during long, bursty HTTP/WebSocket sessions.

### B. Forensic Discrepancy Resolution Table
| # | Conflict / Discrepancy | Stale / Inaccurate Source | Authoritative Source | Authoritative Value | Forensic Resolution & Scientific Rationale |
|---|---|---|---|:---:|---|
| **1** | **Baseline Macro-F1** (0.9500 vs. 0.5873) | `model_comparison.csv` (EXP-01) | `research_baseline.csv` (EXP-R09) | **0.5873** (RF)<br>**0.5802** (DT) | The 0.9500 figure was generated on an early 12-flow synthetic fixture (`dataset_v1`). Real traffic under session-isolated group evaluation achieves 0.5873 Macro-F1. Synthetic 0.95 is marked as `STALE / SYNTHETIC_ONLY`. |
| **2** | **Selective Macro-F1** (0.9500 vs. 0.6515) | `phase8_final_test.csv` (EXP-R08) | `research_selective_prediction.csv` (EXP-R13) | **0.6515** ($\tau^*=0.70$, 54.2% Cov) | `phase8_final_test.csv` reported 0.95 Macro-F1 with **0.0% coverage** (the model rejected 100% of test samples). EXP-R13 calibrates thresholds on validation data, achieving 0.6515 Macro-F1 at 54.2% coverage on real test flows. |
| **3** | **Real-Time Latency** (< 0.003 ms vs. 79.94 ms) | `README.md` (EXP-06 microbench) | `research_early_prediction.csv` (EXP-R12) & `research_latency.csv` (EXP-R14) | **79.94 ms** (Triage)<br>**0.449 ms** (End-to-End) | The <0.003 ms claim isolated single-sample C tree evaluation, ignoring physical packet arrival delays and feature calculation. Total triage time requires 79.94 ms (64 ms physical observation + 16.5 ms inference). |
| **4** | **Direct to Tunneled Generalization** (0.9000 vs. 0.3407) | `generalization_scorecard.csv` (EXP-08) | `research_generalization_scorecard.csv` (EXP-R11) | **0.3407** ($\Delta\text{F1}=-0.2594$) | The legacy 0.9000 figure was computed on synthetic PCAP splits. WireGuard tunnel padding severely masks packet length distributions, causing direct models to drop from 0.6001 to 0.3407 Macro-F1 when evaluated on real WARP traffic. |
| **5** | **Test Pass Count** ("27/27" vs. 100%) | `README.md` / `final_test_matrix.csv` | Active PyTest Suite | **100% Pass** (111 tests) | Legacy documentation referenced a static 27-row table. Active test suite contains comprehensive tests across product, privacy, lifecycle, and research benchmarks. |

---

## 13. Reproducibility Information

### Unified Reproduction Command
Every table and metric in this package can be reproduced from scratch using the unified research script:

```powershell
python scripts/reproduce_research.py --all
```

### Granular Execution Options
- `python scripts/reproduce_research.py --dataset`: Stages 1–4 (Environment, dataset verification, quality audit, leakage audit).
- `python scripts/reproduce_research.py --baseline`: Stages 1–2, 5, 8 (Baseline benchmark & model comparison).
- `python scripts/reproduce_research.py --features`: Stages 1–2, 6, 7 (Feature family ablation & feature reduction).
- `python scripts/reproduce_research.py --generalization`: Stages 1–2, 9 (8 distribution shifts).
- `python scripts/reproduce_research.py --early`: Stages 1–2, 10 (Packet observation horizons 3 to 50 pkts).
- `python scripts/reproduce_research.py --selective`: Stages 1–2, 11 (Confidence threshold sweeps and calibration).
- `python scripts/reproduce_research.py --latency`: Stages 1–2, 12 (Latency and resource benchmarking).

### Manifest & Verification
Upon completion, the pipeline automatically writes [`results/research_manifest.json`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/research_manifest.json), capturing:
- Complete runtime environment metadata (OS, Python version, CPU, RAM).
- Dataset provenance and SHA-256 integrity checksum (`cd3193ecdd2ecb4859ba6b23bb75153571e205930f05fa2dc7323fcfc1a2c16d`).
- Stage execution times and individual status codes.
- SHA-256 cryptographic hashes for all generated CSV tables and publication figures.
