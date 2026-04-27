#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderS_Signals
Module: SpyderS12_WRSSignal.py
Purpose: Walmart Recession Signal (WRS) — macro regime overlay signal

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-20 Time: 00:00:00

Description:
    Implements the Walmart Recession Signal (WRS), a macro-economic ratio
    comparing Walmart (WMT) stock price against an equal-weight luxury basket
    index of US-listed ADRs and equities.

    A rising WRS signals consumer spending shift toward discount retail,
    historically preceding economic downturns by months.

    Formula:
        WRS = Price(WMT) / LUXURY_INDEX

    The luxury basket index is built via daily-return compounding (the same
    methodology used by major indices when adding new constituents).  Each
    day the equal-weight mean of all actively-trading constituent returns is
    taken, then compounded from a base of 100.  This eliminates the
    inception-bias flaw that would arise from rebasing prices and averaging
    absolute levels — e.g. RACE's 2015 IPO joining the basket has zero
    step-change effect on the index level.

    Basket constituents: LVMUY, CFRUY, HESAY, PPRUY, BURBY, SWGAY, RACE, TPR, CPRI
    Data source: Tradier /markets/history (primary); yfinance (fallback)

Signal Levels (by expanding percentile rank):
    NORMAL   :  0 – 60th pct   — full strategy palette
    CAUTION  : 60 – 75th pct   — reduce short-put exposure
    WARNING  : 75 – 90th pct   — defensive posture only
    CRITICAL : 90 – 100th pct  — minimum size, no naked short-puts

Data Sources:
    Primary  : Tradier REST API (TRADIER_API_KEY env var)
    Fallback : yfinance (for development / when Tradier unavailable)

Caching:
    Daily OHLCV data cached to ~/.spyder/wrs_cache/ with 4-hour TTL.
    Avoids repeated API calls on every run.

Update Cadence:
    Daily close — WRS moves on weekly/monthly timescales. No intraday
    refresh needed. Integrated with SpyderS07_CustomMetricsOrchestrator.

Integration:
    - SpyderD30_RegimeGatedSelector: uses signal_level to gate strategies
    - SpyderF10_MarketRegimeDetector: adds macro context to regime composite
    - SpyderS07_CustomMetricsOrchestrator: exposes wrs to MetricSnapshot
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import os
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
import requests

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    _logger = SpyderLogger.get_logger(__name__)
except Exception:
    _logger = logging.getLogger(__name__)

try:
    from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    _error_handler = SpyderErrorHandler()
except Exception:
    _error_handler = None  # type: ignore[assignment]

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Tradier API
TRADIER_LIVE_URL = "https://api.tradier.com/v1"
TRADIER_SANDBOX_URL = "https://sandbox.tradier.com/v1"
REQUEST_TIMEOUT = 15       # seconds per request
MAX_RETRIES = 3

# Primary asset
WMT_TICKER = "WMT"

# Luxury basket — US-listed only (NYSE, NASDAQ, OTC) available via Tradier
# Rebased to 100 at each ticker's first available date; equal-weight mean.
LUXURY_BASKET: list[str] = [
    "LVMUY",  # LVMH Moët Hennessy Louis Vuitton (OTC, ~1999)
    "CFRUY",  # Compagnie Financière Richemont (OTC, ~2010)
    "HESAY",  # Hermès International (OTC, ~2012)
    "PPRUY",  # Kering (OTC, ~2013)
    "BURBY",  # Burberry Group (OTC, ~2009)
    "SWGAY",  # Swatch Group (OTC, ~2002)
    "RACE",   # Ferrari N.V. (NYSE, Oct 2015 IPO)
    "TPR",    # Tapestry / ex-Coach (NYSE, 2000)
    "CPRI",   # Capri Holdings / Michael Kors (NYSE, Dec 2013 IPO)
]

# Data history
HISTORY_START = "2000-01-01"
MIN_BASKET_TICKERS = 3       # below this, refuse to compute
WARN_BASKET_TICKERS = 5      # warn if below this

# Cache
_CACHE_DIR = Path("~/.spyder/wrs_cache").expanduser()
CACHE_TTL_HOURS = 4

# Signal level thresholds (expanding percentile rank 0–100)
SIGNAL_LEVELS: dict[str, tuple[float, float]] = {
    "NORMAL":   (0.0,  60.0),
    "CAUTION":  (60.0, 75.0),
    "WARNING":  (75.0, 90.0),
    "CRITICAL": (90.0, 100.1),  # 100.1 so 100th pct hits CRITICAL
}

