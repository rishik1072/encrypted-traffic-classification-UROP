"""
Collection Session Manager.

Manages CollectionSession with collision-resistant session IDs and lifecycle states:
PREPARING -> WARMUP -> CAPTURING -> FINALIZING -> VALIDATED / FAILED.
"""

from __future__ import annotations

import datetime
import enum
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SessionState(enum.Enum):
    PREPARING = "PREPARING"
    WARMUP = "WARMUP"
    CAPTURING = "CAPTURING"
    FINALIZING = "FINALIZING"
    VALIDATED = "VALIDATED"
    FAILED = "FAILED"


@dataclass
class CollectionSession:
    session_id: str
    traffic_class: str
    capture_source: str = "REAL_LIVE_CAPTURE"
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    environment_id: str = "lab_env_win11"
    device_id: str = "dev_lab_01"
    dataset_id: str = "dataset_real_v1"
    notes: str = ""
    state: SessionState = SessionState.PREPARING
    packet_count: int = 0
    byte_count: int = 0
    flow_count: int = 0
    metadata_path: str = ""
    sha256: str = ""
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    is_synthetic: bool = False

    @classmethod
    def create(
        cls,
        traffic_class: str,
        seq_num: int = 1,
        capture_source: str = "REAL_LIVE_CAPTURE",
        environment_id: str = "lab_env_win11",
        device_id: str = "dev_lab_01",
        dataset_id: str = "dataset_real_v1",
        notes: str = "",
        manifest_path: str = "data/dataset_manifest.csv",
    ) -> CollectionSession:
        now = datetime.datetime.now()
        date_str = now.strftime("%Y%m%d")
        time_str = now.strftime("%H%M%S")
        slug = traffic_class.lower().replace(" ", "_")
        rand_suffix = uuid.uuid4().hex[:4]

        session_id = f"{date_str}_{time_str}_{slug}_{seq_num:03d}_{rand_suffix}"

        # Ensure collision resistance against existing manifest
        p = Path(manifest_path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
                while session_id in content:
                    rand_suffix = uuid.uuid4().hex[:4]
                    session_id = f"{date_str}_{time_str}_{slug}_{seq_num:03d}_{rand_suffix}"

        return cls(
            session_id=session_id,
            traffic_class=traffic_class,
            capture_source=capture_source,
            environment_id=environment_id,
            device_id=device_id,
            dataset_id=dataset_id,
            notes=notes,
            state=SessionState.PREPARING,
        )

    def transition_to(self, new_state: SessionState) -> None:
        logger.info("Session %s transitioned from %s to %s", self.session_id, self.state.value, new_state.value)
        self.state = new_state

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "traffic_class": self.traffic_class,
            "capture_source": self.capture_source,
            "state": self.state.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": round(self.duration, 2),
            "packet_count": self.packet_count,
            "byte_count": self.byte_count,
            "flow_count": self.flow_count,
            "environment_id": self.environment_id,
            "device_id": self.device_id,
            "dataset_id": self.dataset_id,
            "metadata_path": self.metadata_path,
            "sha256": self.sha256,
            "notes": self.notes,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "is_synthetic": self.is_synthetic,
        }
