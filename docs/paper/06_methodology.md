# Chapter 6: Methodology & System Architecture

## 6.1 End-to-End System Pipeline

The classification architecture is designed as a modular, stream-oriented processing pipeline that transforms raw physical wire events into actionable application predictions in real time. Figure 6.1 illustrates the six-stage architecture:

```text
+-------------------+      +----------------------+      +-----------------------------+
| Physical Adapter  | ---> | Flow Tracker         | ---> | Zero-Payload Feature Engine |
| (Npcap Driver)    |      | (Bidirectional State)|      | (7 Families / 84 Features)  |
+-------------------+      +----------------------+      +-----------------------------+
                                                                        |
+-------------------+      +----------------------+      +-----------------------------+
| REST API & SOC    | <--- | Decision Policy      | <--- | Preprocessing & Inference   |
| Dashboard (8080)  |      | (Selective / Tau*)   |      | (Decision Tree / LightGBM)  |
+-------------------+      +----------------------+      +-----------------------------+
```

1. **Packet Capture & Header Extraction:** Ingests live Ethernet frames via the Windows Npcap driver. The driver extracts only the Layer-3 (IPv4/IPv6) and Layer-4 (TCP/UDP) header metadata (packet length, direction, TCP flags, microsecond-resolution arrival timestamp). Application payload bytes are discarded immediately in kernel buffers.
2. **Bidirectional Flow State Tracking:** Manages active network conversations using a bidirectional 5-tuple hash key $(\text{IP}_{\text{src}}, \text{IP}_{\text{dst}}, \text{Port}_{\text{src}}, \text{Port}_{\text{dst}}, \text{Protocol})$. The initial observed packet establishes the forward ($\text{fwd}$) direction, while return traffic is classified as backward ($\text{bwd}$). Flows expire after an inactivity timeout of 60.0 seconds or upon observing TCP FIN/RST flags.
3. **Zero-Payload Feature Engine:** Computes running statistical moments, inter-arrival times, byte volume ratios, and burst counters as packets arrive.
4. **Preprocessing & Standardization:** Standardizes features using pre-fitted scaling parameters (z-score normalization or quantile clipping) fitted strictly on training data.
5. **Lightweight Model Inference:** Generates class posterior probabilities $\mathbf{p} = [p_1, p_2, \dots, p_6]$ using serialized estimators.
6. **Confidence & Abstention Policy:** Applies validation-calibrated thresholds to assign one of four standardized operational states (`KNOWN`, `LOW_CONFIDENCE`, `UNKNOWN`, `INSUFFICIENT_EVIDENCE`).

---

## 6.2 Group-Aware Session-Isolated Partitioning Protocol

To prevent session-level data leakage, we enforce a strict group-aware partitioning protocol across `dataset_v2`. 

### Partitioning Rules:
1. **Grouping Criterion:** The grouping key is the user session identifier (`session_id`). A session represents an individual user session or execution of an application.
2. **Split Proportions:** 70% Train, 15% Validation, 15% Locked Test.
3. **Partition Independence:** Let $\mathcal{S}_{\text{train}}$, $\mathcal{S}_{\text{val}}$, and $\mathcal{S}_{\text{test}}$ denote the sets of session IDs assigned to each partition. The splitting algorithm strictly enforces:
   $$\mathcal{S}_{\text{train}} \cap \mathcal{S}_{\text{val}} = \emptyset, \quad \mathcal{S}_{\text{train}} \cap \mathcal{S}_{\text{test}} = \emptyset, \quad \mathcal{S}_{\text{val}} \cap \mathcal{S}_{\text{test}} = \emptyset$$
4. **Flow Distribution:**
   - **Training Partition:** 205 flows across 102 independent sessions.
   - **Validation Partition:** 48 flows across 24 independent sessions.
   - **Locked Test Partition:** 48 flows across 24 independent sessions.
5. **Evaluation Protocol:** All feature selection, hyperparameter tuning, and decision threshold selection are executed strictly using the Train and Validation sets. The Locked Test partition is evaluated exactly once with frozen parameters.

---

## 6.3 Selective Classification & Confidence Policy

In production network environments, forcing a classification decision on an ambiguous flow is hazardous. We implement selective classification (Geifman & El-Yaniv, 2017) parameterized by a rejection threshold $\tau \in [0.0, 1.0]$.

### Mathematical Formulation
Given an input feature vector $\mathbf{x} \in \mathbb{R}^K$, the estimator outputs a predicted class $\hat{y} = \arg\max_{c} p(y=c|\mathbf{x})$ with associated confidence $C(\mathbf{x}) = \max_{c} p(y=c|\mathbf{x})$.

The selective classifier $(f, g)$ is defined as:
$$(f, g)(\mathbf{x}) = \begin{cases} \hat{y} & \text{if } g(\mathbf{x}) = 1 \\ \text{ABSTAIN} & \text{if } g(\mathbf{x}) = 0 \end{cases}$$
where the selection function $g(\mathbf{x})$ evaluates:
$$g(\mathbf{x}) = \mathbb{I}\left(C(\mathbf{x}) \ge \tau \land N_{\text{pkts}} \ge N_{\text{min}}\right)$$

### Operational Decision States
The decision policy outputs one of four explicit operational states:
1. **`KNOWN`:** $C(\mathbf{x}) \ge \tau$ and $\hat{y} \in \{\text{Web}, \text{Video}, \text{Messaging}, \text{VoIP}, \text{File Transfer}, \text{Other}\}$. The flow is accepted and classified.
2. **`LOW_CONFIDENCE`:** $C(\mathbf{x}) < \tau$. The flow exhibits characteristics of known classes but lacks sufficient certainty; the system abstains to avoid false positives.
3. **`UNKNOWN`:** The flow exhibits statistical anomalies inconsistent with all known application profiles (potential zero-day or unmodeled protocol).
4. **`INSUFFICIENT_EVIDENCE`:** The flow has observed fewer than $N_{\text{min}} = 3$ packets. No statistical prediction is attempted.

### Validation-Based Threshold Selection ($\tau^*$)
To avoid evaluating arbitrary thresholds on the test set, the optimal threshold $\tau^*$ is selected strictly on the Validation set by optimizing the selective risk-coverage trade-off:
$$\tau^* = \arg\max_{\tau} \left( \text{Selective\_F1}_{\text{val}}(\tau) \right) \quad \text{subject to} \quad \text{Coverage}_{\text{val}}(\tau) \ge 0.50$$
As established in Chapter 9, this criterion identifies $\tau^* = 0.70$ on validation data.

---

## 6.4 Privacy and Security Guarantees

The architecture implements defense-in-depth privacy controls:
- **Zero-Payload Storage:** No payload bytes are ever stored in RAM, written to temporary files, or serialized to disk.
- **Endpoint Anonymization:** Raw IP and MAC addresses are immediately hashed into keyed pseudonymous tokens ($\text{HMAC-SHA256}$) before event emission, preventing user tracking.
- **Loopback Isolation:** The REST monitoring API and Streamlit SOC dashboard bind strictly to `127.0.0.1`. Remote network binding is explicitly rejected by configuration schema validation.
- **No External Telemetry:** The runtime contains zero telemetry endpoints, external analytics calls, or cloud dependencies.
