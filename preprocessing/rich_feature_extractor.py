"""
Rich Zero-Payload Statistical Feature Extractor (RICH_ZERO_PAYLOAD_V1).

Extracts ~65 fine-grained statistical features partitioned into 6 structured families:
A. Packet Size Statistics (Bidirectional, Forward, Backward with percentiles)
B. Inter-Arrival Time (IAT) Statistics (Bidirectional, Forward, Backward with percentiles)
C. Directional Statistics (Packet/byte counts, ratios, direction switches)
D. Rate Statistics (Packets/sec, bytes/sec, fwd/bwd rates)
E. Burst Statistics (Burst counts, sizes, durations, density)
F. Flow Statistics (Duration, total volume, aggregate throughput)

Strictly zero-payload compliant: uses only packet timing, byte length, and direction.
No DPI, decryption, or application layer payload inspection.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


def calc_percentile(sorted_vals: List[float], p: float) -> float:
    """Calculates p-th percentile from a sorted list of floats (0 <= p <= 100)."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return d0 + d1


def compute_distribution_moments(vals: List[float]) -> Dict[str, float]:
    """Computes mean, std, min, max, median, and percentiles for a numerical list."""
    if not vals:
        return {
            "mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0,
            "median": 0.0, "p10": 0.0, "p25": 0.0, "p75": 0.0, "p90": 0.0, "p95": 0.0,
        }
    n = len(vals)
    mean_val = sum(vals) / n
    var_val = sum((x - mean_val) ** 2 for x in vals) / (n - 1) if n > 1 else 0.0
    std_val = math.sqrt(max(0.0, var_val))
    sorted_v = sorted(vals)

    return {
        "mean": mean_val,
        "std": std_val,
        "min": float(sorted_v[0]),
        "max": float(sorted_v[-1]),
        "median": calc_percentile(sorted_v, 50.0),
        "p10": calc_percentile(sorted_v, 10.0),
        "p25": calc_percentile(sorted_v, 25.0),
        "p75": calc_percentile(sorted_v, 75.0),
        "p90": calc_percentile(sorted_v, 90.0),
        "p95": calc_percentile(sorted_v, 95.0),
    }


