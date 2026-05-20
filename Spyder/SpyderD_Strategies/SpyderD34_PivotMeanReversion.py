#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD34_PivotMeanReversion.py
Purpose: Intraday SPY pivot-point mean-reversion strategy (0-DTE / 1-DTE).

         Uses Floor Pivot exhaustion zones (R2/R3, S2/S3) as entry triggers
         and intraday VWAP as the reversion target.  Combines four layered
         filters before any signal is emitted:
           1. ADX regime gate    — ADX < 25 → ranging day → mean reversion valid
           2. Time-of-day gate   — enabled only 10:15–14:00 ET (reversion window)
           3. NYSE TICK filter   — extreme reading confirms panic (≤-1000/≥+1000)
           4. S08 score gate     — PivotMeanReversionSignal score ≥ 60

         Option selection: ITM contracts with delta ≈ 0.60 on nearest 0-DTE or
         1-DTE expiry.  Signal metadata carries selection criteria; D31 / D32
         orchestrators handle actual chain lookup and order routing.

         Exit logic (three concurrent triggers — first hit wins):
           A. VWAP take-profit  — close 100 % when SPY crosses intraday VWAP
           B. 12-minute time stop — close if not profitable after 12 minutes
           C. Underlying price stop — close if SPY 5-min close exceeds entry
              pivot by > 0.15 % in the wrong direction

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-21 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field  # noqa: F401
from datetime import date, datetime, timedelta, timezone  # noqa: F401
from enum import Enum  # noqa: F401
from typing import Any
from zoneinfo import ZoneInfo

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# --- F20 imports: independent guards so partial F20 availability is handled ---
try:
    from Spyder.SpyderF_Analysis.SpyderF20_Indicators import ADX as _f20_adx
    _F20_ADX_AVAILABLE = True
except ImportError:  # pragma: no cover
    _F20_ADX_AVAILABLE = False
    _f20_adx = None  # type: ignore[assignment]

try:
    from Spyder.SpyderF_Analysis.SpyderF20_Indicators import RSI as _f20_rsi
    _F20_RSI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _F20_RSI_AVAILABLE = False
    _f20_rsi = None  # type: ignore[assignment]

from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (
    BaseStrategy,
    EventManager,
    PositionState,  # noqa: F401
    PositionType,  # noqa: F401
    RiskProfile,
    SignalStrength,
    SignalType,
    StrategyPosition,
    TradingSignal,
)
from Spyder.SpyderS_Signals.SpyderS08_PivotMeanReversionSignal import (
    MIN_FIRE_SCORE,
    PivotDirection,
    PivotMeanReversionSignal,
    PivotMRInputs,
    PivotMRSignal,
)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger  # noqa: F401

# VWAP is not exported by SpyderF20_Indicators; local implementation is primary.
_F20_VWAP_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
ET = ZoneInfo("America/New_York")


def _today_et() -> date:
    """Return the current trading date in Eastern Time."""
    return datetime.now(tz=ET).date()

# --- Time-of-day windows (Eastern Time) ---
TOD_ENABLE_START = (10, 15)   # 10:15 AM ET — end of opening range
TOD_ENABLE_END   = (14,  0)   # 14:00 ET  — before MOC accumulation

# --- ADX threshold ---
ADX_RANGING_MAX = 25.0        # ADX < 25 → ranging → mean-reversion enabled
ADX_PERIOD      = 14

# --- NYSE TICK extreme thresholds ---
TICK_PANIC_LONG  = -1000.0    # extreme selling → fade-support signal boosted
TICK_PANIC_SHORT = +1000.0    # extreme buying  → fade-resistance signal boosted

# --- Option Greeks targets ---
TARGET_DELTA     = 0.60       # ITM strike selection target
DELTA_TOLERANCE  = 0.10       # acceptable band around target

# --- Exit parameters ---
TIME_STOP_MINUTES  = 12       # close if not profitable after this many minutes
UNDERLYING_STOP_PCT = 0.0015  # 0.15% adverse move beyond entry pivot → stop

# --- Position ---
DEFAULT_DTE_MAX  = 1          # prefer 0-DTE; fall back to 1-DTE
SIGNAL_EXPIRY_S  = 120        # signal valid for 2 minutes

# --- Scoring ---
STRATEGY_ID = "D34_PivotMR"

