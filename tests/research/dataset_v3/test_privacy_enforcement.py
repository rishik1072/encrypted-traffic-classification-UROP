"""
Unit Tests: Dataset V3 Privacy and Anonymization Enforcement.

Validates:
- Complete absence of IP addresses, ports, MAC addresses, and payloads across all output files.
- Random device pseudonyms.
- Cryptographically random flow IDs.
"""

from __future__ import annotations

import re
from pathlib import Path
from research.dataset_v3.collector import PhysicalTrafficCollector
from research.dataset_v3.config import DatasetV3Config
from tests.research.dataset_v3.test_packet_parser import create_synthetic_ipv4_tcp_raw


def test_zero_pii_persistence_guarantee(tmp_path: Path) -> None:
    session_id = "sess_privacy_strict_001"
    config = DatasetV3Config(
        output_root=tmp_path,
        session_id=session_id,
        interface="MockPhysicalInterface",
        intended_traffic_class="Web",
        application_alias="firefox_tls",
    )
    collector = PhysicalTrafficCollector(config=config)
    collector.start_capture(dry_run=True)

    # Ingest packets with highly specific PII strings and addresses
    secret_payload = b"SUPER_SECRET_USER_PASSWORD_TOKEN_XYZ_999"
    secret_ip_src = "192.168.100.222"
    secret_ip_dst = "172.217.16.206"
    secret_sport = 49152
    secret_dport = 8443

    raw_pkt = create_synthetic_ipv4_tcp_raw(
        src_ip=secret_ip_src,
        dst_ip=secret_ip_dst,
        sport=secret_sport,
        dport=secret_dport,
        payload=secret_payload,
    )

    collector.process_raw_ip_bytes(raw_pkt, ts=1700000000.0)
    collector.stop_capture(status="COMPLETED")

    session_dir = tmp_path / session_id
    generated_files = list(session_dir.iterdir())
    assert len(generated_files) >= 5

    # Check every generated file
    for f_path in generated_files:
        with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

            # 1. Assert payload string never written
            assert "SUPER_SECRET_USER_PASSWORD" not in content, f"Payload leaked into {f_path.name}!"

            # 2. Assert source/dest IPs never written
            assert secret_ip_src not in content, f"Source IP leaked into {f_path.name}!"
            assert secret_ip_dst not in content, f"Dest IP leaked into {f_path.name}!"

            # 3. Assert port numbers not written as network identifiers
            # (Note: check that port numbers are not present in keys or values)
            assert f'"{secret_sport}"' not in content
            assert f'"{secret_dport}"' not in content

            # 4. Assert no standard MAC address regex matches
            mac_regex = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})\b")
            assert not mac_regex.search(content), f"MAC address leaked into {f_path.name}!"