# NBER recession bands used by chart module
RECESSION_BANDS: list[tuple[str, str, str]] = [
    ("2001-03-01", "2001-11-30", "Dot-com"),
    ("2007-12-01", "2009-06-30", "GFC"),
    ("2020-02-01", "2020-04-30", "COVID"),
]

# Strategy gate table exposed for regime gating layer
STRATEGY_GATES: dict[str, str] = {
    "NORMAL":   "Full palette, standard sizing",
    "CAUTION":  "Reduce short-put exposure; prefer Iron Condors",
    "WARNING":  "Defensive only — bear call spreads, reduced delta",
    "CRITICAL": "Minimum size; no naked short-puts; VIX hedges active",
}


# ==============================================================================
# ENUMS
# ==============================================================================

class WRSLevel(str, Enum):
    """WRS signal severity levels."""
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class WRSResult:
    """
    Full WRS computation result for a given date.

    Attributes:
        date: ISO date of the most recent reading.
        wrs: Raw ratio (WMT price / luxury basket index).
        wrs_30d_ma: 30-day simple moving average of WRS.
        wrs_90d_ma: 90-day simple moving average of WRS.
        wrs_pct_rank: Expanding percentile rank (0–100) over full history.
        wrs_zscore: Rolling 252-day z-score.
        yoy_change: Year-over-year change in raw WRS (current minus 252d ago).
        signal_level: NORMAL / CAUTION / WARNING / CRITICAL.
        basket_available: Number of luxury tickers successfully fetched.
        basket_missing: Tickers that could not be retrieved.
        data_start: First date in the aligned series.
        data_end: Last date in the aligned series.
        last_crossover_date: Most recent 30d/90d MA crossover date, or None.
        last_crossover_dir: 'up' (worsening) or 'down' (improving), or None.
        strategy_guidance: Human-readable strategy implication.
        timestamp: Wall-clock time of computation.
        error: Non-empty string if computation partially failed.
    """
    date: str = ""
    wrs: float = float("nan")
    wrs_30d_ma: float = float("nan")
    wrs_90d_ma: float = float("nan")
    wrs_pct_rank: float = float("nan")
    wrs_zscore: float = float("nan")
    yoy_change: float = float("nan")
    signal_level: WRSLevel = WRSLevel.NORMAL
    basket_available: int = 0
    basket_missing: list[str] = field(default_factory=list)
    data_start: str = ""
    data_end: str = ""
    last_crossover_date: Optional[str] = None
    last_crossover_dir: Optional[str] = None
    strategy_guidance: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    error: str = ""


# ==============================================================================
# EXCEPTIONS
# ==============================================================================

class WRSDataError(RuntimeError):
    """Raised when WRS computation cannot proceed due to missing data."""


# ==============================================================================
# TRADIER MARKET DATA CLIENT
# ==============================================================================

class _TradierMarketClient:
    """
    Thin HTTP wrapper for Tradier market data endpoints.

    Uses only the /markets/history endpoint — the broker-layer
    SpyderB40_TradierClient covers order management endpoints only.
    """

    def __init__(self, token: str, sandbox: bool = False) -> None:
        base = TRADIER_SANDBOX_URL if sandbox else TRADIER_LIVE_URL
        self._base_url = base
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })
        _logger.debug("WRS TradierMarketClient initialised (sandbox=%s)", sandbox)

    def get_ohlcv_history(
        self,
        symbol: str,
        start: str,
        end: Optional[str] = None,
        interval: str = "daily",
    ) -> list[dict[str, Any]]:
        """
        Fetch full OHLCV history for *symbol* from Tradier.

        Tradier returns the full lifetime in a single call — no pagination.
        The `close` field is already split/dividend-adjusted.

        Args:
            symbol: Ticker, e.g. "WMT" or "LVMUY".
            start: Start date "YYYY-MM-DD" (inclusive).
            end: End date "YYYY-MM-DD" (defaults to today).
            interval: "daily" | "weekly" | "monthly".

        Returns:
            List of dicts with keys: date, open, high, low, close, volume.

        Raises:
            WRSDataError: Symbol returns null/empty history or HTTP error.
        """
        end = end or date.today().isoformat()
        data = self._request(
            "GET",
            "/markets/history",
            params={
                "symbol": symbol,
                "interval": interval,
                "start": start,
                "end": end,
                "session_filter": "all",
            },
        )
        history = data.get("history")
        if not history:
            raise WRSDataError(
                f"Tradier returned null history for {symbol} "
                f"({start} → {end})"
            )
        days = history["day"]
        # Normalise single-day response (dict) to list
        return [days] if isinstance(days, dict) else days

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """HTTP request with retry/back-off."""
        url = f"{self._base_url}{endpoint}"
        last_exc: Exception = RuntimeError("Max retries exceeded")

        for attempt in range(MAX_RETRIES):
            try:
                resp = self._session.request(
                    method, url, params=params, timeout=REQUEST_TIMEOUT
                )
                if resp.status_code == 401:
                    raise WRSDataError(
                        "Tradier 401 — check TRADIER_API_KEY in .env"
                    )
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", "5"))
                    _logger.warning("Tradier 429 — waiting %ds", wait)
                    time.sleep(wait)
                    continue
                if resp.status_code >= 500:
                    last_exc = WRSDataError(
                        f"Tradier {resp.status_code}: {resp.text[:200]}"
                    )
                    time.sleep(2 ** (attempt + 1))
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.Timeout:
                last_exc = TimeoutError(f"Timeout: {url}")
                time.sleep(2 ** (attempt + 1))
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(2 ** (attempt + 1))

        raise WRSDataError(f"Tradier request failed after {MAX_RETRIES} attempts: {last_exc}")


