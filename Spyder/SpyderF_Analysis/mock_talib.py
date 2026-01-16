#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderF_Analysis
Module: mock_talib.py
Purpose: Mock TALIB module - provides stub functions when TALIB is not used

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    Mock TALIB module - provides stub functions when TALIB is not used

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Union, Tuple

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

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
