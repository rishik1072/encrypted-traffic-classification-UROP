"""
Canonical Zero-Payload Feature Registry & Metadata Governance.

Defines, organizes, and validates all zero-payload statistical traffic features
into 7 structured families:
1. Packet size
2. Timing / inter-arrival time
3. Packet counts
4. Byte counts
5. Directionality
6. Burst behavior
7. Flow duration

Strictly asserts zero-payload compliance: every registered feature derives solely
from Layer 3/4 header metadata (packet length, timestamp, direction), completely
excluding payload decryption, deep packet inspection (DPI), or application-layer data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("feature_registry")


class FeatureFamily(str, Enum):
    """Categorization of traffic features into physical/behavioral families."""
    PACKET_SIZE = "packet_size"
    TIMING = "timing"
    PACKET_COUNTS = "packet_counts"
    BYTE_COUNTS = "byte_counts"
    DIRECTIONALITY = "directionality"
    BURST = "burst"
    FLOW_DURATION = "flow_duration"


@dataclass(frozen=True)
class FeatureDefinition:
    """Canonical specification and metadata for an individual traffic feature."""
    name: str
    family: FeatureFamily
    definition: str
    units: str
    required_packet_info: List[str]
    is_zero_payload: bool
    missing_value_behavior: str
    mathematical_formula: str

    def __post_init__(self) -> None:
        if not self.is_zero_payload:
            raise ValueError(f"Feature '{self.name}' must be zero-payload compliant.")
        forbidden = {"payload", "dpi", "sni", "decrypted_text", "http_header", "certificate"}
        for req in self.required_packet_info:
            if any(f in req.lower() for f in forbidden):
                raise ValueError(
                    f"Security/Privacy violation: Feature '{self.name}' requires forbidden packet info '{req}'."
                )


class FeatureRegistry:
    """Authoritative registry and validator for all zero-payload statistical features."""

    def __init__(self) -> None:
        self._registry: Dict[str, FeatureDefinition] = {}
        self._populate_registry()
        self.verify_zero_payload()

    def _register(
        self,
        name: str,
        family: FeatureFamily,
        definition: str,
        units: str,
        required_packet_info: List[str],
        missing_value_behavior: str,
        formula: str,
    ) -> None:
        self._registry[name] = FeatureDefinition(
            name=name,
            family=family,
            definition=definition,
            units=units,
            required_packet_info=required_packet_info,
            is_zero_payload=True,
            missing_value_behavior=missing_value_behavior,
            mathematical_formula=formula,
        )

    def _populate_registry(self) -> None:
        """Populates the complete catalog of 84 rich statistical features."""

        # -------------------------------------------------------------
        # Family 1: PACKET SIZE (30 features)
        # -------------------------------------------------------------
        size_scopes = [
            ("", "Bidirectional", "All packets in flow"),
            ("fwd_", "Forward", "Packets from initiator to responder"),
            ("bwd_", "Backward", "Packets from responder to initiator"),
        ]
        moments = [
            ("mean", "Arithmetic mean of packet sizes", "\\mu = \\frac{1}{N}\\sum L_i"),
            ("std", "Standard deviation of packet sizes", "\\sigma = \\sqrt{\\frac{1}{N}\\sum (L_i - \\mu)^2}"),
            ("min", "Minimum observed packet size", "\\min(L)"),
            ("max", "Maximum observed packet size", "\\max(L)"),
            ("median", "Median (50th percentile) packet size", "P_{50}(L)"),
            ("p10", "10th percentile packet size", "P_{10}(L)"),
            ("p25", "25th percentile (first quartile) packet size", "P_{25}(L)"),
            ("p75", "75th percentile (third quartile) packet size", "P_{75}(L)"),
            ("p90", "90th percentile packet size", "P_{90}(L)"),
            ("p95", "95th percentile packet size", "P_{95}(L)"),
        ]

        for prefix, scope_name, scope_desc in size_scopes:
            for moment, desc, formula in moments:
                fname = f"{prefix}pkt_size_{moment}"
                self._register(
                    name=fname,
                    family=FeatureFamily.PACKET_SIZE,
                    definition=f"{scope_name} {desc} ({scope_desc}).",
                    units="bytes",
                    required_packet_info=["packet_length", "direction"] if prefix else ["packet_length"],
                    missing_value_behavior="impute_zero" if "bwd" in prefix else "impute_median",
                    formula=formula,
                )

        # -------------------------------------------------------------
        # Family 2: TIMING / INTER-ARRIVAL TIME (30 features)
        # -------------------------------------------------------------
        timing_scopes = [
            ("", "Bidirectional", "All consecutive packet arrivals"),
            ("fwd_", "Forward", "Consecutive forward packet arrivals"),
            ("bwd_", "Backward", "Consecutive backward packet arrivals"),
        ]
        iat_moments = [
            ("mean", "Arithmetic mean of inter-arrival times", "\\mu_{\\Delta t} = \\frac{1}{N-1}\\sum (t_i - t_{i-1})"),
            ("std", "Standard deviation of inter-arrival times", "\\sigma_{\\Delta t}"),
            ("min", "Minimum observed inter-arrival time", "\\min(\\Delta t)"),
            ("max", "Maximum observed inter-arrival time", "\\max(\\Delta t)"),
            ("median", "Median (50th percentile) inter-arrival time", "P_{50}(\\Delta t)"),
            ("p10", "10th percentile inter-arrival time", "P_{10}(\\Delta t)"),
            ("p25", "25th percentile inter-arrival time", "P_{25}(\\Delta t)"),
            ("p75", "75th percentile inter-arrival time", "P_{75}(\\Delta t)"),
            ("p90", "90th percentile inter-arrival time", "P_{90}(\\Delta t)"),
            ("p95", "95th percentile inter-arrival time", "P_{95}(\\Delta t)"),
        ]

        for prefix, scope_name, scope_desc in timing_scopes:
            for moment, desc, formula in iat_moments:
                fname = f"{prefix}iat_{moment}"
                self._register(
                    name=fname,
                    family=FeatureFamily.TIMING,
                    definition=f"{scope_name} {desc} ({scope_desc}).",
                    units="seconds",
                    required_packet_info=["timestamp", "direction"] if prefix else ["timestamp"],
                    missing_value_behavior="impute_zero",
                    formula=formula,
                )

        # -------------------------------------------------------------
        # Family 3: PACKET COUNTS (7 features)
        # -------------------------------------------------------------
        self._register(
            name="fwd_packet_count",
            family=FeatureFamily.PACKET_COUNTS,
            definition="Total number of packets transmitted in the forward direction.",
            units="count",
            required_packet_info=["direction"],
            missing_value_behavior="impute_zero",
            formula="N_{fwd} = \\sum [d_i = \\text{FWD}]",
        )
        self._register(
            name="bwd_packet_count",
            family=FeatureFamily.PACKET_COUNTS,
            definition="Total number of packets transmitted in the backward direction.",
            units="count",
            required_packet_info=["direction"],
            missing_value_behavior="impute_zero",
            formula="N_{bwd} = \\sum [d_i = \\text{BWD}]",
        )
        self._register(
            name="total_packets",
            family=FeatureFamily.PACKET_COUNTS,
            definition="Total bidirectional packet count in the flow.",
            units="count",
            required_packet_info=["direction"],
            missing_value_behavior="impute_zero",
            formula="N = N_{fwd} + N_{bwd}",
        )
        self._register(
            name="packets_per_sec",
            family=FeatureFamily.PACKET_COUNTS,
            definition="Bidirectional packet transmission rate per unit time.",
            units="packets/sec",
            required_packet_info=["timestamp"],
            missing_value_behavior="impute_zero",
            formula="R_N = \\frac{N}{\\max(D, 10^{-6})}",
        )
        self._register(
            name="fwd_packets_per_sec",
            family=FeatureFamily.PACKET_COUNTS,
            definition="Forward packet transmission rate.",
            units="packets/sec",
            required_packet_info=["timestamp", "direction"],
            missing_value_behavior="impute_zero",
            formula="R_{N,fwd} = \\frac{N_{fwd}}{\\max(D, 10^{-6})}",
        )
        self._register(
            name="bwd_packets_per_sec",
            family=FeatureFamily.PACKET_COUNTS,
            definition="Backward packet transmission rate.",
            units="packets/sec",
            required_packet_info=["timestamp", "direction"],
            missing_value_behavior="impute_zero",
            formula="R_{N,bwd} = \\frac{N_{bwd}}{\\max(D, 10^{-6})}",
        )
        self._register(
            name="flow_rate_packets",
            family=FeatureFamily.PACKET_COUNTS,
            definition="Flow packet intensity alias.",
            units="packets/sec",
            required_packet_info=["timestamp"],
            missing_value_behavior="impute_zero",
            formula="\\text{PktRate} = \\frac{N}{D}",
        )

        # -------------------------------------------------------------
        # Family 4: BYTE COUNTS (5 features)
        # -------------------------------------------------------------
        self._register(
            name="fwd_byte_count",
            family=FeatureFamily.BYTE_COUNTS,
            definition="Cumulative bytes transmitted in the forward direction.",
            units="bytes",
            required_packet_info=["packet_length", "direction"],
            missing_value_behavior="impute_zero",
            formula="B_{fwd} = \\sum_{d_i=\\text{FWD}} L_i",
        )
        self._register(
            name="bwd_byte_count",
            family=FeatureFamily.BYTE_COUNTS,
            definition="Cumulative bytes transmitted in the backward direction.",
            units="bytes",
            required_packet_info=["packet_length", "direction"],
            missing_value_behavior="impute_zero",
            formula="B_{bwd} = \\sum_{d_i=\\text{BWD}} L_i",
        )
        self._register(
            name="total_bytes",
            family=FeatureFamily.BYTE_COUNTS,
            definition="Total bidirectional byte volume transferred.",
            units="bytes",
            required_packet_info=["packet_length"],
            missing_value_behavior="impute_zero",
            formula="B = B_{fwd} + B_{bwd}",
        )
        self._register(
            name="bytes_per_sec",
            family=FeatureFamily.BYTE_COUNTS,
            definition="Bidirectional throughput in bytes per second.",
            units="bytes/sec",
            required_packet_info=["packet_length", "timestamp"],
            missing_value_behavior="impute_zero",
            formula="R_B = \\frac{B}{\\max(D, 10^{-6})}",
        )
        self._register(
            name="flow_rate_bytes",
            family=FeatureFamily.BYTE_COUNTS,
            definition="Flow volumetric transfer rate alias.",
            units="bytes/sec",
            required_packet_info=["packet_length", "timestamp"],
            missing_value_behavior="impute_zero",
            formula="\\text{ByteRate} = \\frac{B}{D}",
        )

        # -------------------------------------------------------------
        # Family 5: DIRECTIONALITY (3 features)
        # -------------------------------------------------------------
        self._register(
            name="packet_ratio",
            family=FeatureFamily.DIRECTIONALITY,
            definition="Ratio of forward packets to backward packets.",
            units="ratio",
            required_packet_info=["direction"],
            missing_value_behavior="impute_zero",
            formula="\\text{Ratio}_N = \\frac{N_{fwd}}{\\max(N_{bwd}, 1)}",
        )
        self._register(
            name="byte_ratio",
            family=FeatureFamily.DIRECTIONALITY,
            definition="Ratio of forward bytes to backward bytes.",
            units="ratio",
            required_packet_info=["packet_length", "direction"],
            missing_value_behavior="impute_zero",
            formula="\\text{Ratio}_B = \\frac{B_{fwd}}{\\max(B_{bwd}, 1)}",
        )
        self._register(
            name="direction_switch_count",
            family=FeatureFamily.DIRECTIONALITY,
            definition="Number of directional turns (transitions between forward and backward packets).",
            units="count",
            required_packet_info=["direction"],
            missing_value_behavior="impute_zero",
            formula="S_d = \\sum [d_i \\ne d_{i-1}]",
        )

        # -------------------------------------------------------------
        # Family 6: BURST BEHAVIOR (8 features)
        # -------------------------------------------------------------
        self._register(
            name="burst_count",
            family=FeatureFamily.BURST,
            definition="Total number of packet bursts separated by an IAT threshold >= 1.0s.",
            units="count",
            required_packet_info=["timestamp"],
            missing_value_behavior="impute_zero",
            formula="K_{burst} = 1 + \\sum [\\Delta t_i \\ge 1.0]",
        )
        self._register(
            name="mean_burst_packets",
            family=FeatureFamily.BURST,
            definition="Average number of packets contained per burst.",
            units="packets/burst",
            required_packet_info=["timestamp"],
            missing_value_behavior="impute_zero",
            formula="\\bar{N}_{burst} = \\frac{N}{K_{burst}}",
        )
        self._register(
            name="max_burst_packets",
            family=FeatureFamily.BURST,
            definition="Maximum number of packets observed in a single burst.",
            units="count",
            required_packet_info=["timestamp"],
            missing_value_behavior="impute_zero",
            formula="\\max(N_{burst, k})",
        )
        self._register(
            name="mean_burst_bytes",
            family=FeatureFamily.BURST,
            definition="Average byte payload volume per burst.",
            units="bytes/burst",
            required_packet_info=["packet_length", "timestamp"],
            missing_value_behavior="impute_zero",
            formula="\\bar{B}_{burst} = \\frac{B}{K_{burst}}",
        )
        self._register(
            name="max_burst_bytes",
            family=FeatureFamily.BURST,
            definition="Maximum byte payload volume observed in a single burst.",
            units="bytes",
            required_packet_info=["packet_length", "timestamp"],
            missing_value_behavior="impute_zero",
            formula="\\max(B_{burst, k})",
        )
        self._register(
            name="mean_burst_duration",
            family=FeatureFamily.BURST,
            definition="Average temporal duration of packet bursts.",
            units="seconds",
            required_packet_info=["timestamp"],
            missing_value_behavior="impute_zero",
            formula="\\bar{D}_{burst} = \\frac{1}{K}\\sum (t_{end, k} - t_{start, k})",
        )
        self._register(
            name="max_burst_duration",
            family=FeatureFamily.BURST,
            definition="Maximum duration among all observed bursts.",
            units="seconds",
            required_packet_info=["timestamp"],
            missing_value_behavior="impute_zero",
            formula="\\max(t_{end, k} - t_{start, k})",
        )
        self._register(
            name="burst_density",
            family=FeatureFamily.BURST,
            definition="Packet density during active burst periods (packets per burst second).",
            units="packets/sec",
            required_packet_info=["timestamp"],
            missing_value_behavior="impute_zero",
            formula="\\rho_{burst} = \\frac{N}{\\sum D_{burst, k}}",
        )

        # -------------------------------------------------------------
        # Family 7: FLOW DURATION (1 feature)
        # -------------------------------------------------------------
        self._register(
            name="flow_duration",
            family=FeatureFamily.FLOW_DURATION,
            definition="Total active lifetime of the bidirectional flow from first to last packet.",
            units="seconds",
            required_packet_info=["timestamp"],
            missing_value_behavior="impute_zero",
            formula="D = t_{last} - t_{first}",
        )

    def get_feature(self, name: str) -> FeatureDefinition:
        """Retrieves metadata definition for a feature name."""
        if name not in self._registry:
            raise KeyError(f"Feature '{name}' not found in registry. Total features: {len(self._registry)}")
        return self._registry[name]

    def get_features_by_family(self, family: FeatureFamily) -> List[str]:
        """Returns names of all features belonging to a specified family."""
        return [f.name for f in self._registry.values() if f.family == family]

    def list_all_features(self) -> List[str]:
        """Returns all 84 feature names in canonical order."""
        return list(self._registry.keys())

    def verify_zero_payload(self) -> bool:
        """
        Asserts that 100% of registered features are strictly zero-payload compliant.
        Raises AssertionError if any violation is detected.
        """
        for fname, feat in self._registry.items():
            assert feat.is_zero_payload is True, f"Feature {fname} is not zero-payload!"
            for req in feat.required_packet_info:
                assert req in {"packet_length", "timestamp", "direction"}, (
                    f"Forbidden input '{req}' in feature '{fname}'!"
                )
        return True

    def get_family_breakdown(self) -> Dict[str, int]:
        """Returns count of features per family."""
        counts: Dict[str, int] = {}
        for fam in FeatureFamily:
            counts[fam.value] = len(self.get_features_by_family(fam))
        return counts


# Singleton instance
canonical_feature_registry = FeatureRegistry()
