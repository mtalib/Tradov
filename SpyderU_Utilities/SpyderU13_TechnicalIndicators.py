#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderU13_TechnicalIndicators.py
Group: U (Utilities)
Purpose: Technical indicators and market analysis tools

Description:
This module provides a comprehensive collection of technical indicators for
market analysis and signal generation. It includes traditional indicators
(moving averages, oscillators), volatility measures, market breadth indicators,
and custom indicators specifically designed for options trading. All indicators
are optimized for performance with NumPy/Pandas and include proper handling
of edge cases and data validation.

Updated to use pandas-ta instead of TA-Lib for better compatibility and easier installation.

Author: Mohamed Talib
Created: 2025-01-27
Version: 2.0
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

# Primary technical analysis library - pandas-ta
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False
    warnings.warn("pandas-ta not installed. Using fallback implementations for technical indicators.", ImportWarning)

# =============================================================================
# Local Imports
# =============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# =============================================================================
# Constants
# =============================================================================
# Default periods for indicators
DEFAULT_SMA_PERIOD = 20
DEFAULT_EMA_PERIOD = 12
DEFAULT_RSI_PERIOD = 14
DEFAULT_MACD_FAST = 12
DEFAULT_MACD_SLOW = 26
DEFAULT_MACD_SIGNAL = 9
DEFAULT_ATR_PERIOD = 14
DEFAULT_ADX_PERIOD = 14
DEFAULT_BOLLINGER_PERIOD = 20
DEFAULT_BOLLINGER_STD = 2
DEFAULT_STOCH_PERIOD = 14
DEFAULT_STOCH_SMOOTH_K = 3
DEFAULT_STOCH_SMOOTH_D = 3

# Market regime thresholds
VOLATILITY_LOW_THRESHOLD = 0.10
VOLATILITY_HIGH_THRESHOLD = 0.25
TREND_STRENGTH_THRESHOLD = 25
VOLUME_SPIKE_THRESHOLD = 2.0

# =============================================================================
# Enums
# =============================================================================
class SignalType(Enum):
    """Trading signal types."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    STRONG_BUY = "STRONG_BUY"
    STRONG_SELL = "STRONG_SELL"

class TrendDirection(Enum):
    """Market trend directions."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"

class MarketRegime(Enum):
    """Market regime classifications."""
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGE_BOUND = "RANGE_BOUND"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"

