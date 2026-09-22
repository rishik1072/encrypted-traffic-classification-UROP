"""
Traffic Activity Registry.

Defines the expected protocol distributions and operator procedures for each class.
Note: These are operational expectations only; classification features are derived
strictly from statistical flow behavior.
"""

from __future__ import annotations

from typing import Any, Dict

TRAFFIC_ACTIVITIES: Dict[str, Dict[str, Any]] = {
    "Web": {
        "activity": "Interactive HTTPS web browsing, searching, and reading text/documentation",
        "expected_protocols": ["TCP", "TLS", "HTTPS"],
        "expected_ports": [443, 80],
        "notes": "Burst-like request-response patterns with intermittent idle thinking pauses.",
    },
    "Video": {
        "activity": "Adaptive video playback (YouTube / Vimeo / Twitch)",
        "expected_protocols": ["TCP", "UDP", "QUIC", "HTTPS"],
        "expected_ports": [443],
        "notes": "Sustained high-throughput chunks and periodic buffer replenishment bursts.",
    },
    "Messaging": {
        "activity": "Text chat messages and presence heartbeats (Signal / Slack / Discord text)",
        "expected_protocols": ["TCP", "TLS", "WSS"],
        "expected_ports": [443],
        "notes": "Low-volume, discrete packet bursts with long inter-arrival times.",
    },
    "VoIP": {
        "activity": "Interactive two-way voice call (Discord Voice / Zoom Audio / WebRTC)",
        "expected_protocols": ["UDP", "SRTP", "STUN"],
        "expected_ports": [443, 3478, 50000],
        "notes": "Highly periodic, low-jitter bidirectional packets with stable packet sizes.",
    },
    "File Transfer": {
        "activity": "Bulk binary encrypted download/upload (SFTP / Large HTTPS binary)",
        "expected_protocols": ["TCP", "TLS", "SFTP"],
        "expected_ports": [22, 443],
        "notes": "Full MTU packet sizes dominated by one direction with minimal return ACKs.",
    },
    "Other": {
        "activity": "Encrypted background OS telemetry, DNS-over-HTTPS (DoH), and NTP",
        "expected_protocols": ["UDP", "TCP", "HTTPS"],
        "expected_ports": [53, 123, 443, 853],
        "notes": "Periodic short query/response exchanges without interactive user bursts.",
    },
}
