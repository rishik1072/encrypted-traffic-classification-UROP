# Dataset V3 Ground-Truth Annotation and Labeling Guide

**Project**: Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift  
**Document**: Authoritative Annotation Standard Operating Procedure  
**Date**: November 2026  
**Status**: Authoritative Technical Standard (Phase 2A)

---

## 1. Ground-Truth Philosophy and Golden Rule

The integrity of a supervised machine learning benchmark depends entirely on the empirical validity of its ground-truth labels. 

> [!CAUTION]
> **The Golden Rule of Ground-Truth Annotation**:
> Under NO circumstances may a flow's ground-truth label be determined by:
> 1. The output or prediction of an ML model.
> 2. Model confidence scores or posterior probabilities.
> 3. Heuristic inspection of packet sizes or traffic appearance.
> 4. Unverified assumptions that all traffic during a capture belongs to the target application.

Ground truth in Dataset V3 must be established **exclusively by deterministic, operator-controlled execution** of the generating application software.

---

## 2. The Background Traffic Problem

In real-world operating systems, launching an application never generates purely isolated traffic. Concurrent background network activity routinely occurs:
- Operating system telemetry (Windows Update, SmartScreen, telemetry pings).
- Network protocol infrastructure (DNS lookups, mDNS, NetBIOS, NTP time synchronization).
- Background application checks (Slack/Teams background web-sockets, cloud drive sync).

Falsely assigning these concurrent background flows to the target class (e.g., labeling an NTP ping as "Video" simply because YouTube was playing) introduces **severe label noise and shortcut leakage**.

---

## 3. Decoupling Label Quality from Packet Prefix Horizon

In earlier heuristic schemes, flows with $< 3$ packets were automatically marked `AMBIGUOUS`. In Phase 2A.1, this conflation has been eliminated:

> [!IMPORTANT]
> **Decoupling Principle**:
> 1. **Label Quality (`label_quality`)**: Represents the certainty of application origin (attribution fidelity). A 2-packet TCP flow that is deterministically initiated and terminated by the target application (e.g., a verified Chrome connection attempt) has `label_quality = "VERIFIED"`.
> 2. **Prefix Availability Flags (`prefix_K_available`)**: Orthogonally record whether the flow has reached sufficient packet depth for prefix horizon $K \in \{3, 5, 10, 20\}$.
> 3. **Attribution Ambiguity**: `AMBIGUOUS` is reserved for flows whose application origin is genuinely uncertain due to multi-process socket contention or overlapping background activity, NOT simply because the flow was short.

| Label Quality | Permitted Supervised Use | Description & Criteria |
| :--- | :--- :--- |
| **`VERIFIED`** | **Primary Training & Testing** | High-certainty target application flow. Generated deterministically by the target application during active operator control, regardless of whether it has 1 packet or 10,000 packets. |
| **`AMBIGUOUS`** | **Excluded from Supervised Splits** | Flows where the true generating process cannot be definitively distinguished from concurrent processes (uncertain attribution). |
| **`UNLABELLED`** | **Unsupervised / Open-Set Eval** | Background flows observed concurrently during the session whose exact application origin cannot be independently verified. Classified as `traffic_class="Other"`. |
| **`EXCLUDED`** | **Quarantined / Barred** | Corrupted flows, malformed frames, or confirmed cross-talk from unintended background programs. |

---

## 4. Operational Annotation Procedure

### Step 1: Pre-Execution Activity Scoping
Before starting capture, the operator defines:
- `intended_traffic_class`: The canonical class (e.g., `Messaging`).
- `application_alias`: The specific client program (e.g., `signal_desktop`).
- `collection_activity`: Description of user actions (e.g., `Sending 10 text messages and 2 photos`).

### Step 2: Automated Ground-Truth Generation
Upon capture completion, `GroundTruthAnnotator` applies deterministic attribution rules:
1. Target flows generated during the controlled session receive `intended_traffic_class` with `label_quality = "VERIFIED"` and `label_source = "OPERATOR_CONTROLLED"`.
2. Prefix availability flags (`prefix_3_available`, `prefix_5_available`, etc.) are independently assigned based on `packet_count >= K`.
3. If the operator supplies `primary_flow_ids` (known target flow UUIDs identified during the capture), non-matching flows default to `traffic_class = "Other"` with `label_quality = "UNLABELLED"` and `label_source = "BACKGROUND_UNLABELLED"`.

### Step 3: Manual Audit and Verification
The operator inspects `labels.csv` alongside `flow_index.csv`:
```bash
python scripts/research/dataset_v3/inspect_session.py --session data/research_v3/<session_id>
```
If a background flow was erroneously labeled as target traffic, the operator applies an explicit override:
```python
annotator.apply_manual_override(
    current_labels,
    flow_id="flow_1234...",
    traffic_class="Other",
    label_quality="UNLABELLED",
    notes="Confirmed Windows Update background download."
)
```

---

## 5. Supervised Dataset Partitioning Rules

When constructing train, validation, and test partitions:
1. **Strict Inclusion Gate**: Only flows with `label_quality == "VERIFIED"` may enter the primary supervised classification datasets.
2. **Ambiguous Flow Handling**: `AMBIGUOUS` flows ($< 3$ packets) must be evaluated separately in the `INSUFFICIENT_EVIDENCE` evaluation tier.
3. **Open-Set Testing**: `UNLABELLED` background flows may be utilized in open-world evaluation benchmarks to test unknown flow rejection rates.
