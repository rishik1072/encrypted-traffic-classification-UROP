# Master Experiment Registry & Provenance Catalog

**Repository:** Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models  
**Single Source of Truth Status:** ACTIVE  
**Last Updated:** September 2026  

---

## 1. Registry Schema Specification

Every experiment in this repository is cataloged with an immutable **Experiment ID** and required metadata to ensure reproducibility:

- **Experiment ID:** Unique identifier (`EXP-01` to `EXP-12` for historical synthetic, `EXP-R01`+ for real-data pipelines).
- **Objective:** The scientific question or hypothesis tested.
- **Dataset Version:** Target data partition (`dataset_v1`, `dataset_real_v1`, `dataset_v2`).
- **Feature Profile:** Feature subset name and count ($K$).
- **Model Architecture:** Estimator family and configuration.
- **Split Strategy:** Partitioning methodology (`Group-Aware Random`, `Session-Isolated`, `Capture-Isolated`, `Temporal Chronological`).
- **Random Seed:** Pseudo-random seed for reproducibility (`42`).
- **Code Version / Script:** Authoritative script used to generate results.
- **Execution Timestamp:** Date and time of the run.
- **Status:** `STALE / SYNTHETIC_ONLY`, `VERIFIED_REAL`, `UNVERIFIED`, or `BROKEN_ENV`.
- **Primary Metric & Result:** Empirical measurement achieved.
- **Authoritative Artifact:** Primary output table or model artifact.

---

## 2. Historical Synthetic Experiments (EXP-01 through EXP-12)

> [!WARNING]
> **Status: STALE / SYNTHETIC_ONLY**  
> All experiments in this table were executed on `dataset_v1` (a synthetic fixture comprising 12 Scapy-generated PCAPs / 120 flows). These results do **NOT** reflect real-world encrypted traffic dynamics and must never be cited as real-world benchmarks.

| Experiment ID | Objective | Dataset Version | Feature Profile | Model | Split Strategy | Random Seed | Primary Metric | Measured Value | Authoritative Artifact | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **EXP-01** | Baseline model comparison | `dataset_v1` | baseline ($K=21$) | LightGBM, RF, DT, LR | Group-Aware (File ID) | 42 | Macro-F1 | **0.9500** (LightGBM) | `results/tables/model_comparison.csv` | `STALE / SYNTHETIC` |
| **EXP-02** | Multi-method feature ranking | `dataset_v1` | baseline ($K=21$) | RF, LightGBM | Train / Val Split | 42 | Composite Rank | Top: `total_bytes`, `duration` | `results/tables/feature_ranking.csv` | `STALE / SYNTHETIC` |
| **EXP-03** | Controlled feature reduction | `dataset_v1` | $K \in \{21, 15, 10, 5, 3\}$ | LightGBM, RF, DT, LR | Train / Val Split | 42 | Macro-F1 | **0.9500** at $K=10$ | `results/tables/feature_reduction_performance.csv` | `STALE / SYNTHETIC` |
| **EXP-04** | Model complexity reduction | `dataset_v1` | baseline & reduced | RF, DT, LightGBM | Train / Val Split | 42 | Latency vs F1 | 0.0026 ms latency | `experiments/lightweight_model/complexity_comparison.csv` | `STALE / SYNTHETIC` |
| **EXP-05** | Pareto frontier optimization | `dataset_v1` | Candidate subsets | All 4 Models | Train / Val Split | 42 | Pareto Rank | LightGBM ($K=10$) Dominant | `results/tables/feature_model_pareto_frontier.csv` | `STALE / SYNTHETIC` |
| **EXP-06** | Real-time single-flow latency | `dataset_v1` | lightweight_10 ($K=10$) | LightGBM | Streaming Window | 42 | Single Latency | **0.0026 ms** | `results/tables/realtime_feature_cost.csv` | `STALE / SYNTHETIC` |
| **EXP-07** | Traffic volume stress test | `dataset_v1` | lightweight_10 ($K=10$) | LightGBM | Rate Sweeps (1-100 Mbps) | 42 | Throughput | 100 Mbps sustainable | `results/tables/traffic_volume_robustness.csv` | `STALE / SYNTHETIC` |
| **EXP-08** | Capture file generalization | `dataset_v1` | lightweight_10 ($K=10$) | LightGBM | Capture-Isolated Split | 42 | Macro-F1 | **0.9000** | `results/tables/generalization_scorecard.csv` | `STALE / SYNTHETIC` |
| **EXP-09** | Session generalization | `dataset_v1` | lightweight_10 ($K=10$) | LightGBM | Session-Isolated Split | 42 | Macro-F1 | **0.8800** | `results/tables/generalization_scorecard.csv` | `STALE / SYNTHETIC` |
| **EXP-10** | Temporal generalization | `dataset_v1` | lightweight_10 ($K=10$) | LightGBM | Chronological Split | 42 | Macro-F1 | **0.8400** | `results/tables/generalization_scorecard.csv` | `STALE / SYNTHETIC` |
| **EXP-11** | Early prediction robustness | `dataset_v1` | lightweight_10 ($K=10$) | LightGBM | $N \in \{3, 5, 10, 20, 50\}$ | 42 | Macro-F1 @ $N=5$ | **0.8800** (100% cov) | `results/tables/early_prediction_robustness.csv` | `STALE / SYNTHETIC` |
| **EXP-12** | Confidence calibration (ECE)| `dataset_v1` | lightweight_10 ($K=10$) | LightGBM | Platt Scaling Buckets | 42 | ECE | **0.1170** | `results/tables/calibration_results.csv` | `STALE / SYNTHETIC` |

