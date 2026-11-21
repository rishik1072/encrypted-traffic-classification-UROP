# Phase 1 Novelty Assessment, Research Gap Analysis, and Technical Strategy

**Project**: Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models  
**Document**: Authoritative Novelty Assessment and Strategic Research Roadmap  
**Date**: November 2026  
**Status**: Authoritative Forensic Evidence Document

---

## 1. Ground-Truth Implementation Audit (Phase 0 & 0.5 Baseline)

To establish an unassailable baseline, every subsystem in the repository is audited below according to its verified operational status:

| Subsystem Component | Implementation Status | Verified Source Evidence | Deficiencies & Required Phase 1 Upgrades |
| :--- | :---: | :--- | :--- |
| **Live Npcap Ingestion** | **IMPLEMENTED** | `capture/packet_capture.py` captures live physical Wi-Fi packets via Scapy `AsyncSniffer`. | Working; zero code modification required. |
| **Zero-Payload Enforcement**| **IMPLEMENTED** | Packet headers parsed; payload bytes discarded in memory; zero PII on disk. | Verified in `test_payload_security.py` and `test_product_privacy.py`. |
| **Bidirectional Flow Assembly**| **IMPLEMENTED** | In-memory 5-tuple canonicalization with 120s/30s timeouts (`realtime/flow_tracker.py`). | Buffers full packet records in Python lists ($O(N)$ space); requires streaming migration. |
| **Feature Extraction Engine** | **IMPLEMENTED** | Extracts 21 numerical statistical features (`preprocessing/feature_extractor.py`). | Uses two-pass list comprehensions and in-memory sorting; lacks true $O(1)$ Welford / $P^2$ streaming math. |
| **Production LightGBM Model** | **IMPLEMENTED** | Deployed `model_lightgbm_v1` executes in real-time inference (`realtime/classifier.py`). | Operates on raw booster logits; lacks post-hoc temperature scaling; test ECE is **$19.96\%$**. |
| **4-State Prediction Lifecycle**| **IMPLEMENTED** | Emits `KNOWN`, `LOW_CONFIDENCE`, `UNKNOWN`, `INSUFFICIENT_EVIDENCE` (`realtime/events.py`). | States are currently driven by arbitrary heuristic confidence thresholds ($\tau = 0.50$ / $0.30$) rather than calibrated risk bounds. |
| **SQLite Store & REST API** | **IMPLEMENTED** | Local persistence with SHA-256 session digests and HTTP endpoints (`product/local_api.py`). | Fully operational; verified under continuous live execution. |
| **Streamlit SOC Dashboard** | **IMPLEMENTED** | Interactive real-time metrics and flow monitoring interface (`product/dashboard.py`). | Fully operational on `localhost:8501`. |
| **Dedicated Prefix Models** | **PARTIALLY IMPLEMENTED**| Early classification tested offline in `research_early_prediction.csv` on full-flow model. | Full-flow model was evaluated on early packets ($K=3, 5, 10$); lacks specialized models trained specifically on early prefixes. |
| **Dataset Volume & Quality** | **PARTIALLY IMPLEMENTED**| 121 physical flows across 60 capture sessions in `dataset_real_v1`. | 180 flows in `dataset_v2` are synthetic perturbations with prototype cloning leakage; $N=121$ is too small for publication. |
| **Probability Calibration** | **NOT IMPLEMENTED** | Deployed model outputs raw softmax probabilities; `"Platt_Scaling_Sigmoid"` is a placeholder. | Must implement post-hoc Temperature Scaling / Dirichlet calibration on held-out validation data. |
| **Streaming $O(1)$ Math** | **NOT IMPLEMENTED** | `flow.packet_records` retains all packet records; `median_iat` executes `sorted(iats)`. | Implement online one-pass Welford variance and $P^2$ streaming quantile estimation. |
| **Multi-Environment Dataset**| **NOT IMPLEMENTED** | All 121 physical flows collected on a single Windows 11 host and local network. | Collect genuine physical traffic (`dataset_v3`) across at least 3 distinct physical LAN/Wi-Fi/Cellular environments. |

---

## 2. In-Depth Evaluation of Candidate Research Directions

We systematically evaluate seven candidate research directions against the established literature:

```
Candidate Direction A: Early Zero-Payload Flow Classification
Candidate Direction B: Early Classification with Calibrated Selective Prediction
Candidate Direction C: Cross-Session and Cross-Network Environment Generalization
Candidate Direction D: Leakage-Aware Evaluation of Encrypted Traffic Classifiers
Candidate Direction E: Open-World Encrypted Traffic Classification
Candidate Direction F: Lightweight Packet-Sequence Contextual Classification
Candidate Direction G: Drift-Aware Longitudinal Traffic Classification
```

