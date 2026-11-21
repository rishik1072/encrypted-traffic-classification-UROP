# External Public Encrypted Traffic Dataset Registry

**Project**: Early and Selective Zero-Payload Encrypted Traffic Classification Under Network Environment Shift  
**Repository**: `c:\UROP project\encrypted-traffic-classification-UROP`  
**Date**: November 2026  
**Status**: APPROVED & ACTIVE CATALOG  

---

## 1. Overview and Scientific Purpose

To evaluate the generalization, early-prefix degradation, and selective abstention capabilities of zero-payload encrypted traffic classifiers under real-world network shifts, the research platform supports the ingestion and benchmarking of external public datasets.

This registry provides the authoritative record of all supported external datasets:
- **CESNET DataZoo**: Backbone TLS and modern QUIC datasets (`CESNET-TLS22`, `CESNET-QUIC22`, `CESNET-TLS-Year22`, `CESNET-QUICEXT-25`).
- **CipherSpectrum**: TLS 1.3 PCAPs evaluated across 40 web domains and 3 primary cipher suites.
- **ISCXVPN2016**: PCAPs containing encapsulated VPN and non-VPN traffic across 6 service categories.

All downloads and raw archives are strictly preserved in their original form under `data/external_raw/<dataset_id>/`. Processed artifacts are stored in `data/external_processed/<dataset_id>/`, with validation manifests in `data/external_manifests/`.

---

## 2. Dataset Registry Catalog

| Dataset ID | Official Name | Publisher & Reference | License | Size / Samples | Format & Labels |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`cesnet-tls22`** | CESNET-TLS22: Encrypted Traffic Dataset | CESNET (Lux et al., CoNEXT 2023) | CC-BY-NC-SA 4.0 | ~10 GB (S size)<br>25M flows | Parquet / DataZoo<br>~100 Web Services |
| **`cesnet-quic22`** | CESNET-QUIC22: Modern QUIC Encrypted Traffic | CESNET (Lux et al., PAM 2023) | CC-BY-NC-SA 4.0 | ~12 GB (S size)<br>25M flows | Parquet / DataZoo<br>~100 QUIC Services |
| **`cesnet-tls-year22`** | CESNET-TLS-Year22: Long-Term TLS Dataset | CESNET Research (2023) | CC-BY-NC-SA 4.0 | ~50 GB<br>100M flows (52 weeks) | Parquet / DataZoo<br>Longitudinal Web Services |
| **`cesnet-quicext-25`** | CESNET-QUICEXT-25: Extended QUIC Evolution | CESNET Technical Report (2025) | CC-BY-NC-SA 4.0 | ~20 GB<br>30M flows | Parquet / DataZoo<br>HTTP/3 & Multipath QUIC |
| **`cipherspectrum`** | CipherSpectrum: TLS 1.3 Cipher Suite Diversity | UNSW Sydney (IEEE S&P 2024) | CC-BY 4.0 | ~15 GB<br>120K sessions | PCAP (raw headers)<br>40 Domains + 3 Ciphers |
| **`iscxvpn2016`** | ISCX VPN-nonVPN Traffic Dataset | UNB CIC (Draper-Gil et al., 2016) | UNB Academic | ~28 GB<br>500K flows | PCAP (raw headers)<br>VPN vs Non-VPN (6 categories) |

---

## 3. Dataset Profiles & Provenance Details

### 3.1 CESNET-TLS22
- **Source**: `https://datazoo.cesnet.cz/datasets/cesnet-tls22`
- **Download**: `https://zenodo.org/records/10008587`
- **DOI**: `10.5281/zenodo.10008587`
- **Collection**: Two-week collection in October 2021 from the CESNET2 national research backbone network (100 Gbps Czech national network).
- **Features**: Flow summary statistics + Packet Information Sequences (PPI: 30-packet sequences of `IPT`, `DIR`, `SIZE`).
- **Feature Semantics**: `SIZE` represents transport-layer payload size in bytes. It strictly excludes TCP/IP headers and zero-payload TCP ACKs.
- **Forbidden Fields**: Target-identifying shortcuts (`TLS_SNI`, `DST_IP`, `SRC_IP`, `USER_AGENT`) are strictly purged prior to modeling.

