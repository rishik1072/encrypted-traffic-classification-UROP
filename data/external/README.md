# External Dataset Integration & Compatibility Guide

This directory documents the formal protocol for integrating external, publicly available encrypted-traffic datasets into the experimental evaluation pipeline.

---

## 📌 Standard Ingestion Protocol

1. **Do NOT download datasets automatically**: Due to bandwidth, license constraints, and storage variations, external datasets must be placed manually into `data/external/<dataset_name>/`.
2. **Zero-Payload Mandate**: Regardless of dataset origin, the pipeline will strictly parse Layer-3/4 headers and statistical temporal dynamics without inspecting payload contents.
3. **Explicit Class Mapping**: External application labels MUST be explicitly mapped to the project's 6 canonical classes using `training/class_mapping.py` and `config.yaml`.

---

## 📚 Supported Public Benchmarks & Label Mappings

### 1. ISCX VPN-nonVPN (UNB)
- **Source**: University of New Brunswick (ISCX)
- **License**: Research / Non-commercial
- **Traffic Classes**: Voice, Video, Chat, File Transfer, Mail, Streaming, P2P
- **Project Mapping**:
  - `Voice` $\rightarrow$ `VoIP`
  - `Video`, `Streaming` $\rightarrow$ `Video`
  - `Chat` $\rightarrow$ `Messaging`
  - `File Transfer`, `P2P` $\rightarrow$ `File Transfer`
  - `Mail`, `Browsing` $\rightarrow$ `Web`
  - `Other` $\rightarrow$ `Other`

### 2. USTC-TFC2016
- **Source**: University of Science and Technology of China
- **License**: Academic Use
- **Traffic Classes**: 10 Benign applications (BitTorrent, Facetime, FTP, Gmail, MySQL, Outlook, Skype, SMB, Weibo, WorldOfWarcraft) + 10 Malware families
- **Project Mapping**:
  - `Gmail`, `Weibo`, `MySQL` $\rightarrow$ `Web`
  - `Skype`, `Facetime` $\rightarrow$ `VoIP`
  - `BitTorrent`, `FTP`, `SMB` $\rightarrow$ `File Transfer`
  - `WorldOfWarcraft`, `Other` $\rightarrow$ `Other`

### 3. CIC-IoT-2023 / DoH / QUIC Datasets
- **Source**: Canadian Institute for Cybersecurity
- **Conversion Procedure**: Place raw PCAP files in `data/external/<name>/`, create an auxiliary manifest mapping `file_id` and labels, and run `python -m training.class_mapping --external <manifest>`.
