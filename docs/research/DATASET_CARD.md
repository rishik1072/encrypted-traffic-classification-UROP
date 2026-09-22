# Dataset Card: Encrypted Network Traffic Benchmark

**Repository:** Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models  
**Single Source of Truth Status:** ACTIVE  
**Last Updated:** September 2026  
**Format:** Academic Dataset Specification (Gebru et al. / Datasheets for Datasets Standard)  

---

## 1. Dataset Overview & Intended Use

This dataset benchmark supports empirical research in **real-time, zero-payload, privacy-preserving classification of encrypted network sessions** into six canonical categories:
1. **Web:** Interactive HTTPS web browsing, search queries, documentation reading, and multi-asset page loads.
2. **Video:** Adaptive bitrate video streaming (YouTube, Twitch live feeds, Vimeo, Netflix).
3. **Messaging:** Instant messaging, chat exchanges, and WebSocket presence heartbeats (Signal, Slack, Discord text, WhatsApp Web).
4. **VoIP:** Real-time bidirectional voice and video calls (Discord Voice, Zoom Audio, WebRTC audio).
5. **File Transfer:** Bulk binary uploads and downloads (SFTP over SSH, large HTTPS archives, cloud storage synchronization).
6. **Other:** Background OS telemetry, DNS-over-HTTPS (DoH), and NTP synchronization.

### Intended Research Applications
- Evaluation of Layer-3/4 transport dynamics (packet lengths, inter-arrival times, burst behavior, directionality).
- Zero-payload security monitoring: application payload bytes are stripped at ingress; zero TLS decryption, zero private key inspection, zero DPI.
- Lightweight edge and endpoint classification under realistic variability (network jitter, latency, packet loss, Cloudflare WARP / WireGuard encapsulation).

---

## 2. Dataset Lineage & Inventory

