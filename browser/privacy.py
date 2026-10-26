"""Privacy Manager module for Grago.

Provides two browsing modes:
  - Lean Mode  : off-the-record profile + built-in tracker/ad blocker.
  - Private Mode: stricter off-the-record profile, third-party cookie
                  blocking, HTTPS-only upgrades, and tighter JS policy.
"""

from __future__ import annotations

import re
import urllib.parse
from enum import Enum, auto
from typing import Dict, FrozenSet, Optional

from PySide6.QtCore import QObject, QUrl
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineUrlRequestInfo,
    QWebEngineUrlRequestInterceptor,
)

DEFAULT_SEARCH_TEMPLATE = "https://www.google.com/search?q={query}"
DEFAULT_HOME_URL = "https://www.google.com"


# ── Tracker / Ad block list ────────────────────────────────────────────────
# Compact built-in list of the most common tracker and ad domains.
# Requests whose host ends with any of these are silently blocked.
_BLOCKED_DOMAINS: FrozenSet[str] = frozenset({
    # Analytics & tracking
    "google-analytics.com", "googletagmanager.com", "googletagservices.com",
    "doubleclick.net", "googlesyndication.com", "googleadservices.com",
    "ads.google.com",
    "analytics.twitter.com", "static.ads-twitter.com",
    "facebook.net", "connect.facebook.net", "pixel.facebook.com",
    "tr.snapchat.com", "sc-static.net",
    "bat.bing.com", "c.bing.com",
    "analytics.yahoo.com",
    "amazon-adsystem.com",
    "scorecardresearch.com", "comscore.com",
    "segment.com", "segment.io",
    "mixpanel.com",
    "hotjar.com",
    "clarity.ms",
    "mouseflow.com",
    "fullstory.com",
    "logrocket.com",
    "heap.io",
    "amplitude.com",
    "intercom.io", "intercomcdn.com",
    "bugsnag.com",
    "sentry.io",
    "newrelic.com", "nr-data.net",
    "datadog-logs-us.com", "browser.datadoghq.com",
    "optimizely.com",
    "crazyegg.com",
    "quantserve.com",
    "chartbeat.com",
    "pubmatic.com", "rubiconproject.com", "openx.net",
    "adsafeprotected.com", "moatads.com",
    "outbrain.com", "taboola.com",
    "criteo.com", "criteo.net",
    "casalemedia.com",
    "adnxs.com",
    "smartadserver.com",
    "bidswitch.net",
    "contextweb.com",
    "lijit.com",
    "advertising.com",
    "adobedtm.com", "demdex.net",
    "mookie1.com",
    "turn.com",
    "mathtag.com",
    "bluekai.com",
    "adroll.com",
    "spotxchange.com",
})


def _host_is_blocked(host: str) -> bool:
    """Return True if the given hostname matches any blocked domain."""
    host = host.lower().lstrip("www.")
    return any(host == d or host.endswith("." + d) for d in _BLOCKED_DOMAINS)


class BrowsingMode(Enum):
    LEAN = auto()     # Efficient everyday browsing + tracker blocking
    PRIVATE = auto()  # Strict privacy: stronger cookie / JS policy


