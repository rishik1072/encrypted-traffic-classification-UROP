"""
Flow Generation and Bidirectional Flow Tracking Module.

Aggregates individual packets into 5-tuple bidirectional flows with timeout management.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from capture.packet_capture import RawPacketMetadata

logger = logging.getLogger(__name__)


class Direction(Enum):
    FORWARD = 1
    BACKWARD = 2


@dataclass(frozen=True)
class FlowKey:
    """Canonical 5-tuple identifying a bidirectional network flow."""
    ip_a: str
    port_a: int
    ip_b: str
    port_b: int
    protocol: str

    @classmethod
    def from_packet(cls, pkt: RawPacketMetadata) -> Tuple[FlowKey, Direction]:
        """
        Derives canonical flow key and determines packet direction relative to the flow initiator.
        """
        # Canonical sorting to group both directions of the 5-tuple
        endpoint_a = (pkt.src_ip, pkt.src_port)
        endpoint_b = (pkt.dst_ip, pkt.dst_port)

        if endpoint_a <= endpoint_b:
            key = cls(
                ip_a=pkt.src_ip,
                port_a=pkt.src_port,
                ip_b=pkt.dst_ip,
                port_b=pkt.dst_port,
                protocol=pkt.protocol,
            )
            direction = Direction.FORWARD
        else:
            key = cls(
                ip_a=pkt.dst_ip,
                port_a=pkt.dst_port,
                ip_b=pkt.src_ip,
                port_b=pkt.src_port,
                protocol=pkt.protocol,
            )
            direction = Direction.BACKWARD

        return key, direction


@dataclass
class Flow:
    """Represents a bidirectional sequence of packets sharing the same 5-tuple."""
    key: FlowKey
    initiator_ip: str
    initiator_port: int
    start_time: float
    last_seen: float
    
    # Packet metadata records: (timestamp, length, direction)
    packet_records: List[Tuple[float, int, Direction]] = field(default_factory=list)
    
    # TLS metadata accumulator if encountered in handshake
    tls_sni: Optional[str] = None
    tls_version: Optional[str] = None
    tls_cipher_suites_count: Optional[int] = None
    tls_extensions_count: Optional[int] = None

    def add_packet(self, pkt: RawPacketMetadata) -> None:
        """Appends packet metadata to this flow and updates timestamps."""
        # Determine direction relative to the initiator
        if pkt.src_ip == self.initiator_ip and pkt.src_port == self.initiator_port:
            direction = Direction.FORWARD
        else:
            direction = Direction.BACKWARD

        self.packet_records.append((pkt.timestamp, pkt.length, direction))
        self.last_seen = max(self.last_seen, pkt.timestamp)

        # Cache TLS handshake attributes if present
        if pkt.tls_sni and not self.tls_sni:
            self.tls_sni = pkt.tls_sni
        if pkt.tls_version and not self.tls_version:
            self.tls_version = pkt.tls_version
        if pkt.tls_cipher_suites_count is not None:
            self.tls_cipher_suites_count = pkt.tls_cipher_suites_count
        if pkt.tls_extensions_count is not None:
            self.tls_extensions_count = pkt.tls_extensions_count

    @property
    def duration(self) -> float:
        """Returns flow duration in seconds."""
        if not self.packet_records:
            return 0.0
        return max(0.0, self.last_seen - self.start_time)

    @property
    def total_packets(self) -> int:
        return len(self.packet_records)

    def is_expired(self, current_time: float, idle_timeout: float, active_timeout: float) -> bool:
        """Checks whether the flow has exceeded idle or active expiration thresholds."""
        idle_time = current_time - self.last_seen
        active_time = current_time - self.start_time
        return idle_time >= idle_timeout or active_time >= active_timeout


class FlowGenerator:
    """Manages active flows and yields completed flows based on timeout rules."""

    def __init__(self, idle_timeout: float = 120.0, active_timeout: float = 1800.0) -> None:
        self.idle_timeout = idle_timeout
        self.active_timeout = active_timeout
        self.active_flows: Dict[FlowKey, Flow] = {}
        logger.info(
            "FlowGenerator initialized (idle_timeout=%.1fs, active_timeout=%.1fs)",
            self.idle_timeout,
            self.active_timeout,
        )

    def process_packet(self, pkt: RawPacketMetadata) -> Optional[Flow]:
        """
        Inserts a packet into the corresponding flow.
        If an existing flow has timed out, returns the expired flow and starts a new one.
        """
        key, _ = FlowKey.from_packet(pkt)
        current_time = pkt.timestamp
        expired_flow: Optional[Flow] = None

        if key in self.active_flows:
            flow = self.active_flows[key]
            if flow.is_expired(current_time, self.idle_timeout, self.active_timeout):
                logger.debug("Flow %s expired. Archiving and re-initiating.", key)
                expired_flow = flow
                # Create a fresh flow with this packet
                new_flow = Flow(
                    key=key,
                    initiator_ip=pkt.src_ip,
                    initiator_port=pkt.src_port,
                    start_time=pkt.timestamp,
                    last_seen=pkt.timestamp,
                )
                new_flow.add_packet(pkt)
                self.active_flows[key] = new_flow
            else:
                flow.add_packet(pkt)
        else:
            flow = Flow(
                key=key,
                initiator_ip=pkt.src_ip,
                initiator_port=pkt.src_port,
                start_time=pkt.timestamp,
                last_seen=pkt.timestamp,
            )
            flow.add_packet(pkt)
            self.active_flows[key] = flow

        return expired_flow

    def flush_all(self) -> List[Flow]:
        """Flushes and returns all remaining active flows."""
        flows = list(self.active_flows.values())
        self.active_flows.clear()
        logger.info("Flushed %d remaining active flows", len(flows))
        return flows
