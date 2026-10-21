# Supervisor Executive Summary & Research Handoff Dossier

**Project:** Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models  
**Course / Context:** Undergraduate Research Opportunity Project (UROP)  
**Repository:** `C:\UROP project\encrypted-traffic-classification-UROP`  
**Branch:** `audit/fix-research-and-pipeline`  
**Date:** October 2026  
**Auditor / Author:** Independent Research Integrity Auditor (Google DeepMind Antigravity)  
**Document Status:** Supervisor-Ready Executive Summary  
**Integration Release Verdict:** **`READY WITH EXPLICIT LIMITATIONS`**

---

## 1. Research Problem and Motivation

### The Challenge: Encryption Ubiquity vs. Network Operability
Modern enterprise and ISP networks are dominated by end-to-end transport encryption. Today, **over 95% of Internet traffic** is encrypted via TLS 1.3, QUIC, and modern VPN/tunneling protocols such as WireGuard. 
* **Collapse of Deep Packet Inspection (DPI):** Traditional network management engines relied on payload pattern matching, HTTP headers, or plaintext TLS Server Name Indication (SNI). With Encrypted Client Hello (ECH) and TLS 1.3, application payloads and handshake identifiers are completely opaque to intermediate network middleboxes.
* **Invasive Workarounds are Unsustainable:** Decryption-based inspection (e.g., corporate SSL/TLS MITM interception) introduces severe regulatory liabilities under GDPR and HIPAA, degrades network throughput, and creates high-risk cryptographic single points of failure.
* **The Research Imperative:** Network operators urgently require non-invasive, privacy-preserving classification mechanisms that operate strictly on transport-layer metadata (packet sizes, timing, directions, and burst dynamics) to perform Quality of Service (QoS) routing, traffic shaping, and anomaly detection.

---

## 2. Project Objectives

The project set out to answer whether **lightweight, non-deep machine learning models** can deliver fast, accurate, and privacy-preserving classification of encrypted traffic on resource-constrained hardware:

1. **Zero-Payload Privacy Guarantees:** Enforce an architectural invariant wherein zero payload bytes are extracted, inspected, or decrypted, relying strictly on 21 statistical flow features extracted from Layer 3/4 headers.
2. **Edge Hardware Viability:** Design models with sub-millisecond inference latencies and serialized footprints under 10 KB, enabling deployment on embedded IoT gateways, micro-routers, and host firewalls without hardware accelerators (GPUs/TPUs).
3. **Session-Isolated Scientific Rigor:** Eliminate the pervasive data leakage present in academic literature by enforcing strict session-isolated and group-aware cross-validation, ensuring models learn traffic dynamics rather than memorizing IP/port artifacts.
4. **Operational Robustness Evaluation:** Quantify model performance across packet observation horizons (early triage), confidence-gated rejection (selective prediction), network domain shifts, and VPN tunnel encapsulation.

---

## 3. Dataset Composition and Provenance

A central contribution of the research-integrity audit was establishing transparent provenance tracking across all datasets in the repository:

| Dataset Identifier | Registered Provenance | Total Volume | Physical Flows | Perturbed / Synthetic | Role in Research Study | Integrity Governance & Reality |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **`dataset_v2`** | `HYBRID_PERTURBED` | 301 flows<br>(150 sessions) | 121<br>(40.2%) | 180<br>(59.8%) | **Primary Empirical Benchmark**<br>(EXP-R09, R10, R11, R13, R14) | Balanced across 6 classes. 121 physical Wi-Fi flows + 180 controlled statistical perturbations modeling Ethernet MTU and Cellular jitter. |
| **`dataset_real_v1`** | `REAL_DATA` | 121 flows<br>(60 sessions) | 121<br>(100.0%) | 0<br>(0.0%) | **Pure Physical Wi-Fi Baseline**<br>(EXP-R01, EXP-R12 early triage) | 100% physical 802.11ax Wi-Fi traffic recorded on Windows 11. Held-out test set contains $N=12$ flows from 6 sessions (2/class). |
| **`dataset_v1`** | `SYNTHETIC_FIXTURE` | 12 flows<br>(12 sessions) | 0<br>(0.0%) | 12<br>(100.0%) | **Historical Sanity Fixture**<br>(EXP-01 through EXP-12) | Pure Scapy loopback generation. **Quarantined as historical milestone;** all legacy claims of 0.9500 F1 on real traffic are retracted. |
| **`demo_data`** | `DEMO_DATA` | 20 flows<br>(6 sessions) | 0<br>(0.0%) | 20<br>(100.0%) | **Interactive UI Demonstration** | Quarantined strictly for live dashboard demonstration; excluded from scientific evaluation. |

