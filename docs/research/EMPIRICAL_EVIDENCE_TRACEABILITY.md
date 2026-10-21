# Empirical Results Reconciliation and Evidence Traceability Audit

**Document Version:** 1.0.0  
**Audit Date:** 2026-10-21  
**Branch:** `audit/fix-research-and-pipeline`  
**Auditor:** Independent Research Integrity Auditor (Google DeepMind Antigravity)  
**Status:** Authoritative Evidence Traceability Standard  

---

## 1. Executive Summary & Audit Mandate

This document establishes the empirical traceability, mathematical reconciliation, and verification status of headline experimental metrics reported across the research repository:

$$\text{Repository: } \texttt{C:\textbackslash UROP project\textbackslash encrypted-traffic-classification-UROP}$$

Tasks 1–6 addressed dataset provenance, claim boundaries, split-leakage auditing, baseline provenance, and research documentation. Task 7 provides an **independent reconciliation of empirical evidence** to determine which headline results are reproduced or supported by existing artifacts without model retraining or pipeline re-execution.

### Key Audit Findings

1. **Physical Baseline ($0.0833$ Macro-F1 / $0.0833$ Accuracy) is Mathematically and Empirically VERIFIED:**
   - Evaluated on pure physical Wi-Fi traffic (`dataset_real_v1`, $N_{\text{test}}=12$ flows, 6 sessions, 2 flows/class across 6 classes).
   - In `results/tables/real_baseline_error_analysis.csv`, exactly **1 flow out of 12** was correctly classified (`20260823_170113_other_001_b130_flow_00000`, True: *Other*, Pred: *Other*).
   - All other 11 flows were misclassified.
   - For *Other*, $\text{Precision}=0.5, \text{Recall}=0.5, \text{F1}=0.5$; for the other 5 classes, $\text{F1}=0.0$.
   - Macro-F1 across 6 classes is $\frac{0.5}{6} = 0.08333...$; Accuracy is $\frac{1}{12} = 0.08333...$.
   - **Severe limitation:** $N=12$ represents extreme sample starvation (standard error $\approx \pm 14.4\%$). It cannot be generalized to all real encrypted network traffic.

2. **Hybrid Baseline Divergence ($0.5854 / 0.5857$ vs $0.5873$) is Classified as UNRESOLVED:**
   - Both results stem from the multi-environment hybrid benchmark (`dataset_v2`: 301 flows, 150 sessions, 121 physical flows + 180 controlled statistical perturbations).
   - Both runs shared identical dataset partitions (train=205, val=48, test=48) and identical results for Logistic Regression (0.3240 F1), Decision Tree (0.5802 F1), and LightGBM (0.5474 F1).
   - Random Forest achieved $0.5854$ Test F1 (size: 878.04 KB) in `results/tables/research_baseline.csv` and $0.5873$ Test F1 (size: 881.98 KB) in `results/final/baseline_results.csv` (and was transcribed as $0.5857$ in `BASELINE_PROTOCOL.md` with size 880.5 KB).
   - Because prediction logs for the second run were not saved and multi-threaded bagging (`n_jobs=-1`) can introduce non-deterministic tree construction, the exact numerical root cause cannot be confirmed without retraining (strictly prohibited). The numerical relationship is classified as **`UNRESOLVED`**.

3. **Generalization Across Environments (REG-05: $0.9325$ F1) is PARTIALLY VERIFIED:**
   - Verified on controlled synthetic feature perturbations modeling Ethernet MTU and Cellular latency/jitter on base physical flows.
   - **Not verified** on independent physical Ethernet or Cellular hardware captures.

---

## 2. Baseline Metrics Reconciliation Audit

