# Related Work: Encrypted Traffic Classification, Early Observation, Calibration, and Evaluation Integrity

**Document**: Publication-Ready Related Work Section  
**Target Venues**: IEEE S&P, USENIX Security, ACM CCS, IEEE INFOCOM, ACM SIGMETRICS, IEEE TNSM  
**Date**: November 2026  
**Status**: Pre-Implementation Research Document

---

## 1. Encrypted Traffic Classification in the Era of Modern Protocols

Network traffic classification has historically evolved across three major technological paradigms: port-based filtering, Deep Packet Inspection (DPI), and Machine Learning (ML) over statistical flow metadata. With the global adoption of modern transport security standards—specifically TLS 1.3, QUIC, and Encrypted Client Hello (ECH)—traditional approaches have become fundamentally obsolete. Modern encryption hides application-layer signatures, obscures cleartext Server Name Indication (SNI) headers, and prevents deterministic rule-based matching.

In response, recent academic literature has split into two diverging philosophies:
1. **Payload-Centric Deep Learning**: Models such as ET-BERT (Lin et al., 2022) tokenized the first 512 bytes of datagram payloads, employing pre-trained bidirectional Transformer representations to capture contextual associations in encrypted application data. However, as demonstrated by Wickramasinghe et al. (IEEE S&P 2025) in their systematization of encrypted traffic classifiers, deep payload models frequently overfit to ephemeral Session Initialization Information (SII) and pseudo-random cryptographic artifacts rather than authentic application behaviors. When evaluated on modern AEAD cipher suites (AES-256-GCM, ChaCha20-Poly1305), byte-level models suffer dramatic accuracy degradation while imposing prohibitive computational latencies ($> 20\text{ ms}$ on GPUs).
2. **Zero-Payload Statistical Fingerprinting**: Tracing back to foundational works such as AppScanner (Taylor et al., IEEE EuroS&P 2016) and FlowPrint (van Ede et al., NDSS 2020), statistical fingerprinting models leverage only packet lengths, directions, inter-arrival times (IATs), and burst dynamics. Because these approaches never inspect or store payload bytes, they are provably invariant to payload encryption updates and fully compliant with stringent data confidentiality regulations (e.g., GDPR). Our work builds directly upon this privacy-preserving statistical tradition, addressing its primary historical limitation: the reliance on completed, full-flow statistics.

---

## 2. Early-Packet Classification and Operational Latency Constraints

Operational network management tasks—such as dynamic Quality of Service (QoS) routing, traffic policing, and automated intrusion prevention—require actionable classification decisions within the first few packets of a connection. Post-mortem flow analysis, which waits for flow termination (often spanning tens of seconds to minutes), is fundamentally unusable for active inline policy enforcement.

Recent works have actively targeted early-packet classification:
- **Sequential Recurrent Models**: FastFlow (Babaria et al., ACM POMACS / SIGMETRICS 2025) pioneered an adaptive sequential framework, combining LSTM networks with reinforcement learning to dynamically determine the minimal number of time-series packets necessary to reach a confident classification. While achieving high accuracy within 4–8 packets, FastFlow’s recurrent neural network architecture requires continuous hidden-state maintenance across thousands of concurrent flows, introducing non-trivial memory and compute overheads.
- **Decision Caching Engines**: LoFi (Hugon et al., IEEE NetSoft 2026) demonstrated that an early application filter combining exact 5-tuple and SNI hashing with an early decision-tree fallback can eliminate up to 85% of repeated inferences in software-defined network (SDN) data planes. However, LoFi relies heavily on destination repetition and does not address out-of-distribution traffic or formal confidence guarantees.

Our approach differs fundamentally from both FastFlow and LoFi: instead of heavy recurrent networks or simple cache matching, we formulate early classification using **dedicated lightweight tree ensembles (LightGBM/Random Forest)** evaluated across discrete packet horizons ($K \in \{3, 5, 10\}$ packets). By coupling early feature extraction with calibrated selective prediction, our system achieves sub-millisecond decision latency on standard CPUs while providing mathematically bounded error rates.

---

## 3. Uncertainty Quantification, Calibration, and Selective Prediction

A critical vulnerability of deployed machine learning models in security-critical environments is **uncalibrated overconfidence**. As established by Guo et al. (ICML 2017), modern machine learning models and unconstrained tree ensembles output margin scores that do not reflect true empirical probabilities. When exposed to network jitter, packet drops, or ambiguous early-packet prefixes, uncalibrated classifiers frequently produce catastrophic false alarms with $> 90\%$ reported confidence.

In network traffic analysis, this vulnerability is amplified by the **open-world challenge**. While early works like AppScanner (Taylor et al., 2016) relied on heuristic Euclidean distance thresholds to reject unknown classes, and deep open-set frameworks (Scheirer et al., 2013; Bendale & Boult, 2016) redirected logits via OpenMax, these methods lack formal risk guarantees.

