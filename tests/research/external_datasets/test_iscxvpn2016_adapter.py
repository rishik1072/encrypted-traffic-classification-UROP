"""
Tests for ISCXVPN2016 Adapter.
"""

from pathlib import Path
import platform
import pytest
import numpy as np

from scapy.layers.l2 import Ether
from scapy.layers.inet import IP, TCP
from scapy.packet import Raw
from scapy.utils import wrpcap

from research.external_datasets.adapters.iscxvpn2016 import IscxVpn2016Adapter
from research.external_datasets.schemas import FeatureProfileType


@pytest.fixture
def synthetic_iscx_pcap(tmp_path: Path) -> Path:
    """Creates a temporary synthetic ISCXVPN2016 PCAP fixture."""
    pcap_path = tmp_path / "vpn_skype_audio1.pcap"
    packets = []

    # Connection 1: Skype Audio (inside VPN)
    for i in range(8):
        is_client = (i % 2 == 0)
        src = "10.8.0.2" if is_client else "198.51.100.10"
        dst = "198.51.100.10" if is_client else "10.8.0.2"
        sport = 45000 if is_client else 443
        dport = 443 if is_client else 45000

        pkt = Ether() / IP(src=src, dst=dst) / TCP(sport=sport, dport=dport) / Raw(b"\x00" * (100 + i * 20))
        pkt.time = 2000.0 + (i * 0.010)
        packets.append(pkt)

    wrpcap(str(pcap_path), packets)
    return pcap_path


def test_iscxvpn2016_label_inference(tmp_path: Path):
    adapter = IscxVpn2016Adapter(
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
    )

    vpn, cat, app = adapter._infer_labels("vpn_skype_audio1.pcap")
    assert vpn == "VPN"
    assert cat == "Chat"
    assert app == "skype"

    vpn2, cat2, app2 = adapter._infer_labels("youtube2.pcap")
    assert vpn2 == "Non-VPN"
    assert cat2 == "Streaming"
    assert app2 == "youtube"


def test_iscxvpn2016_ingestion_and_bidirectional_assembly(tmp_path: Path, synthetic_iscx_pcap: Path):
    adapter = IscxVpn2016Adapter(
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
    )

    count = adapter.ingest(synthetic_iscx_pcap)
    assert count == 1
    assert len(adapter.flows) == 1

    flow = adapter.flows[0]
    assert flow.label == "Chat"
    assert flow.label_category == "VPN"
    assert flow.total_packets == 8

    # Ensure auxiliary metadata notes legacy capture and server IP warning
    assert flow.auxiliary_metadata.get("server_ip_leakage_warning") is True


def test_iscxvpn2016_prefix_extraction(tmp_path: Path, synthetic_iscx_pcap: Path):
    adapter = IscxVpn2016Adapter(
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
    )
    adapter.ingest(synthetic_iscx_pcap)

    for k in (3, 5):
        X, y, feature_names = adapter.extract_prefix_features(k=k)
        assert X.shape[0] == 1
        assert X.shape[1] == len(feature_names)
        assert y[0] == "Chat"
        # Check no IP addresses or ports in feature names
        for col in feature_names:
            assert "ip" not in col.lower() or "ipt" in col.lower()  # Only ipt (inter-packet time) allowed
            assert "port" not in col.lower()


def test_iscxvpn2016_validation_and_partitions(tmp_path: Path, synthetic_iscx_pcap: Path):
    adapter = IscxVpn2016Adapter(
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
    )
    adapter.ingest(synthetic_iscx_pcap)

    parts = adapter.get_partitions()
    assert "train" in parts
    assert "val" in parts
    assert "test" in parts

    report = adapter.validate()
    assert report.total_flows == 1
    assert report.total_packets == 8
    assert report.leakage_checks.get("zero_payload_persistence") is True
