"""Grago - Privacy-First, Low-Memory Desktop Browser.

Entry point for launching the Grago application.
"""

from __future__ import annotations

import argparse
import os
import sys

# ── Fast-startup & low-idle flags ───────────────────────────────────────────
# Must be set before QApplication is created.
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS",
    "--disable-background-networking "         # no silent network calls
    "--disable-component-update "              # skip component update checks
    "--disable-default-apps "                  # no built-in apps
    "--disable-extensions "                    # no extension overhead
    "--disable-features=TranslateUI "          # no translate bubble
    "--disable-sync "                          # no Google sync
    "--no-first-run "                          # skip first-run dialogs
    "--renderer-process-limit=3 "              # cap renderer processes
    "--memory-pressure-off "                   # let Qt manage its own GC
)

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from browser.controller import (
    APP_NAME,
    DEFAULT_HOME_URL,
    IDLE_TIMEOUT_SECONDS,
    GragoWindow,
)

# Backwards-compatible alias
GragoWindow = GragoWindow


def main() -> int:
    """Parse arguments and execute the Qt application event loop."""
    parser = argparse.ArgumentParser(
        description="Grago: A privacy-first, low-memory Python desktop browser."
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
    args = parser.parse_args()

    QApplication.setApplicationName(APP_NAME)
    QApplication.setOrganizationName("Grago")

    app = QApplication(sys.argv)

    # Pass explicit URL only when the user supplied one; otherwise open new-tab page
    from PySide6.QtCore import QUrl
    start_url = args.url or DEFAULT_HOME_URL
    window = GragoWindow(start_url=start_url)
    if args.idle_timeout != IDLE_TIMEOUT_SECONDS:
        window._memory_manager.idle_timeout_seconds = args.idle_timeout

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
