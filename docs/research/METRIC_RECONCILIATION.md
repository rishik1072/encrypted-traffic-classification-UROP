# Empirical Performance Metric Reconciliation Report

**Document Version:** 1.0.0  
**Audit Date:** November 2026  
**Auditor:** Independent Evidence Reconciliation & Integrity Auditor  
**Repository:** `c:\UROP project\encrypted-traffic-classification-UROP`  
**Core Objective:** Reconcile all reported metrics against exact physical artifacts and identify false or invalid comparisons.  

---

## 1. Executive Summary & Verification Ledger

This audit cross-references every headline performance metric against raw CSV output tables, preserved model artifacts, and evaluation logs. Every metric is categorized as **Verified**, **Unverified**, or **Contradicted**.

```
+---------------------------------------------------------------------------------------------------------+
|                                    METRIC RECONCILIATION SCORECARD                                      |
|                                                                                                         |
|  [VERIFIED]     Random Forest Benchmark on dataset_v2:       Macro-F1 = 0.5854, Accuracy = 0.5833       |
|  [VERIFIED]     Decision Tree Benchmark on dataset_v2:       Macro-F1 = 0.5802, Accuracy = 0.5833       |
|  [VERIFIED]     LightGBM Benchmark on dataset_v2:            Macro-F1 = 0.5474, Accuracy = 0.5417       |
|  [VERIFIED]     Physical Wi-Fi Baseline on dataset_real_v1:  Macro-F1 = 0.0833, Accuracy = 0.0833 (1/12)|
|  [VERIFIED]     Warm Inference Latency:                      LGBM = 335.3 us, DT = 59.3 us              |
|  [CONTRADICTED] Coarse 2-Family Macro-F1 of 0.9439:          Artifact does not exist (flat F1 = 0.0686) |
|  [CONTRADICTED] 87.1% Accuracy at tau=0.70:                 Actual is 73.08% Accuracy at 54.17% Coverage|
|  [CONTRADICTED] Decision Tree 3.1 us / 238,000 flows/sec:    Actual is 59.3 us (~16,800 flows/sec)      |
|  [CONTRADICTED] Comparative "Split Illusion" 0.95 vs 0.58:   Compared 12 synthetic flows vs 301 hybrid  |
+---------------------------------------------------------------------------------------------------------+
```

---

## 2. In-Domain Benchmark Reconciliation (`dataset_v2`)

- **Artifact Source:** [`results/tables/research_baseline.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/research_baseline.csv) and [`research_baseline_per_class.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/research_baseline_per_class.csv).
- **Dataset ID:** `dataset_v2` (Version 2.0.0, `HYBRID_PERTURBED`).
- **Dataset Composition:** 301 total flows (121 physical Wi-Fi flows + 180 controlled statistical feature perturbations).
- **Taxonomy:** 6 Fine-Grained Classes (`File Transfer`, `Messaging`, `Other`, `Video`, `VoIP`, `Web`).
- **Data Partitions:** 70% Train (205 flows, 102 sessions), 15% Validation (48 flows, 24 sessions), 15% Test (48 flows, 24 sessions).
- **Split Strategy:** Session-isolated group split (`EXP-R09_baseline_group_split`, seed 42).
- **Test Set Support:** Perfectly balanced at exactly 8 flows per class across all 6 classes.

### Authoritative Empirical Results Table (`dataset_v2` Held-Out Test Set)

| Model Name | Training Samples | Val Samples | Test Samples | Test Accuracy | Test Macro-F1 | Test Macro-Prec | Test Macro-Rec | Test Balanced Acc | Verification Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Random Forest** | 205 | 48 | 48 | **$0.5833$** | **$0.5854$** | $0.6120$ | $0.5833$ | $0.5833$ | **VERIFIED** |
| **Decision Tree** | 205 | 48 | 48 | **$0.5833$** | **$0.5802$** | $0.6014$ | $0.5833$ | $0.5833$ | **VERIFIED** |
| **LightGBM** | 205 | 48 | 48 | **$0.5417$** | **$0.5474$** | $0.5685$ | $0.5417$ | $0.5417$ | **VERIFIED** |
| **Logistic Regression**| 205 | 48 | 48 | **$0.3333$** | **$0.3240$** | $0.3542$ | $0.3333$ | $0.3333$ | **VERIFIED** |

### Per-Class Performance Breakdown (Held-Out Test Set, $N=48$, Support $= 8$ per class)