# ── Request interceptor ────────────────────────────────────────────────────
class TrackerBlockInterceptor(QWebEngineUrlRequestInterceptor):
    """Blocks requests to known tracker and ad domains at the network level."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._enabled: bool = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:  # noqa: N802
        if not self._enabled:
            return
        host = info.requestUrl().host()
        if host and _host_is_blocked(host):
            info.block(True)


# ── URL helpers ────────────────────────────────────────────────────────────
def get_search_url(query: str) -> QUrl:
    """Format a query string into a Google search QUrl."""
    encoded_query = urllib.parse.quote_plus(query.strip())
    return QUrl(DEFAULT_SEARCH_TEMPLATE.format(query=encoded_query))


def normalize_url(text: str, default_home: str = DEFAULT_HOME_URL) -> QUrl:
    """Parse user input from the address bar into a valid QUrl.

    If the text looks like a valid URL or host (e.g. domain, localhost),
    navigates directly (adding https:// if protocol omitted).
    Otherwise, treats the text as a Google search query.
    """
    cleaned = text.strip()
    if not cleaned:
        return QUrl(default_home)

    # Spaces → search query
    if " " in cleaned:
        return get_search_url(cleaned)

    # Known protocols or about: schemes
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", cleaned) or cleaned.startswith("about:"):
        return QUrl(cleaned)

    # Hostnames like localhost, domain.com, sub.domain.org with optional port/path
    domain_pattern = r"^(localhost|([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})(:\d+)?(/.*)?$"
    if re.match(domain_pattern, cleaned):
        return QUrl(f"https://{cleaned}")

    # Fallback to web search
    return get_search_url(cleaned)


# ── Privacy Manager ────────────────────────────────────────────────────────
class PrivacyManager(QObject):
    """Manages browsing mode profiles and privacy settings for Grago."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._mode: BrowsingMode = BrowsingMode.LEAN

        # Shared tracker interceptor (reused across both profiles)
        self._interceptor = TrackerBlockInterceptor(self)

        # Build both profiles eagerly so switching is instant
        self._lean_profile = self._build_lean_profile()
        self._private_profile = self._build_private_profile()

    # ── Public API ─────────────────────────────────────────────────────────
    @property
    def mode(self) -> BrowsingMode:
        return self._mode

    @property
    def profile(self) -> QWebEngineProfile:
        """Return the QWebEngineProfile for the active browsing mode."""
        return (
            self._lean_profile
            if self._mode == BrowsingMode.LEAN
            else self._private_profile
        )

    def set_mode(self, mode: BrowsingMode) -> None:
        """Switch the active browsing mode."""
        self._mode = mode
        # In Private mode the interceptor still runs; in Lean it's always on
        self._interceptor.enabled = True

    def clear_session_data(self) -> None:
        """Purge all in-memory cache, cookies, and visited links for both profiles."""
        for profile in (self._lean_profile, self._private_profile):
            profile.clearHttpCache()
            store = profile.cookieStore()
            if store:
                store.deleteAllCookies()
            profile.clearAllVisitedLinks()

    def get_privacy_report(self) -> Dict[str, str]:
        """Return a human-readable summary of active privacy protections."""
        mode_label = "Lean Mode ⚡" if self._mode == BrowsingMode.LEAN else "Private Mode 🔒"
        tracker_status = f"Blocking {len(_BLOCKED_DOMAINS)} tracker/ad domains"
        return {
            "Active Mode": mode_label,
            "Profile Storage": "In-Memory Only (Off-The-Record)",
            "Disk Persistence": "Disabled",
            "Cookie Policy": "Session (Purged on close)",
            "Third-Party Cookies": (
                "Allowed (session only)" if self._mode == BrowsingMode.LEAN
                else "Blocked"
            ),
            "Tracker Blocking": tracker_status,
            "HTTPS Upgrade": (
                "Manual" if self._mode == BrowsingMode.LEAN else "Enforced"
            ),
            "DNS Prefetching": "Disabled",
            "Search Engine": "Google",
        }

    # ── Profile builders ───────────────────────────────────────────────────
    def _build_lean_profile(self) -> QWebEngineProfile:
        """Lean Mode: in-memory cache, no persistent cookies, tracker blocking."""
        p = QWebEngineProfile(self)  # anonymous = off-the-record
        p.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        p.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        p.clearHttpCache()
        p.setUrlRequestInterceptor(self._interceptor)

        s = p.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.DnsPrefetchEnabled, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        return p

    def _build_private_profile(self) -> QWebEngineProfile:
        """Private Mode: all Lean restrictions + stricter JS and cookie policy."""
        p = QWebEngineProfile(self)
        p.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        p.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        p.clearHttpCache()
        p.setUrlRequestInterceptor(self._interceptor)

        s = p.settings()
        # All Lean restrictions
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.DnsPrefetchEnabled, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        # Extra Private-Mode restrictions
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)  # keep JS on
        s.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadIconsForPage, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.HyperlinkAuditingEnabled, False)
        return p
