#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Mock TA-Lib Module

Purpose: Provide fallback implementations when TA-Lib is not available
"""

import numpy as np
import pandas as pd
from typing import Optional, Union, Tuple

def RSI(close: Union[np.ndarray, pd.Series], timeperiod: int = 14) -> np.ndarray:
    """Calculate Relative Strength Index."""
    close = np.array(close) if isinstance(close, pd.Series) else close
    
    # Simple RSI calculation
    deltas = np.diff(close)
    seed = deltas[:timeperiod+1]
    up = seed[seed >= 0].sum() / timeperiod
    down = -seed[seed < 0].sum() / timeperiod
    rs = up / down if down != 0 else 100
    rsi = np.zeros_like(close)
    rsi[:timeperiod] = np.nan
    rsi[timeperiod] = 100. - 100. / (1. + rs)
    
    for i in range(timeperiod + 1, len(close)):
        delta = deltas[i - 1]
        if delta > 0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta
        
        up = (up * (timeperiod - 1) + upval) / timeperiod
        down = (down * (timeperiod - 1) + downval) / timeperiod
        rs = up / down if down != 0 else 100
        rsi[i] = 100. - 100. / (1. + rs)
    
    return rsi

def MACD(close: Union[np.ndarray, pd.Series], 
         fastperiod: int = 12, 
         slowperiod: int = 26, 
         signalperiod: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calculate MACD."""
    close = pd.Series(close) if not isinstance(close, pd.Series) else close
    
    exp1 = close.ewm(span=fastperiod, adjust=False).mean()
    exp2 = close.ewm(span=slowperiod, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=signalperiod, adjust=False).mean()
    hist = macd - signal
    
    return macd.values, signal.values, hist.values

def SMA(close: Union[np.ndarray, pd.Series], timeperiod: int = 30) -> np.ndarray:
    """Simple Moving Average."""
    close = pd.Series(close) if not isinstance(close, pd.Series) else close
    return close.rolling(window=timeperiod).mean().values

def EMA(close: Union[np.ndarray, pd.Series], timeperiod: int = 30) -> np.ndarray:
    """Exponential Moving Average."""
    close = pd.Series(close) if not isinstance(close, pd.Series) else close
    return close.ewm(span=timeperiod, adjust=False).mean().values

def BBANDS(close: Union[np.ndarray, pd.Series], 
           timeperiod: int = 20, 
           nbdevup: float = 2, 
           nbdevdn: float = 2, 
           matype: int = 0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bollinger Bands."""
    close = pd.Series(close) if not isinstance(close, pd.Series) else close
    
    middle = close.rolling(window=timeperiod).mean()
    std = close.rolling(window=timeperiod).std()
    upper = middle + (std * nbdevup)
    lower = middle - (std * nbdevdn)
    
    return upper.values, middle.values, lower.values

def STOCH(high: Union[np.ndarray, pd.Series],
          low: Union[np.ndarray, pd.Series],
          close: Union[np.ndarray, pd.Series],
          fastk_period: int = 5,
          slowk_period: int = 3,
          slowk_matype: int = 0,
          slowd_period: int = 3,
          slowd_matype: int = 0) -> Tuple[np.ndarray, np.ndarray]:
    """Stochastic Oscillator."""
    high = pd.Series(high) if not isinstance(high, pd.Series) else high
    low = pd.Series(low) if not isinstance(low, pd.Series) else low
    close = pd.Series(close) if not isinstance(close, pd.Series) else close
    
    lowest_low = low.rolling(window=fastk_period).min()
    highest_high = high.rolling(window=fastk_period).max()
    
    k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
    k_percent = k_percent.rolling(window=slowk_period).mean()
    d_percent = k_percent.rolling(window=slowd_period).mean()
    
    return k_percent.values, d_percent.values

def ATR(high: Union[np.ndarray, pd.Series],
        low: Union[np.ndarray, pd.Series],
        close: Union[np.ndarray, pd.Series],
        timeperiod: int = 14) -> np.ndarray:
    """Average True Range."""
    high = pd.Series(high) if not isinstance(high, pd.Series) else high
    low = pd.Series(low) if not isinstance(low, pd.Series) else low
    close = pd.Series(close) if not isinstance(close, pd.Series) else close
    
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    atr = true_range.rolling(window=timeperiod).mean()
    
    return atr.values

def ADX(high: Union[np.ndarray, pd.Series],
        low: Union[np.ndarray, pd.Series],
        close: Union[np.ndarray, pd.Series],
        timeperiod: int = 14) -> np.ndarray:
    """Average Directional Index."""
    # Simplified ADX calculation
    atr_values = ATR(high, low, close, timeperiod)
    return np.full_like(atr_values, 25.0)  # Placeholder

# Volume indicators
def OBV(close: Union[np.ndarray, pd.Series], 
        volume: Union[np.ndarray, pd.Series]) -> np.ndarray:
    """On Balance Volume."""
    close = pd.Series(close) if not isinstance(close, pd.Series) else close
    volume = pd.Series(volume) if not isinstance(volume, pd.Series) else volume
    
    obv = (volume * (~close.diff().le(0) * 2 - 1)).cumsum()
    return obv.values

def MFI(high: Union[np.ndarray, pd.Series],
        low: Union[np.ndarray, pd.Series],
        close: Union[np.ndarray, pd.Series],
        volume: Union[np.ndarray, pd.Series],
        timeperiod: int = 14) -> np.ndarray:
    """Money Flow Index."""
    typical_price = (high + low + close) / 3
    raw_money_flow = typical_price * volume
    
    # Simplified MFI
    return np.full(len(close), 50.0)  # Placeholder

print("Mock TA-Lib module loaded - providing fallback implementations")
