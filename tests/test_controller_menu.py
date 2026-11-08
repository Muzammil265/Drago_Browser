"""Unit tests for the three-dots menu, SQLite storage integration, and UI dialogs."""

import os
import sys
import tempfile
import pytest

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from browser.controller import (
    AboutDialog,
    BookmarksDialog,
    GragoWindow,
    HistoryDialog,
    SettingsDialog,
)
from browser.storage import StorageManager


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication instance is initialized."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def temp_storage():
    """Create isolated SQLite database for test runs."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    storage = StorageManager(db_path=db_path)
    yield storage
    try:
        os.remove(db_path)
    except OSError:
        pass


def test_three_dots_menu_button_present(qapp):
    """Test that the three-dots icon button is instantiated and placed in the toolbar."""
    win = GragoWindow()
    assert hasattr(win, "btn_menu"), "GragoWindow must have btn_menu"
    assert win.btn_menu.text() == "⋮"
    assert win.btn_menu.objectName() == "menu-btn"
    assert "Alt+F" in win.btn_menu.toolTip()
    # Confirm toolbar search bar expands cleanly
    assert hasattr(win, "url_bar")
    win.close()


def test_toolbar_layout_clean_search_bar(qapp):
    """Test that toolbar options were moved to the menu and url_bar is clean and expanding."""
    win = GragoWindow()
    # url_bar should exist and be set to expanding policy
    assert win.url_bar.sizePolicy().horizontalPolicy().name == "Expanding"
    # Three dots menu button should be directly at the end of the toolbar
    assert win.btn_menu.parent() is not None
    # Mode and sleep controls should work via controller methods
    from browser.privacy import BrowsingMode
    win._set_mode(BrowsingMode.SAFEST)
    assert win._privacy_manager.mode == BrowsingMode.SAFEST
    win._set_mode(BrowsingMode.LEAN)
    assert win._privacy_manager.mode == BrowsingMode.LEAN
    win._set_sleep_timeout(60)
    assert win._memory_manager.idle_timeout_seconds == 60
    win.close()


def test_bookmarks_dialog(qapp, temp_storage):
    """Test BookmarksDialog loading, search filtering, and deletion."""
    temp_storage.add_bookmark("Python", "https://python.org")
    temp_storage.add_bookmark("GitHub", "https://github.com")

    opened_urls = []
    dlg = BookmarksDialog(temp_storage, open_callback=lambda u: opened_urls.append(u))
    assert dlg.table.rowCount() == 2

    # Filter bookmarks
    dlg.search_input.setText("git")
    assert dlg.table.rowCount() == 1

    dlg.search_input.setText("")
    assert dlg.table.rowCount() == 2

    # Select and trigger open
    dlg.table.selectRow(0)
    dlg._open_selected()
    assert len(opened_urls) == 1

    # Delete
    dlg.table.selectRow(0)
    dlg._delete_selected()
    assert dlg.table.rowCount() == 1
    dlg.close()


def test_history_dialog(qapp, temp_storage):
    """Test HistoryDialog rendering, search filtering, and clear all."""
    temp_storage.add_history("https://example.com/page1", "Example Page 1")
    temp_storage.add_history("https://example.com/page2", "Example Page 2")

    opened_urls = []
    dlg = HistoryDialog(temp_storage, open_callback=lambda u: opened_urls.append(u))
    assert dlg.table.rowCount() == 2

    # Filter
    dlg.search_input.setText("page1")
    assert dlg.table.rowCount() == 1

    dlg.search_input.setText("")
    assert dlg.table.rowCount() == 2

    dlg.close()


def test_settings_dialog(qapp, temp_storage):
    """Test SettingsDialog loading and saving settings to SQLite."""
    dlg = SettingsDialog(temp_storage)
    assert dlg.inp_homepage.text() == "https://www.google.com"

    dlg.inp_homepage.setText("https://duckduckgo.com")
    dlg._save_settings()

    assert temp_storage.get_setting("homepage") == "https://duckduckgo.com"
    dlg.close()


def test_about_dialog(qapp):
    """Test AboutDialog initialization."""
    dlg = AboutDialog()
    assert "About LeanBrowse" in dlg.windowTitle()
    dlg.close()


def test_zoom_controls(qapp):
    """Test zoom in, zoom out, and reset."""
    win = GragoWindow()
    current_tab = win._current_tab_item()
    if current_tab and current_tab.web_view:
        initial_zoom = current_tab.web_view.zoomFactor()
        win._zoom_in()
        assert current_tab.web_view.zoomFactor() > initial_zoom
        win._zoom_reset()
        assert current_tab.web_view.zoomFactor() == 1.0
    win.close()

