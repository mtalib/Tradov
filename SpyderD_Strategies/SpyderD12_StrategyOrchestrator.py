#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD12_StrategyOrchestrator.py
Group: D (Trading Strategies)
Purpose: Coordinate multiple strategies and manage conflicts

Description:
    This module acts as the central coordinator for all trading strategies in the
    Spyder system. It handles strategy selection based on market conditions, manages
    capital allocation across strategies, resolves conflicts when multiple strategies
    generate signals, and ensures risk limits are respected. The orchestrator
    implements a priority-based system and uses market regime analysis to optimize
    strategy deployment.

Author: Mohamed Talib
Date: 2025-01-27
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
from datetime import datetime, time
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict
import threading
import uuid

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderC_MarketData.SpyderC04_MarketInternals import MarketInternals
from SpyderD_Strategies.SpyderD02_IronCondor import IronCondorStrategy
from SpyderD_Strategies.SpyderD09_IronButterfly import IronButterflyStrategy
from SpyderD_Strategies.SpyderD10_BullPutSpread import BullPutSpreadStrategy
from SpyderD_Strategies.SpyderD11_BearCallSpread import BearCallSpreadStrategy
from SpyderD_Strategies.SpyderD04_ZeroDTE import ZeroDTEStrategy
from SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
from SpyderE_Risk.SpyderE02_PositionSizer import get_position_sizer
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
from SpyderU_Utilities.SpyderU07_Constants import (
    MAX_PORTFOLIO_HEAT_MONDAY,
    MAX_PORTFOLIO_HEAT_OTHER,
    MAX_DAILY_TRADES_MONDAY,
    MAX_DAILY_TRADES_OTHER,
    VOLATILITY_REGIME_THRESHOLDS
)
from SpyderU_Utilities.SpyderU11_FeatureFlags import get_feature_flags
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType
from SpyderF_Analysis.SpyderF01_Indicators import TechnicalIndicators
from SpyderF_Analysis.SpyderF05_TrendDetection import TrendDetector
from SpyderF_Analysis.SpyderF08_VolatilityRegime import VolatilityRegimeAnalyzer

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy priorities (higher = higher priority)
STRATEGY_PRIORITIES = {
    'IronCondor': 100,
    'IronButterfly': 90,
    'BullPutSpread': 80,
    'BearCallSpread': 80,
    'ZeroDTE': 70
}

# Capital allocation percentages (updated for better distribution)
DEFAULT_ALLOCATIONS = {
    'IronCondor': 0.30,      # 30% to iron condor
    'IronButterfly': 0.25,   # 25% to iron butterfly
    'BullPutSpread': 0.15,   # 15% to bull put spread
    'BearCallSpread': 0.15,  # 15% to bear call spread
    'ZeroDTE': 0.15         # 15% to 0DTE
}

# Conflict resolution parameters
MIN_STRIKE_SEPARATION = 5.0   # Minimum points between strikes
MAX_SIGNALS_PER_CYCLE = 5     # Maximum signals to process per cycle
SIGNAL_EXPIRY_MINUTES = 5      # Signal validity period

# Market analysis parameters
TREND_LOOKBACK_PERIODS = 20
VOLATILITY_LOOKBACK_DAYS = 30
INTERNALS_WEIGHT = 0.25

# ==============================================================================
# ENUMERATIONS
# ==============================================================================
class MarketRegime(Enum):
    """Market regime classification."""
    STRONG_TRENDING_UP = auto()
    TRENDING_UP = auto()
    NEUTRAL_BULLISH = auto()
    NEUTRAL = auto()
    NEUTRAL_BEARISH = auto()
    TRENDING_DOWN = auto()
    STRONG_TRENDING_DOWN = auto()

class VolatilityRegime(Enum):
    """Volatility regime classification."""
    LOW = auto()
    NORMAL = auto()
    HIGH = auto()
    EXTREME = auto()

class ConflictType(Enum):
    """Types of strategy conflicts."""
    OVERLAPPING_STRIKES = auto()
    INSUFFICIENT_CAPITAL = auto()
    RISK_LIMIT_EXCEEDED = auto()
    OPPOSING_BIAS = auto()
    MAX_POSITIONS_REACHED = auto()
    SAME_EXPIRATION = auto()

class OrchestratorState(Enum):
    """Orchestrator operational state."""
    INITIALIZING = auto()
    READY = auto()
    ANALYZING = auto()
    EXECUTING = auto()
    PAUSED = auto()
    ERROR = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StrategySignal:
    """Unified signal structure for all strategies."""
    signal_id: str
    strategy_name: str
    signal_type: str  # 'entry' or 'exit'
    timestamp: datetime
    score: float
    priority: int
    capital_required: float
    risk_amount: float
    signal_data: Any  # Strategy-specific signal object
    expiry_time: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ConflictResolution:
    """Result of conflict resolution."""
    approved_signals: List[StrategySignal]
    rejected_signals: List[StrategySignal]
    conflicts: List[Dict[str, Any]]
    capital_allocated: Dict[str, float]
    resolution_id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class MarketConditions:
    """Current market conditions analysis."""
    market_regime: MarketRegime
    volatility_regime: VolatilityRegime
    trend_strength: float
    volatility_percentile: float
    gap_percentage: float
    internals_score: float
    vix_level: float
    put_call_ratio: float
    market_breadth: float
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExecutionResult:
    """Result of signal execution."""
    signal_id: str
    success: bool
    position_id: Optional[str]
    error_message: Optional[str]
    execution_time: datetime

