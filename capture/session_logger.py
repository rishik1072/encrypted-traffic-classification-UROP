"""
Session Structured JSONL Logger.

Appends metadata records for each collection session to data/raw/metadata/session_log.jsonl.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SessionLogger:
    def __init__(self, log_path: str = "data/raw/metadata/session_log.jsonl") -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_session(self, session_data: Dict[str, Any]) -> None:
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(session_data) + "\n")
        logger.info("Session %s appended to %s", session_data.get("session_id"), self.log_path)
