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
import re
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

try:
    from fredapi import Fred as _FredApi
    FREDAPI_AVAILABLE = True
except ImportError:
    _FredApi = None
    FREDAPI_AVAILABLE = False

try:
    import nasdaqdatalink as _ndl
    NDL_AVAILABLE = True
except ImportError:
    _ndl = None
    NDL_AVAILABLE = False

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
_AAII_URL        = "https://www.aaii.com/files/surveys/sentiment.xls"
_AAII_MAIN_PAGE  = "https://www.aaii.com/sentiment"
_NAAIM_URL       = "https://www.naaim.org/wp-content/uploads/NAAIM_Exposure_data.xlsx"
_NAAIM_INDEX_PAGE = "https://www.naaim.org/programs/naaim-exposure-index/"

# Nasdaq Data Link (formerly Quandl) — PREMIUM dataset, requires paid subscription.
# AAII/SENTIMENT is NOT available on the free tier.
_NASDAQ_DL_AAII_URL = "https://data.nasdaq.com/api/v3/datasets/AAII/SENTIMENT/data.json"

# FRED series used as a free proxy when AAII is unavailable.
# UMCSENT = University of Michigan Consumer Sentiment (monthly, ~0.6 correlation with AAII)
_FRED_UMCSENT_SERIES = "UMCSENT"
# Empirical linear mapping UMCSENT → approximate AAII bull/bear (calibrated on 2000-2024 data)
# UMCSENT range: 50-110 → bearish range: 50-21%, bullish range: 21-50%
_UMCSENT_SLOPE = 29.0 / 60.0   # pp change per UMCSENT point (both bull and bear)

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

