"""
Synthetic Socket Table Fixture Generator and Attribution Simulation.

Generates controlled, synthetic socket table snapshots and process trees
to simulate and verify all attribution scenarios without physical capture:
- TCP exact forward and reverse matches (IPv4 & IPv6)
- UDP local endpoint ownership & shared UDP listeners
- Windows PID reuse with distinct creation times
- Missing contemporaneous sockets and stale observations
- Multi-process Chrome trees vs background traffic
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from research.dataset_v3.attribution.correlator import ProcessSocketCorrelator
from research.dataset_v3.attribution.policy import AttributionEvidencePolicy
from research.dataset_v3.attribution.process_tracker import ProcessTracker
from research.dataset_v3.attribution.report import AttributionReportGenerator
from research.dataset_v3.attribution.schemas import (
    AttributionEvidenceRecord,
    AttributionReport,
    TransientSocketEntry,
)
from research.dataset_v3.attribution.snapshot_manager import SocketSnapshotManager

logger = logging.getLogger("research.dataset_v3.attribution.simulation")


class SyntheticSocketFixtureGenerator:
    """
    Constructs deterministic synthetic socket snapshots and process states for testing.
    """

    def __init__(self, base_timestamp: float = 1700000000.0) -> None:
        self.base_timestamp = base_timestamp

    def create_chrome_process_tree(
        self,
        root_pid: int = 1000,
        network_service_pid: int = 1004,
        renderer_pid: int = 1008,
        root_create_time: str = "2026-11-21T10:00:00.000000+00:00",
        child_create_time: str = "2026-11-21T10:00:01.000000+00:00",
    ) -> ProcessTracker:
        """Sets up a simulated multi-process Chrome hierarchy."""
        tracker = ProcessTracker(controlled_app_alias="chrome_controlled")
        tracker.register_controlled_root(
            pid=root_pid,
            create_time_utc=root_create_time,
            process_name="chrome.exe",
        )
        tracker.register_controlled_child(
            pid=network_service_pid,
            parent_pid=root_pid,
            create_time_utc=child_create_time,
            process_name="chrome.exe",
        )
        tracker.register_controlled_child(
            pid=renderer_pid,
            parent_pid=root_pid,
            create_time_utc=child_create_time,
            process_name="chrome.exe",
        )
        return tracker

    def generate_tcp_snapshot(
        self,
        timestamp: float,
        local_ip: str,
        local_port: int,
        remote_ip: str,
        remote_port: int,
        pid: int,
        process_name: str = "chrome.exe",
        create_time: str = "2026-11-21T10:00:01.000000+00:00",
        state: str = "ESTABLISHED",
    ) -> List[TransientSocketEntry]:
        """Generates a snapshot containing an active TCP connection."""
        return [
            TransientSocketEntry(
                protocol="TCP",
                local_address=local_ip,
                local_port=local_port,
                remote_address=remote_ip,
                remote_port=remote_port,
                state=state,
                pid=pid,
                process_create_time_utc=create_time,
                process_name=process_name,
                timestamp_utc=timestamp,
            )
        ]

    def generate_udp_snapshot(
        self,
        timestamp: float,
        local_ip: str,
        local_port: int,
        pids: List[int],
        process_names: Optional[List[str]] = None,
        create_time: str = "2026-11-21T10:00:01.000000+00:00",
    ) -> List[TransientSocketEntry]:
        """Generates a snapshot containing UDP listeners (supporting shared ports)."""
        names = process_names or ["chrome.exe" for _ in pids]
        entries = []
        for pid, name in zip(pids, names):
            entries.append(
                TransientSocketEntry(
                    protocol="UDP",
                    local_address=local_ip,
                    local_port=local_port,
                    remote_address=None,
                    remote_port=None,
                    state=None,
                    pid=pid,
                    process_create_time_utc=create_time,
                    process_name=name,
                    timestamp_utc=timestamp,
                )
            )
        return entries


class AttributionSimulation:
    """
    Executes an end-to-end attribution simulation using synthetic socket tables.
    """

    def __init__(
        self,
        process_tracker: ProcessTracker,
        snapshot_manager: SocketSnapshotManager,
        policy: Optional[AttributionEvidencePolicy] = None,
    ) -> None:
        self.process_tracker = process_tracker
        self.snapshot_manager = snapshot_manager
        self.correlator = ProcessSocketCorrelator(
            snapshot_manager=self.snapshot_manager,
            process_tracker=self.process_tracker,
        )
        self.policy = policy or AttributionEvidencePolicy()
        self.report_generator = AttributionReportGenerator()

    def run_simulation(
        self,
        session_id: str,
        simulated_flows: List[Dict[str, Any]],
    ) -> Tuple[AttributionReport, List[Tuple[str, Optional[str], str, str]]]:
        """
        Evaluates a batch of simulated flows against the synthetic snapshots.

        Returns:
            (AttributionReport, List of (flow_id, recommended_traffic_class, label_quality, label_source))
        """
        evidence_records: List[AttributionEvidenceRecord] = []
        label_recommendations = []

        for flow in simulated_flows:
            fid = flow["flow_id"]
            proto = flow["protocol"]
            ep_a = flow["endpoint_a"]
            ep_b = flow["endpoint_b"]
            t_start = flow["first_packet_wire_ts"]
            t_end = flow["last_packet_wire_ts"]

            rec = self.correlator.correlate_flow(
                flow_id=fid,
                protocol=proto,
                endpoint_a=ep_a,
                endpoint_b=ep_b,
                first_packet_wire_ts=t_start,
                last_packet_wire_ts=t_end,
            )
            evidence_records.append(rec)

            tc, l_qual, l_src, rej = self.policy.evaluate_label_recommendation(
                evidence=rec,
                intended_traffic_class=flow.get("intended_traffic_class", "Web"),
                controlled_app_alias=self.process_tracker.controlled_app_alias,
            )
            label_recommendations.append((fid, tc, l_qual, l_src))

        report = self.report_generator.generate_report(session_id, evidence_records)
        return report, label_recommendations
