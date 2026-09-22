# Phase 10 — Windows Local Productization V1 Report

**Application**: Encrypted Traffic Monitor  
**Version**: 1.0.0  
**Build Target**: Windows 10/11 x64  
**Date**: 2026-08-26  
**Architecture**: Privacy-Preserving Zero-Payload Local Network Classifier  

---

## 1. Product Goal

The objective of Phase 10 was to transform the historical research artifacts and benchmarked pipelines from Phases 1–9 into an installable, user-friendly desktop application for Microsoft Windows without invalidating research benchmarks, retraining models, or exposing network payload data.

**"Encrypted Traffic Monitor"** enables standard Windows users and cybersecurity analysts to monitor live network traffic on Wi-Fi and Ethernet adapters, extract lightweight statistical flow features in real-time, execute calibrated machine learning inference locally, and inspect security telemetry on a local SOC dashboard without writing code or interacting with complex command-line arguments.

---

## 2. Product Architecture & Layering

The product layer (`product/`) orchestrates existing sub-systems (`capture/`, `flows/`, `preprocessing/`, `models/`, `realtime/`, `dashboard/`) without duplicating logic:

```
+-------------------------------------------------------------------------+
|                  Encrypted Traffic Monitor Desktop App                  |
|                 (EncryptedTrafficMonitor.exe / python -m product)        |
+-------------------------------------------------------------------------+
       |                                                    |
       v                                                    v
+-----------------------------+             +-----------------------------+
|    Product Core Manager     |             |      Local REST API         |
| (Preflight, Health, Security)             |      (http://127.0.0.1:8080)|
+-----------------------------+             +-----------------------------+
       |                                                    |
       +--------------------+-------------------------------+
                            |
       +--------------------+-------------------------------+
       |                                                    |
       v                                                    v
+-----------------------------+             +-----------------------------+
|   Real-Time Capture Engine  |             |     Streamlit SOC Console   |
|   - Adapter Discovery       |             |   - Live Traffic KPIs       |
|   - Npcap / Scapy Sniffer   |             |   - Flow Lifecycle Table    |
|   - Zero-Payload Extractor  |             |   - Rejection & Confidence  |
|   - Model Registry Loader   |             |   - Model Integrity Status  |
|   - Platt-Scaled Classifier |             |   - Local Privacy Badges    |
+-----------------------------+             +-----------------------------+
                            |
                            v
+-------------------------------------------------------------------------+
|                    Local Storage (data/local/)                          |
|   - logs/ (application.log, capture.log, prediction.log, health.log)    |
|   - events/ (Sanitized prediction JSONL/CSV - No Payloads, No PII)      |
|   - metrics/ (Aggregated performance telemetry)                         |
+-------------------------------------------------------------------------+
```

---

## 3. Windows Support

- **Operating Systems**: Windows 11 (22H2/23H2/24H2) and Windows 10 (21H2/22H2) 64-bit.
- **Elevation Detection**: Automated detection of administrative privilege status using Windows Win32 API (`ctypes.windll.shell32.IsUserAnAdmin`).
- **Driver Integration**: Seamless detection of Npcap kernel driver (`npcap.sys`) and Npcap/WinPcap user-mode DLLs (`wpcap.dll`).
- **Dual-Executable Split Packaging**: PyInstaller packaging script (`installer/build_windows.ps1`) compiles two dedicated executables into `dist/EncryptedTrafficMonitor/`:
  1. `EncryptedTrafficMonitor.exe`: Main orchestrator, network adapter detection, Npcap sniffer, ML model inference, zero-payload feature extraction, process supervisor, and `127.0.0.1:8080` local REST API.
  2. `EncryptedTrafficDashboard.exe`: Dedicated Streamlit SOC dashboard runtime binding locally to `http://127.0.0.1:8501`.
- **Supervision & Health Polling**: `ProductLifecycleManager` supervises `EncryptedTrafficDashboard.exe`, polls `http://127.0.0.1:8501` for HTTP readiness before declaring monitoring active, logs structured events to `data/local/logs/packaged_runtime.log`, and guarantees clean zero-orphan process termination.

---

## 4. Installation & Deployment

- **End-User Distribution**: Extract release archive and run `EncryptedTrafficMonitor.exe`.
- **Developer Start**: One-command live monitoring via `python scripts/start_local.py` or demo replay via `python scripts/start_demo.py`.
- **Preflight Diagnostics**: Automated preflight diagnostic verification (`python -m product --check-only`).
- **Documentation**: Comprehensive installation guide available in `release/WINDOWS_INSTALL.md`.

---

## 5. Local Packet Capture

- **Adapter Discovery**: `product/adapter_manager.py` resolves friendly names (Wi-Fi, Ethernet, Virtual NICs), link speed descriptors, and Npcap GUID paths.
- **Default Resolution**: Automatically prioritizes active internet-connected Wi-Fi and Ethernet adapters while ignoring loopbacks and VPN tunnels.
- **Fail-Closed Guarantee**: Live capture strictly terminates or reports degraded state on capture errors; synthetic traffic is never injected into LIVE mode.

