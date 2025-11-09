#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderU13_TechnicalIndicators.py
Group: U (Utilities)
Purpose: Technical analysis indicators and calculations

Description:
    This module provides a comprehensive suite of technical analysis indicators
    optimized for options trading strategies. It includes RSI, MACD, Bollinger
    Bands, Stochastic, Moving Averages, and other key indicators with efficient
    calculations and configurable parameters for real-time trading analysis.

Author: Mohamed Talib
Date Created: 2025-07-18
Last Updated: 2025-07-18 Time: 12:15:00

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
import warnings
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Default indicator parameters
DEFAULT_RSI_PERIOD = 14
DEFAULT_MACD_FAST = 12
DEFAULT_MACD_SLOW = 26
DEFAULT_MACD_SIGNAL = 9
DEFAULT_BB_PERIOD = 20
DEFAULT_BB_STDDEV = 2.0
DEFAULT_STOCH_K = 14
DEFAULT_STOCH_D = 3
DEFAULT_ATR_PERIOD = 14
DEFAULT_ADX_PERIOD = 14

# Moving average types
MA_TYPES = ["SMA", "EMA", "WMA", "HULL", "VWMA"]

# Overbought/Oversold levels
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
STOCH_OVERBOUGHT = 80
STOCH_OVERSOLD = 20

# ==============================================================================
# ENUMS
# ==============================================================================


class MAType(Enum):
    """Moving average types"""

    SMA = "SMA"  # Simple Moving Average
    EMA = "EMA"  # Exponential Moving Average
    WMA = "WMA"  # Weighted Moving Average
    HULL = "HULL"  # Hull Moving Average
    VWMA = "VWMA"  # Volume Weighted Moving Average


class SignalType(Enum):
    """Technical indicator signals"""

    BUY = "buy"
    SELL = "sell"
    NEUTRAL = "neutral"
    STRONG_BUY = "strong_buy"
    STRONG_SELL = "strong_sell"


class TrendDirection(Enum):
    """Trend direction"""

    UP = "up"
    DOWN = "down"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class IndicatorResult:
    """Technical indicator result structure."""

    name: str
    value: Union[float, Dict[str, float]]
    signal: SignalType
    timestamp: pd.Timestamp
    parameters: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "signal": self.signal.value,
            "timestamp": self.timestamp.isoformat(),
            "parameters": self.parameters,
        }


