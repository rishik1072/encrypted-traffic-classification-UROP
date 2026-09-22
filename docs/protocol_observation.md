# Protocol Observation & Capture Environment Audit

**Document Status**: Official Research Dataset Observation Report  
**Dataset Reference**: Real Dataset v1 (60 Controlled Windows 11 Sessions)  
**Analysis Target**: Protocol distribution, encapsulation behavior, UDP/QUIC dominance, and tunnel impact.

---

## 1. Executive Summary

During Phase 1.5 data auditing, a profound protocol asymmetry was identified across all 60 real sessions:
- **Total Real Flows**: 189
- **UDP Flows**: 182 (96.30%)
- **Non-IP / Other Raw Protocol Flows**: 6 (3.17%)
- **TCP Flows**: 1 (0.53%)

This document records the exact physical and network environment factors driving this observation, analyzes whether transport-layer protocol functions as an artificial class proxy, and outlines methodological considerations for subsequent model training.

---

## 2. Capture Path & Network Interface Configuration

### 2.1 Interface & Route Analysis
The real data capture testbed operates on Windows 11 Enterprise (`lab_env_win11`) connected via an Intel(R) Wi-Fi 6 AX201 wireless interface with a Cloudflare WARP client installed (`CloudflareWARP` WireGuard/BoringTun interface tunnel).

```
+-------------------------------------------------------------+
|                     User Application                         |
|   (Browser / YouTube / Discord / WhatsApp / FTP / Spotify)  |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|              Windows 11 TCP/IP Stack & Sockets              |
+-------------------------------------------------------------+
                              |
       +----------------------+----------------------+
       | (Direct Wi-Fi)                             | (WARP Tunnel)
       v                                            v
+-----------------------------+             +-------------------------------+
|  Local Broadcast & Control  |             | Encapsulated Application Flow |
|  - SSDP (UDP 1900)          |             | - WireGuard UDP 52783/50468   |
|  - LLMNR (UDP 5355)         |             | - QUIC/HTTP3 UDP 443          |
|  - mDNS (UDP 5353)          |             +-------------------------------+
|  - NetBIOS (UDP 137)        |                             |
+-----------------------------+                             v
               \                                            /
                +-----------------+------------------------+
                                  |
                                  v
              +---------------------------------------+
              | Real-Time Packet Sniffer / WinPcap    |
              | (Promiscuous Wi-Fi Interface Capture) |
              +---------------------------------------+
```

### 2.2 Impact of Encapsulation and Modern Web Protocols

1. **Cloudflare WARP Tunnel Encapsulation**:
   - Modern system-level privacy/VPN tunnels encapsulate outbound and inbound TCP connections into encrypted UDP datagram tunnels (typically WireGuard or MASQUE over UDP ports 52783, 50468, and 2408).
   - Consequently, application traffic that initiates as TCP at the OS socket layer appears on the physical wireless adapter as high-throughput UDP flows targeting the tunnel gateway.

2. **HTTP/3 and QUIC Proliferation**:
   - Modern browser engines (Chromium/Edge), video platforms (YouTube, Netflix), and messaging CDNs prioritize HTTP/3 over QUIC (UDP port 443).
   - In sessions where direct TLS over TCP might conventionally occur, QUIC 0-RTT handshakes and UDP framing represent the default observed transport.

---

## 3. Protocol Distribution Breakdown

| Traffic Class | Total Flows | UDP Flows | TCP Flows | OTHER Flows | Dominant Transport |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Web** | 32 | 32 (100.0%) | 0 (0.0%) | 0 (0.0%) | UDP (QUIC 443 / Tunnel 52783) |
| **Video** | 26 | 26 (100.0%) | 0 (0.0%) | 0 (0.0%) | UDP (QUIC 443 / Tunnel 52783) |
| **Messaging** | 29 | 29 (100.0%) | 0 (0.0%) | 0 (0.0%) | UDP (QUIC 443 / Tunnel 52783) |
| **VoIP** | 29 | 29 (100.0%) | 0 (0.0%) | 0 (0.0%) | UDP (RTP/Tunnel 52783) |
| **File Transfer**| 25 | 25 (100.0%) | 0 (0.0%) | 0 (0.0%) | UDP (Tunnel 52783 / QUIC 443) |
| **Other** | 48 | 41 (85.4%) | 1 (2.1%) | 6 (12.5%) | UDP (Tunnel 50468 / mDNS / SSDP) |
| **Total** | **189** | **182 (96.3%)**| **1 (0.5%)**| **6 (3.2%)** | **UDP Dominant** |

---

## 4. Label Leakage & Proxy Risk Evaluation

### 4.1 Is Protocol a Proxy for the Class Label?
- In synthetic datasets, protocol is frequently hand-assigned (e.g. TCP for Web/File Transfer, UDP for VoIP/Video).
- In this **real-world dataset**, `protocol == UDP` occurs uniformly across **all 6 traffic classes** (Web: 100%, Video: 100%, Messaging: 100%, VoIP: 100%, File Transfer: 100%, Other: 85.4%).
- **Information Theoretic Verification**:
  - Base class entropy $H(Y) = 2.5456\text{ bits}$.
  - Mutual Information $I(\text{protocol}; Y) = 0.0763\text{ bits}$ (near zero).
- **Conclusion**: The `protocol` feature does **NOT** act as a proxy or cheat code for any traffic class. Models cannot achieve high classification accuracy simply by splitting on transport protocol.

---

## 5. Methodological Guidelines for Machine Learning

1. **Feature Engineering Independence**:
   - Class differentiation relies on statistical temporal dynamics (IAT variance, burst packet distributions, packet size distributions, burst byte volumes), rather than transport protocol headers.
2. **Tunnel Generalization Integrity**:
   - The observed dataset reflects modern realistic client environments where VPN tunnels and QUIC encapsulation predominate.
3. **Preservation of Raw PCAPs**:
   - Original PCAPs and raw metadata files are preserved intact. No retroactive artificial modification of packet headers was performed.