# ==============================================================================
# CACHE HELPERS
# ==============================================================================

def _cache_path(key: str) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f"{key}.csv"


def _load_cache(key: str) -> Optional[pd.Series]:
    """Return cached Series if fresh (within CACHE_TTL_HOURS); else None."""
    path = _cache_path(key)
    if not path.exists():
        return None
    age = datetime.now(timezone.utc) - datetime.fromtimestamp(path.stat().st_mtime)
    if age > timedelta(hours=CACHE_TTL_HOURS):
        return None
    try:
        s = pd.read_csv(path, index_col=0, parse_dates=True).squeeze("columns")
        s.name = key.split("_")[0]
        _logger.debug("WRS cache hit: %s", key)
        return s
    except Exception as exc:
        _logger.warning("WRS cache read failed (%s): %s", key, exc)
        return None


def _save_cache(key: str, series: pd.Series) -> None:
    """Save series to CSV cache."""
    try:
        series.to_csv(_cache_path(key), header=True)
        _logger.debug("WRS cache saved: %s (%d bars)", key, len(series))
    except Exception as exc:
        _logger.warning("WRS cache write failed (%s): %s", key, exc)


# ==============================================================================
# DATA FETCHERS
# ==============================================================================

def _bars_to_series(bars: list[dict[str, Any]], name: str) -> pd.Series:
    """Convert Tradier history bar list to pd.Series of adjusted close prices."""
    idx = pd.DatetimeIndex([b["date"] for b in bars])
    values = [float(b["close"]) for b in bars]
    return pd.Series(values, index=idx, name=name).sort_index()


def _fetch_series_tradier(
    client: _TradierMarketClient,
    symbol: str,
    start: str,
    end: Optional[str],
    use_cache: bool,
) -> pd.Series:
    """Fetch close-price series via Tradier, with disk cache."""
    cache_key = f"{symbol}_{start}"
    if use_cache:
        cached = _load_cache(cache_key)
        if cached is not None:
            return cached
    bars = client.get_ohlcv_history(symbol, start=start, end=end)
    series = _bars_to_series(bars, name=symbol)
    _save_cache(cache_key, series)
    return series


def _fetch_series_yfinance(
    symbol: str,
    start: str,
    end: Optional[str],
    use_cache: bool,
) -> pd.Series:
    """yfinance fallback for when Tradier is unavailable."""
    cache_key = f"{symbol}_{start}_yf"
    if use_cache:
        cached = _load_cache(cache_key)
        if cached is not None:
            return cached
    try:
        import yfinance as yf  # noqa: PLC0415  (deferred import)
        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=start, end=end or date.today().isoformat())
        if hist.empty:
            raise WRSDataError(f"yfinance returned empty history for {symbol}")
        series = hist["Close"].rename(symbol)
        series.index = pd.DatetimeIndex(series.index.date)
        _save_cache(cache_key, series)
        return series
    except ImportError:
        raise WRSDataError("yfinance not installed — Tradier is required")  # noqa: B904


# ==============================================================================
# BASKET BUILDER
# ==============================================================================

