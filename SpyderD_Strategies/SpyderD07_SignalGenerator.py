#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD07_SignalGenerator.py
Group: D (Trading Strategies)
Purpose: Entry/exit signal generation with time window filtering

Description:
    This module generates trading signals by combining multiple technical
    indicators, market internals, and pattern recognition. It provides a
    unified signal generation framework with research-driven entry time
    windows (10:15-11:40 AM) and time-based exits (12:00 PM).

Author: Mohamed Talib
Date: 2025-06-06
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import math
import statistics

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import SignalType
from SpyderU_Utilities.SpyderU11_FeatureFlags import get_feature_flags
from SpyderF_Analysis.SpyderF01_Indicators import TechnicalIndicators
from SpyderF_Analysis.SpyderF02_PriceAction import PriceActionAnalyzer
from SpyderF_Analysis.SpyderF03_SupportResistance import SupportResistanceAnalyzer
from SpyderF_Analysis.SpyderF04_VolatilityAnalysis import VolatilityAnalyzer
from SpyderF_Analysis.SpyderF05_TrendDetection import TrendDetector
from SpyderC_MarketData.SpyderC04_MarketInternals import MarketInternals
from SpyderC_MarketData.SpyderC05_VolumeProfile import VolumeProfileAnalyzer

# ==============================================================================
# CONSTANTS - UPDATED WITH RESEARCH FINDINGS
# ==============================================================================
# Signal thresholds
MIN_SIGNAL_SCORE = 0.6      # Minimum score to generate signal
MIN_CONFLUENCE = 3          # Minimum confirming indicators
MAX_SIGNALS_PER_BAR = 2     # Maximum signals per time period

# Entry time windows (from research)
OPTIMAL_ENTRY_START = time(10, 15)  # 10:15 AM
OPTIMAL_ENTRY_END = time(11, 40)    # 11:40 AM
TIME_BASED_EXIT = time(12, 0)       # 12:00 PM

# Indicator weights
WEIGHT_MOMENTUM = 0.20
WEIGHT_TREND = 0.20
WEIGHT_VOLUME = 0.15
WEIGHT_INTERNALS = 0.15
WEIGHT_SUPPORT_RESISTANCE = 0.15
WEIGHT_PATTERNS = 0.15

# Technical parameters
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
MACD_SIGNAL_THRESHOLD = 0.5
VOLUME_SURGE_MULTIPLIER = 1.5
MOMENTUM_THRESHOLD = 0.002  # 0.2% momentum

# Pattern recognition
MIN_PATTERN_QUALITY = 0.7
BREAKOUT_VOLUME_MULTIPLIER = 2.0
REVERSAL_DIVERGENCE_BARS = 5

# ==============================================================================
# ENUMS
# ==============================================================================
class SignalDirection(Enum):
    """Signal direction"""
    BULLISH = auto()
    BEARISH = auto()
    NEUTRAL = auto()

class SignalCategory(Enum):
    """Signal category"""
    MOMENTUM = auto()
    REVERSAL = auto()
    BREAKOUT = auto()
    CONTINUATION = auto()
    VOLATILITY = auto()
    TIME_EXIT = auto()  # New for time-based exits

class IndicatorState(Enum):
    """Indicator state"""
    BULLISH = auto()
    BEARISH = auto()
    NEUTRAL = auto()
    DIVERGENCE = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class IndicatorSignal:
    """Individual indicator signal"""
    indicator_name: str
    state: IndicatorState
    value: float
    threshold: float
    weight: float
    confidence: float
    notes: str = ""

@dataclass
class SignalComponents:
    """Components of a trading signal"""
    momentum_signals: List[IndicatorSignal]
    trend_signals: List[IndicatorSignal]
    volume_signals: List[IndicatorSignal]
    internal_signals: List[IndicatorSignal]
    pattern_signals: List[IndicatorSignal]
    support_resistance_signals: List[IndicatorSignal]

@dataclass
class TradingSignal:
    """Complete trading signal data"""
    timestamp: datetime
    direction: SignalDirection
    category: SignalCategory
    signal_type: SignalType
    score: float
    confidence: float
    confluence: int
    entry_price: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    components: SignalComponents
    risk_reward_ratio: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

@dataclass
class MarketContext:
    """Current market context for signal generation"""
    trend_direction: int  # -1, 0, 1
    trend_strength: float
    volatility: float
    volume_profile: str  # 'low', 'normal', 'high'
    market_phase: str  # 'accumulation', 'markup', 'distribution', 'markdown'
    key_levels: Dict[str, float]
    recent_patterns: List[str]

