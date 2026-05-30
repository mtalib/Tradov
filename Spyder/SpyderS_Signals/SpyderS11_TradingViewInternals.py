#!/usr/bin/env python3
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
    USI:NYMO   — NYSE McClellan Oscillator

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
import os  # noqa: F401
import queue
import threading
import time
from datetime import datetime, UTC
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import shutil
try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page  # noqa: F401
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Detect a system Chromium when Playwright's bundled browser cannot be installed
# (e.g. Ubuntu 26.04 is not yet in Playwright's support matrix).
_SYSTEM_CHROMIUM_PATHS = (
    "/snap/bin/chromium",          # snap install chromium
    "/usr/bin/chromium-browser",   # apt install chromium-browser
    "/usr/bin/chromium",           # some distros
)
_SYSTEM_CHROMIUM: str | None = next(
    (p for p in _SYSTEM_CHROMIUM_PATHS if shutil.which(p) or __import__('os').path.isfile(p)),
    None,
)

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    logger = SpyderLogger.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================
_SYMBOLS: dict[str, str] = {
    "tick": "https://www.tradingview.com/symbols/USI-TICK/",
    "trin": "https://www.tradingview.com/symbols/USI-TRIN.NY/",
    "add":  "https://www.tradingview.com/symbols/USI-ADD/",
    "vold": "https://www.tradingview.com/symbols/USI-VOLD/",
    # TradingView's USI-VOLD has occasionally emitted unsigned-overflow
    # values; UVOL/DVOL lets us deterministically reconstruct VOLD.
    "uvol": "https://www.tradingview.com/symbols/USI-UVOL/",
    "dvol": "https://www.tradingview.com/symbols/USI-DVOL/",
    # NOTE: USI-NYMO does not have a TradingView symbol page (returns 404).
    # NYMO is computed as an ADD-EMA oscillator proxy in SpyderS07.
}

_CSS_PRICE_PRIMARY = '[data-qa-id="symbol-last-value"]'
_CSS_PRICE_FALLBACK = 'span[class*="last-"]'

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

# NYMO (NYSE McClellan Oscillator) thresholds.
# NYMO oscillates roughly –100 to +100; > 40 is overbought, <– 40 is oversold
# on an intraday basis.  Extremes (±80) signal strong mean-reversion setups.
_NYMO_STRONG_BULL =  60.0
_NYMO_BULL        =  20.0
_NYMO_BEAR        = -20.0
_NYMO_STRONG_BEAR = -60.0