---

## 3. Real Traffic Baseline & Optimization Experiments (EXP-R01 through EXP-R04)

> [!NOTE]
> **Status: VERIFIED_REAL**  
> These experiments were conducted on real controlled Wi-Fi / Ethernet captures. They reflect the actual empirical behavior of statistical features on real encrypted traffic.

| Experiment ID | Objective | Dataset Version | Feature Profile | Model | Split Strategy | Random Seed | Primary Metric | Measured Value | Authoritative Artifact | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **EXP-R01** | Real data baseline benchmark | `dataset_real_v1` | baseline ($K=21$) | LR, DT, RF, LightGBM | Session-Isolated ($N_{test}=12$) | 42 | Test Macro-F1 | **0.0833** (Random Forest) | `results/tables/real_final_baseline_result.csv` | `VERIFIED_REAL` |
| **EXP-R02** | Real feature ranking & audit | `dataset_real_v1` | baseline ($K=21$) | DT, RF, LightGBM | 5-Fold Grouped CV | 42 | Top Feature | `flow_duration` | `results/tables/real_feature_ranking.csv` | `VERIFIED_REAL` |
| **EXP-R03** | Real feature reduction & Pareto | `dataset_v2` | $K \in \{3, 5, 10, 15, 21\}$ | LR, DT, RF, LightGBM | 5-Fold Grouped CV | 42 | Selected Candidate | Decision Tree ($K=10$) | `results/tables/real_selected_candidate.csv` | `VERIFIED_REAL` |
| **EXP-R04** | Real optimized locked test | `dataset_v2` | lightweight_10 ($K=10$) | Decision Tree | Locked Test Split ($N_{test}=12$) | 42 | Test Macro-F1 | **0.2056** (Accuracy: 0.2500) | `results/tables/real_optimized_final_test.csv` | `VERIFIED_REAL` |

---

## 4. Advanced Pipeline Experiments (EXP-R05 through EXP-R09)

