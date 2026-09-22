# PHASE 8 BASELINE & HISTORICAL ARTIFACT FREEZE MANIFEST

This document establishes the frozen historical reference hashes, configurations, and test results for Phases 2 through 7.
All Phase 8 hierarchical investigations are conducted on development data without modifying these historical records.

## 1. Frozen Results Ledger

| Phase | Description | Architecture / Features | Dev Macro-F1 | Held-Out Test Macro-F1 | Held-Out Test Accuracy | Primary Artifact Reference |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **Phase 2** | Real ML Baseline v1 | Random Forest (21 summary features) | 0.2828 (Val) | 0.0833 | 0.0833 | `results/real_baseline_report.md` |
| **Phase 3** | Feature Selection & Optimization | Decision Tree depth 5 (10 features) | 0.1642 ± 0.0570 | 0.2056 | 0.2500 | `results/real_optimization_report.md` |
| **Phase 4** | Dataset Expansion & Generalization | Decision Tree depth 5 (10 features) | 0.1467 ± 0.0496 | 0.1467 | 0.1529 | `results/generalization_report.md` |
| **Phase 5** | Rich Zero-Payload Features | Decision Tree depth 5 (30 rich features) | 0.1720 ± 0.0380 | 0.1074 | 0.2500 | `results/rich_feature_report.md` |
| **Phase 6** | Temporal Windowed Streaming | Decision Tree depth 5 (10-packet prefix) | 0.1934 ± 0.0480 | 0.0333 | 0.0833 | `results/temporal_classification_report.md` |
| **Phase 7** | Sequential Subflow Aggregation | Decision Tree depth 5 (193 seq features) | 0.1981 ± 0.0285 | 0.0606 | 0.1667 | `results/phase7_sequential_report.md` |

## 2. Dataset Split Freeze
- Total sessions: 150 (301 clean flows)
- Development set: 144 sessions (289 clean flows)
- Locked held-out test set: 6 sessions (12 clean flows) - `data/processed/splits/test_session_ids.json`
- Zero session overlap, zero parent flow overlap.

## 3. Scientific Purpose of Phase 8
1. Discover empirical coarse traffic clusters (e.g. Bulk/Streaming vs Interactive vs Background/Other) from zero-payload behavioral patterns.
2. Train Stage 1 Coarse Classifier and Stage 2 Fine Classifiers.
3. Formulate composed probabilistic confidence: $P(\text{fine} \mid \text{flow}) = P(\text{coarse} \mid \text{flow}) \times P(\text{fine} \mid \text{coarse}, \text{flow})$.
4. Evaluate selective prediction and reject low-confidence / unknown traffic.
5. Simulate open-set rejection capability via leave-one-class-out validation on dev flows.
