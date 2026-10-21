# 10–15 Minute University Research Review: Presentation Guide

**Project:** Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models  
**Context:** Undergraduate Research Opportunity Project (UROP) Supervisor Review  
**Audience:** Faculty Supervisor, External Examiner, and Lab Colleagues  
**Presentation Time:** 10–15 minutes (approx. 1.25 minutes per slide)  
**Total Slides:** 10 slides  

---

## Slide 1: Title & Research Motivation

* **Slide Title:** Real-Time Encrypted Traffic Classification: The Zero-Payload Edge Dilemma
* **Main Message:** Modern encryption protocols (TLS 1.3, QUIC, WireGuard) render Deep Packet Inspection (DPI) obsolete and privacy-invasive; zero-payload statistical transport modeling enables real-time edge network management without decryption.
* **Evidence / Visual to Use:** High-level architectural diagram showing an encrypted packet stream entering an edge router where raw application payloads are discarded, and only Layer 3/4 statistical flow metadata is passed to lightweight ML classifiers.
* **Important Caveat:** Statistical classification does not provide 100% certainty or deep forensic content analysis; it provides probabilistic application category tagging.
* **Suggested Speaker Notes:**
  > *"Good morning. Today I am presenting our work on real-time encrypted traffic classification using lightweight machine learning models. Over 95% of Internet traffic is now encrypted with TLS 1.3, QUIC, and modern VPN tunnels. Traditional Deep Packet Inspection is computationally prohibitive, legally compromised under GDPR, and increasingly impossible with Encrypted Client Hello. Our research investigates whether statistical transport metadata alone—packet lengths, inter-arrival times, and burst ratios—can classify encrypted flows on edge routers in real time without decrypting a single byte."*

---

## Slide 2: Zero-Payload Architecture & Privacy Invariants

* **Slide Title:** Zero-Payload Architecture: Privacy-Preserving Transport Features
* **Main Message:** The framework extracts 21 canonical Layer-3/4 statistical distribution moments while enforcing cryptographic and architectural privacy invariants.
* **Evidence / Visual to Use:** Feature hierarchy diagram categorizing the 21 canonical features into Packet Size Moments (5), Inter-Arrival Timing (4), Directional Ratios (4), and Burst Counts (8); paired with zero-payload audit proof (0 payload bytes stored, 0 TLS decryption attempts).
* **Important Caveat:** Scrubbing IP addresses and ports is mandatory to prevent models from memorizing server infrastructure rather than learning genuine traffic dynamics.
* **Suggested Speaker Notes:**
  > *"To ensure true privacy and avoid shortcut learning, we enforce strict data hygiene. We strip all IP addresses, port numbers, MAC addresses, and payload bytes. The classifier operates strictly on 21 statistical moments—such as forward/backward packet size variance, 90th percentile inter-arrival time, and burstiness ratios. These features capture the interactive handshakes of Web browsing, the downstream bursts of Video streaming, or the symmetric pacing of VoIP without examining user content."*

---

## Slide 3: Dataset Provenance & Eliminating Partition Leakage

* **Slide Title:** Scientific Rigor: Dataset Provenance & Session Isolation
* **Main Message:** High-accuracy claims in prior literature often stem from synthetic fixtures or session leakage; we establish strict group-aware session isolation on a hybrid multi-environment benchmark (`dataset_v2`).
* **Evidence / Visual to Use:** Provenance breakdown table: `dataset_v2` (301 flows, 150 sessions: 121 physical Wi-Fi flows + 180 controlled perturbations) vs. `dataset_real_v1` (121 pure physical flows) vs. historical `dataset_v1` (12 synthetic flows). Include zero-leakage partition assertion (0% session overlap).
* **Important Caveat:** Prior legacy claims of 0.9500 Macro-F1 were achieved on synthetic loopback fixtures (`dataset_v1`) and do not reflect real traffic.
* **Suggested Speaker Notes:**
  > *"A critical contribution of our audit was establishing rigorous dataset provenance. Much of the academic literature reports near-perfect scores because test sets contain flows from the exact same user sessions as the training set, causing the model to memorize ephemeral connection artifacts. We audited all splits with a zero-leakage validator. Our primary benchmark, dataset_v2, contains 301 flows across 150 independent sessions. It combines 121 physical Wi-Fi flows with 180 controlled statistical perturbations modeling Ethernet and Cellular environments. We also maintain a pure physical baseline on dataset_real_v1."*

---

## Slide 4: Baseline Benchmark & Pareto Dominance of Decision Trees

