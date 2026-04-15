#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderS_Signals
Module: SpyderS10_SentimentScraper.py
Purpose: Weekly AAII and NAAIM sentiment data scrapers

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-10 Time: 00:00:00

Description:
    Downloads and parses weekly investor sentiment surveys from:

    1. AAII (American Association of Individual Investors)
       Published: Every Thursday
       URL: https://www.aaii.com/files/surveys/sentiment.xls
       Signals: Bullish %, Neutral %, Bearish %, Bull-Bear Spread
       Contrarian use: Extreme bearish readings (>50%) are historically bullish
       for SPY over the following 6-12 weeks.

    2. NAAIM (National Association of Active Investment Managers)
       Published: Every Wednesday
       URL: https://www.naaim.org/wp-content/uploads/NAAIM_Exposure_data.xlsx
       Signal: Exposure Index (average money-manager equity allocation, 0-200%)
       Contrarian use: Readings <40 signal under-invested managers who may chase.

    Both scrapers cache data for the duration of the trading week and return
    NaN-filled stubs when their sources are unreachable, so Spyder continues
    operating even without internet access to these endpoints.

Prerequisites
-------------
    pip install openpyxl requests    (both already in requirements)
    No API key required — public data, free download.

Usage
-----
    scraper = SentimentScraper()
    snap = scraper.get_snapshot()
    # snap = {
    #   'aaii_bullish': 32.1, 'aaii_bearish': 41.8, 'aaii_neutral': 26.1,
    #   'aaii_bull_bear_spread': -9.7, 'aaii_extreme_fear': True,
    #   'naaim_exposure': 58.3, 'naaim_under_invested': False,
    #   'aaii_as_of': date(...), 'naaim_as_of': date(...),
    # }
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import io
import logging
import os
import threading
from datetime import date, datetime, timedelta
from typing import Optional

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import requests

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False  # Highly unlikely given the rest of Spyder

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
_AAII_URL = "https://www.aaii.com/files/surveys/sentiment.xls"
_NAAIM_URL = (
    "https://www.naaim.org/wp-content/uploads/NAAIM_Exposure_data.xlsx"
)

# Cache for one full trading week (until the next publication)
_AAII_CACHE_TTL_SECONDS  = 7 * 24 * 60 * 60   # 7 days (published Thursday)
_NAAIM_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60   # 7 days (published Wednesday)

_HTTP_TIMEOUT = 30  # seconds

# AAII thresholds for contrarian signals
_AAII_EXTREME_BEARISH_THRESHOLD = 40.0   # bearish% > 40 → contrarian bullish
_AAII_EXTREME_BULLISH_THRESHOLD = 50.0   # bullish% > 50 → contrarian bearish

# NAAIM thresholds
_NAAIM_UNDER_INVESTED_THRESHOLD  = 40.0  # managers < 40% allocated → may chase
_NAAIM_OVER_INVESTED_THRESHOLD   = 90.0  # managers > 90% allocated → crowded long

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SpyderTradingBot/1.0; "
        "+https://github.com/mtalib/Spyder)"
    )
}


