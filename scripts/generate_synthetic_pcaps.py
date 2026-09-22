"""
Synthetic PCAP and Traffic Generator Utility.

Creates valid sample PCAPs with multiple bidirectional packets for testing the complete dataset preparation pipeline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def generate_synthetic_pcap_files(base_dir: Path | str = ".") -> List[Path]:
    """
    Generates synthetic PCAPs corresponding to dataset_manifest.csv
    where each flow contains multiple bidirectional packets.
    """
    base = Path(base_dir)
    pcap_dir = base / "data/raw/pcap"
    pcap_dir.mkdir(parents=True, exist_ok=True)

    manifest_files = [
        ("web_sample_01.pcap", "TCP", 50001, 443, 10),
        ("web_sample_02.pcap", "TCP", 50002, 443, 8),
        ("video_sample_01.pcap", "UDP", 50003, 443, 20),
        ("video_sample_02.pcap", "UDP", 50004, 443, 18),
        ("msg_sample_01.pcap", "TCP", 50005, 5222, 10),
        ("msg_sample_02.pcap", "TCP", 50006, 5222, 12),
        ("voip_sample_01.pcap", "UDP", 50007, 5060, 15),
        ("voip_sample_02.pcap", "UDP", 50008, 5060, 15),
        ("file_sample_01.pcap", "TCP", 50009, 22, 25),
        ("file_sample_02.pcap", "TCP", 50010, 22, 22),
        ("other_sample_01.pcap", "UDP", 50011, 123, 8),
        ("other_sample_02.pcap", "UDP", 50012, 53, 8),
    ]

    created_paths = []

    try:
        from scapy.all import IP, TCP, UDP, Raw, wrpcap  # type: ignore

        for filename, proto, sport, dport, n_pkts in manifest_files:
            filepath = pcap_dir / filename
            packets = []
            for i in range(n_pkts):
                t = 1000.0 + (i * 0.05)
                length_pad = b"\x00" * (64 + (i * 10))
                # Alternate forward and backward
                if i % 2 == 0:
                    src_ip, dst_ip = "192.168.1.100", "10.0.0.1"
                    s_port, d_port = sport, dport
                else:
                    src_ip, dst_ip = "10.0.0.1", "192.168.1.100"
                    s_port, d_port = dport, sport

                if proto == "TCP":
                    pkt = IP(src=src_ip, dst=dst_ip) / TCP(sport=s_port, dport=d_port, flags="PA") / Raw(load=length_pad)
                else:
                    pkt = IP(src=src_ip, dst=dst_ip) / UDP(sport=s_port, dport=d_port) / Raw(load=length_pad)
                
                pkt.time = t
                packets.append(pkt)

            wrpcap(str(filepath), packets)
            created_paths.append(filepath)

        logger.info("Generated %d synthetic PCAPs with Scapy", len(created_paths))
    except ImportError:
        logger.warning("Scapy not installed. PCAP generation skipped.")

    return created_paths


if __name__ == "__main__":
    generate_synthetic_pcap_files()
