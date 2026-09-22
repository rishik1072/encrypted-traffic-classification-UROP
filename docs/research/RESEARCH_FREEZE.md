# Authoritative Research Freeze Declaration

**Repository:** Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models  
**Status:** FROZEN (No further tuning, retraining, feature changes, or data modifications permitted)  
**Freeze Date:** September 22, 2026  
**Operating System:** Microsoft Windows 11 Enterprise (Build 10.0.26200 x64)  
**Python Runtime:** Python 3.14.7 AMD64  
**Codebase Version / Git Commit:** `0dea637199`  

---

## 1. Frozen Dataset Specification

The authoritative empirical conclusions of this project are strictly anchored to the following dataset:

| Attribute | Frozen Value |
| :--- | :--- |
| **Dataset Identifier** | `dataset_v2` |
| **Dataset Version** | `2.0.0` |
| **Data Origin Classification** | `REAL_DATA` (Physical Wi-Fi, Ethernet, Cellular LTE) |
| **Total Valid Flows** | 301 bidirectional flows |
| **Total Independent Sessions** | 150 user sessions |
| **Class Balance** | 6 balanced classes (Web: 50, Video: 50, Messaging: 50, VoIP: 50, File Transfer: 50, Other: 51) |
| **Primary Features File** | `data/processed/features/features_real_clean_v2.csv` |
| **Primary Flows File** | `data/processed/flows/flows_real_clean.csv` |
| **Cryptographic Hash (SHA-256)** | `cd3193ecdd2ecb4859ba6b23bb75153571e205930f05fa2dc7323fcfc1a2c16d` |

*Synthetic fixtures (`dataset_v1`, 12 flows) and streaming replay vectors (`demo_data`, 20 flows) are strictly segregated and frozen as non-authoritative reference fixtures.*

---

## 2. Frozen Feature Registry & Profiles

| Feature Profile | Feature Count ($K$) | Defining Scope | Status |
| :--- | :---: | :--- | :--- |
| **Canonical Registry** | 84 | Complete 7-family Layer-3/4 transport feature definitions in `preprocessing/feature_registry.py` | **FROZEN** |
| **Baseline Profile** | 21 | `baseline_21_zero_payload`: Core statistical moments, bidirectional counts, and burst dynamics | **FROZEN** |
| **Lightweight Profile** | 10 | `profile_10_features`: Pareto-optimal edge profile (`fwd_packet_count`, `bwd_packet_count`, `total_bytes`, `avg_packet_size`, `max_packet_size`, `mean_iat`, `fwd_bwd_byte_ratio`, `fwd_bwd_packet_ratio`, `packet_ratio`, `packets_per_sec`) | **FROZEN** |
| **Ultra-Lightweight** | 3 | `top_3_features`: Minimum-compute profile (`packet_ratio`, `byte_ratio`, `fwd_packet_count`) | **FROZEN** |

- **Feature Schema Hash (SHA-256):** `9178786dc46dba8800c66b551c3ebcf78034f357f53405bf6b2ed70b40d88101`

---

## 3. Frozen Model Weights & Serialized Artifacts

The following models are registered in `results/models/production_registry.json` and frozen on disk:

| Model Architecture | Model Identifier | Serialized File Path | Serialized File SHA-256 |
| :--- | :--- | :--- | :--- |
| **LightGBM** | `model_lightgbm_v1` | `results/models/lightgbm.joblib` | `a5a65da6d74e9b3e61e654ac6a81066aaf2b247996b8364d6d71d826023c08cd` |
| **Decision Tree** | `model_decision_tree_v1` | `results/models/decision_tree.joblib` | `31a7f1f2d84b25681005442c70d38c54a061d661499f4a2500b4afa72f4b7a80` |
| **Random Forest** | `model_random_forest_v1` | `results/models/random_forest.joblib` | `9440e23ce67f94cef07ef0d779568e50faba23b4ada61ac91573bf77dd4d6ad9` |
| **Logistic Regression** | `model_logistic_regression_v1`| `results/models/logistic_regression.joblib` | `b7fd88252cca3fbd114551023fde33e2de00df9f82446b91a458f179a1bb2472` |
| **Feature Preprocessor**| `preprocessor_v1` | `results/models/preprocessor.joblib` | `a4b16727401d19417572f97d7b66656adf2f9d1964a53bf5eefcca8c35351e21` |

---

## 4. Frozen Experimental Protocols & Parameters

- **Partitioning Protocol:** Group-aware stratified session isolation (70% Train, 15% Validation, 15% Locked Test).
  - Train Split: 205 flows across 102 independent sessions.
  - Validation Split: 48 flows across 24 independent sessions.
  - Locked Test Split: 48 flows across 24 independent sessions.
- **Pseudo-Random Seed:** `seed = 42` (Deterministic across all splitting, cross-validation, and tree-sampling).
- **Early Prediction Horizons:** Frozen to $N \in \{3, 5, 10, 20, 30, 50, \text{full}\}$.
- **Selective Classification Threshold:** Frozen to validation-selected $\tau^* = 0.70$.

---

## 5. Frozen Authoritative Experiment Registry

| Experiment ID | Experiment Name | Protocol Document | Primary Output Table |
| :--- | :--- | :--- | :--- |
| **EXP-R09** | In-Domain Baseline Benchmark | `docs/research/BASELINE_PROTOCOL.md` | `results/final/baseline_results.csv` |
| **EXP-R10** | Feature Ablation & Reduction | `docs/research/FEATURE_ENGINEERING.md` | `results/final/feature_ablation.csv` |
| **EXP-R11** | Domain-Shift Generalization | `docs/research/GENERALIZATION_PROTOCOL.md` | `results/final/generalization.csv` |
| **EXP-R12** | Early Encrypted-Traffic Classification | `docs/research/EARLY_PREDICTION_PROTOCOL.md` | `results/final/early_prediction.csv` |
| **EXP-R13** | Selective Classification & Calibration | `docs/research/SELECTIVE_CLASSIFICATION_PROTOCOL.md` | `results/final/selective_prediction.csv` |
| **EXP-R14** | Computational Efficiency Benchmark | `docs/research/LIGHTWEIGHT_EFFICIENCY.md` | `results/final/latency.csv` |
| **EXP-R15** | Real-Time Streaming Pipeline Validation | `docs/research/REALTIME_VALIDATION.md` | `results/tables/realtime_research_validation.csv`|

---

## 6. Authoritative Frozen Artifacts

### Final Results Package (`results/final/`):
1. `dataset_summary.csv`
2. `baseline_results.csv`
3. `feature_ablation.csv`
4. `model_comparison.csv`
5. `generalization.csv`
6. `early_prediction.csv`
7. `selective_prediction.csv`
8. `calibration.csv`
9. `latency.csv`
10. `resource_usage.csv`
11. `final_metrics.csv`
12. `FINAL_RESULTS.md`

### Scientific Manuscript (`docs/paper/`):
- `01_abstract.md` through `15_references.md` (15 chapters)
- `INDEX_FIGURES_TABLES.md` (Master catalog of 12 tables and 22 figures)

### Single Source of Truth Provenance:
- `results/research_manifest.json`
- `docs/research/CLAIMS_LEDGER.md`
- `docs/research/FINAL_RESEARCH_STATUS.md`

---

## 7. Freeze Invariants & Guarantee

No further modifications, parameter tuning, weight retraining, or metric adjustments are permitted. The research record is permanently frozen.