class RichFeatureExtractor:
    """
    Implements the RICH_ZERO_PAYLOAD_V1 feature extraction profile.
    """

    def __init__(self, burst_threshold_iat: float = 1.0) -> None:
        self.burst_threshold_iat = burst_threshold_iat

    def extract_rich_features(
        self,
        timestamps: List[float],
        lengths: List[int],
        directions: List[int],  # 1 = FORWARD, 2 = BACKWARD
        duration: Optional[float] = None,
    ) -> Dict[str, float]:
        """
        Extracts complete rich zero-payload feature dictionary from raw packet vectors.
        """
        n_pkts = len(lengths)
        if n_pkts == 0:
            return self._empty_rich_features()

        dur = duration if duration is not None and duration > 0 else (timestamps[-1] - timestamps[0] if n_pkts > 1 else 0.001)
        dur = max(0.0001, dur)

        # 1. Packet Size Statistics
        f_lens = [float(l) for l, d in zip(lengths, directions) if d == 1]
        b_lens = [float(l) for l, d in zip(lengths, directions) if d == 2]
        all_lens = [float(l) for l in lengths]

        bidi_sz = compute_distribution_moments(all_lens)
        fwd_sz = compute_distribution_moments(f_lens)
        bwd_sz = compute_distribution_moments(b_lens)

        # 2. Inter-Arrival Time (IAT) Statistics
        bidi_iats = [max(0.0, timestamps[i] - timestamps[i - 1]) for i in range(1, n_pkts)] if n_pkts > 1 else []
        fwd_times = [t for t, d in zip(timestamps, directions) if d == 1]
        bwd_times = [t for t, d in zip(timestamps, directions) if d == 2]
        fwd_iats = [max(0.0, fwd_times[i] - fwd_times[i - 1]) for i in range(1, len(fwd_times))] if len(fwd_times) > 1 else []
        bwd_iats = [max(0.0, bwd_times[i] - bwd_times[i - 1]) for i in range(1, len(bwd_times))] if len(bwd_times) > 1 else []

        bidi_iat_m = compute_distribution_moments(bidi_iats)
        fwd_iat_m = compute_distribution_moments(fwd_iats)
        bwd_iat_m = compute_distribution_moments(bwd_iats)

        # 3. Directional Statistics
        fwd_cnt = len(f_lens)
        bwd_cnt = len(b_lens)
        fwd_bytes = sum(f_lens)
        bwd_bytes = sum(b_lens)
        tot_bytes = fwd_bytes + bwd_bytes

        pkt_ratio = float(fwd_cnt) / float(bwd_cnt) if bwd_cnt > 0 else float(fwd_cnt)
        byte_ratio = float(fwd_bytes) / float(bwd_bytes) if bwd_bytes > 0 else float(fwd_bytes)

        # Direction switches
        switches = 0
        for i in range(1, n_pkts):
            if directions[i] != directions[i - 1]:
                switches += 1

        # 4. Rate Statistics
        pkts_per_sec = float(n_pkts) / dur
        bytes_per_sec = float(tot_bytes) / dur
        fwd_pkts_per_sec = float(fwd_cnt) / dur
        bwd_pkts_per_sec = float(bwd_cnt) / dur

        # 5. Burst Statistics
        bursts = self._calculate_bursts(timestamps, lengths)
        burst_cnt = len(bursts)
        if burst_cnt > 0:
            b_pkts = [float(b["packets"]) for b in bursts]
            b_bytes = [float(b["bytes"]) for b in bursts]
            b_durs = [float(b["duration"]) for b in bursts]
            mean_b_pkts = sum(b_pkts) / burst_cnt
            max_b_pkts = max(b_pkts)
            mean_b_bytes = sum(b_bytes) / burst_cnt
            max_b_bytes = max(b_bytes)
            mean_b_dur = sum(b_durs) / burst_cnt
            max_b_dur = max(b_durs)
            burst_density = sum(b_pkts) / dur
        else:
            mean_b_pkts = float(n_pkts)
            max_b_pkts = float(n_pkts)
            mean_b_bytes = float(tot_bytes)
            max_b_bytes = float(tot_bytes)
            mean_b_dur = dur
            max_b_dur = dur
            burst_density = pkts_per_sec

        # Construct comprehensive dictionary with precise family mapping
        feats: Dict[str, float] = {
            # Family A: Packet Size (30 features)
            "pkt_size_mean": bidi_sz["mean"],
            "pkt_size_std": bidi_sz["std"],
            "pkt_size_min": bidi_sz["min"],
            "pkt_size_max": bidi_sz["max"],
            "pkt_size_median": bidi_sz["median"],
            "pkt_size_p10": bidi_sz["p10"],
            "pkt_size_p25": bidi_sz["p25"],
            "pkt_size_p75": bidi_sz["p75"],
            "pkt_size_p90": bidi_sz["p90"],
            "pkt_size_p95": bidi_sz["p95"],
            "fwd_pkt_size_mean": fwd_sz["mean"],
            "fwd_pkt_size_std": fwd_sz["std"],
            "fwd_pkt_size_min": fwd_sz["min"],
            "fwd_pkt_size_max": fwd_sz["max"],
            "fwd_pkt_size_median": fwd_sz["median"],
            "fwd_pkt_size_p10": fwd_sz["p10"],
            "fwd_pkt_size_p25": fwd_sz["p25"],
            "fwd_pkt_size_p75": fwd_sz["p75"],
            "fwd_pkt_size_p90": fwd_sz["p90"],
            "fwd_pkt_size_p95": fwd_sz["p95"],
            "bwd_pkt_size_mean": bwd_sz["mean"],
            "bwd_pkt_size_std": bwd_sz["std"],
            "bwd_pkt_size_min": bwd_sz["min"],
            "bwd_pkt_size_max": bwd_sz["max"],
            "bwd_pkt_size_median": bwd_sz["median"],
            "bwd_pkt_size_p10": bwd_sz["p10"],
            "bwd_pkt_size_p25": bwd_sz["p25"],
            "bwd_pkt_size_p75": bwd_sz["p75"],
            "bwd_pkt_size_p90": bwd_sz["p90"],
            "bwd_pkt_size_p95": bwd_sz["p95"],

            # Family B: Inter-Arrival Time (30 features)
            "iat_mean": bidi_iat_m["mean"],
            "iat_std": bidi_iat_m["std"],
            "iat_min": bidi_iat_m["min"],
            "iat_max": bidi_iat_m["max"],
            "iat_median": bidi_iat_m["median"],
            "iat_p10": bidi_iat_m["p10"],
            "iat_p25": bidi_iat_m["p25"],
            "iat_p75": bidi_iat_m["p75"],
            "iat_p90": bidi_iat_m["p90"],
            "iat_p95": bidi_iat_m["p95"],
            "fwd_iat_mean": fwd_iat_m["mean"],
            "fwd_iat_std": fwd_iat_m["std"],
            "fwd_iat_min": fwd_iat_m["min"],
            "fwd_iat_max": fwd_iat_m["max"],
            "fwd_iat_median": fwd_iat_m["median"],
            "fwd_iat_p10": fwd_iat_m["p10"],
            "fwd_iat_p25": fwd_iat_m["p25"],
            "fwd_iat_p75": fwd_iat_m["p75"],
            "fwd_iat_p90": fwd_iat_m["p90"],
            "fwd_iat_p95": fwd_iat_m["p95"],
            "bwd_iat_mean": bwd_iat_m["mean"],
            "bwd_iat_std": bwd_iat_m["std"],
            "bwd_iat_min": bwd_iat_m["min"],
            "bwd_iat_max": bwd_iat_m["max"],
            "bwd_iat_median": bwd_iat_m["median"],
            "bwd_iat_p10": bwd_iat_m["p10"],
            "bwd_iat_p25": bwd_iat_m["p25"],
            "bwd_iat_p75": bwd_iat_m["p75"],
            "bwd_iat_p90": bwd_iat_m["p90"],
            "bwd_iat_p95": bwd_iat_m["p95"],

            # Family C: Directional Statistics (7 features)
            "fwd_packet_count": float(fwd_cnt),
            "bwd_packet_count": float(bwd_cnt),
            "fwd_byte_count": float(fwd_bytes),
            "bwd_byte_count": float(bwd_bytes),
            "packet_ratio": float(pkt_ratio),
            "byte_ratio": float(byte_ratio),
            "direction_switch_count": float(switches),

            # Family D: Rate Statistics (4 features)
            "packets_per_sec": float(pkts_per_sec),
            "bytes_per_sec": float(bytes_per_sec),
            "fwd_packets_per_sec": float(fwd_pkts_per_sec),
            "bwd_packets_per_sec": float(bwd_pkts_per_sec),

            # Family E: Burst Statistics (8 features)
            "burst_count": float(burst_cnt),
            "mean_burst_packets": float(mean_b_pkts),
            "max_burst_packets": float(max_b_pkts),
            "mean_burst_bytes": float(mean_b_bytes),
            "max_burst_bytes": float(max_b_bytes),
            "mean_burst_duration": float(mean_b_dur),
            "max_burst_duration": float(max_b_dur),
            "burst_density": float(burst_density),

            # Family F: Flow Statistics (5 features)
            "flow_duration": float(dur),
            "total_packets": float(n_pkts),
            "total_bytes": float(tot_bytes),
            "flow_rate_packets": float(pkts_per_sec),
            "flow_rate_bytes": float(bytes_per_sec),
        }
        return feats

    def _calculate_bursts(self, timestamps: List[float], lengths: List[int]) -> List[Dict[str, float]]:
        bursts: List[Dict[str, float]] = []
        if not timestamps:
            return bursts

        cur_pkts = 1
        cur_bytes = lengths[0]
        cur_start = timestamps[0]
        cur_end = timestamps[0]

        for i in range(1, len(timestamps)):
            iat = max(0.0, timestamps[i] - timestamps[i - 1])
            if iat <= self.burst_threshold_iat:
                cur_pkts += 1
                cur_bytes += lengths[i]
                cur_end = timestamps[i]
            else:
                bursts.append({
                    "packets": float(cur_pkts),
                    "bytes": float(cur_bytes),
                    "duration": max(0.0001, cur_end - cur_start),
                })
                cur_pkts = 1
                cur_bytes = lengths[i]
                cur_start = timestamps[i]
                cur_end = timestamps[i]

        bursts.append({
            "packets": float(cur_pkts),
            "bytes": float(cur_bytes),
            "duration": max(0.0001, cur_end - cur_start),
        })
        return bursts

    def _empty_rich_features(self) -> Dict[str, float]:
        keys = [
            "pkt_size_mean", "pkt_size_std", "pkt_size_min", "pkt_size_max", "pkt_size_median",
            "pkt_size_p10", "pkt_size_p25", "pkt_size_p75", "pkt_size_p90", "pkt_size_p95",
            "fwd_pkt_size_mean", "fwd_pkt_size_std", "fwd_pkt_size_min", "fwd_pkt_size_max", "fwd_pkt_size_median",
            "fwd_pkt_size_p10", "fwd_pkt_size_p25", "fwd_pkt_size_p75", "fwd_pkt_size_p90", "fwd_pkt_size_p95",
            "bwd_pkt_size_mean", "bwd_pkt_size_std", "bwd_pkt_size_min", "bwd_pkt_size_max", "bwd_pkt_size_median",
            "bwd_pkt_size_p10", "bwd_pkt_size_p25", "bwd_pkt_size_p75", "bwd_pkt_size_p90", "bwd_pkt_size_p95",
            "iat_mean", "iat_std", "iat_min", "iat_max", "iat_median",
            "iat_p10", "iat_p25", "iat_p75", "iat_p90", "iat_p95",
            "fwd_iat_mean", "fwd_iat_std", "fwd_iat_min", "fwd_iat_max", "fwd_iat_median",
            "fwd_iat_p10", "fwd_iat_p25", "fwd_iat_p75", "fwd_iat_p90", "fwd_iat_p95",
            "bwd_iat_mean", "bwd_iat_std", "bwd_iat_min", "bwd_iat_max", "bwd_iat_median",
            "bwd_iat_p10", "bwd_iat_p25", "bwd_iat_p75", "bwd_iat_p90", "bwd_iat_p95",
            "fwd_packet_count", "bwd_packet_count", "fwd_byte_count", "bwd_byte_count",
            "packet_ratio", "byte_ratio", "direction_switch_count",
            "packets_per_sec", "bytes_per_sec", "fwd_packets_per_sec", "bwd_packets_per_sec",
            "burst_count", "mean_burst_packets", "max_burst_packets", "mean_burst_bytes",
            "max_burst_bytes", "mean_burst_duration", "max_burst_duration", "burst_density",
            "flow_duration", "total_packets", "total_bytes", "flow_rate_packets", "flow_rate_bytes",
        ]
        return {k: 0.0 for k in keys}


