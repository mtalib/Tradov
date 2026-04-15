#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderS_Signals
Module: SpyderS11_BarchartInternals.py
Purpose: Market breadth internals ($TICK, $ADD, $TRIN, $NYMO) via Barchart API

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-10 Time: 00:00:00

Description:
    Fetches real-time NYSE/NASDAQ market breadth (internal) indicators from the
    Barchart OnDemand API — the only free-tier API that publicly exposes these
    exchange-calculated indices by their standard $ symbols.

    These signals are NOT available from Tradier (a brokerage API, not an
    exchange data service) and NOT from FRED (macro only).  Barchart is the
    most accessible free source; a Barchart.com account provides a free API
    key with ~25 quote requests per day — more than sufficient for daily/hourly
    polling during market hours.

Market Internals Fetched
------------------------
    $TICK   — NYSE Tick Index  (upticks minus downticks, all NYSE stocks)
    $TICKQ  — NASDAQ Tick Index
    $ADD    — NYSE Advance-Decline Difference (advancing minus declining issues)
    $ADDQ   — NASDAQ Advance-Decline Difference
    $TRIN   — NYSE Arms Index / TRIN (A/D ratio ÷ up-volume/down-volume ratio)
    $TRINQ  — NASDAQ TRIN
    $NYMO   — McClellan Oscillator  (NYSE breadth momentum, EMA-derived)

Additional Breadth Proxies (ETF-derived via Barchart freeform quotes)
----------------------------------------------------------------------
    XLK / XLY / XLF — Offensive-sector comparison
    XLU / XLP / XLV — Defensive-sector comparison
    (These overlap with Tradier but are included here for a single breadth call.)

Prerequisites
-------------
    pip install requests             (already in requirements)
    BARCHART_API_KEY=<key> in .env
    — Register free at: https://www.barchart.com/ondemand/free-api-key

Usage
-----
    client = BarchartInternals()
    snap   = client.get_snapshot()
    # snap = {
    #   'tick':  +520, 'tickq': +310,
    #   'add':   +650, 'addq':  +280,
    #   'trin':   0.83, 'trinq':  0.91,
    #   'nymo':   12.4,
    #   'breadth_regime': 'bullish',   # derived composite signal
    #   'as_of':  datetime(...),
    # }
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import os
import threading
from datetime import datetime
from typing import Optional

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import requests

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    logger = SpyderLogger.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================
_BASE_URL = "https://ondemand.websol.barchart.com/getQuote.json"

# Standard NYSE/NASDAQ breadth symbols supported by Barchart
_INTERNALS_SYMBOLS = "$TICK,$TICKQ,$ADD,$ADDQ,$TRIN,$TRINQ,$NYMO"

# Fields requested from Barchart getQuote
_FIELDS = "symbol,lastPrice,tradeTime,symbolCode"

# Cache TTL during market hours — 15 minutes keeps API calls within the
# Barchart free-tier limit of ~25 requests/day (6.5 h × 60 ÷ 15 ≈ 26 calls/day)
_CACHE_TTL_MARKET_SECONDS = 15 * 60
# Cache TTL outside market hours — refresh every 60 minutes
_CACHE_TTL_CLOSED_SECONDS = 60 * 60

_HTTP_TIMEOUT = 15  # seconds

# Symbol → result dict key mapping
_SYMBOL_MAP = {
    "$TICK":  "tick",
    "$TICKQ": "tickq",
    "$ADD":   "add",
    "$ADDQ":  "addq",
    "$TRIN":  "trin",
    "$TRINQ": "trinq",
    "$NYMO":  "nymo",
}

# Composite breadth regime thresholds
_TICK_STRONG_BULL   =  600
_TICK_STRONG_BEAR   = -600
_ADD_STRONG_BULL    =  800
_ADD_STRONG_BEAR    = -800
_TRIN_BULL_THRESHOLD =  0.80   # below = bullish (volume favours advances)
_TRIN_BEAR_THRESHOLD =  1.20   # above = bearish


