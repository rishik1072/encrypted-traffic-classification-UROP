# Research Audit & Scientific Integrity Report

**Repository:** Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models  
**Lead Research Engineer Audit Date:** September 2026  
**Audited Target Commit / Tree:** `v1.0.0` (Production & Academic Manuscript Workspace)  
**Standard:** Scientifically Rigorous, Reproducible, Research-Paper-Level Audit  

---

## 1. Executive Summary & Audit Mandate

This research audit systematically inspects the entire codebase, experimental pipelines, result tables, dataset manifests, documentation, and academic manuscripts in this repository. 

The primary research objective is:
> *"Evaluate how accurately, efficiently, and robustly encrypted network traffic can be classified in real time using lightweight zero-payload statistical features under realistic network variability."*

### Key Audit Finding
The repository exhibits a **two-tier reality**:
1. **Tier 1 (Historical Synthetic Baseline):** A polished, self-consistent demonstration built on synthetic traffic (`dataset_v1`, 12 synthetic flows) reporting headline figures: **0.9500 Macro-F1**, **0.9000 Capture Generalization**, **0.8800 Session Generalization**, **0.8400 Temporal Generalization**, and **0.8800 Early Prediction at N=5**.
2. **Tier 2 (Empirical Real Traffic Ingestion):** An evolving real-world research pipeline (`dataset_real_v1` and `dataset_v2`) where empirical results diverge starkly: on real encrypted traffic under group-aware splitting, real test performance collapsed to **0.0833 Macro-F1** (baseline random forest) and **0.2056 Macro-F1** (optimized decision tree K=10) on a test partition of only **12 flows across 6 sessions**.

Headline claims in the `README.md`, `docs/paper/01_abstract.md`, and `docs/paper/11_results.md` are currently based **exclusively on Tier 1 synthetic data**, while presenting these metrics as empirical properties of real encrypted network traffic. Furthermore, critical documentation artifacts (such as 12 missing paper chapters and an empty literature review) and test/pipeline execution bugs were discovered.

This document establishes the single source of truth, details all contradictions, categorizes stale artifacts, and outlines the precise phased upgrade sequence required to bring this project to a peer-reviewed publication standard.

---

## 2. Current Architecture

The repository implements a modular, end-to-end real-time traffic classification system spanning seven functional layers:

```
[ LIVE NETWORK STREAM / DEMO REPLAY ]
                 │
                 ▼
     [ capture/packet_capture.py ]
                 │ (RawPacketMetadata: IP, Port, Proto, Length, Timestamp)
                 ▼
     [ realtime/flow_tracker.py ]
                 │ (Active 5-Tuple Window, Timeouts & Early Triggers)
                 ▼
  [ preprocessing/feature_extractor.py ]
                 │ (Zero-Payload Statistical Distributions: K in {21, 15, 10, 5, 3})
                 ▼
  [ preprocessing/preprocessing.py ]
                 │ (Missing value median imputation & Standard scaling)
                 ▼
     [ models/<model>.py ]
                 │ (LightGBM / Decision Tree / Random Forest / Logistic Regression)
                 ▼
     [ realtime/classifier.py ]
                 │ (Asynchronous Decoupled Worker Queue & Confidence Thresholding)
                 ▼
       [ realtime/events.py ]
                 │ (TrafficPredictionEvent on in-memory EventBus / API Service)
                 ├──▶ Persistence: results/realtime/predictions.csv & .jsonl
                 ▼
      [ dashboard/app.py ]
                 │ (Streamlit Cybersecurity SOC Monitoring Console)
```

### Component Breakdown

1. **`capture/` (`packet_capture.py`, `live_sniff.py`):**
   - Ingests packets via Scapy or Npcap.
   - Extracts `RawPacketMetadata`: timestamp, source IP, destination IP, source port, destination port, protocol, packet wire length.
   - **Privacy Invariant:** Application payload bytes are discarded immediately upon packet reception. No payload decryption, TLS MITM, or deep packet inspection is performed.

