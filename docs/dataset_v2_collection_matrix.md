# Dataset v2 Collection & Generalization Matrix

**Dataset Version**: `dataset_v2`  
**Total Real Sessions**: 150 (25 sessions per class)  
**Total Real Clean Flows**: 302 flows  
**Classes (6)**: Web, Video, Messaging, VoIP, File Transfer, Other  

---

## 1. Environment & Experimental Dimensions

| Dimension | Variants / Identifiers | Description |
| :--- | :--- | :--- |
| **Environment** | `env_win11_wifi` (A), `env_win11_eth` (B), `env_win11_cellular` (C) | Physical network interface and link media |
| **Network Condition** | `NORMAL`, `LOW_BANDWIDTH`, `HIGH_LATENCY`, `PACKET_LOSS` | Controlled link emulation profiles |
| **Temporal Dates** | `2026-08-20`, `2026-08-21`, `2026-08-22`, `2026-08-23` | Multi-day longitudinal capture collection |
| **Tunnel Visibility** | `warp_enabled` (WireGuard UDP tunnel), `warp_disabled` (Direct IP transport) | Encapsulation & header obfuscation mode |
| **Device Hardware** | `dev_win11_laptop`, `dev_win11_desktop` | Host device architecture |

---

## 2. Activity Diversity Matrix

| Class | Activity Variant Code | Activity Description | Target Sessions | Collected Sessions |
| :--- | :--- | :--- | :---: | :---: |
| **Web** | `web_wikipedia` | Multi-tab encyclopedic reading & searching | 5 | 5 |
| **Web** | `web_news` | Dynamic newspaper / media page scrolling | 5 | 5 |
| **Web** | `web_ecommerce` | Catalog navigation, product filtering, checkout simulation | 5 | 5 |
| **Web** | `web_github_docs` | Technical documentation and code browsing | 5 | 5 |
| **Web** | `web_tech_blogs` | Static and interactive blog reading | 5 | 5 |
| **Video** | `vid_youtube_1080p` | High-definition 1080p adaptive stream playback | 5 | 5 |
| **Video** | `vid_vimeo_720p` | 720p H.264 Vimeo embedded playback | 5 | 5 |
| **Video** | `vid_twitch_live` | Low-latency live broadcast streaming | 5 | 5 |
| **Video** | `vid_dailymotion_sd` | Standard-definition video buffer replenishment | 5 | 5 |
| **Video** | `vid_netflix_4k` | Ultra HD chunk-based streaming | 5 | 5 |
| **Messaging** | `msg_slack_chat` | Interactive workplace messaging & snippets | 5 | 5 |
| **Messaging** | `msg_discord_text` | Real-time gaming community text chat | 5 | 5 |
| **Messaging** | `msg_telegram_sync` | Channel synchronization and short text bursts | 5 | 5 |
| **Messaging** | `msg_whatsapp_web` | Web client WebSocket text and status exchanges | 5 | 5 |
| **Messaging** | `msg_signal_chat` | End-to-end encrypted desktop message sync | 5 | 5 |
| **VoIP** | `voip_zoom_audio` | Two-way Opus audio conference call | 5 | 5 |
| **VoIP** | `voip_teams_voice` | Corporate voice meeting stream | 5 | 5 |
| **VoIP** | `voip_meet_audio` | WebRTC audio bridge exchange | 5 | 5 |
| **VoIP** | `voip_discord_voice` | Low-jitter interactive gamer voice channel | 5 | 5 |
| **VoIP** | `voip_skype_call` | Peer-to-peer audio call stream | 5 | 5 |
| **File Transfer** | `ft_gdrive_upload` | Large cloud storage file upload | 5 | 5 |
| **File Transfer** | `ft_dropbox_download`| Medium binary archive download | 5 | 5 |
| **File Transfer** | `ft_sftp_sync` | SSH/SFTP bulk directory synchronization | 5 | 5 |
| **File Transfer** | `ft_onedrive_sync` | Small multi-document background sync | 5 | 5 |
| **File Transfer** | `ft_mega_download` | Chunked direct cloud file download | 5 | 5 |
| **Other** | `oth_dns_ntp_sync` | DoH query resolution and NTP clock drift sync | 5 | 5 |
| **Other** | `oth_os_update_check`| Background OS patch verification queries | 5 | 5 |
| **Other** | `oth_telemetry_heartbeat`| Device health & diagnostic telemetry pings | 5 | 5 |
| **Other** | `oth_idle_keepalive` | Background TCP/UDP tunnel NAT keep-alives | 5 | 5 |
| **Other** | `oth_cloud_backup` | Incremental encrypted registry backup heartbeat | 5 | 5 |
| **TOTAL** | **30 Activity Variants** | **Complete Multi-Environment Coverage** | **150** | **150** |

---

## 3. Environment & Condition Split Allocation

| Partition Key | Normal Condition | Low Bandwidth | High Latency | Packet Loss | Total Sessions |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Environment A (`env_win11_wifi`)** | 60 (Phase 1 Baseline) | 12 | 12 | 6 | **90** |
| **Environment B (`env_win11_eth`)** | 20 | 5 | 5 | 0 | **30** |
| **Environment C (`env_win11_cellular`)** | 20 | 5 | 5 | 0 | **30** |
| **TOTAL** | **100** | **22** | **22** | **6** | **150** |
