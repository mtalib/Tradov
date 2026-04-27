#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderS_Signals
Module: SpyderS13_PSRSignal.py
Purpose: Pawn Shop Ratio (PSR) — macro regime overlay signal (working-class
         liquidity exhaustion indicator)

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-21 Time: 00:00:00

Description:
    Implements the Pawn Shop Ratio (PSR), a contrarian macro-economic ratio
    comparing the publicly traded pawn sector against the traditional financial
    sector (XLF).  As consumer credit tightens, working-class households turn
    to pawn collateral loans — the last resort of the unbanked — while bank
    stocks simultaneously suffer rising default risk.  Pawn shop equities
    therefore outperform the financial sector precisely when the credit cycle
    is rolling over.

    Formula:
        PSR = (Price(FCFS) + Price(EZPW)) / Price(XLF)

    Components:
        FCFS  — FirstCash Holdings, the largest US/LatAm pawn operator (NASDAQ)
        EZPW  — EZCORP Inc, the second-largest US pawn operator (NASDAQ)
        XLF   — Financial Select Sector SPDR ETF, representing bank stocks

    Interpretation:
        * PSR FALLING → banks healthy, credit flowing freely; no pawn signal.
        * PSR RISING  → Wall Street pricing in a traditional credit crunch:
                         banks face mounting defaults; pawn shops see surging
                         collateral-loan demand from cash-strapped borrowers.

    This indicator leads official government lagging indicators (CPI,
    unemployment) and traditional bank credit metrics (card write-offs) by
    several months.  People exhaust every other option before defaulting —
    including surrendering personal property to a pawn broker.

Signal Levels (by expanding percentile rank over full history):
    NORMAL   :  0 – 60th pct   — full strategy palette
    CAUTION  : 60 – 75th pct   — reduce short-put exposure
    WARNING  : 75 – 90th pct   — defensive posture only
    CRITICAL : 90 – 100th pct  — minimum size; put-bias on 0-DTE; max hedges

Dual-Signal Interpretation (PSR × WRS):
    WRS LOW  + PSR LOW  → Economy healthy; no signals.
    WRS HIGH + PSR LOW  → Middle-class down-trading only (frugality, not crisis).
    WRS HIGH + PSR HIGH → CONFIRMED SYSTEMIC CRISIS: multi-tiered consumer stress;
                          maximum bearish posture; favour put credit spreads.

Data Sources:
    Primary  : Tradier REST API (TRADIER_API_KEY env var)
    Fallback : yfinance (development / Tradier unavailable)

Caching:
    Daily OHLCV data cached to ~/.spyder/psr_cache/ with 4-hour TTL.

Update Cadence:
    Daily close — PSR moves on weekly/monthly timescales.  No intraday refresh
    needed.  Integrated with SpyderS07_CustomMetricsOrchestrator.

Integration:
    - SpyderD30_RegimeGatedSelector: uses signal_level to gate strategies
    - SpyderF10_MarketRegimeDetector: adds macro context to regime composite
    - SpyderS07_CustomMetricsOrchestrator: exposes psr to MetricSnapshot
    - SpyderG05_TradingDashboard: clickable PSR widget with detail dialog
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import os
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
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

# PSR components
FCFS_TICKER = "FCFS"   # FirstCash Holdings (largest pawn operator)
EZPW_TICKER = "EZPW"   # EZCORP (second largest pawn operator)
XLF_TICKER  = "XLF"    # Financial Select Sector SPDR ETF

# Full history available from start of 2000 for all three tickers
HISTORY_START = "2000-01-01"

# Cache
_CACHE_DIR = Path("~/.spyder/psr_cache").expanduser()
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
    "NORMAL":   "Full strategy palette; no working-class credit stress detected.",
    "CAUTION":  "Pawn sector outperforming banks — credit tightening signal. Reduce short-put exposure.",  # noqa: E501
    "WARNING":  "Significant consumer liquidity stress. Defensive posture only — bear call spreads, reduced size.",  # noqa: E501
    "CRITICAL": "Systemic credit crunch confirmed. Minimum size; put-bias on 0-DTE bounces; maximum hedges.",  # noqa: E501
}