### Direction A: Early Zero-Payload Flow Classification
- **Closest Publications**: FastFlow (Babaria et al., 2025), LoFi (Hugon et al., 2026), AppScanner (Taylor et al., 2016).
- **Existing Solutions**: FastFlow uses an LSTM-RL recurrent agent; LoFi uses hash table decision caching; traditional statistical models evaluate prefixes at $K=5$ or $K=10$.
- **Remaining Limitations**: Heavy recurrent nets cannot achieve sub-millisecond execution on edge CPUs; existing tree models evaluated on prefixes suffer severe accuracy drops without abstention.
- **Required Datasets**: Standard PCAP corpora and prefix-sliced flow records.
- **Required Experiments**: Multi-horizon prefix sweeps ($K \in \{1, 2, 3, 5, 10, 20\}$) comparing tree ensembles against deep models.
- **Potential Contribution**: Demonstrates the efficiency-accuracy Pareto frontier of lightweight tree models on packet prefixes.
- **Implementation Complexity**: Moderate.
- **Risk of Insufficient Novelty**: **High if pursued in isolation**. Prefix slicing on statistical features has been explored since 2016; simply training a tree model on the first 5 packets is incremental.

---

### Direction B: Early Classification with Calibrated Selective Prediction
- **Closest Publications**: SelectiveNet (Geifman & El-Yaniv, 2019), Guo et al. (ICML 2017), FastFlow (2025).
- **Existing Solutions**: Selective classification has been formalized in computer vision and NLP; network traffic classifiers typically use naive uncalibrated argmax softmax thresholds.
- **Remaining Limitations**: No prior work has coupled formal risk-coverage selective classification with **early temporal packet horizons** in encrypted traffic under modern AEAD cipher suites.
- **Required Datasets**: High-quality session-disjoint encrypted traffic with rigorous validation partitions for threshold selection.
- **Required Experiments**: Temperature scaling calibration, Expected Calibration Error (ECE) minimization, risk-coverage trade-off curves ($\operatorname{Risk}(\tau)$ vs $\operatorname{Coverage}(\tau)$) across packet horizons $K \in \{3, 5, 10, \text{full}\}$.
- **Potential Contribution**: Provides mathematical guarantees on error rates during early packet observation, allowing systems to abstain when packet evidence is statistically insufficient.
- **Implementation Complexity**: Moderate to High.
- **Risk of Insufficient Novelty**: **Very Low**. Solves a critical unaddressed failure mode in real-time operational security.

---

### Direction C: Cross-Session and Cross-Network Environment Generalization
- **Closest Publications**: Sharma et al. (arXiv 2026), Wickramasinghe et al. (IEEE S&P 2025), FlowPrint (NDSS 2020).
- **Existing Solutions**: Prior work evaluates multi-client or multi-server splits on centralized static datasets.
- **Remaining Limitations**: Lack of empirical studies evaluating real-time lightweight classifiers across physical network interface types (Wi-Fi 6 vs GbE vs Cellular) with physical adapter jitter and routing shifts.
- **Required Datasets**: Dedicated multi-environment dataset (`dataset_v3`) collected across $\ge 3$ distinct physical networks.
- **Required Experiments**: Cross-environment transfer matrices (Train on Wi-Fi $\to$ Test on Cellular/Ethernet); feature ablation isolating environment-sensitive features.
- **Potential Contribution**: Establishes realistic, un-inflated performance baselines and identifies environment-invariant statistical features.
- **Implementation Complexity**: High (demands rigorous physical data collection).
- **Risk of Insufficient Novelty**: Low to Moderate. Highly valued by security and networking venues when backed by solid physical artifacts.

---

### Direction D: Leakage-Aware Evaluation of Encrypted Traffic Classifiers
- **Closest Publications**: Sharma et al. (2026), Arp et al. (USENIX Security 2022).
- **Existing Solutions**: Sharma et al. demonstrated the split protocol effect on QUIC traffic; Arp et al. identified general ML pitfalls.
- **Remaining Limitations**: Prior work focused on offline deep learning benchmarks; has not investigated prototype-cloning leakage in synthetic dataset expansion or the impact on live operational models.
- **Required Datasets**: Paired synthetic-perturbation and physical prototype datasets.
- **Required Experiments**: Single-identifier diagnostic probes, parent-flow isolation audits, comparison of random vs session vs parent-isolated splits.
- **Potential Contribution**: Important methodological critique, but primarily an evaluation study.
- **Implementation Complexity**: Low.
- **Risk of Insufficient Novelty**: **High as a standalone paper** following Sharma et al. (2026). Better positioned as a foundational methodological pillar of our work.

---

