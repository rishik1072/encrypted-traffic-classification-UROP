# Dataset V3 Privacy and Anonymization Specification

**Project**: Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift  
**Document**: Authoritative Data Privacy and Regulatory Standard  
**Date**: November 2026  
**Status**: Authoritative Technical Standard (Phase 2A)

---

## 1. Executive Privacy Mandate

Dataset V3 is engineered from first principles under a strict **Privacy-by-Design** architecture (GDPR Article 25). 

To eliminate any risk of eavesdropping, credential interception, or identity tracing, the collection infrastructure enforces four non-negotiable architectural guarantees:
1. **Zero-Payload Persistence**: Raw packet payload bytes are sliced off in memory and immediately discarded. No application data, TLS payload ciphertext, HTTP content, or DNS query text is ever written to disk.
2. **Zero-PCAP Persistence**: No PCAP, PCAPNG, or raw Ethernet frames are written to disk or temporary buffers.
3. **Zero Network Identifier Storage**: Raw IPv4/IPv6 addresses, MAC addresses, TCP/UDP port numbers, and domain names (SNI) are strictly barred from on-disk schemas.
4. **Non-Correlatable Flow Identifiers**: Flow identifiers are session-scoped random UUIDs (`flow_[a-f0-9]{32}`) that do not encode or hash network endpoints.

---

## 2. In-Memory Ephemeral Data Handling

To associate bidirectional packets into coherent flows without persisting network identifiers, the infrastructure employs a strict **Volatile-Only Memory Boundary**:

```
[ Physical Wire Ingress ]
       │ Full Ethernet frame (MACs, IPs, Ports, Payload)
       ▼
[ OS Npcap Kernel Driver (Volatile Kernel Memory) ]
       │ Ring buffer in unpaged kernel memory.
       │ Snaplen truncation (if snaplen configured, e.g. 128 bytes):
       │ Payload bytes discarded BEFORE crossing kernel-to-user-space boundary!
       ▼
[ Scapy AsyncSniffer (Volatile User-Space RAM) ]
       │ Receives truncated or raw Ethernet frame into ephemeral memory.
       │ Read wirelen from pcap header and total length from IP header.
       ▼
[ Packet Parser: TransientPacketData (Volatile User-Space RAM) ]
       │ Extracts primitive scalar integers: wire_length, captured_length, timestamps, flags.
       │ Extracts transient 5-tuple: (src_ip, src_port, dst_ip, dst_port, protocol).
       │ Discards the Scapy packet object and raw payload buffer immediately.
       ▼
[ Flow Manager (Volatile In-Memory RAM Table) ]
       │ Canonicalizes 5-tuple key: (min(A, B), max(A, B), protocol).
       │ Matches key to active flow state.
       │ Emits zero-PII PacketMetadataRecord (lengths, relative us, IAT us, direction).
       ▼
[ Flow Termination & Memory Wipe ]
       │ When flow times out, FIN/RST observed, or session ends:
       │ 1. Emits FlowIndexRecord (summary counts & duration).
       │ 2. DELETES 5-tuple key from in-memory dictionary.
       │ 3. Python garbage collector reclaims volatile IP/port memory.
       ▼
[ Atomic Disk Storage (.staging/ -> data/research_v3/) ]
       │ Writes ONLY zero-PII records:
       │ ZERO IPs, ZERO MACs, ZERO Ports, ZERO Payloads, ZERO URLs, ZERO SNI.
```

---

## 3. Pseudonymization and Device Anonymization

| Identifier Type | Standard Literature Practice | Dataset V3 Implementation | Privacy Justification |
| :--- | :--- | :--- | :--- |
| **Flow Identifier** | Encoded 5-tuple hash (e.g. `SHA256(src_ip || dst_ip)`) | Cryptographically random UUID4 (`flow_f8a2...`) | Hashes of small IP/port spaces are vulnerable to rainbow table pre-image recovery. Random UUIDs are mathematically non-invertible. |
| **Device Identifier** | Client MAC address or Hostname | Random session token (`dev_pseudonym_a8f9c2`) | Eliminates device hardware fingerprinting across collection sessions. |
| **Network Location** | Public IP address / ASN | Environmental tag (`env_phys_wifi_01`) | Prevents geographical tracing of collection operators or network locations. |
| **Session Provenance**| Network SSID / BSSID | Ephemeral session token (`sess_v3_...`) | Prevents wireless network geolocation mapping via Wi-Fi wardriving databases (e.g., WiGLE). |

---

## 4. Regulatory Assessment (GDPR Compliance)

Under Regulation (EU) 2016/679 (General Data Protection Regulation):

### Article 4(1) — Definition of Personal Data
- *Analysis*: In volatile memory, IP addresses constitute personal data if linked to an identified individual. However, because IP addresses are processed ephemerally in RAM solely for bidirectional flow assembly and are discarded within seconds without persistent logging, persistent dataset artifacts contain **zero direct or indirect personal identifiers**.
- *Verdict*: Dataset V3 artifacts on disk constitute fully anonymized statistical technical telemetry outside the scope of GDPR personal data restrictions.

### Article 6(1)(f) — Lawful Basis for Processing
- *Analysis*: Transient in-memory processing of packet headers is justified under the **Legitimate Interests** of scientific research in cybersecurity and network performance engineering, with negligible impact on data subject rights due to instantaneous payload destruction.

### Article 32 — Security of Processing
- *Analysis*: Accidental data exposure, disk theft, or repository leaks cannot compromise user credentials, browsing history, or personal identity, because no user application data or routable identifiers exist in the persisted files.

---

## 5. Automated Privacy Verification Suite

The `DatasetV3Validator` enforces two automated security gates:
- **Check 16 (Forbidden Identifier Audit)**: Scans every serialized CSV and JSONL record against regular expressions matching IPv4 addresses, IPv6 addresses, MAC addresses, and URL patterns. Any match immediately fails the validation report.
- **Check 17 (Payload Persistence Audit)**: Confirms that no raw byte buffers, binary objects, or byte-dump keys exist on packet metadata structures.