def _build_luxury_basket(
    client: Optional[_TradierMarketClient],
    start: str,
    end: Optional[str],
    use_cache: bool,
) -> tuple[pd.Series, dict[str, Any]]:
    """
    Build the equal-weight luxury basket via daily-return compounding.

    Methodology (matches major index rebalance conventions):
      1. Fetch raw close prices for each constituent — no per-ticker rebasing.
      2. Compute daily percentage returns for every ticker.
      3. Average the returns cross-sectionally each day (skipna=True so a
         ticker contributes only from its own first traded day onward).
      4. Set the very first row to 0.0 (no prior close) then take the
         cumulative product and scale to 100.

    This eliminates the inception-bias flaw where adding a new IPO (e.g.
    RACE in late 2015) would instantly drag the basket level down because
    its raw price was far below the compounded values of existing tickers.

    Args:
        client: Tradier market client, or None to use yfinance fallback.
        start: History start date "YYYY-MM-DD".
        end: History end date or None for today.
        use_cache: Whether to use disk cache.

    Returns:
        (basket_series, metadata_dict)

    Raises:
        WRSDataError: Fewer than MIN_BASKET_TICKERS available.
    """
    series_map: dict[str, pd.Series] = {}
    missing: list[str] = []

    for ticker in LUXURY_BASKET:
        try:
            if client is not None:
                raw = _fetch_series_tradier(client, ticker, start, end, use_cache)
            else:
                raw = _fetch_series_yfinance(ticker, start, end, use_cache)
            # Store raw prices — do NOT rebase individual tickers
            series_map[ticker] = raw
            _logger.info("WRS basket: %s fetched (%d bars)", ticker, len(raw))
        except WRSDataError as exc:
            missing.append(ticker)
            _logger.warning("WRS basket: %s unavailable — %s", ticker, exc)
        except Exception as exc:
            missing.append(ticker)
            _logger.warning("WRS basket: %s error — %s", ticker, exc)

    n_available = len(series_map)
    if n_available < MIN_BASKET_TICKERS:
        raise WRSDataError(
            f"WRS basket has only {n_available} tickers "
            f"(minimum {MIN_BASKET_TICKERS}). Missing: {missing}"
        )
    if n_available < WARN_BASKET_TICKERS:
        _logger.warning(
            "WRS basket is thin: %d of %d tickers available",
            n_available, len(LUXURY_BASKET),
        )

    # 1. Align raw prices on a common DatetimeIndex (outer join — NaN where a
    #    ticker hasn't started yet or was delisted)
    df_prices = pd.concat(series_map.values(), axis=1)
    df_prices.columns = list(series_map.keys())

    # 2. Daily percentage returns; NaN on a ticker's first row (no prior close)
    df_returns = df_prices.pct_change()

    # 3. Equal-weight cross-sectional mean — only averages actively trading names
    daily_mean_return = df_returns.mean(axis=1, skipna=True)

    # 4. First row has no prior close → treat as 0% return so cumprod starts at 1
    if not daily_mean_return.empty:
        daily_mean_return.iloc[0] = 0.0

    # 5. Compound into an index rebased to 100
    basket = (1 + daily_mean_return).cumprod() * 100.0
    basket.name = "LUXURY"

    # Composition timeline: tickers alive per calendar year
    yearly_counts: dict[int, int] = (
        df_prices.notna().groupby(df_prices.index.year).any().sum(axis=1).to_dict()
    )

    metadata: dict[str, Any] = {
        "available_tickers": list(series_map.keys()),
        "missing_tickers": missing,
        "first_date": basket.index.min().date().isoformat(),
        "last_date": basket.index.max().date().isoformat(),
        "composition_timeline": yearly_counts,
    }
    return basket, metadata


# ==============================================================================
# ALIGNMENT
# ==============================================================================

def _align(wmt: pd.Series, luxury: pd.Series) -> pd.DataFrame:
    """
    Inner-join WMT and LUXURY on DatetimeIndex.

    Forward-fills gaps up to 3 days only (handles missed prints / holidays)
    then drops any remaining NaN rows.
    """
    df = pd.concat([wmt, luxury], axis=1)
    df.columns = ["wmt", "luxury"]
    df = df.ffill(limit=3).dropna()
    return df


# ==============================================================================
# SIGNAL COMPUTATION
# ==============================================================================

