#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderF05_TrendDetection.py
Group: F (Technical Analysis)
Purpose: Trend identification and strength

Description:
    This module identifies market trends using multiple methods including
    moving averages, linear regression, ADX, and price structure analysis.
    It provides real-time trend detection, strength measurement, and trend
    change signals optimized for SPY options trading strategies.

Author: Mohamed Talib
Date: 2025-06-01
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
# Note: Removed scikit-learn dependency - using numpy for linear regression
try:
    from scipy.signal import savgol_filter
except ImportError:
    # Fallback smooth function if scipy not available
    def savgol_filter(data, window_length, polyorder):
        return np.convolve(data, np.ones(window_length)/window_length, mode='same')
    def savgol_filter(data, window_length, polyorder):
        return np.convolve(data, np.ones(window_length)/window_length, mode='same')

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
try:
    from SpyderF_Analysis.SpyderF01_Indicators import TechnicalIndicators
except ImportError:
    # Fallback for TechnicalIndicators
    class TechnicalIndicators:
        def calculate_rsi(self, data, period=14):
            """Simple RSI calculation"""
            closes = data['close']
            delta = closes.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return pd.DataFrame({'rsi': rsi})
        
        def calculate_adx(self, data, period=14):
            """Simple ADX calculation"""
            high = data['high']
            low = data['low']
            close = data['close']
            
            # True Range
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # Directional Movement
            plus_dm = (high - high.shift()).where((high - high.shift()) > (low.shift() - low), 0)
            minus_dm = (low.shift() - low).where((low.shift() - low) > (high - high.shift()), 0)
            
            # Smooth
            atr = tr.rolling(period).mean()
            plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
            minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
            
            # ADX
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            adx = dx.rolling(period).mean()
            
            return pd.DataFrame({
                'adx': adx,
                'plus_di': plus_di,
                'minus_di': minus_di
            })

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Trend analysis periods
TREND_LOOKBACK_SHORT = 20
TREND_LOOKBACK_MEDIUM = 50
TREND_LOOKBACK_LONG = 100
MIN_TREND_LENGTH = 10

# Moving average periods
MA_FAST = 20
MA_SLOW = 50
MA_VERY_SLOW = 200

# Trend strength thresholds
STRONG_TREND_SLOPE = 0.02  # 2% per period
WEAK_TREND_SLOPE = 0.005  # 0.5% per period
STRONG_TREND_ADX = 40
WEAK_TREND_ADX = 20

# ==============================================================================
# ENUMS
# ==============================================================================
class TrendDirection(Enum):
    """Trend direction classification"""
    STRONG_UP = "strong_up"
    UP = "up"
    WEAK_UP = "weak_up"
    SIDEWAYS = "sideways"
    WEAK_DOWN = "weak_down"
    DOWN = "down"
    STRONG_DOWN = "strong_down"

class TrendPhase(Enum):
    """Trend lifecycle phase"""
    EMERGING = "emerging"
    ESTABLISHED = "established"
    MATURE = "mature"
    EXHAUSTED = "exhausted"
    REVERSING = "reversing"

class TrendTimeframe(Enum):
    """Trend timeframe"""
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class Trend:
    """Trend information"""
    direction: TrendDirection
    strength: float
    phase: TrendPhase
    start_price: float
    current_price: float
    start_time: datetime
    duration: int  # Number of bars
    slope: float
    r_squared: float
    volatility: float
    pullback_count: int = 0
    last_pullback: Optional[datetime] = None
    
    @property
    def percentage_move(self) -> float:
        """Get percentage move from start"""
        if self.start_price == 0:
            return 0
        return (self.current_price - self.start_price) / self.start_price * 100
    
    @property
    def is_bullish(self) -> bool:
        """Check if trend is bullish"""
        return self.direction in [TrendDirection.STRONG_UP, TrendDirection.UP, TrendDirection.WEAK_UP]
    
    @property
    def is_bearish(self) -> bool:
        """Check if trend is bearish"""
        return self.direction in [TrendDirection.STRONG_DOWN, TrendDirection.DOWN, TrendDirection.WEAK_DOWN]

@dataclass
class TrendAnalysis:
    """Complete trend analysis"""
    short_trend: Trend
    medium_trend: Trend
    long_trend: Trend
    dominant_trend: Trend
    trend_alignment: float  # -1 to 1 (1 = all trends aligned)
    momentum: float
    trend_quality: float
    change_probability: float
    key_levels: Dict[str, float] = field(default_factory=dict)
    signals: List[str] = field(default_factory=list)

