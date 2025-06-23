#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD14_CalendarSpread.py
Group: D (Trading Strategies)
Purpose: Calendar Spread strategy implementation from LEAN algorithms

Description:
    Calendar Spread strategy implementation based on QuantConnect LEAN's
    LongAndShortPutCalendarSpreadStrategiesAlgorithm.py and 
    LongAndShortCallCalendarSpreadStrategiesAlgorithm.py. Features both
    put and call calendar spreads with professional validation and
    time decay optimization.

Key LEAN Features:
    - Put and Call Calendar Spreads
    - Near/Far expiry management
    - Time decay optimization
    - Volatility regime analysis
    - Professional position group validation

Based on: QuantConnect LEAN Calendar Spread Algorithms
Author: Mohamed Talib
Created: 2025-06-23
Version: 1.0 (New Strategy from LEAN)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
import itertools
from datetime import datetime, timedelta, time
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum, auto
import uuid

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy, StrategySignal, PositionType
from SpyderU_Utilities.SpyderU14_OptionStrategies import SpyderOptionStrategies, StrategyType, OptionStrategy, OptionRight
from SpyderB_Broker.SpyderB01_SpyderClient import get_ib_client
from SpyderB_Broker.SpyderB06_ContractBuilder import ContractBuilder
from SpyderC_MarketData.SpyderC03_OptionChain import OptionChainManager
from SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
from SpyderU_Utilities.SpyderU13_TechnicalIndicators import TechnicalIndicators
from SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import (
    CALENDAR_SPREAD_PROFIT_TARGET,
    CALENDAR_SPREAD_STOP_LOSS,
    SPY_CONTRACT_MULTIPLIER
)
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType

# ==============================================================================
# CONSTANTS (From LEAN Algorithms)
# ==============================================================================
# Calendar spread parameters (LEAN-inspired)
NEAR_EXPIRY_MIN_DAYS = 7      # Minimum days for near expiry
NEAR_EXPIRY_MAX_DAYS = 21     # Maximum days for near expiry
FAR_EXPIRY_MIN_DAYS = 28      # Minimum days for far expiry
FAR_EXPIRY_MAX_DAYS = 60      # Maximum days for far expiry

# Strike selection (LEAN pattern)
ATM_TOLERANCE = 2.0           # Strikes within $2 of ATM
MIN_STRIKE_DISTANCE = 5.0     # Minimum distance between strikes

# Time decay parameters
THETA_ACCELERATION_DAYS = 14  # Days when theta accelerates
VEGA_SENSITIVITY_THRESHOLD = 0.1  # Vega sensitivity threshold

# Position management
MAX_CALENDAR_POSITIONS = 3
CALENDAR_PROFIT_TARGET = 0.25  # 25% profit target
CALENDAR_STOP_LOSS = 0.50     # 50% stop loss
EARLY_CLOSE_DAYS = 3          # Close 3 days before near expiry

# Volatility requirements
MIN_IV_RANK = 30              # Minimum IV rank for entry
MAX_IV_SKEW = 0.15           # Maximum IV skew between expiries

# ==============================================================================
# ENUMERATIONS
# ==============================================================================
class CalendarSpreadType(Enum):
    """Calendar spread types (from LEAN algorithms)"""
    PUT_CALENDAR = "put_calendar"              # Long Put Calendar
    CALL_CALENDAR = "call_calendar"            # Long Call Calendar
    SHORT_PUT_CALENDAR = "short_put_calendar"  # Short Put Calendar
    SHORT_CALL_CALENDAR = "short_call_calendar" # Short Call Calendar
    DIAGONAL_PUT = "diagonal_put"              # Diagonal Put Spread
    DIAGONAL_CALL = "diagonal_call"            # Diagonal Call Spread

