#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovF_Analysis
Module: TradovF20_Indicators.py
Purpose: Drop-in TA-Lib replacement — pure numpy/pandas technical indicators

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    Provides accurate implementations of the TA-Lib functions used across Tradov
    using only numpy and pandas (no compiled C extension required).  Function
    signatures are intentionally compatible with TA-Lib so callers can use this
    module as a straight swap:

        import TradovF_Analysis.TradovF20_Indicators as talib
        rsi = talib.RSI(close, timeperiod=14)

    Implemented indicators
    ──────────────────────
    SMA       Simple Moving Average
    EMA       Exponential Moving Average  (Wilder / RMA variant via span)
    RSI       Relative Strength Index     (Wilder's smoothed)
    MACD      MACD line, signal, histogram
    BBANDS    Bollinger Bands (upper, middle, lower)
    ATR       Average True Range          (Wilder's smoothed)
    STOCH     Stochastic Oscillator (%K, %D)
    ADX       Average Directional Index
    PLUS_DI   Plus Directional Indicator
    MINUS_DI  Minus Directional Indicator

    All functions accept array-like inputs (list, numpy array, or pandas Series)
    and return numpy float64 arrays.  Values in the initial "lookback" window are
    NaN, matching TA-Lib behaviour.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd


# ==============================================================================
# INTERNAL HELPERS
# ==============================================================================

def _arr(x: object) -> np.ndarray:
    """Convert any array-like to a 1-D float64 numpy array."""
    return np.asarray(x, dtype=np.float64).ravel()


def _rma(series: pd.Series, period: int) -> pd.Series:
    """
    Wilder's Running Moving Average (RMA / smoothed EMA).

    Equivalent to EMA with alpha = 1/period.  TA-Lib uses this for RSI,
    ATR, ADX, DI+, and DI-.
    """
    alpha = 1.0 / period
    return series.ewm(alpha=alpha, adjust=False).mean()


# ==============================================================================
# INDICATOR FUNCTIONS
# ==============================================================================

def SMA(close: object, timeperiod: int = 30) -> np.ndarray:
    """
    Simple Moving Average.

    Args:
        close: 1-D array of closing prices.
        timeperiod: Lookback window.

    Returns:
        numpy array of SMA values; first ``timeperiod-1`` values are NaN.
    """
    close = _arr(close)
    result = pd.Series(close).rolling(window=timeperiod, min_periods=timeperiod).mean().to_numpy()
    return result


def EMA(close: object, timeperiod: int = 30) -> np.ndarray:
    """
    Exponential Moving Average (standard EMA, alpha = 2/(n+1)).

    Args:
        close: 1-D array of closing prices.
        timeperiod: Span for EMA calculation.

    Returns:
        numpy array of EMA values; first ``timeperiod-1`` values are NaN.
    """
    close = _arr(close)
    s = pd.Series(close)
    # Seed value: first valid EMA is the SMA of the first 'timeperiod' values.
    # We achieve this by using ewm with min_periods=timeperiod.
    result = s.ewm(span=timeperiod, adjust=False, min_periods=timeperiod).mean().to_numpy()
    return result


def RSI(close: object, timeperiod: int = 14) -> np.ndarray:
    """
    Relative Strength Index using Wilder's smoothing (RMA).

    Args:
        close: 1-D array of closing prices.
        timeperiod: RSI lookback period (default 14).

    Returns:
        numpy array; first ``timeperiod`` values are NaN.
    """
    close = _arr(close)
    delta = pd.Series(close).diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = _rma(gain, timeperiod)
    avg_loss = _rma(loss, timeperiod)

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # NaN out the first timeperiod values (no complete period yet)
    result = rsi.to_numpy().copy()
    result[:timeperiod] = np.nan
    return result


def MACD(
    close: object,
    fastperiod: int = 12,
    slowperiod: int = 26,
    signalperiod: int = 9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Moving Average Convergence/Divergence.

    Args:
        close: 1-D array of closing prices.
        fastperiod: Fast EMA period (default 12).
        slowperiod: Slow EMA period (default 26).
        signalperiod: Signal line EMA period (default 9).

    Returns:
        Tuple of (macd, signal, histogram) as numpy arrays.
    """
    close = _arr(close)
    s = pd.Series(close)
    ema_fast = s.ewm(span=fastperiod, adjust=False, min_periods=fastperiod).mean()
    ema_slow = s.ewm(span=slowperiod, adjust=False, min_periods=slowperiod).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signalperiod, adjust=False, min_periods=signalperiod).mean()
    histogram = macd_line - signal_line
    return macd_line.to_numpy(), signal_line.to_numpy(), histogram.to_numpy()


def BBANDS(
    close: object,
    timeperiod: int = 20,
    nbdevup: float = 2.0,
    nbdevdn: float = 2.0,
    matype: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Bollinger Bands (upper, middle, lower).

    Args:
        close: 1-D array of closing prices.
        timeperiod: Rolling window for middle band SMA (default 20).
        nbdevup: Number of std devs above middle for upper band (default 2).
        nbdevdn: Number of std devs below middle for lower band (default 2).
        matype: Ignored (kept for TA-Lib signature compatibility).

    Returns:
        Tuple of (upper, middle, lower) as numpy arrays.
    """
    close = _arr(close)
    s = pd.Series(close)
    middle = s.rolling(window=timeperiod, min_periods=timeperiod).mean()
    std = s.rolling(window=timeperiod, min_periods=timeperiod).std(ddof=1)
    upper = middle + nbdevup * std
    lower = middle - nbdevdn * std
    return upper.to_numpy(), middle.to_numpy(), lower.to_numpy()


def ATR(
    high: object,
    low: object,
    close: object,
    timeperiod: int = 14,
) -> np.ndarray:
    """
    Average True Range using Wilder's smoothing.

    Args:
        high: 1-D array of high prices.
        low: 1-D array of low prices.
        close: 1-D array of closing prices.
        timeperiod: ATR period (default 14).

    Returns:
        numpy array; first ``timeperiod`` values are NaN.
    """
    high = _arr(high)
    low = _arr(low)
    close = _arr(close)
    prev_close = pd.Series(close).shift(1)
    tr = pd.concat(
        [
            pd.Series(high - low),
            (pd.Series(high) - prev_close).abs(),
            (pd.Series(low) - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = _rma(tr, timeperiod)
    result = atr.to_numpy().copy()
    result[:timeperiod] = np.nan
    return result


def STOCH(
    high: object,
    low: object,
    close: object,
    fastk_period: int = 5,
    slowk_period: int = 3,
    slowk_matype: int = 0,
    slowd_period: int = 3,
    slowd_matype: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Stochastic Oscillator (slow %K and %D).

    Args:
        high: 1-D array of high prices.
        low: 1-D array of low prices.
        close: 1-D array of closing prices.
        fastk_period: Raw %K lookback window (default 5).
        slowk_period: Smoothing period for slow %K (default 3).
        slowd_period: Smoothing period for slow %D (default 3).
        slowk_matype / slowd_matype: Ignored (TA-Lib compatibility).

    Returns:
        Tuple of (slowk, slowd) numpy arrays.
    """
    high = _arr(high)
    low = _arr(low)
    close = _arr(close)
    lowest_low = pd.Series(low).rolling(window=fastk_period, min_periods=fastk_period).min()
    highest_high = pd.Series(high).rolling(window=fastk_period, min_periods=fastk_period).max()
    fastk = 100.0 * (pd.Series(close) - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    slowk = fastk.rolling(window=slowk_period, min_periods=slowk_period).mean()
    slowd = slowk.rolling(window=slowd_period, min_periods=slowd_period).mean()
    return slowk.to_numpy(), slowd.to_numpy()


def _directional_indicators(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    timeperiod: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Shared helper: compute Wilder-smoothed DM+, DM-, and TR components.

    Returns:
        Tuple of (smoothed_dm_plus, smoothed_dm_minus, smoothed_tr) as Series.
    """
    h = pd.Series(high)
    lo = pd.Series(low)
    c = pd.Series(close)
    prev_h = h.shift(1)
    prev_l = lo.shift(1)
    prev_c = c.shift(1)

    up_move = h - prev_h
    down_move = prev_l - lo

    dm_plus = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    dm_minus = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = pd.concat(
        [
            h - lo,
            (h - prev_c).abs(),
            (lo - prev_c).abs(),
        ],
        axis=1,
    ).max(axis=1)

    smoothed_dm_plus = _rma(pd.Series(dm_plus), timeperiod)
    smoothed_dm_minus = _rma(pd.Series(dm_minus), timeperiod)
    smoothed_tr = _rma(tr, timeperiod)
    return smoothed_dm_plus, smoothed_dm_minus, smoothed_tr


def PLUS_DI(
    high: object,
    low: object,
    close: object,
    timeperiod: int = 14,
) -> np.ndarray:
    """
    Plus Directional Indicator (+DI).

    Args:
        high: 1-D array of high prices.
        low: 1-D array of low prices.
        close: 1-D array of closing prices.
        timeperiod: Smoothing period (default 14).

    Returns:
        numpy array; first ``timeperiod`` values are NaN.
    """
    high = _arr(high)
    low = _arr(low)
    close = _arr(close)
    sm_plus, _, sm_tr = _directional_indicators(high, low, close, timeperiod)
    di_plus = 100.0 * sm_plus / sm_tr.replace(0, np.nan)
    result = di_plus.to_numpy().copy()
    result[:timeperiod] = np.nan
    return result


def MINUS_DI(
    high: object,
    low: object,
    close: object,
    timeperiod: int = 14,
) -> np.ndarray:
    """
    Minus Directional Indicator (-DI).

    Args:
        high: 1-D array of high prices.
        low: 1-D array of low prices.
        close: 1-D array of closing prices.
        timeperiod: Smoothing period (default 14).

    Returns:
        numpy array; first ``timeperiod`` values are NaN.
    """
    high = _arr(high)
    low = _arr(low)
    close = _arr(close)
    _, sm_minus, sm_tr = _directional_indicators(high, low, close, timeperiod)
    di_minus = 100.0 * sm_minus / sm_tr.replace(0, np.nan)
    result = di_minus.to_numpy().copy()
    result[:timeperiod] = np.nan
    return result


def ADX(
    high: object,
    low: object,
    close: object,
    timeperiod: int = 14,
) -> np.ndarray:
    """
    Average Directional Index.

    Args:
        high: 1-D array of high prices.
        low: 1-D array of low prices.
        close: 1-D array of closing prices.
        timeperiod: Smoothing period (default 14).

    Returns:
        numpy array; first ``2 * timeperiod`` values are NaN.
    """
    high = _arr(high)
    low = _arr(low)
    close = _arr(close)
    sm_plus, sm_minus, sm_tr = _directional_indicators(high, low, close, timeperiod)
    di_plus = 100.0 * sm_plus / sm_tr.replace(0, np.nan)
    di_minus = 100.0 * sm_minus / sm_tr.replace(0, np.nan)
    dx = 100.0 * (di_plus - di_minus).abs() / (di_plus + di_minus).replace(0, np.nan)
    adx = _rma(dx, timeperiod)
    result = adx.to_numpy().copy()
    result[: 2 * timeperiod] = np.nan
    return result