@dataclass
class TrendAnalysis:
    """Trend analysis result."""

    direction: TrendDirection
    strength: float
    duration: int
    support_level: float
    resistance_level: float


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class TechnicalIndicators:
    """
    Technical indicators calculator for trading analysis.

    This class provides a comprehensive suite of technical analysis indicators
    optimized for options trading. It includes trend-following indicators,
    oscillators, volatility measures, and volume indicators with efficient
    calculations and configurable parameters.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance

    Example:
        >>> indicators = TechnicalIndicators()
        >>> prices = pd.Series([100, 101, 102, 101, 100, 99, 98])
        >>> rsi = indicators.calculate_rsi(prices, period=6)
        >>> macd = indicators.calculate_macd(prices)
        >>> bb = indicators.calculate_bollinger_bands(prices)
    """

    def __init__(self):
        """Initialize the technical indicators calculator."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        self.logger.info(f"{self.__class__.__name__} initialized")

    # ==========================================================================
    # OSCILLATORS
    # ==========================================================================
    def calculate_rsi(self, prices: pd.Series, period: int = DEFAULT_RSI_PERIOD) -> pd.Series:
        """
        Calculate Relative Strength Index (RSI).

        Args:
            prices: Price series (typically close prices)
            period: Calculation period (default 14)

        Returns:
            pd.Series: RSI values (0-100)

        Example:
            >>> indicators = TechnicalIndicators()
            >>> prices = pd.Series([100, 101, 102, 101, 100, 99, 98, 97, 98, 99])
            >>> rsi = indicators.calculate_rsi(prices, period=6)
            >>> print(f"Current RSI: {rsi.iloc[-1]:.2f}")
        """
        try:
            if len(prices) < period + 1:
                self.logger.warning(
                    f"Insufficient data for RSI calculation: {len(prices)} < {period + 1}"
                )
                return pd.Series(dtype=float, index=prices.index)

            # Calculate price changes
            delta = prices.diff()

            # Separate gains and losses
            gains = delta.where(delta > 0, 0)
            losses = -delta.where(delta < 0, 0)

            # Calculate initial averages
            avg_gain = gains.rolling(window=period, min_periods=period).mean()
            avg_loss = losses.rolling(window=period, min_periods=period).mean()

            # Use Wilder's smoothing for subsequent values
            for i in range(period, len(prices)):
                avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gains.iloc[i]) / period
                avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + losses.iloc[i]) / period

            # Calculate RS and RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            return rsi.fillna(50)  # Fill NaN with neutral value

        except Exception as e:
            self.logger.error(f"RSI calculation failed: {e}")
            return pd.Series(dtype=float, index=prices.index)

    def calculate_stochastic(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        k_period: int = DEFAULT_STOCH_K,
        d_period: int = DEFAULT_STOCH_D,
    ) -> Dict[str, pd.Series]:
        """
        Calculate Stochastic Oscillator (%K and %D).

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            k_period: %K period
            d_period: %D smoothing period

        Returns:
            Dictionary with %K and %D series
        """
        try:
            # Calculate %K
            lowest_low = low.rolling(window=k_period, min_periods=k_period).min()
            highest_high = high.rolling(window=k_period, min_periods=k_period).max()

            k_percent = 100 * (close - lowest_low) / (highest_high - lowest_low)

            # Calculate %D (smoothed %K)
            d_percent = k_percent.rolling(window=d_period, min_periods=d_period).mean()

            return {"%K": k_percent.fillna(50), "%D": d_percent.fillna(50)}

        except Exception as e:
            self.logger.error(f"Stochastic calculation failed: {e}")
            return {
                "%K": pd.Series(dtype=float, index=close.index),
                "%D": pd.Series(dtype=float, index=close.index),
            }

    def calculate_williams_r(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """
        Calculate Williams %R oscillator.

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: Calculation period

        Returns:
            pd.Series: Williams %R values (-100 to 0)
        """
        try:
            highest_high = high.rolling(window=period, min_periods=period).max()
            lowest_low = low.rolling(window=period, min_periods=period).min()

            williams_r = -100 * (highest_high - close) / (highest_high - lowest_low)

            return williams_r.fillna(-50)

        except Exception as e:
            self.logger.error(f"Williams %R calculation failed: {e}")
            return pd.Series(dtype=float, index=close.index)

    # ==========================================================================
    # TREND INDICATORS
    # ==========================================================================
    def calculate_macd(
        self,
        prices: pd.Series,
        fast: int = DEFAULT_MACD_FAST,
        slow: int = DEFAULT_MACD_SLOW,
        signal: int = DEFAULT_MACD_SIGNAL,
    ) -> Dict[str, pd.Series]:
        """
        Calculate MACD (Moving Average Convergence Divergence).

        Args:
            prices: Price series
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line EMA period

        Returns:
            Dictionary with MACD line, signal line, and histogram
        """
        try:
            # Calculate EMAs
            ema_fast = self.calculate_ema(prices, fast)
            ema_slow = self.calculate_ema(prices, slow)

            # Calculate MACD line
            macd_line = ema_fast - ema_slow

            # Calculate signal line
            signal_line = self.calculate_ema(macd_line, signal)

            # Calculate histogram
            histogram = macd_line - signal_line

            return {"MACD": macd_line, "Signal": signal_line, "Histogram": histogram}

        except Exception as e:
            self.logger.error(f"MACD calculation failed: {e}")
            return {
                "MACD": pd.Series(dtype=float, index=prices.index),
                "Signal": pd.Series(dtype=float, index=prices.index),
                "Histogram": pd.Series(dtype=float, index=prices.index),
            }

    def calculate_adx(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = DEFAULT_ADX_PERIOD
    ) -> Dict[str, pd.Series]:
        """
        Calculate Average Directional Index (ADX) and directional indicators.

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: Calculation period

        Returns:
            Dictionary with ADX, +DI, and -DI
        """
        try:
            # Calculate True Range
            tr = self.calculate_true_range(high, low, close)

            # Calculate directional movements
            up_move = high.diff()
            down_move = -low.diff()

            plus_dm = pd.Series(0.0, index=close.index)
            minus_dm = pd.Series(0.0, index=close.index)

            plus_dm[up_move > down_move] = up_move[up_move > down_move].clip(lower=0)
            minus_dm[down_move > up_move] = down_move[down_move > up_move].clip(lower=0)

            # Calculate smoothed values
            atr = tr.rolling(window=period, min_periods=period).mean()
            plus_di = 100 * (plus_dm.rolling(window=period, min_periods=period).mean() / atr)
            minus_di = 100 * (minus_dm.rolling(window=period, min_periods=period).mean() / atr)

            # Calculate ADX
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            adx = dx.rolling(window=period, min_periods=period).mean()

            return {"ADX": adx, "+DI": plus_di, "-DI": minus_di}

        except Exception as e:
            self.logger.error(f"ADX calculation failed: {e}")
            return {
                "ADX": pd.Series(dtype=float, index=close.index),
                "+DI": pd.Series(dtype=float, index=close.index),
                "-DI": pd.Series(dtype=float, index=close.index),
            }

    # ==========================================================================
    # VOLATILITY INDICATORS
    # ==========================================================================
    def calculate_bollinger_bands(
        self, prices: pd.Series, period: int = DEFAULT_BB_PERIOD, std_dev: float = DEFAULT_BB_STDDEV
    ) -> Dict[str, pd.Series]:
        """
        Calculate Bollinger Bands.

        Args:
            prices: Price series
            period: Moving average period
            std_dev: Standard deviation multiplier

        Returns:
            Dictionary with upper band, middle band (SMA), and lower band
        """
        try:
            # Calculate middle band (SMA)
            middle_band = self.calculate_sma(prices, period)

            # Calculate standard deviation
            std = prices.rolling(window=period, min_periods=period).std()

            # Calculate bands
            upper_band = middle_band + (std * std_dev)
            lower_band = middle_band - (std * std_dev)

            return {"Upper": upper_band, "Middle": middle_band, "Lower": lower_band}

        except Exception as e:
            self.logger.error(f"Bollinger Bands calculation failed: {e}")
            return {
                "Upper": pd.Series(dtype=float, index=prices.index),
                "Middle": pd.Series(dtype=float, index=prices.index),
                "Lower": pd.Series(dtype=float, index=prices.index),
            }

    def calculate_atr(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = DEFAULT_ATR_PERIOD
    ) -> pd.Series:
        """
        Calculate Average True Range (ATR).

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: Calculation period

        Returns:
            pd.Series: ATR values
        """
        try:
            tr = self.calculate_true_range(high, low, close)
            atr = tr.rolling(window=period, min_periods=period).mean()

            return atr

        except Exception as e:
            self.logger.error(f"ATR calculation failed: {e}")
            return pd.Series(dtype=float, index=close.index)

    def calculate_true_range(self, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """
        Calculate True Range.

        Args:
            high: High prices
            low: Low prices
            close: Close prices

        Returns:
            pd.Series: True Range values
        """
        try:
            prev_close = close.shift(1)

            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)

            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

            return true_range

        except Exception as e:
            self.logger.error(f"True Range calculation failed: {e}")
            return pd.Series(dtype=float, index=close.index)

    # ==========================================================================
    # MOVING AVERAGES
    # ==========================================================================
    def calculate_sma(self, prices: pd.Series, period: int) -> pd.Series:
        """
        Calculate Simple Moving Average (SMA).

        Args:
            prices: Price series
            period: Moving average period

        Returns:
            pd.Series: SMA values
        """
        try:
            return prices.rolling(window=period, min_periods=period).mean()
        except Exception as e:
            self.logger.error(f"SMA calculation failed: {e}")
            return pd.Series(dtype=float, index=prices.index)

    def calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """
        Calculate Exponential Moving Average (EMA).

        Args:
            prices: Price series
            period: Moving average period

        Returns:
            pd.Series: EMA values
        """
        try:
            return prices.ewm(span=period, adjust=False).mean()
        except Exception as e:
            self.logger.error(f"EMA calculation failed: {e}")
            return pd.Series(dtype=float, index=prices.index)

    def calculate_wma(self, prices: pd.Series, period: int) -> pd.Series:
        """
        Calculate Weighted Moving Average (WMA).

        Args:
            prices: Price series
            period: Moving average period

        Returns:
            pd.Series: WMA values
        """
        try:
            weights = np.arange(1, period + 1)
            wma = prices.rolling(window=period, min_periods=period).apply(
                lambda x: np.dot(x, weights) / weights.sum(), raw=True
            )
            return wma
        except Exception as e:
            self.logger.error(f"WMA calculation failed: {e}")
            return pd.Series(dtype=float, index=prices.index)

    def calculate_hull_ma(self, prices: pd.Series, period: int) -> pd.Series:
        """
        Calculate Hull Moving Average.

        Args:
            prices: Price series
            period: Moving average period

        Returns:
            pd.Series: Hull MA values
        """
        try:
            wma_half = self.calculate_wma(prices, period // 2)
            wma_full = self.calculate_wma(prices, period)

            raw_hull = 2 * wma_half - wma_full
            hull_period = int(np.sqrt(period))

            hull_ma = self.calculate_wma(raw_hull, hull_period)

            return hull_ma
        except Exception as e:
            self.logger.error(f"Hull MA calculation failed: {e}")
            return pd.Series(dtype=float, index=prices.index)

    # ==========================================================================
    # VOLUME INDICATORS
    # ==========================================================================
    def calculate_vwap(
        self, high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series
    ) -> pd.Series:
        """
        Calculate Volume Weighted Average Price (VWAP).

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            volume: Volume data

        Returns:
            pd.Series: VWAP values
        """
        try:
            typical_price = (high + low + close) / 3
            cumulative_tpv = (typical_price * volume).cumsum()
            cumulative_volume = volume.cumsum()

            vwap = cumulative_tpv / cumulative_volume

            return vwap
        except Exception as e:
            self.logger.error(f"VWAP calculation failed: {e}")
            return pd.Series(dtype=float, index=close.index)

    def calculate_obv(self, close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        Calculate On-Balance Volume (OBV).

        Args:
            close: Close prices
            volume: Volume data

        Returns:
            pd.Series: OBV values
        """
        try:
            price_change = close.diff()
            obv_change = volume.copy()

            obv_change[price_change < 0] = -volume[price_change < 0]
            obv_change[price_change == 0] = 0

            obv = obv_change.cumsum()

            return obv
        except Exception as e:
            self.logger.error(f"OBV calculation failed: {e}")
            return pd.Series(dtype=float, index=close.index)

    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================
    def generate_rsi_signal(self, rsi_values: pd.Series) -> SignalType:
        """
        Generate trading signal from RSI values.

        Args:
            rsi_values: RSI series

        Returns:
            SignalType: Trading signal
        """
        try:
            current_rsi = rsi_values.iloc[-1]

            if current_rsi >= 80:
                return SignalType.STRONG_SELL
            elif current_rsi >= RSI_OVERBOUGHT:
                return SignalType.SELL
            elif current_rsi <= 20:
                return SignalType.STRONG_BUY
            elif current_rsi <= RSI_OVERSOLD:
                return SignalType.BUY
            else:
                return SignalType.NEUTRAL

        except Exception as e:
            self.logger.error(f"RSI signal generation failed: {e}")
            return SignalType.NEUTRAL

    def generate_macd_signal(self, macd_data: Dict[str, pd.Series]) -> SignalType:
        """
        Generate trading signal from MACD.

        Args:
            macd_data: MACD data dictionary

        Returns:
            SignalType: Trading signal
        """
        try:
            macd_line = macd_data["MACD"]
            signal_line = macd_data["Signal"]
            histogram = macd_data["Histogram"]

            current_macd = macd_line.iloc[-1]
            current_signal = signal_line.iloc[-1]
            current_hist = histogram.iloc[-1]
            prev_hist = histogram.iloc[-2] if len(histogram) > 1 else 0

            # Bullish crossover
            if current_macd > current_signal and prev_hist < 0 and current_hist > 0:
                return SignalType.BUY
            # Bearish crossover
            elif current_macd < current_signal and prev_hist > 0 and current_hist < 0:
                return SignalType.SELL
            else:
                return SignalType.NEUTRAL

        except Exception as e:
            self.logger.error(f"MACD signal generation failed: {e}")
            return SignalType.NEUTRAL


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def calculate_rsi(prices: pd.Series, period: int = DEFAULT_RSI_PERIOD) -> pd.Series:
    """
    Quick RSI calculation function.

    Args:
        prices: Price series
        period: Calculation period

    Returns:
        pd.Series: RSI values
    """
    indicators = TechnicalIndicators()
    return indicators.calculate_rsi(prices, period)