FEATURE_FAMILIES_MAP: Dict[str, str] = {
    # Packet Size
    "pkt_size_mean": "PACKET_SIZE", "pkt_size_std": "PACKET_SIZE", "pkt_size_min": "PACKET_SIZE",
    "pkt_size_max": "PACKET_SIZE", "pkt_size_median": "PACKET_SIZE", "pkt_size_p10": "PACKET_SIZE",
    "pkt_size_p25": "PACKET_SIZE", "pkt_size_p75": "PACKET_SIZE", "pkt_size_p90": "PACKET_SIZE",
    "pkt_size_p95": "PACKET_SIZE", "fwd_pkt_size_mean": "PACKET_SIZE", "fwd_pkt_size_std": "PACKET_SIZE",
    "fwd_pkt_size_min": "PACKET_SIZE", "fwd_pkt_size_max": "PACKET_SIZE", "fwd_pkt_size_median": "PACKET_SIZE",
    "fwd_pkt_size_p10": "PACKET_SIZE", "fwd_pkt_size_p25": "PACKET_SIZE", "fwd_pkt_size_p75": "PACKET_SIZE",
    "fwd_pkt_size_p90": "PACKET_SIZE", "fwd_pkt_size_p95": "PACKET_SIZE", "bwd_pkt_size_mean": "PACKET_SIZE",
    "bwd_pkt_size_std": "PACKET_SIZE", "bwd_pkt_size_min": "PACKET_SIZE", "bwd_pkt_size_max": "PACKET_SIZE",
    "bwd_pkt_size_median": "PACKET_SIZE", "bwd_pkt_size_p10": "PACKET_SIZE", "bwd_pkt_size_p25": "PACKET_SIZE",
    "bwd_pkt_size_p75": "PACKET_SIZE", "bwd_pkt_size_p90": "PACKET_SIZE", "bwd_pkt_size_p95": "PACKET_SIZE",

    # IAT
    "iat_mean": "INTER_ARRIVAL_TIME", "iat_std": "INTER_ARRIVAL_TIME", "iat_min": "INTER_ARRIVAL_TIME",
    "iat_max": "INTER_ARRIVAL_TIME", "iat_median": "INTER_ARRIVAL_TIME", "iat_p10": "INTER_ARRIVAL_TIME",
    "iat_p25": "INTER_ARRIVAL_TIME", "iat_p75": "INTER_ARRIVAL_TIME", "iat_p90": "INTER_ARRIVAL_TIME",
    "iat_p95": "INTER_ARRIVAL_TIME", "fwd_iat_mean": "INTER_ARRIVAL_TIME", "fwd_iat_std": "INTER_ARRIVAL_TIME",
    "fwd_iat_min": "INTER_ARRIVAL_TIME", "fwd_iat_max": "INTER_ARRIVAL_TIME", "fwd_iat_median": "INTER_ARRIVAL_TIME",
    "fwd_iat_p10": "INTER_ARRIVAL_TIME", "fwd_iat_p25": "INTER_ARRIVAL_TIME", "fwd_iat_p75": "INTER_ARRIVAL_TIME",
    "fwd_iat_p90": "INTER_ARRIVAL_TIME", "fwd_iat_p95": "INTER_ARRIVAL_TIME", "bwd_iat_mean": "INTER_ARRIVAL_TIME",
    "bwd_iat_std": "INTER_ARRIVAL_TIME", "bwd_iat_min": "INTER_ARRIVAL_TIME", "bwd_iat_max": "INTER_ARRIVAL_TIME",
    "bwd_iat_median": "INTER_ARRIVAL_TIME", "bwd_iat_p10": "INTER_ARRIVAL_TIME", "bwd_iat_p25": "INTER_ARRIVAL_TIME",
    "bwd_iat_p75": "INTER_ARRIVAL_TIME", "bwd_iat_p90": "INTER_ARRIVAL_TIME", "bwd_iat_p95": "INTER_ARRIVAL_TIME",

    # Directional
    "fwd_packet_count": "DIRECTIONAL", "bwd_packet_count": "DIRECTIONAL",
    "fwd_byte_count": "DIRECTIONAL", "bwd_byte_count": "DIRECTIONAL",
    "packet_ratio": "DIRECTIONAL", "byte_ratio": "DIRECTIONAL",
    "direction_switch_count": "DIRECTIONAL",

    # Rate
    "packets_per_sec": "RATE", "bytes_per_sec": "RATE",
    "fwd_packets_per_sec": "RATE", "bwd_packets_per_sec": "RATE",

    # Burst
    "burst_count": "BURST", "mean_burst_packets": "BURST", "max_burst_packets": "BURST",
    "mean_burst_bytes": "BURST", "max_burst_bytes": "BURST", "mean_burst_duration": "BURST",
    "max_burst_duration": "BURST", "burst_density": "BURST",

    # Flow
    "flow_duration": "FLOW", "total_packets": "FLOW", "total_bytes": "FLOW",
    "flow_rate_packets": "FLOW", "flow_rate_bytes": "FLOW",
}
