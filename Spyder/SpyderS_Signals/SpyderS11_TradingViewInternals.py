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
import queue
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
        self._cache: Dict[str, Any] = {}
        self._cache_ts: float = 0.0

        # All Playwright calls must run on a single persistent thread.
        # _req_queue carries (result_holder: list, event: threading.Event) tuples.
        self._req_queue: queue.Queue = queue.Queue()
        self._worker_thread = threading.Thread(
            target=self._browser_worker,
            name="S11-playwright-worker",
            daemon=True,
        )
        self._worker_thread.start()
        logger.debug("TradingViewInternals created (browser not yet launched).")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_snapshot(self) -> Dict[str, Any]:
        """
        Return the latest breadth internals.

        The call is routed to the persistent browser-worker thread so that
        Playwright always runs on the same thread (sync_playwright is not
        thread-safe across threads).

        Returns:
            Dictionary with keys:
                tick          — float  (NYSE TICK)
                trin          — float  (NYSE TRIN / Arms Index)
                add           — float  (NYSE Advance − Decline)
                breadth_regime — str   (strong_bull|bull|neutral|bear|strong_bear)
                as_of         — datetime (UTC timestamp of the scrape)
        """
        # Serve off-hours cache without hitting the browser thread
        if self._cache and not self._is_market_hours():
            age = time.time() - self._cache_ts
            if age < _OFF_HOURS_CACHE_TTL:
                return dict(self._cache)

        result_holder: list = [None]
        done = threading.Event()
        self._req_queue.put((result_holder, done))
        done.wait(timeout=60)  # generous timeout; browser can be slow
        if result_holder[0] is not None:
            return result_holder[0]
        return self._stub()

    def get_status(self) -> Dict[str, Any]:
        """Return diagnostic status."""
        return {
            "initialised": self._worker_thread.is_alive(),
            "cached": bool(self._cache),
            "cache_age_s": round(time.time() - self._cache_ts, 1) if self._cache_ts else None,
            "pages": list(_SYMBOLS.keys()),
        }

    def close(self) -> None:
        """Signal the browser worker to shut down."""
        self._req_queue.put(None)  # sentinel

    # Context-manager support
    def __enter__(self) -> "TradingViewInternals":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Persistent browser worker — runs entirely on _worker_thread
    # ------------------------------------------------------------------
    def _browser_worker(self) -> None:
        """Event loop that owns the Playwright browser for its full lifetime."""
        pw: Any = None
        browser: Any = None
        ctx: Any = None
        pages: Dict[str, Any] = {}
        initialised = False

        def launch() -> None:
            nonlocal pw, browser, ctx, pages, initialised
            if not PLAYWRIGHT_AVAILABLE:
                raise RuntimeError(
                    "playwright is not installed. "
                    "Run: pip install playwright && python -m playwright install chromium"
                )
            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=_USER_AGENT)
            for name, url in _SYMBOLS.items():
                pg = ctx.new_page()
                pg.goto(url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
                pg.wait_for_selector(_CSS_PRICE, timeout=_SEL_TIMEOUT_MS)
                pages[name] = pg
                logger.debug("TradingView tab opened: %s → %s", name.upper(), url)
            initialised = True
            logger.debug("TradingView headless browser launched with %d tabs.", len(pages))

        def close_browser() -> None:
            nonlocal pw, browser, ctx, pages, initialised
            try:
                if ctx:
                    ctx.close()
                if browser:
                    browser.close()
                if pw:
                    pw.stop()
            except Exception as exc:
                logger.debug("Browser cleanup error (harmless): %s", exc)
            finally:
                pages.clear()
                ctx = browser = pw = None
                initialised = False

        def refresh_all() -> Dict[str, Any]:
            result: Dict[str, Any] = {}
            for name, pg in pages.items():
                try:
                    pg.reload(wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
                    pg.wait_for_selector(_CSS_PRICE, timeout=_SEL_TIMEOUT_MS)
                    raw = pg.locator(_CSS_PRICE).first.inner_text(timeout=_TEXT_TIMEOUT_MS)
                    result[name] = self._parse_price(raw)
                except Exception as exc:
                    logger.warning("Failed to scrape %s: %s", name.upper(), exc)
                    result[name] = float("nan")
            return result

        while True:
            item = self._req_queue.get()
            if item is None:
                # Shutdown sentinel
                close_browser()
                return

            result_holder, done = item
            try:
                if not initialised:
                    launch()

                snapshot = refresh_all()
                snapshot["breadth_regime"] = self._classify_breadth(snapshot)
                snapshot["as_of"] = datetime.now(timezone.utc)

                self._cache = dict(snapshot)
                self._cache_ts = time.time()
                result_holder[0] = snapshot

            except Exception as exc:
                logger.warning("TradingView scrape failed: %s — returning stubs.", exc)
                # On error, reset so next call re-launches the browser
                close_browser()
                result_holder[0] = None
            finally:
                done.set()

    # ------------------------------------------------------------------
    # Browser lifecycle (legacy — kept for _close_browser callers)
    # ------------------------------------------------------------------
    def _close_browser(self) -> None:
        """Deprecated: use close() to stop the worker thread."""
        self.close()

    # ------------------------------------------------------------------
    # Scraping helpers
    # ------------------------------------------------------------------
    def _refresh_all(self) -> Dict[str, Any]:
        """Not used directly — scraping runs inside _browser_worker."""
        return {}

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
