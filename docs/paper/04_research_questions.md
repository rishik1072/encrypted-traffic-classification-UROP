# Chapter 4: Research Questions

To systematically investigate the empirical boundaries and operational viability of zero-payload encrypted traffic classification, this study is structured around six formal research questions.

---

### RQ1: In-Domain Baseline Fidelity & Estimator Trade-offs
> **"What is the true baseline classification fidelity of lightweight machine learning models on real encrypted network traffic under strict group-aware session isolation, and what are the multi-objective trade-offs between linear, shallow tree, and ensemble architectures?"**

- **Motivation:** Prior academic studies routinely report Macro-F1 scores exceeding 0.95, yet these results are predominantly obtained using synthetic traffic fixtures or random flow splitting that leaks session identity. RQ1 seeks to establish the true empirical baseline on real physical traffic under strict session isolation, evaluating whether complex tree ensembles (Random Forest, LightGBM) justify their latency overhead compared to ultra-fast single Decision Trees or linear models.
- **Evaluation Regimes:** Group-aware stratified session splitting (70% Train, 15% Validation, 15% Locked Test) on `dataset_v2`.
- **Target Experiment:** `EXP-R09`.

---

### RQ2: Feature Family Discriminative Power & Dimensionality Trade-offs
> **"Which statistical feature families carry the greatest discriminative density for encrypted traffic classification, and what is the quantitative relationship between feature subset size ($K$) and test generalization?"**

- **Motivation:** High-dimensional feature sets (e.g., 80+ features) introduce substantial computational overhead during per-flow state updates and can induce the curse of dimensionality. RQ2 systematically evaluates the independent performance of six distinct feature families (Packet Size, Timing/IAT, Volume Counts, Byte Ratios, Directionality, and Bursts) and determines the Pareto-optimal feature subset size $K \in \{3, 5, 10, 15, 20, 30, 84\}$.
- **Target Experiment:** `EXP-R10`.

---

### RQ3: Domain-Shift Robustness & Tunnel Asymmetry
> **"How robust are zero-payload classifiers when evaluated under realistic operational distribution shifts—including unseen capture files, unseen user sessions, chronological temporal drift, unseen physical transmission media (Ethernet, Cellular), and unadapted WireGuard/WARP tunnel encapsulation?"**

- **Motivation:** Production classifiers are rarely deployed in environments identical to their training data. Network conditions, physical interfaces, and encapsulation layers change dynamically. RQ3 evaluates model resilience across eight distinct distribution-shift regimes, with particular emphasis on quantifying the performance degradation caused by fixed-MTU WireGuard tunnel padding.
- **Target Experiment:** `EXP-R11` (Regimes 01 through 08b).

---

### RQ4: Early-Stage Classification & Physical Delay Hierarchy
> **"How early in the lifecycle of an encrypted flow can an accurate classification decision be made, and how does the physical packet observation delay on the wire compare to algorithmic feature extraction and inference latency?"**

- **Motivation:** Network management operations require decisions within the opening moments of a connection. Waiting for full-flow completion introduces unacceptable operational delay. RQ4 investigates classification fidelity across discrete packet observation prefixes ($N \in \{3, 5, 10, 20, 30, 50, \text{full}\}$), explicitly decomposing end-to-end decision time into physical packet arrival delay versus computational inference time.
- **Target Experiment:** `EXP-R12`.

---

### RQ5: Calibrated Selective Classification & Risk Reduction
> **"Can a validation-calibrated confidence threshold monotonically reduce decision error on accepted flows, and how well-calibrated are the posterior probability estimates of lightweight estimators on real traffic?"**

- **Motivation:** In high-security environments, making an incorrect classification is far more damaging than abstaining. By implementing a confidence-gated rejection mechanism ($\tau$), the classifier can withhold decisions on ambiguous or out-of-distribution flows. RQ5 evaluates whether confidence thresholds tuned on validation data reliably reduce error rates on locked test sets, measuring Expected Calibration Error (ECE) and Brier scores.
- **Target Experiment:** `EXP-R13`.

---

### RQ6: Edge Computational Efficiency & Production Viability
> **"What are the empirical computational costs (cold start, warm inference, memory footprint, CPU time, and line-rate throughput) of lightweight classifiers on standard commodity x64 hardware, and can an end-to-end zero-payload streaming pipeline operate in real time without payload persistence?"**

- **Motivation:** Real-time edge deployment requires sub-millisecond execution, minimal memory consumption, and strict compliance with privacy standards. RQ6 benchmarks cold-start versus warm-state inference latency, per-stage computational bottlenecks (feature extraction vs. scaling vs. inference), CPU core utilization, and verifies the complete streaming capture-to-dashboard pipeline under zero-payload security invariants.
- **Target Experiments:** `EXP-R14` and `EXP-R15`.