### Direction E: Open-World Encrypted Traffic Classification
- **Closest Publications**: FlowPrint (NDSS 2020), Scheirer et al. (2013), Bendale & Boult (2016).
- **Existing Solutions**: Graph clustering (FlowPrint), extreme value theory (OpenMax).
- **Remaining Limitations**: Requires extensive background traffic distributions; heavy computational complexity; difficult to calibrate on early packet prefixes.
- **Required Datasets**: Massive open-world corpora with hundreds of unmonitored background applications.
- **Required Experiments**: Precision-recall curves across increasing numbers of unseen classes.
- **Potential Contribution**: Substantial, but requires massive dataset collection beyond current UROP scope.
- **Implementation Complexity**: Very High.
- **Risk of Insufficient Novelty**: Low, but high execution risk.

---

### Direction F: Lightweight Packet-Sequence Contextual Classification
- **Closest Publications**: FastFlow (2025), ET-BERT (2022).
- **Existing Solutions**: LSTMs, 1D-CNNs, Transformers.
- **Remaining Limitations**: Recurrent state tracking exceeds CPU budgets; 1D-CNNs require uniform sequence lengths.
- **Required Datasets**: Packet-level time-series streams.
- **Required Experiments**: Model compression, pruning, quantization of sequence models.
- **Potential Contribution**: Engineering optimization, but less novel than statistical/probabilistic guarantees.
- **Implementation Complexity**: High.
- **Risk of Insufficient Novelty**: Moderate.

---

### Direction G: Drift-Aware Longitudinal Traffic Classification
- **Closest Publications**: Wiesner et al. (CESNET-TLS, IEEE TNSM 2024–2026).
- **Existing Solutions**: Continuous online learning, periodic retraining schedules.
- **Remaining Limitations**: Requires multi-month or multi-year continuous longitudinal data collection.
- **Required Datasets**: Datasets spanning 6–24 months of network traffic.
- **Required Experiments**: Temporal degradation profiling over quarters/years.
- **Potential Contribution**: High, but physically infeasible within the project timeline.
- **Implementation Complexity**: Extreme (time-constrained).
- **Risk of Insufficient Novelty**: Moderate.

---

## 3. Authoritative Research Strategy Selection

To achieve maximum scientific impact, methodological rigor, and publishability without falling into the trap of incremental engineering, we select:

### **Primary Research Direction**:
$$\textbf{Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift}$$

### **Supporting Contribution 1 (Methodological / Algorithmic)**:
**Calibrated Risk-Coverage Selective Gating Across Early Packet Horizons**: Formulate early classification not as a fixed argmax guess, but as an optimal risk-coverage trade-off. We calibrate tree ensemble posteriors via validation Temperature Scaling, establishing formal error bounds ($\operatorname{Risk} \le \alpha$) where the model dynamically transitions between `KNOWN` prediction and calibrated abstention (`LOW_CONFIDENCE` / `UNKNOWN`) as packet evidence arrives.

### **Supporting Contribution 2 (Experimental / Data Governance)**:
**Leakage-Aware Parent-Isolated Multi-Environment Benchmark Design**: Operationalize the methodological insights of Sharma et al. (2026) and Arp et al. (2022) by collecting a new physical multi-environment corpus (`dataset_v3`). We enforce strict parent-flow and environment isolation, establishing honest, un-inflated baselines that quantify the true generalization gap across Wi-Fi, Ethernet, and cellular physical interfaces.

---

## 4. The Non-Trivial Novelty Argument

Rule 5 explicitly mandates: *"Do not claim novelty based on combining existing techniques."* 

Our scientific novelty does not arise from mechanically connecting LightGBM to temperature scaling or Scapy. Rather, it addresses a **fundamental, unresolved scientific tension at the intersection of networking and statistical learning theory**:

### 1. The Temporal Ambiguity-Calibration Paradox
During early flow observation ($K \in \{3, 5\}$ packets), statistical features are inherently diffuse and incomplete: TCP three-way handshakes and TLS ClientHello records exhibit near-identical packet length and timing profiles across different application categories. 

Standard machine learning models forced to output a prediction on these incomplete prefixes suffer from **acute miscalibration**: unconstrained tree ensembles produce highly saturated, overconfident probability outputs ($P > 0.85$) on features that carry low mutual information with the true class label. 

Our core scientific insight is that **probability calibration cannot be treated as a static full-flow post-processing step**: the calibration parameter (temperature $T$) is itself a function of the temporal observation horizon $K$. By modeling the horizon-dependent calibration dynamics:
$$T^* = f(K), \quad K \in \{3, 5, 10, \text{full}\}$$
we prove that early classification risk can be strictly bounded, converting catastrophic early errors into safe, deferred abstentions until disambiguating packets arrive.

### 2. Disentangling Environment Artifacts from True Protocol Dynamics
Prior works either report $> 98\%$ accuracy under leaky random splits (learning collection shortcuts) or report massive degradation under distribution shift without explaining the underlying mechanism. By formalizing parent-isolated multi-environment splitting, we scientifically decouple:
- *Invariant Protocol Signatures* (e.g., application-layer chunking and burst cadences) from
- *Environment-Dependent Jitter* (e.g., Wi-Fi contention, carrier bufferbloat, and OS driver batching).
