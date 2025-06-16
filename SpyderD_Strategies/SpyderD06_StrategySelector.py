#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD06_StrategySelector.py
Group: D (Trading Strategies)
Purpose: Strategy selection based on market conditions

Description:
    This module analyzes market conditions and selects the most appropriate
    trading strategy. It considers factors like volatility, trend, market
    internals, and upcoming events to optimize strategy selection.

Author: Mohamed Talib
Date: 2025-05-29
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum, auto
import math
import json

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
from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
from SpyderF_Analysis.SpyderF01_Indicators import TechnicalIndicators
from SpyderF_Analysis.SpyderF04_VolatilityAnalysis import VolatilityAnalyzer
from SpyderF_Analysis.SpyderF05_TrendDetection import TrendDetector
from SpyderC_MarketData.SpyderC04_MarketInternals import MarketInternals

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Market regime thresholds
TREND_STRENGTH_STRONG = 0.7
TREND_STRENGTH_MODERATE = 0.4
VOLATILITY_HIGH = 0.25  # 25% annualized
VOLATILITY_LOW = 0.10   # 10% annualized

# Strategy scoring weights
WEIGHT_MARKET_CONDITION = 0.30
WEIGHT_VOLATILITY = 0.25
WEIGHT_TREND = 0.20
WEIGHT_INTERNALS = 0.15
WEIGHT_TIME_OF_DAY = 0.10

# Time-based preferences
MORNING_HOURS = (time(9, 30), time(11, 30))
MIDDAY_HOURS = (time(11, 30), time(14, 0))
AFTERNOON_HOURS = (time(14, 0), time(16, 0))

# Market condition scores
CONDITION_SCORES = {
    'iron_condor': {
        'low_volatility': 0.9,
        'range_bound': 0.8,
        'moderate_trend': 0.3,
        'strong_trend': 0.1,
        'high_volatility': 0.2
    },
    'credit_spread': {
        'low_volatility': 0.6,
        'range_bound': 0.5,
        'moderate_trend': 0.8,
        'strong_trend': 0.6,
        'high_volatility': 0.4
    },
    'zero_dte': {
        'low_volatility': 0.3,
        'range_bound': 0.4,
        'moderate_trend': 0.7,
        'strong_trend': 0.9,
        'high_volatility': 0.8
    },
    'straddle': {
        'low_volatility': 0.8,
        'range_bound': 0.6,
        'moderate_trend': 0.4,
        'strong_trend': 0.3,
        'high_volatility': 0.2
    }
}

# ==============================================================================
# ENUMS
# ==============================================================================
class MarketRegime(Enum):
    """Overall market regime classification"""
    TRENDING_BULLISH = auto()
    TRENDING_BEARISH = auto()
    RANGE_BOUND = auto()
    VOLATILE_DIRECTIONAL = auto()
    VOLATILE_CHOPPY = auto()
    QUIET_ACCUMULATION = auto()
    QUIET_DISTRIBUTION = auto()

class VolatilityState(Enum):
    """Volatility state classification"""
    VERY_LOW = auto()
    LOW = auto()
    NORMAL = auto()
    ELEVATED = auto()
    HIGH = auto()
    EXTREME = auto()

class TrendState(Enum):
    """Trend state classification"""
    STRONG_UP = auto()
    MODERATE_UP = auto()
    WEAK_UP = auto()
    NEUTRAL = auto()
    WEAK_DOWN = auto()
    MODERATE_DOWN = auto()
    STRONG_DOWN = auto()

class MarketPhase(Enum):
    """Intraday market phase"""
    OPENING = auto()
    MORNING_TREND = auto()
    MIDDAY_CHOP = auto()
    AFTERNOON_TREND = auto()
    CLOSING = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class MarketConditions:
    """Current market conditions"""
    timestamp: datetime
    market_regime: MarketRegime
    volatility_state: VolatilityState
    trend_state: TrendState
    market_phase: MarketPhase
    vix_level: float
    iv_rank: float
    realized_vol: float
    trend_strength: float
    breadth_thrust: float
    tick_extreme: float
    put_call_ratio: float
    volume_ratio: float
    internals_score: float
    upcoming_events: List[str] = field(default_factory=list)
    
class StrategyScore:
    """Strategy scoring result"""
    strategy_name: str
    total_score: float
    condition_score: float
    volatility_score: float
    trend_score: float
    internals_score: float
    time_score: float
    risk_adjusted_score: float
    confidence: float
    reasons: List[str] = field(default_factory=list)

class StrategyRecommendation:
    """Strategy recommendation"""
    primary_strategy: str
    secondary_strategy: Optional[str]
    allocation_primary: float
    allocation_secondary: float
    market_conditions: MarketConditions
    scores: List[StrategyScore]
    risk_level: str  # 'low', 'medium', 'high'
    notes: List[str] = field(default_factory=list)

