"""Privacy Manager module for Grago / LeanBrowse.

Provides three browsing modes:
  - Lean Mode   : off-the-record profile + built-in tracker/ad blocker.
  - Private Mode: stricter off-the-record profile, third-party cookie
                  blocking, HTTPS-only upgrades, anti-fingerprinting noise.
  - Safest Mode : Tor Browser 'Safest' mode — JavaScript disabled,
                  WebGL disabled, strict HTTPS-only, maximum anti-fingerprint.
"""

from __future__ import annotations

import re
import time
import urllib.parse
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, FrozenSet, List, Optional, Set

from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineUrlRequestInfo,
    QWebEngineUrlRequestInterceptor,
)

from browser.filter_engine import FilterListManager, FilterMatchResult
from browser.youtube_shield import YouTubeShieldHandler, YouTubeShieldStats
from browser.security import (
    AntiFingerprintEngine,
    ContainerManager,
    ExtensionManager,
    FingerprintProtectionMode,
    NetworkSecurityService,
    ProxyMode,
    UpdateService,
)

DEFAULT_SEARCH_TEMPLATE = "https://www.google.com/search?q={query}"
DEFAULT_HOME_URL = "https://www.google.com"


@dataclass(frozen=True)
class BlockedRequestRecord:
    """Detailed record of a real intercepted & blocked request."""
    target_url: str
    target_host: str
    first_party_host: str
    rule: str
    resource_type: str
    timestamp: float


# ── Tracker / Ad block list ────────────────────────────────────────────────
# Built-in baseline list of tracker, analytics, telemetry, and ad domains.
_BLOCKED_DOMAINS: FrozenSet[str] = frozenset({
    # Analytics & tracking
    "google-analytics.com", "googletagmanager.com", "googletagservices.com",
    "doubleclick.net", "googlesyndication.com", "googleadservices.com",
    "ads.google.com", "adservice.google.com",
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
    "app-measurement.com",
    "branch.io",
    "adjust.com",
    "appsflyer.com",
    "braze.com",
    "onesignal.com",
    "permutive.com",
    "parsely.com",
    "zemanta.com",
    "revcontent.com",
    "yieldmo.com",
    "inmobi.com",
    "unityads.unity3d.com",
    "applovin.com",
})

_GLOBAL_FILTER_MANAGER: Optional[FilterListManager] = None


def _get_global_filter_manager() -> FilterListManager:
    global _GLOBAL_FILTER_MANAGER
    if _GLOBAL_FILTER_MANAGER is None:
        _GLOBAL_FILTER_MANAGER = FilterListManager()
    return _GLOBAL_FILTER_MANAGER


def _host_is_blocked(host: str) -> bool:
    """Return True if the given hostname matches any maintained or baseline blocked domain."""
    h = host.lower().lstrip("www.")
    if any(h == d or h.endswith("." + d) for d in _BLOCKED_DOMAINS):
        return True
    fm = _get_global_filter_manager()
    eval_res = fm.check_request(f"https://{h}/", "", "script")
    return eval_res.blocked


class BrowsingMode(Enum):
    LEAN = auto()     # Efficient everyday browsing + tracker blocking
    PRIVATE = auto()  # Strict privacy: stronger cookie / JS policy + anti-fingerprinting
    SAFEST = auto()   # Tor-style Safest Mode: JavaScript disabled, WebGL disabled, strict HTTPS


