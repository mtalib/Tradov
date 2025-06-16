#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderF02_PriceAction.py
Group: F (Technical Analysis)
Purpose: Price action and pattern recognition

Description:
    This module analyzes price action patterns and candlestick formations
    for trading signal generation. It identifies key patterns such as
    pin bars, engulfing patterns, inside bars, and complex formations
    like head and shoulders. The module provides real-time pattern
    detection optimized for SPY options trading.

Author: Mohamed Talib
Date: 2025-06-01
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum, auto
import math
import statistics

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from scipy.signal import find_peaks

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU07_Constants import LATENCY_SAMPLE_SIZE

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Pattern recognition settings
MIN_PATTERN_STRENGTH = 0.6
PATTERN_LOOKBACK = 50
CONFIRMATION_BARS = 2

# Price action thresholds
PIN_BAR_RATIO = 0.6        # Wick to body ratio for pin bars
DOJI_BODY_PERCENT = 0.1    # Max body size for doji (% of range)
ENGULFING_THRESHOLD = 1.0  # Body engulfing ratio

# ==============================================================================
# ENUMS
# ==============================================================================
class PatternType(Enum):
    """Price action pattern types"""
    # Single bar patterns
    PIN_BAR = "pin_bar"
    DOJI = "doji"
    MARUBOZU = "marubozu"
    HAMMER = "hammer"
    SHOOTING_STAR = "shooting_star"
    
    # Two bar patterns
    ENGULFING = "engulfing"
    HARAMI = "harami"
    PIERCING = "piercing"
    DARK_CLOUD = "dark_cloud"
    TWEEZER = "tweezer"
    
    # Multi-bar patterns
    INSIDE_BAR = "inside_bar"
    OUTSIDE_BAR = "outside_bar"
    THREE_BAR_REVERSAL = "three_bar_reversal"
    MORNING_STAR = "morning_star"
    EVENING_STAR = "evening_star"
    THREE_SOLDIERS = "three_soldiers"
    THREE_CROWS = "three_crows"
    
    # Chart patterns
    DOUBLE_TOP = "double_top"
    DOUBLE_BOTTOM = "double_bottom"
    HEAD_SHOULDERS = "head_shoulders"
    TRIANGLE = "triangle"
    FLAG = "flag"
    WEDGE = "wedge"
    
    # Price action
    SUPPORT_BOUNCE = "support_bounce"
    RESISTANCE_REJECTION = "resistance_rejection"
    BREAKOUT = "breakout"
    BREAKDOWN = "breakdown"
    FALSE_BREAKOUT = "false_breakout"

class PatternDirection(Enum):
    """Pattern direction bias"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"

class TrendDirection(Enum):
    """Market trend direction"""
    UP = "up"
    DOWN = "down"
    SIDEWAYS = "sideways"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class Candle:
    """Candlestick data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    
    @property
    def body(self) -> float:
        """Get candle body size"""
        return abs(self.close - self.open)
    
    @property
    def range(self) -> float:
        """Get total candle range"""
        return self.high - self.low
    
    @property
    def upper_wick(self) -> float:
        """Get upper wick size"""
        return self.high - max(self.open, self.close)
    
    @property
    def lower_wick(self) -> float:
        """Get lower wick size"""
        return min(self.open, self.close) - self.low

@dataclass
class Pattern:
    """Price action pattern"""
    pattern_type: PatternType
    direction: PatternDirection
    strength: float
    timestamp: datetime
    price_level: float
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

