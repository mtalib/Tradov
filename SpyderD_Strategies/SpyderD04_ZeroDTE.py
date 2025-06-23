#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD04_ZeroDTE.py
Group: D (Trading Strategies)
Purpose: Enhanced 0DTE strategy with LEAN algorithm patterns

Description:
    Enhanced Zero Days to Expiration (0DTE) options strategy using patterns from
    QuantConnect LEAN's IndexOptionShortPutOTMExpiryRegressionAlgorithm.py and
    similar algorithms. Features precise expiry filtering, scheduled entry timing,
    OTM strike selection, and professional expiry management.

Key LEAN Enhancements:
    - Precise expiry filtering by exact date (same day)
    - Scheduled entry timing (1 minute after market open like LEAN)
    - OTM strike selection logic from LEAN algorithms
    - Automated expiry management and delisting handling
    - Professional validation and error handling

Based on: QuantConnect LEAN IndexOptionShortPutOTMExpiryRegressionAlgorithm.py
Author: Mohamed Talib
Created: 2025-06-23
Version: 3.0 (Enhanced with LEAN patterns)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
from datetime import datetime, time, timedelta, date
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
import uuid
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
import pytz

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy, StrategySignal, PositionType
from SpyderU_Utilities.SpyderU14_OptionStrategies import SpyderOptionStrategies, StrategyType, OptionStrategy, OptionRight
from SpyderB_Broker.SpyderB01_SpyderClient import get_ib_client
from SpyderA_Core.SpyderA04_Scheduler import get_scheduler
from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar
from SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
from SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import (
    ZERO_DTE_PROFIT_TARGET,
    ZERO_DTE_MAX_TRADES,
    ZERO_DTE_TIME_DECAY_MULTIPLIER
)
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType

# ==============================================================================
# CONSTANTS (Enhanced with LEAN patterns)
# ==============================================================================
# LEAN-inspired 0DTE parameters
LEAN_ENTRY_DELAY_MINUTES = 1  # From LEAN: "after_market_open(self.spx, 1)"
OPTIMAL_ENTRY_TIME = time(9, 31)  # 9:31 AM ET (1 min after market open)
LEAN_LIQUIDATION_TIME = time(15, 45)  # 15 minutes before close
EXPIRY_CHECK_TIME = time(16, 0)  # Market close for expiry validation

# LEAN OTM thresholds (from IndexOptionShortPutOTMExpiryRegressionAlgorithm)
OTM_PUT_THRESHOLD = 0.95  # Puts: strike <= 95% of underlying
OTM_CALL_THRESHOLD = 1.05  # Calls: strike >= 105% of underlying

# Strategy parameters
MAX_0DTE_POSITIONS = 2
MIN_TIME_TO_EXPIRY_HOURS = 1.0  # Minimum 1 hour to expiry
PROFIT_TARGET_FAST = 0.25  # 25% quick profit target
STOP_LOSS_TIGHT = 0.50  # 50% stop loss for 0DTE

# Volume and liquidity requirements
MIN_0DTE_VOLUME = 1000
MIN_0DTE_OPEN_INTEREST = 5000
MIN_BID_ASK_SPREAD = 0.05

# ==============================================================================
# ENHANCED ENUMERATIONS
# ==============================================================================
class ZeroDTEState(Enum):
    """0DTE position states (LEAN-inspired)"""
    SCANNING = "scanning"
    WAITING_FOR_ENTRY = "waiting_for_entry"  # LEAN: scheduled entry
    VALIDATING_EXPIRY = "validating_expiry"  # LEAN: expiry validation
    ACTIVE = "active"
    MONITORING_EXPIRY = "monitoring_expiry"  # LEAN: delisting monitoring
    EXPIRED_OTM = "expired_otm"  # LEAN: OTM expiry handling
    LIQUIDATED = "liquidated"
    ERROR = "error"

class ZeroDTEStrategy(Enum):
    """0DTE strategy types (from LEAN examples)"""
    SHORT_OTM_PUT = "short_otm_put"  # From IndexOptionShortPutOTMExpiryRegressionAlgorithm
    SHORT_OTM_CALL = "short_otm_call"  # From IndexOptionShortCallOTMExpiryRegressionAlgorithm
    IRON_BUTTERFLY = "iron_butterfly_0dte"
    SHORT_STRADDLE = "short_straddle_0dte"
    SCALP_LONG = "scalp_long_0dte"

