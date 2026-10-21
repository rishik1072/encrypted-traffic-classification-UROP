# Key Scientific Findings

> [!NOTE]
> **Historical Synthetic Findings Notice (`dataset_v1`, EXP-01 through EXP-11):**
> The findings documented below record historical observations measured on an initial 12-flow synthetic loopback fixture (`dataset_v1`) during preliminary feasibility development. As audited in [CLAIMS_LEDGER.md](research/CLAIMS_LEDGER.md) and [FINAL_RESULTS.md](../results/final/FINAL_RESULTS.md), these preliminary metrics (e.g., 0.9500 Macro-F1) are superseded by the authoritative hybrid benchmark (`dataset_v2`: Random Forest 0.5857 / 0.5873, Decision Tree 0.5802) and pure physical baseline (`dataset_real_v1`: 0.0833). They are preserved here strictly for audit trail completeness.

All findings reported below are based strictly on empirical measurements obtained during experimental execution on `dataset_v1`.

---

### Finding 1: Feasibility of Zero-Payload Encrypted Traffic Classification
- **Observed Result**: Flow-level statistical timing, length distributions, and bidirectional ratios achieve a baseline **Macro-F1 of 0.9500** across 6 canonical traffic classes without payload decryption or Deep Packet Inspection.
- **Relevant Experiment**: `EXP-01` (Baseline ML Benchmark).

---

### Finding 2: High Feature Redundancy in Traditional Flow Schemas
- **Observed Result**: Pearson correlation analysis identified severe collinearity ($r > 0.85$) among burst counts and volumetric metrics. Reducing feature dimensions from $K=21$ to $K=10$ preserved classification fidelity while reducing online feature calculation overhead by over 40%.
- **Relevant Experiment**: `EXP-02` (Feature Ranking) & `EXP-03` (Feature Reduction).

---

### Finding 3: Pareto-Optimal Deployment Architectures
- **Observed Result**: Across all evaluated configurations, **LightGBM** ($K=10$) and **Decision Tree** ($K=5$) formed the non-dominated Pareto frontier:
  - *LightGBM ($K=10$)*: Macro-F1 = 0.9500, Latency = 0.003 ms, Disk Footprint = 0.15 MB.
  - *Decision Tree ($K=5$)*: Macro-F1 = 0.9200, Latency = 0.002 ms, Disk Footprint = 0.02 MB.
- **Relevant Experiment**: `EXP-05` (Pareto Optimization).

---

### Finding 4: Sub-Millisecond Real-Time Classification
- **Observed Result**: In streaming simulation across varying traffic rates (1 to 100 Mbps), single-flow processing latency remained below **0.80 ms** with 0 dropped packets up to 80 Mbps.
- **Relevant Experiment**: `EXP-06` (Real-Time Latency) & `EXP-07` (Traffic Stress).

---

### Finding 5: Early-Prediction Feasibility
- **Observed Result**: Observing the first **5 packets** of a session yielded a **Macro-F1 of 0.8800** with 100% flow coverage, demonstrating that full session completion is not required for accurate initial categorization.
- **Relevant Experiment**: `EXP-11` (Early Prediction).

---

### Finding 6: Generalization Gaps Under Distribution Shifts
- **Observed Result**: When moving from random group-aware splits to strictly isolated **unseen captures** (Macro-F1: 0.9000), **unseen sessions** (Macro-F1: 0.8800), and **temporal shifts** (Macro-F1: 0.8400), performance exhibited measurable degradation, underscoring the necessity of continuous multi-environment data collection.
- **Relevant Experiment**: `EXP-08`, `EXP-09`, `EXP-10` (Generalization Splits).
