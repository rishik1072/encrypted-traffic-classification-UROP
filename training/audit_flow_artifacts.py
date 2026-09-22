"""
Flow Artifact Detection, Repeated Signature Analysis, and Data Cleaning Module.

Audits real flow datasets for:
- Discovery / control traffic (SSDP/mDNS/LLMNR/NetBIOS)
- Capture environment artifacts and keepalives
- Repeated identical multi-class feature signatures
- Tiny non-application flows

Outputs:
- results/tables/repeated_flow_signatures.csv
- results/tables/flow_exclusion_log.csv
- results/tables/real_clean_dataset_quality.csv
- data/processed/flows/flows_real_all.csv
- data/processed/flows/flows_real_clean.csv
- data/processed/features/features_real_all.csv
- data/processed/features/features_real_clean.csv
"""

from __future__ import annotations

import argparse
import csv
import logging
import math
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import yaml

# Support large packet streams in flows.csv
try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2147483647)

logger = logging.getLogger(__name__)

# Known background / local discovery / control ports
CONTROL_PORTS: Dict[str, str] = {
    "1900": "SSDP (Simple Service Discovery Protocol)",
    "5355": "LLMNR (Link-Local Multicast Name Resolution)",
    "5353": "mDNS (Multicast DNS)",
    "137": "NetBIOS Name Service",
    "0": "Non-IP / Raw Protocol Control",
}


