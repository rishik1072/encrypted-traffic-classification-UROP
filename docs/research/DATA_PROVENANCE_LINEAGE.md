# Dataset Provenance, Lineage, and Partition Integrity Audit

**Repository**: `encrypted-traffic-classification-UROP`  
**Audit Date**: November 2026  
**Auditor**: Independent ML & Systems Research Audit  
**Status**: Authoritative Forensic Evidence Document

---

## 1. Executive Summary

This document establishes the exact genealogical lineage, physical provenance, transformation steps, and partition integrity for all datasets present in the repository:
1. `dataset_v1` (Synthetic loopback prototype)
2. `dataset_real_v1` (Physical desktop/laptop captures)
3. `dataset_v2` (Hybrid expansion benchmark)

Forensic inspection of the dataset generation code (`capture/expand_dataset_v2.py`) and split manifests reveals a **critical structural vulnerability**: `dataset_v2` was constructed by cloning physical flow prototypes from `dataset_real_v1` (`rec = dict(proto)`) and perturbing a subset of 11 features while overwriting `session_id`. Because **no parent flow or session lineage was recorded**, standard session-disjoint partitioning successfully prevents session ID overlap but **fails to prevent parent prototype leakage** between training, validation, and test splits.

---

## 2. Dataset Genealogy and Physical Inventory

| Property | `dataset_v1` | `dataset_real_v1` (`features_real_clean.csv`) | `dataset_v2` (`features_real_v2.csv`) |
| :--- | :--- | :--- | :--- |
| **Origin Category** | Synthetic Loopback (Scapy) | Genuine Physical Capture | Hybrid (Physical + Perturbation) |
| **Primary Data File** | `data/processed/features/features.csv` | `data/processed/features/features_real_clean.csv` | `data/processed/features/features_real_v2.csv` |
| **Total Flows** | 12 | 121 (189 raw in `features_real.csv`) | 301 |
| **Unique Sessions** | 1 (`loopback_test`) | 60 physical capture sessions | 150 session identifiers |
| **Traffic Classes** | 6 classes (2 per class) | 6 classes (Web, Video, Messaging, VoIP, File Transfer, Other) | 6 classes (50 per class; Other: 51) |
| **Hardware Adapters** | Localhost software interface | Intel Wi-Fi 6 AX201, Realtek PCIe GbE | Synthetic tags (`env_win11_wifi`, `env_win11_eth`, `env_win11_cellular`) |
| **Physical Environments** | 1 local host machine | 1 Windows 11 host (Wi-Fi + Ethernet) | Derived from 1 host |
| **Collection Dates** | August 2026 | 2026-08-20 to 2026-08-21 | 2026-08-20 to 2026-08-23 (Synthesized timestamps) |
| **Missing Values** | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| **Parent Lineage Stored** | N/A | None | **None** (`parent_flow_id` missing) |

---

## 3. The `dataset_v2` Expansion Mechanism

The script `capture/expand_dataset_v2.py` was authored to expand the 121 clean physical flows of `dataset_real_v1` into a 301-flow benchmark dataset (`dataset_v2`) representing multi-day, multi-condition network scenarios.

### 3.1 Code Inspection: `capture/expand_dataset_v2.py` (Lines 132–162)

```python
for cls in CLASSES:
    prototypes = orig_by_class.get(cls, orig_records[:2])
    variants = ACTIVITY_VARIANTS[cls]

    for s_idx, target in enumerate(additional_targets):
        session_counter += 1
        day, date_str, batch, env, iface, dev, cond, tunnel = target
        sess_id = f"sess_{date_str.replace('-', '')}_{cls.lower().replace(' ', '_')}_{session_counter:03d}"
        v_name = variants[s_idx % len(variants)]
        proto = prototypes[s_idx % len(prototypes)]

        # Generate 2 realistic flows per expanded session
        n_flows = 2
        for f_idx in range(n_flows):
            flow_id = f"{sess_id}_flow_{f_idx:05d}"
            rec = dict(proto)  # <-- CLONING PHYSICAL PROTOTYPE
            rec["flow_id"] = flow_id
            rec["file_id"] = f"real_{sess_id}"
            rec["session_id"] = sess_id  # <-- NEW SYNTHETIC SESSION ID
            rec["traffic_class"] = cls
            rec["environment_id"] = env
            rec["network_condition_id"] = cond
            rec["capture_day"] = day
            rec["capture_date"] = date_str
            rec["collection_batch"] = batch
            rec["device_id"] = dev
            rec["interface_type"] = iface
            rec["tunnel_state"] = tunnel
            rec["activity_variant"] = v_name
            rec["dataset_version"] = "v2"
```

