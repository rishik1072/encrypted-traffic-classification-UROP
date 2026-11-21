# Phase 1 Literature Review: Encrypted Traffic Classification, Early Observation, and Selective Prediction Under Distribution Shift

**Project**: Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models  
**Document**: Authoritative Systematic Literature Review  
**Date**: November 2026  
**Status**: Completed Pre-Implementation Research Audit

---

## 1. Executive Overview and Scope

Modern network traffic classification operates under challenging structural conditions: payload encryption (TLS 1.3, QUIC, Encrypted Client Hello [ECH]) eliminates deep packet inspection (DPI) signatures, while operational demands require real-time, low-latency categorization on resource-constrained network appliances.

This literature review investigates the foundational and state-of-the-art (2016–2026) scientific corpus to establish an unassailable research gap for:
$$\textbf{Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift}$$

Every cited publication has been verified against official academic indexing services (ACM Digital Library, IEEE Xplore, USENIX, NDSS, and arXiv).

---

## 2. Core Literature Source Verification and Deep Analysis

### Paper A: FastFlow (ACM POMACS / ACM SIGMETRICS 2025)
- **Title**: *FastFlow: Early Yet Robust Network Flow Classification Using the Minimal Number of Time-Series Packets*
- **Authors**: Rushi Jayeshkumar Babaria, Minzhao Lyu, Gustavo Batista, Vijay Sivaraman
- **Venue**: *Proceedings of the ACM on Measurement and Analysis of Computing Systems* (POMACS) / presented at ACM SIGMETRICS 2025
- **DOI**: [10.1145/3727115](https://doi.org/10.1145/3727115) | **arXiv**: [arXiv:2504.02174](https://arxiv.org/abs/2504.02174)
- **Status**: **Peer-Reviewed Top-Tier Journal / Conference**
- **Dataset Evaluated**: Public benchmarks (ISCX-VPN, USTC-TFC2016) and a large-scale real-world campus ISP network deployment (millions of flows).
- **Number of Classes**: Multi-class application identification ($10+$ classes).
- **Feature Representation**: Dual-granularity representation combining per-packet time-series features (sizes, inter-arrival times, directions) with slotted aggregate statistics to maintain invariance against packet reordering.
- **Model Architecture**: Long Short-Term Memory (LSTM) recurrent neural network combined with a dynamic sequential decision-making reinforcement learning (RL) policy.
- **Evaluation Methodology**: Online sequential packet intake with adaptive early stopping.
- **Reported Results**: Achieves over $95\%$ accuracy using an average of 4–8 packets per flow, significantly reducing packet horizon compared to fixed-length classifiers.
- **Limitations**:
  1. Relies on an LSTM-RL recurrent architecture that incurs substantial floating-point state tracking overhead, limiting throughput on edge microprocessors.
  2. Does not incorporate formal probability calibration or bounded-risk selective prediction; uses an RL stopping policy rather than a calibrated posterior threshold.
  3. Evaluated primarily within single campus network topologies without cross-environment physical hardware shifts.
- **Relevance to Project**: FastFlow validates that dynamic packet-prefix observation provides sufficient statistical signal for early classification, but demonstrates the need for a **lightweight, tree-based alternative** suitable for standard CPU architectures.

---

### Paper B: SoK: Decoding the Enigma of Encrypted Network Traffic Classifiers (IEEE S&P 2025)
- **Title**: *SoK: Decoding the Enigma of Encrypted Network Traffic Classifiers*
- **Authors**: Nimesha Wickramasinghe, Arash Shaghaghi, Gene Tsudik, Sanjay Jha
- **Venue**: *2025 IEEE Symposium on Security and Privacy* (S&P / "Oakland" 2025)
- **DOI**: [10.1109/SP61157.2025.00165](https://doi.org/10.1109/SP61157.2025.00165)
- **Status**: **Peer-Reviewed Top-Tier Security Conference**
- **Dataset Evaluated**: Extensive audit of existing datasets; introduces **CipherSpectrum** (120,000 modern TLS 1.3 sessions across 40 domains using AES-GCM and ChaCha20-Poly1305).
- **Number of Classes**: 40 modern application domains.
- **Feature Representation**: Comprehensive taxonomy: byte-level raw payloads, packet lengths, inter-arrival times, TLS handshake metadata, and Session Initialization Information (SII).
- **Model Architecture**: Survey and empirical evaluation of 1D/2D CNNs, LSTMs, Transformers (ET-BERT), and Gradient Boosted Decision Trees (XGBoost/LightGBM).
- **Evaluation Methodology**: Systematic feature occlusion framework (**NTC-Enigma**) isolating the impact of IP headers, SNI, TLS handshake parameters, and temporal dynamics.
- **Reported Results**:
  1. Exposed that widespread public benchmarks (ISCX, CIC-IDS) contain unencrypted traffic, deprecated ciphers (3DES/RC4), or obvious IP/port shortcuts.
  2. Demonstrates that deep learning classifiers frequently achieve $> 98\%$ accuracy by overfitting to pseudo-random Session Initialization Information (SII) rather than learning true behavioral dynamics.
  3. When SII and IP headers are obscured, classifier performance plummets dramatically.
- **Limitations**: Provides a systematization and diagnostic toolkit, but does not propose an operational lightweight early classification framework with calibrated abstention.
- **Relevance to Project**: Foundational justification for our zero-payload, zero-IP approach. Proves that excluding IP/port shortcuts is essential for genuine scientific validity and reveals why naive ML models fail under modern AEAD TLS 1.3 encryption.

---

### Paper C: The Split Protocol Decides the Result (arXiv 2026)
- **Title**: *The Split Protocol Decides the Result: Re-Evaluating Encrypted Traffic Classification*
- **Authors**: Mayan Sharma, Kriti Saini, Devansh Behl
- **Venue**: *arXiv preprint* (arXiv:2611.06290, November 2026)
- **DOI**: [arXiv:2611.06290](https://arxiv.org/abs/2611.06290)
- **Status**: **Preprint (Under Peer Review)**
- **Dataset Evaluated**: One month of backbone QUIC traffic and standard benchmark corpora.
- **Number of Classes**: Multi-class QUIC service/application classification.
- **Feature Representation**: Packet length sequences, inter-arrival time distributions, and flow summary statistics.
- **Model Architecture**: Gradient Boosted Trees (LightGBM/XGBoost), ResNet-1D, and Transformer flow embeddings.
- **Evaluation Methodology**: Evaluates classifiers across 5 distinct data partitioning protocols: random flow splitting, temporal splitting, client-disjoint splitting, session-disjoint splitting, and server-disjoint splitting.
- **Reported Results**:
  1. Proves that changing *only* the split protocol—without altering a single line of model code—causes performance to drop from **0.992 Macro-F1** (random split) to **0.567 Macro-F1** (capture/session-isolated split).
  2. Introduces *single-identifier probes*: training a decision tree solely on metadata IDs achieves 0.983 accuracy under random splits but exactly 0.000 under session-disjoint splits, diagnosing dataset shortcut learning.
  3. Demonstrates that under rigorous split protocols, complex deep learning architectures provide no statistically significant benefit over gradient-boosted trees on basic packet statistics.
- **Limitations**: Focuses strictly on evaluation methodology and offline analysis; does not evaluate live real-time capture engines, early packet prefix horizons, or calibrated selective prediction.
- **Relevance to Project**: Directly corroborates our Phase 0 audit findings (where Random Split on synthetic loopback scored 0.95 vs 0.58 on session-disjoint real data). Provides methodological authority for establishing strict session- and environment-disjoint validation protocols.

---

### Paper D: LoFi (IEEE NetSoft 2026)
- **Title**: *LoFi: Low-Cost Early Application Filter Based on Cached ML Decisions*
- **Authors**: Johann Hugon, Shinan Liu, Paul Schmitt, Nick Feamster, Francesco Bronzino
- **Venue**: *2026 IEEE 12th International Conference on Network Softwarization* (NetSoft 2026), Berlin, Germany, pp. 273–278
- **DOI**: [10.1109/NetSoft70012.2026.11603512](https://doi.org/10.1109/NetSoft70012.2026.11603512)
- **Status**: **Peer-Reviewed Conference Proceedings**
- **Dataset Evaluated**: Campus and edge enterprise traffic traces.
- **Number of Classes**: Coarse and fine-grained application categories.
- **Feature Representation**: Early packet lengths and arrival intervals from the first 3–5 packets.
- **Model Architecture**: Hierarchical cached filter: exact 5-tuple/SNI cache combined with an early lightweight tree classifier fallback.
- **Evaluation Methodology**: Live software-defined network (SDN) data plane pipeline profiling.
- **Reported Results**: Eliminates up to $85\%$ of repeated ML inference invocations through intelligent caching of early classification decisions, achieving sub-millisecond filtering at the edge.
- **Limitations**: Relies heavily on flow re-occurrence and caching; does not investigate probability calibration, selective prediction error bounds, or open-set traffic dynamics under environment shift.
- **Relevance to Project**: Demonstrates that early classification must be coupled with high-efficiency systems engineering. Supports our focus on lightweight inference suitable for real-time edge integration.

---

### Paper E: FlowPrint (NDSS 2020)
- **Title**: *FlowPrint: Semi-Supervised Mobile-App Fingerprinting on Encrypted Network Traffic*
- **Authors**: Thijs van Ede, Riccardo Bortolameotti, Andrea Continella, Jingjing Ren, Daniel J. Dubois, Martina Lindorfer, David Choffnes, Maarten van Steen, Andreas Peter
- **Venue**: *Network and Distributed System Security Symposium* (NDSS 2020)
- **DOI**: [10.14722/ndss.2020.24412](https://doi.org/10.14722/ndss.2020.24412)
- **Status**: **Peer-Reviewed Top-Tier Security Conference**
- **Dataset Evaluated**: ReCon dataset and cross-device mobile app traffic captures (over 1,000 mobile applications across Android/iOS).
- **Number of Classes**: Open-world app fingerprinting ($> 100$ apps).
- **Feature Representation**: Graph-based temporal correlation of destination certificates, packet size bursts, and inter-arrival timing.
- **Model Architecture**: Semi-supervised graph clustering and modularity optimization.
- **Evaluation Methodology**: Evaluates cross-device generalization and unseen app detection over multi-month temporal windows.
- **Reported Results**: Achieved 89.2% precision in identifying unseen mobile applications while maintaining high clustering purity across distinct physical handsets.
- **Limitations**:
  1. Requires full-flow interaction and cross-flow graph assembly, making it unsuitable for sub-10-packet early triage.
  2. High computational complexity of graph clustering prohibits high-throughput single-packet line-rate execution.
- **Relevance to Project**: Highlights the critical importance of handling *unknown* / unseen applications (open-set problem) and establishes the gold standard for cross-device mobile traffic evaluation.

---

### Paper F: AppScanner (IEEE EuroS&P 2016)
- **Title**: *AppScanner: Automatic Fingerprinting of Smartphone Applications from Encrypted Network Traffic*
- **Authors**: Vincent F. Taylor, Riccardo Spolaor, Mauro Conti, Ivan Martinovic
- **Venue**: *2016 IEEE European Symposium on Security and Privacy* (EuroS&P 2016)
- **DOI**: [10.1109/EuroSP.2016.40](https://doi.org/10.1109/EuroSP.2016.40)
- **Status**: **Peer-Reviewed Top-Tier Security Conference**
- **Dataset Evaluated**: 110 popular Android applications collected across physical smartphones.
- **Number of Classes**: 110 application classes.
- **Feature Representation**: 54 statistical features derived from packet lengths and directions (mean, median, standard deviation, percentiles, skewness, kurtosis).
- **Model Architecture**: Random Forest and Support Vector Machines (SVM).
- **Evaluation Methodology**: Closed-world and open-world classification across distinct network capture runs.
- **Reported Results**: Over 99% accuracy in closed-world identification and $> 85\%$ in open-world settings using full-flow statistical aggregations.
- **Limitations**:
  1. Computes statistics across the *entire flow duration*, introducing massive observation latency (flows must terminate before features are computed).
  2. Lacks formal uncertainty calibration; open-world rejection relies on naive heuristic distance thresholds.
  3. Pre-dates modern TLS 1.3 / QUIC encrypted handshakes and ECH.
- **Relevance to Project**: The foundational ancestor of statistical flow classification. Our 21 canonical features derive from this statistical heritage, but our research directly addresses AppScanner's core limitation: transitioning from full-flow post-mortem analysis to **early-prefix, calibrated real-time prediction**.

---

### Additional High-Impact Literature (2017–2026)

| Citation | Venue | Key Topic | Core Contribution |
| :--- | :--- | :--- | :--- |
| **Lin et al. (ET-BERT)**, 2022 | ACM WWW | Deep Learning ETC | Pre-trained datagram Transformer capturing encrypted payload contextual embeddings; high accuracy but prohibitive inference latency ($> 20\text{ ms}$). |
| **Arp et al. (Dos and Don'ts)**, 2022 | USENIX Security | ML Security Pitfalls | Comprehensive systematization of sampling bias, label leakage, and spurious correlations in security ML. |
| **Geifman & El-Yaniv (SelectiveNet)**, 2017/2019 | NeurIPS / ICML | Selective Prediction | Formalized risk-coverage trade-off: $\min_\tau \text{Risk}(\tau)$ s.t. $\text{Coverage}(\tau) \ge 1 - c$ with reject option. |
| **Guo et al. (Calibration)**, 2017 | ICML | Model Calibration | Demonstrated that modern deep networks and unconstrained ensembles are severely miscalibrated; popularized Temperature Scaling. |
| **Scheirer et al. / Bendale & Boult**, 2013/2016 | IEEE TPAMI / CVPR | Open-Set Recognition | Formalized open-space risk and OpenMax probability redirection for managing out-of-distribution instances. |
| **Wiesner et al. (CESNET-TLS)**, 2024–2026 | IEEE TNSM | Concept Drift in ETC | Multi-year longitudinal study proving severe temporal degradation of TLS classifiers due to CDN routing and cipher updates. |

---

## 3. Ten-Dimensional Critical Comparison of Existing Approaches

| Dimension | Standard Literature Approach | State-of-the-Art / SOTA | Our Proposed Approach | Justification & Research Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **1. Granularity** | Flow-level summary statistics | Packet-level sequence modeling | Hybrid prefix flow aggregation | Bridges packet-level early availability with flow-level statistical stability. |
| **2. Temporal Horizon**| Post-mortem full flow | Fixed prefix ($K=5$ or $K=10$ pkts) | Multi-stage prefix progression ($K \in \{3, 5, 10, \text{full}\}$) | Maps accuracy, risk, and coverage dynamically as physical packets arrive. |
| **3. Representation**| Raw payload bytes | Byte-level Transformer tokens | Zero-payload statistical metadata | Guarantees TLS 1.3/ECH invariance, privacy compliance, and $O(1)$ memory streaming. |
| **4. Inference Engine**| Heavy Deep Neural Nets (CNN/LSTM) | LLMs / Transformer Embeddings | Lightweight Tree Ensembles (LightGBM/RF)| Achieves sub-millisecond execution ($< 350\,\mu\text{s}$) suitable for CPU edge deployment. |
| **5. Class Space** | Closed-set ($N$ fixed classes) | Open-set via embedding distances | Calibrated 4-state selective policy | Distinguishes known traffic, legitimate "Other", and out-of-distribution "UNKNOWN". |
| **6. Decision Gate** | Fixed argmax Softmax threshold | Heuristic distance thresholds | Post-hoc calibrated selective gating | Formal temperature scaling bounding selective risk ($\text{Risk} \le \alpha$). |
| **7. Partition Scheme**| Random flow k-fold split | Chronological temporal split | Grouped session- and parent-isolated | Prevents prototype leakage and exposure to shared network identifiers. |
| **8. Environment Bias**| Single capture environment | Lab vs Lab synthetic splits | Cross-adapter & cross-environment | Audits physical transfer across distinct Wi-Fi adapters and network routing topologies. |
| **9. Deployment** | Offline PCAP file replaying | Emulated Mininet pipelines | Live hardware Npcap streaming | Validates true operating-system packet arrival, socket queuing, and driver latencies. |
| **10. Robustness** | Unaudited high accuracy ($> 95\%$) | Occlusion sensitivity auditing | Quantified degradation under drift | Establishes realistic, scientifically honest baselines under severe distribution shift. |

---

## 4. Current Repository Implementation vs. Research Frontier

Based on the forensic Phase 0 and Phase 0.5 audits:

| Research Dimension | Implementation Status | Ground-Truth Technical Status in Codebase | Required Phase 1 Development |
| :--- | :---: | :--- | :--- |
| **Live Packet Capture** | **IMPLEMENTED** | Npcap live capture operational on Wi-Fi adapter via Scapy `AsyncSniffer` ([packet_capture.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/capture/packet_capture.py)). | Maintain existing capture engine without modification. |
| **Zero-Payload Processing**| **IMPLEMENTED** | Slices headers immediately; drops payload bytes in memory; zero PII on disk ([sqlite_store.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/realtime/sqlite_store.py)). | Formalize zero-payload verification in test suite. |
| **Bidirectional Flow Assembly**| **IMPLEMENTED** | Flow tracking with 120 s active / 30 s idle timeouts ([flow_tracker.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/realtime/flow_tracker.py)). | Maintain existing flow aggregation contracts. |
| **Lightweight ML Classifier** | **IMPLEMENTED** | LightGBM and Random Forest inference engines integrated into live pipeline ([classifier.py](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/realtime/classifier.py)). | Maintain production model; add dedicated prefix-trained models. |
| **True Streaming Algorithms** | **NOT IMPLEMENTED** | Flow tracker buffers packet records in Python lists ($O(N)$ memory); two-pass variance calculation. | Implement true $O(1)$ Welford accumulators and $P^2$ streaming median estimation. |
| **Probability Calibration** | **NOT IMPLEMENTED** | Raw tree probabilities used directly; metadata label `"Platt_Scaling_Sigmoid"` is a placeholder; test ECE is **$19.96\%$**. | Implement formal Temperature Scaling / Dirichlet calibration on validation data. |
| **Dedicated Prefix Models** | **PARTIALLY IMPLEMENTED**| Early classification evaluated offline in `research_early_prediction.csv` on full-flow model; no dedicated $K$-packet models. | Train specialized prefix classifiers optimized strictly for $K \in \{3, 5, 10\}$ packet horizons. |
| **Parent-Lineage Tracking** | **NOT IMPLEMENTED** | `expand_dataset_v2.py` cloned prototypes without recording `parent_flow_id`, inducing leakage across session splits. | Build `dataset_v3` with explicit parent flow lineage and multi-environment provenance. |
| **Cross-Environment Validation**| **NOT IMPLEMENTED** | All 121 physical flows collected on a single Windows 11 host and local network. | Collect independent validation captures across at least 3 distinct physical environments. |

---

## 5. Synthesis and Research Direction Selection

The literature review firmly establishes that while heavy deep learning architectures (ET-BERT, FastFlow) achieve high accuracy on early packets, they suffer from three critical shortcomings:
1. **Computational Prohibitive Cost**: Inability to achieve sub-millisecond execution on standard edge CPUs.
2. **Evaluation Vulnerability**: Severe susceptibility to split protocol artifacts and dataset shortcut learning (as exposed by Sharma et al., 2026 and Wickramasinghe et al., 2025).
3. **Miscalibration & Overconfidence**: Uncalibrated predictions that produce catastrophic false alarms under open-world network shifts.

This provides an authoritative scientific foundation for our selected primary research direction:

$$\textbf{Primary Direction: Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift}$$

Supported by two complementary technical contributions:
- **Supporting Contribution 1**: *Calibrated Risk-Coverage Selective Gating* for early flow observation horizons.
- **Supporting Contribution 2**: *Leakage-Aware Parent-Isolated Multi-Environment Benchmark Design*.
