#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovO_TechnicalIndicators
Module: TradovO01_CoreTechnicalIndicators.py
Purpose: Comprehensive technical indicators with signal generation for options trading
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-04 Time: 16:00:00

Module Description:
    Core technical indicators module providing pure Python implementations of essential
    technical analysis tools. Designed specifically for options trading with signal
    generation, confidence scoring, and regime-aware calculations. Eliminates TA-Lib
    dependency while providing professional-grade indicator calculations with proper
    signal interpretation for automated trading systems.

Key Features:
    • Pure Python implementation - no external TA-Lib dependency
    • Options-specific indicators and calculations
    • Signal generation with confidence levels
    • Regime-aware indicator interpretation
    • Volatility structure analysis
    • Volume profile and flow analysis
    • Support/resistance level detection
    • Multi-timeframe indicator synthesis
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, UTC
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd
from collections import deque
import math

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Signal strength thresholds
STRONG_SIGNAL_THRESHOLD = 0.75
MODERATE_SIGNAL_THRESHOLD = 0.50
WEAK_SIGNAL_THRESHOLD = 0.25

# Volatility regime thresholds
HIGH_VOLATILITY_THRESHOLD = 25    # VIX > 25
LOW_VOLATILITY_THRESHOLD = 15     # VIX < 15

# Trend strength classifications
STRONG_TREND_THRESHOLD = 0.7
MODERATE_TREND_THRESHOLD = 0.4
WEAK_TREND_THRESHOLD = 0.2

# Volume analysis
HIGH_VOLUME_MULTIPLIER = 1.5      # 50% above average
LOW_VOLUME_MULTIPLIER = 0.7       # 30% below average

# Momentum thresholds
MOMENTUM_ACCELERATION_THRESHOLD = 0.02
MOMENTUM_DECELERATION_THRESHOLD = -0.02

