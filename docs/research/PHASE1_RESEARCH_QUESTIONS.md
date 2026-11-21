# Phase 1 Formal Research Questions and Measurable Hypotheses

**Project**: Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models  
**Document**: Authoritative Experimental Protocol  
**Date**: November 2026  
**Status**: Authoritative Scientific Protocol

---

## 1. Context and Motivation

Following the systematic literature review and forensic codebase audit, four critical scientific uncertainties must be resolved through empirical experimentation:
1. The extent to which zero-payload statistical features generalize across independent physical sessions and network environments when data leakage is strictly eliminated.
2. The exact functional relationship between early packet observation horizons ($K$) and classification performance.
3. The degree to which post-hoc probability calibration and selective prediction can bound empirical error risk during early packet observation.
4. The computational and latency trade-offs imposed by online feature extraction and calibrated selective gating in a live operating system environment.

---

## 2. Refined Research Questions (RQs)

### **RQ1 (Generalization & Environment Shift)**:
> *To what extent does a lightweight zero-payload tree ensemble maintain classification performance when evaluated across strictly session-disjoint, parent-isolated, and cross-environment physical network captures?*
- **Focus**: Quantifying the genuine generalization gap between random splitting, session-isolated splitting, and physical cross-environment transfer (Wi-Fi 6 $\to$ Ethernet $\to$ Cellular).

### **RQ2 (Temporal Early Observation Dynamics)**:
> *How does classification performance (Macro-F1, Balanced Accuracy) scale as a function of the packet observation horizon ($K \in \{3, 5, 10, \text{full}\}$), and what is the minimum packet prefix required to achieve statistically significant discrimination across encrypted application classes?*
- **Focus**: Mapping the temporal frontier of zero-payload classification from the initial TLS handshake to full-flow termination.

### **RQ3 (Calibrated Selective Risk Reduction)**:
> *Can horizon-dependent probability calibration (Temperature Scaling) and selective prediction with an abstention option strictly bound empirical classification risk ($\operatorname{Risk} \le \alpha$) on incomplete early-packet prefixes without reducing operational coverage below acceptable utility bounds ($\operatorname{Coverage} \ge 50\%$)?*
- **Focus**: Determining whether calibrated abstention successfully converts early-packet misclassifications into deferred decisions (`LOW_CONFIDENCE` / `UNKNOWN`).

### **RQ4 (Real-Time Systems & Computational Feasibility)**:
> *What are the empirical latency, memory footprint, and CPU throughput trade-offs of integrating multi-stage prefix feature extraction and calibrated selective gating into a live Npcap packet ingestion pipeline on commodity x86_64 hardware?*
- **Focus**: Measuring actual wire delay, feature extraction latency, model inference time, and total single-threaded throughput in flows per second.

---

## 3. Formally Formulated Measurable Hypotheses (H1–H4)

### Hypothesis 1: Environment Generalization Gap
$$\mathcal{H}_{1, \text{null}}: \text{Macro-F1}_{\text{cross-env}} = \text{Macro-F1}_{\text{in-env}}$$
$$\mathcal{H}_{1, \text{alt}}: \text{Macro-F1}_{\text{cross-env}} < \text{Macro-F1}_{\text{in-env}}$$
- **Hypothesis Statement**: When evaluated under strict parent-isolated splitting, transferring a classifier trained on physical Wi-Fi traffic to an unseen physical network environment (Cellular or Ethernet) results in a statistically significant degradation in Macro-F1 score due to network-induced jitter and timing shifts.
- **Independent Variable**: Evaluation partition structure (In-Environment Session-Disjoint vs. Cross-Environment Physical Transfer).
- **Dependent Variables**: Macro-F1 score, Balanced Accuracy, Per-Class Recall.
- **Controlled Variables**: Feature representation (21 canonical statistical features), model hyperparameter configuration, class prior balance, random seed (`seed = 42`).
- **Dataset Requirements**: Dedicated multi-environment dataset (`dataset_v3`) with at least 50 genuine physical flows per class captured across Wi-Fi 6, Gigabit Ethernet, and 4G/5G Cellular.
- **Statistical Test**: Two-tailed Wilcoxon signed-rank test across 10 stratified cross-validation folds ($\alpha = 0.01$).
- **Success Criteria**: Rejection of the null hypothesis ($p < 0.01$) and quantitative characterization of the environment generalization delta ($\Delta_{\text{env}}$).

---