| Model | Class | Precision | Recall | F1-Score | True Positives ($/8$) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Random Forest** | File Transfer | $0.7500$ | $0.7500$ | $0.7500$ | 6 / 8 |
| | Messaging | $0.4286$ | $0.3750$ | $0.4000$ | 3 / 8 |
| | Other | $0.8333$ | $0.6250$ | $0.7143$ | 5 / 8 |
| | Video | $0.5556$ | $0.6250$ | $0.5882$ | 5 / 8 |
| | VoIP | $0.4545$ | $0.6250$ | $0.5263$ | 5 / 8 |
| | Web | $0.5714$ | $0.5000$ | $0.5333$ | 4 / 8 |
| **Decision Tree** | File Transfer | $0.8571$ | $0.7500$ | $0.8000$ | 6 / 8 |
| | Messaging | $0.6667$ | $0.5000$ | $0.5714$ | 4 / 8 |
| | Other | $0.6667$ | $0.5000$ | $0.5714$ | 4 / 8 |
| | Video | $0.4706$ | $1.0000$ | $0.6400$ | 8 / 8 |
| | VoIP | $0.3333$ | $0.3750$ | $0.3529$ | 3 / 8 |
| | Web | $1.0000$ | $0.3750$ | $0.5455$ | 3 / 8 |
| **LightGBM** | File Transfer | $0.7500$ | $0.7500$ | $0.7500$ | 6 / 8 |
| | Messaging | $0.3333$ | $0.3750$ | $0.3529$ | 3 / 8 |
| | Other | $0.7500$ | $0.7500$ | $0.7500$ | 6 / 8 |
| | Video | $0.6250$ | $0.6250$ | $0.6250$ | 5 / 8 |
| | VoIP | $0.2222$ | $0.2500$ | $0.2353$ | 2 / 8 |
| | Web | $0.6667$ | $0.5000$ | $0.5714$ | 4 / 8 |

---

## 3. Pure Physical Baseline Reconciliation (`dataset_real_v1`)

- **Artifact Source:** [`results/tables/real_baseline_per_class_metrics.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/real_baseline_per_class_metrics.csv) and [`real_baseline_error_analysis.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/real_baseline_error_analysis.csv).
- **Dataset ID:** `dataset_real_v1` (Version 1.1.0, pure physical Wi-Fi traffic, zero perturbations).
- **Total Dataset Size:** 121 flows across 60 capture sessions.
- **Data Partitions:** 70% Train (85 flows, 42 sessions), 20% Val (24 flows, 12 sessions), 10% Test (12 flows, 6 sessions).
- **Test Sample Count:** **$N_{\text{test}} = 12$ flows** (exactly 2 flows per class).

### Physical Test Results Breakdown ($N_{\text{test}} = 12$)

| Model Name | Correct Flows ($/12$) | Test Accuracy | Test Macro-F1 | Per-Class Correct Detections | Primary Misclassification Mode |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **Random Forest** | **1 / 12** | **$0.0833$** | **$0.0833$** | `Other`: 1/2 correct (P=0.5, R=0.5, F1=0.5); all other 5 classes: 0/2 | Collapsed to `File Transfer` and `Web` under WireGuard encapsulation |
| **Decision Tree** | **1 / 12** | **$0.0833$** | **$0.0555$** | `Web`: 1/2 correct (P=0.25, R=0.5, F1=0.3333); all other 5 classes: 0/2 | High variance on packet size boundaries |
| **LightGBM** | **1 / 12** | **$0.0833$** | **$0.0667$** | `File Transfer`: 1/2 correct (P=0.33, R=0.5, F1=0.40); all other 5 classes: 0/2 | WireGuard MTU padding neutralizes packet size features |
| **Logistic Regression**| **2 / 12** | **$0.1667$** | **$0.0606$** | `File Transfer`: 2/2 correct (P=0.22, R=1.0, F1=0.36); all other 5 classes: 0/2 | Degenerate majority-class guessing |

### Forensic Finding on Physical Baseline:
The $0.0833$ Macro-F1 score is **mathematically verified**, but represents extreme **sample starvation** ($N=12$). With only 2 flows per class, correctly predicting 1 flow gives $8.33\%$ accuracy; predicting 0 gives $0\%$. This score must be cited alongside its sample size limitation, not as a generalized indictment of machine learning feasibility.

---

## 4. Contradicted Claims & Discrepancy Analysis

