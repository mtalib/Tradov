#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX13_MarketAnalysisAgent.py
Purpose: AI-Enhanced Market Analysis and Pattern Recognition
Group: X (AI Agents)

This module implements an intelligent market analysis agent that performs
technical analysis, pattern recognition, regime detection, and provides
AI-driven market insights using Ollama integration.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-06-16
Last Updated: 2025-06-19 Time: 14:05
"""

# ==============================================================================
# IMPORTS
# ==============================================================================

# Standard library imports
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import statistics

# Third-party imports
import numpy as np
import pandas as pd
from scipy import stats

# Ollama imports (with graceful fallback)
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("Warning: Ollama not installed. AI features will be limited.")

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Market regimes
class MarketRegime(Enum):
    """Market regime types."""
    BULL_QUIET = "BULL_QUIET"
    BULL_VOLATILE = "BULL_VOLATILE"
    BEAR_QUIET = "BEAR_QUIET"
    BEAR_VOLATILE = "BEAR_VOLATILE"
    RANGING = "RANGING"
    TRANSITIONING = "TRANSITIONING"

# Pattern types
class PatternType(Enum):
    """Technical pattern types."""
    # Reversal patterns
    HEAD_SHOULDERS = "HEAD_SHOULDERS"
    DOUBLE_TOP = "DOUBLE_TOP"
    DOUBLE_BOTTOM = "DOUBLE_BOTTOM"
    TRIPLE_TOP = "TRIPLE_TOP"
    TRIPLE_BOTTOM = "TRIPLE_BOTTOM"
    
    # Continuation patterns
    FLAG = "FLAG"
    PENNANT = "PENNANT"
    WEDGE = "WEDGE"
    TRIANGLE = "TRIANGLE"
    CHANNEL = "CHANNEL"
    
    # Candlestick patterns
    DOJI = "DOJI"
    HAMMER = "HAMMER"
    ENGULFING = "ENGULFING"
    MORNING_STAR = "MORNING_STAR"
    EVENING_STAR = "EVENING_STAR"

# Technical indicators
TECHNICAL_INDICATORS = {
    'trend': ['SMA', 'EMA', 'MACD', 'ADX'],
    'momentum': ['RSI', 'Stochastic', 'Williams %R', 'CCI'],
    'volatility': ['Bollinger Bands', 'ATR', 'Keltner Channels'],
    'volume': ['OBV', 'Volume Profile', 'VWAP', 'MFI']
}

# Support/Resistance levels
SUPPORT_RESISTANCE_METHODS = [
    'pivot_points',
    'fibonacci',
    'volume_profile',
    'historical_levels',
    'psychological_levels'
]

# Market microstructure
MICROSTRUCTURE_METRICS = {
    'bid_ask_spread': 'Market liquidity indicator',
    'order_imbalance': 'Buy/sell pressure',
    'tick_distribution': 'Price movement patterns',
    'volume_at_price': 'Support/resistance strength',
    'time_and_sales': 'Order flow analysis'
}

# Default configuration
DEFAULT_CONFIG = {
    'lookback_periods': {
        'short': 20,
        'medium': 50,
        'long': 200
    },
    'pattern_min_confidence': 0.7,
    'regime_change_threshold': 0.8,
    'support_resistance_tolerance': 0.002,  # 0.2%
    'indicator_weights': {
        'trend': 0.4,
        'momentum': 0.3,
        'volatility': 0.2,
        'volume': 0.1
    }
}

# Model configuration
DEFAULT_MODEL = "llama3.2:3b-instruct-q4_K_M"
DEFAULT_TEMPERATURE = 0.3

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class MarketData:
    """Market data structure."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Pattern:
    """Detected pattern structure."""
    pattern_type: PatternType
    start_time: datetime
    end_time: datetime
    confidence: float
    price_target: Optional[float]
    stop_loss: Optional[float]
    description: str
    chart_points: List[Tuple[datetime, float]]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TechnicalAnalysis:
    """Technical analysis results."""
    timestamp: datetime
    indicators: Dict[str, float]
    patterns: List[Pattern]
    support_levels: List[float]
    resistance_levels: List[float]
    trend_direction: str  # 'up', 'down', 'sideways'
    trend_strength: float  # 0-1
    momentum: float  # -1 to 1
    volatility: float
    volume_analysis: Dict[str, Any]
    ai_insights: Dict[str, Any]

@dataclass
class MarketAnalysis:
    """Complete market analysis."""
    timestamp: datetime
    current_regime: MarketRegime
    regime_confidence: float
    technical_analysis: TechnicalAnalysis
    microstructure: Dict[str, Any]
    correlation_analysis: Dict[str, float]
    event_risks: List[Dict[str, Any]]
    trading_opportunities: List[Dict[str, Any]]
    risk_assessment: Dict[str, Any]
    ai_synthesis: Dict[str, Any]

@dataclass
class TradingSignal:
    """Trading signal structure."""
    timestamp: datetime
    direction: str  # 'long', 'short', 'neutral'
    strength: float  # 0-1
    entry_price: float
    target_price: float
    stop_loss: float
    risk_reward_ratio: float
    confidence: float
    reasoning: List[str]
    timeframe: str  # 'intraday', 'swing', 'position'

# ==============================================================================
# MARKET ANALYSIS AGENT CLASS
# ==============================================================================