### Hypothesis 2: Temporal Packet Horizon Progression
$$\mathcal{H}_{2, \text{null}}: \text{Macro-F1}(K=3) = \text{Macro-F1}(K=5) = \text{Macro-F1}(K=10) = \text{Macro-F1}(\text{full})$$
$$\mathcal{H}_{2, \text{alt}}: \text{Macro-F1}(K=3) < \text{Macro-F1}(K=5) < \text{Macro-F1}(K=10) \le \text{Macro-F1}(\text{full})$$
- **Hypothesis Statement**: Classification Macro-F1 increases monotonically as the packet observation horizon expands from $K=3$ to $K=10$, with diminishing marginal returns between $K=10$ and full-flow observation.
- **Independent Variable**: Packet prefix horizon ($K \in \{3, 5, 10, \text{full}\}$).
- **Dependent Variables**: Macro-F1, Micro-Accuracy, Log-Loss.
- **Controlled Variables**: Test set flows, model architecture (LightGBM), feature extraction logic.
- **Dataset Requirements**: Complete packet-level timestamp and length traces for all flows in the benchmark.
- **Statistical Test**: Friedman test across packet horizons with post-hoc Nemenyi pairwise tests ($\alpha = 0.05$).
- **Success Criteria**: Statistically significant performance difference between $K=3$ and $K=10$ ($p < 0.05$), with $K=10$ achieving within $10\%$ of full-flow Macro-F1.

---

### Hypothesis 3: Selective Risk Bounding via Calibration
$$\mathcal{H}_{3, \text{null}}: \operatorname{Risk}_{\text{accepted}}(\tau^*, K=3) \ge \operatorname{Risk}_{\text{unselective}}(K=3)$$
$$\mathcal{H}_{3, \text{alt}}: \operatorname{Risk}_{\text{accepted}}(\tau^*, K=3) < \operatorname{Risk}_{\text{unselective}}(K=3) \quad \text{at} \quad \operatorname{Coverage} \ge 50\%$$
- **Hypothesis Statement**: Applying temperature-calibrated selective prediction at optimal threshold $\tau^*$ on early packet prefixes ($K=3$) significantly reduces empirical classification risk on accepted flows compared to unselective classification, while preserving at least $50\%$ operational coverage.
- **Independent Variable**: Selective decision policy (Unselective $\tau=0.0$ vs. Calibrated Selective $\tau = \tau^*$).
- **Dependent Variables**: Empirical Risk ($\text{Error Rate} = 1 - \text{Selective Accuracy}$), Coverage ($\gamma$), Expected Calibration Error (ECE).
- **Controlled Variables**: Observation horizon ($K=3$), training/validation split ratio (70/15/15), temperature parameter fitting protocol.
- **Dataset Requirements**: Held-out validation split with zero prototype overlap for fitting temperature $T$ and selecting $\tau^*$; locked test split for evaluation.
- **Statistical Test**: One-tailed paired $t$-test / DeLong test on risk curves across test folds ($\alpha = 0.01$).
- **Success Criteria**: Statistically significant reduction in empirical risk on accepted flows ($p < 0.01$) with coverage $\ge 50\%$, and reduction of test ECE from $> 15\%$ to $< 5\%$.

---

### Hypothesis 4: Feature Extraction as the System Bottleneck
$$\mathcal{H}_{4, \text{null}}: \bar{t}_{\text{extraction}} \le \bar{t}_{\text{inference}}$$
$$\mathcal{H}_{4, \text{alt}}: \bar{t}_{\text{extraction}} > 3 \times \bar{t}_{\text{inference}}$$
- **Hypothesis Statement**: In a live CPU-based pipeline, Python feature extraction latency exceeds machine learning model inference latency by at least a factor of 3, representing the primary throughput-limiting bottleneck of the classification system.
- **Independent Variable**: Pipeline execution stage (Feature Extraction vs. Model Inference).
- **Dependent Variables**: Mean latency (ms), median latency (ms), throughput (flows per second).
- **Controlled Variables**: Hardware testbed (Intel Core i7 / Windows 11 host), feature profile (21 canonical features), batch size ($N=1$ single flow).
- **Dataset Requirements**: Live physical packet capture streams and pre-recorded high-volume PCAP replays.
- **Statistical Test**: Paired Welch's $t$-test across 500 warm benchmark repetitions ($\alpha = 0.001$).
- **Success Criteria**: Rejection of the null hypothesis confirming that feature extraction accounts for $> 75\%$ of end-to-end execution latency, validating the architectural necessity for online $O(1)$ streaming accumulators.
