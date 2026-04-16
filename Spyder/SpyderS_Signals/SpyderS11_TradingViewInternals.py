#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderS_Signals
Module: SpyderS11_TradingViewInternals.py
Purpose: Market breadth internals ($TICK, $ADD, $TRIN) via TradingView web scraping

Author: Spyder Development Team
Year Created: 2026
Last Updated: 2026-04-15 Time: 22:00:00

Design
------
Uses Playwright (headless Chromium) to scrape live values from TradingView
public symbol pages.  Three persistent browser tabs are kept open and
refreshed on demand — a single ``get_snapshot()`` call takes ~1-2 s
(refresh), well inside the 15-second polling budget.

Symbols
-------
    USI:TICK   — NYSE Cumulative Tick Index
    USI:TRIN.NY — NYSE Arms Index (TRIN)
    USI:ADD    — NYSE Advance-Decline

Requirements
------------
    pip install playwright
    python -m playwright install chromium

Usage
-----
    from SpyderS_Signals.SpyderS11_TradingViewInternals import get_tv_internals_client

    client = get_tv_internals_client()
    data   = client.get_snapshot()
    print(data)  # {'tick': 73.0, 'trin': 0.76, 'add': 230.0, 'as_of': datetime(...)}
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import math
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

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
_SYMBOLS: Dict[str, str] = {
    "tick": "https://www.tradingview.com/symbols/USI-TICK/",
    "trin": "https://www.tradingview.com/symbols/USI-TRIN.NY/",
    "add":  "https://www.tradingview.com/symbols/USI-ADD/",
}

_CSS_PRICE = 'span[class*="last-"]'

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Cache TTL — during market hours refresh every call;
# outside market hours serve cached data for up to 60 min.
_OFF_HOURS_CACHE_TTL = 3600  # seconds

# Breadth regime classification thresholds
_TICK_STRONG_BULL =  500
_TICK_BULL        =  200
_TICK_BEAR        = -200
_TICK_STRONG_BEAR = -500

_TRIN_STRONG_BULL = 0.50
_TRIN_BULL        = 0.80
_TRIN_BEAR        = 1.20
_TRIN_STRONG_BEAR = 2.00

_ADD_STRONG_BULL =  1500
_ADD_BULL        =  500
_ADD_BEAR        = -500
_ADD_STRONG_BEAR = -1500