# ==============================================================================
# ENUMS
# ==============================================================================

class PSRLevel(str, Enum):
    """PSR signal severity levels."""
    NORMAL   = "NORMAL"
    CAUTION  = "CAUTION"
    WARNING  = "WARNING"
    CRITICAL = "CRITICAL"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class PSRResult:
    """
    Full PSR computation result for a given date.

    Attributes:
        date: ISO date of the most recent reading.
        psr: Raw ratio — (FCFS + EZPW) / XLF.
        psr_30d_ma: 30-day simple moving average of PSR.
        psr_90d_ma: 90-day simple moving average of PSR.
        psr_pct_rank: Expanding percentile rank (0–100) over full history.
        psr_zscore: Rolling 252-day z-score.
        yoy_change: Year-over-year change in raw PSR (current minus 252d ago).
        signal_level: NORMAL / CAUTION / WARNING / CRITICAL.
        fcfs_price: Last closing price of FCFS.
        ezpw_price: Last closing price of EZPW.
        xlf_price: Last closing price of XLF.
        data_start: First date in the aligned series.
        data_end: Last date in the aligned series.
        last_crossover_date: Most recent 30d/90d MA crossover date, or None.
        last_crossover_dir: 'up' (worsening) or 'down' (improving), or None.
        strategy_guidance: Human-readable strategy implication.
        timestamp: Wall-clock time of computation.
        error: Non-empty string if computation partially failed.
    """
    date: str = ""
    psr: float = float("nan")
    psr_30d_ma: float = float("nan")
    psr_90d_ma: float = float("nan")
    psr_pct_rank: float = float("nan")
    psr_zscore: float = float("nan")
    yoy_change: float = float("nan")
    signal_level: PSRLevel = PSRLevel.NORMAL
    fcfs_price: float = float("nan")
    ezpw_price: float = float("nan")
    xlf_price: float = float("nan")
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

class PSRDataError(RuntimeError):
    """Raised when PSR computation cannot proceed due to missing data."""


# ==============================================================================
# TRADIER MARKET DATA CLIENT
# ==============================================================================

