"""SQLite storage engine for LeanBrowse.

Provides persistent storage for:
1. Bookmarks (title, URL, folder, date added)
2. Browsing History (URL, page title, timestamp) with retention & deletion controls
   - Strictly obeys Private & Safest browsing modes (off-the-record, never persisted)
3. Browser Settings (homepage, theme, tab-sleep timeout, search engine, privacy preferences)
4. Privacy Shield configuration & aggregate statistics
5. Optional Session Recovery (open tabs, URLs, and active tab index)
"""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional


def get_default_db_path() -> str:
    """Return default path to SQLite database in ~/.grago/storage.db with fallback."""
    try:
        data_dir = os.path.join(os.path.expanduser("~"), ".grago")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, "storage.db")
    except Exception:
        return "storage.db"


class StorageManager:
    """Thread-safe SQLite storage manager for LeanBrowse."""

    DEFAULT_SETTINGS: Dict[str, Any] = {
        "homepage": "https://www.google.com",
        "search_engine": "Google",
        "search_url_template": "https://www.google.com/search?q={query}",
        "theme": "dark",
        "idle_timeout_seconds": "180",
        "default_mode": "lean",
        "shields_enabled": "1",
        "restore_session_on_startup": "0",
    }

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or get_default_db_path()
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            try:
                self._conn = sqlite3.connect(
                    self.db_path,
                    check_same_thread=False,
                    timeout=10.0,
                )
                self._conn.row_factory = sqlite3.Row
            except sqlite3.OperationalError:
                # Fallback to memory database if file access is restricted
                self.db_path = ":memory:"
                self._conn = sqlite3.connect(
                    self.db_path,
                    check_same_thread=False,
                    timeout=10.0,
                )
                self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        """Create database tables and indexes if they do not exist."""
        with self._lock:
            conn = self._get_connection()
            with conn:
                # 1. Bookmarks Table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS bookmarks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        url TEXT NOT NULL UNIQUE,
                        folder TEXT DEFAULT 'Bookmarks',
                        date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_bookmarks_url ON bookmarks (url);")

                # 2. Browsing History Table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT NOT NULL,
                        title TEXT NOT NULL,
                        visit_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history (visit_timestamp DESC);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_history_url ON history (url);")

                # 3. Settings Table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                """)

                # 4. Shield Stats Table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS shield_stats (
                        date TEXT PRIMARY KEY,
                        trackers_blocked INTEGER DEFAULT 0,
                        ads_blocked INTEGER DEFAULT 0,
                        https_upgrades INTEGER DEFAULT 0
                    );
                """)

                # 5. Session Tabs Table (for session recovery)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS session_tabs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT NOT NULL,
                        title TEXT NOT NULL,
                        tab_order INTEGER NOT NULL,
                        is_active INTEGER DEFAULT 0
                    );
                """)

                # Seed default settings if empty
                for key, val in self.DEFAULT_SETTINGS.items():
                    conn.execute(
                        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);",
                        (key, str(val)),
                    )

    # ── Bookmarks ─────────────────────────────────────────────────────────────
    def add_bookmark(self, title: str, url: str, folder: str = "Bookmarks") -> int:
        """Add a website to bookmarks or update existing title."""
        if not url:
            return -1
        display_title = title.strip() or url
        with self._lock:
            conn = self._get_connection()
            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO bookmarks (title, url, folder, date_added)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(url) DO UPDATE SET title = excluded.title, folder = excluded.folder;
                    """,
                    (display_title, url.strip(), folder),
                )
                return cursor.lastrowid or 0

    def remove_bookmark(self, bookmark_id: int) -> bool:
        """Delete bookmark by ID."""
        with self._lock:
            conn = self._get_connection()
            with conn:
                cursor = conn.execute("DELETE FROM bookmarks WHERE id = ?;", (bookmark_id,))
                return cursor.rowcount > 0

    def remove_bookmark_by_url(self, url: str) -> bool:
        """Delete bookmark by URL."""
        with self._lock:
            conn = self._get_connection()
            with conn:
                cursor = conn.execute("DELETE FROM bookmarks WHERE url = ?;", (url.strip(),))
                return cursor.rowcount > 0

    def is_bookmarked(self, url: str) -> bool:
        """Check if a URL is currently bookmarked."""
        if not url:
            return False
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("SELECT 1 FROM bookmarks WHERE url = ? LIMIT 1;", (url.strip(),))
            return cursor.fetchone() is not None

    def get_bookmarks(self, search: str = "") -> List[Dict[str, Any]]:
        """Return list of bookmarks optionally filtered by query."""
        with self._lock:
            conn = self._get_connection()
            if search.strip():
                pattern = f"%{search.strip()}%"
                cursor = conn.execute(
                    """
                    SELECT id, title, url, folder, date_added
                    FROM bookmarks
                    WHERE title LIKE ? OR url LIKE ?
                    ORDER BY date_added DESC;
                    """,
                    (pattern, pattern),
                )
            else:
                cursor = conn.execute(
                    "SELECT id, title, url, folder, date_added FROM bookmarks ORDER BY date_added DESC;"
                )
            return [dict(row) for row in cursor.fetchall()]

    # ── Browsing History ──────────────────────────────────────────────────────
    def add_history(self, url: str, title: str) -> None:
        """Record visited page to history. (Should only be called in non-private mode)."""
        if not url or url.startswith("about:") or url.startswith("grago://"):
            return
        clean_title = title.strip() or url
        with self._lock:
            conn = self._get_connection()
            with conn:
                conn.execute(
                    """
                    INSERT INTO history (url, title, visit_timestamp)
                    VALUES (?, ?, CURRENT_TIMESTAMP);
                    """,
                    (url.strip(), clean_title),
                )

    def get_history(self, search: str = "", limit: int = 150) -> List[Dict[str, Any]]:
        """Retrieve recent browsing history."""
        with self._lock:
            conn = self._get_connection()
            if search.strip():
                pattern = f"%{search.strip()}%"
                cursor = conn.execute(
                    """
                    SELECT id, url, title, visit_timestamp
                    FROM history
                    WHERE title LIKE ? OR url LIKE ?
                    ORDER BY visit_timestamp DESC
                    LIMIT ?;
                    """,
                    (pattern, pattern, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, url, title, visit_timestamp
                    FROM history
                    ORDER BY visit_timestamp DESC
                    LIMIT ?;
                    """,
                    (limit,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def delete_history_item(self, history_id: int) -> bool:
        """Delete single history record."""
        with self._lock:
            conn = self._get_connection()
            with conn:
                cursor = conn.execute("DELETE FROM history WHERE id = ?;", (history_id,))
                return cursor.rowcount > 0

    def clear_history(self, hours: Optional[int] = None) -> int:
        """Clear browsing history, optionally limited to the last N hours."""
        with self._lock:
            conn = self._get_connection()
            with conn:
                if hours is not None:
                    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
                    cursor = conn.execute("DELETE FROM history WHERE visit_timestamp >= ?;", (cutoff,))
                else:
                    cursor = conn.execute("DELETE FROM history;")
                return cursor.rowcount

    def get_history_count(self) -> int:
        """Return total number of history records."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("SELECT COUNT(*) FROM history;")
            row = cursor.fetchone()
            return row[0] if row else 0

    # ── Browser Settings ──────────────────────────────────────────────────────
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Retrieve setting value by key."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("SELECT value FROM settings WHERE key = ?;", (key,))
            row = cursor.fetchone()
            if row is not None:
                return row["value"]
            return self.DEFAULT_SETTINGS.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """Store or update a setting."""
        with self._lock:
            conn = self._get_connection()
            with conn:
                conn.execute(
                    """
                    INSERT INTO settings (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
                    """,
                    (key, str(value)),
                )

    def get_all_settings(self) -> Dict[str, str]:
        """Return all persisted settings."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("SELECT key, value FROM settings;")
            return {row["key"]: row["value"] for row in cursor.fetchall()}

    # ── Privacy Shield Aggregate Statistics ───────────────────────────────────
    def record_shield_stat(self, trackers: int = 0, ads: int = 0, https_upgrades: int = 0) -> None:
        """Increment daily aggregate shield statistics."""
        today = datetime.date.today().isoformat()
        with self._lock:
            conn = self._get_connection()
            with conn:
                conn.execute(
                    """
                    INSERT INTO shield_stats (date, trackers_blocked, ads_blocked, https_upgrades)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(date) DO UPDATE SET
                        trackers_blocked = trackers_blocked + excluded.trackers_blocked,
                        ads_blocked = ads_blocked + excluded.ads_blocked,
                        https_upgrades = https_upgrades + excluded.https_upgrades;
                    """,
                    (today, trackers, ads, https_upgrades),
                )

    def get_shield_stats_total(self) -> Dict[str, int]:
        """Return cumulative totals for shield blocking."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute(
                """
                SELECT
                    COALESCE(SUM(trackers_blocked), 0) as total_trackers,
                    COALESCE(SUM(ads_blocked), 0) as total_ads,
                    COALESCE(SUM(https_upgrades), 0) as total_https
                FROM shield_stats;
                """
            )
            row = cursor.fetchone()
            if row:
                return {
                    "total_trackers": row["total_trackers"],
                    "total_ads": row["total_ads"],
                    "total_https": row["total_https"],
                }
            return {"total_trackers": 0, "total_ads": 0, "total_https": 0}

    # ── Session Recovery ──────────────────────────────────────────────────────
    def save_session(self, tabs: List[Dict[str, Any]]) -> None:
        """Persist currently open tabs and order for session restoration."""
        with self._lock:
            conn = self._get_connection()
            with conn:
                conn.execute("DELETE FROM session_tabs;")
                for idx, tab in enumerate(tabs):
                    url = tab.get("url", "").strip()
                    title = tab.get("title", "").strip() or url
                    is_active = 1 if tab.get("is_active") else 0
                    if url and not url.startswith("about:"):
                        conn.execute(
                            """
                            INSERT INTO session_tabs (url, title, tab_order, is_active)
                            VALUES (?, ?, ?, ?);
                            """,
                            (url, title, idx, is_active),
                        )

    def get_saved_session(self) -> List[Dict[str, Any]]:
        """Retrieve saved tabs from previous session."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute(
                "SELECT url, title, tab_order, is_active FROM session_tabs ORDER BY tab_order ASC;"
            )
            return [dict(row) for row in cursor.fetchall()]

    def clear_session(self) -> None:
        """Clear saved session state."""
        with self._lock:
            conn = self._get_connection()
            with conn:
                conn.execute("DELETE FROM session_tabs;")

    # ── Database Stats & Maintenance ──────────────────────────────────────────
    def get_db_size_kb(self) -> float:
        """Return SQLite file size in kilobytes."""
        if self.db_path == ":memory:":
            return 0.0
        try:
            return round(os.path.getsize(self.db_path) / 1024.0, 2)
        except OSError:
            return 0.0

