# Production Real-Time Encrypted Traffic Classification & SOC Monitoring Release

## Windows 10/11 x64 Hardened Release

### System Overview
This release provides a production-grade, payload-agnostic encrypted network traffic monitoring engine and real-time SOC console for Windows 10 and 11 (x64). Built with strict zero-payload privacy, sub-millisecond inference latency, cryptographic model registries, and confidence-gated abstention policies.

---

## 🚀 Quickstart & Installation Validation

### Run End-to-End Installation & Hardening Validator
Verify all 9 system requirements, dependencies, model hashes, network adapters, and port bindings:
```powershell
python scripts/validate_installation.py
```

### Run Production Health & Diagnostic Check
```powershell
python -m product.health
```

---

## 💻 Operating Modes

### Option A: Safe Offline Simulated Replay (DEMO_MODE)
*Recommended for initial evaluation, UI demonstrations, and unprivileged user accounts.*
```powershell
# Terminal 1: Launch Monitor & Local REST API (Port 8080)
python -m realtime.run --mode demo --delay 0.1

# Terminal 2: Launch Streamlit SOC Dashboard (Port 8501)
streamlit run dashboard/app.py
```

### Option B: Live Network Interface Sniffing (LIVE_MODE)
*Requires Administrator elevation and Npcap driver.*
```powershell
# In an Administrative PowerShell:
python -m realtime.run --mode live --interface "Wi-Fi"
streamlit run dashboard/app.py
```

---

## 📦 Packaged Executables & Architecture

The system can be deployed directly via Python scripts or built as standalone Windows executables (`dist/`):
- **`EncryptedTrafficMonitor.exe`**: Background network monitor, zero-payload feature pipeline, LightGBM classifier, and localhost REST API server (`127.0.0.1:8080`).
- **`EncryptedTrafficDashboard.exe`**: Streamlit SOC web analytics console (`127.0.0.1:8501`).

```text
       ┌─────────────────────────────────────────────────────────────┐
       │               Windows Host Machine (x64)                    │
       │                                                             │
       │   [Npcap / Raw Socket]  (or Simulated Replay)               │
       │             │                                               │
       │             ▼                                               │
       │   ┌─────────────────────────────────────────────────────┐   │
       │   │  EncryptedTrafficMonitor.exe / realtime.run         │   │
       │   │  - Layer 3/4 Packet Sniffer (Zero Payload)          │   │
       │   │  - Flow Tracker (5-tuple, Timeout, Directionality)  │   │
       │   │  - Feature Extractor (10 Canonical Features)        │   │
       │   │  - Model Inference Engine (LightGBM / Calibrated)   │   │
       │   │  - Abstention & Confidence Gating Policy            │   │
       │   │  - Local REST API Server (127.0.0.1:8080)           │   │
       │   └──────────────────────────┬──────────────────────────┘   │
       │                              │ JSON Events via HTTP         │
       │                              ▼ (Loopback Only)              │
       │   ┌─────────────────────────────────────────────────────┐   │
       │   │  EncryptedTrafficDashboard.exe / dashboard.app      │   │
       │   │  - Streamlit SOC Analytics Console (127.0.0.1:8501) │   │
       │   │  - Real-time KPI Tiles (TPS, P95, Abstention Rate)  │   │
       │   │  - Interactive Flow Table & PII-masked Inspector    │   │
       │   │  - Security Alert Rules & Telemetry Gauges          │   │
       │   └─────────────────────────────────────────────────────┘   │
       └─────────────────────────────────────────────────────────────┘
```

---

## 🔒 Security & Privacy Guarantees

- **Zero-Payload Enforced:** Operates exclusively on Layer-3/4 transport metadata (packet sizes, directionality, inter-arrival times, burst behavior). Raw application payload bytes are never inspected or persisted.
- **Zero Raw PII Persistence:** IP and MAC addresses are never stored in research logs or outputs. Session identifiers are cryptographically hashed using SHA-256 (`session_id_hash`).
- **Zero Credentials & Cloud Telemetry:** No API keys, passwords, or external cloud analytics endpoints exist in configuration or runtime code.
- **Strict Localhost Isolation:** Both the REST API (`127.0.0.1:8080`) and Dashboard (`127.0.0.1:8501`) bind exclusively to loopback interfaces. Non-localhost binding attempts are rejected with security exceptions.
- **Cryptographic Model Integrity:** Models are verified via SHA-256 checksums against `results/models/production_registry.json`. Corrupted or altered model files cause the pipeline to fail-closed into `PIPELINE_DEGRADED`.
- **Fail-Closed Permissions:** When unprivileged users run live sniffing without Npcap or admin rights, the pipeline gracefully reports a privilege boundary error rather than crashing.

---

## 📚 Complete Documentation Suite

- **[Installation Guide](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/docs/INSTALLATION.md):** Complete prerequisites, Npcap driver setup, and 9-point validation procedures.
- **[Deployment Guide](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/docs/DEPLOYMENT.md):** Deployment architecture, security boundaries, background scheduled tasks, and local API specifications.
- **[Troubleshooting Guide](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/docs/TROUBLESHOOTING.md):** Solutions for Npcap errors, port conflicts, admin rights, and model integrity mismatches.
- **[Scientific Final Report](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/final_research_report.md):** 15-section scientific evaluation report detailing the zero-payload methodology and experimental evidence across Phases 1–9.