---

## 6. Zero-Payload Privacy Policy

The product enforces an unchangeable zero-payload and zero-PII security boundary:
1. **No Raw Packets**: Packet payloads are discarded in memory immediately after extracting statistical headers.
2. **Immutable Flag**: `save_raw_packets` is hard-locked to `False` in `product/config.py` and `product/security.py`.
3. **No Raw IP / MAC Persistence**: Network flow events are keyed by ephemeral SHA-256 session and flow identifiers.
4. **Localhost Isolation**: The embedded REST API binds exclusively to `127.0.0.1` and denies all non-loopback connections.

---

## 7. Model Registry & Verification

- **Authoritative Registry**: All model references resolve dynamically from `results/models/production_registry.json`.
- **Cryptographic Hash Verification**:
  - Production Model ID: `model_lightgbm_v1`
  - Model SHA-256: `a5a65da6d74e9b3e61e654ac6a81066aaf2b247996b8364d6d71d826023c08cd`
  - Preprocessor SHA-256: `a4b16727401d19417572f97d7b66656adf2f9d1964a53bf5eefcca8c35351e21`
  - Feature Schema SHA-256: `9178786dc46dba8800c66b551c3ebcf78034f357f53405bf6b2ed70b40d88101`
- **Feature Profile**: Canonical `lightweight_10` feature subset with Platt scaling sigmoid probability calibration.

---

## 8. Dashboard & Visual Console

- **Technology**: Local Streamlit SOC console on `http://127.0.0.1:8501`.
- **Key Modules**:
  - System Status: Live adapter name, Npcap status, model integrity check, feature schema hash.
  - Live Telemetry: Packets/sec, flow counts, p95/p99 inference latency, memory and queue depth.
  - Classification Table: Real-time feed of flows, predicted classes (Web, Video, Messaging, VoIP, File Transfer, Other), family categories, and confidence score.
  - Rejection & Confidence: Breakdown of `KNOWN_CLASS`, `LOW_CONFIDENCE`, `UNKNOWN`, and `INSUFFICIENT_EVIDENCE`.
  - Privacy Indicators: Real-time display of `Zero Payload: PASS` and `Local Only: PASS`.

---

## 9. Security & Boundary Assurances

| Boundary Check | Enforcement Mechanism | Status |
| :--- | :--- | :--- |
| Zero-Payload Feature Extraction | Memory-only statistical computation | PASS |
| Raw Packet Disk Persistence | Immutable `save_raw_packets = False` | PASS |
| IP / MAC Address Persistence | Sanitization filter in `product/security.py` | PASS |
| Cloud Telemetry Isolation | `local_only = True` enforced at config load | PASS |
| Local API Endpoint Binding | Hard-coded binding to `127.0.0.1` | PASS |

---

## 10. Process Lifecycle & Resource Management

- **Managed Child Processes**: `ProductLifecycleManager` tracks PIDs and execution state for both the classification engine and the Streamlit dashboard.
- **Clean Shutdown**: Handles `SIGINT`, `SIGTERM`, and normal exits via registered `atexit` hooks.
- **Orphan Prevention**: Subprocesses are terminated gracefully with a 2-second timeout before escalating to process termination kill.
- **Repeat Cycles**: Verified clean repeat start/stop cycles without memory or process leaks.

---

## 11. Performance & Telemetry

- **Inference Latency**: Sub-millisecond inference time (~0.003 ms per flow).
- **Feature Computation**: Under 20 µs per packet burst.
- **Memory Footprint**: ~2.5 KB per active flow in the flow table.
- **Log Management**: Rotating logs in `data/local/logs/` capped at 10 MB per file with 5 backups.

---

## 12. Multi-Machine Compatibility

Detailed compatibility matrix documented in `docs/windows_compatibility.md`:
- Tested on Windows 11 (24H2) x64 and Windows 10 x64.
- Validated with Npcap 1.70+ in WinPcap API-compatible mode.
- Verified on Wi-Fi 6 (802.11ax) adapters and Gigabit Ethernet controllers.

---

## 13. Research Integrity & Honest Limitations

1. **Research Benchmark Invariance**: Historical F1-scores, accuracy numbers, confusion matrices, and ablation tables from Phases 1–9 remain completely unchanged.
2. **Encapsulation Boundary**: Outer VPN/tunnel encapsulation (Cloudflare WARP / WireGuard) obscures intra-application packet sizing; coarse family classification (Bulk_Streaming vs Interactive) is the recommended operational boundary.
3. **Abstention Policy**: Early flows with packet count $N < 5$ correctly transition to `INSUFFICIENT_EVIDENCE`.

---

## 14. Future Enterprise / Cloud Architecture Roadmap

For future multi-agent or enterprise SOC deployments (Phase 11+):
- Optional mTLS-authenticated local agent forwarding to enterprise SIEM (Splunk, Elastic, Microsoft Sentinel).
- Cryptographic attestation of model binaries before distributed edge deployment.
- Differential privacy aggregation for multi-tenant telemetry without payload or IP exposure.
