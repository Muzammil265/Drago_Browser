"""Tests for YouTube Dedicated Ad Handler, Stream Safety, and Playback Compatibility."""

import pytest
from browser.youtube_shield import YouTubeShieldHandler, YouTubeShieldStats


@pytest.fixture
def yt_shield():
    return YouTubeShieldHandler()


def test_youtube_host_recognition(yt_shield):
    assert yt_shield.is_youtube_host("youtube.com") is True
    assert yt_shield.is_youtube_host("www.youtube.com") is True
    assert yt_shield.is_youtube_host("m.youtube.com") is True
    assert yt_shield.is_youtube_host("music.youtube.com") is True
    assert yt_shield.is_youtube_host("youtu.be") is True

    assert yt_shield.is_youtube_host("google.com") is False
    assert yt_shield.is_youtube_host("vimeo.com") is False
    assert yt_shield.is_youtube_host("dailymotion.com") is False


def test_youtube_protected_stream_whitelisting(yt_shield):
    """Critical test: verify googlevideo.com video stream chunks are recognized as protected."""
    stream_url = "https://rr2---sn-uxa-i5oee.googlevideo.com/videoplayback?expire=1730000000&ei=xyz&ip=1.2.3.4&id=o-ABC"
    assert yt_shield.is_protected_stream(stream_url) is True

    watch_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert yt_shield.is_protected_stream(watch_url) is True

    # Generic ad tracking is NOT a protected stream
    ad_url = "https://googleads.g.doubleclick.net/pagead/ads?client=ca-pub-123"
    assert yt_shield.is_protected_stream(ad_url) is False


def test_youtube_shield_stats_and_recording(yt_shield):
    assert yt_shield.stats.video_ads_handled == 0
    assert yt_shield.stats.cosmetic_ads_hidden == 0

    yt_shield.record_video_ad_handled()
    assert yt_shield.stats.video_ads_handled == 1

    yt_shield.record_cosmetic_ad_hidden(3)
    assert yt_shield.stats.cosmetic_ads_hidden == 3

    report = yt_shield.get_status_report()
    assert report["Video Ads Bypassed"] == "1"
    assert report["Banner / Promo Elements Suppressed"] == "3"
    assert "Operational" in report["YouTube Playback Engine"]

    yt_shield.reset_stats()
    assert yt_shield.stats.video_ads_handled == 0
    assert yt_shield.stats.cosmetic_ads_hidden == 0


def test_youtube_injection_script_generation(yt_shield):
    script = yt_shield.generate_injection_script()
    assert "handleVideoAds" in script
    assert "ytp-ad-skip-button" in script
    assert "masthead-ad" in script
    assert "ytd-ad-slot-renderer" in script
    assert "playbackRate = 16.0" in script
    assert "ytd-enforcement-message-view-model" in script