# =============================================================================
# Data Classes
# =============================================================================
@dataclass
class IndicatorResult:
    """
    Standard result format for all indicators.
    
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

@dataclass
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
# Technical Indicators Class
# =============================================================================
class TechnicalIndicators:
    """
    Collection of technical indicators for market analysis using pandas-ta.
    
    This class provides a comprehensive set of technical indicators optimized
    for options trading analysis. It includes trend, momentum, volatility,
    and volume indicators with proper validation and edge case handling.
    
    Attributes:
        logger (SpyderLogger): Module logger
        cache (Dict): Indicator calculation cache
        _use_pandas_ta (bool): Whether to use pandas-ta for calculations
    """
    
    def __init__(self, use_pandas_ta: bool = True):
        """
        Initialize technical indicators.
        
        Args:
            use_pandas_ta: Whether to use pandas-ta library
        """
        self.logger = SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        self._use_pandas_ta = use_pandas_ta and HAS_PANDAS_TA
        self.cache: Dict[str, Tuple[Any, int]] = {}
        
        # Configure pandas-ta if available
        if self._use_pandas_ta:
            # Set pandas-ta to use all cores for faster computation
            ta.set_config(multiprocess=True)
            self.logger.info("Technical indicators initialized using pandas-ta")
        else:
            self.logger.info("Technical indicators initialized using manual implementations")
    
    # =========================================================================
    # Trend Indicators
    # =========================================================================
    
    def sma(self, data: pd.Series, period: int = DEFAULT_SMA_PERIOD) -> pd.Series:
        """
        Simple Moving Average.
        
        Args:
            data: Price series
            period: SMA period
            
        Returns:
            SMA series
        """
        if len(data) < period:
            return pd.Series(index=data.index, dtype=float)
        
        if self._use_pandas_ta:
            try:
                result = ta.sma(data, length=period)
                return result if result is not None else data.rolling(window=period).mean()
            except Exception as e:
                self.logger.warning(f"pandas-ta SMA failed: {e}, using fallback")
        
        # Fallback to pandas rolling
        return data.rolling(window=period, min_periods=period).mean()
    
    def ema(self, data: pd.Series, period: int = DEFAULT_EMA_PERIOD) -> pd.Series:
        """
        Exponential Moving Average.
        
        Args:
            data: Price series
            period: EMA period
            
        Returns:
            EMA series
        """
        if len(data) < period:
            return pd.Series(index=data.index, dtype=float)
        
        if self._use_pandas_ta:
            try:
                result = ta.ema(data, length=period)
                return result if result is not None else data.ewm(span=period, adjust=False).mean()
            except Exception as e:
                self.logger.warning(f"pandas-ta EMA failed: {e}, using fallback")
        
        # Fallback to pandas ewm
        return data.ewm(span=period, adjust=False, min_periods=period).mean()
    
    def wma(self, data: pd.Series, period: int = DEFAULT_SMA_PERIOD) -> pd.Series:
        """
        Weighted Moving Average.
        
        Args:
            data: Price series
            period: WMA period
            
        Returns:
            WMA series
        """
        if len(data) < period:
            return pd.Series(index=data.index, dtype=float)
        
        if self._use_pandas_ta:
            try:
                result = ta.wma(data, length=period)
                return result if result is not None else self._manual_wma(data, period)
            except Exception as e:
                self.logger.warning(f"pandas-ta WMA failed: {e}, using fallback")
        
        return self._manual_wma(data, period)
    
    def _manual_wma(self, data: pd.Series, period: int) -> pd.Series:
        """Manual weighted moving average calculation."""
        weights = np.arange(1, period + 1)
        return data.rolling(period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)
    
    def vwap(self, high: pd.Series, low: pd.Series, close: pd.Series, 
             volume: pd.Series) -> pd.Series:
        """
        Volume Weighted Average Price.
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            volume: Volume data
            
        Returns:
            VWAP series
        """
        if self._use_pandas_ta:
            try:
                df = pd.DataFrame({
                    'high': high,
                    'low': low,
                    'close': close,
                    'volume': volume
                })
                result = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
                return result if result is not None else self._manual_vwap(high, low, close, volume)
            except Exception as e:
                self.logger.warning(f"pandas-ta VWAP failed: {e}, using fallback")
        
        return self._manual_vwap(high, low, close, volume)
    
    def _manual_vwap(self, high: pd.Series, low: pd.Series, close: pd.Series, 
                     volume: pd.Series) -> pd.Series:
        """Manual VWAP calculation."""
        typical_price = (high + low + close) / 3
        return (typical_price * volume).cumsum() / volume.cumsum()
    
    # =========================================================================
    # Momentum Indicators
    # =========================================================================
    
    def rsi(self, data: pd.Series, period: int = DEFAULT_RSI_PERIOD) -> pd.Series:
        """
        Relative Strength Index.
        
        Args:
            data: Price series
            period: RSI period
            
        Returns:
            RSI series
        """
        if len(data) < period + 1:
            return pd.Series(index=data.index, dtype=float)
        
        if self._use_pandas_ta:
            try:
                result = ta.rsi(data, length=period)
                return result if result is not None else self._manual_rsi(data, period)
            except Exception as e:
                self.logger.warning(f"pandas-ta RSI failed: {e}, using fallback")
        
        return self._manual_rsi(data, period)
    
    def _manual_rsi(self, data: pd.Series, period: int) -> pd.Series:
        """Manual RSI calculation."""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def macd(self, data: pd.Series, fast: int = DEFAULT_MACD_FAST,
             slow: int = DEFAULT_MACD_SLOW, signal: int = DEFAULT_MACD_SIGNAL) -> Dict[str, pd.Series]:
        """
        MACD (Moving Average Convergence Divergence).
        
        Args:
            data: Price series
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line EMA period
            
        Returns:
            Dictionary with 'macd', 'signal', and 'histogram'
        """
        if len(data) < slow + signal:
            empty = pd.Series(index=data.index, dtype=float)
            return {'macd': empty, 'signal': empty, 'histogram': empty}
        
        if self._use_pandas_ta:
            try:
                result = ta.macd(data, fast=fast, slow=slow, signal=signal)
                if result is not None and not result.empty:
                    return {
                        'macd': result[f'MACD_{fast}_{slow}_{signal}'],
                        'signal': result[f'MACDs_{fast}_{slow}_{signal}'],
                        'histogram': result[f'MACDh_{fast}_{slow}_{signal}']
                    }
            except Exception as e:
                self.logger.warning(f"pandas-ta MACD failed: {e}, using fallback")
        
        # Manual fallback
        ema_fast = self.ema(data, fast)
        ema_slow = self.ema(data, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self.ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    def stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series,
                   period: int = DEFAULT_STOCH_PERIOD,
                   smooth_k: int = DEFAULT_STOCH_SMOOTH_K,
                   smooth_d: int = DEFAULT_STOCH_SMOOTH_D) -> Dict[str, pd.Series]:
        """
        Stochastic Oscillator.
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: Look-back period
            smooth_k: K line smoothing period
            smooth_d: D line smoothing period
            
        Returns:
            Dictionary with '%K' and '%D' lines
        """
        if len(close) < period + smooth_k + smooth_d:
            empty = pd.Series(index=close.index, dtype=float)
            return {'%K': empty, '%D': empty}
        
        if self._use_pandas_ta:
            try:
                result = ta.stoch(high, low, close, k=period, d=smooth_d, smooth_k=smooth_k)
                if result is not None and not result.empty:
                    return {
                        '%K': result[f'STOCHk_{period}_{smooth_d}_{smooth_k}'],
                        '%D': result[f'STOCHd_{period}_{smooth_d}_{smooth_k}']
                    }
            except Exception as e:
                self.logger.warning(f"pandas-ta Stochastic failed: {e}, using fallback")
        
        # Manual fallback
        lowest_low = low.rolling(window=period).min()
        highest_high = high.rolling(window=period).max()
        
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        k_percent = k_percent.rolling(window=smooth_k).mean()
        d_percent = k_percent.rolling(window=smooth_d).mean()
        
        return {'%K': k_percent, '%D': d_percent}
    
    def momentum(self, data: pd.Series, period: int = 10) -> pd.Series:
        """
        Momentum indicator.
        
        Args:
            data: Price series
            period: Look-back period
            
        Returns:
            Momentum series
        """
        if self._use_pandas_ta:
            try:
                result = ta.mom(data, length=period)
                return result if result is not None else data.diff(period)
            except Exception as e:
                self.logger.warning(f"pandas-ta Momentum failed: {e}, using fallback")
        
        return data.diff(period)
    
    def roc(self, data: pd.Series, period: int = 10) -> pd.Series:
        """
        Rate of Change.
        
        Args:
            data: Price series
            period: Look-back period
            
        Returns:
            ROC series (percentage)
        """
        if self._use_pandas_ta:
            try:
                result = ta.roc(data, length=period)
                return result if result is not None else ((data - data.shift(period)) / data.shift(period)) * 100
            except Exception as e:
                self.logger.warning(f"pandas-ta ROC failed: {e}, using fallback")
        
        return ((data - data.shift(period)) / data.shift(period)) * 100
    
    # =========================================================================
    # Volatility Indicators
    # =========================================================================
    
    def bollinger_bands(self, data: pd.Series, period: int = DEFAULT_BOLLINGER_PERIOD,
                       std_dev: float = DEFAULT_BOLLINGER_STD) -> Dict[str, pd.Series]:
        """
        Bollinger Bands.
        
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
        
        if self._use_pandas_ta:
            try:
                result = ta.bbands(data, length=period, std=std_dev)
                if result is not None and not result.empty:
                    cols = result.columns
                    return {
                        'lower': result[cols[0]],  # BBL
                        'middle': result[cols[1]],  # BBM
                        'upper': result[cols[2]],   # BBU
                    }
            except Exception as e:
                self.logger.warning(f"pandas-ta Bollinger Bands failed: {e}, using fallback")
        
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
    
    def atr(self, high: pd.Series, low: pd.Series, close: pd.Series,
            period: int = DEFAULT_ATR_PERIOD) -> pd.Series:
        """
        Average True Range.
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ATR period
            
        Returns:
            ATR series
        """
        if len(close) < period + 1:
            return pd.Series(index=close.index, dtype=float)
        
        if self._use_pandas_ta:
            try:
                result = ta.atr(high, low, close, length=period)
                return result if result is not None else self._manual_atr(high, low, close, period)
            except Exception as e:
                self.logger.warning(f"pandas-ta ATR failed: {e}, using fallback")
        
        return self._manual_atr(high, low, close, period)
    
    def _manual_atr(self, high: pd.Series, low: pd.Series, close: pd.Series,
                    period: int) -> pd.Series:
        """Manual ATR calculation."""
        high_low = high - low
        high_close = (high - close.shift()).abs()
        low_close = (low - close.shift()).abs()
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return true_range.rolling(window=period).mean()
    
    def keltner_channels(self, high: pd.Series, low: pd.Series, close: pd.Series,
                        period: int = 20, atr_period: int = 10,
                        multiplier: float = 2.0) -> Dict[str, pd.Series]:
        """
        Keltner Channels.
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: EMA period for middle line
            atr_period: ATR period
            multiplier: ATR multiplier for bands
            
        Returns:
            Dictionary with 'upper', 'middle', and 'lower' channels
        """
        if self._use_pandas_ta:
            try:
                result = ta.kc(high, low, close, length=period, scalar=multiplier)
                if result is not None and not result.empty:
                    cols = result.columns
                    return {
                        'lower': result[cols[0]],
                        'middle': result[cols[1]],
                        'upper': result[cols[2]]
                    }
            except Exception as e:
                self.logger.warning(f"pandas-ta Keltner Channels failed: {e}, using fallback")
        
        # Manual fallback
        middle = self.ema(close, period)
        atr = self.atr(high, low, close, atr_period)
        upper = middle + (atr * multiplier)
        lower = middle - (atr * multiplier)
        
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower
        }
    
    def donchian_channels(self, high: pd.Series, low: pd.Series,
                         period: int = 20) -> Dict[str, pd.Series]:
        """
        Donchian Channels.
        
        Args:
            high: High prices
            low: Low prices
            period: Look-back period
            
        Returns:
            Dictionary with 'upper', 'middle', and 'lower' channels
        """
        if self._use_pandas_ta:
            try:
                result = ta.donchian(high, low, lower_length=period, upper_length=period)
                if result is not None and not result.empty:
                    cols = result.columns
                    return {
                        'lower': result[cols[0]],
                        'middle': result[cols[1]],
                        'upper': result[cols[2]]
                    }
            except Exception as e:
                self.logger.warning(f"pandas-ta Donchian Channels failed: {e}, using fallback")
        
        # Manual fallback
        upper = high.rolling(window=period).max()
        lower = low.rolling(window=period).min()
        middle = (upper + lower) / 2
        
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower
        }
    
    def historical_volatility(self, data: pd.Series, period: int = 20,
                            annualization_factor: int = 252) -> pd.Series:
        """
        Historical volatility (realized volatility).
        
        Args:
            data: Price series
            period: Look-back period
            annualization_factor: Trading days per year
            
        Returns:
            Annualized volatility series
        """
        returns = data.pct_change()
        return returns.rolling(window=period).std() * np.sqrt(annualization_factor)
    
    # =========================================================================
    # Volume Indicators
    # =========================================================================
    
    def obv(self, close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        On Balance Volume.
        
        Args:
            close: Close prices
            volume: Volume data
            
        Returns:
            OBV series
        """
        if self._use_pandas_ta:
            try:
                result = ta.obv(close, volume)
                return result if result is not None else self._manual_obv(close, volume)
            except Exception as e:
                self.logger.warning(f"pandas-ta OBV failed: {e}, using fallback")
        
        return self._manual_obv(close, volume)
    
    def _manual_obv(self, close: pd.Series, volume: pd.Series) -> pd.Series:
        """Manual OBV calculation."""
        return (volume * (~close.diff().le(0) * 2 - 1)).cumsum()
    
    def adl(self, high: pd.Series, low: pd.Series, close: pd.Series,
            volume: pd.Series) -> pd.Series:
        """
        Accumulation/Distribution Line.
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            volume: Volume data
            
        Returns:
            ADL series
        """
        if self._use_pandas_ta:
            try:
                result = ta.ad(high, low, close, volume)
                return result if result is not None else self._manual_adl(high, low, close, volume)
            except Exception as e:
                self.logger.warning(f"pandas-ta ADL failed: {e}, using fallback")
        
        return self._manual_adl(high, low, close, volume)
    
    def _manual_adl(self, high: pd.Series, low: pd.Series, close: pd.Series,
                    volume: pd.Series) -> pd.Series:
        """Manual ADL calculation."""
        clv = ((close - low) - (high - close)) / (high - low)
        clv = clv.fillna(0)
        return (clv * volume).cumsum()
    
    def mfi(self, high: pd.Series, low: pd.Series, close: pd.Series,
            volume: pd.Series, period: int = 14) -> pd.Series:
        """
        Money Flow Index.
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            volume: Volume data
            period: MFI period
            
        Returns:
            MFI series
        """
        if self._use_pandas_ta:
            try:
                result = ta.mfi(high, low, close, volume, length=period)
                return result if result is not None else self._manual_mfi(high, low, close, volume, period)
            except Exception as e:
                self.logger.warning(f"pandas-ta MFI failed: {e}, using fallback")
        
        return self._manual_mfi(high, low, close, volume, period)
    
    def _manual_mfi(self, high: pd.Series, low: pd.Series, close: pd.Series,
                    volume: pd.Series, period: int) -> pd.Series:
        """Manual MFI calculation."""
        typical_price = (high + low + close) / 3
        money_flow = typical_price * volume
        
        positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0)
        negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0)
        
        positive_sum = positive_flow.rolling(window=period).sum()
        negative_sum = negative_flow.rolling(window=period).sum()
        
        mfi = 100 - (100 / (1 + positive_sum / negative_sum))
        return mfi
    
    def vwma(self, close: pd.Series, volume: pd.Series, period: int = 20) -> pd.Series:
        """
        Volume Weighted Moving Average.
        
        Args:
            close: Close prices
            volume: Volume data
            period: VWMA period
            
        Returns:
            VWMA series
        """
        if self._use_pandas_ta:
            try:
                result = ta.vwma(close, volume, length=period)
                return result if result is not None else self._manual_vwma(close, volume, period)
            except Exception as e:
                self.logger.warning(f"pandas-ta VWMA failed: {e}, using fallback")
        
        return self._manual_vwma(close, volume, period)
    
    def _manual_vwma(self, close: pd.Series, volume: pd.Series, period: int) -> pd.Series:
        """Manual VWMA calculation."""
        return (close * volume).rolling(window=period).sum() / volume.rolling(window=period).sum()
    
    # =========================================================================
    # Trend Strength Indicators
    # =========================================================================
    
    def adx(self, high: pd.Series, low: pd.Series, close: pd.Series,
            period: int = DEFAULT_ADX_PERIOD) -> Dict[str, pd.Series]:
        """
        Average Directional Index.
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ADX period
            
        Returns:
            Dictionary with 'ADX', '+DI', and '-DI'
        """
        if self._use_pandas_ta:
            try:
                result = ta.adx(high, low, close, length=period)
                if result is not None and not result.empty:
                    cols = result.columns
                    return {
                        'ADX': result[cols[0]],
                        '+DI': result[cols[1]],
                        '-DI': result[cols[2]]
                    }
            except Exception as e:
                self.logger.warning(f"pandas-ta ADX failed: {e}, using fallback")
        
        # Manual fallback is complex, return empty for now
        empty = pd.Series(index=close.index, dtype=float)
        return {'ADX': empty, '+DI': empty, '-DI': empty}
    
    def aroon(self, high: pd.Series, low: pd.Series, period: int = 25) -> Dict[str, pd.Series]:
        """
        Aroon Indicator.
        
        Args:
            high: High prices
            low: Low prices
            period: Aroon period
            
        Returns:
            Dictionary with 'up', 'down', and 'oscillator'
        """
        if self._use_pandas_ta:
            try:
                result = ta.aroon(high, low, length=period)
                if result is not None and not result.empty:
                    cols = result.columns
                    aroon_up = result[cols[0]]
                    aroon_down = result[cols[1]]
                    aroon_osc = result[cols[2]] if len(cols) > 2 else aroon_up - aroon_down
                    return {
                        'up': aroon_up,
                        'down': aroon_down,
                        'oscillator': aroon_osc
                    }
            except Exception as e:
                self.logger.warning(f"pandas-ta Aroon failed: {e}, using fallback")
        
        # Manual fallback
        aroon_up = high.rolling(period + 1).apply(lambda x: float(np.argmax(x)) / period * 100)
        aroon_down = low.rolling(period + 1).apply(lambda x: float(np.argmin(x)) / period * 100)
        
        return {
            'up': aroon_up,
            'down': aroon_down,
            'oscillator': aroon_up - aroon_down
        }
    
    def cci(self, high: pd.Series, low: pd.Series, close: pd.Series,
            period: int = 20) -> pd.Series:
        """
        Commodity Channel Index.
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: CCI period
            
        Returns:
            CCI series
        """
        if self._use_pandas_ta:
            try:
                result = ta.cci(high, low, close, length=period)
                return result if result is not None else self._manual_cci(high, low, close, period)
            except Exception as e:
                self.logger.warning(f"pandas-ta CCI failed: {e}, using fallback")
        
        return self._manual_cci(high, low, close, period)
    
    def _manual_cci(self, high: pd.Series, low: pd.Series, close: pd.Series,
                    period: int) -> pd.Series:
        """Manual CCI calculation."""
        typical_price = (high + low + close) / 3
        sma = typical_price.rolling(window=period).mean()
        mad = typical_price.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())
        return (typical_price - sma) / (0.015 * mad)
    
    # =========================================================================
    # Pattern Recognition
    # =========================================================================
    
    def find_support_resistance(self, data: pd.Series, window: int = 20,
                               min_touches: int = 2) -> Dict[str, List[float]]:
        """
        Find support and resistance levels.
        
        Args:
            data: Price series
            window: Look-back window for finding levels
            min_touches: Minimum touches to confirm level
            
        Returns:
            Dictionary with 'support' and 'resistance' levels
        """
        # Find peaks and troughs
        peaks, _ = find_peaks(data.values, distance=window)
        troughs, _ = find_peaks(-data.values, distance=window)
        
        # Get price levels
        resistance_levels = data.iloc[peaks].values if len(peaks) > 0 else []
        support_levels = data.iloc[troughs].values if len(troughs) > 0 else []
        
        # Cluster nearby levels
        def cluster_levels(levels, tolerance=0.01):
            if len(levels) == 0:
                return []
            
            clustered = []
            levels = sorted(levels)
            current_cluster = [levels[0]]
            
            for level in levels[1:]:
                if level <= current_cluster[-1] * (1 + tolerance):
                    current_cluster.append(level)
                else:
                    if len(current_cluster) >= min_touches:
                        clustered.append(np.mean(current_cluster))
                    current_cluster = [level]
            
            if len(current_cluster) >= min_touches:
                clustered.append(np.mean(current_cluster))
            
            return clustered
        
        return {
            'support': cluster_levels(support_levels),
            'resistance': cluster_levels(resistance_levels)
        }
    
    def detect_divergence(self, price: pd.Series, indicator: pd.Series,
                         window: int = 14) -> pd.Series:
        """
        Detect divergences between price and indicator.
        
        Args:
            price: Price series
            indicator: Indicator series
            window: Look-back window
            
        Returns:
            Series with divergence signals (1: bullish, -1: bearish, 0: none)
        """
        # Find peaks and troughs in price
        price_peaks, _ = find_peaks(price.values, distance=window)
        price_troughs, _ = find_peaks(-price.values, distance=window)
        
        # Find peaks and troughs in indicator
        ind_peaks, _ = find_peaks(indicator.values, distance=window)
        ind_troughs, _ = find_peaks(-indicator.values, distance=window)
        
        divergence = pd.Series(0, index=price.index)
        
        # Check for bearish divergence (price higher high, indicator lower high)
        for i in range(1, len(price_peaks)):
            if (price.iloc[price_peaks[i]] > price.iloc[price_peaks[i-1]] and
                indicator.iloc[price_peaks[i]] < indicator.iloc[price_peaks[i-1]]):
                divergence.iloc[price_peaks[i]] = -1
        
        # Check for bullish divergence (price lower low, indicator higher low)
        for i in range(1, len(price_troughs)):
            if (price.iloc[price_troughs[i]] < price.iloc[price_troughs[i-1]] and
                indicator.iloc[price_troughs[i]] > indicator.iloc[price_troughs[i-1]]):
                divergence.iloc[price_troughs[i]] = 1
        
        return divergence
    
    # =========================================================================
    # Market Profile Analysis
    # =========================================================================
    
    def calculate_market_profile(self, high: pd.Series, low: pd.Series,
                                close: pd.Series, volume: pd.Series,
                                lookback: int = 20) -> MarketProfile:
        """
        Calculate comprehensive market profile.
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            volume: Volume data
            lookback: Analysis period
            
        Returns:
            MarketProfile object
        """
        # Calculate trend metrics
        sma20 = self.sma(close, 20)
        sma50 = self.sma(close, 50)
        
        # Determine trend
        if close.iloc[-1] > sma20.iloc[-1] > sma50.iloc[-1]:
            trend = TrendDirection.BULLISH
        elif close.iloc[-1] < sma20.iloc[-1] < sma50.iloc[-1]:
            trend = TrendDirection.BEARISH
        else:
            trend = TrendDirection.NEUTRAL
        
        # Calculate volatility
        volatility = self.historical_volatility(close, lookback).iloc[-1]
        
        # Calculate momentum
        rsi = self.rsi(close, 14).iloc[-1]
        momentum = (rsi - 50) / 50  # Normalize to -1 to 1
        
        # Market breadth (simplified)
        advances = (close > close.shift(1)).sum()
        declines = (close < close.shift(1)).sum()
        breadth = (advances - declines) / (advances + declines) if (advances + declines) > 0 else 0
        
        # Volume profile
        avg_volume = volume.rolling(lookback).mean().iloc[-1]
        volume_ratio = volume.iloc[-1] / avg_volume if avg_volume > 0 else 1
        
        volume_profile = {
            'current': float(volume.iloc[-1]),
            'average': float(avg_volume),
            'ratio': float(volume_ratio),
            'trend': 'high' if volume_ratio > 1.5 else 'normal' if volume_ratio > 0.5 else 'low'
        }
        
        # Support and resistance
        levels = self.find_support_resistance(close, lookback)
        
        # Determine regime
        if volatility > VOLATILITY_HIGH_THRESHOLD:
            regime = MarketRegime.HIGH_VOLATILITY
        elif volatility < VOLATILITY_LOW_THRESHOLD:
            regime = MarketRegime.LOW_VOLATILITY
        elif trend == TrendDirection.BULLISH:
            regime = MarketRegime.TRENDING_UP
        elif trend == TrendDirection.BEARISH:
            regime = MarketRegime.TRENDING_DOWN
        else:
            regime = MarketRegime.RANGE_BOUND
        
        return MarketProfile(
            regime=regime,
            trend=trend,
            volatility=float(volatility),
            momentum=float(momentum),
            breadth=float(breadth),
            volume_profile=volume_profile,
            support_resistance=levels
        )
    
    # =========================================================================
    # Signal Generation
    # =========================================================================
    
    def generate_signal(self, data: pd.DataFrame, lookback: int = 20) -> IndicatorResult:
        """
        Generate comprehensive trading signal.
        
        Args:
            data: DataFrame with OHLCV data
            lookback: Analysis period
            
        Returns:
            IndicatorResult with signal and metadata
        """
        # Calculate key indicators
        close = data['close']
        high = data['high']
        low = data['low']
        volume = data['volume']
        
        # Trend indicators
        sma20 = self.sma(close, 20)
        sma50 = self.sma(close, 50)
        ema12 = self.ema(close, 12)
        
        # Momentum indicators
        rsi = self.rsi(close, 14)
        macd_data = self.macd(close)
        
        # Current values
        current_price = close.iloc[-1]
        current_rsi = rsi.iloc[-1]
        current_macd = macd_data['macd'].iloc[-1]
        current_signal = macd_data['signal'].iloc[-1]
        
        # Determine signal
        bullish_signals = 0
        bearish_signals = 0
        
        # Trend signals
        if current_price > sma20.iloc[-1] > sma50.iloc[-1]:
            bullish_signals += 1
        elif current_price < sma20.iloc[-1] < sma50.iloc[-1]:
            bearish_signals += 1
        
        # RSI signals
        if current_rsi < 30:
            bullish_signals += 1
        elif current_rsi > 70:
            bearish_signals += 1
        
        # MACD signals
        if current_macd > current_signal and macd_data['histogram'].iloc[-1] > 0:
            bullish_signals += 1
        elif current_macd < current_signal and macd_data['histogram'].iloc[-1] < 0:
            bearish_signals += 1
        
        # Generate final signal
        if bullish_signals >= 2:
            signal = SignalType.BUY
            if bullish_signals == 3:
                signal = SignalType.STRONG_BUY
        elif bearish_signals >= 2:
            signal = SignalType.SELL
            if bearish_signals == 3:
                signal = SignalType.STRONG_SELL
        else:
            signal = SignalType.HOLD
        
        # Calculate signal strength
        total_signals = bullish_signals + bearish_signals
        strength = total_signals / 6.0  # Normalize to 0-1
        
        # Metadata
        metadata = {
            'price': float(current_price),
            'sma20': float(sma20.iloc[-1]),
            'sma50': float(sma50.iloc[-1]),
            'rsi': float(current_rsi),
            'macd': float(current_macd),
            'macd_signal': float(current_signal),
            'bullish_signals': bullish_signals,
            'bearish_signals': bearish_signals
        }
        
        return IndicatorResult(
            value=float(current_price),
            signal=signal,
            trend=TrendDirection.BULLISH if bullish_signals > bearish_signals else TrendDirection.BEARISH,
            strength=strength,
            metadata=metadata
        )
    
    # =========================================================================
    # Options-Specific Indicators
    # =========================================================================
    
    def calculate_iv_rank(self, iv_series: pd.Series, period: int = 252) -> float:
        """
        Calculate Implied Volatility Rank.
        
        Args:
            iv_series: Historical IV series
            period: Look-back period (default 252 days)
            
        Returns:
            IV Rank (0-100)
        """
        if len(iv_series) < period:
            return 50.0  # Default to middle if insufficient data
        
        current_iv = iv_series.iloc[-1]
        min_iv = iv_series.iloc[-period:].min()
        max_iv = iv_series.iloc[-period:].max()
        
        if max_iv == min_iv:
            return 50.0
        
        return ((current_iv - min_iv) / (max_iv - min_iv)) * 100
    
    def calculate_iv_percentile(self, iv_series: pd.Series, period: int = 252) -> float:
        """
        Calculate Implied Volatility Percentile.
        
        Args:
            iv_series: Historical IV series
            period: Look-back period (default 252 days)
            
        Returns:
            IV Percentile (0-100)
        """
        if len(iv_series) < period:
            return 50.0  # Default to middle if insufficient data
        
        current_iv = iv_series.iloc[-1]
        lookback_data = iv_series.iloc[-period:]
        
        return (lookback_data < current_iv).sum() / len(lookback_data) * 100
    
    def put_call_ratio(self, put_volume: pd.Series, call_volume: pd.Series,
                      smooth_period: int = 5) -> pd.Series:
        """
        Calculate Put/Call Ratio.
        
        Args:
            put_volume: Put volume series
            call_volume: Call volume series
            smooth_period: Smoothing period
            
        Returns:
            Put/Call ratio series
        """
        ratio = put_volume / call_volume.replace(0, 1)  # Avoid division by zero
        return ratio.rolling(window=smooth_period).mean()
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def calculate_all_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all major indicators for a dataset.
        
        Args:
            data: DataFrame with OHLCV columns
            
        Returns:
            DataFrame with all indicators added
        """
        result = data.copy()
        
        # Ensure we have required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in data.columns for col in required_cols):
            self.logger.error("Missing required OHLCV columns")
            return result
        
        # Trend indicators
        result['SMA_20'] = self.sma(data['close'], 20)
        result['SMA_50'] = self.sma(data['close'], 50)
        result['EMA_12'] = self.ema(data['close'], 12)
        result['EMA_26'] = self.ema(data['close'], 26)
        
        # Momentum indicators
        result['RSI_14'] = self.rsi(data['close'], 14)
        macd_data = self.macd(data['close'])
        result['MACD'] = macd_data['macd']
        result['MACD_Signal'] = macd_data['signal']
        result['MACD_Histogram'] = macd_data['histogram']
        
        # Volatility indicators
        bb_data = self.bollinger_bands(data['close'])
        result['BB_Upper'] = bb_data['upper']
        result['BB_Middle'] = bb_data['middle']
        result['BB_Lower'] = bb_data['lower']
        result['ATR_14'] = self.atr(data['high'], data['low'], data['close'])
        
        # Volume indicators
        result['OBV'] = self.obv(data['close'], data['volume'])
        result['ADL'] = self.adl(data['high'], data['low'], data['close'], data['volume'])
        
        return result
    
    def validate_data(self, data: Union[pd.Series, pd.DataFrame]) -> bool:
        """
        Validate input data for indicator calculations.
        
        Args:
            data: Input data to validate
            
        Returns:
            True if valid, False otherwise
        """
        if data is None or len(data) == 0:
            self.logger.error("Empty data provided")
            return False
        
        if data.isnull().all().all() if isinstance(data, pd.DataFrame) else data.isnull().all():
            self.logger.error("All data values are null")
            return False
        
        return True

# =============================================================================
# Module Testing
# =============================================================================
if __name__ == "__main__":
    # Create sample data for testing
    dates = pd.date_range('2024-01-01', periods=100)
    np.random.seed(42)
    
    # Generate synthetic OHLCV data
    close_prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
    high_prices = close_prices + np.abs(np.random.randn(100) * 0.3)
    low_prices = close_prices - np.abs(np.random.randn(100) * 0.3)
    open_prices = close_prices + np.random.randn(100) * 0.2
    volume = np.random.randint(1000000, 5000000, 100)
    
    # Create DataFrame
    test_data = pd.DataFrame({
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volume
    }, index=dates)
    
    # Initialize indicators
    indicators = TechnicalIndicators()
    
    # Test individual indicators
    print("Testing Technical Indicators...")
    print("-" * 50)
    
    # SMA
    sma20 = indicators.sma(test_data['close'], 20)
    print(f"SMA(20) - Last value: {sma20.iloc[-1]:.2f}")
    
    # RSI
    rsi = indicators.rsi(test_data['close'], 14)
    print(f"RSI(14) - Last value: {rsi.iloc[-1]:.2f}")
    
    # MACD
    macd = indicators.macd(test_data['close'])
    print(f"MACD - Last value: {macd['macd'].iloc[-1]:.2f}")
    
    # Bollinger Bands
    bb = indicators.bollinger_bands(test_data['close'])
    print(f"Bollinger Bands - Upper: {bb['upper'].iloc[-1]:.2f}, "
          f"Middle: {bb['middle'].iloc[-1]:.2f}, Lower: {bb['lower'].iloc[-1]:.2f}")
    
    # Market Profile
    profile = indicators.calculate_market_profile(
        test_data['high'], test_data['low'], 
        test_data['close'], test_data['volume']
    )
    print(f"\nMarket Profile:")
    print(f"Regime: {profile.regime.value}")
    print(f"Trend: {profile.trend.value}")
    print(f"Volatility: {profile.volatility:.2%}")
    
    # Generate all indicators
    print("\nGenerating all indicators...")
    all_indicators = indicators.calculate_all_indicators(test_data)
    print(f"Total columns with indicators: {len(all_indicators.columns)}")
    print(f"Indicator columns: {[col for col in all_indicators.columns if col not in test_data.columns]}")
    
    print("\nIndicator testing completed successfully!")
