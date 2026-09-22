"""
Statistical & Metadata Feature Extractor.

Extracts traffic features solely from packet timing, packet length distributions,
flow directionality, and transport/TLS metadata. No payload decryption is performed.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from flows.flow_generator import Direction, Flow

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """
    Computes statistical and structural traffic features for a given bidirectional Flow.
    Handles missing values and single-packet flows gracefully without payload inspection.
    """

    def __init__(self, burst_threshold_iat: float = 1.0) -> None:
        self.burst_threshold_iat = burst_threshold_iat

    def extract_features(self, flow: Flow) -> Dict[str, Any]:
        """
        Extracts tabular features from flow packet records.
        """
        records = flow.packet_records
        total_packet_count = len(records)

        # Baseline fallback for empty flow
        if total_packet_count == 0:
            return self._empty_feature_dict(flow)

        timestamps: List[float] = [r[0] for r in records]
        lengths: List[int] = [r[1] for r in records]
        directions: List[Direction] = [r[2] for r in records]

        # Forward & Backward packet / byte counters
        fwd_lengths = [l for l, d in zip(lengths, directions) if d == Direction.FORWARD]
        bwd_lengths = [l for l, d in zip(lengths, directions) if d == Direction.BACKWARD]

        fwd_packet_count = len(fwd_lengths)
        bwd_packet_count = len(bwd_lengths)

        fwd_bytes = sum(fwd_lengths)
        bwd_bytes = sum(bwd_lengths)
        total_bytes = fwd_bytes + bwd_bytes

        # Ratios (safe division)
        fwd_bwd_packet_ratio = (
            float(fwd_packet_count) / float(bwd_packet_count) if bwd_packet_count > 0 else float(fwd_packet_count)
        )
        fwd_bwd_byte_ratio = (
            float(fwd_bytes) / float(bwd_bytes) if bwd_bytes > 0 else float(fwd_bytes)
        )

        # Packet Length Statistics (pure Python math fallback)
        avg_packet_size = float(sum(lengths)) / total_packet_count
        min_packet_size = float(min(lengths))
        max_packet_size = float(max(lengths))
        if total_packet_count > 1:
            packet_size_variance = sum((x - avg_packet_size) ** 2 for x in lengths) / total_packet_count
        else:
            packet_size_variance = 0.0

        # Inter-Arrival Time (IAT) Statistics
        if total_packet_count > 1:
            iats = [max(0.0, timestamps[i] - timestamps[i - 1]) for i in range(1, total_packet_count)]
            mean_iat = sum(iats) / len(iats)
            sorted_iats = sorted(iats)
            mid = len(sorted_iats) // 2
            median_iat = (sorted_iats[mid] if len(sorted_iats) % 2 != 0 else (sorted_iats[mid - 1] + sorted_iats[mid]) / 2.0)
            iat_std = math.sqrt(sum((x - mean_iat) ** 2 for x in iats) / len(iats))
            min_iat = float(min(iats))
            max_iat = float(max(iats))
        else:
            mean_iat = 0.0
            median_iat = 0.0
            iat_std = 0.0
            min_iat = 0.0
            max_iat = 0.0

        # Burst Statistics
        burst_count, avg_burst_bytes, avg_burst_packets = self._compute_burst_stats(
            timestamps, lengths
        )

        # Destination port heuristic
        dst_port = flow.key.port_b if flow.initiator_port == flow.key.port_a else flow.key.port_a

        # Assemble feature map
        features: Dict[str, Any] = {
            "flow_duration": flow.duration,
            "forward_packet_count": fwd_packet_count,
            "backward_packet_count": bwd_packet_count,
            "total_packet_count": total_packet_count,
            "forward_bytes": fwd_bytes,
            "backward_bytes": bwd_bytes,
            "total_bytes": total_bytes,
            "avg_packet_size": avg_packet_size,
            "min_packet_size": min_packet_size,
            "max_packet_size": max_packet_size,
            "packet_size_variance": packet_size_variance,
            "mean_iat": mean_iat,
            "median_iat": median_iat,
            "iat_std": iat_std,
            "min_iat": min_iat,
            "max_iat": max_iat,
            "fwd_bwd_packet_ratio": fwd_bwd_packet_ratio,
            "fwd_bwd_byte_ratio": fwd_bwd_byte_ratio,
            "burst_count": burst_count,
            "avg_burst_bytes": avg_burst_bytes,
            "avg_burst_packets": avg_burst_packets,
            "protocol": flow.key.protocol,
            "dst_port": dst_port,
            # TLS metadata when present
            "tls_version": flow.tls_version if flow.tls_version is not None else "UNKNOWN",
            "tls_cipher_suites_count": flow.tls_cipher_suites_count if flow.tls_cipher_suites_count is not None else 0,
            "tls_extensions_count": flow.tls_extensions_count if flow.tls_extensions_count is not None else 0,
            "tls_sni_present": 1 if flow.tls_sni else 0,
        }

        return features

    def _compute_burst_stats(
        self, timestamps: List[float], lengths: List[int]
    ) -> Tuple[int, float, float]:
        """Calculates burst count, average bytes per burst, and average packets per burst."""
        if not timestamps:
            return 0, 0.0, 0.0

        bursts_packets: List[int] = []
        bursts_bytes: List[int] = []

        cur_burst_packets = 1
        cur_burst_bytes = lengths[0]

        for i in range(1, len(timestamps)):
            iat = timestamps[i] - timestamps[i - 1]
            if iat < self.burst_threshold_iat:
                cur_burst_packets += 1
                cur_burst_bytes += lengths[i]
            else:
                bursts_packets.append(cur_burst_packets)
                bursts_bytes.append(cur_burst_bytes)
                cur_burst_packets = 1
                cur_burst_bytes = lengths[i]

        bursts_packets.append(cur_burst_packets)
        bursts_bytes.append(cur_burst_bytes)

        burst_count = len(bursts_packets)
        avg_burst_bytes = float(sum(bursts_bytes) / burst_count) if burst_count > 0 else 0.0
        avg_burst_packets = float(sum(bursts_packets) / burst_count) if burst_count > 0 else 0.0

        return burst_count, avg_burst_bytes, avg_burst_packets

    def _empty_feature_dict(self, flow: Flow) -> Dict[str, Any]:
        """Safe default dictionary for flows with no packet records."""
        return {
            "flow_duration": 0.0,
            "forward_packet_count": 0,
            "backward_packet_count": 0,
            "total_packet_count": 0,
            "forward_bytes": 0,
            "backward_bytes": 0,
            "total_bytes": 0,
            "avg_packet_size": 0.0,
            "min_packet_size": 0.0,
            "max_packet_size": 0.0,
            "packet_size_variance": 0.0,
            "mean_iat": 0.0,
            "median_iat": 0.0,
            "iat_std": 0.0,
            "min_iat": 0.0,
            "max_iat": 0.0,
            "fwd_bwd_packet_ratio": 0.0,
            "fwd_bwd_byte_ratio": 0.0,
            "burst_count": 0,
            "avg_burst_bytes": 0.0,
            "avg_burst_packets": 0.0,
            "protocol": flow.key.protocol,
            "dst_port": flow.key.port_b,
            "tls_version": "UNKNOWN",
            "tls_cipher_suites_count": 0,
            "tls_extensions_count": 0,
            "tls_sni_present": 0,
        }
