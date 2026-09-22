# Phase 3: Real Data Feature Discovery, Grouped Cross-Validation, and Model Optimization Report

**Date**: 2026-08-23  
**Project**: Real-Time Encrypted Traffic Classification  
**Status**: Feature Discovery & Grouped CV Optimization Completed  
**Primary Dataset**: `data/processed/features/features_real_clean.csv` (121 Clean Flows across 60 Sessions)  

---

## 1. Baseline Problem
In Phase 2, the un-tuned real baseline benchmark yielded low held-out test performance (Macro-F1 = 0.0833, Accuracy = 0.0833 across 12 test flows). 

Phase 3 was executed to determine whether:
1. The low baseline score was an artifact of high variance on the small 12-flow test set.
2. Un-selected 21-feature representations suffered from redundancy or noise under WireGuard/WARP UDP tunnel encapsulation.
3. Grouped cross-validation across 54 independent sessions could identify stable, lightweight feature representations.

---

## 2. Grouped CV Methodology
To prevent session data leakage while maximizing statistical power on development data:
- **Combined Development Partition**: 109 flows across 54 independent sessions (85 Train + 24 Validation).
- **Group Splitting Key**: `session_id` (Zero session overlap across any CV fold).
- **5-Fold Grouped CV**: Evaluated across 5 folds with fold-local preprocessing and feature selection.

---

## 3. Feature Discovery
Statistical profiling across all 21 zero-payload features revealed:
- **High Correlation Redundancies**: Forward/backward packet counts and byte volumes exhibit Pearson correlations $> 0.92$.
- **Near-Zero Variance**: Under tunnel encapsulation, `max_packet_size` and `protocol` exhibit near-zero discriminative variance.
- **Top Consensus Features**: avg_packet_size, burst_count, max_iat, min_packet_size, forward_packet_count.

---

## 4. Feature Reduction
Controlled feature subset evaluation (K in (21, 15, 10, 7, 5, 3)) demonstrated that reducing features from 21 down to 10 maintains developmental cross-validation stability while cutting feature extraction latency by ~52%.

---

## 5. Model Optimization
Hyperparameter grid searches conducted via 5-fold grouped CV identified that shallow tree depth ($max\_depth = 3$) and regularized ensembles mitigate overfitting to individual session artifacts.

---

## 6. Stability
Multi-seed grouped CV across seeds `[42, 123, 2024, 3407, 7777]` yielded:
- **Mean Grouped CV Macro-F1**: `0.1642`
- **Standard Deviation**: `0.0570`

---

## 7. Calibration
Probability calibration analysis on development out-of-fold predictions produced an **Expected Calibration Error (ECE)** of `0.7573`.

---

## 8. Early Prediction
Packet horizon evaluations ($N \in [5, 10, 20, 50]$) indicate that statistical properties stabilize rapidly within the first 15–20 packets.

---

## 9. Tunnel-Aware Observations
As documented in [`docs/tunnel_observation.md`](file:///c:/UROP%20project/encrypted-traffic-classification/docs/tunnel_observation.md), WireGuard UDP tunneling encapsulates inner protocols and normalizes MTU packet limits. Classification must rely on inter-arrival timing dynamics, bi-directional byte ratios, and burst counts.

---

## 10. Final Candidate
- **Selected Model**: `decision_tree`
- **Feature Count**: 10 features (`avg_packet_size, burst_count, max_iat, min_packet_size, forward_packet_count...`)
- **Development Grouped CV Macro-F1**: `0.1642` (+/- `0.0570`)

---

## 11. One-Time Held-Out Test Evaluation
Evaluated strictly ONCE on `data/processed/splits/real_clean/test.csv` (12 flows / 6 sessions):
- **Final Test Accuracy**: `0.2500`
- **Final Test Macro-F1**: `0.2056`
- **Single-Flow Latency**: `0.0026 ms`
- **Model Size**: `0.43 KB`

---

## 12. Comparison to Baseline

| Metric | Real Baseline v1 (Phase 2) | Real Optimized Candidate (Phase 3) |
| :--- | :---: | :---: |
| **Model Architecture** | Random Forest (21 features) | Random Forest (10 features) |
| **Selection Method** | Single Validation Split | 5-Fold Grouped CV (54 sessions) |
| **Dev CV Macro-F1** | 0.2828 (Single Val) | 0.1642 (+/- 0.0570) |
| **Held-Out Test Macro-F1** | 0.0833 | 0.2056 |
| **Held-Out Test Accuracy** | 0.0833 | 0.2500 |
| **Single-Flow Latency** | 0.0032 ms | 0.0026 ms |
| **Model Storage Size** | 0.49 KB | 0.43 KB |

---

## 13. Limitations
1. **Small Held-Out Test Partition**: The fixed test set comprises 12 flows from 6 sessions ($N=12$), which produces wide confidence intervals and high discrete granularity.
2. **Tunnel Homogenization**: WireGuard UDP encapsulation compresses transport entropy across all interactive applications.
3. **Scientific Realism**: Pure zero-payload statistical classification in heavily encapsulated environments yields modest separability across fine-grained application classes.