### 3.2 CESNET-QUIC22
- **Source**: `https://datazoo.cesnet.cz/datasets/cesnet-quic22`
- **Download**: `https://zenodo.org/records/7808298`
- **DOI**: `10.5281/zenodo.7808298`
- **Collection**: October–November 2022 from CESNET2 backbone.
- **Protocol**: QUIC over UDP (HTTP/3).
- **Features**: QUIC connection metadata + PPI sequences (`IPT`, `DIR`, `SIZE`).

### 3.3 CESNET-TLS-Year22
- **Source**: `https://datazoo.cesnet.cz/datasets/cesnet-tls-year22`
- **Download**: `https://zenodo.org/records/10008600`
- **DOI**: `10.5281/zenodo.10008600`
- **Collection**: 52 distinct weekly temporal partitions spanning all of 2022 (`W-2022-01` to `W-2022-52`).
- **Purpose**: Benchmarks temporal concept drift and classifier degradation over 12 months.

### 3.4 CESNET-QUICEXT-25
- **Source**: `https://datazoo.cesnet.cz/datasets/cesnet-quicext-25`
- **Collection**: 2024–2025 modern QUIC protocol evolution, draft extensions, and multipath flows.

### 3.5 CipherSpectrum
- **Source**: `https://github.com/cipherspectrum`
- **Download**: `https://zenodo.org/records/8300000`
- **DOI**: `10.1109/SP54263.2024.00030` (IEEE S&P 2024)
- **Collection**: 120,000 TLS 1.3 sessions captured across 40 popular web domains using automated headless browsers.
- **Cipher Suites**: Balanced across all 3 standard TLS 1.3 ciphers:
  1. `TLS_AES_128_GCM_SHA256`
  2. `TLS_AES_256_GCM_SHA384`
  3. `TLS_CHACHA20_POLY1305_SHA256`
- **Classification Task**: 40-domain prediction (treated as a separate domain-attribution research task, distinct from our 6-class traffic-family taxonomy).

### 3.6 ISCXVPN2016
- **Source**: `https://www.unb.ca/cic/datasets/vpn.html`
- **DOI**: `10.5220/0005691001060114` (ICISSP 2016)
- **Collection**: 2015 testbed PCAP captures at the Canadian Institute for Cybersecurity.
- **Labels**: VPN vs Non-VPN across 6 service categories:
  - `Chat` (AIM, ICQ, Facebook, Hangouts, Skype)
  - `Email` (SMPT, POP3, IMAP, Gmail)
  - `File_Transfer` (FTPS, SFTP)
  - `P2P` (BitTorrent)
  - `Streaming` (YouTube, Netflix, Vimeo, Spotify)
  - `VoIP` (VoIP calls, Skype audio)
- **Scientific Limitation**: Contains obsolete protocol versions (TLS 1.0, 1.1, early 1.2, SSLv3). Fixed testbed server IPs can cause severe label leakage if IP addresses or ports are included in feature matrices.

---

## 4. Storage Architecture & Directory Invariants

```
data/
├── external_raw/            # Immutable raw source files (PCAP, Parquet, tar.gz)
│   ├── cesnet-tls22/
│   ├── cesnet-quic22/
│   ├── cipherspectrum/
│   └── iscxvpn2016/
├── external_processed/      # Zero-payload normalized flow indices & prefix JSONL
│   ├── cesnet-tls22/
│   ├── cipherspectrum/
│   └── iscxvpn2016/
└── external_manifests/      # Cryptographic hashes, validation reports, registry exports
results/
└── external_benchmarks/     # Model benchmark evaluation results (F1, ECE, latency)
    ├── cesnet-tls22/
    ├── cipherspectrum/
    └── iscxvpn2016/
```

- **Invariant 1**: Raw downloaded archives in `data/external_raw/` are **never modified or in-place edited**.
- **Invariant 2**: Processed outputs contain strictly zero application payloads.
- **Invariant 3**: Results are isolated per dataset under `results/external_benchmarks/<dataset_id>/`.
