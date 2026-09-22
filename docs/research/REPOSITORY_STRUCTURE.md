# Repository Structure & File Governance Guide

**Repository:** Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models  
**Single Source of Truth Status:** ACTIVE  
**Last Cleaned & Audited:** September 2026  

---

## 1. Directory Tree Overview

The repository is strictly structured into authoritative source code, raw and processed data, experimental pipelines, reproducible results, and academic documentation:

```
encrypted-traffic-classification/
├── VERSION                         # Semantic version identifier (1.0.0)
├── CHANGELOG.md                   # Phase change history and release log
├── README.md                      # Primary research guide & executive summary
├── SECURITY.md                    # Zero-payload privacy & non-DPI policy
├── LICENSE                        # MIT License
├── requirements.txt               # Direct runtime & development dependencies
├── requirements-lock.txt          # Frozen dependency lockfile
├── config.yaml                    # Master project configuration (features, thresholds, models)
├── EncryptedTrafficDashboard.spec # PyInstaller build specification for Dashboard
├── EncryptedTrafficMonitor.spec   # PyInstaller build specification for Daemon
│
├── capture/                       # [SOURCE] Packet sniffing, live capture & PCAP parsing
├── flows/                         # [SOURCE] Bidirectional 5-tuple flow generator & state tracking
├── preprocessing/                 # [SOURCE] Feature extraction (21 statistical features) & scaling
├── models/                        # [SOURCE] Machine learning model architectures & fallbacks
├── training/                      # [SOURCE / EXPERIMENT] Model training, ranking, Pareto & split scripts
├── realtime/                      # [SOURCE] Async classification engine, worker queue, & EventBus
├── dashboard/                     # [SOURCE] Streamlit Cyber SOC Console & data adapters
├── product/                       # [SOURCE] Process supervision, packaging runtime, & health monitoring
├── installer/                     # [SOURCE] Windows packaging build script (build_windows.ps1)
│
├── data/                          # [DATASET] Raw captures, metadata, processed features & manifests
│   ├── dataset_manifest.csv       # Master provenance manifest of all capture sessions
│   ├── dataset_versions/          # Versioned dataset release bundles (v2 manifest & provenance)
│   ├── raw/                       # Raw capture data (pcap fixtures and per-packet metadata CSVs)
│   ├── processed/                 # Extracted flows, clean feature matrices, and locked splits
│   ├── external/                  # Public benchmark documentation & ingestion guides
│   └── local/                     # Local test vectors and dummy validation samples
│
├── experiments/                   # [EXPERIMENT] Traffic rate stress tests & robustness benchmarks
│   ├── realtime/                  # Real-time traffic rate throughput benchmarks
│   ├── robustness/                # Dataset perturbation and condition robustness suites
│   ├── lightweight_model/         # Model complexity comparison tables
│   └── real_generalization_v2.py  # Standalone generalization experiment runner
│
├── results/                       # [RESULTS] Empirical result tables, figures, reports & checkpoints
│   ├── tables/                    # CSV performance tables across all experimental phases
│   ├── figures/                   # Confusion matrices, ROC curves, and bar charts
│   ├── models/                    # Small serialized model checkpoints and preprocessors (.joblib)
│   ├── realtime/                  # Runtime prediction event logs and latency metrics
│   ├── baselines/                 # Phase-specific baseline checkpoints
│   └── *.md                       # Phase experimental reports and synthesis summaries
│
├── docs/                          # [DOCUMENTATION] Architecture, methodology, slides & academic paper
│   ├── research/                  # Authoritative research governance documents (Audit, Registry, Claims)
│   ├── paper/                     # Academic manuscript chapters (01_abstract.md, 11_results.md, etc.)
│   ├── presentation/              # Presentation slides (01_problem.md through 15_conclusion.md)
│   └── *.md                       # Supporting design, tunnel observation, and workflow notes
│
├── release/                       # [RELEASE] Lightweight distribution bundle (README, install guide)
│   ├── README.md                  # Release bundle overview
│   ├── WINDOWS_INSTALL.md         # Windows installation guide
│   └── reproducibility.md         # Master reproducibility cheat sheet
│
├── scripts/                       # [ENTRY POINTS] Operational, verification, and diagnostic CLI tools
└── tests/                         # [VERIFICATION] Unit, integration, smoke, and security test suite
```

---

## 2. Directory Categorization & Responsibilities

### A. Source Directories (`capture/`, `flows/`, `preprocessing/`, `models/`, `training/`, `realtime/`, `dashboard/`, `product/`)
- **Category:** Authoritative Source (Class A).
- **Rule:** Version-controlled Python code. Must remain clean of ad-hoc scripts, compiled binaries, or embedded data.
- **Components:**
  - `capture/`: Layer-2/3 packet ingress via Scapy/Npcap. Implements zero-payload inspection guarantee.
  - `flows/`: Flow aggregation based on 5-tuple `(src_ip, dst_ip, src_port, dst_port, protocol)` with idle and active timeout flushes.
  - `preprocessing/`: Computes statistical distributions (packet sizes, IAT, burst dynamics, forward/backward ratios). Implements `FeaturePreprocessor` for median imputation and standard scaling.
  - `models/`: Implementations of Logistic Regression, Decision Tree, Random Forest, LightGBM, and Hierarchical Classifiers with pure-Python fallbacks.
  - `training/`: All data loaders, split generators, feature selectors, model trainers, and evaluation pipelines.
  - `realtime/`: Worker queue decoupling packet capture from model inference; in-memory EventBus; local REST API.
  - `dashboard/`: Streamlit monitoring interface displaying real-time traffic distributions, latency percentiles, and alerts.
  - `product/`: Daemon supervision, runtime path resolution, and adapter validation.