def _compute_wrs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute WRS ratio and derived analytics.

    Input columns: wmt, luxury
    Added columns:
        wrs          — raw ratio wmt / luxury
        wrs_30d_ma   — 30-day SMA (min_periods=20)
        wrs_90d_ma   — 90-day SMA (min_periods=60)
        wrs_pct_rank — expanding percentile rank 0–100
        wrs_zscore   — 252-day rolling z-score
        yoy_change   — year-over-year change in raw WRS
    """
    out = df.copy()
    out["wrs"] = out["wmt"] / out["luxury"]
    out["wrs_30d_ma"] = out["wrs"].rolling(30, min_periods=20).mean()
    out["wrs_90d_ma"] = out["wrs"].rolling(90, min_periods=60).mean()
    out["wrs_pct_rank"] = out["wrs"].expanding().rank(pct=True) * 100.0
    rolling = out["wrs"].rolling(252, min_periods=120)
    out["wrs_zscore"] = (out["wrs"] - rolling.mean()) / rolling.std()
    out["yoy_change"] = out["wrs"] - out["wrs"].shift(252)
    return out


def _resolve_signal_level(pct_rank: float) -> WRSLevel:
    """Map percentile rank to WRSLevel."""
    for level_name, (lo, hi) in SIGNAL_LEVELS.items():
        if lo <= pct_rank < hi:
            return WRSLevel(level_name)
    return WRSLevel.CRITICAL


def _detect_crossovers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return crossover events between wrs_30d_ma and wrs_90d_ma.

    'up' = 30d crosses above 90d (WRS worsening — recession signal rising).
    'down' = 30d crosses below 90d (WRS improving).
    """
    diff = df["wrs_30d_ma"] - df["wrs_90d_ma"]
    sign = np.sign(diff)
    mask = sign != sign.shift(1)
    crossovers = df.loc[mask].copy()
    crossovers["direction"] = np.where(diff[mask] > 0, "up", "down")
    return crossovers[["wrs", "direction"]].dropna()


def _extract_result(
    computed: pd.DataFrame,
    basket_meta: dict[str, Any],
) -> WRSResult:
    """Distil a computed WRS DataFrame into a WRSResult."""
    last = computed.iloc[-1]
    pct = float(last["wrs_pct_rank"])
    level = _resolve_signal_level(pct)

    crossovers = _detect_crossovers(computed)
    last_cross_date: Optional[str] = None
    last_cross_dir: Optional[str] = None
    if not crossovers.empty:
        last_cross_date = crossovers.index[-1].date().isoformat()
        last_cross_dir = str(crossovers.iloc[-1]["direction"])

    return WRSResult(
        date=computed.index[-1].date().isoformat(),
        wrs=float(last["wrs"]),
        wrs_30d_ma=float(last["wrs_30d_ma"]),
        wrs_90d_ma=float(last["wrs_90d_ma"]),
        wrs_pct_rank=pct,
        wrs_zscore=float(last["wrs_zscore"]),
        yoy_change=float(last["yoy_change"]),
        signal_level=level,
        basket_available=len(basket_meta.get("available_tickers", [])),
        basket_missing=basket_meta.get("missing_tickers", []),
        data_start=computed.index.min().date().isoformat(),
        data_end=computed.index.max().date().isoformat(),
        last_crossover_date=last_cross_date,
        last_crossover_dir=last_cross_dir,
        strategy_guidance=STRATEGY_GATES.get(level.value, ""),
        timestamp=datetime.now(timezone.utc),
    )


# ==============================================================================
# MAIN CLASS
# ==============================================================================

