# Phase 2: Real Data Machine Learning Baseline Benchmark Report

**Date**: 2026-08-23  
**Project**: Real-Time Encrypted Traffic Classification  
**Status**: Real Baseline Benchmark Established — **Leading Model Selected on Validation**  
**Primary Dataset**: `data/processed/features/features_real_clean.csv` (121 Clean Flows, 60 Sessions)

---

## 1. Objective
Establish the first rigorous machine learning baseline on the verified real-world traffic dataset following the completion of Phase 1.5 data cleaning. 

> [!IMPORTANT]
> **Historical Baseline Distinction**: This benchmark is evaluated exclusively on real-world traffic flows. Results are not directly comparable to prior synthetic/fixture experiments (which operated on synthetic network traces).

---

## 2. Dataset
- **Total Real Captures**: 60 controlled sessions (10 per class across 6 classes).
- **Total Clean Flows**: 121
- **Traffic Classes (6)**: File Transfer, Messaging, Other, Video, VoIP, Web
- **Protocol Distribution**: 96.3% UDP (QUIC HTTP/3 and WireGuard WARP encapsulation).

---

## 3. Cleaning
- Excluded 68 non-application noise/broadcast flows (SSDP, LLMNR, mDNS, NetBIOS).
- Zero packet payload inspected; exclusions strictly based on broadcast port and multi-class signature frequency.
- Preserved complete original dataset in `flows_real_all.csv` and clean subset in `flows_real_clean.csv`.

---

## 4. Split Methodology
- **Grouping Unit**: `session_id` (ensuring 0 intra-session data leakage).
- **Split Ratio**: 70% Train / 15% Validation / 15% Test (Seed = 42).
- **Train**: 85 flows across 42 sessions.
- **Validation**: 24 flows across 12 sessions.
- **Test**: 12 flows across 6 sessions.
- **Session Overlap Count**: **0** (verified in `results/tables/real_split_integrity.csv`).

---

## 5. Feature Schema
- **ML Feature Count**: 21 features.
- **Included Groups**: Flow Duration, Forward/Backward/Total Packet Counts, Forward/Backward/Total Byte Counts, Packet Size Statistics (Mean/Min/Max/Variance), Inter-Arrival Times (Mean/Median/Std/Min/Max), Packet/Byte Ratios, Burst Statistics (Count/Avg Bytes/Avg Packets).
- **Strictly Excluded**: `session_id`, `file_id`, `data_origin`, `environment_id`, `device_id`, timestamps, paths, and raw metadata.

---

## 6. Models
Four baseline classifiers evaluated:
1. **Logistic Regression** (L-BFGS / linear baseline)
2. **Decision Tree** (Gini impurity / depth=12)
3. **Random Forest** (100 estimators / max_depth=15)
4. **LightGBM** (GBDT / 100 estimators / lr=0.05)

---

## 7. Training Procedure
- `FeaturePreprocessor` fitted **strictly on the 85 training flows**.
- Numerical imputation medians, mean/variance normalizers, and class label encoders learned solely from training data.
- Zero test data leaked into preprocessor state (persisted to `results/models/real_baseline/preprocessor.joblib`).

---

## 8. Validation Procedure
Models were evaluated and ranked strictly on the **Validation Split Macro-F1** before touching the test partition:
- **Locked Leading Model**: `random_forest` (Validation Macro-F1: `0.2828`, Val Accuracy: `0.2917`)

---

## 9. Final Test Evaluation

| Model | Val Macro-F1 | Val Acc | Test Macro-F1 | Test Acc | Test W-F1 | Latency (ms) | Size (KB) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **logistic_regression** | 0.1032 | 0.2083 | 0.0606 | 0.1667 | 0.0606 | 0.0159 | 1.39 |
| **decision_tree** | 0.0833 | 0.1250 | 0.0556 | 0.0833 | 0.0556 | 0.0034 | 0.71 |
| **random_forest** **(Selected)** | 0.2828 | 0.2917 | 0.0833 | 0.0833 | 0.0833 | 0.0032 | 0.49 |
| **lightgbm** | 0.1226 | 0.1250 | 0.0667 | 0.0833 | 0.0667 | 0.0034 | 0.51 |


---

## 10. Per-Class Results for Selected Model (`random_forest`)

| Class | Precision | Recall | F1-Score | Support (Test Flows) |
| :--- | :---: | :---: | :---: | :---: |
| **File Transfer** | 0.0 | 0.0 | 0.0 | 2 |
| **Messaging** | 0.0 | 0.0 | 0.0 | 2 |
| **Other** | 0.5 | 0.5 | 0.5 | 2 |
| **Video** | 0.0 | 0.0 | 0.0 | 2 |
| **VoIP** | 0.0 | 0.0 | 0.0 | 2 |
| **Web** | 0.0 | 0.0 | 0.0 | 2 |


---

## 11. Inference Cost
- **Single-Flow Latency**: `0.0159ms` (evaluated over 500 benchmark passes)
- **Batch Latency**: `0.0164ms per flow`
- **Memory Footprint**: `~2.0 MB` RAM footprint
- **Artifact Size**: All 4 models serialized to disk under `< 250 KB`.

---

## 12. Error Analysis
- **Total Test Flow Count**: 12 flows (held-out from 6 independent sessions).
- **Key Confusion Observations**:
  - Web, Video, Messaging, and VoIP traffic exhibit similar encrypted packet burst structures over WireGuard/QUIC tunnels.
  - Baseline un-tuned tree models without feature selection struggle to separate subtle inter-arrival time differences across tunnel encapsulations.
  - Detailed error logs recorded in `results/tables/real_baseline_error_analysis.csv`.

---

## 13. Limitations
1. **Small Test-Set Size**: The held-out test partition comprises 12 flows from 6 sessions.
2. **Bootstrap 95% Confidence Interval**:
   - Macro-F1: `0.0742` (95% CI: `[0.0000, 0.1667]`)
   - Accuracy: `0.0932` (95% CI: `[0.0000, 0.2500]`)
   - *EXPLORATORY ONLY — NOT RELIABLE FOR STRONG INFERENCE (Test N=12)*.
3. **Tunnel Confounding**: All sessions were captured over WireGuard/WARP tunnel framing, homogenizing transport protocols to UDP.