### 4.1 The Non-Existent "Two-Family Coarse Macro-F1 of $0.9439$"
- **Previous Statement:** "Production LightGBM achieves a two-family macro-F1 of $0.9439$ on Bulk_Streaming vs Interactive in `results/tables/hierarchical_performance.csv`."
- **Audit Investigation:**
  1. The file `results/tables/hierarchical_performance.csv` **does not exist** on disk (`Test-Path` returned `False`).
  2. The actual preserved table measuring hierarchical architectures is [`results/tables/flat_vs_hierarchical.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/flat_vs_hierarchical.csv), which reports:
     - `Hierarchical 2-Stage Classifier (Unfiltered)`: Macro-F1 = **$0.0686$**, Accuracy = **$0.1626$**.
     - `Hierarchical Selective Prediction (Gated)`: Macro-F1 = **$0.0000$** (rejected 100% of flows under $\tau \ge 0.60$).
  3. In [`results/tables/phase_progression_hierarchical.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/phase_progression_hierarchical.csv), Phase 8 (Hierarchical Routing) achieved Macro-F1 = **$0.0476$** and Accuracy = **$0.1667$**.
- **Audit Verdict:** **`CONTRADICTED`**. The claim of $0.9439$ coarse F1 was an ungrounded calculation with no supporting artifact.

### 4.2 The "87.1% Selective Accuracy at $\tau=0.70$" Discrepancy
- **Previous Statement:** "Setting selective threshold $\tau^* = 0.70$ achieves $87.1\%$ accuracy at $64.5\%$ coverage."
- **Audit Investigation:**
  1. In the authoritative table [`results/tables/research_selective_prediction.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/research_selective_prediction.csv) (line 10):
     - For `split = test` at `threshold = 0.7`:
       - `coverage`: **$0.5417$** ($54.2\%$, 26 accepted samples / 48 total).
       - `selective_accuracy`: **$0.7308$** ($73.08\%$).
       - `error_rate_accepted`: **$0.2692$** ($26.92\%$).
       - `selective_macro_f1`: **$0.6515$**.
  2. In [`results/tables/risk_coverage.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/risk_coverage.csv) (line 14), at `target_coverage = 0.65`, `empirical_risk = 0.8717` (error rate is $87.17\%$, precision is $0.1283$).
- **Audit Verdict:** **`CONTRADICTED`**. The previous report conflated empirical risk ($0.8717$) with accuracy, claiming $87.1\%$ accuracy. The true measured accuracy at $\tau=0.70$ is **$73.08\%$ at $54.2\%$ coverage**.

### 4.3 The "Split Illusion" Scientific Comparability Fallacy
- **Previous Statement:** "Random splitting yields $0.9500$ Macro-F1 while session-disjoint splitting yields $0.5854$, proving that random splitting inflates accuracy by $36\%$ on identical data."
- **Audit Investigation:**
  1. From [`results/tables/generalization_scorecard.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/generalization_scorecard.csv) and [`final_results_summary.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/final_results_summary.csv):
     - The $0.9500$ random split was evaluated on **`dataset_v1`** (a 12-flow Scapy synthetic loopback fixture; test set $N=5$).
     - The $0.5854$ session split was evaluated on **`dataset_v2`** (a 301-flow hybrid physical/perturbed dataset; test set $N=48$).
  2. The two evaluations did not use identical samples, identical data origins, or identical feature profiles.
- **Audit Verdict:** **`INVALID COMPARISON`**. Comparing synthetic loopback flows against multi-session hybrid physical traffic and attributing the entire performance drop to the splitting protocol is scientifically invalid. A rigorous split-illusion experiment must evaluate both splitting protocols on the exact same physical dataset.

---

## 5. Summary of Authoritative, Defensible Metrics

| Evaluation Regime | Model | Dataset ID | Test Set Size | True Accuracy | True Macro-F1 | Primary Source Artifact |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **Hybrid Session Split** | Random Forest | `dataset_v2` | 48 | **$0.5833$** | **$0.5854$** | `results/tables/research_baseline.csv` |
| **Hybrid Session Split** | Decision Tree | `dataset_v2` | 48 | **$0.5833$** | **$0.5802$** | `results/tables/research_baseline.csv` |
| **Hybrid Session Split** | LightGBM | `dataset_v2` | 48 | **$0.5417$** | **$0.5474$** | `results/tables/research_baseline.csv` |
| **Physical Session Split** | Random Forest | `dataset_real_v1`| 12 | **$0.0833$** | **$0.0833$** | `results/tables/real_baseline_error_analysis.csv` |
| **Selective Classification** | LightGBM ($\tau=0.70$)| `dataset_v2` | 26 accepted | **$0.7308$** | **$0.6515$** | `results/tables/research_selective_prediction.csv` |
| **Selective Classification** | LightGBM ($\tau=0.80$)| `dataset_v2` | 21 accepted | **$0.8571$** | **$0.8752$** | `results/tables/research_selective_prediction.csv` |
