# External Dataset Benchmark Protocol

**Project**: Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift  
**Repository**: `c:\UROP project\encrypted-traffic-classification-UROP`  
**Date**: November 2026  
**Status**: APPROVED EXPERIMENTAL PROTOCOL  

---

## 1. Objectives & Scope

This protocol establishes the standardized evaluation pipeline for testing machine learning and sequence models on external encrypted traffic datasets (`CESNET-TLS22`, `CipherSpectrum`, `ISCXVPN2016`, etc.) within `research/external_datasets/`.

The primary goals are:
1. **Comparative Zero-Payload Performance**: Measure early-stage classification accuracy without payload inspection.
2. **Early Prefix Degradation**: Quantify accuracy tradeoffs as observation horizon $K \in \{3, 5, 10, 20, 30\}$ decreases.
3. **Probability Calibration**: Assess whether confidence scores reflect true accuracy via Expected Calibration Error (ECE) and Brier scores.
4. **Selective Classification (Abstention)**: Evaluate risk-coverage tradeoff curves when models abstain on low-confidence predictions.
5. **Inference Latency Profiling**: Measure microsecond-level prediction latencies under strict real-time operational constraints.

---

## 2. Standardized Model Suite

The benchmark engine (`research.external_datasets.benchmark_engine.ExternalBenchmarkEngine`) supports five standardized baseline architectures:

| Model Identifier | Algorithm | Hyperparameter Configuration | Purpose |
| :--- | :--- | :--- | :--- |
| **`lr`** | Multinomial Logistic Regression | `max_iter=500`, L2 regularization, `random_state=42` | Linear baseline |
| **`dt`** | Decision Tree Classifier | `max_depth=12`, Gini impurity, `random_state=42` | Interpretable tree baseline |
| **`rf`** | Random Forest Classifier | `n_estimators=100`, `max_depth=16`, `random_state=42` | Non-linear ensemble |
| **`lightgbm`** | LightGBM Gradient Boosting | `n_estimators=100`, `max_depth=6`, `learning_rate=0.05` | Primary tabular gradient booster |
| **`sequence_ngram`** | Sequence N-gram Classifier | Directional N-grams (1, 3) + Linear Classifier | Sequence pattern baseline |

---

## 3. Evaluation Metrics & Mathematical Formulations

### 3.1 Discrimination Metrics
- **Macro-Averaged F1 Score**:
  $$\text{Macro-F1} = \frac{1}{C} \sum_{c=1}^C \frac{2 \cdot \text{Precision}_c \cdot \text{Recall}_c}{\text{Precision}_c + \text{Recall}_c}$$
  Ensures equal weighting across rare and majority traffic categories.
- **Balanced Accuracy**:
  $$\text{Balanced Accuracy} = \frac{1}{C} \sum_{c=1}^C \text{Recall}_c$$
  Prevents inflated performance reporting under extreme class imbalance.

### 3.2 Probability Calibration Metrics
- **Brier Score**:
  $$\text{Brier} = \frac{1}{N} \sum_{i=1}^N \sum_{c=1}^C (p_{ic} - y_{ic})^2$$
- **Expected Calibration Error (ECE)**:
  Partitions confidence predictions $\hat{p}_i = \max_c p_{ic}$ into $M = 10$ equal-width bins $B_m \subset (0, 1]$:
  $$\text{ECE} = \sum_{m=1}^M \frac{|B_m|}{N} \left| \text{acc}(B_m) - \text{conf}(B_m) \right|$$

### 3.3 Selective Classification (Risk-Coverage)
For confidence threshold $\tau \in [0.5, 0.95]$:
- **Coverage**: Fraction of test instances where $\max_c p_{ic} \ge \tau$:
  $$\text{Coverage}(\tau) = \frac{1}{N} \sum_{i=1}^N \mathbb{I}(\max_c p_{ic} \ge \tau)$$
- **Selective Risk (Error Rate under Coverage)**:
  $$\text{Risk}(\tau) = \frac{\sum_{i=1}^N \mathbb{I}(\hat{y}_i \ne y_i \land \max_c p_{ic} \ge \tau)}{\sum_{i=1}^N \mathbb{I}(\max_c p_{ic} \ge \tau)}$$

### 3.4 Inference Latency Profiling
Measures wall-clock prediction latency over $N$ repeated individual sample predictions:
- **p50 (Median)**: Microseconds ($\mu s$).
- **p95 (95th Percentile)**: Microseconds ($\mu s$).
- **p99 (99th Percentile Tail)**: Microseconds ($\mu s$).

---

## 4. Result Isolation & Directory Structure

To ensure complete non-interference with production models and Dataset V1/V2 experiments:
- All benchmark results are stored strictly in:
  `results/external_benchmarks/<dataset_id>/`
- Output files:
  - `benchmark_<dataset_id>_<model>_k{K}_<timestamp>.json`: Complete serialized `BenchmarkModelResult`.
  - `summary_<dataset_id>_k{K}.json`: Multi-model comparison matrix.

---

## 5. Execution Commands

Benchmark evaluations are executed via the command-line interface:

```bash
# Evaluate LightGBM on CESNET DataZoo prefix K=5
python scripts/research/external_datasets/run_external_benchmark.py \
    --dataset cesnet-tls22 \
    --model lightgbm \
    --prefix-k 5

# Evaluate Random Forest on CipherSpectrum prefix K=10 with selective classification
python scripts/research/external_datasets/run_external_benchmark.py \
    --dataset cipherspectrum \
    --model rf \
    --prefix-k 10 \
    --selective-eval

# Evaluate all models across prefix horizons K in [3, 5, 10, 20]
python scripts/research/external_datasets/run_external_benchmark.py \
    --dataset iscxvpn2016 \
    --model all \
    --all-prefixes
```
