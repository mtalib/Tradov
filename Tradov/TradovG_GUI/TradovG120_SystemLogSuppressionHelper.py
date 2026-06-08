#!/usr/bin/env python3
"""Pure system-log suppression helpers for dashboard log filtering."""

from __future__ import annotations


OPENING_WARMUP_ALLOWED_PREFIXES = (
    "🟡 Establishing live connections",
    "⏳ ENTRY gate remains blocked until",
)

ALWAYS_VISIBLE_PREFIXES: tuple[str, ...] = ()

OPENING_WARMUP_QUIET_PREFIXES = (
    "📦 Restored ",
    "♻️ Loaded paper positions from saved session state",
    "✅ Startup readiness validated",
    "✅ Connected to Tradier API",
    "🔌 Disconnected from Tradier API",
    "📊 Market closed - API disconnected",
    "✅ Custom metrics orchestrator started",
    "AUTONOMOUS METRICS ACTIVE",
    "🔥 Real data detected",
    "🔥 Applying proven real data patch",
    "🔥 REAL MARKET DATA ACTIVE",
    "Real-time market data from Tradier",
    "📊 EOD snapshot loaded",
    "📊 Real EOD data loaded from Tradier",
    "📊 EOD MARKET DATA ACTIVE - Tradier API prices",
    "EOD market data from Tradier",
    "✅ Real data patch applied successfully!",
    "✅ Stopped simulation timer",
    "⚠️ EOD snapshot unavailable",
    "📊 No real data detected",
    "📊 Starting with simulation",
)

AFTER_HOURS_QUIET_PREFIXES = (
    "📊 EOD snapshot loaded",
    "📊 Real EOD data loaded from Tradier",
    "📊 EOD MARKET DATA ACTIVE - Tradier API prices",
    "EOD market data from Tradier",
    "✅ Real data patch applied successfully!",
    "✅ Custom metrics orchestrator started (DIX + Black Swan schedulers active)",
    "AUTONOMOUS METRICS ACTIVE - DIX/SWAN stress monitor online",
    "📦 Restored ",
)


def _normalize_system_log_message(message: object) -> str:
    """Normalize a log message for prefix-based suppression checks."""
    return str(message or "").strip()


def should_suppress_opening_warmup_system_log_text(message: object) -> bool:
    """Return True when an opening-warmup log line should stay quiet."""
    text = _normalize_system_log_message(message)
    if not text:
        return False
    if text.startswith(ALWAYS_VISIBLE_PREFIXES):
        return False
    if text.startswith(OPENING_WARMUP_ALLOWED_PREFIXES):
        return False
    return text.startswith(OPENING_WARMUP_QUIET_PREFIXES)


def should_suppress_after_hours_system_log_text(message: object) -> bool:
    """Return True when an after-hours log line should stay quiet."""
    text = _normalize_system_log_message(message)
    if not text:
        return False
    if text.startswith(ALWAYS_VISIBLE_PREFIXES):
        return False
    return text.startswith(AFTER_HOURS_QUIET_PREFIXES)
