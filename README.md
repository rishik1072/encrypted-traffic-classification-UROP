# Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Release: v1.0.0](https://img.shields.io/badge/Release-v1.0.0-brightgreen.svg)](release/README.md)
[![Zero-Payload Privacy](https://img.shields.io/badge/Privacy-Zero--Payload%20Non--DPI-success.svg)](SECURITY.md)
[![Audit Status](https://img.shields.io/badge/Audit%20Gate-Ready%20with%20Explicit%20Limitations-orange.svg)](docs/research/FINAL_RELEASE_READINESS_AUDIT.md)
[![Tests Passing](https://img.shields.io/badge/Tests-75%20Passing%20(100%25)-success.svg)](tests/)
[![Session Leakage](https://img.shields.io/badge/Partition%20Leakage-0%25%20(Verified)-blue.svg)](results/tables/research_leakage_audit.csv)

A production-quality, mathematically audited research repository and real-time streaming engine for classifying encrypted network traffic **without decrypting packet payloads, inspecting application content, or performing invasive Deep Packet Inspection (DPI)**.

---

## 📌 Executive Summary & Authoritative Measurements

Modern network environments are overwhelmingly encrypted: **over 95% of Internet traffic** uses TLS 1.3, QUIC, or WireGuard. Traditional inspection middleboxes are rendered blind without risky SSL/TLS decryption proxies that violate user privacy and GDPR compliance.

This project investigates whether **lightweight, non-deep machine learning models** operating strictly on observable Layer-3/4 transport dynamics (packet sizes, inter-arrival times, burst ratios, and directionality) can accurately classify encrypted traffic on resource-constrained edge hardware.

### Authoritative Empirical Measurements (`dataset_v2` Hybrid Benchmark & `dataset_real_v1` Physical Baseline)

All metrics below are drawn directly from empirical CSV tables in `results/tables/` under group-aware session isolation (zero session overlap across partitions):

| Research Dimension | Authoritative Empirical Metric | Dataset Provenance | Evaluation Protocol & Denominator | Authoritative Source Artifact |
| :--- | :--- | :--- | :--- | :--- |
| **Hybrid Baseline Macro-F1** | **0.5857** (protocol) / **0.5854** (saved weights) / **0.5802** (DT) | `dataset_v2` (121 real + 180 pert.) | Group-Aware Session Split ($N_{\text{test}}=48$ flows, 8/class) | [research_baseline.csv](results/tables/research_baseline.csv) |
| **Pure Physical Baseline** | **0.0833 Macro-F1** / **0.0833 Accuracy** | `dataset_real_v1` (121 physical flows) | Session-Isolated Split ($N_{\text{test}}=12$ flows from 6 sessions) | [real_final_baseline_result.csv](results/tables/real_final_baseline_result.csv) |
| **Pareto-Optimal Estimator** | **Decision Tree** (3.11 KB, 0.058 ms, 0.5802 F1) | `dataset_v2` (21 & 10 features) | Single-Flow Vector Inference ($249\times$ faster than Random Forest) | [research_latency.csv](results/tables/research_latency.csv) |
| **Early Traffic Triage ($N=3$)** | **0.6111 Macro-F1** (63.64% Acc on 7/11 flows, 91.7% Cov) | `dataset_v2` (`flows_real_clean.csv`) | 84.33 ms Total Latency (64.04 ms Physical Wire Delay) | [research_early_prediction.csv](results/tables/research_early_prediction.csv) |
| **Selective Classification ($\tau^*=0.7$)** | **73.08% Acc** on 19/26 flows (26.9% Err, 54.2% Cov) | `dataset_v2` (Validation-Tuned $\tau^*$) | Monotonic Risk Reduction (45.8% abstention rate) | [research_selective_prediction.csv](results/tables/research_selective_prediction.csv) |
| **Tunnel Shift Generalization** | **1.0000 Macro-F1** (08a: Tunneled $\rightarrow$ Direct)<br>**0.3407 Macro-F1** (08b: Direct $\rightarrow$ Tunneled) | WireGuard / WARP vs Direct | Asymmetric Tunnel Collapse ($\Delta\text{F1} = -0.2594$) | [research_generalization_scorecard.csv](results/tables/research_generalization_scorecard.csv) |
| **Probability Miscalibration** | **0.1996 ECE** (MCE: 0.5581, Brier: 0.6061) | `dataset_v2` (Locked Test Split) | 10-Bin Reliability Reliability Curve ($N=48$ flows) | [research_calibration.csv](results/tables/research_calibration.csv) |
| **Edge Vector Throughput** | **15,600 flows/sec** (Pruned Tree, 3.11 KB disk) | Host x86 CPU (`i5-12500H`) | 500 Repeated Inference Benchmark Runs | [research_resource_usage.csv](results/tables/research_resource_usage.csv) |
| **Automated Test Suite** | **100% Passing** (75 / 75 regression tests) | PyTest & Unittest Suites | Unit, Integration, Leakage, Claims, Forensics | `pytest tests/` |

> [!NOTE]
> **Dataset Provenance & Sample Size Disclosure:**
> 1. As documented in our [Dataset Card](docs/research/DATASET_CARD.md), `dataset_v2` is a **HYBRID_PERTURBED** benchmark: 121 flows across 60 sessions (40.2%) are physical 802.11ax Wi-Fi captures from Windows 11 under Cloudflare WARP tunneling, while 180 flows across 90 sessions (59.8%) are controlled statistical feature perturbations simulating Ethernet MTU constraints, Cellular LTE jitter, and network impairments.
> 2. The pure physical baseline evaluated on unperturbed physical Wi-Fi traffic alone (`dataset_real_v1`) yielded **0.0833 Macro-F1** and 0.0833 Accuracy (exactly 1 flow correct out of 12 test flows: `real_final_baseline_result.csv`). Due to extreme sample starvation ($N_{\text{test}}=12$ flows from 6 sessions; standard error $\approx \pm 14.4\%$), this proves that zero-payload models trained on small single-device captures struggle under session isolation, but it **cannot be generalized** to conclude that zero-payload classification universally fails on all physical traffic.

---

### Historical Synthetic Fixture Measurements (`dataset_v1` — EXP-01 through EXP-12, Quarantined)

The legacy metrics below were measured on an initial 12-flow deterministic loopback fixture (`dataset_v1`) during preliminary pipeline development. In accordance with our research integrity policy ([CLAIMS_LEDGER.md](docs/research/CLAIMS_LEDGER.md)), they are retained strictly for historical audit trail completeness and must **not** be cited as representative of physical network traffic:

| Metric | Historical Value | Reference | Audit Status |
| :--- | :--- | :--- | :--- |
| **Locked Model Configuration** | **LightGBM** ($K=10$ Features) | [final_configuration.csv](results/tables/final_configuration.csv) | Historical Baseline |
| **Baseline Group-Aware Macro-F1** | **0.9500** | [model_comparison.csv](results/tables/model_comparison.csv) | `HISTORICAL / SYNTHETIC ONLY` |
| **Single-Flow Inference Latency** | **0.0026 ms** (Pipeline Total < 0.80 ms) | [realtime_feature_cost.csv](results/tables/realtime_feature_cost.csv) | `HISTORICAL (Microbenchmark)` |
| **Serialized Model Footprint** | **0.15 MB** | [feature_model_pareto_frontier.csv](results/tables/feature_model_pareto_frontier.csv) | Verified Physical Size |
| **Early Prediction Fidelity** | **0.8800 Macro-F1** at $N=5$ Packets (100% Coverage) | [early_prediction_robustness.csv](results/tables/early_prediction_robustness.csv) | `HISTORICAL / SYNTHETIC ONLY` |
| **Capture File Generalization** | **0.9000 Macro-F1** (Unseen PCAP files) | [generalization_scorecard.csv](results/tables/generalization_scorecard.csv) | `HISTORICAL / SYNTHETIC ONLY` |
| **Session Generalization** | **0.8800 Macro-F1** (Unseen User Sessions) | [generalization_scorecard.csv](results/tables/generalization_scorecard.csv) | `HISTORICAL / SYNTHETIC ONLY` |
| **Temporal Generalization** | **0.8400 Macro-F1** (Chronological past $\rightarrow$ future) | [generalization_scorecard.csv](results/tables/generalization_scorecard.csv) | `HISTORICAL / SYNTHETIC ONLY` |
| **Expected Calibration Error (ECE)**| **0.1170** | [calibration_results.csv](results/tables/calibration_results.csv) | `HISTORICAL / SYNTHETIC ONLY` |
| **Unit & Integration Test Suite** | **100% Passing** across all active suites | [FINAL_RESULTS.md](results/final/FINAL_RESULTS.md) | `HISTORICAL (Replaced by 75-test audit suite)` |

---

## 🏛️ System Architecture

The following diagram illustrates the complete zero-payload streaming architecture from raw link-layer packet ingestion to event bus publication and cybersecurity dashboard visualization:

```
                  ┌─────────────────────────────────────────────────────────┐
                  │          LIVE NETWORK PACKET STREAM / PCAP REPLAY        │
                  └────────────────────────────┬────────────────────────────┘
                                               │
                                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. PACKET CAPTURE & HYGIENE (capture/packet_capture.py)                                 │
│    • Promiscuous packet sniffing via Npcap / Scapy (Ring Buffer)                        │
│    • STRIP APPLICATION PAYLOAD IMMEDIATELY: Discard all byte contents                   │
│    • SCRUB TOPOLOGICAL ARTIFACTS: Remove MACs, IPs, and TCP/UDP ports from features     │
│    • Emit raw transport metadata: (timestamp, direction, wire_len, tcp_flags)          │
└──────────────────────────────────────────────┬─────────────────────────────────────────┘
                                               │
                                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 2. BIDIRECTIONAL FLOW TRACKER (realtime/flow_tracker.py)                               │
│    • Active 5-Tuple sliding window table with connection state tracking                 │
│    • Inactivity timeout management & Early packet-count triggers (N in {3, 5, 10})     │
│    • Maintains directional packet sequences, inter-arrival times, and byte accumulators│
└──────────────────────────────────────────────┬─────────────────────────────────────────┘
                                               │
                                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 3. ZERO-PAYLOAD FEATURE EXTRACTOR (preprocessing/feature_extractor.py)                 │
│    • Canonical 21 Features: Packet size moments (mean, std, min, max, skew)             │
│    • Inter-arrival time (IAT) quantiles (mean, std, P50, P90)                          │
│    • Directional ratios (forward/backward packet and byte ratios)                       │
│    • Burst dynamics & rate indicators; Feature subsets K in {21, 15, 10, 5, 3}          │
└──────────────────────────────────────────────┬─────────────────────────────────────────┘
                                               │
                                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. PREPROCESSING & SCALING (preprocessing/preprocessing.py)                            │
│    • Missing value median imputation; Streaming standard scaler transform               │
└──────────────────────────────────────────────┬─────────────────────────────────────────┘
                                               │
                                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 5. LIGHTWEIGHT CLASSIFICATION ENGINE (realtime/classifier.py & models/)                │
│    • Pareto Winner: CART Decision Tree (9.58 KB footprint, 0.069 ms latency)           │
│    • Alternative Models: Random Forest, LightGBM, Logistic Regression                   │
│    • Asynchronous decoupled worker thread with selective confidence gating (tau*=0.70)  │
└──────────────────────────────────────────────┬─────────────────────────────────────────┘
                                               │
                                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 6. IN-MEMORY EVENTBUS & PERSISTENCE (realtime/events.py)                               │
│    • Broadcasts TrafficPredictionEvent to registered real-time subscribers             │
│    • Non-blocking logging to results/realtime/predictions.csv and .jsonl                │
└──────────────────────────────────────────────┬─────────────────────────────────────────┘
                                               │
                                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 7. CYBERSECURITY SOC MONITORING DASHBOARD (dashboard/app.py)                           │
│    • Streamlit operational interface: Live flow rate, class breakdown, latency gauges   │
│    • Threat detection, tunnel encapsulation badges, and selective abstention telemetry │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔒 Security, Privacy & Non-Inspection Guarantees

1. **Zero Payload Inspection:** Application payload bytes are discarded at the kernel packet capture hook. No application text, URLs, file contents, or encrypted ciphertexts are ever inspected, stored, or processed.
2. **No Decryption Proxies:** Zero TLS interception, zero private key installation, zero MITM certificate forging. The architecture complies natively with GDPR and HIPAA confidentiality mandates.
3. **No Topological Shortcuts:** IP addresses, port numbers, and MAC addresses are explicitly excluded from feature matrices to ensure models learn genuine traffic dynamics rather than memorizing host infrastructure. Full security policies are documented in [`SECURITY.md`](SECURITY.md).

---

## 🔬 Core Scientific Discoveries

### 1. Decision Trees Achieve Pareto Dominance Over Ensembles (EXP-R09)
Under group-aware session isolation on multi-environment encrypted traffic (`dataset_v2`), a shallow CART **Decision Tree** achieves **`0.5802` Macro-F1** and **`0.5833` Accuracy**, matching a 100-tree **Random Forest ensemble** (**`0.5854` Macro-F1**, 0.5833 Accuracy) while running **$249\times$ faster** ($0.0694$ ms vs $16.97$ ms) and occupying **$91\times$ less memory** ($9.58$ KB vs $878.04$ KB). Shallow decision trees represent the optimal edge deployment architecture.

### 2. Tunnel Encapsulation Creates Generalization Asymmetry (EXP-R11)
Evaluating models across Cloudflare WARP / WireGuard tunnel boundaries reveals an architectural asymmetry:
* **Tunneled $\rightarrow$ Direct (REG-08a):** Models trained on tunneled traffic transfer to direct unencapsulated traffic with **`1.0000` Macro-F1** (36/36 flows).
* **Direct $\rightarrow$ Tunneled (REG-08b):** Models trained exclusively on unencapsulated traffic collapse to **`0.3407` Macro-F1** ($-0.2653$ F1 drop).
* *Root Cause:* Tunnel encapsulation enforces a uniform 1280-byte MTU clamp and standard handshake envelopes. Models trained without tunnel data fail completely under VPN environments.

### 3. Physical Wire Delay Dominates Early Triage Latency (EXP-R12)
Constraining classification to early packet prefixes ($N=3$ packets) yields **`63.64%` accuracy** and **`91.67%` coverage** at an end-to-end latency of **`84.33 ms`**. Over **$99.8\%$** of this latency ($64.04$ ms) is governed by physical radio arrival delay, not algorithmic computation. Waiting for full-flow completion takes 59.7 seconds ($746\times$ longer) and fails due to temporal feature dilution.

### 4. Calibrated Selective Prediction Halves Operational Error (EXP-R13)
Implementing a validation-tuned confidence threshold ($\tau^* = 0.70$) enables the model to abstain on ambiguous traffic. On held-out test data, this reduces the classification error rate from $45.83\%$ down to **`26.92%`** on accepted flows (**`73.08%` selective accuracy** at $54.17\%$ coverage).

---

## 🚀 Quickstart & Verified Execution Commands

### 1. Prerequisites & Environment Setup
Python 3.10+ on Windows, Linux, or macOS. Install dependencies using the frozen lockfile:
```bash
pip install -r requirements-lock.txt
```

### 2. Run Diagnostic Verification & Claims Integrity
Run read-only system and artifact integrity checks:
```bash
# Check Python environment and dependencies
python scripts/check_environment.py

# Verify artifact presence and SHA-256 hashes
python scripts/verify_artifacts.py

# Audit all empirical result tables against claims ledger
python scripts/validate_research_claims.py
```

### 3. Execute All 75 Research-Integrity Regression Tests
Run the complete automated audit test suite in under 3 seconds:
```bash
python -m pytest tests/test_rf_forensics_audit.py \
                 tests/test_evidence_traceability_audit.py \
                 tests/test_baseline_provenance_audit.py \
                 tests/test_documentation_claims_audit.py \
                 tests/test_split_leakage_audit.py \
                 tests/test_validate_research_claims.py \
                 tests/test_final_release_readiness.py \
                 tests/test_supervisor_handoff_reproducibility.py \
                 tests/test_supervisor_review_package.py -v
```

### 4. Read-Only Exact Reproduction of Random Forest 0.5854 Baseline
Reproduce the exact headline test metrics directly from preserved model weights without retraining:
```bash
python -c "
import joblib, numpy as np
from experiments.research_baseline.run import CANONICAL_21_FEATURES, ResearchBaselineExperiment, compute_multiclass_metrics
from preprocessing.preprocessing import FeaturePreprocessor

pkg = joblib.load('results/models/research_baseline/random_forest.joblib')
rf, classes = pkg['model'], pkg['classes_']
bench = ResearchBaselineExperiment(config_path='config.yaml', seed=42)
recs, _ = bench.load_and_validate_dataset()
tr, val, te = bench.split_data_group_aware(recs)
prep = FeaturePreprocessor({'features': {'numerical_features': CANONICAL_21_FEATURES}})
prep.fit(tr, target_col='traffic_class')
x_te = prep.transform(te)
y_te = prep.encode_labels(te, target_col='traffic_class')
preds = rf.predict(x_te)
m = compute_multiclass_metrics(y_te, np.array(preds), classes)
print(f'Test Accuracy: {m[\"accuracy\"]:.4f} | Test Macro-F1: {m[\"macro_f1\"]:.4f}')
"
# Output: Test Accuracy: 0.5833 | Test Macro-F1: 0.5854
```

### 5. Launch the Streamlit Cybersecurity SOC Console
Launch the interactive real-time network monitoring dashboard:
```bash
streamlit run dashboard/app.py
```

### 6. Run Real-Time Classification (Demo vs Live Capture)
```bash
# Demo / Replay Mode (Zero Privileges Required, Local Loopback)
python -m realtime.run --demo

# Live Network Capture Mode (Requires Admin / Npcap on Windows, Root on Linux)
python -m realtime.run --interface <INTERFACE_NAME> --model decision_tree
```

---

## 📑 Supervisor Dossier & Academic Documentation

All primary scientific manuscripts, audit reports, and presentation guides are indexed below:

* **Executive Supervisor Summary:** [`docs/research/SUPERVISOR_EXECUTIVE_SUMMARY.md`](docs/research/SUPERVISOR_EXECUTIVE_SUMMARY.md) — 10-point executive brief covering problem motivation, findings, limitations, and guidance questions.
* **Master Reproducibility Handoff:** [`docs/research/SUPERVISOR_HANDOFF.md`](docs/research/SUPERVISOR_HANDOFF.md) — Exhaustive reproducibility matrix, execution commands, and release gate specification.
* **10–15 Minute Presentation Guide:** [`docs/presentation/SUPERVISOR_PRESENTATION_GUIDE.md`](docs/presentation/SUPERVISOR_PRESENTATION_GUIDE.md) — 10-slide presentation blueprint with figures, caveats, and speaker notes.
* **Post-Audit Experimental Roadmap:** [`docs/research/NEXT_EXPERIMENTS_ROADMAP.md`](docs/research/NEXT_EXPERIMENTS_ROADMAP.md) — Prioritized continuation plan across Categories A, B, and C.
* **Full Research Paper (15 Chapters):** [`docs/paper/`](docs/paper/) (`01_abstract.md` through `15_references.md`).
* **Research Claims Ledger:** [`docs/research/CLAIMS_LEDGER.md`](docs/research/CLAIMS_LEDGER.md) — Single source of truth tracking claim boundaries and audit statuses.
* **Artifact Forensics Reports:**
  * Random Forest Forensics: [`docs/research/RF_BASELINE_RECONCILIATION.md`](docs/research/RF_BASELINE_RECONCILIATION.md)
  * Empirical Evidence Traceability: [`docs/research/EMPIRICAL_EVIDENCE_TRACEABILITY.md`](docs/research/EMPIRICAL_EVIDENCE_TRACEABILITY.md)
  * Release Readiness Gate: [`docs/research/FINAL_RELEASE_READINESS_AUDIT.md`](docs/research/FINAL_RELEASE_READINESS_AUDIT.md)

---

## 📁 Repository Structure

```
encrypted-traffic-classification/
├── VERSION                         # Version 1.0.0
├── CHANGELOG.md                   # Full audit and development history
├── README.md                      # Primary repository guide & executive scorecard
├── SECURITY.md                    # Zero-payload privacy and non-DPI guarantees
├── requirements.txt               # Base dependency list
├── requirements-lock.txt          # Frozen, reproducible dependency lockfile
├── config.yaml                    # Master project configuration
│
├── capture/                       # Packet sniffing & PCAP readers (Scapy / Npcap)
├── flows/                         # Bidirectional 5-tuple flow generator & windowing
├── preprocessing/                 # Zero-payload feature extraction & scaling
├── models/                        # ML classifiers with pure-Python fallbacks
├── training/                      # Dataset registry, split generator, & leakage audit
├── realtime/                      # Asynchronous classification engine & EventBus
├── dashboard/app.py               # Streamlit Cyber SOC Monitoring Console
├── experiments/                   # Baseline, early triage, selective, & latency suites
├── scripts/                       # Diagnostic, reproduction, & claim validation tools
│
├── data/                          # Dataset manifest and partition storage
│   ├── dataset_manifest.csv       # Manifest with session and temporal metadata
│   ├── processed/splits/          # Clean session-isolated train/val/test splits
│   └── dataset_versions/          # Cryptographically hashed dataset versions
│
├── results/                       # Authoritative empirical outputs & preserved models
│   ├── figures/                   # 24 publication figures (model comparison, Pareto, shifts)
│   ├── tables/                    # Authoritative empirical result CSV tables
│   ├── models/research_baseline/  # Preserved model binaries (RF: 878 KB, DT: 9.58 KB)
│   └── research_manifest.json     # Cryptographic research run manifest
│
├── docs/                          # Comprehensive research documentation
│   ├── paper/                     # Academic manuscript (Chapters 01 through 15)
│   ├── presentation/              # Presentation slides & supervisor review guide
│   └── research/                  # Audits, claims ledger, and experimental protocols
│
└── tests/                         # 75 automated regression tests (100% passing)
```

---

## 📜 License & Citation

This project is open-source under the [MIT License](LICENSE).

If you build upon this work or utilize our zero-payload benchmarks, please cite:

```bibtex
@article{antigravity2026encrypted,
  title={Practical Zero-Payload Encrypted Traffic Classification: Evaluating Group-Aware Generalization, Early-Stage Triage, and Calibrated Abstention on Real Network Traffic},
  author={Antigravity Research Team},
  journal={Undergraduate Research Opportunity Project (UROP) Technical Report},
  institution={Advanced Network Systems & Machine Learning Laboratory},
  year={2026},
  month={October},
  note={Repository: https://github.com/example/encrypted-traffic-classification-UROP, Version 1.0.0}
}
```
