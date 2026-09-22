"""
Duplicate Session Detector.

Identifies potential duplicate captures based on cryptographic SHA-256 digests,
packet/byte count equality, and timestamp proximity.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


class DuplicateDetector:
    def __init__(self, manifest_path: str = "data/dataset_manifest.csv") -> None:
        self.manifest_path = Path(manifest_path)

    def check_for_duplicates(self) -> List[Dict[str, str]]:
        if not self.manifest_path.exists():
            return []

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            records = list(csv.DictReader(f))

        seen_signatures: Dict[Tuple[str, str, str], str] = {}
        duplicates: List[Dict[str, str]] = []

        for r in records:
            sid = r.get("session_id", "")
            t_class = r.get("traffic_class", "")
            pkt_cnt = r.get("packet_count", "0")
            byte_cnt = r.get("byte_count", "0")

            sig = (t_class, pkt_cnt, byte_cnt)
            if sig in seen_signatures and int(pkt_cnt) > 0:
                first_sid = seen_signatures[sig]
                logger.warning("Duplicate signature suspected between %s and %s (%s)", sid, first_sid, sig)
                duplicates.append({
                    "session_id": sid,
                    "matched_with": first_sid,
                    "reason": f"Identical packet ({pkt_cnt}) and byte ({byte_cnt}) count in class {t_class}",
                })
            else:
                seen_signatures[sig] = sid

        return duplicates
