# Phase 1 Literature Matrix: Comparative Analysis of State-of-the-Art Encrypted Traffic Classification

**Project**: Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models  
**Document**: Authoritative Comparative Literature Matrix  
**Date**: November 2026  
**Status**: Authoritative Forensic Evidence Document

---

## 1. Overview

This matrix provides a side-by-side technical decomposition of the core literature (Papers A–F), foundational methodological references, and our repository's current status across 14 scientific and systems dimensions.

---

## 2. Comprehensive Comparative Matrix

| Study / Reference | Venue & Year | Peer-Reviewed Status | Evaluated Dataset | Classes | Feature Representation | Model Architecture | Early Prefix Support? | Selective / Abstention Policy | Probability Calibration | Split Protocol | Real-Time Hardware? | Reported Performance | Core Scientific Limitation |
| :--- | :--- | :---: | :--- | :---: | :--- | :--- | :---: | :--- | :--- | :--- | :---: | :--- | :--- |
| **FastFlow** (Babaria et al.) | ACM POMACS / SIGMETRICS 2025 | **Peer-Reviewed** | ISCX-VPN, Campus ISP trace | 10+ | Packet & slot time-series stats | LSTM + Reinforcement Learning | **Yes** (Adaptive 4–8 pkts) | RL stopping policy (no formal risk bound) | **None** (Uncalibrated) | Temporal trace split | Offline simulation / trace replay | $> 95\%$ accuracy on early packets | High recurrent state tracking overhead; lacks formal probability calibration. |
| **SoK: Encrypted Classifiers** (Wickramasinghe et al.) | IEEE S&P 2025 | **Peer-Reviewed** | CipherSpectrum (120k sessions) | 40 | Raw payload, headers, timing, SII | Survey: CNN, LSTM, ET-BERT, LightGBM | **No** (Full flow evaluation) | Fixed softmax threshold | Evaluated Brier score (models uncalibrated) | Temporal & occlusion splits | Offline PCAP analysis | Exposes $> 98\%$ accuracy collapses without SII | Systematization study; does not propose an operational lightweight early classification framework. |
| **The Split Protocol Decides** (Sharma et al.) | arXiv 2026 (2611.06290) | **Preprint** | Backbone QUIC corpus | Multi-class | Packet length sequences & stats | LightGBM, ResNet-1D, Flow Transformers | **No** (Full flow / fixed windows) | Heuristic distance rejection | **None** (Evaluated raw margin scores) | 5 Protocols: Random, Temporal, Client, Session, Server | Offline trace processing | Macro-F1 plummets from 0.992 (Random) to 0.567 (Strict) | Focuses solely on offline splitting protocols; lacks live capture and real-time early prediction. |
| **LoFi** (Hugon et al.) | IEEE NetSoft 2026 | **Peer-Reviewed** | Campus & enterprise SDN traces | Coarse / Fine | First 3–5 packet lengths & IATs | Hierarchical Hash Cache + Decision Tree | **Yes** (Prefix 3–5 pkts) | Fallback to tree on cache miss | **None** (Binary hash match + raw tree) | Host/subnet split | **Yes** (SDN data plane filter) | 85% inference reduction, sub-ms latency | Caching relies heavily on repetitive flow destinations; uncalibrated tree fallbacks. |
| **FlowPrint** (van Ede et al.) | NDSS 2020 | **Peer-Reviewed** | ReCon cross-device mobile traces | 100+ | Destination certs, bursts, timing graphs | Semi-supervised graph clustering | **No** (Full flow / multi-flow batches) | Thresholded graph cluster modularity | **None** (Distance-based cluster purity) | Cross-device temporal split | Offline PCAP processing | 89.2% precision on unseen mobile apps | High computational cost of graph clustering; cannot perform sub-10-packet early triage. |
| **AppScanner** (Taylor et al.) | IEEE EuroS&P 2016 | **Peer-Reviewed** | 110 Android apps | 110 | 54 flow-level statistical metrics | Random Forest & SVM | **No** (Full completed flows) | Naive distance heuristic for open-set | **None** (Uncalibrated margin distances) | Run-isolated split | Offline PCAP processing | 99% closed-world, 85% open-world | Requires completed flows (high latency); pre-dates TLS 1.3 / QUIC encrypted handshakes. |
| **ET-BERT** (Lin et al.) | ACM WWW 2022 | **Peer-Reviewed** | ISCX-VPN, CSTNET-TLS | 12–20 | Byte-level datagram tokens (512 tokens) | BERT Transformer Encoder | **No** (Fixed 512-byte header window) | Standard Softmax argmax | **None** (Severe deep overconfidence) | Random cross-validation | Offline GPU execution | $> 98\%$ Macro-F1 across benchmarks | High computational cost ($> 20\text{ ms}$ inference on GPU); impractical for edge CPUs. |
| **Dos and Don'ts in ML Sec** (Arp et al.) | USENIX Security 2022 | **Peer-Reviewed** | Survey across 30 top security papers | N/A | Methodological audit of security features | Survey of ML security pipelines | N/A | Methodological recommendations | Formally highlights calibration gaps | Highlights severe sampling & split leakage | N/A | Exposes pervasive data leakage in 70%+ papers | Meta-research paper providing methodological guidelines rather than a specific traffic model. |
| **SelectiveNet** (Geifman & El-Yaniv) | ICML 2019 / NeurIPS 2017 | **Peer-Reviewed** | CIFAR-10, ImageNet | 10–1000 | Computer vision pixel tensors | Deep CNN with auxiliary reject head | N/A | **Yes** (Bounded risk $\text{Risk} \le \alpha$) | Empirical risk calibration | Standard CV splits | GPU evaluation | Near-zero error at 60–80% coverage | Evaluated on computer vision; does not address time-series network flows or packet jitter. |
| **On Calibration of DNNs** (Guo et al.) | ICML 2017 | **Peer-Reviewed** | ImageNet, NLP corpora | Multi-class | Continuous feature embeddings | Deep ResNets, DenseNets | N/A | Confidence score ranking | **Temperature Scaling** & Vector Scaling | Standard CV splits | GPU evaluation | Reduces ECE from $> 15\%$ to $< 2\%$ | General ML theory paper; does not examine tree models, encrypted traffic, or packet prefixes. |
| **CESNET-TLS Drift Study** (Wiesner et al.) | IEEE TNSM 2024–2026 | **Peer-Reviewed** | CESNET-TLS (multi-year longitudinal) | 100+ | TLS handshake & flow timing statistics | LightGBM, Random Forest, MLP | **No** (Full flow / early TLS handshake) | Thresholded soft outputs | Evaluated ECE under temporal drift | Multi-year chronological split | High-speed backbone probe | Macro-F1 degrades by 30–50% over 12 months | Demonstrates severe temporal degradation; does not provide an active selective mitigation policy. |
| **OUR REPOSITORY (Current Audit)** | Technical Audit (2026) | **Audit Baseline** | `dataset_v2` (301 hybrid flows) | 6 | 21 canonical statistical features | Production LightGBM & Random Forest | **Partially** (Offline evaluated at $K=3$) | 4-State Policy (`KNOWN`, `LOW`, `UNK`, `INSUFF`) | **None** (Raw probabilities; ECE: 19.96%) | Session-disjoint (compromised by cloning) | **Yes** (Live Windows Npcap on Wi-Fi) | Macro-F1: 0.5474 (Test); Sel-Acc: 73.08% ($\tau=0.70$) | Small sample size ($N=121$ physical); prototype cloning leakage; uncalibrated probabilities. |

