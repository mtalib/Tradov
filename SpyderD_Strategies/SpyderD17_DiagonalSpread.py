#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD17_DiagonalSpread.py
Group: D (Trading Strategies)
Purpose: Diagonal Spread strategy with multi-timeframe approach and directional bias

Description:
    This module implements the Diagonal Spread strategy that combines options of
    the same type with different strike prices and expiration dates. The strategy
    profits from time decay, volatility changes, and directional movement through
    sophisticated bias management, delta-based strike selection, and advanced
    multi-timeframe optimization protocols.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-06-29
Last Updated: 2025-06-29 Time: 15:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
from typing import Dict, List, Tuple, Optional, Union, Any
from dataclasses import dataclass, field
from enum import Enum, auto
import uuid
import asyncio
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy, StrategySignal, PositionType
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU14_OptionStrategies import SpyderOptionStrategies, StrategyType, OptionStrategy, OptionRight
from SpyderU_Utilities.SpyderU07_Constants import (
    OptionType, OrderAction, OrderType, SignalType,
    DIAGONAL_SPREAD_PROFIT_TARGET, DIAGONAL_SPREAD_STOP_LOSS,
    MIN_IV_RANK_FOR_DIRECTIONAL_STRATEGIES, OPTIMAL_ENTRY_START, OPTIMAL_ENTRY_END
)
from SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager, RiskProfile
from SpyderE_Risk.SpyderE08_PositionGroupValidator import PositionGroupValidator
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event
from SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from SpyderF_Analysis.SpyderF08_VolatilityRegime import VolatilityRegimeAnalyzer
from SpyderF_Analysis.SpyderF04_VolatilityAnalysis import VolatilityAnalyzer
from SpyderF_Analysis.SpyderF05_TrendDetection import TrendDetector
from SpyderF_Analysis.SpyderF10_MarketRegimeDetector import MarketRegimeDetector
from SpyderB_Broker.SpyderB06_ContractBuilder import ContractBuilder
from SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
from SpyderU_Utilities.SpyderU13_TechnicalIndicators import TechnicalIndicators
from SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceMetrics
from SpyderC_MarketData.SpyderC10_VIXAnalyzer import VIXAnalyzer

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy-specific constants
DEFAULT_OPTION_TYPE = 'call'
DEFAULT_BIAS = 'bullish'
DEFAULT_SHORT_STRIKE_DELTA = 0.30
DEFAULT_LONG_STRIKE_DELTA = 0.40
DEFAULT_SHORT_TERM_DAYS = 30
DEFAULT_LONG_TERM_DAYS = 60
DEFAULT_PROFIT_TARGET_PERCENT = 0.30
DEFAULT_STOP_LOSS_PERCENT = 0.50
DEFAULT_IV_RANK_MIN = 30
DEFAULT_IV_RANK_MAX = 70
DEFAULT_POSITION_SIZE_PERCENT = 0.05

# Multi-timeframe management
MIN_TIME_SPREAD = 14  # Minimum days between expirations
MAX_TIME_SPREAD = 60  # Maximum days between expirations
OPTIMAL_TIME_SPREAD = 30  # Optimal time spread for theta decay
NEAR_EXPIRY_THRESHOLD = 5  # Days before short expiry to consider closure

# Trading windows
DIAGONAL_ENTRY_START = datetime.time(10, 30)
DIAGONAL_ENTRY_END = datetime.time(14, 30)
MAX_DAYS_HELD = 21
MIN_DAYS_TO_LONG_EXPIRY = 14

# Directional thresholds
BULLISH_DELTA_TARGET = 0.15  # Target net delta for bullish bias
BEARISH_DELTA_TARGET = -0.15  # Target net delta for bearish bias
NEUTRAL_DELTA_MAX = 0.10  # Maximum delta for neutral bias

# Risk thresholds
MAX_DIAGONAL_DELTA = 20.0  # Maximum delta per diagonal
MAX_DIAGONAL_GAMMA = 10.0  # Maximum gamma per diagonal
MAX_DIAGONAL_VEGA = 25.0   # Maximum vega per diagonal
MAX_DIAGONAL_THETA = -15.0  # Maximum theta decay per diagonal

# Price movement thresholds
BREAKOUT_THRESHOLD = 0.02  # 2% price movement
TREND_CONFIRMATION_BARS = 3  # Bars to confirm trend
VOLATILITY_EXPANSION_THRESHOLD = 0.15  # 15% IV increase

# ==============================================================================
# ENUMS
# ==============================================================================
class DiagonalSpreadState(Enum):
    """Diagonal Spread position states"""
    INACTIVE = "inactive"
    MONITORING = "monitoring"
    ACTIVE = "active"
    ROLLING = "rolling"
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"

class DiagonalType(Enum):
    """Types of diagonal spreads"""
    CALL_DIAGONAL = "call_diagonal"
    PUT_DIAGONAL = "put_diagonal"

