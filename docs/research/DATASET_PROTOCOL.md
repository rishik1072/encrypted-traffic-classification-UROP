# Research Dataset Governance & Collection Protocol

**Repository:** Real-Time Encrypted Traffic Classification Using Lightweight Machine Learning Models  
**Single Source of Truth Status:** ACTIVE  
**Last Updated:** September 2026  
**Standard:** Rigorous Experimental Network Traffic Governance  

---

## 1. Protocol Objective & Ethical Boundaries

This protocol establishes mandatory research standards for the collection, annotation, partitioning, and validation of encrypted network traffic datasets in this repository. 

### Core Ethical & Security Principles
1. **Zero-Payload Non-DPI Guarantee:** Packet ingress processing operates strictly on Layer-3/4 transport metadata (packet sizes, inter-arrival times, burst distributions, directionality, protocol flags). Packet payload contents are stripped immediately and never decrypted, stored, or inspected.
2. **Privacy Protection & De-identification:** Network topology shortcuts (MAC addresses, IP addresses, autonomous system numbers, specific domain names) are scrubbed from ML training matrices.
3. **No Shortcut Learning:** Port numbers (e.g., standard port 443 vs 53) are strictly forbidden from serving as primary discriminators. Classification must rely on transport dynamics that generalize across arbitrary ports and encrypted tunnels.
4. **Strict Ground Truth Verification:** Ground-truth labels are established through application process pinning and controlled test execution scripts—never by heuristic port mapping or payload snooping.

---

## 2. Dataset Taxonomy & Origin Classification

Every dataset artifact utilized in this repository must belong to exactly one of the following four authoritative categories:

```
                          ┌────────────────────────┐
                          │   DATASET ORIGIN TAXONOMY   │
                          └───────────┬────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         ▼                            ▼                            ▼
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│    REAL_DATA     │         │SYNTHETIC_FIXTURE │         │    DEMO_DATA     │
│ (Empirical Base) │         │ (Unit / CI Test) │         │ (Interactive UI) │
└────────┬─────────┘         └────────┬─────────┘         └────────┬─────────┘
         │                            │                            │
         │ Controlled Captures        │ Scapy Handshakes           │ Replayed Logs
         │ Real Hardware              │ Deterministic Seeds        │ Synthetic Streams
         │ WIREGUARD / WARP Tunnels   │ Toy Linear Separability    │ Zero Research Use
         │ Multi-Environment          │ Strict CI Gating Only      │
         ▼                            ▼                            ▼
  ALLOWED FOR REAL             STRICTLY FORBIDDEN           STRICTLY FORBIDDEN
  RESEARCH CLAIMS              FOR REAL RESEARCH            FOR REAL RESEARCH
                               CLAIMS                       CLAIMS
```

### 1. `REAL_DATA`
- **Definition:** Network traffic captured from physical or virtual network interfaces executing real application workloads under realistic user interactions.
- **Permitted Use:** Authoritative benchmark training, hyperparameter validation, model ranking, Pareto frontier analysis, and final held-out test evaluations.
- **Registered Versions:** `dataset_real_v1` (Wi-Fi baseline), `dataset_v2` (Multi-environment benchmark).

### 2. `SYNTHETIC_FIXTURE`
- **Definition:** Deterministic packets synthesized via Scapy scripts for testing interface contracts, pipeline integrity, and corner cases.
- **Permitted Use:** Fast unit tests (`test_*.py`), continuous integration, and pipeline validation.
- **Forbidden Use:** Any scientific claim regarding real-world accuracy, generalization, latency, or model comparison.
- **Registered Versions:** `dataset_v1` (12 sample PCAPs).

### 3. `DEMO_DATA`
- **Definition:** Looped packet streams, serialized JSONL events, or synthetic replay logs designed to drive the Streamlit SOC Dashboard in demonstration mode without requiring network administrator privileges.
- **Permitted Use:** UI verification, layout testing, presentation demos.
- **Forbidden Use:** Model training, evaluation, or benchmarking.
- **Registered Versions:** `demo_data`.

### 4. `EXTERNAL_BENCHMARK`
- **Definition:** Standard public reference datasets (e.g., ISCX-VPN-2016, USTC-TFC-2016).
- **Permitted Use:** Macro-level comparative literature review and cross-dataset validation.
- **Registered Versions:** `external_benchmarks`.

---

## 3. Real-Data Collection Protocol

### A. Controlled Hardware & Network Environments
Data collection for `dataset_real_v1` and `dataset_v2` was performed across three distinct physical access environments:

| Environment ID | Access Medium | Interface | MTU | Network Topology |
| :--- | :--- | :--- | :--- | :--- |
| `env_win11_wifi` | Wi-Fi 6 (802.11ax) | Intel Wi-Fi 6 AX201 160MHz | 1500 | Home/Office AP $\rightarrow$ Commercial ISP Fiber |
| `env_win11_eth` | Gigabit Ethernet (802.3) | Realtek PCIe GbE Family | 1500 | Managed Switch $\rightarrow$ Campus Gateway |
| `env_win11_cellular` | LTE / 5G Mobile Hotspot | USB Tethered Interface | 1420 | Mobile Carrier APN $\rightarrow$ Commercial Mobile Core |

