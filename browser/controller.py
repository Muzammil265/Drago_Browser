"""Browser Controller and UI module for Grago.

Manages tabs, UI layout, address bar navigation, tab hibernation lifecycles,
and the dark desktop interface.
"""

from __future__ import annotations

import random
import time
from typing import Dict, Optional

from PySide6.QtCore import QEvent, QPoint, QSize, QTimer, QUrl, Qt, Signal, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QShortcut,
    QLinearGradient,
    QBrush,
    QPalette,
    QPixmap,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsBlurEffect,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView

from browser.memory_manager import ResourceMonitor, TabMemoryManager
from browser.privacy import BrowsingMode, PrivacyManager, normalize_url
from browser.security import FingerprintProtectionMode, ProxyMode
from browser.storage import StorageManager

APP_NAME = "Grago"
DEFAULT_HOME_URL = "https://www.google.com"
NEW_TAB_SENTINEL = "grago://newtab"
IDLE_TIMEOUT_SECONDS = 180
# Raised intervals → less CPU burn while the browser sits idle
MEMORY_REFRESH_MS = 8000
IDLE_CHECK_MS = 10000

# Curated Unsplash collections for random new-tab backgrounds (1920x1080)
BG_IMAGE_URLS = [
    "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1920&q=80",  # mountains
    "https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=1920&q=80",  # forest light
    "https://images.unsplash.com/photo-1501854140801-50d01698950b?w=1920&q=80",  # aerial nature
    "https://images.unsplash.com/photo-1493246507139-91e8fad9978e?w=1920&q=80",  # misty mountains
    "https://images.unsplash.com/photo-1518173946687-a4c8892bbd9f?w=1920&q=80",  # aurora
    "https://images.unsplash.com/photo-1475924156734-496f6cac6ec1?w=1920&q=80",  # sunset lake
    "https://images.unsplash.com/photo-1419242902214-272b3f66ee7a?w=1920&q=80",  # starry night
    "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=1920&q=80",  # mountain peak
]


DARK_STYLESHEET = """
QMainWindow {
    background-color: #0f1115;
}

QWidget {
    color: #e2e8f0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QToolBar {
    background-color: #171922;
    border-bottom: 1px solid #232734;
    spacing: 6px;
    padding: 6px 10px;
}

QPushButton {
    background-color: #232734;
    border: 1px solid #2e3447;
    border-radius: 6px;
    color: #e2e8f0;
    padding: 5px 12px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #2d3345;
    border-color: #3b82f6;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #1e2230;
}

QPushButton:disabled {
    background-color: #151821;
    border-color: #1f2330;
    color: #4a5568;
}

QPushButton#accent-btn {
    background-color: #2563eb;
    border-color: #3b82f6;
    color: #ffffff;
}

QPushButton#accent-btn:hover {
    background-color: #1d4ed8;
}

QPushButton#shield-btn {
    background-color: #064e3b;
    border: 1px solid #059669;
    color: #34d399;
    font-weight: 600;
    padding: 5px 11px;
    border-radius: 6px;
}

QPushButton#shield-btn:hover {
    background-color: #065f46;
    border-color: #10b981;
    color: #6ee7b7;
}

QPushButton#identity-btn {
    background-color: #2e1065;
    border: 1px solid #7c3aed;
    color: #ddd6fe;
    font-weight: 600;
    padding: 5px 11px;
    border-radius: 6px;
}

QPushButton#identity-btn:hover {
    background-color: #3b0764;
    border-color: #a855f7;
    color: #ffffff;
}

QPushButton#security-badge-btn {
    background-color: transparent;
    border: none;
    font-size: 14px;
    padding: 2px 4px;
}

QPushButton#sleep-btn {
    background-color: #232038;
    border: 1px solid #6366f1;
    color: #a5b4fc;
    font-weight: 500;
    padding: 5px 10px;
    border-radius: 6px;
}

QPushButton#sleep-btn:hover {
    background-color: #312e52;
    color: #c7d2fe;
}

QLabel#memory-badge {
    background-color: #1b202c;
    border: 1px solid #2d3447;
    border-radius: 6px;
    padding: 4px 10px;
    color: #38bdf8;
    font-weight: 600;
    font-size: 12px;
}

QComboBox {
    background-color: #232734;
    border: 1px solid #2e3447;
    border-radius: 6px;
    color: #cbd5e1;
    padding: 4px 8px;
    min-width: 110px;
}

QComboBox:hover {
    border-color: #3b82f6;
}

QComboBox QAbstractItemView {
    background-color: #171922;
    border: 1px solid #2e3447;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    color: #cbd5e1;
}

QLineEdit#url-bar {
    background-color: #0f1117;
    border: 1px solid #2b3143;
    border-radius: 8px;
    color: #f8fafc;
    padding: 6px 14px;
    font-size: 13px;
    selection-background-color: #2563eb;
}

QLineEdit#url-bar:focus {
    border: 1px solid #3b82f6;
    background-color: #0a0c10;
}

QProgressBar {
    border: none;
    background-color: transparent;
    height: 2px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #3b82f6;
}

QTabWidget::pane {
    border-top: 1px solid #232734;
    background-color: #0f1115;
}

QTabBar {
    background-color: #0f1115;
}

QTabBar::tab {
    background-color: #141720;
    color: #94a3b8;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    border: 1px solid #1e2230;
    border-bottom: none;
    padding: 6px 14px 6px 14px;
    margin-right: 2px;
    min-width: 100px;
    max-width: 220px;
}

QTabBar::tab:selected {
    background-color: #1f2432;
    color: #ffffff;
    font-weight: 600;
    border-top: 2px solid #3b82f6;
    border-left: 1px solid #2d3447;
    border-right: 1px solid #2d3447;
}

QTabBar::tab:hover:!selected {
    background-color: #191c28;
    color: #cbd5e1;
}

QTabBar::close-button {
    subcontrol-position: right;
    margin-left: 4px;
    image: none;
    width: 0px;
    height: 0px;
}

QStatusBar {
    background-color: #141720;
    border-top: 1px solid #1f2330;
    color: #94a3b8;
    font-size: 11px;
    padding: 2px 10px;
}

QPushButton#tab-close-btn {
    background: transparent;
    border: none;
    color: #64748b;
    font-size: 13px;
    font-weight: 700;
    padding: 0px;
    margin: 0px;
    min-width: 18px;
    max-width: 18px;
    min-height: 18px;
    max-height: 18px;
    border-radius: 9px;
}

QPushButton#tab-close-btn:hover {
    background-color: #ef4444;
    color: #ffffff;
}

QPushButton#tab-add-btn {
    background: transparent;
    border: 1px solid #2e3447;
    color: #64748b;
    font-size: 16px;
    font-weight: 300;
    padding: 0px;
    margin: 2px 4px;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    border-radius: 14px;
}

QPushButton#tab-add-btn:hover {
    background-color: #232734;
    border-color: #3b82f6;
    color: #3b82f6;
}

/* ── Mode switcher ─────────────────────────────────────────────────── */
QPushButton#mode-lean-btn, QPushButton#mode-private-btn, QPushButton#mode-safest-btn {
    background: transparent;
    border: none;
    border-radius: 6px;
    color: #64748b;
    font-size: 12px;
    font-weight: 600;
    padding: 4px 10px;
    min-height: 24px;
}

QPushButton#mode-lean-btn:checked {
    background-color: #1a2e1a;
    color: #4ade80;
    border: 1px solid #16a34a;
}

QPushButton#mode-private-btn:checked {
    background-color: #1a1535;
    color: #a78bfa;
    border: 1px solid #7c3aed;
}

QPushButton#mode-safest-btn:checked {
    background-color: #431407;
    color: #fdba74;
    border: 1px solid #ea580c;
}

QPushButton#mode-lean-btn:hover:!checked,
QPushButton#mode-private-btn:hover:!checked,
QPushButton#mode-safest-btn:hover:!checked {
    background-color: #1e2330;
    color: #cbd5e1;
}

/* ── Main Menu & Three-Dots Button ─────────────────────────────────── */
QPushButton#menu-btn {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    color: #e2e8f0;
    font-size: 18px;
    font-weight: 700;
    padding: 2px 8px;
    min-width: 28px;
    max-width: 32px;
    min-height: 26px;
}

QPushButton#menu-btn:hover {
    background-color: #232734;
    border-color: #3b82f6;
    color: #ffffff;
}

QPushButton#menu-btn:pressed {
    background-color: #1e2230;
}

QMenu {
    background-color: #171922;
    border: 1px solid #2e3447;
    border-radius: 8px;
    padding: 6px;
    color: #e2e8f0;
}

QMenu::item {
    background-color: transparent;
    padding: 6px 28px 6px 12px;
    border-radius: 6px;
    font-size: 13px;
    margin: 1px 2px;
}

QMenu::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QMenu::item:disabled {
    color: #4b5563;
}

QMenu::separator {
    height: 1px;
    background-color: #232734;
    margin: 4px 8px;
}

/* ── Table widgets for Bookmarks & History ──────────────────────────── */
QTableWidget {
    background-color: #141720;
    border: 1px solid #232838;
    border-radius: 8px;
    gridline-color: #1f2432;
    color: #e2e8f0;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #171922;
    color: #94a3b8;
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid #232838;
    font-weight: 600;
}
"""