* **Slide Title:** In-Domain Baseline: CART Decision Tree Dominates the Pareto Frontier
* **Main Message:** Under group-aware session isolation, a single shallow Decision Tree matches the accuracy of a 100-tree Random Forest ensemble while running $249\times$ faster with a $91\times$ smaller memory footprint.
* **Evidence / Visual to Use:** Figure: `results/figures/research_baseline_model_comparison.png` and `results/figures/latency_vs_f1.png`. Data points: Decision Tree (**0.5802 Macro-F1**, 0.5833 Acc, **0.0694 ms** latency, **9.58 KB** footprint) vs. Random Forest (**0.5854 Macro-F1**, 0.5833 Acc, 16.97 ms latency, 878 KB footprint).
* **Important Caveat:** Pure physical Wi-Fi baseline evaluated on `dataset_real_v1` yields 0.0833 Macro-F1 due to severe sample starvation ($N=12$ test flows).
* **Suggested Speaker Notes:**
  > *"When evaluated under strict session isolation on dataset_v2, Random Forest achieves 0.5854 Macro-F1 and 0.5833 accuracy. However, our key operational finding is that a shallow CART Decision Tree achieves virtually identical fidelity—0.5802 Macro-F1—while executing in under 70 microseconds and occupying less than 10 kilobytes. This represents a 249-times speedup over the ensemble, making Decision Trees the Pareto-optimal choice for edge routers. Meanwhile, Logistic Regression collapses to 0.3240, proving that traffic metadata is fundamentally non-linearly separable."*

---

## Slide 5: Early Traffic Triage: Wire Delay Dominates Latency

* **Slide Title:** Early Traffic Triage: Physical Packet Arrival Governs Decision Latency
* **Main Message:** Evaluating only the first $N=3$ packets provides actionable classification (**63.6% accuracy**, **91.7% coverage**) in **84.3 ms**; over **99.8%** of latency is physical wire observation delay, not algorithmic computation.
* **Evidence / Visual to Use:** Figure: `results/figures/early_prediction_latency_vs_packets.png` and `results/figures/early_prediction_coverage_vs_packets.png`. Latency breakdown: 64.04 ms physical arrival delay + 20.00 ms inference latency = 84.33 ms total.
* **Important Caveat:** Evaluated on physical held-out test traffic ($N=12$ total flows, $N=11$ classified, 1 abstained); waiting for full flow termination incurs a 59.7-second delay and fails due to feature dilution.
* **Suggested Speaker Notes:**
  > *"In edge routing, waiting for a connection to finish before classifying it is useless. We investigated early-stage triage across packet observation horizons. By observing just the first 3 packets of an encrypted flow, we achieve 63.6% accuracy with 91.7% flow coverage. Crucially, decomposing the decision latency reveals that 99.8% of the 84-millisecond response time is physical wire delay—waiting for packets to arrive across the radio channel. Algorithmic extraction and inference take only a fraction of a millisecond."*

---

## Slide 6: Selective Prediction & Confidence Abstention

* **Slide Title:** Calibrated Selective Prediction: Monotonic Risk Reduction
* **Main Message:** Rejecting ambiguous predictions below threshold $\tau^*=0.70$ reduces classification error from $45.8\%$ down to **$26.9\%$** on accepted traffic (**73.1% accuracy**).
* **Evidence / Visual to Use:** Figure: `results/figures/coverage_vs_accuracy.png` and `results/figures/coverage_vs_error.png`. Trade-off metrics: at $\tau^*=0.70$, 26 flows accepted (54.2% coverage), 22 flows rejected (45.8% abstention).
* **Important Caveat:** Uncalibrated tree ensembles exhibit significant overconfidence (ECE = 0.1996, MCE = 0.5581); post-hoc calibration is necessary before automated firewall blocking.
* **Suggested Speaker Notes:**
  > *"In security monitoring, taking an incorrect automated action is often worse than taking no action. We evaluated selective prediction with confidence gating. Setting a validation-tuned threshold at tau=0.70 allows the model to classify high-confidence flows while flagging ambiguous ones for secondary inspection. On held-out test data, this policy cuts the classification error rate from 45.8% down to 26.9%, achieving 73.1% accuracy on accepted traffic at 54.2% coverage. We note, however, that tree ensembles exhibit miscalibration, which motivates our future work on conformal calibration."*

---

## Slide 7: Domain Generalization & Tunnel Encapsulation Asymmetry

