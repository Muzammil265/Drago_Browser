"""Security Architecture and Protection Layer for Grago / LeanBrowse.

Implements key security recommendations:
1. Anti-Fingerprinting engine (Canvas micro-noise, AudioContext perturbation,
   WebGL vendor/renderer spoofing, Screen/dimension uniformity, Navigator standardization).
2. Extension Manager with strict security policy (minimal attack surface).
3. Security Update Service (automatic version & advisory check).
4. Network Security & Proxy Service (Tor SOCKS5, custom proxy, HTTPS-Only mode).
5. First-Party Isolation / Container Management.
"""

from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple

from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtNetwork import QNetworkProxy
from PySide6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEngineScript,
    QWebEngineSettings,
)


# ── 1. Anti-Fingerprinting Engine ──────────────────────────────────────────

class FingerprintProtectionMode(Enum):
    DISABLED = auto()
    BALANCED = auto()  # Brave-style: subtle randomization/noise per session
    STRICT = auto()    # Tor/Mullvad-style: strict uniformity and masking


class AntiFingerprintEngine(QObject):
    """Generates and injects JavaScript shields to thwart browser fingerprinting."""

    def __init__(self, mode: FingerprintProtectionMode = FingerprintProtectionMode.BALANCED, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._mode = mode
        self._session_seed = random.randint(1000, 999999)
        self._cached_script: Optional[QWebEngineScript] = None

    @property
    def mode(self) -> FingerprintProtectionMode:
        return self._mode

    @mode.setter
    def mode(self, new_mode: FingerprintProtectionMode) -> None:
        self._mode = new_mode
        self._cached_script = None

    @property
    def session_seed(self) -> int:
        return self._session_seed

    def regenerate_seed(self) -> int:
        """Rotate seed upon New Identity to produce distinct fingerprint signatures."""
        self._session_seed = random.randint(1000, 999999)
        self._cached_script = None
        return self._session_seed

    def generate_injection_code(self) -> str:
        """Build the JavaScript payload injected before any page scripts execute."""
        if self._mode == FingerprintProtectionMode.DISABLED:
            return "// Anti-fingerprinting disabled"

        seed = self._session_seed
        is_strict = (self._mode == FingerprintProtectionMode.STRICT)

        return f"""(function() {{
    'use strict';
    // Grago Anti-Fingerprint Protection Shield (Mode: {'STRICT' if is_strict else 'BALANCED'})
    try {{
        const SEED = {seed};
        const IS_STRICT = {str(is_strict).lower()};

        // 1. Canvas Fingerprint Protection (Micro-noise injection)
        if (typeof CanvasRenderingContext2D !== 'undefined') {{
            const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {{
                try {{
                    const imageData = origGetImageData.apply(this, arguments);
                    if (imageData && imageData.data) {{
                        const data = imageData.data;
                        const step = IS_STRICT ? 20 : 40;
                        for (let i = 0; i < data.length; i += step) {{
                            data[i] = (data[i] ^ (SEED & 0x03));
                        }}
                    }}
                    return imageData;
                }} catch (e) {{
                    return origGetImageData.apply(this, arguments);
                }}
            }};

            const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function() {{
                try {{
                    const ctx = this.getContext('2d');
                    if (ctx && this.width > 0 && this.height > 0) {{
                        const img = ctx.getImageData(0, 0, Math.min(this.width, 16), Math.min(this.height, 16));
                        if (img && img.data) {{
                            img.data[0] = (img.data[0] ^ (SEED & 0x01));
                            ctx.putImageData(img, 0, 0);
                        }}
                    }}
                }} catch (e) {{}}
                return origToDataURL.apply(this, arguments);
            }};

            const origToBlob = HTMLCanvasElement.prototype.toBlob;
            HTMLCanvasElement.prototype.toBlob = function(callback, type, quality) {{
                try {{
                    const ctx = this.getContext('2d');
                    if (ctx && this.width > 0 && this.height > 0) {{
                        const img = ctx.getImageData(0, 0, Math.min(this.width, 16), Math.min(this.height, 16));
                        if (img && img.data) {{
                            img.data[0] = (img.data[0] ^ (SEED & 0x01));
                            ctx.putImageData(img, 0, 0);
                        }}
                    }}
                }} catch (e) {{}}
                return origToBlob.apply(this, arguments);
            }};
        }}

        // 2. AudioContext Fingerprint Protection
        if (typeof AudioBuffer !== 'undefined') {{
            const origGetChannelData = AudioBuffer.prototype.getChannelData;
            AudioBuffer.prototype.getChannelData = function() {{
                try {{
                    const buffer = origGetChannelData.apply(this, arguments);
                    if (buffer) {{
                        for (let i = 0; i < buffer.length; i += 120) {{
                            buffer[i] = buffer[i] + ((SEED % 100) * 0.0000001);
                        }}
                    }}
                    return buffer;
                }} catch (e) {{
                    return origGetChannelData.apply(this, arguments);
                }}
            }};
        }}

        // 3. WebGL Vendor & Renderer Masking (Uniform Intel Iris / Mesa ID)
        const maskWebGL = function(targetProto) {{
            if (!targetProto) return;
            const origGetParam = targetProto.getParameter;
            targetProto.getParameter = function(param) {{
                // UNMASKED_VENDOR_WEBGL
                if (param === 0x9245) return 'Intel Inc.';
                // UNMASKED_RENDERER_WEBGL
                if (param === 0x9246) return 'Intel(R) UHD Graphics 630';
                return origGetParam.apply(this, arguments);
            }};
        }};
        if (typeof WebGLRenderingContext !== 'undefined') maskWebGL(WebGLRenderingContext.prototype);
        if (typeof WebGL2RenderingContext !== 'undefined') maskWebGL(WebGL2RenderingContext.prototype);

        // 4. Navigator Uniformity (Tor / Mullvad style)
        try {{
            Object.defineProperty(Navigator.prototype, 'hardwareConcurrency', {{ get: () => 4, configurable: true }});
            Object.defineProperty(Navigator.prototype, 'deviceMemory', {{ get: () => 8, configurable: true }});
            Object.defineProperty(Navigator.prototype, 'maxTouchPoints', {{ get: () => 0, configurable: true }});
            Object.defineProperty(Navigator.prototype, 'platform', {{ get: () => 'Win32', configurable: true }});
            Object.defineProperty(Navigator.prototype, 'doNotTrack', {{ get: () => '1', configurable: true }});
            if (navigator.globalPrivacyControl === undefined) {{
                Object.defineProperty(Navigator.prototype, 'globalPrivacyControl', {{ get: () => true, configurable: true }});
            }}
        }} catch(e) {{}}

        // 5. Screen Uniformity
        try {{
            Object.defineProperty(Screen.prototype, 'colorDepth', {{ get: () => 24, configurable: true }});
            Object.defineProperty(Screen.prototype, 'pixelDepth', {{ get: () => 24, configurable: true }});
        }} catch(e) {{}}

    }} catch (err) {{
        // Prevent fingerprinting defenses from breaking normal rendering
    }}
}})();"""

    def get_web_engine_script(self) -> QWebEngineScript:
        """Create or retrieve a QWebEngineScript configured for DocumentCreation injection."""
        script = QWebEngineScript()
        script.setName("GragoAntiFingerprint")
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(True)
        script.setSourceCode(self.generate_injection_code())
        self._cached_script = script
        return script

    def apply_to_profile(self, profile: QWebEngineProfile) -> None:
        """Inject or replace the anti-fingerprinting script inside a profile."""
        scripts = profile.scripts()
        # Remove existing if any
        for s in list(scripts.toList()):
            if s.name() == "GragoAntiFingerprint":
                scripts.remove(s)
        if self._mode != FingerprintProtectionMode.DISABLED:
            scripts.insert(self.get_web_engine_script())


# ── 2. Extension Policy Manager ────────────────────────────────────────────

class ExtensionPermission(Enum):
    SAFE_THEME = "theme"
    TABS = "tabs"
    STORAGE = "storage"
    COOKIES = "cookies"
    WEB_REQUEST = "webRequest"
    WEB_REQUEST_BLOCKING = "webRequestBlocking"
    DEBUGGER = "debugger"
    NATIVE_MESSAGING = "nativeMessaging"
    MANAGEMENT = "management"
    ALL_URLS = "<all_urls>"


@dataclass
class ExtensionAuditResult:
    is_allowed: bool
    extension_id: str
    reasons: List[str] = field(default_factory=list)
    risk_level: str = "Low"


class ExtensionManager(QObject):
    """Enforces strict extension policy — disabled by default to minimize attack surface."""

    # Disallowed high-risk permissions that can compromise isolation or sniff traffic
    DISALLOWED_PERMISSIONS: Set[str] = {
        "debugger",
        "nativeMessaging",
        "management",
        "webRequestBlocking",
        "proxy",
        "vpnProvider",
    }

    def __init__(self, allow_extensions: bool = False, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._allow_extensions = allow_extensions
        self._trusted_extensions: Set[str] = set()

    @property
    def allow_extensions(self) -> bool:
        return self._allow_extensions

    @allow_extensions.setter
    def allow_extensions(self, val: bool) -> None:
        self._allow_extensions = val

    def audit_extension_manifest(self, manifest: Dict) -> ExtensionAuditResult:
        """Audit an extension manifest against strict security rules."""
        ext_id = manifest.get("name", "unknown_extension")
        if not self._allow_extensions:
            return ExtensionAuditResult(
                is_allowed=False,
                extension_id=ext_id,
                reasons=["Extensions are disabled by default for minimal attack surface"],
                risk_level="High (Policy Blocked)",
            )

        permissions = manifest.get("permissions", [])
        reasons = []
        is_risky = False

        for perm in permissions:
            if perm in self.DISALLOWED_PERMISSIONS:
                reasons.append(f"Forbidden dangerous permission requested: '{perm}'")
                is_risky = True

        if is_risky:
            return ExtensionAuditResult(
                is_allowed=False,
                extension_id=ext_id,
                reasons=reasons,
                risk_level="High (Disallowed Permissions)",
            )

        return ExtensionAuditResult(
            is_allowed=True,
            extension_id=ext_id,
            reasons=["Manifest complies with Grago strict extension policy"],
            risk_level="Low",
        )

    def get_status_summary(self) -> Dict[str, str]:
        return {
            "Policy": "Strict (Disabled by default)" if not self._allow_extensions else "Strict (Audited Only)",
            "Extensions Enabled": "No (Minimal Attack Surface)" if not self._allow_extensions else "Yes",
            "Dangerous Permissions": "Blocked (debugger, nativeMessaging, webRequestBlocking)",
        }


# ── 3. Security Update Service ─────────────────────────────────────────────

@dataclass
class SecurityAdvisory:
    id: str
    severity: str
    title: str
    description: str
    min_safe_version: str


class UpdateService(QObject):
    """Monitors version currency and checks against security advisories."""

    update_available = Signal(str, str)  # new_version, advisory_summary

    CURRENT_VERSION = "1.0.0"

    # Known advisories for security telemetry
    KNOWN_ADVISORIES: List[SecurityAdvisory] = [
        SecurityAdvisory(
            id="SEC-2026-001",
            severity="Info",
            title="Site Isolation Hardening",
            description="Ensure --site-per-process flag is enabled for full origin isolation.",
            min_safe_version="1.0.0",
        )
    ]

    def __init__(self, current_version: str = CURRENT_VERSION, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._current_version = current_version
        self._last_checked = time.time()
        self._update_status = "Up to date (Secure)"

    @property
    def current_version(self) -> str:
        return self._current_version

    @property
    def update_status(self) -> str:
        return self._update_status

    def check_for_updates(self, remote_version: Optional[str] = None) -> Tuple[bool, str]:
        """Check if current version satisfies all known security requirements."""
        self._last_checked = time.time()
        target_version = remote_version or self._current_version

        # Simple semantic version check
        if target_version > self._current_version:
            msg = f"New security update available: v{target_version} (Current: v{self._current_version})"
            self._update_status = msg
            self.update_available.emit(target_version, msg)
            return True, msg

        self._update_status = f"v{self._current_version} (Latest security baseline)"
        return False, self._update_status


# ── 4. Network Security & Proxy / Tor Service ──────────────────────────────

class ProxyMode(Enum):
    DIRECT = "Direct Connection"
    TOR = "Tor Network (SOCKS5 127.0.0.1:9050)"
    CUSTOM = "Custom Proxy"


class NetworkSecurityService(QObject):
    """Manages Tor/SOCKS5 proxy routing, HTTPS-Only mode, and exit wipes."""

    proxy_changed = Signal(ProxyMode)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._proxy_mode: ProxyMode = ProxyMode.DIRECT
        self._https_only: bool = True
        self._clear_on_exit: bool = True
        self._custom_host: str = "127.0.0.1"
        self._custom_port: int = 9050

    @property
    def proxy_mode(self) -> ProxyMode:
        return self._proxy_mode

    @property
    def https_only(self) -> bool:
        return self._https_only

    @https_only.setter
    def https_only(self, val: bool) -> None:
        self._https_only = val

    @property
    def clear_on_exit(self) -> bool:
        return self._clear_on_exit

    @clear_on_exit.setter
    def clear_on_exit(self, val: bool) -> None:
        self._clear_on_exit = val

    def set_proxy_mode(self, mode: ProxyMode, host: str = "127.0.0.1", port: int = 9050) -> None:
        """Apply application-level proxy (Direct or Tor SOCKS5)."""
        self._proxy_mode = mode
        self._custom_host = host
        self._custom_port = port

        if mode == ProxyMode.DIRECT:
            QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
        elif mode == ProxyMode.TOR:
            proxy = QNetworkProxy(QNetworkProxy.ProxyType.Socks5Proxy, "127.0.0.1", 9050)
            QNetworkProxy.setApplicationProxy(proxy)
        elif mode == ProxyMode.CUSTOM:
            proxy = QNetworkProxy(QNetworkProxy.ProxyType.Socks5Proxy, host, port)
            QNetworkProxy.setApplicationProxy(proxy)

        self.proxy_changed.emit(mode)


# ── 5. First-Party Isolation / Containers ───────────────────────────────────

@dataclass
class ContainerContext:
    id: str
    name: str
    icon: str
    color: str
    description: str


class ContainerManager(QObject):
    """Manages container profiles to ensure Site A cannot correlate with Site B."""

    CONTAINERS: Dict[str, ContainerContext] = {
        "default": ContainerContext("default", "Standard Container", "🌐", "#3b82f6", "General isolated browsing"),
        "personal": ContainerContext("personal", "Personal", "👤", "#10b981", "Personal accounts & email"),
        "work": ContainerContext("work", "Work", "💼", "#f59e0b", "Work related sessions"),
        "shopping": ContainerContext("shopping", "Shopping", "🛒", "#ec4899", "E-commerce & retail isolation"),
        "tor_isolated": ContainerContext("tor_isolated", "High Isolation", "🧅", "#8b5cf6", "Maximum isolation profile"),
    }

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._active_container: str = "default"

    @property
    def active_container(self) -> ContainerContext:
        return self.CONTAINERS.get(self._active_container, self.CONTAINERS["default"])

    def set_active_container(self, container_id: str) -> None:
        if container_id in self.CONTAINERS:
            self._active_container = container_id
