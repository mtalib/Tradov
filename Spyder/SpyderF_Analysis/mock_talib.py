"""
Mock TALIB module - provides stub functions when TALIB is not used

Since Spyder doesn't use TALIB, this module provides basic placeholder
functions that return neutral/default values.
"""

import numpy as np
from typing import Union, Tuple

def SMA(close, timeperiod=30):
    """Simple Moving Average stub"""
    return np.full_like(close, np.mean(close))

def EMA(close, timeperiod=30):
    """Exponential Moving Average stub"""
    return np.full_like(close, np.mean(close))

def RSI(close, timeperiod=14):
    """RSI stub - returns neutral 50"""
    return np.full_like(close, 50.0)

def MACD(close, fastperiod=12, slowperiod=26, signalperiod=9):
    """MACD stub - returns zeros"""
    macd = np.zeros_like(close)
    signal = np.zeros_like(close)
    hist = np.zeros_like(close)
    return macd, signal, hist

def BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0):
    """Bollinger Bands stub"""
    middle = np.full_like(close, np.mean(close))
    upper = middle * 1.02  # 2% above
    lower = middle * 0.98  # 2% below
    return upper, middle, lower

def ADX(high, low, close, timeperiod=14):
    """ADX stub"""
    return np.full_like(close, 25.0)

def ATR(high, low, close, timeperiod=14):
    """ATR stub"""
    return np.full_like(close, np.mean(close) * 0.02)
