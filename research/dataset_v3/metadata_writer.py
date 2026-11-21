"""
Atomic Session Metadata Writer and Staging Manager for Dataset V3.

Implements safe, atomic multi-stage session publication:
- Accumulates session artifacts in a private staging directory: .staging/<session_id>/
- Writes all files atomically using tempfile and rename.
- Flushes buffers and validates integrity before publication.
- Publishes completed session to data/research_v3/<session_id>/ via atomic directory rename.
- Quarantines failed or interrupted sessions to .incomplete/<session_id>/.
- Places immutable SESSION_COMPLETE marker file upon successful validation.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from research.dataset_v3.schemas import (
    FlowIndexRecord,
    LabelRecord,
    PacketMetadataRecord,
    SessionManifest,
    ValidationReport,
)

logger = logging.getLogger("research.dataset_v3.metadata_writer")


class MetadataWriter:
    """
    Thread-safe atomic writer and staging publisher for Dataset V3 session files.
    """

    def __init__(
        self,
        final_dir: Path,
        staging_dir: Path,
        incomplete_dir: Path,
        session_id: str,
    ) -> None:
        self.final_dir = Path(final_dir)
        self.staging_dir = Path(staging_dir)
        self.incomplete_dir = Path(incomplete_dir)
        self.session_id = session_id
        self._lock = threading.RLock()

        # Artifact paths in staging
        self.manifest_path = self.staging_dir / "session_manifest.json"
        self.packets_path = self.staging_dir / "packet_metadata.jsonl"
        self.flows_path = self.staging_dir / "flow_index.csv"
        self.labels_path = self.staging_dir / "labels.csv"
        self.validation_path = self.staging_dir / "validation_report.json"

        self._packets_file = None
        self._is_initialized = False

    def initialize_session(self, manifest: SessionManifest) -> None:
        """Initializes staging directory and writes initial manifest atomically."""
        with self._lock:
            # Overwrite protection: check final destination
            if self.final_dir.exists():
                comp_marker = self.final_dir / "SESSION_COMPLETE"
                if comp_marker.exists():
                    raise FileExistsError(
                        f"Final session directory '{self.final_dir}' already contains a published COMPLETE session."
                    )

            # Clean and create staging directory
            if self.staging_dir.exists():
                shutil.rmtree(self.staging_dir, ignore_errors=True)
            self.staging_dir.mkdir(parents=True, exist_ok=True)

            self._write_json_atomically(self.manifest_path, manifest.to_dict())

            # Open packets file in append mode
            self._packets_file = open(self.packets_path, "a", encoding="utf-8", buffering=1)
            self._is_initialized = True
            logger.info("Initialized Dataset V3 staging session: %s", self.staging_dir)

    def write_packet(self, record: PacketMetadataRecord) -> None:
        """Appends a single packet record to packet_metadata.jsonl."""
        with self._lock:
            if not self._is_initialized or self._packets_file is None:
                raise RuntimeError("MetadataWriter is not initialized. Call initialize_session() first.")
            line = json.dumps(record.to_dict(), ensure_ascii=False) + "\n"
            self._packets_file.write(line)

    def write_flow_index(self, flow_records: List[FlowIndexRecord]) -> None:
        """Writes flow_index.csv atomically to staging."""
        with self._lock:
            fieldnames = [
                "session_id",
                "flow_id",
                "parent_flow_id",
                "first_packet_timestamp_utc",
                "last_packet_timestamp_utc",
                "packet_count",
                "duration_us",
                "direction_0_packets",
                "direction_1_packets",
                "direction_0_bytes",
                "direction_1_bytes",
                "transport_protocol",
                "termination_reason",
                "prefix_3_available",
                "prefix_5_available",
                "prefix_10_available",
                "prefix_20_available",
                "is_synthetic",
            ]
            self._write_csv_atomically(self.flows_path, fieldnames, [r.to_dict() for r in flow_records])

    def write_labels(self, label_records: List[LabelRecord]) -> None:
        """Writes labels.csv atomically to staging."""
        with self._lock:
            fieldnames = [
                "session_id",
                "flow_id",
                "traffic_class",
                "application_alias",
                "label_source",
                "label_quality",
                "annotator",
                "annotation_timestamp",
                "packet_count",
                "prefix_3_available",
                "prefix_5_available",
                "prefix_10_available",
                "prefix_20_available",
            ]
            self._write_csv_atomically(self.labels_path, fieldnames, [r.to_dict() for r in label_records])

    def flush_and_close_packets(self) -> None:
        """Flushes and closes packet stream prior to validation."""
        with self._lock:
            if self._packets_file is not None:
                self._packets_file.flush()
                self._packets_file.close()
                self._packets_file = None

    def write_manifest(self, manifest: SessionManifest) -> None:
        """Writes manifest update to staging."""
        with self._lock:
            self._write_json_atomically(self.manifest_path, manifest.to_dict())

    def write_validation_report(self, report: ValidationReport) -> None:
        """Writes validation_report.json to staging."""
        with self._lock:
            self._write_json_atomically(self.validation_path, report.to_dict())

    def compute_artifact_hashes(self) -> Dict[str, str]:
        """Computes SHA-256 cryptographic hashes of all staging session artifacts."""
        hashes = {}
        for name, path in [
            ("packet_metadata.jsonl", self.packets_path),
            ("flow_index.csv", self.flows_path),
            ("labels.csv", self.labels_path),
            ("session_manifest.json", self.manifest_path),
        ]:
            if path.exists():
                h = hashlib.sha256()
                with open(path, "rb") as f:
                    while chunk := f.read(65536):
                        h.update(chunk)
                hashes[name] = h.hexdigest()
        return hashes

    def publish_complete_session(self, manifest: SessionManifest) -> Path:
        """
        Atomically publishes the staged session to final destination.
        Computes SHA-256 integrity hashes and writes SESSION_COMPLETE marker file.
        """
        with self._lock:
            self.flush_and_close_packets()
            manifest.capture_status = "COMPLETE"

            # Compute and embed SHA-256 file hashes
            hashes = self.compute_artifact_hashes()
            manifest.file_integrity_hashes = hashes
            self._write_json_atomically(self.manifest_path, manifest.to_dict())

            # Write completion marker inside staging before rename
            marker_file = self.staging_dir / "SESSION_COMPLETE"
            with open(marker_file, "w", encoding="utf-8") as f:
                f.write(f"SESSION_COMPLETE:{self.session_id}:{manifest.collection_end_utc}\n")
                for fname, fhash in sorted(hashes.items()):
                    f.write(f"SHA256:{fname}:{fhash}\n")

            # Atomic directory rename / move to final_dir
            self.final_dir.parent.mkdir(parents=True, exist_ok=True)
            if self.final_dir.exists():
                shutil.rmtree(self.final_dir, ignore_errors=True)

            try:
                os.replace(self.staging_dir, self.final_dir)
            except Exception:
                shutil.move(str(self.staging_dir), str(self.final_dir))

            logger.info("Successfully published COMPLETE session to: %s", self.final_dir)
            return self.final_dir

    def quarantine_incomplete_session(self, manifest: SessionManifest, failure_reason: str) -> Path:
        """
        Moves an interrupted or invalid session to .incomplete/ quarantine directory.
        """
        with self._lock:
            self.flush_and_close_packets()
            manifest.capture_status = "FAILED" if "fail" in failure_reason.lower() else "INTERRUPTED"
            manifest.notes = f"{manifest.notes} | Quarantine Reason: {failure_reason}".strip(" |")
            self._write_json_atomically(self.manifest_path, manifest.to_dict())

            marker_file = self.staging_dir / "SESSION_INCOMPLETE"
            with open(marker_file, "w", encoding="utf-8") as f:
                f.write(f"SESSION_INCOMPLETE:{self.session_id}:{failure_reason}\n")

            self.incomplete_dir.parent.mkdir(parents=True, exist_ok=True)
            if self.incomplete_dir.exists():
                shutil.rmtree(self.incomplete_dir, ignore_errors=True)

            try:
                os.replace(self.staging_dir, self.incomplete_dir)
            except Exception:
                shutil.move(str(self.staging_dir), str(self.incomplete_dir))

            logger.warning("Quarantined incomplete session to: %s", self.incomplete_dir)
            return self.incomplete_dir

    @classmethod
    def quarantine_invalid_published_session(
        cls,
        published_session_dir: Path,
        incomplete_root: Path,
        failure_reason: str,
    ) -> Path:
        """
        Controlled session invalidation and safe quarantine procedure for an incorrectly
        published session:
        1. Updates session_manifest.json (capture_status='FAILED', notes='INVALID: ...').
        2. Removes SESSION_COMPLETE marker.
        3. Creates SESSION_INCOMPLETE marker with diagnostic failure reason.
        4. Moves session directory to .incomplete/<session_id>/ preserving all artifacts.
        Never deletes raw data or diagnostic evidence.
        """
        pub_dir = Path(published_session_dir)
        inc_root = Path(incomplete_root)
        session_id = pub_dir.name

        if not pub_dir.exists():
            raise FileNotFoundError(f"Published session directory does not exist: {pub_dir}")

        # 1. Update manifest
        manifest_path = pub_dir / "session_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                manifest_data["capture_status"] = "FAILED"
                curr_notes = manifest_data.get("notes", "")
                manifest_data["notes"] = f"{curr_notes} | INVALID: {failure_reason}".strip(" |")
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(manifest_data, f, indent=2)
            except Exception as e:
                logger.warning("Failed to update manifest during quarantine: %s", e)

        # 2. Remove SESSION_COMPLETE marker
        complete_marker = pub_dir / "SESSION_COMPLETE"
        if complete_marker.exists():
            try:
                complete_marker.unlink()
            except Exception as e:
                logger.warning("Failed to remove SESSION_COMPLETE: %s", e)

        # 3. Create SESSION_INCOMPLETE marker
        incomplete_marker = pub_dir / "SESSION_INCOMPLETE"
        with open(incomplete_marker, "w", encoding="utf-8") as f:
            now_iso = datetime.now(timezone.utc).isoformat()
            f.write(f"SESSION_INCOMPLETE:{session_id}:{now_iso}:{failure_reason}\n")

        # 4. Safe move to quarantine
        inc_root.mkdir(parents=True, exist_ok=True)
        dest_dir = inc_root / session_id
        if dest_dir.exists():
            shutil.rmtree(dest_dir, ignore_errors=True)

        try:
            os.replace(pub_dir, dest_dir)
        except Exception:
            shutil.move(str(pub_dir), str(dest_dir))

        logger.warning(
            "Successfully invalidated and quarantined session '%s' to '%s' (Reason: %s)",
            session_id,
            dest_dir,
            failure_reason,
        )
        return dest_dir

    def close(self) -> None:
        """Closes file descriptors."""
        self.flush_and_close_packets()

    def _write_json_atomically(self, target_path: Path, data: Dict[str, Any]) -> None:
        """Writes JSON data to a temp file, then atomic rename."""
        target_dir = target_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=target_dir, prefix="tmp_json_")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            if os.path.exists(target_path):
                os.replace(tmp_path, target_path)
            else:
                os.rename(tmp_path, target_path)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            raise

    def _write_csv_atomically(
        self, target_path: Path, fieldnames: List[str], rows: List[Dict[str, Any]]
    ) -> None:
        """Writes CSV rows to a temp file, then atomic rename."""
        target_dir = target_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=target_dir, prefix="tmp_csv_")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            if os.path.exists(target_path):
                os.replace(tmp_path, target_path)
            else:
                os.rename(tmp_path, target_path)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            raise
