#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderU16_TechnicalAnalysis.py
Group: U (Utilities)
Purpose: Technical analysis indicators and calculations
Author: Mohamed Talib
Date Created: 2025-01-16
Last Updated: 2025-08-14 Time: 11:00:00

Description:
    This module provides comprehensive technical analysis functionality including
    trend indicators, momentum oscillators, volatility measures, and volume
    analysis. It serves as the central hub for all technical indicators used
    throughout the Spyder trading system. Fixed to use VWAP instead of
    non-existent VolumeSMAIndicator.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Any

import numpy as np
import pandas as pd
import logging

# ==============================================================================
# THIRD-PARTY IMPORTS - TA LIBRARY (NOT TA-LIB)
# ==============================================================================
try:
    # Trend Indicators
    # Momentum Indicators
    from ta.momentum import (AwesomeOscillatorIndicator, KAMAIndicator,  # noqa: F401
                            PercentagePriceOscillator,  # noqa: F401
                            PercentageVolumeOscillator, ROCIndicator,  # noqa: F401
                            RSIIndicator, StochasticOscillator,
                            StochRSIIndicator, TSIIndicator,  # noqa: F401
                            UltimateOscillator, WilliamsRIndicator)  # noqa: F401
    from ta.trend import (MACD, ADXIndicator, AroonIndicator, CCIIndicator,  # noqa: F401
                        DPOIndicator, EMAIndicator, IchimokuIndicator,  # noqa: F401
                        KSTIndicator, PSARIndicator, SMAIndicator,  # noqa: F401
                        STCIndicator, TRIXIndicator, VortexIndicator,  # noqa: F401
                        WMAIndicator)  # noqa: F401
    # Volatility Indicators
    from ta.volatility import (AverageTrueRange, BollingerBands,
                            DonchianChannel, KeltnerChannel, UlcerIndex)  # noqa: F401
    # Volume Indicators - FIXED IMPORT
    from ta.volume import \
        VolumeWeightedAveragePrice  # Using VWAP instead of VolumeSMAIndicator
    from ta.volume import (AccDistIndexIndicator, ChaikinMoneyFlowIndicator,  # noqa: F401
                        EaseOfMovementIndicator, ForceIndexIndicator,  # noqa: F401
                        NegativeVolumeIndexIndicator,  # noqa: F401
                        OnBalanceVolumeIndicator, VolumePriceTrendIndicator)  # noqa: F401

    TA_AVAILABLE = True
except ImportError as e:
    logging.info("Warning: TA library not fully available: %s", e)
    TA_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    logging.info("Warning: Logger and ErrorHandler not available")
    SpyderLogger = None
    SpyderErrorHandler = None

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Default periods for indicators
DEFAULT_PERIODS = {
    "sma_short": 20,
    "sma_long": 50,
    "ema": 21,
    "rsi": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "bollinger_period": 20,
    "bollinger_std": 2,
    "atr": 14,
    "adx": 14,
    "stochastic_k": 14,
    "stochastic_d": 3,
    "volume_sma": 20,  # For custom volume SMA if needed
    "vwap_window": 14,  # VWAP typically doesn't use a window, but for custom implementations
}

# Signal thresholds
SIGNAL_THRESHOLDS = {
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "adx_trending": 25,
    "macd_signal_threshold": 0,
    "volume_surge": 1.5,  # 150% of average
}

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


class TrendDirection(Enum):
    """Trend direction classification"""

    STRONG_UP = "strong_up"
    UP = "up"
    NEUTRAL = "neutral"
    DOWN = "down"
    STRONG_DOWN = "strong_down"


class SignalStrength(Enum):
    """Signal strength classification"""

    VERY_STRONG = "very_strong"
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    VERY_WEAK = "very_weak"


@dataclass
class TechnicalSignal:
    """Technical analysis signal"""

    indicator: str
    value: float
    signal: str  # buy, sell, neutral
    strength: SignalStrength
    timestamp: datetime
    metadata: dict[str, Any] = None


@dataclass
class TechnicalAnalysisResult:
    """Complete technical analysis result"""

    trend: TrendDirection
    momentum: dict[str, float]
    volatility: dict[str, float]
    volume: dict[str, float]
    signals: list[TechnicalSignal]
    composite_score: float  # -100 to +100
    timestamp: datetime


