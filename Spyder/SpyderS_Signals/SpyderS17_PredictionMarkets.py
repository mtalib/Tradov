#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderS_Signals
Module: SpyderS17_PredictionMarkets.py
Purpose: Fetch live prediction-market probabilities from Kalshi for macro risk
         signals (recession probability, Fed rate-decision outcomes).  Results
         are TTL-cached so callers can invoke ``get_snapshot()`` every S07
         cycle without triggering network I/O.

API key env vars:
  KALSHI_API_KEY   – Kalshi API token (required; module degrades gracefully
                     if absent or request fails)

Outputs (keys returned by :meth:`PredictionMarketsClient.get_snapshot`):
  KALSHI_RECESSION_PROB   – float 0–1, current-year recession yes-price midpoint
  KALSHI_FED_PAUSE_PROB   – float 0–1, next-FOMC no-change yes-price midpoint
  KALSHI_AVAILABLE        – bool, True when at least one market was fetched
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
_KALSHI_BASE = "https://trading.kalshi.com/trade-api/v2"
_KALSHI_TTL_SECONDS = 600          # 10-minute cache
_REQUEST_TIMEOUT = 15              # seconds

# Kalshi series tickers to query.  The client pulls the first open market
# from each series and extracts its yes-price midpoint as a probability.
_RECESSION_SERIES = "KXRECESSION"
_FED_SERIES = "FED"

# Public keys emitted by get_snapshot()
KALSHI_RECESSION_PROB = "KALSHI_RECESSION_PROB"
KALSHI_FED_PAUSE_PROB = "KALSHI_FED_PAUSE_PROB"
KALSHI_AVAILABLE = "KALSHI_AVAILABLE"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _yes_midpoint(market: dict[str, Any]) -> float:
    """Return yes-price midpoint as a 0–1 probability.

    Kalshi prices are in cents (0–100).  Missing or zero ask defaults to 100
    to avoid a division-by-zero mid, which would produce a misleading 0%.
    """
    try:
        bid = float(market.get("yes_bid") or 0)
        ask = float(market.get("yes_ask") or 100)
        mid = (bid + ask) / 2.0
        return mid / 100.0
    except (TypeError, ValueError):
        return float("nan")


def _empty_snapshot() -> dict[str, Any]:
    return {
        KALSHI_RECESSION_PROB: float("nan"),
        KALSHI_FED_PAUSE_PROB: float("nan"),
        KALSHI_AVAILABLE: False,
    }


# ---------------------------------------------------------------------------
# PredictionMarketsClient
# ---------------------------------------------------------------------------

