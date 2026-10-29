"""Comprehensive test suite for the 4-Layer Security Architecture and Key Recommendations.

Tests:
1. Process Isolation & Chromium Flags (Site Isolation style)
2. Brave-Style Ad & Tracker Blocking (TrackerBlockInterceptor & Per-Site Shields)
3. Anti-Fingerprinting Engine (Canvas, Audio, WebGL, Screen, Navigator, Seed Rotation)
4. Minimal Attack Surface & WebEngine Attributes
5. Strict Extension Policy Manager (Permission Auditing)
6. Security Update Service (Advisory & Version Verification)
7. Tor SOCKS5 & Proxy Security Services
8. High-Security Safest Mode (JavaScript & WebGL disabled)
9. Tor-Style New Identity and Session Reset
10. First-Party Isolation Container Contexts
"""

import sys
import pytest
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from browser.privacy import BrowsingMode, PrivacyManager, _host_is_blocked
from browser.security import (
    AntiFingerprintEngine,
    ContainerManager,
    ExtensionManager,
    FingerprintProtectionMode,
    NetworkSecurityService,
    ProxyMode,
    UpdateService,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


# ── 1. Brave-Style Tracker & Ad Blocker Tests ──────────────────────────────
def test_tracker_blocker_detection():
    # Known blocked domains
    assert _host_is_blocked("google-analytics.com") is True
    assert _host_is_blocked("subdomain.google-analytics.com") is True
    assert _host_is_blocked("doubleclick.net") is True
    assert _host_is_blocked("pixel.facebook.com") is True
    assert _host_is_blocked("criteo.com") is True
    assert _host_is_blocked("outbrain.com") is True

    # Legitimate non-tracker domains
    assert _host_is_blocked("python.org") is False
    assert _host_is_blocked("wikipedia.org") is False
    assert _host_is_blocked("github.com") is False


def test_interceptor_per_site_shields(qapp):
    pm = PrivacyManager()
    interceptor = pm.interceptor

    test_host = "example.com"
    assert interceptor.is_site_allowed(test_host) is False

    # Turn shields down for this site
    interceptor.set_site_shields(test_host, shields_up=False)
    assert interceptor.is_site_allowed(test_host) is True

    # Turn shields back up
    interceptor.set_site_shields(test_host, shields_up=True)
    assert interceptor.is_site_allowed(test_host) is False


def test_interceptor_stats_tracking(qapp):
    pm = PrivacyManager()
    interceptor = pm.interceptor
    assert interceptor.total_blocked == 0

    interceptor.reset_stats()
    assert interceptor.total_blocked == 0


# ── 2. Anti-Fingerprinting Engine Tests ─────────────────────────────────────
def test_anti_fingerprint_script_generation():
    engine = AntiFingerprintEngine(mode=FingerprintProtectionMode.BALANCED)
    script_code = engine.generate_injection_code()

    # Verify script covers all key fingerprinting attack vectors
    assert "Canvas Fingerprint Protection" in script_code
    assert "AudioContext Fingerprint Protection" in script_code
    assert "WebGL Vendor & Renderer Masking" in script_code
    assert "Navigator Uniformity" in script_code
    assert "Screen Uniformity" in script_code
    assert "Intel Inc." in script_code
    assert "hardwareConcurrency" in script_code


def test_anti_fingerprint_seed_rotation():
    engine = AntiFingerprintEngine(mode=FingerprintProtectionMode.BALANCED)
    seed1 = engine.session_seed
    assert seed1 > 0

    seed2 = engine.regenerate_seed()
    assert seed2 > 0
    # Seed rotation creates a fresh signature
    assert seed1 != seed2


def test_anti_fingerprint_profile_application(qapp):
    pm = PrivacyManager()
    profile = pm.profile
    scripts = profile.scripts().toList()
    # Script can be verified in profiles
    script_names = [s.name() for s in scripts]
    # In Lean mode balanced or Private mode
    pm.set_mode(BrowsingMode.PRIVATE)
    private_scripts = [s.name() for s in pm.profile.scripts().toList()]
    assert "GragoAntiFingerprint" in private_scripts


# ── 3. Strict Extension Policy Manager Tests ───────────────────────────────
def test_extension_manager_default_disabled():
    mgr = ExtensionManager(allow_extensions=False)
    manifest = {
        "name": "Harmless Theme",
        "permissions": ["theme"],
    }
    audit = mgr.audit_extension_manifest(manifest)
    assert audit.is_allowed is False
    assert "disabled by default" in audit.reasons[0].lower()


def test_extension_manager_dangerous_permissions_rejected():
    mgr = ExtensionManager(allow_extensions=True)
    dangerous_manifest = {
        "name": "Suspicious Extension",
        "permissions": ["debugger", "webRequestBlocking", "storage"],
    }
    audit = mgr.audit_extension_manifest(dangerous_manifest)
    assert audit.is_allowed is False
    assert any("debugger" in r for r in audit.reasons)


def test_extension_manager_safe_permissions_allowed():
    mgr = ExtensionManager(allow_extensions=True)
    safe_manifest = {
        "name": "Verified Add-on",
        "permissions": ["storage", "tabs"],
    }
    audit = mgr.audit_extension_manifest(safe_manifest)
    assert audit.is_allowed is True
    assert audit.risk_level == "Low"


# ── 4. Security Update Service Tests ───────────────────────────────────────
def test_update_service_current_version():
    svc = UpdateService(current_version="1.0.0")
    has_update, msg = svc.check_for_updates()
    assert has_update is False
    assert "Latest security baseline" in msg


def test_update_service_newer_remote_version():
    svc = UpdateService(current_version="1.0.0")
    has_update, msg = svc.check_for_updates(remote_version="1.1.0")
    assert has_update is True
    assert "1.1.0" in msg


# ── 5. Network Security & Tor Proxy Tests ───────────────────────────────────
def test_network_security_proxy_toggle():
    net = NetworkSecurityService()
    assert net.proxy_mode == ProxyMode.DIRECT

    # Enable Tor Proxy mode
    net.set_proxy_mode(ProxyMode.TOR)
    assert net.proxy_mode == ProxyMode.TOR

    # Switch back to direct
    net.set_proxy_mode(ProxyMode.DIRECT)
    assert net.proxy_mode == ProxyMode.DIRECT


def test_network_security_clear_on_exit():
    net = NetworkSecurityService()
    assert net.clear_on_exit is True
    net.clear_on_exit = False
    assert net.clear_on_exit is False


# ── 6. Safest Mode & Minimal Attack Surface Tests ──────────────────────────
def test_safest_mode_disables_javascript_and_webgl(qapp):
    pm = PrivacyManager()
    pm.set_mode(BrowsingMode.SAFEST)
    assert pm.mode == BrowsingMode.SAFEST

    profile = pm.profile
    settings = profile.settings()

    from PySide6.QtWebEngineCore import QWebEngineSettings
    assert settings.testAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled) is False
    assert settings.testAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled) is False
    assert settings.testAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled) is False
    assert settings.testAttribute(QWebEngineSettings.WebAttribute.ReadingFromCanvasEnabled) is False


