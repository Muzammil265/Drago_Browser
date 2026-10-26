"""Tests for Privacy Manager and URL normalization."""

import sys
import pytest
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from browser.privacy import PrivacyManager, get_search_url, normalize_url

# Ensure QApplication exists for Qt WebEngine Profile initialization
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_get_search_url():
    url = get_search_url("python tutorial")
    assert url.isValid()
    assert url.toString() == "https://www.google.com/search?q=python+tutorial"


def test_normalize_url_empty():
    url = normalize_url("", default_home="https://www.example.com")
    assert url.toString() == "https://www.example.com"


def test_normalize_url_search_query_with_spaces():
    url = normalize_url("low ram browser python")
    assert url.toString() == "https://www.google.com/search?q=low+ram+browser+python"


def test_normalize_url_with_scheme():
    url_https = normalize_url("https://www.wikipedia.org")
    assert url_https.toString() == "https://www.wikipedia.org"

    url_about = normalize_url("about:blank")
    assert url_about.toString() == "about:blank"


def test_normalize_url_domains():
    url_domain = normalize_url("wikipedia.org")
    assert url_domain.toString() == "https://wikipedia.org"

    url_subdomain = normalize_url("docs.python.org/3/")
    assert url_subdomain.toString() == "https://docs.python.org/3/"

    url_localhost = normalize_url("localhost:8080")
    assert url_localhost.toString() == "https://localhost:8080"


def test_normalize_url_single_word_fallback():
    url_fallback = normalize_url("pythontutorial")
    assert "google.com/search?q=pythontutorial" in url_fallback.toString()


def test_privacy_manager_profile(qapp):
    pm = PrivacyManager()
    profile = pm.profile
    assert profile.isOffTheRecord() is True

    report = pm.get_privacy_report()
    assert "Profile Mode" in report
    assert "Disk Persistence" in report
    assert "Cookie Policy" in report
    assert "Search Engine" in report
    assert "Google" in report["Search Engine"]


def test_privacy_manager_clear_session(qapp):
    pm = PrivacyManager()
    # Should execute without throwing any exception
    pm.clear_session_data()
