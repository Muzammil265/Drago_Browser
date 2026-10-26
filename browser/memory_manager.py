"""Memory Management and Resource Monitoring module for Grago.

Monitors memory consumption of the main Python application and child Chromium/QtWebEngine
processes. Manages tab lifecycles and tracks idle thresholds to trigger tab hibernation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import psutil


@dataclass
class MemoryStats:
    """Snapshot of process memory usage."""

    main_mb: float
    child_mb: float
    total_mb: float
    child_count: int


@dataclass
class TabStateRecord:
    """Metadata tracking tab activity and memory status."""

    tab_id: str
    title: str
    url: str
    last_active_time: float
    is_unloaded: bool = False
    unloaded_at: Optional[float] = None


class ResourceMonitor:
    """Reads and calculates RSS memory usage of the application process tree."""

    @staticmethod
    def get_memory_usage() -> MemoryStats:
        """Measure RSS memory of the main process and all observable child processes."""
        try:
            main_proc = psutil.Process()
            main_rss = main_proc.memory_info().rss
            child_rss = 0
            child_count = 0

            # Chromium renders pages in dedicated child processes
            children = main_proc.children(recursive=True)
            for child in children:
                try:
                    child_rss += child.memory_info().rss
                    child_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

            total_rss = main_rss + child_rss
            return MemoryStats(
                main_mb=main_rss / (1024 * 1024),
                child_mb=child_rss / (1024 * 1024),
                total_mb=total_rss / (1024 * 1024),
                child_count=child_count,
            )
        except Exception:
            return MemoryStats(main_mb=0.0, child_mb=0.0, total_mb=0.0, child_count=0)

    @classmethod
    def format_summary(cls, stats: Optional[MemoryStats] = None) -> str:
        """Generate human-readable memory string for UI badges."""
        if stats is None:
            stats = cls.get_memory_usage()
        return f"{stats.total_mb:.1f} MB (App: {stats.main_mb:.1f}M · Engine: {stats.child_mb:.1f}M)"


class TabMemoryManager:
    """Tracks tab activity and decides when background tabs should hibernate."""

    def __init__(self, idle_timeout_seconds: int = 180) -> None:
        """Initialize with an idle timeout threshold in seconds (default 180s = 3 minutes)."""
        self._idle_timeout_seconds = idle_timeout_seconds
        self._tabs: Dict[str, TabStateRecord] = {}

    @property
    def idle_timeout_seconds(self) -> int:
        return self._idle_timeout_seconds

    @idle_timeout_seconds.setter
    def idle_timeout_seconds(self, value: int) -> None:
        self._idle_timeout_seconds = max(0, value)

    def register_tab(self, tab_id: str, title: str = "New Tab", url: str = "about:blank") -> None:
        """Register a new tab for lifecycle tracking."""
        self._tabs[tab_id] = TabStateRecord(
            tab_id=tab_id,
            title=title,
            url=url,
            last_active_time=time.time(),
            is_unloaded=False,
        )

    def unregister_tab(self, tab_id: str) -> None:
        """Remove tab from tracking upon closure."""
        self._tabs.pop(tab_id, None)

    def touch_tab(self, tab_id: str) -> None:
        """Mark tab as actively used by the user, resetting its idle timer."""
        if tab_id in self._tabs:
            tab = self._tabs[tab_id]
            tab.last_active_time = time.time()
            tab.is_unloaded = False
            tab.unloaded_at = None

    def update_tab(self, tab_id: str, title: Optional[str] = None, url: Optional[str] = None) -> None:
        """Update tab metadata when title or URL changes."""
        if tab_id in self._tabs:
            if title is not None:
                self._tabs[tab_id].title = title
            if url is not None:
                self._tabs[tab_id].url = url

    def mark_unloaded(self, tab_id: str) -> None:
        """Mark tab as hibernated/unloaded."""
        if tab_id in self._tabs:
            self._tabs[tab_id].is_unloaded = True
            self._tabs[tab_id].unloaded_at = time.time()

    def get_tabs_to_unload(self, active_tab_id: Optional[str]) -> List[str]:
        """Return list of tab IDs that have exceeded the idle threshold and should be unloaded."""
        if self._idle_timeout_seconds <= 0:
            return []  # Hibernation disabled

        now = time.time()
        to_unload = []
        for tab_id, tab in self._tabs.items():
            if tab_id == active_tab_id:
                # Active tab is kept alive
                tab.last_active_time = now
                continue
            if not tab.is_unloaded:
                idle_duration = now - tab.last_active_time
                if idle_duration >= self._idle_timeout_seconds:
                    to_unload.append(tab_id)
        return to_unload

    def get_inactive_background_tabs(self, active_tab_id: Optional[str]) -> List[str]:
        """Return all background tabs that are currently active (not yet sleeping)."""
        return [
            tab_id
            for tab_id, tab in self._tabs.items()
            if tab_id != active_tab_id and not tab.is_unloaded
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Return tab memory breakdown stats."""
        total = len(self._tabs)
        sleeping = sum(1 for t in self._tabs.values() if t.is_unloaded)
        active = total - sleeping
        return {
            "total": total,
            "active": active,
            "sleeping": sleeping,
            "idle_timeout_seconds": self._idle_timeout_seconds,
        }