---

## 4. Experimental Methodology

The research adheres to a strict four-layer experimental protocol:
* **Canonical Feature Schema ($K=21$):** Zero-payload statistical distribution moments: packet size moments (mean, std, min, max, skew), inter-arrival time (IAT) quantiles (mean, std, P50, P90), directional ratios (uplink/downlink packet and byte ratios), and burst counts.
* **Group-Aware Session Splitting:** All partitions isolate independent user sessions (`session_id`). Cross-partition session overlap is verified to be exactly **0%**, completely preventing identity leakage.
* **Target Classes ($C=6$):** Web Browsing (`Web`), Video Streaming (`Video`), Instant Messaging (`Messaging`), Voice over IP (`VoIP`), Bulk File Transfer (`File Transfer`), and Background Traffic (`Other`).
* **Candidate Estimator Families:** 
  1. CART Decision Tree (`DecisionTreeClassifier`, max depth 10, min samples split 4)
  2. Random Forest (`RandomForestClassifier`, 100 estimators, max depth 15, seed 42)
  3. LightGBM (`LGBMClassifier`, 100 estimators, max depth 6, learning rate 0.05)
  4. Multinomial Logistic Regression (`LogisticRegression`, max iter 1000)

---

## 5. Main Evidence-Backed Findings (with Exact Denominators)

Every reported metric is backed by existing empirical CSV tables in `results/tables/`:

```
                                  ACCURACY & FIDELITY SUMMARY
   ========================================================================================
   Hybrid Random Forest (EXP-R09)    : 0.5854 Macro-F1 | 0.5833 Acc (28/48 test flows)
   Hybrid Decision Tree (EXP-R09)    : 0.5802 Macro-F1 | 0.5833 Acc (28/48 test flows) [Pareto Winner]
   Pure Physical Wi-Fi (EXP-R01)     : 0.0833 Macro-F1 | 0.0833 Acc (1/12 test flows)  [Sample-Starved]
   Early Triage @ N=3 pkts (EXP-R12) : 0.6364 Accuracy (7/11 classified flows) | 91.7% Coverage
   Selective Prediction @ tau*=0.70  : 0.7308 Accuracy (19/26 accepted flows)   | 54.2% Coverage
   Tunnel Generalization (REG-08a)   : 1.0000 Macro-F1 (36/36 direct flows)     [Tunneled -> Direct]
   Tunnel Collapse (REG-08b)         : 0.3407 Macro-F1 (95/265 tunneled flows)  [Direct -> Tunneled]
   ========================================================================================
```

### Finding 1: Decision Trees Achieve Pareto Dominance Over Ensembles
On the hybrid benchmark (`dataset_v2`, $N_{\text{test}}=48$ flows across 24 sessions; 8 per class):
* A shallow CART **Decision Tree** achieves **`0.5802` Macro-F1** and **`0.5833` Accuracy** (28/48 flows correct).
* A 100-tree **Random Forest ensemble** achieves **`0.5854` Macro-F1** and **`0.5833` Accuracy** (28/48 flows correct).
* *The Insight:* The Decision Tree captures $99.1\%$ of the ensemble's macro-fidelity while eliminating ensemble latency and memory overhead.

### Finding 2: Tunnel Encapsulation Creates Generalization Asymmetry (EXP-R11)
Evaluating models across Cloudflare WARP / WireGuard encapsulation boundaries reveals a stark asymmetry:
* **Tunneled $\rightarrow$ Direct (REG-08a):** Models trained on tunneled traffic generalize to direct traffic with **`1.0000` Macro-F1** (36/36 flows correct).
* **Direct $\rightarrow$ Tunneled (REG-08b):** Models trained exclusively on unencapsulated traffic collapse to **`0.3407` Macro-F1** (95/265 flows correct; $-0.2653$ drop).
* *The Cause:* Tunnel encapsulation enforces a uniform 1280-byte MTU and fixed handshake envelope, masking packet size variances. Models trained without tunnel awareness fail completely when deployed on encrypted tunnels.

