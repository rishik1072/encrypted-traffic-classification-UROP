# Dataset Storage and Directory Structure

This directory houses raw and processed network traffic data for the **Encrypted Traffic Classification** research project.

## Directory Layout

```
data/
├── dataset_manifest.csv       # Authoritative mapping between PCAP files and ground-truth traffic classes
├── README.md                  # Storage guidelines, policies, and conventions
│
├── raw/
│   ├── pcap/                  # Raw encrypted PCAP / PCAPNG capture files (DO NOT commit large files to git)
│   └── metadata/              # Capture session logs, environment notes, and network topologies
│
├── processed/
│   ├── flows/                 # Extracted bidirectional flow records (CSV/JSON/Parquet)
│   ├── features/              # Tabular zero-payload statistical feature datasets (features.csv)
│   └── splits/                # Leakage-free train.csv, validation.csv, and test.csv partitions
│
└── external/                  # Public benchmark dataset references (e.g. ISCX-VPN, USTC-TFC)
```

---

## 🔒 Privacy & Zero-Payload Principle

1. **No Payload Decryption**: This project operates strictly on network transport metadata (packet sizes, inter-arrival times, burst distributions, directionality, and protocol headers). Packet payload contents are never decrypted or inspected.
2. **Zero Sensitive Payload Storage**: Processed feature matrices retain only statistical characteristics and non-identifying attributes. Raw application data, decrypted streams, and identifying IP addresses are omitted from downstream training datasets to prevent model shortcut learning and protect privacy.

---

## 📋 Naming Conventions

- **PCAP Files**: `<traffic_class>_<source>_<YYYYMMDD>_<seq_id>.pcap`
  - *Example*: `video_youtube_20260823_001.pcap`
  - *Example*: `voip_zoom_20260823_002.pcap`
- **Manifest**: Every raw PCAP file must be cataloged in `data/dataset_manifest.csv` with a unique `file_id` and verified `traffic_class`.