# ==============================================================================
# STRATEGY ORCHESTRATOR
# ==============================================================================
class StrategyOrchestrator:
    """
    Central coordinator for all trading strategies.
    
    Responsibilities:
    - Strategy selection based on market conditions
    - Capital allocation across strategies
    - Conflict resolution between signals
    - Risk limit enforcement
    - Performance-based adjustments
    - Real-time strategy coordination
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the strategy orchestrator."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config
        
        # Component initialization
        self.risk_manager = get_risk_manager()
        self.position_sizer = get_position_sizer()
        self.market_internals = MarketInternals()
        self.event_manager = get_event_manager()
        self.feature_flags = get_feature_flags()
        
        # Analysis components
        self.indicators = TechnicalIndicators()
        self.trend_detector = TrendDetector()
        self.vol_analyzer = VolatilityRegimeAnalyzer()
        
        # Strategy instances
        self.strategies: Dict[str, Any] = {}
        self._initialize_strategies()
        
        # Capital allocation
        self.capital_allocations = config.get('allocations', DEFAULT_ALLOCATIONS.copy())
        self.total_capital = config.get('total_capital', 100000)
        self.available_capital = self.total_capital
        
        # State tracking
        self.state = OrchestratorState.INITIALIZING
        self.active_positions: Dict[str, Dict[str, Any]] = {}
        self.pending_signals: List[StrategySignal] = []
        self.signal_history: List[StrategySignal] = []
        self.daily_trades = 0
        self.last_analysis_time = None
        self.current_conditions: Optional[MarketConditions] = None
        
        # Performance tracking
        self.performance_history = defaultdict(list)
        self.strategy_metrics = defaultdict(lambda: {
            'signals_generated': 0,
            'signals_approved': 0,
            'signals_rejected': 0,
            'positions_opened': 0,
            'positions_closed': 0,
            'total_pnl': 0.0
        })
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Complete initialization
        self.state = OrchestratorState.READY
        self.logger.info(f"Strategy orchestrator initialized with {len(self.strategies)} strategies")
    
    def _initialize_strategies(self) -> None:
        """Initialize all available strategies."""
        try:
            # Get strategy configurations
            strategy_configs = self.config.get('strategies', {})
            
            # Iron Condor
            if self.feature_flags.is_enabled('iron_condor_strategy'):
                config = strategy_configs.get('IronCondor', {})
                self.strategies['IronCondor'] = IronCondorStrategy(config)
                self.logger.info("Iron Condor strategy initialized")
            
            # Iron Butterfly
            if self.feature_flags.is_enabled('iron_butterfly_strategy'):
                config = strategy_configs.get('IronButterfly', {})
                self.strategies['IronButterfly'] = IronButterflyStrategy(config)
                self.logger.info("Iron Butterfly strategy initialized")
            
            # Bull Put Spread
            if self.feature_flags.is_enabled('directional_spreads'):
                config = strategy_configs.get('BullPutSpread', {})
                self.strategies['BullPutSpread'] = BullPutSpreadStrategy(config)
                self.logger.info("Bull Put Spread strategy initialized")
            
            # Bear Call Spread
            if self.feature_flags.is_enabled('directional_spreads'):
                config = strategy_configs.get('BearCallSpread', {})
                # self.strategies['BearCallSpread'] = BearCallSpreadStrategy(config)
                self.logger.info("Bear Call Spread strategy initialized (pending implementation)")
            
            # Zero DTE
            if self.feature_flags.is_enabled('zero_dte_strategy'):
                config = strategy_configs.get('ZeroDTE', {})
                # self.strategies['ZeroDTE'] = ZeroDTEStrategy(config)
                self.logger.info("Zero DTE strategy initialized (pending implementation)")
            
        except Exception as e:
            self.logger.error(f"Error initializing strategies: {e}")
            self.error_handler.handle_error(e)
            self.state = OrchestratorState.ERROR
    
    def analyze_market_conditions(self, market_data: Dict[str, Any]) -> MarketConditions:
        """
        Comprehensive market condition analysis.
        
        Args:
            market_data: Current market data
            
        Returns:
            MarketConditions object
        """
        try:
            # Extract key metrics
            price = market_data.get('last_price', 0)
            prev_close = market_data.get('prev_close', price)
            volume = market_data.get('volume', 0)
            
            # Calculate gap
            gap_pct = ((price - prev_close) / prev_close) if prev_close > 0 else 0
            
            # Trend analysis
            trend_data = self.trend_detector.analyze_trend(market_data)
            trend_strength = trend_data.get('strength', 0)
            trend_direction = trend_data.get('direction', 'neutral')
            
            # Determine market regime
            market_regime = self._classify_market_regime(trend_direction, trend_strength)
            
            # Volatility analysis
            vol_data = self.vol_analyzer.analyze_regime(market_data)
            vol_regime = self._classify_volatility_regime(vol_data)
            vol_percentile = vol_data.get('iv_percentile', 50)
            vix_level = market_data.get('vix', 20)
            
            # Market internals
            internals_data = self.market_internals.get_current_snapshot()
            internals_score = self._calculate_internals_score(internals_data)
            
            # Market breadth
            breadth = self._calculate_market_breadth(internals_data)
            
            # Put/Call ratio
            pc_ratio = market_data.get('put_call_ratio', 1.0)
            
            conditions = MarketConditions(
                market_regime=market_regime,
                volatility_regime=vol_regime,
                trend_strength=trend_strength,
                volatility_percentile=vol_percentile,
                gap_percentage=gap_pct,
                internals_score=internals_score,
                vix_level=vix_level,
                put_call_ratio=pc_ratio,
                market_breadth=breadth,
                timestamp=datetime.now(),
                metadata={
                    'trend_data': trend_data,
                    'vol_data': vol_data,
                    'internals_data': internals_data
                }
            )
            
            self.current_conditions = conditions
            self.last_analysis_time = datetime.now()
            
            return conditions
            
        except Exception as e:
            self.logger.error(f"Error analyzing market conditions: {e}")
            self.error_handler.handle_error(e)
            
            # Return neutral conditions on error
            return MarketConditions(
                market_regime=MarketRegime.NEUTRAL,
                volatility_regime=VolatilityRegime.NORMAL,
                trend_strength=0.0,
                volatility_percentile=50.0,
                gap_percentage=0.0,
                internals_score=0.0,
                vix_level=20.0,
                put_call_ratio=1.0,
                market_breadth=0.0,
                timestamp=datetime.now()
            )
    
    def _classify_market_regime(self, direction: str, strength: float) -> MarketRegime:
        """Classify market regime based on trend"""
        if direction == 'up':
            if strength > 0.7:
                return MarketRegime.STRONG_TRENDING_UP
            elif strength > 0.4:
                return MarketRegime.TRENDING_UP
            else:
                return MarketRegime.NEUTRAL_BULLISH
        elif direction == 'down':
            if strength > 0.7:
                return MarketRegime.STRONG_TRENDING_DOWN
            elif strength > 0.4:
                return MarketRegime.TRENDING_DOWN
            else:
                return MarketRegime.NEUTRAL_BEARISH
        else:
            return MarketRegime.NEUTRAL
    
    def _classify_volatility_regime(self, vol_data: Dict) -> VolatilityRegime:
        """Classify volatility regime"""
        iv_rank = vol_data.get('iv_rank', 50)
        
        if iv_rank < 25:
            return VolatilityRegime.LOW
        elif iv_rank < 50:
            return VolatilityRegime.NORMAL
        elif iv_rank < 75:
            return VolatilityRegime.HIGH
        else:
            return VolatilityRegime.EXTREME
    
    def _calculate_internals_score(self, internals_data: Any) -> float:
        """Calculate market internals score"""
        if not internals_data:
            return 0.0
        
        score = 0.0
        
        # NYSE TICK
        tick = internals_data.nyse_tick or 0
        if abs(tick) > 1000:
            score += 0.3
        elif abs(tick) > 500:
            score += 0.2
        else:
            score += 0.1
        
        # ADD Line
        add_line = internals_data.nyse_add_line or 0
        if abs(add_line) > 2000:
            score += 0.3
        elif abs(add_line) > 1000:
            score += 0.2
        else:
            score += 0.1
        
        # Advance/Decline
        if internals_data.advances and internals_data.declines:
            ratio = internals_data.advances / max(internals_data.declines, 1)
            if ratio > 2 or ratio < 0.5:
                score += 0.2
            else:
                score += 0.1
        
        # Up/Down Volume
        if internals_data.up_volume and internals_data.down_volume:
            vol_ratio = internals_data.up_volume / max(internals_data.down_volume, 1)
            if vol_ratio > 2 or vol_ratio < 0.5:
                score += 0.2
            else:
                score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_market_breadth(self, internals_data: Any) -> float:
        """Calculate market breadth score"""
        if not internals_data or not internals_data.advances:
            return 0.0
        
        total_issues = internals_data.advances + internals_data.declines
        if total_issues == 0:
            return 0.0
        
        breadth = (internals_data.advances - internals_data.declines) / total_issues
        return breadth  # Range: -1 to 1
    
    def select_active_strategies(self, conditions: MarketConditions) -> List[str]:
        """
        Select which strategies should be active based on market conditions.
        
        Args:
            conditions: Current market conditions
            
        Returns:
            List of strategy names to activate
        """
        active = []
        
        try:
            # Always consider Iron Condor in normal/high volatility
            if ('IronCondor' in self.strategies and 
                conditions.volatility_regime in [VolatilityRegime.NORMAL, VolatilityRegime.HIGH]):
                active.append('IronCondor')
            
            # Iron Butterfly in high volatility with neutral market
            if ('IronButterfly' in self.strategies and
                conditions.volatility_regime in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME] and
                conditions.market_regime in [MarketRegime.NEUTRAL, MarketRegime.NEUTRAL_BULLISH, 
                                           MarketRegime.NEUTRAL_BEARISH]):
                active.append('IronButterfly')
            
            # Bull Put Spread in bullish conditions
            if ('BullPutSpread' in self.strategies and
                conditions.market_regime in [MarketRegime.TRENDING_UP, MarketRegime.STRONG_TRENDING_UP] and
                conditions.trend_strength > 0.3):
                active.append('BullPutSpread')
            
            # Bear Call Spread in bearish conditions
            if ('BearCallSpread' in self.strategies and
                conditions.market_regime in [MarketRegime.TRENDING_DOWN, MarketRegime.STRONG_TRENDING_DOWN] and
                conditions.trend_strength > 0.3):
                active.append('BearCallSpread')
            
            # Zero DTE in strong trending markets with high volatility
            if ('ZeroDTE' in self.strategies and
                conditions.trend_strength > 0.5 and
                conditions.volatility_regime in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME]):
                active.append('ZeroDTE')
            
            # Filter based on time of day
            active = self._filter_by_time_restrictions(active)
            
            self.logger.info(
                f"Selected strategies for {conditions.market_regime.name}/"
                f"{conditions.volatility_regime.name}: {active}"
            )
            
        except Exception as e:
            self.logger.error(f"Error selecting strategies: {e}")
            # Default to Iron Condor if available
            if 'IronCondor' in self.strategies:
                active = ['IronCondor']
        
        return active
    
    def _filter_by_time_restrictions(self, strategies: List[str]) -> List[str]:
        """Filter strategies based on time restrictions"""
        current_time = datetime.now().time()
        filtered = []
        
        for strategy in strategies:
            # Zero DTE only in morning and afternoon sessions
            if strategy == 'ZeroDTE':
                if (time(9, 45) <= current_time <= time(11, 30) or
                    time(13, 0) <= current_time <= time(15, 30)):
                    filtered.append(strategy)
            else:
                filtered.append(strategy)
        
        return filtered
    
    def collect_strategy_signals(self, 
                               active_strategies: List[str],
                               market_data: Dict[str, Any]) -> List[StrategySignal]:
        """
        Collect signals from all active strategies.
        
        Args:
            active_strategies: List of active strategy names
            market_data: Current market data
            
        Returns:
            List of strategy signals
        """
        all_signals = []
        
        try:
            for strategy_name in active_strategies:
                strategy = self.strategies.get(strategy_name)
                if not strategy:
                    continue
                
                # Get signals from strategy
                if hasattr(strategy, 'analyze_market'):
                    signals = strategy.analyze_market(market_data)
                elif hasattr(strategy, 'generate_entry_signal'):
                    signal = strategy.generate_entry_signal(market_data)
                    signals = [signal] if signal else []
                else:
                    continue
                
                # Convert to unified signal format
                for signal in signals:
                    if signal:
                        unified_signal = self._convert_to_unified_signal(
                            strategy_name, signal, market_data
                        )
                        if unified_signal:
                            all_signals.append(unified_signal)
                            self.strategy_metrics[strategy_name]['signals_generated'] += 1
            
            # Clean expired signals
            self._clean_expired_signals()
            
            self.logger.info(f"Collected {len(all_signals)} signals from {len(active_strategies)} strategies")
            
        except Exception as e:
            self.logger.error(f"Error collecting signals: {e}")
            self.error_handler.handle_error(e)
        
        return all_signals
    
    def _convert_to_unified_signal(self, strategy_name: str, signal: Any, 
                                 market_data: Dict) -> Optional[StrategySignal]:
        """Convert strategy-specific signal to unified format"""
        try:
            # Calculate capital required and risk
            capital_required = self._calculate_capital_required(signal)
            risk_amount = self._calculate_risk_amount(signal)
            
            # Create unified signal
            unified = StrategySignal(
                signal_id=getattr(signal, 'signal_id', str(uuid.uuid4())),
                strategy_name=strategy_name,
                signal_type='entry',  # Assuming entry signal
                timestamp=datetime.now(),
                score=getattr(signal, 'score', 50),
                priority=STRATEGY_PRIORITIES.get(strategy_name, 50),
                capital_required=capital_required,
                risk_amount=risk_amount,
                signal_data=signal,
                expiry_time=datetime.now() + pd.Timedelta(minutes=SIGNAL_EXPIRY_MINUTES),
                metadata={
                    'market_conditions': self.current_conditions,
                    'signal_metadata': getattr(signal, 'metadata', {})
                }
            )
            
            return unified
            
        except Exception as e:
            self.logger.error(f"Error converting signal: {e}")
            return None
    
    def resolve_conflicts(self, signals: List[StrategySignal]) -> ConflictResolution:
        """
        Resolve conflicts between multiple signals.
        
        Args:
            signals: List of all strategy signals
            
        Returns:
            ConflictResolution with approved/rejected signals
        """
        approved = []
        rejected = []
        conflicts = []
        capital_allocated = defaultdict(float)
        
        try:
            with self._lock:
                # Separate exits and entries
                exit_signals = [s for s in signals if s.signal_type == 'exit']
                entry_signals = [s for s in signals if s.signal_type == 'entry']
                
                # Always approve exits first
                approved.extend(exit_signals)
                
                # Sort entries by priority and score
                entry_signals.sort(key=lambda x: (x.priority, x.score), reverse=True)
                
                # Process entry signals
                remaining_capital = self.available_capital
                total_risk = self._calculate_total_portfolio_risk()
                max_risk = self._get_max_portfolio_risk()
                
                for signal in entry_signals:
                    # Check all conflict conditions
                    conflict_found = False
                    conflict_reasons = []
                    
                    # 1. Capital check
                    if signal.capital_required > remaining_capital:
                        conflict_found = True
                        conflict_reasons.append({
                            'type': ConflictType.INSUFFICIENT_CAPITAL,
                            'details': f'Required: ${signal.capital_required:.2f}, Available: ${remaining_capital:.2f}'
                        })
                    
                    # 2. Risk limit check
                    if total_risk + signal.risk_amount > max_risk:
                        conflict_found = True
                        conflict_reasons.append({
                            'type': ConflictType.RISK_LIMIT_EXCEEDED,
                            'details': f'Would exceed max risk: ${max_risk:.2f}'
                        })
                    
                    # 3. Strike overlap check
                    overlap_conflict = self._check_strike_overlaps(signal, approved)
                    if overlap_conflict:
                        conflict_found = True
                        conflict_reasons.append(overlap_conflict)
                    
                    # 4. Max positions check
                    if self.daily_trades >= self._get_max_daily_trades():
                        conflict_found = True
                        conflict_reasons.append({
                            'type': ConflictType.MAX_POSITIONS_REACHED,
                            'details': f'Daily limit reached: {self.daily_trades}'
                        })
                    
                    # 5. Opposing bias check
                    bias_conflict = self._check_opposing_bias(signal, approved)
                    if bias_conflict:
                        conflict_found = True
                        conflict_reasons.append(bias_conflict)
                    
                    # 6. Same expiration check
                    expiry_conflict = self._check_same_expiration(signal, approved)
                    if expiry_conflict:
                        conflict_found = True
                        conflict_reasons.append(expiry_conflict)
                    
                    # Decision
                    if not conflict_found:
                        approved.append(signal)
                        remaining_capital -= signal.capital_required
                        total_risk += signal.risk_amount
                        capital_allocated[signal.strategy_name] += signal.capital_required
                        self.strategy_metrics[signal.strategy_name]['signals_approved'] += 1
                    else:
                        rejected.append(signal)
                        self.strategy_metrics[signal.strategy_name]['signals_rejected'] += 1
                        for reason in conflict_reasons:
                            conflicts.append({
                                'signal': signal,
                                'conflict': reason
                            })
            
            # Log resolution results
            self.logger.info(
                f"Conflict resolution: {len(approved)} approved, "
                f"{len(rejected)} rejected, {len(conflicts)} conflicts"
            )
            
        except Exception as e:
            self.logger.error(f"Error resolving conflicts: {e}")
            self.error_handler.handle_error(e)
            # On error, approve only exits
            approved = [s for s in signals if s.signal_type == 'exit']
            rejected = [s for s in signals if s.signal_type == 'entry']
        
        return ConflictResolution(
            approved_signals=approved,
            rejected_signals=rejected,
            conflicts=conflicts,
            capital_allocated=dict(capital_allocated)
        )
    
    def _check_strike_overlaps(self, signal: StrategySignal, 
                              approved: List[StrategySignal]) -> Optional[Dict]:
        """Check for overlapping strikes between signals"""
        try:
            signal_strikes = self._extract_strikes(signal.signal_data)
            
            for approved_signal in approved:
                if approved_signal.signal_type != 'entry':
                    continue
                
                approved_strikes = self._extract_strikes(approved_signal.signal_data)
                
                # Check for overlap
                for s1 in signal_strikes:
                    for s2 in approved_strikes:
                        if abs(s1 - s2) < MIN_STRIKE_SEPARATION:
                            return {
                                'type': ConflictType.OVERLAPPING_STRIKES,
                                'details': f'Strike {s1} overlaps with {s2} from {approved_signal.strategy_name}'
                            }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking strike overlap: {e}")
            return None
    
    def _check_opposing_bias(self, signal: StrategySignal, 
                           approved: List[StrategySignal]) -> Optional[Dict]:
        """Check if signal has opposing directional bias"""
        try:
            # Bull and bear spreads are opposing
            if signal.strategy_name == 'BullPutSpread':
                for approved_signal in approved:
                    if approved_signal.strategy_name == 'BearCallSpread':
                        return {
                            'type': ConflictType.OPPOSING_BIAS,
                            'details': 'Bull and bear spreads conflict'
                        }
            
            elif signal.strategy_name == 'BearCallSpread':
                for approved_signal in approved:
                    if approved_signal.strategy_name == 'BullPutSpread':
                        return {
                            'type': ConflictType.OPPOSING_BIAS,
                            'details': 'Bear and bull spreads conflict'
                        }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking opposing bias: {e}")
            return None
    
    def _check_same_expiration(self, signal: StrategySignal, 
                              approved: List[StrategySignal]) -> Optional[Dict]:
        """Check if multiple neutral strategies target same expiration"""
        try:
            # Only check for neutral strategies
            neutral_strategies = ['IronCondor', 'IronButterfly']
            
            if signal.strategy_name not in neutral_strategies:
                return None
            
            signal_expiry = self._extract_expiration(signal.signal_data)
            
            for approved_signal in approved:
                if (approved_signal.strategy_name in neutral_strategies and
                    approved_signal.signal_type == 'entry'):
                    
                    approved_expiry = self._extract_expiration(approved_signal.signal_data)
                    
                    if signal_expiry == approved_expiry:
                        return {
                            'type': ConflictType.SAME_EXPIRATION,
                            'details': f'Same expiration as {approved_signal.strategy_name}'
                        }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking expiration conflict: {e}")
            return None
    
    def _extract_strikes(self, signal_data: Any) -> List[float]:
        """Extract strike prices from signal data"""
        strikes = []
        
        try:
            # Handle different signal types
            if hasattr(signal_data, 'strikes'):
                strikes.extend(signal_data.strikes)
            elif hasattr(signal_data, 'short_strike') and hasattr(signal_data, 'long_strike'):
                strikes.extend([signal_data.short_strike, signal_data.long_strike])
            elif hasattr(signal_data, 'position'):  # Iron Butterfly
                position = signal_data.position
                strikes.extend([
                    position.short_call_strike,
                    position.short_put_strike,
                    position.long_call_strike,
                    position.long_put_strike
                ])
            
        except Exception as e:
            self.logger.error(f"Error extracting strikes: {e}")
        
        return [s for s in strikes if s > 0]
    
    def _extract_expiration(self, signal_data: Any) -> Optional[str]:
        """Extract expiration from signal data"""
        try:
            if hasattr(signal_data, 'expiration'):
                return signal_data.expiration
            elif hasattr(signal_data, 'position'):
                return signal_data.position.expiration
            return None
        except:
            return None
    
    def _calculate_capital_required(self, signal: Any) -> float:
        """Calculate capital required for a signal"""
        try:
            if hasattr(signal, 'max_loss'):
                return abs(signal.max_loss)
            elif hasattr(signal, 'capital_required'):
                return signal.capital_required
            elif hasattr(signal, 'position'):  # Iron Butterfly
                return abs(signal.position.max_loss * signal.position.quantity)
            else:
                # Default calculation
                return 5000  # Default $5000 per trade
                
        except Exception as e:
            self.logger.error(f"Error calculating capital: {e}")
            return 5000
    
    def _calculate_risk_amount(self, signal: Any) -> float:
        """Calculate risk amount for a signal"""
        try:
            if hasattr(signal, 'max_loss'):
                return abs(signal.max_loss)
            elif hasattr(signal, 'risk_amount'):
                return signal.risk_amount
            elif hasattr(signal, 'position'):  # Iron Butterfly
                return abs(signal.position.max_loss * signal.position.quantity)
            else:
                return self._calculate_capital_required(signal) * 0.5  # Default 50% risk
                
        except Exception as e:
            self.logger.error(f"Error calculating risk: {e}")
            return 2500
    
    def _calculate_total_portfolio_risk(self) -> float:
        """Calculate total portfolio risk from open positions"""
        total_risk = 0
        
        try:
            with self._lock:
                for position in self.active_positions.values():
                    total_risk += position.get('risk_amount', 0)
                
        except Exception as e:
            self.logger.error(f"Error calculating portfolio risk: {e}")
        
        return total_risk
    
    def _get_max_portfolio_risk(self) -> float:
        """Get maximum allowed portfolio risk based on day of week"""
        if DateTimeUtils.is_monday():
            return self.total_capital * MAX_PORTFOLIO_HEAT_MONDAY
        else:
            return self.total_capital * MAX_PORTFOLIO_HEAT_OTHER
    
    def _get_max_daily_trades(self) -> int:
        """Get maximum daily trades based on day of week"""
        if DateTimeUtils.is_monday():
            return MAX_DAILY_TRADES_MONDAY
        else:
            return MAX_DAILY_TRADES_OTHER
    
    def _clean_expired_signals(self) -> None:
        """Remove expired signals from pending list"""
        current_time = datetime.now()
        self.pending_signals = [
            s for s in self.pending_signals 
            if s.expiry_time > current_time
        ]
    
    def execute_approved_signals(self, resolution: ConflictResolution) -> Dict[str, Any]:
        """
        Execute approved signals and update tracking.
        
        Args:
            resolution: Conflict resolution results
            
        Returns:
            Execution summary
        """
        execution_summary = {
            'executed': [],
            'failed': [],
            'capital_used': 0,
            'positions_opened': 0,
            'positions_closed': 0,
            'execution_id': str(uuid.uuid4())
        }
        
        try:
            # Execute each approved signal
            for signal in resolution.approved_signals:
                try:
                    result = self._execute_single_signal(signal)
                    
                    if result.success:
                        execution_summary['executed'].append(result)
                        
                        if signal.signal_type == 'exit':
                            execution_summary['positions_closed'] += 1
                        else:
                            execution_summary['positions_opened'] += 1
                            execution_summary['capital_used'] += signal.capital_required
                            self.daily_trades += 1
                        
                        # Update strategy metrics
                        self.strategy_metrics[signal.strategy_name]['positions_opened'] += 1
                    else:
                        execution_summary['failed'].append(result)
                    
                except Exception as e:
                    self.logger.error(f"Failed to execute signal {signal.signal_id}: {e}")
                    execution_summary['failed'].append(
                        ExecutionResult(
                            signal_id=signal.signal_id,
                            success=False,
                            position_id=None,
                            error_message=str(e),
                            execution_time=datetime.now()
                        )
                    )
            
            # Update available capital
            self._update_available_capital()
            
            # Emit execution event
            self.event_manager.create_event(
                EventType.TRADING,
                {
                    'action': 'strategy_execution',
                    'summary': execution_summary,
                    'resolution_id': resolution.resolution_id,
                    'timestamp': datetime.now()
                },
                source='strategy_orchestrator'
            )
            
            self.logger.info(
                f"Execution complete: {execution_summary['positions_opened']} opened, "
                f"{execution_summary['positions_closed']} closed, "
                f"${execution_summary['capital_used']:.2f} deployed"
            )
            
        except Exception as e:
            self.logger.error(f"Error executing signals: {e}")
            self.error_handler.handle_error(e)
        
        return execution_summary
    
    def _execute_single_signal(self, signal: StrategySignal) -> ExecutionResult:
        """Execute a single signal"""
        try:
            strategy = self.strategies.get(signal.strategy_name)
            
            if not strategy:
                return ExecutionResult(
                    signal_id=signal.signal_id,
                    success=False,
                    position_id=None,
                    error_message=f"Strategy {signal.strategy_name} not found",
                    execution_time=datetime.now()
                )
            
            # Execute through strategy
            if hasattr(strategy, 'execute_signal'):
                success = strategy.execute_signal(signal.signal_data)
            else:
                success = False
            
            if success:
                # Track position
                position_id = f"{signal.strategy_name}_{signal.signal_id}"
                
                if signal.signal_type == 'entry':
                    self.active_positions[position_id] = {
                        'strategy': signal.strategy_name,
                        'entry_time': datetime.now(),
                        'signal_data': signal.signal_data,
                        'capital_allocated': signal.capital_required,
                        'risk_amount': signal.risk_amount,
                        'status': 'open'
                    }
                
                return ExecutionResult(
                    signal_id=signal.signal_id,
                    success=True,
                    position_id=position_id,
                    error_message=None,
                    execution_time=datetime.now()
                )
            else:
                return ExecutionResult(
                    signal_id=signal.signal_id,
                    success=False,
                    position_id=None,
                    error_message="Strategy execution failed",
                    execution_time=datetime.now()
                )
            
        except Exception as e:
            return ExecutionResult(
                signal_id=signal.signal_id,
                success=False,
                position_id=None,
                error_message=str(e),
                execution_time=datetime.now()
            )
    
    def _update_available_capital(self) -> None:
        """Update available capital based on open positions"""
        with self._lock:
            used_capital = sum(
                pos['capital_allocated'] 
                for pos in self.active_positions.values() 
                if pos['status'] == 'open'
            )
            self.available_capital = self.total_capital - used_capital
    
    def orchestrate(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main orchestration method - coordinates all strategies.
        
        Args:
            market_data: Current market data
            
        Returns:
            Orchestration results
        """
        results = {
            'timestamp': datetime.now(),
            'state': self.state.name,
            'market_conditions': None,
            'active_strategies': [],
            'signals_generated': 0,
            'signals_approved': 0,
            'execution_summary': {},
            'status': 'success'
        }
        
        try:
            # Check if orchestrator is ready
            if self.state != OrchestratorState.READY:
                results['status'] = 'not_ready'
                return results
            
            # Set state to analyzing
            self.state = OrchestratorState.ANALYZING
            
            # 1. Analyze market conditions
            conditions = self.analyze_market_conditions(market_data)
            results['market_conditions'] = conditions
            
            # 2. Select active strategies
            active_strategies = self.select_active_strategies(conditions)
            results['active_strategies'] = active_strategies
            
            if not active_strategies:
                self.logger.info("No strategies selected for current conditions")
                self.state = OrchestratorState.READY
                return results
            
            # 3. Collect signals from strategies
            signals = self.collect_strategy_signals(active_strategies, market_data)
            results['signals_generated'] = len(signals)
            
            # Store signals in history
            self.signal_history.extend(signals)
            
            if not signals:
                self.logger.info("No signals generated")
                self.state = OrchestratorState.READY
                return results
            
            # 4. Resolve conflicts
            resolution = self.resolve_conflicts(signals)
            results['signals_approved'] = len(resolution.approved_signals)
            results['signals_rejected'] = len(resolution.rejected_signals)
            results['conflicts'] = len(resolution.conflicts)
            
            # 5. Execute approved signals
            if resolution.approved_signals:
                self.state = OrchestratorState.EXECUTING
                execution_summary = self.execute_approved_signals(resolution)
                results['execution_summary'] = execution_summary
            
            # 6. Update performance tracking
            self._update_performance_tracking(results)
            
            # 7. Manage existing positions
            self._manage_existing_positions()
            
            # Return to ready state
            self.state = OrchestratorState.READY
            
            self.logger.info(
                f"Orchestration complete: {results['signals_generated']} generated, "
                f"{results['signals_approved']} approved, "
                f"{results.get('signals_rejected', 0)} rejected"
            )
            
        except Exception as e:
            self.logger.error(f"Error in orchestration: {e}")
            self.error_handler.handle_error(e)
            results['status'] = 'error'
            results['error'] = str(e)
            self.state = OrchestratorState.ERROR
        
        return results
    
    def _manage_existing_positions(self) -> None:
        """Manage existing positions across all strategies"""
        try:
            for strategy_name, strategy in self.strategies.items():
                if hasattr(strategy, 'manage_positions'):
                    strategy.manage_positions()
                    
        except Exception as e:
            self.logger.error(f"Error managing positions: {e}")
    
    def _update_performance_tracking(self, results: Dict[str, Any]) -> None:
        """Update performance tracking for strategies"""
        try:
            # Update strategy-specific metrics
            for strategy_name in results.get('active_strategies', []):
                self.performance_history[strategy_name].append({
                    'timestamp': results['timestamp'],
                    'signals_generated': sum(
                        1 for s in self.signal_history 
                        if s.strategy_name == strategy_name and 
                        s.timestamp.date() == datetime.now().date()
                    ),
                    'market_conditions': results.get('market_conditions')
                })
            
            # Clean old history (keep last 100 entries per strategy)
            for strategy_name in self.performance_history:
                if len(self.performance_history[strategy_name]) > 100:
                    self.performance_history[strategy_name] = \
                        self.performance_history[strategy_name][-100:]
                
        except Exception as e:
            self.logger.error(f"Error updating performance: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current orchestrator status"""
        with self._lock:
            # Calculate active position stats
            active_positions = [
                p for p in self.active_positions.values() 
                if p['status'] == 'open'
            ]
            
            total_allocated = sum(p['capital_allocated'] for p in active_positions)
            total_risk = sum(p['risk_amount'] for p in active_positions)
            
            return {
                'state': self.state.name,
                'active_strategies': list(self.strategies.keys()),
                'total_capital': self.total_capital,
                'available_capital': self.available_capital,
                'capital_allocated': total_allocated,
                'total_risk': total_risk,
                'risk_utilization': total_risk / self._get_max_portfolio_risk() if self._get_max_portfolio_risk() > 0 else 0,
                'open_positions': len(active_positions),
                'daily_trades': self.daily_trades,
                'max_daily_trades': self._get_max_daily_trades(),
                'capital_allocations': dict(self.capital_allocations),
                'last_analysis': self.last_analysis_time.isoformat() if self.last_analysis_time else None,
                'current_conditions': {
                    'market_regime': self.current_conditions.market_regime.name if self.current_conditions else None,
                    'volatility_regime': self.current_conditions.volatility_regime.name if self.current_conditions else None,
                    'trend_strength': self.current_conditions.trend_strength if self.current_conditions else 0,
                    'internals_score': self.current_conditions.internals_score if self.current_conditions else 0
                },
                'strategy_metrics': dict(self.strategy_metrics)
            }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all strategies"""
        summary = {
            'total_signals_generated': sum(m['signals_generated'] for m in self.strategy_metrics.values()),
            'total_signals_approved': sum(m['signals_approved'] for m in self.strategy_metrics.values()),
            'total_signals_rejected': sum(m['signals_rejected'] for m in self.strategy_metrics.values()),
            'total_positions_opened': sum(m['positions_opened'] for m in self.strategy_metrics.values()),
            'total_positions_closed': sum(m['positions_closed'] for m in self.strategy_metrics.values()),
            'total_pnl': sum(m['total_pnl'] for m in self.strategy_metrics.values()),
            'by_strategy': {}
        }
        
        # Add strategy-specific summaries
        for strategy_name, metrics in self.strategy_metrics.items():
            approval_rate = (
                metrics['signals_approved'] / metrics['signals_generated'] 
                if metrics['signals_generated'] > 0 else 0
            )
            
            summary['by_strategy'][strategy_name] = {
                'signals_generated': metrics['signals_generated'],
                'signals_approved': metrics['signals_approved'],
                'approval_rate': approval_rate,
                'positions_opened': metrics['positions_opened'],
                'positions_closed': metrics['positions_closed'],
                'total_pnl': metrics['total_pnl']
            }
        
        return summary
    
    def pause_orchestration(self) -> None:
        """Pause orchestration without closing positions"""
        with self._lock:
            self.state = OrchestratorState.PAUSED
            self.logger.info("Orchestrator paused")
    
    def resume_orchestration(self) -> None:
        """Resume orchestration"""
        with self._lock:
            if self.state == OrchestratorState.PAUSED:
                self.state = OrchestratorState.READY
                self.logger.info("Orchestrator resumed")
    
    def reset_daily_stats(self) -> None:
        """Reset daily statistics"""
        with self._lock:
            self.daily_trades = 0
            
            # Reset strategy daily stats
            for strategy in self.strategies.values():
                if hasattr(strategy, 'reset_daily_stats'):
                    strategy.reset_daily_stats()
            
            self.logger.info("Daily stats reset for all strategies")
    
    def update_capital_allocations(self, new_allocations: Dict[str, float]) -> bool:
        """
        Update capital allocations across strategies.
        
        Args:
            new_allocations: New allocation percentages by strategy
            
        Returns:
            bool: Success status
        """
        try:
            # Validate allocations sum to 1.0
            total = sum(new_allocations.values())
            if abs(total - 1.0) > 0.01:
                self.logger.error(f"Allocations must sum to 1.0, got {total}")
                return False
            
            # Validate all strategies exist
            for strategy in new_allocations:
                if strategy not in self.strategies:
                    self.logger.error(f"Unknown strategy: {strategy}")
                    return False
            
            with self._lock:
                self.capital_allocations = new_allocations.copy()
            
            self.logger.info(f"Updated capital allocations: {new_allocations}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating allocations: {e}")
            return False
    
    def get_strategy_details(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific strategy"""
        if strategy_name not in self.strategies:
            return None
        
        strategy = self.strategies[strategy_name]
        metrics = self.strategy_metrics[strategy_name]
        
        details = {
            'name': strategy_name,
            'enabled': True,
            'priority': STRATEGY_PRIORITIES.get(strategy_name, 50),
            'capital_allocation': self.capital_allocations.get(strategy_name, 0),
            'metrics': metrics,
            'performance_history': self.performance_history.get(strategy_name, [])[-20:],  # Last 20 entries
            'active_positions': sum(
                1 for p in self.active_positions.values() 
                if p['strategy'] == strategy_name and p['status'] == 'open'
            )
        }
        
        # Add strategy-specific metrics if available
        if hasattr(strategy, 'get_strategy_metrics'):
            details['strategy_metrics'] = strategy.get_strategy_metrics()
        
        return details
    
    def emergency_close_all_positions(self, reason: str = "emergency_shutdown") -> Dict[str, Any]:
        """
        Emergency close all positions across all strategies.
        
        Args:
            reason: Reason for emergency closure
            
        Returns:
            Summary of closed positions
        """
        self.logger.warning(f"Emergency close initiated: {reason}")
        
        summary = {
            'positions_closed': 0,
            'strategies_affected': [],
            'errors': []
        }
        
        try:
            with self._lock:
                # Pause orchestration
                self.pause_orchestration()
                
                # Close positions in each strategy
                for strategy_name, strategy in self.strategies.items():
                    try:
                        if hasattr(strategy, 'emergency_close_all'):
                            closed = strategy.emergency_close_all(reason)
                            summary['positions_closed'] += closed
                            summary['strategies_affected'].append(strategy_name)
                        elif hasattr(strategy, 'shutdown'):
                            strategy.shutdown()
                            summary['strategies_affected'].append(strategy_name)
                            
                    except Exception as e:
                        error_msg = f"Error closing {strategy_name} positions: {e}"
                        self.logger.error(error_msg)
                        summary['errors'].append(error_msg)
                
                # Clear active positions
                self.active_positions.clear()
                
                # Reset available capital
                self.available_capital = self.total_capital
            
            self.logger.info(
                f"Emergency close complete: {summary['positions_closed']} positions closed"
            )
            
        except Exception as e:
            self.logger.error(f"Error in emergency close: {e}")
            summary['errors'].append(str(e))
        
        return summary
    
    def shutdown(self) -> None:
        """Shutdown the orchestrator and all strategies"""
        try:
            self.logger.info("Shutting down strategy orchestrator")
            
            # Set state
            self.state = OrchestratorState.PAUSED
            
            # Shutdown each strategy
            for strategy_name, strategy in self.strategies.items():
                try:
                    if hasattr(strategy, 'shutdown'):
                        strategy.shutdown()
                    self.logger.info(f"Strategy {strategy_name} shutdown complete")
                except Exception as e:
                    self.logger.error(f"Error shutting down {strategy_name}: {e}")
            
            # Clear tracking
            self.active_positions.clear()
            self.pending_signals.clear()
            
            self.logger.info("Strategy orchestrator shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during orchestrator shutdown: {e}")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_strategy_orchestrator(config: Dict[str, Any]) -> StrategyOrchestrator:
    """
    Factory function to create Strategy Orchestrator instance.
    
    Args:
        config: Orchestrator configuration
        
    Returns:
        StrategyOrchestrator instance
    """
    return StrategyOrchestrator(config)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test the orchestrator
    test_config = {
        'total_capital': 100000,
        'allocations': {
            'IronCondor': 0.30,
            'IronButterfly': 0.25,
            'BullPutSpread': 0.20,
            'BearCallSpread': 0.15,
            'ZeroDTE': 0.10
        },
        'strategies': {
            'IronCondor': {'max_positions': 3},
            'IronButterfly': {'target_dte': 30},
            'BullPutSpread': {'delta_short': -0.30},
            'BearCallSpread': {'delta_short': 0.30},
            'ZeroDTE': {'max_trades_per_day': 5}
        }
    }
    
    # Create orchestrator
    orchestrator = create_strategy_orchestrator(test_config)
    
    # Create test market data
    test_market_data = {
        'last_price': 450.00,
        'prev_close': 448.50,
        'volume': 85000000,
        'bid': 449.95,
        'ask': 450.05,
        'vix': 18.5,
        'put_call_ratio': 1.1,
        'sma_10': 449.00,
        'sma_20': 447.50,
        'rsi': 55,
        'vwap': 449.80
    }
    
    # Get current status
    print("\nOrchestrator Status:")
    print("=" * 50)
    status = orchestrator.get_status()
    for key, value in status.items():
        if isinstance(value, dict):
            print(f"{key}:")
            for k, v in value.items():
                print(f"  {k}: {v}")
        else:
            print(f"{key}: {value}")
    
    # Run orchestration
    print("\nRunning Orchestration:")
    print("=" * 50)
    results = orchestrator.orchestrate(test_market_data)
    
    print(f"Timestamp: {results['timestamp']}")
    print(f"State: {results['state']}")
    print(f"Status: {results['status']}")
    
    if results['market_conditions']:
        conditions = results['market_conditions']
        print(f"\nMarket Conditions:")
        print(f"  Market Regime: {conditions.market_regime.name}")
        print(f"  Volatility Regime: {conditions.volatility_regime.name}")
        print(f"  Trend Strength: {conditions.trend_strength:.2%}")
        print(f"  Internals Score: {conditions.internals_score:.2f}")
    
    print(f"\nActive Strategies: {results['active_strategies']}")
    print(f"Signals Generated: {results['signals_generated']}")
    print(f"Signals Approved: {results['signals_approved']}")
    
    if results['execution_summary']:
        summary = results['execution_summary']
        print(f"\nExecution Summary:")
        print(f"  Positions Opened: {summary.get('positions_opened', 0)}")
        print(f"  Positions Closed: {summary.get('positions_closed', 0)}")
        print(f"  Capital Used: ${summary.get('capital_used', 0):.2f}")
    
    # Get performance summary
    print("\nPerformance Summary:")
    print("=" * 50)
    perf_summary = orchestrator.get_performance_summary()
    print(f"Total Signals Generated: {perf_summary['total_signals_generated']}")
    print(f"Total Signals Approved: {perf_summary['total_signals_approved']}")
    print(f"Total Positions Opened: {perf_summary['total_positions_opened']}")
    
    # Shutdown
    orchestrator.shutdown()
    print("\nOrchestrator shutdown complete")
        