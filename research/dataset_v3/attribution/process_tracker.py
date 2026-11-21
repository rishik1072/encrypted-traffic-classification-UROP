"""
Process Tree Tracker and PID-Reuse Disambiguation for Dataset V3.

Tracks controlled Chrome browser instances and their multi-process descendants
(network service, renderers, utility). Disambiguates recycled Windows process IDs
using process creation-time timestamps.
"""

from __future__ import annotations

import ctypes
import logging
import os
import platform
from typing import Dict, Optional, Set, Tuple

from research.dataset_v3.attribution.ip_helper import get_process_creation_time_and_name
from research.dataset_v3.attribution.schemas import TransientProcessIdentity

logger = logging.getLogger("research.dataset_v3.attribution.process_tracker")

_is_windows = platform.system() == "Windows"


class ProcessTracker:
    """
    Maintains the known tree of controlled processes and maps PIDs to privacy-safe aliases.
    """

    def __init__(self, controlled_app_alias: str = "chrome_controlled") -> None:
        self.controlled_app_alias = controlled_app_alias
        # Controlled identities: (pid, create_time_utc) -> TransientProcessIdentity
        self._controlled_identities: Dict[Tuple[int, str], TransientProcessIdentity] = {}
        # Set of controlled PIDs (for fast preliminary lookup, verified with create_time)
        self._controlled_pids: Set[int] = set()
        # Controlled root PID
        self.root_pid: Optional[int] = None
        self.root_create_time_utc: Optional[str] = None

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
        self._controlled_pids.add(pid)
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
        self._controlled_pids.add(pid)
        return identity

    def refresh_descendants(self) -> int:
        """
        Scans running processes on Windows to discover newly spawned child processes
        descending from any known controlled process.
        Returns the number of new descendants discovered.
        """
        if not _is_windows or not self._controlled_pids:
            return 0

        discovered_count = 0
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

            parent_map: Dict[int, Tuple[int, str]] = {}
            if kernel32.Process32FirstW(h_snap, ctypes.byref(pe)):
                while True:
                    pid = pe.th32ProcessID
                    ppid = pe.th32ParentProcessID
                    exe = pe.szExeFile
                    parent_map[pid] = (ppid, exe)
                    if not kernel32.Process32NextW(h_snap, ctypes.byref(pe)):
                        break

            kernel32.CloseHandle(h_snap)

            # Discover descendants breadth-first
            controlled_set = set(self._controlled_pids)
            changed = True
            while changed:
                changed = False
                for pid, (ppid, exe) in parent_map.items():
                    if ppid in controlled_set and pid not in controlled_set:
                        # Check process creation time
                        ctime, pname = get_process_creation_time_and_name(pid)
                        if ctime:
                            # Verify child was created after or at root creation
                            if self.root_create_time_utc and ctime < self.root_create_time_utc:
                                continue
                            self.register_controlled_child(
                                pid=pid,
                                parent_pid=ppid,
                                create_time_utc=ctime,
                                process_name=pname or exe,
                            )
                            controlled_set.add(pid)
                            discovered_count += 1
                            changed = True

        except Exception as e:
            logger.debug("Process tree discovery note: %s", e)

        return discovered_count

    def refresh_chrome_tree(self) -> int:
        """Alias for refresh_descendants() for Chrome process hierarchy."""
        return self.refresh_descendants()

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

        # If creation time is known, perform exact key match
        if create_time_utc:
            key = (pid, create_time_utc)
            if key in self._controlled_identities:
                return self.controlled_app_alias, True
            # PID is known to controlled set, but creation time is DIFFERENT -> PID REUSE!
            if pid in self._controlled_pids:
                logger.info(
                    "Detected PID reuse: PID %d previously controlled, but creation time '%s' does not match",
                    pid,
                    create_time_utc,
                )
                return "system_background", False

        # If creation time is unknown but PID is in controlled set
        if pid in self._controlled_pids:
            # If process_name is provided, check if it matches expected browser executable
            if process_name and "chrome" in process_name.lower():
                return self.controlled_app_alias, True
            # Process name mismatch for controlled PID indicates PID reuse
            if process_name and "chrome" not in process_name.lower():
                return "system_background", False

        # Non-controlled process
        return "system_background", False

    def clear(self) -> None:
        """Purges all volatile tracked process identities from memory."""
        self._controlled_identities.clear()
        self._controlled_pids.clear()
        self.root_pid = None
        self.root_create_time_utc = None
        logger.debug("Process tracker identities purged from volatile memory")