class WRSSignal:
    """
    Walmart Recession Signal — macro regime overlay for Spyder.

    Singleton-compatible; thread-safe via internal lock.

    Usage:
        signal = WRSSignal()
        result = signal.compute()
        print(result.signal_level, result.wrs_pct_rank)

    Integration with S07 orchestrator:
        The `get_signal_dict()` method returns a flat dict compatible
        with MetricSnapshot expansion in SpyderS07.
    """

    _instance: Optional["WRSSignal"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        tradier_token: Optional[str] = None,
        sandbox: bool = False,
        use_cache: bool = True,
        start: str = HISTORY_START,
    ) -> None:
        env_token = tradier_token or os.getenv("TRADIER_API_KEY")
        env_sandbox = sandbox or (
            os.getenv("TRADIER_ENVIRONMENT", "live").lower() == "sandbox"
        )

        self._use_cache = use_cache
        self._start = start
        self._last_result: Optional[WRSResult] = None
        self._compute_lock = threading.Lock()

        if env_token:
            self._client: Optional[_TradierMarketClient] = _TradierMarketClient(
                env_token, sandbox=env_sandbox
            )
            _logger.info("WRSSignal: Tradier client initialised (sandbox=%s)", env_sandbox)
        else:
            self._client = None
            _logger.warning(
                "WRSSignal: TRADIER_API_KEY not set — will fall back to yfinance"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(self, force_refresh: bool = False) -> WRSResult:
        """
        Compute (or return cached) WRS result.

        Args:
            force_refresh: Bypass disk cache and re-fetch all price data.

        Returns:
            WRSResult with current signal level and analytics.
        """
        with self._compute_lock:
            use_cache = self._use_cache and not force_refresh
            try:
                return self._compute_internal(use_cache)
            except WRSDataError as exc:
                _logger.error("WRS computation failed: %s", exc)
                result = WRSResult(error=str(exc), timestamp=datetime.now(timezone.utc))
                self._last_result = result
                return result
            except Exception as exc:
                _logger.exception("WRS unexpected error: %s", exc)
                result = WRSResult(
                    error=f"Unexpected: {exc}", timestamp=datetime.now(timezone.utc)
                )
                self._last_result = result
                return result

    def get_signal_dict(self, force_refresh: bool = False) -> dict[str, Any]:
        """
        Return flat dict for MetricSnapshot / dashboard consumption.

        Keys:
            wrs, wrs_pct_rank, wrs_zscore, wrs_signal_level,
            wrs_30d_ma, wrs_90d_ma, wrs_yoy_change,
            wrs_basket_available, wrs_data_date, wrs_error
        """
        r = self.compute(force_refresh=force_refresh)
        return {
            "wrs":                   r.wrs,
            "wrs_pct_rank":          r.wrs_pct_rank,
            "wrs_zscore":            r.wrs_zscore,
            "wrs_signal_level":      r.signal_level.value,
            "wrs_30d_ma":            r.wrs_30d_ma,
            "wrs_90d_ma":            r.wrs_90d_ma,
            "wrs_yoy_change":        r.yoy_change,
            "wrs_basket_available":  r.basket_available,
            "wrs_data_date":         r.date,
            "wrs_strategy_guidance": r.strategy_guidance,
            "wrs_error":             r.error,
        }

    @property
    def last_result(self) -> Optional[WRSResult]:
        """Most recent computed result, or None if never computed."""
        return self._last_result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _compute_internal(self, use_cache: bool) -> WRSResult:
        """Core computation — not thread-protected (caller holds lock)."""
        end_date = date.today().isoformat()

        # Fetch WMT
        _logger.info("WRS: fetching WMT history (%s → %s)", self._start, end_date)
        if self._client is not None:
            wmt = _fetch_series_tradier(
                self._client, WMT_TICKER, self._start, end_date, use_cache
            )
        else:
            wmt = _fetch_series_yfinance(
                WMT_TICKER, self._start, end_date, use_cache
            )
        _logger.info("WRS: WMT — %d bars", len(wmt))

        # Build luxury basket
        _logger.info("WRS: building luxury basket")
        luxury, basket_meta = _build_luxury_basket(
            self._client, self._start, end_date, use_cache
        )

        # Align
        aligned = _align(wmt, luxury)
        if len(aligned) < 252:
            _logger.warning(
                "WRS: aligned series has only %d bars — "
                "percentile rank and z-score may be unreliable",
                len(aligned),
            )

        # Compute
        computed = _compute_wrs(aligned)
        result = _extract_result(computed, basket_meta)
        self._last_result = result

        _logger.info(
            "WRS: %s | pct_rank=%.1f%% | z=%.2f | level=%s",
            result.date,
            result.wrs_pct_rank,
            result.wrs_zscore,
            result.signal_level.value,
        )
        return result


# ==============================================================================
# SINGLETON ACCESSOR
# ==============================================================================

_wrs_instance: Optional[WRSSignal] = None
_wrs_init_lock = threading.Lock()


def get_wrs_signal(
    tradier_token: Optional[str] = None,
    sandbox: bool = False,
    use_cache: bool = True,
) -> WRSSignal:
    """
    Return the module-level WRSSignal singleton.

    Creates it on first call with the supplied (or env-derived) credentials.
    Subsequent calls return the same instance regardless of arguments.
    """
    global _wrs_instance
    with _wrs_init_lock:
        if _wrs_instance is None:
            _wrs_instance = WRSSignal(
                tradier_token=tradier_token,
                sandbox=sandbox,
                use_cache=use_cache,
            )
    return _wrs_instance


# ==============================================================================
# OPTIONAL CHART HELPER
# ==============================================================================

def plot_wrs(
    start: str = HISTORY_START,
    tradier_token: Optional[str] = None,
    output_path: Optional[Path] = None,
    show: bool = False,
) -> Optional[Path]:
    """
    Render a 3-panel WRS chart and save to PNG.

    Panel 1: Raw WRS + 30d/90d MAs + recession bands + crossover markers.
    Panel 2: Expanding percentile rank with threshold lines.
    Panel 3: WMT vs luxury basket (normalised to 100 at HISTORY_START).

    Args:
        start: History start date.
        tradier_token: Override TRADIER_API_KEY env var.
        output_path: Save path. Defaults to ~/.spyder/wrs_cache/wrs_YYYYMMDD.png.
        show: Call plt.show() after rendering.

    Returns:
        Path to the saved PNG, or None on failure.
    """
    try:
        import matplotlib.pyplot as plt  # noqa: PLC0415
        import matplotlib.patches as mpatches  # noqa: F401, PLC0415
    except ImportError:
        _logger.error("WRS chart: matplotlib not installed")
        return None

    signal = get_wrs_signal(tradier_token=tradier_token)
    result = signal.compute()
    if result.error:
        _logger.error("WRS chart: cannot render — %s", result.error)
        return None

    # Re-fetch the full computed DataFrame for charting
    # (compute() only stores the scalar result; re-run internally)
    try:
        end_date = date.today().isoformat()
        if signal._client is not None:
            wmt = _fetch_series_tradier(
                signal._client, WMT_TICKER, start, end_date, use_cache=True
            )
        else:
            wmt = _fetch_series_yfinance(WMT_TICKER, start, end_date, use_cache=True)
        luxury, _ = _build_luxury_basket(signal._client, start, end_date, use_cache=True)
        aligned = _align(wmt, luxury)
        df = _compute_wrs(aligned)
    except Exception as exc:
        _logger.error("WRS chart: data preparation failed — %s", exc)
        return None

    plt.style.use("dark_background")
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(16, 12), dpi=100, sharex=True)

    title_icon = {"NORMAL": "✅", "CAUTION": "⚠️", "WARNING": "🔶", "CRITICAL": "🚨"}
    icon = title_icon.get(result.signal_level.value, "")
    fig.suptitle(
        f"Walmart Recession Signal (WRS) | {result.date}\n"
        f"Value: {result.wrs:.5f}  |  Rank: {result.wrs_pct_rank:.1f}%  "
        f"|  {icon} {result.signal_level.value}",
        fontsize=13,
        color="white",
    )

    # --- Panel 1: WRS ratio + MAs ---
    ax1.plot(df.index, df["wrs"], color="#888888", linewidth=0.8, alpha=0.6, label="WRS")
    ax1.plot(df.index, df["wrs_30d_ma"], color="#FFA500", linewidth=1.8, label="30d MA")
    ax1.plot(
        df.index, df["wrs_90d_ma"],
        color="#00BFFF", linewidth=1.8, linestyle="--", label="90d MA",
    )
    for band_start, band_end, label in RECESSION_BANDS:
        ax1.axvspan(
            pd.Timestamp(band_start), pd.Timestamp(band_end),
            alpha=0.15, color="red",
        )
        ax1.text(
            pd.Timestamp(band_start), ax1.get_ylim()[1] if ax1.get_ylim()[1] else 0.1,
            label, color="red", fontsize=7, va="top",
        )
    crossovers = _detect_crossovers(df)
    up_crosses = crossovers[crossovers["direction"] == "up"]
    for ts in up_crosses.index:
        ax1.axvline(ts, color="red", linewidth=0.8, linestyle="--", alpha=0.5)
    ax1.set_ylabel("WRS Ratio", color="white")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(alpha=0.2)

    # --- Panel 2: Percentile rank ---
    ax2.fill_between(df.index, df["wrs_pct_rank"], alpha=0.4, color="#9370DB")
    ax2.axhline(60.0, color="green", linewidth=1.0, linestyle="--", label="60 (Caution)")
    ax2.axhline(75.0, color="orange", linewidth=1.0, linestyle="--", label="75 (Warning)")
    ax2.axhline(90.0, color="red", linewidth=1.0, linestyle="--", label="90 (Critical)")
    ax2.fill_between(
        df.index,
        np.where(df["wrs_pct_rank"] >= 90, df["wrs_pct_rank"], 90),
        90,
        alpha=0.3, color="red",
    )
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("Pct Rank", color="white")
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(alpha=0.2)

    # --- Panel 3: WMT vs luxury (normalised to 100 at HISTORY_START) ---
    wmt_norm = (df["wmt"] / df["wmt"].iloc[0]) * 100
    lux_norm = (df["luxury"] / df["luxury"].iloc[0]) * 100
    ax3.plot(df.index, wmt_norm, color="#4169E1", linewidth=1.5, label="WMT")
    ax3.plot(df.index, lux_norm, color="#FFD700", linewidth=1.5, label="Luxury Basket")
    ax3.set_ylabel("Normalised (100)", color="white")
    ax3.legend(loc="upper left", fontsize=8)
    ax3.grid(alpha=0.2)
    ax3.set_xlabel("Date", color="white")

    plt.tight_layout(rect=[0, 0, 1, 0.95])

    if output_path is None:
        today_str = date.today().strftime("%Y%m%d")
        output_path = _CACHE_DIR / f"wrs_{today_str}.png"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=100, bbox_inches="tight", facecolor="#1a1a1a")
    _logger.info("WRS chart saved: %s", output_path)

    if show:
        plt.show()
    plt.close(fig)
    return output_path