# ==============================================================================
# STRATEGY SELECTOR CLASS
# ==============================================================================
class StrategySelector:
    """
    Selects optimal trading strategies based on market conditions.
    
    Analyzes multiple factors to determine which strategy or combination
    of strategies is most appropriate for current market conditions.
    """
    
    def __init__(self, event_manager: EventManager):
        """
        Initialize strategy selector.
        
        Args:
            event_manager: Event manager instance
        """
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Analysis components
        self.indicators = TechnicalIndicators()
        self.volatility_analyzer = VolatilityAnalyzer()
        self.trend_detector = TrendDetector()
        self.market_internals = None  # Will be set when MarketInternals is available
        self.trading_calendar = TradingCalendar()
        
        # Available strategies
        self.available_strategies = [
            'iron_condor',
            'credit_spread',
            'zero_dte',
            'straddle'
        ]
        
        # State tracking
        self.current_conditions: Optional[MarketConditions] = None
        self.last_recommendation: Optional[StrategyRecommendation] = None
        self.performance_history: Dict[str, List[float]] = {
            strategy: [] for strategy in self.available_strategies
        }
        
        # Configuration
        self.min_confidence_threshold = 0.6
        self.rebalance_threshold = 0.2  # 20% score change triggers rebalance
        
        self.logger.info("StrategySelector initialized")
    
    def set_market_internals_manager(self, manager: MarketInternals) -> None:
        """Set the market internals manager instance"""
        self.market_internals = manager
    
    # ==========================================================================
    # MAIN SELECTION PROCESS
    # ==========================================================================
    def select_strategy(
        self,
        market_data: pd.DataFrame,
        account_info: Dict[str, Any]
    ) -> StrategyRecommendation:
        """
        Select optimal strategy based on current conditions.
        
        Args:
            market_data: Market data DataFrame
            account_info: Account information
            
        Returns:
            Strategy recommendation
        """
        try:
            # Analyze market conditions
            self.current_conditions = self._analyze_market_conditions(market_data)
            
            # Score each strategy
            scores = self._score_strategies()
            
            # Apply risk adjustments
            scores = self._apply_risk_adjustments(scores, account_info)
            
            # Select best strategies
            recommendation = self._create_recommendation(scores)
            
            # Check if rebalancing needed
            if self._should_rebalance(recommendation):
                self._emit_rebalance_event(recommendation)
            
            self.last_recommendation = recommendation
            
            return recommendation
            
        except Exception as e:
            self.logger.error(f"Error selecting strategy: {e}")
            self.error_handler.handle_error(e, "StrategySelector")
            
            # Return safe default
            return self._get_default_recommendation()
    
    def _analyze_market_conditions(self, market_data: pd.DataFrame) -> MarketConditions:
        """Analyze current market conditions"""
        if len(market_data) < 100:
            raise ValueError("Insufficient market data for analysis")
        
        current_price = market_data['close'].iloc[-1]
        current_time = datetime.now()
        
        # Get market regime
        market_regime = self._classify_market_regime(market_data)
        
        # Get volatility state
        volatility_state, realized_vol, iv_rank = self._analyze_volatility(market_data)
        
        # Get trend state
        trend_state, trend_strength = self._analyze_trend(market_data)
        
        # Get market phase
        market_phase = self._get_market_phase(current_time.time())
        
        # Get market internals
        internals = self._analyze_internals()
        
        # Get VIX level (simplified)
        vix_level = self._estimate_vix(market_data)
        
        # Volume analysis
        volume_ratio = market_data['volume'].iloc[-1] / market_data['volume'].rolling(20).mean().iloc[-1]
        
        # Check upcoming events
        upcoming_events = self._check_upcoming_events()
        
        return MarketConditions(
            timestamp=current_time,
            market_regime=market_regime,
            volatility_state=volatility_state,
            trend_state=trend_state,
            market_phase=market_phase,
            vix_level=vix_level,
            iv_rank=iv_rank,
            realized_vol=realized_vol,
            trend_strength=trend_strength,
            breadth_thrust=internals.get('breadth_thrust', 0),
            tick_extreme=internals.get('tick_extreme', 0),
            put_call_ratio=internals.get('put_call_ratio', 1.0),
            volume_ratio=volume_ratio,
            internals_score=internals.get('score', 0),
            upcoming_events=upcoming_events
        )
    
    def _score_strategies(self) -> List[StrategyScore]:
        """Score each available strategy"""
        scores = []
        
        for strategy in self.available_strategies:
            score = self._score_strategy(strategy)
            scores.append(score)
        
        # Sort by total score
        scores.sort(key=lambda x: x.total_score, reverse=True)
        
        return scores
    
    def _score_strategy(self, strategy_name: str) -> StrategyScore:
        """Score individual strategy"""
        if not self.current_conditions:
            return StrategyScore(
                strategy_name=strategy_name,
                total_score=0,
                condition_score=0,
                volatility_score=0,
                trend_score=0,
                internals_score=0,
                time_score=0,
                risk_adjusted_score=0,
                confidence=0
            )
        
        # Calculate component scores
        condition_score = self._score_market_condition(strategy_name)
        volatility_score = self._score_volatility(strategy_name)
        trend_score = self._score_trend(strategy_name)
        internals_score = self._score_internals(strategy_name)
        time_score = self._score_time_of_day(strategy_name)
        
        # Calculate weighted total
        total_score = (
            condition_score * WEIGHT_MARKET_CONDITION +
            volatility_score * WEIGHT_VOLATILITY +
            trend_score * WEIGHT_TREND +
            internals_score * WEIGHT_INTERNALS +
            time_score * WEIGHT_TIME_OF_DAY
        )
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            strategy_name,
            [condition_score, volatility_score, trend_score, internals_score, time_score]
        )
        
        # Generate reasons
        reasons = self._generate_reasons(
            strategy_name,
            condition_score,
            volatility_score,
            trend_score,
            internals_score,
            time_score
        )
        
        return StrategyScore(
            strategy_name=strategy_name,
            total_score=total_score,
            condition_score=condition_score,
            volatility_score=volatility_score,
            trend_score=trend_score,
            internals_score=internals_score,
            time_score=time_score,
            risk_adjusted_score=total_score,  # Adjusted later
            confidence=confidence,
            reasons=reasons
        )
    
    # ==========================================================================
    # SCORING COMPONENTS
    # ==========================================================================
    def _score_market_condition(self, strategy: str) -> float:
        """Score strategy based on market condition"""
        if not self.current_conditions:
            return 0.5
        
        # Map market regime to condition
        regime_map = {
            MarketRegime.TRENDING_BULLISH: 'strong_trend',
            MarketRegime.TRENDING_BEARISH: 'strong_trend',
            MarketRegime.RANGE_BOUND: 'range_bound',
            MarketRegime.VOLATILE_DIRECTIONAL: 'high_volatility',
            MarketRegime.VOLATILE_CHOPPY: 'high_volatility',
            MarketRegime.QUIET_ACCUMULATION: 'low_volatility',
            MarketRegime.QUIET_DISTRIBUTION: 'low_volatility'
        }
        
        condition = regime_map.get(self.current_conditions.market_regime, 'moderate_trend')
        
        return CONDITION_SCORES.get(strategy, {}).get(condition, 0.5)
    
    def _score_volatility(self, strategy: str) -> float:
        """Score strategy based on volatility"""
        if not self.current_conditions:
            return 0.5
        
        vol_state = self.current_conditions.volatility_state
        
        # Strategy-specific volatility preferences
        if strategy == 'iron_condor':
            if vol_state in [VolatilityState.VERY_LOW, VolatilityState.LOW]:
                return 0.9
            elif vol_state == VolatilityState.NORMAL:
                return 0.7
            else:
                return 0.3
                
        elif strategy == 'credit_spread':
            if vol_state == VolatilityState.NORMAL:
                return 0.8
            elif vol_state in [VolatilityState.LOW, VolatilityState.ELEVATED]:
                return 0.6
            else:
                return 0.4
                
        elif strategy == 'zero_dte':
            if vol_state in [VolatilityState.ELEVATED, VolatilityState.HIGH]:
                return 0.9
            elif vol_state == VolatilityState.NORMAL:
                return 0.6
            else:
                return 0.3
                
        elif strategy == 'straddle':
            # Look for low IV rank with potential for expansion
            if (vol_state in [VolatilityState.VERY_LOW, VolatilityState.LOW] and
                self.current_conditions.iv_rank < 30):
                return 0.9
            elif vol_state == VolatilityState.NORMAL:
                return 0.5
            else:
                return 0.2
        
        return 0.5
    
    def _score_trend(self, strategy: str) -> float:
        """Score strategy based on trend"""
        if not self.current_conditions:
            return 0.5
        
        trend_state = self.current_conditions.trend_state
        trend_strength = self.current_conditions.trend_strength
        
        # Strategy-specific trend preferences
        if strategy == 'iron_condor':
            # Prefers no trend
            if trend_state == TrendState.NEUTRAL:
                return 0.9
            elif trend_state in [TrendState.WEAK_UP, TrendState.WEAK_DOWN]:
                return 0.7
            else:
                return 0.3
                
        elif strategy == 'credit_spread':
            # Works in moderate trends
            if trend_state in [TrendState.MODERATE_UP, TrendState.MODERATE_DOWN]:
                return 0.8
            elif trend_state in [TrendState.WEAK_UP, TrendState.WEAK_DOWN]:
                return 0.6
            else:
                return 0.4
                
        elif strategy == 'zero_dte':
            # Loves strong trends
            if trend_state in [TrendState.STRONG_UP, TrendState.STRONG_DOWN]:
                return 0.9
            elif trend_state in [TrendState.MODERATE_UP, TrendState.MODERATE_DOWN]:
                return 0.7
            else:
                return 0.4
                
        elif strategy == 'straddle':
            # Prefers uncertainty
            if trend_state == TrendState.NEUTRAL and trend_strength < 0.3:
                return 0.8
            else:
                return 0.4
        
        return 0.5
    
    def _score_internals(self, strategy: str) -> float:
        """Score strategy based on market internals"""
        if not self.current_conditions:
            return 0.5
        
        internals_score = self.current_conditions.internals_score
        tick_extreme = abs(self.current_conditions.tick_extreme)
        
        # Strategy-specific internals preferences
        if strategy == 'iron_condor':
            # Prefers neutral internals
            if tick_extreme < 200:
                return 0.8
            else:
                return 0.4
                
        elif strategy == 'credit_spread':
            # Moderate internals
            if 200 <= tick_extreme <= 600:
                return 0.7
            else:
                return 0.5
                
        elif strategy == 'zero_dte':
            # Loves extreme internals
            if tick_extreme > 600:
                return 0.9
            elif tick_extreme > 400:
                return 0.7
            else:
                return 0.4
                
        elif strategy == 'straddle':
            # Neutral on internals
            return 0.5 + internals_score * 0.2
        
        return 0.5
    
    def _score_time_of_day(self, strategy: str) -> float:
        """Score strategy based on time of day"""
        current_time = datetime.now().time()
        
        # Strategy-specific time preferences
        if strategy == 'zero_dte':
            # Best in morning and afternoon trends
            if (MORNING_HOURS[0] <= current_time <= MORNING_HOURS[1] or
                AFTERNOON_HOURS[0] <= current_time <= AFTERNOON_HOURS[1]):
                return 0.9
            else:
                return 0.5
                
        elif strategy == 'iron_condor':
            # Avoid opening hour
            if current_time < time(10, 30):
                return 0.3
            else:
                return 0.7
                
        elif strategy == 'credit_spread':
            # Flexible timing
            if time(10, 0) <= current_time <= time(15, 0):
                return 0.8
            else:
                return 0.5
                
        elif strategy == 'straddle':
            # Before events or quiet periods
            if MIDDAY_HOURS[0] <= current_time <= MIDDAY_HOURS[1]:
                return 0.7
            else:
                return 0.6
        
        return 0.5
    
    # ==========================================================================
    # RISK ADJUSTMENTS
    # ==========================================================================
    def _apply_risk_adjustments(
        self,
        scores: List[StrategyScore],
        account_info: Dict[str, Any]
    ) -> List[StrategyScore]:
        """Apply risk-based adjustments to scores"""
        adjusted_scores = []
        
        for score in scores:
            # Adjust based on account size
            size_adjustment = self._get_size_adjustment(
                score.strategy_name,
                account_info.get('account_size', 100000)
            )
            
            # Adjust based on current exposure
            exposure_adjustment = self._get_exposure_adjustment(
                score.strategy_name,
                account_info.get('current_positions', {})
            )
            
            # Adjust based on recent performance
            performance_adjustment = self._get_performance_adjustment(
                score.strategy_name
            )
            
            # Calculate risk-adjusted score
            risk_adjusted = score.total_score * size_adjustment * exposure_adjustment * performance_adjustment
            
            score.risk_adjusted_score = risk_adjusted
            adjusted_scores.append(score)
        
        # Re-sort by risk-adjusted score
        adjusted_scores.sort(key=lambda x: x.risk_adjusted_score, reverse=True)
        
        return adjusted_scores
    
    def _get_size_adjustment(self, strategy: str, account_size: float) -> float:
        """Get account size adjustment factor"""
        # Smaller accounts might avoid certain strategies
        if account_size < 25000:
            if strategy == 'iron_condor':
                return 0.7  # Requires more capital
            elif strategy == 'zero_dte':
                return 1.1  # Good for small accounts
        elif account_size > 100000:
            if strategy == 'iron_condor':
                return 1.1  # Better for larger accounts
        
        return 1.0
    
    def _get_exposure_adjustment(
        self,
        strategy: str,
        current_positions: Dict[str, Any]
    ) -> float:
        """Get exposure adjustment factor"""
        # Reduce score if already heavily exposed
        strategy_positions = current_positions.get(strategy, 0)
        
        if strategy_positions >= 3:
            return 0.6
        elif strategy_positions >= 2:
            return 0.8
        elif strategy_positions >= 1:
            return 0.9
        
        return 1.0
    
    def _get_performance_adjustment(self, strategy: str) -> float:
        """Get performance-based adjustment factor"""
        # Use recent performance history
        recent_performance = self.performance_history.get(strategy, [])
        
        if len(recent_performance) >= 5:
            # Calculate win rate
            wins = sum(1 for p in recent_performance[-5:] if p > 0)
            win_rate = wins / 5
            
            if win_rate >= 0.8:
                return 1.1
            elif win_rate >= 0.6:
                return 1.0
            elif win_rate >= 0.4:
                return 0.9
            else:
                return 0.8
        
        return 1.0
    
    # ==========================================================================
    # RECOMMENDATION CREATION
    # ==========================================================================
    def _create_recommendation(
        self,
        scores: List[StrategyScore]
    ) -> StrategyRecommendation:
        """Create strategy recommendation from scores"""
        if not scores or not self.current_conditions:
            return self._get_default_recommendation()
        
        # Get top strategies
        primary = scores[0]
        secondary = scores[1] if len(scores) > 1 else None
        
        # Determine allocations
        if primary.confidence >= self.min_confidence_threshold:
            if secondary and secondary.confidence >= self.min_confidence_threshold:
                # Use both strategies
                total_score = primary.risk_adjusted_score + secondary.risk_adjusted_score
                allocation_primary = primary.risk_adjusted_score / total_score
                allocation_secondary = secondary.risk_adjusted_score / total_score
            else:
                # Use only primary
                allocation_primary = 1.0
                allocation_secondary = 0.0
                secondary = None
        else:
            # Low confidence - use conservative allocation
            allocation_primary = 0.5
            allocation_secondary = 0.0
            secondary = None
        
        # Determine risk level
        risk_level = self._determine_risk_level(primary, secondary)
        
        # Generate notes
        notes = self._generate_recommendation_notes(scores)
        
        return StrategyRecommendation(
            primary_strategy=primary.strategy_name,
            secondary_strategy=secondary.strategy_name if secondary else None,
            allocation_primary=allocation_primary,
            allocation_secondary=allocation_secondary,
            market_conditions=self.current_conditions,
            scores=scores,
            risk_level=risk_level,
            notes=notes
        )
    
    def _determine_risk_level(
        self,
        primary: StrategyScore,
        secondary: Optional[StrategyScore]
    ) -> str:
        """Determine overall risk level"""
        # Based on strategy types and market conditions
        high_risk_strategies = ['zero_dte', 'straddle']
        
        if primary.strategy_name in high_risk_strategies:
            return 'high'
        elif secondary and secondary.strategy_name in high_risk_strategies:
            return 'medium'
        else:
            return 'low'
    
    def _generate_recommendation_notes(
        self,
        scores: List[StrategyScore]
    ) -> List[str]:
        """Generate recommendation notes"""
        notes = []
        
        if not self.current_conditions:
            return notes
        
        # Market regime note
        notes.append(f"Market regime: {self.current_conditions.market_regime.name}")
        
        # Volatility note
        if self.current_conditions.volatility_state in [VolatilityState.HIGH, VolatilityState.EXTREME]:
            notes.append("High volatility environment - consider reducing position sizes")
        elif self.current_conditions.volatility_state == VolatilityState.VERY_LOW:
            notes.append("Very low volatility - potential for volatility expansion")
        
        # Event notes
        if self.current_conditions.upcoming_events:
            notes.append(f"Upcoming events: {', '.join(self.current_conditions.upcoming_events)}")
        
        # Top strategy reasons
        if scores:
            top_reasons = scores[0].reasons[:2]
            notes.extend(top_reasons)
        
        return notes
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def _classify_market_regime(self, market_data: pd.DataFrame) -> MarketRegime:
        """Classify overall market regime"""
        # Simplified regime classification
        returns = market_data['close'].pct_change()
        volatility = returns.rolling(20).std().iloc[-1] * math.sqrt(252)
        
        # Trend analysis
        sma_20 = market_data['close'].rolling(20).mean()
        sma_50 = market_data['close'].rolling(50).mean()
        
        trend_up = sma_20.iloc[-1] > sma_50.iloc[-1]
        trend_strength = abs(sma_20.iloc[-1] - sma_50.iloc[-1]) / sma_50.iloc[-1]
        
        # Classify
        if volatility > VOLATILITY_HIGH:
            if trend_strength > TREND_STRENGTH_STRONG:
                return MarketRegime.VOLATILE_DIRECTIONAL
            else:
                return MarketRegime.VOLATILE_CHOPPY
        elif volatility < VOLATILITY_LOW:
            if trend_up:
                return MarketRegime.QUIET_ACCUMULATION
            else:
                return MarketRegime.QUIET_DISTRIBUTION
        else:
            if trend_strength > TREND_STRENGTH_STRONG:
                return MarketRegime.TRENDING_BULLISH if trend_up else MarketRegime.TRENDING_BEARISH
            else:
                return MarketRegime.RANGE_BOUND
    
    def _analyze_volatility(
        self,
        market_data: pd.DataFrame
    ) -> Tuple[VolatilityState, float, float]:
        """Analyze volatility conditions"""
        # Calculate realized volatility
        returns = market_data['close'].pct_change()
        realized_vol = returns.rolling(20).std().iloc[-1] * math.sqrt(252)
        
        # Estimate IV rank (simplified)
        iv_rank = 50  # Would use actual option data
        
        # Classify volatility state
        if realized_vol < 0.08:
            vol_state = VolatilityState.VERY_LOW
        elif realized_vol < 0.12:
            vol_state = VolatilityState.LOW
        elif realized_vol < 0.18:
            vol_state = VolatilityState.NORMAL
        elif realized_vol < 0.25:
            vol_state = VolatilityState.ELEVATED
        elif realized_vol < 0.35:
            vol_state = VolatilityState.HIGH
        else:
            vol_state = VolatilityState.EXTREME
        
        return vol_state, realized_vol, iv_rank
    
    def _analyze_trend(
        self,
        market_data: pd.DataFrame
    ) -> Tuple[TrendState, float]:
        """Analyze trend conditions"""
        # Use trend detector
        trend_info = self.trend_detector.analyze(market_data)
        
        # Get dominant trend
        dominant_trend = trend_info.dominant_trend
        
        # Map to TrendState
        direction_map = {
            'strong_up': TrendState.STRONG_UP,
            'up': TrendState.MODERATE_UP,
            'weak_up': TrendState.WEAK_UP,
            'sideways': TrendState.NEUTRAL,
            'weak_down': TrendState.WEAK_DOWN,
            'down': TrendState.MODERATE_DOWN,
            'strong_down': TrendState.STRONG_DOWN
        }
        
        trend_state = direction_map.get(dominant_trend.direction.value, TrendState.NEUTRAL)
        strength = dominant_trend.strength
        
        return trend_state, strength
    
    def _get_market_phase(self, current_time: time) -> MarketPhase:
        """Get current market phase"""
        if current_time < time(10, 0):
            return MarketPhase.OPENING
        elif current_time < time(11, 30):
            return MarketPhase.MORNING_TREND
        elif current_time < time(14, 0):
            return MarketPhase.MIDDAY_CHOP
        elif current_time < time(15, 30):
            return MarketPhase.AFTERNOON_TREND
        else:
            return MarketPhase.CLOSING
    
    def _analyze_internals(self) -> Dict[str, float]:
        """Analyze market internals"""
        # Get current internals from MarketInternals if available
        if self.market_internals:
            snapshot = self.market_internals.get_current_snapshot()
            
            return {
                'breadth_thrust': snapshot.nyse_add_line or 0,
                'tick_extreme': snapshot.nyse_tick or 0,
                'put_call_ratio': 1.0,  # Would use actual data
                'score': snapshot.internals_score
            }
        else:
            # Default values when market internals not available
            return {
                'breadth_thrust': 0,
                'tick_extreme': 0,
                'put_call_ratio': 1.0,
                'score': 0.5
            }
    
    def _estimate_vix(self, market_data: pd.DataFrame) -> float:
        """Estimate VIX level"""
        # Simplified VIX estimation
        returns = market_data['close'].pct_change()
        realized_vol = returns.rolling(20).std().iloc[-1] * math.sqrt(252)
        
        # VIX typically trades at premium to realized
        vix_estimate = realized_vol * 100 * 1.2
        
        return vix_estimate
    
    def _check_upcoming_events(self) -> List[str]:
        """Check for upcoming market events"""
        events = []
        
        # Check for FOMC
        next_fomc = self.trading_calendar.get_next_fomc_date()
        if next_fomc and (next_fomc - datetime.now()).days <= 5:
            events.append("FOMC")
        
        # Check for options expiration
        if self.trading_calendar.is_options_expiration_week():
            events.append("OPEX")
        
        # Check for major economic data (simplified)
        if datetime.now().day in [12, 13, 14]:  # Around CPI release
            events.append("CPI")
        
        return events
    
    def _calculate_confidence(
        self,
        strategy: str,
        scores: List[float]
    ) -> float:
        """Calculate confidence in strategy selection"""
        # Average of component scores
        avg_score = sum(scores) / len(scores)
        
        # Penalize if scores are inconsistent
        std_dev = np.std(scores)
        consistency_factor = 1.0 - min(std_dev, 0.3)
        
        return avg_score * consistency_factor
    
    def _generate_reasons(
        self,
        strategy: str,
        condition_score: float,
        volatility_score: float,
        trend_score: float,
        internals_score: float,
        time_score: float
    ) -> List[str]:
        """Generate reasons for strategy selection"""
        reasons = []
        
        # Add top scoring components as reasons
        scores = [
            ('Market conditions', condition_score),
            ('Volatility environment', volatility_score),
            ('Trend alignment', trend_score),
            ('Market internals', internals_score),
            ('Time of day', time_score)
        ]
        
        # Sort by score
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # Add top reasons
        for reason, score in scores[:3]:
            if score >= 0.7:
                reasons.append(f"{reason} favorable for {strategy} (score: {score:.2f})")
        
        # Add strategy-specific reasons
        if strategy == 'iron_condor' and volatility_score >= 0.8:
            reasons.append("Low volatility ideal for premium collection")
        elif strategy == 'zero_dte' and trend_score >= 0.8:
            reasons.append("Strong trend momentum for scalping")
        elif strategy == 'straddle' and volatility_score >= 0.8:
            reasons.append("Volatility expansion setup detected")
        elif strategy == 'credit_spread' and condition_score >= 0.7:
            reasons.append("Moderate market conditions suit directional spreads")
        
        return reasons
    
    def _should_rebalance(self, new_recommendation: StrategyRecommendation) -> bool:
        """Check if rebalancing is needed"""
        if not self.last_recommendation:
            return True
        
        # Check if primary strategy changed
        if new_recommendation.primary_strategy != self.last_recommendation.primary_strategy:
            return True
        
        # Check if allocation changed significantly
        allocation_change = abs(
            new_recommendation.allocation_primary - 
            self.last_recommendation.allocation_primary
        )
        
        if allocation_change > self.rebalance_threshold:
            return True
        
        # Check if risk level changed
        if new_recommendation.risk_level != self.last_recommendation.risk_level:
            return True
        
        return False
    
    def _emit_rebalance_event(self, recommendation: StrategyRecommendation) -> None:
        """Emit rebalancing event"""
        self.event_manager.emit(Event(
            EventType.STRATEGY,
            {
                'action': 'rebalance',
                'recommendation': {
                    'primary': recommendation.primary_strategy,
                    'secondary': recommendation.secondary_strategy,
                    'allocation_primary': recommendation.allocation_primary,
                    'allocation_secondary': recommendation.allocation_secondary,
                    'risk_level': recommendation.risk_level
                },
                'previous': {
                    'primary': self.last_recommendation.primary_strategy if self.last_recommendation else None,
                    'secondary': self.last_recommendation.secondary_strategy if self.last_recommendation else None
                }
            }
        ))
    
    def _get_default_recommendation(self) -> StrategyRecommendation:
        """Get default safe recommendation"""
        return StrategyRecommendation(
            primary_strategy='credit_spread',
            secondary_strategy=None,
            allocation_primary=0.5,
            allocation_secondary=0.0,
            market_conditions=self.current_conditions or self._get_neutral_conditions(),
            scores=[],
            risk_level='low',
            notes=['Using default conservative allocation due to analysis error']
        )
    
    def _get_neutral_conditions(self) -> MarketConditions:
        """Get neutral market conditions"""
        return MarketConditions(
            timestamp=datetime.now(),
            market_regime=MarketRegime.RANGE_BOUND,
            volatility_state=VolatilityState.NORMAL,
            trend_state=TrendState.NEUTRAL,
            market_phase=MarketPhase.MIDDAY_CHOP,
            vix_level=15.0,
            iv_rank=50.0,
            realized_vol=0.15,
            trend_strength=0.3,
            breadth_thrust=0.0,
            tick_extreme=0.0,
            put_call_ratio=1.0,
            volume_ratio=1.0,
            internals_score=0.5,
            upcoming_events=[]
        )
    
    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    def update_performance(self, strategy: str, pnl: float) -> None:
        """
        Update strategy performance history.
        
        Args:
            strategy: Strategy name
            pnl: P&L result
        """
        if strategy in self.performance_history:
            self.performance_history[strategy].append(pnl)
            # Keep last 20 results
            if len(self.performance_history[strategy]) > 20:
                self.performance_history[strategy].pop(0)
    
    def get_current_recommendation(self) -> Optional[StrategyRecommendation]:
        """Get current recommendation"""
        return self.last_recommendation
    
    def get_strategy_scores(self) -> List[StrategyScore]:
        """Get current strategy scores"""
        if self.last_recommendation:
            return self.last_recommendation.scores
        return []
    
    def get_market_conditions(self) -> Optional[MarketConditions]:
        """Get current market conditions"""
        return self.current_conditions
    
    def force_reanalysis(self, market_data: pd.DataFrame) -> None:
        """Force reanalysis of market conditions"""
        self.current_conditions = self._analyze_market_conditions(market_data)
        self.logger.info("Forced market condition reanalysis")

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test strategy selector
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    
    # Initialize
    event_manager = EventManager()
    selector = StrategySelector(event_manager)
    
    # Create sample market data
    dates = pd.date_range(end=datetime.now(), periods=100, freq='5min')
    
    # Simulate different market conditions
    # Low volatility range-bound (good for Iron Condor)
    base_price = 450
    prices = base_price + np.sin(np.linspace(0, 4*np.pi, 100)) * 2
    
    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices + np.random.randn(100) * 0.1,
        'high': prices + abs(np.random.randn(100) * 0.2),
        'low': prices - abs(np.random.randn(100) * 0.2),
        'close': prices,
        'volume': np.random.randint(50000000, 150000000, 100)
    })
    
    # Account info
    account_info = {
        'account_size': 100000,
        'current_positions': {
            'iron_condor': 1,
            'credit_spread': 0,
            'zero_dte': 0,
            'straddle': 0
        }
    }
    
    # Get recommendation
    recommendation = selector.select_strategy(market_data, account_info)
    
    # Print results
    print("STRATEGY RECOMMENDATION")
    print("=" * 50)
    print(f"Primary Strategy: {recommendation.primary_strategy}")
    print(f"Secondary Strategy: {recommendation.secondary_strategy}")
    print(f"Allocation: {recommendation.allocation_primary:.0%} / {recommendation.allocation_secondary:.0%}")
    print(f"Risk Level: {recommendation.risk_level}")
    
    print(f"\nMarket Conditions:")
    if recommendation.market_conditions:
        print(f"  Regime: {recommendation.market_conditions.market_regime.name}")
        print(f"  Volatility: {recommendation.market_conditions.volatility_state.name}")
        print(f"  Trend: {recommendation.market_conditions.trend_state.name}")
        print(f"  Phase: {recommendation.market_conditions.market_phase.name}")
        print(f"  VIX: {recommendation.market_conditions.vix_level:.1f}")
    
    print(f"\nStrategy Scores:")
    for score in recommendation.scores:
        print(f"\n{score.strategy_name.upper()}:")
        print(f"  Total Score: {score.total_score:.3f}")
        print(f"  Risk-Adjusted: {score.risk_adjusted_score:.3f}")
        print(f"  Confidence: {score.confidence:.0%}")
        print(f"  Components:")
        print(f"    Market: {score.condition_score:.2f}")
        print(f"    Volatility: {score.volatility_score:.2f}")
        print(f"    Trend: {score.trend_score:.2f}")
        print(f"    Internals: {score.internals_score:.2f}")
        print(f"    Time: {score.time_score:.2f}")
        if score.reasons:
            print(f"  Reasons:")
            for reason in score.reasons:
                print(f"    - {reason}")
    
    print(f"\nNotes:")
    for note in recommendation.notes:
        print(f"  - {note}")
    
    # Test different market conditions
    print("\n" + "=" * 50)
    print("TESTING DIFFERENT MARKET CONDITIONS")
    print("=" * 50)
    
    # High volatility trending (good for 0DTE)
    trend = np.linspace(0, 10, 100)
    noise = np.random.randn(100) * 3
    prices = base_price + trend + noise
    
    market_data['close'] = prices
    market_data['high'] = prices + abs(np.random.randn(100) * 1)
    market_data['low'] = prices - abs(np.random.randn(100) * 1)
    
    recommendation2 = selector.select_strategy(market_data, account_info)
    print(f"\nHigh Volatility Trending Market:")
    print(f"  Recommended: {recommendation2.primary_strategy}")
    print(f"  Market Regime: {recommendation2.market_conditions.market_regime.name}")
    
    # Low volatility before expansion (good for Straddle)
    prices = base_price + np.random.randn(100) * 0.5  # Very low volatility
    market_data['close'] = prices
    market_data['high'] = prices + abs(np.random.randn(100) * 0.1)
    market_data['low'] = prices - abs(np.random.randn(100) * 0.1)
    
    recommendation3 = selector.select_strategy(market_data, account_info)
    print(f"\nLow Volatility Compression:")
    print(f"  Recommended: {recommendation3.primary_strategy}")
    print(f"  Market Regime: {recommendation3.market_conditions.market_regime.name}")