| Property | `research_baseline.csv` | `baseline_results.csv` | `real_final_baseline_result.csv` |
| :--- | :--- | :--- | :--- |
| **Reported Metric (RF)** | **0.5854** (cited as 0.5857) | **0.5873** | **0.0833** |
| **Reported Accuracy (RF)** | 0.5833 | 0.5833 | 0.0833 |
| **Dataset ID** | `dataset_v2` | `dataset_v2` | `dataset_real_v1` |
| **Dataset Provenance** | `HYBRID_PERTURBED` | `HYBRID_PERTURBED` | `REAL_DATA` |
| **Physical Flows** | 121 (40.2%) | 121 (40.2%) | 121 (100.0%) |
| **Synthetic Perturbations** | 180 (59.8%) | 180 (59.8%) | 0 (0.0%) |
| **Total Flows** | 301 flows (150 sessions) | 301 flows (150 sessions) | 121 flows (60 sessions) |
| **Split Strategy** | Group-aware session (70/15/15) | Group-aware session (70/15/15) | Group-aware session (70/20/10) |
| **Partition Counts** | Train: 205, Val: 48, Test: 48 | Train: 205, Val: 48, Test: 48 | Train: 85, Val: 24, Test: 12 |
| **Test Denominator** | 48 flows (8 per class) | 48 flows (8 per class) | 12 flows (2 per class) |
| **Random Seed** | 42 | 42 | 42 |
| **RF Hyperparameters** | `n_estimators=100, max_depth=15, min_samples_split=4, n_jobs=-1, random_state=42` | `n_estimators=100, max_depth=15, min_samples_split=4, n_jobs=-1, random_state=42` | `n_estimators=100, max_depth=15, min_samples_split=4, n_jobs=-1, random_state=42` |
| **Model Size** | 878.04 KB (899,117 bytes) | 881.98 KB (903,147 bytes) | 0.49 KB (499 bytes) |
| **Model Winner Status** | NO (LGBM won val: 0.5664 > 0.5582) | YES (RF won val: 0.5984 > 0.5664) | YES (RF won val: 0.2828 > 0.1226) |
| **Verification Status** | **UNRESOLVED** (vs 0.5873) | **UNRESOLVED** (vs 0.5854) | **VERIFIED** |

### Investigation of Random Forest Divergence (0.5854 / 0.5857 vs 0.5873)

1. **Deterministic Models are Completely Identical:**
   - Logistic Regression: Val Macro-F1 = `0.3684`, Test Macro-F1 = `0.3240`, Size = `2.0 KB` (identical across both CSV files).
   - Decision Tree: Val Macro-F1 = `0.5382`, Test Macro-F1 = `0.5802`, Size = `9.58 KB` (identical across both CSV files).
   - LightGBM: Val Macro-F1 = `0.5664`, Test Macro-F1 = `0.5474`, Size = `689.33 KB` (identical across both CSV files).

2. **Random Forest Discrepancy:**
   - In `research_baseline.csv`: RF Validation Macro-F1 is `0.5582`, Test Macro-F1 is `0.5854`, serialized disk size is `878.04 KB`. Because LightGBM achieved `0.5664` validation Macro-F1, LightGBM was selected as the winner (`is_selected_winner = YES`).
   - In `baseline_results.csv`: RF Validation Macro-F1 is `0.5984`, Test Macro-F1 is `0.5873`, serialized disk size is `881.98 KB`. Here, Random Forest was selected as winner (`is_selected_winner = YES`).
   - In `BASELINE_PROTOCOL.md`: RF Validation Macro-F1 is `0.5833`, Test Macro-F1 is `0.5857`, model size is `880.5 KB`.

3. **Root Cause Analysis & Status:**
   - Random Forest configuration specifies `n_jobs=-1`. Multi-threaded bagging across CPU cores in scikit-learn without thread-level synchronization can cause slight variations in split ties or sample assignment across runs.
   - The saved model artifact on disk (`results/models/research_baseline/random_forest.joblib`, 899,117 bytes = 878.04 KB) corresponds directly to `research_baseline.csv` ($0.5854$ F1).
   - However, since per-sample prediction logs for the secondary execution were not preserved, proving whether the difference arose from multi-core threading, platform differences, or an intermediate commit cannot be done without retraining.
   - **Verdict:** Classify the relationship between $0.5854/0.5857$ and $0.5873$ as **`UNRESOLVED`**.

---

## 3. Physical Baseline Audit (`dataset_real_v1`)