class _TradierMarketClient:
    """
    Thin HTTP wrapper for Tradier market data endpoints.

    Dedicated instance for PSR to avoid coupling with the broker-layer
    SpyderB40_TradierClient (which handles order management only).
    """

    def __init__(self, token: str, sandbox: bool = False) -> None:
        base = TRADIER_SANDBOX_URL if sandbox else TRADIER_LIVE_URL
        self._base_url = base
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })
        _logger.debug("PSR TradierMarketClient initialised (sandbox=%s)", sandbox)

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
        The `close` field is split/dividend-adjusted.

        Args:
            symbol: Ticker, e.g. "FCFS" or "XLF".
            start: Start date "YYYY-MM-DD" (inclusive).
            end: End date "YYYY-MM-DD" (defaults to today).
            interval: "daily" | "weekly" | "monthly".

        Returns:
            List of dicts with keys: date, open, high, low, close, volume.

        Raises:
            PSRDataError: Symbol returns null/empty history or HTTP error.
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
            raise PSRDataError(
                f"Tradier returned null history for {symbol} "
                f"({start} → {end})"
            )
        days = history["day"]
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
                    raise PSRDataError(
                        "Tradier 401 — check TRADIER_API_KEY in .env"
                    )
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", "5"))
                    _logger.warning("Tradier 429 — waiting %ds", wait)
                    time.sleep(wait)
                    continue
                if resp.status_code >= 500:
                    last_exc = PSRDataError(
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

        raise PSRDataError(
            f"Tradier request failed after {MAX_RETRIES} attempts: {last_exc}"
        )


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
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    if age > timedelta(hours=CACHE_TTL_HOURS):
        return None
    try:
        s = pd.read_csv(path, index_col=0, parse_dates=True).squeeze("columns")
        s.name = key.split("_")[0]
        _logger.debug("PSR cache hit: %s", key)
        return s
    except Exception as exc:
        _logger.warning("PSR cache read failed (%s): %s", key, exc)
        return None


def _save_cache(key: str, series: pd.Series) -> None:
    """Save series to CSV cache."""
    try:
        series.to_csv(_cache_path(key), header=True)
        _logger.debug("PSR cache saved: %s (%d bars)", key, len(series))
    except Exception as exc:
        _logger.warning("PSR cache write failed (%s): %s", key, exc)


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
            raise PSRDataError(f"yfinance returned empty history for {symbol}")
        series = hist["Close"].rename(symbol)
        series.index = pd.DatetimeIndex(series.index.date)
        _save_cache(cache_key, series)
        return series
    except ImportError:
        raise PSRDataError("yfinance not installed — Tradier is required")  # noqa: B904


# ==============================================================================
# ALIGNMENT
# ==============================================================================

def _align(fcfs: pd.Series, ezpw: pd.Series, xlf: pd.Series) -> pd.DataFrame:
    """
    Inner-join FCFS, EZPW, XLF on DatetimeIndex.

    Forward-fills gaps up to 3 days only (handles missed prints / holidays)
    then drops any remaining NaN rows.
    """
    df = pd.concat([fcfs, ezpw, xlf], axis=1)
    df.columns = ["fcfs", "ezpw", "xlf"]
    df = df.ffill(limit=3).dropna()
    return df


# ==============================================================================
# SIGNAL COMPUTATION
# ==============================================================================

def _compute_psr(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute PSR ratio and derived analytics.

    Input columns: fcfs, ezpw, xlf
    Added columns:
        psr          — raw ratio (fcfs + ezpw) / xlf
        psr_30d_ma   — 30-day SMA (min_periods=20)
        psr_90d_ma   — 90-day SMA (min_periods=60)
        psr_pct_rank — expanding percentile rank 0–100
        psr_zscore   — 252-day rolling z-score
        yoy_change   — year-over-year change in raw PSR
    """
    out = df.copy()
    out["psr"] = (out["fcfs"] + out["ezpw"]) / out["xlf"]
    out["psr_30d_ma"] = out["psr"].rolling(30, min_periods=20).mean()
    out["psr_90d_ma"] = out["psr"].rolling(90, min_periods=60).mean()
    out["psr_pct_rank"] = out["psr"].expanding().rank(pct=True) * 100.0
    rolling = out["psr"].rolling(252, min_periods=120)
    out["psr_zscore"] = (out["psr"] - rolling.mean()) / rolling.std()
    out["yoy_change"] = out["psr"] - out["psr"].shift(252)
    return out


def _resolve_signal_level(pct_rank: float) -> PSRLevel:
    """Map percentile rank to PSRLevel."""
    for level_name, (lo, hi) in SIGNAL_LEVELS.items():
        if lo <= pct_rank < hi:
            return PSRLevel(level_name)
    return PSRLevel.CRITICAL


def _detect_crossovers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return crossover events between psr_30d_ma and psr_90d_ma.

    'up'   = 30d crosses above 90d (PSR worsening — liquidity stress rising).
    'down' = 30d crosses below 90d (PSR improving).
    """
    diff = df["psr_30d_ma"] - df["psr_90d_ma"]
    sign = np.sign(diff)
    mask = sign != sign.shift(1)
    crossovers = df.loc[mask].copy()
    crossovers["direction"] = np.where(diff[mask] > 0, "up", "down")
    return crossovers[["psr", "direction"]].dropna()


def _extract_result(computed: pd.DataFrame) -> PSRResult:
    """Distil a computed PSR DataFrame into a PSRResult."""
    last = computed.iloc[-1]
    pct = float(last["psr_pct_rank"])
    level = _resolve_signal_level(pct)

    crossovers = _detect_crossovers(computed)
    last_cross_date: Optional[str] = None
    last_cross_dir: Optional[str] = None
    if not crossovers.empty:
        last_cross_date = crossovers.index[-1].date().isoformat()
        last_cross_dir = str(crossovers.iloc[-1]["direction"])

    return PSRResult(
        date=computed.index[-1].date().isoformat(),
        psr=float(last["psr"]),
        psr_30d_ma=float(last["psr_30d_ma"]),
        psr_90d_ma=float(last["psr_90d_ma"]),
        psr_pct_rank=pct,
        psr_zscore=float(last["psr_zscore"]),
        yoy_change=float(last["yoy_change"]),
        signal_level=level,
        fcfs_price=float(last["fcfs"]),
        ezpw_price=float(last["ezpw"]),
        xlf_price=float(last["xlf"]),
        data_start=computed.index.min().date().isoformat(),
        data_end=computed.index.max().date().isoformat(),
        last_crossover_date=last_cross_date,
        last_crossover_dir=last_cross_dir,
        strategy_guidance=STRATEGY_GATES.get(level.value, ""),
        timestamp=datetime.now(),
    )


# ==============================================================================
# DUAL-SIGNAL INTERPRETER
# ==============================================================================

def interpret_dual_signal(
    psr_level: str,
    wrs_level: str,
) -> dict[str, str]:
    """
    Combine PSR and WRS signal levels into a unified macro regime assessment.

    Args:
        psr_level: One of NORMAL / CAUTION / WARNING / CRITICAL.
        wrs_level: One of NORMAL / CAUTION / WARNING / CRITICAL.

    Returns:
        Dict with keys: regime, description, trading_bias, size_multiplier.
    """
    _severity: dict[str, int] = {
        "NORMAL": 0, "CAUTION": 1, "WARNING": 2, "CRITICAL": 3
    }
    p = _severity.get(psr_level, 0)
    w = _severity.get(wrs_level, 0)
    combined = p + w

    if combined == 0:
        return {
            "regime":           "HEALTHY",
            "description":      "Economy healthy — no consumer stress detected.",
            "trading_bias":     "Neutral; full strategy palette.",
            "size_multiplier":  "1.00",
        }
    if w >= 2 and p <= 0:
        return {
            "regime":           "MIDDLE_CLASS_PULLBACK",
            "description":      "Middle class down-trading (WRS elevated) but credit still available (PSR low). Mild bearish bias.",  # noqa: E501
            "trading_bias":     "Slight bear bias; reduce Iron Condor long-delta tilt.",
            "size_multiplier":  "0.80",
        }
    if p >= 2 and w <= 0:
        return {
            "regime":           "WORKING_CLASS_STRESS",
            "description":      "Pawn shops outperforming banks (PSR elevated) without middle-class stress. Watch for contagion upward.",  # noqa: E501
            "trading_bias":     "Defensive; reduce short-put exposure; monitor WRS.",
            "size_multiplier":  "0.75",
        }
    if combined >= 5:
        return {
            "regime":           "SYSTEMIC_CRISIS",
            "description":      "CONFIRMED MULTI-TIERED CONSUMER CRISIS — both WRS and PSR critical. Maximum bearish posture.",  # noqa: E501
            "trading_bias":     "Heavy put-side bias; sell call credit spreads on rallies; 0-DTE mean reversion down.",  # noqa: E501
            "size_multiplier":  "0.40",
        }
    if combined >= 3:
        return {
            "regime":           "BROAD_STRESS",
            "description":      "Broad consumer stress across income tiers. Both indicators elevated.",  # noqa: E501
            "trading_bias":     "Bearish regime; favour put spreads; reduce naked premium selling.",
            "size_multiplier":  "0.60",
        }
    return {
        "regime":           "EARLY_DETERIORATION",
        "description":      "Early consumer stress signals. One or both indicators moving into caution territory.",  # noqa: E501
        "trading_bias":     "Reduce size; avoid aggressive premium selling.",
        "size_multiplier":  "0.85",
    }


# ==============================================================================
# MAIN CLASS
# ==============================================================================

class PSRSignal:
    """
    Pawn Shop Ratio — macro liquidity-exhaustion regime overlay for Spyder.

    Singleton-compatible; thread-safe via internal lock.

    Usage:
        signal = PSRSignal()
        result = signal.compute()
        print(result.signal_level, result.psr_pct_rank)

    Integration with S07 orchestrator:
        The ``get_signal_dict()`` method returns a flat dict compatible
        with MetricSnapshot expansion in SpyderS07.
    """

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
        self._last_result: Optional[PSRResult] = None
        self._compute_lock = threading.Lock()

        if env_token:
            self._client: Optional[_TradierMarketClient] = _TradierMarketClient(
                env_token, sandbox=env_sandbox
            )
            _logger.info(
                "PSRSignal: Tradier client initialised (sandbox=%s)", env_sandbox
            )
        else:
            self._client = None
            _logger.warning(
                "PSRSignal: TRADIER_API_KEY not set — will fall back to yfinance"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(self, force_refresh: bool = False) -> PSRResult:
        """
        Compute (or return cached) PSR result.

        Args:
            force_refresh: Bypass disk cache and re-fetch all price data.

        Returns:
            PSRResult with current signal level and analytics.
        """
        with self._compute_lock:
            use_cache = self._use_cache and not force_refresh
            try:
                return self._compute_internal(use_cache)
            except PSRDataError as exc:
                _logger.error("PSR computation failed: %s", exc)
                result = PSRResult(error=str(exc), timestamp=datetime.now())
                self._last_result = result
                return result
            except Exception as exc:
                _logger.exception("PSR unexpected error: %s", exc)
                result = PSRResult(
                    error=f"Unexpected: {exc}", timestamp=datetime.now()
                )
                self._last_result = result
                return result

    def get_signal_dict(self, force_refresh: bool = False) -> dict[str, Any]:
        """
        Return flat dict for MetricSnapshot / dashboard consumption.

        Keys:
            psr, psr_pct_rank, psr_zscore, psr_signal_level,
            psr_30d_ma, psr_90d_ma, psr_yoy_change,
            psr_fcfs_price, psr_ezpw_price, psr_xlf_price,
            psr_data_date, psr_error
        """
        r = self.compute(force_refresh=force_refresh)
        return {
            "psr":               r.psr,
            "psr_pct_rank":      r.psr_pct_rank,
            "psr_zscore":        r.psr_zscore,
            "psr_signal_level":  r.signal_level.value,
            "psr_30d_ma":        r.psr_30d_ma,
            "psr_90d_ma":        r.psr_90d_ma,
            "psr_yoy_change":    r.yoy_change,
            "psr_fcfs_price":    r.fcfs_price,
            "psr_ezpw_price":    r.ezpw_price,
            "psr_xlf_price":     r.xlf_price,
            "psr_data_date":     r.date,
            "psr_strategy_guidance": r.strategy_guidance,
            "psr_crossover_date": r.last_crossover_date,
            "psr_crossover_dir":  r.last_crossover_dir,
            "psr_data_start":    r.data_start,
            "psr_data_end":      r.data_end,
            "psr_error":         r.error,
        }

    @property
    def last_result(self) -> Optional[PSRResult]:
        """Most recent computed result, or None if never computed."""
        return self._last_result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _compute_internal(self, use_cache: bool) -> PSRResult:
        """Core computation — not thread-protected (caller holds lock)."""
        end_date = date.today().isoformat()

        def _fetch(symbol: str) -> pd.Series:
            if self._client is not None:
                return _fetch_series_tradier(
                    self._client, symbol, self._start, end_date, use_cache
                )
            return _fetch_series_yfinance(symbol, self._start, end_date, use_cache)

        _logger.info(
            "PSR: fetching FCFS, EZPW, XLF (%s → %s)", self._start, end_date
        )
        fcfs = _fetch(FCFS_TICKER)
        ezpw = _fetch(EZPW_TICKER)
        xlf  = _fetch(XLF_TICKER)
        _logger.info(
            "PSR: bars — FCFS=%d, EZPW=%d, XLF=%d",
            len(fcfs), len(ezpw), len(xlf),
        )

        aligned = _align(fcfs, ezpw, xlf)
        if len(aligned) < 252:
            _logger.warning(
                "PSR: aligned series has only %d bars — "
                "percentile rank and z-score may be unreliable",
                len(aligned),
            )

        computed = _compute_psr(aligned)
        result = _extract_result(computed)
        self._last_result = result

        _logger.info(
            "PSR: %s | psr=%.4f | pct_rank=%.1f%% | z=%.2f | level=%s",
            result.date,
            result.psr,
            result.psr_pct_rank,
            result.psr_zscore,
            result.signal_level.value,
        )
        return result


# ==============================================================================
# SINGLETON ACCESSOR
# ==============================================================================

_psr_instance: Optional[PSRSignal] = None
_psr_init_lock = threading.Lock()


def get_psr_signal(
    tradier_token: Optional[str] = None,
    sandbox: bool = False,
    use_cache: bool = True,
) -> PSRSignal:
    """
    Return the module-level PSRSignal singleton.

    Creates it on first call with the supplied (or env-derived) credentials.
    Subsequent calls return the same instance regardless of arguments.
    """
    global _psr_instance
    with _psr_init_lock:
        if _psr_instance is None:
            _psr_instance = PSRSignal(
                tradier_token=tradier_token,
                sandbox=sandbox,
                use_cache=use_cache,
            )
    return _psr_instance


# ==============================================================================
# OPTIONAL CHART HELPER
# ==============================================================================

def plot_psr(
    start: str = HISTORY_START,
    tradier_token: Optional[str] = None,
    output_path: Optional[Path] = None,
    show: bool = False,
) -> Optional[Path]:
    """
    Render a 3-panel PSR chart and save to PNG.

    Panel 1: Raw PSR + 30d/90d MAs + recession bands + crossover markers.
    Panel 2: Expanding percentile rank with threshold lines.
    Panel 3: FCFS, EZPW, XLF (normalised to 100 at HISTORY_START).

    Args:
        start: History start date.
        tradier_token: Override TRADIER_API_KEY env var.
        output_path: Save path. Defaults to ~/.spyder/psr_cache/psr_YYYYMMDD.png.
        show: Call plt.show() after rendering.

    Returns:
        Path to the saved PNG, or None on failure.
    """
    try:
        import matplotlib.pyplot as plt  # noqa: PLC0415
    except ImportError:
        _logger.error("PSR chart: matplotlib not installed")
        return None

    signal = get_psr_signal(tradier_token=tradier_token)
    result = signal.compute()
    if result.error:
        _logger.error("PSR chart: cannot render — %s", result.error)
        return None

    # Re-fetch aligned DataFrame for charting
    try:
        end_date = date.today().isoformat()

        def _fetch(symbol: str) -> pd.Series:
            if signal._client is not None:
                return _fetch_series_tradier(
                    signal._client, symbol, start, end_date, use_cache=True
                )
            return _fetch_series_yfinance(symbol, start, end_date, use_cache=True)

        fcfs = _fetch(FCFS_TICKER)
        ezpw = _fetch(EZPW_TICKER)
        xlf  = _fetch(XLF_TICKER)
        aligned = _align(fcfs, ezpw, xlf)
        df = _compute_psr(aligned)
    except Exception as exc:
        _logger.error("PSR chart: data preparation failed — %s", exc)
        return None

    plt.style.use("dark_background")
    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1, figsize=(16, 12), dpi=100, sharex=True
    )

    title_icon = {
        "NORMAL": "✅", "CAUTION": "⚠️", "WARNING": "🔶", "CRITICAL": "🚨"
    }
    icon = title_icon.get(result.signal_level.value, "")
    fig.suptitle(
        f"Pawn Shop Ratio (PSR) — (FCFS + EZPW) / XLF | {result.date}\n"
        f"Value: {result.psr:.4f}  |  Rank: {result.psr_pct_rank:.1f}%  "
        f"|  {icon} {result.signal_level.value}",
        fontsize=13,
        color="white",
    )

    # --- Panel 1: PSR ratio + MAs ---
    ax1.plot(
        df.index, df["psr"],
        color="#888888", linewidth=0.8, alpha=0.6, label="PSR"
    )
    ax1.plot(
        df.index, df["psr_30d_ma"],
        color="#FFA500", linewidth=1.8, label="30d MA"
    )
    ax1.plot(
        df.index, df["psr_90d_ma"],
        color="#00BFFF", linewidth=1.8, linestyle="--", label="90d MA"
    )
    for band_start, band_end, label in RECESSION_BANDS:
        ax1.axvspan(
            pd.Timestamp(band_start), pd.Timestamp(band_end),
            alpha=0.15, color="red",
        )
        ax1.text(
            pd.Timestamp(band_start), df["psr"].max() * 0.98,
            label, color="red", fontsize=7, va="top",
        )
    crossovers = _detect_crossovers(df)
    up_crosses = crossovers[crossovers["direction"] == "up"]
    for ts in up_crosses.index:
        ax1.axvline(ts, color="red", linewidth=0.8, linestyle="--", alpha=0.5)
    ax1.set_ylabel("PSR = (FCFS+EZPW)/XLF", color="white")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(alpha=0.2)

    # --- Panel 2: Percentile rank ---
    ax2.fill_between(df.index, df["psr_pct_rank"], alpha=0.4, color="#9370DB")
    ax2.axhline(60.0, color="green",  linewidth=1.0, linestyle="--", label="60 (Caution)")
    ax2.axhline(75.0, color="orange", linewidth=1.0, linestyle="--", label="75 (Warning)")
    ax2.axhline(90.0, color="red",    linewidth=1.0, linestyle="--", label="90 (Critical)")
    ax2.fill_between(
        df.index,
        np.where(df["psr_pct_rank"] >= 90, df["psr_pct_rank"], 90),
        90,
        alpha=0.3, color="red",
    )
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("Pct Rank", color="white")
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(alpha=0.2)

    # --- Panel 3: FCFS, EZPW, XLF (normalised to 100) ---
    fcfs_norm = (df["fcfs"] / df["fcfs"].iloc[0]) * 100
    ezpw_norm = (df["ezpw"] / df["ezpw"].iloc[0]) * 100
    xlf_norm  = (df["xlf"]  / df["xlf"].iloc[0])  * 100
    ax3.plot(df.index, fcfs_norm, color="#4169E1", linewidth=1.5, label="FCFS")
    ax3.plot(df.index, ezpw_norm, color="#32CD32", linewidth=1.5, label="EZPW")
    ax3.plot(df.index, xlf_norm,  color="#FFD700", linewidth=1.5, label="XLF")
    ax3.set_ylabel("Normalised (100)", color="white")
    ax3.legend(loc="upper left", fontsize=8)
    ax3.grid(alpha=0.2)
    ax3.set_xlabel("Date", color="white")

    plt.tight_layout(rect=[0, 0, 1, 0.95])

    if output_path is None:
        today_str = date.today().strftime("%Y%m%d")
        output_path = _CACHE_DIR / f"psr_{today_str}.png"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=100, bbox_inches="tight", facecolor="#1a1a1a")
    _logger.info("PSR chart saved: %s", output_path)

    if show:
        plt.show()
    plt.close(fig)
    return output_path


# ==============================================================================
# CLI ENTRY POINT
# ==============================================================================

def _cli_main() -> None:
    """Standalone CLI — print PSR report to stdout."""
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(
        description="Pawn Shop Ratio (PSR) — working-class liquidity exhaustion signal"
    )
    parser.add_argument("--refresh", action="store_true", help="Force cache refresh")
    parser.add_argument("--chart",   action="store_true", help="Generate PNG chart")
    parser.add_argument("--show",    action="store_true", help="Display chart interactively")
    parser.add_argument("--sandbox", action="store_true", help="Use Tradier sandbox")
    args = parser.parse_args()

    signal = PSRSignal(sandbox=args.sandbox)
    result = signal.compute(force_refresh=args.refresh)

    if result.error:
        print(f"ERROR: {result.error}")  # noqa: T201
        return

    _ICONS = {
        "NORMAL":   "✅",
        "CAUTION":  "⚠️",
        "WARNING":  "🔶",
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

    width = 52
    border = "─" * width
    print(f"┌{border}┐")  # noqa: T201
    print(f"│{'PAWN SHOP RATIO (PSR)':^{width}}│")  # noqa: T201
    print(f"│{f'As of: {result.date}':^{width}}│")  # noqa: T201
    print(f"│{'Formula: (FCFS + EZPW) / XLF':^{width}}│")  # noqa: T201
    print(f"├{border}┤")  # noqa: T201
    print(f"│  {'PSR Value':22}: {result.psr:.4f}{' ' * (width - 30)}│")  # noqa: T201
    print(f"│  {'30-Day MA':22}: {result.psr_30d_ma:.4f}{' ' * (width - 30)}│")  # noqa: T201
    print(f"│  {'90-Day MA':22}: {result.psr_90d_ma:.4f}{' ' * (width - 30)}│")  # noqa: T201
    print(f"│  {'YoY Change':22}: {yoy_str}{' ' * (width - 10 - len(yoy_str))}│")  # noqa: T201
    pct_str = f"{result.psr_pct_rank:.1f}%"
    print(f"│  {'Percentile Rank':22}: {pct_str}{' ' * (width - 10 - len(pct_str))}│")  # noqa: T201
    z_str = f"{result.psr_zscore:.2f}"
    print(f"│  {'Z-Score (252d)':22}: {z_str}{' ' * (width - 10 - len(z_str))}│")  # noqa: T201
    lvl_str = f"{icon} {result.signal_level.value}"
    print(f"│  {'Signal Level':22}: {lvl_str}{' ' * (width - 10 - len(lvl_str))}│")  # noqa: T201
    print(f"├{border}┤")  # noqa: T201
    print(f"│  {'FCFS (FirstCash)':22}: ${result.fcfs_price:.2f}{' ' * max(0, width - 12 - len(f'${result.fcfs_price:.2f}'))}│")  # noqa: E501, T201
    print(f"│  {'EZPW (EZCORP)':22}: ${result.ezpw_price:.2f}{' ' * max(0, width - 12 - len(f'${result.ezpw_price:.2f}'))}│")  # noqa: E501, T201
    print(f"│  {'XLF (Fin. Sector)':22}: ${result.xlf_price:.2f}{' ' * max(0, width - 12 - len(f'${result.xlf_price:.2f}'))}│")  # noqa: E501, T201
    rng_str = f"{result.data_start} → {result.data_end}"
    print(f"│  {'Data Range':22}: {rng_str}{' ' * max(0, width - 10 - len(rng_str))}│")  # noqa: T201
    print(f"│  {'Last Crossover':22}: {last_cross}{' ' * max(0, width - 10 - len(last_cross))}│")  # noqa: T201
    print(f"└{border}┘")  # noqa: T201
    print(f"\nGuidance: {result.strategy_guidance}")  # noqa: T201

    if args.chart or args.show:
        path = plot_psr(show=args.show)
        if path:
            print(f"\nChart saved: {path}")  # noqa: T201


if __name__ == "__main__":
    _cli_main()