### B. Dataset Directories (`data/`)
- **Category:** Large Raw Data (Class C) & Authoritative Manifests (Class A).
- **Rule:**
  - `data/dataset_manifest.csv` and `data/dataset_versions/` are **authoritative source manifests** tracking provenance and hashes.
  - `data/raw/` contains raw capture fixtures:
    - `data/raw/pcap/`: Small PCAP sample fixtures for unit and smoke tests.
    - `data/raw/metadata/`: 60 controlled Wi-Fi capture metadata CSV files (packet timestamps, lengths, and headers without payload).
  - `data/processed/` contains extracted flow records (`flows/`), tabular feature matrices (`features/`), and locked split subsets (`splits/`, `splits_session/`, `splits_temporal/`, `splits_capture/`).
  - Large binary PCAP dumps must never be committed to source control; they are excluded via `.gitignore`.

### C. Experiment Directories (`training/`, `experiments/`)
- **Category:** Authoritative Source & Experiment Runners.
- **Rule:** Every experiment runner must accept command-line arguments and reference immutable configuration files (`config.yaml`).
- **Organization:**
  - Standard training and ablation pipelines reside in `training/` (e.g., `real_ml_baseline.py`, `real_optimization_pipeline.py`, `rich_feature_pipeline.py`).
  - Benchmarks for network stress and rate limits reside in `experiments/` (e.g., `experiments/realtime/benchmark_traffic_rates.py`, `experiments/robustness/run.py`).

### D. Result Directories (`results/`)
- **Category:** Reproducible Generated Results (Class B).
- **Rule:** Contains small reproducible artifacts generated by experimental scripts:
  - `results/tables/`: Authoritative CSV metrics tables (e.g., `real_final_baseline_result.csv`, `real_optimized_final_test.csv`).
  - `results/figures/`: Confusion matrices, ROC curves, and feature importance bar plots.
  - `results/models/`: Serialized model checkpoints (`.joblib`) and `production_registry.json`. Total size is strictly budgeted (< 1 MB).
  - `results/*.md`: Detailed markdown reports synthesized at the completion of experimental phases.
  - `results/realtime/`: Local execution logs (`predictions.csv`, `live_metrics.csv`).

### E. Research Documentation (`docs/`, `README.md`)
- **Category:** Research Documentation (Class G).
- **Rule:** Peer-reviewed academic writing and governance records:
  - `docs/research/`: Contains foundational audit records:
    - `RESEARCH_AUDIT.md`: System audit, baseline state, contradictions, and risk register.
    - `EXPERIMENT_REGISTRY.md`: Single source of truth cataloging all synthetic and real experiments.
    - `CLAIMS_LEDGER.md`: Forensic audit of public claims against empirical data.
    - `DATASET_CARD.md`: Academic dataset card following Gebru et al. standard.
    - `REPOSITORY_STRUCTURE.md`: This file.
  - `docs/paper/`: Chapters of the formal academic manuscript.
  - `docs/presentation/`: 15 markdown slide decks summarizing contributions.

---

## 3. Generated & Excluded Artifacts Lifecycle

The following artifact classes are strictly excluded from source control via `.gitignore`:

| Artifact Class | Examples | Handling Policy |
| :--- | :--- | :--- |
| **PyInstaller Build Caches** | `build/`, `dist_build/`, `*.spec.bak` | Generated during packaging; automatically purged; ignored in `.gitignore`. |
| **Packaged Binaries** | `dist/`, `*.exe`, `*.dll`, `*.so` | Built on-demand using `installer/build_windows.ps1`; never committed. |
| **Recursive Archives** | `*.zip`, `*.tar.gz`, `UROP_source.zip` | Strictly forbidden. The repository must never contain a recursive zip copy of itself. |
| **Python Bytecode & Caches** | `**/__pycache__/`, `*.pyc`, `.pytest_cache/` | Automatically regenerated by Python interpreter and pytest; ignored in `.gitignore`. |
| **Runtime Diagnostic Logs** | `*.log`, `packaged_runtime.log` | Ephemeral runtime logs generated by test runs or daemons. |

---

## 4. Reproducibility Entry Points

All system diagnostics, verifications, and experimental workflows are triggered via standardized scripts:

### Diagnostic & Verification Entry Points
```powershell
# 1. Environment & Dependency Diagnostic
python scripts/check_environment.py

# 2. Model Artifact & Inference Verification
python scripts/verify_artifacts.py

# 3. Production Health Check (8 Subsystem Gates)
python scripts/production_health_check.py

# 4. Master Test Suite Execution
python -m pytest tests/ -q
```

### Experimental Pipeline Entry Points
```powershell
# Phase 2 Real Data ML Baseline
python -m training.real_ml_baseline

# Phase 3 Real Data Optimization & Feature Reduction
python -m training.real_optimization_pipeline

# Phase 5 Rich Feature Extraction & Evaluation
python -m training.rich_feature_pipeline

# Phase 6 Temporal Chronological Classification
python -m training.temporal_classification_pipeline

# Phase 7 Sequential Window Classification
python -m training.sequential_classification_pipeline

# Phase 8 Hierarchical & Selective Classification
python -m training.hierarchical_classification_pipeline
```

### Interactive Application Entry Points
```powershell
# Launch Streamlit SOC Dashboard Console
streamlit run dashboard/app.py

# Launch Real-Time Daemon in Demo Replay Mode
python -m realtime.run --demo
```