The repository contains five cataloged dataset definitions (audited in [`results/tables/research_dataset_inventory.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/research_dataset_inventory.csv)):

| Dataset ID | Version | Origin Category | Real Data? | Sessions | Flows | Classes | Environments | Tunnels | Primary Feature Path | Checksum (SHA-256) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`dataset_v1`** | 1.0.0 | `SYNTHETIC_FIXTURE` | **No** | 12 | 12 | 6 | `lab_env_a`, `lab_env_b` | `direct_unencapsulated` | `data/processed/features/features_cleaned.csv` | `2b9090acff8bfb22...` |
| **`dataset_real_v1`** | 1.1.0 | `REAL_DATA` | **Yes** | 60 | 48 | 6 | `lab_env_win11` | `warp_enabled`, `direct` | `data/processed/features/features_real_clean.csv` | `6cf742c5519d88a1...` |
| **`dataset_v2`** | 2.0.0 | `REAL_DATA` | **Yes** | 150 | 301 | 6 | `env_win11_wifi`, `env_win11_eth`, `env_win11_cellular` | `warp_enabled`, `warp_disabled` | `data/processed/features/features_real_clean_v2.csv` | `cd3193ecdd2ecb48...` |
| **`demo_data`** | 1.0.0 | `DEMO_DATA` | **No** | 6 | 20 | 6 | `demo_virtual_tap` | `warp_simulated` | `data/local/sample_packet_stream.jsonl` | `N/A` |
| **`external_benchmarks`**| ref | `EXTERNAL_BENCHMARK`| **No** | 0 | 0 | 4 | `unb_crc_lab`, `ustc_network` | `openvpn_tun`, `ipsec` | `data/external/README.md` | `N/A` |

---

## 3. Dataset Composition & Class Distribution

### Authoritative Benchmark: `dataset_v2` (301 Flows across 150 Sessions)

```
Traffic Class Breakdown in dataset_v2:
┌─────────────────┬──────────┬────────┬──────────────┬────────────────┐
│ Traffic Class   │ Sessions │ Flows  │ Pkt Range    │ Byte Range     │
├─────────────────┼──────────┼────────┼──────────────┼────────────────┤
│ Web             │ 25       │ 50     │ 800 - 6,000  │ 200KB - 4.6MB  │
│ Video           │ 25       │ 50     │ 900 - 19,000 │ 250KB - 22.3MB │
│ Messaging       │ 25       │ 50     │ 700 - 52,000 │ 170KB - 61.4MB │
│ VoIP            │ 25       │ 50     │ 600 - 1,500  │ 120KB - 400KB  │
│ File Transfer   │ 25       │ 51     │ 650 - 1,700  │ 135KB - 530KB  │
│ Other           │ 25       │ 50     │ 640 - 2,900  │ 145KB - 1.8MB  │
├─────────────────┼──────────┼────────┼──────────────┼────────────────┤
│ Total           │ 150      │ 301    │ 600 - 52,000 │ 120KB - 61.4MB │
└─────────────────┴──────────┴────────┴──────────────┴────────────────┘
```

### Access Environments & Network Impairment Breakdown
- **Physical Access:** Wi-Fi 6 (90 sessions), Gigabit Ethernet (30 sessions), LTE Cellular (30 sessions).
- **Network Conditions:** Normal (102 sessions), Low Bandwidth (24 sessions), High Latency (18 sessions), Packet Loss (6 sessions).
- **Tunnel States:** Cloudflare WARP / WireGuard enabled (132 sessions), Direct unencapsulated (18 sessions).
- **Capture Days:** Day 1 (24 sessions), Day 2 (24 sessions), Day 3 (24 sessions), Day 4 (78 sessions).

---

## 4. Collection Protocol & Methodology

1. **Hardware Setup:** Intel Core i7 Windows 11 workstation with dedicated gigabit Ethernet and Intel Wi-Fi 6 AX201 wireless network interfaces.
2. **Packet Tap:** Ingress sniffing performed using Scapy with native Npcap kernel-level packet buffering (`snaplen: 262144`).
3. **Ground-Truth Labeling:**
   - Active application automation scripts launched single target applications in isolation.
   - Ground truth assigned based on active process execution logs (`session_log.jsonl`), avoiding heuristic port or DNS matching.
   - Inter-session gaps of $\ge 30$ seconds enforced to ensure complete socket closure and active timeout drainage.
4. **Zero-Payload Stripping:** Application payload bytes were discarded at the tap ring buffer before flow aggregation.

---

## 5. Inclusion & Exclusion Criteria

### Inclusion Criteria
- Flow must have at least **3 packets** ($N_{total} \ge 3$) to ensure valid Layer-4 handshake representation.
- Flow must transfer at least **128 total wire bytes** ($B_{total} \ge 128$) to exclude empty keepalives.
- Flow must have unambiguous session-to-class ground-truth mapping in `data/dataset_manifest.csv`.
- Must have verified origin tag `data_origin == 'real'`.

### Exclusion Criteria
- Transient port scanners and incomplete TCP RST floods.
- Link-local broadcast traffic (mDNS, SSDP, LLMNR, ARP, DHCP).
- Identifiers that permit topological shortcut learning:
  - Source and Destination IP addresses.
  - Source and Destination port numbers (e.g., port 443, 53, 22).
  - MAC addresses and VLAN identifiers.
  - Capture timestamps and file IDs.

---

## 6. Dataset Quality & Integrity Audit

As verified in [`results/tables/research_dataset_quality.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/research_dataset_quality.csv):

| Quality Check | `dataset_v1` (Synthetic) | `dataset_real_v1` (Real Baseline) | `dataset_v2` (Real Benchmark) |
| :--- | :--- | :--- | :--- |
| **Total Flow Records** | 11 | 121 (48 clean) | 301 |
| **Duplicate Flow Signatures** | 0 | 0 | 0 |
| **Duplicate Captures** | 0 | 0 | 0 |
| **Missing Labels** | 0 | 0 | 0 |
| **Impossible Timestamps ($t < 0$)** | 0 | 0 | 0 |
| **Malformed Flow IDs** | 0 | 0 | 0 |
| **Contradictory Metadata** | 0 | 0 | 0 |
| **Class Imbalance Ratio** | 2.00 | 1.05 | **1.02 (Balanced)** |
| **Split Group Overlap (Leakage)** | 0 | 0 (0 sessions overlap) | 0 (0 sessions overlap) |
| **Audit Status** | `SYNTHETIC_ONLY` | `VALID (REAL)` | `AUTHORITATIVE (REAL)` |

---

## 7. Known Limitations & Research Boundaries

1. **WireGuard / WARP Feature Space Compression:** Encapsulation normalizes MTU to 1420 bytes, applies packet padding, and coalesces ACKs. Packet length distributions overlap substantially between Web and Messaging. Timing dynamics (IAT variance and burst rates) become the primary discriminators.
2. **Held-Out Test Sample Size:** In the current `dataset_v2` split, the held-out test partition comprises 12 flows across 6 sessions (2 per class). While strictly leakage-free, statistical power is constrained; future phases should scale the test partition to $N \ge 100$ independent sessions.
3. **Single Platform Capture:** Captures originated from Windows 11 endpoints; cross-OS generalization (e.g., Linux/macOS/Android TCP stack dynamics) remains an open research question.

---

## 8. Ethical & Privacy Considerations

- **Non-Invasive:** Operates entirely passively without active network probing or traffic manipulation.
- **Zero TLS Interception:** No root CA injection, no man-in-the-middle decryption, no credential extraction.
- **No Personal Identifiable Information (PII):** IP addresses, hostnames, and user credentials are omitted from all published tables and feature files.
