"""Browser Controller and UI module for Grago.

Manages tabs, UI layout, address bar navigation, tab hibernation lifecycles,
and the dark desktop interface.
"""

from __future__ import annotations

import random
import time
from typing import Dict, Optional

from PySide6.QtCore import QEvent, QPoint, QSize, QTimer, QUrl, Qt, Signal, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QPainter, QShortcut, QLinearGradient, QBrush, QPalette, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsBlurEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QTabBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView

from browser.memory_manager import ResourceMonitor, TabMemoryManager
from browser.privacy import BrowsingMode, PrivacyManager, normalize_url

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
    background-color: #132e27;
    border: 1px solid #059669;
    color: #34d399;
    font-weight: 600;
    padding: 5px 10px;
    border-radius: 6px;
}

QPushButton#shield-btn:hover {
    background-color: #1b4337;
    border-color: #10b981;
    color: #6ee7b7;
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
QPushButton#mode-lean-btn, QPushButton#mode-private-btn {
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

QPushButton#mode-lean-btn:hover:!checked,
QPushButton#mode-private-btn:hover:!checked {
    background-color: #1e2330;
    color: #cbd5e1;
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


class PrivacyDialog(QDialog):
    """Dialog displaying active privacy protections and session wiping."""

    def __init__(self, privacy_manager: PrivacyManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._privacy_manager = privacy_manager
        self.setWindowTitle("Privacy & Security Controls — Grago")
        self.setMinimumSize(480, 420)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #13161f;
                color: #e2e8f0;
            }
            QLabel {
                color: #cbd5e1;
            }
            """
        )
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        header = QLabel("🛡️ Grago Privacy & Security", self)
        header.setStyleSheet("font-size: 16px; font-weight: 700; color: #34d399;")
        layout.addWidget(header)

        desc = QLabel(
            "Grago runs in a dedicated private profile by default. "
            "No cookies, web cache, or browsing history are ever written to your hard drive.",
            self,
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(desc)

        report = self._privacy_manager.get_privacy_report()
        report_frame = QFrame(self)
        report_frame.setStyleSheet(
            "background-color: #1a1e2b; border: 1px solid #293044; border-radius: 8px; padding: 8px;"
        )
        report_layout = QVBoxLayout(report_frame)
        report_layout.setSpacing(8)

        for feature, status in report.items():
            row = QHBoxLayout()
            lbl_key = QLabel(feature, report_frame)
            lbl_key.setStyleSheet("font-weight: 600; color: #e2e8f0; font-size: 12px;")
            lbl_val = QLabel(status, report_frame)
            lbl_val.setStyleSheet("color: #38bdf8; font-size: 12px;")
            lbl_val.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(lbl_key)
            row.addWidget(lbl_val)
            report_layout.addLayout(row)

        layout.addWidget(report_frame)

        btn_clear = QPushButton("🗑️ Flush In-Memory Session & Cookies Now", self)
        btn_clear.setStyleSheet(
            """
            QPushButton {
                background-color: #7f1d1d;
                border: 1px solid #dc2626;
                color: #fecaca;
                font-weight: 600;
                padding: 8px 14px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #991b1b;
                color: #ffffff;
            }
            """
        )
        btn_clear.clicked.connect(self._on_clear_clicked)
        layout.addWidget(btn_clear)

        btn_close = QPushButton("Done", self)
        btn_close.setObjectName("accent-btn")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _on_clear_clicked(self) -> None:
        self._privacy_manager.clear_session_data()
        QMessageBox.information(
            self,
            "Session Cleared",
            "In-memory HTTP cache, cookies, and visited link records have been completely purged.",
        )


class GragoWindow(QMainWindow):
    """Main window for the Grago browser application."""

    def __init__(self, start_url: str = DEFAULT_HOME_URL) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 800)
        self.setStyleSheet(DARK_STYLESHEET)

        # Managers
        self._privacy_manager = PrivacyManager(self)
        self._memory_manager = TabMemoryManager(idle_timeout_seconds=IDLE_TIMEOUT_SECONDS)
        self._start_url = start_url
        self._tab_counter = 0

        self._setup_ui()
        self._setup_shortcuts()
        self._setup_timers()

        # Open initial tab
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

        # Address / Search Bar
        self.url_bar = QLineEdit(self)
        self.url_bar.setObjectName("url-bar")
        self.url_bar.setPlaceholderText("Search or enter web address...")
        self.url_bar.setClearButtonEnabled(True)
        self.url_bar.returnPressed.connect(self._navigate_to_input)
        toolbar.addWidget(self.url_bar)

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

        # ── Mode Switcher (Lean / Private) ──────────────────────────────
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
        self.btn_mode_private.setToolTip("Private Mode: stricter cookie & JS policy, no 3rd-party tracking")
        self.btn_mode_private.setCheckable(True)
        self.btn_mode_private.setChecked(False)
        self.btn_mode_private.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_private.clicked.connect(lambda: self._set_mode(BrowsingMode.PRIVATE))
        mode_layout.addWidget(self.btn_mode_private)

        toolbar.addWidget(mode_frame)

        # Privacy details button
        self.btn_privacy = QPushButton("🛡️", self)
        self.btn_privacy.setObjectName("shield-btn")
        self.btn_privacy.setToolTip("View privacy status & clear session data")
        self.btn_privacy.clicked.connect(self._show_privacy_dialog)
        toolbar.addWidget(self.btn_privacy)

        # Memory Indicator Badge
        self.lbl_memory = QLabel("⚡ Initializing...", self)
        self.lbl_memory.setObjectName("memory-badge")
        self.lbl_memory.setToolTip("Memory (RSS) consumed by Python app and child Chromium engines")
        toolbar.addWidget(self.lbl_memory)

        # (New Tab button is now in the tab bar corner — removed from toolbar)

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
        QShortcut(QKeySequence("Ctrl+Shift+Delete"), self, self._show_privacy_dialog)

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
        is_lean = mode == BrowsingMode.LEAN
        self.btn_mode_lean.setChecked(is_lean)
        self.btn_mode_private.setChecked(not is_lean)

        label = "Lean Mode ⚡" if is_lean else "Private Mode 🔒"
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
        target_url = normalize_url(text, default_home=self._start_url)
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
        dlg = PrivacyDialog(self._privacy_manager, self)
        dlg.exec()
