# Multi-Dataset Feature Harmonization Specification

**Project**: Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift  
**Repository**: `c:\UROP project\encrypted-traffic-classification-UROP`  
**Date**: November 2026  
**Status**: APPROVED DESIGN SPECIFICATION  

---

## 1. Motivation: Heterogeneous Semantics Across Public Datasets

When benchmarking machine learning models across diverse external encrypted traffic datasets, a major pitfall is **semantic mismatch in packet length and timing definitions**. Different data collection tools record fundamentally different physical or logical quantities:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Complete Physical Wire Frame                          │
├───────────────┬────────────────────────┬────────────────────────────────────┤
│ Ethernet (14B)│ IP Header (20-60B)     │ TCP/UDP Header (8-60B) │ Payload   │
└───────────────┴────────────────────────┴────────────────────────┴───────────┘
▲                                                                 ▲
│                                                                 │
└── Profile A & C (Link-Layer Frame Length)                       └── Profile B (Transport Payload)
```

Attempting to evaluate a model trained on Profile A directly on Profile B without explicit harmonization introduces massive distribution shifts caused purely by measurement definitions rather than network behavior.

---

## 2. Feature Profile Taxonomy

We define four explicit feature profiles implemented in `research.external_datasets.harmonization`:

### Profile A: Dataset V3 Physical Wire Lengths
- **Source**: Dataset V3 physical collector (`research.dataset_v3`).
- **Packet Length**: True link-layer Ethernet II wire frame length (`captured_link_layer_length_bytes`).
- **Control Packets**: Preserves all zero-payload packets (SYN, SYN-ACK, FIN, pure TCP ACKs) with wire lengths of 54 to 66 bytes.
- **Timing**: Microsecond-resolution monotonic hardware arrival timestamps.

### Profile B: CESNET DataZoo Transport Payload Sizes
- **Source**: CESNET DataZoo PPI records (`CESNET-TLS22`, `CESNET-QUIC22`, etc.).
- **Packet Length**: Layer-4 transport payload size (`SIZE`). Excludes Ethernet, IP, and TCP/UDP headers.
- **Control Packets**: Zero-payload TCP packets (e.g. pure ACKs) are **omitted entirely** or recorded as `SIZE = 0`.
- **Timing**: Inter-packet arrival times (`IPT`) in seconds/milliseconds converted to integer microseconds.

### Profile C: PCAP-Derived Link-Layer Wire Frames
- **Source**: CipherSpectrum and ISCXVPN2016 PCAPs.
- **Packet Length**: Link-layer Ethernet II frame length derived from PCAP packet headers (`len(pkt)`).
- **Control Packets**: Retained with non-zero frame lengths (e.g., 54 bytes).
- **Timing**: Microsecond arrival timestamps relative to flow start.

### Common Harmonized Subset (Cross-Profile Invariant)
- **Source**: Dimensionless and relative features computable across all profiles.
- **Features**:
  1. Direction sequence transitions: client-to-server vs server-to-client switch counts.
  2. Direction ratios: forward packet count fraction $\frac{N_{\text{fwd}}}{N_{\text{total}}}$.
  3. Normalized inter-arrival timing: fractional IAT distribution relative to prefix duration.
  4. Prefix duration in microseconds.

---

## 3. The Strict "No Silent Conversion" Invariant

> [!CAUTION]
> **Prohibition of Hardcoded Header Offsets**:  
> Converting Profile B (transport payload) to Profile A or C (wire frame length) by adding a constant offset (e.g. $+54\text{ bytes}$) is **strictly prohibited**.

### Scientific Justification
1. **Dynamic TCP Option Variation**: Modern TCP connections negotiate TCP options in the SYN handshake (Window Scale, Timestamp, SACK Permitted, MSS). These options inflate the TCP header from the 20-byte minimum up to 60 bytes dynamically per packet (e.g. standard Linux TCP headers with timestamps are 32 bytes, not 20 bytes).
2. **IPv4 vs IPv6 Disparity**: IPv4 base headers are 20 bytes; standard IPv6 headers are 40 bytes. An arbitrary constant assumes IPv4 and fails completely under IPv6.
3. **Control Packet Invisibility**: Adding $+54\text{ bytes}$ to payload records does not recover the pure ACK packets that were entirely filtered out at capture time by the CESNET flow exporter.

---

## 4. Cross-Profile Compatibility Matrix

| Train Profile | Test Profile | Allowed Feature Set | Conversion Permitted? |
| :--- | :--- | :--- | :--- |
| **Profile A (Dataset V3)** | **Profile A (Dataset V3)** | Full Profile A Features | Direct |
| **Profile A (Dataset V3)** | **Profile C (PCAP Wire)** | Frame-length & Timing Features | Direct (compatible semantics) |
| **Profile A (Dataset V3)** | **Profile B (CESNET PPI)** | **Common Harmonized Subset Only** | **No conversion; Common subset only** |
| **Profile B (CESNET PPI)** | **Profile B (CESNET PPI)** | Full Profile B Features | Direct |
| **Profile B (CESNET PPI)** | **Profile C (PCAP Wire)** | **Common Harmonized Subset Only** | **No conversion; Common subset only** |
| **Profile C (PCAP Wire)** | **Profile C (PCAP Wire)** | Full Profile C Features | Direct |

Any attempt by a script or model pipeline to evaluate a Profile A/C model on Profile B data using frame lengths raises an explicit `ValueError` in `FeatureHarmonizer.validate_profile_compatibility()`.