# ==============================================================================
# MAIN SCRAPER CLASS
# ==============================================================================
class SentimentScraper:
    """
    Downloads and caches weekly AAII and NAAIM sentiment data.

    Thread-safe via internal locks.  Returns NaN-filled stubs gracefully
    when either data source is unreachable so Spyder never hard-crashes on
    a network timeout.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._aaii_cache: Optional[dict]  = None
        self._aaii_cache_time: Optional[datetime] = None
        self._naaim_cache: Optional[dict] = None
        self._naaim_cache_time: Optional[datetime] = None
        logger.info("SentimentScraper initialised (AAII + NAAIM, no API key required).")

    # --------------------------------------------------------------------------
    # Public API
    # --------------------------------------------------------------------------

    def get_snapshot(self, force_refresh: bool = False) -> dict:
        """
        Return a unified sentiment snapshot combining AAII and NAAIM data.

        Args:
            force_refresh: Bypass cache and re-download from source URLs now.

        Returns:
            dict with keys:
                aaii_bullish          — AAII bulls (%) as of latest survey
                aaii_bearish          — AAII bears (%)
                aaii_neutral          — AAII neutral (%)
                aaii_bull_bear_spread — Bulls minus Bears (pp)
                aaii_extreme_fear     — True if bearish > 40%
                aaii_extreme_greed    — True if bullish > 50%
                naaim_exposure        — NAAIM Exposure Index (average equity %)
                naaim_under_invested  — True if exposure < 40 (managers may chase)
                naaim_over_invested   — True if exposure > 90 (crowded long)
                aaii_as_of            — date of AAII survey
                naaim_as_of           — date of NAAIM survey
        """
        aaii  = self._get_aaii(force_refresh)
        naaim = self._get_naaim(force_refresh)
        return {**aaii, **naaim}

    def get_aaii(self, force_refresh: bool = False) -> dict:
        """Return AAII sentiment fields only."""
        return self._get_aaii(force_refresh)

    def get_naaim(self, force_refresh: bool = False) -> dict:
        """Return NAAIM exposure fields only."""
        return self._get_naaim(force_refresh)

    def get_status(self) -> dict:
        """Return cache and availability status for both sources."""
        with self._lock:
            aaii_age = (
                (datetime.now() - self._aaii_cache_time).total_seconds()
                if self._aaii_cache_time else None
            )
            naaim_age = (
                (datetime.now() - self._naaim_cache_time).total_seconds()
                if self._naaim_cache_time else None
            )
        return {
            "aaii_cached": self._aaii_cache is not None,
            "aaii_cache_age_seconds": aaii_age,
            "naaim_cached": self._naaim_cache is not None,
            "naaim_cache_age_seconds": naaim_age,
            "pandas_available": PANDAS_AVAILABLE,
        }

    # --------------------------------------------------------------------------
    # Internal — AAII
    # --------------------------------------------------------------------------

    def _get_aaii(self, force_refresh: bool) -> dict:
        with self._lock:
            if not force_refresh and self._aaii_cache is not None:
                age = (datetime.now() - self._aaii_cache_time).total_seconds()
                if age < _AAII_CACHE_TTL_SECONDS:
                    return dict(self._aaii_cache)

        data = self._fetch_aaii()

        with self._lock:
            self._aaii_cache = data
            self._aaii_cache_time = datetime.now()

        return dict(data)

    def _fetch_aaii(self) -> dict:
        """Download and parse the AAII sentiment Excel file."""
        if not PANDAS_AVAILABLE:
            logger.warning("pandas not available — AAII data returning stubs.")
            return self._aaii_stub()

        try:
            response = requests.get(
                _AAII_URL, headers=_HEADERS, timeout=_HTTP_TIMEOUT
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("AAII download failed: %s — using stub data.", exc)
            return self._aaii_stub()

        try:
            df = pd.read_excel(
                io.BytesIO(response.content),
                sheet_name=0,
                header=None,
            )

            # AAII workbook layout (as of 2026):
            # Row 0: headers row ("Reported Date", "Bullish", "Neutral",
            #         "Bearish", "Bull-Bear Spread", ...)
            # Rows 1+: weekly data, most recent at bottom.
            # Locate the header row by searching for 'Bullish'
            header_row = None
            for idx, row in df.iterrows():
                if any(
                    "bullish" in str(v).lower() for v in row.values if pd.notna(v)
                ):
                    header_row = idx
                    break

            if header_row is None:
                raise ValueError("Could not find 'Bullish' header row in AAII file.")

            df.columns = df.iloc[header_row].str.strip().str.lower().str.replace(
                r"[\s\-]+", "_", regex=True
            )
            df = df.iloc[header_row + 1:].reset_index(drop=True)
            df = df.dropna(subset=["bullish", "bearish"])

            # Coerce percentage columns — AAII stores them as fractions (0.32) or %
            for col in ("bullish", "bearish", "neutral"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                    # Normalise: if max is ≤ 1.0 they're fractions, convert to %
                    if df[col].max() <= 1.0:
                        df[col] = df[col] * 100.0

            # Most recent row
            latest = df.iloc[-1]
            bullish  = float(latest.get("bullish",  float("nan")))
            bearish  = float(latest.get("bearish",  float("nan")))
            neutral  = float(latest.get("neutral",  float("nan")))

            # Date column detection
            date_col = next(
                (c for c in df.columns if "date" in c or "reported" in c),
                None,
            )
            as_of: Optional[date] = None
            if date_col:
                try:
                    as_of = pd.to_datetime(latest[date_col]).date()
                except Exception:
                    pass

            spread = bullish - bearish if (bullish == bullish and bearish == bearish) else float("nan")

            return {
                "aaii_bullish":          bullish,
                "aaii_bearish":          bearish,
                "aaii_neutral":          neutral,
                "aaii_bull_bear_spread": spread,
                "aaii_extreme_fear":     bearish > _AAII_EXTREME_BEARISH_THRESHOLD,
                "aaii_extreme_greed":    bullish > _AAII_EXTREME_BULLISH_THRESHOLD,
                "aaii_as_of":            as_of,
            }

        except Exception as exc:
            logger.warning("AAII parse failed: %s — using stub data.", exc)
            return self._aaii_stub()

    def _aaii_stub(self) -> dict:
        return {
            "aaii_bullish":          float("nan"),
            "aaii_bearish":          float("nan"),
            "aaii_neutral":          float("nan"),
            "aaii_bull_bear_spread": float("nan"),
            "aaii_extreme_fear":     False,
            "aaii_extreme_greed":    False,
            "aaii_as_of":            None,
        }

    # --------------------------------------------------------------------------
    # Internal — NAAIM
    # --------------------------------------------------------------------------

    def _get_naaim(self, force_refresh: bool) -> dict:
        with self._lock:
            if not force_refresh and self._naaim_cache is not None:
                age = (datetime.now() - self._naaim_cache_time).total_seconds()
                if age < _NAAIM_CACHE_TTL_SECONDS:
                    return dict(self._naaim_cache)

        data = self._fetch_naaim()

        with self._lock:
            self._naaim_cache = data
            self._naaim_cache_time = datetime.now()

        return dict(data)

    def _fetch_naaim(self) -> dict:
        """Download and parse the NAAIM Exposure Index Excel file."""
        if not PANDAS_AVAILABLE:
            logger.warning("pandas not available — NAAIM data returning stubs.")
            return self._naaim_stub()

        try:
            response = requests.get(
                _NAAIM_URL, headers=_HEADERS, timeout=_HTTP_TIMEOUT
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("NAAIM download failed: %s — using stub data.", exc)
            return self._naaim_stub()

        try:
            df = pd.read_excel(
                io.BytesIO(response.content),
                sheet_name=0,
            )

            # NAAIM workbook layout (as of 2026):
            # Columns typically: Date, NAAIM Number (mean), Bearish, ..., Bullish
            # We want the "NAAIM Number" (the average exposure index).
            df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
            df = df.dropna(how="all")

            # Locate exposure column
            exposure_col = next(
                (
                    c for c in df.columns
                    if "naaim" in c or "exposure" in c or "number" in c
                ),
                None,
            )
            if exposure_col is None:
                # Fallback: last numeric column is often the index value
                numeric_cols = df.select_dtypes(include="number").columns.tolist()
                exposure_col = numeric_cols[-1] if numeric_cols else None

            if exposure_col is None:
                raise ValueError("Could not identify NAAIM exposure column.")

            df[exposure_col] = pd.to_numeric(df[exposure_col], errors="coerce")
            df = df.dropna(subset=[exposure_col])
            latest = df.iloc[-1]
            exposure = float(latest[exposure_col])

            # Date column
            date_col = next(
                (c for c in df.columns if "date" in c or "week" in c),
                None,
            )
            as_of: Optional[date] = None
            if date_col:
                try:
                    as_of = pd.to_datetime(latest[date_col]).date()
                except Exception:
                    pass

            return {
                "naaim_exposure":       exposure,
                "naaim_under_invested": exposure < _NAAIM_UNDER_INVESTED_THRESHOLD,
                "naaim_over_invested":  exposure > _NAAIM_OVER_INVESTED_THRESHOLD,
                "naaim_as_of":          as_of,
            }

        except Exception as exc:
            logger.warning("NAAIM parse failed: %s — using stub data.", exc)
            return self._naaim_stub()

    def _naaim_stub(self) -> dict:
        return {
            "naaim_exposure":       float("nan"),
            "naaim_under_invested": False,
            "naaim_over_invested":  False,
            "naaim_as_of":          None,
        }


# ==============================================================================
# MODULE-LEVEL SINGLETON
# ==============================================================================
_sentiment_scraper: Optional[SentimentScraper] = None


def get_sentiment_scraper() -> SentimentScraper:
    """Return the module-level SentimentScraper singleton."""
    global _sentiment_scraper
    if _sentiment_scraper is None:
        _sentiment_scraper = SentimentScraper()
    return _sentiment_scraper
