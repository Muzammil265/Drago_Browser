"""Grago - Privacy-First, Low-Memory Desktop Browser.

Entry point for launching the Grago application with strong process isolation
and minimal attack surface architecture.
"""

from __future__ import annotations

import argparse
import os
import sys

# ── Recommended Security & Process Isolation Flags ─────────────────────────
# Must be set before QApplication or any QtWebEngine components are loaded.
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS",
    # 1. Strong Process Isolation (Site-Isolation Architecture)
    "--site-per-process "
    "--enable-features=IsolateOrigins,site-per-process,NetworkServiceInProcess "
    "--enable-sandbox "
    # 2. Strict Content Privileges & Sandboxing
    "--disallow-file-access-from-files "
    # 3. Minimal Attack Surface (Disable Unnecessary Features)
    "--disable-background-networking "
    "--disable-component-update "
    "--disable-default-apps "
    "--disable-extensions "
    "--disable-features=TranslateUI "
    "--disable-sync "
    "--disable-speech-api "
    "--disable-breakpad "
    "--disable-media-session-api "
    "--disable-notifications "
    "--disable-geolocation "
    "--disable-domain-reliability "
    "--no-first-run "
    # 4. Resource & Memory Controls
    "--renderer-process-limit=6 "
    "--memory-pressure-off "
)

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from browser.controller import (
    APP_NAME,
    DEFAULT_HOME_URL,
    IDLE_TIMEOUT_SECONDS,
    GragoWindow,
)
from browser.privacy import BrowsingMode
from browser.security import ProxyMode

# Backwards-compatible alias
GragoWindow = GragoWindow


def main() -> int:
    """Parse arguments and execute the Qt application event loop."""
    parser = argparse.ArgumentParser(
        description="Grago: A privacy-first, low-memory Python desktop browser with security architecture."
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Initial URL to open (default: new-tab page)",
    )
    parser.add_argument(
        "--idle-timeout",
        type=int,
        default=IDLE_TIMEOUT_SECONDS,
        help=f"Idle seconds before background tabs hibernate (default: {IDLE_TIMEOUT_SECONDS}s)",
    )
    parser.add_argument(
        "--mode",
        choices=["lean", "private", "safest"],
        default="lean",
        help="Initial browsing mode: lean (default), private, or safest (JS disabled)",
    )
    parser.add_argument(
        "--tor",
        action="store_true",
        help="Route network connections through Tor SOCKS5 proxy (127.0.0.1:9050)",
    )
    args = parser.parse_args()

    QApplication.setApplicationName(APP_NAME)
    QApplication.setOrganizationName("Grago")

    app = QApplication(sys.argv)

    start_url = args.url or DEFAULT_HOME_URL
    window = GragoWindow(start_url=start_url)

    if args.idle_timeout != IDLE_TIMEOUT_SECONDS:
        window._memory_manager.idle_timeout_seconds = args.idle_timeout

    # Apply initial mode if specified
    if args.mode == "private":
        window._set_mode(BrowsingMode.PRIVATE)
    elif args.mode == "safest":
        window._set_mode(BrowsingMode.SAFEST)

    # Apply Tor proxy if requested
    if args.tor:
        window._privacy_manager.network_security.set_proxy_mode(ProxyMode.TOR)

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
