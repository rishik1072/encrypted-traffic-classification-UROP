# Experiment Integrity & Methodological Verification Audit

**Status:** ALL INVARIANTS PASSED (11/11 PASS)  
**Audit Date:** September 22, 2026  
**Audited Target:** Research Pipeline, Data Registry, Feature Registry, Training Scripts, and Model Artifacts (`EXP-R09` through `EXP-R15`)

---

## 1. Executive Summary

This audit independently verifies the foundational scientific and engineering invariants of the Encrypted Traffic Classification research project. To ensure absolute research integrity, every phase of data collection, feature generation, model training, evaluation, and real-time streaming was audited against data leakage, payload contamination, uncalibrated tuning, and synthetic data pollution.

All **11 core integrity invariants** have been evaluated and achieved an unqualified **PASS**.

---

## 2. Invariant Verification Scorecard

| Invariant ID | Research Invariant | Required Criterion | Verification Method & Evidence | Status |
| :---: | :--- | :--- | :--- | :---: |
| **INV-01** | **No Test-Set Tuning** | Locked test split evaluated strictly once; zero hyperparameter or threshold optimization on test samples | Inspected `training/train_baseline.py`, `training/feature_study.py`, `training/research_early_prediction.py`, and `training/research_selective_prediction.py`. Hyperparameters, feature subsets, and thresholds ($\tau^*$) are derived strictly on train/val folds. Held-out test set ($N=48$, 24 sessions) is strictly evaluated post-freeze. | **PASS** |
| **INV-02** | **No Session Leakage** | Complete independence of user sessions ($S_{\text{train}} \cap S_{\text{test}} = \emptyset$) | Evaluated Group-Aware Stratified Session Splitter in `scripts/preprocess_real_traffic.py` and `training/real_optimization_pipeline.py`. Stage 4 of `reproduce_research.py` computes set intersection across 102 train, 24 val, and 24 test sessions: overlap count = 0. | **PASS** |
| **INV-03** | **No Capture Leakage** | Physical capture files disjoint between training and test sets in capture-shift experiments | Audited `training/research_generalization.py` (Regime 2). 120 capture files assigned to training, 30 distinct capture files assigned to testing. Exact file paths verified non-intersecting ($C_{\text{train}} \cap C_{\text{test}} = \emptyset$). | **PASS** |
| **INV-04** | **No Duplicated Flow Leakage** | Zero identical flow tuples or exact duplicate feature vectors across splits | Audited flow deduplication logic in `scripts/preprocess_real_traffic.py`. Cryptographic SHA-256 row-hash audit in `scripts/reproduce_research.py` confirms 0 identical feature vectors cross partition boundaries. | **PASS** |
| **INV-05** | **Validation-Only Threshold Selection** | Confidence rejection thresholds ($\tau^*$) and early horizons selected solely on validation data | In `training/research_selective_prediction.py`, threshold search sweeps validation split; $\tau^*=0.70$ is chosen by maximizing $\text{Macro-F1}_{\text{val}} \times \text{Coverage}_{\text{val}}$. The selected threshold is applied blindly to the locked test split. | **PASS** |
| **INV-06** | **Fixed Random Seeds** | Deterministic pseudo-random number generator initialization across all operations | Global seed `seed=42` declared in `config.yaml` and enforced across Python `random`, `numpy.random`, `scikit-learn`, and `lightgbm`. Reproducibility verified by identical SHA-256 metric generation across multiple runs. | **PASS** |
| **INV-07** | **No DEMO_MODE in Research Results** | Synthetic or replay vectors flagged as DEMO_MODE are strictly excluded from research tables | `realtime/events.py` enforces mandatory `traffic_origin` metadata. `dataset/dataset_registry.py` raises hard exceptions if `DEMO_MODE` or synthetic files are fed into real-traffic research runners. Validated by `tests/test_zero_payload_live.py`. | **PASS** |
| **INV-08** | **No Synthetic Fixtures in REAL_DATA** | Research experiments run exclusively on `dataset_v2` (`features_real_clean_v2.csv`) | `dataset/dataset_registry.py` enforces cryptographic SHA-256 hash checks (`cd3193ecdd...`) on all input datasets before benchmark initialization. Legacy 12-flow `dataset_v1` is physically segregated. | **PASS** |
| **INV-09** | **No Payload-Derived Features** | All 84 features derived strictly from Layer-3/4 transport header fields and timing dynamics | Code review of `preprocessing/feature_extractor.py` confirms extraction functions ingest only `RawPacketMetadata` (timestamp, IP length, protocol, direction, TCP flags). Zero application payload bytes, SNI, or HTTP headers are inspected. | **PASS** |
| **INV-10** | **No Decrypted Payload Information** | Zero TLS decryption, private key extraction, or MITM interception | Architectural audit of the entire codebase confirms absence of TLS decryption modules (no OpenSSL key-logging, no SSLKEYLOGFILE, no root certificate tampering, no cleartext proxying). Operates purely on ciphertext traffic. | **PASS** |
| **INV-11** | **No Raw Payload Persistence** | Zero packet application payloads written to disk, SQLite, logs, or JSONL outputs | Audited `realtime/persistence.py`, `realtime/flow_tracker.py`, and `capture/packet_capture.py`. Application payloads are discarded immediately at network ingress. All IP addresses are hashed with SHA-256 prior to persistence. | **PASS** |

---

## 3. Deep-Dive Audit Findings

### 3.1 Session-Level Group Isolation (INV-02)
Standard stratified random splitting on network traffic causes severe optimistic bias due to session autocorrelation: packets from the same TLS handshake or streaming download share identical server configurations, OS TCP stacks, and network paths.
- **Audit Test:** Checked `tests/test_real_generalization_v2.py` and `tests/test_real_metadata_pipeline.py`.
- **Finding:** The dataset splits (`data/processed/splits/real_clean/`) strictly group all bidirectional flows belonging to the same user session into a single split. Zero session identifiers overlap between train, validation, and test partitions.

### 3.2 Threshold Optimization Discipline (INV-05)
Post-hoc threshold tuning on test data is a rampant failure mode in selective classification research.
- **Audit Test:** Inspected `training/research_selective_prediction.py`.
- **Finding:** Threshold $\tau^*=0.70$ was selected strictly from the validation split ROC/Risk-Coverage trade-off curve. When evaluated on the locked test set at $\tau^*=0.70$, the model achieved 73.08% Selective Accuracy (26.92% Error Rate) and 0.6515 Selective Macro-F1 at 54.17% Coverage without any retroactive test adjustments.

### 3.3 Zero-Payload Privacy Preservation (INV-09, INV-10, INV-11)
To ensure compliance with organizational data protection standards (GDPR / HIPAA):
- **Audit Test:** Executed `tests/test_payload_security.py` and `tests/test_product_privacy.py`.
- **Finding:** The capture engine reads only the IP packet length and TCP/UDP header headers via Scapy/libpcap. Packet payload byte arrays are never stored in memory structures beyond instantaneous header unpacking. Persistent artifacts (`results/realtime/predictions.csv`, `predictions.jsonl`) record only classification outcomes, confidence scores, and masked flow IDs.

---

## 4. Verification Conclusion

The empirical pipeline adheres strictly to rigorous research methodology standards. No evidence of data leakage, target contamination, post-hoc optimization, or synthetic pollution exists in the authoritative research release.
