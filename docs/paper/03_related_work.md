# Chapter 3: Related Work

## 3.1 Historical Evolution: From Port Numbers to Statistical Signatures

Network traffic classification has progressed through three major paradigms:

1. **Port-Based Identification:** In early Internet architectures, standard well-known TCP/UDP port numbers assigned by IANA (e.g., port 80 for HTTP, port 21 for FTP) provided reliable classification. However, the advent of dynamic port allocation, port masquerading, peer-to-peer (P2P) networks, and universal HTTP/HTTPS port multiplexing (port 443) rendered port-based heuristics obsolete.
2. **Deep Packet Inspection (DPI):** Network appliances inspect application-layer payloads for distinctive regular expressions, protocol signatures, and magic byte sequences. While highly accurate for unencrypted traffic, DPI requires immense processing power, introduces significant memory buffer overhead, and is completely thwarted by modern end-to-end cryptographic protocols like TLS 1.3, QUIC, and WireGuard.
3. **Statistical Flow and Behavioral Fingerprinting:** Pioneered by Paxson (1994), Moore and Zuev (2005), and Crotti et al. (2007), statistical classification characterizes network sessions via aggregate distributions—such as packet size histograms, inter-arrival time (IAT) variance, bidirectional byte ratios, and burst behavior. Because these metrics depend only on transport-layer metadata, they remain observable even when payloads are completely encrypted.

---

## 3.2 Machine Learning and Deep Learning Paradigms

### Statistical Machine Learning Classifiers
Traditional machine learning algorithms—including Logistic Regression, Naive Bayes, Support Vector Machines (SVM), CART Decision Trees, Random Forests, and Gradient Boosted Decision Trees (GBDT / LightGBM)—have been extensively applied to statistical traffic features. Random Forest ensembles and GBDTs typically achieve the highest accuracy in benchmark studies due to their capacity to capture non-linear feature interactions and handle tabular data with heterogeneous feature scales. However, as demonstrated in our benchmarks, complex ensembles incur substantial latency penalties during inference ($4.25\text{ ms}$ for Random Forest vs. $0.058\text{ ms}$ for a single Decision Tree), which can overwhelm edge devices operating under sub-millisecond line-rate budgets.

### Deep Learning and Representation Learning
Recent research has increasingly focused on deep learning architectures, including 1D and 2D Convolutional Neural Networks (CNNs) (Wang et al., 2017), Recurrent Neural Networks (RNNs/LSTMs), and Transformer-based models (e.g., ET-BERT, Lin et al., 2022). These models take raw packet byte prefixes or sequential packet headers as input, automatically extracting hierarchical representations. 

While deep learning approaches report high benchmark accuracy, they introduce substantial drawbacks for real-time edge deployment:
- **Computational Footprint:** Deep models require hundreds of megabytes or gigabytes of memory, rendering them unsuitable for deployment on low-power consumer routers, IoT gateways, or programmable network switches (e.g., P4 hardware).
- **Inference Latency:** Evaluating multi-layer neural networks or Transformer attention mechanisms requires tens of milliseconds per flow, far exceeding the strict microsecond budgets required for per-flow line-rate switching.
- **Susceptibility to Concept Drift:** Deep networks trained on raw byte sequences often overfit to specific handshake byte patterns (such as TLS cipher suite lists or extension orders) that change rapidly across browser versions and OS patches.

Our work intentionally focuses on lightweight classical estimators (Decision Trees, LightGBM, Random Forest) to rigorously evaluate whether ultra-compact models can provide adequate classification fidelity while satisfying wire-speed edge latency constraints.

---

## 3.3 Methodological Pitfalls and Evaluation Crises

A growing body of literature highlights systemic evaluation failures in applied machine learning for networking and security:

- **Data Snooping and Session Leakage:** Arp et al. (2022) and Pendlebury et al. (2019) demonstrated that random train/test splitting on network datasets introduces severe data leakage. When multiple flows from the same user session or network capture are split across partitions, classifiers learn ephemeral host identifiers (e.g., server IP addresses, ephemeral client ports, or specific TCP timestamp options) rather than application-intrinsic transport behaviors.
- **Synthetic Fixture Bias:** Evaluating models on synthetic or loopback traffic generates artificial confidence. Synthetic generators produce deterministic packet generation rates and uniform packet lengths that do not reflect physical network bufferbloat, wireless contention, or packet loss.
- **Overlooking Domain Shift:** Most studies evaluate models exclusively in-domain (training and testing on identical network environments). Studies that investigate out-of-domain transfer (e.g., transferring from Wi-Fi to Cellular or unencapsulated to tunneled traffic) are exceedingly rare, leaving the vulnerability of statistical models under protocol shifts unquantified.

---

## 3.4 Early Traffic Classification

Early traffic classification aims to identify the application class within the first few packets of a connection, enabling real-time QoS enforcement, firewall routing, or early intrusion interception. Bernaille et al. (2006) demonstrated that early packet size sequences in TCP connections carry substantial application intent during protocol handshakes. 

However, prior studies on early classification suffer from two primary limitations:
1. **Offline Packet-Horizon Evaluation:** Most studies evaluate early classification by artificially truncating pre-collected PCAP files in an offline setting, reporting only the model's accuracy on the truncated feature vectors.
2. **Neglecting Physical Observation Delay:** Prior literature routinely equates early classification with sub-millisecond real-time capability, conflating algorithmic vector inference time with the physical time required for packets to traverse the physical network. In this work, we explicitly separate physical packet arrival delay from algorithmic inference latency, demonstrating that physical wire delay accounts for >99% of total operational classification latency.

---

## 3.5 Selective Classification and Confidence Calibration

In operational environments, forced classification on ambiguous or out-of-distribution flows leads to catastrophic false positives. Selective classification (Geifman & El-Yaniv, 2017) introduces an abstention mechanism where a classifier outputs a prediction only when its confidence exceeds a specified threshold $\tau$, otherwise assigning an `UNKNOWN` or `LOW_CONFIDENCE` status.

Furthermore, modern classification models are frequently uncalibrated (Guo et al., 2017), meaning predicted softmax probabilities do not reflect true empirical probabilities of correctness. Despite its critical importance for network defense, calibrated selective prediction has remained largely unstudied in the context of encrypted traffic classification. This work provides an empirical study of confidence calibration (measuring ECE and Brier score) and validates a 4-state selective policy on real locked test flows.