class CalendarState(Enum):
    """Calendar spread position states"""
    SCANNING = "scanning"
    VALIDATING_EXPIRIES = "validating_expiries"
    PENDING_ENTRY = "pending_entry"
    ACTIVE = "active"
    NEAR_EXPIRY_WARNING = "near_expiry_warning"
    CLOSING = "closing"
    CLOSED = "closed"
    NEAR_EXPIRED = "near_expired"
    ERROR = "error"

class VolatilityRegime(Enum):
    """Volatility regime classification"""
    LOW = "low"           # Favorable for calendar spreads
    NORMAL = "normal"     # Neutral
    HIGH = "high"         # Unfavorable for calendar spreads
    EXTREME = "extreme"   # Avoid calendar spreads

# ==============================================================================
# DATA STRUCTURES (LEAN-Inspired)
# ==============================================================================
@dataclass
class CalendarSpreadLegs:
    """Calendar spread legs (from LEAN's calendar spread algorithms)"""
    # Contract details
    underlying_symbol: str
    strike: float
    option_right: OptionRight
    
    # Expiry management (LEAN pattern)
    near_expiry: datetime
    far_expiry: datetime
    
    # Time parameters
    near_dte: int = 0
    far_dte: int = 0
    time_spread: int = 0  # Days between expiries
    
    # Market data
    near_price: float = 0.0
    far_price: float = 0.0
    net_debit: float = 0.0  # Far premium - Near premium
    
    # Greeks differential
    delta_diff: float = 0.0
    theta_diff: float = 0.0
    vega_diff: float = 0.0
    
    # Volatility analysis
    near_iv: float = 0.0
    far_iv: float = 0.0
    iv_skew: float = 0.0
    
    # Quality metrics
    setup_quality: float = 0.0
    validation_errors: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate derived fields (LEAN-style)"""
        self._calculate_time_metrics()
        self._calculate_iv_skew()
        self._validate_expiry_order()
    
    def _calculate_time_metrics(self):
        """Calculate time-related metrics"""
        now = datetime.now()
        self.near_dte = (self.near_expiry - now).days
        self.far_dte = (self.far_expiry - now).days
        self.time_spread = self.far_dte - self.near_dte
    
    def _calculate_iv_skew(self):
        """Calculate IV skew between expiries"""
        if self.near_iv > 0 and self.far_iv > 0:
            self.iv_skew = abs(self.far_iv - self.near_iv) / self.near_iv
    
    def _validate_expiry_order(self):
        """Validate expiry order (LEAN pattern)"""
        if self.near_expiry >= self.far_expiry:
            self.validation_errors.append("Near expiry must be before far expiry")
        
        if self.near_dte < NEAR_EXPIRY_MIN_DAYS:
            self.validation_errors.append(f"Near expiry too close: {self.near_dte} < {NEAR_EXPIRY_MIN_DAYS}")
        
        if self.far_dte > FAR_EXPIRY_MAX_DAYS:
            self.validation_errors.append(f"Far expiry too distant: {self.far_dte} > {FAR_EXPIRY_MAX_DAYS}")
        
        if self.time_spread < 7:
            self.validation_errors.append(f"Insufficient time spread: {self.time_spread} < 7 days")

@dataclass
class CalendarSpreadPosition:
    """Calendar spread position tracking (LEAN-inspired)"""
    position_id: str
    spread_type: CalendarSpreadType
    legs: CalendarSpreadLegs
    strategy: OptionStrategy
    
    # Execution details
    entry_time: datetime
    entry_debit: float
    quantity: int
    
    # Position tracking
    state: CalendarState
    current_value: float = 0.0
    unrealized_pnl: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    
    # Time decay tracking
    theta_pnl: float = 0.0
    vega_pnl: float = 0.0
    
    # Near expiry management
    near_expiry_warned: bool = False
    days_to_near_expiry: int = 0
    
    def update_metrics(self, market_data: Dict[str, Any]):
        """Update position metrics"""
        # Calculate days to near expiry
        self.days_to_near_expiry = (self.legs.near_expiry - datetime.now()).days
        
        # Update P&L (simplified)
        if self.entry_debit > 0:
            self.unrealized_pnl = (self.current_value - self.entry_debit) * self.quantity * 100
            self.max_profit = max(self.max_profit, self.unrealized_pnl)
            self.max_loss = min(self.max_loss, self.unrealized_pnl)
        
        # Check for near expiry warning
        if self.days_to_near_expiry <= EARLY_CLOSE_DAYS and not self.near_expiry_warned:
            self.state = CalendarState.NEAR_EXPIRY_WARNING
            self.near_expiry_warned = True

# ==============================================================================
# MAIN CALENDAR SPREAD STRATEGY CLASS
# ==============================================================================
class CalendarSpreadStrategy(BaseStrategy):
    """
    Calendar Spread strategy implementation from LEAN algorithms.
    
    Key Features (from LEAN):
    - Put and Call Calendar Spreads
    - Professional expiry management
    - Time decay optimization
    - Volatility regime analysis
    - Position group validation
    
    Based on LEAN's LongAndShortPutCalendarSpreadStrategiesAlgorithm.py
    and LongAndShortCallCalendarSpreadStrategiesAlgorithm.py
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Calendar Spread strategy"""
        super().__init__("CalendarSpread", config)
        
        # Initialize components
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.ib_client = get_ib_client()
        self.option_chain_manager = OptionChainManager()
        self.greeks_calculator = GreeksCalculator()
        self.risk_manager = get_risk_manager()
        self.event_manager = get_event_manager()
        self.indicators = TechnicalIndicators()
        
        # Calendar spread configuration
        self.max_positions = config.get("max_positions", MAX_CALENDAR_POSITIONS)
        self.profit_target = config.get("profit_target", CALENDAR_PROFIT_TARGET)
        self.stop_loss = config.get("stop_loss", CALENDAR_STOP_LOSS)
        self.min_iv_rank = config.get("min_iv_rank", MIN_IV_RANK)
        
        # Position tracking
        self.active_positions: Dict[str, CalendarSpreadPosition] = {}
        self.pending_entries: Dict[str, CalendarSpreadLegs] = {}
        
        # Performance tracking
        self.strategy_stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'total_pnl': 0.0,
            'theta_pnl': 0.0,
            'vega_pnl': 0.0,
            'near_expiry_closures': 0
        }
        
        self.logger.info("Calendar Spread strategy initialized with LEAN patterns")
    
    # ==========================================================================
    # LEAN ALGORITHM PATTERNS - Market Analysis
    # ==========================================================================
    def analyze_market(self, market_data: Dict[str, Any]) -> StrategySignal:
        """
        Analyze market for Calendar Spread opportunities using LEAN patterns.
        
        From LEAN LongAndShortPutCalendarSpreadStrategiesAlgorithm:
        - Group contracts by strike
        - Sort by expiry
        - Select near and far expiries
        - Validate contract pairs
        """
        try:
            # Check market conditions
            if not self._should_analyze_calendar_spreads(market_data):
                return StrategySignal.NO_SIGNAL
            
            # Get option chain
            option_chain = market_data.get('option_chain', [])
            underlying_price = market_data.get('underlying_price', 0.0)
            
            if not option_chain or underlying_price <= 0:
                return StrategySignal.NO_SIGNAL
            
            # LEAN Pattern: Group by strike, then by expiry
            opportunities = self._find_calendar_opportunities_lean_style(option_chain, underlying_price)
            
            if opportunities:
                # Select best opportunity
                best_opportunity = self._select_best_calendar_opportunity(opportunities, market_data)
                
                if best_opportunity and self._validate_calendar_setup(best_opportunity):
                    return self._create_calendar_signal(best_opportunity, market_data)
            
            return StrategySignal.NO_SIGNAL
            
        except Exception as e:
            self.logger.error(f"Calendar spread market analysis failed: {e}")
            return StrategySignal.NO_SIGNAL
    
    def _find_calendar_opportunities_lean_style(self, option_chain: List[Any], 
                                               underlying_price: float) -> List[CalendarSpreadLegs]:
        """
        Find calendar opportunities using LEAN's grouping pattern.
        
        From LEAN: "for strike, group in itertools.groupby(put_contracts, lambda x: x.strike)"
        """
        opportunities = []
        
        try:
            # Separate puts and calls
            put_contracts = [c for c in option_chain if c.option_right == "PUT"]
            call_contracts = [c for c in option_chain if c.option_right == "CALL"]
            
            # Process puts (LEAN pattern)
            put_opportunities = self._process_contracts_by_strike(
                put_contracts, underlying_price, OptionRight.PUT
            )
            opportunities.extend(put_opportunities)
            
            # Process calls (LEAN pattern)
            call_opportunities = self._process_contracts_by_strike(
                call_contracts, underlying_price, OptionRight.CALL
            )
            opportunities.extend(call_opportunities)
            
            self.logger.debug(f"Found {len(opportunities)} calendar opportunities")
            return opportunities
            
        except Exception as e:
            self.logger.error(f"Error finding calendar opportunities: {e}")
            return []
    
    def _process_contracts_by_strike(self, contracts: List[Any], 
                                   underlying_price: float, 
                                   option_right: OptionRight) -> List[CalendarSpreadLegs]:
        """
        Process contracts by strike (LEAN's groupby pattern).
        
        From LEAN: Group by strike, sort by expiry, select near/far
        """
        opportunities = []
        
        # Sort contracts by strike distance from ATM
        atm_contracts = sorted(contracts, key=lambda x: abs(x.strike - underlying_price))
        
        # LEAN Pattern: Group by strike
        for strike, group in itertools.groupby(atm_contracts, lambda x: x.strike):
            contracts_at_strike = sorted(group, key=lambda x: x.expiry)
            
            # LEAN Pattern: Need at least 2 contracts (near and far)
            if len(contracts_at_strike) < 2:
                continue
            
            # Skip if too far from ATM
            if abs(strike - underlying_price) > ATM_TOLERANCE:
                continue
            
            # Select near and far expiries (LEAN pattern)
            near_contract = contracts_at_strike[0]
            far_contract = contracts_at_strike[1]
            
            # Create calendar spread setup
            calendar_legs = CalendarSpreadLegs(
                underlying_symbol="SPY",
                strike=strike,
                option_right=option_right,
                near_expiry=near_contract.expiry,
                far_expiry=far_contract.expiry,
                near_price=getattr(near_contract, 'mid_price', 0.0),
                far_price=getattr(far_contract, 'mid_price', 0.0),
                near_iv=getattr(near_contract, 'implied_volatility', 0.0),
                far_iv=getattr(far_contract, 'implied_volatility', 0.0)
            )
            
            # Calculate net debit (buy far, sell near)
            calendar_legs.net_debit = calendar_legs.far_price - calendar_legs.near_price
            
            opportunities.append(calendar_legs)
        
        return opportunities
    
    def _select_best_calendar_opportunity(self, opportunities: List[CalendarSpreadLegs],
                                        market_data: Dict[str, Any]) -> Optional[CalendarSpreadLegs]:
        """Select best calendar opportunity based on quality metrics"""
        if not opportunities:
            return None
        
        # Score each opportunity
        for opportunity in opportunities:
            score = 0.0
            
            # Time spread quality (prefer 3-4 weeks between expiries)
            ideal_time_spread = 28  # 4 weeks
            time_spread_score = 1.0 - abs(opportunity.time_spread - ideal_time_spread) / ideal_time_spread
            score += time_spread_score * 5
            
            # IV skew (prefer low skew)
            if opportunity.iv_skew > 0:
                skew_score = max(0, 1.0 - opportunity.iv_skew / MAX_IV_SKEW)
                score += skew_score * 3
            
            # Debit reasonableness (prefer reasonable cost)
            if opportunity.net_debit > 0:
                debit_ratio = opportunity.net_debit / opportunity.strike
                if 0.01 <= debit_ratio <= 0.05:  # 1-5% of strike
                    score += 3
            
            # Time decay potential
            if opportunity.near_dte <= THETA_ACCELERATION_DAYS:
                score += 2  # Theta acceleration bonus
            
            # Distance from ATM (prefer ATM for calendars)
            underlying_price = market_data.get('underlying_price', 0)
            if underlying_price > 0:
                atm_distance = abs(opportunity.strike - underlying_price) / underlying_price
                atm_score = max(0, 1.0 - atm_distance / 0.02)  # Within 2%
                score += atm_score * 4
            
            opportunity.setup_quality = score
        
        # Return best scoring opportunity
        best = max(opportunities, key=lambda x: x.setup_quality)
        
        self.logger.info(f"Selected best calendar: {best.option_right.value} "
                        f"strike {best.strike} quality {best.setup_quality:.2f}")
        
        return best
    
    def _validate_calendar_setup(self, legs: CalendarSpreadLegs) -> bool:
        """Validate calendar setup (LEAN-style validation)"""
        if legs.validation_errors:
            self.logger.warning(f"Calendar validation failed: {legs.validation_errors}")
            return False
        
        # Check position limits
        if len(self.active_positions) >= self.max_positions:
            self.logger.warning("Maximum calendar positions reached")
            return False
        
        # Net debit validation
        if legs.net_debit <= 0:
            self.logger.warning("Invalid net debit for calendar spread")
            return False
        
        # Quality threshold
        if legs.setup_quality < 5.0:
            self.logger.warning(f"Calendar setup quality too low: {legs.setup_quality}")
            return False
        
        return True
    
    # ==========================================================================
    # LEAN ALGORITHM PATTERNS - Strategy Execution
    # ==========================================================================
    def execute_signal(self, signal: StrategySignal) -> bool:
        """
        Execute calendar spread using LEAN patterns.
        
        From LEAN: Create calendar spread strategy and buy it
        """
        try:
            legs = signal.metadata.get('calendar_legs')
            if not legs:
                self.logger.error("No calendar legs in signal")
                return False
            
            # Create LEAN-style calendar spread strategy
            if legs.option_right == OptionRight.PUT:
                strategy = SpyderOptionStrategies.put_calendar_spread(
                    underlying_symbol=legs.underlying_symbol,
                    strike=legs.strike,
                    near_expiry=legs.near_expiry,
                    far_expiry=legs.far_expiry,
                    quantity=1
                )
                spread_type = CalendarSpreadType.PUT_CALENDAR
            else:
                strategy = SpyderOptionStrategies.call_calendar_spread(
                    underlying_symbol=legs.underlying_symbol,
                    strike=legs.strike,
                    near_expiry=legs.near_expiry,
                    far_expiry=legs.far_expiry,
                    quantity=1
                )
                spread_type = CalendarSpreadType.CALL_CALENDAR
            
            # Validate strategy
            SpyderOptionStrategies.validate_strategy_legs(strategy)
            
            # Execute strategy
            execution_result = self._execute_calendar_strategy(strategy, legs)
            
            if execution_result['success']:
                # Create position tracking
                position = CalendarSpreadPosition(
                    position_id=f"CAL_{uuid.uuid4().hex[:8]}",
                    spread_type=spread_type,
                    legs=legs,
                    strategy=strategy,
                    entry_time=datetime.now(),
                    entry_debit=legs.net_debit,
                    quantity=1,
                    state=CalendarState.ACTIVE
                )
                
                # Store position
                self.active_positions[position.position_id] = position
                self.strategy_stats['total_trades'] += 1
                
                self.logger.info(f"Calendar spread executed: {position.position_id}")
                return True
            else:
                self.logger.error(f"Calendar execution failed: {execution_result['error']}")
                return False
                
        except Exception as e:
            self.logger.error(f"Calendar signal execution failed: {e}")
            return False
    
    def _execute_calendar_strategy(self, strategy: OptionStrategy, 
                                 legs: CalendarSpreadLegs) -> Dict[str, Any]:
        """Execute calendar strategy (mock implementation)"""
        try:
            # Mock execution - would integrate with broker
            return {
                'success': True,
                'entry_debit': legs.net_debit,
                'near_leg_price': legs.near_price,
                'far_leg_price': legs.far_price,
                'order_id': f"CAL_{uuid.uuid4().hex[:8]}"
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # ==========================================================================
    # LEAN ALGORITHM PATTERNS - Position Management
    # ==========================================================================
    def manage_positions(self) -> List[Dict[str, Any]]:
        """
        Manage calendar positions with LEAN expiry patterns.
        
        From LEAN: Monitor near expiry and manage accordingly
        """
        management_actions = []
        
        for position_id, position in self.active_positions.items():
            try:
                # Update position metrics
                position.update_metrics({})  # Would pass real market data
                
                # Check for management actions
                action = self._check_calendar_management(position)
                if action:
                    management_actions.append(action)
                    
            except Exception as e:
                self.logger.error(f"Calendar position management failed for {position_id}: {e}")
        
        return management_actions
    
    def _check_calendar_management(self, position: CalendarSpreadPosition) -> Optional[Dict[str, Any]]:
        """Check if calendar position needs management"""
        # Profit target check
        if position.unrealized_pnl >= (position.entry_debit * self.profit_target * 100):
            return {
                'action': 'CLOSE_PROFITABLE',
                'position_id': position.position_id,
                'pnl': position.unrealized_pnl,
                'reason': 'Profit target reached'
            }
        
        # Stop loss check
        if position.unrealized_pnl <= -(position.entry_debit * self.stop_loss * 100):
            return {
                'action': 'CLOSE_LOSS',
                'position_id': position.position_id,
                'pnl': position.unrealized_pnl,
                'reason': 'Stop loss triggered'
            }
        
        # Near expiry management (LEAN pattern)
        if position.days_to_near_expiry <= EARLY_CLOSE_DAYS:
            return {
                'action': 'CLOSE_NEAR_EXPIRY',
                'position_id': position.position_id,
                'pnl': position.unrealized_pnl,
                'reason': f'Near expiry in {position.days_to_near_expiry} days'
            }
        
        return None
    
    def liquidate_calendar_strategy(self, position: CalendarSpreadPosition) -> bool:
        """
        Liquidate calendar strategy (from LEAN's liquidation pattern).
        
        From LEAN: "We should be able to close the position using the inverse strategy"
        """
        try:
            # Create inverse strategy for liquidation (LEAN pattern)
            if position.spread_type == CalendarSpreadType.PUT_CALENDAR:
                inverse_strategy = SpyderOptionStrategies.short_put_calendar_spread(
                    underlying_symbol=position.legs.underlying_symbol,
                    strike=position.legs.strike,
                    near_expiry=position.legs.near_expiry,
                    far_expiry=position.legs.far_expiry,
                    quantity=1
                )
            else:  # CALL_CALENDAR
                inverse_strategy = SpyderOptionStrategies.short_call_calendar_spread(
                    underlying_symbol=position.legs.underlying_symbol,
                    strike=position.legs.strike,
                    near_expiry=position.legs.near_expiry,
                    far_expiry=position.legs.far_expiry,
                    quantity=1
                )
            
            # Execute liquidation
            success = self._execute_liquidation(inverse_strategy, position)
            
            if success:
                position.state = CalendarState.CLOSED
                self.strategy_stats['total_pnl'] += position.unrealized_pnl
                if position.unrealized_pnl > 0:
                    self.strategy_stats['winning_trades'] += 1
                
                self.logger.info(f"Calendar position liquidated: {position.position_id}")
                return True
            else:
                self.logger.error(f"Failed to liquidate calendar position: {position.position_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Calendar liquidation failed: {e}")
            return False
    
    def _execute_liquidation(self, inverse_strategy: OptionStrategy, 
                           position: CalendarSpreadPosition) -> bool:
        """Execute liquidation (mock implementation)"""
        # Would execute the inverse strategy to close position
        return True
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _should_analyze_calendar_spreads(self, market_data: Dict[str, Any]) -> bool:
        """Check if market conditions favor calendar spreads"""
        # Check volatility regime
        iv_rank = market_data.get('iv_rank', 0)
        if iv_rank < self.min_iv_rank:
            return False
        
        # Check position capacity
        if len(self.active_positions) >= self.max_positions:
            return False
        
        # Check market trend (calendars prefer sideways markets)
        trend_strength = market_data.get('trend_strength', 0.5)
        if trend_strength > 0.8:  # Strong trending market
            return False
        
        return True
    
    def _create_calendar_signal(self, legs: CalendarSpreadLegs, 
                              market_data: Dict[str, Any]) -> StrategySignal:
        """Create calendar spread signal"""
        return StrategySignal(
            signal_type="ENTRY",
            strategy_name="CalendarSpread",
            confidence=legs.setup_quality / 10.0,
            timestamp=datetime.now(),
            metadata={
                'calendar_legs': legs,
                'spread_type': f"{legs.option_right.value}_calendar",
                'net_debit': legs.net_debit,
                'time_spread': legs.time_spread
            }
        )
    
    def get_strategy_statistics(self) -> Dict[str, Any]:
        """Get comprehensive calendar strategy statistics"""
        active_count = len(self.active_positions)
        total_unrealized = sum(pos.unrealized_pnl for pos in self.active_positions.values())
        
        return {
            **self.strategy_stats,
            'active_positions': active_count,
            'total_unrealized_pnl': total_unrealized,
            'win_rate': (self.strategy_stats['winning_trades'] / 
                        max(1, self.strategy_stats['total_trades'])),
            'avg_pnl_per_trade': (self.strategy_stats['total_pnl'] / 
                                 max(1, self.strategy_stats['total_trades'])),
            'theta_contribution': self.strategy_stats['theta_pnl'],
            'vega_contribution': self.strategy_stats['vega_pnl']
        }

# ==============================================================================
# LEAN-STYLE POSITION GROUP VALIDATION
# ==============================================================================
def validate_calendar_position_group(position: CalendarSpreadPosition) -> bool:
    """
    Validate calendar position group (from LEAN's assert_strategy_position_group).
    
    From LEAN Calendar algorithms: Validate 2 legs with opposite quantities
    """
    try:
        # Should have exactly 2 positions (near and far)
        if len(position.strategy.legs) != 2:
            raise AssertionError(f"Expected calendar to have 2 legs. Actual: {len(position.strategy.legs)}")
        
        leg1, leg2 = position.strategy.legs
        
        # Should be same strike and option type
        if leg1.strike != leg2.strike:
            raise AssertionError(f"Calendar legs must have same strike. Got: {leg1.strike}, {leg2.strike}")
        
        if leg1.option_right != leg2.option_right:
            raise AssertionError(f"Calendar legs must be same option type. Got: {leg1.option_right}, {leg2.option_right}")
        
        # Should have opposite quantities (one long, one short)
        if leg1.quantity * leg2.quantity >= 0:
            raise AssertionError(f"Calendar legs must have opposite quantities. Got: {leg1.quantity}, {leg2.quantity}")
        
        # Near expiry leg should be short, far expiry leg should be long
        near_leg = leg1 if leg1.expiry == position.legs.near_expiry else leg2
        far_leg = leg2 if leg2.expiry == position.legs.far_expiry else leg1
        
        if near_leg.quantity >= 0:
            raise AssertionError(f"Near expiry leg should be short. Actual quantity: {near_leg.quantity}")
        
        if far_leg.quantity <= 0:
            raise AssertionError(f"Far expiry leg should be long. Actual quantity: {far_leg.quantity}")
        
        return True
        
    except AssertionError as e:
        logging.error(f"Calendar position group validation failed: {e}")
        raise

# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================
def create_spy_put_calendar(strike: float, near_days: int, far_days: int) -> OptionStrategy:
    """Quick SPY Put Calendar creation"""
    near_expiry = datetime.now() + timedelta(days=near_days)
    far_expiry = datetime.now() + timedelta(days=far_days)
    
    return SpyderOptionStrategies.put_calendar_spread("SPY", strike, near_expiry, far_expiry)

def create_spy_call_calendar(strike: float, near_days: int, far_days: int) -> OptionStrategy:
    """Quick SPY Call Calendar creation"""
    near_expiry = datetime.now() + timedelta(days=near_days)
    far_expiry = datetime.now() + timedelta(days=far_days)
    
    return SpyderOptionStrategies.call_calendar_spread("SPY", strike, near_expiry, far_expiry)

def analyze_calendar_opportunity(underlying_price: float, strike: float, 
                               near_iv: float, far_iv: float) -> Dict[str, Any]:
    """Analyze calendar opportunity quality"""
    # Distance from ATM
    atm_distance = abs(strike - underlying_price) / underlying_price
    
    # IV skew analysis
    iv_skew = abs(far_iv - near_iv) / near_iv if near_iv > 0 else 0
    
    # Quality assessment
    quality_score = 0.0
    
    # ATM bonus
    if atm_distance <= 0.01:  # Within 1%
        quality_score += 5.0
    elif atm_distance <= 0.02:  # Within 2%
        quality_score += 3.0
    
    # Low skew bonus
    if iv_skew <= 0.05:  # Low skew
        quality_score += 3.0
    elif iv_skew <= 0.10:  # Moderate skew
        quality_score += 1.0
    
    return {
        'quality_score': quality_score,
        'atm_distance_pct': atm_distance * 100,
        'iv_skew_pct': iv_skew * 100,
        'recommendation': 'EXCELLENT' if quality_score >= 7 else 
                         'GOOD' if quality_score >= 5 else 
                         'FAIR' if quality_score >= 3 else 'POOR'
    }

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test Calendar Spread strategy with LEAN patterns
    config = {
        'max_positions': 3,
        'profit_target': 0.25,
        'stop_loss': 0.50,
        'min_iv_rank': 30
    }
    
    strategy = CalendarSpreadStrategy(config)
    
    print("Testing Calendar Spread Strategy with LEAN Patterns:")
    print("=" * 55)
    
    # Test opportunity analysis
    analysis = analyze_calendar_opportunity(
        underlying_price=600.0,
        strike=600.0,
        near_iv=0.20,
        far_iv=0.22
    )
    print(f"Calendar opportunity analysis: {analysis}")
    
    # Test strategy creation
    put_calendar = create_spy_put_calendar(strike=600.0, near_days=14, far_days=42)
    call_calendar = create_spy_call_calendar(strike=600.0, near_days=14, far_days=42)
    
    print(f"Put calendar created: {put_calendar.strategy_type}")
    print(f"Call calendar created: {call_calendar.strategy_type}")
    
    # Test statistics
    stats = strategy.get_strategy_statistics()
    print(f"Strategy statistics: {stats}")
    
    print("\n✅ Calendar Spread strategy with LEAN patterns ready!")
    print("Key LEAN features:")
    print("- Put and Call Calendar Spreads")
    print("- Near/Far expiry management")
    print("- Time decay optimization")
    print("- Professional position group validation")
    print("- IV skew analysis")
    print("- Automated liquidation using inverse strategies")