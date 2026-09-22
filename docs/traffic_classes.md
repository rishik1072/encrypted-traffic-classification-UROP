# Traffic Class Definitions & Labeling Rules

Definitive operational boundaries for all 6 canonical traffic classes.

---

### 1. Web
- **Definition:** Interactive browser-based HTTPS requests, DOM asset loading, REST/GraphQL API querying.
- **Inclusion:** Navigation across encrypted web pages (e.g. Wikipedia, GitHub, news portals).
- **Exclusion:** Continuous video streaming embedded in web pages (classified as Video).
- **Labeling Rule:** Assigned when the session consists solely of page browsing and DOM asset fetching.

---

### 2. Video
- **Definition:** Adaptive encrypted streaming media via HTTPS/DASH/HLS or QUIC.
- **Inclusion:** YouTube, Vimeo, Twitch video playback.
- **Exclusion:** Web browsing without media playback; real-time two-way video calls (classified as VoIP).
- **Labeling Rule:** Assigned when the session involves continuous video streaming buffering and playback.

---

### 3. Messaging
- **Definition:** Instant messaging protocols, presence notifications, and text communication over TLS or WSS.
- **Inclusion:** Signal desktop, Slack text channels, Discord messaging.
- **Exclusion:** Voice/video calls within messaging platforms (classified as VoIP); file attachments > 5 MB (classified as File Transfer).
- **Labeling Rule:** Assigned when sending/receiving short text messages and presence heartbeats.

---

### 4. VoIP
- **Definition:** Real-time bidirectional interactive audio communication.
- **Inclusion:** Discord voice channels, Zoom audio calls, WebRTC voice streams.
- **Exclusion:** One-way audio streaming (podcasts/music, classified as Video/Media).
- **Labeling Rule:** Assigned when active two-way voice communication occurs during the session.

---

### 5. File Transfer
- **Definition:** Sustained, high-throughput transmission of binary files over encrypted channels.
- **Inclusion:** SFTP uploads/downloads, large HTTPS ISO/ZIP downloads, cloud drive bulk synchronization.
- **Exclusion:** Small API payloads (< 100 KB) associated with standard web browsing.
- **Labeling Rule:** Assigned when transferring continuous files exceeding 5 MB in size.

---

### 6. Other
- **Definition:** Encrypted background operating system services, DoH/DoT DNS resolution, NTP synchronization, and telemetry.
- **Inclusion:** Windows Update / OS telemetry, Cloudflare 1.1.1.1 DoH queries.
- **Exclusion:** Explicit user-driven web, video, or communication sessions.
- **Labeling Rule:** Assigned for autonomous background system traffic.
