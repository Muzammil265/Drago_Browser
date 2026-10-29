"""Comprehensive tests for FilterListManager, maintained rules, and functionality protections."""

import pytest
from browser.filter_engine import FallbackTrieEngine, FilterListManager


@pytest.fixture(scope="module")
def filter_manager():
    return FilterListManager()


def test_filter_manager_loads_maintained_rules(filter_manager):
    assert filter_manager.total_rules > 0
    assert len(filter_manager.lists_meta) >= 3
    # Check that metadata was correctly extracted
    names = [m.name for m in filter_manager.lists_meta]
    assert any("Maintained" in n or "Tracker" in n for n in names)
    assert any("Functionality" in n or "Exception" in n or "Whitelist" in n for n in names)


def test_maintained_trackers_and_ads_blocked(filter_manager):
    # Advertising networks
    r1 = filter_manager.check_request("https://ad.doubleclick.net/pagead/id", "https://news.example.com", "script")
    assert r1.blocked is True

    r2 = filter_manager.check_request("https://static.criteo.net/js/ld/ld.js", "https://shop.example.com", "script")
    assert r2.blocked is True

    r3 = filter_manager.check_request("https://trc.taboola.com/123/log/3/unip?", "https://blog.example.com", "script")
    assert r3.blocked is True

    # Analytics & Trackers
    r4 = filter_manager.check_request("https://www.google-analytics.com/analytics.js", "https://example.com", "script")
    assert r4.blocked is True

    r5 = filter_manager.check_request("https://api.mixpanel.com/track", "https://example.com", "xmlhttprequest")
    assert r5.blocked is True


def test_protect_website_functionality_sso_and_auth(filter_manager):
    """Verify that essential identity providers and single sign-on flows are never broken."""
    auth_endpoints = [
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "https://appleid.apple.com/auth/authorize",
        "https://github.com/login/oauth/authorize",
        "https://auth0.com/authorize",
    ]
    for url in auth_endpoints:
        res = filter_manager.check_request(url, "https://myapp.com", "script")
        assert res.blocked is False, f"Auth endpoint must not be blocked: {url}"


def test_protect_website_functionality_payments_and_captcha(filter_manager):
    """Verify that payment gateways and bot-verification services remain functional."""
    functional_urls = [
        "https://js.stripe.com/v3/",
        "https://www.paypal.com/sdk/js?client-id=test",
        "https://challenges.cloudflare.com/turnstile/v0/api.js",
        "https://www.google.com/recaptcha/api.js",
        "https://hcaptcha.com/1/api.js",
    ]
    for url in functional_urls:
        res = filter_manager.check_request(url, "https://store.example.com", "script")
        assert res.blocked is False, f"Payment/verification endpoint must not be blocked: {url}"


def test_protect_website_functionality_media_playback(filter_manager):
    """Verify video streaming manifests and media segments are never blocked."""
    media_urls = [
        "https://example.com/stream/manifest.m3u8",
        "https://example.com/stream/manifest.mpd",
        "https://rr1---sn-4g5edn7k.googlevideo.com/videoplayback?expire=123",
        "https://player.vimeo.com/api/player.js",
    ]
    for url in media_urls:
        res = filter_manager.check_request(url, "https://video.example.com", "media")
        assert res.blocked is False, f"Media playback URL must not be blocked: {url}"


def test_main_frame_navigation_never_blocked(filter_manager):
    """Even if an advertising site is loaded directly by user in address bar, main navigation must work."""
    res = filter_manager.check_request("https://doubleclick.net/", "", "main_frame")
    assert res.blocked is False


def test_fallback_trie_engine():
    """Verify the pure-Python Trie engine handles subdomains and exceptions accurately."""
    trie = FallbackTrieEngine()
    trie.add_rule("||doubleclick.net^")
    trie.add_rule("||analytics.google.com^")
    trie.add_rule("@@||safe-site.com^")

    # Blocked domains and subdomains
    match1 = trie.match("doubleclick.net")
    assert match1 is not None and match1[0] is True

    match2 = trie.match("ads.sub.doubleclick.net")
    assert match2 is not None and match2[0] is True

    # Exception domain
    match_ex = trie.match("safe-site.com")
    assert match_ex is not None and match_ex[0] is False

    # Legitimate non-matched domain
    match3 = trie.match("example.com")
    assert match3 is None
