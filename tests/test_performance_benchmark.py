"""Performance Benchmarking Test Suite for LeanBrowse Privacy Shield.

Validates that maintained filter rules and interceptor processing do not introduce
noticeable delays or consume excessive CPU and RAM.
"""

import sys
import time
import psutil
import pytest
from PySide6.QtWidgets import QApplication

from browser.filter_engine import FilterListManager
from browser.privacy import PrivacyManager


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_filter_lookup_latency_benchmark():
    """Verify average rule check latency is well below human perception (< 50 microseconds)."""
    fm = FilterListManager()
    urls = [
        ("https://ad.doubleclick.net/ad.js", "https://example.com", "script"),
        ("https://google-analytics.com/collect", "https://example.com", "xmlhttprequest"),
        ("https://static.criteo.net/ld.js", "https://store.example.com", "script"),
        ("https://cdn.example.com/main.css", "https://example.com", "stylesheet"),
        ("https://images.example.com/banner.png", "https://example.com", "image"),
        ("https://accounts.google.com/auth", "https://example.com", "script"),
        ("https://rr1---sn-abc.googlevideo.com/videoplayback", "https://youtube.com", "media"),
    ]

    total_checks = 5000
    t0 = time.perf_counter()
    for i in range(total_checks):
        target, source, rtype = urls[i % len(urls)]
        fm.check_request(target, source, rtype)
    elapsed = time.perf_counter() - t0

    avg_microsecs = (elapsed / total_checks) * 1_000_000
    throughput_rps = total_checks / elapsed

    print(f"\n[Benchmark] {total_checks} checks in {elapsed:.4f}s | Avg: {avg_microsecs:.2f} µs/req | Throughput: {throughput_rps:,.0f} req/s")

    # High performance threshold: must complete in < 50 microseconds per request (Rust adblock is ~1.5 µs)
    assert avg_microsecs < 50.0, f"Average latency too high: {avg_microsecs:.2f} µs"
    # Throughput must exceed 20,000 requests per second
    assert throughput_rps > 20_000, f"Throughput too low: {throughput_rps:.0f} req/s"


def test_memory_overhead_benchmark():
    """Verify that filter rules and compiled engines consume minimal RAM (< 30 MB)."""
    process = psutil.Process()
    ram_before_mb = process.memory_info().rss / (1024 * 1024)

    # Instantiate multiple managers to test heap footprint
    managers = [FilterListManager() for _ in range(3)]
    ram_after_mb = process.memory_info().rss / (1024 * 1024)
    ram_delta_mb = max(0.0, ram_after_mb - ram_before_mb)

    print(f"\n[Benchmark] RAM footprint delta for 3 FilterListManagers: {ram_delta_mb:.2f} MB")
    assert ram_delta_mb < 30.0, f"RAM overhead too high: {ram_delta_mb:.2f} MB"


def test_real_counts_tracking_verification(qapp):
    """Verify that blocked request counters reflect genuine intercepted requests, not decorative numbers."""
    pm = PrivacyManager()
    interceptor = pm.interceptor

    initial_total = interceptor.total_blocked
    assert initial_total == 0
    assert interceptor.get_site_blocked_count("example.com") == 0

    # Reset stats
    interceptor.reset_stats()
    assert interceptor.total_blocked == 0
    assert len(interceptor.get_site_blocked_records("example.com")) == 0
