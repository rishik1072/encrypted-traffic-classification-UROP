# ISCXVPN2016 Dataset Adapter: Architecture & Feature Semantics

**Project**: Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift  
**Repository**: `c:\UROP project\encrypted-traffic-classification-UROP`  
**Date**: November 2026  
**Status**: APPROVED DESIGN SPECIFICATION  

---

## 1. Scope & Dataset Provenance

The ISCXVPN2016 adapter (`research.external_datasets.adapters.iscxvpn2016.IscxVpn2016Adapter`) interfaces with the widely cited encrypted and VPN traffic benchmark published by the University of New Brunswick (UNB) Canadian Institute for Cybersecurity:
> **Reference**: Gerard Draper-Gil, Arash Habibi Lashkari, Mohammad Saiful Islam Mamun, and Ali A. Ghorbani, *"Characterization of Encrypted and VPN Traffic Using Large-Scale Data Analytics"*, ICISSP 2016.  
> **Repository ID**: `iscxvpn2016`  
> **Source Format**: Standard `.pcap` files organized by service and tunnel mode.  
> **Volume**: ~28 GB raw PCAPs across VPN and non-VPN captures.

---

## 2. Classification Tasks & Taxonomy

The adapter structures ISCXVPN2016 data across two standardized classification tasks:

### 2.1 Multi-Class Traffic Category Task (`label`)
Maps individual applications to 6 standardized service categories:

| Target Category | Mapped Applications in ISCX Capture |
| :--- | :--- |
| **`Chat`** | AIM, Facebook Chat, Hangouts, ICQ, Skype Chat |
| **`Email`** | Gmail, Thunderbird/IMAP/POP3, Webmail |
| **`File_Transfer`** | FTPS, SFTP, Skype File Transfer |
| **`P2P`** | BitTorrent, uTorrent |
| **`Streaming`** | YouTube, Netflix, Vimeo, Spotify |
| **`VoIP`** | Skype Voice Calls, Hangouts Voice, VoipBuster |

### 2.2 Binary Encapsulation Task (`label_category`)
- **`VPN`**: Encapsulated within an OpenVPN tunnel.
- **`Non-VPN`**: Direct encrypted transport without VPN tunneling.

---

## 3. Bidirectional Flow Reconstruction

Because raw ISCX captures contain interleaved packets from multiple concurrent connections, the adapter performs deterministic 5-tuple bidirectional flow reconstruction:

```
Raw PCAP Stream
  │
  ▼
Canonical 5-Tuple Grouping:
  fkey = (min(src_ip, dst_ip), max(src_ip, dst_ip), min(sport, dport), max(sport, dport), proto)
  │
  ├── Filter: Require protocol == TCP (6) or UDP (17)
  ├── Filter: Discard single-packet noise flows (< 2 packets)
  │
  ├── Direction Assignment:
  │     Packets with src_ip == flow_initiator_ip → Direction 0 (Client -> Server)
  │     Packets with src_ip != flow_initiator_ip → Direction 1 (Server -> Client)
  │
  ├── Relative Microsecond Timing:
  │     relative_time_us = (pkt.time - flow_start_time) * 1e6
  │     iat_us = (pkt.time - previous_pkt.time) * 1e6
  │
  └── Strict Zero-Payload Disposal:
        Extract len(pkt); immediately discard payload bytes.
```

---

## 4. Scientific Caveats & Artifact Warnings

> [!WARNING]
> **Legacy Protocol Distribution (2015 Capture)**:  
> - ISCXVPN2016 traces were collected in 2015. They contain deprecated protocols including **TLS 1.0, TLS 1.1, and SSLv3**, as well as legacy TLS 1.2 cipher suites (CBC-mode ciphers with HMAC-SHA1).
> - Several captured applications (AIM, ICQ, older Skype desktop protocols) are now obsolete.
> - Models trained on ISCXVPN2016 may learn legacy handshake size patterns (e.g., short TLS 1.0 ClientHello records) that do not transfer to modern TLS 1.3 or QUIC traffic.

> [!CAUTION]
> **Severe Risk of Server IP Memorization & Leakage**:  
> - In ISCXVPN2016, laboratory capture topology used a very small set of fixed public servers and local VPN gateway addresses.
> - If `SRC_IP`, `DST_IP`, or fixed server ports (e.g. OpenVPN port 1194) are included in feature sets, classifiers achieve artificially high accuracy (>99%) purely by memorizing IP subnets rather than learning traffic dynamics.
> - The adapter strictly purges IP addresses and TCP/UDP ports from the generated feature vectors.

---

## 5. Early Packet Prefix Extraction ($K = 3, 5, 10, 20$)

Consistent with the Dataset V3 and CipherSpectrum interfaces, early prefix vectors are reconstructed for horizons $K \in \{3, 5, 10, 20\}$:
- Forward/backward packet counts (`k{K}_fwd_packets`, `k{K}_bwd_packets`).
- Forward/backward and total link-layer frame bytes (`k{K}_fwd_frame_bytes`, `k{K}_bwd_frame_bytes`, `k{K}_total_frame_bytes`).
- Frame length distribution statistics (mean, std, min, max).
- Timing dynamics (mean, std, max IAT in microseconds, and prefix duration).

Zero payload bytes and no full-flow statistics are exposed to the prefix feature vectors.

---

## 6. Partitioning Strategy

- **Stratified Flow Split**: 60% Train, 20% Validation, 20% Test stratified across the 6 traffic categories.
- **VPN Domain Disjoint Split**: Evaluates whether classifiers trained on non-VPN traffic generalize to VPN-tunneled traffic (and vice-versa).