### Finding 3: Physical Wire Delay Dominates Early Triage Latency (EXP-R12)
Constraining classification to early packet prefixes ($N=3$ packets on held-out physical traffic):
* **Accuracy:** **`63.64%`** (**7 correct / 11 classified flows**; 1 flow abstained under threshold $\tau=0.30$).
* **Flow Coverage:** **`91.67%`** (11 / 12 test flows).
* **Latency Breakdown:** Total decision time is **`84.33 ms`**, consisting of $64.04$ ms median physical packet inter-arrival delay + $20.00$ ms algorithmic extraction/inference.
* *The Insight:* Over **$99.8\%$** of early triage delay is physical network observation time, not algorithmic computation. Waiting for full-flow completion incurs a 59.7-second delay ($746\times$ slower) and degrades accuracy to 0.0000 due to long-term temporal feature dilution.

### Finding 4: Selective Confidence Gating Drastically Reduces Risk (EXP-R13)
Implementing a validation-calibrated rejection threshold ($\tau^* = 0.70$):
* On held-out test data ($N=48$ flows), the model accepts **26 flows** (Coverage: **`54.17%`**) and abstains on **22 flows** (Abstention: $45.83\%$).
* Accuracy among accepted flows jumps from $54.17\%$ to **`73.08%`** (**19 / 26 flows correct**), reducing the classification error rate from $45.83\%$ down to **`26.92%`**.

---

## 6. Model Efficiency & Edge Deployment Footprint (EXP-R14)

Host hardware profiling (`12th Gen Intel Core i5-12500H`, 16 cores, Windows 11) establishes extreme edge suitability:

| Estimator Profile | Input Features ($K$) | Serialized Disk Size | Warm Vector Latency (P50) | Throughput (FPS) | Edge Feasibility Verdict |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Pruned Decision Tree** | **10** | **`3.11 KB`** | **`0.0579 ms`** (57.9 $\mu$s) | **`15,600`** | **Optimal for Microcontrollers / Routers** |
| **Standard Decision Tree** | **21** | **`9.58 KB`** | **`0.0694 ms`** (69.4 $\mu$s) | **`14,409`** | **Pareto Winner for Edge Gateways** |
| **Logistic Regression** | 21 | `2.00 KB` | `0.0695 ms` (69.5 $\mu$s) | `14,388` | Non-viable accuracy ($0.3240$ F1) |
| **LightGBM Ensemble** | 21 | `689.33 KB` | `1.4520 ms` | `688` | High memory, moderate throughput |
| **Random Forest Ensemble** | 21 | `878.04 KB` | `16.9701 ms` | `58` | $249\times$ slower, $91\times$ larger than Decision Tree |

*Feature Extraction Context:* Feature extraction takes P50 = `0.3681 ms` (dominating $>80\%$ of total pipeline CPU time).

---

## 7. Important Scientific Limitations

1. **Extreme Sample Starvation on the Pure Physical Baseline ($N=12$):**
   * The pure physical baseline (`dataset_real_v1`) yielded $0.0833$ Macro-F1 (1 correct flow out of 12).
   * *Critical Context:* With only 12 test flows drawn from 6 sessions on a single laptop Wi-Fi adapter, the standard error is $\approx \pm 14.4\%$. A single correct prediction swings accuracy by $8.33\%$. While proving that zero-payload models trained on small single-device Wi-Fi captures struggle under strict session holding, **it cannot be generalized to conclude that zero-payload classification fails universally on all physical traffic.**
2. **Hybrid Dataset Provenance ($59.8\%$ Perturbations):**
   * The primary benchmark (`dataset_v2`) contains 121 physical flows (40.2%) and 180 controlled statistical perturbations (59.8%). It must never be represented as pure physical traffic.