def calculate_macd(
    prices: pd.Series,
    fast: int = DEFAULT_MACD_FAST,
    slow: int = DEFAULT_MACD_SLOW,
    signal: int = DEFAULT_MACD_SIGNAL,
) -> Dict[str, pd.Series]:
    """
    Quick MACD calculation function.

    Args:
        prices: Price series
        fast: Fast EMA period
        slow: Slow EMA period
        signal: Signal line period

    Returns:
        Dictionary with MACD components
    """
    indicators = TechnicalIndicators()
    return indicators.calculate_macd(prices, fast, slow, signal)


def calculate_bollinger_bands(
    prices: pd.Series, period: int = DEFAULT_BB_PERIOD, std_dev: float = DEFAULT_BB_STDDEV
) -> Dict[str, pd.Series]:
    """
    Quick Bollinger Bands calculation function.

    Args:
        prices: Price series
        period: Moving average period
        std_dev: Standard deviation multiplier

    Returns:
        Dictionary with Bollinger Bands
    """
    indicators = TechnicalIndicators()
    return indicators.calculate_bollinger_bands(prices, period, std_dev)


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
_technical_indicators_instance: Optional[TechnicalIndicators] = None


def get_technical_indicators() -> TechnicalIndicators:
    """
    Get singleton instance of technical indicators calculator.

    Returns:
        TechnicalIndicators instance
    """
    global _technical_indicators_instance
    if _technical_indicators_instance is None:
        _technical_indicators_instance = TechnicalIndicators()
    return _technical_indicators_instance


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("=" * 80)
    print("SPYDER U13 - Technical Indicators Test")
    print("=" * 80)

    indicators = TechnicalIndicators()

    # Create test data
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=100, freq="D")
    prices = pd.Series(100 + np.cumsum(np.random.randn(100) * 0.5), index=dates)
    high = prices + np.random.rand(100) * 2
    low = prices - np.random.rand(100) * 2
    volume = pd.Series(np.random.randint(1000, 10000, 100), index=dates)

    # Test RSI
    print("\n1. Testing RSI calculation...")
    rsi = indicators.calculate_rsi(prices, period=14)
    print(f"   Current RSI: {rsi.iloc[-1]:.2f}")
    print(f"   RSI Signal: {indicators.generate_rsi_signal(rsi).value}")

    # Test MACD
    print("\n2. Testing MACD calculation...")
    macd = indicators.calculate_macd(prices)
    print(f"   Current MACD: {macd['MACD'].iloc[-1]:.4f}")
    print(f"   Signal Line: {macd['Signal'].iloc[-1]:.4f}")
    print(f"   Histogram: {macd['Histogram'].iloc[-1]:.4f}")

    # Test Bollinger Bands
    print("\n3. Testing Bollinger Bands...")
    bb = indicators.calculate_bollinger_bands(prices)
    print(f"   Upper Band: {bb['Upper'].iloc[-1]:.2f}")
    print(f"   Middle Band: {bb['Middle'].iloc[-1]:.2f}")
    print(f"   Lower Band: {bb['Lower'].iloc[-1]:.2f}")

    # Test Stochastic
    print("\n4. Testing Stochastic Oscillator...")
    stoch = indicators.calculate_stochastic(high, low, prices)
    print(f"   %K: {stoch['%K'].iloc[-1]:.2f}")
    print(f"   %D: {stoch['%D'].iloc[-1]:.2f}")

    # Test ATR
    print("\n5. Testing ATR...")
    atr = indicators.calculate_atr(high, low, prices)
    print(f"   Current ATR: {atr.iloc[-1]:.4f}")

    print("\n" + "=" * 80)
    print("✅ Technical Indicators test completed!")
