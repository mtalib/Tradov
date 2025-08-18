#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pure Python Technical Indicators for Spyder
No TA-Lib dependency required!
"""

import numpy as np
import pandas as pd
from typing import Union, Optional

class TechnicalIndicators:
    """Pure Python implementations of technical indicators"""
    
    @staticmethod
    def sma(prices: Union[list, np.ndarray, pd.Series], period: int) -> np.ndarray:
        """Simple Moving Average"""
        return pd.Series(prices).rolling(period).mean().values
    
    @staticmethod
    def ema(prices: Union[list, np.ndarray, pd.Series], period: int) -> np.ndarray:
        """Exponential Moving Average"""
        return pd.Series(prices).ewm(span=period, adjust=False).mean().values
    
    @staticmethod
    def rsi(prices: Union[list, np.ndarray, pd.Series], period: int = 14) -> np.ndarray:
        """Relative Strength Index"""
        prices = pd.Series(prices)
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return (100 - (100 / (1 + rs))).values
    
    @staticmethod
    def macd(prices: Union[list, np.ndarray, pd.Series], 
             fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
        """MACD (Moving Average Convergence Divergence)"""
        prices = pd.Series(prices)
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line.values,
            'signal': signal_line.values,
            'histogram': histogram.values
        }
    
    @staticmethod
    def bollinger_bands(prices: Union[list, np.ndarray, pd.Series], 
                       period: int = 20, std_dev: float = 2.0) -> dict:
        """Bollinger Bands"""
        prices = pd.Series(prices)
        sma = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        
        return {
            'upper': (sma + std_dev * std).values,
            'middle': sma.values,
            'lower': (sma - std_dev * std).values
        }
    
    @staticmethod
    def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        """Average True Range"""
        high = pd.Series(high)
        low = pd.Series(low)
        close = pd.Series(close)
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        return tr.rolling(period).mean().values

# For compatibility - replace talib references
SMA = TechnicalIndicators.sma
EMA = TechnicalIndicators.ema
RSI = TechnicalIndicators.rsi
MACD = TechnicalIndicators.macd
BBANDS = TechnicalIndicators.bollinger_bands
ATR = TechnicalIndicators.atr

print("✅ Pure Python Technical Indicators loaded - No TA-Lib needed!")
