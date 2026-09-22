# Research Objectives

The research objectives of this project are:

1. **Zero-Payload Pipeline Design**: Develop an end-to-end network traffic classification pipeline that inspects only Layer-3/4 header metadata, packet lengths, and inter-arrival timing without decrypting payload bytes.
2. **Model Architecture Benchmarking**: Implement and compare four lightweight classifiers (Logistic Regression, Decision Tree, Random Forest, LightGBM) across Macro-F1, inference latency, and memory footprint.
3. **Multi-Method Feature Ranking**: Systematically identify the most informative statistical flow features using Mutual Information, Random Forest Gini importance, LightGBM gain, and validation permutation importance.
4. **Accuracy–Cost Trade-Off & Pareto Analysis**: Measure performance degradation curves across reduced feature subsets ($K \in \{21, 15, 10, 5, 3\}$) and establish non-dominated Pareto deployment configurations.
5. **Real-Time Streaming Engine**: Engineer an asynchronous classification engine with bidirectional flow tracking, lifecycle state management, and continuous performance telemetry.
6. **Multi-Regime Generalization Evaluation**: Evaluate model stability across unseen captures (file-level isolation), unseen sessions (session-level isolation), and chronological temporal shifts.
7. **Early-Prediction & Load Robustness**: Quantify classification fidelity within initial flow observation windows ($N \le 5$ packets) and under network traffic load scaling from 1 to 100 Mbps.
8. **Cybersecurity SOC Console Demonstration**: Provide an interactive monitoring dashboard displaying live flow telemetry, low-confidence alerts, and lightweight trade-off explorers.
