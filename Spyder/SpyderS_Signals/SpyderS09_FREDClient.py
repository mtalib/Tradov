#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderS_Signals
Module: SpyderS09_FREDClient.py
Purpose: FRED (Federal Reserve Economic Data) API client for macro/yield signals

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-10 Time: 00:00:00

Description:
    Fetches macro-economic time series from the St. Louis Federal Reserve FRED
    API.  Provides daily Treasury yield curve data, the Fed Funds Target Rate,
    the BIS/Fed broad USD index (DXY proxy), and yield-spread signals that feed
    directly into Spyder's regime classification and risk management layers.

    Data is daily (updated once per business day by FRED) and cached in-process
    so callers can poll the module frequently without hammering the API.

Key FRED Series Used
---------------------
    GS2      — 2-Year Treasury Constant Maturity Rate (%)
    GS5      — 5-Year Treasury Constant Maturity Rate (%)
    GS10     — 10-Year Treasury Constant Maturity Rate (%)
    GS30     — 30-Year Treasury Constant Maturity Rate (%)
    DFEDTARU — Federal Funds Target Rate Upper Bound (%)
    T10Y2Y   — 10-Year minus 2-Year Treasury spread (%, inversion signal)
    T10Y3M   — 10-Year minus 3-Month Treasury spread (%, inversion signal)
    DTWEXBGS — Trade Weighted USD Index: Broad, Goods (DXY proxy, index level)
    VIXCLS   — CBOE VIX daily close (backup for live VIX when market is closed)