| Experiment ID | Objective | Dataset Version | Feature Profile | Model | Split Strategy | Random Seed | Primary Metric | Measured Value | Authoritative Artifact | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **EXP-R05** | Rich feature engineering | `dataset_v2` | rich ($K=103$, reduced $K=30$) | Decision Tree | Locked Test Split ($N_{test}=12$) | 42 | Test Macro-F1 | **0.1074** (Accuracy: 0.2500) | `results/tables/rich_final_test.csv` | `VERIFIED_REAL` |
| **EXP-R06** | Temporal classification | `dataset_v2` | temporal ($K=30$) | Decision Tree | Chronological Past $\rightarrow$ Future | 42 | Test Macro-F1 | **0.1667** (Accuracy: 0.1667) | `results/tables/temporal_final_test.csv` | `VERIFIED_REAL` |
| **EXP-R07** | Sequential window classification | `dataset_v2` | sequence_aggregated ($K=193$) | Decision Tree | Session-Isolated ($N_{test}=12$) | 42 | Test Macro-F1 | **0.0606** (Accuracy: 0.1667) | `results/tables/phase7_final_test.csv` | `VERIFIED_REAL` |
| **EXP-R08** | Hierarchical & selective classification | `dataset_v2` | hierarchical ($K=9$) | Hierarchical Decision Tree | Session-Isolated ($N_{test}=12$) | 42 | Unfiltered Macro-F1<br>Selective Macro-F1 | **0.0476** (Unfiltered)<br>**0.9500*** *(Coverage: 0.0%)* | `results/tables/phase8_final_test.csv` | `VERIFIED_REAL` |
| **EXP-R09** | **Research Baseline Benchmark (Group-Aware)** | `dataset_v2` | baseline ($K=21$) | LR, DT, RF, LightGBM | Session-Isolated Stratified (70/15/15) | 42 | **Test Macro-F1** (Winner: RF)<br>Decision Tree Test F1<br>LightGBM Test F1<br>Logistic Reg Test F1 | **0.5857** (Accuracy: 0.5833)<br>**0.5802** (Accuracy: 0.5833)<br>**0.5474** (Accuracy: 0.5417)<br>**0.3240** (Accuracy: 0.3333) | `results/tables/research_baseline.csv`<br>`docs/research/BASELINE_PROTOCOL.md` | `VERIFIED_REAL` |
| **EXP-R10** | **Zero-Payload Feature Family & Dimensionality Study** | `dataset_v2` | rich ($K=84$) & subsets ($K \in [3..84]$) | RF Ensembles | Session-Isolated Stratified (70/15/15) | 42 | **Optimal Top-3 Test F1**<br>Direction Only F1<br>All-84 Features Test F1 | **0.6708** (Accuracy: 0.6667)<br>**0.4265** (Accuracy: 0.4167)<br>**0.3359** (Accuracy: 0.3333) | `results/tables/feature_family_ablation_research.csv`<br>`results/tables/feature_count_tradeoff_research.csv`<br>`docs/research/FEATURE_ENGINEERING.md` | `VERIFIED_REAL` |
| **EXP-R11** | **Research Generalization & Domain Shift Benchmark** | `dataset_v2` | baseline ($K=21$) | Random Forest | 8 Group-Aware Domain Shifts | 42 | **Baseline F1**<br>Unseen Environment F1<br>Unseen Network Cond F1<br>Direct -> Tunneled F1 | **0.5840** (In-Domain)<br>**0.9325** (Eth+Cellular)<br>**0.9030** (Impaired)<br>**0.3407** (Severe Degradation) | `results/tables/research_generalization_scorecard.csv`<br>`docs/research/GENERALIZATION_PROTOCOL.md` | `VERIFIED_REAL` |
| **EXP-R12** | **Early Encrypted-Traffic Classification Study** | `dataset_v2` (`flows_real_clean.csv`) | baseline ($K=21$) | Random Forest | Session-Isolated Stratified (70/15/15) | 42 | **Macro-F1 @ N=3** ($80\text{ ms}$)<br>Macro-F1 @ N=5 ($348\text{ ms}$)<br>Accuracy @ N=10 ($1.33\text{ s}$)<br>Retrospective Full Flow | **0.6111** (Cov: 91.7%)<br>**0.3643** (Cov: 100.0%)<br>**0.8000** (Cov: 41.7%)<br>**0.0000** (Cov: 33.3%, $59.7\text{ s}$) | `results/tables/research_early_prediction.csv`<br>`docs/research/EARLY_PREDICTION_PROTOCOL.md` | `VERIFIED_REAL` |

*\*Caveat on EXP-R08:* The selective prediction policy achieved 0.9500 precision by abstaining on all 12 test instances.

---

## 5. Traceability & Execution Matrix

