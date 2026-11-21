"""
In-Memory Transient Bidirectional Flow Manager for Dataset V3.

Associates incoming packets into bidirectional flows in volatile memory.
Generates cryptographically random UUID flow identifiers without encoding network metadata.
Calculates relative timestamps, microsecond IATs, first-observed directions, and termination reasons.
Wipes all transient IP and port mappings from memory upon flow termination.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from research.dataset_v3.packet_parser import TransientPacketData
from research.dataset_v3.schemas import FlowIndexRecord, PacketMetadataRecord

logger = logging.getLogger("research.dataset_v3.flow_manager")


@dataclass
class _ActiveFlowState:
    """Internal volatile tracking state for an active in-flight flow."""
    flow_id: str
    parent_flow_id: str
    init_endpoint: Tuple[str, int]  # (src_ip, src_port) of packet index 0
    first_packet_wire_ts: float
    last_packet_wire_ts: float
    first_packet_arrival_mono: float
    last_packet_arrival_mono: float
    packet_count: int
    direction_0_packets: int
    direction_1_packets: int
    direction_0_bytes: int
    direction_1_bytes: int
    transport_protocol: str
    pending_termination: Optional[str] = None  # TCP_FIN, TCP_RST


class FlowManager:
    """
    Manages active bidirectional flows in memory during a Dataset V3 capture session.
    """

    def __init__(
        self,
        session_id: str,
        idle_timeout_seconds: float = 30.0,
        active_timeout_seconds: float = 120.0,
        max_packets_per_flow: int = 10000,
    ) -> None:
        self.session_id = session_id
        self.idle_timeout_seconds = idle_timeout_seconds
        self.active_timeout_seconds = active_timeout_seconds
        self.max_packets_per_flow = max_packets_per_flow

        # Transient in-memory 5-tuple lookup table
        # Key: ((ip_a, port_a), (ip_b, port_b), protocol)
        self._active_flows: Dict[Tuple[Tuple[str, int], Tuple[str, int], str], _ActiveFlowState] = {}
        self._completed_flow_records: List[FlowIndexRecord] = []

    def _canonical_key(
        self, src_ip: str, src_port: int, dst_ip: str, dst_port: int, protocol: str
    ) -> Tuple[Tuple[str, int], Tuple[str, int], str]:
        """Creates canonical bidirectional flow key."""
        ep_a = (src_ip, src_port)
        ep_b = (dst_ip, dst_port)
        if ep_a <= ep_b:
            return (ep_a, ep_b, protocol)
        return (ep_b, ep_a, protocol)

    def process_packet(
        self, pkt: TransientPacketData
    ) -> Tuple[PacketMetadataRecord, Optional[FlowIndexRecord]]:
        """
        Processes a single transient packet:
        1. Associates it with an active flow or creates a new one.
        2. Determines direction (0 = first observed, 1 = reverse).
        3. Calculates relative timestamp and inter-arrival time in microseconds.
        4. Detects TCP FIN/RST termination flags.
        5. Generates a privacy-preserving PacketMetadataRecord.
        """
        key = self._canonical_key(
            pkt.src_ip, pkt.src_port, pkt.dst_ip, pkt.dst_port, pkt.protocol
        )

        flow_state = self._active_flows.get(key)
        now_wire = pkt.wire_timestamp
        now_mono = pkt.arrival_monotonic
        completed_flow: Optional[FlowIndexRecord] = None

        if flow_state is None:
            # First packet observed for this 5-tuple
            flow_id = f"flow_{uuid.uuid4().hex}"
            parent_flow_id = flow_id  # Physical capture: parent_flow_id == flow_id
            init_endpoint = (pkt.src_ip, pkt.src_port)

            flow_state = _ActiveFlowState(
                flow_id=flow_id,
                parent_flow_id=parent_flow_id,
                init_endpoint=init_endpoint,
                first_packet_wire_ts=now_wire,
                last_packet_wire_ts=now_wire,
                first_packet_arrival_mono=now_mono,
                last_packet_arrival_mono=now_mono,
                packet_count=1,
                direction_0_packets=1,
                direction_1_packets=0,
                direction_0_bytes=pkt.wire_length,
                direction_1_bytes=0,
                transport_protocol=pkt.protocol,
                pending_termination="TCP_RST" if pkt.has_rst else ("TCP_FIN" if pkt.has_fin else None),
            )
            self._active_flows[key] = flow_state

            direction = 0
            packet_index = 0
            relative_us = 0
            iat_us = 0
        else:
            # Flow already exists: determine direction relative to packet index 0
            current_endpoint = (pkt.src_ip, pkt.src_port)
            direction = 0 if current_endpoint == flow_state.init_endpoint else 1

            packet_index = flow_state.packet_count
            relative_us = max(0, int(round((now_wire - flow_state.first_packet_wire_ts) * 1_000_000)))
            iat_us = max(0, int(round((now_wire - flow_state.last_packet_wire_ts) * 1_000_000)))

            # Update flow state
            flow_state.packet_count += 1
            flow_state.last_packet_wire_ts = now_wire
            flow_state.last_packet_arrival_mono = now_mono

            if pkt.has_rst:
                flow_state.pending_termination = "TCP_RST"
            elif pkt.has_fin and not flow_state.pending_termination:
                flow_state.pending_termination = "TCP_FIN"

            if direction == 0:
                flow_state.direction_0_packets += 1
                flow_state.direction_0_bytes += pkt.wire_length
            else:
                flow_state.direction_1_packets += 1
                flow_state.direction_1_bytes += pkt.wire_length

            # Check max packet limit
            if flow_state.packet_count >= self.max_packets_per_flow:
                completed_flow = self._finalize_flow(
                    key, flow_state, termination_reason="ACTIVE_TIMEOUT"
                )

        record = PacketMetadataRecord(
            session_id=self.session_id,
            flow_id=flow_state.flow_id,
            parent_flow_id=flow_state.parent_flow_id,
            packet_index=packet_index,
            relative_timestamp_us=relative_us,
            inter_arrival_time_us=iat_us,
            packet_length=pkt.captured_link_layer_length,
            captured_link_layer_length_bytes=pkt.captured_link_layer_length,
            captured_length_bytes=pkt.captured_length,
            wire_frame_length_bytes=pkt.wire_frame_length,
            ip_total_length_bytes=pkt.ip_total_length,
            captured_length=pkt.captured_length,
            direction=direction,
            transport_protocol=pkt.protocol,
            tcp_flags=pkt.tcp_flags,
            is_synthetic=False,
        )

        return record, completed_flow

    def _finalize_flow(
        self,
        key: Tuple[Tuple[str, int], Tuple[str, int], str],
        state: _ActiveFlowState,
        termination_reason: str = "UNKNOWN",
    ) -> FlowIndexRecord:
        """Converts active flow state into immutable FlowIndexRecord and wipes 5-tuple."""
        dt_start = datetime.fromtimestamp(state.first_packet_wire_ts, tz=timezone.utc).isoformat()
        dt_end = datetime.fromtimestamp(state.last_packet_wire_ts, tz=timezone.utc).isoformat()
        dur_us = max(0, int(round((state.last_packet_wire_ts - state.first_packet_wire_ts) * 1_000_000)))

        # Priority: explicit TCP termination flags override timeout if observed
        final_reason = state.pending_termination or termination_reason

        cnt = state.packet_count
        index_record = FlowIndexRecord(
            session_id=self.session_id,
            flow_id=state.flow_id,
            parent_flow_id=state.parent_flow_id,
            first_packet_timestamp_utc=dt_start,
            last_packet_timestamp_utc=dt_end,
            packet_count=cnt,
            duration_us=dur_us,
            direction_0_packets=state.direction_0_packets,
            direction_1_packets=state.direction_1_packets,
            direction_0_bytes=state.direction_0_bytes,
            direction_1_bytes=state.direction_1_bytes,
            transport_protocol=state.transport_protocol,
            termination_reason=final_reason,
            prefix_3_available=(cnt >= 3),
            prefix_5_available=(cnt >= 5),
            prefix_10_available=(cnt >= 10),
            prefix_20_available=(cnt >= 20),
            is_synthetic=False,
        )

        self._completed_flow_records.append(index_record)
        if key in self._active_flows:
            del self._active_flows[key]

        return index_record

    def check_timeouts(self, current_ts: float) -> List[FlowIndexRecord]:
        """Checks idle and active timeouts; finalizes expired flows."""
        expired_items: List[Tuple[Tuple[Tuple[str, int], Tuple[str, int], str], str]] = []
        for key, state in self._active_flows.items():
            idle_elapsed = current_ts - state.last_packet_wire_ts
            active_elapsed = current_ts - state.first_packet_wire_ts
            if active_elapsed >= self.active_timeout_seconds:
                expired_items.append((key, "ACTIVE_TIMEOUT"))
            elif idle_elapsed >= self.idle_timeout_seconds:
                expired_items.append((key, "IDLE_TIMEOUT"))

        newly_completed: List[FlowIndexRecord] = []
        for key, reason in expired_items:
            state = self._active_flows[key]
            rec = self._finalize_flow(key, state, termination_reason=reason)
            newly_completed.append(rec)

        return newly_completed

    def finalize_all(self, termination_reason: str = "CAPTURE_END") -> List[FlowIndexRecord]:
        """
        Finalizes all remaining active flows at session end.
        Assigns CAPTURE_END (so capture interruption is not mistaken for natural flow end).
        Wipes all transient keys from memory.
        """
        all_keys = list(self._active_flows.keys())
        newly_completed: List[FlowIndexRecord] = []
        for key in all_keys:
            state = self._active_flows[key]
            rec = self._finalize_flow(key, state, termination_reason=termination_reason)
            newly_completed.append(rec)

        self._active_flows.clear()
        return self._completed_flow_records

    @property
    def active_flow_count(self) -> int:
        return len(self._active_flows)

    @property
    def completed_flow_count(self) -> int:
        return len(self._completed_flow_records)