class SpyderX13_MarketAnalysisAgent:
    """
    AI-Enhanced Market Analysis Agent.
    
    This agent performs comprehensive market analysis using technical indicators,
    pattern recognition, and AI to identify trading opportunities and market regimes.
    """
    
    def __init__(self, model_name: str = DEFAULT_MODEL,
                 temperature: float = DEFAULT_TEMPERATURE):
        """
        Initialize the Market Analysis Agent.
        
        Args:
            model_name: Ollama model to use
            temperature: Temperature for AI responses
        """
        self.model_name = model_name
        self.temperature = temperature
        self.logger = self._setup_logger()
        self.config = DEFAULT_CONFIG.copy()
        
        # Initialize Ollama if available
        self.ollama_client = None
        if OLLAMA_AVAILABLE:
            try:
                ollama.list()  # Test connection
                self.ollama_client = ollama
                self.logger.info("Ollama connection established")
            except Exception as e:
                self.logger.error(f"Failed to connect to Ollama: {e}")
        
        # Market data storage
        self.price_history = deque(maxlen=5000)  # ~20 days of 5-min bars
        self.volume_profile = defaultdict(float)
        
        # Analysis cache
        self.pattern_cache = {}
        self.indicator_cache = {}
        self.regime_history = deque(maxlen=100)
        
        # Performance tracking
        self.signal_history = deque(maxlen=1000)
        self.analysis_metrics = defaultdict(int)
    
    def _setup_logger(self) -> logging.Logger:
        """Set up module logger."""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    # ==========================================================================
    # MAIN ANALYSIS METHODS
    # ==========================================================================
    
    async def analyze_market(self, market_data: List[MarketData],
                           symbol: str = "SPY") -> MarketAnalysis:
        """
        Perform comprehensive market analysis.
        
        Args:
            market_data: List of market data points
            symbol: Symbol being analyzed
            
        Returns:
            MarketAnalysis object
        """
        self.logger.info(f"Analyzing market for {symbol}")
        
        try:
            # Update price history
            self.price_history.extend(market_data)
            
            # Perform technical analysis
            technical = await self._perform_technical_analysis(market_data)
            
            # Detect market regime
            regime, regime_confidence = await self._detect_market_regime(market_data)
            
            # Analyze microstructure
            microstructure = self._analyze_microstructure(market_data)
            
            # Correlation analysis
            correlations = self._analyze_correlations(market_data)
            
            # Identify event risks
            event_risks = await self._identify_event_risks(symbol)
            
            # Find trading opportunities
            opportunities = await self._find_trading_opportunities(
                technical, regime, microstructure
            )
            
            # Risk assessment
            risk_assessment = self._assess_market_risk(
                regime, technical, microstructure
            )
            
            # AI synthesis
            ai_synthesis = await self._get_ai_market_synthesis(
                regime, technical, opportunities, risk_assessment
            )
            
            return MarketAnalysis(
                timestamp=datetime.now(),
                current_regime=regime,
                regime_confidence=regime_confidence,
                technical_analysis=technical,
                microstructure=microstructure,
                correlation_analysis=correlations,
                event_risks=event_risks,
                trading_opportunities=opportunities,
                risk_assessment=risk_assessment,
                ai_synthesis=ai_synthesis
            )
            
        except Exception as e:
            self.logger.error(f"Market analysis failed: {e}")
            return self._create_default_analysis()
    
    async def detect_patterns(self, market_data: List[MarketData],
                            min_confidence: Optional[float] = None) -> List[Pattern]:
        """
        Detect technical patterns in market data.
        
        Args:
            market_data: Market data to analyze
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of detected patterns
        """
        self.logger.info("Detecting market patterns")
        
        min_conf = min_confidence or self.config['pattern_min_confidence']
        patterns = []
        
        # Check each pattern type
        for pattern_type in PatternType:
            pattern = self._detect_specific_pattern(market_data, pattern_type)
            if pattern and pattern.confidence >= min_conf:
                patterns.append(pattern)
        
        # Get AI pattern insights
        if patterns and self.ollama_client:
            patterns = await self._enhance_patterns_with_ai(patterns, market_data)
        
        # Sort by confidence
        patterns.sort(key=lambda p: p.confidence, reverse=True)
        
        return patterns
    
    async def generate_trading_signal(self, analysis: MarketAnalysis) -> Optional[TradingSignal]:
        """
        Generate trading signal from market analysis.
        
        Args:
            analysis: Market analysis results
            
        Returns:
            Trading signal if conditions are met
        """
        self.logger.info("Generating trading signal")
        
        try:
            # Check if conditions are favorable
            if not self._check_trading_conditions(analysis):
                return None
            
            # Determine signal direction
            direction = self._determine_signal_direction(analysis)
            
            if direction == 'neutral':
                return None
            
            # Calculate entry, target, and stop
            current_price = self.price_history[-1].close if self.price_history else 0
            entry, target, stop = self._calculate_signal_levels(
                direction, current_price, analysis
            )
            
            # Calculate signal strength
            strength = self._calculate_signal_strength(analysis)
            
            # Get AI confirmation
            if self.ollama_client:
                ai_confirmation = await self._get_ai_signal_confirmation(
                    direction, analysis, strength
                )
                if not ai_confirmation.get('confirm', False):
                    return None
                strength *= ai_confirmation.get('confidence_adjustment', 1.0)
            
            # Build reasoning
            reasoning = self._build_signal_reasoning(direction, analysis)
            
            # Determine timeframe
            timeframe = self._determine_signal_timeframe(analysis)
            
            signal = TradingSignal(
                timestamp=datetime.now(),
                direction=direction,
                strength=strength,
                entry_price=entry,
                target_price=target,
                stop_loss=stop,
                risk_reward_ratio=abs(target - entry) / abs(entry - stop),
                confidence=strength * analysis.regime_confidence,
                reasoning=reasoning,
                timeframe=timeframe
            )
            
            # Track signal
            self.signal_history.append(signal)
            
            return signal
            
        except Exception as e:
            self.logger.error(f"Signal generation failed: {e}")
            return None
    
    # ==========================================================================
    # TECHNICAL ANALYSIS METHODS
    # ==========================================================================
    
    async def _perform_technical_analysis(self, 
                                        market_data: List[MarketData]) -> TechnicalAnalysis:
        """Perform comprehensive technical analysis."""
        # Calculate indicators
        indicators = self._calculate_all_indicators(market_data)
        
        # Detect patterns
        patterns = await self.detect_patterns(market_data)
        
        # Find support/resistance
        support_levels, resistance_levels = self._find_support_resistance(market_data)
        
        # Analyze trend
        trend_direction, trend_strength = self._analyze_trend(indicators)
        
        # Calculate momentum
        momentum = self._calculate_momentum(indicators)
        
        # Calculate volatility
        volatility = self._calculate_volatility(market_data)
        
        # Volume analysis
        volume_analysis = self._analyze_volume(market_data)
        
        # Get AI insights
        ai_insights = await self._get_ai_technical_insights(
            indicators, patterns, trend_direction
        )
        
        return TechnicalAnalysis(
            timestamp=datetime.now(),
            indicators=indicators,
            patterns=patterns,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            momentum=momentum,
            volatility=volatility,
            volume_analysis=volume_analysis,
            ai_insights=ai_insights
        )
    
    def _calculate_all_indicators(self, market_data: List[MarketData]) -> Dict[str, float]:
        """Calculate all technical indicators."""
        if len(market_data) < 20:
            return {}
        
        # Convert to arrays
        closes = [d.close for d in market_data]
        highs = [d.high for d in market_data]
        lows = [d.low for d in market_data]
        volumes = [d.volume for d in market_data]
        
        indicators = {}
        
        # Trend indicators
        indicators['SMA_20'] = self._sma(closes, 20)
        indicators['SMA_50'] = self._sma(closes, 50)
        indicators['SMA_200'] = self._sma(closes, 200)
        indicators['EMA_12'] = self._ema(closes, 12)
        indicators['EMA_26'] = self._ema(closes, 26)
        
        # MACD
        macd, signal, histogram = self._calculate_macd(closes)
        indicators['MACD'] = macd
        indicators['MACD_Signal'] = signal
        indicators['MACD_Histogram'] = histogram
        
        # Momentum indicators
        indicators['RSI'] = self._calculate_rsi(closes, 14)
        indicators['Stochastic_K'], indicators['Stochastic_D'] = self._calculate_stochastic(
            highs, lows, closes
        )
        
        # Volatility indicators
        upper, middle, lower = self._calculate_bollinger_bands(closes)
        indicators['BB_Upper'] = upper
        indicators['BB_Middle'] = middle
        indicators['BB_Lower'] = lower
        indicators['ATR'] = self._calculate_atr(highs, lows, closes)
        
        # Volume indicators
        indicators['OBV'] = self._calculate_obv(closes, volumes)
        indicators['Volume_SMA'] = self._sma(volumes, 20)
        
        return indicators
    
    def _sma(self, data: List[float], period: int) -> float:
        """Simple Moving Average."""
        if len(data) < period:
            return 0.0
        return sum(data[-period:]) / period
    
    def _ema(self, data: List[float], period: int) -> float:
        """Exponential Moving Average."""
        if len(data) < period:
            return 0.0
        
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def _calculate_macd(self, closes: List[float]) -> Tuple[float, float, float]:
        """Calculate MACD."""
        if len(closes) < 26:
            return 0.0, 0.0, 0.0
        
        ema_12 = self._ema(closes, 12)
        ema_26 = self._ema(closes, 26)
        macd = ema_12 - ema_26
        
        # Signal line (9-period EMA of MACD)
        macd_values = []
        for i in range(26, len(closes)):
            e12 = self._ema(closes[:i], 12)
            e26 = self._ema(closes[:i], 26)
            macd_values.append(e12 - e26)
        
        signal = self._ema(macd_values, 9) if len(macd_values) >= 9 else 0
        histogram = macd - signal
        
        return macd, signal, histogram
    
    def _calculate_rsi(self, closes: List[float], period: int = 14) -> float:
        """Calculate RSI."""
        if len(closes) < period + 1:
            return 50.0
        
        gains = []
        losses = []
        
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_stochastic(self, highs: List[float], lows: List[float],
                            closes: List[float], period: int = 14) -> Tuple[float, float]:
        """Calculate Stochastic oscillator."""
        if len(closes) < period:
            return 50.0, 50.0
        
        recent_highs = highs[-period:]
        recent_lows = lows[-period:]
        current_close = closes[-1]
        
        highest = max(recent_highs)
        lowest = min(recent_lows)
        
        if highest == lowest:
            k = 50.0
        else:
            k = ((current_close - lowest) / (highest - lowest)) * 100
        
        # %D is 3-period SMA of %K
        k_values = []
        for i in range(period, len(closes)):
            h = max(highs[i-period:i])
            l = min(lows[i-period:i])
            if h != l:
                k_values.append(((closes[i] - l) / (h - l)) * 100)
        
        d = self._sma(k_values[-3:], 3) if len(k_values) >= 3 else k
        
        return k, d
    
    def _calculate_bollinger_bands(self, closes: List[float],
                                 period: int = 20, std_dev: int = 2) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands."""
        if len(closes) < period:
            return 0.0, 0.0, 0.0
        
        middle = self._sma(closes, period)
        std = np.std(closes[-period:])
        
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        
        return upper, middle, lower
    
    def _calculate_atr(self, highs: List[float], lows: List[float],
                      closes: List[float], period: int = 14) -> float:
        """Calculate Average True Range."""
        if len(closes) < period + 1:
            return 0.0
        
        true_ranges = []
        
        for i in range(1, len(closes)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            
            true_range = max(high_low, high_close, low_close)
            true_ranges.append(true_range)
        
        return self._sma(true_ranges[-period:], period)
    
    def _calculate_obv(self, closes: List[float], volumes: List[int]) -> float:
        """Calculate On-Balance Volume."""
        if len(closes) < 2:
            return 0.0
        
        obv = 0
        
        for i in range(1, len(closes)):
            if closes[i] > closes[i-1]:
                obv += volumes[i]
            elif closes[i] < closes[i-1]:
                obv -= volumes[i]
        
        return obv
    
    # ==========================================================================
    # PATTERN RECOGNITION METHODS
    # ==========================================================================
    
    def _detect_specific_pattern(self, market_data: List[MarketData],
                               pattern_type: PatternType) -> Optional[Pattern]:
        """Detect a specific pattern type."""
        if len(market_data) < 20:
            return None
        
        if pattern_type == PatternType.HEAD_SHOULDERS:
            return self._detect_head_shoulders(market_data)
        elif pattern_type == PatternType.DOUBLE_TOP:
            return self._detect_double_top(market_data)
        elif pattern_type == PatternType.DOUBLE_BOTTOM:
            return self._detect_double_bottom(market_data)
        elif pattern_type == PatternType.FLAG:
            return self._detect_flag(market_data)
        elif pattern_type == PatternType.TRIANGLE:
            return self._detect_triangle(market_data)
        elif pattern_type in [PatternType.DOJI, PatternType.HAMMER, PatternType.ENGULFING]:
            return self._detect_candlestick_pattern(market_data, pattern_type)
        
        return None
    
    def _detect_head_shoulders(self, market_data: List[MarketData]) -> Optional[Pattern]:
        """Detect head and shoulders pattern."""
        if len(market_data) < 50:
            return None
        
        highs = [d.high for d in market_data]
        
        # Find peaks (simplified)
        peaks = []
        for i in range(5, len(highs) - 5):
            if highs[i] == max(highs[i-5:i+6]):
                peaks.append((i, highs[i]))
        
        if len(peaks) < 3:
            return None
        
        # Check for head and shoulders formation
        for i in range(len(peaks) - 2):
            left_shoulder = peaks[i]
            head = peaks[i + 1]
            right_shoulder = peaks[i + 2]
            
            # Head should be higher than shoulders
            if (head[1] > left_shoulder[1] and head[1] > right_shoulder[1] and
                abs(left_shoulder[1] - right_shoulder[1]) / left_shoulder[1] < 0.03):
                
                # Calculate neckline
                neckline = min(highs[left_shoulder[0]:head[0]]) + min(highs[head[0]:right_shoulder[0]])
                neckline /= 2
                
                # Calculate price target
                pattern_height = head[1] - neckline
                price_target = neckline - pattern_height
                
                confidence = 0.7  # Simplified confidence
                
                return Pattern(
                    pattern_type=PatternType.HEAD_SHOULDERS,
                    start_time=market_data[left_shoulder[0]].timestamp,
                    end_time=market_data[right_shoulder[0]].timestamp,
                    confidence=confidence,
                    price_target=price_target,
                    stop_loss=head[1],
                    description="Head and Shoulders reversal pattern detected",
                    chart_points=[
                        (market_data[left_shoulder[0]].timestamp, left_shoulder[1]),
                        (market_data[head[0]].timestamp, head[1]),
                        (market_data[right_shoulder[0]].timestamp, right_shoulder[1])
                    ]
                )
        
        return None
    
    def _detect_double_top(self, market_data: List[MarketData]) -> Optional[Pattern]:
        """Detect double top pattern."""
        if len(market_data) < 30:
            return None
        
        highs = [d.high for d in market_data]
        
        # Find two peaks of similar height
        peaks = []
        for i in range(5, len(highs) - 5):
            if highs[i] == max(highs[i-5:i+6]):
                peaks.append((i, highs[i]))
        
        if len(peaks) < 2:
            return None
        
        # Check last two peaks
        if len(peaks) >= 2:
            peak1, peak2 = peaks[-2], peaks[-1]
            
            # Similar height (within 2%)
            if abs(peak1[1] - peak2[1]) / peak1[1] < 0.02:
                # Find valley between peaks
                valley = min(highs[peak1[0]:peak2[0]])
                
                # Calculate target
                pattern_height = peak1[1] - valley
                price_target = valley - pattern_height
                
                confidence = 0.75
                
                return Pattern(
                    pattern_type=PatternType.DOUBLE_TOP,
                    start_time=market_data[peak1[0]].timestamp,
                    end_time=market_data[peak2[0]].timestamp,
                    confidence=confidence,
                    price_target=price_target,
                    stop_loss=max(peak1[1], peak2[1]),
                    description="Double Top reversal pattern detected",
                    chart_points=[
                        (market_data[peak1[0]].timestamp, peak1[1]),
                        (market_data[peak2[0]].timestamp, peak2[1])
                    ]
                )
        
        return None
    
    def _detect_double_bottom(self, market_data: List[MarketData]) -> Optional[Pattern]:
        """Detect double bottom pattern."""
        if len(market_data) < 30:
            return None
        
        lows = [d.low for d in market_data]
        
        # Find two valleys of similar depth
        valleys = []
        for i in range(5, len(lows) - 5):
            if lows[i] == min(lows[i-5:i+6]):
                valleys.append((i, lows[i]))
        
        if len(valleys) < 2:
            return None
        
        # Check last two valleys
        if len(valleys) >= 2:
            valley1, valley2 = valleys[-2], valleys[-1]
            
            # Similar depth (within 2%)
            if abs(valley1[1] - valley2[1]) / valley1[1] < 0.02:
                # Find peak between valleys
                peak = max(lows[valley1[0]:valley2[0]])
                
                # Calculate target
                pattern_height = peak - valley1[1]
                price_target = peak + pattern_height
                
                confidence = 0.75
                
                return Pattern(
                    pattern_type=PatternType.DOUBLE_BOTTOM,
                    start_time=market_data[valley1[0]].timestamp,
                    end_time=market_data[valley2[0]].timestamp,
                    confidence=confidence,
                    price_target=price_target,
                    stop_loss=min(valley1[1], valley2[1]),
                    description="Double Bottom reversal pattern detected",
                    chart_points=[
                        (market_data[valley1[0]].timestamp, valley1[1]),
                        (market_data[valley2[0]].timestamp, valley2[1])
                    ]
                )
        
        return None
    
    def _detect_flag(self, market_data: List[MarketData]) -> Optional[Pattern]:
        """Detect flag continuation pattern."""
        if len(market_data) < 20:
            return None
        
        # Simplified flag detection
        closes = [d.close for d in market_data]
        
        # Look for strong move followed by consolidation
        move_period = 10
        consol_period = 10
        
        if len(closes) < move_period + consol_period:
            return None
        
        # Calculate move
        move_start = closes[-(move_period + consol_period)]
        move_end = closes[-consol_period]
        move_size = (move_end - move_start) / move_start
        
        # Strong move threshold (3%)
        if abs(move_size) > 0.03:
            # Check consolidation
            consol_high = max(closes[-consol_period:])
            consol_low = min(closes[-consol_period:])
            consol_range = (consol_high - consol_low) / consol_low
            
            # Tight consolidation (less than 1.5%)
            if consol_range < 0.015:
                direction = 'bullish' if move_size > 0 else 'bearish'
                
                # Price target
                if direction == 'bullish':
                    price_target = consol_high + abs(move_end - move_start)
                    stop_loss = consol_low
                else:
                    price_target = consol_low - abs(move_end - move_start)
                    stop_loss = consol_high
                
                return Pattern(
                    pattern_type=PatternType.FLAG,
                    start_time=market_data[-(move_period + consol_period)].timestamp,
                    end_time=market_data[-1].timestamp,
                    confidence=0.7,
                    price_target=price_target,
                    stop_loss=stop_loss,
                    description=f"{direction.capitalize()} flag pattern detected",
                    chart_points=[]
                )
        
        return None
    
    def _detect_triangle(self, market_data: List[MarketData]) -> Optional[Pattern]:
        """Detect triangle pattern."""
        if len(market_data) < 30:
            return None
        
        highs = [d.high for d in market_data]
        lows = [d.low for d in market_data]
        
        # Find converging trendlines (simplified)
        # Calculate slopes of highs and lows
        n = len(highs)
        x = list(range(n))
        
        # High trendline
        high_slope = self._calculate_trendline_slope(x[-20:], highs[-20:])
        
        # Low trendline
        low_slope = self._calculate_trendline_slope(x[-20:], lows[-20:])
        
        # Check for convergence
        if high_slope < 0 and low_slope > 0:  # Converging
            # Estimate apex
            current_range = highs[-1] - lows[-1]
            
            # Price target (breakout of triangle height)
            triangle_height = max(highs[-20:]) - min(lows[-20:])
            price_target = highs[-1] + triangle_height
            
            return Pattern(
                pattern_type=PatternType.TRIANGLE,
                start_time=market_data[-20].timestamp,
                end_time=market_data[-1].timestamp,
                confidence=0.65,
                price_target=price_target,
                stop_loss=lows[-1],
                description="Symmetrical triangle pattern detected",
                chart_points=[]
            )
        
        return None
    
    def _detect_candlestick_pattern(self, market_data: List[MarketData],
                                  pattern_type: PatternType) -> Optional[Pattern]:
        """Detect candlestick patterns."""
        if len(market_data) < 3:
            return None
        
        # Get last few candles
        candles = market_data[-3:]
        
        if pattern_type == PatternType.DOJI:
            # Check last candle for doji
            last = candles[-1]
            body = abs(last.close - last.open)
            range_hl = last.high - last.low
            
            if range_hl > 0 and body / range_hl < 0.1:  # Small body
                return Pattern(
                    pattern_type=PatternType.DOJI,
                    start_time=last.timestamp,
                    end_time=last.timestamp,
                    confidence=0.8,
                    price_target=None,
                    stop_loss=last.low,
                    description="Doji candlestick pattern - indecision",
                    chart_points=[(last.timestamp, last.close)]
                )
        
        elif pattern_type == PatternType.HAMMER:
            # Check for hammer
            last = candles[-1]
            body = abs(last.close - last.open)
            lower_shadow = min(last.open, last.close) - last.low
            upper_shadow = last.high - max(last.open, last.close)
            
            if lower_shadow > body * 2 and upper_shadow < body * 0.5:
                return Pattern(
                    pattern_type=PatternType.HAMMER,
                    start_time=last.timestamp,
                    end_time=last.timestamp,
                    confidence=0.75,
                    price_target=last.high + body,
                    stop_loss=last.low,
                    description="Hammer pattern - potential reversal",
                    chart_points=[(last.timestamp, last.close)]
                )
        
        elif pattern_type == PatternType.ENGULFING and len(candles) >= 2:
            # Check for engulfing pattern
            prev = candles[-2]
            last = candles[-1]
            
            # Bullish engulfing
            if (prev.close < prev.open and  # Red candle
                last.close > last.open and  # Green candle
                last.open < prev.close and   # Opens below prev close
                last.close > prev.open):     # Closes above prev open
                
                return Pattern(
                    pattern_type=PatternType.ENGULFING,
                    start_time=prev.timestamp,
                    end_time=last.timestamp,
                    confidence=0.8,
                    price_target=last.close + (last.close - last.open),
                    stop_loss=last.low,
                    description="Bullish engulfing pattern",
                    chart_points=[
                        (prev.timestamp, prev.close),
                        (last.timestamp, last.close)
                    ]
                )
        
        return None
    
    def _calculate_trendline_slope(self, x: List[int], y: List[float]) -> float:
        """Calculate slope of trendline."""
        n = len(x)
        if n < 2:
            return 0.0
        
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi**2 for xi in x)
        
        denominator = n * sum_x2 - sum_x**2
        if denominator == 0:
            return 0.0
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        return slope
    
    # ==========================================================================
    # SUPPORT/RESISTANCE METHODS
    # ==========================================================================
    
    def _find_support_resistance(self, 
                               market_data: List[MarketData]) -> Tuple[List[float], List[float]]:
        """Find support and resistance levels."""
        if len(market_data) < 20:
            return [], []
        
        highs = [d.high for d in market_data]
        lows = [d.low for d in market_data]
        closes = [d.close for d in market_data]
        volumes = [d.volume for d in market_data]
        
        support_levels = []
        resistance_levels = []
        
        # Method 1: Local extrema
        for i in range(5, len(market_data) - 5):
            # Local high (resistance)
            if highs[i] == max(highs[i-5:i+6]):
                resistance_levels.append(highs[i])
            
            # Local low (support)
            if lows[i] == min(lows[i-5:i+6]):
                support_levels.append(lows[i])
        
        # Method 2: Volume profile peaks
        self._update_volume_profile(market_data)
        volume_peaks = self._find_volume_peaks()
        support_levels.extend(volume_peaks)
        resistance_levels.extend(volume_peaks)
        
        # Method 3: Psychological levels
        current_price = closes[-1]
        psych_levels = self._find_psychological_levels(current_price)
        
        for level in psych_levels:
            if level < current_price:
                support_levels.append(level)
            else:
                resistance_levels.append(level)
        
        # Remove duplicates and sort
        support_levels = sorted(list(set(support_levels)), reverse=True)
        resistance_levels = sorted(list(set(resistance_levels)))
        
        # Filter by proximity to current price
        current = closes[-1]
        support_levels = [s for s in support_levels if s < current and (current - s) / current < 0.1]
        resistance_levels = [r for r in resistance_levels if r > current and (r - current) / current < 0.1]
        
        return support_levels[:5], resistance_levels[:5]  # Top 5 each
    
    def _update_volume_profile(self, market_data: List[MarketData]):
        """Update volume profile."""
        for data in market_data:
            price_level = round(data.close, 0)  # Round to nearest dollar
            self.volume_profile[price_level] += data.volume
    
    def _find_volume_peaks(self) -> List[float]:
        """Find price levels with high volume."""
        if not self.volume_profile:
            return []
        
        # Sort by volume
        sorted_levels = sorted(self.volume_profile.items(), key=lambda x: x[1], reverse=True)
        
        # Return top price levels
        return [level for level, _ in sorted_levels[:10]]
    
    def _find_psychological_levels(self, current_price: float) -> List[float]:
        """Find psychological price levels."""
        levels = []
        
        # Round numbers
        base = int(current_price / 10) * 10
        for offset in [-20, -10, 0, 10, 20]:
            level = base + offset
            if level > 0:
                levels.append(float(level))
        
        # Half levels
        base_half = int(current_price / 5) * 5
        for offset in [-10, -5, 0, 5, 10]:
            level = base_half + offset
            if level > 0 and level not in levels:
                levels.append(float(level))
        
        return sorted(levels)
    
    # ==========================================================================
    # REGIME DETECTION METHODS
    # ==========================================================================
    
    async def _detect_market_regime(self, 
                                  market_data: List[MarketData]) -> Tuple[MarketRegime, float]:
        """Detect current market regime."""
        if len(market_data) < 50:
            return MarketRegime.RANGING, 0.5
        
        # Calculate regime indicators
        trend_score = self._calculate_trend_score(market_data)
        volatility_score = self._calculate_volatility_score(market_data)
        
        # Get AI regime assessment
        if self.ollama_client:
            ai_regime = await self._get_ai_regime_assessment(
                market_data, trend_score, volatility_score
            )
            regime_type = ai_regime.get('regime', 'RANGING')
            confidence = ai_regime.get('confidence', 0.5)
        else:
            # Rule-based regime detection
            regime_type, confidence = self._rule_based_regime_detection(
                trend_score, volatility_score
            )
        
        # Convert to enum
        try:
            regime = MarketRegime(regime_type)
        except:
            regime = MarketRegime.RANGING
        
        # Update regime history
        self.regime_history.append({
            'timestamp': datetime.now(),
            'regime': regime,
            'confidence': confidence
        })
        
        return regime, confidence
    
    def _calculate_trend_score(self, market_data: List[MarketData]) -> float:
        """Calculate trend score (-1 to 1)."""
        closes = [d.close for d in market_data]
        
        # Multiple timeframe trend
        short_trend = (closes[-1] - closes[-20]) / closes[-20] if len(closes) > 20 else 0
        medium_trend = (closes[-1] - closes[-50]) / closes[-50] if len(closes) > 50 else 0
        
        # Weighted average
        trend_score = short_trend * 0.6 + medium_trend * 0.4
        
        # Normalize to -1 to 1
        return max(-1, min(1, trend_score * 10))
    
    def _calculate_volatility_score(self, market_data: List[MarketData]) -> float:
        """Calculate volatility score (0 to 1)."""
        returns = []
        for i in range(1, len(market_data)):
            ret = (market_data[i].close - market_data[i-1].close) / market_data[i-1].close
            returns.append(ret)
        
        if not returns:
            return 0.5
        
        # Current volatility
        current_vol = np.std(returns[-20:]) if len(returns) > 20 else np.std(returns)
        
        # Historical volatility
        hist_vol = np.std(returns) if len(returns) > 50 else current_vol
        
        # Relative volatility
        rel_vol = current_vol / hist_vol if hist_vol > 0 else 1
        
        # Normalize to 0-1
        return min(1, rel_vol)
    
    def _rule_based_regime_detection(self, trend_score: float,
                                   volatility_score: float) -> Tuple[str, float]:
        """Rule-based regime detection."""
        confidence = 0.7
        
        if trend_score > 0.3:
            if volatility_score < 0.5:
                return 'BULL_QUIET', confidence
            else:
                return 'BULL_VOLATILE', confidence
        elif trend_score < -0.3:
            if volatility_score < 0.5:
                return 'BEAR_QUIET', confidence
            else:
                return 'BEAR_VOLATILE', confidence
        else:
            if volatility_score > 0.7:
                return 'TRANSITIONING', confidence * 0.8
            else:
                return 'RANGING', confidence * 0.9
    
    # ==========================================================================
    # AI INTEGRATION METHODS
    # ==========================================================================
    
    async def _get_ai_technical_insights(self, indicators: Dict[str, float],
                                       patterns: List[Pattern],
                                       trend: str) -> Dict[str, Any]:
        """Get AI insights on technical analysis."""
        if not self.ollama_client:
            return {'source': 'rule-based'}
        
        prompt = f"""Analyze this technical analysis data:

