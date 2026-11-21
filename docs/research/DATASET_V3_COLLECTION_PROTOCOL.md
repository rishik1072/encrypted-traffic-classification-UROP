# Dataset V3 Physical Collection Protocol

**Project**: Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift  
**Document**: Authoritative Data Collection Standard Operating Procedure (SOP)  
**Date**: November 2026  
**Status**: Approved Pre-Collection Protocol (Phase 2A)

---

## 1. Objectives and Scope

This protocol establishes the standardized procedure for collecting **Dataset V3**: an isolated, privacy-preserving, reproducible corpus of physical network traffic metadata.

Dataset V3 resolves the empirical deficiencies of earlier datasets by enforcing:
1. **100% Genuine Physical Ingestion**: Zero synthetic perturbation or cloning; every record originates from a live physical network adapter.
2. **Explicit Parent-Flow Provenance**: Every flow record maintains immutable lineage (`parent_flow_id == flow_id`).
3. **Multi-Environment Stratification**: Systematic capture across Wi-Fi, Ethernet, and Cellular physical network environments.
4. **Controlled Ground-Truth Attribution**: Rigorous activity-based flow annotation with explicit separation of background traffic.
5. **Early-Prefix Feasibility**: Chronological preservation of packet arrivals enabling prefix reconstruction for horizons $K \in \{1, 3, 5, 10, 20\}$.

> [!IMPORTANT]
> **Pilot Dataset Scope**: The initial target of **300–600 physical flows** (50 flows per class across 6 classes) represents a **pilot dataset** designed for preliminary feasibility and threshold calibration. It must not be declared sufficient for final publication until post-pilot statistical power and variance analyses are conducted.

---

## 2. Environmental Matrix and Adapter Profiles

Data collection must span three distinct physical physical environments to evaluate cross-environment generalization (answering RQ1 and testing $\mathcal{H}_1$):

| Environment ID | Physical Medium | Network Hardware / Driver | Network Topology Characteristics | Tunnel States Evaluated |
| :--- | :--- | :--- | :--- | :--- |
| `env_phys_wifi_01` | **Wi-Fi 6 (802.11ax)** | Intel Wi-Fi 6 AX201 160MHz | Wireless contention, CSMA/CA backoff, multi-path fading, local AP jitter. | `DIRECT`, `VPN` (WireGuard) |
| `env_phys_eth_01` | **Gigabit Ethernet (802.3)**| Realtek PCIe GbE Family Controller | Full-duplex wired medium, minimal queuing jitter, stable packet burst arrivals. | `DIRECT`, `VPN` (WireGuard) |
| `env_phys_cell_01`| **4G / 5G Cellular Hotspot**| USB Tethering / Wi-Fi Hotspot via Carrier | Cellular scheduling delays, carrier-grade NAT (CGNAT), high RTT, bufferbloat. | `DIRECT` |

---

## 3. Application Aliases and Activity Standards Across the 6 Classes

To prevent the classifier from overfitting to a single domain or application binary, each traffic class must be collected across multiple distinct application aliases:

| Canonical Traffic Class | Application Alias | Controlled Activity Description | Session Duration | Minimum Target Flows |
| :--- | :--- | :--- | :---: | :---: |
| **Web** | `chrome_browsing` | Chrome: Navigating Tranco top 100 news, commerce, and informational HTTPS websites. | 60–120 s | 25 |
| **Web** | `firefox_browsing` | Firefox: Multi-tab HTTPS session browsing technical blogs and documentation. | 60–120 s | 25 |
| **Video** | `youtube_1080p` | Streaming 1080p 60fps video over HTTPS/QUIC on YouTube. | 120–180 s | 25 |
| **Video** | `twitch_live` | Watching low-latency live streaming content on Twitch. | 120–180 s | 25 |
| **Messaging** | `signal_desktop` | Signal Desktop: Text messaging, image attachments, and presence pings. | 60–90 s | 25 |
| **Messaging** | `telegram_desktop`| Telegram Desktop: Group channel reading and media synchronization. | 60–90 s | 25 |
| **VoIP** | `discord_voice` | Active two-way voice call in Discord channel (Opus codec over UDP/WebRTC). | 120 s | 25 |
| **VoIP** | `zoom_meeting` | Active video/audio conference meeting in Zoom client. | 120 s | 25 |
| **File Transfer** | `sftp_upload` | SFTP encrypted bulk file upload ($50\,\text{MB}$ random binary payload) via OpenSSH. | 90–120 s | 25 |
| **File Transfer** | `gdrive_download` | Downloading large zip archive ($100\,\text{MB}$) from Google Drive via browser. | 90–120 s | 25 |
| **Other** | `os_telemetry` | Baseline idle system traffic, Windows Update checks, NTP time sync. | 60 s | 25 |
| **Other** | `package_manager` | Running `winget upgrade` / `pip install` package downloads. | 60 s | 25 |

