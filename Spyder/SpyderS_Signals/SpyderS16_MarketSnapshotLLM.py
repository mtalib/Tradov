#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderS_Signals
Module: SpyderS16_MarketSnapshotLLM.py
Purpose: Generate a concise (~60-word) market context paragraph from structured
         S07 metrics using the OpenRouter LLM gateway. Falls back to a
         deterministic template when OPENROUTER_API_KEY is absent or the
         request fails.

API key env vars:
  OPENROUTER_API_KEY  – OpenRouter gateway API key (optional)
  OPENROUTER_MODEL    – Model identifier (default: openai/gpt-4o-mini)

The snapshot is cached for SNAPSHOT_TTL_SECONDS (default 15 min) so this
module can be called every S07 cycle without triggering repeated LLM calls.
All network I/O must happen off the Qt main thread.
"""

from __future__ import annotations

import math
import os
import threading
import time
from typing import Any

import requests

from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

logger = SpyderLogger.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_MODEL = "openai/gpt-4o-mini"
_SNAPSHOT_TTL_SECONDS = 900   # 15-minute cache; avoid LLM calls every cycle
_REQUEST_TIMEOUT = 20         # seconds

MARKET_SNAPSHOT_TEXT = "MARKET_SNAPSHOT_TEXT"  # key for the generated paragraph


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any, default: float = float("nan")) -> float:
    """Coerce *value* to float, returning *default* on failure or NaN input."""
    try:
        f = float(value)
        return default if not math.isfinite(f) else f
    except (TypeError, ValueError):
        return default


def _metric_val(metrics: dict, key: str, default: float = float("nan")) -> float:
    """Extract a numeric value from a formatted S07 metrics dict entry."""
    entry = metrics.get(key)
    if isinstance(entry, dict):
        return _safe_float(entry.get("value", default), default)
    return _safe_float(entry, default) if entry is not None else default


def _metric_str(metrics: dict, key: str, default: str = "—") -> str:
    """Extract a string value from a formatted S07 metrics dict entry."""
    entry = metrics.get(key)
    if isinstance(entry, dict):
        v = entry.get("value", default)
        return str(v) if v is not None else default
    return str(entry) if entry is not None else default


# ---------------------------------------------------------------------------
# Deterministic fallback generator
# ---------------------------------------------------------------------------

def _build_fallback_text(metrics: dict) -> str:
    """Return a template-based market summary when the LLM is unavailable."""
    swan = _metric_val(metrics, "SWAN", 1.85)
    dix = _metric_val(metrics, "DIX", 42.5)
    gex = _metric_val(metrics, "GEX", 0.0)
    skew = _metric_val(metrics, "SKEW", 120.0)
    breadth = _metric_str(metrics, "BREADTH_REGIME", "neutral").lower()
    news_verdict = _metric_str(metrics, "NEWS_FLOW_VERDICT", "neutral").lower()
    adanos_entry = metrics.get("ADANOS_SENTIMENT", {})
    if isinstance(adanos_entry, dict):
        adanos_inner = adanos_entry.get("value", adanos_entry)
    else:
        adanos_inner = {}
    adanos_trend = (
        adanos_inner.get("trend", "neutral")
        if isinstance(adanos_inner, dict)
        else "neutral"
    )

    risk_tone = "elevated" if swan >= 1.95 else "contained"
    dark_pool = "accumulating" if dix >= 45.0 else "light"
    dealer_stance = "long gamma" if gex > 0 else "short gamma"
    skew_tone = "stressed" if skew >= 135 else ("compressed" if skew < 115 else "normal")

    return (
        f"Market risk is {risk_tone} (SWAN {swan:.2f}). "
        f"Dark-pool flow is {dark_pool} (DIX {dix:.1f}%). "
        f"Dealers are {dealer_stance} (GEX {gex:+.1f}B). "
        f"Skew is {skew_tone} at {skew:.0f}. "
        f"Breadth regime: {breadth}. "
        f"News flow: {news_verdict}. "
        f"Social sentiment: {adanos_trend}."
    )


# ---------------------------------------------------------------------------
# MarketSnapshotLLM
# ---------------------------------------------------------------------------

class MarketSnapshotLLM:
    """Generates and caches an LLM-authored market context paragraph.

    Call :meth:`get_snapshot_text` from a worker thread; it refreshes from the
    LLM only when the TTL has expired.
    """

    def __init__(self) -> None:
        self._api_key: str | None = os.getenv("OPENROUTER_API_KEY") or None
        self._model: str = os.getenv("OPENROUTER_MODEL") or _DEFAULT_MODEL

        self._lock = threading.Lock()
        self._cached_text: str = ""
        self._cache_ts: float = 0.0

        logger.debug(
            "S16_MarketSnapshotLLM init | openrouter=%s model=%s",
            "key-set" if self._api_key else "no-key",
            self._model,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_snapshot_text(self, metrics: dict) -> str:
        """Return a ≤60-word market context paragraph.

        Refreshes from the LLM only when the TTL has expired.  Falls back to
        the deterministic template immediately when OpenRouter is unavailable.

        Args:
            metrics: The formatted metrics dict from S07 ``_format_metrics()``.

        Returns:
            Plain-text market summary string.
        """
        with self._lock:
            now = time.monotonic()
            if self._cached_text and (now - self._cache_ts) < _SNAPSHOT_TTL_SECONDS:
                return self._cached_text

            text = self._generate(metrics)
            self._cached_text = text
            self._cache_ts = now
            return text

    # ------------------------------------------------------------------
    # Internal generation
    # ------------------------------------------------------------------

    def _generate(self, metrics: dict) -> str:
        """Try LLM; fall back to template on any failure."""
        if not self._api_key:
            return _build_fallback_text(metrics)
        try:
            return self._call_openrouter(metrics)
        except Exception as exc:
            logger.warning("OpenRouter call failed (%s) — using fallback", exc)
            return _build_fallback_text(metrics)

    def _call_openrouter(self, metrics: dict) -> str:
        """Issue the OpenRouter API request and return the generated text."""
        swan = _metric_val(metrics, "SWAN", 1.85)
        dix = _metric_val(metrics, "DIX", 42.5)
        gex = _metric_val(metrics, "GEX", 0.0)
        skew = _metric_val(metrics, "SKEW", 120.0)
        breadth = _metric_str(metrics, "BREADTH_REGIME", "neutral")

        # Pull market-intel keys written by S15 (may be nested or flat)
        news_verdict = _metric_str(metrics, "NEWS_FLOW_VERDICT", "neutral")
        news_headline = _metric_str(metrics, "NEWS_FLOW_HEADLINE", "")

        adanos_entry = metrics.get("ADANOS_SENTIMENT", {})
        if isinstance(adanos_entry, dict):
            adanos_inner = adanos_entry.get("value", adanos_entry)
        else:
            adanos_inner = {}
        adanos_trend = (
            adanos_inner.get("trend", "neutral")
            if isinstance(adanos_inner, dict)
            else "neutral"
        )

        data_block = (
            f"SWAN risk score: {swan:.2f}\n"
            f"DIX dark-pool flow: {dix:.1f}%\n"
            f"GEX dealer gamma: {gex:+.1f}B\n"
            f"SKEW tail risk: {skew:.0f}\n"
            f"Breadth regime: {breadth}\n"
            f"News flow verdict: {news_verdict}\n"
            f"Latest headline: {news_headline[:120] if news_headline else 'n/a'}\n"
            f"Social sentiment trend: {adanos_trend}"
        )

        prompt = (
            "You are a concise quantitative market analyst. "
            "Based on the data below, write a single paragraph of 55 words or fewer "
            "summarising current market conditions. "
            "Be specific, factual, and plain-language. No markdown, no bullet points.\n\n"
            f"{data_block}"
        )

        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 120,
            "temperature": 0.3,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        resp = requests.post(
            _OPENROUTER_URL, json=payload, headers=headers, timeout=_REQUEST_TIMEOUT
        )
        if resp.status_code != 200:
            raise RuntimeError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:200]}")

        body = resp.json()
        text = (
            body.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not text:
            raise ValueError("Empty response from OpenRouter")
        return text


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------
_instance: MarketSnapshotLLM | None = None
_instance_lock = threading.Lock()


def get_market_snapshot_llm() -> MarketSnapshotLLM:
    """Return the module-level singleton :class:`MarketSnapshotLLM`."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = MarketSnapshotLLM()
    return _instance
