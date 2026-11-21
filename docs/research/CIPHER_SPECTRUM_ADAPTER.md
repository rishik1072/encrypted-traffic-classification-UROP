# CipherSpectrum Dataset Adapter: Architecture & Feature Semantics

**Project**: Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift  
**Repository**: `c:\UROP project\encrypted-traffic-classification-UROP`  
**Date**: November 2026  
**Status**: APPROVED DESIGN SPECIFICATION  

---

## 1. Scope & Dataset Provenance

The CipherSpectrum adapter (`research.external_datasets.adapters.cipherspectrum.CipherSpectrumAdapter`) interfaces with the TLS 1.3 PCAP benchmark dataset introduced in:
> **Reference**: "SoK: Decoding the Enigma of Encrypted Network Traffic Classifiers", IEEE Symposium on Security and Privacy (S&P), 2024.  
> **Repository ID**: `cipherspectrum`  
> **Source Format**: Standard `.pcap` files capturing complete TLS 1.3 handshakes and application records.

### Core Dataset Characteristics
- **Volume**: ~120,000 PCAP traces (~15 GB raw).
- **Target Domains**: 40 distinct web domains (e.g. Google, Wikipedia, Amazon, Twitter).
- **Cryptographic Protocol**: Strictly TLS 1.3 across multiple cryptographic configurations.
- **Primary Cipher Suites**:
  1. `TLS_AES_128_GCM_SHA256`
  2. `TLS_AES_256_GCM_SHA384`
  3. `TLS_CHACHA20_POLY1305_SHA256`

---

## 2. Dual Research Dimensions: Domain Attribution vs Cipher Suite Robustness

The CipherSpectrum dataset provides two orthogonal evaluation axes:

### 2.1 40-Domain Website Attribution Task
- **Label**: Target domain name (e.g., `google`, `cloudflare`, `wikipedia`).
- **Nature of Task**: Closed-world and open-world website fingerprinting / domain attribution.
- **Scientific Significance**: Evaluates whether early timing and frame length dynamics can distinguish encrypted destinations without relying on plaintext Server Name Indication (`TLS_SNI`).

### 2.2 Cipher Suite Environment Shift
- **Label Category / Attribute**: One of the three negotiated TLS 1.3 cipher suites.
- **Scientific Significance**: Different cipher suites use different authenticated encryption algorithms (AES-GCM with 128-bit or 256-bit keys vs ChaCha20-Poly1305 stream cipher). While record padding and TLS 1.3 inner plaintext formatting introduce slight size differences, an invariant classifier must generalize across cipher suites without experiencing accuracy collapse.

---

## 3. Ingestion & Zero-Payload Enforcement

```
Raw PCAP File (e.g. domain_ciphersuite_01.pcap)
  │
  ▼
Scapy PcapReader (streaming header inspection)
  │
  ├── Extract: Frame Length (len(pkt))
  ├── Extract: Direction (0 = Client->Server, 1 = Server->Client)
  ├── Extract: Relative Timestamp & IAT (microseconds)
  │
  ├── PURGE: IP Addresses, TCP Ports (prevent table memorization)
  └── DISCARD: Application payload bytes (zero payload persistence)
  │
  ▼
ExternalFlowRecord (Profile C: Wire Frame Lengths)
```

### Zero-Payload Enforcement Guarantees
1. **Header-Only Ingestion**: Only the frame length (`len(pkt)`), IP layer source/destination addresses (used solely to assign binary direction relative to flow initiator), and arrival timestamps are read.
2. **Payload Disposal**: Application payload bytes (encrypted TLS ClientHello extensions, ServerHello, EncryptedExtensions, and ApplicationData records) are **never extracted, stored in memory structures, or persisted to disk**.
3. **No Shortcut Leakage**: `TLS_SNI`, server IP addresses, client IP addresses, and ephemeral TCP ports are excluded from feature vectors.

---

## 4. Length Semantics: Profile C (Link-Layer Wire Frame Length)

- In CipherSpectrum PCAPs, packet lengths represent the **link-layer Ethernet II frame length** (Profile C):
  $$\text{length} = \text{len(pkt)} = 14\text{B (Ethernet)} + 20\text{--}60\text{B (IP)} + 20\text{--}60\text{B (TCP)} + \text{Payload}$$
- Zero-payload TCP control packets (SYN, pure ACK, FIN, RST) appear with non-zero frame lengths (typically 54 to 66 bytes).
- **Distinction from Profile B (CESNET DataZoo)**: Profile C includes link-layer and transport-layer headers. It cannot be combined with Profile B without explicit feature harmonization.

---

## 5. Early Packet Prefix Extraction ($K = 3, 5, 10, 20$)

For each flow, early prefix features are extracted for horizons $K \in \{3, 5, 10, 20\}$:

| Feature Name | Description | Formula / Source |
| :--- | :--- | :--- |
| `k{K}_packet_count` | Number of observed packets in prefix | $\min(K, N)$ |
| `k{K}_fwd_packets` | Forward (client-to-server) packet count | $\sum_{i=1}^{\min(K,N)} \mathbb{I}(\text{dir}_i = 0)$ |
| `k{K}_bwd_packets` | Backward (server-to-client) packet count | $\sum_{i=1}^{\min(K,N)} \mathbb{I}(\text{dir}_i = 1)$ |
| `k{K}_fwd_frame_bytes` | Total forward link-layer frame bytes | $\sum_{i, \text{dir}_i=0} \text{len}_i$ |
| `k{K}_bwd_frame_bytes` | Total backward link-layer frame bytes | $\sum_{i, \text{dir}_i=1} \text{len}_i$ |
| `k{K}_total_frame_bytes`| Total link-layer frame bytes in prefix | $\sum_{i=1}^{\min(K,N)} \text{len}_i$ |
| `k{K}_mean_frame_bytes` | Mean frame length in prefix | $\frac{1}{\min(K,N)} \sum \text{len}_i$ |
| `k{K}_std_frame_bytes`  | Standard deviation of frame lengths | Sample standard deviation |
| `k{K}_min_frame_bytes`  | Minimum frame length in prefix | $\min_{i} \text{len}_i$ |
| `k{K}_max_frame_bytes`  | Maximum frame length in prefix | $\max_{i} \text{len}_i$ |
| `k{K}_mean_ipt_us`      | Mean inter-packet arrival time ($\mu s$) | $\frac{1}{\min(K,N)-1} \sum \text{IAT}_i$ |
| `k{K}_std_ipt_us`       | Standard deviation of IAT ($\mu s$) | Sample standard deviation |
| `k{K}_max_ipt_us`       | Maximum inter-packet arrival time ($\mu s$) | $\max_i \text{IAT}_i$ |
| `k{K}_duration_us`      | Microseconds elapsed across first $K$ pkts | $t_{\min(K,N)} - t_1$ |

> [!IMPORTANT]
> **No Future Leakage**: No packet beyond index $K-1$, nor total flow duration or overall byte counts, are permitted in prefix feature extraction.

---

## 6. Partitioning & Evaluation Modes

The adapter supports three distinct partitioning schemes:
1. **Stratified Domain Split**: 60% Train, 20% Validation, 20% Test stratified by domain label.
2. **Open-World Domain Split**: Known domains (top 80%) allocated across Train, Val, and Test; unknown domains (remaining 20%) allocated strictly to the Test partition.
3. **Cross-Cipher-Suite Shift Evaluation**: Train on flows from cipher suite $A$ (e.g. `TLS_AES_128_GCM_SHA256`) and test generalization on flows from cipher suite $B$ (e.g. `TLS_CHACHA20_POLY1305_SHA256`).
