# Research Question & Scientific Motivation

## 🎯 Primary Research Question

> **Can encrypted network traffic be accurately classified in real time across common traffic classes (Web, Video, Messaging, VoIP, File Transfer, Other) using lightweight machine learning models and a compact set of inexpensive statistical features WITHOUT decrypting packet payloads or performing Deep Packet Inspection?**

---

## ⚖️ Multi-Objective Optimization Problem

In resource-constrained cybersecurity and network monitoring environments, maximizing classification accuracy in isolation is insufficient. The primary engineering trade-off is:

$$\max \left[ \text{Classification Fidelity (Macro-F1, Accuracy)} \right] \quad \text{subject to} \quad \min \left[ \text{Feature Count } (K), \text{ Latency}, \text{ Model Size}, \text{ CPU}, \text{ RAM} \right]$$

### Evaluation Dimensions:
1. **Feature Dimension ($K$):** $21 \longrightarrow 15 \longrightarrow 10 \longrightarrow 5 \longrightarrow 3$ features.
2. **Computational Overhead:** Online feature extraction latency ($< 0.1\text{ ms}$) + Model inference latency ($< 1.0\text{ ms}$).
3. **Storage & Serialization:** Model artifact size ($< 1\text{ MB}$).
4. **Early-Prediction Feasibility:** Classification fidelity after observing $N \in \{3, 5, 10, 20\}$ packets.
5. **Generalization Robustness:** Performance preservation across unseen captures, sessions, and chronological shifts.
