# Changelog

All notable changes to the **Real-Time Encrypted Traffic Classification Using Lightweight ML Models** research project will be documented in this file.

## [1.0.0] - Phase 7: Final System Integration, Packaging & UROP Release - 2026-08-23
### Added
- Complete architecture documentation (`docs/final_architecture.md`), formal research question (`docs/research_question.md`), and objectives (`docs/research_objectives.md`).
- 15 academic manuscript chapters in `docs/paper/` and 15 presentation slides in `docs/presentation/`.
- Automated reproducibility tools: `scripts/check_environment.py`, `scripts/verify_artifacts.py`, `scripts/validate_research_claims.py`, and master orchestrator `scripts/reproduce.py`.
- End-to-end smoke test `tests/test_end_to_end.py`.
- Final experiment matrix and results summaries in `results/tables/final_experiment_matrix.csv` and `results/tables/final_results_summary.csv`.
- Lightweight release package bundle in `release/`.

## [0.6.0] - Phase 6: Dataset Expansion, Robustness & Generalization - 2026-08-23
### Added
- Dataset manifest metadata expansion and cryptographic SHA-256 manifest hashing.
- External dataset ingestion guide and canonical 6-class mapper (`training/class_mapping.py`).
- Chronological temporal, session-isolated, and capture-isolated splitting protocols.
- Robustness benchmarks: traffic load stress (1–100 Mbps), flow length variations, early-prediction observation windows ($N \in \{3, 5, 10, 20, 50\}$), and confidence calibration (ECE = 0.1170).
- Generalization scorecard and markdown research report (`results/generalization_report.md`).

## [0.5.0] - Phase 5: Lightweight Feature Selection & Model Optimization - 2026-08-23
### Added
- Multi-method feature ranking (Mutual Information, Random Forest, LightGBM, Permutation).
- Controlled feature reduction experiments ($K \in \{21, 15, 10, 5, 3\}$).
- Multi-objective Pareto frontier analysis and project-specific Lightweight Scoring.
- Real-time feature compute compatibility and extraction latency profiling.
- Final configuration locking (`LightGBM`, $K=10$) and single held-out test evaluation.

## [0.4.0] - Phase 4: Real-Time Classification Pipeline & SOC Dashboard - 2026-08-23
### Added
- Real-time bidirectional flow tracker with lifecycle states (`FLOW_STARTED`, `FLOW_UPDATED`, `FLOW_COMPLETED`, `FLOW_EXPIRED`).
- Online feature extractor with strict canonical schema validation (`validate_feature_schema`).
- Asynchronous classification engine with decoupled prediction worker queue.
- Rolling continuous metrics collector (throughput, p95 latency, CPU %, RAM MB).
- Streamlit Cybersecurity Monitoring SOC Console (`dashboard/app.py`).
- Deterministic offline Demo / Replay engine (`realtime/demo_mode.py`).

## [0.3.0] - Phase 3: ML Baseline Training & Benchmarking - 2026-08-23
### Added
- Implementations for Logistic Regression, Decision Tree, Random Forest, and LightGBM with pure-Python fallbacks.
- Multi-criteria model ranking, Pareto analysis, feature importance extraction, and error analysis.

## [0.2.0] - Phase 2: Dataset Preparation & Processing Pipeline - 2026-08-23
### Added
- PCAP-to-flow pipeline, feature extractor, dataset cleaner, and group-aware leakage-free splitting.

## [0.1.0] - Phase 1: Foundation Architecture - 2026-08-23
### Added
- Initial project structure, config schema, zero-payload packet reader, and flow generator.
