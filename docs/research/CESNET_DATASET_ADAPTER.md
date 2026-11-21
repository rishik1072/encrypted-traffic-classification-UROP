# CESNET DataZoo Dataset Adapter: Architecture & Feature Semantics

**Project**: Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift  
**Repository**: `c:\UROP project\encrypted-traffic-classification-UROP`  
**Date**: November 2026  
**Status**: APPROVED DESIGN SPECIFICATION  

---

## 1. Scope & Supported Datasets

The CESNET DataZoo adapter (`research.external_datasets.adapters.cesnet.CesnetAdapter`) interfaces with the public benchmark datasets published by CESNET:
1. `CESNET-TLS22` (October 2021)
2. `CESNET-QUIC22` (October–November 2022)
3. `CESNET-TLS-Year22` (Full Year 2022, 52 weekly slices)
4. `CESNET-QUICEXT-25` (2024–2025 QUIC evolution)

---

## 2. Scale Configuration (XS / S / M / L)

CESNET DataZoo supports standardized size subsets:
- **`XS`** (Extra Small): ~10M flows (~4 GB download). Intended for rapid hyperparameter tuning and smoke testing.
- **`S`** (Small — Recommended Default): ~25M flows (~10 GB download). Balances statistical rigor with computational feasibility.
- **`M`** (Medium): ~50M flows (~20 GB download).
- **`L`** (Large): ~100M flows (~40 GB download).
- **Full**: Complete multi-terabyte backbone traces (available through academic agreement).

---

## 3. Critical Feature Semantics: Transport Payload vs Wire Length

> [!CAUTION]
> **CESNET PPI `SIZE` represents transport-layer payload size, NOT link-layer Ethernet frame length.**  
> Equating or silently converting CESNET payload sizes to Dataset V3 wire frame lengths introduces severe systematic error.

### Semantic Distinctions
1. **Transport Payload Size (`SIZE`)**:
   - In CESNET DataZoo, `SIZE` records the number of raw application bytes in the TCP segment or UDP datagram.
   - For pure TCP acknowledgments, SYN, FIN, or RST packets carrying zero application bytes, `SIZE = 0` or the packet is **entirely omitted from the PPI sequence**.
2. **Dataset V3 Wire Frame Length (`captured_link_layer_length_bytes`)**:
   - Represents the complete Ethernet II frame size on the wire (typically 54 to 1514 bytes).
   - A zero-payload TCP ACK still has a frame length of 54 to 66 bytes on the wire.
3. **No Header Guessing Rule**:
   - The adapter strictly forbids adding an assumed header constant (e.g. $+54\text{ bytes}$) because real TCP/IP headers vary dynamically based on TCP options (timestamps, window scaling, SACK), IPv4 options, IPv6 extension headers, and Ethernet VLAN tags.

---

## 4. Exclusion of Target Shortcuts & Leakage Prevention

To prevent trivial accuracy inflation and ensure genuine zero-payload evaluation, the adapter strictly purges the following shortcut fields prior to feature assembly:

| Forbidden Attribute | Reason for Exclusion |
| :--- | :--- |
| **`TLS_SNI` / `QUIC_SNI`** | Server Name Indication plaintext string directly reveals target identity. |
| **`USER_AGENT`** | Discloses client software and application type in plaintext. |
| **`DST_IP` / `SRC_IP`** | Server IP addresses and autonomous systems (ASNs) cause models to memorize IP tables rather than traffic dynamics. |
| **`DST_SUBNET`** | Memorizes provider subnets (e.g., Google or Meta IP blocks). |

---

## 5. Early Packet Prefix Reconstruction ($K = 3, 5, 10, 20, 30$)

CESNET DataZoo records PPI sequences up to length 30:
- `IPT`: Inter-packet arrival times (seconds/milliseconds).
- `DIR`: Direction ($+1$ for client-to-server, $-1$ for server-to-client).
- `SIZE`: Transport payload size.

### Prefix Feature Extraction
For horizon $K \in \{3, 5, 10, 20, 30\}$:
1. Slice the sequence strictly to the first $K$ packets.
2. Compute directional counters:
   - `k{K}_fwd_packets`: Packets with $\text{direction} = 0$.
   - `k{K}_bwd_packets`: Packets with $\text{direction} = 1$.
   - `k{K}_fwd_payload_bytes`: Sum of forward payload bytes.
   - `k{K}_bwd_payload_bytes`: Sum of backward payload bytes.
   - `k{K}_total_payload_bytes`: Total payload bytes in prefix.
   - `k{K}_mean_payload_bytes`, `k{K}_std_payload_bytes`, `k{K}_min_payload_bytes`, `k{K}_max_payload_bytes`.
   - `k{K}_mean_ipt_us`, `k{K}_std_ipt_us`, `k{K}_max_ipt_us`.
   - `k{K}_duration_us`: Microseconds elapsed across first $K$ packets.

> [!IMPORTANT]
> **No full-flow leakage rule**: Features derived from packets beyond index $K-1$, full flow duration, or total flow packet count are strictly prohibited from entering prefix feature vectors.

---

## 6. Partitioning: Temporal Splits and Open-World Evaluation

### 6.1 Temporal Partitioning
- Ingested flows are sorted chronologically by collection period (e.g. `W-2022-44` to `W-2022-45`).
- Slices:
  - **Train**: Earliest 60% of chronological flows.
  - **Validation**: Intermediate 20% of flows.
  - **Test**: Latest 20% of flows.

### 6.2 Known vs Unknown Application Splitting (Open-World)
- In open-world evaluation (`open_world=True`):
  - Top 80% of application classes are designated `is_known_class = True` (eligible for Train/Val/Test).
  - Remaining 20% of applications are designated `is_known_class = False` and placed **strictly into the Test partition**.
  - Models must classify known classes while maintaining a rejection/abstention option for unknown applications.
