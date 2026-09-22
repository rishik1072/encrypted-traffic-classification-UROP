# Research Limitations & Scope Boundaries

Transparent documentation of experimental constraints, environmental dependencies, and methodological boundaries.

---

## 1. Experimental Dataset Scale & Diversity
- **Sample Scale**: The baseline dataset contains 12 synthetic/representative PCAP files across 6 classes. While sufficient for end-to-end pipeline validation and algorithm benchmarking, broad real-world generalization claims require expansion to larger enterprise/ISP datasets (e.g., ISCX, CIC).
- **Class Balance**: Controlled synthetic captures exhibit balanced classes; real-world networks exhibit severe power-law class imbalance.

## 2. Temporal & Protocol Drift
- **Protocol Evolution**: Network applications frequently update encryption ciphers, multiplexing behaviors (e.g. HTTP/2 $\rightarrow$ HTTP/3 / QUIC), and padding strategies, which may shift inter-arrival and burst distributions over time.
- **Temporal Degradation**: Our temporal split experiment demonstrated an F1 degradation from 0.95 to 0.84 when predicting future sessions.

## 3. Metadata-Only Evasion Limitations
- **Active Padding & Morphing**: Sophisticated traffic evasion tools (e.g., Tor obfs4, traffic morphing) can deliberately shape packet sizes and inject dummy packets to mimic other traffic classes.
- **Classification vs Intrusion Detection**: This system performs **traffic category classification** (Web vs Video vs Messaging) and is NOT an intrusion detection system (IDS) or signature-based malware scanner.

## 4. Hardware & Measurement Constraints
- **Resource Measurements**: Latency and memory benchmarks reflect the local evaluation hardware (Windows 11 / Python 3.14). Production C/Rust kernel-bypass drivers (e.g. DPDK/XDP) would achieve substantially higher raw throughput.