| Experiment Group | Source Script | Configuration File | Inputs Used | Outputs Produced | Test Coverage |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **EXP-01 to 05** | `training/ml_pipeline.py`, `training/optimization_pipeline.py` | `config.yaml` | `data/processed/features/features_cleaned.csv` | `results/tables/model_comparison.csv`, `feature_model_pareto_frontier.csv` | `tests/test_ml_pipeline.py`, `tests/test_optimization_pipeline.py` |
| **EXP-06 to 07** | `experiments/realtime/benchmark_traffic_rates.py` | `config.yaml` | Streaming synthetic window | `results/tables/realtime_feature_cost.csv`, `traffic_volume_robustness.csv` | `tests/test_realtime_pipeline.py` |
| **EXP-08 to 12** | `experiments/robustness/run.py` | `config.yaml` | `data/processed/splits/` | `results/tables/generalization_scorecard.csv`, `calibration_results.csv` | `tests/test_generalization_pipeline.py` |
| **EXP-R01 to R02**| `training/real_ml_baseline.py` | `config.yaml` | `data/processed/features/features_real_clean.csv` | `results/tables/real_final_baseline_result.csv`, `real_baseline_report.md` | `tests/test_real_ml_baseline.py` |
| **EXP-R03 to R04**| `training/real_optimization_pipeline.py` | `config.yaml` | `data/processed/features/features_real_clean_v2.csv` | `results/tables/real_optimized_final_test.csv`, `real_optimization_report.md` | `tests/test_real_optimization_pipeline.py` (Broken: dim mismatch) |
| **EXP-R05** | `training/rich_feature_pipeline.py` | `config.yaml` | `data/processed/features/features_real_rich_clean_v2.csv`| `results/tables/rich_final_test.csv`, `rich_feature_report.md` | `tests/test_rich_feature_pipeline.py` (Broken: param 'C') |
| **EXP-R06** | `training/temporal_classification_pipeline.py` | `config.yaml` | `data/processed/features/features_real_clean_v2.csv` | `results/tables/temporal_final_test.csv`, `temporal_classification_report.md` | `tests/test_temporal_classification_pipeline.py` |
| **EXP-R07** | `training/sequential_classification_pipeline.py` | `config.yaml` | `data/processed/features/features_real_clean_v2.csv` | `results/tables/phase7_final_test.csv`, `phase7_sequential_report.md` | `tests/test_sequential_classification_pipeline.py` |
| **EXP-R08** | `training/hierarchical_classification_pipeline.py` | `config.yaml` | `data/processed/features/features_real_clean_v2.csv` | `results/tables/phase8_final_test.csv`, `phase8_hierarchical_report.md` | `tests/test_hierarchical_classification_pipeline.py` (Broken: empty slice) |
| **EXP-R09** | `experiments/research_baseline/run.py` | `config.yaml` | `data/processed/features/features_real_clean_v2.csv` | `results/tables/research_baseline.csv`, `research_baseline_per_class.csv`, `research_baseline_confusion_matrix.png`, `research_baseline_model_comparison.png` | `tests/test_research_baseline.py` |
| **EXP-R10** | `experiments/feature_study/run.py` | `config.yaml` | `data/processed/features/features_real_rich_clean_v2.csv` | `results/tables/feature_family_ablation_research.csv`, `results/tables/feature_count_tradeoff_research.csv`, 4 figures | `tests/test_feature_study.py` |
| **EXP-R11** | `experiments/robustness/research_generalization.py` | `config.yaml` | `data/processed/features/features_real_clean_v2.csv` | `results/tables/research_generalization_scorecard.csv`, 5 plots | `tests/test_research_generalization.py` |
| **EXP-R12** | `experiments/research_early_prediction/run.py` | `config.yaml` | `data/processed/flows/flows_real_clean.csv` | `results/tables/research_early_prediction.csv`, 3 figures (`f1`, `coverage`, `latency`) | `tests/test_early_prediction.py` |
| **EXP-R13** | `experiments/selective_prediction/run.py` | `config.yaml` | `data/processed/features/features_real_clean_v2.csv` | `results/tables/research_selective_prediction.csv`, `results/tables/research_calibration.csv`, 4 figures (`coverage_vs_accuracy`, `coverage_vs_error`, `confidence_distribution`, `calibration_curve`) | `tests/test_selective_prediction.py` |
| **EXP-R14** | `experiments/computational_efficiency/run.py` | `config.yaml` | `data/processed/features/features_real_clean_v2.csv`, `flows_real_clean.csv` | `results/tables/research_latency.csv`, `results/tables/research_resource_usage.csv`, `results/tables/research_model_footprint.csv`, 4 figures (`latency_distribution`, `model_size_vs_f1`, `latency_vs_f1`, `resource_usage`) | `tests/test_computational_efficiency.py` |
| **EXP-R15** | `experiments/realtime_validation/run.py` | `config.yaml` | `flows_real_clean.csv`, live packet streams | `results/tables/realtime_research_validation.csv`, `docs/research/REALTIME_VALIDATION.md` | `tests/test_realtime_validation.py` |


