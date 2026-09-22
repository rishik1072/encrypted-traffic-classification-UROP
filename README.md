# Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status: Released](https://img.shields.io/badge/Release-v1.0.0-brightgreen.svg)](release/README.md)
[![Zero-Payload Privacy](https://img.shields.io/badge/Privacy-Zero--Payload%20Non--DPI-success.svg)](SECURITY.md)

A production-quality, fully reproducible research repository for classifying encrypted network traffic in real time **without decrypting packet payloads** or performing Deep Packet Inspection (DPI).

---

## 📌 Executive Summary & Headline Measurements

The system operates strictly on Layer-3/4 transport headers, packet length distributions, and inter-arrival timing dynamics to classify sessions into 6 canonical categories: **Web, Video, Messaging, VoIP, File Transfer, Other**.

| Metric | Measured Empirical Value | Reference |
| :--- | :--- | :--- |
| **Locked Model Configuration** | **LightGBM** ($K=10$ Features) | [final_configuration.csv](results/tables/final_configuration.csv) |
| **Baseline Group-Aware Macro-F1** | **0.9500** | [model_comparison.csv](results/tables/model_comparison.csv) |
| **Single-Flow Inference Latency** | **0.0026 ms** (Pipeline Total < 0.80 ms) | [realtime_feature_cost.csv](results/tables/realtime_feature_cost.csv) |
| **Serialized Model Footprint** | **0.15 MB** | [feature_model_pareto_frontier.csv](results/tables/feature_model_pareto_frontier.csv) |
| **Early Prediction Fidelity** | **0.8800 Macro-F1** at $N=5$ Packets (100% Coverage) | [early_prediction_robustness.csv](results/tables/early_prediction_robustness.csv) |
| **Capture File Generalization** | **0.9000 Macro-F1** (Unseen PCAP files) | [generalization_scorecard.csv](results/tables/generalization_scorecard.csv) |
| **Session Generalization** | **0.8800 Macro-F1** (Unseen User Sessions) | [generalization_scorecard.csv](results/tables/generalization_scorecard.csv) |
| **Temporal Generalization** | **0.8400 Macro-F1** (Chronological past $\rightarrow$ future) | [generalization_scorecard.csv](results/tables/generalization_scorecard.csv) |
| **Expected Calibration Error (ECE)**| **0.1170** | [calibration_results.csv](results/tables/calibration_results.csv) |
| **Unit & Integration Test Suite** | **27 / 27 Tests Passing** | [final_test_matrix.csv](results/tables/final_test_matrix.csv) |

---

## 🏛️ System Architecture

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
                 │ (TrafficPredictionEvent on in-memory EventBus)
                 ├──▶ Persistence: results/realtime/predictions.csv & .jsonl
                 ▼
      [ dashboard/app.py ]
                 │ (Streamlit Cybersecurity SOC Monitoring Console)
```

---

## 🔒 Security, Privacy & Non-Inspection Guarantee

1. **Zero Payload Inspection**: Strips application payload contents immediately at packet ingress.
2. **No Decryption**: Zero TLS interception, zero private key extraction, zero MITM proxying.
3. **Privacy by Design**: Raw IP addresses are scrubbed from feature arrays to prevent topological shortcuts. Full privacy documentation is in [`SECURITY.md`](SECURITY.md).

---

## 🚀 Quickstart & Reproduction Commands

### 1. Diagnostic Environment & Artifact Verification
```bash
python scripts/check_environment.py
python scripts/verify_artifacts.py
python scripts/validate_research_claims.py
```

### 2. Launch the Streamlit Cybersecurity SOC Console
```bash
streamlit run dashboard/app.py
```

### 3. Run Real-Time Classification (Demo vs Live Capture)
```bash
# Demo / Replay Mode (Zero Privileges Required)
python -m realtime.run --demo

# Live Network Capture Mode
python -m realtime.run --interface <INTERFACE_NAME> --model lightgbm
```

### 4. Master One-Command Reproduction Pipeline
```bash
python scripts/reproduce.py --all
```

### 5. Execute Full Test Suite
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 📁 Repository Structure

```
encrypted-traffic-classification/
├── VERSION                         # Version 1.0.0
├── CHANGELOG.md                   # Full phase change history
├── README.md                      # Primary research guide
├── SECURITY.md                    # Privacy and non-DPI policy
├── requirements.txt               # Base dependency list
├── requirements-lock.txt          # Frozen dependency lockfile
├── config.yaml                    # Master project configuration
│
├── data/
│   ├── dataset_manifest.csv       # Manifest with session & temporal metadata
│   ├── raw/ (pcap, metadata)
│   ├── processed/ (flows, features, splits_temporal, splits_session, splits_capture)
│   └── external/README.md         # Public benchmark ingestion guide
│
├── capture/                       # Packet sniffing & PCAP readers
├── flows/                         # Bidirectional 5-tuple flow generator
├── preprocessing/                 # Feature extraction & preprocessing
├── models/                        # ML classifiers with pure-Python fallbacks
├── training/                      # Training, ranking, Pareto, & splitting pipelines
├── realtime/                      # Async classification engine & EventBus
├── dashboard/app.py               # Streamlit Cyber SOC Console
├── experiments/                   # Robustness & traffic rate benchmarks
├── scripts/                       # Reproduction, verification, & diagnostic CLI tools
├── results/                       # Markdown reports, serialized models, & CSV tables
├── docs/                          # Architecture, findings, limitations, paper/, presentation/
├── release/                       # UROP lightweight release distribution bundle
└── tests/                         # 27 comprehensive unit & smoke tests
```

---

## 📚 Academic Manuscript & Presentation Slides

- **Full Paper Chapters:** [`docs/paper/`](docs/paper/) (`01_abstract.md` through `15_references.md`)
- **Presentation Slides:** [`docs/presentation/`](docs/presentation/) (`01_problem.md` through `15_conclusion.md`)
- **Live Demo Script:** [`docs/demo_script.md`](docs/demo_script.md)
- **UROP Release Bundle:** [`release/`](release/)
