"""
Tests for CipherSpectrum Adapter.
"""

from pathlib import Path
import platform
import pytest
import numpy as np

from scapy.layers.l2 import Ether
from scapy.layers.inet import IP, TCP
from scapy.packet import Raw
from scapy.utils import wrpcap

from research.external_datasets.adapters.cipherspectrum import CipherSpectrumAdapter
from research.external_datasets.schemas import FeatureProfileType


@pytest.fixture
def synthetic_cipherspectrum_pcap(tmp_path: Path) -> Path:
    """Creates a temporary synthetic CipherSpectrum PCAP fixture."""
    pcap_path = tmp_path / "google_TLS_AES_128_GCM_SHA256_sess01.pcap"
    packets = []

    # Packet 1: Client -> Server SYN
    p1 = Ether() / IP(src="192.168.1.50", dst="142.250.190.46") / TCP(sport=54321, dport=443, flags="S", seq=100)
    p1.time = 1000.0
    packets.append(p1)

    # Packet 2: Server -> Client SYN-ACK
    p2 = Ether() / IP(src="142.250.190.46", dst="192.168.1.50") / TCP(sport=443, dport=54321, flags="SA", seq=200, ack=101)
    p2.time = 1000.025
    packets.append(p2)

    # Packet 3: Client -> Server ACK
    p3 = Ether() / IP(src="192.168.1.50", dst="142.250.190.46") / TCP(sport=54321, dport=443, flags="A", seq=101, ack=201)
    p3.time = 1000.026
    packets.append(p3)

    # Packet 4: Client -> Server ClientHello (Simulated with payload)
    p4 = Ether() / IP(src="192.168.1.50", dst="142.250.190.46") / TCP(sport=54321, dport=443, flags="PA", seq=101, ack=201) / Raw(b"\x16\x03\x01\x02\x00" + b"\xaa" * 500)
    p4.time = 1000.030
    packets.append(p4)

    # Packet 5: Server -> Client ServerHello + EncryptedExtensions
    p5 = Ether() / IP(src="142.250.190.46", dst="192.168.1.50") / TCP(sport=443, dport=54321, flags="PA", seq=201, ack=606) / Raw(b"\x16\x03\x03\x04\x00" + b"\xbb" * 1200)
    p5.time = 1000.060
    packets.append(p5)

    wrpcap(str(pcap_path), packets)
    return pcap_path


def test_cipherspectrum_ingestion_and_zero_payload(tmp_path: Path, synthetic_cipherspectrum_pcap: Path):
    adapter = CipherSpectrumAdapter(
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
    )

    count = adapter.ingest(synthetic_cipherspectrum_pcap)
    assert count == 1
    assert len(adapter.flows) == 1

    flow = adapter.flows[0]
    assert flow.label == "google"
    assert flow.label_category == "TLS_AES_128_GCM_SHA256"
    assert flow.total_packets == 5
    assert adapter.get_feature_profile_type() == FeatureProfileType.PROFILE_C_CIPHER_SPECTRUM

    # Verify zero-payload: ExternalPacketItem must only contain length and timing, NO raw payload field exists
    for pkt in flow.packets:
        assert isinstance(pkt.length, int)
        assert pkt.length > 0
        assert not hasattr(pkt, "payload")
        assert not hasattr(pkt, "data")
        assert not hasattr(pkt, "bytes")


def test_cipherspectrum_prefix_features(tmp_path: Path, synthetic_cipherspectrum_pcap: Path):
    adapter = CipherSpectrumAdapter(
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
    )
    adapter.ingest(synthetic_cipherspectrum_pcap)

    for k in (3, 5):
        X, y, feature_names = adapter.extract_prefix_features(k=k)
        assert X.shape[0] == 1
        assert X.shape[1] == len(feature_names)
        assert y[0] == "google"
        assert f"k{k}_fwd_frame_bytes" in feature_names
        assert f"k{k}_bwd_frame_bytes" in feature_names


def test_cipherspectrum_partitioning_and_validation(tmp_path: Path, synthetic_cipherspectrum_pcap: Path):
    adapter = CipherSpectrumAdapter(
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
    )
    adapter.ingest(synthetic_cipherspectrum_pcap)

    parts = adapter.get_partitions()
    assert "train" in parts
    assert "val" in parts
    assert "test" in parts

    report = adapter.validate()
    assert report.total_flows == 1
    assert report.total_packets == 5
    assert report.leakage_checks.get("zero_payload_persistence") is True
    assert report.leakage_checks.get("no_sni_leak") is True