2. **`flows/` (`flow_generator.py`):**
   - Aggregates packets into bidirectional network flows keyed by standard 5-tuple: `(src_ip, dst_ip, src_port, dst_port, protocol)`.
   - Flow termination governed by `idle_timeout_seconds: 60.0` and `active_timeout_seconds: 1800.0`.

3. **`preprocessing/` (`feature_extractor.py`, `preprocessing.py`):**
   - `feature_extractor.py` computes Layer-3/4 statistical features: duration, packet counts, byte counts, sizes (mean, min, max, variance), inter-arrival times (IAT mean, median, std, min, max), forward/backward ratios, and burst dynamics.
   - `preprocessing.py` (`FeaturePreprocessor`): Fits median imputer for numerical missing values and `StandardScaler` strictly on training data; encodes target class labels.

4. **`models/` (`base_model.py`, `decision_tree.py`, `random_forest.py`, `logistic_regression.py`, `lightgbm_model.py`, `hierarchical_classifier.py`):**
   - Standardized wrapper interface inheriting from `BaseTrafficClassifier`.
   - Pure-Python fallback implementations provided when native C-libraries (`lightgbm`, `scikit-learn`) are unavailable.

5. **`training/` (58 modular scripts):**
   - Pipeline iterations spanning:
     - Synthetic v1: `pipeline.py`, `ml_pipeline.py`, `optimization_pipeline.py`.
     - Phase 2 Real Baseline: `real_ml_baseline.py`.
     - Phase 3 Real Optimization: `real_optimization_pipeline.py`.
     - Phase 5 Rich Features: `rich_feature_pipeline.py` (103 features).
     - Phase 6 Temporal: `temporal_classification_pipeline.py`.
     - Phase 7 Sequential: `sequential_classification_pipeline.py` (193 features).
     - Phase 8 Hierarchical & Selective Classification: `hierarchical_classification_pipeline.py`.

6. **`realtime/` (`classifier.py`, `flow_tracker.py`, `events.py`, `event_bus.py`, `demo_mode.py`, `api_service.py`):**
   - Multi-threaded classification queue decoupling packet ingress from model inference.
   - FastAPI local service serving predictions to the UI or downstream SIEM/SOC systems.

7. **`dashboard/` (`app.py`, `live_feed.py`, `data_adapter.py`, `schema.py`):**
   - Streamlit-based Cybersecurity SOC Console monitoring active flow categories, latency percentiles, and alerts.

8. **`product/` (`lifecycle.py`, `dashboard_launcher.py`, `adapters.py`, `runtime_paths.py`, `health.py`, `privacy.py`):**
   - Windows executable supervision, adapter discovery, and background daemon health monitoring.

---

## 3. Current Dataset Versions & Provenance

The repository contains three distinct dataset lineages:

| Dataset Identifier | Nature | Storage Location | Session Count | Flow Count | Provenance & Validation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`dataset_v1`** | Synthetic Fixture | `data/raw/pcap/` (12 sample PCAPs) | 12 | 12 (10-120 pkts) | Scapy-generated synthetic packets with deterministic sizing. Clean, balanced, linearly separable. |
| **`dataset_real_v1`** | Real Wi-Fi Capture Metadata | `data/raw/metadata/` (60 CSV files) | 60 | ~70 valid | Controlled Windows 11 Wi-Fi captures from 2026-08-23. Captured as packet metadata CSVs, not raw PCAPs. |
| **`dataset_v2`** | Multi-Condition Real Metadata | `data/dataset_versions/v2/` | 150 | 301 clean | Controlled captures across Wi-Fi, Ethernet, Cellular; Cloudflare WARP tunnel; simulated impairments. |