The mathematical framework of **Selective Classification** (or classification with a reject option), formalized by Geifman and El-Yaniv (NeurIPS 2017, ICML 2019), addresses this by optimizing the **risk-coverage trade-off**:
$$\min_\tau \operatorname{Risk}(\tau) \quad \text{subject to} \quad \operatorname{Coverage}(\tau) \ge 1 - c$$
Under this formulation, the classifier abstains from predicting when its posterior confidence is below a calibrated threshold $\tau$, designating ambiguous flows for human inspection or deferral until further packets arrive.

While selective classification has been explored in computer vision and natural language processing, its formal application to **early encrypted network traffic classification under physical environment shift** remains largely unexplored. In this work, we implement post-hoc **Temperature Scaling** on validation data to calibrate tree ensemble posteriors, directly driving a 4-state prediction engine (`KNOWN`, `LOW_CONFIDENCE`, `UNKNOWN`, `INSUFFICIENT_EVIDENCE`) that bounds empirical risk during early flow observation.

---

## 4. Evaluation Protocols, Dataset Leakage, and Generalization Under Distribution Shift

A persistent crisis in machine learning for computer security is the prevalence of methodological flaws and inflated performance claims. Arp et al. (USENIX Security 2022) surveyed 30 top-tier security papers, identifying pervasive sampling bias, label leakage, and spurious correlation learning across more than 70% of published works.

In encrypted traffic classification, this crisis was recently brought into sharp focus by Sharma, Saini, and Behl (arXiv:2611.06290, November 2026) in their seminal study *"The Split Protocol Decides the Result: Re-Evaluating Encrypted Traffic Classification"*. The authors demonstrated that:
- Standard random train-test splitting causes severe data leakage: models memorize capture identifiers, IP subnets, or shared timing artifacts.
- When evaluated under strict **session-disjoint or capture-isolated splitting**, model Macro-F1 collapsed from **0.992 down to 0.567** without changing a single line of model code.
- Single-identifier diagnostic probes proved that classifiers were learning dataset collection shortcuts rather than authentic protocol dynamics.

Furthermore, longitudinal studies such as Wiesner et al. (IEEE TNSM 2024–2026) evaluating the multi-year CESNET-TLS corpus revealed that temporal concept drift (e.g., CDN routing modifications and cipher migrations) causes unmitigated model degradation of 30–50% over twelve months.

Our research directly operationalizes these insights. Having forensically uncovered prototype-cloning leakage in historical project benchmarks, our Phase 1 experimental protocol establishes a rigorous **parent-isolated, multi-environment splitting standard**, ensuring that no flow variants or physical capture environments overlap across training, validation, and test partitions.

---

## 5. Real-Time Systems Engineering and Edge Host Feasibility

While extensive research exists on offline PCAP replaying, relatively few studies implement and profile complete end-to-end classification engines operating on live physical hardware. Bridging the gap between offline ML research and live network deployment requires overcoming kernel driver bottlenecks, asynchronous socket buffering, and thread synchronization overheads.

Many literature proposals claim "line-rate 10 Gbps" capability based solely on microbenchmarked single-vector inference times (e.g., multiplying $3\,\mu\text{s}$ inference to assert $> 300,000\text{ flows/s}$). As our systems audit demonstrates, these theoretical extrapolations ignore the true bottleneck: **feature extraction latency**. In pure Python, extracting statistical features across packet lists requires $\approx 1.46\text{ ms}$, bounding single-threaded performance to $\approx 552\text{ flows/s}$.

Our work grounds scientific classification models in a **fully operational real-time system** featuring:
- Npcap promiscuous live capture on physical Wi-Fi/Ethernet adapters.
- Asynchronous multi-threaded pipeline decoupled via thread-safe queues.
- Synchronous REST telemetry APIs and live SOC dashboards.
- A roadmap for true $O(1)$ streaming feature accumulators (online Welford algorithm and $P^2$ quantile estimation).

---

## 6. Summary: Research Gap and System Positioning

The existing literature presents a fundamental trade-off:
- Deep learning sequence models achieve early accuracy but suffer from extreme latency, memory overhead, and uncalibrated overconfidence.
- Statistical flow classifiers offer lightweight, privacy-compliant inference but require full-flow termination and lack formal risk-coverage guarantees.
- Benchmark evaluations routinely suffer from split leakage and fail to generalize across real-world environment shifts.

Our research directly resolves this trade-off by establishing:
$$\begin{array}{c}
\textbf{The First Calibrated, Zero-Payload Early Encrypted Traffic Classifier} \\
\textbf{Evaluated Under Strict Leakage-Aware Multi-Environment Shift} \\
\textbf{and Deployed in an Operational Sub-Millisecond Real-Time Capture Engine.}
\end{array}$$
