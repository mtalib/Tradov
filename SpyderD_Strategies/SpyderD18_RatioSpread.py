#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD18_RatioSpread.py
Group: D (Trading Strategies)
Purpose: Ratio Spread strategy with unequal option quantities for premium collection

Description:
    This module implements the Ratio Spread strategy that involves buying options
    at one strike price and selling more options at a different strike price, creating
    an unbalanced position with enhanced premium collection potential. The strategy
    profits from limited price movement while collecting substantial premium through
    sophisticated ratio management and dynamic risk zone monitoring.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-06-29
Last Updated: 2025-06-29 Time: 14:00:00
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
    RATIO_SPREAD_PROFIT_TARGET, RATIO_SPREAD_STOP_LOSS,
    MIN_IV_RANK_FOR_PREMIUM_STRATEGIES, OPTIMAL_ENTRY_START, OPTIMAL_ENTRY_END
)
from SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager, RiskProfile
from SpyderE_Risk.SpyderE08_PositionGroupValidator import PositionGroupValidator
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event
from SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from SpyderF_Analysis.SpyderF08_VolatilityRegime import VolatilityRegimeAnalyzer
from SpyderF_Analysis.SpyderF04_VolatilityAnalysis import VolatilityAnalyzer
from SpyderF_Analysis.SpyderF10_MarketRegimeDetector import MarketRegimeDetector
from SpyderB_Broker.SpyderB06_ContractBuilder import ContractBuilder
from SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
from SpyderU_Utilities.SpyderU13_TechnicalIndicators import TechnicalIndicators
from SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceMetrics
from SpyderN_OptionsAnalytics.SpyderN09_GammaExposure import GammaExposureCalculator

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy-specific constants
DEFAULT_OPTION_TYPE = 'call'
DEFAULT_BIAS = 'neutral'
DEFAULT_RATIO = 1.5  # 3:2 ratio (1.5x short to long)
DEFAULT_LONG_STRIKE_DELTA = 0.40
DEFAULT_SHORT_STRIKE_DELTA = 0.25
DEFAULT_DAYS_TO_EXPIRATION = 45
DEFAULT_PROFIT_TARGET_PERCENT = 0.25
DEFAULT_STOP_LOSS_PERCENT = 0.50
DEFAULT_IV_RANK_MIN = 40
DEFAULT_IV_RANK_MAX = 80
DEFAULT_POSITION_SIZE_PERCENT = 0.05

# Ratio management
MIN_RATIO = 1.2  # Minimum 1.2:1 ratio
MAX_RATIO = 3.0  # Maximum 3:1 ratio
OPTIMAL_RATIO = 1.5  # Optimal 1.5:1 ratio
MIN_BASE_CONTRACTS = 2  # Minimum contracts for long side

# Trading windows
RATIO_SPREAD_ENTRY_START = datetime.time(10, 30)
RATIO_SPREAD_ENTRY_END = datetime.time(14, 30)
MAX_DAYS_HELD = 30
MIN_DAYS_TO_EXPIRY = 7

# Risk zone management
RISK_ZONE_BUFFER = 0.05  # 5% buffer around risk zones
GAMMA_RISK_THRESHOLD = 15.0  # Maximum gamma exposure
DELTA_RISK_THRESHOLD = 25.0  # Maximum delta exposure
VEGA_RISK_THRESHOLD = 30.0   # Maximum vega exposure

# Premium collection
MIN_NET_CREDIT = 0.50  # Minimum net credit for ratio spreads
TARGET_NET_CREDIT = 1.50  # Target net credit
MAX_NET_DEBIT = 0.25  # Maximum acceptable net debit

# Market movement thresholds
CALL_RATIO_UPSIDE_LIMIT = 1.10  # 10% above short strike
PUT_RATIO_DOWNSIDE_LIMIT = 0.90  # 10% below short strike

# ==============================================================================
# ENUMS
# ==============================================================================
class RatioSpreadState(Enum):
    """Ratio Spread position states"""
    INACTIVE = "inactive"
    MONITORING = "monitoring"
    ACTIVE = "active"
    IN_RISK_ZONE = "in_risk_zone"
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"

class RatioType(Enum):
    """Types of ratio spreads"""
    CALL_RATIO = "call_ratio"
    PUT_RATIO = "put_ratio"

