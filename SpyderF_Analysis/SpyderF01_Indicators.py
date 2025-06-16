#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderF01_Indicators.py
Group: F (Technical Analysis)
Purpose: Technical indicators and market analysis tools

Description:
This module provides a comprehensive collection of technical indicators for
market analysis and signal generation. It includes traditional indicators
(moving averages, oscillators), volatility measures, market breadth indicators,
and custom indicators specifically designed for options trading. All indicators
are optimized for performance with NumPy/Pandas and include proper handling
of edge cases and data validation.

Author: Mohamed Talib
Created: 2025-01-27
Version: 1.4
"""

# =============================================================================
# Standard Library Imports
# =============================================================================
import warnings
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass
from enum import Enum
import math

# =============================================================================
# Third-Party Imports
# =============================================================================
import numpy as np
import pandas as pd
from scipy import stats
from scipy.signal import find_peaks
from scipy.ndimage import gaussian_filter1d

# Try to import TA-Lib, but make it optional
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False
    warnings.warn("TA-Lib not installed. Using fallback implementations for technical indicators.", ImportWarning)

# Try to import Finta as primary fallback
try:
    from finta import TA
    HAS_FINTA = True
except ImportError:
    HAS_FINTA = False
    if not HAS_TALIB:
        warnings.warn("Neither TA-Lib nor Finta installed. Using manual implementations for technical indicators.", ImportWarning)

# =============================================================================
# Local Application Imports
# =============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# =============================================================================
# Constants
# =============================================================================
# Default periods
DEFAULT_SMA_PERIOD = 20
DEFAULT_EMA_PERIOD = 12
DEFAULT_RSI_PERIOD = 14
DEFAULT_MACD_FAST = 12
DEFAULT_MACD_SLOW = 26
DEFAULT_MACD_SIGNAL = 9
DEFAULT_BB_PERIOD = 20
DEFAULT_BB_STD = 2.0
DEFAULT_ATR_PERIOD = 14
DEFAULT_ADX_PERIOD = 14

# Overbought/Oversold levels
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
STOCH_OVERSOLD = 20
STOCH_OVERBOUGHT = 80

# Market regime thresholds
TREND_THRESHOLD = 0.02  # 2% for trend identification
VOLATILITY_LOW = 0.01   # 1% daily volatility
VOLATILITY_HIGH = 0.03  # 3% daily volatility

# [Keep all your existing enumerations and data classes - they remain unchanged]
class TrendDirection(Enum):
    """Market trend directions."""
    STRONG_UP = 2
    UP = 1
    NEUTRAL = 0
    DOWN = -1
    STRONG_DOWN = -2

class MarketRegime(Enum):
    """Market regime classifications."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    QUIET = "quiet"