Prerequisites
-------------
    pip install fredapi           (already in requirements; used by SpyderC22)
    FRED_API_KEY=<key> in .env    (free at https://fred.stlouisfed.org/docs/api/api_key.html)

Usage
-----
    client = FREDClient()
    snapshot = client.get_snapshot()
    # snapshot = {
    #   'yield_2y': 4.72, 'yield_5y': 4.51, 'yield_10y': 4.35, 'yield_30y': 4.52,
    #   'fed_funds_target_upper': 5.25, 'spread_10y_2y': -0.37,
    #   'spread_10y_3m': -0.88, 'dxy_broad': 103.4, 'vix_close': 15.2,
    #   'yield_curve_inverted': True, 'as_of': datetime(...),
    # }
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Optional

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from fredapi import Fred
    FREDAPI_AVAILABLE = True
except ImportError:
    FREDAPI_AVAILABLE = False

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
# FRED series IDs
_SERIES = {
    "yield_2y":                "GS2",
    "yield_5y":                "GS5",
    "yield_10y":               "GS10",
    "yield_30y":               "GS30",
    "fed_funds_target_upper":  "DFEDTARU",
    "spread_10y_2y":           "T10Y2Y",
    "spread_10y_3m":           "T10Y3M",
    "dxy_broad":               "DTWEXBGS",
    "vix_close":               "VIXCLS",
}

# Cache TTL: FRED data is published once per business day — cache for 4 hours
_CACHE_TTL_SECONDS = 4 * 60 * 60

# Number of recent observations to fetch per series (daily, last 5 trading days)
_OBSERVATION_LOOKBACK = "5"


# ==============================================================================
# MAIN CLIENT CLASS
# ==============================================================================
class FREDClient:
    """
    Fetches daily macro signals from the FRED API and exposes them as a unified
    snapshot dictionary for regime classification, risk management, and charting.

    Thread-safe; uses an internal lock and TTL-based in-process cache so that
    multiple Spyder subsystems can call ``get_snapshot()`` freely.

    Attributes:
        api_key (str | None): FRED API key loaded from FRED_API_KEY env var.
        _fred (Fred | None): fredapi client instance, None if key unavailable.
        _cache (dict | None): Last successfully fetched snapshot.
        _cache_time (datetime | None): Timestamp of the cached snapshot.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """
        Initialise the FRED client.

        Args:
            api_key: FRED API key.  If None, reads ``FRED_API_KEY`` from the
                environment.  If neither is available, the client runs in
                stub/offline mode (returns NaN placeholders).
        """
        self.api_key: Optional[str] = api_key or os.getenv("FRED_API_KEY")
        self._fred: Optional[Fred] = None
        self._cache: Optional[dict] = None
        self._cache_time: Optional[datetime] = None
        self._lock = threading.Lock()

        if not FREDAPI_AVAILABLE:
            logger.warning(
                "fredapi package not installed. Run: pip install fredapi. "
                "FREDClient will return stub data."
            )
            return

        if not self.api_key:
            logger.warning(
                "FRED_API_KEY not set in environment. "
                "FREDClient will return stub data. "
                "Get a free key at: https://fred.stlouisfed.org/docs/api/api_key.html"
            )
            return

        self._fred = Fred(api_key=self.api_key)
        logger.info("FREDClient initialised (key loaded from environment).")

    # --------------------------------------------------------------------------
    # Public API
    # --------------------------------------------------------------------------

    def get_snapshot(self, force_refresh: bool = False) -> dict:
        """
        Return the latest macro snapshot, using cached data if fresh enough.

        Args:
            force_refresh: If True, bypass the cache and fetch from FRED now.

        Returns:
            dict with the following keys (float values, NaN when unavailable):
                yield_2y              — 2-Year Treasury yield (%)
                yield_5y              — 5-Year Treasury yield (%)
                yield_10y             — 10-Year Treasury yield (%)
                yield_30y             — 30-Year Treasury yield (%)
                fed_funds_target_upper — Fed Funds Target upper bound (%)
                spread_10y_2y         — 10Y minus 2Y spread (%, negative = inverted)
                spread_10y_3m         — 10Y minus 3M spread (%, negative = inverted)
                dxy_broad             — Broad USD Index level (DXY proxy)
                vix_close             — Previous-day VIX close (backup source)
                yield_curve_inverted  — True if spread_10y_2y < 0
                as_of                 — datetime of the most recent observation
        """
        with self._lock:
            if not force_refresh and self._cache is not None:
                age = (datetime.now() - self._cache_time).total_seconds()
                if age < _CACHE_TTL_SECONDS:
                    return dict(self._cache)

        snapshot = self._fetch_all()

        with self._lock:
            self._cache = snapshot
            self._cache_time = datetime.now()

        return dict(snapshot)

    def get_yield_curve_slope(self) -> float:
        """
        Return the 10Y-2Y Treasury spread as a float (%).

        A negative value (inverted curve) is a well-known recession leading
        indicator and triggers more defensive strategy selection in Spyder.

        Returns:
            Spread in percentage points, or float('nan') if unavailable.
        """
        return self.get_snapshot().get("spread_10y_2y", float("nan"))

    def is_yield_curve_inverted(self) -> bool:
        """
        Return True if the 10Y-2Y yield spread is currently negative.

        Returns:
            bool — True when curve is inverted (spread < 0).
        """
        slope = self.get_yield_curve_slope()
        if slope != slope:  # NaN check
            return False
        return slope < 0.0

    def get_dxy(self) -> float:
        """
        Return the broad USD index level (FRED DTWEXBGS, a DXY proxy).

        Returns:
            Index level as float, or float('nan') if unavailable.
        """
        return self.get_snapshot().get("dxy_broad", float("nan"))

    def get_10y_yield(self) -> float:
        """
        Return the 10-Year Treasury yield (%).

        Returns:
            Yield as float (e.g. 4.35), or float('nan') if unavailable.
        """
        return self.get_snapshot().get("yield_10y", float("nan"))

    def get_status(self) -> dict:
        """
        Return the operational status of this client.

        Returns:
            dict with keys: available (bool), cached (bool), cache_age_seconds (float).
        """
        with self._lock:
            age = (
                (datetime.now() - self._cache_time).total_seconds()
                if self._cache_time
                else None
            )
        return {
            "available": self._fred is not None,
            "cached": self._cache is not None,
            "cache_age_seconds": age,
        }

    # --------------------------------------------------------------------------
    # Internal helpers
    # --------------------------------------------------------------------------

    def _fetch_all(self) -> dict:
        """Fetch the latest observation for each configured series from FRED."""
        if self._fred is None:
            return self._stub_snapshot()

        result: dict = {}
        as_of: Optional[datetime] = None

        for key, series_id in _SERIES.items():
            try:
                series = self._fred.get_series_latest_release(series_id)
                if series is None or series.empty:
                    result[key] = float("nan")
                    continue
                latest = series.dropna()
                if latest.empty:
                    result[key] = float("nan")
                    continue
                value = float(latest.iloc[-1])
                index_dt = latest.index[-1]
                # Track the most-recent observation date across all series
                if hasattr(index_dt, "to_pydatetime"):
                    dt = index_dt.to_pydatetime()
                    if as_of is None or dt > as_of:
                        as_of = dt
                result[key] = value
            except Exception as exc:
                logger.debug("FRED series %s fetch failed: %s", series_id, exc)
                result[key] = float("nan")

        result["yield_curve_inverted"] = (
            result.get("spread_10y_2y", 0.0) < 0.0
            if result.get("spread_10y_2y") == result.get("spread_10y_2y")  # NaN guard
            else False
        )
        result["as_of"] = as_of or datetime.now()
        return result

    def _stub_snapshot(self) -> dict:
        """Return a NaN-filled stub when FRED is unavailable."""
        stub = {k: float("nan") for k in _SERIES}
        stub["yield_curve_inverted"] = False
        stub["as_of"] = datetime.now()
        return stub


# ==============================================================================
# MODULE-LEVEL SINGLETON
# ==============================================================================
_fred_client: Optional[FREDClient] = None


def get_fred_client() -> FREDClient:
    """Return the module-level FREDClient singleton."""
    global _fred_client
    if _fred_client is None:
        _fred_client = FREDClient()
    return _fred_client
