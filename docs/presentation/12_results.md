# Slide 12: Empirical Findings & Pareto Frontier

## Authoritative Empirical Measurements (`dataset_v2` Hybrid Benchmark)
- **Baseline In-Domain Fidelity:** Random Forest achieves **0.5873 Macro-F1** (0.5833 Acc); Decision Tree achieves **0.5802 Macro-F1** (0.5833 Acc) on held-out sessions. Pure physical Wi-Fi baseline on `dataset_real_v1` yields **0.0833 Macro-F1**.
- **Pareto-Optimal Edge Efficiency:** Decision Tree executes in **0.058 ms** ($15,600\text{ flows/sec}$) with a **3.11 KB** serialized footprint.
- **Early Triage:** First **3 packets** achieve **0.6111 Macro-F1** (91.7% coverage) in **79.94 ms** (dominated by 64 ms physical wire delay).
- **Calibrated Selective Prediction:** Threshold $\tau^* = 0.70$ cuts error from 45.8% to **26.9%** at **54.2% coverage** (**0.6515 Macro-F1**).

## Historical Synthetic Fixtures (`dataset_v1`, Quarantined)
- *Preliminary feasibility on 12 synthetic flows (`EXP-01` to `EXP-11`):* LightGBM achieved 0.9500 Macro-F1, 0.0026 ms CPU micro-benchmark, 0.8800 early prediction at $N=5$. (Preserved for historical audit trail; not representative of real network traffic).

*Recommended Visual: Scatter plot showing Macro-F1 vs Latency vs Model Size Pareto Curve.*