### Test Partition Composition
- Source: `data/processed/splits/real_clean/test.csv`
- Total flows: 12 flows across 6 sessions (exactly 2 flows per session, 1 session per class):
  1. `20260823_145151_web_001_0bbf` (Web, 2 flows: port 52783 & 443)
  2. `20260823_155216_video_001_1ce3` (Video, 2 flows: port 443 & 52783)
  3. `20260823_160947_messaging_001_869a` (Messaging, 2 flows: port 52783 & 443)
  4. `20260823_162302_voip_001_6194` (VoIP, 2 flows: port 52783 & 443)
  5. `20260823_163126_file_transfer_001_bea6` (File Transfer, 2 flows: port 52783 & 443)
  6. `20260823_170113_other_001_b130` (Other, 2 flows: port 50468 & 443)

### Prediction Audit & Confusion Matrix
From `results/tables/real_baseline_error_analysis.csv`:
- **Correct flow (1):**
  - `20260823_170113_other_001_b130_flow_00000`: True: *Other*, Pred: *Other* (Confidence: 0.9500).
- **Misclassified flows (11):**
  - Web flow 0 $\rightarrow$ Other
  - Web flow 1 $\rightarrow$ Video
  - Video flow 0 $\rightarrow$ Web
  - Video flow 1 $\rightarrow$ File Transfer
  - Messaging flow 0 $\rightarrow$ VoIP
  - Messaging flow 1 $\rightarrow$ File Transfer
  - VoIP flow 0 $\rightarrow$ Web
  - VoIP flow 1 $\rightarrow$ Video
  - File Transfer flow 0 $\rightarrow$ VoIP
  - File Transfer flow 1 $\rightarrow$ Web
  - Other flow 1 $\rightarrow$ File Transfer

### Metric Calculation Breakdown
- Accuracy: $\frac{1 \text{ correct}}{12 \text{ total}} = 0.08333...$
- Class *Other*: $\text{TP} = 1, \text{FN} = 1, \text{FP} = 1 \implies \text{Precision} = \frac{1}{2} = 0.5, \text{Recall} = \frac{1}{2} = 0.5, \text{F1} = 0.5$
- Classes *Web, Video, Messaging, VoIP, File Transfer*: $\text{TP} = 0 \implies \text{F1} = 0.0$
- **Macro-F1:** $\frac{0.5 + 0 + 0 + 0 + 0 + 0}{6} = \frac{0.5}{6} = 0.08333...$
- **Macro-Precision:** $\frac{0.5 + 0 + 0 + 0 + 0 + 0}{6} = 0.08333...$
- **Macro-Recall:** $\frac{0.5 + 0 + 0 + 0 + 0 + 0}{6} = 0.08333...$
- **Weighted-F1:** $\frac{2 \times 0.5 + 10 \times 0.0}{12} = \frac{1.0}{12} = 0.08333...$

**Conclusion:** All headline metrics ($0.0833$) in `real_final_baseline_result.csv` are mathematically verified on this specific partition.

### Critical Limitations of the Physical Test Set
1. **Severe Sample Starvation ($N=12$):** A test set of 12 flows drawn from only 6 sessions recorded on a single laptop Wi-Fi adapter has an enormous standard error ($\approx \pm 14.4\%$). A single additional correct prediction swings accuracy by $8.33\%$.
2. **Cannot Generalize:** While proving that zero-payload models trained on small Wi-Fi captures struggle under strict session isolation, it **cannot be claimed** that zero-payload classification universally collapses on all encrypted traffic.

---

## 4. Primary Empirical Claims Traceability Analysis

### Claim 1: Early Prediction at Horizon $N=3$
- **Statement:** Zero-payload features classify flows after observing only $N=3$ packets with $63.6\%$ accuracy, $91.7\%$ coverage, and $84.3$ ms median latency.
- **Source Artifact:** `results/tables/research_early_prediction.csv` (Row 2).
- **Dataset:** Real clean test partition ($N=12$ flows).
- **Denominator Verification:**
  - Total test flows: 12
  - Flows meeting horizon: 12
  - Flows classified: 11 (1 flow abstained under decision threshold $\tau=0.30$)
  - Coverage: $11 / 12 = 0.9167$ ($91.67\%$)
  - Accuracy: $7 \text{ correct} / 11 \text{ classified} = 0.6364$ ($63.64\%$)
  - Latency: $64.04$ ms median observation delay + $20.00$ ms inference latency = $84.33$ ms total latency.