# Page load / selector timeouts (ms)
# NYMO can take 15-20 s to render its price element after domcontentloaded;
# keep _SEL_TIMEOUT_MS generous to avoid aborting the entire launch.
_NAV_TIMEOUT_MS  = 20_000
_SEL_TIMEOUT_MS  = 25_000
_TEXT_TIMEOUT_MS  =  5_000
_FALLBACK_SEL_TIMEOUT_MS = 1_000
_UINT64_MAX = float(2 ** 64)


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
        self._cache: dict[str, Any] = {}
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
    def get_snapshot(self) -> dict[str, Any]:
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
                nymo          — float  (NYSE McClellan Oscillator)
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

    def get_status(self) -> dict[str, Any]:
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
        pages: dict[str, Any] = {}
        initialised = False

        def launch() -> None:
            nonlocal pw, browser, ctx, pages, initialised
            if not PLAYWRIGHT_AVAILABLE:
                raise RuntimeError(
                    "playwright is not installed. "
                    "Run: pip install playwright && python -m playwright install chromium"
                )
            pw = sync_playwright().start()
            # Try bundled Playwright Chromium first; fall back to system Chromium
            # when the bundled binary is unavailable (e.g. unsupported OS version).
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception as _bundled_exc:
                if _SYSTEM_CHROMIUM is None:
                    raise RuntimeError(
                        f"Playwright bundled Chromium unavailable ({_bundled_exc}) and no "
                        "system Chromium found. "
                        "Install one with: sudo snap install chromium"
                    ) from _bundled_exc
                logger.debug(
                    "Playwright bundled Chromium unavailable (%s); using system Chromium at %s",
                    _bundled_exc, _SYSTEM_CHROMIUM,
                )
                browser = pw.chromium.launch(headless=True, executable_path=_SYSTEM_CHROMIUM)
            ctx = browser.new_context(user_agent=_USER_AGENT)
            for name, url in _SYMBOLS.items():
                try:
                    pg = self._open_symbol_page(ctx, url)
                    pages[name] = pg
                    logger.debug("TradingView tab opened: %s → %s", name.upper(), url)
                except Exception as page_exc:
                    logger.warning(
                        "TradingView: failed to open tab for %s (%s) — symbol will show NaN.",
                        name.upper(), self._format_scrape_error(page_exc),
                    )
            if not pages:
                raise RuntimeError("TradingView: all symbol pages failed to open — browser unusable.")  # noqa: E501
            initialised = True
            logger.debug("TradingView headless browser launched with %d/%d tabs.", len(pages), len(_SYMBOLS))  # noqa: E501

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

        def refresh_all() -> dict[str, Any]:
            result: dict[str, Any] = {}
            for name, pg in pages.items():
                try:
                    pg.reload(wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
                    raw = self._read_price_text(pg)
                    result[name] = self._parse_price(raw)
                except Exception as exc:
                    logger.warning(
                        "Failed to scrape %s: %s",
                        name.upper(),
                        self._format_scrape_error(exc),
                    )
                    result[name] = float("nan")

            result["vold"] = self._normalise_vold(
                raw_vold=result.get("vold", float("nan")),
                uvol=result.get("uvol", float("nan")),
                dvol=result.get("dvol", float("nan")),
            )
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
                snapshot["as_of"] = datetime.now(UTC)

                self._cache = dict(snapshot)
                self._cache_ts = time.time()
                result_holder[0] = snapshot

            except Exception as exc:
                logger.warning(
                    "TradingView scrape failed: %s — returning stubs.",
                    self._format_scrape_error(exc),
                )
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
    def _refresh_all(self) -> dict[str, Any]:
        """Not used directly — scraping runs inside _browser_worker."""
        return {}

    @staticmethod
    def _open_symbol_page(context: Any, url: str) -> Any:
        """Open a TradingView symbol page without blocking on the first price render."""
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        return page

    @staticmethod
    def _read_price_text(page: Any) -> str:
        """Return the visible TradingView last-price text for a symbol page."""
        primary_locator = page.locator(_CSS_PRICE_PRIMARY).first
        try:
            primary_locator.wait_for(state="visible", timeout=_SEL_TIMEOUT_MS)
            return primary_locator.inner_text(timeout=_TEXT_TIMEOUT_MS)
        except Exception as primary_exc:
            fallback_locator = page.locator(_CSS_PRICE_FALLBACK).first
            try:
                fallback_locator.wait_for(state="visible", timeout=_FALLBACK_SEL_TIMEOUT_MS)
                return fallback_locator.inner_text(timeout=_TEXT_TIMEOUT_MS)
            except Exception:
                raise primary_exc

    @staticmethod
    def _format_scrape_error(exc: Exception) -> str:
        """Collapse verbose Playwright call logs to their first summary line."""
        return str(exc).splitlines()[0].strip()

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

    @staticmethod
    def _normalise_vold(raw_vold: Any, uvol: Any, dvol: Any) -> float:
        """Return a sane VOLD value from available TradingView internals.

        Priority:
          1) UVOL - DVOL when both are finite.
          2) Signed uint64 unwrap for overflowed USI-VOLD values.
          3) Raw USI-VOLD when it is already sane.
        """
        def _to_float(value: Any) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return float("nan")

        def _is_finite(value: float) -> bool:
            return not math.isnan(value) and math.isfinite(value)

        raw = _to_float(raw_vold)
        up = _to_float(uvol)
        down = _to_float(dvol)

        if _is_finite(up) and _is_finite(down):
            return up - down

        if _is_finite(raw) and raw > 9e18:
            unwrapped = raw - _UINT64_MAX
            if abs(unwrapped) < 5e9:
                return unwrapped

        if _is_finite(raw):
            return raw
        return float("nan")

    # ------------------------------------------------------------------
    # Breadth regime classification
    # ------------------------------------------------------------------
    @staticmethod
    def _classify_breadth(data: dict[str, Any]) -> str:
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

        # NYMO vote (NYSE McClellan Oscillator)
        nymo = data.get("nymo", float("nan"))
        if not math.isnan(nymo):
            if nymo >= _NYMO_STRONG_BULL:
                votes["strong_bull"] += 1
            elif nymo >= _NYMO_BULL:
                votes["bull"] += 1
            elif nymo <= _NYMO_STRONG_BEAR:
                votes["strong_bear"] += 1
            elif nymo <= _NYMO_BEAR:
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
        utc_now = datetime.now(UTC)
        et_offset = timedelta(hours=-4)   # EDT (summer); adjust if needed
        et_now = utc_now + et_offset
        if et_now.weekday() >= 5:         # Saturday / Sunday
            return False
        market_open  = et_now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = et_now.replace(hour=16, minute=0,  second=0, microsecond=0)
        return market_open <= et_now <= market_close

    @staticmethod
    def _stub() -> dict[str, Any]:
        """Return NaN stub snapshot."""
        return {
            "tick": float("nan"),
            "trin": float("nan"),
            "add":  float("nan"),
            "vold": float("nan"),
            "nymo": float("nan"),
            "breadth_regime": "neutral",
            "as_of": datetime.now(UTC),
        }


# ==============================================================================
# MODULE SINGLETON
# ==============================================================================
_tv_client: TradingViewInternals | None = None


def get_tv_internals_client() -> TradingViewInternals:
    """Return (or create) the module-level singleton."""
    global _tv_client
    if _tv_client is None:
        _tv_client = TradingViewInternals()
    return _tv_client