### 3.2 Selective Perturbation vs. Verbatim Copying (Lines 163–201)

The expansion script applies multiplicative noise to **only 11 specific features**:
- `flow_duration`: scaled by `random.uniform(0.85, 1.15)`
- `forward_packet_count`, `backward_packet_count`, `total_packet_count`
- `forward_bytes`, `backward_bytes`, `total_bytes`
- `avg_packet_size`: recomputed as `total_bytes / total_packet_count`
- `mean_iat`: scaled by condition multipliers (e.g., $1.5\times - 2.5\times$ for `LOW_BANDWIDTH`, $2.0\times - 4.0\times$ for `HIGH_LATENCY`)
- `max_iat`: scaled by condition multipliers
- `burst_count`: scaled by condition multipliers

**Crucially, all remaining 10+ canonical features are copied verbatim from the prototype**:
- `min_packet_size`
- `max_packet_size`
- `packet_size_variance` (and `std_packet_size`)
- `min_iat`
- `median_iat`
- `iat_std`
- `fwd_bwd_packet_ratio`
- `fwd_bwd_byte_ratio`
- `avg_burst_bytes`
- `avg_burst_packets`

---

## 4. Parent-Flow Independence Failure (Data Leakage)

### 4.1 The Mechanism of Leakage
In `experiments/selective_prediction/run.py` (lines 236–268) and `scripts/split_dataset.py`, data partitioning is performed using group-aware stratified session isolation:
```python
assert len(train_sessions & val_sessions) == 0
assert len(train_sessions & test_sessions) == 0
assert len(val_sessions & test_sessions) == 0
```

While this assertion mathematically guarantees that no string matching `session_id` appears in both training and test sets, **it fails to prevent prototype feature leakage**:
1. Prototype flow $P_1$ from session `sess_20260820_web_001` is assigned to `train.csv`.
2. Cloned variant $C_1$ with synthetic session `sess_20260822_web_045` is assigned to `test.csv`.
3. In both $P_1$ (in `train`) and $C_1$ (in `test`), `packet_size_variance`, `min_packet_size`, `max_packet_size`, `median_iat`, and `iat_std` are **bit-for-bit identical**.
4. The classifier can identify the test flow not by learning generalizable traffic patterns, but by recognizing the unique exact fingerprint of the prototype flow's packet length distribution.

### 4.2 Impact on Research Claims
- The model performance measured on `dataset_v2` ($F_1 \approx 0.5854$ uncalibrated / $0.6515$ selective at $\tau=0.70$) is partially stabilized by these cloned feature fingerprints.
- If true parent-isolated splitting had been enforced (holding all progeny of prototype $P_1$ within a single partition), test performance would likely experience further degradation.

---

## 5. Dataset Quality and Missing Value Audit

Direct inspection of `features_real_v2.csv` across all 301 records yields:
- **Missing / NaN / Null values**: 0 (100% complete across all 21 canonical features).
- **Infinite values**: 0.
- **Negative values**: 0 (all IATs clamped via `max(0.0, ...)`, counts $\ge 0$).
- **Zero-duration flows**: Handled safely with fallback clamping in `feature_extractor.py`.
- **Label Consistency**: Verified. Classes strictly conform to the 6 canonical names (`Web`, `Video`, `Messaging`, `VoIP`, `File Transfer`, `Other`).

---

## 6. Recommendations for Phase 1 Research Data Governance

1. **Mandate Provenance Metadata**:
   Any synthetic or perturbed records must include explicit metadata fields:
   - `is_synthetic: bool`
   - `parent_flow_id: Optional[str]`
   - `parent_session_id: Optional[str]`
   - `perturbation_profile: Optional[str]`
2. **Implement Parent-Grouped Cross-Validation**:
   Cross-validation grouping must group by `parent_session_id` rather than ephemeral `session_id`.
3. **Execute Physical Multi-Device Captures**:
   Phase 1 must deprecate perturbation expansion and collect genuine network captures across at least 3 distinct physical operating environments (different LANs, different Wi-Fi routers, cellular tethering) on distinct hardware hosts.
