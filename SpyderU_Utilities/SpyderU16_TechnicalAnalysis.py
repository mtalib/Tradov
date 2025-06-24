#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Technical Analysis Wrapper
Module: SpyderU16_TechnicalAnalysis.py
Purpose: Unified technical analysis using 'ta' library
"""

import pandas as pd
import numpy as np
from ta import add_all_ta_features
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import SMAIndicator, EMAIndicator, MACD
from ta.volatility import BollingerBands
from ta.volume import VolumeSMAIndicator

class TechnicalAnalysis:
    """Technical Analysis wrapper using 'ta' library"""
    
    @staticmethod
    def add_all_indicators(df):
        """Add all technical indicators to dataframe"""
        return add_all_ta_features(
            df, open="open", high="high", low="low", 
            close="close", volume="volume", fillna=True
        )
    
    @staticmethod
    def rsi(close, window=14):
        """Relative Strength Index"""
        return RSIIndicator(close=close, window=window).rsi()
    
    @staticmethod
    def sma(close, window=20):
        """Simple Moving Average"""
        return SMAIndicator(close=close, window=window).sma_indicator()
    
    @staticmethod
    def ema(close, window=20):
        """Exponential Moving Average"""
        return EMAIndicator(close=close, window=window).ema_indicator()
    
    @staticmethod
    def macd(close, window_slow=26, window_fast=12, window_sign=9):
        """MACD Indicator"""
        macd = MACD(close=close, window_slow=window_slow, 
                   window_fast=window_fast, window_sign=window_sign)
        return {
            'macd': macd.macd(),
            'signal': macd.macd_signal(),
            'histogram': macd.macd_diff()
        }
    
    @staticmethod
    def bollinger_bands(close, window=20, window_dev=2):
        """Bollinger Bands"""
        bb = BollingerBands(close=close, window=window, window_dev=window_dev)
        return {
            'upper': bb.bollinger_hband(),
            'middle': bb.bollinger_mavg(),
            'lower': bb.bollinger_lband()
        }

# Compatibility aliases for pandas-ta style usage
def rsi(close, length=14):
    return TechnicalAnalysis.rsi(close, window=length)

def sma(close, length=20):
    return TechnicalAnalysis.sma(close, window=length)

def ema(close, length=20):
    return TechnicalAnalysis.ema(close, window=length)