class SleepingTabWidget(QWidget):
    """Placeholder view shown when a background tab is hibernated to conserve memory."""

    wake_requested = Signal()

    def __init__(
        self,
        title: str,
        url: str,
        idle_seconds: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._url = url
        self._idle_seconds = idle_seconds
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)

        card = QFrame(self)
        card.setObjectName("sleeping-card")
        card.setStyleSheet(
            """
            QFrame#sleeping-card {
                background-color: #171a24;
                border: 1px solid #282f42;
                border-radius: 12px;
                padding: 32px;
                max-width: 600px;
            }
            """
        )
        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.setSpacing(14)

        icon_label = QLabel("💤", card)
        icon_label.setStyleSheet("font-size: 48px; background: transparent;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon_label)

        status_badge = QLabel("TAB HIBERNATED TO SAVE RAM", card)
        status_badge.setStyleSheet(
            """
            background-color: #261f3d;
            color: #a78bfa;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 10px;
            border: 1px solid #4c3d75;
            """
        )
        status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(status_badge)

        title_label = QLabel(self._title or "Untitled Page", card)
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: 600; color: #f8fafc; background: transparent;"
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        card_layout.addWidget(title_label)

        url_label = QLabel(self._url, card)
        url_label.setStyleSheet(
            "font-size: 12px; color: #38bdf8; font-family: monospace; background: transparent;"
        )
        url_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        url_label.setWordWrap(True)
        card_layout.addWidget(url_label)

        minutes = max(1, self._idle_seconds // 60)
        desc_label = QLabel(
            f"This tab was automatically hibernated after {minutes} minutes of inactivity.\n"
            "Chromium's rendering process and memory have been unloaded.\n"
            "Click anywhere or press the button below to restore.",
            card,
        )
        desc_label.setStyleSheet("font-size: 12px; color: #94a3b8; background: transparent;")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(desc_label)

        btn_wake = QPushButton("⚡ Wake Tab & Restore", card)
        btn_wake.setObjectName("accent-btn")
        btn_wake.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_wake.setMinimumWidth(180)
        btn_wake.setMinimumHeight(38)
        btn_wake.clicked.connect(self.wake_requested.emit)
        card_layout.addWidget(btn_wake, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(card)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Clicking anywhere wakes the tab."""
        self.wake_requested.emit()
        super().mousePressEvent(event)


class NewTabPage(QWidget):
    """Beautiful new-tab page with a random background image and centered search bar."""

    search_requested = Signal(str)

    # Greeting messages shown at top
    GREETINGS = [
        "Good morning ☀️", "Good afternoon 🌤️", "Good evening 🌙",
        "Hello, Explorer 🚀", "Ready to browse? 🌐", "Where to next? 🗺️",
    ]

    def __init__(self, nav_callback, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._nav_callback = nav_callback
        self._pixmap: Optional[QPixmap] = None
        self._nam = QNetworkAccessManager(self)
        self._setup_ui()
        self._load_random_bg()

    def _setup_ui(self) -> None:
        self.setAutoFillBackground(False)

        # Main overlay layout
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Transparent overlay container
        self._overlay = QWidget(self)
        self._overlay.setObjectName("nt-overlay")
        self._overlay.setStyleSheet("""
            QWidget#nt-overlay {
                background: transparent;
            }
        """)
        outer.addWidget(self._overlay)

        overlay_layout = QVBoxLayout(self._overlay)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overlay_layout.setSpacing(0)

        # ── Card ──────────────────────────────────────────────────────────────
        card = QFrame(self._overlay)
        card.setObjectName("nt-card")
        card.setStyleSheet("""
            QFrame#nt-card {
                background-color: rgba(15, 17, 21, 0.72);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 20px;
            }
        """)
        card.setFixedWidth(560)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(20)
        card_layout.setContentsMargins(36, 36, 36, 40)

        # Greeting label
        hour = time.localtime().tm_hour
        if hour < 12:
            greeting = "Good morning ☀️"
        elif hour < 17:
            greeting = "Good afternoon 🌤️"
        else:
            greeting = "Good evening 🌙"

        lbl_greeting = QLabel(greeting, card)
        lbl_greeting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_greeting.setStyleSheet("""
            color: #f8fafc;
            font-size: 26px;
            font-weight: 700;
            background: transparent;
            letter-spacing: 0.5px;
        """)
        card_layout.addWidget(lbl_greeting)

        lbl_sub = QLabel("Search the web or enter an address", card)
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sub.setStyleSheet("color: #94a3b8; font-size: 13px; background: transparent; margin-bottom: 4px;")
        card_layout.addWidget(lbl_sub)

        # Search input row
        search_row = QHBoxLayout()
        search_row.setSpacing(0)

        self._search_box = QLineEdit(card)
        self._search_box.setObjectName("nt-search")
        self._search_box.setPlaceholderText("Search the web or enter a URL...")
        self._search_box.setMinimumHeight(46)
        self._search_box.setStyleSheet("""
            QLineEdit#nt-search {
                background-color: rgba(255,255,255,0.07);
                border: 1.5px solid rgba(255,255,255,0.15);
                border-right: none;
                border-top-left-radius: 12px;
                border-bottom-left-radius: 12px;
                color: #f8fafc;
                font-size: 15px;
                padding: 0 16px;
                selection-background-color: #2563eb;
            }
            QLineEdit#nt-search:focus {
                border-color: #3b82f6;
                background-color: rgba(255,255,255,0.10);
            }
        """)
        self._search_box.returnPressed.connect(self._on_search)
        search_row.addWidget(self._search_box)

        btn_go = QPushButton("→", card)
        btn_go.setObjectName("nt-go-btn")
        btn_go.setMinimumHeight(46)
        btn_go.setFixedWidth(52)
        btn_go.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_go.setStyleSheet("""
            QPushButton#nt-go-btn {
                background-color: #2563eb;
                color: #ffffff;
                border: 1.5px solid #3b82f6;
                border-left: none;
                border-top-right-radius: 12px;
                border-bottom-right-radius: 12px;
                font-size: 18px;
                font-weight: 700;
            }
            QPushButton#nt-go-btn:hover {
                background-color: #1d4ed8;
            }
        """)
        btn_go.clicked.connect(self._on_search)
        search_row.addWidget(btn_go)
        card_layout.addLayout(search_row)

        # Quick-links row
        links_row = QHBoxLayout()
        links_row.setSpacing(12)
        links_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        quick_links = [
            ("🔍 Search", "https://www.google.com"),
            ("📰 News", "https://news.ycombinator.com"),
            ("🐙 GitHub", "https://github.com"),
            ("🎬 YouTube", "https://www.youtube.com"),
        ]
        for label, url in quick_links:
            ql_btn = QPushButton(label, card)
            ql_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            ql_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255,255,255,0.07);
                    border: 1px solid rgba(255,255,255,0.12);
                    border-radius: 8px;
                    color: #cbd5e1;
                    font-size: 12px;
                    padding: 6px 14px;
                }
                QPushButton:hover {
                    background-color: rgba(59,130,246,0.25);
                    border-color: #3b82f6;
                    color: #ffffff;
                }
            """)
            ql_btn.clicked.connect(lambda checked, u=url: self._nav_callback(u))
            links_row.addWidget(ql_btn)
        card_layout.addLayout(links_row)

        overlay_layout.addWidget(card)

        # ── Credit label at bottom ────────────────────────────────────────────
        self._credit_lbl = QLabel("Photo: Unsplash", self._overlay)
        self._credit_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self._credit_lbl.setStyleSheet("""
            color: rgba(255,255,255,0.35);
            font-size: 10px;
            background: transparent;
            padding: 6px 12px;
        """)
        overlay_layout.addWidget(self._credit_lbl)

    def _load_random_bg(self) -> None:
        """Fetch a random background image from Unsplash."""
        url = random.choice(BG_IMAGE_URLS)
        req = QNetworkRequest(QUrl(url))
        reply = self._nam.get(req)
        reply.finished.connect(lambda r=reply: self._on_image_downloaded(r))

    def _on_image_downloaded(self, reply: QNetworkReply) -> None:
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            pix = QPixmap()
            pix.loadFromData(data)
            if not pix.isNull():
                self._pixmap = pix
                self.update()  # trigger paintEvent
        reply.deleteLater()

    def paintEvent(self, event) -> None:  # noqa: N802
        """Draw the background image scaled to fill, with a dark gradient overlay."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = self.rect()

        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - rect.width()) // 2
            y = (scaled.height() - rect.height()) // 2
            painter.drawPixmap(-x, -y, scaled)
        else:
            # Fallback: deep blue-purple gradient
            grad = QLinearGradient(0, 0, rect.width(), rect.height())
            grad.setColorAt(0.0, QColor("#0a0c1a"))
            grad.setColorAt(0.5, QColor("#0d1b3e"))
            grad.setColorAt(1.0, QColor("#1a0a2e"))
            painter.fillRect(rect, QBrush(grad))

        # Dark scrim so the card is readable
        scrim = QLinearGradient(0, 0, 0, rect.height())
        scrim.setColorAt(0.0, QColor(0, 0, 0, 120))
        scrim.setColorAt(1.0, QColor(0, 0, 0, 160))
        painter.fillRect(rect, QBrush(scrim))

        painter.end()
        super().paintEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        """Focus the search box when page is shown."""
        super().showEvent(event)
        QTimer.singleShot(50, self._search_box.setFocus)

    def _on_search(self) -> None:
        text = self._search_box.text().strip()
        if text:
            self._nav_callback(text)


class BrowserTabItem(QWidget):
    """Container for a single tab, hosting either an active QWebEngineView or a SleepingTabWidget."""

    title_changed = Signal(str)
    url_changed = Signal(QUrl)
    load_progress = Signal(int)
    load_finished = Signal(bool)
    link_hovered = Signal(str)
    wake_requested = Signal()

    def __init__(
        self,
        tab_id: str,
        profile: QWebEngineProfile,
        initial_url: QUrl,
        idle_seconds: int = 180,
        nav_callback=None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.tab_id = tab_id
        self._profile = profile
        self._url = initial_url
        self._title = "New Tab"
        self._idle_seconds = idle_seconds
        self._is_sleeping = False
        self._web_view: Optional[QWebEngineView] = None
        self._sleeping_widget: Optional[SleepingTabWidget] = None
        self._new_tab_page: Optional[NewTabPage] = None
        self._nav_callback = nav_callback

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        is_new_tab = (
            not initial_url.isValid()
            or initial_url.isEmpty()
            or initial_url.toString() == NEW_TAB_SENTINEL
        )
        if is_new_tab:
            self._show_new_tab_page()
        else:
            self._init_web_view()
            self._web_view.load(initial_url)

    @property
    def is_sleeping(self) -> bool:
        return self._is_sleeping

    @property
    def url(self) -> QUrl:
        if self._web_view and not self._is_sleeping:
            return self._web_view.url()
        return self._url

    @property
    def title(self) -> str:
        if self._web_view and not self._is_sleeping:
            return self._web_view.title() or self._title
        return self._title

    @property
    def web_view(self) -> Optional[QWebEngineView]:
        return self._web_view

    def _show_new_tab_page(self) -> None:
        """Display the custom new-tab page instead of a web view."""
        self._new_tab_page = NewTabPage(nav_callback=self._nav_callback or (lambda _: None), parent=self)
        self._layout.addWidget(self._new_tab_page)

    def _hide_new_tab_page(self) -> None:
        """Remove the new-tab page to make room for the web view."""
        if self._new_tab_page:
            self._layout.removeWidget(self._new_tab_page)
            self._new_tab_page.deleteLater()
            self._new_tab_page = None

    def _init_web_view(self) -> None:
        """Create and configure the QWebEngineView using the shared off-the-record profile."""
        self._web_view = QWebEngineView(self)
        page = QWebEnginePage(self._profile, self._web_view)
        self._web_view.setPage(page)

        # Wire signals
        self._web_view.titleChanged.connect(self._on_title_changed)
        self._web_view.urlChanged.connect(self._on_url_changed)
        self._web_view.loadProgress.connect(self.load_progress.emit)
        self._web_view.loadFinished.connect(self.load_finished.emit)
        page.linkHovered.connect(self.link_hovered.emit)

        self._layout.addWidget(self._web_view)

    def _on_title_changed(self, new_title: str) -> None:
        if new_title:
            self._title = new_title
            self.title_changed.emit(new_title)

    def _on_url_changed(self, new_url: QUrl) -> None:
        if new_url.isValid():
            self._url = new_url
            self.url_changed.emit(new_url)

    def hibernate(self) -> None:
        """Unload the web view and release memory resources."""
        if self._is_sleeping or not self._web_view:
            return

        # Record last state
        if self._web_view.url().isValid() and not self._web_view.url().isEmpty():
            self._url = self._web_view.url()
        current_title = self._web_view.title()
        if current_title:
            self._title = current_title

        # Destroy WebEngineView to release Chromium renderer process memory
        self._layout.removeWidget(self._web_view)
        self._web_view.stop()
        self._web_view.setPage(None)
        self._web_view.deleteLater()
        self._web_view = None

        # Mount sleeping placeholder widget
        self._sleeping_widget = SleepingTabWidget(
            title=self._title,
            url=self._url.toString(),
            idle_seconds=self._idle_seconds,
            parent=self,
        )
        self._sleeping_widget.wake_requested.connect(self.wake)
        self._layout.addWidget(self._sleeping_widget)

        self._is_sleeping = True

    def wake(self) -> None:
        """Re-create the web view and reload the saved URL."""
        if not self._is_sleeping:
            return

        # Remove sleeping widget
        if self._sleeping_widget:
            self._layout.removeWidget(self._sleeping_widget)
            self._sleeping_widget.deleteLater()
            self._sleeping_widget = None

        # Re-initialize web view and reload
        self._init_web_view()
        self._is_sleeping = False
        self.wake_requested.emit()

        if self._url.isValid() and not self._url.isEmpty():
            self._web_view.load(self._url)

    def load(self, url: QUrl) -> None:
        """Load a target URL, waking first if hibernated, or replacing the new-tab page."""
        self._url = url
        if self._is_sleeping:
            self.wake()
        elif self._new_tab_page:
            # Replace new tab page with actual web view
            self._hide_new_tab_page()
            self._init_web_view()
            self._web_view.load(url)
        elif self._web_view:
            self._web_view.load(url)


class ShieldsFlyoutDialog(QDialog):
    """Brave-style Shields control panel for per-site and session privacy controls."""

    def __init__(
        self,
        privacy_manager: PrivacyManager,
        current_url: QUrl,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._privacy_manager = privacy_manager
        self._current_url = current_url
        raw_host = current_url.host() if current_url.isValid() else ""
        self._host = raw_host if raw_host else "New Tab / Internal"

        self.setWindowTitle("Brave Shields — Site Protection")
        self.setFixedWidth(400)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #131620;
                color: #e2e8f0;
                border: 1px solid #232838;
                border-radius: 10px;
            }
            QLabel {
                color: #cbd5e1;
            }
            QCheckBox {
                color: #e2e8f0;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #3b4252;
                background-color: #1e222d;
            }
            QCheckBox::indicator:checked {
                background-color: #059669;
                border-color: #10b981;
            }
            """
        )
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        # Header card
        header_card = QFrame(self)
        header_card.setStyleSheet("background-color: #1a1e2b; border-radius: 8px; padding: 6px;")
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(8, 8, 8, 8)

        lbl_shield_icon = QLabel("🛡️", header_card)
        lbl_shield_icon.setStyleSheet("font-size: 26px; background: transparent;")
        h_layout.addWidget(lbl_shield_icon)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_title = QLabel("Brave Shields", header_card)
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #34d399; background: transparent;")
        title_vbox.addWidget(lbl_title)

        lbl_host = QLabel(self._host, header_card)
        lbl_host.setStyleSheet("font-size: 12px; color: #94a3b8; background: transparent;")
        title_vbox.addWidget(lbl_host)
        h_layout.addLayout(title_vbox)

        h_layout.addStretch()

        # Shields Master Toggle
        is_allowed = self._privacy_manager.interceptor.is_site_allowed(self._host)
        self._chk_master = QPushButton("UP" if not is_allowed else "DOWN", header_card)
        self._chk_master.setCheckable(True)
        self._chk_master.setChecked(not is_allowed)
        self._chk_master.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_master_button_style(not is_allowed)
        self._chk_master.clicked.connect(self._toggle_master_shield)
        h_layout.addWidget(self._chk_master)

        layout.addWidget(header_card)

        # Metrics Card
        metrics_card = QFrame(self)
        metrics_card.setStyleSheet("background-color: #161924; border: 1px solid #232838; border-radius: 8px; padding: 6px;")
        m_layout = QVBoxLayout(metrics_card)
        m_layout.setSpacing(8)

        site_count = self._privacy_manager.interceptor.get_site_blocked_count(self._host)
        total_count = self._privacy_manager.interceptor.total_blocked

        row1 = QHBoxLayout()
        r1_k = QLabel("Trackers & Ads Blocked on This Site:", metrics_card)
        r1_k.setStyleSheet("color: #cbd5e1; font-size: 12px; background: transparent;")
        self._lbl_site_count = QLabel(str(site_count), metrics_card)
        self._lbl_site_count.setStyleSheet("color: #34d399; font-weight: 700; font-size: 13px; background: transparent;")
        row1.addWidget(r1_k)
        row1.addStretch()
        row1.addWidget(self._lbl_site_count)
        m_layout.addLayout(row1)

        row2 = QHBoxLayout()
        r2_k = QLabel("Total Blocked This Session:", metrics_card)
        r2_k.setStyleSheet("color: #cbd5e1; font-size: 12px; background: transparent;")
        self._lbl_total_count = QLabel(str(total_count), metrics_card)
        self._lbl_total_count.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 13px; background: transparent;")
        row2.addWidget(r2_k)
        row2.addStretch()
        row2.addWidget(self._lbl_total_count)
        m_layout.addLayout(row2)

        # Filter List Engine Info Row
        fm = self._privacy_manager.filter_manager
        engine_name = "Rust adblock-rust ⚡" if fm.is_using_rust_engine else "Pure Python Trie"
        row3 = QHBoxLayout()
        r3_k = QLabel("Maintained Filter Rules:", metrics_card)
        r3_k.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent;")
        lbl_rules = QLabel(f"{fm.total_rules} rules ({engine_name})", metrics_card)
        lbl_rules.setStyleSheet("color: #a78bfa; font-weight: 600; font-size: 11px; background: transparent;")
        row3.addWidget(r3_k)
        row3.addStretch()
        row3.addWidget(lbl_rules)
        m_layout.addLayout(row3)

        layout.addWidget(metrics_card)

        # ── YouTube-Dedicated Compatibility & Protection Card ─────────────────
        is_yt = self._privacy_manager.youtube_shield.is_youtube_host(self._host)
        if is_yt:
            yt_card = QFrame(self)
            yt_card.setStyleSheet("background-color: #1e1318; border: 1px solid #701a35; border-radius: 8px; padding: 8px;")
            yt_layout = QVBoxLayout(yt_card)
            yt_layout.setSpacing(6)

            yt_title_row = QHBoxLayout()
            yt_icon = QLabel("▶️", yt_card)
            yt_icon.setStyleSheet("font-size: 14px; background: transparent;")
            yt_title = QLabel("YouTube Dedicated Ad & Stream Shield", yt_card)
            yt_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #fb7185; background: transparent;")
            yt_title_row.addWidget(yt_icon)
            yt_title_row.addWidget(yt_title)
            yt_title_row.addStretch()
            yt_layout.addLayout(yt_title_row)

            yt_status = QLabel("✓ Video streams whitelisted (*.googlevideo.com)\n✓ Dynamic video ad skipper active\n✓ Companion & masthead banner ads hidden", yt_card)
            yt_status.setStyleSheet("color: #cbd5e1; font-size: 11px; background: transparent;")
            yt_layout.addWidget(yt_status)

            layout.addWidget(yt_card)

        # ── Live Blocked Requests Log Card ────────────────────────────────────
        log_card = QFrame(self)
        log_card.setStyleSheet("background-color: #161924; border: 1px solid #232838; border-radius: 8px; padding: 8px;")
        l_layout = QVBoxLayout(log_card)
        l_layout.setSpacing(4)

        lbl_log_title = QLabel("Live Intercepted Requests Log:", log_card)
        lbl_log_title.setStyleSheet("font-size: 12px; font-weight: 600; color: #e2e8f0; background: transparent;")
        l_layout.addWidget(lbl_log_title)

        records = self._privacy_manager.interceptor.get_site_blocked_records(self._host)
        if records:
            scroll = QScrollArea(log_card)
            scroll.setFixedHeight(90)
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("background: transparent; border: none;")
            scroll_content = QWidget()
            scroll_layout = QVBoxLayout(scroll_content)
            scroll_layout.setContentsMargins(0, 0, 0, 0)
            scroll_layout.setSpacing(3)

            for rec in records[-8:]:
                item_lbl = QLabel(f"🚫 {rec.target_host} ({rec.resource_type})", scroll_content)
                item_lbl.setStyleSheet("color: #f87171; font-size: 11px; background: transparent;")
                item_lbl.setToolTip(f"URL: {rec.target_url}\nRule: {rec.rule}")
                scroll_layout.addWidget(item_lbl)

            scroll.setWidget(scroll_content)
            l_layout.addWidget(scroll)
        else:
            lbl_empty = QLabel("✓ No third-party trackers or ads blocked on this origin yet.", log_card)
            lbl_empty.setStyleSheet("color: #64748b; font-size: 11px; font-style: italic; background: transparent;")
            l_layout.addWidget(lbl_empty)

        layout.addWidget(log_card)

        # Protections Controls Card
        ctrl_card = QFrame(self)
        ctrl_card.setStyleSheet("background-color: #1a1e2b; border-radius: 8px; padding: 10px;")
        c_layout = QVBoxLayout(ctrl_card)
        c_layout.setSpacing(10)

        # 1. Tracker & Ad Block mode
        self._chk_trackers = QCheckBox("Block Trackers & Ads", ctrl_card)
        self._chk_trackers.setChecked(self._privacy_manager.interceptor.enabled)
        self._chk_trackers.toggled.connect(self._toggle_tracker_blocking)
        c_layout.addWidget(self._chk_trackers)

        # 2. Anti-Fingerprinting
        af_active = (self._privacy_manager.anti_fingerprint.mode != FingerprintProtectionMode.DISABLED)
        self._chk_fingerprint = QCheckBox("Anti-Fingerprinting (Canvas / Audio / WebGL)", ctrl_card)
        self._chk_fingerprint.setChecked(af_active)
        self._chk_fingerprint.toggled.connect(self._toggle_fingerprinting)
        c_layout.addWidget(self._chk_fingerprint)

        # 3. Upgrade HTTP to HTTPS
        self._chk_https = QCheckBox("Enforce HTTPS-Only Mode", ctrl_card)
        self._chk_https.setChecked(self._privacy_manager.interceptor.https_only)
        self._chk_https.toggled.connect(self._toggle_https_only)
        c_layout.addWidget(self._chk_https)

        # 4. Block JavaScript
        self._chk_js = QCheckBox("Block JavaScript (Tor Safest Mode)", ctrl_card)
        self._chk_js.setChecked(self._privacy_manager.mode == BrowsingMode.SAFEST)
        self._chk_js.toggled.connect(self._toggle_javascript)
        c_layout.addWidget(self._chk_js)

        layout.addWidget(ctrl_card)

        # Actions
        btn_layout = QHBoxLayout()
        btn_arch = QPushButton("🏛️ Architecture Details", self)
        btn_arch.setStyleSheet(
            "background-color: #232734; border: 1px solid #333b4f; color: #cbd5e1; padding: 6px 12px; border-radius: 6px;"
        )
        btn_arch.clicked.connect(self._open_architecture_dialog)
        btn_layout.addWidget(btn_arch)

        btn_done = QPushButton("Done", self)
        btn_done.setObjectName("accent-btn")
        btn_done.clicked.connect(self.accept)
        btn_layout.addWidget(btn_done)

        layout.addLayout(btn_layout)

    def _update_master_button_style(self, checked: bool) -> None:
        if checked:
            self._chk_master.setText("SHIELDS UP")
            self._chk_master.setStyleSheet(
                "background-color: #065f46; color: #6ee7b7; border: 1px solid #10b981; font-weight: 700; padding: 6px 12px; border-radius: 6px;"
            )
        else:
            self._chk_master.setText("SHIELDS DOWN")
            self._chk_master.setStyleSheet(
                "background-color: #7f1d1d; color: #fecaca; border: 1px solid #ef4444; font-weight: 700; padding: 6px 12px; border-radius: 6px;"
            )

    def _toggle_master_shield(self) -> None:
        shields_up = self._chk_master.isChecked()
        self._update_master_button_style(shields_up)
        self._privacy_manager.interceptor.set_site_shields(self._host, shields_up)

    def _toggle_tracker_blocking(self, checked: bool) -> None:
        self._privacy_manager.interceptor.enabled = checked

    def _toggle_fingerprinting(self, checked: bool) -> None:
        mode = FingerprintProtectionMode.BALANCED if checked else FingerprintProtectionMode.DISABLED
        self._privacy_manager.anti_fingerprint.mode = mode

    def _toggle_https_only(self, checked: bool) -> None:
        self._privacy_manager.interceptor.https_only = checked

    def _toggle_javascript(self, checked: bool) -> None:
        if checked:
            self._privacy_manager.set_mode(BrowsingMode.SAFEST)
        else:
            self._privacy_manager.set_mode(BrowsingMode.PRIVATE)

    def _open_architecture_dialog(self) -> None:
        self.accept()
        dlg = SecurityArchitectureDialog(self._privacy_manager, self.parent())
        dlg.exec()


