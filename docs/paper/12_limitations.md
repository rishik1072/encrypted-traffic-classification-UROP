# Chapter 12: System Limitations & Threat Model

In adherence to rigorous scientific standards, this chapter details the explicit operational boundaries, methodological constraints, and threat model of our zero-payload classification framework.

---

## 12.1 Methodological and Algorithmic Limitations

### 1. Closed-World Class Assumption
The primary supervised models are formulated under a closed-world assumption over $C=6$ canonical categories (`Web`, `Video`, `Messaging`, `VoIP`, `File Transfer`, `Other`). In production Internet backbones, thousands of heterogeneous protocols and background daemons coexist. While our confidence abstention policy ($\tau^* = 0.70$) effectively filters out ambiguous flows by assigning `LOW_CONFIDENCE` or `UNKNOWN` states, the classifier is not a dedicated open-set anomaly detector. Highly novel malware protocols or unseen P2P traffic that happen to match the statistical burst profile of video streaming may still produce false positive classifications.

### 2. Class-Conditional Overlap in Modern Interactive Protocols
Modern web applications increasingly blur traditional traffic boundaries. For example:
- Single Page Applications (SPAs) and dynamic web dashboards utilize persistent WebSockets or long-polling HTTP connections that mimic the low-bandwidth, event-driven signaling of `Messaging` applications.
- Modern enterprise collaboration platforms (e.g., Slack, Microsoft Teams, Discord) multiplex text messaging, voice calls, file sharing, and video streaming over identical QUIC or HTTP/2 connections.
Disentangling multiplexed sub-flows within a single encrypted transport session using purely statistical transport features remains an open research challenge.

### 3. Asymmetric Tunnel Degradation
As established in Section 10.3 (`EXP-R11`), statistical classifiers trained on unencapsulated traffic suffer significant degradation when evaluated on WireGuard/WARP tunneled traffic (**0.3407 Macro-F1**, $\Delta\text{F1} = -0.2594$). Fixed MTU clamping (1280 bytes) and cryptographic padding compress the packet length spectrum. Deploying this system in enterprise VPN concentrators requires retraining models on tunnel-encapsulated data.

---

## 12.2 Operational and Platform Limitations

### 1. Windows Npcap Driver Dependency and Privilege Boundaries
On Microsoft Windows 10/11 x64 hosts, capturing physical link-layer frames via the `scapy` / Npcap engine requires:
- An installed Npcap kernel driver.
- Elevated Administrator privileges (User Account Control elevation).
Standard unprivileged users cannot initiate live promiscuous network capture due to Windows OS kernel security boundaries. For unprivileged testing, the software provides a fail-closed `DEMO_MODE` utilizing synthetic packet streams, but this mode is strictly segregated from research claims.

### 2. Multi-Gigabit Single-Threaded Processing Limits
Our streaming Python architecture achieves **81.78 flows/sec** in full end-to-end integration testing and **15,600 flows/sec** in isolated Decision Tree vector inference. While sufficient for small-to-medium enterprise edge links (100 Mbps to 1 Gbps), monitoring high-capacity core links (>10 Gbps) requires re-implementing the packet capture and feature extraction pipeline in C/Rust using Linux eBPF/XDP or DPDK kernel-bypass drivers.

---

## 12.3 Threat Model & Adversarial Evasion

Zero-payload classifiers operate exclusively on observable transport dynamics. Consequently, they are susceptible to intentional adversarial traffic morphing:

1. **Packet Padding (Chaffing):** An adversary can pad application payload bytes with random noise to force all packets to maximum MTU length (1460 bytes), neutralizing packet size moments.
2. **Timing Jitter Injection:** Adversaries can introduce randomized synthetic delays between packets, distorting inter-arrival time distributions.
3. **Dummy Packet Injection:** Injecting bidirectional dummy packets alters packet ratios and burst counts.
4. **Multipath Protocol Shuffling:** Splitting a single application session across multiple concurrent TCP connections or multipath QUIC paths fragments the flow's statistical signature.

Our system does not claim active defense against dedicated cryptographic obfuscators (such as Tor Pluggable Transports or obfs4). It is designed for benign network management, QoS bandwidth allocation, and coarse traffic monitoring in cooperative enterprise networks.

---

## 12.4 Dataset Scale & Environmental Diversity

While `dataset_v2` provides 301 flows and 150 independent sessions collected across physical 802.11ax Wi-Fi, Gigabit Ethernet, and Cellular LTE interfaces under strict group-aware isolation, it represents a single Windows 11 host environment. Validating statistical feature invariance across diverse host operating systems (Linux, macOS, Android, iOS) and geographically dispersed ISP backbones remains an essential direction for future work.