# ==============================================================================
# TECHNICAL ANALYSIS ENGINE
# ==============================================================================


class TechnicalAnalysis:
    """
    Comprehensive technical analysis engine for the Spyder system.

    This class provides all technical indicators and analysis functions
    needed for trading decisions, including trend, momentum, volatility,
    and volume analysis.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize technical analysis engine."""
        self.logger = SpyderLogger.get_logger(__name__) if SpyderLogger else None
        self.error_handler = SpyderErrorHandler() if SpyderErrorHandler else None

        # Configuration
        self.config = config or {}
        self.periods = {**DEFAULT_PERIODS, **self.config.get("periods", {})}
        self.thresholds = {**SIGNAL_THRESHOLDS, **self.config.get("thresholds", {})}

        # Cache for indicator calculations (bounded with TTL)
        self.indicator_cache: dict = {}
        self.cache_ttl = 60  # seconds
        self._cache_timestamps: dict[str, float] = {}
        self._cache_maxsize: int = 256

        if self.logger:
            self.logger.info("%s initialized", self.__class__.__name__)

    # ==========================================================================
    # TREND INDICATORS
    # ==========================================================================

    def calculate_sma(self, data: pd.Series, period: int | None = None) -> pd.Series:
        """Calculate Simple Moving Average."""
        period = period or self.periods["sma_short"]
        if TA_AVAILABLE:
            sma = SMAIndicator(close=data, window=period)
            return sma.sma_indicator()
        else:
            return data.rolling(window=period).mean()

    def calculate_ema(self, data: pd.Series, period: int | None = None) -> pd.Series:
        """Calculate Exponential Moving Average."""
        period = period or self.periods["ema"]
        if TA_AVAILABLE:
            ema = EMAIndicator(close=data, window=period)
            return ema.ema_indicator()
        else:
            return data.ewm(span=period, adjust=False).mean()

    def calculate_macd(self, data: pd.Series) -> dict[str, pd.Series]:
        """Calculate MACD indicator."""
        if TA_AVAILABLE:
            macd = MACD(
                close=data,
                window_slow=self.periods["macd_slow"],
                window_fast=self.periods["macd_fast"],
                window_sign=self.periods["macd_signal"],
            )
            return {
                "macd": macd.macd(),
                "signal": macd.macd_signal(),
                "histogram": macd.macd_diff(),
            }
        else:
            # Fallback implementation
            ema_fast = data.ewm(span=self.periods["macd_fast"], adjust=False).mean()
            ema_slow = data.ewm(span=self.periods["macd_slow"], adjust=False).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=self.periods["macd_signal"], adjust=False).mean()
            histogram = macd_line - signal_line

            return {"macd": macd_line, "signal": signal_line, "histogram": histogram}

    def calculate_adx(self, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """Calculate Average Directional Index."""
        if TA_AVAILABLE:
            adx = ADXIndicator(high=high, low=low, close=close, window=self.periods["adx"])
            return adx.adx()
        else:
            # Simplified fallback
            return pd.Series([25.0] * len(close), index=close.index)

    # ==========================================================================
    # MOMENTUM INDICATORS
    # ==========================================================================

    def calculate_rsi(self, data: pd.Series, period: int | None = None) -> pd.Series:
        """Calculate Relative Strength Index."""
        period = period or self.periods["rsi"]
        if TA_AVAILABLE:
            rsi = RSIIndicator(close=data, window=period)
            return rsi.rsi()
        else:
            # Fallback RSI calculation
            delta = data.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi

    def calculate_stochastic(
        self, high: pd.Series, low: pd.Series, close: pd.Series
    ) -> dict[str, pd.Series]:
        """Calculate Stochastic Oscillator."""
        if TA_AVAILABLE:
            stoch = StochasticOscillator(
                high=high,
                low=low,
                close=close,
                window=self.periods["stochastic_k"],
                smooth_window=self.periods["stochastic_d"],
            )
            return {"k": stoch.stoch(), "d": stoch.stoch_signal()}
        else:
            # Fallback implementation
            lowest_low = low.rolling(window=self.periods["stochastic_k"]).min()
            highest_high = high.rolling(window=self.periods["stochastic_k"]).max()
            k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
            d_percent = k_percent.rolling(window=self.periods["stochastic_d"]).mean()

            return {"k": k_percent, "d": d_percent}

    # ==========================================================================
    # VOLATILITY INDICATORS
    # ==========================================================================

    def calculate_bollinger_bands(self, data: pd.Series) -> dict[str, pd.Series]:
        """Calculate Bollinger Bands."""
        if TA_AVAILABLE:
            bb = BollingerBands(
                close=data,
                window=self.periods["bollinger_period"],
                window_dev=self.periods["bollinger_std"],
            )
            return {
                "upper": bb.bollinger_hband(),
                "middle": bb.bollinger_mavg(),
                "lower": bb.bollinger_lband(),
                "width": bb.bollinger_wband(),
                "percent": bb.bollinger_pband(),
            }
        else:
            # Fallback implementation
            sma = data.rolling(window=self.periods["bollinger_period"]).mean()
            std = data.rolling(window=self.periods["bollinger_period"]).std()
            upper = sma + (std * self.periods["bollinger_std"])
            lower = sma - (std * self.periods["bollinger_std"])

            return {
                "upper": upper,
                "middle": sma,
                "lower": lower,
                "width": upper - lower,
                "percent": (data - lower) / (upper - lower),
            }

    def calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """Calculate Average True Range."""
        if TA_AVAILABLE:
            atr = AverageTrueRange(high=high, low=low, close=close, window=self.periods["atr"])
            return atr.average_true_range()
        else:
            # Fallback implementation
            high_low = high - low
            high_close = np.abs(high - close.shift())
            low_close = np.abs(low - close.shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            atr = true_range.rolling(window=self.periods["atr"]).mean()
            return atr

    # ==========================================================================
    # VOLUME INDICATORS - FIXED TO USE VWAP
    # ==========================================================================

    def calculate_vwap(
        self, high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series
    ) -> pd.Series:
        """
        Calculate Volume Weighted Average Price (VWAP).

        This replaces the non-existent VolumeSMAIndicator with the more
        commonly used VWAP indicator for trading.
        """
        if TA_AVAILABLE:
            vwap = VolumeWeightedAveragePrice(high=high, low=low, close=close, volume=volume)
            return vwap.volume_weighted_average_price()
        else:
            # Fallback VWAP calculation
            typical_price = (high + low + close) / 3
            vwap = (typical_price * volume).cumsum() / volume.cumsum()
            return vwap

    def calculate_volume_sma(self, volume: pd.Series, period: int | None = None) -> pd.Series:
        """
        Calculate Simple Moving Average of Volume.

        Custom implementation since VolumeSMAIndicator doesn't exist in ta library.
        """
        period = period or self.periods["volume_sma"]
        return volume.rolling(window=period).mean()

    def calculate_obv(self, close: pd.Series, volume: pd.Series) -> pd.Series:
        """Calculate On Balance Volume."""
        if TA_AVAILABLE:
            obv = OnBalanceVolumeIndicator(close=close, volume=volume)
            return obv.on_balance_volume()
        else:
            # Fallback implementation
            obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
            return obv

    def calculate_cmf(
        self, high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 20
    ) -> pd.Series:
        """Calculate Chaikin Money Flow."""
        if TA_AVAILABLE:
            cmf = ChaikinMoneyFlowIndicator(
                high=high, low=low, close=close, volume=volume, window=period
            )
            return cmf.chaikin_money_flow()
        else:
            # Fallback implementation
            mfv = ((close - low) - (high - close)) / (high - low) * volume
            return mfv.rolling(window=period).sum() / volume.rolling(window=period).sum()

    def detect_volume_surge(self, volume: pd.Series) -> pd.Series:
        """
        Detect volume surges compared to average.

        Returns a boolean series indicating volume surge conditions.
        """
        volume_avg = self.calculate_volume_sma(volume)
        surge_threshold = volume_avg * self.thresholds["volume_surge"]
        return volume > surge_threshold

    # ==========================================================================
    # COMPOSITE ANALYSIS
    # ==========================================================================

    def analyze_trend(self, close: pd.Series) -> TrendDirection:
        """Analyze overall trend direction."""
        sma_short = self.calculate_sma(close, self.periods["sma_short"])
        sma_long = self.calculate_sma(close, self.periods["sma_long"])

        current_price = close.iloc[-1]
        short_sma = sma_short.iloc[-1]
        long_sma = sma_long.iloc[-1]

        # Trend strength calculation
        if current_price > short_sma > long_sma:
            pct_above = ((current_price - long_sma) / long_sma) * 100
            if pct_above > 5:
                return TrendDirection.STRONG_UP
            return TrendDirection.UP
        elif current_price < short_sma < long_sma:
            pct_below = ((long_sma - current_price) / long_sma) * 100
            if pct_below > 5:
                return TrendDirection.STRONG_DOWN
            return TrendDirection.DOWN
        else:
            return TrendDirection.NEUTRAL

    def generate_signals(self, df: pd.DataFrame) -> list[TechnicalSignal]:
        """
        Generate trading signals from technical indicators.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            List of technical signals
        """
        signals = []
        timestamp = datetime.now(timezone.utc)

        # RSI signals
        rsi = self.calculate_rsi(df["close"])
        current_rsi = rsi.iloc[-1]

        if current_rsi < self.thresholds["rsi_oversold"]:
            signals.append(
                TechnicalSignal(
                    indicator="RSI",
                    value=current_rsi,
                    signal="buy",
                    strength=SignalStrength.STRONG if current_rsi < 20 else SignalStrength.MODERATE,
                    timestamp=timestamp,
                )
            )
        elif current_rsi > self.thresholds["rsi_overbought"]:
            signals.append(
                TechnicalSignal(
                    indicator="RSI",
                    value=current_rsi,
                    signal="sell",
                    strength=SignalStrength.STRONG if current_rsi > 80 else SignalStrength.MODERATE,
                    timestamp=timestamp,
                )
            )

        # MACD signals
        macd_data = self.calculate_macd(df["close"])
        macd_current = macd_data["macd"].iloc[-1]
        signal_current = macd_data["signal"].iloc[-1]
        macd_prev = macd_data["macd"].iloc[-2]
        signal_prev = macd_data["signal"].iloc[-2]

        # MACD crossover signals
        if macd_prev <= signal_prev and macd_current > signal_current:
            signals.append(
                TechnicalSignal(
                    indicator="MACD",
                    value=macd_current - signal_current,
                    signal="buy",
                    strength=SignalStrength.STRONG,
                    timestamp=timestamp,
                )
            )
        elif macd_prev >= signal_prev and macd_current < signal_current:
            signals.append(
                TechnicalSignal(
                    indicator="MACD",
                    value=macd_current - signal_current,
                    signal="sell",
                    strength=SignalStrength.STRONG,
                    timestamp=timestamp,
                )
            )

        # Volume signals using VWAP
        vwap = self.calculate_vwap(df["high"], df["low"], df["close"], df["volume"])
        current_price = df["close"].iloc[-1]
        current_vwap = vwap.iloc[-1]

        if current_price > current_vwap:
            signals.append(
                TechnicalSignal(
                    indicator="VWAP",
                    value=current_vwap,
                    signal="buy",
                    strength=SignalStrength.MODERATE,
                    timestamp=timestamp,
                    metadata={"price_above_vwap": True},
                )
            )
        else:
            signals.append(
                TechnicalSignal(
                    indicator="VWAP",
                    value=current_vwap,
                    signal="sell",
                    strength=SignalStrength.MODERATE,
                    timestamp=timestamp,
                    metadata={"price_below_vwap": True},
                )
            )

        # Volume surge detection
        volume_surge = self.detect_volume_surge(df["volume"])
        if volume_surge.iloc[-1]:
            signals.append(
                TechnicalSignal(
                    indicator="Volume",
                    value=df["volume"].iloc[-1],
                    signal="neutral",
                    strength=SignalStrength.STRONG,
                    timestamp=timestamp,
                    metadata={"volume_surge": True},
                )
            )

        return signals

    def get_composite_score(self, df: pd.DataFrame) -> float:
        """
        Calculate composite technical score from -100 to +100.

        Positive values indicate bullish bias, negative indicate bearish.
        """
        score = 0.0
        weights = {"trend": 0.3, "momentum": 0.3, "volume": 0.2, "volatility": 0.2}

        # Trend component
        trend = self.analyze_trend(df["close"])
        trend_scores = {
            TrendDirection.STRONG_UP: 100,
            TrendDirection.UP: 50,
            TrendDirection.NEUTRAL: 0,
            TrendDirection.DOWN: -50,
            TrendDirection.STRONG_DOWN: -100,
        }
        score += trend_scores[trend] * weights["trend"]

        # Momentum component (RSI)
        rsi = self.calculate_rsi(df["close"]).iloc[-1]
        rsi_score = (rsi - 50) * 2  # Convert to -100 to +100 scale
        score += rsi_score * weights["momentum"]

        # Volume component (VWAP relationship)
        vwap = self.calculate_vwap(df["high"], df["low"], df["close"], df["volume"])
        price_vwap_pct = ((df["close"].iloc[-1] - vwap.iloc[-1]) / vwap.iloc[-1]) * 100
        volume_score = max(-100, min(100, price_vwap_pct * 10))
        score += volume_score * weights["volume"]

        # Volatility component (Bollinger Band position)
        bb = self.calculate_bollinger_bands(df["close"])
        bb_percent = bb["percent"].iloc[-1]
        volatility_score = (bb_percent - 0.5) * 200  # Convert to -100 to +100
        score += volatility_score * weights["volatility"]

        return max(-100, min(100, score))

    def full_analysis(self, df: pd.DataFrame) -> TechnicalAnalysisResult:
        """
        Perform complete technical analysis on OHLCV data.

        Args:
            df: DataFrame with columns: open, high, low, close, volume

        Returns:
            Comprehensive technical analysis result
        """
        # Calculate all indicators
        momentum = {
            "rsi": self.calculate_rsi(df["close"]).iloc[-1],
            "macd": self.calculate_macd(df["close"])["histogram"].iloc[-1],
            "stochastic_k": self.calculate_stochastic(df["high"], df["low"], df["close"])["k"].iloc[
                -1
            ],
        }

        volatility = {
            "atr": self.calculate_atr(df["high"], df["low"], df["close"]).iloc[-1],
            "bollinger_width": self.calculate_bollinger_bands(df["close"])["width"].iloc[-1],
            "bollinger_percent": self.calculate_bollinger_bands(df["close"])["percent"].iloc[-1],
        }

        volume = {
            "vwap": self.calculate_vwap(df["high"], df["low"], df["close"], df["volume"]).iloc[-1],
            "obv": self.calculate_obv(df["close"], df["volume"]).iloc[-1],
            "cmf": self.calculate_cmf(df["high"], df["low"], df["close"], df["volume"]).iloc[-1],
            "volume_sma": self.calculate_volume_sma(df["volume"]).iloc[-1],
            "current_volume": df["volume"].iloc[-1],
        }

        # Generate result
        return TechnicalAnalysisResult(
            trend=self.analyze_trend(df["close"]),
            momentum=momentum,
            volatility=volatility,
            volume=volume,
            signals=self.generate_signals(df),
            composite_score=self.get_composite_score(df),
            timestamp=datetime.now(timezone.utc),
        )


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def quick_analysis(df: pd.DataFrame) -> dict[str, Any]:
    """
    Quick technical analysis for immediate decision making.

    Args:
        df: OHLCV DataFrame

    Returns:
        Dictionary with key indicators and signals
    """
    ta = TechnicalAnalysis()

    return {
        "trend": ta.analyze_trend(df["close"]).value,
        "rsi": ta.calculate_rsi(df["close"]).iloc[-1],
        "vwap": ta.calculate_vwap(df["high"], df["low"], df["close"], df["volume"]).iloc[-1],
        "composite_score": ta.get_composite_score(df),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================


# Module-level instance for convenience
_ta_instance: TechnicalAnalysis | None = None


def get_technical_analysis() -> TechnicalAnalysis:
    """Get singleton instance of technical analysis engine."""
    global _ta_instance
    if _ta_instance is None:
        _ta_instance = TechnicalAnalysis()
    return _ta_instance


# ==============================================================================
# MODULE EXPORTS
# ==============================================================================


__all__ = [
    # Main class
    "TechnicalAnalysis",
    # Enums
    "TrendDirection",
    "SignalStrength",
    # Data structures
    "TechnicalSignal",
    "TechnicalAnalysisResult",
    # Functions
    "quick_analysis",
    "get_technical_analysis",
    # Constants
    "DEFAULT_PERIODS",
    "SIGNAL_THRESHOLDS",
]

# Log module initialization
logging.info("✅ Technical Analysis Module Loaded - VWAP Integration Complete")