class PredictionMarketsClient:
    """Fetch and cache Kalshi market probabilities for macro-risk signals.

    Thread-safe: internal lock guards cache reads/writes so multiple S07
    update threads cannot race on a shared snapshot.
    """

    def __init__(self) -> None:
        self._api_key: str = os.getenv("KALSHI_API_KEY", "").strip()
        self._lock = threading.Lock()
        self._snapshot: dict[str, Any] = _empty_snapshot()
        self._last_fetch_ts: float = 0.0
        self.available: bool = bool(self._api_key)

        if not self._api_key:
            logger.debug("S17: KALSHI_API_KEY not set — prediction markets disabled")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_snapshot(self) -> dict[str, Any]:
        """Return the latest prediction-market snapshot.

        Fetches fresh data at most once per ``_KALSHI_TTL_SECONDS``.  On error
        the previous snapshot (or the empty default) is returned.

        Returns:
            dict with keys KALSHI_RECESSION_PROB, KALSHI_FED_PAUSE_PROB,
            KALSHI_AVAILABLE.
        """
        if not self._api_key:
            return _empty_snapshot()

        with self._lock:
            age = time.monotonic() - self._last_fetch_ts
            if age < _KALSHI_TTL_SECONDS:
                return dict(self._snapshot)

        # Fetch outside the lock so other threads are not blocked during I/O
        fresh = self._fetch()

        with self._lock:
            self._snapshot = fresh
            self._last_fetch_ts = time.monotonic()
            return dict(self._snapshot)

    # ------------------------------------------------------------------
    # Internal fetch
    # ------------------------------------------------------------------

    def _fetch(self) -> dict[str, Any]:
        """Query Kalshi API and build a snapshot dict."""
        headers = {"Authorization": self._api_key}
        result: dict[str, Any] = _empty_snapshot()

        try:
            recession_prob = self._fetch_series_prob(
                headers, _RECESSION_SERIES, match_title_kw="recession"
            )
            if math.isfinite(recession_prob):
                result[KALSHI_RECESSION_PROB] = recession_prob
                result[KALSHI_AVAILABLE] = True
        except Exception as exc:
            logger.debug("S17: recession market fetch failed: %s", exc)

        try:
            fed_pause_prob = self._fetch_fed_pause_prob(headers)
            if math.isfinite(fed_pause_prob):
                result[KALSHI_FED_PAUSE_PROB] = fed_pause_prob
                result[KALSHI_AVAILABLE] = True
        except Exception as exc:
            logger.debug("S17: Fed pause market fetch failed: %s", exc)

        return result

    def _fetch_series_prob(
        self, headers: dict, series_ticker: str, match_title_kw: str = ""
    ) -> float:
        """Fetch the first open market in *series_ticker* and return its yes-mid.

        Args:
            headers: Kalshi auth headers.
            series_ticker: Series ticker to filter by.
            match_title_kw: Optional keyword; if set, only markets whose title
                contains this keyword (case-insensitive) are considered.

        Returns:
            Probability 0–1 or NaN if no matching open market found.
        """
        resp = requests.get(
            f"{_KALSHI_BASE}/markets",
            headers=headers,
            params={"series_ticker": series_ticker, "status": "open", "limit": 20},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        markets: list[dict] = resp.json().get("markets", [])

        for mkt in markets:
            title = (mkt.get("title") or "").lower()
            if match_title_kw and match_title_kw.lower() not in title:
                continue
            prob = _yes_midpoint(mkt)
            if math.isfinite(prob):
                return prob

        return float("nan")

    def _fetch_fed_pause_prob(self, headers: dict) -> float:
        """Return the probability the Fed keeps rates unchanged at the next meeting.

        Strategy: look for open markets in the FED series whose title contains
        'unchanged' or 'hold' or 'pause'.  If no such market is found, fall
        back to 1 minus the first available cut/hike probability.

        Returns:
            Probability 0–1 or NaN.
        """
        resp = requests.get(
            f"{_KALSHI_BASE}/markets",
            headers=headers,
            params={"series_ticker": _FED_SERIES, "status": "open", "limit": 50},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        markets: list[dict] = resp.json().get("markets", [])

        # Priority 1: explicit "unchanged" / "hold" / "pause" market
        for mkt in markets:
            title = (mkt.get("title") or "").lower()
            if any(kw in title for kw in ("unchanged", "hold", "pause", "no change")):
                prob = _yes_midpoint(mkt)
                if math.isfinite(prob):
                    return prob

        # Priority 2: derive from cut or hike probability
        for mkt in markets:
            title = (mkt.get("title") or "").lower()
            if any(kw in title for kw in ("cut", "hike", "raise")):
                prob = _yes_midpoint(mkt)
                if math.isfinite(prob):
                    return max(0.0, 1.0 - prob)

        return float("nan")


# ---------------------------------------------------------------------------
# Module-level singleton factory
# ---------------------------------------------------------------------------

_client_instance: PredictionMarketsClient | None = None
_client_lock = threading.Lock()


def get_prediction_markets_client() -> PredictionMarketsClient:
    """Return the module-level singleton :class:`PredictionMarketsClient`.

    Thread-safe double-checked locking; safe to call from any thread.
    """
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    with _client_lock:
        if _client_instance is None:
            _client_instance = PredictionMarketsClient()
    return _client_instance