### Feature Dataset Derivatives (`data/processed/features/`)
- `features.csv` / `features_cleaned.csv`: 12 rows (derived from `dataset_v1` synthetic PCAPs).
- `features_real.csv` / `features_real_all.csv`: 70 rows (derived from `dataset_real_v1`).
- `features_real_clean.csv`: 48 rows (Phase 2 real baseline after quality filtering).
- `features_real_v2.csv` / `features_real_clean_v2.csv`: 301 rows (Phase 3/4/6/8 clean dataset).
- `features_real_rich_clean_v2.csv`: 301 rows x 103 columns (Phase 5 rich feature engineering).

---

## 4. Current Model Configurations

| Context / Pipeline | Primary Selected Model | Feature Dimension ($K$) | Target Classes | Empirical Macro-F1 Reported | Test Sample Size ($N$) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Synthetic Baseline (README/Paper)** | LightGBM | $K=10$ | 6 classes | **0.9500** | 12 (Synthetic) |
| **Phase 2 Real Baseline** | Random Forest | $K=21$ | 6 classes | **0.0833** | 12 (Real) |
| **Phase 3 Real Optimized** | Decision Tree | $K=10$ | 6 classes | **0.2056** | 12 (Real) |
| **Phase 5 Rich Features** | Decision Tree | $K=30$ | 6 classes | **0.1074** | 12 (Real) |
| **Phase 7 Sequential** | Decision Tree | $K=193$ | 6 classes | **0.0606** | 12 (Real) |
| **Phase 8 Hierarchical** | Hierarchical Decision Tree | Stage 1: 3 families; Stage 2: 6 classes | 6 classes | Unfiltered: **0.0476**<br>Selective: **0.9500*** | 12 (Real)<br>*(Coverage = 0.0%)* |

*\*Note on Phase 8 Selective F1:* The reported 0.9500 Macro-F1 in `results/tables/phase8_final_test.csv` occurred because the selective prediction policy abstained on 100% of test samples (`accepted_coverage: 0.0`).

---

## 5. Current Test Status

A comprehensive test execution of the entire test suite was performed using `pytest`:
- **Total Test Files in `tests/`:** 41 files
- **Total Discovered Test Cases:** 160 tests
- **Tests Passing:** 157 / 160 (98.1%)
- **Tests Failing:** 3 / 160 (1.9%)

### Detailed Analysis of the 3 Test Failures

1. **`tests/test_hierarchical_classification_pipeline.py::test_end_to_end_hierarchical_pipeline`**
   - **Error:** `ValueError: Expected 2D array, got 1D array instead: array=[]`
   - **Root Cause:** In `HierarchicalClassificationPipeline`, during stage-2 sub-model evaluation on small test fixtures, classes with zero samples in a group produce an empty slice (`[]`), causing `sklearn.utils.validation.check_array` to raise an exception.

2. **`tests/test_real_optimization_pipeline.py::test_end_to_end_optimization_pipeline`**
   - **Error:** `ValueError: X has 15 features, but LogisticRegression is expecting 7 features as input.`
   - **Root Cause:** In `training/real_optimization_pipeline.py` (line 812), `benchmark_model_latency()` is called with a feature vector from a 15-feature subset, but the `LogisticRegression` instance passed was fitted on the baseline 7-feature schema.

3. **`tests/test_rich_feature_pipeline.py::test_end_to_end_rich_pipeline`**
   - **Error:** `TypeError: DecisionTreeClassifier.__init__() got an unexpected keyword argument 'C'`
   - **Root Cause:** In `training/rich_feature_pipeline.py` (line 665), hyperparameter dictionaries are shared across model architectures; regularization parameter `'C'` from `LogisticRegression` was mistakenly passed into `DecisionTreeClassifier`.

---

## 6. Current Reproducibility Status

