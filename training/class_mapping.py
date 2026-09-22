"""
External Traffic Class Mapping and Normalization Module.

Maps arbitrary external dataset labels and granular application protocols into
the project's canonical 6-class ontology:
['Web', 'Video', 'Messaging', 'VoIP', 'File Transfer', 'Other'].
"""

from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import yaml

logger = logging.getLogger(__name__)

# Default canonical project classes
CANONICAL_CLASSES: Set[str] = {"Web", "Video", "Messaging", "VoIP", "File Transfer", "Other"}

# Standard mapping dictionary from external benchmarks
DEFAULT_EXTERNAL_MAPPINGS: Dict[str, str] = {
    # Web / Browsing
    "browsing": "Web",
    "http": "Web",
    "https": "Web",
    "web": "Web",
    "gmail": "Web",
    "weibo": "Web",
    "mail": "Web",
    "dns": "Web",
    # Streaming / Video
    "video": "Video",
    "streaming": "Video",
    "youtube": "Video",
    "netflix": "Video",
    "vimeo": "Video",
    "twitch": "Video",
    # Instant Messaging / Chat
    "chat": "Messaging",
    "messaging": "Messaging",
    "whatsapp": "Messaging",
    "telegram": "Messaging",
    "signal": "Messaging",
    "slack": "Messaging",
    # Voice / VoIP
    "voip": "VoIP",
    "voice": "VoIP",
    "skype": "VoIP",
    "facetime": "VoIP",
    "zoom": "VoIP",
    "discord_audio": "VoIP",
    # File Transfer
    "file transfer": "File Transfer",
    "file_transfer": "File Transfer",
    "ftp": "File Transfer",
    "sftp": "File Transfer",
    "ftps": "File Transfer",
    "bittorrent": "File Transfer",
    "p2p": "File Transfer",
    "smb": "File Transfer",
    "dropbox": "File Transfer",
    "gdrive": "File Transfer",
    # Other / Background / Gaming
    "other": "Other",
    "gaming": "Other",
    "worldofwarcraft": "Other",
    "ssh": "Other",
    "telnet": "Other",
    "ntp": "Other",
    "icmp": "Other",
}


def map_external_label(
    raw_label: str,
    custom_mappings: Optional[Dict[str, str]] = None,
    default_fallback: str = "Other",
) -> str:
    """Maps a raw label string to a canonical traffic class."""
    if not raw_label:
        return default_fallback

    clean_key = str(raw_label).strip().lower()
    mapping_pool = dict(DEFAULT_EXTERNAL_MAPPINGS)
    if custom_mappings:
        mapping_pool.update({k.lower(): v for k, v in custom_mappings.items()})

    mapped = mapping_pool.get(clean_key)
    if mapped is not None and mapped in CANONICAL_CLASSES:
        return mapped

    # Check for direct case-insensitive match against canonical classes
    for c in CANONICAL_CLASSES:
        if clean_key == c.lower():
            return c

    logger.debug("Label '%s' not found in mapping table. Assigning fallback: %s", raw_label, default_fallback)
    return default_fallback


def convert_manifest_classes(
    input_manifest: str | Path,
    output_manifest: str | Path,
    label_col: str = "traffic_class",
) -> List[Dict[str, Any]]:
    """Reads an external dataset manifest, normalizes class labels, and saves."""
    in_path = Path(input_manifest)
    out_path = Path(output_manifest)

    with open(in_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for r in rows:
        orig = r.get(label_col, "")
        r[label_col] = map_external_label(orig)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    logger.info("Mapped classes for %d records from %s to %s", len(rows), in_path, out_path)
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Map external dataset labels to canonical classes.")
    parser.add_argument("--input", required=True, help="Input manifest CSV")
    parser.add_argument("--output", required=True, help="Output manifest CSV")
    args = parser.parse_args()
    convert_manifest_classes(args.input, args.output)
