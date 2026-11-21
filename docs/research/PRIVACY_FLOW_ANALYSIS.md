# Privacy Flow Analysis and Data Lifecycle Audit

**Repository**: `encrypted-traffic-classification-UROP`  
**Audit Date**: November 2026  
**Auditor**: Independent ML & Systems Research Audit  
**Status**: Authoritative Forensic Evidence Document

---

## 1. Executive Summary

Previous project documentation frequently asserted that:
> *"IP addresses and MAC addresses are stripped immediately at ingress."*

Forensic inspection of the actual network capture and packet handling code (`capture/packet_capture.py`, `realtime/flow_tracker.py`, and `realtime/sqlite_store.py`) clarifies this statement:
- **MAC Addresses**: Verified. MAC addresses are stripped at Scapy parsing and never stored or forwarded.
- **IP Addresses**: **Clarified**. IP addresses are **NOT** stripped immediately at physical ingress. They are held in memory as plaintext strings in `RawPacketMetadata` and utilized by `RealTimeFlowTracker` to compute the canonical bidirectional 5-tuple flow key `(ip_a, port_a, ip_b, port_b, protocol)`.
- **Zero-PII Storage**: Verified. Raw IP addresses, ports, and payload bytes are **never written to disk** (the SQLite event database stores only truncated 16-character SHA-256 session digests), **never included in model feature vectors**, and **never present in training datasets**.

This document outlines the exact 6-tier lifecycle of network data from the physical wire to long-term persistence.

---

## 2. Six-Tier Data Lifecycle Architecture

```
[ Tier 1: Wire / Npcap Driver ]
  │ Full Ethernet Frame (MAC, IP, TCP/UDP Headers, Encrypted Payload)
  ▼
[ Tier 2: Ingress Parsing (capture/packet_capture.py) ]
  │ Scapy decodes frame; drops MAC addresses & payload bytes.
  │ Extracts: RawPacketMetadata(src_ip, dst_ip, src_port, dst_port, protocol, length, timestamp)
  ▼
[ Tier 3: Flow Aggregation (realtime/flow_tracker.py) ]
  │ In-memory lookup: FlowKey(ip_a, port_a, ip_b, port_b, proto)
  │ Appends to flow.packet_records: (timestamp, length, direction)
  ▼
[ Tier 4: Statistical Feature Extraction (preprocessing/feature_extractor.py) ]
  │ Transforms packet records into 21 numerical statistical features.
  │ IP addresses and port numbers are strictly omitted.
  ▼
[ Tier 5: Event Serialization (realtime/events.py) ]
  │ Combines prediction output with pseudonymized identifiers.
  │ Computes SHA-256 hash digest of session/flow identifiers.
  ▼
[ Tier 6: Persistent Storage (realtime/sqlite_store.py) ]
  │ Inserts into SQLite: flow_id, timestamp, predicted_class, confidence, session_id_hash.
  │ ZERO IP addresses, ZERO MAC addresses, ZERO payloads on disk.
```

---

## 3. Forensic Code Inspection by Tier

### Tier 1 & 2: Ingress Parsing (`capture/packet_capture.py`, Lines 44–58)
```python
@dataclass
class RawPacketMetadata:
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: int
    timestamp: float
    length: int
```
- **Evidence**: MAC addresses from the Ethernet header are discarded upon parsing.
- **Evidence**: The raw payload bytes are discarded immediately (`len(packet[IP].payload)` or header length slicing is recorded; the payload bytes themselves are never copied).
- **Nuance**: Plaintext IP addresses (`src_ip`, `dst_ip`) are instantiated in memory. Claiming that IP addresses are stripped at ingress is factually inaccurate.

### Tier 3: In-Memory Flow Aggregation (`realtime/flow_tracker.py`, Lines 22–38)
```python
@dataclass(frozen=True)
class FlowKey:
    ip_a: str
    port_a: int
    ip_b: str
    port_b: int
    protocol: int

    @classmethod
    def create(cls, src_ip: str, src_port: int, dst_ip: str, dst_port: int, protocol: int) -> "FlowKey":
        if (src_ip, src_port) <= (dst_ip, dst_port):
            return cls(src_ip, src_port, dst_ip, dst_port, protocol)
        return cls(dst_ip, dst_port, src_ip, src_port, protocol)
```
- **Evidence**: Bidirectional flow matching requires comparing IP addresses and ports to assign incoming packets to the correct conversation flow bucket.
- **Evidence**: `flow.packet_records` stores only tuples of `(timestamp, length, direction)`. Once assigned to a flow, individual packet IP headers are discarded from the flow record.

### Tier 4: Feature Extraction (`preprocessing/feature_extractor.py`, Lines 62–126)
- **Evidence**: The 21 canonical features extracted for machine learning inference consist exclusively of aggregate statistical metrics:
  - Duration, packet counts, byte counts, length statistics (min, max, mean, variance).
  - Timing statistics (mean IAT, median IAT, std IAT, min/max IAT).
  - Burst dynamics (count, average bytes, average packets) and forward/backward ratios.
- **Zero-Payload & Zero-Header Guarantee**: No IP addresses, subnet prefixes, MAC addresses, or application layer payload signatures are included in the feature vector.

### Tier 5 & 6: Event Persistence (`realtime/sqlite_store.py`, Lines 35–65)
The SQLite schema for event persistence is defined as follows:
```sql
CREATE TABLE IF NOT EXISTS prediction_events (
    flow_id TEXT PRIMARY KEY,
    timestamp REAL,
    predicted_class TEXT,
    confidence REAL,
    prediction_state TEXT,
    total_packet_count INTEGER,
    flow_duration REAL,
    session_id_hash TEXT
);
```
- **Evidence**: The database schema contains **no columns** for IP addresses, MAC addresses, or packet payloads.
- **Session Pseudonymization**: The session identifier is hashed prior to disk storage:
  `session_id_hash = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]`

---

## 4. Privacy & Regulatory Assessment (GDPR Compliance)

| Evaluation Standard | Implementation Reality | Regulatory Verdict |
| :--- | :--- | :--- |
| **Payload Privacy** | Payloads are sliced off at packet arrival; zero payload bytes buffered or inspected. | **Compliant**: Prevents accidental eavesdropping on TLS/HTTP application payload. |
| **In-Memory IP Processing** | Ephemeral buffering of IP 5-tuples for flow session assembly. | **Legitimate Interest**: Necessary for network telemetry aggregation (GDPR Art. 6(1)(f)). |
| **On-Disk Anonymization** | SHA-256 16-hex truncated session hashes; zero IP addresses or MACs stored in database. | **Privacy-by-Design**: Prevents forensic identity tracing from compromised database artifacts. |
| **Model Invariance** | 21 statistical flow features; model cannot memorize or overfit to client IP subnets. | **Robust**: Zero IP-based shortcut learning or geographical leakage. |

---

## 5. Required Terminology Corrections for Academic Publication

In any academic paper or conference submission derived from this repository, the following terminology adjustments must be made:
1. **Replace**: *"IP addresses are stripped at network ingress."*  
   **With**: *"IP addresses are parsed ephemerally in volatile memory solely to index bidirectional 5-tuple flow records; they are strictly excluded from feature extraction and persistent storage."*
2. **Replace**: *"Zero-payload inspection ensures absolute privacy."*  
   **With**: *"Zero-payload metadata processing extracts only timing and packet volume statistics, ensuring application data confidentiality and compliance with privacy-by-design standards."*