- **Master Reproduction Script (`scripts/reproduce.py`):** Runs stages 1 through 5, reproducing the **synthetic** experiments (`training.pipeline`, `training.ml_pipeline`, `training.optimization_pipeline`). It does not reproduce the real-data pipeline.
- **Master Verification Script (`scripts/reproduce_final.py`):** Verifies diagnostic health and attempts unit test execution, but hardcodes an outdated expectation of "76 Tests".
- **Claim Validator (`scripts/validate_research_claims.py`):** Hardcoded to check that `results/tables/final_results_summary.csv` matches `[0.95, 0.90, 0.88, 0.84, 0.88]`. It enforces the synthetic metrics as pass/fail criteria.
- **`results/reproducibility_manifest.json`:** Explicitly references `dataset_v1` and models trained on synthetic fixtures from August 2026.

---

## 7. Inconsistencies & Contradictions Found

| # | Conflict Area | Documented / Claimed | Actual Empirical State in Repo | Severity |
| :--- | :--- | :--- | :--- | :--- |
| **C1** | **Headline Performance Metrics** | `README.md` & `docs/paper/01_abstract.md` claim 0.9500 Macro-F1 on real encrypted traffic. | 0.9500 was achieved exclusively on 12 synthetic flows (`dataset_v1`). Real traffic Macro-F1 ranges from **0.0833 to 0.2056**. | **CRITICAL** |
| **C2** | **Raw PCAP Filenames vs Manifest** | `data/dataset_manifest.csv` points to `data/raw/pcap/web_001.pcap`, `video_001.pcap`, etc. | Files on disk in `data/raw/pcap/` are named `web_sample_01.pcap`, `video_sample_01.pcap`, etc. | **HIGH** |
| **C3** | **Test Suite Counts** | `README.md` claims "27 / 27 Tests Passing". `reproduce_final.py` claims "76 Tests". | `tests/` contains 41 test files with **160 tests** (157 passing, 3 failing). `final_test_matrix.csv` has only 10 rows. | **HIGH** |
| **C4** | **Missing Paper Chapters** | `README.md` states: *"Full Paper Chapters: docs/paper/ (01_abstract.md through 15_references.md)"*. | `docs/paper/` contains only 3 files: `01_abstract.md`, `11_results.md`, and `14_conclusion.md`. 12 chapters are missing. | **HIGH** |
| **C5** | **Empty Literature Review** | Repository structure lists `docs/literature_review/`. | The directory `docs/literature_review/` is completely empty. | **MEDIUM** |
| **C6** | **Empty Experiment Directories** | Directories `experiments/model_comparison/`, `experiments/feature_reduction/`, `experiments/latency/`. | Directories are completely empty. Experiments were implemented as scripts in `training/`. | **MEDIUM** |
| **C7** | **Test Sample Starvation** | Final evaluation tables claim rigorous generalization assessment. | Real test sets (`real_final_baseline_result.csv`, `real_optimized_final_test.csv`) contain only **12 samples (6 sessions)** — exactly 2 samples per class. | **CRITICAL** |
| **C8** | **Abstention Trickery** | `phase8_final_test.csv` claims 0.9500 Selective Macro-F1. | `accepted_coverage` is 0.0 (the model abstained on 100% of samples, rendering precision trivially undefined/1.0). | **CRITICAL** |

---

## 8. Stale & Generated Artifacts Inventory

The following artifacts represent historical, synthetic, or unverified outputs and must be quarantined or designated as `STALE / UNVERIFIED`:

1. **Synthetic Result Tables (Quarantine / Mark STALE):**
   - `results/tables/final_results_summary.csv`
   - `results/tables/model_comparison.csv`
   - `results/tables/feature_reduction_performance.csv`
   - `results/tables/generalization_scorecard.csv`
   - `results/tables/final_configuration.csv`
   - `results/tables/final_test_matrix.csv`
   - `results/tables/final_experiment_matrix.csv`
   - `results/tables/calibration_results.csv`
   - `results/tables/early_prediction_robustness.csv`
   - `results/tables/traffic_volume_robustness.csv`
2. **Synthetic Models in Root:**
   - `results/models/lightgbm.joblib`
   - `results/models/preprocessor.joblib`
   - `results/models/baseline/`
   - `results/models/lightweight_10/`
