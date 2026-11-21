"""
Process Tree Tracker and PID-Reuse Disambiguation for Dataset V3.

Tracks controlled Chrome browser instances and their multi-process descendants
(network service, renderers, utility). Disambiguates recycled Windows process IDs
using process creation-time timestamps.
Continuously refreshes the process hierarchy during capture to detect late-spawned
renderers and prunes terminated descendants from active identity mappings.
"""

from __future__ import annotations

import ctypes
import logging
import os
import platform
import threading
import time
from typing import Dict, List, Optional, Set, Tuple

from research.dataset_v3.attribution.ip_helper import get_process_creation_time_and_name
from research.dataset_v3.attribution.schemas import TransientProcessIdentity

logger = logging.getLogger("research.dataset_v3.attribution.process_tracker")

_is_windows = platform.system() == "Windows"


class ProcessTracker:
    """
    Maintains the known tree of controlled processes and maps PIDs to privacy-safe aliases.
    Supports thread-safe dynamic discovery of newly spawned descendants and removal
    of terminated child processes from active identity mappings.
    """

    def __init__(self, controlled_app_alias: str = "chrome_controlled") -> None:
        self.controlled_app_alias = controlled_app_alias
        # Historical/session controlled identities: (pid, create_time_utc) -> TransientProcessIdentity
        self._controlled_identities: Dict[Tuple[int, str], TransientProcessIdentity] = {}
        # Active controlled PIDs (currently running)
        self._active_pids: Set[int] = set()
        # Active identity mapping: pid -> TransientProcessIdentity
        self._active_identities: Dict[int, TransientProcessIdentity] = {}
        # Backward-compatibility alias for active PIDs
        self._controlled_pids: Set[int] = self._active_pids
        # Controlled root PID
        self.root_pid: Optional[int] = None
        self.root_create_time_utc: Optional[str] = None
        self._lock = threading.RLock()

        # Background periodic refresh worker
        self._refresh_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.refresh_interval_seconds: float = 1.0

    @property
    def active_controlled_pids(self) -> Set[int]:
        """Returns a snapshot copy of currently active, running controlled PIDs."""
        with self._lock:
            return set(self._active_pids)

    @property
    def active_identities(self) -> Dict[int, TransientProcessIdentity]:
        """Returns a snapshot copy of active PID -> TransientProcessIdentity mappings."""
        with self._lock:
            return dict(self._active_identities)

    def is_pid_active(self, pid: int) -> bool:
        """Checks whether a PID is currently an active controlled process."""
        with self._lock:
            return pid in self._active_pids

    def register_controlled_root(
        self,
        pid: int,
        create_time_utc: Optional[str] = None,
        process_name: str = "chrome.exe",
    ) -> TransientProcessIdentity:
        """
        Registers the root controlled Chrome browser process.
        If create_time_utc is None, queries the operating system directly.
        """
        if create_time_utc is None:
            ctime, pname = get_process_creation_time_and_name(pid)
            create_time_utc = ctime or "UNKNOWN_CREATION_TIME"
            if pname:
                process_name = pname

        with self._lock:
            self.root_pid = pid
            self.root_create_time_utc = create_time_utc

            identity = TransientProcessIdentity(
                pid=pid,
                create_time_utc=create_time_utc,
                process_name=process_name.lower(),
                application_alias=self.controlled_app_alias,
                parent_pid=None,
                is_controlled=True,
            )

            key = (pid, create_time_utc)
            self._controlled_identities[key] = identity
            self._active_identities[pid] = identity
            self._active_pids.add(pid)

        logger.info(
            "Registered controlled root process: PID=%d, name='%s', alias='%s'",
            pid,
            process_name,
            self.controlled_app_alias,
        )
        return identity

    def register_controlled_child(
        self,
        pid: int,
        parent_pid: int,
        create_time_utc: Optional[str] = None,
        process_name: str = "chrome.exe",
    ) -> TransientProcessIdentity:
        """
        Registers a descendant process (e.g. Network Service, Renderer).
        """
        if create_time_utc is None:
            ctime, pname = get_process_creation_time_and_name(pid)
            create_time_utc = ctime or "UNKNOWN_CREATION_TIME"
            if pname:
                process_name = pname

        with self._lock:
            identity = TransientProcessIdentity(
                pid=pid,
                create_time_utc=create_time_utc,
                process_name=process_name.lower(),
                application_alias=self.controlled_app_alias,
                parent_pid=parent_pid,
                is_controlled=True,
            )

            key = (pid, create_time_utc)
            self._controlled_identities[key] = identity
            self._active_identities[pid] = identity
            self._active_pids.add(pid)

        logger.debug(
            "Registered controlled child process: PID=%d, parent_PID=%d, alias='%s'",
            pid,
            parent_pid,
            self.controlled_app_alias,
        )
        return identity

    def remove_descendant(self, pid: int) -> bool:
        """
        Removes a terminated descendant from active identity mappings.
        Root process is not removed via this method.
        """
        with self._lock:
            if pid == self.root_pid:
                return False
            removed = False
            if pid in self._active_pids:
                self._active_pids.remove(pid)
                removed = True
            if pid in self._active_identities:
                del self._active_identities[pid]
                removed = True
        if removed:
            logger.debug("Removed terminated descendant PID %d from active identity mappings", pid)
        return removed

    def refresh_descendants(
        self,
        parent_map: Optional[Dict[int, Tuple[int, str]]] = None,
    ) -> int:
        """
        Scans running processes to:
        1. Discover newly spawned child processes descending from known controlled processes.
        2. Verify process creation time >= root process creation time.
        3. Remove terminated child processes from active identity mappings.

        If parent_map is None, queries the operating system on Windows via CreateToolhelp32Snapshot.
        Returns the count of newly discovered descendants.
        """
        with self._lock:
            if not self._active_pids:
                return 0
            controlled_set = set(self._active_pids)
            root_ctime = self.root_create_time_utc
            root_pid = self.root_pid

        # If parent_map not provided, enumerate running processes on Windows
        if parent_map is None:
            if not _is_windows:
                return 0
            try:
                from ctypes import wintypes

                TH32CS_SNAPPROCESS = 0x00000002

                class PROCESSENTRY32W(ctypes.Structure):
                    _fields_ = [
                        ("dwSize", wintypes.DWORD),
                        ("cntUsage", wintypes.DWORD),
                        ("th32ProcessID", wintypes.DWORD),
                        ("th32DefaultHeapID", ctypes.c_size_t),
                        ("th32ModuleID", wintypes.DWORD),
                        ("cntThreads", wintypes.DWORD),
                        ("th32ParentProcessID", wintypes.DWORD),
                        ("pcPriClassBase", wintypes.LONG),
                        ("dwFlags", wintypes.DWORD),
                        ("szExeFile", ctypes.c_wchar * 260),
                    ]

                kernel32 = ctypes.windll.kernel32
                h_snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
                if not h_snap:
                    return 0

                pe = PROCESSENTRY32W()
                pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)

                p_map: Dict[int, Tuple[int, str]] = {}
                if kernel32.Process32FirstW(h_snap, ctypes.byref(pe)):
                    while True:
                        pid = pe.th32ProcessID
                        ppid = pe.th32ParentProcessID
                        exe = pe.szExeFile
                        p_map[pid] = (ppid, exe)
                        if not kernel32.Process32NextW(h_snap, ctypes.byref(pe)):
                            break

                kernel32.CloseHandle(h_snap)
                parent_map = p_map
            except Exception as e:
                logger.debug("Process tree enumeration error: %s", e)
                return 0

        if not parent_map:
            return 0

        discovered_count = 0

        # Step 1: Discover descendants breadth-first
        with self._lock:
            current_active = set(self._active_pids)

        changed = True
        while changed:
            changed = False
            for pid, (ppid, exe) in parent_map.items():
                if ppid in current_active and pid not in current_active:
                    # Check process creation time to reject recycled PIDs and unrelated processes
                    ctime, pname = get_process_creation_time_and_name(pid)
                    if ctime:
                        # Verify child was created after or at root creation
                        if root_ctime and ctime < root_ctime:
                            continue
                        self.register_controlled_child(
                            pid=pid,
                            parent_pid=ppid,
                            create_time_utc=ctime,
                            process_name=pname or exe,
                        )
                        current_active.add(pid)
                        discovered_count += 1
                        changed = True

        # Step 2: Remove terminated descendants from active identity mappings
        with self._lock:
            tracked_children = [p for p in self._active_pids if p != root_pid]

        for pid in tracked_children:
            if pid not in parent_map:
                # Process has terminated
                self.remove_descendant(pid)
            else:
                # Process exists in parent_map: verify creation time has not changed
                current_ctime, _ = get_process_creation_time_and_name(pid)
                with self._lock:
                    active_identity = self._active_identities.get(pid)
                if active_identity and current_ctime and current_ctime != active_identity.create_time_utc:
                    # PID was recycled by the OS for a different process! Original child terminated.
                    logger.info("Detected PID reuse during tree refresh: PID %d recycled; removing from active mappings", pid)
                    self.remove_descendant(pid)

        return discovered_count

    def refresh_chrome_tree(
        self,
        parent_map: Optional[Dict[int, Tuple[int, str]]] = None,
    ) -> int:
        """Alias for refresh_descendants() for Chrome process hierarchy."""
        return self.refresh_descendants(parent_map=parent_map)

    def start_periodic_refresh(self, interval_seconds: float = 1.0) -> None:
        """
        Starts background periodic process tree refresh thread.
        Runs independently of socket snapshot polling to avoid adding jitter to packet sampling.
        """
        with self._lock:
            if self._refresh_thread and self._refresh_thread.is_alive():
                return
            self._stop_event.clear()
            self.refresh_interval_seconds = interval_seconds

            def _refresh_worker() -> None:
                logger.info("Process tree periodic refresh worker started (interval=%.1fs)", interval_seconds)
                while not self._stop_event.is_set():
                    try:
                        self.refresh_descendants()
                    except Exception as err:
                        logger.debug("Error in periodic process refresh: %s", err)
                    self._stop_event.wait(self.refresh_interval_seconds)
                logger.info("Process tree periodic refresh worker stopped cleanly")

            self._refresh_thread = threading.Thread(
                target=_refresh_worker,
                name="ProcessTreeRefresher",
                daemon=True,
            )
            self._refresh_thread.start()

    def stop_periodic_refresh(self, timeout_seconds: float = 2.0) -> None:
        """Stops background periodic refresh thread."""
        with self._lock:
            self._stop_event.set()
            thread = self._refresh_thread

        if thread and thread.is_alive():
            thread.join(timeout=timeout_seconds)

        with self._lock:
            self._refresh_thread = None

    def is_periodic_refresh_active(self) -> bool:
        """Returns True if background periodic refresh thread is alive."""
        with self._lock:
            if self._refresh_thread is not None:
                return self._refresh_thread.is_alive()
            return False

    def resolve_application_alias(
        self,
        pid: int,
        create_time_utc: Optional[str] = None,
        process_name: Optional[str] = None,
    ) -> Tuple[Optional[str], bool]:
        """
        Resolves process identity to privacy-safe application alias and controlled status.

        Returns:
            (application_alias, is_controlled)
            - If PID matches controlled process AND creation time matches:
              ("chrome_controlled", True)
            - If PID matches controlled process BUT creation time differs:
              ("system_background", False) [Detected PID reuse by unrelated process!]
            - If unrelated process:
              ("system_background", False)
            - If unresolvable (pid <= 0):
              (None, False)
        """
        if pid <= 0:
            return None, False

        with self._lock:
            # If creation time is known, perform exact key match against registered identities
            if create_time_utc:
                key = (pid, create_time_utc)
                if key in self._controlled_identities:
                    return self.controlled_app_alias, True
                # PID is known to controlled set, but creation time is DIFFERENT -> PID REUSE!
                if pid in self._active_pids or pid in {k[0] for k in self._controlled_identities}:
                    logger.info(
                        "Detected PID reuse: PID %d previously controlled, but creation time '%s' does not match",
                        pid,
                        create_time_utc,
                    )
                    return "system_background", False

            # If creation time is unknown but PID is in active controlled set
            if pid in self._active_pids:
                if process_name and "chrome" in process_name.lower():
                    return self.controlled_app_alias, True
                if process_name and "chrome" not in process_name.lower():
                    return "system_background", False

        # Non-controlled or unrelated process
        return "system_background", False

    def clear(self) -> None:
        """Purges all volatile tracked process identities from memory and stops worker."""
        self.stop_periodic_refresh()
        with self._lock:
            self._controlled_identities.clear()
            self._active_identities.clear()
            self._active_pids.clear()
            self.root_pid = None
            self.root_create_time_utc = None
        logger.debug("Process tracker identities purged from volatile memory")
