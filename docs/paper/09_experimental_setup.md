# Chapter 9: Experimental Setup & Evaluation Protocol

## 9.1 Hardware Platform & Execution Environment

All benchmarks, training workflows, and real-time streaming simulations were conducted on a standardized commodity workstation without GPU acceleration, reflecting typical edge deployment environments.

### Table 9.1: System Specifications & Environment Metadata

| Parameter | Specification |
| :--- | :--- |
| **Host Processor (CPU)** | Intel Core i5-12500H (12 Cores / 16 Threads, 4 Performance @ 4.5 GHz, 8 Efficient @ 3.3 GHz) |
| **Host Memory (RAM)** | 15.69 GB Dual-Channel DDR4/DDR5 |
| **Operating System** | Microsoft Windows 11 Enterprise (x64, Build 10.0.26200) |
| **Python Runtime** | Python 3.14.7 (win32 64-bit AMD64) |
| **Core Machine Learning** | scikit-learn 1.9.1, LightGBM 4.7.0, NumPy 2.4.2, SciPy 1.17.1 |
| **Packet & Network Capture** | Npcap OEM / WinPcap driver, Scapy 2.7.0 |
| **Web Service & UI** | Streamlit 1.55.0, Python `http.server`, psutil 7.2.2 |
| **Random Seed** | Deterministic `seed = 42` enforced across all stochastic processes |

---

## 9.2 Evaluation Metrics & Mathematical Formulations

To provide a comprehensive evaluation spanning classification fidelity, uncertainty calibration, and real-time computational performance, we utilize the following metrics.

### 1. Classification Performance Metrics
Given $C=6$ target classes and class-specific True Positives ($\text{TP}_c$), False Positives ($\text{FP}_c$), and False Negatives ($\text{FN}_c$):

- **Overall Accuracy:** $\text{Acc} = \frac{\sum_{c=1}^C \text{TP}_c}{N}$
- **Macro-Precision ($P_{\text{macro}}$):** Unweighted mean of class precisions:
  $$P_{\text{macro}} = \frac{1}{C} \sum_{c=1}^C \frac{\text{TP}_c}{\text{TP}_c + \text{FP}_c}$$
- **Macro-Recall ($R_{\text{macro}}$):** Unweighted mean of class recalls:
  $$R_{\text{macro}} = \frac{1}{C} \sum_{c=1}^C \frac{\text{TP}_c}{\text{TP}_c + \text{FN}_c}$$
- **Macro-F1 Score ($F_{1,\text{macro}}$):** Harmonic mean of Macro-Precision and Macro-Recall:
  $$F_{1,\text{macro}} = \frac{2 \cdot P_{\text{macro}} \cdot R_{\text{macro}}}{P_{\text{macro}} + R_{\text{macro}}}$$
  *Note:* Macro-F1 is our primary evaluation metric because it treats all six traffic classes equally, preventing dominant classes from masking degradation in smaller classes.
- **Balanced Accuracy:** Average recall achieved across all classes: $\frac{1}{C} \sum_{c=1}^C R_c$.

### 2. Selective Classification & Calibration Metrics
- **Flow Coverage ($\Phi(\tau)$):** Proportion of flows for which the classifier makes a definitive prediction:
  $$\Phi(\tau) = \frac{|\{i : C(\mathbf{x}_i) \ge \tau\}|}{N}$$
- **Selective Accuracy ($\text{Acc}_{\text{sel}}(\tau)$):** Classification accuracy evaluated exclusively over accepted flows:
  $$\text{Acc}_{\text{sel}}(\tau) = \frac{\sum_{i: C(\mathbf{x}_i) \ge \tau} \mathbb{I}(\hat{y}_i = y_i)}{|\{i : C(\mathbf{x}_i) \ge \tau\}|}$$
- **Error Rate Among Accepted Flows:** $\text{Err}_{\text{sel}}(\tau) = 1 - \text{Acc}_{\text{sel}}(\tau)$
- **Expected Calibration Error (ECE):** Partitions predicted probabilities into $M=10$ equally spaced confidence bins $B_m \subset (0, 1]$:
  $$\text{ECE} = \sum_{m=1}^M \frac{|B_m|}{N} \left| \text{acc}(B_m) - \text{conf}(B_m) \right|$$
  where $\text{acc}(B_m) = \frac{1}{|B_m|} \sum_{i \in B_m} \mathbb{I}(\hat{y}_i = y_i)$ and $\text{conf}(B_m) = \frac{1}{|B_m|} \sum_{i \in B_m} C(\mathbf{x}_i)$.
- **Multiclass Brier Score:** Mean squared error between predicted posterior probability vectors and one-hot ground-truth indicators:
  $$\text{Brier} = \frac{1}{N} \sum_{i=1}^N \sum_{c=1}^C (p_{i,c} - y_{i,c})^2$$

### 3. Real-Time Latency & Throughput Metrics
End-to-end classification latency per flow is decomposed into three components:
$$T_{\text{total}} = T_{\text{obs}} + T_{\text{feat}} + T_{\text{inf}}$$
- **Observation Delay ($T_{\text{obs}}$):** Physical wire time between the arrival of the first packet ($t_1$) and the $N$-th packet ($t_N$): $T_{\text{obs}} = t_N - t_1$.
- **Feature Extraction Latency ($T_{\text{feat}}$):** Time required to compute statistical moments from packet header buffers.
- **Inference Latency ($T_{\text{inf}}$):** Algorithmic execution time to evaluate model predictions.
- **Throughput:** Maximum sustainable flows processed per second: $\text{FPS} = \frac{1000}{\text{Mean Pipeline Latency (ms)}}$.
- **Percentiles:** Reported across P50 (median), P95, P99, and maximum values over repeated benchmark runs.
