"""
In-Memory Socket Snapshot Manager for Dataset V3.

Manages time-stamped socket table snapshots during physical capture or simulation.
Provides windowed queries for flow correlation using aligned monotonic timestamps,
and strictly wipes all volatile snapshots from memory upon session finalization.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import threading
import time
from typing import List, Optional, Tuple

from research.dataset_v3.attribution.ip_helper import WindowsIPHelperReader
from research.dataset_v3.attribution.schemas import TransientSocketEntry

logger = logging.getLogger("research.dataset_v3.attribution.snapshot_manager")


@dataclass
class _SnapshotRecord:
    wall_ts: float
    mono_ts: float
    entries: List[TransientSocketEntry]


class SocketSnapshotManager:
    """
    Collects, stores, and indexes volatile socket table snapshots in memory.
    """

    def __init__(
        self,
        reader: Optional[WindowsIPHelperReader] = None,
        snapshot_interval_seconds: float = 0.15,  # 150 ms default
    ) -> None:
        self.reader = reader or WindowsIPHelperReader()
        self.snapshot_interval_seconds = snapshot_interval_seconds
        # Chronological series of _SnapshotRecord
        self._snapshots: List[_SnapshotRecord] = []
        self._lock = threading.RLock()
        self._polling_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.last_polling_error: Optional[str] = None
        self.polling_exception: Optional[Exception] = None

    @property
    def is_polling_active(self) -> bool:
        with self._lock:
            return bool(self._polling_thread and self._polling_thread.is_alive() and not self._stop_event.is_set())

    def add_snapshot(
        self,
        timestamp: float,
        entries: List[TransientSocketEntry],
        monotonic_ts: Optional[float] = None,
    ) -> None:
        """Manually adds a pre-formed snapshot (used for synthetic test fixtures and simulation)."""
        now_mono = monotonic_ts if monotonic_ts is not None else timestamp
        # Tag entries with timestamps if missing
        tagged_entries: List[TransientSocketEntry] = []
        for e in entries:
            if getattr(e, "monotonic_ts", None) is None:
                tagged_entry = TransientSocketEntry(
                    protocol=e.protocol,
                    local_address=e.local_address,
                    local_port=e.local_port,
                    remote_address=e.remote_address,
                    remote_port=e.remote_port,
                    state=e.state,
                    pid=e.pid,
                    process_create_time_utc=e.process_create_time_utc,
                    process_name=e.process_name,
                    timestamp_utc=timestamp,
                    monotonic_ts=now_mono,
                )
                tagged_entries.append(tagged_entry)
            else:
                tagged_entries.append(e)

        with self._lock:
            self._snapshots.append(_SnapshotRecord(wall_ts=timestamp, mono_ts=now_mono, entries=tagged_entries))
            self._snapshots.sort(key=lambda s: s.mono_ts)

    def take_snapshot(
        self,
        timestamp: Optional[float] = None,
        monotonic_ts: Optional[float] = None,
    ) -> List[TransientSocketEntry]:
        """Takes a live snapshot via the IP Helper reader and records it with monotonic timestamps."""
        now_mono = monotonic_ts if monotonic_ts is not None else time.monotonic()
        now_wall = timestamp if timestamp is not None else time.time()

        raw_entries = self.reader.snapshot(now_wall)
        tagged_entries: List[TransientSocketEntry] = []
        for e in raw_entries:
            tagged = TransientSocketEntry(
                protocol=e.protocol,
                local_address=e.local_address,
                local_port=e.local_port,
                remote_address=e.remote_address,
                remote_port=e.remote_port,
                state=e.state,
                pid=e.pid,
                process_create_time_utc=e.process_create_time_utc,
                process_name=e.process_name,
                timestamp_utc=now_wall,
                monotonic_ts=now_mono,
            )
            tagged_entries.append(tagged)

        with self._lock:
            self._snapshots.append(_SnapshotRecord(wall_ts=now_wall, mono_ts=now_mono, entries=tagged_entries))
            self._snapshots.sort(key=lambda s: s.mono_ts)

        return tagged_entries

    def get_snapshots_in_window(
        self,
        start_ts: float,
        end_ts: float,
        margin_seconds: float = 1.0,
        use_monotonic: bool = False,
    ) -> List[Tuple[float, List[TransientSocketEntry]]]:
        """
        Retrieves all snapshots whose timestamp falls within [start_ts - margin, end_ts + margin].
        Returns list of (timestamp, entries) tuples for clean unpacking.
        """
        w_start = start_ts - margin_seconds
        w_end = end_ts + margin_seconds
        with self._lock:
            if use_monotonic:
                return [
                    (s.mono_ts, s.entries)
                    for s in self._snapshots
                    if w_start <= s.mono_ts <= w_end
                ]
            else:
                return [
                    (s.wall_ts, s.entries)
                    for s in self._snapshots
                    if w_start <= s.wall_ts <= w_end
                ]

    def total_snapshot_count(self) -> int:
        with self._lock:
            return len(self._snapshots)

    def start_polling(self) -> None:
        """Starts background periodic polling thread."""
        with self._lock:
            if self._polling_thread and self._polling_thread.is_alive():
                return
            self._stop_event.clear()
            self.last_polling_error = None
            self.polling_exception = None

            def _poll_worker():
                logger.info(
                    "Socket snapshot polling worker started (interval=%.3fs, monotonic timing)",
                    self.snapshot_interval_seconds,
                )
                while not self._stop_event.is_set():
                    try:
                        self.take_snapshot()
                    except Exception as e:
                        err_msg = f"Socket snapshot polling error: {e}"
                        logger.warning("%s", err_msg)
                        with self._lock:
                            self.last_polling_error = err_msg
                            self.polling_exception = e
                    self._stop_event.wait(self.snapshot_interval_seconds)
                logger.info("Socket snapshot polling worker stopped cleanly")

            self._polling_thread = threading.Thread(
                target=_poll_worker, name="SocketSnapshotPoller", daemon=True
            )
            self._polling_thread.start()

    def stop_polling(self, timeout_seconds: float = 2.0) -> None:
        """Stops background periodic polling deterministically."""
        with self._lock:
            self._stop_event.set()
            thread = self._polling_thread

        if thread and thread.is_alive():
            thread.join(timeout=timeout_seconds)

        with self._lock:
            self._polling_thread = None

    def clear(self) -> None:
        """Completely purges all volatile snapshots and references from memory."""
        self.stop_polling()
        with self._lock:
            self._snapshots.clear()
            self.last_polling_error = None
            self.polling_exception = None
        logger.info("Socket snapshots purged from volatile memory")