- **Verification Status:** **`VERIFIED`** (for the stated denominator: 7/11 classified flows).
- **Limitation:** Small sample size ($N=12$ test flows).

### Claim 2: Selective Prediction at Threshold $\tau^*=0.70$
- **Statement:** Abstaining on low-confidence predictions ($\tau < 0.70$) yields $73.1\%$ accuracy on accepted flows ($54.2\%$ coverage, $26.9\%$ error rate).
- **Source Artifact:** `results/tables/research_selective_prediction.csv` (Row 11).
- **Dataset:** `dataset_v2` test partition ($N=48$ flows).
- **Denominator Verification:**
  - Total samples: 48 flows
  - Accepted samples: 26 flows ($54.17\%$ coverage)
  - Rejected samples: 22 flows ($45.83\%$ rejection rate)
  - Selective accuracy: $19 \text{ correct} / 26 \text{ accepted} = 0.7308$ ($73.08\%$)
  - Error rate on accepted: $7 \text{ errors} / 26 \text{ accepted} = 0.2692$ ($26.92\%$)
  - Selective Macro-F1: $0.6515$
- **Verification Status:** **`VERIFIED`**.
- **Limitation:** High abstention penalty ($45.8\%$ of traffic rejected).

### Claim 3: Domain Shift Generalization (REG-05 & REG-08a/08b)
- **REG-05 (Unseen Environment: Wi-Fi $\rightarrow$ Ethernet + Cellular):**
  - Source: `results/tables/research_generalization_scorecard.csv` (Row 6).
  - Train: Wi-Fi (`env_win11_wifi`, 181 flows); Test: Ethernet + Cellular (`env_win11_eth`, `env_win11_cellular`, 120 flows: 20 per class).
  - Metrics: Macro-F1 = $0.9325$, Accuracy = $0.9333$ (112/120 flows).
  - Status: **`PARTIALLY VERIFIED`**. The numbers reflect empirical execution on `dataset_v2`, but the Ethernet/Cellular environments were generated via synthetic statistical perturbation (MTU, latency, jitter modeling), not physical NIC captures.
- **REG-08a (Tunnel Shift: Tunneled $\rightarrow$ Direct):**
  - Source: `results/tables/research_generalization_scorecard.csv` (Row 9).
  - Train: Tunneled (265 flows); Test: Direct (36 flows: 6 per class).
  - Metrics: Macro-F1 = $1.0000$, Accuracy = $1.0000$ (36/36 flows).
  - Status: **`VERIFIED`** (as empirical property of `dataset_v2`).
- **REG-08b (Tunnel Shift: Direct $\rightarrow$ Tunneled):**
  - Source: `results/tables/research_generalization_scorecard.csv` (Row 10).
  - Train: Direct (36 flows); Test: Tunneled (265 flows: ~44 per class).
  - Metrics: Macro-F1 = $0.3407$, Accuracy = $0.3585$ (95/265 flows). Degradation: $-0.2653$ F1 drop.
  - Status: **`VERIFIED`**. Proves tunnel asymmetry: unencapsulated training fails on tunneled traffic.

### Claim 4: Decision Tree Latency and Serialized Model Footprint
- **Statement:** CART Decision Tree achieves warm P50 inference latency under $70\ \mu\text{s}$ and serialized model footprint under $10$ KB ($249\times$ faster than Random Forest).
- **Source Artifacts:**
  - `results/tables/research_latency.csv`: Decision Tree warm P50 inference latency = $0.0541$ ms (21 features) / $0.0594$ ms (10 features). Extractor P50 = $0.3681$ ms.
  - `results/final/baseline_results.csv`: Median latency = $0.0694$ ms (vs RF $17.2884$ ms $\implies 249.1\times$ faster).
  - `results/tables/research_baseline.csv`: Median latency = $0.0625$ ms (vs RF $16.9701$ ms $\implies 271.5\times$ faster).
  - `results/models/research_baseline/decision_tree.joblib`: Serialized file size = 9,814 bytes ($9.58$ KB).
  - `results/tables/research_model_footprint.csv`: Pruned 10-feature tree = $3.11$ KB.