class SecurityArchitectureDialog(QDialog):
    """Full 4-Layer Security Architecture dialog implementing the recommended specification."""

    def __init__(self, privacy_manager: PrivacyManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._privacy_manager = privacy_manager
        self.setWindowTitle("Recommended Security Architecture — Grago")
        self.setMinimumSize(660, 680)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #0f1117;
                color: #e2e8f0;
            }
            QLabel {
                color: #cbd5e1;
            }
            """
        )
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        # Header
        header = QLabel("🛡️ 4-Layer Security Architecture", self)
        header.setStyleSheet("font-size: 18px; font-weight: 700; color: #38bdf8;")
        main_layout.addWidget(header)

        sub = QLabel(
            "Practical and strong isolation architecture combining process sandboxing, "
            "Brave-style shields, anti-fingerprinting, and Tor-style identity wiping.",
            self,
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #94a3b8; font-size: 12px;")
        main_layout.addWidget(sub)

        # Scroll Area for the 4 Layers
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(10)
        scroll_layout.setContentsMargins(0, 0, 8, 0)

        # ── Layer 1: User Interface (UI) ──────────────────────────────────
        card1 = self._build_layer_card(
            "1. User Interface (UI) Layer",
            "#38bdf8",
            [
                ("Address Bar", "Real-time HTTPS security badge, domain highlight, query normalizer"),
                ("Tab Management", "Lightweight sleeping tabs with idle-timeout memory conservation"),
                ("Shields Button", f"Brave Shields popover ({self._privacy_manager.interceptor.total_blocked} blocked)"),
                ("New Identity Button", "Tor-style zero-restart session wipe & fingerprint rotation (Ctrl+Shift+U)"),
            ],
        )
        scroll_layout.addWidget(card1)

        # ── Layer 2: Browser Core / Broker Process ────────────────────────
        card2 = self._build_layer_card(
            "2. Browser Core / Broker Process",
            "#818cf8",
            [
                ("Process Management", "Site-per-process isolation flags (--site-per-process, IsolateOrigins)"),
                ("Network Service", "Sandboxed network worker, Sec-GPC: 1, DNT: 1, Upgrade-Insecure-Requests"),
                ("Extension Manager", self._privacy_manager.extension_manager.get_status_summary()["Policy"]),
                ("Update Service", self._privacy_manager.update_service.update_status),
            ],
        )
        scroll_layout.addWidget(card2)

        # ── Layer 3: Renderer Process Isolation ───────────────────────────
        card3 = self._build_layer_card(
            "3. Renderer Process Isolation (Site A / Site B)",
            "#f472b6",
            [
                ("Site Isolation", "Dedicated isolated Chromium renderer processes for separate origins"),
                ("Sandboxing", "Strict OS sandbox enabled (--enable-sandbox)"),
                ("No File Access", "Local file access disallowed (--disallow-file-access-from-files)"),
                ("Limited Privileges", "No clipboard theft, no unauthorized popups, media requires gesture"),
            ],
        )
        scroll_layout.addWidget(card3)

        # ── Layer 4: Privacy & Security Layer ─────────────────────────────
        card4 = self._build_layer_card(
            "4. Privacy & Security Layer",
            "#34d399",
            [
                ("Built-in Tracker / Ad Blocker", f"Blocking {len(self._privacy_manager.get_privacy_report())} active rules"),
                ("Anti-Fingerprinting", f"Active ({self._privacy_manager.anti_fingerprint.mode.name.title()} Seed: {self._privacy_manager.anti_fingerprint.session_seed})"),
                ("First-Party Containers", f"Context: {self._privacy_manager.container_manager.active_container.name} (Isolated cookies/storage)"),
                ("Strict CSP & HTTPS-Only", "Automatic HTTP to HTTPS upgrades with strict security headers"),
                ("Optional Tor / Proxy", self._privacy_manager.network_security.proxy_mode.value),
                ("Clear on Exit", "Automatic purge of memory cache, cookies & storage on browser exit"),
            ],
        )
        scroll_layout.addWidget(card4)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # Interactive controls card
        settings_frame = QFrame(self)
        settings_frame.setStyleSheet("background-color: #171b26; border: 1px solid #23293a; border-radius: 8px; padding: 10px;")
        sf_layout = QVBoxLayout(settings_frame)
        sf_layout.setSpacing(8)

        # Proxy / Tor Selector
        p_row = QHBoxLayout()
        lbl_proxy = QLabel("Network Proxy Mode:", settings_frame)
        lbl_proxy.setStyleSheet("font-weight: 600; color: #e2e8f0; font-size: 12px; background: transparent;")
        self._combo_proxy = QComboBox(settings_frame)
        self._combo_proxy.addItem("Direct Connection", ProxyMode.DIRECT)
        self._combo_proxy.addItem("Tor Network (SOCKS5 127.0.0.1:9050)", ProxyMode.TOR)
        self._combo_proxy.setCurrentIndex(1 if self._privacy_manager.network_security.proxy_mode == ProxyMode.TOR else 0)
        self._combo_proxy.currentIndexChanged.connect(self._on_proxy_changed)
        p_row.addWidget(lbl_proxy)
        p_row.addStretch()
        p_row.addWidget(self._combo_proxy)
        sf_layout.addLayout(p_row)

        # Clear on Exit Checkbox
        self._chk_exit_clear = QCheckBox("Clear all cookies and cache automatically on browser exit", settings_frame)
        self._chk_exit_clear.setChecked(self._privacy_manager.network_security.clear_on_exit)
        self._chk_exit_clear.toggled.connect(lambda val: setattr(self._privacy_manager.network_security, "clear_on_exit", val))
        sf_layout.addWidget(self._chk_exit_clear)

        main_layout.addWidget(settings_frame)

        # Action Buttons
        btn_row = QHBoxLayout()

        btn_wipe = QPushButton("🗑️ Flush Session & Cookies Now", self)
        btn_wipe.setStyleSheet("background-color: #7f1d1d; border: 1px solid #dc2626; color: #fecaca; font-weight: 600; padding: 7px 12px; border-radius: 6px;")
        btn_wipe.clicked.connect(self._on_flush_clicked)
        btn_row.addWidget(btn_wipe)

        btn_rotate_seed = QPushButton("🔄 Rotate Seed", self)
        btn_rotate_seed.setStyleSheet("background-color: #1e1b4b; border: 1px solid #4f46e5; color: #c7d2fe; font-weight: 600; padding: 7px 12px; border-radius: 6px;")
        btn_rotate_seed.clicked.connect(self._on_rotate_seed)
        btn_row.addWidget(btn_rotate_seed)

        btn_check_updates = QPushButton("🔍 Check Updates", self)
        btn_check_updates.setStyleSheet("background-color: #172554; border: 1px solid #2563eb; color: #bfdbfe; font-weight: 600; padding: 7px 12px; border-radius: 6px;")
        btn_check_updates.clicked.connect(self._on_check_updates)
        btn_row.addWidget(btn_check_updates)

        btn_close = QPushButton("Done", self)
        btn_close.setObjectName("accent-btn")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        main_layout.addLayout(btn_row)

    def _build_layer_card(self, title: str, color: str, items: List[Tuple[str, str]]) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"background-color: #161924; border: 1px solid #24293a; border-left: 3px solid {color}; border-radius: 8px; padding: 10px;"
        )
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(6)
        c_layout.setContentsMargins(8, 8, 8, 8)

        lbl_t = QLabel(title, card)
        lbl_t.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {color}; background: transparent;")
        c_layout.addWidget(lbl_t)

        for k, v in items:
            row = QHBoxLayout()
            lbl_k = QLabel(f"• {k}:", card)
            lbl_k.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 500; background: transparent;")
            lbl_v = QLabel(v, card)
            lbl_v.setStyleSheet("color: #f1f5f9; font-size: 12px; background: transparent;")
            lbl_v.setWordWrap(True)
            row.addWidget(lbl_k)
            row.addSpacing(6)
            row.addWidget(lbl_v)
            row.addStretch()
            c_layout.addLayout(row)

        return card

    def _on_proxy_changed(self) -> None:
        mode = self._combo_proxy.currentData()
        self._privacy_manager.network_security.set_proxy_mode(mode)
        QMessageBox.information(
            self,
            "Proxy Configuration Updated",
            f"Network routing switched to: {mode.value}",
        )

    def _on_flush_clicked(self) -> None:
        self._privacy_manager.clear_session_data()
        QMessageBox.information(
            self,
            "Session Cleared",
            "In-memory HTTP cache, cookies, and visited link records have been completely purged.",
        )

    def _on_rotate_seed(self) -> None:
        new_seed = self._privacy_manager.anti_fingerprint.regenerate_seed()
        QMessageBox.information(
            self,
            "Anti-Fingerprint Seed Rotated",
            f"A fresh random noise seed ({new_seed}) has been generated and applied to the anti-fingerprinting shields.",
        )

    def _on_check_updates(self) -> None:
        has_update, msg = self._privacy_manager.update_service.check_for_updates()
        QMessageBox.information(
            self,
            "Security Update Status",
            msg,
        )


PrivacyDialog = SecurityArchitectureDialog


class BookmarksDialog(QDialog):
    """Manager dialog for saved bookmarks stored in SQLite."""

    def __init__(
        self,
        storage: StorageManager,
        parent: Optional[QWidget] = None,
        open_callback=None,
    ) -> None:
        super().__init__(parent)
        self._storage = storage
        self._open_callback = open_callback

        self.setWindowTitle("Bookmarks — LeanBrowse")
        self.resize(680, 440)
        self.setStyleSheet("""
            QDialog {
                background-color: #131620;
                color: #e2e8f0;
            }
            QLabel {
                color: #cbd5e1;
            }
            QLineEdit#bm-search {
                background-color: #171922;
                border: 1px solid #2e3447;
                border-radius: 6px;
                padding: 6px 12px;
                color: #f8fafc;
                font-size: 13px;
            }
            QLineEdit#bm-search:focus {
                border-color: #3b82f6;
            }
        """)
        self._setup_ui()
        self._load_bookmarks()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        # Header card
        header = QFrame(self)
        header.setStyleSheet("background-color: #1a1e2b; border-radius: 8px; padding: 6px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 10, 12, 10)

        lbl_icon = QLabel("🔖", header)
        lbl_icon.setStyleSheet("font-size: 24px; background: transparent;")
        h_layout.addWidget(lbl_icon)

        v_head = QVBoxLayout()
        v_head.setSpacing(2)
        lbl_title = QLabel("Bookmarks Manager", header)
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #f8fafc; background: transparent;")
        lbl_desc = QLabel("Organize and search your saved sites (stored locally in SQLite).", header)
        lbl_desc.setStyleSheet("font-size: 12px; color: #94a3b8; background: transparent;")
        v_head.addWidget(lbl_title)
        v_head.addWidget(lbl_desc)
        h_layout.addLayout(v_head)
        h_layout.addStretch()

        layout.addWidget(header)

        # Search bar
        self.search_input = QLineEdit(self)
        self.search_input.setObjectName("bm-search")
        self.search_input.setPlaceholderText("🔍  Search bookmarks by title or URL...")
        self.search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_input)

        # Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Title", "URL", "Date Added"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(0, 220)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.table)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_open = QPushButton("🌐 Open Selected", self)
        self.btn_open.setObjectName("accent-btn")
        self.btn_open.clicked.connect(self._open_selected)
        btn_row.addWidget(self.btn_open)

        self.btn_delete = QPushButton("🗑️ Delete", self)
        self.btn_delete.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.btn_delete)

        btn_row.addStretch()

        btn_close = QPushButton("Close", self)
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _load_bookmarks(self, search: str = "") -> None:
        bookmarks = self._storage.get_bookmarks(search)
        self.table.setRowCount(len(bookmarks))
        for row, bm in enumerate(bookmarks):
            item_title = QTableWidgetItem(bm["title"])
            item_title.setData(Qt.ItemDataRole.UserRole, bm["url"])
            item_title.setData(Qt.ItemDataRole.UserRole + 1, bm["id"])

            item_url = QTableWidgetItem(bm["url"])
            item_url.setForeground(QColor("#38bdf8"))

            item_date = QTableWidgetItem(str(bm.get("date_added", "")))
            item_date.setForeground(QColor("#94a3b8"))

            self.table.setItem(row, 0, item_title)
            self.table.setItem(row, 1, item_url)
            self.table.setItem(row, 2, item_date)

    def _on_search_changed(self, text: str) -> None:
        self._load_bookmarks(text)

    def _on_item_double_clicked(self, item: QTableWidgetItem) -> None:
        self._open_selected()

    def _open_selected(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                url = item.data(Qt.ItemDataRole.UserRole)
                if url and self._open_callback:
                    self._open_callback(url)
                    self.accept()

    def _delete_selected(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                bm_id = item.data(Qt.ItemDataRole.UserRole + 1)
                if bm_id:
                    self._storage.remove_bookmark(bm_id)
                    self._load_bookmarks(self.search_input.text())


class HistoryDialog(QDialog):
    """Manager dialog for browsing history stored in SQLite."""

    def __init__(
        self,
        storage: StorageManager,
        parent: Optional[QWidget] = None,
        open_callback=None,
    ) -> None:
        super().__init__(parent)
        self._storage = storage
        self._open_callback = open_callback

        self.setWindowTitle("History — LeanBrowse")
        self.resize(740, 480)
        self.setStyleSheet("""
            QDialog {
                background-color: #131620;
                color: #e2e8f0;
            }
            QLabel {
                color: #cbd5e1;
            }
            QLineEdit#hist-search {
                background-color: #171922;
                border: 1px solid #2e3447;
                border-radius: 6px;
                padding: 6px 12px;
                color: #f8fafc;
                font-size: 13px;
            }
            QLineEdit#hist-search:focus {
                border-color: #3b82f6;
            }
        """)
        self._setup_ui()
        self._load_history()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        # Header card
        header = QFrame(self)
        header.setStyleSheet("background-color: #1a1e2b; border-radius: 8px; padding: 6px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 10, 12, 10)

        lbl_icon = QLabel("🕒", header)
        lbl_icon.setStyleSheet("font-size: 24px; background: transparent;")
        h_layout.addWidget(lbl_icon)

        v_head = QVBoxLayout()
        v_head.setSpacing(2)
        lbl_title = QLabel("Browsing History", header)
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #f8fafc; background: transparent;")
        lbl_desc = QLabel("🔒 Private & Safest mode sessions are off-the-record and never recorded here.", header)
        lbl_desc.setStyleSheet("font-size: 12px; color: #a5b4fc; background: transparent;")
        v_head.addWidget(lbl_title)
        v_head.addWidget(lbl_desc)
        h_layout.addLayout(v_head)
        h_layout.addStretch()

        layout.addWidget(header)

        # Search bar
        self.search_input = QLineEdit(self)
        self.search_input.setObjectName("hist-search")
        self.search_input.setPlaceholderText("🔍  Search history by title or URL...")
        self.search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_input)

        # Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Visit Time", "Title", "URL"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 240)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.table)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_open = QPushButton("🌐 Open Selected", self)
        self.btn_open.setObjectName("accent-btn")
        self.btn_open.clicked.connect(self._open_selected)
        btn_row.addWidget(self.btn_open)

        self.btn_delete = QPushButton("🗑️ Delete Selected", self)
        self.btn_delete.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.btn_delete)

        self.btn_clear_all = QPushButton("🧹 Clear All History", self)
        self.btn_clear_all.clicked.connect(self._clear_all)
        btn_row.addWidget(self.btn_clear_all)

        btn_row.addStretch()

        btn_close = QPushButton("Close", self)
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _load_history(self, search: str = "") -> None:
        history = self._storage.get_history(search)
        self.table.setRowCount(len(history))
        for row, item in enumerate(history):
            item_date = QTableWidgetItem(str(item.get("visit_timestamp", "")))
            item_date.setForeground(QColor("#94a3b8"))
            item_date.setData(Qt.ItemDataRole.UserRole, item["url"])
            item_date.setData(Qt.ItemDataRole.UserRole + 1, item["id"])

            item_title = QTableWidgetItem(item["title"])
            item_url = QTableWidgetItem(item["url"])
            item_url.setForeground(QColor("#38bdf8"))

            self.table.setItem(row, 0, item_date)
            self.table.setItem(row, 1, item_title)
            self.table.setItem(row, 2, item_url)

    def _on_search_changed(self, text: str) -> None:
        self._load_history(text)

    def _on_item_double_clicked(self, item: QTableWidgetItem) -> None:
        self._open_selected()

    def _open_selected(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                url = item.data(Qt.ItemDataRole.UserRole)
                if url and self._open_callback:
                    self._open_callback(url)
                    self.accept()

    def _delete_selected(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                hist_id = item.data(Qt.ItemDataRole.UserRole + 1)
                if hist_id:
                    self._storage.delete_history_item(hist_id)
                    self._load_history(self.search_input.text())

    def _clear_all(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Are you sure you want to delete your entire browsing history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._storage.clear_history()
            self._load_history()


class SettingsDialog(QDialog):
    """Browser settings dialog managing SQLite-backed configuration."""

    def __init__(
        self,
        storage: StorageManager,
        parent: Optional[QWidget] = None,
        on_saved=None,
    ) -> None:
        super().__init__(parent)
        self._storage = storage
        self._on_saved = on_saved

        self.setWindowTitle("Settings — LeanBrowse")
        self.resize(600, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #131620;
                color: #e2e8f0;
            }
            QLabel {
                color: #cbd5e1;
            }
            QLineEdit {
                background-color: #171922;
                border: 1px solid #2e3447;
                border-radius: 6px;
                padding: 6px 12px;
                color: #f8fafc;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        self._setup_ui()
        self._load_values()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        # Tabs
        self.tab_widget = QTabWidget(self)

        # Tab 1: General
        tab_general = QWidget()
        v_gen = QVBoxLayout(tab_general)
        v_gen.setSpacing(12)
        v_gen.setContentsMargins(14, 14, 14, 14)

        lbl_home = QLabel("Homepage URL:", tab_general)
        lbl_home.setStyleSheet("font-weight: 600;")
        v_gen.addWidget(lbl_home)
        self.inp_homepage = QLineEdit(tab_general)
        v_gen.addWidget(self.inp_homepage)

        lbl_se = QLabel("Default Search Engine:", tab_general)
        lbl_se.setStyleSheet("font-weight: 600; margin-top: 8px;")
        v_gen.addWidget(lbl_se)
        self.combo_engine = QComboBox(tab_general)
        self.combo_engine.addItem("Google", "https://www.google.com/search?q={query}")
        self.combo_engine.addItem("DuckDuckGo", "https://duckduckgo.com/?q={query}")
        self.combo_engine.addItem("Brave Search", "https://search.brave.com/search?q={query}")
        self.combo_engine.addItem("Bing", "https://www.bing.com/search?q={query}")
        self.combo_engine.addItem("Startpage", "https://www.startpage.com/sp/search?query={query}")
        self.combo_engine.currentIndexChanged.connect(self._on_engine_changed)
        v_gen.addWidget(self.combo_engine)

        lbl_tmpl = QLabel("Search URL Template:", tab_general)
        lbl_tmpl.setStyleSheet("font-weight: 600; margin-top: 8px;")
        v_gen.addWidget(lbl_tmpl)
        self.inp_template = QLineEdit(tab_general)
        v_gen.addWidget(self.inp_template)

        self.chk_restore_session = QCheckBox("Restore open tabs from previous session on launch", tab_general)
        self.chk_restore_session.setStyleSheet("margin-top: 10px;")
        v_gen.addWidget(self.chk_restore_session)

        v_gen.addStretch()
        self.tab_widget.addTab(tab_general, "🌐 General")

        # Tab 2: Performance & Privacy
        tab_privacy = QWidget()
        v_priv = QVBoxLayout(tab_privacy)
        v_priv.setSpacing(12)
        v_priv.setContentsMargins(14, 14, 14, 14)

        lbl_sleep = QLabel("Background Tab Sleep Timeout:", tab_privacy)
        lbl_sleep.setStyleSheet("font-weight: 600;")
        v_priv.addWidget(lbl_sleep)
        self.combo_sleep = QComboBox(tab_privacy)
        self.combo_sleep.addItem("30 seconds (Demo)", "30")
        self.combo_sleep.addItem("1 minute", "60")
        self.combo_sleep.addItem("3 minutes (Recommended)", "180")
        self.combo_sleep.addItem("5 minutes", "300")
        self.combo_sleep.addItem("10 minutes", "600")
        self.combo_sleep.addItem("Disabled", "0")
        v_priv.addWidget(self.combo_sleep)

        lbl_mode = QLabel("Default Browsing Mode on Launch:", tab_privacy)
        lbl_mode.setStyleSheet("font-weight: 600; margin-top: 8px;")
        v_priv.addWidget(lbl_mode)
        self.combo_mode = QComboBox(tab_privacy)
        self.combo_mode.addItem("⚡ Lean Mode (Tracker blocking + Tab sleeping)", "lean")
        self.combo_mode.addItem("🔒 Private Mode (Strict cookies + Anti-fingerprinting)", "private")
        self.combo_mode.addItem("🛡️ Safest Mode (No JavaScript, No WebGL)", "safest")
        v_priv.addWidget(self.combo_mode)

        lbl_priv_note = QLabel(
            "Note: LeanBrowse enforces off-the-record WebEngine profiles and never writes private session data to disk.",
            tab_privacy,
        )
        lbl_priv_note.setWordWrap(True)
        lbl_priv_note.setStyleSheet("color: #94a3b8; font-size: 11px; margin-top: 12px;")
        v_priv.addWidget(lbl_priv_note)

        v_priv.addStretch()
        self.tab_widget.addTab(tab_privacy, "🛡️ Privacy & Memory")

        # Tab 3: SQLite Storage
        tab_storage = QWidget()
        v_stor = QVBoxLayout(tab_storage)
        v_stor.setSpacing(10)
        v_stor.setContentsMargins(14, 14, 14, 14)

        card_stor = QFrame(tab_storage)
        card_stor.setStyleSheet("background-color: #1a1e2b; border-radius: 8px; padding: 10px;")
        v_card = QVBoxLayout(card_stor)
        v_card.setSpacing(6)

        self.lbl_db_path = QLabel(f"<b>Database Location:</b> {self._storage.db_path}", card_stor)
        self.lbl_db_path.setWordWrap(True)
        self.lbl_db_size = QLabel(f"<b>File Size:</b> {self._storage.get_db_size_kb()} KB", card_stor)
        self.lbl_hist_count = QLabel(f"<b>History Entries:</b> {self._storage.get_history_count()}", card_stor)
        self.lbl_bm_count = QLabel(f"<b>Bookmarks Count:</b> {len(self._storage.get_bookmarks())}", card_stor)

        v_card.addWidget(self.lbl_db_path)
        v_card.addWidget(self.lbl_db_size)
        v_card.addWidget(self.lbl_hist_count)
        v_card.addWidget(self.lbl_bm_count)
        v_stor.addWidget(card_stor)

        btn_clear_hist = QPushButton("🧹 Clear Browsing History", tab_storage)
        btn_clear_hist.clicked.connect(self._clear_hist_from_settings)
        v_stor.addWidget(btn_clear_hist)

        v_stor.addStretch()
        self.tab_widget.addTab(tab_storage, "💾 SQLite Storage")

        layout.addWidget(self.tab_widget)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self.btn_save = QPushButton("Save Settings", self)
        self.btn_save.setObjectName("accent-btn")
        self.btn_save.clicked.connect(self._save_settings)
        btn_row.addWidget(self.btn_save)

        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        layout.addLayout(btn_row)

    def _load_values(self) -> None:
        self.inp_homepage.setText(self._storage.get_setting("homepage", DEFAULT_HOME_URL))
        engine = self._storage.get_setting("search_engine", "Google")
        idx = self.combo_engine.findText(engine)
        if idx >= 0:
            self.combo_engine.setCurrentIndex(idx)
        self.inp_template.setText(
            self._storage.get_setting("search_url_template", "https://www.google.com/search?q={query}")
        )
        self.chk_restore_session.setChecked(
            self._storage.get_setting("restore_session_on_startup", "0") == "1"
        )
        sleep_sec = self._storage.get_setting("idle_timeout_seconds", "180")
        s_idx = self.combo_sleep.findData(sleep_sec)
        if s_idx >= 0:
            self.combo_sleep.setCurrentIndex(s_idx)
        def_mode = self._storage.get_setting("default_mode", "lean")
        m_idx = self.combo_mode.findData(def_mode)
        if m_idx >= 0:
            self.combo_mode.setCurrentIndex(m_idx)

    def _on_engine_changed(self, index: int) -> None:
        data = self.combo_engine.itemData(index)
        if data:
            self.inp_template.setText(str(data))

    def _clear_hist_from_settings(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Clear all browsing history from the database?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._storage.clear_history()
            self.lbl_hist_count.setText("<b>History Entries:</b> 0")

    def _save_settings(self) -> None:
        self._storage.set_setting("homepage", self.inp_homepage.text().strip())
        self._storage.set_setting("search_engine", self.combo_engine.currentText())
        self._storage.set_setting("search_url_template", self.inp_template.text().strip())
        self._storage.set_setting("restore_session_on_startup", "1" if self.chk_restore_session.isChecked() else "0")
        self._storage.set_setting("idle_timeout_seconds", str(self.combo_sleep.currentData()))
        self._storage.set_setting("default_mode", str(self.combo_mode.currentData()))
        if self._on_saved:
            self._on_saved()
        self.accept()


class AboutDialog(QDialog):
    """About dialog describing LeanBrowse architecture and features."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About LeanBrowse")
        self.setFixedSize(460, 380)
        self.setStyleSheet("""
            QDialog {
                background-color: #131620;
                color: #e2e8f0;
                border-radius: 10px;
            }
            QLabel {
                color: #cbd5e1;
            }
        """)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        card = QFrame(self)
        card.setStyleSheet("background-color: #1a1e2b; border-radius: 8px; padding: 12px;")
        v_card = QVBoxLayout(card)
        v_card.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_card.setSpacing(6)

        lbl_logo = QLabel("🌐⚡", card)
        lbl_logo.setStyleSheet("font-size: 36px; background: transparent;")
        lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_card.addWidget(lbl_logo)

        lbl_title = QLabel("LeanBrowse", card)
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 700; color: #f8fafc; background: transparent;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_card.addWidget(lbl_title)

        lbl_ver = QLabel("Version 1.0.0 — Privacy-First & Low Memory", card)
        lbl_ver.setStyleSheet("font-size: 12px; color: #38bdf8; background: transparent;")
        lbl_ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_card.addWidget(lbl_ver)

        layout.addWidget(card)

        lbl_body = QLabel(
            "Built with Python 3, PySide6, and Qt WebEngine.<br><br>"
            "<b>Key Highlights:</b><br>"
            "• Built-in Ad & Tracker Shield (Brave Shields architecture)<br>"
            "• Canvas & Audio Anti-Fingerprinting randomization<br>"
            "• Automated Background Tab Hibernation for minimal RAM usage<br>"
            "• SQLite-backed local persistence for Bookmarks, History & Settings<br>"
            "• Strong Process Isolation with Site-per-Process sandboxing",
            self,
        )
        lbl_body.setWordWrap(True)
        lbl_body.setStyleSheet("font-size: 12px; color: #94a3b8; line-height: 1.4;")
        layout.addWidget(lbl_body)

        btn_close = QPushButton("Close", self)
        btn_close.setObjectName("accent-btn")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


