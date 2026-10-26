"""Tests for ResourceMonitor and TabMemoryManager."""

import time
import pytest
from browser.memory_manager import MemoryStats, ResourceMonitor, TabMemoryManager


def test_resource_monitor_get_memory_usage():
    stats = ResourceMonitor.get_memory_usage()
    assert isinstance(stats, MemoryStats)
    assert stats.main_mb > 0
    assert stats.child_mb >= 0
    assert stats.total_mb >= stats.main_mb
    assert stats.child_count >= 0

    summary = ResourceMonitor.format_summary(stats)
    assert "MB" in summary
    assert "App:" in summary


def test_tab_memory_manager_registration():
    mgr = TabMemoryManager(idle_timeout_seconds=60)
    mgr.register_tab("tab_1", title="First Tab", url="https://example.com")
    mgr.register_tab("tab_2", title="Second Tab", url="https://wikipedia.org")

    stats = mgr.get_stats()
    assert stats["total"] == 2
    assert stats["active"] == 2
    assert stats["sleeping"] == 0

    mgr.unregister_tab("tab_1")
    stats_after = mgr.get_stats()
    assert stats_after["total"] == 1


def test_tab_memory_manager_touch_and_unload():
    mgr = TabMemoryManager(idle_timeout_seconds=2)
    mgr.register_tab("tab_1", title="Tab 1")
    mgr.register_tab("tab_2", title="Tab 2")

    # Both are fresh
    assert mgr.get_tabs_to_unload(active_tab_id="tab_1") == []

    # Artificially age tab_2
    mgr._tabs["tab_2"].last_active_time = time.time() - 5.0

    # tab_2 should now be flagged for unloading; active tab_1 should not
    to_unload = mgr.get_tabs_to_unload(active_tab_id="tab_1")
    assert to_unload == ["tab_2"]

    mgr.mark_unloaded("tab_2")
    stats = mgr.get_stats()
    assert stats["sleeping"] == 1
    assert stats["active"] == 1

    # Touch tab_2 -> should wake up
    mgr.touch_tab("tab_2")
    stats_woken = mgr.get_stats()
    assert stats_woken["sleeping"] == 0
    assert stats_woken["active"] == 2


def test_tab_memory_manager_timeout_disabled():
    mgr = TabMemoryManager(idle_timeout_seconds=0)  # Disabled
    mgr.register_tab("tab_1")
    mgr._tabs["tab_1"].last_active_time = time.time() - 1000

    # Should return empty list when disabled
    assert mgr.get_tabs_to_unload(active_tab_id=None) == []


def test_tab_memory_manager_background_tabs():
    mgr = TabMemoryManager(idle_timeout_seconds=60)
    mgr.register_tab("tab_1")
    mgr.register_tab("tab_2")
    mgr.register_tab("tab_3")

    mgr.mark_unloaded("tab_3")

    bg = mgr.get_inactive_background_tabs(active_tab_id="tab_1")
    assert bg == ["tab_2"]  # tab_3 is already unloaded, tab_1 is active