Indicators:
- RSI: {indicators.get('RSI', 50):.1f}
- MACD: {indicators.get('MACD', 0):.3f}
- Stochastic: {indicators.get('Stochastic_K', 50):.1f}
- Bollinger Band Position: {self._bb_position(indicators):.1%}

Patterns Detected: {len(patterns)}
{self._format_patterns(patterns[:3])}

Trend: {trend}

Provide a JSON response:
{{
    "market_structure": "description of current structure",
    "key_levels": ["important price levels"],
    "momentum_assessment": "momentum analysis",
    "probability_direction": "up/down/sideways",
    "entry_timing": "good/wait/avoid",
    "risk_factors": ["risk1", "risk2"],
    "confidence": 0.0-1.0
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            else:
                return {'source': 'failed_parsing'}
                
        except Exception as e:
            self.logger.error(f"AI technical insights failed: {e}")
            return {'error': str(e)}
    
    async def _get_ai_regime_assessment(self, market_data: List[MarketData],
                                      trend_score: float,
                                      volatility_score: float) -> Dict[str, Any]:
        """Get AI assessment of market regime."""
        if not self.ollama_client:
            return {'regime': 'RANGING', 'confidence': 0.5}
        
        # Prepare market summary
        closes = [d.close for d in market_data[-20:]]
        volumes = [d.volume for d in market_data[-20:]]
        
        prompt = f"""Assess the current market regime:

Recent Price Action:
- Trend Score: {trend_score:.2f} (-1 to 1)
- Volatility Score: {volatility_score:.2f} (0 to 1)
- 20-day Return: {((closes[-1] - closes[0]) / closes[0]):.1%}
- Volume Trend: {'increasing' if volumes[-1] > np.mean(volumes) else 'decreasing'}

Price Pattern:
{self._describe_price_pattern(closes)}

Available Regimes:
- BULL_QUIET: Uptrend with low volatility
- BULL_VOLATILE: Uptrend with high volatility
- BEAR_QUIET: Downtrend with low volatility
- BEAR_VOLATILE: Downtrend with high volatility
- RANGING: Sideways movement
- TRANSITIONING: Regime change in progress

Provide a JSON response:
{{
    "regime": "REGIME_NAME",
    "confidence": 0.0-1.0,
    "characteristics": ["char1", "char2"],
    "expected_behavior": "description",
    "trading_approach": "recommended approach"
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            else:
                return {'regime': 'RANGING', 'confidence': 0.5}
                
        except Exception as e:
            self.logger.error(f"AI regime assessment failed: {e}")
            return {'regime': 'RANGING', 'confidence': 0.5}
    
    async def _enhance_patterns_with_ai(self, patterns: List[Pattern],
                                      market_data: List[MarketData]) -> List[Pattern]:
        """Enhance pattern analysis with AI."""
        if not self.ollama_client or not patterns:
            return patterns
        
        current_price = market_data[-1].close if market_data else 0
        
        prompt = f"""Analyze these detected chart patterns:

Current Price: ${current_price:.2f}

Patterns:
{self._format_patterns_detailed(patterns[:5])}

Market Context:
- Trend: {self._determine_overall_trend(market_data)}
- Volume: {'increasing' if self._is_volume_increasing(market_data) else 'decreasing'}

For each pattern, assess:
1. Reliability in current context
2. Adjusted price targets
3. Failure conditions

Provide a JSON response:
{{
    "pattern_analysis": [
        {{
            "pattern_type": "pattern name",
            "reliability": 0.0-1.0,
            "adjusted_target": price,
            "adjusted_stop": price,
            "key_factor": "most important consideration",
            "failure_condition": "what invalidates pattern"
        }}
    ]
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                analyses = data.get('pattern_analysis', [])
                
                # Apply enhancements
                for i, analysis in enumerate(analyses):
                    if i < len(patterns):
                        patterns[i].confidence *= analysis.get('reliability', 1.0)
                        if 'adjusted_target' in analysis:
                            patterns[i].price_target = analysis['adjusted_target']
                        if 'adjusted_stop' in analysis:
                            patterns[i].stop_loss = analysis['adjusted_stop']
                        patterns[i].metadata['ai_analysis'] = analysis
            
            return patterns
                
        except Exception as e:
            self.logger.error(f"AI pattern enhancement failed: {e}")
            return patterns
    
    async def _get_ai_market_synthesis(self, regime: MarketRegime,
                                     technical: TechnicalAnalysis,
                                     opportunities: List[Dict[str, Any]],
                                     risk: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI synthesis of complete market analysis."""
        if not self.ollama_client:
            return {'synthesis': 'No AI available'}
        
        prompt = f"""Synthesize this comprehensive market analysis:

Market Regime: {regime.value}
Trend: {technical.trend_direction} (strength: {technical.trend_strength:.1f})
Momentum: {technical.momentum:.2f}
Volatility: {technical.volatility:.1%}

Key Patterns: {len(technical.patterns)}
Trading Opportunities: {len(opportunities)}
Risk Level: {risk.get('overall_risk', 'medium')}

Top Opportunity:
{json.dumps(opportunities[0], indent=2) if opportunities else 'None'}

Provide a JSON response with executive summary:
{{
    "market_outlook": "1-2 sentence summary",
    "trading_bias": "bullish/bearish/neutral",
    "best_strategy": "recommended trading approach",
    "key_risks": ["risk1", "risk2"],
    "conviction_level": 0.0-1.0,
    "time_horizon": "intraday/swing/position"
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            else:
                return {'synthesis': 'Failed to parse'}
                
        except Exception as e:
            self.logger.error(f"AI market synthesis failed: {e}")
            return {'error': str(e)}
    
    async def _get_ai_signal_confirmation(self, direction: str,
                                        analysis: MarketAnalysis,
                                        strength: float) -> Dict[str, Any]:
        """Get AI confirmation for trading signal."""
        if not self.ollama_client:
            return {'confirm': True, 'confidence_adjustment': 1.0}
        
        prompt = f"""Confirm this trading signal:

Signal Direction: {direction}
Signal Strength: {strength:.2f}
Market Regime: {analysis.current_regime.value}
Technical Trend: {analysis.technical_analysis.trend_direction}

Supporting Factors:
- Patterns: {len(analysis.technical_analysis.patterns)}
- Momentum: {analysis.technical_analysis.momentum:.2f}
- Risk Level: {analysis.risk_assessment.get('overall_risk', 'medium')}

Should we take this trade? Consider:
1. Confluence of signals
2. Risk/reward setup
3. Market conditions

Provide a JSON response:
{{
    "confirm": true/false,
    "confidence_adjustment": 0.5-1.5,
    "reasoning": "explanation",
    "concerns": ["concern1", "concern2"]
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            else:
                return {'confirm': True, 'confidence_adjustment': 1.0}
                
        except Exception as e:
            self.logger.error(f"AI signal confirmation failed: {e}")
            return {'confirm': True, 'confidence_adjustment': 1.0}
    
    # ==========================================================================
    # ANALYSIS METHODS
    # ==========================================================================
    
    def _analyze_trend(self, indicators: Dict[str, float]) -> Tuple[str, float]:
        """Analyze trend direction and strength."""
        # Moving average analysis
        sma_20 = indicators.get('SMA_20', 0)
        sma_50 = indicators.get('SMA_50', 0)
        sma_200 = indicators.get('SMA_200', 0)
        
        if not sma_20:
            return 'sideways', 0.0
        
        current_price = self.price_history[-1].close if self.price_history else sma_20
        
        # Trend direction
        bullish_count = 0
        bearish_count = 0
        
        if current_price > sma_20:
            bullish_count += 1
        else:
            bearish_count += 1
        
        if sma_20 > sma_50 > 0:
            bullish_count += 1
        elif sma_50 > sma_20 > 0:
            bearish_count += 1
        
        if sma_50 > sma_200 > 0:
            bullish_count += 1
        elif sma_200 > sma_50 > 0:
            bearish_count += 1
        
        # MACD
        macd = indicators.get('MACD', 0)
        macd_signal = indicators.get('MACD_Signal', 0)
        
        if macd > macd_signal:
            bullish_count += 1
        else:
            bearish_count += 1
        
        # Determine direction
        if bullish_count > bearish_count + 1:
            direction = 'up'
        elif bearish_count > bullish_count + 1:
            direction = 'down'
        else:
            direction = 'sideways'
        
        # Trend strength (0-1)
        total_signals = bullish_count + bearish_count
        strength = abs(bullish_count - bearish_count) / total_signals if total_signals > 0 else 0
        
        return direction, strength
    
    def _calculate_momentum(self, indicators: Dict[str, float]) -> float:
        """Calculate market momentum (-1 to 1)."""
        momentum_scores = []
        
        # RSI momentum
        rsi = indicators.get('RSI', 50)
        rsi_momentum = (rsi - 50) / 50
        momentum_scores.append(rsi_momentum)
        
        # MACD momentum
        macd_hist = indicators.get('MACD_Histogram', 0)
        if macd_hist != 0:
            # Normalize MACD histogram
            recent_prices = [d.close for d in list(self.price_history)[-20:]]
            if recent_prices:
                price_scale = np.mean(recent_prices)
                macd_momentum = np.clip(macd_hist / (price_scale * 0.01), -1, 1)
                momentum_scores.append(macd_momentum)
        
        # Stochastic momentum
        stoch_k = indicators.get('Stochastic_K', 50)
        stoch_momentum = (stoch_k - 50) / 50
        momentum_scores.append(stoch_momentum)
        
        # Average momentum
        return np.mean(momentum_scores) if momentum_scores else 0.0
    
    def _calculate_volatility(self, market_data: List[MarketData]) -> float:
        """Calculate current volatility."""
        if len(market_data) < 2:
            return 0.0
        
        returns = []
        for i in range(1, len(market_data)):
            ret = np.log(market_data[i].close / market_data[i-1].close)
            returns.append(ret)
        
        # Annualized volatility
        return np.std(returns) * np.sqrt(252) if returns else 0.0
    
    def _analyze_volume(self, market_data: List[MarketData]) -> Dict[str, Any]:
        """Analyze volume patterns."""
        if not market_data:
            return {}
        
        volumes = [d.volume for d in market_data]
        closes = [d.close for d in market_data]
        
        analysis = {
            'average_volume': np.mean(volumes) if volumes else 0,
            'volume_trend': 'neutral',
            'volume_price_correlation': 0.0,
            'unusual_volume': False,
            'accumulation_distribution': 'neutral'
        }
        
        if len(volumes) > 20:
            # Volume trend
            recent_avg = np.mean(volumes[-10:])
            older_avg = np.mean(volumes[-20:-10])
            
            if recent_avg > older_avg * 1.2:
                analysis['volume_trend'] = 'increasing'
            elif recent_avg < older_avg * 0.8:
                analysis['volume_trend'] = 'decreasing'
            
            # Volume-price correlation
            if len(volumes) == len(closes):
                analysis['volume_price_correlation'] = np.corrcoef(volumes, closes)[0, 1]
            
            # Unusual volume
            std_vol = np.std(volumes)
            if volumes[-1] > analysis['average_volume'] + 2 * std_vol:
                analysis['unusual_volume'] = True
            
            # Accumulation/Distribution
            ad_line = 0
            for i in range(1, len(market_data)):
                money_flow_mult = ((market_data[i].close - market_data[i].low) - 
                                 (market_data[i].high - market_data[i].close)) / \
                                 (market_data[i].high - market_data[i].low + 0.0001)
                money_flow_vol = money_flow_mult * market_data[i].volume
                ad_line += money_flow_vol
            
            if ad_line > 0:
                analysis['accumulation_distribution'] = 'accumulation'
            else:
                analysis['accumulation_distribution'] = 'distribution'
        
        return analysis
    
    def _analyze_microstructure(self, market_data: List[MarketData]) -> Dict[str, Any]:
        """Analyze market microstructure."""
        microstructure = {
            'avg_spread': 0.0,
            'spread_volatility': 0.0,
            'price_efficiency': 0.0,
            'tick_distribution': 'normal'
        }
        
        spreads = []
        for data in market_data:
            if data.bid and data.ask:
                spread = (data.ask - data.bid) / data.bid
                spreads.append(spread)
        
        if spreads:
            microstructure['avg_spread'] = np.mean(spreads)
            microstructure['spread_volatility'] = np.std(spreads)
        
        # Price efficiency (simplified - how quickly price reverts to VWAP)
        vwaps = [d.vwap for d in market_data if d.vwap]
        closes = [d.close for d in market_data if d.vwap]
        
        if vwaps and closes and len(vwaps) == len(closes):
            deviations = [abs(c - v) / v for c, v in zip(closes, vwaps)]
            microstructure['price_efficiency'] = 1 - np.mean(deviations)
        
        return microstructure
    
    def _analyze_correlations(self, market_data: List[MarketData]) -> Dict[str, float]:
        """Analyze correlations (simplified)."""
        # In production, would correlate with other assets
        correlations = {
            'vix_correlation': -0.7,  # Typical SPY-VIX correlation
            'bond_correlation': 0.3,   # Typical stock-bond correlation
            'dollar_correlation': -0.2 # Typical SPY-USD correlation
        }
        
        # Add autocorrelation
        if len(market_data) > 20:
            returns = []
            for i in range(1, len(market_data)):
                ret = (market_data[i].close - market_data[i-1].close) / market_data[i-1].close
                returns.append(ret)
            
            if len(returns) > 1:
                correlations['autocorrelation'] = np.corrcoef(returns[:-1], returns[1:])[0, 1]
        
        return correlations
    
    async def _identify_event_risks(self, symbol: str) -> List[Dict[str, Any]]:
        """Identify upcoming event risks."""
        # Simplified - in production would check economic calendar
        events = []
        
        # Common market events
        now = datetime.now()
        
        # FOMC meetings (simplified - 3rd Wednesday of certain months)
        if now.day <= 20 and now.weekday() <= 2:  # Before Wednesday
            events.append({
                'event': 'FOMC Meeting',
                'date': 'This Week',
                'impact': 'high',
                'expected_volatility': 'elevated'
            })
        
        # Options expiration (3rd Friday)
        if 15 <= now.day <= 21 and now.weekday() <= 4:
            events.append({
                'event': 'Options Expiration',
                'date': 'This Week',
                'impact': 'medium',
                'expected_volatility': 'increased'
            })
        
        # Earnings season (simplified)
        if now.month in [1, 4, 7, 10]:
            events.append({
                'event': 'Earnings Season',
                'date': 'This Month',
                'impact': 'medium',
                'expected_volatility': 'variable'
            })
        
        return events
    
    async def _find_trading_opportunities(self, technical: TechnicalAnalysis,
                                        regime: MarketRegime,
                                        microstructure: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find trading opportunities based on analysis."""
        opportunities = []
        
        # Pattern-based opportunities
        for pattern in technical.patterns[:3]:  # Top 3 patterns
            if pattern.confidence > 0.7:
                opportunities.append({
                    'type': 'pattern',
                    'description': pattern.description,
                    'entry': pattern.price_target,
                    'stop': pattern.stop_loss,
                    'confidence': pattern.confidence,
                    'timeframe': 'swing'
                })
        
        # Support/Resistance opportunities
        current_price = self.price_history[-1].close if self.price_history else 0
        
        # Near support
        for support in technical.support_levels[:2]:
            if current_price > support and (current_price - support) / support < 0.02:
                opportunities.append({
                    'type': 'support_bounce',
                    'description': f"Near support at {support:.2f}",
                    'entry': support * 1.001,
                    'stop': support * 0.995,
                    'target': support * 1.02,
                    'confidence': 0.65,
                    'timeframe': 'intraday'
                })
        
        # Momentum opportunities
        if abs(technical.momentum) > 0.5:
            direction = 'long' if technical.momentum > 0 else 'short'
            opportunities.append({
                'type': 'momentum',
                'description': f"Strong {direction} momentum",
                'entry': current_price,
                'stop': current_price * (0.99 if direction == 'long' else 1.01),
                'target': current_price * (1.02 if direction == 'long' else 0.98),
                'confidence': abs(technical.momentum),
                'timeframe': 'intraday'
            })
        
        # Sort by confidence
        opportunities.sort(key=lambda x: x['confidence'], reverse=True)
        
        return opportunities[:5]  # Top 5
    
    def _assess_market_risk(self, regime: MarketRegime,
                          technical: TechnicalAnalysis,
                          microstructure: Dict[str, Any]) -> Dict[str, Any]:
        """Assess overall market risk."""
        risk_factors = []
        risk_score = 0
        
        # Regime risk
        if regime in [MarketRegime.BEAR_VOLATILE, MarketRegime.TRANSITIONING]:
            risk_factors.append("Unstable market regime")
            risk_score += 3
        elif regime == MarketRegime.BEAR_QUIET:
            risk_factors.append("Bearish regime")
            risk_score += 2
        
        # Volatility risk
        if technical.volatility > 0.25:  # 25% annualized
            risk_factors.append("High volatility")
            risk_score += 2
        
        # Technical risk
        if technical.indicators.get('RSI', 50) > 70:
            risk_factors.append("Overbought conditions")
            risk_score += 1
        elif technical.indicators.get('RSI', 50) < 30:
            risk_factors.append("Oversold conditions")
            risk_score += 1
        
        # Microstructure risk
        if microstructure.get('avg_spread', 0) > 0.002:  # 0.2%
            risk_factors.append("Wide spreads")
            risk_score += 1
        
        # Overall risk level
        if risk_score >= 6:
            overall_risk = 'high'
        elif risk_score >= 3:
            overall_risk = 'medium'
        else:
            overall_risk = 'low'
        
        return {
            'overall_risk': overall_risk,
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'recommended_position_size': max(0.2, 1 - (risk_score * 0.1)),
            'hedging_recommended': risk_score >= 4
        }
    
    # ==========================================================================
    # SIGNAL GENERATION METHODS
    # ==========================================================================
    
    def _check_trading_conditions(self, analysis: MarketAnalysis) -> bool:
        """Check if trading conditions are favorable."""
        # Risk check
        if analysis.risk_assessment.get('overall_risk') == 'high':
            return False
        
        # Regime check
        if analysis.current_regime == MarketRegime.TRANSITIONING:
            return False
        
        # Confidence check
        if analysis.regime_confidence < 0.6:
            return False
        
        # Opportunity check
        if not analysis.trading_opportunities:
            return False
        
        return True
    
    def _determine_signal_direction(self, analysis: MarketAnalysis) -> str:
        """Determine trading signal direction."""
        votes = {'long': 0, 'short': 0, 'neutral': 0}
        
        # Technical trend
        if analysis.technical_analysis.trend_direction == 'up':
            votes['long'] += 2
        elif analysis.technical_analysis.trend_direction == 'down':
            votes['short'] += 2
        else:
            votes['neutral'] += 1
        
        # Momentum
        if analysis.technical_analysis.momentum > 0.3:
            votes['long'] += 1
        elif analysis.technical_analysis.momentum < -0.3:
            votes['short'] += 1
        
        # Regime
        if analysis.current_regime in [MarketRegime.BULL_QUIET, MarketRegime.BULL_VOLATILE]:
            votes['long'] += 1
        elif analysis.current_regime in [MarketRegime.BEAR_QUIET, MarketRegime.BEAR_VOLATILE]:
            votes['short'] += 1
        
        # Patterns
        bullish_patterns = sum(1 for p in analysis.technical_analysis.patterns
                             if 'bullish' in p.description.lower())
        bearish_patterns = sum(1 for p in analysis.technical_analysis.patterns
                             if 'bearish' in p.description.lower())
        
        votes['long'] += bullish_patterns
        votes['short'] += bearish_patterns
        
        # Determine winner
        max_votes = max(votes.values())
        if votes['long'] == max_votes and votes['long'] > votes['short']:
            return 'long'
        elif votes['short'] == max_votes and votes['short'] > votes['long']:
            return 'short'
        else:
            return 'neutral'
    
    def _calculate_signal_levels(self, direction: str, current_price: float,
                               analysis: MarketAnalysis) -> Tuple[float, float, float]:
        """Calculate entry, target, and stop levels."""
        # Get ATR for position sizing
        atr = analysis.technical_analysis.indicators.get('ATR', current_price * 0.01)
        
        if direction == 'long':
            # Entry slightly above current
            entry = current_price * 1.001
            
            # Target based on resistance or ATR
            if analysis.technical_analysis.resistance_levels:
                target = min(analysis.technical_analysis.resistance_levels[0],
                           entry + (2 * atr))
            else:
                target = entry + (2 * atr)
            
            # Stop based on support or ATR
            if analysis.technical_analysis.support_levels:
                stop = max(analysis.technical_analysis.support_levels[0],
                          entry - (1.5 * atr))
            else:
                stop = entry - (1.5 * atr)
        
        else:  # short
            # Entry slightly below current
            entry = current_price * 0.999
            
            # Target based on support or ATR
            if analysis.technical_analysis.support_levels:
                target = max(analysis.technical_analysis.support_levels[0],
                           entry - (2 * atr))
            else:
                target = entry - (2 * atr)
            
            # Stop based on resistance or ATR
            if analysis.technical_analysis.resistance_levels:
                stop = min(analysis.technical_analysis.resistance_levels[0],
                          entry + (1.5 * atr))
            else:
                stop = entry + (1.5 * atr)
        
        return entry, target, stop
    
    def _calculate_signal_strength(self, analysis: MarketAnalysis) -> float:
        """Calculate signal strength (0-1)."""
        strength_factors = []
        
        # Trend strength
        strength_factors.append(analysis.technical_analysis.trend_strength)
        
        # Momentum strength
        strength_factors.append(abs(analysis.technical_analysis.momentum))
        
        # Pattern confidence
        if analysis.technical_analysis.patterns:
            avg_pattern_conf = np.mean([p.confidence for p in analysis.technical_analysis.patterns[:3]])
            strength_factors.append(avg_pattern_conf)
        
        # Volume confirmation
        vol_analysis = analysis.technical_analysis.volume_analysis
        if vol_analysis.get('volume_trend') == 'increasing':
            strength_factors.append(0.8)
        else:
            strength_factors.append(0.5)
        
        # Regime confidence
        strength_factors.append(analysis.regime_confidence)
        
        return np.mean(strength_factors) if strength_factors else 0.5
    
    def _build_signal_reasoning(self, direction: str,
                              analysis: MarketAnalysis) -> List[str]:
        """Build reasoning for signal."""
        reasoning = []
        
        # Trend reason
        trend = analysis.technical_analysis.trend_direction
        if trend != 'sideways':
            reasoning.append(f"{trend.capitalize()}trend confirmed by multiple timeframes")
        
        # Momentum reason
        momentum = analysis.technical_analysis.momentum
        if abs(momentum) > 0.3:
            reasoning.append(f"Strong {'positive' if momentum > 0 else 'negative'} momentum")
        
        # Pattern reasons
        for pattern in analysis.technical_analysis.patterns[:2]:
            reasoning.append(f"{pattern.pattern_type.value} pattern (confidence: {pattern.confidence:.0%})")
        
        # Regime reason
        regime = analysis.current_regime
        reasoning.append(f"Market in {regime.value} regime")
        
        # Volume reason
        vol_trend = analysis.technical_analysis.volume_analysis.get('volume_trend')
        if vol_trend == 'increasing':
            reasoning.append("Increasing volume confirms move")
        
        return reasoning[:5]  # Top 5 reasons
    
    def _determine_signal_timeframe(self, analysis: MarketAnalysis) -> str:
        """Determine appropriate timeframe for signal."""
        # Based on volatility and patterns
        volatility = analysis.technical_analysis.volatility
        
        if volatility > 0.3:  # High volatility
            return 'intraday'
        
        # Check pattern timeframes
        pattern_timeframes = []
        for pattern in analysis.technical_analysis.patterns:
            time_diff = (pattern.end_time - pattern.start_time).total_seconds() / 3600
            if time_diff < 24:
                pattern_timeframes.append('intraday')
            elif time_diff < 120:
                pattern_timeframes.append('swing')
            else:
                pattern_timeframes.append('position')
        
        if pattern_timeframes:
            # Most common timeframe
            return max(set(pattern_timeframes), key=pattern_timeframes.count)
        
        # Default based on regime
        if analysis.current_regime in [MarketRegime.BULL_QUIET, MarketRegime.BEAR_QUIET]:
            return 'position'
        else:
            return 'swing'
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def _bb_position(self, indicators: Dict[str, float]) -> float:
        """Calculate position within Bollinger Bands."""
        upper = indicators.get('BB_Upper', 0)
        lower = indicators.get('BB_Lower', 0)
        current = self.price_history[-1].close if self.price_history else 0
        
        if upper == lower or upper == 0:
            return 0.5
        
        return (current - lower) / (upper - lower)
    
    def _format_patterns(self, patterns: List[Pattern]) -> str:
        """Format patterns for AI prompt."""
        if not patterns:
            return "None"
        
        formatted = []
        for p in patterns:
            formatted.append(f"- {p.pattern_type.value}: confidence {p.confidence:.0%}")
        
        return "\n".join(formatted)
    
    def _format_patterns_detailed(self, patterns: List[Pattern]) -> str:
        """Format patterns with details for AI."""
        if not patterns:
            return "None"
        
        formatted = []
        for p in patterns:
            formatted.append(f"""- Pattern: {p.pattern_type.value}
  Confidence: {p.confidence:.0%}
  Target: ${p.price_target:.2f} if p.price_target else 'N/A'
  Stop: ${p.stop_loss:.2f} if p.stop_loss else 'N/A'""")
        
        return "\n".join(formatted)
    
    def _describe_price_pattern(self, prices: List[float]) -> str:
        """Describe recent price pattern."""
        if len(prices) < 5:
            return "Insufficient data"
        
        # Check for trends
        first_half = np.mean(prices[:len(prices)//2])
        second_half = np.mean(prices[len(prices)//2:])
        
        if second_half > first_half * 1.02:
            pattern = "Strong upward movement"
        elif second_half < first_half * 0.98:
            pattern = "Strong downward movement"
        else:
            pattern = "Sideways consolidation"
        
        # Check for volatility
        returns = [abs(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        avg_move = np.mean(returns)
        
        if avg_move > 0.02:
            pattern += " with high volatility"
        elif avg_move < 0.005:
            pattern += " with low volatility"
        
        return pattern
    
    def _determine_overall_trend(self, market_data: List[MarketData]) -> str:
        """Determine overall trend from market data."""
        if len(market_data) < 20:
            return "unclear"
        
        closes = [d.close for d in market_data]
        sma_20 = np.mean(closes[-20:])
        current = closes[-1]
        
        if current > sma_20 * 1.02:
            return "strong uptrend"
        elif current > sma_20:
            return "uptrend"
        elif current < sma_20 * 0.98:
            return "strong downtrend"
        elif current < sma_20:
            return "downtrend"
        else:
            return "sideways"
    
    def _is_volume_increasing(self, market_data: List[MarketData]) -> bool:
        """Check if volume is increasing."""
        if len(market_data) < 10:
            return False
        
        volumes = [d.volume for d in market_data]
        recent_avg = np.mean(volumes[-5:])
        older_avg = np.mean(volumes[-10:-5])
        
        return recent_avg > older_avg * 1.1
    
    def _create_default_analysis(self) -> MarketAnalysis:
        """Create default analysis for error cases."""
        return MarketAnalysis(
            timestamp=datetime.now(),
            current_regime=MarketRegime.RANGING,
            regime_confidence=0.5,
            technical_analysis=TechnicalAnalysis(
                timestamp=datetime.now(),
                indicators={},
                patterns=[],
                support_levels=[],
                resistance_levels=[],
                trend_direction='sideways',
                trend_strength=0.0,
                momentum=0.0,
                volatility=0.2,
                volume_analysis={},
                ai_insights={}
            ),
            microstructure={},
            correlation_analysis={},
            event_risks=[],
            trading_opportunities=[],
            risk_assessment={'overall_risk': 'medium'},
            ai_synthesis={'error': 'Analysis failed'}
        )

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_market_analysis_agent(model_name: str = DEFAULT_MODEL,
                               temperature: float = DEFAULT_TEMPERATURE) -> SpyderX13_MarketAnalysisAgent:
    """
    Factory function to create Market Analysis Agent instance.
    
    Args:
        model_name: Ollama model to use
        temperature: Temperature for AI responses
        
    Returns:
        SpyderX13_MarketAnalysisAgent instance
    """
    return SpyderX13_MarketAnalysisAgent(model_name, temperature)

# Singleton instance
_module_instance = None

def get_module_instance() -> SpyderX13_MarketAnalysisAgent:
    """Get or create singleton instance of the agent."""
    global _module_instance
    if _module_instance is None:
        _module_instance = create_market_analysis_agent()
    return _module_instance

# ==============================================================================
# TEST EXECUTION
# ==============================================================================

async def test_market_analysis():
    """Test the Market Analysis Agent functionality."""
    print("="*80)
    print("Testing SpyderX13_MarketAnalysisAgent")
    print("="*80)
    
    agent = create_market_analysis_agent()
    
    # Generate sample market data
    np.random.seed(42)
    market_data = []
    base_price = 450.0
    
    for i in range(100):
        # Simulate price movement
        returns = np.random.normal(0.0005, 0.015)
        base_price *= (1 + returns)
        
        # OHLC
        open_price = base_price
        high = base_price * (1 + abs(np.random.normal(0, 0.005)))
        low = base_price * (1 - abs(np.random.normal(0, 0.005)))
        close = base_price * (1 + np.random.normal(0, 0.002))
        
        # Update base price
        base_price = close
        
        market_data.append(MarketData(
            timestamp=datetime.now() - timedelta(minutes=(100-i)*5),
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=int(np.random.normal(1000000, 200000)),
            vwap=(high + low + close) / 3,
            bid=close - 0.01,
            ask=close + 0.01
        ))
    
    # Test 1: Market Analysis
    print("\nTest 1: Comprehensive Market Analysis")
    print("-"*40)
    
    analysis = await agent.analyze_market(market_data)
    
    print(f"Market Regime: {analysis.current_regime.value}")
    print(f"Regime Confidence: {analysis.regime_confidence:.1%}")
    
    print(f"\nTechnical Analysis:")
    print(f"  Trend: {analysis.technical_analysis.trend_direction} "
          f"(strength: {analysis.technical_analysis.trend_strength:.1f})")
    print(f"  Momentum: {analysis.technical_analysis.momentum:+.2f}")
    print(f"  Volatility: {analysis.technical_analysis.volatility:.1%}")
    print(f"  Patterns Found: {len(analysis.technical_analysis.patterns)}")
    
    print(f"\nKey Levels:")
    print(f"  Support: {analysis.technical_analysis.support_levels[:3]}")
    print(f"  Resistance: {analysis.technical_analysis.resistance_levels[:3]}")
    
    print(f"\nRisk Assessment:")
    print(f"  Overall Risk: {analysis.risk_assessment['overall_risk']}")
    print(f"  Risk Factors: {', '.join(analysis.risk_assessment['risk_factors'][:3])}")
    
    # Test 2: Pattern Detection
    print("\n\nTest 2: Pattern Detection")
    print("-"*40)
    
    patterns = await agent.detect_patterns(market_data[-50:])
    
    print(f"Detected {len(patterns)} patterns:")
    for pattern in patterns[:3]:
        print(f"\n  {pattern.pattern_type.value}:")
        print(f"    Confidence: {pattern.confidence:.1%}")
        if pattern.price_target:
            print(f"    Target: ${pattern.price_target:.2f}")
        if pattern.stop_loss:
            print(f"    Stop: ${pattern.stop_loss:.2f}")
        print(f"    Description: {pattern.description}")
    
    # Test 3: Trading Signal Generation
    print("\n\nTest 3: Trading Signal Generation")
    print("-"*40)
    
    signal = await agent.generate_trading_signal(analysis)
    
    if signal:
        print(f"Signal Generated:")
        print(f"  Direction: {signal.direction.upper()}")
        print(f"  Strength: {signal.strength:.1%}")
        print(f"  Entry: ${signal.entry_price:.2f}")
        print(f"  Target: ${signal.target_price:.2f}")
        print(f"  Stop Loss: ${signal.stop_loss:.2f}")
        print(f"  Risk/Reward: {signal.risk_reward_ratio:.2f}")
        print(f"  Timeframe: {signal.timeframe}")
        print(f"\nReasoning:")
        for reason in signal.reasoning:
            print(f"  - {reason}")
    else:
        print("No signal generated (conditions not met)")
    
    # Test 4: Technical Indicators
    print("\n\nTest 4: Technical Indicators")
    print("-"*40)
    
    indicators = analysis.technical_analysis.indicators
    print(f"RSI: {indicators.get('RSI', 0):.1f}")
    print(f"MACD: {indicators.get('MACD', 0):.3f}")
    print(f"Stochastic K: {indicators.get('Stochastic_K', 0):.1f}")
    print(f"ATR: {indicators.get('ATR', 0):.2f}")
    print(f"Bollinger Band Position: {agent._bb_position(indicators):.1%}")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print(f"Initializing {__name__}")
    print(f"Ollama Available: {OLLAMA_AVAILABLE}")
    
    # Run async tests
    asyncio.run(test_market_analysis())
    
    print("\n" + "="*80)
    print("SpyderX13_MarketAnalysisAgent module loaded successfully!")
    print("="*80)