#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderJ_Alerts
Module: SpyderJ03_WebhookNotifier.py
Purpose: HTTP webhook notifications for Slack, Microsoft Teams, and Discord

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-01

Module Description:
    Generic HTTP webhook notifier that supports Slack incoming webhooks,
    Microsoft Teams connectors, and Discord webhooks.  Configuration is
    read from environment variables or the Spyder config system.

    Environment variables (any subset may be set):
        SPYDER_SLACK_WEBHOOK_URL   — Slack incoming webhook URL
        SPYDER_TEAMS_WEBHOOK_URL   — Microsoft Teams connector URL
        SPYDER_DISCORD_WEBHOOK_URL — Discord webhook URL

    All sends are fire-and-forget with exponential-backoff retry (3 attempts).
    Failures are logged as warnings; they never raise exceptions to the caller.

Key Features:
    • Slack, Teams, Discord in a single class
    • Exponential-backoff retry (up to 3 attempts)
    • Colour-coded severity levels (info / warning / critical)
    • Optional alert title and optional field attachments
    • Thread-safe (uses urllib — no external HTTP library required)

Dependencies:
    • Python standard library only (urllib, json, os, threading)
    • SpyderU01_Logger (graceful fallback to stdlib logging)
"""

from __future__ import annotations

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import StrEnum
from threading import Lock
from typing import Any
from datetime import UTC

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    _log = SpyderLogger.get_logger(__name__)
except ImportError:
    _log = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================
_ENV_SLACK   = "SPYDER_SLACK_WEBHOOK_URL"
_ENV_TEAMS   = "SPYDER_TEAMS_WEBHOOK_URL"
_ENV_DISCORD = "SPYDER_DISCORD_WEBHOOK_URL"

_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY = 1.0   # seconds; doubled on each retry

# Colour hex codes for severity levels (used by Teams / Discord)
_COLOURS: dict[str, int] = {
    "info":     0x2196F3,   # blue
    "warning":  0xFFC107,   # amber
    "critical": 0xF44336,   # red
}
_SLACK_COLOURS: dict[str, str] = {
    "info":     "#2196F3",
    "warning":  "#FFC107",
    "critical": "#F44336",
}


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

class Severity(StrEnum):
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"


@dataclass
class WebhookField:
    """Optional key-value field appended to a notification."""
    title: str
    value: str
    short: bool = True


@dataclass
class WebhookConfig:
    """Runtime configuration for WebhookNotifier."""
    slack_url:   str | None = field(default_factory=lambda: os.getenv(_ENV_SLACK))
    teams_url:   str | None = field(default_factory=lambda: os.getenv(_ENV_TEAMS))
    discord_url: str | None = field(default_factory=lambda: os.getenv(_ENV_DISCORD))


# ==============================================================================
# MAIN CLASS
# ==============================================================================

class WebhookNotifier:
    """
    HTTP webhook notifier for Slack, Microsoft Teams, and Discord.

    Usage::

        notifier = WebhookNotifier()
        notifier.send(message="SPY alert fired", severity=Severity.CRITICAL)

        # Platform-specific helpers:
        notifier.send_slack(message="...", title="Black Swan")
        notifier.send_teams(message="...", severity=Severity.WARNING)
        notifier.send_discord(message="...", fields=[WebhookField("Strike", "590")])
    """

    def __init__(self, config: WebhookConfig | None = None) -> None:
        self._config = config or WebhookConfig()
        self._lock   = Lock()
        self._log    = _log

    # --------------------------------------------------------------------------
    # Public API
    # --------------------------------------------------------------------------

    def send(
        self,
        message:  str,
        title:    str = "Spyder Alert",
        severity: Severity | str = Severity.INFO,
        fields:   list[WebhookField] | None = None,
    ) -> None:
        """Broadcast to all configured platforms."""
        sev = Severity(severity) if isinstance(severity, str) else severity
        self.send_slack(message=message, title=title, severity=sev, fields=fields)
        self.send_teams(message=message, title=title, severity=sev, fields=fields)
        self.send_discord(message=message, title=title, severity=sev, fields=fields)

    def send_slack(
        self,
        message:  str,
        title:    str = "Spyder Alert",
        severity: Severity | str = Severity.INFO,
        fields:   list[WebhookField] | None = None,
    ) -> bool:
        """Send a Slack incoming-webhook message.  Returns True on success."""
        url = self._config.slack_url
        if not url:
            self._log.debug("Slack webhook URL not configured — skipping")
            return False
        sev = Severity(severity) if isinstance(severity, str) else severity
        payload = self._build_slack_payload(message, title, sev, fields or [])
        return self._post(url, payload, platform="Slack")

    def send_teams(
        self,
        message:  str,
        title:    str = "Spyder Alert",
        severity: Severity | str = Severity.INFO,
        fields:   list[WebhookField] | None = None,
    ) -> bool:
        """Send a Microsoft Teams connector card.  Returns True on success."""
        url = self._config.teams_url
        if not url:
            self._log.debug("Teams webhook URL not configured — skipping")
            return False
        sev = Severity(severity) if isinstance(severity, str) else severity
        payload = self._build_teams_payload(message, title, sev, fields or [])
        return self._post(url, payload, platform="Teams")

    def send_discord(
        self,
        message:  str,
        title:    str = "Spyder Alert",
        severity: Severity | str = Severity.INFO,
        fields:   list[WebhookField] | None = None,
    ) -> bool:
        """Send a Discord embed.  Returns True on success."""
        url = self._config.discord_url
        if not url:
            self._log.debug("Discord webhook URL not configured — skipping")
            return False
        sev = Severity(severity) if isinstance(severity, str) else severity
        payload = self._build_discord_payload(message, title, sev, fields or [])
        return self._post(url, payload, platform="Discord")

    def is_configured(self) -> bool:
        """Return True if at least one webhook URL is set."""
        return any([
            self._config.slack_url,
            self._config.teams_url,
            self._config.discord_url,
        ])

    def configured_platforms(self) -> list[str]:
        """Return configured webhook platform names in lowercase."""
        platforms: list[str] = []
        if self._config.slack_url:
            platforms.append("slack")
        if self._config.teams_url:
            platforms.append("teams")
        if self._config.discord_url:
            platforms.append("discord")
        return platforms

    # --------------------------------------------------------------------------
    # Payload builders
    # --------------------------------------------------------------------------

    def _build_slack_payload(
        self,
        message: str,
        title: str,
        severity: Severity,
        fields: list[WebhookField],
    ) -> dict[str, Any]:
        attachment: dict[str, Any] = {
            "color":      _SLACK_COLOURS[severity.value],
            "title":      title,
            "text":       message,
            "footer":     "Spyder Trading System",
            "ts":         int(time.time()),
        }
        if fields:
            attachment["fields"] = [
                {"title": f.title, "value": f.value, "short": f.short}
                for f in fields
            ]
        return {"attachments": [attachment]}

    def _build_teams_payload(
        self,
        message: str,
        title: str,
        severity: Severity,
        fields: list[WebhookField],
    ) -> dict[str, Any]:
        colour_hex = format(_COLOURS[severity.value], "06X")
        card: dict[str, Any] = {
            "@type":      "MessageCard",
            "@context":   "http://schema.org/extensions",
            "themeColor": colour_hex,
            "summary":    title,
            "sections": [
                {
                    "activityTitle":    title,
                    "activitySubtitle": message,
                    "facts": [
                        {"name": f.title, "value": f.value}
                        for f in fields
                    ],
                    "markdown": True,
                }
            ],
        }
        return card

    def _build_discord_payload(
        self,
        message: str,
        title: str,
        severity: Severity,
        fields: list[WebhookField],
    ) -> dict[str, Any]:
        embed: dict[str, Any] = {
            "title":       title,
            "description": message,
            "color":       _COLOURS[severity.value],
            "footer":      {"text": "Spyder Trading System"},
            "timestamp":   _iso_now(),
        }
        if fields:
            embed["fields"] = [
                {"name": f.title, "value": f.value, "inline": f.short}
                for f in fields
            ]
        return {"embeds": [embed]}

    # --------------------------------------------------------------------------
    # HTTP transport with retry
    # --------------------------------------------------------------------------

    def _post(self, url: str, payload: dict[str, Any], platform: str) -> bool:
        """POST JSON payload to *url* with exponential-backoff retry."""
        data = json.dumps(payload).encode("utf-8")
        delay = _RETRY_BASE_DELAY
        for attempt in range(1, _RETRY_ATTEMPTS + 1):
            try:
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status < 300:
                        self._log.info("%s webhook delivered (attempt %d)", platform, attempt)
                        return True
                    self._log.warning(
                        "%s webhook returned HTTP %d (attempt %d/%d)",
                        platform, resp.status, attempt, _RETRY_ATTEMPTS,
                    )
            except urllib.error.HTTPError as exc:
                self._log.warning(
                    "%s webhook HTTP error %d (attempt %d/%d): %s",
                    platform, exc.code, attempt, _RETRY_ATTEMPTS, exc,
                )
            except Exception as exc:
                self._log.warning(
                    "%s webhook failed (attempt %d/%d): %s",
                    platform, attempt, _RETRY_ATTEMPTS, exc,
                )
            if attempt < _RETRY_ATTEMPTS:
                time.sleep(delay)
                delay *= 2
        self._log.error("%s webhook failed after %d attempts", platform, _RETRY_ATTEMPTS)
        return False


# ==============================================================================
# MODULE HELPERS
# ==============================================================================

def _iso_now() -> str:
    """Return current UTC time as an ISO-8601 string."""
    from datetime import datetime
    return datetime.now(UTC).isoformat()


# Module-level singleton for convenience
_instance: WebhookNotifier | None = None
_instance_lock = Lock()


def get_notifier(config: WebhookConfig | None = None) -> WebhookNotifier:
    """Return the module-level WebhookNotifier singleton."""
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = WebhookNotifier(config)
    return _instance