# ==============================================================================
# ENUMERATIONS
# ==============================================================================
class SignalType(Enum):
    """Technical signal types"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    DIVERGENCE = "divergence"
    BREAKOUT = "breakout"
    BREAKDOWN = "breakdown"

class IndicatorStrength(Enum):
    """Indicator signal strength"""
    VERY_STRONG = "very_strong"
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    VERY_WEAK = "very_weak"

class TrendDirection(Enum):
    """Trend direction classification"""
    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    SIDEWAYS = "sideways"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"

class VolatilityRegime(Enum):
    """Volatility regime classification"""
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class IndicatorSignal:
    """Technical indicator signal with metadata"""
    indicator_name: str
    signal_type: SignalType
    strength: IndicatorStrength
    confidence: float
    value: float
    timestamp: datetime

    # Context data
    current_price: float = 0.0
    timeframe: str = "5min"
    regime_context: str | None = None

    # Supporting data
    supporting_indicators: list[str] = field(default_factory=list)
    conflicting_indicators: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            'indicator': self.indicator_name,
            'signal': self.signal_type.value,
            'strength': self.strength.value,
            'confidence': self.confidence,
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'price': self.current_price,
            'timeframe': self.timeframe,
            'regime': self.regime_context,
            'supporting': self.supporting_indicators,
            'conflicting': self.conflicting_indicators
        }

@dataclass
class SupportResistanceLevel:
    """Support or resistance level with metadata"""
    price_level: float
    level_type: str  # 'support' or 'resistance'
    strength: float  # 0-1 scale
    touches: int
    age: int  # bars since formation
    volume_confirmation: bool

    # Price action at level
    last_test_price: float = 0.0
    penetration_distance: float = 0.0
    holding_strength: float = 0.0

@dataclass
class VolumeProfile:
    """Volume profile analysis"""
    poc: float  # Point of Control
    value_area_high: float
    value_area_low: float
    total_volume: int

    # Distribution metrics
    volume_at_price: dict[float, int] = field(default_factory=dict)
    value_area_volume_pct: float = 0.7  # 70% of volume

    # Profile shape
    profile_type: str = "normal"  # normal, b_shape, p_shape
    skewness: float = 0.0
    kurtosis: float = 0.0

# ==============================================================================
# CORE TECHNICAL INDICATORS CLASS
# ==============================================================================
class CoreTechnicalIndicators:
    """
    Comprehensive technical indicators with signal generation.

    Pure Python implementation designed for options trading with proper
    signal interpretation, confidence scoring, and regime-aware analysis.
    """

    def __init__(self):
        """Initialize technical indicators engine"""
        self.logger = TradovLogger.get_logger(__name__)
        self.error_handler = TradovErrorHandler()

        # Signal history for pattern recognition
        self.signal_history: dict[str, deque] = {}

        # Indicator state tracking
        self.indicator_states: dict[str, Any] = {}

        # Performance tracking
        self.indicator_performance: dict[str, dict[str, float]] = {}

        self.logger.info("CoreTechnicalIndicators initialized")

    # ==========================================================================
    # TREND INDICATORS
    # ==========================================================================

    def sma(self, data: pd.Series | np.ndarray, period: int) -> np.ndarray:
        """Simple Moving Average with validation"""
        try:
            if len(data) < period:
                return np.full(len(data), np.nan)

            return pd.Series(data).rolling(window=period, min_periods=period).mean().values

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'sma', 'period': period})
            return np.full(len(data), np.nan)

    def ema(self, data: pd.Series | np.ndarray, period: int,
            alpha: float | None = None) -> np.ndarray:
        """Exponential Moving Average with custom alpha"""
        try:
            if alpha is None:
                alpha = 2.0 / (period + 1)

            data_series = pd.Series(data)
            return data_series.ewm(alpha=alpha, adjust=False).mean().values

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'ema', 'period': period})
            return np.full(len(data), np.nan)

    def hull_ma(self, data: pd.Series | np.ndarray, period: int) -> np.ndarray:
        """Hull Moving Average - reduced lag moving average"""
        try:
            half_period = int(period / 2)
            sqrt_period = int(math.sqrt(period))

            wma_half = self.wma(data, half_period)
            wma_full = self.wma(data, period)

            # 2 * WMA(n/2) - WMA(n)
            raw_hull = 2 * wma_half - wma_full

            # Apply WMA with period sqrt(n)
            return self.wma(raw_hull, sqrt_period)

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'hull_ma', 'period': period})
            return np.full(len(data), np.nan)

    def wma(self, data: pd.Series | np.ndarray, period: int) -> np.ndarray:
        """Weighted Moving Average"""
        try:
            data_series = pd.Series(data)
            weights = np.arange(1, period + 1)

            def weighted_avg(x):
                if len(x) < period:
                    return np.nan
                return np.average(x, weights=weights)

            return data_series.rolling(window=period).apply(weighted_avg, raw=True).values

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'wma', 'period': period})
            return np.full(len(data), np.nan)

    def macd(self, data: pd.Series | np.ndarray, fast: int = 12,
             slow: int = 26, signal: int = 9) -> dict[str, np.ndarray]:
        """MACD with signal generation"""
        try:
            data_series = pd.Series(data)

            # Calculate MACD line
            ema_fast = data_series.ewm(span=fast, adjust=False).mean()
            ema_slow = data_series.ewm(span=slow, adjust=False).mean()
            macd_line = ema_fast - ema_slow

            # Signal line
            signal_line = macd_line.ewm(span=signal, adjust=False).mean()

            # Histogram
            histogram = macd_line - signal_line

            return {
                'macd': macd_line.values,
                'signal': signal_line.values,
                'histogram': histogram.values
            }

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'macd'})
            return {
                'macd': np.full(len(data), np.nan),
                'signal': np.full(len(data), np.nan),
                'histogram': np.full(len(data), np.nan)
            }

    def adx(self, high: np.ndarray, low: np.ndarray, close: np.ndarray,
            period: int = 14) -> dict[str, np.ndarray]:
        """Average Directional Index with DI+ and DI-"""
        try:
            # Calculate True Range and Directional Movements
            tr = self.true_range(high, low, close)

            # Directional movements
            dm_plus = np.where((high[1:] - high[:-1]) > (low[:-1] - low[1:]),
                              np.maximum(high[1:] - high[:-1], 0), 0)
            dm_minus = np.where((low[:-1] - low[1:]) > (high[1:] - high[:-1]),
                               np.maximum(low[:-1] - low[1:], 0), 0)

            # Pad with zero for first element
            dm_plus = np.concatenate([[0], dm_plus])
            dm_minus = np.concatenate([[0], dm_minus])

            # Smooth the values
            tr_smooth = pd.Series(tr).ewm(span=period, adjust=False).mean().values
            dm_plus_smooth = pd.Series(dm_plus).ewm(span=period, adjust=False).mean().values
            dm_minus_smooth = pd.Series(dm_minus).ewm(span=period, adjust=False).mean().values

            # Calculate DI+ and DI-
            di_plus = 100 * dm_plus_smooth / tr_smooth
            di_minus = 100 * dm_minus_smooth / tr_smooth

            # Calculate DX
            dx = 100 * np.abs(di_plus - di_minus) / (di_plus + di_minus + 1e-10)

            # Calculate ADX
            adx_values = pd.Series(dx).ewm(span=period, adjust=False).mean().values

            return {
                'adx': adx_values,
                'di_plus': di_plus,
                'di_minus': di_minus
            }

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'adx'})
            return {
                'adx': np.full(len(high), np.nan),
                'di_plus': np.full(len(high), np.nan),
                'di_minus': np.full(len(high), np.nan)
            }

    # ==========================================================================
    # MOMENTUM INDICATORS
    # ==========================================================================

    def rsi(self, data: pd.Series | np.ndarray, period: int = 14) -> np.ndarray:
        """Relative Strength Index with proper handling"""
        try:
            data_series = pd.Series(data)
            delta = data_series.diff()

            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)

            avg_gain = gain.ewm(span=period, adjust=False).mean()
            avg_loss = loss.ewm(span=period, adjust=False).mean()

            rs = avg_gain / (avg_loss + 1e-10)  # Avoid division by zero
            rsi_values = 100 - (100 / (1 + rs))

            return rsi_values.values

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'rsi', 'period': period})
            return np.full(len(data), np.nan)

    def stochastic(self, high: np.ndarray, low: np.ndarray, close: np.ndarray,
                   k_period: int = 14, d_period: int = 3) -> dict[str, np.ndarray]:
        """Stochastic Oscillator"""
        try:
            # Calculate %K
            lowest_low = pd.Series(low).rolling(window=k_period).min()
            highest_high = pd.Series(high).rolling(window=k_period).max()

            k_percent = 100 * (close - lowest_low) / (highest_high - lowest_low + 1e-10)

            # Calculate %D (SMA of %K)
            d_percent = pd.Series(k_percent).rolling(window=d_period).mean()

            return {
                'k_percent': k_percent.values,
                'd_percent': d_percent.values
            }

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'stochastic'})
            return {
                'k_percent': np.full(len(high), np.nan),
                'd_percent': np.full(len(high), np.nan)
            }

    def williams_r(self, high: np.ndarray, low: np.ndarray, close: np.ndarray,
                   period: int = 14) -> np.ndarray:
        """Williams %R"""
        try:
            highest_high = pd.Series(high).rolling(window=period).max()
            lowest_low = pd.Series(low).rolling(window=period).min()

            williams_r = -100 * (highest_high - close) / (highest_high - lowest_low + 1e-10)

            return williams_r.values

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'williams_r'})
            return np.full(len(high), np.nan)

    def cci(self, high: np.ndarray, low: np.ndarray, close: np.ndarray,
            period: int = 20) -> np.ndarray:
        """Commodity Channel Index"""
        try:
            typical_price = (high + low + close) / 3
            sma_tp = pd.Series(typical_price).rolling(window=period).mean()

            # Mean deviation
            mad = pd.Series(typical_price).rolling(window=period).apply(
                lambda x: np.mean(np.abs(x - x.mean())), raw=True
            )

            cci_values = (typical_price - sma_tp) / (0.015 * mad)

            return cci_values.values

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'cci'})
            return np.full(len(high), np.nan)

    # ==========================================================================
    # VOLATILITY INDICATORS
    # ==========================================================================

    def bollinger_bands(self, data: pd.Series | np.ndarray, period: int = 20,
                       std_multiplier: float = 2.0) -> dict[str, np.ndarray]:
        """Bollinger Bands with squeeze detection"""
        try:
            data_series = pd.Series(data)

            # Calculate bands
            sma = data_series.rolling(window=period).mean()
            std = data_series.rolling(window=period).std()

            upper = sma + (std_multiplier * std)
            lower = sma - (std_multiplier * std)

            # Band width for squeeze detection
            band_width = (upper - lower) / sma

            # %B (position within bands)
            percent_b = (data_series - lower) / (upper - lower)

            return {
                'upper': upper.values,
                'middle': sma.values,
                'lower': lower.values,
                'width': band_width.values,
                'percent_b': percent_b.values
            }

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'bollinger_bands'})
            return {
                'upper': np.full(len(data), np.nan),
                'middle': np.full(len(data), np.nan),
                'lower': np.full(len(data), np.nan),
                'width': np.full(len(data), np.nan),
                'percent_b': np.full(len(data), np.nan)
            }

    def atr(self, high: np.ndarray, low: np.ndarray, close: np.ndarray,
            period: int = 14) -> np.ndarray:
        """Average True Range"""
        try:
            tr = self.true_range(high, low, close)
            return pd.Series(tr).rolling(window=period).mean().values

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'atr'})
            return np.full(len(high), np.nan)

    def true_range(self, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
        """True Range calculation"""
        try:
            # Handle first element
            tr = np.zeros(len(high))
            tr[0] = high[0] - low[0]

            for i in range(1, len(high)):
                tr[i] = max(
                    high[i] - low[i],
                    abs(high[i] - close[i-1]),
                    abs(low[i] - close[i-1])
                )

            return tr

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'true_range'})
            return np.full(len(high), np.nan)

    def keltner_channels(self, high: np.ndarray, low: np.ndarray, close: np.ndarray,
                        period: int = 20, atr_multiplier: float = 2.0) -> dict[str, np.ndarray]:
        """Keltner Channels"""
        try:
            ema_close = self.ema(close, period)
            atr_values = self.atr(high, low, close, period)

            upper = ema_close + (atr_multiplier * atr_values)
            lower = ema_close - (atr_multiplier * atr_values)

            return {
                'upper': upper,
                'middle': ema_close,
                'lower': lower
            }

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'keltner_channels'})
            return {
                'upper': np.full(len(high), np.nan),
                'middle': np.full(len(high), np.nan),
                'lower': np.full(len(high), np.nan)
            }

    # ==========================================================================
    # VOLUME INDICATORS
    # ==========================================================================

    def obv(self, close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """On-Balance Volume"""
        try:
            obv_values = np.zeros(len(close))
            obv_values[0] = volume[0]

            for i in range(1, len(close)):
                if close[i] > close[i-1]:
                    obv_values[i] = obv_values[i-1] + volume[i]
                elif close[i] < close[i-1]:
                    obv_values[i] = obv_values[i-1] - volume[i]
                else:
                    obv_values[i] = obv_values[i-1]

            return obv_values

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'obv'})
            return np.full(len(close), np.nan)

    def vwap(self, high: np.ndarray, low: np.ndarray, close: np.ndarray,
             volume: np.ndarray) -> np.ndarray:
        """Volume Weighted Average Price"""
        try:
            typical_price = (high + low + close) / 3
            cumulative_tp_volume = np.cumsum(typical_price * volume)
            cumulative_volume = np.cumsum(volume)

            return cumulative_tp_volume / (cumulative_volume + 1e-10)

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'vwap'})
            return np.full(len(high), np.nan)

    def mfi(self, high: np.ndarray, low: np.ndarray, close: np.ndarray,
            volume: np.ndarray, period: int = 14) -> np.ndarray:
        """Money Flow Index"""
        try:
            typical_price = (high + low + close) / 3
            money_flow = typical_price * volume

            # Positive and negative money flow
            positive_flow = np.where(np.diff(typical_price, prepend=typical_price[0]) > 0,
                                   money_flow[1:], 0)
            negative_flow = np.where(np.diff(typical_price, prepend=typical_price[0]) < 0,
                                   money_flow[1:], 0)

            # Pad with zeros
            positive_flow = np.concatenate([[0], positive_flow])
            negative_flow = np.concatenate([[0], negative_flow])

            # Calculate MFI
            positive_mf = pd.Series(positive_flow).rolling(window=period).sum()
            negative_mf = pd.Series(negative_flow).rolling(window=period).sum()

            money_ratio = positive_mf / (negative_mf + 1e-10)
            mfi_values = 100 - (100 / (1 + money_ratio))

            return mfi_values.values

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'mfi'})
            return np.full(len(high), np.nan)

    # ==========================================================================
    # SUPPORT/RESISTANCE DETECTION
    # ==========================================================================

    def find_pivot_points(self, high: np.ndarray, low: np.ndarray, close: np.ndarray,
                          method: str = 'standard') -> dict[str, float]:
        """Calculate pivot points"""
        try:
            h = high[-1] if len(high) > 0 else 0
            lo = low[-1] if len(low) > 0 else 0
            c = close[-1] if len(close) > 0 else 0

            if method == 'standard':
                pivot = (h + lo + c) / 3
                r1 = 2 * pivot - lo
                s1 = 2 * pivot - h
                r2 = pivot + (h - lo)
                s2 = pivot - (h - lo)
                r3 = h + 2 * (pivot - lo)
                s3 = lo - 2 * (h - pivot)

            elif method == 'fibonacci':
                pivot = (h + lo + c) / 3
                r1 = pivot + 0.382 * (h - lo)
                s1 = pivot - 0.382 * (h - lo)
                r2 = pivot + 0.618 * (h - lo)
                s2 = pivot - 0.618 * (h - lo)
                r3 = pivot + (h - lo)
                s3 = pivot - (h - lo)

            else:  # camarilla
                pivot = (h + lo + c) / 3
                r1 = c + 1.1 * (h - lo) / 12
                s1 = c - 1.1 * (h - lo) / 12
                r2 = c + 1.1 * (h - lo) / 6
                s2 = c - 1.1 * (h - lo) / 6
                r3 = c + 1.1 * (h - lo) / 4
                s3 = c - 1.1 * (h - lo) / 4

            return {
                'pivot': pivot,
                'r1': r1, 'r2': r2, 'r3': r3,
                's1': s1, 's2': s2, 's3': s3
            }

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'find_pivot_points'})
            return {}

    def detect_support_resistance(self, high: np.ndarray, low: np.ndarray,
                                 close: np.ndarray, window: int = 20,
                                 min_touches: int = 2) -> list[SupportResistanceLevel]:
        """Detect support and resistance levels"""
        try:
            levels = []

            # Find local highs and lows
            for i in range(window, len(high) - window):
                # Check for local high
                if all(high[i] >= high[j] for j in range(i-window, i+window+1) if j != i):
                    level = SupportResistanceLevel(
                        price_level=high[i],
                        level_type='resistance',
                        strength=0.5,  # Will be calculated
                        touches=1,
                        age=len(high) - i,
                        volume_confirmation=False
                    )
                    levels.append(level)

                # Check for local low
                if all(low[i] <= low[j] for j in range(i-window, i+window+1) if j != i):
                    level = SupportResistanceLevel(
                        price_level=low[i],
                        level_type='support',
                        strength=0.5,  # Will be calculated
                        touches=1,
                        age=len(low) - i,
                        volume_confirmation=False
                    )
                    levels.append(level)

            # Merge nearby levels and count touches
            merged_levels = self._merge_nearby_levels(levels, close[-1] * 0.002)  # 0.2% threshold

            # Filter by minimum touches
            return [level for level in merged_levels if level.touches >= min_touches]

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'detect_support_resistance'})
            return []

    def _merge_nearby_levels(self, levels: list[SupportResistanceLevel],
                            threshold: float) -> list[SupportResistanceLevel]:
        """Merge nearby support/resistance levels"""
        if not levels:
            return []

        merged = []
        levels.sort(key=lambda x: x.price_level)

        current_level = levels[0]

        for level in levels[1:]:
            if abs(level.price_level - current_level.price_level) <= threshold:
                # Merge levels
                current_level.touches += level.touches
                current_level.price_level = (current_level.price_level + level.price_level) / 2
                current_level.strength = max(current_level.strength, level.strength)
            else:
                merged.append(current_level)
                current_level = level

        merged.append(current_level)
        return merged

    # ==========================================================================
    # SIGNAL GENERATION AND ANALYSIS
    # ==========================================================================

    def generate_trend_signals(self, data: pd.DataFrame) -> list[IndicatorSignal]:
        """Generate trend-based signals"""
        signals = []

        try:
            close = data['close'].values
            high = data['high'].values
            low = data['low'].values

            # MACD signals
            macd_data = self.macd(close)
            if not np.isnan(macd_data['macd'][-1]):
                signals.extend(self._analyze_macd_signals(macd_data, close[-1]))

            # ADX signals
            adx_data = self.adx(high, low, close)
            if not np.isnan(adx_data['adx'][-1]):
                signals.extend(self._analyze_adx_signals(adx_data, close[-1]))

            # Moving average signals
            signals.extend(self._analyze_ma_signals(close, close[-1]))

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'generate_trend_signals'})

        return signals

    def generate_momentum_signals(self, data: pd.DataFrame) -> list[IndicatorSignal]:
        """Generate momentum-based signals"""
        signals = []

        try:
            close = data['close'].values
            high = data['high'].values
            low = data['low'].values

            # RSI signals
            rsi_values = self.rsi(close)
            if not np.isnan(rsi_values[-1]):
                signals.extend(self._analyze_rsi_signals(rsi_values, close[-1]))

            # Stochastic signals
            stoch_data = self.stochastic(high, low, close)
            if not np.isnan(stoch_data['k_percent'][-1]):
                signals.extend(self._analyze_stochastic_signals(stoch_data, close[-1]))

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'generate_momentum_signals'})

        return signals

    def generate_volatility_signals(self, data: pd.DataFrame) -> list[IndicatorSignal]:
        """Generate volatility-based signals"""
        signals = []

        try:
            close = data['close'].values
            high = data['high'].values
            low = data['low'].values

            # Bollinger Bands signals
            bb_data = self.bollinger_bands(close)
            if not np.isnan(bb_data['upper'][-1]):
                signals.extend(self._analyze_bollinger_signals(bb_data, close[-1]))

            # ATR signals for volatility regime
            atr_values = self.atr(high, low, close)
            if not np.isnan(atr_values[-1]):
                signals.extend(self._analyze_volatility_regime(atr_values, close[-1]))

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'generate_volatility_signals'})

        return signals

    # ==========================================================================
    # SIGNAL ANALYSIS METHODS
    # ==========================================================================

    def _analyze_macd_signals(self, macd_data: dict[str, np.ndarray],
                             current_price: float) -> list[IndicatorSignal]:
        """Analyze MACD for signals"""
        signals = []

        try:
            macd = macd_data['macd']
            signal = macd_data['signal']
            histogram = macd_data['histogram']

            if len(macd) < 2:
                return signals

            # MACD line crossing signal line
            if macd[-2] <= signal[-2] and macd[-1] > signal[-1]:
                confidence = min(0.9, abs(histogram[-1]) / (abs(macd[-1]) + 1e-10))
                signals.append(IndicatorSignal(
                    indicator_name='MACD',
                    signal_type=SignalType.BULLISH,
                    strength=self._calculate_signal_strength(confidence),
                    confidence=confidence,
                    value=macd[-1],
                    timestamp=datetime.now(UTC),
                    current_price=current_price
                ))

            elif macd[-2] >= signal[-2] and macd[-1] < signal[-1]:
                confidence = min(0.9, abs(histogram[-1]) / (abs(macd[-1]) + 1e-10))
                signals.append(IndicatorSignal(
                    indicator_name='MACD',
                    signal_type=SignalType.BEARISH,
                    strength=self._calculate_signal_strength(confidence),
                    confidence=confidence,
                    value=macd[-1],
                    timestamp=datetime.now(UTC),
                    current_price=current_price
                ))

            # Histogram divergence
            if len(histogram) >= 5:
                if self._detect_divergence(histogram[-5:]):
                    signals.append(IndicatorSignal(
                        indicator_name='MACD',
                        signal_type=SignalType.DIVERGENCE,
                        strength=IndicatorStrength.MODERATE,
                        confidence=0.6,
                        value=histogram[-1],
                        timestamp=datetime.now(UTC),
                        current_price=current_price
                    ))

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_analyze_macd_signals'})

        return signals

    def _analyze_rsi_signals(self, rsi_values: np.ndarray,
                            current_price: float) -> list[IndicatorSignal]:
        """Analyze RSI for overbought/oversold signals"""
        signals = []

        try:
            if len(rsi_values) < 2:
                return signals

            current_rsi = rsi_values[-1]

            # Overbought condition
            if current_rsi > 70:
                if len(rsi_values) >= 3 and rsi_values[-2] <= 70:
                    confidence = min(0.9, (current_rsi - 70) / 30)
                    signals.append(IndicatorSignal(
                        indicator_name='RSI',
                        signal_type=SignalType.BEARISH,
                        strength=self._calculate_signal_strength(confidence),
                        confidence=confidence,
                        value=current_rsi,
                        timestamp=datetime.now(UTC),
                        current_price=current_price
                    ))

            # Oversold condition
            elif current_rsi < 30:
                if len(rsi_values) >= 3 and rsi_values[-2] >= 30:
                    confidence = min(0.9, (30 - current_rsi) / 30)
                    signals.append(IndicatorSignal(
                        indicator_name='RSI',
                        signal_type=SignalType.BULLISH,
                        strength=self._calculate_signal_strength(confidence),
                        confidence=confidence,
                        value=current_rsi,
                        timestamp=datetime.now(UTC),
                        current_price=current_price
                    ))

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_analyze_rsi_signals'})

        return signals

    def _analyze_bollinger_signals(self, bb_data: dict[str, np.ndarray],
                                  current_price: float) -> list[IndicatorSignal]:
        """Analyze Bollinger Bands for squeeze and breakout signals"""
        signals = []

        try:
            upper = bb_data['upper']
            bb_data['lower']
            width = bb_data['width']
            percent_b = bb_data['percent_b']

            if len(upper) < 2:
                return signals

            current_width = width[-1]
            current_percent_b = percent_b[-1]

            # Bollinger Band squeeze (low volatility)
            if len(width) >= 20:
                if current_width < np.percentile(width[-20:], 20):
                    signals.append(IndicatorSignal(
                        indicator_name='BollingerBands',
                        signal_type=SignalType.NEUTRAL,
                        strength=IndicatorStrength.MODERATE,
                        confidence=0.7,
                        value=current_width,
                        timestamp=datetime.now(UTC),
                        current_price=current_price
                    ))

            # Band breakouts
            if current_percent_b > 1.0:  # Above upper band
                signals.append(IndicatorSignal(
                    indicator_name='BollingerBands',
                    signal_type=SignalType.BREAKOUT,
                    strength=IndicatorStrength.STRONG,
                    confidence=min(0.9, current_percent_b - 1.0),
                    value=current_percent_b,
                    timestamp=datetime.now(UTC),
                    current_price=current_price
                ))

            elif current_percent_b < 0.0:  # Below lower band
                signals.append(IndicatorSignal(
                    indicator_name='BollingerBands',
                    signal_type=SignalType.BREAKDOWN,
                    strength=IndicatorStrength.STRONG,
                    confidence=min(0.9, abs(current_percent_b)),
                    value=current_percent_b,
                    timestamp=datetime.now(UTC),
                    current_price=current_price
                ))

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_analyze_bollinger_signals'})

        return signals

    def _analyze_adx_signals(self, adx_data: dict[str, np.ndarray],
                            current_price: float) -> list[IndicatorSignal]:
        """Analyze ADX for trend strength signals"""
        signals = []

        try:
            adx = adx_data['adx']
            di_plus = adx_data['di_plus']
            di_minus = adx_data['di_minus']

            if len(adx) < 2:
                return signals

            current_adx = adx[-1]

            # Strong trend detection
            if current_adx > 25:
                if di_plus[-1] > di_minus[-1]:
                    confidence = min(0.9, current_adx / 50)
                    signals.append(IndicatorSignal(
                        indicator_name='ADX',
                        signal_type=SignalType.BULLISH,
                        strength=self._calculate_signal_strength(confidence),
                        confidence=confidence,
                        value=current_adx,
                        timestamp=datetime.now(UTC),
                        current_price=current_price
                    ))
                else:
                    confidence = min(0.9, current_adx / 50)
                    signals.append(IndicatorSignal(
                        indicator_name='ADX',
                        signal_type=SignalType.BEARISH,
                        strength=self._calculate_signal_strength(confidence),
                        confidence=confidence,
                        value=current_adx,
                        timestamp=datetime.now(UTC),
                        current_price=current_price
                    ))

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_analyze_adx_signals'})

        return signals

    def _analyze_stochastic_signals(self, stoch_data: dict[str, np.ndarray],
                                   current_price: float) -> list[IndicatorSignal]:
        """Analyze Stochastic for overbought/oversold signals"""
        signals = []

        try:
            k_percent = stoch_data['k_percent']
            d_percent = stoch_data['d_percent']

            if len(k_percent) < 2:
                return signals

            current_k = k_percent[-1]
            current_d = d_percent[-1]

            # Overbought condition
            if current_k > 80 and current_d > 80:
                if len(k_percent) >= 3 and k_percent[-2] <= 80:
                    confidence = min(0.8, (current_k - 80) / 20)
                    signals.append(IndicatorSignal(
                        indicator_name='Stochastic',
                        signal_type=SignalType.BEARISH,
                        strength=self._calculate_signal_strength(confidence),
                        confidence=confidence,
                        value=current_k,
                        timestamp=datetime.now(UTC),
                        current_price=current_price
                    ))

            # Oversold condition
            elif current_k < 20 and current_d < 20:
                if len(k_percent) >= 3 and k_percent[-2] >= 20:
                    confidence = min(0.8, (20 - current_k) / 20)
                    signals.append(IndicatorSignal(
                        indicator_name='Stochastic',
                        signal_type=SignalType.BULLISH,
                        strength=self._calculate_signal_strength(confidence),
                        confidence=confidence,
                        value=current_k,
                        timestamp=datetime.now(UTC),
                        current_price=current_price
                    ))

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_analyze_stochastic_signals'})

        return signals

    def _analyze_ma_signals(self, close: np.ndarray, current_price: float) -> list[IndicatorSignal]:
        """Analyze moving average signals"""
        signals = []

        try:
            if len(close) < 50:
                return signals

            # Calculate multiple moving averages
            sma_20 = self.sma(close, 20)
            sma_50 = self.sma(close, 50)
            self.ema(close, 12)

            # Golden cross / Death cross
            if len(sma_20) >= 2 and len(sma_50) >= 2:
                if sma_20[-2] <= sma_50[-2] and sma_20[-1] > sma_50[-1]:
                    signals.append(IndicatorSignal(
                        indicator_name='MovingAverage',
                        signal_type=SignalType.BULLISH,
                        strength=IndicatorStrength.STRONG,
                        confidence=0.8,
                        value=sma_20[-1],
                        timestamp=datetime.now(UTC),
                        current_price=current_price
                    ))

                elif sma_20[-2] >= sma_50[-2] and sma_20[-1] < sma_50[-1]:
                    signals.append(IndicatorSignal(
                        indicator_name='MovingAverage',
                        signal_type=SignalType.BEARISH,
                        strength=IndicatorStrength.STRONG,
                        confidence=0.8,
                        value=sma_20[-1],
                        timestamp=datetime.now(UTC),
                        current_price=current_price
                    ))

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_analyze_ma_signals'})

        return signals

    def _analyze_volatility_regime(self, atr_values: np.ndarray,
                                  current_price: float) -> list[IndicatorSignal]:
        """Analyze volatility regime changes"""
        signals = []

        try:
            if len(atr_values) < 20:
                return signals

            current_atr = atr_values[-1]
            atr_percentile = np.percentile(atr_values[-20:], 50)

            # Volatility expansion
            if current_atr > atr_percentile * 1.5:
                signals.append(IndicatorSignal(
                    indicator_name='VolatilityRegime',
                    signal_type=SignalType.BREAKOUT,
                    strength=IndicatorStrength.MODERATE,
                    confidence=0.7,
                    value=current_atr,
                    timestamp=datetime.now(UTC),
                    current_price=current_price
                ))

            # Volatility contraction
            elif current_atr < atr_percentile * 0.7:
                signals.append(IndicatorSignal(
                    indicator_name='VolatilityRegime',
                    signal_type=SignalType.NEUTRAL,
                    strength=IndicatorStrength.MODERATE,
                    confidence=0.6,
                    value=current_atr,
                    timestamp=datetime.now(UTC),
                    current_price=current_price
                ))

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_analyze_volatility_regime'})

        return signals

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def _calculate_signal_strength(self, confidence: float) -> IndicatorStrength:
        """Convert confidence to signal strength enum"""
        if confidence >= STRONG_SIGNAL_THRESHOLD:
            return IndicatorStrength.VERY_STRONG
        elif confidence >= MODERATE_SIGNAL_THRESHOLD:
            return IndicatorStrength.STRONG
        elif confidence >= WEAK_SIGNAL_THRESHOLD:
            return IndicatorStrength.MODERATE
        else:
            return IndicatorStrength.WEAK

    def _detect_divergence(self, values: np.ndarray) -> bool:
        """Detect bullish/bearish divergence in indicator values"""
        try:
            if len(values) < 3:
                return False

            # Simple divergence detection
            trend = np.polyfit(range(len(values)), values, 1)[0]
            return abs(trend) > 0.01  # Threshold for meaningful divergence

        except Exception:
            return False

    def get_all_signals(self, data: pd.DataFrame) -> dict[str, list[IndicatorSignal]]:
        """Get all technical signals categorized"""
        return {
            'trend_signals': self.generate_trend_signals(data),
            'momentum_signals': self.generate_momentum_signals(data),
            'volatility_signals': self.generate_volatility_signals(data)
        }

    def get_signal_summary(self, data: pd.DataFrame) -> dict[str, Any]:
        """Get comprehensive signal summary"""
        all_signals = self.get_all_signals(data)

        total_signals = sum(len(signals) for signals in all_signals.values())
        bullish_signals = sum(1 for signals in all_signals.values()
                             for signal in signals
                             if signal.signal_type == SignalType.BULLISH)
        bearish_signals = sum(1 for signals in all_signals.values()
                             for signal in signals
                             if signal.signal_type == SignalType.BEARISH)

        return {
            'total_signals': total_signals,
            'bullish_signals': bullish_signals,
            'bearish_signals': bearish_signals,
            'signal_breakdown': {k: len(v) for k, v in all_signals.items()},
            'net_bias': 'bullish' if bullish_signals > bearish_signals else 'bearish' if bearish_signals > bullish_signals else 'neutral',  # noqa: E501
            'signal_strength': 'strong' if total_signals > 5 else 'moderate' if total_signals > 2 else 'weak'  # noqa: E501
        }

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_technical_indicators() -> CoreTechnicalIndicators:
    """Create technical indicators instance"""
    return CoreTechnicalIndicators()

# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":

    # Create indicators engine
    indicators = create_technical_indicators()

    # Generate sample market data
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=200, freq='D')

    # Create realistic price movement
    base_price = 450
    returns = np.random.randn(200) * 0.02  # 2% daily volatility
    prices = base_price * np.exp(np.cumsum(returns))

    # Add some trend
    trend = np.linspace(0, 50, 200)
    prices = prices + trend

    # Create OHLCV data
    high = prices + np.abs(np.random.randn(200) * 2)
    low = prices - np.abs(np.random.randn(200) * 2)
    volume = np.random.randint(1000000, 5000000, 200)

    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': np.roll(prices, 1),
        'high': high,
        'low': low,
        'close': prices,
        'volume': volume
    })


    # Test individual indicators

    # Moving averages
    sma_20 = indicators.sma(prices, 20)
    ema_20 = indicators.ema(prices, 20)

    # MACD
    macd_data = indicators.macd(prices)

    # RSI
    rsi_values = indicators.rsi(prices)

    # Bollinger Bands
    bb_data = indicators.bollinger_bands(prices)

    # ATR
    atr_values = indicators.atr(high, low, prices)

    # ADX
    adx_data = indicators.adx(high, low, prices)

    # Test signal generation

    all_signals = indicators.get_all_signals(market_data)

    for _category, signals in all_signals.items():
        for _signal in signals:
            pass

    # Signal summary
    summary = indicators.get_signal_summary(market_data)

    # Test support/resistance detection

    sr_levels = indicators.detect_support_resistance(high, low, prices)

    for _level in sr_levels[-5:]:  # Show last 5 levels
        pass

    # Test pivot points
    pivots = indicators.find_pivot_points(high, low, prices, method='standard')
    if pivots:
        pass

    # Test volume indicators

    obv_values = indicators.obv(prices, volume)
    vwap_values = indicators.vwap(high, low, prices, volume)
    mfi_values = indicators.mfi(high, low, prices, volume)