class SignalType(Enum):
    """Trading signal types."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    STRONG_BUY = "strong_buy"
    STRONG_SELL = "strong_sell"

class IndicatorResult:
    """
    Result from indicator calculation.
    
    Attributes:
        value: Current indicator value
        signal: Trading signal if applicable
        trend: Trend direction
        strength: Signal strength (0-1)
        metadata: Additional indicator-specific data
    """
    value: float
    signal: Optional[SignalType] = None
    trend: Optional[TrendDirection] = None
    strength: float = 0.0
    metadata: Dict[str, Any] = None

class MarketProfile:
    """
    Comprehensive market profile.
    
    Attributes:
        regime: Current market regime
        trend: Overall trend direction
        volatility: Current volatility level
        momentum: Momentum score
        breadth: Market breadth score
        volume_profile: Volume characteristics
        support_resistance: Key levels
    """
    regime: MarketRegime
    trend: TrendDirection
    volatility: float
    momentum: float
    breadth: float
    volume_profile: Dict[str, float]
    support_resistance: Dict[str, List[float]]

# =============================================================================
# Updated Technical Indicators Class
# =============================================================================
class TechnicalIndicators:
    """
    Collection of technical indicators for market analysis.
    
    This class provides a comprehensive set of technical indicators optimized
    for options trading analysis. It includes trend, momentum, volatility,
    and volume indicators with proper validation and edge case handling.
    
    Attributes:
        logger (SpyderLogger): Module logger
        cache (Dict): Indicator calculation cache
        _use_talib (bool): Whether to use TA-Lib for calculations
        _use_finta (bool): Whether to use Finta for calculations
    """
    
    def __init__(self, use_talib: bool = True, use_finta: bool = True):
        """
        Initialize technical indicators.
        
        Args:
            use_talib: Whether to use TA-Lib library
            use_finta: Whether to use Finta library
        """
        self.logger = SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        self._use_talib = use_talib and HAS_TALIB
        self._use_finta = use_finta and HAS_FINTA
        self.cache: Dict[str, Tuple[Any, int]] = {}
        
        # Log which libraries are available
        available_libs = []
        if self._use_talib:
            available_libs.append("TA-Lib")
        if self._use_finta:
            available_libs.append("Finta")
        if not available_libs:
            available_libs.append("Manual implementations")
            
        self.logger.info(f"Technical indicators initialized using: {', '.join(available_libs)}")
    
    def _check_talib(self) -> bool:
        """Check if TA-Lib is available."""
        return HAS_TALIB
        
    def _check_finta(self) -> bool:
        """Check if Finta is available."""
        return HAS_FINTA

    def _ensure_dataframe_format(self, data: Union[pd.Series, pd.DataFrame]) -> pd.DataFrame:
        """
        Ensure data is in DataFrame format for Finta compatibility.
        
        Args:
            data: Input data (Series or DataFrame)
            
        Returns:
            DataFrame with OHLCV columns
        """
        if isinstance(data, pd.Series):
            # Convert Series to DataFrame format expected by Finta
            return pd.DataFrame({
                'open': data,
                'high': data,
                'low': data,
                'close': data,
                'volume': pd.Series(index=data.index, data=1000)  # Default volume
            })
        return data

    # =========================================================================
    # Updated Indicator Methods with Finta Support
    # =========================================================================
    
    def sma(self, data: pd.Series, period: int = DEFAULT_SMA_PERIOD) -> pd.Series:
        """
        Simple Moving Average with multiple library support.
        
        Args:
            data: Price series
            period: SMA period
            
        Returns:
            SMA series
        """
        if len(data) < period:
            return pd.Series(index=data.index, dtype=float)
        
        # Try TA-Lib first
        if self._use_talib:
            try:
                return pd.Series(talib.SMA(data.values, timeperiod=period), index=data.index)
            except Exception as e:
                self.logger.warning(f"TA-Lib SMA failed: {e}, falling back to Finta")
        
        # Try Finta second
        if self._use_finta:
            try:
                df = self._ensure_dataframe_format(data)
                result = TA.SMA(df, period=period)
                if isinstance(result, pd.Series):
                    return result.reindex(data.index)
                else:
                    return pd.Series(result, index=data.index)
            except Exception as e:
                self.logger.warning(f"Finta SMA failed: {e}, falling back to manual calculation")
        
        # Manual fallback
        return data.rolling(window=period, min_periods=period).mean()
    
    def ema(self, data: pd.Series, period: int = DEFAULT_EMA_PERIOD) -> pd.Series:
        """
        Exponential Moving Average with multiple library support.
        
        Args:
            data: Price series
            period: EMA period
            
        Returns:
            EMA series
        """
        if len(data) < period:
            return pd.Series(index=data.index, dtype=float)
        
        # Try TA-Lib first
        if self._use_talib:
            try:
                return pd.Series(talib.EMA(data.values, timeperiod=period), index=data.index)
            except Exception as e:
                self.logger.warning(f"TA-Lib EMA failed: {e}, falling back to Finta")
        
        # Try Finta second
        if self._use_finta:
            try:
                df = self._ensure_dataframe_format(data)
                result = TA.EMA(df, period=period)
                if isinstance(result, pd.Series):
                    return result.reindex(data.index)
                else:
                    return pd.Series(result, index=data.index)
            except Exception as e:
                self.logger.warning(f"Finta EMA failed: {e}, falling back to manual calculation")
        
        # Manual fallback
        return data.ewm(span=period, adjust=False, min_periods=period).mean()
    
    def rsi(self, data: pd.Series, period: int = DEFAULT_RSI_PERIOD) -> pd.Series:
        """
        Relative Strength Index with multiple library support.
        
        Args:
            data: Price series
            period: RSI period
            
        Returns:
            RSI series (0-100)
        """
        if len(data) < period + 1:
            return pd.Series(index=data.index, dtype=float)
        
        # Try TA-Lib first
        if self._use_talib:
            try:
                return pd.Series(talib.RSI(data.values, timeperiod=period), index=data.index)
            except Exception as e:
                self.logger.warning(f"TA-Lib RSI failed: {e}, falling back to Finta")
        
        # Try Finta second
        if self._use_finta:
            try:
                df = self._ensure_dataframe_format(data)
                result = TA.RSI(df, period=period)
                if isinstance(result, pd.Series):
                    return result.reindex(data.index)
                else:
                    return pd.Series(result, index=data.index)
            except Exception as e:
                self.logger.warning(f"Finta RSI failed: {e}, falling back to manual calculation")
        
        # Manual fallback
        delta = data.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()
        
        # Handle division by zero
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi

    def macd(self, data: pd.Series, fast: int = DEFAULT_MACD_FAST,
             slow: int = DEFAULT_MACD_SLOW, signal: int = DEFAULT_MACD_SIGNAL) -> Dict[str, pd.Series]:
        """
        MACD with multiple library support.
        
        Args:
            data: Price series
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period
            
        Returns:
            Dictionary with 'macd', 'signal', and 'histogram' series
        """
        if len(data) < slow + signal:
            empty = pd.Series(index=data.index, dtype=float)
            return {'macd': empty, 'signal': empty, 'histogram': empty}
        
        # Try TA-Lib first
        if self._use_talib:
            try:
                macd_line, signal_line, histogram = talib.MACD(
                    data.values, fastperiod=fast, slowperiod=slow, signalperiod=signal
                )
                return {
                    'macd': pd.Series(macd_line, index=data.index),
                    'signal': pd.Series(signal_line, index=data.index),
                    'histogram': pd.Series(histogram, index=data.index)
                }
            except Exception as e:
                self.logger.warning(f"TA-Lib MACD failed: {e}, falling back to Finta")
        
        # Try Finta second
        if self._use_finta:
            try:
                df = self._ensure_dataframe_format(data)
                result = TA.MACD(df, period_fast=fast, period_slow=slow, signal=signal)
                if isinstance(result, pd.DataFrame):
                    return {
                        'macd': result['MACD'].reindex(data.index),
                        'signal': result['SIGNAL'].reindex(data.index),
                        'histogram': (result['MACD'] - result['SIGNAL']).reindex(data.index)
                    }
            except Exception as e:
                self.logger.warning(f"Finta MACD failed: {e}, falling back to manual calculation")
        
        # Manual fallback
        ema_fast = self.ema(data, fast)
        ema_slow = self.ema(data, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self.ema(macd_line.dropna(), signal)
        
        # Align indices
        signal_line = signal_line.reindex(macd_line.index)
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }

    def bollinger_bands(self, data: pd.Series, period: int = DEFAULT_BB_PERIOD,
                       std_dev: float = DEFAULT_BB_STD) -> Dict[str, pd.Series]:
        """
        Bollinger Bands with multiple library support.
        
        Args:
            data: Price series
            period: Moving average period
            std_dev: Standard deviation multiplier
            
        Returns:
            Dictionary with 'upper', 'middle', and 'lower' bands
        """
        if len(data) < period:
            empty = pd.Series(index=data.index, dtype=float)
            return {'upper': empty, 'middle': empty, 'lower': empty}
        
        # Try TA-Lib first
        if self._use_talib:
            try:
                upper, middle, lower = talib.BBANDS(
                    data.values, timeperiod=period, nbdevup=std_dev, nbdevdn=std_dev
                )
                return {
                    'upper': pd.Series(upper, index=data.index),
                    'middle': pd.Series(middle, index=data.index),
                    'lower': pd.Series(lower, index=data.index)
                }
            except Exception as e:
                self.logger.warning(f"TA-Lib BBANDS failed: {e}, falling back to Finta")
        
        # Try Finta second
        if self._use_finta:
            try:
                df = self._ensure_dataframe_format(data)
                result = TA.BBANDS(df, period=period, std_multiplier=std_dev)
                if isinstance(result, pd.DataFrame):
                    return {
                        'upper': result['BB_UPPER'].reindex(data.index),
                        'middle': result['BB_MIDDLE'].reindex(data.index),
                        'lower': result['BB_LOWER'].reindex(data.index)
                    }
            except Exception as e:
                self.logger.warning(f"Finta BBANDS failed: {e}, falling back to manual calculation")
        
        # Manual fallback
        middle = self.sma(data, period)
        std = data.rolling(window=period, min_periods=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower
        }

    # [Keep all your other existing methods unchanged - they'll use the same pattern]
    # [Include all the remaining methods from your original file]
    
    def atr(self, high: pd.Series, low: pd.Series, close: pd.Series,
            period: int = DEFAULT_ATR_PERIOD) -> pd.Series:
        """
        Average True Range with multiple library support.
        
        Args:
            high: High price series
            low: Low price series
            close: Close price series
            period: ATR period
            
        Returns:
            ATR series
        """
        if len(close) < period + 1:
            return pd.Series(index=close.index, dtype=float)
        
        # Try TA-Lib first
        if self._use_talib:
            try:
                return pd.Series(talib.ATR(high.values, low.values, close.values,
                                         timeperiod=period), index=close.index)
            except Exception as e:
                self.logger.warning(f"TA-Lib ATR failed: {e}, falling back to Finta")
        
        # Try Finta second
        if self._use_finta:
            try:
                df = pd.DataFrame({
                    'open': close,
                    'high': high,
                    'low': low,
                    'close': close,
                    'volume': pd.Series(index=close.index, data=1000)
                })
                result = TA.ATR(df, period=period)
                if isinstance(result, pd.Series):
                    return result.reindex(close.index)
                else:
                    return pd.Series(result, index=close.index)
            except Exception as e:
                self.logger.warning(f"Finta ATR failed: {e}, falling back to manual calculation")
        
        # Manual fallback
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=period, min_periods=period).mean()
        
        return atr

# [Include all your remaining methods from the original file unchanged]
# [They will continue to work with the existing fallback patterns]

# =============================================================================
# Module Functions (keep unchanged)
# =============================================================================
def calculate_pivot_points(high: float, low: float, close: float) -> Dict[str, float]:
    """Calculate pivot points for support and resistance."""
    pivot = (high + low + close) / 3
    
    r1 = 2 * pivot - low
    r2 = pivot + (high - low)
    r3 = high + 2 * (pivot - low)
    
    s1 = 2 * pivot - high
    s2 = pivot - (high - low)
    s3 = low - 2 * (high - pivot)
    
    return {
        'pivot': pivot,
        'r1': r1,
        'r2': r2,
        'r3': r3,
        's1': s1,
        's2': s2,
        's3': s3
    }

# [Keep all other existing module functions]

# =============================================================================
# Module Initialization
# =============================================================================
# Create singleton instance
_INDICATORS_INSTANCE: Optional[TechnicalIndicators] = None

def get_indicators() -> TechnicalIndicators:
    """Get singleton instance of technical indicators."""
    global _INDICATORS_INSTANCE
    if _INDICATORS_INSTANCE is None:
        _INDICATORS_INSTANCE = TechnicalIndicators()
    return _INDICATORS_INSTANCE