- **Verification Status:** **`VERIFIED`**.

### Claim 5: Real-Time Operational Smoke Test
- **Statement:** The streaming engine processes live localhost packets without queue overflow, memory growth, or dropped flows.
- **Source Artifact:** `results/tables/realtime_research_validation.csv` (Row 3).
- **Observations:** 142 packets observed, 15 flows generated, 112 sliding window classifications, $81.78$ pred/s, P50 latency $0.072$ ms, 0 dropped flows. All payload persistence and zero-payload checks PASSED.
- **Verification Status:** **`VERIFIED`** (as a local software smoke test).

### Claim 6: Calibration & Expected Calibration Error (ECE)
- **Statement:** Baseline tree models are miscalibrated on held-out test data, exhibiting substantial overconfidence.
- **Source Artifact:** `results/tables/research_calibration.csv` (Rows 2–11).
- **Observations:** Overall ECE = $0.1996$ ($19.96\%$), MCE = $0.5581$ ($55.81\%$), Brier score = $0.6061$, NLL = $1.4153$ across 10 bins on 48 held-out test flows.
- **Verification Status:** **`VERIFIED`**.

### Claim 7: Zero-Payload and Localhost-Only Security Invariants
- **Statement:** The system inspects no packet payload bytes, performs zero TLS decryption, and transmits zero data to external endpoints.
- **Source Artifacts:** `flows/flow_generator.py`, `preprocessing/feature_extractor.py`, `tests/test_payload_security.py`, `tests/test_zero_payload_live.py`.
- **Verification Status:** **`VERIFIED`**.

---

## 5. Comprehensive Evidence Traceability Matrix

