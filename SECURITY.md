# Security, Privacy & Non-Inspection Policy

**Standard:** Privacy-Preserving Zero-Payload Network Monitoring  
**Verification Protocol:** [`docs/research/REALTIME_VALIDATION.md`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/docs/research/REALTIME_VALIDATION.md)  
**Verification Evidence:** [`results/tables/realtime_research_validation.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/realtime_research_validation.csv)  

---

## 1. 🔒 The Zero-Payload Principle

This research platform is engineered strictly for **Encrypted Network Traffic Classification without payload decryption, content inspection, or plaintext persistence**. The system adheres to strict information-theoretic and privacy boundaries:

### Verified Guarantees:
1. **No Deep Packet Inspection (DPI):** The packet processing engine strictly parses Layer-3 (IP), Layer-4 (TCP/UDP), and unencrypted initial handshake headers (TLS ClientHello metadata where present).
2. **No Payload Decryption:** The system does NOT perform SSL/TLS interception, man-in-the-middle (MITM) proxying, private key extraction, or cryptographic session decryption.
3. **No Payload Persistence:** Packet buffers and application payloads are discarded immediately upon extracting packet length, arrival timestamp, and direction. The `RawPacketMetadata`, `Flow`, `FlowLifecycleEvent`, and `TrafficPredictionEvent` dataclasses contain zero payload byte arrays or content buffers.
4. **No Payload Features:** All 21 canonical features derive purely from packet timing, packet counts, byte counts, inter-arrival distributions, packet size statistics, and directionality ratios. No byte n-grams, text entropy, or signature regexes exist in the feature pipeline.
5. **No External Network Transmission:** All background processes, ML inference workers, and local REST APIs bind strictly to `127.0.0.1` (localhost). Zero outbound telemetry, diagnostic logs, or prediction streams are transmitted over external networks.
6. **Network Identifier Sanitization:** IP addresses and MAC addresses are explicitly excluded from machine learning feature vectors. Flow IDs and session identifiers are pseudonymized using deterministic cryptographic hashes (`session_id_hash`) to prevent spurious topology memorization.
7. **Dashboard Privacy:** The real-time SOC console presents anonymized Flow IDs, protocol types, port numbers, packet rates, and statistical traffic categories without exposing sensitive user endpoints.
8. **Fail-Closed Safety:** If network adapters or permissions are misconfigured, the pipeline degrades cleanly into `PIPELINE_DEGRADED` or unprivileged monitoring without crashing or leaking unhandled packet buffers.

---

## 2. Invariant Verification Ledger

As proven in [`results/tables/realtime_research_validation.csv`](file:///c:/UROP%20project/encrypted-traffic-classification-UROP/results/tables/realtime_research_validation.csv), the real-time pipeline satisfies all 10 core invariants:

| # | Security / Correctness Invariant | Enforcement Mechanism | Verified Status |
| :-: | :--- | :--- | :---: |
| **1** | **Zero Payload Persistence** | `RawPacketMetadata` dataclass contains only header metadata; no byte buffers stored. | **PASSED** |
| **2** | **Zero Payload Features** | Feature schema contains only timing, count, size, and ratio attributes. | **PASSED** |
| **3** | **No TLS Decryption** | Only unencrypted TLS ClientHello metadata (SNI, cipher count) read before session encryption. | **PASSED** |
| **4** | **No External Transmission** | All HTTP APIs bind exclusively to `127.0.0.1`; zero remote telemetry. | **PASSED** |
| **5** | **Canonical Event Schema** | All emitted events strictly conform to the 14-field production specification. | **PASSED** |
| **6** | **Deterministic State Machine** | Predictions assigned to `KNOWN`, `LOW_CONFIDENCE`, `UNKNOWN`, or `INSUFFICIENT_EVIDENCE`. | **PASSED** |
| **7** | **Model Provenance** | Every event stamps registered `model_id` matching cryptographic weights hash. | **PASSED** |
| **8** | **Feature Profile Alignment** | Every event stamps active `feature_profile` (`lightweight_10` / `canonical_21`). | **PASSED** |
| **9** | **Bounded Confidence** | Probabilities bounded in $[0.0, 1.0]$ with multiclass probability normalization. | **PASSED** |
| **10**| **Valid Latency Accounting** | End-to-end latency (`latency_us`, `elapsed_seconds`) strictly positive and tracked. | **PASSED** |

---

## 3. Operating Mode Segregation Policy

The repository operates in three strictly segregated modes:
- **`LIVE_MODE`:** Direct packet ingestion from physical network adapters (`Wi-Fi`, `Ethernet`) or loopback sockets. Events are tagged `operating_mode: "LIVE_MODE"`.
- **`DEMO_MODE`:** Synthetic or recorded replay for UI/dashboard demonstrations without elevated privileges. Events are permanently tagged `operating_mode: "DEMO_MODE"`.
- **`RESEARCH_MODE`:** Batch evaluation on frozen, session-isolated real datasets (`dataset_v2`).

> [!CAUTION]
> **Data Segregation Rule:** Under no circumstances may `DEMO_MODE` events or metrics be published, cited, or logged as research paper findings or real-traffic validation claims.