# ==============================================================================
# CLI ENTRY POINT
# ==============================================================================

def _cli_main() -> None:
    """Standalone CLI — print WRS report to stdout."""
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Walmart Recession Signal (WRS)")
    parser.add_argument("--refresh", action="store_true", help="Force cache refresh")
    parser.add_argument("--chart", action="store_true", help="Generate PNG chart")
    parser.add_argument("--show", action="store_true", help="Display chart interactively")
    parser.add_argument("--sandbox", action="store_true", help="Use Tradier sandbox")
    args = parser.parse_args()

    signal = WRSSignal(sandbox=args.sandbox)
    result = signal.compute(force_refresh=args.refresh)

    if result.error:
        print(f"ERROR: {result.error}")  # noqa: T201
        return

    _ICONS = {
        "NORMAL": "✅",
        "CAUTION": "⚠️",
        "WARNING": "🔶",
        "CRITICAL": "🚨",
    }
    icon = _ICONS.get(result.signal_level.value, "")
    yoy_str = f"{result.yoy_change:+.4f}" if not np.isnan(result.yoy_change) else "N/A"
    last_cross = (
        f"{result.last_crossover_date} (↑ up)"
        if result.last_crossover_dir == "up"
        else f"{result.last_crossover_date} (↓ down)"
        if result.last_crossover_date
        else "None"
    )

    width = 50
    border = "─" * width
    print(f"┌{border}┐")  # noqa: T201
    print(f"│{'WALMART RECESSION SIGNAL (WRS)':^{width}}│")  # noqa: T201
    print(f"│{f'As of: {result.date}':^{width}}│")  # noqa: T201
    print(f"├{border}┤")  # noqa: T201
    print(f"│  {'WRS Value':20}: {result.wrs:.5f}{' ' * (width - 29)}│")  # noqa: T201
    print(f"│  {'30-Day MA':20}: {result.wrs_30d_ma:.5f}{' ' * (width - 29)}│")  # noqa: T201
    print(f"│  {'90-Day MA':20}: {result.wrs_90d_ma:.5f}{' ' * (width - 29)}│")  # noqa: T201
    print(f"│  {'YoY Change':20}: {yoy_str}{' ' * (width - 12 - len(yoy_str))}│")  # noqa: T201
    pct_str = f"{result.wrs_pct_rank:.1f}%"
    print(f"│  {'Percentile Rank':20}: {pct_str}{' ' * (width - 12 - len(pct_str))}│")  # noqa: T201
    z_str = f"{result.wrs_zscore:.2f}"
    print(f"│  {'Z-Score (252d)':20}: {z_str}{' ' * (width - 12 - len(z_str))}│")  # noqa: T201
    lvl_str = f"{icon} {result.signal_level.value}"
    print(f"│  {'Signal Level':20}: {lvl_str}{' ' * (width - 12 - len(lvl_str))}│")  # noqa: T201
    print(f"├{border}┤")  # noqa: T201
    bkt_str = f"{result.basket_available} of {len(LUXURY_BASKET)} tickers"
    print(f"│  {'Luxury Basket':20}: {bkt_str}{' ' * (width - 12 - len(bkt_str))}│")  # noqa: T201
    miss_str = ", ".join(result.basket_missing) if result.basket_missing else "None"
    print(f"│  {'Missing':20}: {miss_str}{' ' * max(0, width - 12 - len(miss_str))}│")  # noqa: T201
    rng_str = f"{result.data_start} → {result.data_end}"
    print(f"│  {'Data Range':20}: {rng_str}{' ' * max(0, width - 12 - len(rng_str))}│")  # noqa: T201
    print(f"│  {'Last Crossover':20}: {last_cross}{' ' * max(0, width - 12 - len(last_cross))}│")  # noqa: T201
    print(f"└{border}┘")  # noqa: T201
    print(f"\nGuidance: {result.strategy_guidance}")  # noqa: T201

    if args.chart or args.show:
        path = plot_wrs(show=args.show)
        if path:
            print(f"\nChart saved: {path}")  # noqa: T201


if __name__ == "__main__":
    _cli_main()
