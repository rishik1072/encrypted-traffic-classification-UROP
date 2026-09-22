# Final Research Status & Scientific Claims Ledger

**Status:** ACTIVE AUDIT  
**Date:** September 2026  
**Authoritative Dataset:** `dataset_v2` (Multi-Environment Real Network Traffic)  
**Evaluation Standard:** Session-Level Group-Aware Isolation, Locked Test Split  

---

## 1. Executive Summary

This document establishes the authoritative scientific boundary of the Encrypted Traffic Classification research project. It explicitly distinguishes claims backed by empirical evidence on real network traffic from legacy synthetic claims, catalogs known system limitations, and defines the recommended claims for academic publication.

---

## 2. Verified Claims (Backed by Real-World Empirical Evidence)

### Claim 1: Feasibility of Zero-Payload Classification Under Group-Aware Evaluation
- **Verdict:** **VERIFIED (REAL)** (`EXP-R09`)
- **Evidence:** On 301 flows (150 independent sessions) from `dataset_v2`, zero-payload statistical features achieve **0.5873 Macro-F1** (0.5833 Accuracy) with Random Forest and **0.5802 Macro-F1** (0.5833 Accuracy) with Decision Tree under strict session-isolated splitting.
- **Allowed Publication Claim:** *"Zero-payload transport-layer statistical features classify real encrypted traffic into 6 canonical application classes with 0.5873 Macro-F1 under rigorous group-aware evaluation."*

### Claim 2: Pareto Optimality of Ultra-Lightweight Decision Trees
- **Verdict:** **VERIFIED (REAL)** (`EXP-R09`, `EXP-R14`)
- **Evidence:** A CART Decision Tree trained on 10 features achieves **0.5802 Macro-F1** (98.8% of Random Forest ensemble performance) while requiring only **0.0553 ms** ($55.3\ \mu\text{s}$) median inference time ($16,366\text{ flows/sec}$) and **3.11 KB** serialized disk footprint.
- **Allowed Publication Claim:** *"A single 10-feature Decision Tree achieves comparable classification fidelity to a 100-tree ensemble while reducing memory footprint to 3.11 KB and inference latency to 55 microseconds."*

### Claim 3: Invariance to Physical Transmission Media (Network Drift)
- **Verdict:** **VERIFIED (REAL)** (`EXP-R11`, `REG-05`, `REG-06`)
- **Evidence:** Models trained on Wi-Fi generalized to Ethernet and Cellular LTE test traffic with **0.9325 Macro-F1** (0.9333 Accuracy). Under artificial network impairment (delay and jitter), performance reached **0.9030 Macro-F1**.
- **Allowed Publication Claim:** *"Zero-payload statistical signatures demonstrate strong transferability across physical Layer-1/2 media (Wi-Fi, Gigabit Ethernet, Cellular LTE), retaining >0.90 Macro-F1 across unseen network interfaces."*

### Claim 4: Actionable Early-Stage Flow Classification
- **Verdict:** **VERIFIED (REAL)** (`EXP-R12`)
- **Evidence:** Evaluating traffic after observing only the first 3 packets achieves **0.6111 Macro-F1** with **91.7% flow coverage** in **80.4 ms** total latency. Retrospective full-flow classification delays decisions by **59.7 seconds** without accuracy benefit.
- **Allowed Publication Claim:** *"Observing the first 3 packets of an encrypted flow provides 0.6111 Macro-F1 triage in 80.4 ms, reducing time-to-classification by over 700x compared to retrospective full-flow evaluation."*

### Claim 5: Monotonic Risk Reduction via Calibrated Selective Classification
- **Verdict:** **VERIFIED (REAL)** (`EXP-R13`)
- **Evidence:** Confidence-gated abstention reduces classification error rate monotonically from **45.83%** (at 100% coverage, $\tau=0.0$) down to **26.92%** at 54.17% coverage ($\tau^*=0.70$, Selective Macro-F1: **0.6515**), and reaches **10.00% error** (90.00% selective accuracy) at $\tau=0.90$ (20.83% coverage). Model Expected Calibration Error (ECE) is **0.1996**.
- **Allowed Publication Claim:** *"Validation-calibrated selective classification monotonically reduces decision error on real traffic from 45.8% to 26.9% at 54.2% coverage (tau*=0.70), reaching 90.0% accuracy on high-confidence flows."*

### Claim 6: Complete Zero-Payload Privacy & Localhost Security
- **Verdict:** **VERIFIED (REAL)** (`EXP-R15`, Product Test Suite)
- **Evidence:** Code verification and automated test suites confirm:
  1. Application payloads are never inspected, buffered, or stored.
  2. No raw IP or MAC addresses are written to research outputs or logs (SHA-256 session masking only).
  3. The REST API and SOC dashboard bind strictly to `127.0.0.1`.
  4. Zero cloud telemetry endpoints or external credentials exist.