| Claim / Exp ID | Scientific Claim | Reported Metric | Dataset ID & Origin | Source Artifact | Split & Denominator | Reproducibility Evidence | Verification Status | Limitations | Required Next Action |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **EXP-01** | Synthetic feasibility baseline | Macro-F1: 0.9500<br>Accuracy: 0.9167 | `dataset_v1`<br>(`SYNTHETIC_FIXTURE`) | `results/tables/model_comparison.csv` | Synthetic fixture split<br>($N_{\text{test}}=5$) | Deterministic Scapy generator script | **HISTORICAL** | Pure synthetic loopback fixture; trivial separability; 0% real traffic | Preserve strictly as historical development milestone; disallow real claims |
| **EXP-R09-RF** | In-domain baseline ensemble on hybrid benchmark | Macro-F1: 0.5854 / 0.5857 vs 0.5873<br>Accuracy: 0.5833 | `dataset_v2`<br>(`HYBRID_PERTURBED`) | `results/tables/research_baseline.csv`<br>`results/final/baseline_results.csv` | Group-aware session (70/15/15)<br>$N_{\text{test}}=48$ flows (8/class) | Model joblib (878.04 KB) matches 0.5854; secondary run lacks saved prediction dump | **UNRESOLVED** | Exact 0.5854 vs 0.5873 variance unresolved; 59.8% synthetic perturbations | Track 0.5854 vs 0.5873 as unresolved stochastic difference; disallow pure real claim |
| **EXP-R09-DT** | In-domain lightweight Decision Tree baseline | Macro-F1: 0.5802<br>Accuracy: 0.5833 | `dataset_v2`<br>(`HYBRID_PERTURBED`) | `results/tables/research_baseline.csv`<br>`results/final/baseline_results.csv` | Group-aware session (70/15/15)<br>$N_{\text{test}}=48$ flows (8/class) | Identical across all tables; model joblib on disk (9,814 B) | **VERIFIED** | Evaluated on hybrid dataset; test set $N=48$ flows | Cite as authoritative hybrid Decision Tree benchmark |
| **EXP-R09-LGBM** | In-domain LightGBM gradient boosting baseline | Macro-F1: 0.5474<br>Accuracy: 0.5417 | `dataset_v2`<br>(`HYBRID_PERTURBED`) | `results/tables/research_baseline.csv`<br>`results/final/baseline_results.csv` | Group-aware session (70/15/15)<br>$N_{\text{test}}=48$ flows (8/class) | Identical across all tables; model joblib on disk (705,876 B) | **VERIFIED** | Evaluated on hybrid dataset; test set $N=48$ flows | Retain in model comparison |
| **EXP-R09-LR** | In-domain linear baseline (Logistic Regression) | Macro-F1: 0.3240<br>Accuracy: 0.3333 | `dataset_v2`<br>(`HYBRID_PERTURBED`) | `results/tables/research_baseline.csv`<br>`results/final/baseline_results.csv` | Group-aware session (70/15/15)<br>$N_{\text{test}}=48$ flows (8/class) | Identical across all tables; model joblib on disk (2,044 B) | **VERIFIED** | Linear model fails on statistical features; test set $N=48$ | Retain as linear lower bound |
| **EXP-R01** | Pure physical Wi-Fi baseline under session isolation | Macro-F1: 0.0833<br>Accuracy: 0.0833 | `dataset_real_v1`<br>(`REAL_DATA`) | `results/tables/real_final_baseline_result.csv`<br>`real_baseline_model_comparison.csv` | Session-isolated split<br>$N_{\text{test}}=12$ flows (2/class) | Error analysis logs exact flow (`other_001_b130_flow_00000`) correct (1/12) | **VERIFIED** | Severe sample starvation ($N=12$ flows from 6 sessions); standard error $\pm 14.4\%$ | Document sample limits; disallow universal generalization to all real traffic |
| **EXP-R11-EARLY** | Early triage at packet horizon $N=3$ | Accuracy: 0.6364 (7/11)<br>Coverage: 0.9167 (11/12)<br>Median Latency: 84.33 ms | Clean real test set<br>(`REAL_DATA`) | `results/tables/research_early_prediction.csv` (Row 2) | Packet truncation split<br>$N_{\text{classified}}=11$ (1 abstained) | Direct metrics table with flow count breakdown | **VERIFIED** | Small test denominator (11 classified flows out of 12) | Always cite 7/11 and 91.7% coverage alongside accuracy |
| **EXP-R12-SELECT** | Selective classification at threshold $\tau^*=0.70$ | Selective Acc: 0.7308 (19/26)<br>Coverage: 0.5417 (26/48)<br>Error Rate: 0.2692 | `dataset_v2`<br>(`HYBRID_PERTURBED`) | `results/tables/research_selective_prediction.csv` (Row 11) | Confidence threshold filter<br>$N_{\text{accepted}}=26$ (22 rejected) | Validation and test threshold sweeps in table | **VERIFIED** | High abstention rate ($45.8\%$ rejected); hybrid dataset | Present coverage and rejection rates in all tables |
| **EXP-R13-REG05** | Generalization to unseen network interfaces | Macro-F1: 0.9325<br>Accuracy: 0.9333 (112/120) | `dataset_v2`<br>(`HYBRID_PERTURBED`) | `results/tables/research_generalization_scorecard.csv` (Row 6) | Train: Wi-Fi (181 flows)<br>Test: Eth + Cell (120 flows) | Scorecard table with exact sample counts | **PARTIALLY VERIFIED** | Ethernet and Cellular were synthetically perturbed, not physical NIC captures | Explicitly state interfaces were modeled via statistical perturbation |
| **EXP-R13-REG08A** | Tunnel shift generalization (Tunneled $\rightarrow$ Direct) | Macro-F1: 1.0000<br>Accuracy: 1.0000 (36/36) | `dataset_v2`<br>(`HYBRID_PERTURBED`) | `results/tables/research_generalization_scorecard.csv` (Row 9) | Train: Tunneled (265 flows)<br>Test: Direct (36 flows) | Scorecard table with sample counts | **VERIFIED** | Small test set ($N=36$ flows) | Cite as evidence that tunnel features encompass direct traffic |
| **EXP-R13-REG08B** | Tunnel shift generalization (Direct $\rightarrow$ Tunneled) | Macro-F1: 0.3407<br>Accuracy: 0.3585 (95/265) | `dataset_v2`<br>(`HYBRID_PERTURBED`) | `results/tables/research_generalization_scorecard.csv` (Row 10) | Train: Direct (36 flows)<br>Test: Tunneled (265 flows) | Scorecard table with sample counts | **VERIFIED** | Training set is small ($N=36$ flows) | Highlight tunnel opacity as fundamental challenge |
| **EXP-R14-LAT** | Vector inference latency for Decision Tree | Warm P50: 0.0541–0.0694 ms<br>P95: 0.0713–0.1893 ms | `dataset_v2` feature matrices | `results/tables/research_latency.csv`<br>`results/final/baseline_results.csv` | 500 repetitions CPU vector benchmark | Warm/cold benchmarks recorded across 4 models | **VERIFIED** | Measured on x86 workstation; embedded edge hardware may differ | Benchmark on target embedded router architecture |
| **EXP-R14-SIZE** | Serialized model footprint for Decision Tree | 9.58 KB (21 features)<br>3.11 KB (10 features) | Joblib serialized binaries | `results/tables/research_model_footprint.csv`<br>`results/models/research_baseline/decision_tree.joblib` | Disk file stat & in-memory profiling | Model file exists on disk (9,814 bytes) | **VERIFIED** | Serialization format is Python joblib (scikit-learn) | Provide C header / array export if embedding on microcontrollers |
| **EXP-R15-SMOKE** | Operational streaming pipeline smoke test | 142 packets, 15 flows<br>81.78 pred/s, 0 drops | Local live loopback capture | `results/tables/realtime_research_validation.csv` (Row 3) | Controlled live stream test phase | Validation table with security and throughput flags | **VERIFIED** | Short controlled live stream; not a multi-gigabit enterprise backbone test | Frame strictly as engine feasibility demonstration |
| **EXP-R16-CALIB** | Probability calibration on held-out test set | ECE: 0.1996<br>MCE: 0.5581<br>Brier: 0.6061 | `dataset_v2`<br>(`HYBRID_PERTURBED`) | `results/tables/research_calibration.csv` (Rows 2–11) | 10 uniform reliability bins<br>$N_{\text{test}}=48$ flows | Reliability table with bin counts and accuracies | **VERIFIED** | Small sample size ($N=48$ flows) | Recommend temperature scaling / Platt scaling before policy automation |
| **EXP-R17-SEC** | Zero-payload & local-only security invariants | 0 payload bytes extracted<br>0 cloud calls | All datasets & pipeline modules | `flows/flow_generator.py`<br>`preprocessing/feature_extractor.py`<br>`tests/test_payload_security.py` | Full codebase static & dynamic security audit | Automated test suites passing cleanly | **VERIFIED** | Privacy preserved by design; padding/morphing defenses still challenge accuracy | Maintain architectural security guards in CI |
| **EXP-R10-ABL** | Feature family ablation (Timing vs Volume) | Full ($K=21$): 0.5802 F1<br>Without IAT: 0.3857 F1<br>Timing only: 0.2624 F1 | `dataset_v2`<br>(`HYBRID_PERTURBED`) | `results/tables/feature_family_ablation_research.csv` | Group-aware session (70/15/15)<br>$N_{\text{test}}=48$ flows | Systematic feature masking table | **VERIFIED** | Evaluated on hybrid dataset | Document IAT as essential feature family |
| **EXP-R10-COUNT**| Feature count Pareto optimization ($K=10$) | $K=10$: 0.3857 F1 (ablation) / 0.5827 F1 (pruned tree)<br>Size: 3.11 KB | `dataset_v2`<br>(`HYBRID_PERTURBED`) | `results/tables/feature_count_tradeoff_research.csv`<br>`results/tables/selected_features_10.csv` | Feature reduction sweep<br>$N_{\text{test}}=48$ flows | Ranked feature lists and tradeoff table | **VERIFIED** | Evaluated on hybrid dataset | Highlight $K=10$ as edge candidate |