# ==============================================================================
# SIGNAL GENERATOR CLASS
# ==============================================================================
class SignalGenerator:
    """
    Generates trading signals with research-driven time window filtering.
    
    Combines technical analysis, market internals, and pattern recognition
    to generate high-confidence trading signals. Implements optimal entry
    window (10:15-11:40 AM) and time-based exit (12:00 PM).
    """
    
    def __init__(self):
        """Initialize signal generator"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Analysis components
        self.indicators = TechnicalIndicators()
        self.price_action = PriceActionAnalyzer()
        self.support_resistance = SupportResistanceAnalyzer()
        self.volatility_analyzer = VolatilityAnalyzer()
        self.trend_detector = TrendDetector()
        self.market_internals = MarketInternals()
        self.volume_profile = VolumeProfileAnalyzer()
        
        # Signal tracking
        self.recent_signals: List[TradingSignal] = []
        self.signal_history: List[Dict[str, Any]] = []
        self.open_positions: List[Dict[str, Any]] = []  # Track for time-based exits
        
        # Configuration
        self.config = {
            'use_internals': True,
            'use_patterns': True,
            'use_volume_profile': True,
            'min_confluence': MIN_CONFLUENCE,
            'min_score': MIN_SIGNAL_SCORE
        }
        
        self.logger.info("SignalGenerator initialized with time window filtering")
    
    # ==========================================================================
    # MAIN SIGNAL GENERATION WITH TIME WINDOWS
    # ==========================================================================
    def generate_signals(
        self,
        market_data: pd.DataFrame,
        strategy_type: Optional[str] = None,
        open_positions: Optional[List[Dict[str, Any]]] = None
    ) -> List[TradingSignal]:
        """
        Generate trading signals with entry time window filtering.
        
        Args:
            market_data: Market data DataFrame
            strategy_type: Optional strategy filter
            open_positions: Current open positions for time-based exits
            
        Returns:
            List of trading signals
        """
        signals = []
        
        if len(market_data) < 50:
            return signals
        
        try:
            # Update open positions tracking
            if open_positions:
                self.open_positions = open_positions
            
            # Check if we should exit existing positions by time
            if self._should_exit_by_time():
                # Generate exit signals for all open positions
                exit_signals = self._generate_time_based_exit_signals()
                if exit_signals:
                    signals.extend(exit_signals)
                    # Don't generate new entry signals if exiting
                    self.logger.info(
                        f"Generated {len(exit_signals)} time-based exit signals at {datetime.now().time()}"
                    )
                    return signals
            
            # Check if within optimal entry window
            if not self._is_optimal_entry_time():
                self.logger.debug(
                    f"Outside optimal entry window ({OPTIMAL_ENTRY_START}-{OPTIMAL_ENTRY_END}) "
                    f"- no new signals"
                )
                return signals
            
            # Analyze market context
            market_context = self._analyze_market_context(market_data)
            
            # Generate signals by category
            # Check for momentum signals
            momentum_signals = self._check_momentum_signals(market_data, market_context)
            signals.extend(momentum_signals)
            
            # Check for reversal signals
            reversal_signals = self._check_reversal_signals(market_data, market_context)
            signals.extend(reversal_signals)
            
            # Check for breakout signals
            breakout_signals = self._check_breakout_signals(market_data, market_context)
            signals.extend(breakout_signals)
            
            # Check for continuation signals
            continuation_signals = self._check_continuation_signals(market_data, market_context)
            signals.extend(continuation_signals)
            
            # Filter and rank signals
            signals = self._filter_and_rank_signals(signals, strategy_type)
            
            # Add entry window metadata to all signals
            for signal in signals:
                signal.metadata['entry_time_optimal'] = True
                signal.metadata['entry_window'] = f"{OPTIMAL_ENTRY_START}-{OPTIMAL_ENTRY_END}"
                signal.metadata['current_time'] = datetime.now().time().strftime('%H:%M:%S')
            
            # Store recent signals
            self.recent_signals = signals
            self._update_signal_history(signals)
            
            # Log signal generation with time info
            self.logger.info(
                f"Generated {len(signals)} signals at {datetime.now().time()} "
                f"(Within optimal window: {self._is_optimal_entry_time()})"
            )
            
        except Exception as e:
            self.logger.error(f"Error generating signals: {e}")
            self.error_handler.handle_error(e, "SignalGenerator")
        
        return signals
    
    # ==========================================================================
    # TIME WINDOW METHODS (NEW)
    # ==========================================================================
    def _is_optimal_entry_time(self) -> bool:
        """
        Check if current time is within optimal entry window.
        Research shows 10:15 AM - 11:40 AM is optimal for entry.
        
        Returns:
            bool: True if within optimal window
        """
        flags = get_feature_flags()
        if not flags.is_enabled('optimal_entry_window'):
            return True  # No restriction if feature is disabled
        
        current_time = datetime.now().time()
        in_window = OPTIMAL_ENTRY_START <= current_time <= OPTIMAL_ENTRY_END
        
        if not in_window:
            self.logger.debug(
                f"Outside optimal entry window. Current: {current_time}, "
                f"Window: {OPTIMAL_ENTRY_START}-{OPTIMAL_ENTRY_END}"
            )
        
        return in_window
    
    def _should_exit_by_time(self) -> bool:
        """
        Check if positions should be exited based on time.
        Research suggests exiting by 12:00 PM for optimal results.
        
        Returns:
            bool: True if should exit
        """
        flags = get_feature_flags()
        if not flags.is_enabled('time_based_exit'):
            return False
        
        current_time = datetime.now().time()
        should_exit = current_time >= TIME_BASED_EXIT
        
        if should_exit and self.open_positions:
            self.logger.info(f"Time-based exit triggered at {current_time}")
        
        return should_exit
    
    def _generate_time_based_exit_signals(self) -> List[TradingSignal]:
        """
        Generate exit signals for time-based exit at 12:00 PM.
        
        Returns:
            List of exit signals
        """
        exit_signals = []
        
        if not self.open_positions:
            return exit_signals
        
        current_time = datetime.now()
        
        for position in self.open_positions:
            # Create exit signal for each open position
            signal = TradingSignal(
                timestamp=current_time,
                direction=SignalDirection.NEUTRAL,  # Exit signal
                category=SignalCategory.TIME_EXIT,
                signal_type=SignalType.EXIT,
                score=1.0,  # Maximum score for time-based exit
                confidence=1.0,  # High confidence
                confluence=1,  # Single rule
                entry_price=None,  # N/A for exits
                stop_loss=None,
                take_profit=None,
                components=self._create_empty_components(),  # Empty components
                risk_reward_ratio=0.0,
                metadata={
                    'reason': 'time_based_exit',
                    'exit_time': TIME_BASED_EXIT.strftime('%H:%M'),
                    'position_id': position.get('id', 'unknown'),
                    'symbol': position.get('symbol', 'SPY'),
                    'contracts': position.get('contracts', 0),
                    'message': 'Exiting position at 12:00 PM per research'
                },
                notes=['Time-based exit at 12:00 PM', 'Research-driven exit rule']
            )
            
            exit_signals.append(signal)
        
        return exit_signals
    
    def get_entry_window_status(self) -> Dict[str, Any]:
        """
        Get current entry window status.
        
        Returns:
            Dict with window status information
        """
        current_time = datetime.now().time()
        in_window = self._is_optimal_entry_time()
        
        # Calculate time until window opens/closes
        if current_time < OPTIMAL_ENTRY_START:
            time_until = self._time_difference(current_time, OPTIMAL_ENTRY_START)
            status = "before_window"
            next_event = "window_opens"
        elif current_time > OPTIMAL_ENTRY_END:
            # Calculate time until tomorrow's window
            tomorrow_open = datetime.combine(
                datetime.now().date() + timedelta(days=1),
                OPTIMAL_ENTRY_START
            )
            time_until = str(tomorrow_open - datetime.now())
            status = "after_window"
            next_event = "next_window_opens"
        else:
            time_until = self._time_difference(current_time, OPTIMAL_ENTRY_END)
            status = "in_window"
            next_event = "window_closes"
        
        # Check if approaching exit time
        approaching_exit = False
        if current_time < TIME_BASED_EXIT:
            time_to_exit = self._time_difference(current_time, TIME_BASED_EXIT)
            approaching_exit = current_time >= time(11, 45)  # 15 min warning
        else:
            time_to_exit = "Passed"
        
        return {
            'current_time': current_time.strftime('%H:%M:%S'),
            'window_start': OPTIMAL_ENTRY_START.strftime('%H:%M'),
            'window_end': OPTIMAL_ENTRY_END.strftime('%H:%M'),
            'exit_time': TIME_BASED_EXIT.strftime('%H:%M'),
            'in_window': in_window,
            'status': status,
            'next_event': next_event,
            'time_until': time_until,
            'time_to_exit': time_to_exit,
            'approaching_exit': approaching_exit,
            'feature_enabled': get_feature_flags().is_enabled('optimal_entry_window'),
            'exit_enabled': get_feature_flags().is_enabled('time_based_exit')
        }
    
    def _time_difference(self, time1: time, time2: time) -> str:
        """Calculate time difference as string"""
        # Convert to datetime for calculation
        today = datetime.now().date()
        dt1 = datetime.combine(today, time1)
        dt2 = datetime.combine(today, time2)
        
        diff = dt2 - dt1
        if diff.total_seconds() < 0:
            # Handle case where time2 is tomorrow
            dt2 = datetime.combine(today + timedelta(days=1), time2)
            diff = dt2 - dt1
        
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    # ==========================================================================
    # MARKET ANALYSIS
    # ==========================================================================
    def _analyze_market_context(self, market_data: pd.DataFrame) -> MarketContext:
        """Analyze overall market context"""
        # Trend analysis
        trend_info = self.trend_detector.detect_trend(market_data)
        trend_direction = 1 if trend_info['direction'] > 0 else -1 if trend_info['direction'] < 0 else 0
        trend_strength = trend_info['strength']
        
        # Volatility
        volatility = self.volatility_analyzer.calculate_volatility(market_data)
        
        # Volume profile
        volume_analysis = self.volume_profile.analyze(market_data)
        volume_profile = 'high' if volume_analysis['relative_volume'] > 1.5 else 'low' if volume_analysis['relative_volume'] < 0.5 else 'normal'
        
        # Market phase
        market_phase = self._determine_market_phase(market_data, trend_info)
        
        # Key levels
        key_levels = self._find_key_levels(market_data)
        
        # Recent patterns
        recent_patterns = self.price_action.find_patterns(market_data)
        
        return MarketContext(
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            volatility=volatility['current_volatility'],
            volume_profile=volume_profile,
            market_phase=market_phase,
            key_levels=key_levels,
            recent_patterns=[p['pattern'] for p in recent_patterns[-5:]]
        )
    
    # ==========================================================================
    # SIGNAL TYPES
    # ==========================================================================
    def _check_momentum_signals(
        self,
        market_data: pd.DataFrame,
        context: MarketContext
    ) -> List[TradingSignal]:
        """Check for momentum-based signals"""
        signals = []
        current_price = market_data['close'].iloc[-1]
        
        # Get indicator signals
        components = self._get_momentum_components(market_data, context)
        
        # Calculate signal score
        score, direction = self._calculate_component_score(components)
        
        if score >= self.config['min_score']:
            # Determine entry and exits
            entry_price = current_price
            atr = self.indicators.atr(market_data['high'], market_data['low'], market_data['close'])
            
            if direction == SignalDirection.BULLISH:
                stop_loss = entry_price - atr.iloc[-1] * 2
                take_profit = entry_price + atr.iloc[-1] * 3
            else:
                stop_loss = entry_price + atr.iloc[-1] * 2
                take_profit = entry_price - atr.iloc[-1] * 3
            
            # Create signal
            signal = TradingSignal(
                timestamp=datetime.now(),
                direction=direction,
                category=SignalCategory.MOMENTUM,
                signal_type=SignalType.BUY if direction == SignalDirection.BULLISH else SignalType.SELL,
                score=score,
                confidence=self._calculate_confidence(components),
                confluence=self._count_confluence(components),
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                components=components,
                risk_reward_ratio=abs(take_profit - entry_price) / abs(entry_price - stop_loss),
                notes=self._generate_signal_notes(components, context)
            )
            
            signals.append(signal)
        
        return signals
    
    def _check_reversal_signals(
        self,
        market_data: pd.DataFrame,
        context: MarketContext
    ) -> List[TradingSignal]:
        """Check for reversal signals"""
        signals = []
        current_price = market_data['close'].iloc[-1]
        
        # Look for divergences
        divergences = self._find_divergences(market_data)
        
        # Check support/resistance tests
        sr_tests = self._check_sr_tests(market_data, context)
        
        # Pattern-based reversals
        reversal_patterns = self._find_reversal_patterns(market_data)
        
        # Combine reversal indicators
        for div in divergences:
            components = self._build_reversal_components(div, sr_tests, reversal_patterns, market_data)
            score, direction = self._calculate_component_score(components)
            
            if score >= self.config['min_score']:
                # Reversal trades often have tighter stops
                atr = self.indicators.atr(market_data['high'], market_data['low'], market_data['close'])
                
                if direction == SignalDirection.BULLISH:
                    stop_loss = min(market_data['low'].iloc[-5:]) - atr.iloc[-1] * 0.5
                    take_profit = current_price + atr.iloc[-1] * 2.5
                else:
                    stop_loss = max(market_data['high'].iloc[-5:]) + atr.iloc[-1] * 0.5
                    take_profit = current_price - atr.iloc[-1] * 2.5
                
                signal = TradingSignal(
                    timestamp=datetime.now(),
                    direction=direction,
                    category=SignalCategory.REVERSAL,
                    signal_type=SignalType.BUY if direction == SignalDirection.BULLISH else SignalType.SELL,
                    score=score,
                    confidence=self._calculate_confidence(components),
                    confluence=self._count_confluence(components),
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    components=components,
                    risk_reward_ratio=abs(take_profit - current_price) / abs(current_price - stop_loss),
                    notes=self._generate_signal_notes(components, context) + [f"Divergence: {div['type']}"]
                )
                
                signals.append(signal)
        
        return signals
    
    def _check_breakout_signals(
        self,
        market_data: pd.DataFrame,
        context: MarketContext
    ) -> List[TradingSignal]:
        """Check for breakout signals"""
        signals = []
        current_price = market_data['close'].iloc[-1]
        
        # Find breakout levels
        breakout_levels = self._find_breakout_levels(market_data, context)
        
        for level in breakout_levels:
            if self._confirm_breakout(market_data, level):
                components = self._build_breakout_components(level, market_data, context)
                score, direction = self._calculate_component_score(components)
                
                if score >= self.config['min_score']:
                    # Breakout trades use the level as stop
                    if direction == SignalDirection.BULLISH:
                        stop_loss = level['price'] - (current_price - level['price']) * 0.5
                        take_profit = current_price + (current_price - level['price']) * 2
                    else:
                        stop_loss = level['price'] + (level['price'] - current_price) * 0.5
                        take_profit = current_price - (level['price'] - current_price) * 2
                    
                    signal = TradingSignal(
                        timestamp=datetime.now(),
                        direction=direction,
                        category=SignalCategory.BREAKOUT,
                        signal_type=SignalType.BUY if direction == SignalDirection.BULLISH else SignalType.SELL,
                        score=score,
                        confidence=self._calculate_confidence(components),
                        confluence=self._count_confluence(components),
                        entry_price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        components=components,
                        risk_reward_ratio=abs(take_profit - current_price) / abs(current_price - stop_loss),
                        notes=self._generate_signal_notes(components, context) + [f"Breakout: {level['type']} at {level['price']:.2f}"]
                    )
                    
                    signals.append(signal)
        
        return signals
    
    def _check_continuation_signals(
        self,
        market_data: pd.DataFrame,
        context: MarketContext
    ) -> List[TradingSignal]:
        """Check for trend continuation signals"""
        signals = []
        
        # Only look for continuation in trending markets
        if abs(context.trend_direction) == 0 or context.trend_strength < 0.4:
            return signals
        
        current_price = market_data['close'].iloc[-1]
        
        # Look for pullbacks to key levels
        pullbacks = self._find_pullbacks(market_data, context)
        
        for pullback in pullbacks:
            components = self._build_continuation_components(pullback, market_data, context)
            score, direction = self._calculate_component_score(components)
            
            # Continuation should align with trend
            if (score >= self.config['min_score'] and
                ((direction == SignalDirection.BULLISH and context.trend_direction > 0) or
                 (direction == SignalDirection.BEARISH and context.trend_direction < 0))):
                
                # Use trend structure for stops
                atr = self.indicators.atr(market_data['high'], market_data['low'], market_data['close'])
                
                if direction == SignalDirection.BULLISH:
                    stop_loss = pullback['support_level'] - atr.iloc[-1] * 0.5
                    take_profit = current_price + atr.iloc[-1] * 3
                else:
                    stop_loss = pullback['resistance_level'] + atr.iloc[-1] * 0.5
                    take_profit = current_price - atr.iloc[-1] * 3
                
                signal = TradingSignal(
                    timestamp=datetime.now(),
                    direction=direction,
                    category=SignalCategory.CONTINUATION,
                    signal_type=SignalType.BUY if direction == SignalDirection.BULLISH else SignalType.SELL,
                    score=score,
                    confidence=self._calculate_confidence(components),
                    confluence=self._count_confluence(components),
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    components=components,
                    risk_reward_ratio=abs(take_profit - current_price) / abs(current_price - stop_loss),
                    notes=self._generate_signal_notes(components, context) + ["Trend continuation trade"]
                )
                
                signals.append(signal)
        
        return signals
    
    # ==========================================================================
    # COMPONENT ANALYSIS
    # ==========================================================================
    def _get_momentum_components(
        self,
        market_data: pd.DataFrame,
        context: MarketContext
    ) -> SignalComponents:
        """Get momentum indicator components"""
        # RSI
        rsi = self.indicators.rsi(market_data['close'])
        rsi_signal = self._analyze_rsi(rsi)
        
        # MACD
        macd, signal, histogram = self.indicators.macd(market_data['close'])
        macd_signal = self._analyze_macd(macd, signal, histogram)
        
        # Stochastic
        stoch_k, stoch_d = self.indicators.stochastic(
            market_data['high'],
            market_data['low'],
            market_data['close']
        )
        stoch_signal = self._analyze_stochastic(stoch_k, stoch_d)
        
        # Price momentum
        momentum = self._calculate_price_momentum(market_data)
        momentum_signal = self._analyze_momentum(momentum)
        
        momentum_signals = [rsi_signal, macd_signal, stoch_signal, momentum_signal]
        
        # Trend components
        trend_signals = self._get_trend_components(market_data, context)
        
        # Volume components
        volume_signals = self._get_volume_components(market_data)
        
        # Market internals
        internal_signals = self._get_internal_components() if self.config['use_internals'] else []
        
        # Pattern signals
        pattern_signals = self._get_pattern_components(market_data) if self.config['use_patterns'] else []
        
        # Support/Resistance
        sr_signals = self._get_sr_components(market_data, context)
        
        return SignalComponents(
            momentum_signals=momentum_signals,
            trend_signals=trend_signals,
            volume_signals=volume_signals,
            internal_signals=internal_signals,
            pattern_signals=pattern_signals,
            support_resistance_signals=sr_signals
        )
    
    def _get_trend_components(
        self,
        market_data: pd.DataFrame,
        context: MarketContext
    ) -> List[IndicatorSignal]:
        """Get trend indicator components"""
        signals = []
        
        # Moving average alignment
        sma_20 = market_data['close'].rolling(20).mean()
        sma_50 = market_data['close'].rolling(50).mean()
        ema_9 = market_data['close'].ewm(span=9).mean()
        
        ma_alignment = self._analyze_ma_alignment(
            market_data['close'].iloc[-1],
            ema_9.iloc[-1],
            sma_20.iloc[-1],
            sma_50.iloc[-1]
        )
        signals.append(ma_alignment)
        
        # ADX trend strength
        adx = self.indicators.adx(
            market_data['high'],
            market_data['low'],
            market_data['close']
        )
        adx_signal = self._analyze_adx(adx)
        signals.append(adx_signal)
        
        # Price position relative to VWAP
        vwap = self._calculate_vwap(market_data)
        vwap_signal = self._analyze_vwap_position(
            market_data['close'].iloc[-1],
            vwap
        )
        signals.append(vwap_signal)
        
        return signals
    
    def _get_volume_components(self, market_data: pd.DataFrame) -> List[IndicatorSignal]:
        """Get volume indicator components"""
        signals = []
        
        # Volume surge detection
        volume_ratio = market_data['volume'].iloc[-1] / market_data['volume'].rolling(20).mean().iloc[-1]
        volume_surge = IndicatorSignal(
            indicator_name="Volume Surge",
            state=IndicatorState.BULLISH if volume_ratio > VOLUME_SURGE_MULTIPLIER else IndicatorState.NEUTRAL,
            value=volume_ratio,
            threshold=VOLUME_SURGE_MULTIPLIER,
            weight=0.7,
            confidence=min(volume_ratio / VOLUME_SURGE_MULTIPLIER, 1.0) if volume_ratio > 1 else 0.5
        )
        signals.append(volume_surge)
        
        # On-Balance Volume
        obv = self.indicators.obv(market_data['close'], market_data['volume'])
        obv_signal = self._analyze_obv(obv)
        signals.append(obv_signal)
        
        # Volume-Price Trend
        vpt = self._calculate_vpt(market_data)
        vpt_signal = self._analyze_vpt(vpt)
        signals.append(vpt_signal)
        
        return signals
    
    def _get_internal_components(self) -> List[IndicatorSignal]:
        """Get market internal components"""
        signals = []
        
        # Get current internals
        internals = self.market_internals.get_current_readings()
        
        # TICK
        tick = internals.get('TICK', 0)
        tick_signal = IndicatorSignal(
            indicator_name="TICK",
            state=IndicatorState.BULLISH if tick > 500 else IndicatorState.BEARISH if tick < -500 else IndicatorState.NEUTRAL,
            value=tick,
            threshold=500,
            weight=0.8,
            confidence=min(abs(tick) / 1000, 1.0)
        )
        signals.append(tick_signal)
        
        # ADD (Advance-Decline)
        add = internals.get('ADD', 0)
        add_signal = IndicatorSignal(
            indicator_name="ADD",
            state=IndicatorState.BULLISH if add > 1000 else IndicatorState.BEARISH if add < -1000 else IndicatorState.NEUTRAL,
            value=add,
            threshold=1000,
            weight=0.7,
            confidence=min(abs(add) / 2000, 1.0)
        )
        signals.append(add_signal)
        
        return signals
    
    def _get_pattern_components(self, market_data: pd.DataFrame) -> List[IndicatorSignal]:
        """Get pattern-based components"""
        signals = []
        
        # Find recent patterns
        patterns = self.price_action.find_patterns(market_data)
        
        for pattern in patterns[-3:]:  # Last 3 patterns
            if pattern['quality'] >= MIN_PATTERN_QUALITY:
                state = IndicatorState.BULLISH if pattern['direction'] > 0 else IndicatorState.BEARISH
                
                signal = IndicatorSignal(
                    indicator_name=f"Pattern: {pattern['pattern']}",
                    state=state,
                    value=pattern['quality'],
                    threshold=MIN_PATTERN_QUALITY,
                    weight=0.9,
                    confidence=pattern['quality'],
                    notes=f"Detected at bar {pattern['bar_index']}"
                )
                signals.append(signal)
        
        return signals
    
    def _get_sr_components(
        self,
        market_data: pd.DataFrame,
        context: MarketContext
    ) -> List[IndicatorSignal]:
        """Get support/resistance components"""
        signals = []
        current_price = market_data['close'].iloc[-1]
        
        # Get key levels
        levels = self.support_resistance.find_levels(market_data)
        
        # Check proximity to levels
        for level in levels:
            distance_pct = abs(current_price - level['price']) / current_price
            
            if distance_pct < 0.002:  # Within 0.2%
                if level['type'] == 'support' and current_price > level['price']:
                    state = IndicatorState.BULLISH
                    notes = "Bounced from support"
                elif level['type'] == 'resistance' and current_price < level['price']:
                    state = IndicatorState.BEARISH
                    notes = "Rejected from resistance"
                else:
                    state = IndicatorState.NEUTRAL
                    notes = "Testing level"
                
                signal = IndicatorSignal(
                    indicator_name=f"S/R: {level['type'].capitalize()}",
                    state=state,
                    value=level['price'],
                    threshold=current_price,
                    weight=0.8,
                    confidence=level['strength'],
                    notes=notes
                )
                signals.append(signal)
        
        return signals
    
    # ==========================================================================
    # INDICATOR ANALYSIS
    # ==========================================================================
    def _analyze_rsi(self, rsi: pd.Series) -> IndicatorSignal:
        """Analyze RSI indicator"""
        current_rsi = rsi.iloc[-1]
        
        if current_rsi < RSI_OVERSOLD:
            state = IndicatorState.BULLISH
            confidence = (RSI_OVERSOLD - current_rsi) / RSI_OVERSOLD
        elif current_rsi > RSI_OVERBOUGHT:
            state = IndicatorState.BEARISH
            confidence = (current_rsi - RSI_OVERBOUGHT) / (100 - RSI_OVERBOUGHT)
        else:
            state = IndicatorState.NEUTRAL
            confidence = 0.5
        
        # Check for divergence
        if len(rsi) > REVERSAL_DIVERGENCE_BARS:
            if self._check_divergence(rsi[-REVERSAL_DIVERGENCE_BARS:], 'bullish'):
                state = IndicatorState.DIVERGENCE
                confidence = 0.8
        
        return IndicatorSignal(
            indicator_name="RSI",
            state=state,
            value=current_rsi,
            threshold=RSI_OVERSOLD if state == IndicatorState.BULLISH else RSI_OVERBOUGHT,
            weight=WEIGHT_MOMENTUM,
            confidence=confidence
        )
    
    def _analyze_macd(
        self,
        macd: pd.Series,
        signal: pd.Series,
        histogram: pd.Series
    ) -> IndicatorSignal:
        """Analyze MACD indicator"""
        current_macd = macd.iloc[-1]
        current_signal = signal.iloc[-1]
        current_histogram = histogram.iloc[-1]
        prev_histogram = histogram.iloc[-2]
        
        # Check crossovers
        if current_macd > current_signal and macd.iloc[-2] <= signal.iloc[-2]:
            state = IndicatorState.BULLISH
            confidence = 0.8
        elif current_macd < current_signal and macd.iloc[-2] >= signal.iloc[-2]:
            state = IndicatorState.BEARISH
            confidence = 0.8
        elif current_histogram > 0 and current_histogram > prev_histogram:
            state = IndicatorState.BULLISH
            confidence = 0.6
        elif current_histogram < 0 and current_histogram < prev_histogram:
            state = IndicatorState.BEARISH
            confidence = 0.6
        else:
            state = IndicatorState.NEUTRAL
            confidence = 0.5
        
        return IndicatorSignal(
            indicator_name="MACD",
            state=state,
            value=current_histogram,
            threshold=0,
            weight=WEIGHT_MOMENTUM,
            confidence=confidence
        )
    
    def _analyze_stochastic(
        self,
        stoch_k: pd.Series,
        stoch_d: pd.Series
    ) -> IndicatorSignal:
        """Analyze Stochastic indicator"""
        current_k = stoch_k.iloc[-1]
        current_d = stoch_d.iloc[-1]
        
        if current_k < 20 and current_k > current_d:
            state = IndicatorState.BULLISH
            confidence = 0.8
        elif current_k > 80 and current_k < current_d:
            state = IndicatorState.BEARISH
            confidence = 0.8
        elif current_k < 20:
            state = IndicatorState.BULLISH
            confidence = 0.6
        elif current_k > 80:
            state = IndicatorState.BEARISH
            confidence = 0.6
        else:
            state = IndicatorState.NEUTRAL
            confidence = 0.5
        
        return IndicatorSignal(
            indicator_name="Stochastic",
            state=state,
            value=current_k,
            threshold=20 if state == IndicatorState.BULLISH else 80,
            weight=WEIGHT_MOMENTUM * 0.8,
            confidence=confidence
        )
    
    def _analyze_momentum(self, momentum: float) -> IndicatorSignal:
        """Analyze price momentum"""
        if momentum > MOMENTUM_THRESHOLD:
            state = IndicatorState.BULLISH
            confidence = min(momentum / (MOMENTUM_THRESHOLD * 2), 1.0)
        elif momentum < -MOMENTUM_THRESHOLD:
            state = IndicatorState.BEARISH
            confidence = min(abs(momentum) / (MOMENTUM_THRESHOLD * 2), 1.0)
        else:
            state = IndicatorState.NEUTRAL
            confidence = 0.5
        
        return IndicatorSignal(
            indicator_name="Price Momentum",
            state=state,
            value=momentum,
            threshold=MOMENTUM_THRESHOLD,
            weight=WEIGHT_MOMENTUM,
            confidence=confidence
        )
    
    def _analyze_ma_alignment(self, price: float, ema9: float, sma20: float, sma50: float) -> IndicatorSignal:
        """Analyze moving average alignment"""
        # Bullish: Price > EMA9 > SMA20 > SMA50
        # Bearish: Price < EMA9 < SMA20 < SMA50
        
        if price > ema9 > sma20 > sma50:
            state = IndicatorState.BULLISH
            confidence = 0.9
        elif price < ema9 < sma20 < sma50:
            state = IndicatorState.BEARISH
            confidence = 0.9
        elif price > ema9 and ema9 > sma20:
            state = IndicatorState.BULLISH
            confidence = 0.7
        elif price < ema9 and ema9 < sma20:
            state = IndicatorState.BEARISH
            confidence = 0.7
        else:
            state = IndicatorState.NEUTRAL
            confidence = 0.5
        
        return IndicatorSignal(
            indicator_name="MA Alignment",
            state=state,
            value=price,
            threshold=ema9,
            weight=WEIGHT_TREND,
            confidence=confidence
        )
    
    def _analyze_adx(self, adx: pd.Series) -> IndicatorSignal:
        """Analyze ADX trend strength"""
        current_adx = adx.iloc[-1]
        
        if current_adx > 25:
            state = IndicatorState.BULLISH  # Strong trend
            confidence = min(current_adx / 40, 1.0)
        else:
            state = IndicatorState.NEUTRAL  # Weak trend
            confidence = 0.5
        
        return IndicatorSignal(
            indicator_name="ADX",
            state=state,
            value=current_adx,
            threshold=25,
            weight=WEIGHT_TREND * 0.8,
            confidence=confidence
        )
    
    def _analyze_vwap_position(self, price: float, vwap: float) -> IndicatorSignal:
        """Analyze price position relative to VWAP"""
        distance_pct = (price - vwap) / vwap
        
        if distance_pct > 0.002:  # Above VWAP
            state = IndicatorState.BULLISH
            confidence = min(distance_pct / 0.01, 1.0)
        elif distance_pct < -0.002:  # Below VWAP
            state = IndicatorState.BEARISH
            confidence = min(abs(distance_pct) / 0.01, 1.0)
        else:
            state = IndicatorState.NEUTRAL
            confidence = 0.5
        
        return IndicatorSignal(
            indicator_name="VWAP Position",
            state=state,
            value=price,
            threshold=vwap,
            weight=WEIGHT_TREND * 0.9,
            confidence=confidence
        )
    
    def _analyze_obv(self, obv: pd.Series) -> IndicatorSignal:
        """Analyze On-Balance Volume"""
        obv_ma = obv.rolling(20).mean()
        current_obv = obv.iloc[-1]
        current_ma = obv_ma.iloc[-1]
        
        if current_obv > current_ma and obv.iloc[-2] <= obv_ma.iloc[-2]:
            state = IndicatorState.BULLISH
            confidence = 0.8
        elif current_obv < current_ma and obv.iloc[-2] >= obv_ma.iloc[-2]:
            state = IndicatorState.BEARISH
            confidence = 0.8
        elif current_obv > current_ma:
            state = IndicatorState.BULLISH
            confidence = 0.6
        elif current_obv < current_ma:
            state = IndicatorState.BEARISH
            confidence = 0.6
        else:
            state = IndicatorState.NEUTRAL
            confidence = 0.5
        
        return IndicatorSignal(
            indicator_name="OBV",
            state=state,
            value=current_obv,
            threshold=current_ma,
            weight=WEIGHT_VOLUME,
            confidence=confidence
        )
    
    def _analyze_vpt(self, vpt: pd.Series) -> IndicatorSignal:
        """Analyze Volume-Price Trend"""
        current_vpt = vpt.iloc[-1]
        vpt_ma = vpt.rolling(10).mean().iloc[-1]
        
        if current_vpt > vpt_ma:
            state = IndicatorState.BULLISH
            confidence = 0.7
        elif current_vpt < vpt_ma:
            state = IndicatorState.BEARISH
            confidence = 0.7
        else:
            state = IndicatorState.NEUTRAL
            confidence = 0.5
        
        return IndicatorSignal(
            indicator_name="VPT",
            state=state,
            value=current_vpt,
            threshold=vpt_ma,
            weight=WEIGHT_VOLUME * 0.8,
            confidence=confidence
        )
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def _calculate_component_score(
        self,
        components: SignalComponents
    ) -> Tuple[float, SignalDirection]:
        """Calculate overall score from components"""
        all_signals = (
            components.momentum_signals +
            components.trend_signals +
            components.volume_signals +
            components.internal_signals +
            components.pattern_signals +
            components.support_resistance_signals
        )
        
        bullish_score = 0
        bearish_score = 0
        total_weight = 0
        
        for signal in all_signals:
            if signal.state == IndicatorState.BULLISH:
                bullish_score += signal.weight * signal.confidence
            elif signal.state == IndicatorState.BEARISH:
                bearish_score += signal.weight * signal.confidence
            elif signal.state == IndicatorState.DIVERGENCE:
                # Divergence is typically a reversal signal
                if signal.value > 0:  # Bullish divergence
                    bullish_score += signal.weight * signal.confidence * 1.2
                else:  # Bearish divergence
                    bearish_score += signal.weight * signal.confidence * 1.2
            
            total_weight += signal.weight
        
        # Normalize scores
        if total_weight > 0:
            bullish_score /= total_weight
            bearish_score /= total_weight
        
        # Determine direction
        if bullish_score > bearish_score:
            direction = SignalDirection.BULLISH
            score = bullish_score
        elif bearish_score > bullish_score:
            direction = SignalDirection.BEARISH
            score = bearish_score
        else:
            direction = SignalDirection.NEUTRAL
            score = 0
        
        return score, direction
    
    def _calculate_confidence(self, components: SignalComponents) -> float:
        """Calculate signal confidence"""
        all_signals = (
            components.momentum_signals +
            components.trend_signals +
            components.volume_signals +
            components.internal_signals +
            components.pattern_signals +
            components.support_resistance_signals
        )
        
        if not all_signals:
            return 0
        
        # Average confidence of all signals
        avg_confidence = sum(s.confidence for s in all_signals) / len(all_signals)
        
        # Boost confidence for high confluence
        confluence_boost = min(self._count_confluence(components) / 10, 0.2)
        
        return min(avg_confidence + confluence_boost, 1.0)
    
    def _count_confluence(self, components: SignalComponents) -> int:
        """Count number of confirming signals"""
        all_signals = (
            components.momentum_signals +
            components.trend_signals +
            components.volume_signals +
            components.internal_signals +
            components.pattern_signals +
            components.support_resistance_signals
        )
        
        # Count non-neutral signals
        confirming = sum(
            1 for s in all_signals
            if s.state != IndicatorState.NEUTRAL and s.confidence > 0.6
        )
        
        return confirming
    
    def _filter_and_rank_signals(
        self,
        signals: List[TradingSignal],
        strategy_type: Optional[str]
    ) -> List[TradingSignal]:
        """Filter and rank signals"""
        # Filter by minimum confluence
        filtered = [
            s for s in signals
            if s.confluence >= self.config['min_confluence']
        ]
        
        # Filter by strategy type if specified
        if strategy_type:
            filtered = self._filter_by_strategy(filtered, strategy_type)
        
        # Sort by score and confidence
        filtered.sort(key=lambda x: (x.score, x.confidence), reverse=True)
        
        # Limit number of signals
        return filtered[:MAX_SIGNALS_PER_BAR]
    
    def _filter_by_strategy(
        self,
        signals: List[TradingSignal],
        strategy_type: str
    ) -> List[TradingSignal]:
        """Filter signals based on strategy type"""
        if strategy_type == 'momentum':
            return [s for s in signals if s.category == SignalCategory.MOMENTUM]
        elif strategy_type == 'reversal':
            return [s for s in signals if s.category == SignalCategory.REVERSAL]
        elif strategy_type == 'breakout':
            return [s for s in signals if s.category == SignalCategory.BREAKOUT]
        else:
            return signals
    
    def _generate_signal_notes(
        self,
        components: SignalComponents,
        context: MarketContext
    ) -> List[str]:
        """Generate descriptive notes for signal"""
        notes = []
        
        # Add time window info
        current_time = datetime.now().time()
        if self._is_optimal_entry_time():
            notes.append(f"Within optimal entry window ({OPTIMAL_ENTRY_START}-{OPTIMAL_ENTRY_END})")
        else:
            notes.append(f"Outside optimal entry window (current: {current_time.strftime('%H:%M')})")
        
        # Market context
        notes.append(f"Market phase: {context.market_phase}")
        notes.append(f"Trend: {context.trend_strength:.2f}")
        
        # Key confirmations
        all_signals = (
            components.momentum_signals +
            components.trend_signals +
            components.volume_signals +
            components.internal_signals +
            components.pattern_signals +
            components.support_resistance_signals
        )
        
        # Find strongest signals
        strong_signals = sorted(
            [s for s in all_signals if s.confidence > 0.7],
            key=lambda x: x.confidence,
            reverse=True
        )[:3]
        
        for signal in strong_signals:
            notes.append(f"{signal.indicator_name}: {signal.state.name}")
        
        return notes
    
    def _update_signal_history(self, signals: List[TradingSignal]) -> None:
        """Update signal history"""
        for signal in signals:
            self.signal_history.append({
                'timestamp': signal.timestamp,
                'direction': signal.direction.name,
                'category': signal.category.name,
                'score': signal.score,
                'confluence': signal.confluence,
                'entry_price': signal.entry_price,
                'in_optimal_window': self._is_optimal_entry_time()
            })
        
        # Keep last 100 signals
        if len(self.signal_history) > 100:
            self.signal_history = self.signal_history[-100:]
    
    # ==========================================================================
    # HELPER METHODS (PLACEHOLDERS)
    # ==========================================================================
    def _determine_market_phase(self, market_data: pd.DataFrame, trend_info: Dict) -> str:
        """Determine market phase"""
        # Simplified implementation
        if trend_info['strength'] > 0.7:
            return 'markup' if trend_info['direction'] > 0 else 'markdown'
        elif trend_info['strength'] < 0.3:
            return 'accumulation'
        else:
            return 'distribution'
    
    def _find_key_levels(self, market_data: pd.DataFrame) -> Dict[str, float]:
        """Find key price levels"""
        return {
            'high': market_data['high'].max(),
            'low': market_data['low'].min(),
            'pivot': (market_data['high'].max() + market_data['low'].min() + market_data['close'].iloc[-1]) / 3
        }
    
    def _calculate_price_momentum(self, market_data: pd.DataFrame) -> float:
        """Calculate price momentum"""
        return (market_data['close'].iloc[-1] - market_data['close'].iloc[-10]) / market_data['close'].iloc[-10]
    
    def _calculate_vwap(self, market_data: pd.DataFrame) -> float:
        """Calculate VWAP"""
        typical_price = (market_data['high'] + market_data['low'] + market_data['close']) / 3
        return (typical_price * market_data['volume']).sum() / market_data['volume'].sum()
    
    def _calculate_vpt(self, market_data: pd.DataFrame) -> pd.Series:
        """Calculate Volume-Price Trend"""
        price_change = market_data['close'].pct_change()
        vpt = (price_change * market_data['volume']).cumsum()
        return vpt
    
    def _check_divergence(self, indicator: pd.Series, divergence_type: str) -> bool:
        """Check for divergence between price and indicator"""
        # Simplified divergence check
        return False  # Placeholder
    
    def _find_divergences(self, market_data: pd.DataFrame) -> List[Dict]:
        """Find divergences"""
        return []  # Placeholder
    
    def _check_sr_tests(self, market_data: pd.DataFrame, context: MarketContext) -> List[Dict]:
        """Check support/resistance tests"""
        return []  # Placeholder
    
    def _find_reversal_patterns(self, market_data: pd.DataFrame) -> List[Dict]:
        """Find reversal patterns"""
        return []  # Placeholder
    
    def _build_reversal_components(self, div: Dict, sr_tests: List, patterns: List, market_data: pd.DataFrame) -> SignalComponents:
        """Build reversal signal components"""
        # Simplified - return momentum components as placeholder
        return self._get_momentum_components(market_data, MarketContext(0, 0.5, 0.15, 'normal', 'accumulation', {}, []))
    
    def _find_breakout_levels(self, market_data: pd.DataFrame, context: MarketContext) -> List[Dict]:
        """Find breakout levels"""
        return []  # Placeholder
    
    def _confirm_breakout(self, market_data: pd.DataFrame, level: Dict) -> bool:
        """Confirm breakout"""
        return True  # Placeholder
    
    def _build_breakout_components(self, level: Dict, market_data: pd.DataFrame, context: MarketContext) -> SignalComponents:
        """Build breakout signal components"""
        # Simplified - return momentum components as placeholder
        return self._get_momentum_components(market_data, context)
    
    def _find_pullbacks(self, market_data: pd.DataFrame, context: MarketContext) -> List[Dict]:
        """Find pullbacks"""
        return []  # Placeholder
    
    def _build_continuation_components(self, pullback: Dict, market_data: pd.DataFrame, context: MarketContext) -> SignalComponents:
        """Build continuation signal components"""
        # Simplified - return momentum components as placeholder
        return self._get_momentum_components(market_data, context)
    
    def _create_empty_components(self) -> SignalComponents:
        """Create empty signal components for exit signals"""
        return SignalComponents(
            momentum_signals=[],
            trend_signals=[],
            volume_signals=[],
            internal_signals=[],
            pattern_signals=[],
            support_resistance_signals=[]
        )

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test signal generator with time windows
    generator = SignalGenerator()
    
    # Create sample market data
    dates = pd.date_range(end=datetime.now(), periods=100, freq='5min')
    
    # Simulate trending market with momentum
    trend = np.linspace(0, 5, 100)
    noise = np.random.randn(100) * 0.5
    prices = 450 + trend + noise
    
    # Add some momentum
    prices[80:] += np.linspace(0, 2, 20)
    
    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices + np.random.randn(100) * 0.1,
        'high': prices + abs(np.random.randn(100) * 0.3),
        'low': prices - abs(np.random.randn(100) * 0.3),
        'close': prices,
        'volume': np.random.randint(50000000, 150000000, 100)
    })
    
    # Increase volume on momentum
    market_data.loc[80:, 'volume'] *= 2
    
    # Test entry window status
    print("SIGNAL GENERATOR TEST - Time Window Analysis")
    print("=" * 60)
    
    window_status = generator.get_entry_window_status()
    print(f"Current Time: {window_status['current_time']}")
    print(f"Entry Window: {window_status['window_start']} - {window_status['window_end']}")
    print(f"Exit Time: {window_status['exit_time']}")
    print(f"In Window: {window_status['in_window']}")
    print(f"Status: {window_status['status']}")
    print(f"Next Event: {window_status['next_event']} in {window_status['time_until']}")
    
    # Generate signals
    print("\nGenerating Signals...")
    signals = generator.generate_signals(market_data)
    
    print(f"\nSignals Generated: {len(signals)}")
    
    for i, signal in enumerate(signals):
        print(f"\nSignal #{i+1}:")
        print(f"  Direction: {signal.direction.name}")
        print(f"  Category: {signal.category.name}")
        print(f"  Score: {signal.score:.3f}")
        print(f"  Confidence: {signal.confidence:.1%}")
        print(f"  Confluence: {signal.confluence}")
        print(f"  Entry: ${signal.entry_price:.2f}")
        print(f"  Stop Loss: ${signal.stop_loss:.2f}")
        print(f"  Take Profit: ${signal.take_profit:.2f}")
        print(f"  Risk/Reward: {signal.risk_reward_ratio:.2f}")
        print(f"  Metadata: {signal.metadata}")
        print(f"  Notes:")
        for note in signal.notes:
            print(f"    - {note}")
    
    # Test time-based exit
    print("\nTesting Time-Based Exit...")
    test_positions = [
        {'id': 'pos1', 'symbol': 'SPY', 'contracts': 5},
        {'id': 'pos2', 'symbol': 'SPY', 'contracts': 3}
    ]
    
    # Override time check for testing
    original_method = generator._should_exit_by_time
    generator._should_exit_by_time = lambda: True
    
    exit_signals = generator.generate_signals(market_data, open_positions=test_positions)
    
    print(f"\nExit Signals Generated: {len(exit_signals)}")
    for signal in exit_signals:
        print(f"  {signal.category.name}: {signal.metadata}")
    
    # Restore original method
    generator._should_exit_by_time = original_method
    
    # Get signal history summary
    print("\nSignal History Summary:")
    if generator.signal_history:
        df = pd.DataFrame(generator.signal_history)
        print(f"Total signals: {len(df)}")
        print(f"In optimal window: {df['in_optimal_window'].sum()}")
        print(f"Direction breakdown: {df['direction'].value_counts().to_dict()}")
        print(f"Category breakdown: {df['category'].value_counts().to_dict()}")
