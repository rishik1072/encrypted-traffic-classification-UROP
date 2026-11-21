"""
Dataset V3 Configuration and Environment Validation.

Encapsulates capture configuration parameters, controlled vocabulary validation,
snap-length settings, staging directories, and system prerequisite checks.
"""

from __future__ import annotations

import os
import platform
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from research.dataset_v3.schemas import (
    VALID_ADAPTER_TYPES,
    VALID_TRAFFIC_CLASSES,
    VALID_TUNNEL_STATES,
)


def get_or_create_device_pseudonym(state_dir: Optional[Path] = None) -> str:
    """
    Retrieves or generates a persistent, cryptographically random device pseudonym for this host.

    Guarantees:
    - Consistent reuse across all capture sessions executed on this physical machine.
    - NEVER derived from MAC address, serial number, hostname, public IP, or hardware IDs.
    - Stored locally in a protected configuration file.
    - Never exposed in public logs.
    """
    if state_dir is None:
        state_dir = Path.home() / ".dataset_v3"
    else:
        state_dir = Path(state_dir)

    token_file = state_dir / "device_pseudonym.token"
    if token_file.exists():
        try:
            token = token_file.read_text(encoding="utf-8").strip()
            if re.match(r"^dev_pseudonym_[a-f0-9]{8,32}$", token):
                return token
        except Exception:
            pass

    new_token = f"dev_pseudonym_{uuid.uuid4().hex[:12]}"
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        token_file.write_text(new_token, encoding="utf-8")
        try:
            token_file.chmod(0o600)
        except Exception:
            pass
    except Exception:
        pass

    return new_token


@dataclass
class DatasetV3Config:
    """
    Configuration specification for an isolated Dataset V3 physical capture session.
    """
    output_root: Path = field(default_factory=lambda: Path("data/research_v3"))
    collection_plan_id: Optional[str] = None
    session_id: Optional[str] = None
    interface: Optional[str] = None
    adapter_type: str = "Wi-Fi"
    environment_id: str = "env_phys_wifi_01"
    intended_traffic_class: str = "Web"
    application_alias: str = "browser_https"
    collection_activity: str = "Standard HTTPS browsing session"
    device_pseudonym: Optional[str] = None
    tunnel_status: str = "DIRECT"
    collection_operator_label: str = "operator_01"
    duration_seconds: float = 60.0
    flow_idle_timeout_seconds: float = 30.0
    flow_active_timeout_seconds: float = 120.0
    max_packets_per_flow: int = 10000
    pcap_filter: Optional[str] = "ip or ip6"
    promiscuous: bool = True
    snaplen: Optional[int] = None  # None for full wire capture; integer (e.g. 128) for safe header truncation
    is_synthetic: bool = False  # Strictly False for physical capture
    collection_day: Optional[str] = None
    staging_root: Optional[Path] = None
    incomplete_root: Optional[Path] = None
    device_state_dir: Optional[Path] = None

    def __post_init__(self) -> None:
        self.output_root = Path(self.output_root)
        now_dt = datetime.now(timezone.utc)

        if not self.collection_day:
            self.collection_day = now_dt.strftime("%Y-%m-%d")

        # Generate a newly generated random UUID session ID if not provided
        if not self.session_id:
            self.session_id = f"sess_{uuid.uuid4().hex}"

        # Retrieve or generate persistent random device pseudonym
        if not self.device_pseudonym:
            self.device_pseudonym = get_or_create_device_pseudonym(self.device_state_dir)

        # Staging and incomplete paths on the same volume as output_root for atomic rename
        if not self.staging_root:
            self.staging_root = self.output_root / ".staging"
        else:
            self.staging_root = Path(self.staging_root)

        if not self.incomplete_root:
            self.incomplete_root = self.output_root / ".incomplete"
        else:
            self.incomplete_root = Path(self.incomplete_root)

        self.validate()

    @property
    def final_session_dir(self) -> Path:
        """Returns the final published directory path for this session."""
        return self.output_root / self.session_id

    @property
    def staging_session_dir(self) -> Path:
        """Returns the isolated staging directory path where artifacts are accumulated."""
        return self.staging_root / self.session_id

    @property
    def incomplete_session_dir(self) -> Path:
        """Returns the quarantine directory path for incomplete or failed sessions."""
        return self.incomplete_root / self.session_id

    def validate(self) -> None:
        """Enforces all controlled vocabularies and invariant constraints."""
        if self.is_synthetic:
            raise ValueError(
                "Invariant Violation: Dataset V3 capture configuration must have is_synthetic=False."
            )

        if self.intended_traffic_class not in VALID_TRAFFIC_CLASSES:
            raise ValueError(
                f"Invalid traffic class: '{self.intended_traffic_class}'. "
                f"Must be one of {sorted(VALID_TRAFFIC_CLASSES)}"
            )

        if self.adapter_type not in VALID_ADAPTER_TYPES:
            raise ValueError(
                f"Invalid adapter type: '{self.adapter_type}'. "
                f"Must be one of {sorted(VALID_ADAPTER_TYPES)}"
            )

        if self.tunnel_status not in VALID_TUNNEL_STATES:
            raise ValueError(
                f"Invalid tunnel status: '{self.tunnel_status}'. "
                f"Must be one of {sorted(VALID_TUNNEL_STATES)}"
            )

        if self.duration_seconds <= 0.0:
            raise ValueError("Capture duration_seconds must be strictly positive.")

        if self.flow_idle_timeout_seconds <= 0.0 or self.flow_active_timeout_seconds <= 0.0:
            raise ValueError("Flow timeouts must be strictly positive.")

        if self.snaplen is not None and self.snaplen < 64:
            raise ValueError("Snaplen must be at least 64 bytes to guarantee complete IP/TCP/UDP header parsing.")

    @classmethod
    def check_system_prerequisites(cls) -> tuple[bool, str]:
        """
        Validates host environment prerequisites:
        - Windows administrator / elevated permissions check.
        - Npcap driver presence on Windows.
        """
        is_windows = platform.system() == "Windows"
        
        # 1. Admin permission check
        try:
            is_admin = False
            if is_windows:
                import ctypes
                is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            else:
                is_admin = os.geteuid() == 0
            
            if not is_admin:
                return (
                    False,
                    "Administrative / elevated privileges required for physical packet capture.",
                )
        except Exception as e:
            return False, f"Error verifying administrative privileges: {e}"

        # 2. Npcap verification on Windows
        if is_windows:
            npcap_dir = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32" / "Npcap"
            wpcap_dll = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32" / "wpcap.dll"
            if not npcap_dir.exists() and not wpcap_dll.exists():
                return False, "Npcap driver (wpcap.dll) was not detected on this system."

        return True, "Capture prerequisites satisfied."
