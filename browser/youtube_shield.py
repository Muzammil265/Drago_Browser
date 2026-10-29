"""YouTube Dedicated Ad Handler & Playback Compatibility Shield.

Handles YouTube video advertising separately from standard network filtering:
- Ensures video stream playback (googlevideo.com) is never disrupted
- Provides client-side video ad skipping & acceleration
- Cosmetically hides YouTube banner, promo, and companion ad slots
- Tracks YouTube-specific diagnostics and playback compatibility
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional
from PySide6.QtCore import QObject, Signal, QUrl

logger = logging.getLogger(__name__)


@dataclass
class YouTubeShieldStats:
    """Real-time YouTube ad handling and compatibility metrics."""
    video_ads_handled: int = 0
    cosmetic_ads_hidden: int = 0
    playback_protected: bool = True
    active_stream_url: Optional[str] = None


class YouTubeShieldHandler(QObject):
    """Specialized controller for YouTube ad management and playback safety."""

    stats_updated = Signal(object)  # Emits YouTubeShieldStats

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._stats = YouTubeShieldStats()
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def stats(self) -> YouTubeShieldStats:
        return self._stats

    def is_youtube_host(self, host: str) -> bool:
        """Check if hostname belongs to YouTube."""
        h = host.lower().lstrip("www.")
        return h == "youtube.com" or h.endswith(".youtube.com") or h in ("youtu.be", "m.youtube.com")

    def is_protected_stream(self, url_str: str) -> bool:
        """Return True if URL is an essential video playback stream or YouTube core asset."""
        u = url_str.lower()
        # Explicit ad endpoints on YouTube must remain blockable
        if "googleads" in u or "pagead" in u or "/api/stats/ads" in u or "doubleclick" in u:
            return False
        # Video streams
        if "googlevideo.com" in u or "/videoplayback" in u:
            return True
        # Core player framework, UI bundles, and API
        if "youtube.com/watch" in u or "m.youtube.com/watch" in u or u.startswith("https://www.youtube.com/?"):
            return True
        if "youtube.com/s/desktop/" in u or "youtube.com/s/player/" in u or "youtube.com/youtubei/v1/" in u:
            return True
        if "i.ytimg.com" in u or "yt3.ggpht.com" in u:
            return True
        return False

    def record_video_ad_handled(self) -> None:
        """Increment count of video ads bypassed or auto-skipped."""
        self._stats.video_ads_handled += 1
        self.stats_updated.emit(self._stats)

    def record_cosmetic_ad_hidden(self, count: int = 1) -> None:
        """Increment count of banner/promo ad elements removed."""
        self._stats.cosmetic_ads_hidden += count
        self.stats_updated.emit(self._stats)

    def reset_stats(self) -> None:
        self._stats = YouTubeShieldStats()
        self.stats_updated.emit(self._stats)

    def get_status_report(self) -> Dict[str, str]:
        """Summary of YouTube-specific protections for the Privacy Shield."""
        return {
            "YouTube Playback Engine": "Operational & Stream-Protected",
            "Video Stream Whitelist": "Active (*.googlevideo.com unthrottled)",
            "Video Ads Bypassed": str(self._stats.video_ads_handled),
            "Banner / Promo Elements Suppressed": str(self._stats.cosmetic_ads_hidden),
            "Anti-Adblock Modal Protection": "Active (Enforcement Bypassed)",
        }

    def generate_injection_script(self) -> str:
        """Generate client-side script for YouTube video ad skipping & cosmetic blocking."""
        return """
        (function() {
            if (window.__grago_yt_shield_active) return;
            window.__grago_yt_shield_active = true;

            // 1. Inject Cosmetic CSS to hide YouTube promo/banner ad elements
            const style = document.createElement('style');
            style.id = 'grago-yt-shield-style';
            style.textContent = `
                /* Companion and banner ads */
                #masthead-ad,
                ytd-ad-slot-renderer,
                ytd-in-feed-ad-layout-renderer,
                ytd-banner-promo-renderer,
                ytd-promoted-video-renderer,
                ytd-statement-banner-renderer,
                #player-ads,
                .ytp-ad-overlay-container,
                .ytp-ad-message-container,
                ytd-enforcement-message-view-model {
                    display: none !important;
                    visibility: hidden !important;
                    opacity: 0 !important;
                    height: 0 !important;
                    pointer-events: none !important;
                }
            `;
            (document.head || document.documentElement).appendChild(style);

            // 2. Video Player Ad Skipper & Fast-Forward Engine
            function handleVideoAds() {
                const player = document.querySelector('#movie_player') || document.querySelector('.html5-video-player');
                const video = document.querySelector('video.html5-main-video') || document.querySelector('video');

                if (!video) return;

                const isAdShowing = player && (
                    player.classList.contains('ad-showing') ||
                    player.classList.contains('ad-interrupting')
                );

                if (isAdShowing) {
                    // Try instant skip button click
                    const skipSelectors = [
                        '.ytp-ad-skip-button',
                        '.ytp-ad-skip-button-modern',
                        '.ytp-skip-ad-button',
                        '.ytp-ad-skip-button-slot button'
                    ];

                    let clicked = false;
                    for (const sel of skipSelectors) {
                        const btn = document.querySelector(sel);
                        if (btn) {
                            btn.click();
                            clicked = true;
                            break;
                        }
                    }

                    // For non-skippable video ads: accelerate to end & mute
                    if (!clicked && isFinite(video.duration) && video.duration > 0) {
                        try {
                            video.muted = true;
                            video.playbackRate = 16.0;
                            video.currentTime = video.duration - 0.1;
                        } catch (e) {}
                    }
                } else if (video.playbackRate === 16.0) {
                    video.playbackRate = 1.0;
                    video.muted = false;
                }

                // 3. Dismiss anti-adblock enforcement modals automatically
                const enforcementModal = document.querySelector('ytd-enforcement-message-view-model');
                if (enforcementModal) {
                    const dialog = enforcementModal.closest('tp-yt-paper-dialog');
                    if (dialog) dialog.remove();
                    const backdrop = document.querySelector('tp-yt-iron-overlay-backdrop');
                    if (backdrop) backdrop.remove();
                    if (video.paused) video.play();
                }
            }

            // Run monitor loop
            setInterval(handleVideoAds, 250);
        })();
        """