class LEANExpiryStatus(Enum):
    """Expiry status tracking (LEAN-inspired)"""
    VALID = "valid"
    EXPIRING_TODAY = "expiring_today"
    EXPIRED_ITM = "expired_itm"
    EXPIRED_OTM = "expired_otm"
    DELISTING_WARNING = "delisting_warning"

# ==============================================================================
# ENHANCED DATA STRUCTURES
# ==============================================================================
@dataclass
class LEANZeroDTESetup:
    """Enhanced 0DTE setup with LEAN patterns"""
    strategy_type: ZeroDTEStrategy
    underlying_symbol: str
    underlying_price: float
    
    # Contract details (LEAN-style)
    selected_strike: float
    option_right: OptionRight
    expiry: datetime
    
    # Entry timing (LEAN pattern)
    scheduled_entry_time: datetime
    market_open_time: datetime
    
    # Risk parameters
    entry_price_estimate: float
    profit_target: float
    stop_loss: float
    max_loss: float
    
    # LEAN validation fields
    is_otm: bool = False
    otm_percentage: float = 0.0
    time_to_expiry_hours: float = 0.0
    expected_contract_symbol: str = ""
    
    # Liquidity validation
    volume: int = 0
    open_interest: int = 0
    bid_ask_spread: float = 0.0
    
    # Quality assessment
    setup_quality: float = 0.0
    validation_errors: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate derived fields (LEAN-style)"""
        self._calculate_otm_status()
        self._calculate_time_to_expiry()
        self._generate_expected_symbol()
        self._validate_lean_requirements()
    
    def _calculate_otm_status(self):
        """Calculate OTM status (from LEAN algorithms)"""
        if self.option_right == OptionRight.PUT:
            self.is_otm = self.selected_strike <= (self.underlying_price * OTM_PUT_THRESHOLD)
            self.otm_percentage = (self.underlying_price - self.selected_strike) / self.underlying_price
        else:  # CALL
            self.is_otm = self.selected_strike >= (self.underlying_price * OTM_CALL_THRESHOLD)
            self.otm_percentage = (self.selected_strike - self.underlying_price) / self.underlying_price
    
    def _calculate_time_to_expiry(self):
        """Calculate time to expiry in hours"""
        now = datetime.now()
        if self.expiry > now:
            delta = self.expiry - now
            self.time_to_expiry_hours = delta.total_seconds() / 3600
        else:
            self.time_to_expiry_hours = 0.0
    
    def _generate_expected_symbol(self):
        """Generate expected contract symbol (LEAN pattern)"""
        # Format: SPY_YYMMDD_C/P_STRIKE
        expiry_str = self.expiry.strftime("%y%m%d")
        right_str = "C" if self.option_right == OptionRight.CALL else "P"
        self.expected_contract_symbol = f"{self.underlying_symbol}_{expiry_str}_{right_str}_{self.selected_strike:08.0f}"
    
    def _validate_lean_requirements(self):
        """Validate LEAN-specific requirements"""
        # Must be same-day expiry
        if self.expiry.date() != datetime.now().date():
            self.validation_errors.append("Not a same-day expiry (0DTE)")
        
        # Must be OTM
        if not self.is_otm:
            self.validation_errors.append("Option is not Out-of-The-Money")
        
        # Minimum time to expiry
        if self.time_to_expiry_hours < MIN_TIME_TO_EXPIRY_HOURS:
            self.validation_errors.append(f"Insufficient time to expiry: {self.time_to_expiry_hours:.1f}h < {MIN_TIME_TO_EXPIRY_HOURS}h")
        
        # Liquidity requirements
        if self.volume < MIN_0DTE_VOLUME:
            self.validation_errors.append(f"Insufficient volume: {self.volume} < {MIN_0DTE_VOLUME}")
        
        if self.open_interest < MIN_0DTE_OPEN_INTEREST:
            self.validation_errors.append(f"Insufficient open interest: {self.open_interest} < {MIN_0DTE_OPEN_INTEREST}")

@dataclass
class LEANZeroDTEPosition:
    """LEAN-style 0DTE position tracking"""
    position_id: str
    setup: LEANZeroDTESetup
    strategy: OptionStrategy
    
    # Execution details
    entry_time: datetime
    entry_price: float
    quantity: int
    
    # Current status
    state: ZeroDTEState
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    
    # Expiry tracking (LEAN pattern)
    expiry_status: LEANExpiryStatus = LEANExpiryStatus.VALID
    delisting_warned: bool = False
    
    # Performance metrics
    max_profit: float = 0.0
    max_loss: float = 0.0
    time_in_position: float = 0.0
    
    def update_metrics(self):
        """Update position metrics"""
        if self.entry_price > 0:
            self.unrealized_pnl = (self.current_price - self.entry_price) * self.quantity * 100
            self.max_profit = max(self.max_profit, self.unrealized_pnl)
            self.max_loss = min(self.max_loss, self.unrealized_pnl)
        
        # Update time in position
        self.time_in_position = (datetime.now() - self.entry_time).total_seconds() / 3600

# ==============================================================================
# ENHANCED ZERO DTE STRATEGY CLASS
# ==============================================================================
class EnhancedZeroDTEStrategy(BaseStrategy):
    """
    Enhanced 0DTE strategy with LEAN algorithm patterns.
    
    Key LEAN Enhancements:
    - Precise same-day expiry filtering
    - Scheduled entry timing (1 minute after market open)
    - OTM strike selection from LEAN algorithms
    - Automated expiry and delisting monitoring
    - Professional validation and error handling
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Enhanced 0DTE strategy"""
        super().__init__("Enhanced0DTE", config)
        
        # Initialize components
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.ib_client = get_ib_client()
        self.scheduler = get_scheduler()
        self.trading_calendar = TradingCalendar()
        self.risk_manager = get_risk_manager()
        self.greeks_calculator = GreeksCalculator()
        self.event_manager = get_event_manager()
        
        # LEAN-inspired configuration
        self.max_positions = config.get("max_positions", MAX_0DTE_POSITIONS)
        self.profit_target = config.get("profit_target", PROFIT_TARGET_FAST)
        self.stop_loss = config.get("stop_loss", STOP_LOSS_TIGHT)
        self.entry_delay_minutes = config.get("entry_delay_minutes", LEAN_ENTRY_DELAY_MINUTES)
        
        # Enhanced position tracking
        self.active_positions: Dict[str, LEANZeroDTEPosition] = {}
        self.scheduled_entries: Dict[str, LEANZeroDTESetup] = {}
        self.today_trades: int = 0
        
        # Market timing (LEAN pattern)
        self.market_open_time: Optional[datetime] = None
        self.entry_scheduled: bool = False
        
        # Performance tracking
        self.daily_stats = {
            'trades_attempted': 0,
            'trades_executed': 0,
            'expired_otm': 0,
            'expired_itm': 0,
            'total_pnl': 0.0
        }
        
        self.logger.info("Enhanced 0DTE strategy initialized with LEAN patterns")
        
        # Schedule market open actions (LEAN pattern)
        self._schedule_market_open_actions()
    
    # ==========================================================================
    # LEAN ALGORITHM PATTERNS - Market Timing and Scheduling
    # ==========================================================================
    def _schedule_market_open_actions(self):
        """
        Schedule market open actions (from LEAN's scheduling pattern).
        
        From LEAN: "self.schedule.on(self.date_rules.tomorrow, 
                   self.time_rules.after_market_open(self.spx, 1), 
                   lambda: self.market_order(self.spx_option, -1))"
        """
        try:
            # Get today's market open time
            today = datetime.now().date()
            if self.trading_calendar.is_trading_day(today):
                self.market_open_time = self.trading_calendar.get_market_open(today)
                
                # Schedule entry 1 minute after market open (LEAN pattern)
                entry_time = self.market_open_time + timedelta(minutes=self.entry_delay_minutes)
                
                self.scheduler.schedule_action(
                    scheduled_time=entry_time,
                    action=self._execute_scheduled_0dte_entry,
                    description="0DTE Entry (LEAN-style)"
                )
                
                # Schedule liquidation before market close (LEAN pattern)
                liquidation_time = self.trading_calendar.get_market_close(today) - timedelta(minutes=15)
                self.scheduler.schedule_action(
                    scheduled_time=liquidation_time,
                    action=self._liquidate_0dte_positions,
                    description="0DTE Liquidation (LEAN-style)"
                )
                
                self.entry_scheduled = True
                self.logger.info(f"0DTE entry scheduled for {entry_time.strftime('%H:%M:%S')}")
            
        except Exception as e:
            self.logger.error(f"Failed to schedule market open actions: {e}")
    
    def analyze_market(self, market_data: Dict[str, Any]) -> StrategySignal:
        """
        Analyze market for 0DTE opportunities using LEAN patterns.
        
        From LEAN: Filter options expiring today, validate OTM status
        """
        try:
            # Check if we should scan for opportunities
            if not self._should_scan_for_0dte():
                return StrategySignal.NO_SIGNAL
            
            # Get option chain
            option_chain = market_data.get('option_chain', [])
            underlying_price = market_data.get('underlying_price', 0.0)
            
            if not option_chain or underlying_price <= 0:
                return StrategySignal.NO_SIGNAL
            
            # LEAN Pattern: Filter for same-day expiry only
            today_options = self._filter_same_day_expiry(option_chain)
            if not today_options:
                self.logger.debug("No same-day expiry options found")
                return StrategySignal.NO_SIGNAL
            
            # LEAN Pattern: Select OTM options based on threshold
            otm_opportunities = self._select_otm_opportunities(today_options, underlying_price)
            
            if otm_opportunities:
                # Select best opportunity
                best_setup = self._select_best_0dte_setup(otm_opportunities, market_data)
                
                if best_setup and self._validate_0dte_setup(best_setup):
                    return self._create_0dte_signal(best_setup)
            
            return StrategySignal.NO_SIGNAL
            
        except Exception as e:
            self.logger.error(f"0DTE market analysis failed: {e}")
            return StrategySignal.NO_SIGNAL
    
    def _filter_same_day_expiry(self, option_chain: List[Any]) -> List[Any]:
        """
        Filter for same-day expiry options (LEAN pattern).
        
        From LEAN: "i.id.date.year == 2021 and i.id.date.month == 1"
        """
        today = datetime.now().date()
        same_day_options = []
        
        for contract in option_chain:
            try:
                # Check if expiry is today
                if hasattr(contract, 'expiry') and contract.expiry.date() == today:
                    same_day_options.append(contract)
            except Exception as e:
                self.logger.debug(f"Error filtering contract: {e}")
                continue
        
        self.logger.debug(f"Found {len(same_day_options)} same-day expiry options")
        return same_day_options
    
    def _select_otm_opportunities(self, options: List[Any], underlying_price: float) -> List[LEANZeroDTESetup]:
        """
        Select OTM opportunities (from LEAN's OTM filtering).
        
        From LEAN: "i.id.strike_price <= 3200 and i.id.option_right == OptionRight.PUT"
        """
        opportunities = []
        
        for contract in options:
            try:
                # Determine if OTM based on LEAN thresholds
                is_otm_put = (contract.option_right == "PUT" and 
                             contract.strike <= underlying_price * OTM_PUT_THRESHOLD)
                is_otm_call = (contract.option_right == "CALL" and 
                              contract.strike >= underlying_price * OTM_CALL_THRESHOLD)
                
                if is_otm_put or is_otm_call:
                    # Create setup
                    setup = LEANZeroDTESetup(
                        strategy_type=ZeroDTEStrategy.SHORT_OTM_PUT if is_otm_put else ZeroDTEStrategy.SHORT_OTM_CALL,
                        underlying_symbol="SPY",
                        underlying_price=underlying_price,
                        selected_strike=contract.strike,
                        option_right=OptionRight.PUT if contract.option_right == "PUT" else OptionRight.CALL,
                        expiry=contract.expiry,
                        scheduled_entry_time=self.market_open_time + timedelta(minutes=self.entry_delay_minutes),
                        market_open_time=self.market_open_time,
                        entry_price_estimate=getattr(contract, 'mid_price', 1.0),
                        profit_target=getattr(contract, 'mid_price', 1.0) * self.profit_target,
                        stop_loss=getattr(contract, 'mid_price', 1.0) * (1 + self.stop_loss),
                        max_loss=getattr(contract, 'mid_price', 1.0) * self.stop_loss,
                        volume=getattr(contract, 'volume', 0),
                        open_interest=getattr(contract, 'open_interest', 0),
                        bid_ask_spread=getattr(contract, 'ask', 1.0) - getattr(contract, 'bid', 0.0)
                    )
                    
                    opportunities.append(setup)
                    
            except Exception as e:
                self.logger.debug(f"Error processing contract: {e}")
                continue
        
        self.logger.debug(f"Found {len(opportunities)} OTM opportunities")
        return opportunities
    
    def _select_best_0dte_setup(self, opportunities: List[LEANZeroDTESetup], 
                               market_data: Dict[str, Any]) -> Optional[LEANZeroDTESetup]:
        """Select best 0DTE setup based on quality metrics"""
        if not opportunities:
            return None
        
        # Score each opportunity
        for setup in opportunities:
            score = 0.0
            
            # OTM percentage (prefer more OTM)
            score += setup.otm_percentage * 10
            
            # Time to expiry (prefer more time)
            score += setup.time_to_expiry_hours * 2
            
            # Volume and open interest
            score += min(setup.volume / MIN_0DTE_VOLUME, 2.0) * 3
            score += min(setup.open_interest / MIN_0DTE_OPEN_INTEREST, 2.0) * 2
            
            # Bid-ask spread (prefer tighter spreads)
            if setup.bid_ask_spread > 0:
                score -= (setup.bid_ask_spread / setup.entry_price_estimate) * 5
            
            setup.setup_quality = score
        
        # Return best scoring setup
        best_setup = max(opportunities, key=lambda x: x.setup_quality)
        self.logger.info(f"Selected best 0DTE setup: {best_setup.strategy_type.value} "
                        f"strike {best_setup.selected_strike} quality {best_setup.setup_quality:.2f}")
        
        return best_setup
    
    def _validate_0dte_setup(self, setup: LEANZeroDTESetup) -> bool:
        """Validate 0DTE setup (LEAN-style validation)"""
        if setup.validation_errors:
            self.logger.warning(f"Setup validation failed: {setup.validation_errors}")
            return False
        
        # Check position limits
        if len(self.active_positions) >= self.max_positions:
            self.logger.warning("Maximum 0DTE positions reached")
            return False
        
        # Check daily trade limit
        if self.today_trades >= ZERO_DTE_MAX_TRADES:
            self.logger.warning("Daily 0DTE trade limit reached")
            return False
        
        # Quality threshold
        if setup.setup_quality < 5.0:
            self.logger.warning(f"Setup quality too low: {setup.setup_quality}")
            return False
        
        return True
    
    # ==========================================================================
    # LEAN ALGORITHM PATTERNS - Strategy Execution
    # ==========================================================================
    def _execute_scheduled_0dte_entry(self):
        """
        Execute scheduled 0DTE entry (LEAN's scheduled execution pattern).
        
        From LEAN: Scheduled execution after market open
        """
        try:
            self.logger.info("Executing scheduled 0DTE entry (LEAN pattern)")
            
            # Get current market data
            market_data = self._get_current_market_data()
            
            # Analyze for opportunities
            signal = self.analyze_market(market_data)
            
            if signal != StrategySignal.NO_SIGNAL:
                success = self.execute_signal(signal)
                if success:
                    self.daily_stats['trades_executed'] += 1
                else:
                    self.logger.warning("Scheduled 0DTE entry failed")
            else:
                self.logger.info("No 0DTE opportunities found at scheduled time")
                
        except Exception as e:
            self.logger.error(f"Scheduled 0DTE entry failed: {e}")
    
    def execute_signal(self, signal: StrategySignal) -> bool:
        """
        Execute 0DTE signal using LEAN patterns.
        
        From LEAN: market_order execution with validation
        """
        try:
            setup = signal.metadata.get('0dte_setup')
            if not setup:
                self.logger.error("No 0DTE setup in signal")
                return False
            
            # Create option strategy (short single option for 0DTE)
            if setup.strategy_type == ZeroDTEStrategy.SHORT_OTM_PUT:
                # Create short put position
                strategy = self._create_short_option_strategy(setup, OptionRight.PUT)
            elif setup.strategy_type == ZeroDTEStrategy.SHORT_OTM_CALL:
                # Create short call position
                strategy = self._create_short_option_strategy(setup, OptionRight.CALL)
            else:
                self.logger.error(f"Unsupported 0DTE strategy: {setup.strategy_type}")
                return False
            
            # Execute strategy
            execution_result = self._execute_0dte_strategy(strategy, setup)
            
            if execution_result['success']:
                # Create position tracking
                position = LEANZeroDTEPosition(
                    position_id=f"0DTE_{uuid.uuid4().hex[:8]}",
                    setup=setup,
                    strategy=strategy,
                    entry_time=datetime.now(),
                    entry_price=execution_result['entry_price'],
                    quantity=execution_result['quantity'],
                    state=ZeroDTEState.ACTIVE
                )
                
                # Store position
                self.active_positions[position.position_id] = position
                self.today_trades += 1
                self.daily_stats['trades_attempted'] += 1
                
                self.logger.info(f"0DTE position opened: {position.position_id}")
                return True
            else:
                self.logger.error(f"0DTE execution failed: {execution_result['error']}")
                return False
                
        except Exception as e:
            self.logger.error(f"0DTE signal execution failed: {e}")
            return False
    
    def _create_short_option_strategy(self, setup: LEANZeroDTESetup, option_right: OptionRight) -> OptionStrategy:
        """Create short option strategy for 0DTE"""
        # For 0DTE, we typically sell single options
        legs = [{
            'symbol': setup.expected_contract_symbol,
            'option_right': option_right,
            'strike': setup.selected_strike,
            'expiry': setup.expiry,
            'quantity': -1  # Short position
        }]
        
        # Create strategy (simplified - would use OptionStrategies helper)
        return type('Strategy', (), {
            'strategy_type': setup.strategy_type,
            'underlying_symbol': setup.underlying_symbol,
            'legs': legs
        })()
    
    def _execute_0dte_strategy(self, strategy, setup: LEANZeroDTESetup) -> Dict[str, Any]:
        """Execute 0DTE strategy (mock implementation)"""
        try:
            # Mock execution (would integrate with real broker)
            return {
                'success': True,
                'entry_price': setup.entry_price_estimate,
                'quantity': 1,
                'order_id': f"0DTE_{uuid.uuid4().hex[:8]}"
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # ==========================================================================
    # LEAN ALGORITHM PATTERNS - Position Management and Expiry Handling
    # ==========================================================================
    def manage_positions(self) -> List[Dict[str, Any]]:
        """
        Manage 0DTE positions with LEAN expiry patterns.
        
        From LEAN: Monitor for delisting warnings and expiry events
        """
        management_actions = []
        
        for position_id, position in self.active_positions.items():
            try:
                # Update position metrics
                position.update_metrics()
                
                # Check expiry status (LEAN pattern)
                self._check_expiry_status(position)
                
                # Check for management actions
                action = self._check_0dte_management(position)
                if action:
                    management_actions.append(action)
                    
            except Exception as e:
                self.logger.error(f"Position management failed for {position_id}: {e}")
        
        return management_actions
    
    def _check_expiry_status(self, position: LEANZeroDTEPosition):
        """
        Check expiry status (from LEAN's delisting assertion).
        
        From LEAN: "Assert delistings, so that we can make sure that we receive 
        the delisting warnings at the expected time."
        """
        now = datetime.now()
        time_to_expiry = (position.setup.expiry - now).total_seconds() / 3600
        
        # Update expiry status
        if time_to_expiry <= 0:
            # Determine if expired ITM or OTM
            if self._is_expired_itm(position):
                position.expiry_status = LEANExpiryStatus.EXPIRED_ITM
                position.state = ZeroDTEState.EXPIRED_OTM
                self.daily_stats['expired_itm'] += 1
            else:
                position.expiry_status = LEANExpiryStatus.EXPIRED_OTM
                position.state = ZeroDTEState.EXPIRED_OTM
                self.daily_stats['expired_otm'] += 1
        elif time_to_expiry <= 0.5:  # 30 minutes to expiry
            position.expiry_status = LEANExpiryStatus.DELISTING_WARNING
            position.state = ZeroDTEState.MONITORING_EXPIRY
            if not position.delisting_warned:
                self.logger.info(f"Delisting warning for position {position.position_id}")
                position.delisting_warned = True
    
    def _is_expired_itm(self, position: LEANZeroDTEPosition) -> bool:
        """Check if option expired in-the-money"""
        current_price = position.setup.underlying_price  # Would get real-time price
        
        if position.setup.option_right == OptionRight.PUT:
            return current_price < position.setup.selected_strike
        else:  # CALL
            return current_price > position.setup.selected_strike
    
    def _check_0dte_management(self, position: LEANZeroDTEPosition) -> Optional[Dict[str, Any]]:
        """Check if 0DTE position needs management"""
        # Quick profit target (0DTE moves fast)
        profit_pct = position.unrealized_pnl / (position.entry_price * position.quantity * 100)
        
        if profit_pct >= self.profit_target:
            return {
                'action': 'CLOSE_PROFITABLE',
                'position_id': position.position_id,
                'pnl': position.unrealized_pnl,
                'reason': 'Profit target reached'
            }
        
        # Stop loss
        if profit_pct <= -self.stop_loss:
            return {
                'action': 'CLOSE_LOSS',
                'position_id': position.position_id,
                'pnl': position.unrealized_pnl,
                'reason': 'Stop loss triggered'
            }
        
        # Time-based close (30 minutes before expiry)
        if position.setup.time_to_expiry_hours <= 0.5:
            return {
                'action': 'CLOSE_TIME',
                'position_id': position.position_id,
                'pnl': position.unrealized_pnl,
                'reason': 'Approaching expiry'
            }
        
        return None
    
    def _liquidate_0dte_positions(self):
        """
        Liquidate all 0DTE positions (LEAN's liquidation pattern).
        
        From LEAN: Scheduled liquidation before close
        """
        self.logger.info("Liquidating all 0DTE positions (LEAN pattern)")
        
        for position_id, position in list(self.active_positions.items()):
            try:
                # Execute liquidation
                success = self._liquidate_position(position)
                if success:
                    position.state = ZeroDTEState.LIQUIDATED
                    self.daily_stats['total_pnl'] += position.unrealized_pnl
                else:
                    self.logger.error(f"Failed to liquidate position {position_id}")
                    
            except Exception as e:
                self.logger.error(f"Liquidation failed for {position_id}: {e}")
    
    def _liquidate_position(self, position: LEANZeroDTEPosition) -> bool:
        """Liquidate individual position (mock implementation)"""
        # Would execute actual closing order
        self.logger.info(f"Liquidating position {position.position_id}")
        return True
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _should_scan_for_0dte(self) -> bool:
        """Check if we should scan for 0DTE opportunities"""
        now = datetime.now()
        
        # Only during market hours
        if not self.trading_calendar.is_market_open(now):
            return False
        
        # Only if we have capacity
        if len(self.active_positions) >= self.max_positions:
            return False
        
        # Only if we haven't hit daily limit
        if self.today_trades >= ZERO_DTE_MAX_TRADES:
            return False
        
        return True
    
    def _get_current_market_data(self) -> Dict[str, Any]:
        """Get current market data (mock implementation)"""
        # Would get real market data
        return {
            'option_chain': [],
            'underlying_price': 600.0,
            'timestamp': datetime.now()
        }
    
    def _create_0dte_signal(self, setup: LEANZeroDTESetup) -> StrategySignal:
        """Create 0DTE signal from validated setup"""
        return StrategySignal(
            signal_type="ENTRY",
            strategy_name="Enhanced0DTE",
            confidence=setup.setup_quality / 10.0,  # Normalize to 0-1
            timestamp=datetime.now(),
            metadata={
                '0dte_setup': setup,
                'expiry_same_day': True,
                'otm_validated': setup.is_otm
            }
        )
    
    def get_daily_statistics(self) -> Dict[str, Any]:
        """Get comprehensive daily statistics"""
        active_count = len(self.active_positions)
        total_unrealized = sum(pos.unrealized_pnl for pos in self.active_positions.values())
        
        return {
            **self.daily_stats,
            'active_positions': active_count,
            'today_trades': self.today_trades,
            'total_unrealized_pnl': total_unrealized,
            'success_rate': self.daily_stats['expired_otm'] / max(1, self.daily_stats['trades_executed']),
            'avg_pnl_per_trade': self.daily_stats['total_pnl'] / max(1, self.daily_stats['trades_executed'])
        }

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test Enhanced 0DTE with LEAN patterns
    config = {
        'max_positions': 2,
        'profit_target': 0.25,
        'stop_loss': 0.50,
        'entry_delay_minutes': 1
    }
    
    strategy = EnhancedZeroDTEStrategy(config)
    
    print("Testing Enhanced 0DTE with LEAN Patterns:")
    print("=" * 50)
    
    # Test daily statistics
    stats = strategy.get_daily_statistics()
    print(f"Daily statistics: {stats}")
    
    print("\n✅ Enhanced 0DTE with LEAN patterns ready!")
    print("Key LEAN enhancements:")
    print("- Precise same-day expiry filtering")
    print("- Scheduled entry timing (1 min after market open)")
    print("- OTM strike selection logic")
    print("- Automated expiry and delisting monitoring")
    print("- Professional validation and error handling")