# ── Request interceptor (Brave Shields Engine) ─────────────────────────────
class TrackerBlockInterceptor(QWebEngineUrlRequestInterceptor):
    """Blocks requests to maintained tracker/ad domains and enforces HTTPS-Only upgrades."""

    blocked_count_changed = Signal(int)
    site_blocked_count_changed = Signal(str, int)  # (host, count_on_site)
    request_blocked = Signal(object)  # BlockedRequestRecord

    def __init__(
        self,
        filter_manager: Optional[FilterListManager] = None,
        youtube_shield: Optional[YouTubeShieldHandler] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._enabled: bool = True
        self._aggressive: bool = False
        self._https_only: bool = True
        self._allowed_hosts: Set[str] = set()
        self._total_blocked: int = 0
        self._per_host_blocked: Dict[str, int] = {}
        self._blocked_records: List[BlockedRequestRecord] = []

        self._filter_manager = filter_manager or _get_global_filter_manager()
        self._youtube_shield = youtube_shield or YouTubeShieldHandler(self)

    @property
    def filter_manager(self) -> FilterListManager:
        return self._filter_manager

    @property
    def youtube_shield(self) -> YouTubeShieldHandler:
        return self._youtube_shield

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def aggressive(self) -> bool:
        return self._aggressive

    @aggressive.setter
    def aggressive(self, value: bool) -> None:
        self._aggressive = value

    @property
    def https_only(self) -> bool:
        return self._https_only

    @https_only.setter
    def https_only(self, value: bool) -> None:
        self._https_only = value

    @property
    def total_blocked(self) -> int:
        return self._total_blocked

    def get_host_blocked_count(self, host: str) -> int:
        """Return the number of blocked requests attributed to this host."""
        host = host.lower().lstrip("www.")
        return self._per_host_blocked.get(host, 0)

    def get_site_blocked_count(self, host: str) -> int:
        """Alias for get_host_blocked_count with normalized origin hostname."""
        return self.get_host_blocked_count(host)

    def get_site_blocked_records(self, host: str) -> List[BlockedRequestRecord]:
        """Return full history of blocked requests on a specific website."""
        norm = host.lower().lstrip("www.")
        return [r for r in self._blocked_records if r.first_party_host == norm]

    def is_site_allowed(self, host: str) -> bool:
        host = host.lower().lstrip("www.")
        return host in self._allowed_hosts

    def set_site_shields(self, host: str, shields_up: bool) -> None:
        host = host.lower().lstrip("www.")
        if shields_up:
            self._allowed_hosts.discard(host)
        else:
            self._allowed_hosts.add(host)

    def reset_stats(self) -> None:
        self._total_blocked = 0
        self._per_host_blocked.clear()
        self._blocked_records.clear()
        self.blocked_count_changed.emit(0)

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:  # noqa: N802
        req_url = info.requestUrl()
        target_host = req_url.host()
        target_str = req_url.toString()

        # Determine first-party origin / top-level site making this request
        first_party_url = info.firstPartyUrl()
        first_party_host = ""
        first_party_str = ""
        if first_party_url.isValid() and not first_party_url.isEmpty():
            first_party_host = first_party_url.host()
            first_party_str = first_party_url.toString()

        if not first_party_host:
            initiator = info.initiator()
            if initiator.isValid() and not initiator.isEmpty():
                first_party_host = initiator.host()
                first_party_str = initiator.toString()

        norm_first_party = first_party_host.lower().lstrip("www.") if first_party_host else ""
        norm_target_host = target_host.lower().lstrip("www.") if target_host else ""

        # Site for tracking attribution (prefer first-party page, fallback to target)
        attribution_host = norm_first_party or norm_target_host

        # Check if shields are turned off specifically for this site
        if attribution_host and self.is_site_allowed(attribution_host):
            return

        # 1. Privacy Headers (Sec-GPC & DNT)
        info.setHttpHeader(b"Sec-GPC", b"1")
        info.setHttpHeader(b"DNT", b"1")
        info.setHttpHeader(b"Upgrade-Insecure-Requests", b"1")

        # 2. HTTPS-Only Mode Upgrade
        if self._https_only and req_url.scheme() == "http":
            if not (target_host in ("localhost", "127.0.0.1")):
                upgraded_str = "https://" + target_str[7:]
                info.redirect(QUrl(upgraded_str))
                return

        # 3. Ad & Tracker Blocking
        if not self._enabled:
            return

        # 4. Critical Protection: Never block video streams or YouTube playback
        if self._youtube_shield.is_protected_stream(target_str):
            return

        # Map Qt resource type to adblock standard type
        try:
            res_val = info.resourceType().value if hasattr(info.resourceType(), "value") else int(info.resourceType())
            res_type_name = self._filter_manager.RESOURCE_TYPE_MAP.get(res_val, "other")
        except Exception:
            res_type_name = "other"

        # Check Maintained Filter Rules
        match_res = self._filter_manager.check_request(
            target_url=target_str,
            source_url=first_party_str or target_str,
            resource_type=res_type_name,
        )

        # Fallback check against baseline blocked domains if not matched
        should_block = match_res.blocked
        matched_rule = match_res.rule or "Maintained Rule"

        if not should_block and not match_res.is_exception:
            if target_host and any(norm_target_host == d or norm_target_host.endswith("." + d) for d in _BLOCKED_DOMAINS):
                should_block = True
                matched_rule = f"||{norm_target_host}^"

        if should_block:
            info.block(True)
            self._total_blocked += 1

            if attribution_host:
                self._per_host_blocked[attribution_host] = self._per_host_blocked.get(attribution_host, 0) + 1
                site_count = self._per_host_blocked[attribution_host]
            else:
                site_count = 1

            record = BlockedRequestRecord(
                target_url=target_str,
                target_host=norm_target_host,
                first_party_host=attribution_host,
                rule=matched_rule,
                resource_type=res_type_name,
                timestamp=time.time(),
            )
            self._blocked_records.append(record)
            if len(self._blocked_records) > 1000:
                self._blocked_records.pop(0)

            self.blocked_count_changed.emit(self._total_blocked)
            if attribution_host:
                self.site_blocked_count_changed.emit(attribution_host, site_count)
            self.request_blocked.emit(record)


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
    """Manages browsing mode profiles, security policies, and protections for Grago."""

    mode_changed = Signal(BrowsingMode)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._mode: BrowsingMode = BrowsingMode.LEAN

        # Core Security Subsystems
        self._anti_fingerprint = AntiFingerprintEngine(
            mode=FingerprintProtectionMode.BALANCED,
            parent=self,
        )
        self._extension_manager = ExtensionManager(allow_extensions=False, parent=self)
        self._update_service = UpdateService(parent=self)
        self._network_security = NetworkSecurityService(parent=self)
        self._container_manager = ContainerManager(parent=self)

        # Maintained filter rules manager and YouTube dedicated shield
        self._filter_manager = FilterListManager()
        self._youtube_shield = YouTubeShieldHandler(self)

        # Shared tracker interceptor (reused across profiles)
        self._interceptor = TrackerBlockInterceptor(
            filter_manager=self._filter_manager,
            youtube_shield=self._youtube_shield,
            parent=self,
        )

        # Build profiles eagerly so switching is instant
        self._lean_profile = self._build_lean_profile()
        self._private_profile = self._build_private_profile()
        self._safest_profile = self._build_safest_profile()

    # ── Public API ─────────────────────────────────────────────────────────
    @property
    def mode(self) -> BrowsingMode:
        return self._mode

    @property
    def interceptor(self) -> TrackerBlockInterceptor:
        return self._interceptor

    @property
    def filter_manager(self) -> FilterListManager:
        return self._filter_manager

    @property
    def youtube_shield(self) -> YouTubeShieldHandler:
        return self._youtube_shield

    @property
    def anti_fingerprint(self) -> AntiFingerprintEngine:
        return self._anti_fingerprint

    @property
    def extension_manager(self) -> ExtensionManager:
        return self._extension_manager

    @property
    def update_service(self) -> UpdateService:
        return self._update_service

    @property
    def network_security(self) -> NetworkSecurityService:
        return self._network_security

    @property
    def container_manager(self) -> ContainerManager:
        return self._container_manager

    @property
    def profile(self) -> QWebEngineProfile:
        """Return the QWebEngineProfile for the active browsing mode."""
        if self._mode == BrowsingMode.LEAN:
            return self._lean_profile
        elif self._mode == BrowsingMode.PRIVATE:
            return self._private_profile
        else:
            return self._safest_profile

    def set_mode(self, mode: BrowsingMode) -> None:
        """Switch the active browsing mode."""
        self._mode = mode
        self._interceptor.enabled = True

        if mode == BrowsingMode.SAFEST:
            self._anti_fingerprint.mode = FingerprintProtectionMode.STRICT
            self._interceptor.aggressive = True
            self._interceptor.https_only = True
        elif mode == BrowsingMode.PRIVATE:
            self._anti_fingerprint.mode = FingerprintProtectionMode.BALANCED
            self._interceptor.aggressive = False
            self._interceptor.https_only = True
        else:
            self._anti_fingerprint.mode = FingerprintProtectionMode.BALANCED
            self._interceptor.aggressive = False
            self._interceptor.https_only = False

        self.mode_changed.emit(mode)

    def new_identity(self) -> None:
        """Tor-style New Identity: resets sessions, purges cache/cookies, rotates fingerprint seed."""
        self.clear_session_data()
        self._anti_fingerprint.regenerate_seed()
        # Re-apply updated seed to profiles
        self._anti_fingerprint.apply_to_profile(self._private_profile)
        self._anti_fingerprint.apply_to_profile(self._safest_profile)
        self._interceptor.reset_stats()

    def clear_session_data(self) -> None:
        """Purge all in-memory cache, cookies, and visited links across all profiles."""
        for profile in (self._lean_profile, self._private_profile, self._safest_profile):
            profile.clearHttpCache()
            store = profile.cookieStore()
            if store:
                store.deleteAllCookies()
            profile.clearAllVisitedLinks()

    def get_privacy_report(self) -> Dict[str, str]:
        """Return a human-readable summary of active privacy & security protections."""
        if self._mode == BrowsingMode.LEAN:
            mode_label = "Lean Mode ⚡"
        elif self._mode == BrowsingMode.PRIVATE:
            mode_label = "Private Mode 🔒"
        else:
            mode_label = "Safest Mode 🛡️ (High Security)"

        engine_type = "Rust adblock-rust (Sub-microsecond)" if self._filter_manager.is_using_rust_engine else "Pure Python Trie"
        tracker_status = (
            f"Active ({self._interceptor.total_blocked} blocked, "
            f"{self._filter_manager.total_rules} maintained rules across {len(self._filter_manager.lists_meta)} lists [{engine_type}])"
        )
        proxy_name = self._network_security.proxy_mode.value

        return {
            "Profile Mode": mode_label,
            "Active Mode": mode_label,
            "Process Isolation": "Site-Per-Process (Strict Sandboxing)",
            "Profile Storage": "In-Memory Only (Off-The-Record)",
            "Disk Persistence": "Disabled",
            "Cookie Policy": "Session Only (Purged on close / New Identity)",
            "Third-Party Cookies": (
                "Allowed (session only)" if self._mode == BrowsingMode.LEAN
                else "Blocked"
            ),
            "Tracker & Ad Blocking": tracker_status,
            "Maintained Filter Lists": f"{self._filter_manager.total_rules} rules loaded",
            "YouTube Dedicated Shield": "Playback Stream Protected & Ad Skipper Active",
            "Anti-Fingerprinting": (
                "Disabled" if self._anti_fingerprint.mode == FingerprintProtectionMode.DISABLED
                else f"Active ({self._anti_fingerprint.mode.name.title()} Seed: {self._anti_fingerprint.session_seed})"
            ),
            "HTTPS Upgrade": (
                "Enforced (HTTPS-Only)" if self._interceptor.https_only
                else "Manual"
            ),
            "JavaScript Policy": (
                "Disabled (Safest Mode)" if self._mode == BrowsingMode.SAFEST
                else "Enabled"
            ),
            "Network / Proxy": proxy_name,
            "DNS Prefetching": "Disabled",
            "WebRTC IP Leak Protection": "Public Interfaces Only",
            "Extension Policy": self._extension_manager.get_status_summary()["Policy"],
            "Security Update Status": self._update_service.update_status,
            "Search Engine": "Google",
        }

    # ── Profile builders ───────────────────────────────────────────────────
    def _apply_baseline_security(self, profile: QWebEngineProfile) -> None:
        """Apply minimal attack surface attributes common to all secure profiles."""
        s = profile.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.DnsPrefetchEnabled, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.WebRTCPublicInterfacesOnly, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.HyperlinkAuditingEnabled, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.AllowGeolocationOnInsecureOrigins, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, True)

    def _build_lean_profile(self) -> QWebEngineProfile:
        """Lean Mode: in-memory cache, no persistent cookies, tracker blocking."""
        p = QWebEngineProfile(self)  # anonymous = off-the-record
        p.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        p.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        p.clearHttpCache()
        p.setUrlRequestInterceptor(self._interceptor)
        self._apply_baseline_security(p)

        s = p.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        return p

    def _build_private_profile(self) -> QWebEngineProfile:
        """Private Mode: all Lean restrictions + anti-fingerprinting noise + strict cookie policy."""
        p = QWebEngineProfile(self)
        p.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        p.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        p.clearHttpCache()
        p.setUrlRequestInterceptor(self._interceptor)
        self._apply_baseline_security(p)

        s = p.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadIconsForPage, False)

        # Inject Anti-Fingerprinting Shield
        self._anti_fingerprint.apply_to_profile(p)
        return p

    def _build_safest_profile(self) -> QWebEngineProfile:
        """Safest Mode (Tor Safest equivalent): JavaScript disabled, WebGL disabled, strict HTTPS."""
        p = QWebEngineProfile(self)
        p.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        p.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        p.clearHttpCache()
        p.setUrlRequestInterceptor(self._interceptor)
        self._apply_baseline_security(p)

        s = p.settings()
        # High Security: completely disable JavaScript, WebGL, canvas reading
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.ReadingFromCanvasEnabled, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadIconsForPage, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, False)

        # Inject Anti-Fingerprinting Shield
        self._anti_fingerprint.apply_to_profile(p)
        return p