---

## 3. Structural Gap Synthesis

The matrix reveals four distinct clusters of prior art, each with an unaddressed gap:

1. **Deep Learning Sequence Models (ET-BERT, FastFlow)**:
   - *Strengths*: High accuracy on benchmark corpora; captures fine-grained sequence order.
   - *Critical Void*: Prohibitive computational and memory overhead; completely impractical for sub-millisecond edge host classification on standard CPUs without GPU acceleration.
2. **Diagnostic & Benchmark Audits (Wickramasinghe et al., Sharma et al., Arp et al.)**:
   - *Strengths*: Exposes widespread evaluation flaws, session overfitting, and split protocol sensitivity.
   - *Critical Void*: Primarily diagnostic; they do not provide a real-time, lightweight deployed classification system.
3. **Early Edge Systems (LoFi)**:
   - *Strengths*: High throughput; optimized for edge and SDN data plane deployment.
   - *Critical Void*: Relies on hash table decision caching; lacks formal uncertainty handling, probability calibration, and adaptation to non-repetitive out-of-distribution traffic.
4. **Statistical Flow Fingerprinting (AppScanner, FlowPrint)**:
   - *Strengths*: Lightweight and interpretable; zero-payload privacy compliance.
   - *Critical Void*: Requires completed flows or multi-flow graphs, introducing massive observation delays (seconds to minutes) that render them useless for early security triage.

---

## 4. Distinct Positioning of Our Research

Our project occupies a unique, unpopulated niche at the intersection of these four clusters:

$$\begin{aligned}
\textbf{Our Focus} = &\quad \text{Lightweight Tree Ensembles (sub-millisecond CPU inference)} \\
&+ \text{Zero-Payload Early Prefix Extraction ($K \in \{3, 5, 10\}$ packets)} \\
&+ \text{Formal Temperature-Calibrated Selective Prediction (bounded error risk)} \\
&+ \text{Leakage-Aware Parent-Isolated Multi-Environment Splitting} \\
&+ \text{Real-Time Physical Npcap Hardware Operation}
\end{aligned}$$
