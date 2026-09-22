"""
Temporal Window Feature Extractor Module for Phase 6.

Extracts a compact 20-feature zero-payload statistical representation across:
1. Whole Flow
2. Prefix Windows (first N packets)
3. Time Windows (first T seconds)
4. Sliding Overlapping Windows (window_sec / stride_sec)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

TEMPORAL_FEATURE_NAMES = [
    "packet_count",
    "byte_count",
    "mean_packet_size",
    "std_packet_size",
    "median_packet_size",
    "p95_packet_size",
    "mean_iat",
    "std_iat",
    "median_iat",
    "p95_iat",
    "forward_packet_count",
    "backward_packet_count",
    "forward_byte_count",
    "backward_byte_count",
    "packet_rate",
    "byte_rate",
    "burst_count",
    "mean_burst_size",
    "burst_rate",
    "direction_switch_count",
]


def _calc_mean(vals: List[float]) -> float:
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def _calc_std(vals: List[float], mean_val: Optional[float] = None) -> float:
    if len(vals) < 2:
        return 0.0
    m = mean_val if mean_val is not None else _calc_mean(vals)
    variance = sum((x - m) ** 2 for x in vals) / len(vals)
    return math.sqrt(variance)


def _calc_quantile(vals: List[float], q: float) -> float:
    if not vals:
        return 0.0
    sorted_vals = sorted(vals)
    n = len(sorted_vals)
    if n == 1:
        return float(sorted_vals[0])
    pos = q * (n - 1)
    low_idx = int(math.floor(pos))
    high_idx = int(math.ceil(pos))
    weight = pos - low_idx
    return (1.0 - weight) * sorted_vals[low_idx] + weight * sorted_vals[high_idx]


class TemporalWindowExtractor:
    """Extracts compact 20 zero-payload temporal features from packet sequences."""

    def __init__(self, min_packets: int = 3, burst_threshold_sec: float = 0.05) -> None:
        self.min_packets = min_packets
        self.burst_threshold_sec = burst_threshold_sec

    def extract_window_features(
        self,
        timestamps: List[float],
        lengths: List[int],
        directions: List[int],
        window_duration: Optional[float] = None,
    ) -> Dict[str, float]:
        """
        Extracts 20 zero-payload statistical features from a window slice.
        Directions: 1 for FORWARD, 2 for BACKWARD.
        """
        n_pkts = len(lengths)
        if n_pkts == 0:
            return {name: 0.0 for name in TEMPORAL_FEATURE_NAMES}

        tot_bytes = sum(lengths)
        dur = window_duration
        if dur is None or dur <= 0:
            dur = max(0.0001, timestamps[-1] - timestamps[0]) if len(timestamps) > 1 else 0.001

        # Packet sizes
        fl_lengths = [float(x) for x in lengths]
        mean_pkt_sz = _calc_mean(fl_lengths)
        std_pkt_sz = _calc_std(fl_lengths, mean_pkt_sz)
        median_pkt_sz = _calc_quantile(fl_lengths, 0.50)
        p95_pkt_sz = _calc_quantile(fl_lengths, 0.95)

        # Inter-arrival times (IAT)
        iats: List[float] = []
        if len(timestamps) > 1:
            for i in range(1, len(timestamps)):
                dt = max(0.0, timestamps[i] - timestamps[i - 1])
                iats.append(dt)

        mean_iat = _calc_mean(iats)
        std_iat = _calc_std(iats, mean_iat)
        median_iat = _calc_quantile(iats, 0.50)
        p95_iat = _calc_quantile(iats, 0.95)

        # Directional statistics
        fwd_pkts = 0
        bwd_pkts = 0
        fwd_bytes = 0
        bwd_bytes = 0
        switches = 0
        prev_dir: Optional[int] = None

        for l, d in zip(lengths, directions):
            if d == 1:
                fwd_pkts += 1
                fwd_bytes += l
            else:
                bwd_pkts += 1
                bwd_bytes += l

            if prev_dir is not None and d != prev_dir:
                switches += 1
            prev_dir = d

        # Rate statistics
        pkt_rate = float(n_pkts) / dur
        byte_rate = float(tot_bytes) / dur

        # Burst statistics (consecutive packets within burst_threshold_sec)
        burst_counts = 0
        burst_sizes: List[int] = []
        cur_burst_size = 1

        for i in range(1, len(timestamps)):
            if timestamps[i] - timestamps[i - 1] <= self.burst_threshold_sec:
                cur_burst_size += 1
            else:
                burst_counts += 1
                burst_sizes.append(cur_burst_size)
                cur_burst_size = 1
        burst_counts += 1
        burst_sizes.append(cur_burst_size)

        mean_burst_sz = _calc_mean([float(b) for b in burst_sizes])
        burst_rate = float(burst_counts) / dur

        return {
            "packet_count": float(n_pkts),
            "byte_count": float(tot_bytes),
            "mean_packet_size": mean_pkt_sz,
            "std_packet_size": std_pkt_sz,
            "median_packet_size": median_pkt_sz,
            "p95_packet_size": p95_pkt_sz,
            "mean_iat": mean_iat,
            "std_iat": std_iat,
            "median_iat": median_iat,
            "p95_iat": p95_iat,
            "forward_packet_count": float(fwd_pkts),
            "backward_packet_count": float(bwd_pkts),
            "forward_byte_count": float(fwd_bytes),
            "backward_byte_count": float(bwd_bytes),
            "packet_rate": pkt_rate,
            "byte_rate": byte_rate,
            "burst_count": float(burst_counts),
            "mean_burst_size": mean_burst_sz,
            "burst_rate": burst_rate,
            "direction_switch_count": float(switches),
        }

    def extract_prefix(
        self,
        timestamps: List[float],
        lengths: List[int],
        directions: List[int],
        prefix_size: int,
    ) -> Optional[Dict[str, float]]:
        """Extracts features from the first N packets if flow has at least N packets."""
        if len(lengths) < prefix_size or prefix_size < self.min_packets:
            return None
        sub_t = timestamps[:prefix_size]
        sub_l = lengths[:prefix_size]
        sub_d = directions[:prefix_size]
        dur = max(0.0001, sub_t[-1] - sub_t[0])
        return self.extract_window_features(sub_t, sub_l, sub_d, window_duration=dur)

    def extract_time_window(
        self,
        timestamps: List[float],
        lengths: List[int],
        directions: List[int],
        window_sec: float,
    ) -> Optional[Dict[str, float]]:
        """Extracts features from packets arriving within first window_sec of flow start."""
        if not timestamps:
            return None
        t0 = timestamps[0]
        sub_indices = [i for i, t in enumerate(timestamps) if t - t0 <= window_sec]
        if len(sub_indices) < self.min_packets:
            return None
        sub_t = [timestamps[i] for i in sub_indices]
        sub_l = [lengths[i] for i in sub_indices]
        sub_d = [directions[i] for i in sub_indices]
        return self.extract_window_features(sub_t, sub_l, sub_d, window_duration=window_sec)

    def extract_sliding_windows(
        self,
        timestamps: List[float],
        lengths: List[int],
        directions: List[int],
        window_sec: float,
        stride_sec: float,
    ) -> List[Tuple[float, float, Dict[str, float]]]:
        """
        Extracts sliding overlapping windows.
        Returns list of (win_start, win_end, features).
        """
        if not timestamps:
            return []
        t0 = timestamps[0]
        t_max = timestamps[-1]
        results: List[Tuple[float, float, Dict[str, float]]] = []

        cur_start = 0.0
        while cur_start <= t_max - t0:
            cur_end = cur_start + window_sec
            sub_indices = [
                i for i, t in enumerate(timestamps) if cur_start <= (t - t0) <= cur_end
            ]
            if len(sub_indices) >= self.min_packets:
                sub_t = [timestamps[i] for i in sub_indices]
                sub_l = [lengths[i] for i in sub_indices]
                sub_d = [directions[i] for i in sub_indices]
                feats = self.extract_window_features(sub_t, sub_l, sub_d, window_duration=window_sec)
                results.append((cur_start, cur_end, feats))
            cur_start += stride_sec

        return results
