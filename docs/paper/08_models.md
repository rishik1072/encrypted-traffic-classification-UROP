# Chapter 8: Lightweight Model Architectures

## 8.1 Model Selection Criteria for Edge Deployment

Selecting machine learning models for network traffic classification requires balancing classification accuracy against real-time operational constraints. In line-rate edge environments (such as commodity Wi-Fi access points, industrial gateways, or software-defined switches), classifiers must satisfy four strict operational criteria:

1. **Sub-Millisecond Inference Budget:** The end-to-end classification latency per flow must not exceed wire-speed packet processing intervals.
2. **Minimal Memory Footprint:** The serialized model artifact and its runtime working set must comfortably reside in limited RAM (< 512 MB).
3. **Absence of Hardware Acceleration Dependencies:** Models must execute entirely on general-purpose x64 or ARM CPUs without requiring dedicated GPUs, TPUs, or proprietary neural network coprocessors.
4. **Deterministic Execution:** The algorithmic execution time must exhibit low variance and tight tail latency percentiles (P95/P99) to prevent packet queue starvation.

Based on these criteria, we evaluate four lightweight supervised estimators representing linear, recursive tree, bagging ensemble, and gradient boosting paradigms.

---

## 8.2 Candidate Estimator Formulations

### 1. Multinomial Logistic Regression (`logistic_regression`)
Serves as the convex linear baseline. For $C=6$ target classes and a $K$-dimensional standardized feature vector $\mathbf{x} \in \mathbb{R}^K$, the posterior class probabilities are modeled via the softmax function:

$$P(y = c \mid \mathbf{x}) = \frac{\exp(\mathbf{w}_c^T \mathbf{x} + b_c)}{\sum_{j=1}^C \exp(\mathbf{w}_j^T \mathbf{x} + b_j)}$$

- **Objective:** Cross-entropy loss with L2 regularization:
  $$\mathcal{L}(\mathbf{W}, \mathbf{b}) = -\frac{1}{N} \sum_{i=1}^N \sum_{c=1}^C y_{i,c} \log P(y = c \mid \mathbf{x}_i) + \frac{1}{2C_{\text{reg}}} \sum_{c=1}^C \|\mathbf{w}_c\|_2^2$$
- **Hyperparameters:** Inverse regularization strength $C_{\text{reg}} = 1.0$, solver = L-BFGS, maximum iterations = 500.

### 2. CART Decision Tree (`decision_tree`)
Constructs a single binary decision tree using greedy recursive partitioning. At each node $t$, the split criterion selects feature $k$ and threshold $\theta$ that maximizes the reduction in Gini impurity:

$$\Delta I_G(t) = I_G(t) - \frac{N_L}{N_t} I_G(t_L) - \frac{N_R}{N_t} I_G(t_R), \quad \text{where } I_G(t) = 1 - \sum_{c=1}^C p(c \mid t)^2$$

- **Inference Mechanism:** A sequence of at most $D_{\text{max}}$ scalar comparisons. Class probabilities are estimated via the empirical class distribution of the terminal leaf.
- **Hyperparameters:** Criterion = Gini impurity, maximum depth $D_{\text{max}} = 12$, minimum samples per split = 5, minimum samples per leaf = 2, random seed = 42.

### 3. Random Forest Ensemble (`random_forest`)
Constructs an ensemble of $B=100$ decorrelated decision trees using bootstrap aggregating (bagging) with random feature sub-sampling:

$$\hat{y} = \arg\max_{c} \frac{1}{B} \sum_{b=1}^B P_b(y = c \mid \mathbf{x})$$

- **Inductive Bias:** Reduces variance by averaging predictions across decorrelated trees, providing robustness against noisy features.
- **Hyperparameters:** Number of estimators $B = 100$, maximum depth = 15, max features per split = $\sqrt{K}$, minimum samples per split = 4, random seed = 42.

### 4. LightGBM Gradient Boosted Decision Trees (`lightgbm`)
Builds an additive ensemble of shallow regression trees trained sequentially to minimize multiclass logarithmic loss using gradient descent in functional space:

$$F_m(\mathbf{x}) = F_{m-1}(\mathbf{x}) + \eta \sum_{j=1}^J \gamma_{jm} \mathbb{I}(\mathbf{x} \in R_{jm})$$

- **Algorithmic Optimizations:** Utilizes leaf-wise (best-first) tree growth and Gradient-Based One-Side Sampling (GOSS), prioritizing instances with larger gradients to accelerate convergence.
- **Hyperparameters:** Objective = `multiclass`, boosting type = GBDT, number of boosting rounds = 100, maximum leaves = 31, learning rate $\eta = 0.05$, feature fraction = 0.8, random seed = 42.

---

## 8.3 Algorithmic Complexity & Edge Profiling

Table 8.1 compares the asymptotic computational complexity and empirical footprints of the candidate architectures.

### Table 8.1: Theoretical Complexity & Empirical Resource Footprint (`results/final/resource_usage.csv`)

| Architecture | Training Complexity | Single-Vector Inference Complexity | Serialized Disk Footprint (10 Features) | Working Set RAM | Median Warm Inference Latency | Max Throughput (FPS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Logistic Regression** | $O(N \cdot K \cdot C)$ | $O(K \cdot C)$ | **1.00 KB** | 289.60 MB | 0.0695 ms | 12,224.9 flows/s |
| **Decision Tree** | $O(N \cdot K \cdot D)$ | $O(D), \quad D \le 12$ | **3.11 KB** | **289.60 MB** | **0.0579 ms** | **15,600.6 flows/s** |
| **Random Forest** | $O(B \cdot N \cdot K \cdot D)$ | $O(B \cdot D), \quad B=100$ | 175.41 KB | 289.62 MB | 4.2476 ms | 213.3 flows/s |
| **LightGBM** | $O(M \cdot N \cdot K)$ | $O(M \cdot J), \quad M=100$ | 225.64 KB | 290.12 MB | 0.3520 ms | 2,307.3 flows/s |

### Critical Takeaway
While Random Forest and LightGBM achieve strong benchmark results, their ensemble traversal requirements reduce throughput to 213–2,307 flows/sec. In contrast, the single Decision Tree evaluates in at most 12 scalar comparisons, achieving **15,600 flows/sec** with an ultra-compact **3.11 KB** model footprint.