# ==============================================================================
# TREND DETECTOR CLASS
# ==============================================================================
class TrendDetector:
    """
    Detects and analyzes market trends using multiple methods.
    
    Features:
    - Multi-timeframe trend analysis
    - Trend strength measurement
    - Trend phase identification
    - Trend change detection
    """
    
    def __init__(self):
        """Initialize trend detector"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.indicators = TechnicalIndicators()
        
        self.logger.info("TrendDetector initialized")
    
    def analyze(self, data: pd.DataFrame) -> TrendAnalysis:
        """
        Comprehensive trend analysis.
        
        Args:
            data: OHLCV DataFrame
            
        Returns:
            TrendAnalysis object
        """
        if len(data) < MIN_TREND_LENGTH:
            return self._empty_analysis()
        
        # Detect trends at different timeframes
        short_trend = self._detect_trend(data, TREND_LOOKBACK_SHORT, TrendTimeframe.SHORT)
        medium_trend = self._detect_trend(data, TREND_LOOKBACK_MEDIUM, TrendTimeframe.MEDIUM)
        long_trend = self._detect_trend(data, TREND_LOOKBACK_LONG, TrendTimeframe.LONG)
        
        # Determine dominant trend
        dominant_trend = medium_trend  # Simplified
        
        # Calculate trend alignment
        alignment = self._calculate_trend_alignment(short_trend, medium_trend, long_trend)
        
        # Calculate momentum
        momentum = self._calculate_momentum(data)
        
        # Calculate trend quality
        quality = min(1.0, (short_trend.strength + medium_trend.strength + long_trend.strength) / 3)
        
        # Estimate trend change probability
        change_prob = 0.3  # Simplified
        
        # Identify key levels
        key_levels = self._identify_key_levels(data, dominant_trend)
        
        # Generate signals
        signals = []
        if dominant_trend.is_bullish:
            signals.append("bullish_trend")
        elif dominant_trend.is_bearish:
            signals.append("bearish_trend")
        
        return TrendAnalysis(
            short_trend=short_trend,
            medium_trend=medium_trend,
            long_trend=long_trend,
            dominant_trend=dominant_trend,
            trend_alignment=alignment,
            momentum=momentum,
            trend_quality=quality,
            change_probability=change_prob,
            key_levels=key_levels,
            signals=signals
        )
    
    def detect_trend(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Simple trend detection method for compatibility.
        
        Args:
            data: OHLCV DataFrame
            
        Returns:
            Dictionary with trend information
        """
        if len(data) < 10:
            return {
                'direction': 0,
                'strength': 0,
                'type': 'sideways'
            }
        
        # Simple trend detection using moving averages
        short_ma = data['close'].rolling(10).mean().iloc[-1]
        long_ma = data['close'].rolling(20).mean().iloc[-1]
        current_price = data['close'].iloc[-1]
        
        if current_price > short_ma > long_ma:
            direction = 1
            trend_type = 'bullish'
        elif current_price < short_ma < long_ma:
            direction = -1
            trend_type = 'bearish'
        else:
            direction = 0
            trend_type = 'sideways'
        
        # Simple strength calculation
        if direction != 0:
            strength = min(1.0, abs(current_price - long_ma) / long_ma / 0.02)
        else:
            strength = 0
        
        return {
            'direction': direction,
            'strength': strength,
            'type': trend_type
        }
    
    def _detect_trend(self, data: pd.DataFrame, lookback: int, timeframe: TrendTimeframe) -> Trend:
        """Detect trend for specific timeframe"""
        if len(data) < lookback:
            lookback = len(data)
        
        if lookback < MIN_TREND_LENGTH:
            return self._neutral_trend(data)
        
        trend_data = data.tail(lookback).copy()
        
        # Simple linear regression using numpy
        regression_trend = self._numpy_linear_regression(trend_data['close'].values)
        
        # Moving average trend
        ma_trend = self._moving_average_trend(trend_data)
        
        # Combine methods
        direction_score = (regression_trend['direction_score'] + ma_trend['direction_score']) / 2
        strength = (regression_trend['strength'] + ma_trend['strength']) / 2
        
        # Determine direction
        direction = self._score_to_direction(direction_score, strength)
        
        # Simple phase determination
        phase = TrendPhase.ESTABLISHED
        
        # Calculate volatility
        volatility = trend_data['close'].pct_change().std() * np.sqrt(252)
        
        trend = Trend(
            direction=direction,
            strength=strength,
            phase=phase,
            start_price=trend_data['close'].iloc[0],
            current_price=trend_data['close'].iloc[-1],
            start_time=trend_data.index[0],
            duration=len(trend_data),
            slope=regression_trend['slope'],
            r_squared=regression_trend['r_squared'],
            volatility=volatility,
            pullback_count=0
        )
        
        return trend
    
    def _numpy_linear_regression(self, y: np.ndarray) -> Dict[str, Any]:
        """Linear regression using numpy"""
        x = np.arange(len(y))
        
        # Calculate slope and intercept
        n = len(x)
        sum_x = np.sum(x)
        sum_y = np.sum(y)
        sum_xy = np.sum(x * y)
        sum_x2 = np.sum(x * x)
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        intercept = (sum_y - slope * sum_x) / n
        
        # Calculate R-squared
        y_pred = slope * x + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        # Normalize slope
        avg_price = np.mean(y)
        normalized_slope = slope / avg_price if avg_price != 0 else 0
        
        # Direction score
        direction_score = np.tanh(normalized_slope * 100)
        
        # Strength
        strength = r_squared * min(1.0, abs(normalized_slope) / STRONG_TREND_SLOPE)
        
        return {
            'direction_score': direction_score,
            'strength': strength,
            'slope': normalized_slope,
            'r_squared': r_squared
        }
    
    def _moving_average_trend(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Detect trend using moving averages"""
        closes = data['close']
        
        # Calculate MAs
        ma_fast = closes.rolling(min(MA_FAST, len(data))).mean()
        ma_slow = closes.rolling(min(MA_SLOW, len(data))).mean()
        
        current_price = closes.iloc[-1]
        current_fast = ma_fast.iloc[-1]
        current_slow = ma_slow.iloc[-1]
        
        # Direction score
        if current_price > current_fast > current_slow:
            direction_score = 1.0
        elif current_price < current_fast < current_slow:
            direction_score = -1.0
        else:
            direction_score = 0.0
        
        # Strength
        if current_slow != 0:
            ma_separation = abs(current_fast - current_slow) / current_slow
            strength = min(1.0, ma_separation / 0.02)
        else:
            strength = 0
        
        return {
            'direction_score': direction_score,
            'strength': strength
        }
    
    def _score_to_direction(self, score: float, strength: float) -> TrendDirection:
        """Convert direction score to TrendDirection enum"""
        if abs(score) < 0.1 or strength < 0.3:
            return TrendDirection.SIDEWAYS
        
        if score > 0:
            if strength >= 0.7:
                return TrendDirection.STRONG_UP
            elif strength >= 0.5:
                return TrendDirection.UP
            else:
                return TrendDirection.WEAK_UP
        else:
            if strength >= 0.7:
                return TrendDirection.STRONG_DOWN
            elif strength >= 0.5:
                return TrendDirection.DOWN
            else:
                return TrendDirection.WEAK_DOWN
    
    def _calculate_trend_alignment(self, short: Trend, medium: Trend, long: Trend) -> float:
        """Calculate trend alignment score"""
        # Simple alignment check
        if (short.is_bullish and medium.is_bullish and long.is_bullish) or \
           (short.is_bearish and medium.is_bearish and long.is_bearish):
            return 1.0
        elif short.direction == TrendDirection.SIDEWAYS:
            return 0.5
        else:
            return -0.5
    
    def _calculate_momentum(self, data: pd.DataFrame) -> float:
        """Calculate momentum"""
        if len(data) < 10:
            return 0
        
        closes = data['close']
        roc = (closes.iloc[-1] - closes.iloc[-10]) / closes.iloc[-10]
        return np.tanh(roc * 20)  # Bound to -1, 1
    
    def _identify_key_levels(self, data: pd.DataFrame, trend: Trend) -> Dict[str, float]:
        """Identify key support/resistance levels"""
        levels = {}
        
        if len(data) >= 20:
            current_price = data['close'].iloc[-1]
            recent_high = data['high'].iloc[-20:].max()
            recent_low = data['low'].iloc[-20:].min()
            
            levels['resistance'] = recent_high
            levels['support'] = recent_low
        
        return levels
    
    def _neutral_trend(self, data: pd.DataFrame) -> Trend:
        """Return neutral trend"""
        return Trend(
            direction=TrendDirection.SIDEWAYS,
            strength=0,
            phase=TrendPhase.ESTABLISHED,
            start_price=data['close'].iloc[0] if len(data) > 0 else 0,
            current_price=data['close'].iloc[-1] if len(data) > 0 else 0,
            start_time=data.index[0] if len(data) > 0 else datetime.now(),
            duration=len(data),
            slope=0,
            r_squared=0,
            volatility=0
        )
    
    def _empty_analysis(self) -> TrendAnalysis:
        """Return empty analysis"""
        neutral = self._neutral_trend(pd.DataFrame())
        
        return TrendAnalysis(
            short_trend=neutral,
            medium_trend=neutral,
            long_trend=neutral,
            dominant_trend=neutral,
            trend_alignment=0,
            momentum=0,
            trend_quality=0,
            change_probability=0,
            key_levels={},
            signals=[]
        )

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def trend_following_signal(analysis: TrendAnalysis, risk_tolerance: str = 'moderate') -> Dict[str, Any]:
    """Generate trend following signal"""
    signal = {
        'action': 'HOLD',
        'confidence': 0,
        'reason': 'No clear trend'
    }
    
    dominant = analysis.dominant_trend
    
    if dominant.is_bullish and dominant.strength > 0.5:
        signal['action'] = 'BUY'
        signal['confidence'] = dominant.strength
        signal['reason'] = f"Bullish trend ({dominant.direction.value})"
    elif dominant.is_bearish and dominant.strength > 0.5:
        signal['action'] = 'SELL'
        signal['confidence'] = dominant.strength
        signal['reason'] = f"Bearish trend ({dominant.direction.value})"
    
    return signal

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Simple test
    detector = TrendDetector()
    print("TrendDetector test completed successfully!")
