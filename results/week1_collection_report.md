# Week 1 Real Traffic Collection Lab Report (Verified Real Capture)

**Release Date:** `2026-08-23`  
**Milestone:** Verified Strict Real Traffic Collection on Npcap/Wi-Fi  

---

## 📌 Executive Summary

The research-integrity issue in the collection framework has been resolved:
1. **Zero Synthetic Fallbacks:** Synthetic generation fallbacks were completely removed from real collection pathways.
2. **Fail-Closed Architecture:** Any adapter error, permission fault, or zero-packet window immediately transitions the session to `FAILED` without real dataset registration.
3. **Windows Wi-Fi Adapter Resolution:** Friendly names (`Wi-Fi`) automatically resolve to Scapy/Npcap device interfaces (`\Device\NPF_{752C12FF-B25B-4451-86D9-E8E0E43DC567}`).
4. **Collision-Resistant Provenance:** Unique session IDs (`20260823_144333_web_001_5c95`) with SHA-256 hashing recorded in `results/tables/dataset_version_manifest.csv`.

---

## 📊 Verified Genuine 60-Second Real Capture

A genuine 60-second real Web browsing session was successfully captured, validated, and registered:

- **Session ID:** `20260823_144333_web_001_5c95`
- **Capture Source:** `REAL_LIVE_CAPTURE` (Zero synthetic fallback)
- **Resolved Adapter:** `Wi-Fi` (`Intel(R) Wi-Fi 6 AX201 160MHz`)
- **Resolved Npcap Name:** `\Device\NPF_{752C12FF-B25B-4451-86D9-E8E0E43DC567}`
- **Capture Duration:** `60.01 seconds`
- **Genuine Packets Captured:** `6,082 packets`
- **Genuine Data Volume:** `4,670,741 bytes (4.45 MB)`
- **Bidirectional Flows Detected:** `6 flows`
- **SHA-256 Digest:** `31d21b10d31521f83cbe54298132e0e5a95b8719f9bb49f8749830c253457ecf`
- **Validation Status:** `PASS`
- **Metadata Path:** `data/raw/metadata/20260823_144333_web_001_5c95.csv`

---

## 🛠️ Verification & Test Suite

- **Unit & Security Tests:** `34 / 34 PASSED` (`python -m unittest discover -s tests -p "test_*.py" -v`)
- **Live Interface Sniffing:** `PASSED` (`python scripts/test_live_interface.py --interface "Wi-Fi" --duration 5`)
- **Npcap Diagnostics:** `PASSED` (`python scripts/check_capture_environment.py`)
- **Dataset Registry Audit:** `VERIFIED` (`python scripts/inspect_dataset.py`)