- **Allowed Publication Claim:** *"The monitoring pipeline preserves end-user privacy by operating exclusively on Layer-3/4 transport metadata with zero payload persistence, zero cleartext IP storage, and complete loopback isolation."*

---

## 3. Unsupported / Retracted Claims (Forensic De-biasing)

The following claims found in early drafts or exploratory notes are unsupported by real empirical data and must **NOT** be claimed in academic publications:

1. **"95% Overall Real-World Classification Accuracy"**
   - *Status:* **RETRACTED / SYNTHETIC ONLY**
   - *Forensic Cause:* Derived from early 12-flow Scapy synthetic fixtures (`dataset_v1`, `EXP-01`). Real-world performance on `dataset_v2` is **0.5873 Macro-F1**.
2. **"Seamless Generalization from Direct Traffic to WireGuard/WARP Tunnels"**
   - *Status:* **RETRACTED / CONTRADICTED**
   - *Forensic Cause:* Direct models transfer poorly to WireGuard tunneled traffic (`EXP-R11`, `REG-08b`), dropping to **0.3407 Macro-F1** ($\Delta\text{F1}=-0.2466$) due to WireGuard packet padding and handshake standardization.
3. **"Sub-Millisecond End-to-End Classification Across the Network"**
   - *Status:* **RETRACTED / MISLEADING**
   - *Forensic Cause:* While raw vector inference takes $0.055\text{ ms}$, physical packet arrival delay on the wire requires **64 to 331 ms**. Physical observation delay accounts for >99% of actual operational time.
4. **"Phase 8 Hierarchical 0.9500 Selective Macro-F1"**
   - *Status:* **RETRACTED / ARTIFACT DECEPTION**
   - *Forensic Cause:* `phase8_final_test.csv` reported 0.95 Macro-F1 because the model rejected **100% of test samples** (0.0% coverage). Superseded by `EXP-R13`.

---

## 4. Unresolved Issues & Research Boundaries

1. **Class-Conditional Imbalance on Specific Fine Classes:**
   - While coarse families (Bulk/Streaming vs. Interactive) separate cleanly, fine distinction between `Messaging` and `Web` remains prone to confusion during long interactive browsing sessions.
2. **Adversarial Flow Padding & Traffic Shaping:**
   - The current zero-payload feature pipeline does not incorporate defensive defenses against active adversarial traffic morphing (e.g., randomized packet padding injection).
3. **Multi-Tenant Concurrent Port Saturation:**
   - The real-time pipeline sniffs up to 730 flows/sec on single-threaded Python workers; higher line rates (> 1 Gbps) require multi-process C-accelerated eBPF or AF_PACKET dispatch.

---

## 5. Final System Limitations

1. **Windows Platform Driver Dependency:**
   - In `LIVE_MODE`, packet capture requires an active Npcap driver installation and administrative privileges on Windows. Standard unprivileged users must operate in `DEMO_MODE`.
2. **Closed-World Class Assumption:**
   - The primary classifier operates over 6 canonical classes. Flows from unseen third-party protocols must be filtered through the confidence abstention policy ($\tau=0.70$) to avoid forced misclassification.
3. **Tunnel Asymmetry:**
   - Classifiers trained on unencapsulated traffic require retraining on tunneled traffic to recognize WireGuard/WARP flows reliably.

---

## 6. Recommended Paper Claims & Title Strategy

### Recommended Paper Title:
*"Practical Zero-Payload Encrypted Traffic Classification: Evaluating Group-Aware Generalization, Early-Stage Triage, and Calibrated Abstention on Real Network Traffic"*

### Recommended Abstract Headline Findings:
1. *"Zero-payload Layer-3/4 statistical features achieve 0.5873 Macro-F1 on real encrypted traffic under rigorous group-aware session isolation, disproving over-optimistic synthetic claims."*
2. *"A 3.11 KB Decision Tree achieves 98.8% of ensemble accuracy with 58-microsecond single-flow inference, enabling wire-speed embedded execution."*
3. *"Early-stage classification at 3 packets achieves 0.6111 Macro-F1 in 79.94 ms, reducing classification latency by over 700x relative to full flow observation."*
4. *"Validation-calibrated selective classification monotonically reduces decision error from 45.8% to 26.9% at 54.2% coverage (tau*=0.70) and delivers 90.0% accuracy on high-confidence traffic (tau=0.90)."*
5. *"Statistical signatures generalize robustly across physical network media (0.9325 F1), but experience significant degradation (-0.2594 F1) under unadapted WireGuard tunnel encapsulation."*