# --- State management ---
TRADE_STATE_REAP_HORIZON_MIN = max(TIME_STOP_MINUTES * 3, 40)  # 40 min; catches leaked states


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class DailyPivots:
    """Floor pivot levels computed from prior session's OHLC."""
    calc_date: date
    P:  float
    R1: float
    R2: float
    R3: float
    S1: float
    S2: float
    S3: float

    def as_dict(self) -> dict[str, float]:
        return {
            "P":  self.P,
            "R1": self.R1, "R2": self.R2, "R3": self.R3,
            "S1": self.S1, "S2": self.S2, "S3": self.S3,
        }

    @staticmethod
    def from_ohlc(prev_high: float, prev_low: float, prev_close: float) -> DailyPivots:
        P  = (prev_high + prev_low + prev_close) / 3.0
        R1 = 2 * P - prev_low
        S1 = 2 * P - prev_high
        R2 = P + (prev_high - prev_low)
        S2 = P - (prev_high - prev_low)
        R3 = prev_high + 2.0 * (P - prev_low)
        S3 = prev_low  - 2.0 * (prev_high - P)
        return DailyPivots(
            calc_date=_today_et(),
            P=P, R1=R1, R2=R2, R3=R3, S1=S1, S2=S2, S3=S3,
        )


@dataclass
class IntradayBar:
    """Minimal intraday bar for indicator computation."""
    timestamp: datetime
    open:   float
    high:   float
    low:    float
    close:  float
    volume: float


@dataclass
class OpenTradeState:
    """Per-position exit tracking state."""
    position_id:   str
    direction:     PivotDirection
    entry_time:    datetime
    entry_spot:    float          # SPY price at entry
    entry_pivot:   float          # R/S level that triggered entry
    entry_pivot_name: str         # e.g. "R2"
    vwap_at_entry: float
    stop_price:    float          # adverse pivot + 0.15%
    time_limit:    datetime       # entry_time + 12 min
    # Current bar for underlying price tracking
    _five_min_bar_close: float = 0.0

    def update_last_close(self, close: float) -> None:
        """Update the most-recent bar close used by check_underlying_stop."""
        self._five_min_bar_close = close

    def check_time_stop(self, current_price: float, now: datetime) -> str | None:
        """Return exit reason if time stop triggered, else None."""
        if now >= self.time_limit:
            pnl_sign = 1 if self.direction == PivotDirection.FADE_SUPPORT else -1
            unrealised_rough = pnl_sign * (current_price - self.entry_spot)
            if unrealised_rough <= 0:
                return "time_stop_12min"
        return None

    def check_underlying_stop(self) -> str | None:
        """Return exit reason if underlying price stop triggered, else None."""
        if self._five_min_bar_close == 0.0:
            return None
        close = self._five_min_bar_close
        threshold = UNDERLYING_STOP_PCT * self.entry_pivot
        if self.direction == PivotDirection.FADE_RESISTANCE:
            # We are short-biased; stop if close > pivot + threshold
            if close > self.entry_pivot + threshold:
                return "underlying_stop_long_pivot_break"
        else:
            # We are long-biased; stop if close < pivot - threshold
            if close < self.entry_pivot - threshold:
                return "underlying_stop_below_pivot"
        return None

    def check_vwap_target(self, current_spot: float, current_vwap: float) -> str | None:
        """Return exit reason when SPY crosses the intraday VWAP (take-profit).

        Returns None (hold) when current_vwap is NaN — prevents a spurious
        take-profit trigger on sessions where VWAP cannot yet be computed.
        """
        if np.isnan(current_vwap):
            return None
        if self.direction == PivotDirection.FADE_RESISTANCE:
            # We want spot to fall toward VWAP from above
            if current_spot <= current_vwap:
                return "vwap_take_profit"
        else:
            # We want spot to rise toward VWAP from below
            if current_spot >= current_vwap:
                return "vwap_take_profit"
        return None


# ==============================================================================
# ADX COMPUTATION — delegates to SpyderF20_Indicators.ADX
# ==============================================================================

def _compute_adx(bars: list[IntradayBar], period: int = ADX_PERIOD) -> float:
    """
    Compute the Average Directional Index via SpyderF20_Indicators.ADX.

    Args:
        bars:   List of IntradayBar, oldest first.
        period: Smoothing period (default 14).

    Returns:
        ADX value (0–100), or float("nan") if insufficient data or F20 unavailable.
    """
    if len(bars) < period * 2:
        return float("nan")
    if not _F20_ADX_AVAILABLE:
        return float("nan")
    highs  = np.array([b.high  for b in bars], dtype=float)
    lows   = np.array([b.low   for b in bars], dtype=float)
    closes = np.array([b.close for b in bars], dtype=float)
    result = _f20_adx(highs, lows, closes, timeperiod=period)  # type: ignore[misc]
    last   = result[-1]
    return float(last) if not np.isnan(last) else float("nan")


