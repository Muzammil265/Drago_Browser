"""Unit tests for SQLite storage manager in LeanBrowse."""

import os
import tempfile
import pytest

from browser.storage import StorageManager


@pytest.fixture
def temp_storage():
    """Create a temporary storage manager with clean SQLite database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    storage = StorageManager(db_path=db_path)
    yield storage
    try:
        os.remove(db_path)
    except OSError:
        pass


def test_bookmarks_crud(temp_storage):
    """Test bookmark addition, query, check, and deletion."""
    # Add bookmark
    b_id = temp_storage.add_bookmark("Google", "https://google.com")
    assert b_id > 0
    assert temp_storage.is_bookmarked("https://google.com")
    assert not temp_storage.is_bookmarked("https://duckduckgo.com")

    # Retrieve bookmark
    items = temp_storage.get_bookmarks()
    assert len(items) == 1
    assert items[0]["title"] == "Google"
    assert items[0]["url"] == "https://google.com"

    # Search bookmark
    results = temp_storage.get_bookmarks("oogl")
    assert len(results) == 1
    no_results = temp_storage.get_bookmarks("nonexistent")
    assert len(no_results) == 0

    # Delete bookmark
    assert temp_storage.remove_bookmark(b_id)
    assert not temp_storage.is_bookmarked("https://google.com")


def test_history_crud(temp_storage):
    """Test history recording, querying, and deletion controls."""
    temp_storage.add_history("https://python.org", "Python Home")
    temp_storage.add_history("https://github.com", "GitHub")

    items = temp_storage.get_history()
    assert len(items) == 2
    assert items[0]["url"] in ("https://github.com", "https://python.org")

    # Search history
    results = temp_storage.get_history("github")
    assert len(results) == 1
    assert results[0]["title"] == "GitHub"

    # Delete item
    item_id = items[0]["id"]
    assert temp_storage.delete_history_item(item_id)
    assert temp_storage.get_history_count() == 1

    # Clear all history
    deleted = temp_storage.clear_history()
    assert deleted == 1
    assert temp_storage.get_history_count() == 0


def test_settings_storage(temp_storage):
    """Test settings get, set, and defaults."""
    assert temp_storage.get_setting("homepage") == "https://www.google.com"
    temp_storage.set_setting("homepage", "https://duckduckgo.com")
    assert temp_storage.get_setting("homepage") == "https://duckduckgo.com"

    all_settings = temp_storage.get_all_settings()
    assert "homepage" in all_settings
    assert "theme" in all_settings


def test_session_recovery(temp_storage):
    """Test saving and restoring open tabs."""
    tabs_data = [
        {"url": "https://python.org", "title": "Python", "is_active": True},
        {"url": "https://github.com", "title": "GitHub", "is_active": False},
    ]
    temp_storage.save_session(tabs_data)

    restored = temp_storage.get_saved_session()
    assert len(restored) == 2
    assert restored[0]["url"] == "https://python.org"
    assert restored[0]["is_active"] == 1
    assert restored[1]["url"] == "https://github.com"
    assert restored[1]["is_active"] == 0

    temp_storage.clear_session()
    assert len(temp_storage.get_saved_session()) == 0


def test_shield_stats(temp_storage):
    """Test shield statistics tracking."""
    temp_storage.record_shield_stat(trackers=5, ads=10, https_upgrades=2)
    temp_storage.record_shield_stat(trackers=3, ads=2, https_upgrades=1)

    totals = temp_storage.get_shield_stats_total()
    assert totals["total_trackers"] == 8
    assert totals["total_ads"] == 12
    assert totals["total_https"] == 3