---

## 6. Dataset and Split Traceability Audit

### Dataset Registry Consistency
All active datasets were audited against `training/dataset_registry.py`:
- `dataset_v1`: Correctly labeled `SYNTHETIC_FIXTURE` ($N=12$ flows, 0 physical flows).
- `dataset_real_v1`: Correctly labeled `REAL_DATA` ($N=121$ flows, 60 sessions, 121 physical Wi-Fi flows, 0 synthetic flows).
- `dataset_v2`: Correctly labeled `HYBRID_PERTURBED` ($N=301$ flows, 150 sessions, 121 physical flows [40.2%] + 180 controlled statistical perturbations [59.8%]).
- `demo_data`: Correctly labeled `DEMO_DATA` ($N=20$ flows).
- `external_benchmarks`: Correctly cataloged `EXTERNAL_BENCHMARK`.

### Split Partition Integrity
The partition membership audit conducted by `training/split_leakage_audit.py` was inspected and verified:
1. `data/processed/splits/real_clean`: Train (85 flows, 42 sessions), Val (24 flows, 12 sessions), Test (12 flows, 6 sessions). Pairwise session overlap: **0**.
2. `EXP-R09_baseline_group_split` (`dataset_v2`): Train (205 flows, 102 sessions), Val (48 flows, 24 sessions), Test (48 flows, 24 sessions). Pairwise session overlap: **0**.
3. All 8 domain-shift evaluation regimes (REG-01 to REG-08b) have zero partition overlap for their designated isolation criteria.

