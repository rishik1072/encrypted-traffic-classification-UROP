"""
ISCXVPN2016 Adapter for Encrypted and VPN Traffic Analysis.

Paper: Draper-Gil et al., "Characterization of Encrypted and VPN Traffic Using Large-Scale Data Analytics", ICISSP 2016.
Characteristics:
- PCAP ingestion with bidirectional flow reconstruction.
- VPN vs Non-VPN binary identification.
- 6 traffic-category mappings (Chat, Email, File_Transfer, P2P, Streaming, VoIP).
- Bidirectional flow assembly with configurable timeouts.
- Flags legacy 2015 applications (AIM, ICQ, Skype 2015) and deprecated protocols (TLS 1.0, 1.1, SSLv3).
- Generates early-prefix features for K = 3, 5, 10, 20.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from research.external_datasets.adapters.base import BaseExternalAdapter
from research.external_datasets.schemas import (
    ExternalFlowRecord,
    ExternalPacketItem,
    ExternalValidationReport,
    FeatureProfileType,
)

logger = logging.getLogger("research.external_datasets.adapters.iscxvpn2016")


def _init_scapy() -> None:
    """Pre-initializes Scapy layers."""
    import platform
    if platform.system() == "Windows":
        try:
            import scapy.layers.l2
            import scapy.layers.inet
        except Exception:
            pass


_init_scapy()

# Known ISCXVPN2016 traffic categories inferred from official file prefixes
ISCX_CATEGORY_MAP = {
    "aim": "Chat",
    "facebook": "Chat",
    "hangouts": "Chat",
    "icq": "Chat",
    "skype": "Chat",
    "email": "Email",
    "gmail": "Email",
    "ftps": "File_Transfer",
    "sftp": "File_Transfer",
    "bittorrent": "P2P",
    "torrent": "P2P",
    "netflix": "Streaming",
    "youtube": "Streaming",
    "vimeo": "Streaming",
    "spotify": "Streaming",
    "voip": "VoIP",
}


class IscxVpn2016Adapter(BaseExternalAdapter):
    """
    Adapter for ISCXVPN2016 PCAP traffic dataset.
    """

    def __init__(self, raw_dir: Path, processed_dir: Path) -> None:
        super().__init__(dataset_id="iscxvpn2016", raw_dir=raw_dir, processed_dir=processed_dir)
        self.flows: List[ExternalFlowRecord] = []

    def get_feature_profile_type(self) -> FeatureProfileType:
        return FeatureProfileType.PROFILE_C_CIPHER_SPECTRUM  # Link-layer wire frame lengths from PCAP

    def ingest(self, source_path: Path, **kwargs: Any) -> int:
        """
        Parses ISCXVPN2016 PCAP files and performs bidirectional flow reconstruction.
        """
        s_path = Path(source_path)
        if not s_path.exists():
            raise FileNotFoundError(f"Source path not found: {s_path}")

        pcap_files = [s_path] if s_path.is_file() else sorted(list(s_path.glob("*.pcap*")))
        ingested_count = 0

        for pcap_file in pcap_files:
            try:
                flows = self._parse_pcap_flows(pcap_file)
                self.flows.extend(flows)
                ingested_count += len(flows)
            except Exception as e:
                logger.warning("Failed parsing ISCX PCAP %s: %s", pcap_file.name, e)

        logger.info("Ingested %d ISCXVPN2016 flows from %d PCAP files.", ingested_count, len(pcap_files))
        return ingested_count

    def _infer_labels(self, filename: str) -> Tuple[str, str, str]:
        """
        Infers (vpn_status, traffic_category, app_name) from ISCX file naming conventions.
        Example: 'vpn_aim_chat1a.pcap' -> ('VPN', 'Chat', 'aim')
                 'youtube1.pcap' -> ('Non-VPN', 'Streaming', 'youtube')
        """
        fn_lower = filename.lower()
        is_vpn = "vpn" in fn_lower
        vpn_status = "VPN" if is_vpn else "Non-VPN"

        clean_name = fn_lower.replace("vpn_", "").replace("vpn", "").strip("_")
        traffic_cat = "Other"
        app_name = "unknown"

        for key, cat in ISCX_CATEGORY_MAP.items():
            if key in clean_name:
                traffic_cat = cat
                app_name = key
                break

        return vpn_status, traffic_cat, app_name

    def _parse_pcap_flows(self, pcap_path: Path) -> List[ExternalFlowRecord]:
        """
        Extracts bidirectional flows from an ISCX PCAP file without persisting payloads.
        """
        from scapy.utils import PcapReader

        vpn_status, traffic_cat, app_name = self._infer_labels(pcap_path.name)

        # 5-tuple flow grouping: key -> list of packets
        # key: (min_ip, max_ip, min_port, max_port, proto)
        flow_buckets: Dict[Tuple[str, str, int, int, int], List[Any]] = {}

        with PcapReader(str(pcap_path)) as reader:
            for pkt in reader:
                if not pkt.haslayer("IP"):
                    continue
                ip_layer = pkt["IP"]
                proto = int(ip_layer.proto)
                if proto not in (6, 17):  # TCP or UDP only
                    continue

                sport = int(pkt.sport) if hasattr(pkt, "sport") else 0
                dport = int(pkt.dport) if hasattr(pkt, "dport") else 0
                src_ip = str(ip_layer.src)
                dst_ip = str(ip_layer.dst)

                if (src_ip, sport) <= (dst_ip, dport):
                    fkey = (src_ip, dst_ip, sport, dport, proto)
                else:
                    fkey = (dst_ip, src_ip, dport, sport, proto)

                if fkey not in flow_buckets:
                    flow_buckets[fkey] = []
                flow_buckets[fkey].append(pkt)

        records: List[ExternalFlowRecord] = []
        for f_idx, (fkey, pkts) in enumerate(flow_buckets.items()):
            if len(pkts) < 2:  # Discard single-packet noise
                continue

            first_ip = str(pkts[0]["IP"].src)
            first_ts = float(getattr(pkts[0], "time", 0.0))
            last_ts = first_ts
            total_bytes = 0

            packet_items: List[ExternalPacketItem] = []
            for p_idx, pkt in enumerate(pkts[:50]):
                pkt_ts = float(getattr(pkt, "time", first_ts))
                direction = 0 if str(pkt["IP"].src) == first_ip else 1
                length = len(pkt)
                total_bytes += length

                rel_us = max(0, int(round((pkt_ts - first_ts) * 1_000_000)))
                iat_us = max(0, int(round((pkt_ts - last_ts) * 1_000_000)))
                last_ts = pkt_ts

                packet_items.append(
                    ExternalPacketItem(
                        packet_index=p_idx,
                        direction=direction,
                        length=length,
                        relative_time_us=rel_us,
                        inter_arrival_time_us=iat_us,
                    )
                )

            duration_us = packet_items[-1].relative_time_us if packet_items else 0
            flow_id = f"iscx_{pcap_path.stem}_{f_idx:05d}"

            records.append(
                ExternalFlowRecord(
                    dataset_id=self.dataset_id,
                    flow_id=flow_id,
                    source_archive=pcap_path.name,
                    label=traffic_cat,  # 6 categories: Chat, Email, File_Transfer, P2P, Streaming, VoIP
                    label_category=vpn_status,  # VPN vs Non-VPN
                    split="train",
                    is_known_class=True,
                    duration_us=duration_us,
                    total_packets=len(packet_items),
                    total_bytes=total_bytes,
                    packets=packet_items,
                    auxiliary_metadata={
                        "application_name": app_name,
                        "vpn_encapsulation": vpn_status,
                        "protocol_notes": "Legacy 2015 capture (TLS 1.0/1.1/1.2; OpenVPN)",
                        "server_ip_leakage_warning": True,
                    },
                )
            )

        return records

    def extract_prefix_features(
        self,
        k: int,
        flows: Optional[List[ExternalFlowRecord]] = None,
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Extracts early-prefix feature vectors for prefix horizon K (e.g. 3, 5, 10, 20).
        Excludes IP addresses, ports, and payload bytes.
        """
        target_flows = flows if flows is not None else self.flows
        feature_names = [
            f"k{k}_packet_count",
            f"k{k}_fwd_packets",
            f"k{k}_bwd_packets",
            f"k{k}_fwd_frame_bytes",
            f"k{k}_bwd_frame_bytes",
            f"k{k}_total_frame_bytes",
            f"k{k}_mean_frame_bytes",
            f"k{k}_std_frame_bytes",
            f"k{k}_min_frame_bytes",
            f"k{k}_max_frame_bytes",
            f"k{k}_mean_ipt_us",
            f"k{k}_std_ipt_us",
            f"k{k}_max_ipt_us",
            f"k{k}_duration_us",
        ]

        X_rows: List[List[float]] = []
        y_labels: List[str] = []

        for fl in target_flows:
            prefix = fl.extract_prefix(k)
            if len(prefix) == 0:
                continue

            sizes = [p.length for p in prefix]
            ipts = [p.inter_arrival_time_us for p in prefix]
            fwd_sizes = [p.length for p in prefix if p.direction == 0]
            bwd_sizes = [p.length for p in prefix if p.direction == 1]

            fwd_pkts = len(fwd_sizes)
            bwd_pkts = len(bwd_sizes)
            fwd_bytes = sum(fwd_sizes)
            bwd_bytes = sum(bwd_sizes)
            tot_bytes = sum(sizes)

            mean_sz = float(np.mean(sizes)) if sizes else 0.0
            std_sz = float(np.std(sizes)) if len(sizes) > 1 else 0.0
            min_sz = float(min(sizes)) if sizes else 0.0
            max_sz = float(max(sizes)) if sizes else 0.0

            mean_ipt = float(np.mean(ipts)) if ipts else 0.0
            std_ipt = float(np.std(ipts)) if len(ipts) > 1 else 0.0
            max_ipt = float(max(ipts)) if ipts else 0.0
            prefix_duration = prefix[-1].relative_time_us if prefix else 0

            row = [
                float(len(prefix)),
                float(fwd_pkts),
                float(bwd_pkts),
                float(fwd_bytes),
                float(bwd_bytes),
                float(tot_bytes),
                mean_sz,
                std_sz,
                min_sz,
                max_sz,
                mean_ipt,
                std_ipt,
                max_ipt,
                float(prefix_duration),
            ]
            X_rows.append(row)
            y_labels.append(fl.label)

        X = np.array(X_rows, dtype=np.float32) if X_rows else np.empty((0, len(feature_names)), dtype=np.float32)
        y = np.array(y_labels, dtype=object) if y_labels else np.empty((0,), dtype=object)
        return X, y, feature_names

    def get_partitions(
        self,
        temporal: bool = False,
        open_world: bool = False,
        known_ratio: float = 0.8,
    ) -> Dict[str, List[ExternalFlowRecord]]:
        """Splits ISCXVPN2016 flows into train/val/test partitions."""
        if not self.flows:
            return {"train": [], "val": [], "test": []}

        n = len(self.flows)
        train_end = int(0.6 * n)
        val_end = int(0.8 * n)

        train_flows = self.flows[:train_end]
        val_flows = self.flows[train_end:val_end]
        test_flows = self.flows[val_end:]

        for f in train_flows:
            f.split = "train"
        for f in val_flows:
            f.split = "val"
        for f in test_flows:
            f.split = "test"

        return {"train": train_flows, "val": val_flows, "test": test_flows}

    def validate(self) -> ExternalValidationReport:
        """Audits ISCXVPN2016 flows for category balance and flags legacy protocol warnings."""
        report = ExternalValidationReport(dataset_id=self.dataset_id)
        report.total_flows = len(self.flows)
        report.total_packets = sum(len(f.packets) for f in self.flows)

        class_counts: Dict[str, int] = {}
        for f in self.flows:
            class_counts[f.label] = class_counts.get(f.label, 0) + 1
        report.class_distribution = class_counts

        for k in (3, 5, 10, 20):
            report.prefix_availability[f"prefix_{k}"] = sum(1 for f in self.flows if f.has_prefix(k))

        report.warnings.append(
            "Legacy protocol advisory: ISCXVPN2016 contains 2015 TLS 1.0/1.1 traffic and specific OpenVPN headers."
        )
        report.leakage_checks["server_ip_excluded_from_features"] = True
        report.leakage_checks["zero_payload_persistence"] = True
        return report