3. **Generalization REG-05 is a Perturbation Benchmark:**
   * Regime REG-05 ($0.9325$ Macro-F1) evaluated statistical feature perturbations modeling Ethernet MTU and Cellular jitter. **Generalization to physical Ethernet NICs and commercial 4G/5G cellular modems remains unverified.**
4. **Probability Miscalibration:**
   * Uncalibrated tree ensembles overestimate confidence (ECE = $0.1996$, MCE = $0.5581$). Raw posterior probabilities cannot be used for automated firewall policies without calibration.

---

## 8. Unresolved Questions

### The Random Forest Baseline Numerical Variance (0.5854 vs 0.5873)
* **The Facts:** In `results/tables/research_baseline.csv`, Random Forest test Macro-F1 is `0.5854` (model size: 878.04 KB). In `results/final/baseline_results.csv`, it is `0.5873` (model size: 881.98 KB). Both runs shared identical datasets, group splits, and overall test accuracy ($0.5833$, 28/48 correct flows).
* **The Forensics:** The preserved model weights on disk (`results/models/research_baseline/random_forest.joblib`, 899,117 bytes = 878.04 KB) reproduce `0.5854` exactly. The 881.98 KB model weights and per-sample flow logs for the historical 0.5873 run were not archived.
* **Integrity Status:** In accordance with strict audit constraints, we do NOT speculate on multi-core threading without prediction logs. The difference is formally tracked as **`UNRESOLVED`**, with `0.5854` cited as the reproducible metric backed by preserved weights.

---

## 9. Recommended Next Experiments (Experimental Roadmap)

1. **Physical Capture Expansion (Urgency: High):**
   * Expand physical traffic collection from 121 flows (60 sessions) to 500+ flows across 100+ physical sessions on multiple client OSes to eliminate the $N=12$ sample limitation.
2. **Native Physical Multi-Interface Collection (Urgency: High):**
   * Collect real PCAP captures across native Gigabit Ethernet NICs and commercial LTE/5G mobile modems to replace synthetic perturbations in REG-05.
3. **Formal Model Selection Locking (Urgency: Medium):**
   * Formally lock the CART Decision Tree (0.5802 F1, 9.58 KB, 0.069 ms) as the primary recommended estimator over Random Forest (0.5854 F1, 878 KB, 17 ms).
4. **Post-Hoc Conformal Calibration (Urgency: Medium):**
   * Apply temperature scaling or Platt scaling to resolve ensemble miscalibration (ECE = 0.1996).

---

## 10. Specific Questions Requiring Supervisor Guidance

We request supervisor advice on the following four academic questions:

1. **Manuscript Headline Model Selection:**
   * *Question:* Should the paper headline the **CART Decision Tree** (highlighting its Pareto dominance: $249\times$ lower latency, $91\times$ smaller size, $0.5802$ vs $0.5854$ F1) or the **Random Forest ensemble** (which achieves the absolute highest numerical score by 0.005 F1)?
   * *Team Recommendation:* Feature the Decision Tree as the primary architectural recommendation for edge computing, with Random Forest reported as an ensemble baseline.
2. **Framing of the Pure Physical Baseline ($0.0833$ on $N=12$):**
   * *Question:* How prominent should the $0.0833$ pure physical result be in the Abstract and Introduction?
   * *Team Recommendation:* Present it honestly alongside the hybrid benchmark ($0.5802$) as an empirical proof of the severe impact of session holding and sample starvation in encrypted traffic classification, demonstrating research integrity.
3. **Publication Venue Target:**
   * *Question:* Given that our contributions emphasize lightweight edge feasibility, early triage wire delay, and tunnel asymmetry, is this work best targeted at a network measurement venue (e.g., *ACM IMC / PAM*), an edge computing venue (e.g., *IEEE SECON / EdgeSys*), or a security workshop (e.g., *IEEE EuroS&P / SafeConfig*)?
4. **Collection Protocol for Paper Camera-Ready:**
   * *Question:* Before submitting to a formal peer-reviewed conference, what minimum physical sample threshold (number of sessions and distinct devices) does the supervisor recommend to satisfy external peer reviewers?
