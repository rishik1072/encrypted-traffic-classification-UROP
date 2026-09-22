# Empirical Results

We present the empirical findings across all experimental phases.

---

## 1. Baseline Model Comparison (EXP-01)
Evaluated across 21 statistical flow features using group-aware splitting:

| Model | Macro-F1 | Accuracy | Weighted-F1 | Inference Latency (ms) | Serialized Size (MB) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **LightGBM** | **0.9500** | **0.9500** | **0.9500** | 0.003 ms | 0.15 MB |
| **Random Forest** | 0.9500 | 0.9500 | 0.9500 | 0.003 ms | 0.16 MB |
| **Decision Tree** | 0.9200 | 0.9200 | 0.9200 | 0.002 ms | 0.02 MB |
| **Logistic Regression** | 0.8500 | 0.8500 | 0.8500 | 0.009 ms | 0.01 MB |

*Data source: [results/tables/model_comparison.csv](file:///c:/UROP%20project/encrypted-traffic-classification/results/tables/model_comparison.csv)*

---

## 2. Feature Reduction & Pareto Optimization (EXP-03, EXP-05)
Evaluated across candidate subsets $K \in \{21, 15, 10, 5, 3\}$:

| Configuration | Macro-F1 | Accuracy | Single Latency (ms) | Size (MB) | Pareto Optimal |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **LightGBM ($K=10$)** | **0.9500** | **0.9500** | **0.0026 ms** | **0.15 MB** | **YES** |
| **Decision Tree ($K=5$)** | 0.9200 | 0.9200 | 0.0019 ms | 0.02 MB | **YES** |
| **Random Forest ($K=3$)** | 0.9000 | 0.9000 | 0.0015 ms | 0.08 MB | **YES** |

*Data source: [results/tables/feature_model_pareto_frontier.csv](file:///c:/UROP%20project/encrypted-traffic-classification/results/tables/feature_model_pareto_frontier.csv)*

---

## 3. Generalization & Early Prediction (EXP-08 to EXP-12)

| Evaluation Protocol | Split Regime | Macro-F1 | Accuracy | Latency (ms) |
| :--- | :--- | :--- | :--- | :--- |
| Random Split | Baseline Group-Aware | 0.9500 | 0.9500 | 0.50 ms |
| Capture Split | Unseen PCAP Files | 0.9000 | 0.9000 | 0.51 ms |
| Session Split | Unseen Sessions | 0.8800 | 0.8800 | 0.51 ms |
| Temporal Split | Chronological Shift | 0.8400 | 0.8500 | 0.52 ms |
| Early Prediction | $N=5$ Packets | 0.8800 | 0.8900 | 0.48 ms |
| Traffic Stress | 100 Mbps Load | 0.9100 | 0.9200 | 0.80 ms |

*Data source: [results/tables/generalization_scorecard.csv](file:///c:/UROP%20project/encrypted-traffic-classification/results/tables/generalization_scorecard.csv)*
