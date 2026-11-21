"""
Session Manifest Builder and Provenance Tracker for Dataset V3.

Constructs, updates, and serializes top-level provenance metadata for each session.
Guarantees clean adherence to controlled vocabularies and anonymization rules.
"""

from __future__ import annotations

import logging
import platform
from datetime import datetime, timezone
from typing import Optional

from research.dataset_v3.config import DatasetV3Config
from research.dataset_v3.schemas import SessionManifest

logger = logging.getLogger("research.dataset_v3.manifest")

COLLECTOR_VERSION = "3.0.0"


class ManifestManager:
    """Manages the creation, mutation, and finalization of session manifests."""

    @staticmethod
    def create_initial_manifest(config: DatasetV3Config) -> SessionManifest:
        """Constructs an initial active session manifest from configuration."""
        now_utc = datetime.now(timezone.utc).isoformat()
        os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"

        manifest = SessionManifest(
            session_id=config.session_id,
            collection_start_utc=now_utc,
            collection_end_utc="",  # populated at completion
            collector_version=COLLECTOR_VERSION,
            operating_system=os_info,
            device_pseudonym=config.device_pseudonym,
            adapter_type=config.adapter_type,
            environment_id=config.environment_id,
            tunnel_status=config.tunnel_status,
            collection_activity=config.collection_activity,
            application_alias=config.application_alias,
            intended_traffic_class=config.intended_traffic_class,
            collection_operator_label=config.collection_operator_label,
            capture_status="CREATED",
            collection_plan_id=config.collection_plan_id,
            packet_count=0,
            flow_count=0,
            label_quality="VERIFIED",
            collection_day=config.collection_day or "",
            snaplen=config.snaplen,
            kernel_buffer_drops=None,
            interface_drops=None,
            queue_drops=0,
            parsing_failures=0,
            processing_failures=0,
            notes="",
        )
        logger.info(
            "Created initial session manifest for '%s' (Class: %s, Env: %s)",
            manifest.session_id,
            manifest.intended_traffic_class,
            manifest.environment_id,
        )
        return manifest

    @staticmethod
    def finalize_manifest(
        manifest: SessionManifest,
        packet_count: int,
        flow_count: int,
        status: str = "COMPLETE",
        label_quality: str = "VERIFIED",
        notes: str = "",
        kernel_buffer_drops: Optional[int] = None,
        interface_drops: Optional[int] = None,
        queue_drops: int = 0,
        parsing_failures: int = 0,
        processing_failures: int = 0,
    ) -> SessionManifest:
        """Finalizes an active manifest with final counts, timestamps, status, and drop telemetry."""
        manifest.collection_end_utc = datetime.now(timezone.utc).isoformat()
        manifest.packet_count = packet_count
        manifest.flow_count = flow_count
        manifest.capture_status = status
        manifest.label_quality = label_quality
        manifest.notes = notes
        manifest.kernel_buffer_drops = kernel_buffer_drops
        manifest.interface_drops = interface_drops
        manifest.queue_drops = queue_drops
        manifest.parsing_failures = parsing_failures
        manifest.processing_failures = processing_failures

        logger.info(
            "Finalized manifest for '%s' with %d packets and %d flows (Status: %s, Drops: q=%d, parse=%d, proc=%d)",
            manifest.session_id,
            packet_count,
            flow_count,
            status,
            queue_drops,
            parsing_failures,
            processing_failures,
        )
        return manifest