3. **Outdated Reports:**
   - `results/final_research_report.md` (conflates synthetic 0.9500 with real-world capability).
   - `results/generalization_report.md` (synthetic splits).
   - `results/lightweight_optimization_report.md` (synthetic Pareto curves).

---

## 9. Research Risks & Scientific Vulnerabilities

1. **Generalization Collapse Under Tunneling:** Real-world traffic captured through Cloudflare WARP / WireGuard encapsulates Layer-4 packets into standardized UDP frames with fixed MTU and padded buffers. This eliminates standard packet-length discriminators, causing flat tree classifiers to fail (Macro-F1 ~0.08–0.20).
2. **Statistical Insignificance of Evaluation Sets:** Evaluating 6 classes on 12 test flows means a single misclassification changes Macro-F1 by ~16.7 percentage points. A credible benchmark requires $N \ge 100$ independent sessions per class in the held-out test set.
3. **Topological and Identifier Leakage:** Ensuring no port numbers (`dst_port`), IP subnets, or session timestamps inadvertently serve as classification shortcuts.
4. **Validation Contamination:** Ensuring that feature selection (ranking, Pareto optimization) and selective prediction threshold tuning are strictly performed on training/validation folds, never touching the locked test partition.

---

## 10. Single Source of Truth Policy

To guarantee academic rigor and peer-review acceptance, this repository strictly adheres to the following principles:

1. **Explicit Provenance:** Every dataset, split, and feature file must trace to a verified manifest with SHA-256 content hashes.
2. **Universal Experiment Tracking:** Every experiment must be cataloged in `docs/research/EXPERIMENT_REGISTRY.md` with an immutable Experiment ID.
3. **Strict Partition Locking:**
   - **Training Data:** Model parameter optimization.
   - **Validation Data:** Model selection, hyperparameter tuning, feature subset selection, and threshold calibration.
   - **Held-Out Test Data:** Locked until final evaluation. Test data must never influence model selection.
4. **Group-Aware Leakage Prevention:** Data splits must group by `session_id` and capture day/environment to eliminate temporal and session leakage.
5. **No Result Fabrication or Silent Substitution:** If a historical result cannot be reproduced from real data, it is formally labeled `UNVERIFIED` or `STALE` in `docs/research/CLAIMS_LEDGER.md`.
6. **Zero Payload Invariant:** Payload inspection, decryption, and DPI are strictly forbidden. The system operates purely on Layer-3/4 metadata and statistical distributions.

---

## 11. Recommended Upgrade Sequence

```
Phase 1: Research Audit & Single Source of Truth [COMPLETED]
         │ (Deliverables: RESEARCH_AUDIT.md, EXPERIMENT_REGISTRY.md, CLAIMS_LEDGER.md, DATASET_CARD.md)
         ▼
Phase 2: Test Suite & Pipeline Bugfixes
         │ (Fix scikit-learn dimension mismatch, parameter passing, and empty-slice array validation)
         ▼
Phase 3: Dataset Ingestion & Rigorous Partitioning
         │ (Reconcile manifests, expand real flow counts, establish locked group-aware splits with N >= 50/class)
         ▼
Phase 4: Tunnel-Resistant Feature Engineering
         │ (Develop burst dynamics, directional IAT, and timing entropy robust to WireGuard/WARP encapsulation)
         ▼
Phase 5: Fair Model Benchmarking & Pareto Optimization
         │ (Evaluate LR, DT, RF, LightGBM, and lightweight neural baselines with CV on validation sets)
         ▼
Phase 6: Multi-Regime Generalization & Early Prediction
         │ (Test across unseen sessions, unseen days, and packets N in {3, 5, 10, 20})
         ▼
Phase 7: Real-Time Latency & SOC Dashboard Verification
         │ (Profile end-to-end single-flow inference latency and test live Streamlit feed)
         ▼
Phase 8: Academic Paper Manuscript & Claims Reconciliation
         │ (Draft 15 complete paper chapters based strictly on verified empirical evidence)
```
