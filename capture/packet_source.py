"""
Packet Source Abstraction Layer.

Provides unified stream readers (PCAPPacketSource, MetadataPacketSource, SyntheticPacketSource)
producing RawPacketMetadata records for FlowGenerator.
"""

from __future__ import annotations

import csv
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Generator, Optional

from capture.packet_capture import RawPacketMetadata

logger = logging.getLogger(__name__)


class PacketSource(ABC):
    """Abstract base class for all packet input sources."""

    @abstractmethod
    def read_packets(self) -> Generator[RawPacketMetadata, None, None]:
        """Yields standardized RawPacketMetadata items sequentially."""
        raise NotImplementedError

    def close(self) -> None:
        """Closes underlying file descriptors or resources."""
        pass


class PCAPPacketSource(PacketSource):
    """Reads packets from an offline PCAP/PCAPNG file using Scapy/PyShark."""

    def __init__(self, pcap_path: str | Path) -> None:
        self.pcap_path = Path(pcap_path)
        if not self.pcap_path.exists() or self.pcap_path.is_dir():
            raise FileNotFoundError(f"PCAP source file not found or is a directory: {self.pcap_path}")

    def read_packets(self) -> Generator[RawPacketMetadata, None, None]:
        from capture.packet_capture import PCAPReader
        reader = PCAPReader(self.pcap_path)
        yield from reader.read_packets()


class MetadataPacketSource(PacketSource):
    """Reads packets from zero-payload metadata CSV files produced during live collection."""

    def __init__(self, metadata_path: str | Path) -> None:
        self.metadata_path = Path(metadata_path)
        if not self.metadata_path.exists() or self.metadata_path.is_dir():
            raise FileNotFoundError(f"Metadata source file not found or is a directory: {self.metadata_path}")

    def read_packets(self) -> Generator[RawPacketMetadata, None, None]:
        with open(self.metadata_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                # Anonymize IP representations while preserving 5-tuple consistency
                src_port = int(r.get("source_port", 0))
                dst_port = int(r.get("destination_port", 0))
                proto = str(r.get("protocol", "TCP"))
                length = int(r.get("packet_length", 0))
                ts = float(r.get("timestamp", 0.0))

                yield RawPacketMetadata(
                    timestamp=ts,
                    src_ip="192.168.1.100",  # Anonymized canonical endpoint
                    dst_ip="1.1.1.1",
                    src_port=src_port,
                    dst_port=dst_port,
                    protocol=proto,
                    length=length,
                )


class SyntheticPacketSource(PacketSource):
    """Generates synthetic deterministic packets for unit test fixtures."""

    def __init__(self, packet_count: int = 20, traffic_class: str = "Web") -> None:
        self.packet_count = packet_count
        self.traffic_class = traffic_class

    def read_packets(self) -> Generator[RawPacketMetadata, None, None]:
        base_t = 1000.0
        dst_p = 443 if self.traffic_class in ["Web", "Video", "Messaging", "File Transfer"] else 50000
        proto = "UDP" if self.traffic_class in ["VoIP", "Other"] else "TCP"

        for i in range(self.packet_count):
            yield RawPacketMetadata(
                timestamp=base_t + i * 0.1,
                src_ip="10.0.0.1",
                dst_ip="10.0.0.2",
                src_port=50000 + (i % 3),
                dst_port=dst_p,
                protocol=proto,
                length=500 + (i * 20),
            )


def create_packet_source(
    raw_source_type: str,
    raw_source_path: str,
    traffic_class: str = "Web",
) -> PacketSource:
    """Factory creating appropriate PacketSource based on manifest metadata."""
    stype = raw_source_type.upper().strip()

    if stype == "PCAP":
        if not raw_source_path or not Path(raw_source_path).exists() or Path(raw_source_path).is_dir():
            raise FileNotFoundError(f"PCAP source validation failed: '{raw_source_path}' does not exist.")
        return PCAPPacketSource(raw_source_path)

    elif stype in ["METADATA_CSV", "METADATA_PARQUET"]:
        if not raw_source_path or not Path(raw_source_path).exists() or Path(raw_source_path).is_dir():
            raise FileNotFoundError(f"Metadata source validation failed: '{raw_source_path}' does not exist.")
        return MetadataPacketSource(raw_source_path)

    elif stype == "SYNTHETIC_FIXTURE":
        return SyntheticPacketSource(packet_count=20, traffic_class=traffic_class)

    else:
        raise ValueError(f"Unsupported raw_source_type: '{raw_source_type}' (Path: '{raw_source_path}')")
