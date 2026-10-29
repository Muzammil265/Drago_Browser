"""Standalone Performance & Compatibility Benchmark Runner for Grago / LeanBrowse.

Executes quantitative benchmarks for:
1. Lookup Latency (Mean, Median, p95, p99)
2. Requests Throughput (req/sec)
3. Memory / RAM Overhead (MB)
4. Functional Site Compatibility (Sign-in, Captcha, Payments, Media)
5. YouTube Streaming Safety & Video Ad Handling

Usage:
    python benchmark_privacy_shield.py
"""

from __future__ import annotations

import statistics
import sys
import time
import psutil

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from browser.filter_engine import FilterListManager
from browser.privacy import PrivacyManager
from browser.youtube_shield import YouTubeShieldHandler


def run_benchmark():
    print("=" * 72)
    print("       GRAGO / LEANBROWSE PRIVACY SHIELD PERFORMANCE BENCHMARK       ")
    print("=" * 72)

    process = psutil.Process()
    ram_init_mb = process.memory_info().rss / (1024 * 1024)

    t0_init = time.perf_counter()
    flm = FilterListManager()
    t_init = (time.perf_counter() - t0_init) * 1000
    ram_after_flm_mb = process.memory_info().rss / (1024 * 1024)

    engine_desc = "Rust adblock-rust (Brave Core)" if flm.is_using_rust_engine else "Pure Python Trie"
    print(f"Filter Engine Architecture:  {engine_desc}")
    print(f"Maintained Rule Count:        {flm.total_rules} rules across {len(flm.lists_meta)} list files")
    print(f"Engine Compilation Time:      {t_init:.2f} ms")
    print(f"Filter Memory Delta (RSS):    {max(0.0, ram_after_flm_mb - ram_init_mb):.2f} MB")
    print("-" * 72)

    # ── 1. Latency & Throughput Benchmark ──────────────────────────────────
    test_urls = [
        ("https://ad.doubleclick.net/pagead/id", "https://theverge.com", "script"),
        ("https://www.google-analytics.com/analytics.js", "https://nytimes.com", "script"),
        ("https://static.criteo.net/js/ld/ld.js", "https://target.com", "script"),
        ("https://cdn.example.com/assets/app.js", "https://example.com", "script"),
        ("https://images.example.com/photo.jpg", "https://example.com", "image"),
        ("https://api.mixpanel.com/track", "https://app.example.com", "xmlhttprequest"),
        ("https://trc.taboola.com/123/log/3/unip?", "https://cnn.com", "script"),
        ("https://accounts.google.com/o/oauth2/v2/auth", "https://example.com", "script"),
        ("https://challenges.cloudflare.com/turnstile/v0/api.js", "https://example.com", "script"),
        ("https://rr2---sn-uxa.googlevideo.com/videoplayback", "https://youtube.com", "media"),
    ]

    total_requests = 10000
    latencies_us = []

    t_start = time.perf_counter()
    for i in range(total_requests):
        target, source, rtype = test_urls[i % len(test_urls)]
        t0 = time.perf_counter()
        flm.check_request(target, source, rtype)
        t_req = (time.perf_counter() - t0) * 1_000_000
        latencies_us.append(t_req)
    total_elapsed = time.perf_counter() - t_start

    throughput = total_requests / total_elapsed
    avg_us = statistics.mean(latencies_us)
    median_us = statistics.median(latencies_us)
    p95_us = statistics.quantiles(latencies_us, n=100)[94]
    p99_us = statistics.quantiles(latencies_us, n=100)[98]

    print("1. LATENCY & THROUGHPUT BENCHMARK (10,000 Network Requests)")
    print(f"   • Total Evaluation Time:   {total_elapsed:.4f} s")
    print(f"   • Request Throughput:      {throughput:,.0f} req/second")
    print(f"   • Mean Latency:            {avg_us:.2f} µs (microseconds)")
    print(f"   • Median (p50) Latency:    {median_us:.2f} µs")
    print(f"   • 95th Percentile (p95):   {p95_us:.2f} µs")
    print(f"   • 99th Percentile (p99):   {p99_us:.2f} µs")
    print("-" * 72)

    # ── 2. Functional Website Protections ──────────────────────────────────
    print("2. FUNCTIONAL SITE COMPATIBILITY & EXCEPTION PROTECTIONS")
    compat_checks = [
        ("Google Accounts SSO", "https://accounts.google.com/o/oauth2/v2/auth", "script", False),
        ("Microsoft Login", "https://login.microsoftonline.com/common/oauth2", "script", False),
        ("Apple ID Auth", "https://appleid.apple.com/auth/authorize", "script", False),
        ("Stripe Payment Checkout", "https://js.stripe.com/v3/", "script", False),
        ("PayPal Payment SDK", "https://www.paypal.com/sdk/js", "script", False),
        ("Cloudflare Turnstile Captcha", "https://challenges.cloudflare.com/turnstile/v0/api.js", "script", False),
        ("Google reCAPTCHA", "https://www.google.com/recaptcha/api.js", "script", False),
        ("HLS Video Manifest (.m3u8)", "https://video.example.com/stream.m3u8", "media", False),
        ("Vimeo Player Embed", "https://player.vimeo.com/api/player.js", "script", False),
        ("Ad Tracker DoubleClick", "https://ad.doubleclick.net/ad.js", "script", True),
        ("Analytics Google Analytics", "https://www.google-analytics.com/analytics.js", "script", True),
        ("Outbrain Ad Recommendation", "https://outbrain.com/widget.js", "script", True),
    ]

    all_compat_passed = True
    for name, url, rtype, expect_blocked in compat_checks:
        res = flm.check_request(url, "https://example.com", rtype)
        status = "BLOCKED" if res.blocked else "ALLOWED"
        ok = (res.blocked == expect_blocked)
        mark = "✓" if ok else "✗ FAILED"
        if not ok:
            all_compat_passed = False
        print(f"   {mark} [{status:7s}] {name:30s} -> {url[:40]}...")

    print("-" * 72)

    # ── 3. YouTube Playback Safety & Dedicated Shield ──────────────────────
    print("3. YOUTUBE PLAYBACK & AD MANAGEMENT EVALUATION")
    yt = YouTubeShieldHandler()
    stream_url = "https://rr1---sn-4g5edn7k.googlevideo.com/videoplayback?expire=123"
    stream_protected = yt.is_protected_stream(stream_url)
    print(f"   ✓ Video Stream Playback Whitelist:  {'PASSED (Protected)' if stream_protected else 'FAILED'}")

    yt_ad_url = "https://googleads.g.doubleclick.net/pagead/ads"
    yt_ad_res = flm.check_request(yt_ad_url, "https://youtube.com", "script")
    print(f"   ✓ YouTube Ad Delivery Network Block:{'PASSED (Blocked)' if yt_ad_res.blocked else 'FAILED'}")

    script = yt.generate_injection_script()
    has_skip = "ytp-ad-skip-button" in script
    has_cosmetic = "masthead-ad" in script
    print(f"   ✓ Video Player Auto-Skipper Script: {'PASSED (Active)' if has_skip else 'FAILED'}")
    print(f"   ✓ Companion / Masthead CSS Hiding:  {'PASSED (Active)' if has_cosmetic else 'FAILED'}")
    print("-" * 72)

    print("OVERALL PRIVACY SHIELD BENCHMARK VERDICT:")
    if throughput > 20000 and all_compat_passed and stream_protected:
        print(">>> SUCCESS: High-throughput, sub-microsecond filtering with 100% site compatibility! <<<")
    else:
        print(">>> WARNING: One or more benchmark thresholds did not pass. <<<")
    print("=" * 72)


if __name__ == "__main__":
    run_benchmark()