# Page load / selector timeouts (ms)
_NAV_TIMEOUT_MS  = 15_000
_SEL_TIMEOUT_MS  = 10_000
_TEXT_TIMEOUT_MS  =  3_000


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class TradingViewInternals:
    """
    Headless-browser scraper for NYSE market breadth internals from
    TradingView public symbol pages.

    The browser and three tabs are created lazily on first
    ``get_snapshot()`` and kept alive for fast refresh on subsequent
    calls.  Call ``close()`` (or use as a context manager) to release
    browser resources.

    Thread-safety: a ``threading.Lock`` serialises all browser
    interaction so the instance can be shared across threads.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pw: Any = None          # Playwright context-manager object
        self._browser: Optional[Browser] = None
        self._ctx: Optional[BrowserContext] = None
        self._pages: Dict[str, Page] = {}
        self._cache: Dict[str, Any] = {}
        self._cache_ts: float = 0.0
        self._initialised: bool = False
        logger.info("TradingViewInternals created (browser not yet launched).")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_snapshot(self) -> Dict[str, Any]:
        """
        Return the latest breadth internals.

        Returns:
            Dictionary with keys:
                tick          — float  (NYSE TICK)
                trin          — float  (NYSE TRIN / Arms Index)
                add           — float  (NYSE Advance − Decline)
                breadth_regime — str   (strong_bull|bull|neutral|bear|strong_bear)
                as_of         — datetime (UTC timestamp of the scrape)
        """
        with self._lock:
            # Serve cache outside market hours if fresh enough
            if self._cache and not self._is_market_hours():
                age = time.time() - self._cache_ts
                if age < _OFF_HOURS_CACHE_TTL:
                    return dict(self._cache)

            try:
                if not self._initialised:
                    self._launch_browser()

                result = self._refresh_all()
                result["breadth_regime"] = self._classify_breadth(result)
                result["as_of"] = datetime.now(timezone.utc)

                self._cache = dict(result)
                self._cache_ts = time.time()
                return result

            except Exception as exc:
                logger.warning(
                    "TradingView scrape failed: %s — returning stubs.", exc
                )
                return self._stub()

    def get_status(self) -> Dict[str, Any]:
        """Return diagnostic status."""
        return {
            "initialised": self._initialised,
            "cached": bool(self._cache),
            "cache_age_s": round(time.time() - self._cache_ts, 1) if self._cache_ts else None,
            "pages": list(self._pages.keys()),
        }

    def close(self) -> None:
        """Shut down the headless browser."""
        with self._lock:
            self._close_browser()

    # Context-manager support
    def __enter__(self) -> "TradingViewInternals":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------
    def _launch_browser(self) -> None:
        """Start Playwright + Chromium and open persistent tabs."""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "playwright is not installed.  "
                "Run: pip install playwright && python -m playwright install chromium"
            )

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self._ctx = self._browser.new_context(user_agent=_USER_AGENT)

        for name, url in _SYMBOLS.items():
            pg = self._ctx.new_page()
            pg.goto(url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
            pg.wait_for_selector(_CSS_PRICE, timeout=_SEL_TIMEOUT_MS)
            self._pages[name] = pg
            logger.info("TradingView tab opened: %s → %s", name.upper(), url)

        self._initialised = True
        logger.info("TradingView headless browser launched with %d tabs.", len(self._pages))

    def _close_browser(self) -> None:
        """Release all Playwright resources."""
        try:
            if self._ctx:
                self._ctx.close()
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception as exc:
            logger.debug("Browser cleanup error (harmless): %s", exc)
        finally:
            self._pages.clear()
            self._ctx = None
            self._browser = None
            self._pw = None
            self._initialised = False

    # ------------------------------------------------------------------
    # Scraping helpers
    # ------------------------------------------------------------------
    def _refresh_all(self) -> Dict[str, Any]:
        """Reload every tab and extract the current price."""
        result: Dict[str, Any] = {}
        for name, pg in self._pages.items():
            try:
                pg.reload(wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
                pg.wait_for_selector(_CSS_PRICE, timeout=_SEL_TIMEOUT_MS)
                raw = pg.locator(_CSS_PRICE).first.inner_text(timeout=_TEXT_TIMEOUT_MS)
                result[name] = self._parse_price(raw)
            except Exception as exc:
                logger.warning("Failed to scrape %s: %s", name.upper(), exc)
                result[name] = float("nan")
        return result

    @staticmethod
    def _parse_price(text: str) -> float:
        """Parse TradingView price text (e.g. '73.000', '−0.480') to float."""
        cleaned = (
            text.replace(",", "")
                .replace("\u2212", "-")   # minus sign
                .replace("\u2013", "-")   # en-dash
                .replace("\xa0", "")      # non-breaking space
                .strip()
        )
        return float(cleaned)

    # ------------------------------------------------------------------
    # Breadth regime classification
    # ------------------------------------------------------------------
    @staticmethod
    def _classify_breadth(data: Dict[str, Any]) -> str:
        """
        Majority-vote classification from TICK + TRIN + ADD.

        Returns one of: strong_bull, bull, neutral, bear, strong_bear
        """
        tick = data.get("tick", float("nan"))
        trin = data.get("trin", float("nan"))
        add  = data.get("add",  float("nan"))

        votes = {"strong_bull": 0, "bull": 0, "neutral": 0, "bear": 0, "strong_bear": 0}

        # TICK vote
        if not math.isnan(tick):
            if tick >= _TICK_STRONG_BULL:
                votes["strong_bull"] += 1
            elif tick >= _TICK_BULL:
                votes["bull"] += 1
            elif tick <= _TICK_STRONG_BEAR:
                votes["strong_bear"] += 1
            elif tick <= _TICK_BEAR:
                votes["bear"] += 1
            else:
                votes["neutral"] += 1

        # TRIN vote (inverted — low TRIN = bullish)
        if not math.isnan(trin):
            if trin <= _TRIN_STRONG_BULL:
                votes["strong_bull"] += 1
            elif trin <= _TRIN_BULL:
                votes["bull"] += 1
            elif trin >= _TRIN_STRONG_BEAR:
                votes["strong_bear"] += 1
            elif trin >= _TRIN_BEAR:
                votes["bear"] += 1
            else:
                votes["neutral"] += 1

        # ADD vote
        if not math.isnan(add):
            if add >= _ADD_STRONG_BULL:
                votes["strong_bull"] += 1
            elif add >= _ADD_BULL:
                votes["bull"] += 1
            elif add <= _ADD_STRONG_BEAR:
                votes["strong_bear"] += 1
            elif add <= _ADD_BEAR:
                votes["bear"] += 1
            else:
                votes["neutral"] += 1

        return max(votes, key=votes.get)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_market_hours() -> bool:
        """True if current ET time is within NYSE regular session."""
        from datetime import timedelta
        utc_now = datetime.now(timezone.utc)
        et_offset = timedelta(hours=-4)   # EDT (summer); adjust if needed
        et_now = utc_now + et_offset
        if et_now.weekday() >= 5:         # Saturday / Sunday
            return False
        market_open  = et_now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = et_now.replace(hour=16, minute=0,  second=0, microsecond=0)
        return market_open <= et_now <= market_close

    @staticmethod
    def _stub() -> Dict[str, Any]:
        """Return NaN stub snapshot."""
        return {
            "tick": float("nan"),
            "trin": float("nan"),
            "add":  float("nan"),
            "breadth_regime": "neutral",
            "as_of": datetime.now(timezone.utc),
        }


# ==============================================================================
# MODULE SINGLETON
# ==============================================================================
_tv_client: Optional[TradingViewInternals] = None


def get_tv_internals_client() -> TradingViewInternals:
    """Return (or create) the module-level singleton."""
    global _tv_client
    if _tv_client is None:
        _tv_client = TradingViewInternals()
    return _tv_client