PrivacyDialog = SecurityArchitectureDialog


class GragoWindow(QMainWindow):
    """Main window for the Grago browser application."""

    def __init__(self, start_url: Optional[str] = None) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 800)
        self.setStyleSheet(DARK_STYLESHEET)

        # Managers
        self._privacy_manager = PrivacyManager(self)
        self._memory_manager = TabMemoryManager(idle_timeout_seconds=IDLE_TIMEOUT_SECONDS)
        self._storage = StorageManager()
        self._start_url = start_url or self._storage.get_setting("homepage", DEFAULT_HOME_URL)
        self._tab_counter = 0

        # Wire interceptor real-time blocked count signals
        self._privacy_manager.interceptor.blocked_count_changed.connect(self._on_blocked_count_changed)
        self._privacy_manager.interceptor.site_blocked_count_changed.connect(self._on_site_blocked_count_changed)

        self._setup_ui()
        self._setup_shortcuts()
        self._setup_timers()

        # Check session restoration setting
        restored = False
        if self._storage.get_setting("restore_session_on_startup", "0") == "1":
            saved = self._storage.get_saved_session()
            if saved:
                for item in saved:
                    u = item.get("url")
                    if u:
                        self.add_new_tab(QUrl(u))
                        restored = True
        if not restored:
            # Open initial tab as the new-tab page (fast startup — no web request on launch)
            self.add_new_tab()

    def _setup_ui(self) -> None:
        """Assemble main layout, toolbar, tabs, and status bar."""
        # Main central widget
        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Navigation Toolbar
        toolbar = QToolBar("Navigation", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.btn_back = QPushButton("◀", self)
        self.btn_back.setToolTip("Back (Alt+Left)")
        self.btn_back.clicked.connect(self._navigate_back)
        toolbar.addWidget(self.btn_back)

        self.btn_forward = QPushButton("▶", self)
        self.btn_forward.setToolTip("Forward (Alt+Right)")
        self.btn_forward.clicked.connect(self._navigate_forward)
        toolbar.addWidget(self.btn_forward)

        self.btn_reload = QPushButton("🔄", self)
        self.btn_reload.setToolTip("Reload (Ctrl+R / F5)")
        self.btn_reload.clicked.connect(self._reload_page)
        toolbar.addWidget(self.btn_reload)

        self.btn_home = QPushButton("🏠", self)
        self.btn_home.setToolTip("Home")
        self.btn_home.clicked.connect(self._navigate_home)
        toolbar.addWidget(self.btn_home)

        # Security Padlock / Status Indicator
        self.btn_security_indicator = QPushButton("🔒", self)
        self.btn_security_indicator.setObjectName("security-badge-btn")
        self.btn_security_indicator.setToolTip("Connection Security (Click for Brave Shields)")
        self.btn_security_indicator.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_security_indicator.clicked.connect(self._show_shields_flyout)
        toolbar.addWidget(self.btn_security_indicator)

        # Address / Search Bar
        self.url_bar = QLineEdit(self)
        self.url_bar.setObjectName("url-bar")
        self.url_bar.setPlaceholderText("Search or enter web address...")
        self.url_bar.setClearButtonEnabled(True)
        self.url_bar.returnPressed.connect(self._navigate_to_input)
        self.url_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        toolbar.addWidget(self.url_bar)

        # Brave Shields Button
        self.btn_shields = QPushButton("🛡️ Shields", self)
        self.btn_shields.setObjectName("shield-btn")
        self.btn_shields.setToolTip("Brave Shields: Tracker & ad blocking, anti-fingerprinting (Ctrl+Shift+B)")
        self.btn_shields.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_shields.clicked.connect(self._show_shields_flyout)
        toolbar.addWidget(self.btn_shields)

        # Tor New Identity Button
        self.btn_new_identity = QPushButton("✨ New Identity", self)
        self.btn_new_identity.setObjectName("identity-btn")
        self.btn_new_identity.setToolTip("Tor New Identity: Wipe cookies, cache & rotate seed (Ctrl+Shift+U)")
        self.btn_new_identity.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_identity.clicked.connect(self._trigger_new_identity)
        toolbar.addWidget(self.btn_new_identity)

        # Sleep threshold selector
        self.combo_timeout = QComboBox(self)
        self.combo_timeout.addItem("Sleep: 30s (Demo)", 30)
        self.combo_timeout.addItem("Sleep: 1 min", 60)
        self.combo_timeout.addItem("Sleep: 3 min (Default)", 180)
        self.combo_timeout.addItem("Sleep: 5 min", 300)
        self.combo_timeout.addItem("Sleep: 10 min", 600)
        self.combo_timeout.addItem("Sleep: Disabled", 0)
        self.combo_timeout.setCurrentIndex(2)  # 3 min default
        self.combo_timeout.currentIndexChanged.connect(self._on_timeout_changed)
        self.combo_timeout.setToolTip("Select inactive duration before tab is put to sleep")
        toolbar.addWidget(self.combo_timeout)

        # Instant Hibernate Button
        self.btn_sleep_bg = QPushButton("💤 Sleep Background", self)
        self.btn_sleep_bg.setObjectName("sleep-btn")
        self.btn_sleep_bg.setToolTip("Hibernate inactive tabs right now to free memory (Ctrl+Shift+S)")
        self.btn_sleep_bg.clicked.connect(self._hibernate_background_tabs)
        toolbar.addWidget(self.btn_sleep_bg)

        # ── Mode Switcher (Lean / Private / Safest) ──────────────────────
        mode_frame = QFrame(self)
        mode_frame.setObjectName("mode-frame")
        mode_frame.setStyleSheet("""
            QFrame#mode-frame {
                background-color: #0f1115;
                border: 1px solid #2e3447;
                border-radius: 8px;
                padding: 2px;
            }
        """)
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(2, 2, 2, 2)
        mode_layout.setSpacing(2)

        self.btn_mode_lean = QPushButton("⚡ Lean", self)
        self.btn_mode_lean.setObjectName("mode-lean-btn")
        self.btn_mode_lean.setToolTip("Lean Mode: tracker blocking, low memory (active)")
        self.btn_mode_lean.setCheckable(True)
        self.btn_mode_lean.setChecked(True)
        self.btn_mode_lean.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_lean.clicked.connect(lambda: self._set_mode(BrowsingMode.LEAN))
        mode_layout.addWidget(self.btn_mode_lean)

        self.btn_mode_private = QPushButton("🔒 Private", self)
        self.btn_mode_private.setObjectName("mode-private-btn")
        self.btn_mode_private.setToolTip("Private Mode: stricter cookie & JS policy, anti-fingerprinting")
        self.btn_mode_private.setCheckable(True)
        self.btn_mode_private.setChecked(False)
        self.btn_mode_private.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_private.clicked.connect(lambda: self._set_mode(BrowsingMode.PRIVATE))
        mode_layout.addWidget(self.btn_mode_private)

        self.btn_mode_safest = QPushButton("🛡️ Safest", self)
        self.btn_mode_safest.setObjectName("mode-safest-btn")
        self.btn_mode_safest.setToolTip("Safest Mode: JavaScript disabled, WebGL disabled, strict HTTPS (Tor 'Safest')")
        self.btn_mode_safest.setCheckable(True)
        self.btn_mode_safest.setChecked(False)
        self.btn_mode_safest.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_safest.clicked.connect(lambda: self._set_mode(BrowsingMode.SAFEST))
        mode_layout.addWidget(self.btn_mode_safest)

        toolbar.addWidget(mode_frame)

        # Architecture details button
        self.btn_privacy = QPushButton("🏛️ Architecture", self)
        self.btn_privacy.setObjectName("shield-btn")
        self.btn_privacy.setToolTip("View full 4-Layer Security Architecture & Telemetry")
        self.btn_privacy.clicked.connect(self._show_security_architecture_dialog)
        toolbar.addWidget(self.btn_privacy)

        # Wire interceptor count update
        self._privacy_manager.interceptor.blocked_count_changed.connect(self._on_blocked_count_changed)

        # Memory Indicator Badge
        self.lbl_memory = QLabel("⚡ Initializing...", self)
        self.lbl_memory.setObjectName("memory-badge")
        self.lbl_memory.setToolTip("Memory (RSS) consumed by Python app and child Chromium engines")
        toolbar.addWidget(self.lbl_memory)

        # ── Three-Dots Menu Button in the Right Side Corner ───────────────
        self.btn_menu = QPushButton("⋮", self)
        self.btn_menu.setObjectName("menu-btn")
        self.btn_menu.setToolTip("Customize and control LeanBrowse (Alt+F)")
        self.btn_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_menu.clicked.connect(self._show_main_menu)
        toolbar.addWidget(self.btn_menu)

        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.setVisible(False)
        root_layout.addWidget(self.progress_bar)

        # Tabs Widget
        self.tab_widget = QTabWidget(self)
        self.tab_widget.setTabsClosable(False)  # We manage close buttons ourselves
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)
        self.tab_widget.tabBarDoubleClicked.connect(self._on_tab_bar_double_clicked)

        # '+' New Tab button embedded in the tab bar corner
        self._btn_add_tab = QPushButton("+", self)
        self._btn_add_tab.setObjectName("tab-add-btn")
        self._btn_add_tab.setToolTip("New Tab (Ctrl+T)")
        self._btn_add_tab.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_add_tab.clicked.connect(lambda: self.add_new_tab())
        self.tab_widget.setCornerWidget(self._btn_add_tab, Qt.Corner.TopRightCorner)

        root_layout.addWidget(self.tab_widget)

        # Status Bar
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.lbl_tab_stats = QLabel("Tabs: 0", self)
        self.lbl_tab_stats.setStyleSheet("color: #94a3b8; font-size: 11px; margin-right: 12px;")
        self.status_bar.addPermanentWidget(self.lbl_tab_stats)

    def _setup_shortcuts(self) -> None:
        """Bind common browser keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+T"), self, lambda: self.add_new_tab())
        QShortcut(QKeySequence("Ctrl+W"), self, self._close_current_tab)
        QShortcut(QKeySequence("Ctrl+R"), self, self._reload_page)
        QShortcut(QKeySequence("F5"), self, self._reload_page)
        QShortcut(QKeySequence("Alt+Left"), self, self._navigate_back)
        QShortcut(QKeySequence("Alt+Right"), self, self._navigate_forward)
        QShortcut(QKeySequence("Ctrl+L"), self, self._focus_address_bar)
        QShortcut(QKeySequence("Alt+D"), self, self._focus_address_bar)
        QShortcut(QKeySequence("Ctrl+Tab"), self, self._next_tab)
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self, self._prev_tab)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self._hibernate_background_tabs)
        QShortcut(QKeySequence("Ctrl+Shift+Delete"), self, self._clear_browsing_data)
        QShortcut(QKeySequence("Ctrl+Shift+U"), self, self._trigger_new_identity)
        QShortcut(QKeySequence("Ctrl+Shift+B"), self, self._show_shields_flyout)

        # Menu and navigation shortcuts
        QShortcut(QKeySequence("Alt+F"), self, self._show_main_menu)
        QShortcut(QKeySequence("Alt+E"), self, self._show_main_menu)
        QShortcut(QKeySequence("Ctrl+D"), self, self._bookmark_current_page)
        QShortcut(QKeySequence("Ctrl+Shift+O"), self, self._show_bookmarks_dialog)
        QShortcut(QKeySequence("Ctrl+H"), self, self._show_history_dialog)
        QShortcut(QKeySequence("Ctrl+J"), self, self._show_downloads)
        QShortcut(QKeySequence("Ctrl+Plus"), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+="), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self._zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self._zoom_reset)
        QShortcut(QKeySequence("Ctrl+P"), self, self._print_page)
        QShortcut(QKeySequence("Ctrl+F"), self, self._find_in_page)
        QShortcut(QKeySequence("Ctrl+N"), self, self._open_new_window)
        QShortcut(QKeySequence("Ctrl+Shift+P"), self, self._open_private_tab)

    def _setup_timers(self) -> None:
        """Start memory monitoring and tab idle checkers."""
        # Memory stats refresher
        self.memory_timer = QTimer(self)
        self.memory_timer.timeout.connect(self._update_memory_indicator)
        self.memory_timer.start(MEMORY_REFRESH_MS)

        # Tab inactivity checker
        self.idle_timer = QTimer(self)
        self.idle_timer.timeout.connect(self._check_tab_inactivity)
        self.idle_timer.start(IDLE_CHECK_MS)

    def add_new_tab(self, url: Optional[QUrl] = None) -> BrowserTabItem:
        """Create and append a new browser tab."""
        self._tab_counter += 1
        tab_id = f"tab_{self._tab_counter}"

        # None / sentinel → show new-tab page; otherwise load the given URL
        is_new_tab_page = url is None or url.toString() == NEW_TAB_SENTINEL
        target_url = QUrl(NEW_TAB_SENTINEL) if is_new_tab_page else url

        tab_item = BrowserTabItem(
            tab_id=tab_id,
            profile=self._privacy_manager.profile,
            initial_url=target_url,
            idle_seconds=self._memory_manager.idle_timeout_seconds,
            nav_callback=self._navigate_from_new_tab,
            parent=self.tab_widget,
        )

        # Wire tab signals
        tab_item.title_changed.connect(lambda t, item=tab_item: self._on_tab_title_changed(item, t))
        tab_item.url_changed.connect(lambda u, item=tab_item: self._on_tab_url_changed(item, u))
        tab_item.load_progress.connect(self._on_load_progress)
        tab_item.load_finished.connect(lambda ok, item=tab_item: self._on_load_finished(item, ok))
        tab_item.link_hovered.connect(self._on_link_hovered)
        tab_item.wake_requested.connect(lambda item=tab_item: self._on_tab_woken(item))

        index = self.tab_widget.addTab(tab_item, "New Tab")
        self.tab_widget.setCurrentIndex(index)
        self._apply_tab_close_button(index)

        # Register with memory manager
        self._memory_manager.register_tab(
            tab_id=tab_id,
            title="New Tab",
            url=target_url.toString(),
        )

        self._update_tab_stats()
        return tab_item

    def _navigate_from_new_tab(self, text: str) -> None:
        """Called when user searches/navigates from the new-tab page."""
        target_url = normalize_url(text, default_home=self._start_url)
        tab = self._current_tab_item()
        if tab:
            tab.load(target_url)
            self.url_bar.setText(target_url.toString())

    def _set_mode(self, mode: BrowsingMode) -> None:
        """Switch browsing mode and update toolbar button states."""
        self._privacy_manager.set_mode(mode)
        self.btn_mode_lean.setChecked(mode == BrowsingMode.LEAN)
        self.btn_mode_private.setChecked(mode == BrowsingMode.PRIVATE)
        self.btn_mode_safest.setChecked(mode == BrowsingMode.SAFEST)

        if mode == BrowsingMode.LEAN:
            label = "Lean Mode ⚡"
        elif mode == BrowsingMode.PRIVATE:
            label = "Private Mode 🔒"
        else:
            label = "Safest Mode 🛡️ (JavaScript Disabled)"

        self._update_security_indicator()
        self.status_bar.showMessage(f"Switched to {label} — applies to new tabs.", 4000)

    def _apply_tab_close_button(self, index: int) -> None:
        """Replace the default close button with a styled × button."""
        close_btn = QPushButton("×", self)
        close_btn.setObjectName("tab-close-btn")
        close_btn.setToolTip("Close Tab")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(lambda checked, idx=index: self._close_tab_by_btn(close_btn))
        self.tab_widget.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, close_btn)

    def _current_tab_item(self) -> Optional[BrowserTabItem]:
        """Return the currently selected tab widget."""
        widget = self.tab_widget.currentWidget()
        if isinstance(widget, BrowserTabItem):
            return widget
        return None

    def _on_tab_changed(self, index: int) -> None:
        """Handle active tab switch."""
        tab = self._current_tab_item()
        if not tab:
            return

        # Touch memory manager for active tab
        self._memory_manager.touch_tab(tab.tab_id)

        # If tab was hibernating, automatically wake it up
        if tab.is_sleeping:
            tab.wake()

        # Update address bar
        self.url_bar.setText(tab.url.toString())
        self._update_nav_buttons()
        self._update_tab_title(index, tab)
        self._update_tab_stats()
        self._update_security_indicator()
        self._update_shields_button_for_current_tab()

    def _on_tab_title_changed(self, tab: BrowserTabItem, title: str) -> None:
        index = self.tab_widget.indexOf(tab)
        if index >= 0:
            self._update_tab_title(index, tab)
            self._memory_manager.update_tab(tab.tab_id, title=title)

    def _on_tab_url_changed(self, tab: BrowserTabItem, url: QUrl) -> None:
        index = self.tab_widget.indexOf(tab)
        if tab == self._current_tab_item():
            self.url_bar.setText(url.toString())
            self._update_nav_buttons()
            self._update_security_indicator()
            self._update_shields_button_for_current_tab()
        self._memory_manager.update_tab(tab.tab_id, url=url.toString())

    def _on_load_progress(self, progress: int) -> None:
        if progress < 100:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(progress)
            self.btn_reload.setText("✕")
        else:
            self.progress_bar.setVisible(False)
            self.btn_reload.setText("🔄")

    def _on_load_finished(self, tab: BrowserTabItem, ok: bool) -> None:
        self.progress_bar.setVisible(False)
        self.btn_reload.setText("🔄")
        self._update_nav_buttons()
        self._update_shields_button_for_current_tab()

        # Record visited page in SQLite history (strictly in non-private mode)
        if ok and tab.url.isValid() and self._privacy_manager.mode == BrowsingMode.LEAN:
            u_str = tab.url.toString()
            if not u_str.startswith("grago://") and not u_str.startswith("about:"):
                self._storage.add_history(u_str, tab.title)

        # Check and apply YouTube-specific Ad & Streaming Shield
        if ok and tab.web_view and tab.url.isValid():
            host = tab.url.host()
            if self._privacy_manager.youtube_shield.is_youtube_host(host):
                script = self._privacy_manager.youtube_shield.generate_injection_script()
                tab.web_view.page().runJavaScript(script)

    def _on_link_hovered(self, link_text: str) -> None:
        if link_text:
            self.status_bar.showMessage(link_text)
        else:
            self.status_bar.clearMessage()

    def _on_tab_woken(self, tab: BrowserTabItem) -> None:
        self._memory_manager.touch_tab(tab.tab_id)
        index = self.tab_widget.indexOf(tab)
        if index >= 0:
            self._update_tab_title(index, tab)
        self._update_tab_stats()
        self._update_memory_indicator()

    def _update_tab_title(self, index: int, tab: BrowserTabItem) -> None:
        title = tab.title or "Untitled"
        if len(title) > 28:
            title = title[:25] + "..."
        if tab.is_sleeping:
            self.tab_widget.setTabText(index, f"💤 [Sleeping] {title}")
        else:
            self.tab_widget.setTabText(index, title)

    def _close_tab_by_btn(self, close_btn: QPushButton) -> None:
        """Find the tab whose close button was clicked and close it."""
        tab_bar = self.tab_widget.tabBar()
        for i in range(self.tab_widget.count()):
            btn = tab_bar.tabButton(i, QTabBar.ButtonPosition.RightSide)
            if btn is close_btn:
                self._on_tab_close_requested(i)
                return

    def _on_tab_close_requested(self, index: int) -> None:
        widget = self.tab_widget.widget(index)
        if isinstance(widget, BrowserTabItem):
            self._memory_manager.unregister_tab(widget.tab_id)
            widget.hibernate()  # releases web view
            widget.deleteLater()
        self.tab_widget.removeTab(index)

        if self.tab_widget.count() == 0:
            # If all tabs are closed, create a fresh new-tab page
            self.add_new_tab()

        self._update_tab_stats()
        self._update_memory_indicator()

    def _close_current_tab(self) -> None:
        idx = self.tab_widget.currentIndex()
        if idx >= 0:
            self._on_tab_close_requested(idx)

    def _on_tab_bar_double_clicked(self, index: int) -> None:
        if index == -1:  # clicked empty space
            self.add_new_tab()

    def _navigate_to_input(self) -> None:
        """Read text from address bar, normalize into a search query or URL, and load."""
        text = self.url_bar.text().strip()
        if not text:
            return
        tmpl = self._storage.get_setting("search_url_template", None)
        target_url = normalize_url(text, default_home=self._start_url, search_template=tmpl)
        tab = self._current_tab_item()
        if tab:
            tab.load(target_url)

    def _navigate_back(self) -> None:
        tab = self._current_tab_item()
        if tab and tab.web_view:
            tab.web_view.back()

    def _navigate_forward(self) -> None:
        tab = self._current_tab_item()
        if tab and tab.web_view:
            tab.web_view.forward()

    def _reload_page(self) -> None:
        tab = self._current_tab_item()
        if tab and tab.web_view:
            if self.progress_bar.isVisible():
                tab.web_view.stop()
            else:
                tab.web_view.reload()

    def _navigate_home(self) -> None:
        tab = self._current_tab_item()
        if tab:
            tab.load(QUrl(self._start_url))

    def _focus_address_bar(self) -> None:
        self.url_bar.setFocus()
        self.url_bar.selectAll()

    def _next_tab(self) -> None:
        count = self.tab_widget.count()
        if count > 1:
            self.tab_widget.setCurrentIndex((self.tab_widget.currentIndex() + 1) % count)

    def _prev_tab(self) -> None:
        count = self.tab_widget.count()
        if count > 1:
            self.tab_widget.setCurrentIndex((self.tab_widget.currentIndex() - 1) % count)

    def _update_nav_buttons(self) -> None:
        tab = self._current_tab_item()
        if tab and tab.web_view:
            history = tab.web_view.history()
            self.btn_back.setEnabled(history.canGoBack())
            self.btn_forward.setEnabled(history.canGoForward())
        else:
            self.btn_back.setEnabled(False)
            self.btn_forward.setEnabled(False)

    def _on_timeout_changed(self) -> None:
        timeout_seconds = self.combo_timeout.currentData()
        self._memory_manager.idle_timeout_seconds = timeout_seconds
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if isinstance(widget, BrowserTabItem):
                widget._idle_seconds = timeout_seconds

    def _check_tab_inactivity(self) -> None:
        """Periodically evaluate tabs against idle timeout and hibernate inactive ones."""
        current_tab = self._current_tab_item()
        active_id = current_tab.tab_id if current_tab else None

        tabs_to_unload = self._memory_manager.get_tabs_to_unload(active_id)
        for tab_id in tabs_to_unload:
            for i in range(self.tab_widget.count()):
                widget = self.tab_widget.widget(i)
                if isinstance(widget, BrowserTabItem) and widget.tab_id == tab_id:
                    widget.hibernate()
                    self._memory_manager.mark_unloaded(tab_id)
                    self._update_tab_title(i, widget)
                    break

        if tabs_to_unload:
            self._update_tab_stats()
            self._update_memory_indicator()

    def _hibernate_background_tabs(self) -> None:
        """Instant action: sleep all background tabs to immediately reclaim memory."""
        current_tab = self._current_tab_item()
        active_id = current_tab.tab_id if current_tab else None

        bg_tabs = self._memory_manager.get_inactive_background_tabs(active_id)
        if not bg_tabs:
            self.status_bar.showMessage("No background tabs to hibernate.", 3000)
            return

        for tab_id in bg_tabs:
            for i in range(self.tab_widget.count()):
                widget = self.tab_widget.widget(i)
                if isinstance(widget, BrowserTabItem) and widget.tab_id == tab_id:
                    widget.hibernate()
                    self._memory_manager.mark_unloaded(tab_id)
                    self._update_tab_title(i, widget)
                    break

        self._update_tab_stats()
        self._update_memory_indicator()
        self.status_bar.showMessage(
            f"Hibernated {len(bg_tabs)} background tab(s) to free memory.", 4000
        )

    def _update_memory_indicator(self) -> None:
        """Query psutil for process tree RSS and update badge."""
        stats = ResourceMonitor.get_memory_usage()
        text = f"⚡ {stats.total_mb:.1f} MB"
        self.lbl_memory.setText(text)
        tooltip = (
            f"Total RSS Memory: {stats.total_mb:.1f} MB\n"
            f"• Main Python App: {stats.main_mb:.1f} MB\n"
            f"• Chromium Child Engines: {stats.child_mb:.1f} MB ({stats.child_count} processes)"
        )
        self.lbl_memory.setToolTip(tooltip)

    def _update_tab_stats(self) -> None:
        """Update status bar tab counter."""
        stats = self._memory_manager.get_stats()
        self.lbl_tab_stats.setText(
            f"Tabs: {stats['total']}  |  Active: {stats['active']}  |  Sleeping: {stats['sleeping']}"
        )

    def _show_privacy_dialog(self) -> None:
        self._show_security_architecture_dialog()

    def _show_security_architecture_dialog(self) -> None:
        """Open the 4-layer security architecture and controls dialog."""
        dlg = SecurityArchitectureDialog(self._privacy_manager, self)
        dlg.exec()

    def _show_shields_flyout(self) -> None:
        """Open the Brave Shields popup flyout for the active tab."""
        tab = self._current_tab_item()
        url = tab.url if tab else QUrl()
        dlg = ShieldsFlyoutDialog(self._privacy_manager, url, self)
        dlg.exec()

    def _on_blocked_count_changed(self, count: int) -> None:
        """Dynamically update Brave Shields button label if no site-specific count is shown."""
        self._update_shields_button_for_current_tab()

    def _on_site_blocked_count_changed(self, host: str, count: int) -> None:
        """Dynamically update Brave Shields button label when requests on the active site are blocked."""
        tab = self._current_tab_item()
        if tab and tab.url.isValid() and not tab.url.isEmpty():
            curr_host = tab.url.host().lower().lstrip("www.")
            if curr_host == host.lower().lstrip("www."):
                if hasattr(self, "btn_shields"):
                    self.btn_shields.setText(f"🛡️ Shields ({count})")

    def _update_shields_button_for_current_tab(self) -> None:
        """Update Shields button text to reflect the actual blocked count for the current tab origin."""
        if not hasattr(self, "btn_shields"):
            return
        tab = self._current_tab_item()
        if tab and tab.url.isValid() and not tab.url.isEmpty():
            host = tab.url.host()
            site_count = self._privacy_manager.interceptor.get_site_blocked_count(host)
            if site_count > 0:
                self.btn_shields.setText(f"🛡️ Shields ({site_count})")
            else:
                self.btn_shields.setText("🛡️ Shields")
        else:
            self.btn_shields.setText("🛡️ Shields")

    def _trigger_new_identity(self) -> None:
        """Tor-style New Identity: resets sessions, wipes cache/cookies, rotates fingerprint seed."""
        reply = QMessageBox.question(
            self,
            "Tor New Identity",
            "This will close background tabs, wipe in-memory cookies and cache, "
            "rotate your anti-fingerprint seed, and create a fresh session.\n\n"
            "Do you wish to proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            # 1. Close background tabs
            while self.tab_widget.count() > 1:
                self._on_tab_close_requested(self.tab_widget.count() - 1)
            # 2. Reset active tab to new-tab page
            tab = self._current_tab_item()
            if tab:
                tab.load(QUrl(NEW_TAB_SENTINEL))
            # 3. Purge data & rotate anti-fingerprint seed
            self._privacy_manager.new_identity()
            self._on_blocked_count_changed(0)
            self._update_security_indicator()
            self.status_bar.showMessage("✨ New Identity Active: In-memory cache & cookies cleared, fresh seed assigned.", 5000)
            self._update_tab_stats()
            self._update_memory_indicator()

    def _update_security_indicator(self) -> None:
        """Update address bar security icon and tooltip based on connection security and mode."""
        if not hasattr(self, "btn_security_indicator"):
            return
        tab = self._current_tab_item()
        url = tab.url if tab else QUrl()
        mode = self._privacy_manager.mode

        if mode == BrowsingMode.SAFEST:
            self.btn_security_indicator.setText("🛡️")
            self.btn_security_indicator.setToolTip("Safest Mode Active: JavaScript & WebGL disabled, strict HTTPS")
            self.btn_security_indicator.setStyleSheet("color: #fb923c;")
        elif url.scheme() == "https":
            self.btn_security_indicator.setText("🔒")
            self.btn_security_indicator.setToolTip("Secure Connection (HTTPS)")
            self.btn_security_indicator.setStyleSheet("color: #34d399;")
        elif url.scheme() == "http":
            self.btn_security_indicator.setText("⚠️")
            self.btn_security_indicator.setToolTip("Insecure Connection (HTTP)")
            self.btn_security_indicator.setStyleSheet("color: #f87171;")
        else:
            self.btn_security_indicator.setText("🌐")
            self.btn_security_indicator.setToolTip("Local / Internal Page")
            self.btn_security_indicator.setStyleSheet("color: #38bdf8;")

    def _show_main_menu(self) -> None:
        """Pop up the main application menu below the three-dots button."""
        menu = QMenu(self)

        action_new_tab = menu.addAction("🗂️  New Tab")
        action_new_tab.setShortcut(QKeySequence("Ctrl+T"))
        action_new_tab.triggered.connect(lambda: self.add_new_tab())

        action_new_window = menu.addAction("🪟  New Window")
        action_new_window.setShortcut(QKeySequence("Ctrl+N"))
        action_new_window.triggered.connect(self._open_new_window)

        action_new_private = menu.addAction("🔒  New Private Tab")
        action_new_private.setShortcut(QKeySequence("Ctrl+Shift+P"))
        action_new_private.triggered.connect(self._open_private_tab)

        menu.addSeparator()

        # Bookmarks submenu
        bookmarks_menu = menu.addMenu("🔖  Bookmarks")
        action_add_bm = bookmarks_menu.addAction("⭐  Bookmark This Tab")
        action_add_bm.setShortcut(QKeySequence("Ctrl+D"))
        action_add_bm.triggered.connect(self._bookmark_current_page)

        action_show_bm = bookmarks_menu.addAction("📑  Show Bookmarks")
        action_show_bm.setShortcut(QKeySequence("Ctrl+Shift+O"))
        action_show_bm.triggered.connect(self._show_bookmarks_dialog)

        # History submenu
        history_menu = menu.addMenu("🕒  History")
        action_show_hist = history_menu.addAction("🕒  Show Full History")
        action_show_hist.setShortcut(QKeySequence("Ctrl+H"))
        action_show_hist.triggered.connect(self._show_history_dialog)

        action_clear_hist = history_menu.addAction("🧹  Clear Browsing Data...")
        action_clear_hist.setShortcut(QKeySequence("Ctrl+Shift+Delete"))
        action_clear_hist.triggered.connect(self._clear_browsing_data)

        action_downloads = menu.addAction("📥  Downloads")
        action_downloads.setShortcut(QKeySequence("Ctrl+J"))
        action_downloads.triggered.connect(self._show_downloads)

        menu.addSeparator()

        # Zoom submenu
        zoom_menu = menu.addMenu("🔍  Zoom")
        action_zoom_in = zoom_menu.addAction("➕  Zoom In")
        action_zoom_in.setShortcut(QKeySequence("Ctrl++"))
        action_zoom_in.triggered.connect(self._zoom_in)

        action_zoom_out = zoom_menu.addAction("➖  Zoom Out")
        action_zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        action_zoom_out.triggered.connect(self._zoom_out)

        action_zoom_reset = zoom_menu.addAction("↺  Reset Zoom (100%)")
        action_zoom_reset.setShortcut(QKeySequence("Ctrl+0"))
        action_zoom_reset.triggered.connect(self._zoom_reset)

        action_print = menu.addAction("📄  Print...")
        action_print.setShortcut(QKeySequence("Ctrl+P"))
        action_print.triggered.connect(self._print_page)

        action_find = menu.addAction("🔎  Find in Page...")
        action_find.setShortcut(QKeySequence("Ctrl+F"))
        action_find.triggered.connect(self._find_in_page)

        menu.addSeparator()

        action_shields = menu.addAction("🛡️  Brave Shields")
        action_shields.setShortcut(QKeySequence("Ctrl+Shift+B"))
        action_shields.triggered.connect(self._show_shields_flyout)

        action_sleep = menu.addAction("💤  Hibernate Inactive Tabs")
        action_sleep.setShortcut(QKeySequence("Ctrl+Shift+S"))
        action_sleep.triggered.connect(self._hibernate_background_tabs)

        action_tor = menu.addAction("✨  Tor New Identity")
        action_tor.setShortcut(QKeySequence("Ctrl+Shift+U"))
        action_tor.triggered.connect(self._trigger_new_identity)

        action_restore_session = menu.addAction("🔄  Restore Previous Session")
        action_restore_session.triggered.connect(self._restore_previous_session)

        menu.addSeparator()

        action_settings = menu.addAction("⚙️  Settings")
        action_settings.triggered.connect(self._show_settings_dialog)

        action_arch = menu.addAction("🏛️  Security Architecture & Telemetry")
        action_arch.triggered.connect(self._show_security_architecture_dialog)

        action_about = menu.addAction("ℹ️  About LeanBrowse")
        action_about.triggered.connect(self._show_about_dialog)

        menu.addSeparator()

        action_exit = menu.addAction("🚪  Exit")
        action_exit.setShortcut(QKeySequence("Ctrl+Q"))
        action_exit.triggered.connect(self.close)

        # Position menu right below the three-dots button aligned to its right edge
        pos = self.btn_menu.mapToGlobal(QPoint(self.btn_menu.width(), self.btn_menu.height()))
        pos.setX(pos.x() - menu.sizeHint().width())
        menu.exec(pos)

    def _bookmark_current_page(self) -> None:
        tab = self._current_tab_item()
        if not tab or not tab.url.isValid():
            return
        url_str = tab.url.toString()
        if url_str.startswith("grago://") or url_str.startswith("about:"):
            return
        title = tab.title or url_str
        self._storage.add_bookmark(title, url_str)
        self.status_bar.showMessage(f"⭐ Bookmarked: {title}", 3500)

    def _show_bookmarks_dialog(self) -> None:
        dialog = BookmarksDialog(self._storage, self, open_callback=self._navigate_url_from_dialog)
        dialog.exec()

    def _show_history_dialog(self) -> None:
        dialog = HistoryDialog(self._storage, self, open_callback=self._navigate_url_from_dialog)
        dialog.exec()

    def _navigate_url_from_dialog(self, url_str: str) -> None:
        current = self._current_tab_item()
        if current:
            current.load(QUrl(url_str))
        else:
            self.add_new_tab(QUrl(url_str))

    def _clear_browsing_data(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear Browsing Data",
            "Clear browsing history and purge all session cache?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._storage.clear_history()
            self._privacy_manager.clear_session_data()
            self.status_bar.showMessage("🧹 Browsing data and cache cleared.", 3500)

    def _show_downloads(self) -> None:
        downloads_path = os.path.expanduser("~/Downloads")
        os.makedirs(downloads_path, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(downloads_path))

    def _zoom_in(self) -> None:
        tab = self._current_tab_item()
        if tab and tab.web_view:
            new_zoom = round(min(3.0, tab.web_view.zoomFactor() + 0.1), 2)
            tab.web_view.setZoomFactor(new_zoom)
            self.status_bar.showMessage(f"🔍 Zoom: {int(new_zoom * 100)}%", 2000)

    def _zoom_out(self) -> None:
        tab = self._current_tab_item()
        if tab and tab.web_view:
            new_zoom = round(max(0.25, tab.web_view.zoomFactor() - 0.1), 2)
            tab.web_view.setZoomFactor(new_zoom)
            self.status_bar.showMessage(f"🔍 Zoom: {int(new_zoom * 100)}%", 2000)

    def _zoom_reset(self) -> None:
        tab = self._current_tab_item()
        if tab and tab.web_view:
            tab.web_view.setZoomFactor(1.0)
            self.status_bar.showMessage("🔍 Zoom: 100%", 2000)

    def _print_page(self) -> None:
        tab = self._current_tab_item()
        if tab and tab.web_view:
            pdf_path = os.path.join(os.path.expanduser("~"), "Downloads", f"LeanBrowse_Print_{int(time.time())}.pdf")
            try:
                os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
                tab.web_view.page().printToPdf(pdf_path)
                self.status_bar.showMessage(f"📄 Page saved as PDF: {pdf_path}", 4000)
            except Exception as e:
                self.status_bar.showMessage(f"Print error: {e}", 3000)

    def _find_in_page(self) -> None:
        tab = self._current_tab_item()
        if not tab or not tab.web_view:
            return
        text, ok = QInputDialog.getText(self, "Find in Page", "Enter text to find:")
        if ok and text:
            tab.web_view.findText(text)

    def _open_new_window(self) -> None:
        new_win = GragoWindow(start_url=self._start_url)
        new_win.show()
        if not hasattr(self, "_child_windows"):
            self._child_windows = []
        self._child_windows.append(new_win)

    def _open_private_tab(self) -> None:
        self.add_new_tab()
        self._set_mode(BrowsingMode.PRIVATE)

    def _restore_previous_session(self) -> None:
        saved_tabs = self._storage.get_saved_session()
        if not saved_tabs:
            self.status_bar.showMessage("No saved session found in database.", 3000)
            return
        active_idx = 0
        for idx, tab_info in enumerate(saved_tabs):
            u_str = tab_info.get("url")
            if u_str:
                self.add_new_tab(QUrl(u_str))
                if tab_info.get("is_active"):
                    active_idx = self.tab_widget.count() - 1
        if self.tab_widget.count() > active_idx:
            self.tab_widget.setCurrentIndex(active_idx)
        self.status_bar.showMessage(f"🔄 Restored {len(saved_tabs)} tabs from previous session.", 3500)

    def _show_settings_dialog(self) -> None:
        dialog = SettingsDialog(self._storage, self, on_saved=self._apply_settings)
        dialog.exec()

    def _apply_settings(self) -> None:
        self._start_url = self._storage.get_setting("homepage", DEFAULT_HOME_URL)
        timeout_str = self._storage.get_setting("idle_timeout_seconds", "180")
        try:
            self._memory_manager.idle_timeout_seconds = int(timeout_str)
            t_idx = self.combo_timeout.findData(int(timeout_str))
            if t_idx >= 0:
                self.combo_timeout.setCurrentIndex(t_idx)
        except ValueError:
            pass
        self.status_bar.showMessage("⚙️ Settings applied successfully.", 3000)

    def _show_about_dialog(self) -> None:
        dialog = AboutDialog(self)
        dialog.exec()

    def closeEvent(self, event) -> None:  # noqa: N802
        """Save session tabs to SQLite, purge in-memory cookies/storage if enabled, and exit."""
        try:
            tabs_data = []
            current_idx = self.tab_widget.currentIndex()
            for i in range(self.tab_widget.count()):
                tab = self.tab_widget.widget(i)
                if isinstance(tab, BrowserTabItem):
                    tabs_data.append({
                        "url": tab.url.toString(),
                        "title": tab.title,
                        "is_active": (i == current_idx),
                    })
            if tabs_data:
                self._storage.save_session(tabs_data)
        except Exception:
            pass

        if self._privacy_manager.network_security.clear_on_exit:
            self._privacy_manager.clear_session_data()
        super().closeEvent(event)