---

## 4. Pre-Collection Environmental Isolation

To maintain high label purity and prevent unmanaged background traffic from contaminating supervised classes:

1. **Terminate Non-Essential Processes**: Close background cloud synchronizers (OneDrive, Dropbox), torrent clients, and auto-updating software prior to collection.
2. **Dedicated Clean Browser Profiles**: Use isolated browser profiles with caching enabled normally (simulating genuine user behavior) but without ad-blocking extensions that alter TLS chunk sizes.
3. **Verify Adapter Routing**: Confirm that the active default gateway routes through the intended physical adapter:
   ```powershell
   Get-NetRoute -DestinationPrefix "0.0.0.0/0" | Select-Object InterfaceAlias, NextHop, RouteMetric
   ```
4. **Administrator Privileges**: Open an elevated PowerShell / terminal prompt to satisfy Npcap kernel driver requirements.

---

## 5. Execution Lifecycle and Command Invocations

Data collection is executed using the isolated Dataset V3 collector script:

```bash
# Example 1: Collecting Web Traffic over Wi-Fi
python -m research.dataset_v3.collector \
    --interface "Wi-Fi" \
    --adapter-type "Wi-Fi" \
    --environment "env_phys_wifi_01" \
    --class "Web" \
    --app "chrome_browsing" \
    --activity "Tranco top 50 informational browsing" \
    --duration 90.0 \
    --tunnel "DIRECT" \
    --operator "operator_rishi"

# Example 2: Collecting VoIP Traffic over Ethernet with VPN
python -m research.dataset_v3.collector \
    --interface "Ethernet" \
    --adapter-type "Ethernet" \
    --environment "env_phys_eth_01" \
    --class "VoIP" \
    --app "discord_voice" \
    --activity "Two-way voice conversation" \
    --duration 120.0 \
    --tunnel "VPN" \
    --operator "operator_rishi"
```

### 5.1 Snaplen and Hardware Header Truncation Guidelines

To enforce structural privacy boundaries at the kernel level, operators may optionally pass `--snaplen 128` (or $\ge 64$ bytes):
1. **Kernel Truncation**: When `snaplen` is specified, the OS Npcap driver truncates raw frame buffers in kernel space before transferring bytes across the user-space boundary to Scapy.
2. **Wire Length Invariance**: Scapy reads the original frame length from the pcap packet header (`packet.wirelen`) and the IP total length header, preserving the authentic on-the-wire packet size (`packet_length`) while storing only truncated bytes (`captured_length`) in transient RAM.
3. **Header Guarantee**: Snaplen must never be set below 64 bytes to guarantee full IP, TCP, and UDP header extraction.

### 5.2 Atomic Staging and Quarantine Lifecycle

To guarantee zero corrupted or partially-written sessions enter the primary benchmark directory:
1. **Isolated Staging**: All active session artifacts are initially written into a private staging directory:
   `data/research_v3/.staging/<session_id>/`
2. **Pre-Publication Integrity Verification**: Upon capture termination, all file descriptors are flushed and closed, and the 21-point automated validator runs against the staged directory.
3. **Atomic Publication**: If and only if all 21 checks pass and `capture_status == "COMPLETE"`, the collector places an immutable `SESSION_COMPLETE` marker file and atomically renames the directory into:
   `data/research_v3/<session_id>/`
4. **Automated Quarantine**: If validation fails or the session was interrupted (e.g., Ctrl+C), the session is atomically moved to:
   `data/research_v3/.incomplete/<session_id>/`
   along with an explanatory `SESSION_INCOMPLETE` marker and diagnostic notes.

### 5.3 Post-Capture Immediate Validation
Upon capture completion, the operator must immediately run the session inspection and validation tools:
```bash
# Inspect session counts and prefix distributions
python scripts/research/dataset_v3/inspect_session.py --session data/research_v3/<session_id>

# Run formal 21-check validation
python scripts/research/dataset_v3/validate_dataset.py --session data/research_v3/<session_id>
```

---

## 6. Failure Recovery and Interruption Handling

1. **Driver Crashes or Socket Drops**: If the physical adapter disconnects, the collector catches the socket exception, writes `capture_status = "INTERRUPTED"`, finalizes flows received up to the disconnect timestamp, and flushes metadata.
2. **Short Incomplete Sessions**: Sessions generating fewer than 3 flows or experiencing packet capture initialization errors must be marked `label_quality = "EXCLUDED"` and quarantined from the primary benchmark.
3. **Accidental Overwrites**: The atomic writer checks for existing `COMPLETED` manifests and raises `FileExistsError` to prevent clobbering completed sessions.