### B. Tunneling Configuration & Encapsulation
To represent modern privacy-preserving transport protocols, traffic sessions were recorded under two explicit tunnel states:
1. **`warp_enabled` (WireGuard / Cloudflare WARP):** All client Layer-3 packets are encapsulated into ChaCha20-Poly1305 encrypted UDP datagrams targeting Cloudflare edge servers. Transport headers are normalized, packet lengths are padded, and internal port/IP information is completely concealed from intermediate observers.
2. **`warp_disabled` (Direct Transport):** Standard native TLS 1.3 / QUIC connections directly negotiating with destination servers.

### C. Traffic Class Definitions & Activity Scripts
Traffic was generated using controlled user activity automation to prevent label ambiguity:

| Traffic Class | Activity Variants | Applications / Endpoints | Protocol Distribution |
| :--- | :--- | :--- | :--- |
| **Web** | `web_tech_blogs`<br>`web_ecommerce`<br>`web_github_docs` | Chrome/Edge browsing: GitHub, Wikipedia, Amazon, CNN, arXiv. Multi-asset HTTP/2 and TLS 1.3. | TCP (TLS 1.3) / UDP (QUIC) |
| **Video** | `vid_twitch_live`<br>`vid_vimeo_720p`<br>`vid_netflix_4k`<br>`vid_dailymotion_sd` | YouTube (1080p60/4K), Twitch live streams, Vimeo adaptive DASH/HLS buffering chunks. | TCP (TLS) / UDP (QUIC) |
| **Messaging** | `msg_whatsapp_web`<br>`msg_slack_chat`<br>`msg_discord_text` | Discord text chat, Slack WebSocket messaging, Signal Desktop, WhatsApp Web polling. | TCP (WebSockets/WSS) |
| **VoIP** | `voip_zoom_meeting`<br>`voip_discord_call`<br>`voip_google_meet` | Interactive two-way voice call sessions (Discord Voice UDP, Zoom Audio RTP, WebRTC audio). | UDP (SRTP / WebRTC) |
| **File Transfer**| `file_sftp_binary`<br>`file_https_large_zip`<br>`file_drive_sync` | Bulk binary uploads and downloads (SFTP over SSH, 100MB HTTPS ZIP downloads, Google Drive sync). | TCP (SSH / HTTPS) |
| **Other** | `other_windows_telemetry`<br>`other_doh_queries`<br>`other_ntp_sync` | OS background telemetry, DNS-over-HTTPS (Cloudflare DoH), NTP time synchronization, Windows Update handshakes. | UDP / TCP |

---

## 4. Data Cleaning, Filtering & Exclusion Policies

Raw packet streams undergo strict deterministic cleaning before inclusion into feature datasets:

```
[ RAW PACKET STREAM ]
          │
          ▼
[ Packet Quality Filter ] ──▶ DROP if frame length < 20 bytes or corrupt checksum
          │
          ▼
[ Bidirectional Flow Aggregation ] (5-tuple window, 60s idle timeout)
          │
          ▼
[ Flow Quality Threshold ]
  ├── DROP if total_packet_count < 3 (Transient handshakes / port probes)
  └── DROP if total_bytes < 128 (Zero-data keepalives)
          │
          ▼
[ Leakage Prevention Filter ]
  └── STRIP src_ip, dst_ip, src_port, dst_port, session_id, capture_date
          │
          ▼
[ AUTHORITATIVE FEATURE RECORD ]
```

---

## 5. Group-Aware Split Governance (Zero Leakage Protocol)

To eliminate data leakage, all dataset partitions must adhere to group-aware splitting:

1. **Session Isolation:**
   $$\text{Sessions}(\text{Train}) \cap \text{Sessions}(\text{Test}) = \emptyset$$
   $$\text{Sessions}(\text{Train}) \cap \text{Sessions}(\text{Validation}) = \emptyset$$
   Flows belonging to the same application execution session cannot appear across both training and evaluation splits.
2. **Temporal Independence:**
   For chronological evaluation, a strict time boundary $T_{split}$ is established:
   $$\forall f_{train} \in \text{Train}, \quad t_{start}(f_{train}) < T_{split}$$
   $$\forall f_{test} \in \text{Test}, \quad t_{start}(f_{test}) \ge T_{split}$$
3. **Partition Locking:**
   - **Training Set (70%):** Parameter optimization.
   - **Validation Set (15%):** Model selection, hyperparameter tuning, feature subset ranking, and threshold calibration.
   - **Test Set (15%):** Locked until final model verification. Test sets must never be used for feature selection or threshold optimization.

---

## 6. Programmatic Integrity Guard

All experimental scripts must invoke the registry validation guard before executing training:

```python
from training.dataset_registry import DatasetRegistry

registry = DatasetRegistry()

# Enforces that 'dataset_id' is an authoritative real dataset
registry.validate_real_data_claim(dataset_id="dataset_v2", records=loaded_records)
```

If an experiment attempts to use `dataset_v1` (synthetic) or `demo_data` while claiming real-world results, `validate_real_data_claim()` raises a fatal `ValueError`, terminating execution immediately.
