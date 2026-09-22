# Tunnel-Aware Feature Observability Analysis (WireGuard / Cloudflare WARP)

**Date**: 2026-08-23  
**Project**: Real-Time Encrypted Traffic Classification  
**Environment**: Windows 11 Endpoint capturing real application traffic via Cloudflare WARP (WireGuard UDP tunnel)  

---

## 1. Executive Summary

In modern encrypted network environments, user traffic is increasingly tunneled through encrypted VPN/proxy protocols such as WireGuard, MASQUE (HTTP/3 proxying), and Cloudflare 1.1.1.1 / WARP. 

Under this architecture, **all outer network frames are encapsulated into UDP packets directed to tunnel endpoints (typically port 2408 or port 443)**. This architectural property has fundamental consequences for zero-payload encrypted traffic classification:

1. **Outer Transport Homogenization**: 96.3%+ of captured packets share identical outer transport protocols (UDP), source/destination tunnel endpoints, and fixed transport header overheads.
2. **Payload Opacity**: Zero payload bytes, unencrypted TLS Server Name Indication (SNI), cleartext certificate exchanges, or HTTP/2 headers are observable on the wire.
3. **Statistical Observability**: Only packet lengths, inter-arrival times (IAT), directional packet ratios, burstiness patterns, and total session durations remain observable.

This document systematically delineates what statistical features remain invariant, what signals are confounded by tunneling, and what information is strictly unavailable without payload decryption.

---

## 2. Observability Matrix

| Feature Category | Specific Metrics | Observability Status | Impact of WireGuard/WARP Tunneling |
| :--- | :--- | :---: | :--- |
| **Transport Protocol** | `protocol`, `dst_port` | **Confounded / Constant** | WireGuard encapsulates inner TCP/UDP packets into outer UDP packets. Destination ports point to Cloudflare gateway rather than application origin. |
| **Packet Sizes** | `min_packet_size`, `max_packet_size`, `avg_packet_size`, `packet_size_variance` | **Observable with Padding/Overhead** | WireGuard adds a 32-byte header + 16-byte Poly1305 authentication tag (48 bytes overhead). While MTU clamping occurs (typically 1280-1420 bytes), application payload size variations remain partially visible in aggregate packet sizes. |
| **Inter-Arrival Timing** | `mean_iat`, `median_iat`, `iat_std`, `min_iat`, `max_iat` | **Observable (Subject to Jitter)** | Packet pacing and application burst intervals are preserved, though jitter buffer mechanics and tunnel keepalive pings (every 25s) inject baseline timing noise. |
| **Directional Ratios** | `fwd_bwd_packet_ratio`, `fwd_bwd_byte_ratio` | **Highly Observable** | Asymmetry between request and response data is preserved. Video and File Transfer exhibit heavy downstream asymmetry, whereas VoIP and Messaging show symmetric bi-directional flows. |
| **Burst Characteristics** | `burst_count`, `avg_burst_bytes`, `avg_burst_packets` | **Observable** | High-volume media streaming generates distinct burst pulses (chunking) compared to continuous low-packet VoIP or sporadic interactive Web traffic. |
| **Flow Duration** | `flow_duration` | **Observable (Session Dependent)** | Distinguishes short-lived messaging pings from long-lived video streaming and VoIP calls. |
| **TLS & Application Metadata** | `tls_version`, `cipher_suites`, `sni` | **Completely Hidden** | Inner TLS handshakes are encrypted inside the WireGuard noise protocol handshake before leaving the network interface. |

---

## 3. Tunneling Confounding Effects on Baseline Classifiers

### 3.1 Outer Port Invalidation
In traditional un-tunneled network environments, naive classifiers often rely heavily on well-known destination ports (`80` for HTTP, `443` for HTTPS, `5060` for SIP). In tunneled captures, destination ports are uniform or randomized ephemeral ports, forcing ML models to learn strictly from physical and statistical dynamics.

### 3.2 Packet Padding and MTU Clamping
Because large packets are clamped to the tunnel MTU, bulk data transfers (File Transfer, Video) produce identical maximum packet sizes (`max_packet_size = 1420` bytes). Consequently, `max_packet_size` exhibits zero or near-zero variance across multiple high-throughput traffic classes.

### 3.3 Protocol Invariance
Because `protocol == 17` (UDP) across 96%+ of all clean flows, the `protocol` feature contributes virtually zero entropy for discriminating Web (HTTP/3), Video, Messaging, and VoIP.

---

## 4. Methodological Safeguards & Ethical Commitments

To preserve strict privacy and security standards in alignment with the research charter:
- **Zero Payload Inspection**: No deep packet inspection (DPI), payload scraping, or SNI extraction is attempted.
- **Pure Statistical Analysis**: All features are computed solely from packet header lengths, timestamps, and directional flow counters.
- **Empirical Feature Selection**: Features are validated via grouped cross-validation to ensure that only generalizable statistical properties (e.g. byte ratios, IAT distributions) are retained for inference.