class MarketBias(Enum):
    """Market bias for ratio spreads"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"

class ExitReason(Enum):
    """Exit reasons for Ratio Spread positions"""
    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    TIME_DECAY = "time_decay"
    EXPIRATION = "expiration"
    RISK_ZONE_BREACH = "risk_zone_breach"
    GAMMA_RISK = "gamma_risk"
    DELTA_RISK = "delta_risk"
    UNDERLYING_MOVEMENT = "underlying_movement"
    IV_CRUSH = "iv_crush"
    RISK_MANAGEMENT = "risk_management"

class RiskZone(Enum):
    """Risk zones for ratio spreads"""
    SAFE_ZONE = "safe_zone"
    WARNING_ZONE = "warning_zone"
    DANGER_ZONE = "danger_zone"
    CRITICAL_ZONE = "critical_zone"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class RatioSpreadLeg:
    """Individual ratio spread leg data"""
    action: str  # 'BUY' or 'SELL'
    strike: float
    quantity: int
    option_type: str  # 'call' or 'put'
    current_value: float = 0.0
    entry_value: float = 0.0
    greeks: Dict[str, float] = field(default_factory=dict)

@dataclass
class RiskZoneData:
    """Risk zone analysis data"""
    current_zone: RiskZone
    distance_to_danger: float
    breakeven_points: List[float]
    max_profit_zone: Tuple[float, float]
    unlimited_risk_threshold: float
    profit_probability: float

@dataclass
class RatioSpreadPosition:
    """Ratio Spread position data structure"""
    id: str
    entry_time: datetime.datetime
    expiration: datetime.datetime
    ratio_type: RatioType
    market_bias: MarketBias
    ratio: float
    long_leg: RatioSpreadLeg
    short_leg: RatioSpreadLeg
    net_credit: float
    entry_iv: float
    entry_iv_rank: float
    entry_price: float
    current_pnl: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    risk_zone_data: Optional[RiskZoneData] = None
    state: RatioSpreadState = RatioSpreadState.ACTIVE
    exit_reason: Optional[ExitReason] = None
    portfolio_greeks: Dict[str, float] = field(default_factory=dict)
    gamma_exposure: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RatioSpreadMetrics:
    """Performance metrics for Ratio Spread strategy"""
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
    total_credit_collected: float = 0.0
    average_credit_per_trade: float = 0.0
    average_ratio: float = 0.0
    risk_zone_breaches: int = 0
    gamma_adjustments: int = 0
    max_concurrent_positions: int = 0

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderD18_RatioSpread(BaseStrategy):
    """
    Ratio Spread Strategy implementation for SPYDER.
    
    A Ratio Spread involves buying options at one strike price and selling more options
    at a different strike price, creating an unbalanced position that collects premium
    while maintaining limited directional exposure. The strategy profits from time decay
    and limited price movement within optimal zones.
    
    Key Features:
    - Unequal ratio positioning (default 1.5:1) for enhanced premium collection
    - Dynamic risk zone monitoring with real-time breach detection
    - Flexible bias handling (bullish, bearish, neutral market views)
    - Advanced gamma exposure management with automatic adjustments
    - Professional strike selection using delta-based targeting
    - Real-time Greeks monitoring across all legs
    - Sophisticated margin and capital requirement calculations
    - Market regime-aware position sizing and entry timing
    
    Strategy Profiles:
    - Call Ratio Spreads: Long lower strike calls + Short higher strike calls
    - Put Ratio Spreads: Long higher strike puts + Short lower strike puts
    - Neutral Bias: Profit from range-bound movement
    - Directional Bias: Enhanced profit from limited directional movement
    
    Risk Profile:
    - Limited risk up to breakeven points
    - Unlimited risk beyond critical thresholds (managed through monitoring)
    - High probability of profit within optimal price ranges
    - Enhanced premium collection compared to standard spreads
    
    Attributes:
        name: Strategy name
        strategy_type: Strategy type identifier
        positions: Current Ratio Spread positions
        metrics: Performance tracking metrics
        state: Current strategy state
        
    Example:
        >>> config = {'ratio': 1.5, 'bias': 'neutral', 'option_type': 'call'}
        >>> strategy = SpyderD18_RatioSpread(config)
        >>> signals = strategy.generate_signals(market_data)
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize Ratio Spread strategy.
        
        Args:
            config: Strategy configuration parameters
        """
        super().__init__(
            name="Ratio Spread",
            strategy_type="ratio_spread",
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
        self.market_regime_detector = MarketRegimeDetector()
        self.position_validator = PositionGroupValidator()
        self.contract_builder = ContractBuilder()
        self.datetime_utils = DateTimeUtils()
        self.technical_indicators = TechnicalIndicators()
        self.performance_metrics = PerformanceMetrics()
        self.gamma_exposure_calculator = GammaExposureCalculator()
        
        # Default parameters
        self.default_params = {
            'option_type': DEFAULT_OPTION_TYPE,
            'bias': DEFAULT_BIAS,
            'ratio': DEFAULT_RATIO,
            'long_strike_delta': DEFAULT_LONG_STRIKE_DELTA,
            'short_strike_delta': DEFAULT_SHORT_STRIKE_DELTA,
            'days_to_expiration': DEFAULT_DAYS_TO_EXPIRATION,
            'entry_day': 'monday',
            'entry_time_start': RATIO_SPREAD_ENTRY_START,
            'entry_time_end': RATIO_SPREAD_ENTRY_END,
            'max_days_held': MAX_DAYS_HELD,
            'profit_target_percent': DEFAULT_PROFIT_TARGET_PERCENT,
            'stop_loss_percent': DEFAULT_STOP_LOSS_PERCENT,
            'iv_rank_min': DEFAULT_IV_RANK_MIN,
            'iv_rank_max': DEFAULT_IV_RANK_MAX,
            'position_size_percent': DEFAULT_POSITION_SIZE_PERCENT,
            'max_concurrent_positions': 2,
            'min_ratio': MIN_RATIO,
            'max_ratio': MAX_RATIO,
            'min_net_credit': MIN_NET_CREDIT,
            'target_net_credit': TARGET_NET_CREDIT,
            'max_net_debit': MAX_NET_DEBIT,
            'risk_zone_buffer': RISK_ZONE_BUFFER,
            'gamma_threshold': GAMMA_RISK_THRESHOLD,
            'delta_threshold': DELTA_RISK_THRESHOLD,
            'vega_threshold': VEGA_RISK_THRESHOLD,
            'is_active': True
        }
        
        # Update with provided configuration
        self.params = {**self.default_params, **self.config}
        
        # Initialize strategy state
        self.positions: List[RatioSpreadPosition] = []
        self.metrics = RatioSpreadMetrics()
        self.state = RatioSpreadState.INACTIVE
        
        # Performance tracking
        self.trade_history: List[Dict[str, Any]] = []
        self.daily_pnl: float = 0.0
        self.total_exposure: float = 0.0
        self.gamma_exposure_today: float = 0.0
        
        # Risk zone monitoring
        self.active_risk_zones: Dict[str, RiskZoneData] = {}
        self.risk_zone_alerts: List[Dict[str, Any]] = []
        
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
            
            # Check entry conditions
            if self._check_entry_conditions(market_data):
                signal = self._generate_entry_signal(market_data)
                if signal:
                    signals.append(signal)
            
            # Check exit conditions for existing positions
            exit_signals = self._check_exit_conditions(market_data)
            signals.extend(exit_signals)
            
            # Update position monitoring and risk zones
            self._update_position_monitoring(market_data)
            
            # Update gamma exposure tracking
            self._update_gamma_exposure_metrics(market_data)
            
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
        Check if entry conditions are met for Ratio Spread strategy.
        
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
            
            # Check IV rank (ratio spreads prefer higher IV)
            iv_rank = market_data.get('iv_rank', 0)
            if not (self.params['iv_rank_min'] <= iv_rank <= self.params['iv_rank_max']):
                self.logger.debug(f"IV rank outside range: {iv_rank}")
                return False
            
            # Check market regime (prefer neutral to moderate trending)
            if not self._is_favorable_market_regime(market_data):
                self.logger.debug("Unfavorable market regime for ratio spreads")
                return False
            
            # Check volatility environment
            if not self._is_favorable_volatility_environment(market_data):
                self.logger.debug("Unfavorable volatility environment")
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
            
            # Check gamma exposure limits
            if not self._check_gamma_exposure_limits(market_data):
                self.logger.debug("Gamma exposure limits would be exceeded")
                return False
            
            self.logger.info("✅ All entry conditions met for Ratio Spread")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_check_entry_conditions',
                'market_data': market_data
            })
            return False
    
    def _generate_entry_signal(self, market_data: Dict[str, Any]) -> Optional[StrategySignal]:
        """
        Generate entry signal for Ratio Spread strategy.
        
        Args:
            market_data: Current market data
            
        Returns:
            Strategy signal or None if generation fails
        """
        try:
            # Determine ratio spread configuration
            ratio_config = self._determine_ratio_configuration(market_data)
            if not ratio_config:
                return None
    
    # ==========================================================================
    # POSITION MONITORING AND UPDATES
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
                
                # Update risk zones
                self._update_position_risk_zone(position, market_data)
                
                # Update gamma exposure
                self._update_position_gamma_exposure(position, market_data)
                
                # Check risk thresholds
                self._check_position_risk_thresholds(position, market_data)
                
            except Exception as e:
                self.error_handler.handle_error(e, {
                    'method': '_update_position_monitoring',
                    'position_id': position.id
                })
    
    def _update_position_pnl(self, position: RatioSpreadPosition, 
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
                # Calculate current value of all legs
                long_leg_value = self._calculate_leg_value(position.long_leg, option_chain, position.expiration)
                short_leg_value = self._calculate_leg_value(position.short_leg, option_chain, position.expiration)
                
                # Total current value (considering quantities and actions)
                current_total_value = long_leg_value + short_leg_value
                
                # P&L calculation for ratio spread
                entry_value = position.long_leg.entry_value + position.short_leg.entry_value
                position.current_pnl = current_total_value - entry_value
                
                # Update max profit achieved
                if position.current_pnl > position.max_profit:
                    position.max_profit = position.current_pnl
        
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_position_pnl',
                'position_id': position.id
            })
    
    def _calculate_leg_value(self, leg: RatioSpreadLeg, option_chain: Dict[str, Any],
                           expiration: datetime.datetime) -> float:
        """
        Calculate current value of a position leg.
        
        Args:
            leg: Position leg data
            option_chain: Current option chain data
            expiration: Option expiration date
            
        Returns:
            Current leg value
        """
        try:
            option_key = f"{expiration.strftime('%Y-%m-%d')}_{leg.strike}_{leg.option_type}"
            
            if option_key in option_chain:
                current_price = option_chain[option_key].get('mid', 0)
                leg.current_value = current_price
                
                # Calculate value based on action (BUY = negative cost, SELL = positive credit)
                if leg.action == 'BUY':
                    return -current_price * leg.quantity * 100  # We pay (negative)
                else:  # SELL
                    return current_price * leg.quantity * 100   # We receive (positive)
            
            return 0.0
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_calculate_leg_value'
            })
            return 0.0
    
    def _update_position_greeks(self, position: RatioSpreadPosition,
                              market_data: Dict[str, Any]) -> None:
        """
        Update position Greeks using SPYDER's Greeks calculator.
        
        Args:
            position: Position to update
            market_data: Current market data
        """
        try:
            underlying_price = market_data.get('underlying_price', 0)
            if underlying_price <= 0:
                return
            
            # Calculate Greeks for all legs and aggregate
            all_legs = [
                {
                    'option_type': position.long_leg.option_type,
                    'strike': position.long_leg.strike,
                    'expiry': position.expiration,
                    'quantity': position.long_leg.quantity,  # Long position
                    'underlying_price': underlying_price
                },
                {
                    'option_type': position.short_leg.option_type,
                    'strike': position.short_leg.strike,
                    'expiry': position.expiration,
                    'quantity': -position.short_leg.quantity,  # Short position (negative)
                    'underlying_price': underlying_price
                }
            ]
            
            # Calculate portfolio Greeks
            portfolio_greeks = self.greeks_calculator.calculate_position_greeks(all_legs)
            position.portfolio_greeks = portfolio_greeks
            
            # Update individual leg Greeks
            for leg_data in all_legs:
                leg_greeks = self.greeks_calculator.calculate_single_option_greeks(leg_data)
                if leg_data['quantity'] > 0:  # Long leg
                    position.long_leg.greeks = leg_greeks
                else:  # Short leg
                    position.short_leg.greeks = leg_greeks
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_position_greeks',
                'position_id': position.id
            })
    
    def _update_position_risk_zone(self, position: RatioSpreadPosition,
                                 market_data: Dict[str, Any]) -> None:
        """
        Update position risk zone data.
        
        Args:
            position: Position to update
            market_data: Current market data
        """
        try:
            underlying_price = market_data.get('underlying_price', 0)
            if underlying_price <= 0:
                return
            
            # Recalculate risk zones with current data
            risk_zone_data = self._calculate_risk_zones(
                market_data,
                position.long_leg.option_type,
                position.long_leg.strike,
                position.short_leg.strike,
                position.ratio
            )
            
            # Update position risk zone data
            old_zone = position.risk_zone_data.current_zone if position.risk_zone_data else RiskZone.SAFE_ZONE
            position.risk_zone_data = risk_zone_data
            
            # Emit event if risk zone changed
            if old_zone != risk_zone_data.current_zone:
                self._emit_strategy_event('risk_zone_changed', {
                    'position_id': position.id,
                    'old_zone': old_zone.value,
                    'new_zone': risk_zone_data.current_zone.value,
                    'underlying_price': underlying_price,
                    'distance_to_danger': risk_zone_data.distance_to_danger
                })
                
                # Update position state based on risk zone
                if risk_zone_data.current_zone in [RiskZone.DANGER_ZONE, RiskZone.CRITICAL_ZONE]:
                    position.state = RatioSpreadState.IN_RISK_ZONE
                else:
                    position.state = RatioSpreadState.ACTIVE
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_position_risk_zone',
                'position_id': position.id
            })
    
    def _update_position_gamma_exposure(self, position: RatioSpreadPosition,
                                      market_data: Dict[str, Any]) -> None:
        """
        Update position gamma exposure using SPYDER's gamma calculator.
        
        Args:
            position: Position to update
            market_data: Current market data
        """
        try:
            # Calculate gamma exposure using SPYDER's gamma exposure calculator
            gamma_data = {
                'underlying_price': market_data.get('underlying_price', 0),
                'positions': [
                    {
                        'option_type': position.long_leg.option_type,
                        'strike': position.long_leg.strike,
                        'expiry': position.expiration,
                        'quantity': position.long_leg.quantity
                    },
                    {
                        'option_type': position.short_leg.option_type,
                        'strike': position.short_leg.strike,
                        'expiry': position.expiration,
                        'quantity': -position.short_leg.quantity  # Negative for short
                    }
                ]
            }
            
            gamma_exposure = self.gamma_exposure_calculator.calculate_net_gamma_exposure(gamma_data)
            position.gamma_exposure = gamma_exposure
            
            # Update daily tracking
            self.gamma_exposure_today = sum(pos.gamma_exposure for pos in self.positions)
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_position_gamma_exposure',
                'position_id': position.id
            })
    
    def _update_gamma_exposure_metrics(self, market_data: Dict[str, Any]) -> None:
        """
        Update overall gamma exposure metrics.
        
        Args:
            market_data: Current market data
        """
        try:
            total_gamma = sum(pos.gamma_exposure for pos in self.positions)
            
            # Update strategy metrics
            if total_gamma > self.params['gamma_threshold'] * 0.8:  # 80% of threshold
                self._emit_strategy_event('gamma_exposure_warning', {
                    'total_gamma': total_gamma,
                    'threshold': self.params['gamma_threshold'],
                    'utilization': total_gamma / self.params['gamma_threshold']
                })
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_gamma_exposure_metrics'
            })
    
    def _check_position_risk_thresholds(self, position: RatioSpreadPosition,
                                      market_data: Dict[str, Any]) -> None:
        """
        Check position against all risk thresholds.
        
        Args:
            position: Position to check
            market_data: Current market data
        """
        try:
            # Check P&L risk
            max_loss_threshold = position.net_credit * 1.0  # 100% of credit
            if position.current_pnl <= -max_loss_threshold:
                self._emit_strategy_event('pnl_risk_warning', {
                    'position_id': position.id,
                    'current_pnl': position.current_pnl,
                    'threshold': -max_loss_threshold
                })
            
            # Check risk zone status
            if position.risk_zone_data:
                if position.risk_zone_data.current_zone == RiskZone.CRITICAL_ZONE:
                    self._emit_strategy_event('critical_risk_zone_warning', {
                        'position_id': position.id,
                        'underlying_price': market_data.get('underlying_price'),
                        'risk_threshold': position.risk_zone_data.unlimited_risk_threshold,
                        'distance_to_danger': position.risk_zone_data.distance_to_danger
                    })
        
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_check_position_risk_thresholds',
                'position_id': position.id
            })
    
    # ==========================================================================
    # EXIT SIGNAL GENERATION
    # ==========================================================================
    def _generate_exit_signal(self, position: RatioSpreadPosition,
                            market_data: Dict[str, Any],
                            exit_reason: ExitReason) -> Optional[StrategySignal]:
        """
        Generate exit signal for position.
        
        Args:
            position: Position to exit
            market_data: Current market data
            exit_reason: Reason for exit
            
        Returns:
            Exit signal or None
        """
        try:
            # Create inverse strategy for closing
            option_strategy = self._create_closing_strategy(position)
            
            # Create exit signal
            signal = StrategySignal(
                strategy_id=self.id,
                strategy_name=self.name,
                signal_type=SignalType.EXIT,
                timestamp=datetime.datetime.now(),
                underlying_symbol=market_data['underlying_symbol'],
                option_strategy=option_strategy,
                confidence=0.9,  # High confidence for risk management exits
                expected_profit=position.current_pnl,
                max_risk=0,  # Closing position
                probability_of_profit=1.0,  # Certain exit
                metadata={
                    'position_id': position.id,
                    'exit_reason': exit_reason.value,
                    'days_held': (datetime.datetime.now() - position.entry_time).days,
                    'entry_credit': position.net_credit,
                    'current_pnl': position.current_pnl,
                    'ratio': position.ratio,
                    'risk_zone': position.risk_zone_data.current_zone.value if position.risk_zone_data else None,
                    'gamma_exposure': position.gamma_exposure
                }
            )
            
            self.logger.info(f"Generated exit signal for position {position.id}: {exit_reason.value}")
            self._emit_strategy_event('exit_signal_generated', {
                'position_id': position.id,
                'exit_reason': exit_reason.value,
                'pnl': position.current_pnl,
                'risk_zone': position.risk_zone_data.current_zone.value if position.risk_zone_data else None
            })
            
            return signal
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_generate_exit_signal',
                'position_id': position.id,
                'exit_reason': exit_reason.value
            })
            return None
    
    def _create_closing_strategy(self, position: RatioSpreadPosition) -> OptionStrategy:
        """
        Create inverse strategy for closing position.
        
        Args:
            position: Position to close
            
        Returns:
            Closing option strategy
        """
        return SpyderOptionStrategies.ratio_spread_close(
            underlying_symbol="SPY",
            option_type=position.long_leg.option_type,
            long_strike=position.long_leg.strike,
            short_strike=position.short_leg.strike,
            expiry=position.expiration,
            long_quantity=position.long_leg.quantity,
            short_quantity=position.short_leg.quantity
        )
            
            option_type, bias, ratio, long_strike, short_strike = ratio_config
            
            # Get expiration date
            expiration = self._get_target_expiration(market_data)
            if not expiration:
                return None
            
            # Calculate position quantities
            long_quantity, short_quantity = self._calculate_ratio_quantities(market_data, ratio)
            if long_quantity <= 0 or short_quantity <= 0:
                return None
            
            # Create ratio spread strategy using SPYDER's OptionStrategies
            option_strategy = self._create_ratio_spread_strategy(
                market_data['underlying_symbol'],
                option_type,
                long_strike,
                short_strike,
                expiration,
                long_quantity,
                short_quantity
            )
            
            # Validate strategy positions
            if not self._validate_strategy_positions(option_strategy):
                return None
            
            # Calculate expected metrics and risk zones
            metrics = self._calculate_strategy_metrics(
                market_data, option_type, long_strike, short_strike, 
                long_quantity, short_quantity
            )
            
            # Calculate risk zones
            risk_zone_data = self._calculate_risk_zones(
                market_data, option_type, long_strike, short_strike, ratio
            )
            
            # Create strategy signal
            signal = StrategySignal(
                strategy_id=self.id,
                strategy_name=self.name,
                signal_type=SignalType.ENTRY,
                timestamp=datetime.datetime.now(),
                underlying_symbol=market_data['underlying_symbol'],
                option_strategy=option_strategy,
                confidence=self._calculate_signal_confidence(market_data, risk_zone_data),
                expected_profit=metrics.get('expected_profit', 0),
                max_risk=metrics.get('max_risk', 0),
                probability_of_profit=metrics.get('pop', 0),
                metadata={
                    'option_type': option_type,
                    'bias': bias,
                    'ratio': ratio,
                    'long_strike': long_strike,
                    'short_strike': short_strike,
                    'long_quantity': long_quantity,
                    'short_quantity': short_quantity,
                    'expiration': expiration,
                    'net_credit': metrics.get('net_credit', 0),
                    'risk_zones': {
                        'max_profit_zone': risk_zone_data.max_profit_zone,
                        'breakeven_points': risk_zone_data.breakeven_points,
                        'unlimited_risk_threshold': risk_zone_data.unlimited_risk_threshold
                    },
                    'iv_rank': market_data.get('iv_rank'),
                    'entry_criteria': self._get_entry_criteria_summary(market_data)
                }
            )
            
            self.logger.info(f"Generated Ratio Spread entry signal: {option_type.upper()} {ratio}:1 {long_strike}/{short_strike}")
            self._emit_strategy_event('entry_signal_generated', signal.__dict__)
            
            return signal
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_generate_entry_signal',
                'market_data': market_data
            })
            return None
    
    # ==========================================================================
    # RATIO CONFIGURATION AND STRIKE SELECTION
    # ==========================================================================
    def _determine_ratio_configuration(self, market_data: Dict[str, Any]) -> Optional[Tuple[str, str, float, float, float]]:
        """
        Determine optimal ratio spread configuration based on market conditions.
        
        Args:
            market_data: Current market data
            
        Returns:
            Tuple of (option_type, bias, ratio, long_strike, short_strike) or None
        """
        try:
            underlying_price = market_data.get('underlying_price', 0)
            if underlying_price <= 0:
                return None
            
            # Get configuration from parameters
            option_type = self.params['option_type']
            bias = self.params['bias']
            ratio = self.params['ratio']
            
            # Auto-detect bias if set to 'auto'
            if bias == 'auto':
                bias = self._detect_market_bias(market_data)
            
            # Calculate strikes based on configuration
            long_strike, short_strike = self._calculate_ratio_strikes(
                underlying_price, market_data, option_type, bias
            )
            
            if not long_strike or not short_strike:
                return None
            
            # Validate strike relationships
            if not self._validate_strike_relationships(
                option_type, long_strike, short_strike, underlying_price
            ):
                return None
            
            return option_type, bias, ratio, long_strike, short_strike
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_determine_ratio_configuration'
            })
            return None
    
    def _calculate_ratio_strikes(self, underlying_price: float, market_data: Dict[str, Any],
                               option_type: str, bias: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate strike prices for ratio spread based on bias and option type.
        
        Args:
            underlying_price: Current underlying price
            market_data: Current market data
            option_type: 'call' or 'put'
            bias: 'bullish', 'bearish', or 'neutral'
            
        Returns:
            Tuple of (long_strike, short_strike) or (None, None)
        """
        try:
            iv = market_data.get('iv', 0.2)
            days_to_exp = self.params['days_to_expiration']
            
            long_delta = self.params['long_strike_delta']
            short_delta = self.params['short_strike_delta']
            
            # Adjust deltas based on option type and bias
            if option_type == 'call':
                if bias == 'bullish':
                    # For bullish call ratio: long ITM/ATM call, short OTM calls
                    long_delta = abs(long_delta)
                    short_delta = abs(short_delta)
                elif bias == 'bearish':
                    # For bearish call ratio: long OTM call, short further OTM calls
                    long_delta = abs(long_delta) * 0.5
                    short_delta = abs(short_delta) * 0.5
                else:  # neutral
                    # For neutral call ratio: long slightly OTM call, short further OTM calls
                    long_delta = abs(long_delta) * 0.8
                    short_delta = abs(short_delta) * 0.8
            else:  # put
                if bias == 'bullish':
                    # For bullish put ratio: long OTM put, short further OTM puts
                    long_delta = -abs(short_delta) * 0.5
                    short_delta = -abs(long_delta) * 0.5
                elif bias == 'bearish':
                    # For bearish put ratio: long ITM/ATM put, short OTM puts
                    long_delta = -abs(long_delta)
                    short_delta = -abs(short_delta)
                else:  # neutral
                    # For neutral put ratio: long slightly OTM put, short further OTM puts
                    long_delta = -abs(long_delta) * 0.8
                    short_delta = -abs(short_delta) * 0.8
            
            # Calculate strikes using delta targeting
            long_strike = self._get_strike_by_delta(
                underlying_price, days_to_exp, long_delta, option_type, iv
            )
            
            short_strike = self._get_strike_by_delta(
                underlying_price, days_to_exp, short_delta, option_type, iv
            )
            
            # Round to available strikes
            available_strikes = market_data.get('available_strikes', [])
            if available_strikes:
                long_strike = self._round_to_available_strike(long_strike, available_strikes)
                short_strike = self._round_to_available_strike(short_strike, available_strikes)
            
            return long_strike, short_strike
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_calculate_ratio_strikes'
            })
            return None, None
    
    def _validate_strike_relationships(self, option_type: str, long_strike: float,
                                     short_strike: float, underlying_price: float) -> bool:
        """
        Validate strike price relationships for ratio spread.
        
        Args:
            option_type: 'call' or 'put'
            long_strike: Long strike price
            short_strike: Short strike price
            underlying_price: Current underlying price
            
        Returns:
            Whether strikes are valid
        """
        try:
            if option_type == 'call':
                # For call ratios, long strike should be below short strike
                if long_strike >= short_strike:
                    self.logger.warning("Call ratio: long strike should be below short strike")
                    return False
            else:  # put
                # For put ratios, long strike should be above short strike
                if long_strike <= short_strike:
                    self.logger.warning("Put ratio: long strike should be above short strike")
                    return False
            
            # Check minimum strike separation
            strike_separation = abs(long_strike - short_strike)
            min_separation = underlying_price * 0.02  # Minimum 2% separation
            
            if strike_separation < min_separation:
                self.logger.warning(f"Strike separation too narrow: {strike_separation}")
                return False
            
            # Check maximum strike separation
            max_separation = underlying_price * 0.15  # Maximum 15% separation
            if strike_separation > max_separation:
                self.logger.warning(f"Strike separation too wide: {strike_separation}")
                return False
            
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_validate_strike_relationships'
            })
            return False
    
    # ==========================================================================
    # RISK ZONE MANAGEMENT METHODS
    # ==========================================================================
    def _calculate_risk_zones(self, market_data: Dict[str, Any], option_type: str,
                            long_strike: float, short_strike: float, ratio: float) -> RiskZoneData:
        """
        Calculate risk zones for ratio spread position.
        
        Args:
            market_data: Current market data
            option_type: 'call' or 'put'
            long_strike: Long strike price
            short_strike: Short strike price
            ratio: Ratio of short to long options
            
        Returns:
            Risk zone data
        """
        try:
            underlying_price = market_data.get('underlying_price', 0)
            
            # Calculate breakeven points
            breakeven_points = self._calculate_breakeven_points(
                option_type, long_strike, short_strike, ratio, market_data
            )
            
            # Determine max profit zone
            if option_type == 'call':
                # For call ratios, max profit at short strike
                max_profit_zone = (long_strike, short_strike)
                unlimited_risk_threshold = short_strike * CALL_RATIO_UPSIDE_LIMIT
            else:  # put
                # For put ratios, max profit at short strike
                max_profit_zone = (short_strike, long_strike)
                unlimited_risk_threshold = short_strike * PUT_RATIO_DOWNSIDE_LIMIT
            
            # Determine current risk zone
            current_zone = self._determine_current_risk_zone(
                underlying_price, breakeven_points, max_profit_zone, unlimited_risk_threshold
            )
            
            # Calculate distance to danger zone
            distance_to_danger = self._calculate_distance_to_danger(
                underlying_price, unlimited_risk_threshold
            )
            
            # Estimate profit probability
            profit_probability = self._estimate_profit_probability_for_zone(
                underlying_price, breakeven_points, market_data
            )
            
            return RiskZoneData(
                current_zone=current_zone,
                distance_to_danger=distance_to_danger,
                breakeven_points=breakeven_points,
                max_profit_zone=max_profit_zone,
                unlimited_risk_threshold=unlimited_risk_threshold,
                profit_probability=profit_probability
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_calculate_risk_zones'
            })
            # Return safe default
            return RiskZoneData(
                current_zone=RiskZone.SAFE_ZONE,
                distance_to_danger=0.1,
                breakeven_points=[],
                max_profit_zone=(0, 0),
                unlimited_risk_threshold=0,
                profit_probability=0.5
            )
    
    def _calculate_breakeven_points(self, option_type: str, long_strike: float,
                                  short_strike: float, ratio: float,
                                  market_data: Dict[str, Any]) -> List[float]:
        """
        Calculate breakeven points for ratio spread.
        
        Args:
            option_type: 'call' or 'put'
            long_strike: Long strike price
            short_strike: Short strike price
            ratio: Ratio of short to long options
            market_data: Current market data
            
        Returns:
            List of breakeven points
        """
        try:
            # Estimate net credit/debit
            net_credit = self._estimate_net_credit(
                option_type, long_strike, short_strike, ratio, market_data
            )
            
            breakeven_points = []
            
            if option_type == 'call':
                # Call ratio spread breakeven points
                # Lower breakeven: long_strike + net_credit
                lower_be = long_strike + net_credit
                breakeven_points.append(lower_be)
                
                # Upper breakeven: short_strike + max_profit_per_extra_short / extra_shorts
                extra_shorts = ratio - 1.0
                if extra_shorts > 0:
                    strike_diff = short_strike - long_strike
                    max_profit = net_credit + strike_diff
                    upper_be = short_strike + (max_profit / extra_shorts)
                    breakeven_points.append(upper_be)
                    
            else:  # put
                # Put ratio spread breakeven points
                # Upper breakeven: long_strike - net_credit
                upper_be = long_strike - net_credit
                breakeven_points.append(upper_be)
                
                # Lower breakeven: short_strike - max_profit_per_extra_short / extra_shorts
                extra_shorts = ratio - 1.0
                if extra_shorts > 0:
                    strike_diff = long_strike - short_strike
                    max_profit = net_credit + strike_diff
                    lower_be = short_strike - (max_profit / extra_shorts)
                    breakeven_points.append(lower_be)
            
            return sorted(breakeven_points)
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_calculate_breakeven_points'
            })
            return []
    
    def _determine_current_risk_zone(self, underlying_price: float, breakeven_points: List[float],
                                   max_profit_zone: Tuple[float, float],
                                   unlimited_risk_threshold: float) -> RiskZone:
        """
        Determine current risk zone based on underlying price.
        
        Args:
            underlying_price: Current underlying price
            breakeven_points: List of breakeven points
            max_profit_zone: Max profit zone boundaries
            unlimited_risk_threshold: Threshold for unlimited risk
            
        Returns:
            Current risk zone
        """
        try:
            # Check if in max profit zone
            if max_profit_zone[0] <= underlying_price <= max_profit_zone[1]:
                return RiskZone.SAFE_ZONE
            
            # Check distance to unlimited risk threshold
            risk_distance = abs(underlying_price - unlimited_risk_threshold) / underlying_price
            
            if risk_distance < 0.02:  # Within 2%
                return RiskZone.CRITICAL_ZONE
            elif risk_distance < 0.05:  # Within 5%
                return RiskZone.DANGER_ZONE
            elif risk_distance < 0.10:  # Within 10%
                return RiskZone.WARNING_ZONE
            else:
                return RiskZone.SAFE_ZONE
                
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_determine_current_risk_zone'
            })
            return RiskZone.SAFE_ZONE
    
    def _calculate_distance_to_danger(self, underlying_price: float,
                                    unlimited_risk_threshold: float) -> float:
        """
        Calculate distance to danger zone as percentage.
        
        Args:
            underlying_price: Current underlying price
            unlimited_risk_threshold: Threshold for unlimited risk
            
        Returns:
            Distance to danger zone (0.0 to 1.0)
        """
        try:
            if unlimited_risk_threshold <= 0:
                return 1.0
            
            distance = abs(underlying_price - unlimited_risk_threshold) / underlying_price
            return min(1.0, max(0.0, distance))
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_calculate_distance_to_danger'
            })
            return 0.5
    
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
    
    def _should_exit_position(self, position: RatioSpreadPosition,
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
            self._update_position_risk_zone(position, market_data)
            
            # Check profit target
            profit_target = position.net_credit * self.params['profit_target_percent']
            if position.current_pnl >= profit_target:
                return ExitReason.PROFIT_TARGET
            
            # Check stop loss
            stop_loss = position.net_credit * self.params['stop_loss_percent']
            if position.current_pnl <= -stop_loss:
                return ExitReason.STOP_LOSS
            
            # Check time-based exit
            days_held = (datetime.datetime.now() - position.entry_time).days
            if days_held >= self.params['max_days_held']:
                return ExitReason.TIME_DECAY
            
            # Check days to expiration
            days_to_exp = (position.expiration - datetime.datetime.now()).days
            if days_to_exp <= MIN_DAYS_TO_EXPIRY:
                return ExitReason.EXPIRATION
            
            # Check risk zone breach
            if position.risk_zone_data:
                if position.risk_zone_data.current_zone in [RiskZone.DANGER_ZONE, RiskZone.CRITICAL_ZONE]:
                    return ExitReason.RISK_ZONE_BREACH
            
            # Check Greeks risk thresholds
            greeks_risk = self._check_position_greeks_risk(position)
            if greeks_risk:
                return greeks_risk
            
            # Check underlying movement against position
            underlying_movement_risk = self._check_underlying_movement_risk(position, market_data)
            if underlying_movement_risk:
                return underlying_movement_risk
            
            # Check IV crush
            current_iv = market_data.get('iv', 0)
            if current_iv > 0 and position.entry_iv > 0:
                iv_change = (current_iv - position.entry_iv) / position.entry_iv
                if iv_change < -0.30:  # 30% IV crush
                    return ExitReason.IV_CRUSH
            
            return None
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_should_exit_position',
                'position_id': position.id
            })
            return ExitReason.RISK_MANAGEMENT
    
    def _check_position_greeks_risk(self, position: RatioSpreadPosition) -> Optional[ExitReason]:
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
    
    def _check_underlying_movement_risk(self, position: RatioSpreadPosition,
                                      market_data: Dict[str, Any]) -> Optional[ExitReason]:
        """
        Check if underlying price movement warrants exit.
        
        Args:
            position: Position to check
            market_data: Current market data
            
        Returns:
            Exit reason if movement risk detected, None otherwise
        """
        try:
            underlying_price = market_data.get('underlying_price', 0)
            if underlying_price <= 0:
                return None
            
            # Check against risk zone thresholds
            if position.risk_zone_data:
                threshold = position.risk_zone_data.unlimited_risk_threshold
                
                if position.ratio_type == RatioType.CALL_RATIO:
                    # For call ratios, risk increases significantly above short strike
                    if underlying_price > threshold:
                        return ExitReason.UNDERLYING_MOVEMENT
                else:  # PUT_RATIO
                    # For put ratios, risk increases significantly below short strike
                    if underlying_price < threshold:
                        return ExitReason.UNDERLYING_MOVEMENT
            
            return None
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_check_underlying_movement_risk'
            })
            return None
