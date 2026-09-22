# Week 1 Traffic Collection Schedule

## Target: 6 Classes × 10 Sessions = 60 Real Encrypted Sessions

| Day | Focus Area | Target Sessions | Goal |
| :--- | :--- | :--- | :--- |
| **Day 1** | Lab Setup & Sample Validation | 1 Sample / Class (6 total) | Verify end-to-end capture, metadata exporter, and flow ingestion. |
| **Day 2** | Web Browsing Sessions | 10 Web Sessions | HTTPS news sites, documentation, search engines. |
| **Day 3** | Adaptive Video Streaming | 10 Video Sessions | YouTube 1080p, Vimeo, Twitch live streams. |
| **Day 4** | Messaging & VoIP Calls | 10 Messaging + 10 VoIP | Signal/Slack text chats; Discord/Zoom audio calls. |
| **Day 5** | File Transfers & Background Other | 10 File Transfer + 10 Other | SFTP/HTTPS binary downloads; DNS-over-HTTPS & telemetry. |
| **Day 6** | Quality Control & Duplicate Audit | Quality verification | Run `duplicate_detector.py` and capture validator audits. |
| **Day 7** | Full Pipeline Integration | Ingestion test | Ingest real metadata into `FlowGenerator` and `FeatureExtractor`. |