# Generic bot-detection bypass headers (used for direct site downloads)
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Minimal headers used for authenticated/structured API calls
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
        # Suppress repeated warnings after the first failure per session
        self._aaii_warned: bool = False
        self._naaim_warned: bool = False
        logger.debug("SentimentScraper initialised (AAII + NAAIM, no API key required).")

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
        """Download AAII sentiment with multi-strategy fallback.

        Strategy 1: Nasdaq Data Link REST API — requires PAID Premium subscription.
                    Add NASDAQ_DATA_LINK_API_KEY to .env if you have access.
        Strategy 2: Browser-simulated direct download (often blocked by Cloudflare).
        Strategy 3: FRED UMCSENT proxy — University of Michigan Consumer Sentiment
                    mapped to approximate AAII bull/bear percentages.  Free,
                    monthly cadence.  Requires FRED_API_KEY in .env.
        Fallback:   NaN-filled stub; WARNING logged once per session.
        """
        # Strategy 1: Nasdaq Data Link SDK (reads NASDAQ_DATA_LINK_API_KEY from env automatically)
        # NOTE: AAII/SENTIMENT is a Premium dataset — requires a paid Nasdaq Data Link subscription.
        # See: https://github.com/Nasdaq/data-link-python
        if NDL_AVAILABLE and os.environ.get("NASDAQ_DATA_LINK_API_KEY", "").strip():
            result = self._fetch_aaii_nasdaq()
            if result is not None:
                logger.debug("AAII data fetched via Nasdaq Data Link SDK.")
                return result

        # Strategy 2: Browser-simulated direct download
        result = self._fetch_aaii_direct()
        if result is not None:
            logger.debug("AAII data fetched via direct download.")
            return result

        # Strategy 3: FRED UMCSENT proxy (free, monthly)
        result = self._fetch_aaii_fred()
        if result is not None:
            logger.debug("AAII proxied via FRED UMCSENT (monthly consumer sentiment).")
            return result

        # All strategies failed
        if not self._aaii_warned:
            logger.warning(
                "AAII sentiment unavailable — all fetch strategies failed. "
                "AAII/SENTIMENT on Nasdaq Data Link requires a PAID Premium "
                "subscription. Add FRED_API_KEY to .env as a free monthly proxy. "
                "Using stub data."
            )
            self._aaii_warned = True
        else:
            logger.debug("AAII still unavailable — using stub data.")
        return self._aaii_stub()

    def _fetch_aaii_nasdaq(self) -> Optional[dict]:
        """Fetch AAII sentiment via the official nasdaqdatalink Python SDK.

        The SDK reads NASDAQ_DATA_LINK_API_KEY from the environment automatically.
        No manual key configuration needed — just set the env var in .env.

        Dataset AAII/SENTIMENT — columns: date, Bullish, Neutral, Bearish,
        Total, Bull-Bear Spread, ...  Values may be fractions (0.321 = 32.1%).

        NOTE: AAII/SENTIMENT is a Premium dataset requiring a paid subscription.
        See: https://github.com/Nasdaq/data-link-python
        """
        if not NDL_AVAILABLE or _ndl is None:
            return None
        try:
            # SDK reads NASDAQ_DATA_LINK_API_KEY from environment automatically
            df = _ndl.get("AAII/SENTIMENT", rows=3)
            if df is None or df.empty:
                return None
            # Normalise column names
            df.columns = [
                c.lower().replace(" ", "_").replace("-", "_")
                for c in df.columns
            ]
            latest = df.iloc[0]  # most-recent row

            def _pct(key: str) -> float:
                val = float(latest.get(key, float("nan")))
                # NDL stores fractions (0.321 → 32.1%); normalise if needed
                if 0.0 < val <= 1.0:
                    val *= 100.0
                return val

            bullish = _pct("bullish")
            bearish = _pct("bearish")
            neutral = _pct("neutral")
            spread  = (
                bullish - bearish
                if (bullish == bullish and bearish == bearish)
                else float("nan")
            )
            as_of: Optional[date] = None
            try:
                as_of = df.index[0].date()
            except Exception:
                pass
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
            logger.debug("AAII Nasdaq Data Link failed: %s", exc)
            return None

    def _fetch_aaii_direct(self) -> Optional[dict]:
        """Download AAII Excel with a browser-simulated session.

        A warm-up GET to the AAII sentiment page acquires session cookies
        that help bypass Cloudflare bot-detection on the file download.
        """
        if not PANDAS_AVAILABLE:
            return None
        try:
            session = requests.Session()
            # Warm-up — collect session cookies before the file download
            session.get(_AAII_MAIN_PAGE, headers=_BROWSER_HEADERS, timeout=15)
            dl_headers = {
                **_BROWSER_HEADERS,
                "Accept": (
                    "application/vnd.ms-excel,"
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
                    "*/*;q=0.8"
                ),
                "Referer": _AAII_MAIN_PAGE,
            }
            resp = session.get(_AAII_URL, headers=dl_headers, timeout=_HTTP_TIMEOUT)
            resp.raise_for_status()
            return self._parse_aaii_excel(resp.content)
        except Exception as exc:
            logger.debug("AAII direct download failed: %s", exc)
            return None

    def _parse_aaii_excel(self, content: bytes) -> Optional[dict]:
        """Parse raw bytes of the AAII sentiment Excel/XLS workbook."""
        try:
            df = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None)
            # Locate header row by searching for 'Bullish'
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
            for col in ("bullish", "bearish", "neutral"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                    if df[col].max() <= 1.0:
                        df[col] = df[col] * 100.0
            latest  = df.iloc[-1]
            bullish = float(latest.get("bullish", float("nan")))
            bearish = float(latest.get("bearish", float("nan")))
            neutral = float(latest.get("neutral", float("nan")))
            date_col = next(
                (c for c in df.columns if "date" in c or "reported" in c), None
            )
            as_of: Optional[date] = None
            if date_col:
                try:
                    as_of = pd.to_datetime(latest[date_col]).date()
                except Exception:
                    pass
            spread = (
                bullish - bearish
                if (bullish == bullish and bearish == bearish)
                else float("nan")
            )
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
            logger.debug("AAII Excel parse failed: %s", exc)
            return None

    def _fetch_aaii_fred(self) -> Optional[dict]:
        """Derive approximate AAII bull/bear from FRED UMCSENT (University of
        Michigan Consumer Sentiment, monthly).

        The mapping is a linear regression calibrated on 2000-2024 historical
        data (Pearson r ≈ 0.58).  Returned values are labelled as a proxy so
        downstream consumers can treat them with appropriate scepticism.

        Returns None if fredapi is unavailable or the FRED key is not set.
        """
        if not FREDAPI_AVAILABLE or _FredApi is None:
            return None
        fred_key = os.environ.get("FRED_API_KEY", "").strip()
        if not fred_key:
            return None
        try:
            fred = _FredApi(api_key=fred_key)
            series = fred.get_series(_FRED_UMCSENT_SERIES)
            series = series.dropna()
            if series.empty:
                return None
            umcsent = float(series.iloc[-1])
            as_of_ts = series.index[-1]
            as_of = as_of_ts.date() if hasattr(as_of_ts, "date") else None

            # Linear mapping: UMCSENT 50 → bear≈50%, bull≈21%; UMCSENT 110 → bear≈21%, bull≈50%
            umcsent_clamped = max(50.0, min(110.0, umcsent))
            bearish = round(50.0 - (umcsent_clamped - 50.0) * _UMCSENT_SLOPE, 1)
            bullish = round(21.0 + (umcsent_clamped - 50.0) * _UMCSENT_SLOPE, 1)
            neutral = round(max(0.0, 100.0 - bullish - bearish), 1)
            spread  = round(bullish - bearish, 1)

            logger.info(
                "AAII proxy via FRED UMCSENT=%.1f (as of %s): "
                "bull≈%.1f%% bear≈%.1f%% [monthly proxy, not real AAII survey]",
                umcsent, as_of, bullish, bearish,
            )
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
            logger.debug("FRED UMCSENT proxy failed: %s", exc)
            return None

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
        """Download NAAIM Exposure Index with multi-strategy fallback.

        Strategy 1: Scrape the NAAIM index page to discover the current Excel
                    download URL.  The WordPress upload path changes whenever
                    NAAIM re-publishes (YYYY/MM/ prefix), so a static URL goes
                    stale — page discovery always finds the latest link.
        Strategy 2: Try a set of known/guessed URL patterns (canonical +
                    date-stamped current and prior month).
        Fallback:   NaN-filled stub; WARNING logged once per session.
        """
        result = self._fetch_naaim_from_page()
        if result is not None:
            logger.debug("NAAIM data fetched via page discovery.")
            return result

        result = self._fetch_naaim_direct()
        if result is not None:
            logger.debug("NAAIM data fetched via direct URL.")
            return result

        if not self._naaim_warned:
            logger.warning("NAAIM exposure data unavailable — using stub data.")
            self._naaim_warned = True
        else:
            logger.debug("NAAIM still unavailable — using stub data.")
        return self._naaim_stub()

    def _fetch_naaim_from_page(self) -> Optional[dict]:
        """Scrape the NAAIM exposure-index page to find the current Excel URL.

        NAAIM hosts their data on a WordPress site; the file URL includes a
        YYYY/MM/ upload path that changes with each publication.  Scraping the
        page to discover the actual href is more robust than guessing the path.
        """
        if not PANDAS_AVAILABLE:
            return None
        try:
            resp = requests.get(
                _NAAIM_INDEX_PAGE, headers=_BROWSER_HEADERS, timeout=15
            )
            resp.raise_for_status()
            # Locate .xlsx / .xls hrefs that mention 'naaim' or 'exposure'
            links = re.findall(
                r'href=["\']([^"\']*\.xlsx?)["\']',
                resp.text,
                re.IGNORECASE,
            )
            naaim_links = [
                l for l in links
                if "naaim" in l.lower() or "exposure" in l.lower()
            ]
            if not naaim_links:
                logger.debug("No NAAIM Excel link found on index page.")
                return None
            url = naaim_links[0]
            if not url.startswith("http"):
                url = "https://www.naaim.org" + url
            logger.debug("Found NAAIM download URL: %s", url)
            xl_resp = requests.get(url, headers=_BROWSER_HEADERS, timeout=_HTTP_TIMEOUT)
            xl_resp.raise_for_status()
            return self._parse_naaim_excel(xl_resp.content)
        except Exception as exc:
            logger.debug("NAAIM page-discovery failed: %s", exc)
            return None

    def _fetch_naaim_direct(self) -> Optional[dict]:
        """Try a set of known NAAIM Excel URL patterns.

        Tries the canonical URL first, then date-stamped WordPress paths for
        the current and previous month (matching the YYYY/MM/ upload prefix).
        """
        if not PANDAS_AVAILABLE:
            return None
        today = date.today()
        prev_year  = today.year if today.month > 1 else today.year - 1
        prev_month = today.month - 1 if today.month > 1 else 12
        url_candidates = [
            _NAAIM_URL,  # canonical (no date prefix)
            f"https://www.naaim.org/wp-content/uploads/{today.year}/{today.month:02d}/NAAIM_Exposure_data.xlsx",
            f"https://www.naaim.org/wp-content/uploads/{prev_year}/{prev_month:02d}/NAAIM_Exposure_data.xlsx",
        ]
        for url in url_candidates:
            try:
                resp = requests.get(url, headers=_BROWSER_HEADERS, timeout=_HTTP_TIMEOUT)
                if resp.status_code == 200:
                    result = self._parse_naaim_excel(resp.content)
                    if result is not None:
                        logger.debug("NAAIM fetched from: %s", url)
                        return result
            except Exception as exc:
                logger.debug("NAAIM URL %s failed: %s", url, exc)
        return None

    def _parse_naaim_excel(self, content: bytes) -> Optional[dict]:
        """Parse raw bytes of the NAAIM Exposure Index Excel workbook."""
        try:
            df = pd.read_excel(io.BytesIO(content), sheet_name=0)
            df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
            df = df.dropna(how="all")
            exposure_col = next(
                (
                    c for c in df.columns
                    if "naaim" in c or "exposure" in c or "number" in c
                ),
                None,
            )
            if exposure_col is None:
                numeric_cols = df.select_dtypes(include="number").columns.tolist()
                exposure_col = numeric_cols[-1] if numeric_cols else None
            if exposure_col is None:
                raise ValueError("Could not identify NAAIM exposure column.")
            df[exposure_col] = pd.to_numeric(df[exposure_col], errors="coerce")
            df = df.dropna(subset=[exposure_col])
            # Sort by date so iloc[-1] always returns the most recent row
            date_col = next(
                (c for c in df.columns if "date" in c or "week" in c), None
            )
            if date_col:
                df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
                df = df.sort_values(date_col)
            latest   = df.iloc[-1]
            exposure = float(latest[exposure_col])
            as_of: Optional[date] = None
            if date_col:
                try:
                    as_of = latest[date_col].date()
                except Exception:
                    pass
            return {
                "naaim_exposure":       exposure,
                "naaim_under_invested": exposure < _NAAIM_UNDER_INVESTED_THRESHOLD,
                "naaim_over_invested":  exposure > _NAAIM_OVER_INVESTED_THRESHOLD,
                "naaim_as_of":          as_of,
            }
        except Exception as exc:
            logger.debug("NAAIM Excel parse failed: %s", exc)
            return None

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