### Missing Artifacts & Unresolved Traces
1. **Missing Per-Sample Prediction Dump for Baseline Run 2:** `results/final/baseline_results.csv` contains Random Forest metrics ($0.5873$ F1), but individual flow predictions (`pred_flow_id`, `y_true`, `y_pred`, `prob`) were not archived for that run, leaving the minor difference with $0.5854$ permanently `UNRESOLVED` without prohibited retraining.
2. **Missing Physical Interface Captures for REG-05:** Ethernet and Cellular test sets in REG-05 are feature perturbations of Wi-Fi sessions, not native Ethernet or Cellular PCAPs.

---

## 7. Audit Verdict & Publication Readiness

### Summary of Claim Statuses
- **VERIFIED:** 13 claims (Physical baseline 0.0833, Decision Tree 0.5802, LightGBM 0.5474, Logistic Regression 0.3240, Early prediction 0.6364 on 11 flows, Selective prediction 0.7308 on 26 flows, Tunnel shifts REG-08a & REG-08b, Decision Tree latency & footprint, Real-time smoke test, Calibration ECE, Zero-payload security, Feature ablation).
- **PARTIALLY VERIFIED:** 1 claim (Unseen environment REG-05: verified as perturbation benchmark, unverified on physical hardware).
- **UNRESOLVED:** 1 claim relationship (Baseline Random Forest $0.5854 / 0.5857$ vs $0.5873$ numerical divergence).
- **HISTORICAL:** 1 claim (`EXP-01` 0.9500 Macro-F1 on synthetic fixture).
- **CONTRADICTED:** 0 active paper claims (all legacy claims of 0.9500 or 0.5857 on "pure real traffic" were successfully corrected in Tasks 1–6).

### Final Recommendation for Paper Submission
1. **Report Evidence Transparently:** Publish the hybrid benchmark results with explicit disclosure of the 121 physical + 180 perturbation composition.
2. **Do Not Hide 0.0833:** Present the pure physical Wi-Fi baseline ($0.0833$ on 12 flows) alongside the hybrid results as honest proof of the challenge of real encrypted traffic under strict session isolation and small sample sizes.
3. **Report Denominators:** Always publish the evaluation denominator (e.g., $N_{\text{test}}=11/12$ for early prediction; $N_{\text{accepted}}=26/48$ for selective prediction).