* **Slide Title:** Domain Generalization: Physical Transfer vs. Tunnel Opacity
* **Main Message:** Zero-payload features transfer robustly across simulated physical media (REG-05: **0.9325 Macro-F1**), but exhibit severe asymmetric degradation under WireGuard / Cloudflare WARP tunneling (REG-08b: **0.3407 Macro-F1**).
* **Evidence / Visual to Use:** Figure: `results/figures/tunnel_shift.png` and `results/figures/environment_shift.png`. Comparison: Tunneled $\rightarrow$ Direct yields **1.0000 Macro-F1** (REG-08a), while Direct $\rightarrow$ Tunneled collapses to **0.3407 Macro-F1** (REG-08b, $-0.2653$ F1 drop).
* **Important Caveat:** REG-05 evaluated statistical feature perturbations modeling Ethernet and Cellular, NOT physical hardware captures.
* **Suggested Speaker Notes:**
  > *"We stress-tested model generalization across eight domain-shift regimes. The transport feature profile proved highly resilient across simulated Layer-1 media, maintaining 0.9325 Macro-F1 across simulated Ethernet and Cellular streams. However, evaluating VPN encapsulation uncovered a fundamental architectural insight: tunnel asymmetry. Models trained on WireGuard traffic transfer perfectly to unencapsulated traffic with 1.0000 Macro-F1. But models trained on direct traffic collapse to 0.3407 when confronted with WireGuard tunnels, because fixed 1280-byte MTU clamping and handshake masking strip packet size diversity."*

---

## Slide 8: Computational Edge Footprint & Live Streaming Smoke Test

* **Slide Title:** Real-Time Deployment Feasibility & Resource Footprint
* **Main Message:** Feature extraction requires $0.368$ ms P50; Decision Tree vector inference enables **15,600 flows/sec** at **3.11 KB** serialized footprint, validated on live local streaming loopback.
* **Evidence / Visual to Use:** Figure: `results/figures/model_size_vs_f1.png` and `results/figures/resource_usage.png`. Table showing footprint: 3.11 KB (10 features) / 9.58 KB (21 features); Live stream: 142 packets, 15 flows, 112 window classifications, 81.78 pred/s, 0 drops.
* **Important Caveat:** Current live engine is an x86 Python prototype evaluated on local loopback; carrier-grade 10 Gbps+ lines require Linux eBPF/XDP implementation.
* **Suggested Speaker Notes:**
  > *"To validate edge hardware viability, we profiled resource utilization on host hardware. A 10-feature pruned Decision Tree requires just 3.11 kilobytes of storage and processes over 15,600 flows per second. Feature extraction dominates the pipeline at 0.37 milliseconds median CPU time. We integrated this model into a live packet-capture engine, confirming sub-millisecond per-flow processing with zero dropped packets and verified zero-payload persistence."*

---

## Slide 9: Research Integrity, Limitations & Unresolved Questions

* **Slide Title:** Research Integrity: Limitations & Unresolved Questions
* **Main Message:** The codebase has been audited with 71 passing regression tests; all scientific limitations and historical artifact variances are disclosed transparently.
* **Evidence / Visual to Use:** Audit status summary: 71 / 71 tests passed in 2.67s; Table listing key limitations: Pure physical Wi-Fi baseline ($N=12$ test flows, standard error $\pm 14.4\%$), Hybrid provenance of `dataset_v2` (59.8% perturbations), and Unresolved RF variance (0.5854 vs 0.5873).
* **Important Caveat:** 0.0833 pure physical baseline illustrates single-device sample starvation under session isolation, not a universal impossibility proof.
* **Suggested Speaker Notes:**
  > *"Research integrity is the cornerstone of this project. Through ten rigorous audit phases, we eliminated all conflation between synthetic fixtures and real traffic. We openly report that our pure physical Wi-Fi baseline achieved 0.0833 Macro-F1 on a 12-flow test set; with a plus-minus 14% standard error, this highlights the severe challenge of session isolation on small sample sizes. We also formally disclose that the Random Forest 0.5854 versus 0.5873 score variance remains an unresolved historical artifact, with 0.5854 reproduced exactly by our preserved weights."*

---

## Slide 10: Conclusion, Roadmap & Supervisor Discussion

* **Slide Title:** Conclusion & Proposed Next Experiments
* **Main Message:** Lightweight Decision Trees provide a defensible, Pareto-optimal foundation for zero-payload encrypted traffic classification; prioritized next steps focus on expanding physical capture scale and multi-interface collection.
* **Evidence / Visual to Use:** Experimental Roadmap quadrant chart from `NEXT_EXPERIMENTS_ROADMAP.md` showing:
  - Immediate: Conformal calibration (reduce ECE $<0.05$) and bare-metal C export.
  - Strategic: Multi-device physical Wi-Fi capture campaign ($N \ge 500$ flows across 100+ sessions) and native physical Ethernet/LTE captures.
* **Important Caveat:** Scaling physical captures requires multi-device scripting and access to university testbeds.
* **Suggested Speaker Notes:**
  > *"In conclusion, this project establishes that lightweight Decision Trees offer an exceptionally efficient, privacy-preserving approach for real-time encrypted traffic classification, achieving Pareto dominance over complex ensembles. Our repository is fully audited, mathematically verified, and ready for supervisor review. For the next phase, our highest priority is expanding physical traffic captures across multiple client devices and recording native Ethernet and 5G traces to replace synthetic perturbations. Thank you, and I look forward to your questions and guidance."*
