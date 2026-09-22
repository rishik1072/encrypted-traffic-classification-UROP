"""
Sequential Subflow Feature Extractor and Sequence Aggregator Module for Phase 7.

Extracts:
1. Window-level features: 21 compact zero-payload statistical features per window.
2. Sequence-level features: Aggregated statistics (mean, std, min, max, median, first, last, delta, slope)
   plus macro sequence descriptors (window_count, active_window_fraction, burst_fraction, idle_fraction).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

WINDOW_BASE_FEATURES = [
    "packet_count",
    "byte_count",
    "mean_packet_size",
    "std_packet_size",
    "median_packet_size",
    "p90_packet_size",
    "p95_packet_size",
    "mean_iat",
    "std_iat",
    "median_iat",
    "p90_iat",
    "forward_packets",
    "backward_packets",
    "forward_bytes",
    "backward_bytes",
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


class SequentialFeatureExtractor:
    """Extracts window-level and sequence-level subflow features."""

    def __init__(self, min_packets: int = 2, burst_threshold_sec: float = 0.05) -> None:
        self.min_packets = min_packets
        self.burst_threshold_sec = burst_threshold_sec

    def extract_window_features(
        self,
        timestamps: List[float],
        lengths: List[int],
        directions: List[int],
        window_duration: float,
    ) -> Dict[str, float]:
        """Extracts 21 zero-payload statistical features for a single window."""
        n_pkts = len(lengths)
        if n_pkts == 0:
            return {name: 0.0 for name in WINDOW_BASE_FEATURES}

        tot_bytes = sum(lengths)
        dur = max(0.0001, window_duration)

        fl_lengths = [float(x) for x in lengths]
        mean_pkt_sz = _calc_mean(fl_lengths)
        std_pkt_sz = _calc_std(fl_lengths, mean_pkt_sz)
        med_pkt_sz = _calc_quantile(fl_lengths, 0.50)
        p90_pkt_sz = _calc_quantile(fl_lengths, 0.90)
        p95_pkt_sz = _calc_quantile(fl_lengths, 0.95)

        iats: List[float] = []
        if len(timestamps) > 1:
            for i in range(1, len(timestamps)):
                iats.append(max(0.0, timestamps[i] - timestamps[i - 1]))

        mean_iat = _calc_mean(iats)
        std_iat = _calc_std(iats, mean_iat)
        med_iat = _calc_quantile(iats, 0.50)
        p90_iat = _calc_quantile(iats, 0.90)

        fwd_pkts = 0
        bwd_pkts = 0
        fwd_bytes = 0
        bwd_bytes = 0
        switches = 0
        prev_d: Optional[int] = None

        for l, d in zip(lengths, directions):
            if d == 1:
                fwd_pkts += 1
                fwd_bytes += l
            else:
                bwd_pkts += 1
                bwd_bytes += l
            if prev_d is not None and d != prev_d:
                switches += 1
            prev_d = d

        pkt_rate = float(n_pkts) / dur
        byte_rate = float(tot_bytes) / dur

        burst_counts = 0
        burst_sizes: List[int] = []
        cur_burst_sz = 1
        for i in range(1, len(timestamps)):
            if timestamps[i] - timestamps[i - 1] <= self.burst_threshold_sec:
                cur_burst_sz += 1
            else:
                burst_counts += 1
                burst_sizes.append(cur_burst_sz)
                cur_burst_sz = 1
        burst_counts += 1
        burst_sizes.append(cur_burst_sz)

        mean_burst_sz = _calc_mean([float(b) for b in burst_sizes])
        burst_rate = float(burst_counts) / dur

        return {
            "packet_count": float(n_pkts),
            "byte_count": float(tot_bytes),
            "mean_packet_size": mean_pkt_sz,
            "std_packet_size": std_pkt_sz,
            "median_packet_size": med_pkt_sz,
            "p90_packet_size": p90_pkt_sz,
            "p95_packet_size": p95_pkt_sz,
            "mean_iat": mean_iat,
            "std_iat": std_iat,
            "median_iat": med_iat,
            "p90_iat": p90_iat,
            "forward_packets": float(fwd_pkts),
            "backward_packets": float(bwd_pkts),
            "forward_bytes": float(fwd_bytes),
            "backward_bytes": float(bwd_bytes),
            "packet_rate": pkt_rate,
            "byte_rate": byte_rate,
            "burst_count": float(burst_counts),
            "mean_burst_size": mean_burst_sz,
            "burst_rate": burst_rate,
            "direction_switch_count": float(switches),
        }

    def generate_sequential_windows(
        self,
        timestamps: List[float],
        lengths: List[int],
        directions: List[int],
        window_sec: float = 2.0,
        stride_sec: float = 1.0,
        max_windows: Optional[int] = None,
    ) -> List[Tuple[float, float, Dict[str, float]]]:
        """
        Slices flow packet stream into ordered sequential subflow windows.
        Returns: list of (win_start, win_end, window_features).
        """
        if not timestamps:
            return []

        t0 = timestamps[0]
        t_max = timestamps[-1]
        flow_duration = max(0.01, t_max - t0)

        windows: List[Tuple[float, float, Dict[str, float]]] = []
        cur_start = 0.0

        while cur_start <= flow_duration:
            cur_end = cur_start + window_sec
            sub_indices = [
                i for i, t in enumerate(timestamps) if cur_start <= (t - t0) <= cur_end
            ]
            if len(sub_indices) >= self.min_packets:
                sub_t = [timestamps[i] for i in sub_indices]
                sub_l = [lengths[i] for i in sub_indices]
                sub_d = [directions[i] for i in sub_indices]
                feats = self.extract_window_features(sub_t, sub_l, sub_d, window_duration=window_sec)
                windows.append((cur_start, cur_end, feats))
            else:
                # Include sparse window with zeros/minimal stats if within active flow
                empty_feats = {name: 0.0 for name in WINDOW_BASE_FEATURES}
                windows.append((cur_start, cur_end, empty_feats))

            if max_windows and len(windows) >= max_windows:
                break

            cur_start += stride_sec

        return windows

    def aggregate_sequence_features(
        self,
        window_feature_list: List[Dict[str, float]],
    ) -> Dict[str, float]:
        """
        Aggregates a temporal sequence of window feature dictionaries into a single
        sequence-level representation (193 features).
        """
        if not window_feature_list:
            # Return empty schema
            seq_feats = {}
            for col in WINDOW_BASE_FEATURES:
                for stat in ["mean", "std", "min", "max", "median", "first", "last", "delta", "slope"]:
                    seq_feats[f"{col}_{stat}"] = 0.0
            seq_feats["window_count"] = 0.0
            seq_feats["active_window_fraction"] = 0.0
            seq_feats["burst_fraction"] = 0.0
            seq_feats["idle_fraction"] = 1.0
            return seq_feats

        n_win = len(window_feature_list)
        seq_feats: Dict[str, float] = {}

        for col in WINDOW_BASE_FEATURES:
            series = [w.get(col, 0.0) for w in window_feature_list]
            m_val = _calc_mean(series)
            s_val = _calc_std(series, m_val)
            min_val = min(series)
            max_val = max(series)
            med_val = _calc_quantile(series, 0.50)
            first_val = series[0]
            last_val = series[-1]
            delta_val = last_val - first_val
            slope_val = delta_val / float(n_win) if n_win > 1 else 0.0

            seq_feats[f"{col}_mean"] = m_val
            seq_feats[f"{col}_std"] = s_val
            seq_feats[f"{col}_min"] = min_val
            seq_feats[f"{col}_max"] = max_val
            seq_feats[f"{col}_median"] = med_val
            seq_feats[f"{col}_first"] = first_val
            seq_feats[f"{col}_last"] = last_val
            seq_feats[f"{col}_delta"] = delta_val
            seq_feats[f"{col}_slope"] = slope_val

        # Macro sequence descriptors
        active_windows = sum(1 for w in window_feature_list if w.get("packet_count", 0.0) > 0)
        burst_windows = sum(1 for w in window_feature_list if w.get("burst_count", 0.0) > 1)
        idle_windows = n_win - active_windows

        seq_feats["window_count"] = float(n_win)
        seq_feats["active_window_fraction"] = float(active_windows) / float(n_win)
        seq_feats["burst_fraction"] = float(burst_windows) / float(n_win)
        seq_feats["idle_fraction"] = float(idle_windows) / float(n_win)

        return seq_feats
