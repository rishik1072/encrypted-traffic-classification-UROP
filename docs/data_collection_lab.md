# Controlled Data Collection Lab Documentation

## 1. Laboratory Environment Overview

The traffic collection laboratory is a controlled physical/virtual host dedicated to capturing real encrypted network sessions under isolated operator supervision.

### Laboratory Specifications:
- **Collection Host:** Windows 11 / Linux workstation
- **Network Interface:** Promiscuous / standard Ethernet or Wi-Fi interface (resolved automatically via `capture/interface_resolver.py` from friendly names like `Wi-Fi`)
- **Operator Isolation:** Strictly single active activity per capture window to guarantee unambiguous ground-truth labels.
- **Fail-Closed Privacy & Integrity:** The real collection pipeline fails closed. If live packet capture fails or encounters adapter errors, no synthetic data is generated and no session is registered as real.
- **Payload Privacy:** Ephemeral capture with immediate zero-payload metadata extraction.

---

## 2. Privacy Safeguards & Whitelist Policy

The framework enforces a **Strict Whitelist** at metadata extraction:
- **Captured & Retained:**
  - Packet arrival timestamps ($t$)
  - Packet wire lengths ($L$)
  - IP Protocol (TCP, UDP)
  - Direction (Forward / Backward relative to initiator)
  - Transport Ports (Source Port, Destination Port)
  - Unencrypted TLS/QUIC handshake record lengths
- **Strictly Stripped & Discarded:**
  - Application payload byte buffers
  - HTTP headers, URIs, cookies, and POST bodies
  - User messages, keystrokes, and audio buffers
  - Decryption keys and session secrets

---

## 3. Ground-Truth Labeling Protocol

The session ground-truth class is assigned directly by the operator's controlled activity prior to capture initiation. Because only the designated application is active during the session window, labeling ambiguity is prevented.