class MarketBias(Enum):
    """Market bias for diagonal spreads"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"

class ExitReason(Enum):
    """Exit reasons for Diagonal Spread positions"""
    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    TIME_DECAY = "time_decay"
    SHORT_EXPIRATION = "short_expiration"
    TREND_REVERSAL = "trend_reversal"
    VOLATILITY_CRUSH = "volatility_crush"
    VOLATILITY_EXPANSION = "volatility_expansion"
    DELTA_RISK = "delta_risk"
    GAMMA_RISK = "gamma_risk"
    BREAKOUT_FAILURE = "breakout_failure"
    RISK_MANAGEMENT = "risk_management"

class TrendStrength(Enum):
    """Trend strength classification"""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class DiagonalLeg:
    """Individual diagonal spread leg data"""
    action: str  # 'BUY' or 'SELL'
    strike: float
    expiry: datetime.datetime
    option_type: str  # 'call' or 'put'
    delta: float
    current_value: float = 0.0
    entry_value: float = 0.0
    time_decay: float = 0.0
    greeks: Dict[str, float] = field(default_factory=dict)

@dataclass
class TrendAnalysis:
    """Trend analysis data"""
    direction: str  # 'bullish', 'bearish', 'neutral'
    strength: TrendStrength
    confidence: float
    momentum: float
    breakout_level: Optional[float]
    support_level: Optional[float]
    resistance_level: Optional[float]
    trend_duration: int  # days

@dataclass
class DiagonalSpreadPosition:
    """Diagonal Spread position data structure"""
    id: str
    entry_time: datetime.datetime
    diagonal_type: DiagonalType
    market_bias: MarketBias
    short_leg: DiagonalLeg
    long_leg: DiagonalLeg
    time_spread: int  # Days between expirations
    net_debit: float
    entry_iv: float
    entry_iv_rank: float
    entry_price: float
    entry_trend: TrendAnalysis
    current_pnl: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    time_decay_collected: float = 0.0
    state: DiagonalSpreadState = DiagonalSpreadState.ACTIVE
    exit_reason: Optional[ExitReason] = None
    portfolio_greeks: Dict[str, float] = field(default_factory=dict)
    current_trend: Optional[TrendAnalysis] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DiagonalSpreadMetrics:
    """Performance metrics for Diagonal Spread strategy"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    average_days_held: float = 0.0
    total_debit_paid: float = 0.0
    average_debit_per_trade: float = 0.0
    average_time_spread: float = 0.0
    time_decay_efficiency: float = 0.0
    trend_following_wins: int = 0
    volatility_expansion_wins: int = 0
    max_concurrent_positions: int = 0

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderD17_DiagonalSpread(BaseStrategy):
    """
    Diagonal Spread Strategy implementation for SPYDER.
    
    A Diagonal Spread involves buying and selling options of the same type but with
    different strike prices and expiration dates. This creates a position that profits
    from time decay, changes in implied volatility, and/or directional movement through
    sophisticated multi-timeframe optimization.
    
    Key Features:
    - Multi-timeframe approach combining different expiration cycles
    - Directional bias support (bullish, bearish, neutral)
    - Advanced strike selection using delta-based targeting
    - Trend analysis integration for optimal entry timing
    - Sophisticated time decay management across different expirations
    - Real-time Greeks monitoring and risk management
    - Volatility regime-aware position sizing
    - Professional rolling and adjustment capabilities
    
    Strategy Profiles:
    - Bullish Call Diagonal: Long further OTM/longer-term call + Short nearer OTM/shorter-term call
    - Bearish Call Diagonal: Long nearer ITM/longer-term call + Short further ITM/shorter-term call
    - Bullish Put Diagonal: Long further ITM/longer-term put + Short nearer ITM/shorter-term put
    - Bearish Put Diagonal: Long further OTM/longer-term put + Short nearer OTM/shorter-term put
    
    Risk Profile:
    - Limited risk (net debit paid)
    - Moderate to high reward potential
    - Time decay advantage when properly structured
    - Volatility expansion benefit from long-term leg
    
    Attributes:
        name: Strategy name
        strategy_type: Strategy type identifier
        positions: Current Diagonal Spread positions
        metrics: Performance tracking metrics
        state: Current strategy state
        
    Example:
        >>> config = {'bias': 'bullish', 'option_type': 'call', 'time_spread': 30}
        >>> strategy = SpyderD17_DiagonalSpread(config)
        >>> signals = strategy.generate_signals(market_data)
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize Diagonal Spread strategy.
        
        Args:
            config: Strategy configuration parameters
        """
        super().__init__(
            name="Diagonal Spread",
            strategy_type="diagonal_spread",
            config=config or {}
        )
        
        # SPYDER component initialization
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()
        self.risk_manager = get_risk_manager()
        
        # Strategy-specific components
        self.greeks_calculator = GreeksCalculator()
        self.volatility_analyzer = VolatilityAnalyzer()
        self.volatility_regime_analyzer = VolatilityRegimeAnalyzer()
        self.trend_detector = TrendDetector()
        self.market_regime_detector = MarketRegimeDetector()
        self.position_validator = PositionGroupValidator()
        self.contract_builder = ContractBuilder()
        self.datetime_utils = DateTimeUtils()
        self.technical_indicators = TechnicalIndicators()
        self.performance_metrics = PerformanceMetrics()
        self.vix_analyzer = VIXAnalyzer()
        
        # Default parameters
        self.default_params = {
            'option_type': DEFAULT_OPTION_TYPE,
            'bias': DEFAULT_BIAS,
            'short_strike_delta': DEFAULT_SHORT_STRIKE_DELTA,
            'long_strike_delta': DEFAULT_LONG_STRIKE_DELTA,
            'short_term_days': DEFAULT_SHORT_TERM_DAYS,
            'long_term_days': DEFAULT_LONG_TERM_DAYS,
            'entry_day': 'monday',
            'entry_time_start': DIAGONAL_ENTRY_START,
            'entry_time_end': DIAGONAL_ENTRY_END,
            'max_days_held': MAX_DAYS_HELD,
            'profit_target_percent': DEFAULT_PROFIT_TARGET_PERCENT,
            'stop_loss_percent': DEFAULT_STOP_LOSS_PERCENT,
            'iv_rank_min': DEFAULT_IV_RANK_MIN,
            'iv_rank_max': DEFAULT_IV_RANK_MAX,
            'position_size_percent': DEFAULT_POSITION_SIZE_PERCENT,
            'max_concurrent_positions': 3,
            'min_time_spread': MIN_TIME_SPREAD,
            'max_time_spread': MAX_TIME_SPREAD,
            'optimal_time_spread': OPTIMAL_TIME_SPREAD,
            'delta_threshold': MAX_DIAGONAL_DELTA,
            'gamma_threshold': MAX_DIAGONAL_GAMMA,
            'vega_threshold': MAX_DIAGONAL_VEGA,
            'theta_threshold': MAX_DIAGONAL_THETA,
            'trend_confirmation_required': True,
            'volatility_expansion_exit': True,
            'is_active': True
        }
        
        # Update with provided configuration
        self.params = {**self.default_params, **self.config}
        
        # Initialize strategy state
        self.positions: List[DiagonalSpreadPosition] = []
        self.metrics = DiagonalSpreadMetrics()
        self.state = DiagonalSpreadState.INACTIVE
        
        # Performance tracking
        self.trade_history: List[Dict[str, Any]] = []
        self.daily_pnl: float = 0.0
        self.total_exposure: float = 0.0
        self.time_decay_today: float = 0.0
        
        # Trend and market analysis
        self.current_market_trend: Optional[TrendAnalysis] = None
        self.trend_history: List[TrendAnalysis] = []
        
        self.logger.info(f"Initialized {self.name} strategy with parameters: {self.params}")
        self._emit_strategy_event('strategy_initialized', {'params': self.params})
        
    # ==========================================================================
    # SIGNAL GENERATION METHODS
    # ==========================================================================
    def generate_signals(self, market_data: Dict[str, Any]) -> List[StrategySignal]:
        """
        Generate trading signals based on market conditions.
        
        Args:
            market_data: Current market data including price, IV, Greeks, etc.
            
        Returns:
            List of strategy signals
        """
        signals = []
        
        try:
            # Check if strategy is active
            if not self.params['is_active']:
                return signals
            
            # Validate market data
            if not self._validate_market_data(market_data):
                self.logger.warning("Invalid market data received")
                return signals
            
            # Update trend analysis
            self._update_trend_analysis(market_data)
            
            # Check entry conditions
            if self._check_entry_conditions(market_data):
                signal = self._generate_entry_signal(market_data)
                if signal:
                    signals.append(signal)
            
            # Check exit conditions for existing positions
            exit_signals = self._check_exit_conditions(market_data)
            signals.extend(exit_signals)
            
            # Check rolling opportunities
            rolling_signals = self._check_rolling_opportunities(market_data)
            signals.extend(rolling_signals)
            
            # Update position monitoring
            self._update_position_monitoring(market_data)
            
            # Update time decay tracking
            self._update_time_decay_metrics(market_data)
            
            return signals
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'generate_signals',
                'strategy': self.name,
                'market_data_keys': list(market_data.keys()) if market_data else []
            })
            return []
    
    def _check_entry_conditions(self, market_data: Dict[str, Any]) -> bool:
        """
        Check if entry conditions are met for Diagonal Spread strategy.
        
        Args:
            market_data: Current market data
            
        Returns:
            Whether entry conditions are satisfied
        """
        try:
            # Check maximum concurrent positions
            if len(self.positions) >= self.params['max_concurrent_positions']:
                self.logger.debug("Maximum concurrent positions reached")
                return False
            
            # Check day of week
            current_day = market_data.get('current_day_of_week', '').lower()
            entry_day = self.params.get('entry_day', 'any')
            if entry_day != 'any' and current_day != entry_day:
                self.logger.debug(f"Entry day mismatch: {current_day} != {entry_day}")
                return False
            
            # Check time of day
            current_time = market_data.get('current_time')
            if current_time:
                if isinstance(current_time, str):
                    current_time = datetime.datetime.strptime(current_time, '%H:%M').time()
                
                if not (self.params['entry_time_start'] <= current_time <= self.params['entry_time_end']):
                    self.logger.debug(f"Outside entry time window: {current_time}")
                    return False
            
            # Check IV rank (diagonal spreads work in various IV environments)
            iv_rank = market_data.get('iv_rank', 0)
            if not (self.params['iv_rank_min'] <= iv_rank <= self.params['iv_rank_max']):
                self.logger.debug(f"IV rank outside range: {iv_rank}")
                return False
            
            # Check trend confirmation if required
            if self.params['trend_confirmation_required']:
                if not self._is_trend_confirmed(market_data):
                    self.logger.debug("Trend not confirmed for diagonal entry")
                    return False
            
            # Check market regime
            if not self._is_favorable_market_regime(market_data):
                self.logger.debug("Unfavorable market regime for diagonals")
                return False
            
            # Check volatility environment
            if not self._is_favorable_volatility_environment(market_data):
                self.logger.debug("Unfavorable volatility environment")
                return False
            
            # Check available expiration dates
            if not self._validate_expiration_availability(market_data):
                self.logger.debug("Required expiration dates not available")
                return False
            
            # Check available capital
            required_capital = self._calculate_required_capital(market_data)
            if not self.risk_manager.check_capital_available(required_capital):
                self.logger.debug("Insufficient capital available")
                return False
            
            # Check strategy exposure limits
            if not self.risk_manager.check_strategy_exposure(
                self.strategy_type, 
                required_capital
            ):
                self.logger.debug("Strategy exposure limit reached")
                return False
            
            self.logger.info("✅ All entry conditions met for Diagonal Spread")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_check_entry_conditions',
                'market_data': market_data
            })
            return False
    
    def _generate_entry_signal(self, market_data: Dict[str, Any]) -> Optional[StrategySignal]:
        """
        Generate entry signal for Diagonal Spread strategy.
        
        Args:
            market_data: Current market data
            
        Returns:
            Strategy signal or None if generation fails
        """
        try:
            # Determine diagonal configuration
            diagonal_config = self._determine_diagonal_configuration(market_data)
            if not diagonal_config:
                return None
            
            option_type, bias, short_strike, long_strike, short_expiry, long_expiry = diagonal_config
            
            # Calculate position size
            position_size = self._calculate_position_size(market_data)
            if position_size <= 0:
                return None
            
            # Create diagonal spread strategy using SPYDER's OptionStrategies
            option_strategy = self._create_diagonal_spread_strategy(
                market_data['underlying_symbol'],
                option_type,
                short_strike,
                long_strike,
                short_expiry,
                long_expiry,
                position_size
            )
            
            # Validate strategy positions
            if not self._validate_strategy_positions(option_strategy):
                return None
            
            # Calculate expected metrics
            metrics = self._calculate_strategy_metrics(
                market_data, option_type, short_strike, long_strike, 
                short_expiry, long_expiry, position_size
            )
            
            # Create strategy signal
            signal = StrategySignal(
                strategy_id=self.id,
                strategy_name=self.name,
                signal_type=SignalType.ENTRY,
                timestamp=datetime.datetime.now(),
                underlying_symbol=market_data['underlying_symbol'],
                option_strategy=option_strategy,
                confidence=self._calculate_signal_confidence(market_data),
                expected_profit=metrics.get('expected_profit', 0),
                max_risk=metrics.get('max_risk', 0),
                probability_of_profit=metrics.get('pop', 0),
                metadata={
                    'option_type': option_type,
                    'bias': bias,
                    'short_strike': short_strike,
                    'long_strike': long_strike,
                    'short_expiry': short_expiry,
                    'long_expiry': long_expiry,
                    'time_spread': (long_expiry - short_expiry).days,
                    'net_debit': metrics.get('net_debit', 0),
                    'target_delta': metrics.get('target_delta', 0),
                    'trend_analysis': self.current_market_trend.__dict__ if self.current_market_trend else None,
                    'iv_rank': market_data.get('iv_rank'),
                    'entry_criteria': self._get_entry_criteria_summary(market_data)
                }
            )
            
            self.logger.info(f"Generated Diagonal Spread entry signal: {option_type.upper()} {bias} {short_strike}/{long_strike}")
            self._emit_strategy_event('entry_signal_generated', signal.__dict__)
            
            return signal
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_generate_entry_signal',
                'market_data': market_data
            })
            return None
    
    # ==========================================================================
    # TREND ANALYSIS AND MARKET REGIME DETECTION
    # ==========================================================================
    def _update_trend_analysis(self, market_data: Dict[str, Any]) -> None:
        """
        Update current trend analysis using SPYDER's trend detector.
        
        Args:
            market_data: Current market data
        """
        try:
            # Use SPYDER's trend detector
            trend_data = self.trend_detector.analyze_trend(market_data)
            
            # Convert to our internal format
            self.current_market_trend = TrendAnalysis(
                direction=trend_data.get('direction', 'neutral'),
                strength=TrendStrength(trend_data.get('strength', 'moderate')),
                confidence=trend_data.get('confidence', 0.5),
                momentum=trend_data.get('momentum', 0),
                breakout_level=trend_data.get('breakout_level'),
                support_level=trend_data.get('support_level'),
                resistance_level=trend_data.get('resistance_level'),
                trend_duration=trend_data.get('duration_days', 0)
            )
            
            # Add to trend history
            self.trend_history.append(self.current_market_trend)
            
            # Keep only recent history
            if len(self.trend_history) > 20:
                self.trend_history = self.trend_history[-20:]
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_trend_analysis'
            })
    
    def _is_trend_confirmed(self, market_data: Dict[str, Any]) -> bool:
        """
        Check if current trend is confirmed for diagonal entry.
        
        Args:
            market_data: Current market data
            
        Returns:
            Whether trend is confirmed
        """
        try:
            if not self.current_market_trend:
                return False
            
            # Check trend strength and confidence
            if (self.current_market_trend.strength in [TrendStrength.MODERATE, TrendStrength.STRONG, TrendStrength.VERY_STRONG] 
                and self.current_market_trend.confidence >= 0.6):
                return True
            
            # Check trend duration
            if self.current_market_trend.trend_duration >= TREND_CONFIRMATION_BARS:
                return True
            
            return False
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_is_trend_confirmed'
            })
            return False
    
    def _is_favorable_market_regime(self, market_data: Dict[str, Any]) -> bool:
        """
        Check if current market regime is favorable for diagonal spreads.
        
        Args:
            market_data: Current market data
            
        Returns:
            Whether market regime is favorable
        """
        try:
            # Use market regime detector
            market_regime = self.market_regime_detector.detect_regime(market_data)
            
            # Diagonal spreads work well in trending and moderate volatility environments
            favorable_regimes = ['trending', 'breakout', 'moderate_volatility']
            
            return market_regime.regime_type in favorable_regimes
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_is_favorable_market_regime'
            })
            return True
    
    def _is_favorable_volatility_environment(self, market_data: Dict[str, Any]) -> bool:
        """
        Check if volatility environment is favorable for diagonal spreads.
        
        Args:
            market_data: Current market data
            
        Returns:
            Whether volatility environment is favorable
        """
        try:
            iv_rank = market_data.get('iv_rank', 50)
            
            # Diagonal spreads work in various IV environments but prefer moderate levels
            if 30 <= iv_rank <= 70:
                return True
            
            # Also check IV trend
            iv_trend = market_data.get('iv_trend', 'neutral')
            if iv_trend in ['rising', 'stable'] and iv_rank >= 25:
                return True
            
            return False
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_is_favorable_volatility_environment'
            })
            return True
    
    # ==========================================================================
    # DIAGONAL CONFIGURATION AND STRIKE SELECTION
    # ==========================================================================
    def _determine_diagonal_configuration(self, market_data: Dict[str, Any]) -> Optional[Tuple[str, str, float, float, datetime.datetime, datetime.datetime]]:
        """
        Determine optimal diagonal spread configuration based on market conditions.
        
        Args:
            market_data: Current market data
            
        Returns:
            Tuple of (option_type, bias, short_strike, long_strike, short_expiry, long_expiry) or None
        """
        try:
            underlying_price = market_data.get('underlying_price', 0)
            if underlying_price <= 0:
                return None
            
            # Get configuration from parameters
            option_type = self.params['option_type']
            bias = self.params['bias']
            
            # Auto-detect bias from trend if needed
            if bias == 'auto' and self.current_market_trend:
                if self.current_market_trend.direction == 'bullish':
                    bias = 'bullish'
                elif self.current_market_trend.direction == 'bearish':
                    bias = 'bearish'
                else:
                    bias = 'neutral'
            
            # Get expiration dates
            short_expiry, long_expiry = self._get_target_expirations(market_data)
            if not short_expiry or not long_expiry:
                return None
            
            # Calculate strikes based on bias and option type
            short_strike, long_strike = self._calculate_diagonal_strikes(
                underlying_price, market_data, option_type, bias
            )
            
            if not short_strike or not long_strike:
                return None
            
            # Validate configuration
            if not self._validate_diagonal_configuration(
                option_type, bias, short_strike, long_strike, underlying_price
            ):
                return None
            
            return option_type, bias, short_strike, long_strike, short_expiry, long_expiry
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_determine_diagonal_configuration'
            })
            return None
    
       
     
    def _calculate_diagonal_strikes(self, underlying_price: float, market_data: Dict[str, Any],
                                  option_type: str, bias: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate strike prices for diagonal spread based on bias and option type.
        
        Args:
            underlying_price: Current underlying price
            market_data: Current market data
            option_type: 'call' or 'put'
            bias: 'bullish', 'bearish', or 'neutral'
            
        Returns:
            Tuple of (short_strike, long_strike) or (None, None)
        """
        try:
            iv = market_data.get('iv', 0.2)
            short_days = self.params['short_term_days']
            long_days = self.params['long_term_days']
            
            short_delta = self.params['short_strike_delta']
            long_delta = self.params['long_strike_delta']
            
            # Adjust deltas based on option type and bias
            if option_type == 'call':
                if bias == 'bullish':
                    # Bullish call diagonal: short OTM call, long further OTM call (longer term)
                    short_delta = abs(short_delta)
                    long_delta = abs(long_delta)
                elif bias == 'bearish':
                    # Bearish call diagonal: short ITM call, long further ITM call (longer term)
                    short_delta = 1 - abs(short_delta)
                    long_delta = 1 - abs(long_delta)
                else:  # neutral
                    # Neutral call diagonal: short slightly OTM, long further OTM
                    short_delta = abs(short_delta) * 0.8
                    long_delta = abs(long_delta) * 0.8
            else:  # put
                if bias == 'bullish':
                    # Bullish put diagonal: short ITM put, long further ITM put (longer term)
                    short_delta = -(1 - abs(short_delta))
                    long_delta = -(1 - abs(long_delta))
                elif bias == 'bearish':
                    # Bearish put diagonal: short OTM put, long further OTM put (longer term)
                    short_delta = -abs(short_delta)
                    long_delta = -abs(long_delta)
                else:  # neutral
                    # Neutral put diagonal: short slightly OTM, long further OTM
                    short_delta = -abs(short_delta) * 0.8
                    long_delta = -abs(long_delta) * 0.8
            
            # Calculate strikes using delta targeting
            short_strike = self._get_strike_by_delta(
                underlying_price, short_days, short_delta, option_type, iv
            )
            
            long_strike = self._get_strike_by_delta(
                underlying_price, long_days, long_delta, option_type, iv
            )
            
            # Round to available strikes
            available_strikes = market_data.get('available_strikes', [])
            if available_strikes:
                short_strike = self._round_to_available_strike(short_strike, available_strikes)
                long_strike = self._round_to_available_strike(long_strike, available_strikes)
            
            return short_strike, long_strike
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_calculate_diagonal_strikes'
            })
            return None, None
    
    def _validate_diagonal_configuration(self, option_type: str, bias: str,
                                       short_strike: float, long_strike: float,
                                       underlying_price: float) -> bool:
        """
        Validate diagonal spread configuration.
        
        Args:
            option_type: 'call' or 'put'
            bias: Market bias
            short_strike: Short strike price
            long_strike: Long strike price
            underlying_price: Current underlying price
            
        Returns:
            Whether configuration is valid
        """
        try:
            # Check minimum strike separation
            strike_separation = abs(long_strike - short_strike)
            min_separation = underlying_price * 0.01  # Minimum 1% separation
            
            if strike_separation < min_separation:
                self.logger.warning(f"Strike separation too narrow: {strike_separation}")
                return False
            
            # Check maximum strike separation
            max_separation = underlying_price * 0.20  # Maximum 20% separation
            if strike_separation > max_separation:
                self.logger.warning(f"Strike separation too wide: {strike_separation}")
                return False
            
            # Check strike relationships based on diagonal type
            if option_type == 'call':
                if bias == 'bullish':
                    # For bullish call diagonal, long strike should be higher than short
                    if long_strike <= short_strike:
                        self.logger.warning("Bullish call diagonal: long strike should be higher")
                        return False
                elif bias == 'bearish':
                    # For bearish call diagonal, long strike should be lower than short
                    if long_strike >= short_strike:
                        self.logger.warning("Bearish call diagonal: long strike should be lower")
                        return False
            else:  # put
                if bias == 'bullish':
                    # For bullish put diagonal, long strike should be higher than short
                    if long_strike <= short_strike:
                        self.logger.warning("Bullish put diagonal: long strike should be higher")
                        return False
                elif bias == 'bearish':
                    # For bearish put diagonal, long strike should be lower than short
                    if long_strike >= short_strike:
                        self.logger.warning("Bearish put diagonal: long strike should be lower")
                        return False
            
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_validate_diagonal_configuration'
            })
            return False
    
    def _get_target_expirations(self, market_data: Dict[str, Any]) -> Tuple[Optional[datetime.datetime], Optional[datetime.datetime]]:
        """
        Get target expiration dates for short and long legs.
        
        Args:
            market_data: Current market data
            
        Returns:
            Tuple of (short_expiry, long_expiry) or (None, None)
        """
        try:
            expiration_dates = market_data.get('expiration_dates', {})
            
            # Get short expiration
            short_days_str = str(self.params['short_term_days'])
            short_expiry = expiration_dates.get(short_days_str)
            
            # Get long expiration
            long_days_str = str(self.params['long_term_days'])
            long_expiry = expiration_dates.get(long_days_str)
            
            # If exact dates not available, find closest
            if not short_expiry or not long_expiry:
                available_days = [int(k) for k in expiration_dates.keys() if k.isdigit()]
                
                if not short_expiry and available_days:
                    closest_short = min(available_days,
                                      key=lambda x: abs(x - self.params['short_term_days']))
                    short_expiry = expiration_dates[str(closest_short)]
                
                if not long_expiry and available_days:
                    closest_long = min(available_days,
                                     key=lambda x: abs(x - self.params['long_term_days']))
                    long_expiry = expiration_dates[str(closest_long)]
            
            # Validate time spread
            if short_expiry and long_expiry:
                time_spread = (long_expiry - short_expiry).days
                if not (self.params['min_time_spread'] <= time_spread <= self.params['max_time_spread']):
                    self.logger.warning(f"Time spread outside acceptable range: {time_spread} days")
                    return None, None
            
            return short_expiry, long_expiry
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_get_target_expirations'
            })
            return None, None
    
    # ==========================================================================
    # POSITION MANAGEMENT AND MONITORING
    # ==========================================================================
    def _check_exit_conditions(self, market_data: Dict[str, Any]) -> List[StrategySignal]:
        """
        Check exit conditions for existing positions.
        
        Args:
            market_data: Current market data
            
        Returns:
            List of exit signals
        """
        exit_signals = []
        
        for position in self.positions.copy():
            exit_reason = self._should_exit_position(position, market_data)
            if exit_reason:
                exit_signal = self._generate_exit_signal(position, market_data, exit_reason)
                if exit_signal:
                    exit_signals.append(exit_signal)
        
        return exit_signals
    
    def _should_exit_position(self, position: DiagonalSpreadPosition,
                            market_data: Dict[str, Any]) -> Optional[ExitReason]:
        """
        Determine if position should be exited and why.
        
        Args:
            position: Current position
            market_data: Current market data
            
        Returns:
            Exit reason or None if position should be held
        """
        try:
            # Update position data
            self._update_position_pnl(position, market_data)
            self._update_position_greeks(position, market_data)
            self._update_position_trend_analysis(position, market_data)
            
            # Check profit target
            profit_target = position.net_debit * self.params['profit_target_percent']
            if position.current_pnl >= profit_target:
                return ExitReason.PROFIT_TARGET
            
            # Check stop loss
            stop_loss = position.net_debit * self.params['stop_loss_percent']
            if position.current_pnl <= -stop_loss:
                return ExitReason.STOP_LOSS
            
            # Check time-based exit
            days_held = (datetime.datetime.now() - position.entry_time).days
            if days_held >= self.params['max_days_held']:
                return ExitReason.TIME_DECAY
            
            # Check short expiration approach
            days_to_short_exp = (position.short_leg.expiry - datetime.datetime.now()).days
            if days_to_short_exp <= NEAR_EXPIRY_THRESHOLD:
                return ExitReason.SHORT_EXPIRATION
            
            # Check trend reversal
            trend_reversal = self._check_trend_reversal(position, market_data)
            if trend_reversal:
                return ExitReason.TREND_REVERSAL
            
            # Check volatility changes
            volatility_exit = self._check_volatility_exit_conditions(position, market_data)
            if volatility_exit:
                return volatility_exit
            
            # Check Greeks risk thresholds
            greeks_risk = self._check_position_greeks_risk(position)
            if greeks_risk:
                return greeks_risk
            
            # Check breakout failure (for trend-following diagonals)
            breakout_failure = self._check_breakout_failure(position, market_data)
            if breakout_failure:
                return ExitReason.BREAKOUT_FAILURE
            
            return None
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_should_exit_position',
                'position_id': position.id
            })
            return ExitReason.RISK_MANAGEMENT
    
    def _check_trend_reversal(self, position: DiagonalSpreadPosition,
                            market_data: Dict[str, Any]) -> bool:
        """
        Check if trend has reversed against the position.
        
        Args:
            position: Position to check
            market_data: Current market data
            
        Returns:
            Whether trend reversal detected
        """
        try:
            if not self.current_market_trend or not position.entry_trend:
                return False
            
            # Check for significant trend direction change
            entry_direction = position.entry_trend.direction
            current_direction = self.current_market_trend.direction
            
            # Detect reversal
            if ((entry_direction == 'bullish' and current_direction == 'bearish') or
                (entry_direction == 'bearish' and current_direction == 'bullish')):
                
                # Confirm reversal strength
                if (self.current_market_trend.strength in [TrendStrength.MODERATE, TrendStrength.STRONG] and
                    self.current_market_trend.confidence >= 0.6):
                    
                    self._emit_strategy_event('trend_reversal_detected', {
                        'position_id': position.id,
                        'entry_trend': entry_direction,
                        'current_trend': current_direction,
                        'trend_strength': self.current_market_trend.strength.value,
                        'confidence': self.current_market_trend.confidence
                    })
                    return True
            
            return False
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_check_trend_reversal'
            })
            return False
    
    def _check_volatility_exit_conditions(self, position: DiagonalSpreadPosition,
                                        market_data: Dict[str, Any]) -> Optional[ExitReason]:
        """
        Check volatility-based exit conditions.
        
        Args:
            position: Position to check
            market_data: Current market data
            
        Returns:
            Exit reason if volatility condition met, None otherwise
        """
        try:
            current_iv = market_data.get('iv', 0)
            if current_iv <= 0 or position.entry_iv <= 0:
                return None
            
            iv_change = (current_iv - position.entry_iv) / position.entry_iv
            
            # Check for volatility crush
            if iv_change < -0.25:  # 25% IV crush
                return ExitReason.VOLATILITY_CRUSH
            
            # Check for significant volatility expansion (may benefit diagonal)
            if (self.params['volatility_expansion_exit'] and 
                iv_change > VOLATILITY_EXPANSION_THRESHOLD and
                position.current_pnl > position.net_debit * 0.20):  # 20% profit
                return ExitReason.VOLATILITY_EXPANSION
            
            return None
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_check_volatility_exit_conditions'
            })
            return None
    
    def _check_position_greeks_risk(self, position: DiagonalSpreadPosition) -> Optional[ExitReason]:
        """
        Check if position exceeds Greeks risk thresholds.
        
        Args:
            position: Position to check
            
        Returns:
            Exit reason if risk threshold exceeded, None otherwise
        """
        try:
            greeks = position.portfolio_greeks
            
            # Check delta risk
            if abs(greeks.get('delta', 0)) > self.params['delta_threshold']:
                self._emit_strategy_event('delta_risk_warning', {
                    'position_id': position.id,
                    'delta': greeks.get('delta', 0),
                    'threshold': self.params['delta_threshold']
                })
                return ExitReason.DELTA_RISK
            
            # Check gamma risk
            if abs(greeks.get('gamma', 0)) > self.params['gamma_threshold']:
                self._emit_strategy_event('gamma_risk_warning', {
                    'position_id': position.id,
                    'gamma': greeks.get('gamma', 0),
                    'threshold': self.params['gamma_threshold']
                })
                return ExitReason.GAMMA_RISK
            
            return None
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_check_position_greeks_risk'
            })
            return ExitReason.RISK_MANAGEMENT
    
    def _check_breakout_failure(self, position: DiagonalSpreadPosition,
                              market_data: Dict[str, Any]) -> bool:
        """
        Check if expected breakout has failed.
        
        Args:
            position: Position to check
            market_data: Current market data
            
        Returns:
            Whether breakout failure detected
        """
        try:
            if not position.entry_trend or not position.entry_trend.breakout_level:
                return False
            
            underlying_price = market_data.get('underlying_price', 0)
            breakout_level = position.entry_trend.breakout_level
            
            # Check how long since entry
            days_since_entry = (datetime.datetime.now() - position.entry_time).days
            
            # If position was expecting breakout but price hasn't moved sufficiently
            if days_since_entry >= 5:  # Give 5 days for breakout to develop
                expected_move = abs(underlying_price - breakout_level) / breakout_level
                
                if expected_move < BREAKOUT_THRESHOLD:  # Less than 2% move
                    return True
            
            return False
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_check_breakout_failure'
            })
            return False
    
    # ==========================================================================
    # ROLLING OPPORTUNITIES
    # ==========================================================================
    def _check_rolling_opportunities(self, market_data: Dict[str, Any]) -> List[StrategySignal]:
        """
        Check for rolling opportunities on existing positions.
        
        Args:
            market_data: Current market data
            
        Returns:
            List of rolling signals
        """
        rolling_signals = []
        
        for position in self.positions:
            try:
                # Check if position is eligible for rolling
                if self._is_rolling_eligible(position, market_data):
                    rolling_signal = self._generate_rolling_signal(position, market_data)
                    if rolling_signal:
                        rolling_signals.append(rolling_signal)
            
            except Exception as e:
                self.error_handler.handle_error(e, {
                    'method': '_check_rolling_opportunities',
                    'position_id': position.id
                })
        
        return rolling_signals
    
    def _is_rolling_eligible(self, position: DiagonalSpreadPosition,
                           market_data: Dict[str, Any]) -> bool:
        """
        Check if position is eligible for rolling.
        
        Args:
            position: Position to check
            market_data: Current market data
            
        Returns:
            Whether position is eligible for rolling
        """
        try:
            # Check days to short expiration
            days_to_short_exp = (position.short_leg.expiry - datetime.datetime.now()).days
            
            # Rolling typically done 7-10 days before short expiration
            if not (7 <= days_to_short_exp <= 10):
                return False
            
            # Check if position is profitable or near breakeven
            if position.current_pnl < -position.net_debit * 0.3:  # More than 30% loss
                return False
            
            # Check if long leg still has sufficient time
            days_to_long_exp = (position.long_leg.expiry - datetime.datetime.now()).days
            if days_to_long_exp < MIN_DAYS_TO_LONG_EXPIRY:
                return False
            
            # Check market conditions are still favorable
            if not self._is_favorable_market_regime(market_data):
                return False
            
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_is_rolling_eligible'
            })
            return False
    
    def _generate_rolling_signal(self, position: DiagonalSpreadPosition,
                               market_data: Dict[str, Any]) -> Optional[StrategySignal]:
        """
        Generate rolling signal for position.
        
        Args:
            position: Position to roll
            market_data: Current market data
            
        Returns:
            Rolling signal or None
        """
        try:
            # Calculate new short strike and expiration
            new_short_strike, new_short_expiry = self._calculate_rolling_parameters(
                position, market_data
            )
            
            if not new_short_strike or not new_short_expiry:
                return None
            
            # Create rolling strategy
            rolling_strategy = self._create_rolling_strategy(
                position, new_short_strike, new_short_expiry, market_data
            )
            
            # Create rolling signal
            signal = StrategySignal(
                strategy_id=self.id,
                strategy_name=self.name,
                signal_type=SignalType.ADJUSTMENT,  # Rolling is an adjustment
                timestamp=datetime.datetime.now(),
                underlying_symbol=market_data['underlying_symbol'],
                option_strategy=rolling_strategy,
                confidence=0.8,  # High confidence for rolling
                expected_profit=0,  # Rolling typically extends time
                max_risk=0,  # Adjusting existing position
                probability_of_profit=0.7,  # Rolling generally improves PoP
                metadata={
                    'position_id': position.id,
                    'action_type': 'roll',
                    'old_short_strike': position.short_leg.strike,
                    'new_short_strike': new_short_strike,
                    'old_short_expiry': position.short_leg.expiry,
                    'new_short_expiry': new_short_expiry,
                    'days_to_old_expiry': (position.short_leg.expiry - datetime.datetime.now()).days
                }
            )
            
            self.logger.info(f"Generated rolling signal for position {position.id}")
            self._emit_strategy_event('rolling_signal_generated', {
                'position_id': position.id,
                'new_short_strike': new_short_strike,
                'new_short_expiry': new_short_expiry
            })
            
            return signal
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_generate_rolling_signal',
                'position_id': position.id
            })
            return None
    
    # ==========================================================================
    # CALCULATION AND UTILITY METHODS
    # ==========================================================================
    def _calculate_required_capital(self, market_data: Dict[str, Any]) -> float:
        """
        Calculate required capital for Diagonal Spread strategy.
        
        Args:
            market_data: Current market data
            
        Returns:
            Required capital amount
        """
        try:
            underlying_price = market_data.get('underlying_price', 0)
            if underlying_price <= 0:
                return 0
            
            # For diagonal spread, required capital is the net debit (cost of the spread)
            estimated_cost_per_contract = underlying_price * 0.06  # Estimate 6% of underlying
            
            # Calculate position size
            position_size = self._calculate_position_size(market_data)
            
            # Total capital required
            required_capital = estimated_cost_per_contract * position_size * 100  # 100 shares per contract
            
            return required_capital
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_calculate_required_capital'
            })
            return 0
    
    def _calculate_position_size(self, market_data: Dict[str, Any]) -> int:
        """
        Calculate appropriate position size.
        
        Args:
            market_data: Current market data
            
        Returns:
            Position size in contracts
        """
        try:
            account_value = market_data.get('account_value', 0)
            underlying_price = market_data.get('underlying_price', 0)
            
            if account_value <= 0 or underlying_price <= 0:
                return 0
            
            # Calculate based on percentage of account
            target_investment = account_value * self.params['position_size_percent']
            contracts = int(target_investment / (underlying_price * 100))
            
            return max(1, contracts)  # Minimum 1 contract
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_calculate_position_size'
            })
            return 0
    
    def _calculate_strategy_metrics(self, market_data: Dict[str, Any], option_type: str,
                                  short_strike: float, long_strike: float,
                                  short_expiry: datetime.datetime, long_expiry: datetime.datetime,
                                  position_size: int) -> Dict[str, float]:
        """
        Calculate strategy metrics for entry signal.
        
        Args:
            market_data: Current market data
            option_type: 'call' or 'put'
            short_strike: Short strike price
            long_strike: Long strike price
            short_expiry: Short expiration date
            long_expiry: Long expiration date
            position_size: Position size
            
        Returns:
            Strategy metrics dictionary
        """
        try:
            underlying_price = market_data.get('underlying_price', 0)
            iv = market_data.get('iv', 0.2)
            
            # Estimate option premiums
            short_premium = self._estimate_option_premium(
                underlying_price, short_strike, 
                (short_expiry - datetime.datetime.now()).days, iv, option_type
            )
            long_premium = self._estimate_option_premium(
                underlying_price, long_strike,
                (long_expiry - datetime.datetime.now()).days, iv, option_type
            )
            
            # Net debit (cost of diagonal)
            net_debit_per_contract = long_premium - short_premium
            total_net_debit = net_debit_per_contract * position_size * 100
            
            # Estimate max profit (varies by diagonal type)
            strike_diff = abs(long_strike - short_strike)
            max_profit_per_contract = min(strike_diff, net_debit_per_contract * 2)
            total_max_profit = max_profit_per_contract * position_size * 100
            
            # Max risk is the net debit
            max_risk = total_net_debit
            
            # Calculate target delta
            bias = self.params['bias']
            if bias == 'bullish':
                target_delta = BULLISH_DELTA_TARGET
            elif bias == 'bearish':
                target_delta = BEARISH_DELTA_TARGET
            else:
                target_delta = 0
            
            # Expected profit based on probability
            pop = self.calculate_probability_of_profit(market_data)
            expected_profit = pop * total_max_profit - (1 - pop) * (max_risk * 0.4)
            
            return {
                'net_debit': total_net_debit,
                'max_profit': total_max_profit,
                'max_risk': max_risk,
                'expected_profit': expected_profit,
                'pop': pop,
                'target_delta': target_delta,
                'time_spread_days': (long_expiry - short_expiry).days
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_calculate_strategy_metrics'
            })
            return {}
    
    def _estimate_option_premium(self, underlying_price: float, strike: float,
                               days_to_exp: int, iv: float, option_type: str) -> float:
        """
        Estimate option premium using simplified Black-Scholes.
        
        Args:
            underlying_price: Current underlying price
            strike: Option strike price
            days_to_exp: Days to expiration
            iv: Implied volatility
            option_type: 'call' or 'put'
            
        Returns:
            Estimated option premium
        """
        try:
            # Simplified time value estimation
            time_value = underlying_price * 0.02 * (iv / 0.2) * (days_to_exp / 30)
            
            # Add intrinsic value
            if option_type == 'call':
                intrinsic = max(0, underlying_price - strike)
            else:  # put
                intrinsic = max(0, strike - underlying_price)
            
            return intrinsic + time_value
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_estimate_option_premium'
            })
            return 0
    
    # ==========================================================================
    # POSITION UPDATES AND MONITORING
    # ==========================================================================
    def _update_position_monitoring(self, market_data: Dict[str, Any]) -> None:
        """
        Update position monitoring and analytics.
        
        Args:
            market_data: Current market data
        """
        for position in self.positions:
            try:
                # Update P&L
                self._update_position_pnl(position, market_data)
                
                # Update Greeks
                self._update_position_greeks(position, market_data)
                
                # Update trend analysis
                self._update_position_trend_analysis(position, market_data)
                
                # Update time decay
                self._update_position_time_decay(position, market_data)
                
                # Check risk thresholds
                self._check_position_risk_thresholds(position, market_data)
                
            except Exception as e:
                self.error_handler.handle_error(e, {
                    'method': '_update_position_monitoring',
                    'position_id': position.id
                })
    
    def _update_position_pnl(self, position: DiagonalSpreadPosition,
                           market_data: Dict[str, Any]) -> None:
        """
        Update position P&L based on current market data.
        
        Args:
            position: Position to update
            market_data: Current market data
        """
        try:
            option_chain = market_data.get('option_chain', {})
            
            if option_chain:
                # Calculate current value of both legs
                short_leg_value = self._calculate_leg_value(position.short_leg, option_chain)
                long_leg_value = self._calculate_leg_value(position.long_leg, option_chain)
                
                # Update leg values
                position.short_leg.current_value = short_leg_value
                position.long_leg.current_value = long_leg_value
                
                # Calculate total P&L (long premium - short premium - net debit)
                current_total_value = long_leg_value - short_leg_value
                position.current_pnl = current_total_value - position.net_debit
                
                # Update max profit achieved
                if position.current_pnl > position.max_profit:
                    position.max_profit = position.current_pnl
        
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_position_pnl',
                'position_id': position.id
            })
    
    def _calculate_leg_value(self, leg: DiagonalLeg, option_chain: Dict[str, Any]) -> float:
        """
        Calculate current value of a diagonal leg.
        
        Args:
            leg: Diagonal leg data
            option_chain: Current option chain data
            
        Returns:
            Current leg value
        """
        try:
            option_key = f"{leg.expiry.strftime('%Y-%m-%d')}#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD17_DiagonalSpread.py
Group: D (Trading Strategies)
Purpose: Diagonal Spread strategy with multi-timeframe approach and directional bias

Description:
    This module implements the Diagonal Spread strategy that combines options of
    the same type with different strike prices and expiration dates. The strategy
    profits from time decay, volatility changes, and directional movement through
    sophisticated bias management, delta-based strike selection, and advanced
    multi-timeframe optimization protocols.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-06-29
Last Updated: 2025-06-29 Time: 15:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
from typing import Dict, List, Tuple, Optional, Union, Any
from dataclasses import dataclass, field
from enum import Enum, auto
import uuid
import asyncio
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy, StrategySignal, PositionType
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU14_OptionStrategies import SpyderOptionStrategies, StrategyType, OptionStrategy, OptionRight
from SpyderU_Utilities.SpyderU07_Constants import (
    OptionType, OrderAction, OrderType, SignalType,
    DIAGONAL_SPREAD_PROFIT_TARGET, DIAGONAL_SPREAD_STOP_LOSS,
    MIN_IV_RANK_FOR_DIRECTIONAL_STRATEGIES, OPTIMAL_ENTRY_START, OPTIMAL_ENTRY_END
)
from SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager, RiskProfile
from SpyderE_Risk.SpyderE08_PositionGroupValidator import PositionGroupValidator
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event
from SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from SpyderF_Analysis.SpyderF08_VolatilityRegime import VolatilityRegimeAnalyzer
from SpyderF_Analysis.SpyderF04_VolatilityAnalysis import VolatilityAnalyzer
from SpyderF_Analysis.SpyderF05_TrendDetection import TrendDetector
from SpyderF_Analysis.SpyderF10_MarketRegimeDetector import MarketRegimeDetector
from SpyderB_Broker.SpyderB06_ContractBuilder import ContractBuilder
from SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
from SpyderU_Utilities.SpyderU13_TechnicalIndicators import TechnicalIndicators
from SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceMetrics
from SpyderC_MarketData.SpyderC10_VIXAnalyzer import VIXAnalyzer

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy-specific constants
DEFAULT_OPTION_TYPE = 'call'
DEFAULT_BIAS = 'bullish'
DEFAULT_SHORT_STRIKE_DELTA = 0.30
DEFAULT_LONG_STRIKE_DELTA = 0.40
DEFAULT_SHORT_TERM_DAYS = 30
DEFAULT_LONG_TERM_DAYS = 60
DEFAULT_PROFIT_TARGET_PERCENT = 0.30
DEFAULT_STOP_LOSS_PERCENT = 0.50
DEFAULT_IV_RANK_MIN = 30
DEFAULT_IV_RANK_MAX = 70
DEFAULT_POSITION_SIZE_PERCENT = 0.05

# Multi-timeframe management
MIN_TIME_SPREAD = 14  # Minimum days between expirations
MAX_TIME_SPREAD = 60  # Maximum days between expirations
OPTIMAL_TIME_SPREAD = 30  # Optimal time spread for theta decay
NEAR_EXPIRY_THRESHOLD = 5  # Days before short expiry to consider closure

# Trading windows
DIAGONAL_ENTRY_START = datetime.time(10, 30)
DIAGONAL_ENTRY_END = datetime.time(14, 30)
MAX_DAYS_HELD = 21
MIN_DAYS_TO_LONG_EXPIRY = 14

# Directional thresholds
BULLISH_DELTA_TARGET = 0.15  # Target net delta for bullish bias
BEARISH_DELTA_TARGET = -0.15  # Target net delta for bearish bias
NEUTRAL_DELTA_MAX = 0.10  # Maximum delta for neutral bias

# Risk thresholds
MAX_DIAGONAL_DELTA = 20.0  # Maximum delta per diagonal
MAX_DIAGONAL_GAMMA = 10.0  # Maximum gamma per diagonal
MAX_DIAGONAL_VEGA = 25.0   # Maximum vega per diagonal
MAX_DIAGONAL_THETA = -15.0  # Maximum theta decay per diagonal

# Price movement thresholds
BREAKOUT_THRESHOLD = 0.02  # 2% price movement
TREND_CONFIRMATION_BARS = 3  # Bars to confirm trend
VOLATILITY_EXPANSION_THRESHOLD = 0.15  # 15% IV increase

# ==============================================================================
# ENUMS
# ==============================================================================
class DiagonalSpreadState(Enum):
    """Diagonal Spread position states"""
    INACTIVE = "inactive"
    MONITORING = "monitoring"
    ACTIVE = "active"
    ROLLING = "rolling"
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"

class DiagonalType(Enum):
    """Types of diagonal spreads"""
    CALL_DIAGONAL = "call_diagonal"
    PUT_DIAGONAL = "put_diagonal"

class MarketBias(Enum):
    """Market bias for diagonal spreads"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"

class ExitReason(Enum):
    """Exit reasons for Diagonal Spread positions"""
    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    TIME_DECAY = "time_decay"
    SHORT_EXPIRATION = "short_expiration"
    TREND_REVERSAL = "trend_reversal"
    VOLATILITY_CRUSH = "volatility_crush"
    VOLATILITY_EXPANSION = "volatility_expansion"
    DELTA_RISK = "delta_risk"
    GAMMA_RISK = "gamma_risk"
    BREAKOUT_FAILURE = "breakout_failure"
    RISK_MANAGEMENT = "risk_management"

class TrendStrength(Enum):
    """Trend strength classification"""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class DiagonalLeg:
    """Individual diagonal spread leg data"""
    action: str  # 'BUY' or 'SELL'
    strike: float
    expiry: datetime.datetime
    option_type: str  # 'call' or 'put'
    delta: float
    current_value: float = 0.0
    entry_value: float = 0.0
    time_decay: float = 0.0
    greeks: Dict[str, float] = field(default_factory=dict)

@dataclass
class TrendAnalysis:
    """Trend analysis data"""
    direction: str  # 'bullish', 'bearish', 'neutral'
    strength: TrendStrength
    confidence: float
    momentum: float
    breakout_level: Optional[float]
    support_level: Optional[float]
    resistance_level: Optional[float]
    trend_duration: int  # days

@dataclass
class DiagonalSpreadPosition:
    """Diagonal Spread position data structure"""
    id: str
    entry_time: datetime.datetime
    diagonal_type: DiagonalType
    market_bias: MarketBias
    short_leg: DiagonalLeg
    long_leg: DiagonalLeg
    time_spread: int  # Days between expirations
    net_debit: float
    entry_iv: float
    entry_iv_rank: float
    entry_price: float
    entry_trend: TrendAnalysis
    current_pnl: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    time_decay_collected: float = 0.0
    state: DiagonalSpreadState = DiagonalSpreadState.ACTIVE
    exit_reason: Optional[ExitReason] = None
    portfolio_greeks: Dict[str, float] = field(default_factory=dict)
    current_trend: Optional[TrendAnalysis] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DiagonalSpreadMetrics:
    """Performance metrics for Diagonal Spread strategy"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    average_days_held: float = 0.0
    total_debit_paid: float = 0.0
    average_debit_per_trade: float = 0.0
    average_time_spread: float = 0.0
    time_decay_efficiency: float = 0.0
    trend_following_wins: int = 0
    volatility_expansion_wins: int = 0
    max_concurrent_positions: int = 0

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderD17_DiagonalSpread(BaseStrategy):
    """
    Diagonal Spread Strategy implementation for SPYDER.
    
    A Diagonal Spread involves buying and selling options of the same type but with
    different strike prices and expiration dates. This creates a position that profits
    from time decay, changes in implied volatility, and/or directional movement through
    sophisticated multi-timeframe optimization.
    
    Key Features:
    - Multi-timeframe approach combining different expiration cycles
    - Directional bias support (bullish, bearish, neutral)
    - Advanced strike selection using delta-based targeting
    - Trend analysis integration for optimal entry timing
    - Sophisticated time decay management across different expirations
    - Real-time Greeks monitoring and risk management
    - Volatility regime-aware position sizing
    - Professional rolling and adjustment capabilities
    
    Strategy Profiles:
    - Bullish Call Diagonal: Long further OTM/longer-term call + Short nearer OTM/shorter-term call
    - Bearish Call Diagonal: Long nearer ITM/longer-term call + Short further ITM/shorter-term call
    - Bullish Put Diagonal: Long further ITM/longer-term put + Short nearer ITM/shorter-term put
    - Bearish Put Diagonal: Long further OTM/longer-term put + Short nearer OTM/shorter-term put
    
    Risk Profile:
    - Limited risk (net debit paid)
    - Moderate to high reward potential
    - Time decay advantage when properly structured
    - Volatility expansion benefit from long-term leg
    
    Attributes:
        name: Strategy name
        strategy_type: Strategy type identifier
        positions: Current Diagonal Spread positions
        metrics: Performance tracking metrics
        state: Current strategy state
        
    Example:
        >>> config = {'bias': 'bullish', 'option_type': 'call', 'time_spread': 30}
        >>> strategy = SpyderD17_DiagonalSpread(config)
        >>> signals = strategy.generate_signals(market_data)
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize Diagonal Spread strategy.
        
        Args:
            config: Strategy configuration parameters
        """
        super().__init__(
            name="Diagonal Spread",
            strategy_type="diagonal_spread",
            config=config or {}
        )
        
        # SPYDER component initialization
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()
        self.risk_manager = get_risk_manager()
        
        # Strategy-specific components
        self.greeks_calculator = GreeksCalculator()
        self.volatility_analyzer = VolatilityAnalyzer()
        self.volatility_regime_analyzer = VolatilityRegimeAnalyzer()
        self.trend_detector = TrendDetector()
        self.market_regime_detector = MarketRegimeDetector()
        self.position_validator = PositionGroupValidator()
        self.contract_builder = ContractBuilder()
        self.datetime_utils = DateTimeUtils()
        self.technical_indicators = TechnicalIndicators()
        self.performance_metrics = PerformanceMetrics()
        self.vix_analyzer = VIXAnalyzer()
        
        # Default parameters
        self.default_params = {
            'option_type': DEFAULT_OPTION_TYPE,
            'bias': DEFAULT_BIAS,
            'short_strike_delta': DEFAULT_SHORT_STRIKE_DELTA,
            'long_strike_delta': DEFAULT_LONG_STRIKE_DELTA,
            'short_term_days': DEFAULT_SHORT_TERM_DAYS,
            'long_term_days': DEFAULT_LONG_TERM_DAYS,
            'entry_day': 'monday',
            'entry_time_start': DIAGONAL_ENTRY_START,
            'entry_time_end': DIAGONAL_ENTRY_END,
            'max_days_held': MAX_DAYS_HELD,
            'profit_target_percent': DEFAULT_PROFIT_TARGET_PERCENT,
            'stop_loss_percent': DEFAULT_STOP_LOSS_PERCENT,
            'iv_rank_min': DEFAULT_IV_RANK_MIN,
            'iv_rank_max': DEFAULT_IV_RANK_MAX,
            'position_size_percent': DEFAULT_POSITION_SIZE_PERCENT,
            'max_concurrent_positions': 3,
            'min_time_spread': MIN_TIME_SPREAD,
            'max_time_spread': MAX_TIME_SPREAD,
            'optimal_time_spread': OPTIMAL_TIME_SPREAD,
            'delta_threshold': MAX_DIAGONAL_DELTA,
            'gamma_threshold': MAX_DIAGONAL_GAMMA,
            'vega_threshold': MAX_DIAGONAL_VEGA,
            'theta_threshold': MAX_DIAGONAL_THETA,
            'trend_confirmation_required': True,
            'volatility_expansion_exit': True,
            'is_active': True
        }
        
        # Update with provided configuration
        self.params = {**self.default_params, **self.config}
        
        # Initialize strategy state
        self.positions: List[DiagonalSpreadPosition] = []
        self.metrics = DiagonalSpreadMetrics()
        self.state = DiagonalSpreadState.INACTIVE
        
        # Performance tracking
        self.trade_history: List[Dict[str, Any]] = []
        self.daily_pnl: float = 0.0
        self.total_exposure: float = 0.0
        self.time_decay_today: float = 0.0
        
        # Trend and market analysis
        self.current_market_trend: Optional[TrendAnalysis] = None
        self.trend_history: List[TrendAnalysis] = []
        
        self.logger.info(f"Initialized {self.name} strategy with parameters: {self.params}")
        self._emit_strategy_event('strategy_initialized', {'params': self.params})
        
    # ==========================================================================
    # SIGNAL GENERATION METHODS
    # ==========================================================================
    def generate_signals(self, market_data: Dict[str, Any]) -> List[StrategySignal]:
        """
        Generate trading signals based on market conditions.
        
        Args:
            market_data: Current market data including price, IV, Greeks, etc.
            
        Returns:
            List of strategy signals
        """
        signals = []
        
        try:
            # Check if strategy is active
            if not self.params['is_active']:
                return signals
            
            # Validate market data
            if not self._validate_market_data(market_data):
                self.logger.warning("Invalid market data received")
                return signals
            
            # Update trend analysis
            self._update_trend_analysis(market_data)
            
            # Check entry conditions
            if self._check_entry_conditions(market_data):
                signal = self._generate_entry_signal(market_data)
                if signal:
                    signals.append(signal)
            
            # Check exit conditions for existing positions
            exit_signals = self._check_exit_conditions(market_data)
            signals.extend(exit_signals)
            
            # Check rolling opportunities
            rolling_signals = self._check_rolling_opportunities(market_data)
            signals.extend(rolling_signals)
            
            # Update position monitoring
            self._update_position_monitoring(market_data)
            
            # Update time decay tracking
            self._update_time_decay_metrics(market_data)
            
            return signals
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'generate_signals',
                'strategy': self.name,
                'market_data_keys': list(market_data.keys()) if market_data else []
            })
            return []
    
    def _check_entry_conditions(self, market_data: Dict[str, Any]) -> bool:
        """
        Check if entry conditions are met for Diagonal Spread strategy.
        
        Args:
            market_data: Current market data
            
        Returns:
            Whether entry conditions are satisfied
        """
        try:
            # Check maximum concurrent positions
            if len(self.positions) >= self.params['max_concurrent_positions']:
                self.logger.debug("Maximum concurrent positions reached")
                return False
            
            # Check day of week
            current_day = market_data.get('current_day_of_week', '').lower()
            entry_day = self.params.get('entry_day', 'any')
            if entry_day != 'any' and current_day != entry_day:
                self.logger.debug(f"Entry day mismatch: {current_day} != {entry_day}")
                return False
            
            # Check time of day
            current_time = market_data.get('current_time')
            if current_time:
                if isinstance(current_time, str):
                    current_time = datetime.datetime.strptime(current_time, '%H:%M').time()
                
                if not (self.params['entry_time_start'] <= current_time <= self.params['entry_time_end']):
                    self.logger.debug(f"Outside entry time window: {current_time}")
                    return False
            
            # Check IV rank (diagonal spreads work in various IV environments)
            iv_rank = market_data.get('iv_rank', 0)
            if not (self.params['iv_rank_min'] <= iv_rank <= self.params['iv_rank_max']):
                self.logger.debug(f"IV rank outside range: {iv_rank}")
                return False
            
            # Check trend confirmation if required
            if self.params['trend_confirmation_required']:
                if not self._is_trend_confirmed(market_data):
                    self.logger.debug("Trend not confirmed for diagonal entry")
                    return False
            
            # Check market regime
            if not self._is_favorable_market_regime(market_data):
                self.logger.debug("Unfavorable market regime for diagonals")
                return False
            
            # Check volatility environment
            if not self._is_favorable_volatility_environment(market_data):
                self.logger.debug("Unfavorable volatility environment")
                return False
            
            # Check available expiration dates
            if not self._validate_expiration_availability(market_data):
                self.logger.debug("Required expiration dates not available")
                return False
            
            # Check available capital
            required_capital = self._calculate_required_capital(market_data)
            if not self.risk_manager.check_capital_available(required_capital):
                self.logger.debug("Insufficient capital available")
                return False
            
            # Check strategy exposure limits
            if not self.risk_manager.check_strategy_exposure(
                self.strategy_type, 
                required_capital
            ):
                self.logger.debug("Strategy exposure limit reached")
                return False
            
            self.logger.info("✅ All entry conditions met for Diagonal Spread")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_check_entry_conditions',
                'market_data': market_data
            })
            return False
    
    def _generate_entry_signal(self, market_data: Dict[str, Any]) -> Optional[StrategySignal]:
        """
        Generate entry signal for Diagonal Spread strategy.
        
        Args:
            market_data: Current market data
            
        Returns:
            Strategy signal or None if generation fails
        """
        try:
            # Determine diagonal configuration
            diagonal_config = self._determine_diagonal_configuration(market_data)
            if not diagonal_config:
                return None
            
            option_type, bias, short_strike, long_strike, short_expiry, long_expiry = diagonal_config
            
            # Calculate position size
            position_size = self._calculate_position_size(market_data)
            if position_size <= 0:
                return None
            
            # Create diagonal spread strategy using SPYDER's OptionStrategies
            option_strategy = self._create_diagonal_spread_strategy(
                market_data['underlying_symbol'],
                option_type,
                short_strike,
                long_strike,
                short_expiry,
                long_expiry,
                position_size
            )
            
            # Validate strategy positions
            if not self._validate_strategy_positions(option_strategy):
                return None
            
            # Calculate expected metrics
            metrics = self._calculate_strategy_metrics(
                market_data, option_type, short_strike, long_strike, 
                short_expiry, long_expiry, position_size
            )
            
            # Create strategy signal
            signal = StrategySignal(
                strategy_id=self.id,
                strategy_name=self.name,
                signal_type=SignalType.ENTRY,
                timestamp=datetime.datetime.now(),
                underlying_symbol=market_data['underlying_symbol'],
                option_strategy=option_strategy,
                confidence=self._calculate_signal_confidence(market_data),
                expected_profit=metrics.get('expected_profit', 0),
                max_risk=metrics.get('max_risk', 0),
                probability_of_profit=metrics.get('pop', 0),
                metadata={
                    'option_type': option_type,
                    'bias': bias,
                    'short_strike': short_strike,
                    'long_strike': long_strike,
                    'short_expiry': short_expiry,
                    'long_expiry': long_expiry,
                    'time_spread': (long_expiry - short_expiry).days,
                    'net_debit': metrics.get('net_debit', 0),
                    'target_delta': metrics.get('target_delta', 0),
                    'trend_analysis': self.current_market_trend.__dict__ if self.current_market_trend else None,
                    'iv_rank': market_data.get('iv_rank'),
                    'entry_criteria': self._get_entry_criteria_summary(market_data)
                }
            )
            
            self.logger.info(f"Generated Diagonal Spread entry signal: {option_type.upper()} {bias} {short_strike}/{long_strike}")
            self._emit_strategy_event('entry_signal_generated', signal.__dict__)
            
            return signal
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_generate_entry_signal',
                'market_data': market_data
            })
            return None
    
    # ==========================================================================
    # TREND ANALYSIS AND MARKET REGIME DETECTION
    # ==========================================================================
    def _update_trend_analysis(self, market_data: Dict[str, Any]) -> None:
        """
        Update current trend analysis using SPYDER's trend detector.
        
        Args:
            market_data: Current market data
        """
        try:
            # Use SPYDER's trend detector
            trend_data = self.trend_detector.analyze_trend(market_data)
            
            # Convert to our internal format
            self.current_market_trend = TrendAnalysis(
                direction=trend_data.get('direction', 'neutral'),
                strength=TrendStrength(trend_data.get('strength', 'moderate')),
                confidence=trend_data.get('confidence', 0.5),
                momentum=trend_data.get('momentum', 0),
                breakout_level=trend_data.get('breakout_level'),
                support_level=trend_data.get('support_level'),
                resistance_level=trend_data.get('resistance_level'),
                trend_duration=trend_data.get('duration_days', 0)
            )
            
            # Add to trend history
            self.trend_history.append(self.current_market_trend)
            
            # Keep only recent history
            if len(self.trend_history) > 20:
                self.trend_history = self.trend_history[-20:]
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_trend_analysis'
            })
    
    def _is_trend_confirmed(self, market_data: Dict[str, Any]) -> bool:
        """
        Check if current trend is confirmed for diagonal entry.
        
        Args:
            market_data: Current market data
            
        Returns:
            Whether trend is confirmed
        """
        try:
            if not self.current_market_trend:
                return False
            
            # Check trend strength and confidence
            if (self.current_market_trend.strength in [TrendStrength.MODERATE, TrendStrength.STRONG, TrendStrength.VERY_STRONG] 
                and self.current_market_trend.confidence >= 0.6):
                return True
            
            # Check trend duration
            if self.current_market_trend.trend_duration >= TREND_CONFIRMATION_BARS:
                return True
            
            return False
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_is_trend_confirmed'
            })
            return False
    
    def _is_favorable_market_regime(self, market_data: Dict[str, Any]) -> bool:
        """
        Check if current market regime is favorable for diagonal spreads.
        
        Args:
            market_data: Current market data
            
        Returns:
            Whether market regime is favorable
        """
        try:
            # Use market regime detector
            market_regime = self.market_regime_detector.detect_regime(market_data)
            
            # Diagonal spreads work well in trending and moderate volatility environments
            favorable_regimes = ['trending', 'breakout', 'moderate_volatility']
            
            return market_regime.regime_type in favorable_regimes
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_is_favorable_market_regime'
            })
            return True
    
    def _is_favorable_volatility_environment(self, market_data: Dict[str, Any]) -> bool:
        """
        Check if volatility environment is favorable for diagonal spreads.
        
        Args:
            market_data: Current market data
            
        Returns:
            Whether volatility environment is favorable
        """
        try:
            iv_rank = market_data.get('iv_rank', 50)
            
            # Diagonal spreads work in various IV environments but prefer moderate levels
            if 30 <= iv_rank <= 70:
                return True
            
            # Also check IV trend
            iv_trend = market_data.get('iv_trend', 'neutral')
            if iv_trend in ['rising', 'stable'] and iv_rank >= 25:
                return True
            
            return False
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_is_favorable_volatility_environment'
            })
            return True
    
    # ==========================================================================
    # DIAGONAL CONFIGURATION AND STRIKE SELECTION
    # ==========================================================================
    def _determine_diagonal_configuration(self, market_data: Dict[str, Any]) -> Optional[Tuple[str, str, float, float, datetime.datetime, datetime.datetime]]:
        """
        Determine optimal diagonal spread configuration based on market conditions.
        
        Args:
            market_data: Current market data
            
        Returns:
            Tuple of (option_type, bias, short_strike, long_strike, short_expiry, long_expiry) or None
        """
        try:
            underlying_price = market_data.get('underlying_price', 0)
            if underlying_price <= 0:
                return None
            
            # Get configuration from parameters
            option_type = self.params['option_type']
            bias = self.params['bias']
            
            # Auto-detect bias from trend if needed
            if bias == 'auto' and self.current_market_trend:
                if self.current_market_trend.direction == 'bullish':
                    bias = 'bullish'
                elif self.current_market_trend.direction == 'bearish':
                    bias = 'bearish'
                else:
                    bias = 'neutral'
            
            # Get expiration dates
            short_expiry, long_expiry = self._get_target_expirations(market_data)
            if not short_expiry or not long_expiry:
                return None
            
            # Calculate strikes based on bias and option type
            short_strike, long_strike = self._calculate_diagonal_strikes(
                underlying_price, market_data, option_type, bias
            )
            
            if not short_strike or not long_strike:
                return None
            
            # Validate configuration
            if not self._validate_diagonal_configuration(
                option_type, bias, short_strike, long_strike, underlying_price
            ):
                return None
            
            return option_type, bias, short_strike, long_strike, short_expiry, long_expiry
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_determine_diagonal_configuration'
            })
            return None
    
    def _calculate_diagonal_strikes(self, underlying_price: float, market_data: Dict[str, Any],
                                  
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
                                  