def _rolling_rsi(arr: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Compute a full RSI series matching _compute_rsi's SMA-of-gains/losses formula.

    Runs in O(n) (one pass) instead of the O(n²) loop that _rsi_curl_confirms
    previously used.  The result is cached in PivotMeanReversionStrategy._rsi_cache.

    Args:
        arr:    Array of close prices, oldest first.
        period: RSI period (default 14).

    Returns:
        Float array of length len(arr); positions < period are NaN.
    """
    n = len(arr)
    result = np.full(n, float("nan"))
    if n < period + 1:
        return result
    deltas = np.diff(arr.astype(float))  # length n-1
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    for i in range(period, n):
        ag = gains[i - period:i].mean()
        al = losses[i - period:i].mean()
        if al == 0.0:
            result[i] = 100.0
        else:
            rs = ag / al
            result[i] = round(100.0 - (100.0 / (1.0 + rs)), 2)
    return result


# DEPRECATED: Use _rolling_rsi() + PivotMeanReversionStrategy._rsi_cache for
# series computation.  Retained for direct one-off scalar calls.
def _compute_rsi(closes: list[float], period: int = 14) -> float:
    """Compute RSI(period) from a sequence of close prices. Returns NaN if insufficient."""
    if len(closes) < period + 1:
        return float("nan")
    arr = np.array(closes, dtype=float)
    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains[-period:].mean()
    avg_loss = losses[-period:].mean()
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


# DEPRECATED: Use ATR from SpyderF20_Indicators.ATR when _F20_ATR_AVAILABLE.
# Retained as fallback for when F20 is unavailable.
def _compute_atr(bars: list[IntradayBar], period: int = 14) -> float:
    """Compute ATR(period). Returns NaN if insufficient bars."""
    if len(bars) < period + 1:
        return float("nan")
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i].high, bars[i].low, bars[i - 1].close  # noqa: E741
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return float("nan")
    return float(np.mean(trs[-period:]))


# DEPRECATED: VWAP is not exported by SpyderF20_Indicators (_F20_VWAP_AVAILABLE=False);
# this local implementation remains primary.
def _compute_session_vwap(bars: list[IntradayBar]) -> float:
    """Session VWAP from session-start. Returns NaN if no bars."""
    if not bars:
        return float("nan")
    cum_pv = sum((b.high + b.low + b.close) / 3.0 * b.volume for b in bars)
    cum_vol = sum(b.volume for b in bars)
    return cum_pv / cum_vol if cum_vol > 0 else float("nan")


# DEPRECATED: VWAP is not exported by SpyderF20_Indicators (_F20_VWAP_AVAILABLE=False);
# this local implementation remains primary.
def _compute_vwap_slope_bps_per_min(bars: list[IntradayBar], lookback: int = 5) -> float:
    """
    Estimate VWAP slope over the last `lookback` bars in bps/minute.

    Returns NaN if fewer bars than lookback.
    """
    if len(bars) < lookback + 1:
        return float("nan")

    def _vwap_through(idx: int) -> float:
        sub = bars[:idx + 1]
        cum_pv = sum((b.high + b.low + b.close) / 3.0 * b.volume for b in sub)
        cum_vol = sum(b.volume for b in sub)
        return cum_pv / cum_vol if cum_vol > 0 else float("nan")

    v_now  = _vwap_through(len(bars) - 1)
    v_prev = _vwap_through(len(bars) - 1 - lookback)
    if np.isnan(v_now) or np.isnan(v_prev) or v_prev == 0:
        return float("nan")
    mid_price = (v_now + v_prev) / 2.0 or 1.0
    delta_bps = (v_now - v_prev) / mid_price * 10_000
    # Assume each bar is 1 minute
    return delta_bps / lookback


# ==============================================================================
# MAIN STRATEGY CLASS
# ==============================================================================

class PivotMeanReversionStrategy(BaseStrategy):
    """
    Intraday SPY pivot-point mean-reversion strategy.

    Architectural overview:

        generate_signals(market_data) is called by the trading engine every bar.
        market_data must include columns: open, high, low, close, volume
        with a DatetimeIndex in UTC.

        External state injected per bar via update_context():
            tick     — most-recent NYSE TICK reading  (float)
            vix      — most-recent VIX last price     (float)
            regime   — F08 volatility-regime label    (str)

        Pivots are recomputed once per trading day from the previous session's
        daily OHLC (last row of market_data where date < today).

        Signal metadata (consumed by D31/D32 for chain selection):
            option_type     : "call" | "put"
            target_delta    : 0.60
            dte_max         : 1
            entry_pivot     : float  — pivot level that triggered entry
            entry_pivot_name: str    — e.g. "S2"
            stop_price      : float  — underlying stop level
            vwap_tp         : float  — current session VWAP (take-profit target)
            time_limit      : ISO-8601 datetime of time stop
            score           : int    — S08 composite score
    """

    def __init__(
        self,
        name: str,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(name, event_manager, risk_profile, config or {})

        # --- State ---
        self._bar_buffer: list[IntradayBar] = []
        self._rsi_cache: np.ndarray = np.array([], dtype=float)  # pre-computed RSI series
        self._daily_pivots: DailyPivots | None = None
        self._open_trade_states: dict[str, OpenTradeState] = {}
        self._trade_lock = threading.Lock()

        # Injected intraday context (updated each bar by the caller)
        self._ctx_tick:    float | None = None
        self._ctx_vix:     float | None = None
        self._ctx_regime:  str = ""
        self._ctx_net_gex: float | None = None

        # Scorer (stateless)
        self._scorer = PivotMeanReversionSignal()

        # Config overrides
        self._adx_max      = float(self.config.get("adx_max",    ADX_RANGING_MAX))
        self._tick_long    = float(self.config.get("tick_long",   TICK_PANIC_LONG))
        self._tick_short   = float(self.config.get("tick_short",  TICK_PANIC_SHORT))
        self._time_stop_m  = int(  self.config.get("time_stop_minutes", TIME_STOP_MINUTES))
        self._stop_pct     = float(self.config.get("underlying_stop_pct", UNDERLYING_STOP_PCT))
        self._dte_max      = int(  self.config.get("dte_max", DEFAULT_DTE_MAX))
        self._max_contracts_per_signal = int(self.config.get("max_contracts", 2))

        self.logger.info(
            "%s initialised | ADX≤%.0f | tick_long≤%.0f | tick_short≥%.0f | "
            "time_stop=%dmin | stop=%.2f%%",
            name, self._adx_max, self._tick_long, self._tick_short,
            self._time_stop_m, self._stop_pct * 100,
        )

    def _reap_stale_trade_states(self) -> None:
        """Remove open trade states older than TRADE_STATE_REAP_HORIZON_MIN.

        Protects against `_open_trade_states` growing unbounded when
        `on_position_closed` is not called (e.g. after an orchestrator restart).
        """
        now = datetime.now(tz=ET)
        horizon = timedelta(minutes=TRADE_STATE_REAP_HORIZON_MIN)
        with self._trade_lock:
            stale = [
                pid for pid, state in self._open_trade_states.items()
                if (now - state.entry_time) > horizon
            ]
            for pid in stale:
                self.logger.warning(
                    "PMR: reaping stale trade state %s (age > %dmin)",
                    pid[:8], TRADE_STATE_REAP_HORIZON_MIN,
                )
                del self._open_trade_states[pid]

    def _resolve_position_id(self, position: Any) -> str | None:
        """Resolve a strategy position identifier across runtime adapters."""
        position_id = getattr(position, "position_id", None)
        if position_id:
            return str(position_id)

        raw = getattr(position, "raw", None)
        if isinstance(raw, dict):
            for key in ("position_id", "id", "spread_id"):
                raw_position_id = raw.get(key)
                if raw_position_id:
                    return str(raw_position_id)

            strategy_positions = raw.get("strategy_positions")
            if isinstance(strategy_positions, dict):
                for strategy_position in strategy_positions.values():
                    if not isinstance(strategy_position, dict):
                        continue
                    for key in ("position_id", "id", "spread_id"):
                        raw_position_id = strategy_position.get(key)
                        if raw_position_id:
                            return str(raw_position_id)

        return None

    # ==========================================================================
    # CONTEXT INJECTION (called once per bar before generate_signals)
    # ==========================================================================

    def update_context(
        self,
        tick: float | None = None,
        vix: float | None = None,
        regime: str = "",
        net_gex: float | None = None,
    ) -> None:
        """Inject live intraday context that cannot be derived from OHLCV bars.

        Args:
            tick:    Most-recent NYSE TICK reading.
            vix:     Most-recent VIX last price.
            regime:  F08 volatility-regime label (e.g. "LOW_VOL", "TREND").
            net_gex: Net Gamma Exposure from SpyderN09 (raw dollars).  Feeds
                     the +20 GEX bonus in S08 scoring.
        """
        self._ctx_tick    = tick
        self._ctx_vix     = vix
        self._ctx_regime  = regime
        self._ctx_net_gex = net_gex

    # ==========================================================================
    # ABSTRACT METHOD IMPLEMENTATIONS
    # ==========================================================================

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """
        Generate pivot mean-reversion signals from intraday bars.

        Args:
            market_data: DataFrame with columns (open, high, low, close, volume)
                         and a timezone-aware DatetimeIndex (UTC preferred).

        Returns:
            List of TradingSignal (may be empty).
        """
        if market_data.empty or len(market_data) < 2:
            return []

        # Reap stale trade states (leak protection against missed on_position_closed)
        self._reap_stale_trade_states()

        # --- Refresh bar buffer ---
        self._refresh_bar_buffer(market_data)

        if len(self._bar_buffer) < ADX_PERIOD * 2:
            return []  # Insufficient history

        # --- Time-of-day gate ---
        if not self._is_in_trading_window():
            return []

        # --- Refresh daily pivots (once per session) ---
        self._refresh_daily_pivots(market_data)
        if self._daily_pivots is None:
            return []

        # --- Compute indicators ---
        spot   = self._bar_buffer[-1].close
        atr    = _compute_atr(self._bar_buffer)
        rsi    = _compute_rsi([b.close for b in self._bar_buffer])
        adx    = _compute_adx(self._bar_buffer)
        vwap   = _compute_session_vwap(self._bar_session_bars())
        vwap_slope = _compute_vwap_slope_bps_per_min(self._bar_session_bars())

        if np.isnan(atr) or np.isnan(rsi) or np.isnan(adx):
            return []

        # --- ADX regime gate ---
        if adx > self._adx_max:
            self.logger.debug(
                "ADX=%.1f > %.0f — trending day; mean-reversion disabled.", adx, self._adx_max
            )
            return []

        # --- Build S08 inputs ---
        s08_inputs = PivotMRInputs(
            spot_price   = spot,
            pivots       = self._daily_pivots.as_dict(),
            atr          = atr,
            rsi          = rsi,
            regime_label = self._ctx_regime,
            net_gex         = self._ctx_net_gex,
            vwap_slope      = vwap_slope if not np.isnan(vwap_slope) else None,
            max_pain_strike = None,
            # breadth_tick is intentionally None here: D34 owns the TICK gate
            # via _tick_confirms(); passing it to S08 would create a double-
            # penalty (S08 rewards |tick|<800 while D34 requires |tick|>=1000).
            breadth_tick    = None,
            vix          = self._ctx_vix,
            vix_backwardation = False,
            is_news_window    = False,
            is_edge_of_day    = self._is_edge_of_day(),
        )

        signal_out: PivotMRSignal = self._scorer.evaluate(s08_inputs)

        if not signal_out.fired:
            self.logger.debug(
                "S08 score=%d < %d; no signal (%s)",
                signal_out.score, MIN_FIRE_SCORE,
                "; ".join(signal_out.penalties[:3]),
            )
            return []

        # --- TICK confirmation gate ---
        if not self._tick_confirms(signal_out.direction):
            self.logger.debug(
                "TICK=%.0f does not confirm %s direction — signal suppressed.",
                self._ctx_tick or 0, signal_out.direction.value,
            )
            return []

        # --- RSI curl confirmation ---
        if not self._rsi_curl_confirms(signal_out.direction, rsi):
            self.logger.debug(
                "RSI=%.1f has not yet curled back — waiting for reversal confirmation.",
                rsi,
            )
            return []

        # --- Construct TradingSignal ---
        ts = self._build_signal(signal_out, spot, vwap, rsi, adx)
        self.logger.info(
            "🎯 PMR signal | dir=%s level=%s(%.2f) score=%d RSI=%.1f ADX=%.1f "
            "TICK=%s VWAP=%.2f stop=%.2f",
            signal_out.direction.value,
            signal_out.nearest_level_name,
            signal_out.nearest_level_price,
            signal_out.score, rsi, adx,
            f"{self._ctx_tick:+.0f}" if self._ctx_tick is not None else "n/a",
            vwap,
            float(ts.metadata.get("stop_price", 0.0)),
        )
        return [ts]

    def validate_signal(self, signal: TradingSignal) -> bool:
        """Accept all signals that carry required PMR metadata."""
        meta = signal.metadata or {}
        return (
            meta.get("strategy_tag") == STRATEGY_ID
            and meta.get("option_type") in ("call", "put")
            and meta.get("score", 0) >= MIN_FIRE_SCORE
            and signal.is_valid()
        )

    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Size by confidence: high confidence → 2 contracts, else 1."""
        score = signal.metadata.get("score", MIN_FIRE_SCORE)
        return 2 if score >= 80 else 1

    def should_exit_position(
        self,
        position: StrategyPosition,
        market_data: pd.DataFrame,
    ) -> tuple[bool, str]:
        """
        Check all three exit conditions for an open position.

        Called by BaseStrategy._check_exit_conditions() each bar.

        Returns:
            (True, reason) if any exit is triggered, else (False, "").
        """
        position_id = self._resolve_position_id(position)
        if not position_id:
            return False, ""

        with self._trade_lock:
            state = self._open_trade_states.get(position_id)
        if state is None:
            return False, ""

        if market_data.empty:
            return False, ""

        spot = market_data["close"].iloc[-1]
        now  = datetime.now(tz=ET)
        vwap = _compute_session_vwap(self._bar_session_bars())
        if np.isnan(vwap):
            self.logger.warning(
                "PMR: session VWAP is NaN; VWAP take-profit disabled for %s", position_id[:8]
            )

        # --- Exit A: VWAP take-profit ---
        reason = state.check_vwap_target(spot, vwap)
        if reason:
            return True, reason

        # --- Exit B: 12-minute time stop ---
        reason = state.check_time_stop(spot, now)
        if reason:
            return True, reason

        # --- Exit C: Underlying price stop (5-min close) ---
        state.update_last_close(spot)   # every bar; strategy caller may batch
        reason = state.check_underlying_stop()
        if reason:
            return True, reason

        return False, ""

    def check_exit(self, position: Any) -> Any:
        """
        ExitMonitor integration (v18 C2 fix).

        Args:
            position: _PositionView namedtuple from SpyderR14_ExitMonitor.

        Returns:
            None to hold, or dict {"action": "close", "reason": str} to exit.
        """
        position_id = self._resolve_position_id(position)
        if not position_id:
            return None

        with self._trade_lock:
            state = self._open_trade_states.get(position_id)
        if state is None:
            return None

        spot = float(position.current_price)
        now  = datetime.now(tz=ET)
        vwap = _compute_session_vwap(self._bar_session_bars())
        if np.isnan(vwap):
            self.logger.warning("PMR: session VWAP is NaN in check_exit; VWAP take-profit skipped")
        state.update_last_close(spot)

        for check in (
            state.check_vwap_target(spot, vwap),
            state.check_time_stop(spot, now),
            state.check_underlying_stop(),
        ):
            if check:
                return {"action": "close", "reason": check}

        return None

    # ==========================================================================
    # POSITION LIFECYCLE HOOKS
    # ==========================================================================

    def on_position_opened(self, position_id: str, metadata: dict[str, Any]) -> None:
        """Register trade state for a newly opened position.

        Called externally (e.g. by D31) after an order fill is confirmed.

        Args:
            position_id: UUID of the position.
            metadata:    The metadata dict from the originating TradingSignal.
        """
        try:
            now = datetime.now(tz=ET)
            entry_spot = float(metadata.get("entry_spot", 0.0))
            entry_pivot = float(metadata.get("entry_pivot", 0.0))
            direction_str = metadata.get("direction", PivotDirection.NONE.value)
            try:
                direction = PivotDirection(direction_str)
            except ValueError:
                direction = PivotDirection.NONE

            state = OpenTradeState(
                position_id      = position_id,
                direction        = direction,
                entry_time       = now,
                entry_spot       = entry_spot,
                entry_pivot      = entry_pivot,
                entry_pivot_name = metadata.get("entry_pivot_name", ""),
                vwap_at_entry    = float(metadata.get("vwap_tp", 0.0)),
                stop_price       = float(metadata.get("stop_price", 0.0)),
                time_limit       = now + timedelta(minutes=self._time_stop_m),
            )
            with self._trade_lock:
                self._open_trade_states[position_id] = state

            self.logger.info(
                "PMR trade state registered: %s | dir=%s pivot=%s(%.2f) "
                "stop=%.2f time_limit=%s",
                position_id[:8], direction.value, state.entry_pivot_name,
                entry_pivot, state.stop_price,
                state.time_limit.strftime("%H:%M:%S"),
            )
        except Exception as exc:
            self.logger.error("on_position_opened failed: %s", exc, exc_info=True)

    def on_position_closed(self, position_id: str, reason: str) -> None:
        """Clean up trade state when a position closes.

        Args:
            position_id: UUID of the closed position.
            reason:      Exit reason string.
        """
        with self._trade_lock:
            removed = self._open_trade_states.pop(position_id, None)
        if removed:
            self.logger.info(
                "PMR trade state cleared: %s | reason=%s", position_id[:8], reason
            )

    # ==========================================================================
    # PRIVATE HELPERS
    # ==========================================================================

    def _refresh_bar_buffer(self, market_data: pd.DataFrame) -> None:
        """Rebuild _bar_buffer from market_data, keeping last 200 bars.

        Also pre-computes the full RSI series and caches it in _rsi_cache so
        that _rsi_curl_confirms can do an O(1) lookup instead of O(n²) recomputation.
        """
        bars: list[IntradayBar] = []
        for ts, row in market_data.iterrows():
            dt = ts if isinstance(ts, datetime) else pd.Timestamp(ts).to_pydatetime()
            bars.append(IntradayBar(
                timestamp = dt,
                open      = float(row.get("open",  row.get("close", 0))),
                high      = float(row.get("high",  row.get("close", 0))),
                low       = float(row.get("low",   row.get("close", 0))),
                close     = float(row["close"]),
                volume    = float(row.get("volume", 1.0)),
            ))
        self._bar_buffer = bars[-200:]

        # Pre-compute RSI cache (O(n) via _rolling_rsi or F20)
        closes_arr = np.array([b.close for b in self._bar_buffer], dtype=float)
        if _F20_RSI_AVAILABLE and _f20_rsi is not None:
            try:
                rsi_result = _f20_rsi(closes_arr, timeperiod=14)  # type: ignore[misc]
                self._rsi_cache = np.asarray(rsi_result, dtype=float)
            except Exception as exc:
                self.logger.debug("F20 RSI failed, falling back to local: %s", exc)
                self._rsi_cache = _rolling_rsi(closes_arr)
        else:
            self._rsi_cache = _rolling_rsi(closes_arr)

    def _bar_session_bars(self) -> list[IntradayBar]:
        """Return bars from today's session only (for VWAP).

        v27 fix: compare against ET date, not local server tz. ``date.today()``
        returns the host wallclock date; if the host is in UTC, after 20:00 ET
        the day boundary rolls before NYSE close, dropping every session bar
        and zeroing VWAP — killing PMR signals across EOT close.
        """
        today_et = datetime.now(tz=ET).date()
        return [
            b for b in self._bar_buffer
            if (b.timestamp.astimezone(ET).date() if b.timestamp.tzinfo else b.timestamp.date())
            == today_et
        ]

    def _refresh_daily_pivots(self, market_data: pd.DataFrame) -> None:
        """Recompute daily pivots from yesterday's OHLC (once per session)."""
        today = _today_et()
        if self._daily_pivots and self._daily_pivots.calc_date == today:
            return  # Already current

        # Find the last complete prior-day row
        try:
            df = market_data.copy()
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index, utc=True)
            elif df.index.tz is None:
                df.index = df.index.tz_localize("UTC")

            df_et = df.tz_convert(ET)
            df_prior = df_et[df_et.index.date < today]  # type: ignore[attr-defined]
            if df_prior.empty:
                self.logger.debug("No prior-day data available for pivot calculation.")
                return

            # Aggregate prior session to daily OHLC
            df_daily = df_prior.resample("1D").agg({
                "high":  "max",
                "low":   "min",
                "close": "last",
            }).dropna()
            if df_daily.empty:
                return

            prev = df_daily.iloc[-1]
            self._daily_pivots = DailyPivots.from_ohlc(
                prev_high  = float(prev["high"]),
                prev_low   = float(prev["low"]),
                prev_close = float(prev["close"]),
            )
            self.logger.info(
                "Daily pivots refreshed | P=%.2f R1=%.2f R2=%.2f R3=%.2f "
                "S1=%.2f S2=%.2f S3=%.2f",
                self._daily_pivots.P,
                self._daily_pivots.R1, self._daily_pivots.R2, self._daily_pivots.R3,
                self._daily_pivots.S1, self._daily_pivots.S2, self._daily_pivots.S3,
            )
        except Exception as exc:
            self.logger.warning("Pivot refresh failed: %s", exc)

    def _is_in_trading_window(self) -> bool:
        """True if current ET time is inside the 10:15–14:00 reversion window."""
        now_et = datetime.now(tz=ET)
        now_hm = (now_et.hour, now_et.minute)
        return TOD_ENABLE_START <= now_hm < TOD_ENABLE_END

    def _is_edge_of_day(self) -> bool:
        """True if within the first 15 or last 15 minutes of the session."""
        now_et = datetime.now(tz=ET)
        now_hm = (now_et.hour, now_et.minute)
        open_15  = (9, 30 + 15)     # 9:45
        close_15 = (15, 60 - 15)    # 15:45
        return now_hm < open_15 or now_hm >= close_15

    def _tick_confirms(self, direction: PivotDirection) -> bool:
        """Check NYSE TICK confirms the intended fade direction.

        We require an extreme reading (panic in the opposing direction) to
        confirm the reversal is imminent.  If TICK is unavailable (None),
        the filter passes to avoid blocking signals during connectivity gaps.
        """
        if self._ctx_tick is None:
            return True
        if direction == PivotDirection.FADE_SUPPORT:
            # Long-biased: want extreme selling (TICK ≤ -1000)
            return self._ctx_tick <= self._tick_long
        if direction == PivotDirection.FADE_RESISTANCE:
            # Short-biased: want extreme buying (TICK ≥ +1000)
            return self._ctx_tick >= self._tick_short
        return False

    def _rsi_curl_confirms(self, direction: PivotDirection, rsi: float) -> bool:
        """
        Confirm RSI has reached an extreme AND is now curling back.

        For a fade-support (long) signal: RSI must have been ≤ 30 at some
        recent bar and is now reading > 30 (the curl-back confirmation).
        For a fade-resistance (short) signal: RSI must have reached ≥ 70 and
        is now < 70.

        Uses the pre-computed _rsi_cache (populated by _refresh_bar_buffer)
        for an O(1) lookup instead of the previous O(n²) per-bar recomputation.
        """
        n = len(self._rsi_cache)

        if n < 16:
            # Insufficient history — relax to single-bar band check
            if direction == PivotDirection.FADE_SUPPORT:
                return rsi <= 38
            if direction == PivotDirection.FADE_RESISTANCE:
                return rsi >= 62
            return False

        recent = self._rsi_cache[max(0, n - 15):]
        recent = recent[~np.isnan(recent)]

        if direction == PivotDirection.FADE_SUPPORT:
            was_oversold = bool(np.any(recent <= 30))
            return was_oversold and rsi > 30

        if direction == PivotDirection.FADE_RESISTANCE:
            was_overbought = bool(np.any(recent >= 70))
            return was_overbought and rsi < 70

        return False

    def _build_signal(
        self,
        s08: PivotMRSignal,
        spot: float,
        vwap: float,
        rsi: float,
        adx: float,
    ) -> TradingSignal:
        """Construct a TradingSignal from a fired S08 result."""
        now_et = datetime.now(tz=ET)

        # Option type: fade-resistance → put; fade-support → call
        option_type = "put" if s08.direction == PivotDirection.FADE_RESISTANCE else "call"

        # Stop price: pivot ± 0.15% in adverse direction
        pivot = s08.nearest_level_price
        if s08.direction == PivotDirection.FADE_RESISTANCE:
            stop_price = pivot * (1.0 + self._stop_pct)   # stop above R level
            signal_type = SignalType.SELL
        else:
            stop_price = pivot * (1.0 - self._stop_pct)   # stop below S level
            signal_type = SignalType.BUY

        # Strength from score
        score = s08.score
        if score >= 85:
            strength = SignalStrength.VERY_STRONG
        elif score >= 70:
            strength = SignalStrength.STRONG
        elif score >= MIN_FIRE_SCORE:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK

        expires_at = now_et + timedelta(seconds=SIGNAL_EXPIRY_S)

        meta: dict[str, Any] = {
            "strategy_tag":      STRATEGY_ID,
            "strategy_type":     "pivot_mean_reversion",
            "direction":         s08.direction.value,
            "option_type":       option_type,
            "target_delta":      TARGET_DELTA,
            "delta_tolerance":   DELTA_TOLERANCE,
            "dte_max":           self._dte_max,
            "entry_pivot":       pivot,
            "entry_pivot_name":  s08.nearest_level_name,
            "entry_spot":        spot,
            "stop_price":        stop_price,
            "vwap_tp":           vwap,            # VWAP take-profit target
            "time_limit":        (now_et + timedelta(minutes=self._time_stop_m)).isoformat(),
            "score":             score,
            "rsi":               rsi,
            "adx":               adx,
            "tick":              self._ctx_tick,
            "vix":               self._ctx_vix,
            "atr_distance":      s08.atr_distance,
            "reasons":           s08.reasons,
            "penalties":         s08.penalties,
            # Profit scaling targets:
            # Sell 50% at S1/R1, remainder at P (VWAP used intraday as proxy)
            "partial_tp_50pct_level": (
                self._daily_pivots.S1 if s08.direction == PivotDirection.FADE_SUPPORT
                else self._daily_pivots.R1
            ) if self._daily_pivots else None,
            "full_tp_level": self._daily_pivots.P if self._daily_pivots else None,
        }

        return TradingSignal(
            signal_id     = str(uuid.uuid4()),
            signal_type   = signal_type,
            symbol        = "SPY",
            strength      = strength,
            confidence    = s08.confidence,
            entry_price   = spot,
            stop_loss     = stop_price,
            take_profit   = vwap,
            position_size = self._max_contracts_per_signal,
            timestamp     = now_et,
            expires_at    = expires_at,
            metadata      = meta,
        )