class FlowArtifactAuditor:
    """
    Performs deterministic, rule-based auditing and separation of flow artifacts
    without corrupting or overwriting original real datasets.
    """

    def __init__(self, config_path: str | Path = "config.yaml") -> None:
        self.config_path = Path(config_path)
        self.base_dir = self.config_path.parent
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config: Dict[str, Any] = yaml.safe_load(f)

        quality_cfg = self.config.get("dataset_quality", {})
        self.min_packets = int(quality_cfg.get("minimum_packets_for_training", 3))
        self.min_bytes = int(quality_cfg.get("minimum_bytes_for_training", 128))
        self.review_enabled = bool(quality_cfg.get("artifact_review_enabled", True))

        # Default paths
        self.flows_real_path = self.base_dir / "data/processed/flows/flows_real.csv"
        self.features_real_path = self.base_dir / "data/processed/features/features_real.csv"
        self.manifest_path = self.base_dir / "data/dataset_manifest.csv"

        self.tables_dir = self.base_dir / "results/tables"
        self.tables_dir.mkdir(parents=True, exist_ok=True)

    def audit_and_clean(
        self,
        flows_input_path: Optional[str | Path] = None,
        features_input_path: Optional[str | Path] = None,
    ) -> Dict[str, Any]:
        """
        Executes full artifact detection, signature analysis, exclusion logging,
        and clean dataset generation.
        """
        flows_file = Path(flows_input_path) if flows_input_path else self.flows_real_path
        features_file = Path(features_input_path) if features_input_path else self.features_real_path

        if not flows_file.exists():
            raise FileNotFoundError(f"Flows file not found at {flows_file}")
        if not features_file.exists():
            raise FileNotFoundError(f"Features file not found at {features_file}")

        logger.info("Reading flows from %s and features from %s", flows_file, features_file)
        with open(flows_file, "r", encoding="utf-8") as f:
            flow_rows = list(csv.DictReader(f))
        with open(features_file, "r", encoding="utf-8") as f:
            feature_rows = list(csv.DictReader(f))

        # Map flow_id -> flow row & feature row
        flow_map = {r["flow_id"]: r for r in flow_rows}
        feature_map = {r["flow_id"]: r for r in feature_rows}

        # 1. Repeated Flow Signature Analysis
        repeated_signatures, sig_details = self._analyze_signatures(feature_rows)
        self._write_repeated_signatures_csv(
            self.tables_dir / "repeated_flow_signatures.csv",
            repeated_signatures
        )

        # 2. Flag Artifacts & Determine Exclusions
        exclusion_log: List[Dict[str, Any]] = []
        excluded_flow_ids: Set[str] = set()

        for feat in feature_rows:
            flow_id = feat.get("flow_id", "")
            session_id = feat.get("session_id", "")
            traffic_class = feat.get("traffic_class", "")
            dst_port = str(feat.get("dst_port", ""))
            pkt_count = int(float(feat.get("total_packet_count", 0)))
            byte_count = int(float(feat.get("total_bytes", 0)))
            duration = float(feat.get("flow_duration", 0.0))
            proto = feat.get("protocol", "UNKNOWN")

            # Signature representation
            sig_key = f"{pkt_count}pkts_{byte_count}B_{proto}_port{dst_port}"
            sig_info = sig_details.get(sig_key, {})
            class_count = sig_info.get("class_count", 1)

            # Exclusion Rules:
            # Rule 1: Multi-class repeated control / background broadcast artifact (e.g. SSDP, LLMNR, NetBIOS, mDNS)
            if dst_port in CONTROL_PORTS and class_count >= 2:
                reason = f"Multi-class background control traffic ({CONTROL_PORTS[dst_port]}) repeated across {class_count} classes"
                rule = "RULE_MULTICLASS_CONTROL_TRAFFIC"
                exclusion_log.append({
                    "flow_id": flow_id,
                    "session_id": session_id,
                    "class": traffic_class,
                    "reason": reason,
                    "rule": rule,
                    "packet_count": pkt_count,
                    "byte_count": byte_count,
                })
                excluded_flow_ids.add(flow_id)

            # Rule 2: Single-class isolated discovery / background control broadcast (e.g. mDNS, SSDP, LLMNR, NetBIOS, proto 0)
            elif dst_port in CONTROL_PORTS:
                reason = f"Local discovery/broadcast control artifact ({CONTROL_PORTS.get(dst_port, 'Port ' + dst_port)}) unassociated with targeted application session"
                rule = "RULE_DISCOVERY_CONTROL_ARTIFACT"
                exclusion_log.append({
                    "flow_id": flow_id,
                    "session_id": session_id,
                    "class": traffic_class,
                    "reason": reason,
                    "rule": rule,
                    "packet_count": pkt_count,
                    "byte_count": byte_count,
                })
                excluded_flow_ids.add(flow_id)

            # Rule 3: Configured minimum threshold failure
            elif pkt_count < self.min_packets or byte_count < self.min_bytes:
                reason = f"Flow below minimum volume threshold ({pkt_count} < {self.min_packets} pkts or {byte_count} < {self.min_bytes} B)"
                rule = "RULE_MINIMUM_VOLUME_THRESHOLD"
                exclusion_log.append({
                    "flow_id": flow_id,
                    "session_id": session_id,
                    "class": traffic_class,
                    "reason": reason,
                    "rule": rule,
                    "packet_count": pkt_count,
                    "byte_count": byte_count,
                })
                excluded_flow_ids.add(flow_id)

        # Write Exclusion Log
        self._write_exclusion_log_csv(
            self.tables_dir / "flow_exclusion_log.csv",
            exclusion_log
        )

        # 3. Create datasets: ALL and CLEAN (both flows and features)
        flows_dir = self.base_dir / "data/processed/flows"
        features_dir = self.base_dir / "data/processed/features"
        flows_dir.mkdir(parents=True, exist_ok=True)
        features_dir.mkdir(parents=True, exist_ok=True)

        flows_all_path = flows_dir / "flows_real_all.csv"
        flows_clean_path = flows_dir / "flows_real_clean.csv"
        features_all_path = features_dir / "features_real_all.csv"
        features_clean_path = features_dir / "features_real_clean.csv"

        # Save ALL
        self._write_csv(flows_all_path, flow_rows)
        self._write_csv(features_all_path, feature_rows)

        # Filter CLEAN
        clean_flows = [r for r in flow_rows if r["flow_id"] not in excluded_flow_ids]
        clean_features = [r for r in feature_rows if r["flow_id"] not in excluded_flow_ids]

        self._write_csv(flows_clean_path, clean_flows)
        self._write_csv(features_clean_path, clean_features)

        # 4. Generate Clean Dataset Quality Stats
        quality_stats = self._calculate_clean_quality(
            original_flows=flow_rows,
            clean_flows=clean_flows,
            exclusion_log=exclusion_log
        )
        self._write_quality_stats_csv(
            self.tables_dir / "real_clean_dataset_quality.csv",
            quality_stats
        )

        logger.info(
            "Audit & Clean complete:\n"
            "  Original Flows: %d\n"
            "  Excluded Flows: %d (%.2f%%)\n"
            "  Clean Flows: %d\n"
            "  Flows per class: %s",
            len(flow_rows),
            len(excluded_flow_ids),
            (len(excluded_flow_ids) / len(flow_rows) * 100) if flow_rows else 0.0,
            len(clean_flows),
            dict(Counter(r["traffic_class"] for r in clean_flows)),
        )

        return {
            "total_flows": len(flow_rows),
            "excluded_flows": len(excluded_flow_ids),
            "clean_flows": len(clean_flows),
            "clean_features": len(clean_features),
            "quality_stats": quality_stats,
        }

    def _analyze_signatures(
        self, feature_rows: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """Groups flows by structural signature and flags cross-class candidates."""
        sig_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in feature_rows:
            pkt = int(float(r.get("total_packet_count", 0)))
            b = int(float(r.get("total_bytes", 0)))
            proto = r.get("protocol", "UNKNOWN")
            port = r.get("dst_port", "")
            sig = f"{pkt}pkts_{b}B_{proto}_port{port}"
            sig_groups[sig].append(r)

        repeated_list: List[Dict[str, Any]] = []
        sig_details: Dict[str, Dict[str, Any]] = {}

        for sig, rows in sorted(sig_groups.items(), key=lambda x: len(x[1]), reverse=True):
            occ_count = len(rows)
            classes = sorted(list(set(r.get("traffic_class", "") for r in rows)))
            sessions = sorted(list(set(r.get("session_id", "") for r in rows)))
            cls_count = len(classes)
            sess_count = len(sessions)

            # Determine artifact candidate
            # Suspicious if appears across >=2 classes or has known control port with low packets
            port = str(rows[0].get("dst_port", ""))
            is_candidate = "YES" if (cls_count >= 2 or port in CONTROL_PORTS or (occ_count > 1 and int(float(rows[0].get("total_packet_count", 0))) <= 4)) else "NO"

            example_sess = ";".join(sessions[:3])
            classes_str = ";".join(classes)

            entry = {
                "signature": sig,
                "occurrence_count": occ_count,
                "class_count": cls_count,
                "session_count": sess_count,
                "classes": classes_str,
                "example_sessions": example_sess,
                "artifact_candidate": is_candidate,
            }
            repeated_list.append(entry)
            sig_details[sig] = entry

        return repeated_list, sig_details

    @staticmethod
    def _write_repeated_signatures_csv(path: Path, entries: List[Dict[str, Any]]) -> None:
        fieldnames = [
            "signature",
            "occurrence_count",
            "class_count",
            "session_count",
            "classes",
            "example_sessions",
            "artifact_candidate",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(entries)

    @staticmethod
    def _write_exclusion_log_csv(path: Path, entries: List[Dict[str, Any]]) -> None:
        fieldnames = [
            "flow_id",
            "session_id",
            "class",
            "reason",
            "rule",
            "packet_count",
            "byte_count",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(entries)

    @staticmethod
    def _write_quality_stats_csv(path: Path, stats: Dict[str, Any]) -> None:
        rows = [{"metric": k, "value": v} for k, v in stats.items()]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["metric", "value"])
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        fieldnames = list(rows[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _calculate_clean_quality(
        self,
        original_flows: List[Dict[str, Any]],
        clean_flows: List[Dict[str, Any]],
        exclusion_log: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        total_orig = len(original_flows)
        total_clean = len(clean_flows)
        total_excluded = len(exclusion_log)
        pct_excluded = (total_excluded / total_orig * 100.0) if total_orig > 0 else 0.0

        clean_sessions = set(r.get("session_id", "") for r in clean_flows if r.get("session_id"))
        clean_packets = sum(int(float(r.get("total_packets") or r.get("total_packet_count", 0))) for r in clean_flows)
        clean_bytes = sum(int(float(r.get("total_bytes", 0))) for r in clean_flows)

        class_counts = Counter(r.get("traffic_class", "") for r in clean_flows)
        class_str = "; ".join(f"{c}:{cnt}" for c, cnt in sorted(class_counts.items()))

        return {
            "sessions": len(clean_sessions),
            "flows": total_clean,
            "packets": clean_packets,
            "bytes": clean_bytes,
            "flows_per_class": class_str,
            "excluded_flows": total_excluded,
            "excluded_percentage": f"{pct_excluded:.2f}%",
        }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
    parser = argparse.ArgumentParser(description="Audit flow artifacts and create clean datasets.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--flows", default=None, help="Path to flows_real.csv")
    parser.add_argument("--features", default=None, help="Path to features_real.csv")
    args = parser.parse_args()

    auditor = FlowArtifactAuditor(config_path=args.config)
    auditor.audit_and_clean(
        flows_input_path=args.flows,
        features_input_path=args.features,
    )


if __name__ == "__main__":
    main()