def test_minimal_attack_surface_attributes(qapp):
    pm = PrivacyManager()
    profile = pm.profile
    settings = profile.settings()

    from PySide6.QtWebEngineCore import QWebEngineSettings
    # Attack surface reductions
    assert settings.testAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls) is False
    assert settings.testAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls) is False
    assert settings.testAttribute(QWebEngineSettings.WebAttribute.DnsPrefetchEnabled) is False
    assert settings.testAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows) is False
    assert settings.testAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard) is False
    assert settings.testAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled) is False
    assert settings.testAttribute(QWebEngineSettings.WebAttribute.WebRTCPublicInterfacesOnly) is True
    assert settings.testAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture) is True


# ── 7. Tor-Style New Identity Tests ────────────────────────────────────────
def test_new_identity_rotates_and_clears(qapp):
    pm = PrivacyManager()
    old_seed = pm.anti_fingerprint.session_seed
    pm.new_identity()
    new_seed = pm.anti_fingerprint.session_seed
    assert old_seed != new_seed


# ── 8. First-Party Isolation Containers Tests ──────────────────────────────
def test_container_manager():
    cm = ContainerManager()
    assert cm.active_container.id == "default"

    cm.set_active_container("tor_isolated")
    assert cm.active_container.id == "tor_isolated"
    assert "High Isolation" in cm.active_container.name


# ── 9. Complete Security Report Telemetry ──────────────────────────────────
def test_privacy_report_architecture_layers(qapp):
    pm = PrivacyManager()
    report = pm.get_privacy_report()

    assert "Process Isolation" in report
    assert "Site-Per-Process" in report["Process Isolation"]
    assert "Anti-Fingerprinting" in report
    assert "WebRTC IP Leak Protection" in report
    assert "Extension Policy" in report
    assert "Security Update Status" in report