# ==============================================================================
# MAIN CLIENT CLASS
# ==============================================================================
class BarchartInternals:
    """
    Real-time NYSE/NASDAQ market breadth client using the Barchart OnDemand API.

    The free tier provides enough quota for every-5-minute refreshes during the
    6.5-hour trading session (~78 calls/day).  If the API key is missing or the
    network is unavailable, the client returns NaN stubs so Spyder continues
    operating in a degraded-but-functional state.

    Thread-safe via internal lock with TTL-based caching.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """
        Initialise the Barchart client.

        Args:
            api_key: Barchart OnDemand API key.  If None, reads
                ``BARCHART_API_KEY`` from the environment.
        """
        self.api_key: Optional[str] = api_key or os.getenv("BARCHART_API_KEY")
        self._cache: Optional[dict] = None
        self._cache_time: Optional[datetime] = None
        self._lock = threading.Lock()

        if not self.api_key:
            logger.warning(
                "BARCHART_API_KEY not set in environment.  "
                "BarchartInternals will return stub data for $TICK/$ADD/$TRIN/$NYMO.  "
                "Register free at: https://www.barchart.com/ondemand/free-api-key"
            )
        else:
            logger.info("BarchartInternals initialised (key loaded from environment).")

    # --------------------------------------------------------------------------
    # Public API
    # --------------------------------------------------------------------------

    def get_snapshot(self, force_refresh: bool = False) -> dict:
        """
        Return the latest market breadth snapshot.

        Caches results for 5 minutes during market hours, 60 minutes otherwise
        (TTL is conservative given the free-tier quota limit).

        Args:
            force_refresh: Bypass cache and call the API immediately.

        Returns:
            dict with keys:
                tick    — NYSE Tick Index (int, e.g. +520)
                tickq   — NASDAQ Tick Index
                add     — NYSE Advance-Decline (int, e.g. +650)
                addq    — NASDAQ Advance-Decline
                trin    — NYSE TRIN / Arms Index (float, e.g. 0.83)
                trinq   — NASDAQ TRIN
                nymo    — McClellan Oscillator (float, e.g. 12.4)
                breadth_regime — composite string: 'strong_bull', 'bull',
                                 'neutral', 'bear', 'strong_bear'
                as_of   — datetime of the most-recent Barchart quote
        """
        ttl = (
            _CACHE_TTL_MARKET_SECONDS
            if self._is_market_hours()
            else _CACHE_TTL_CLOSED_SECONDS
        )

        with self._lock:
            if not force_refresh and self._cache is not None:
                age = (datetime.now() - self._cache_time).total_seconds()
                if age < ttl:
                    return dict(self._cache)

        snapshot = self._fetch()

        with self._lock:
            self._cache = snapshot
            self._cache_time = datetime.now()

        return dict(snapshot)

    def get_tick(self) -> float:
        """Return the NYSE Tick Index value, or NaN if unavailable."""
        return self.get_snapshot().get("tick", float("nan"))

    def get_add(self) -> float:
        """Return the NYSE Advance-Decline difference, or NaN if unavailable."""
        return self.get_snapshot().get("add", float("nan"))

    def get_trin(self) -> float:
        """Return the NYSE TRIN (Arms Index), or NaN if unavailable."""
        return self.get_snapshot().get("trin", float("nan"))

    def get_nymo(self) -> float:
        """Return the NYSE McClellan Oscillator, or NaN if unavailable."""
        return self.get_snapshot().get("nymo", float("nan"))

    def get_breadth_regime(self) -> str:
        """
        Return the composite breadth regime string.

        Returns:
            One of: 'strong_bull', 'bull', 'neutral', 'bear', 'strong_bear'.
        """
        return self.get_snapshot().get("breadth_regime", "neutral")

    def get_status(self) -> dict:
        """Return operational status dict."""
        with self._lock:
            age = (
                (datetime.now() - self._cache_time).total_seconds()
                if self._cache_time
                else None
            )
        return {
            "api_key_set": bool(self.api_key),
            "cached": self._cache is not None,
            "cache_age_seconds": age,
        }

    # --------------------------------------------------------------------------
    # Internal helpers
    # --------------------------------------------------------------------------

    def _fetch(self) -> dict:
        """Call the Barchart API and parse the response."""
        if not self.api_key:
            return self._stub()

        params = {
            "apikey":  self.api_key,
            "symbols": _INTERNALS_SYMBOLS,
            "fields":  _FIELDS,
        }

        try:
            resp = requests.get(
                _BASE_URL, params=params, timeout=_HTTP_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.warning("Barchart API request failed: %s — returning stubs.", exc)
            return self._stub()
        except ValueError as exc:
            logger.warning("Barchart API JSON decode error: %s — returning stubs.", exc)
            return self._stub()

        # Validate top-level response status
        status = data.get("status", {})
        if status.get("code") not in (200, "200"):
            logger.warning(
                "Barchart API error %s: %s — returning stubs.",
                status.get("code"), status.get("message"),
            )
            return self._stub()

        results = data.get("results", [])
        snapshot: dict = {key: float("nan") for key in _SYMBOL_MAP.values()}
        as_of: Optional[datetime] = None

        for quote in results:
            raw_symbol = quote.get("symbol", "").upper()
            key = _SYMBOL_MAP.get(raw_symbol)
            if key is None:
                continue

            last_price = quote.get("lastPrice")
            if last_price is not None:
                try:
                    snapshot[key] = float(last_price)
                except (TypeError, ValueError):
                    pass

            trade_time = quote.get("tradeTime")
            if trade_time and as_of is None:
                try:
                    as_of = datetime.fromisoformat(str(trade_time))
                except (ValueError, TypeError):
                    pass

        snapshot["breadth_regime"] = self._classify_breadth(snapshot)
        snapshot["as_of"] = as_of or datetime.now()
        return snapshot

    def _classify_breadth(self, snap: dict) -> str:
        """
        Derive a composite breadth regime label from TICK, ADD, and TRIN.

        Logic (in priority order):
          1. strong_bull — TICK > 600 AND ADD > 800 AND TRIN < 0.80
          2. strong_bear — TICK < -600 AND ADD < -800 AND TRIN > 1.20
          3. bull        — majority of TICK/ADD/TRIN signals are bullish
          4. bear        — majority are bearish
          5. neutral     — mixed signals

        Returns:
            Regime string label.
        """
        tick  = snap.get("tick",  float("nan"))
        add   = snap.get("add",   float("nan"))
        trin  = snap.get("trin",  float("nan"))

        nan = float("nan")
        signals_available = sum(1 for v in (tick, add, trin) if v == v)  # NaN check

        if signals_available == 0:
            return "neutral"

        # Strong regimes require all three signals to align
        if (
            tick == tick and tick > _TICK_STRONG_BULL
            and add == add and add > _ADD_STRONG_BULL
            and trin == trin and trin < _TRIN_BULL_THRESHOLD
        ):
            return "strong_bull"

        if (
            tick == tick and tick < _TICK_STRONG_BEAR
            and add == add and add < _ADD_STRONG_BEAR
            and trin == trin and trin > _TRIN_BEAR_THRESHOLD
        ):
            return "strong_bear"

        # Majority vote among available signals
        bull_votes = 0
        bear_votes = 0

        if tick == tick:  # not NaN
            if tick > 0:   bull_votes += 1
            else:          bear_votes += 1

        if add == add:
            if add > 0:    bull_votes += 1
            else:          bear_votes += 1

        if trin == trin:
            if trin < 1.0: bull_votes += 1
            else:          bear_votes += 1

        if bull_votes > bear_votes:
            return "bull"
        elif bear_votes > bull_votes:
            return "bear"
        return "neutral"

    def _stub(self) -> dict:
        """Return NaN-filled stub snapshot."""
        stub = {key: float("nan") for key in _SYMBOL_MAP.values()}
        stub["breadth_regime"] = "neutral"
        stub["as_of"] = datetime.now()
        return stub

    @staticmethod
    def _is_market_hours() -> bool:
        """
        Rough check: True during NYSE regular hours (09:30–16:00 ET Mon–Fri).

        Uses UTC offset -4 (EDT) — does not handle DST transitions precisely.
        Good enough for cache TTL selection; not used for trade decisions.
        """
        from datetime import timezone, timedelta as td
        et = datetime.now(timezone(td(hours=-4)))
        if et.weekday() >= 5:        # Saturday or Sunday
            return False
        market_open  = et.replace(hour=9,  minute=30, second=0, microsecond=0)
        market_close = et.replace(hour=16, minute=0,  second=0, microsecond=0)
        return market_open <= et <= market_close


# ==============================================================================
# MODULE-LEVEL SINGLETON
# ==============================================================================
_barchart_client: Optional[BarchartInternals] = None


def get_barchart_client() -> BarchartInternals:
    """Return the module-level BarchartInternals singleton."""
    global _barchart_client
    if _barchart_client is None:
        _barchart_client = BarchartInternals()
    return _barchart_client