# ==============================================================================
# PRICE ACTION ANALYZER CLASS
# ==============================================================================
class PriceActionAnalyzer:
    """Price action pattern recognition and analysis."""
    
    def __init__(self):
        """Initialize price action analyzer."""
        self.logger = SpyderLogger("PriceActionAnalyzer")
        self.error_handler = SpyderErrorHandler()
        self.detected_patterns = []
    
    def analyze_patterns(self, data: pd.DataFrame) -> List[Pattern]:
        """Analyze price data for patterns."""
        try:
            patterns = []
            
            if len(data) < 3:
                return patterns
            
            # Convert to candle objects
            candles = self._dataframe_to_candles(data)
            
            # Detect various patterns
            patterns.extend(self._detect_single_bar_patterns(candles))
            patterns.extend(self._detect_multi_bar_patterns(candles))
            
            return patterns
            
        except Exception as e:
            self.error_handler.handle_error(e, {"data_length": len(data)})
            return []
    
    def _dataframe_to_candles(self, data: pd.DataFrame) -> List[Candle]:
        """Convert DataFrame to Candle objects."""
        candles = []
        
        for _, row in data.iterrows():
            candle = Candle(
                timestamp=row.name if isinstance(row.name, datetime) else datetime.now(),
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=int(row.get('volume', 0))
            )
            candles.append(candle)
        
        return candles
    
    def _detect_single_bar_patterns(self, candles: List[Candle]) -> List[Pattern]:
        """Detect single bar patterns."""
        patterns = []
        
        for i, candle in enumerate(candles[-10:]):  # Check last 10 candles
            # Pin bar detection
            if self._is_pin_bar(candle):
                direction = PatternDirection.BULLISH if candle.lower_wick > candle.upper_wick else PatternDirection.BEARISH
                pattern = Pattern(
                    pattern_type=PatternType.PIN_BAR,
                    direction=direction,
                    strength=0.7,
                    timestamp=candle.timestamp,
                    price_level=candle.close,
                    confidence=0.8
                )
                patterns.append(pattern)
            
            # Doji detection
            if self._is_doji(candle):
                pattern = Pattern(
                    pattern_type=PatternType.DOJI,
                    direction=PatternDirection.NEUTRAL,
                    strength=0.6,
                    timestamp=candle.timestamp,
                    price_level=candle.close,
                    confidence=0.7
                )
                patterns.append(pattern)
        
        return patterns
    
    def _detect_multi_bar_patterns(self, candles: List[Candle]) -> List[Pattern]:
        """Detect multi-bar patterns."""
        patterns = []
        
        if len(candles) < 2:
            return patterns
        
        # Check last few candle pairs
        for i in range(len(candles) - 1, max(0, len(candles) - 5), -1):
            if i < 1:
                continue
                
            current = candles[i]
            previous = candles[i-1]
            
            # Engulfing pattern
            if self._is_engulfing(previous, current):
                direction = PatternDirection.BULLISH if current.close > current.open else PatternDirection.BEARISH
                pattern = Pattern(
                    pattern_type=PatternType.ENGULFING,
                    direction=direction,
                    strength=0.8,
                    timestamp=current.timestamp,
                    price_level=current.close,
                    confidence=0.85
                )
                patterns.append(pattern)
        
        return patterns
    
    def _is_pin_bar(self, candle: Candle) -> bool:
        """Check if candle is a pin bar."""
        if candle.range == 0:
            return False
        
        body_ratio = candle.body / candle.range
        wick_ratio = max(candle.upper_wick, candle.lower_wick) / candle.range
        
        return body_ratio < 0.3 and wick_ratio > PIN_BAR_RATIO
    
    def _is_doji(self, candle: Candle) -> bool:
        """Check if candle is a doji."""
        if candle.range == 0:
            return True
        
        body_ratio = candle.body / candle.range
        return body_ratio < DOJI_BODY_PERCENT
    
    def _is_engulfing(self, prev: Candle, current: Candle) -> bool:
        """Check if current candle engulfs previous."""
        prev_bullish = prev.close > prev.open
        curr_bullish = current.close > current.open
        
        if prev_bullish == curr_bullish:
            return False
        
        # Check if current body engulfs previous body
        curr_body_top = max(current.open, current.close)
        curr_body_bottom = min(current.open, current.close)
        prev_body_top = max(prev.open, prev.close)
        prev_body_bottom = min(prev.open, prev.close)
        
        return (curr_body_top > prev_body_top and 
                curr_body_bottom < prev_body_bottom)

def calculate_support_resistance(data: pd.DataFrame, lookback: int = 50) -> Dict[str, List[float]]:
    """
    Calculate support and resistance levels.
    
    Args:
        data: OHLCV DataFrame
        lookback: Lookback period
        
    Returns:
        Dictionary with support and resistance levels
    """
    if len(data) < lookback:
        lookback = len(data)
    
    recent_data = data.tail(lookback)
    
    # Find peaks and troughs
    highs = recent_data['high'].values
    lows = recent_data['low'].values
    
    # Detect peaks (resistance)
    peaks, _ = find_peaks(highs, distance=5, prominence=highs.std() * 0.5)
    
    # Detect troughs (support)
    troughs, _ = find_peaks(-lows, distance=5, prominence=lows.std() * 0.5)
    
    # Extract price levels
    resistance_levels = sorted([highs[p] for p in peaks], reverse=True)[:5]
    support_levels = sorted([lows[t] for t in troughs])[:5]
    
    return {
        'resistance': resistance_levels,
        'support': support_levels,
        'current_price': data['close'].iloc[-1]
    }

def calculate_pattern_success_rate(patterns: List[Pattern], outcomes: List[bool]) -> Dict[str, float]:
    """
    Calculate success rate for different pattern types.
    
    Args:
        patterns: List of detected patterns
        outcomes: List of pattern outcomes (True = successful)
        
    Returns:
        Dictionary of pattern type to success rate
    """
    if len(patterns) != len(outcomes):
        raise ValueError("Patterns and outcomes must have same length")
    
    success_rates = {}
    
    for pattern_type in PatternType:
        pattern_outcomes = [
            outcomes[i] for i, p in enumerate(patterns)
            if p.pattern_type == pattern_type
        ]
        
        if pattern_outcomes:
            success_rates[pattern_type.value] = sum(pattern_outcomes) / len(pattern_outcomes)
        else:
            success_rates[pattern_type.value] = 0.0
    
    return success_rates

# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    "PriceActionAnalyzer",
    "Pattern",
    "PatternType", 
    "PatternDirection",
    "TrendDirection",
    "Candle",
    "calculate_support_resistance",
    "calculate_pattern_success_rate"
]
