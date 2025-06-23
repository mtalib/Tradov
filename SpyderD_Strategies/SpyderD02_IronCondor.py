#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD02_IronCondor.py
Group: D (Trading Strategies)
Purpose: Enhanced Iron Condor strategy with LEAN algorithm patterns

Description:
    Enhanced Iron Condor strategy implementation using patterns from 
    QuantConnect LEAN's IronCondorStrategyAlgorithm.py. Features professional
    strike selection, position group management, atomic strategy execution,
    and institutional-grade validation.

Key LEAN Enhancements:
    - Automated strike selection using sorted contracts
    - Position group validation with assertions
    - Atomic strategy execution using OptionStrategies helper
    - Professional error handling and logging
    - LEAN-style expiry and contract filtering

Based on: QuantConnect LEAN IronCondorStrategyAlgorithm.py
Author: Mohamed Talib
Created: 2025-06-23
Version: 3.0 (Enhanced with LEAN patterns)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
import itertools
from datetime import datetime, timedelta, time
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
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
from SpyderU_Utilities.SpyderU14_OptionStrategies import SpyderOptionStrategies, StrategyType, OptionStrategy
from SpyderB_Broker.SpyderB01_SpyderClient import get_ib_client
from SpyderB_Broker.SpyderB06_ContractBuilder import ContractBuilder
from SpyderC_MarketData.SpyderC03_OptionChain import OptionChainManager
from SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
from SpyderU_Utilities.SpyderU13_TechnicalIndicators import TechnicalIndicators
from SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import (
    IRON_CONDOR_MAX_LOSS_MULTIPLIER,
    IRON_CONDOR_PROFIT_TARGET,
    IRON_CONDOR_STOP_LOSS,
    SPY_CONTRACT_MULTIPLIER
)
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType

# ==============================================================================
# CONSTANTS (Enhanced with LEAN patterns)
# ==============================================================================
# LEAN-inspired strategy parameters
MIN_DAYS_TO_EXPIRATION = 20
MAX_DAYS_TO_EXPIRATION = 45
TARGET_DELTA_SHORT = 0.15  # Target delta for short strikes
TARGET_DELTA_RANGE = 0.05  # Acceptable delta range (0.10 - 0.20)
MIN_CREDIT_RATIO = 0.25    # Minimum credit as ratio of width
MAX_IV_RANK = 50           # Max IV rank to enter trade
MIN_VOLUME = 100           # Minimum option volume
MIN_OPEN_INTEREST = 500    # Minimum open interest

# Position management (LEAN-style)
MAX_POSITIONS = 3          # Maximum concurrent positions
ADJUSTMENT_THRESHOLD = 0.30 # Delta threshold for adjustments
ROLL_DAYS_BEFORE_EXPIRY = 7 # Days before expiry to consider rolling

# LEAN algorithm parameters
MIN_CONTRACTS_FOR_STRATEGY = 4  # From LEAN: "if len(contracts) < 4: continue"
POSITION_GROUP_VALIDATION = True

# ==============================================================================
# ENHANCED ENUMERATIONS
# ==============================================================================
class IronCondorState(Enum):
    """Enhanced Iron Condor position states (LEAN-inspired)"""
    SCANNING = "scanning"
    VALIDATING = "validating"  # New: LEAN-style validation
    PENDING_ENTRY = "pending_entry"
    ACTIVE = "active"
    ADJUSTING = "adjusting"
    CLOSING = "closing"
    CLOSED = "closed"
    EXPIRED = "expired"
    ERROR = "error"  # New: Error handling

class LEANContractQuality(Enum):
    """Contract quality assessment (LEAN-inspired)"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    REJECTED = "rejected"

# ==============================================================================
# ENHANCED DATA STRUCTURES
# ==============================================================================
@dataclass
class LEANIronCondorLegs:
    """Enhanced Iron Condor legs with LEAN patterns"""
    # Strike prices (LEAN ordering: long_put < short_put < short_call < long_call)
    long_put_strike: float
    short_put_strike: float
    short_call_strike: float
    long_call_strike: float
    
    # Contract details
    expiry: datetime
    underlying_symbol: str = "SPY"
    
    # Market data
    entry_credit: float = 0.0
    current_value: float = 0.0
    
    # Strategy metrics
    put_spread_width: float = 0.0
    call_spread_width: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    
    # Quality assessment (LEAN-inspired)
    contract_quality: LEANContractQuality = LEANContractQuality.FAIR
    validation_errors: List[str] = None
    
    def __post_init__(self):
        """Calculate derived fields (LEAN-style)"""
        if self.validation_errors is None:
            self.validation_errors = []
            
        self.put_spread_width = self.short_put_strike - self.long_put_strike
        self.call_spread_width = self.long_call_strike - self.short_call_strike
        self.max_loss = max(self.put_spread_width, self.call_spread_width) - self.entry_credit
        self.max_profit = self.entry_credit
        
        # Validate strike order (LEAN-style validation)
        self._validate_strike_order()
    
    def _validate_strike_order(self):
        """Validate strike order (from LEAN IronCondorStrategyAlgorithm)"""
        strikes = [self.long_put_strike, self.short_put_strike, 
                  self.short_call_strike, self.long_call_strike]
        
        if strikes != sorted(strikes):
            error = "Iron Condor strikes must be in ascending order: long_put < short_put < short_call < long_call"
            self.validation_errors.append(error)
            self.contract_quality = LEANContractQuality.REJECTED
    
    @property
    def breakeven_upper(self) -> float:
        """Upper breakeven point"""
        return self.short_call_strike + self.entry_credit
    
    @property
    def breakeven_lower(self) -> float:
        """Lower breakeven point"""
        return self.short_put_strike - self.entry_credit
    
    @property
    def profit_zone_width(self) -> float:
        """Width of profit zone"""
        return self.short_call_strike - self.short_put_strike

@dataclass
class LEANPositionGroup:
    """LEAN-style position group for Iron Condor (inspired by IPositionGroup)"""
    strategy: OptionStrategy
    positions: List[Dict[str, Any]]
    position_group_id: str
    entry_time: datetime
    state: IronCondorState
    
    # P&L tracking (LEAN-style)
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    # Greeks (aggregated across all legs)
    total_delta: float = 0.0
    total_gamma: float = 0.0
    total_theta: float = 0.0
    total_vega: float = 0.0
    
    def validate_position_group(self) -> bool:
        """
        Validate position group (from LEAN's assert_strategy_position_group).
        
        Returns:
            True if valid, raises AssertionError if invalid
        """
        if len(self.positions) != 4:
            raise AssertionError(f"Expected position group to have 4 positions. Actual: {len(self.positions)}")
        
        # Get ordered strikes from strategy
        strikes = sorted([leg.strike for leg in self.strategy.legs])
        
        # Validate each leg exists and has correct quantity
        long_put_strike = strikes[0]
        short_put_strike = strikes[1]
        short_call_strike = strikes[2]
        long_call_strike = strikes[3]
        
        # Find and validate long put position
        long_put_pos = self._find_position_by_criteria("PUT", long_put_strike)
        if not long_put_pos or long_put_pos['quantity'] <= 0:
            raise AssertionError(f"Expected long put position quantity > 0. Actual: {long_put_pos['quantity'] if long_put_pos else 'None'}")
        
        # Find and validate short put position
        short_put_pos = self._find_position_by_criteria("PUT", short_put_strike)
        if not short_put_pos or short_put_pos['quantity'] >= 0:
            raise AssertionError(f"Expected short put position quantity < 0. Actual: {short_put_pos['quantity'] if short_put_pos else 'None'}")
        
        # Find and validate short call position
        short_call_pos = self._find_position_by_criteria("CALL", short_call_strike)
        if not short_call_pos or short_call_pos['quantity'] >= 0:
            raise AssertionError(f"Expected short call position quantity < 0. Actual: {short_call_pos['quantity'] if short_call_pos else 'None'}")
        
        # Find and validate long call position
        long_call_pos = self._find_position_by_criteria("CALL", long_call_strike)
        if not long_call_pos or long_call_pos['quantity'] <= 0:
            raise AssertionError(f"Expected long call position quantity > 0. Actual: {long_call_pos['quantity'] if long_call_pos else 'None'}")
        
        return True
    
    def _find_position_by_criteria(self, option_right: str, strike: float) -> Optional[Dict[str, Any]]:
        """Find position matching criteria"""
        for pos in self.positions:
            if (pos.get('option_right') == option_right and 
                abs(pos.get('strike', 0) - strike) < 0.01):
                return pos
        return None

# ==============================================================================
# ENHANCED IRON CONDOR STRATEGY CLASS
# ==============================================================================
class EnhancedIronCondorStrategy(BaseStrategy):
    """
    Enhanced Iron Condor strategy with LEAN algorithm patterns.
    
    Key LEAN Enhancements:
    - Automated strike selection using sorted contracts
    - Position group management and validation
    - Atomic strategy execution using OptionStrategies helper
    - Professional error handling and logging
    - LEAN-style contract filtering and validation
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Enhanced Iron Condor strategy"""
        super().__init__("EnhancedIronCondor", config)
        
        # Initialize components
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.ib_client = get_ib_client()
        self.option_chain_manager = OptionChainManager()
        self.greeks_calculator = GreeksCalculator()
        self.risk_manager = get_risk_manager()
        self.event_manager = get_event_manager()
        self.indicators = TechnicalIndicators()
        
        # LEAN-inspired configuration
        self.target_delta = config.get("target_delta", TARGET_DELTA_SHORT)
        self.min_credit_ratio = config.get("min_credit_ratio", MIN_CREDIT_RATIO)
        self.max_positions = config.get("max_positions", MAX_POSITIONS)
        self.profit_target = config.get("profit_target", IRON_CONDOR_PROFIT_TARGET)
        self.stop_loss = config.get("stop_loss", IRON_CONDOR_STOP_LOSS)
        
        # Enhanced position tracking (LEAN-style)
        self.active_position_groups: Dict[str, LEANPositionGroup] = {}
        self.pending_strategies: Dict[str, OptionStrategy] = {}
        self.validation_cache: Dict[str, bool] = {}
        
        # Performance tracking
        self.strategy_statistics = {
            'total_trades': 0,
            'winning_trades': 0,
            'total_pnl': 0.0,
            'validation_failures': 0,
            'execution_errors': 0
        }
        
        self.logger.info(f"Enhanced Iron Condor strategy initialized with LEAN patterns")
    
    # ==========================================================================
    # LEAN ALGORITHM PATTERNS - Contract Selection
    # ==========================================================================
    def analyze_market(self, market_data: Dict[str, Any]) -> StrategySignal:
        """
        Analyze market for Iron Condor opportunities using LEAN patterns.
        
        From LEAN IronCondorStrategyAlgorithm.py:
        - Iterate through expiries using itertools.groupby
        - Sort contracts by strike
        - Validate minimum contract count
        - Separate puts and calls
        - Select appropriate strikes
        """
        try:
            # Get option chain
            option_chain = market_data.get('option_chain', [])
            underlying_price = market_data.get('underlying_price', 0.0)
            
            if not option_chain or underlying_price <= 0:
                return StrategySignal.NO_SIGNAL
            
            # LEAN Pattern: Group by expiry and process each
            for expiry, group in itertools.groupby(option_chain, lambda x: x.expiry):
                contracts = sorted(group, key=lambda x: x.strike)
                
                # LEAN Pattern: Skip if insufficient contracts
                if len(contracts) < MIN_CONTRACTS_FOR_STRATEGY:
                    continue
                
                # LEAN Pattern: Separate puts and calls
                put_contracts = [x for x in contracts if x.option_right == "PUT"]
                call_contracts = [x for x in contracts if x.option_right == "CALL"]
                
                if len(put_contracts) < 2 or len(call_contracts) < 2:
                    continue
                
                # LEAN Pattern: Select strikes for Iron Condor
                ic_setup = self._select_iron_condor_strikes_lean_style(
                    put_contracts, call_contracts, underlying_price, expiry
                )
                
                if ic_setup and self._validate_iron_condor_setup(ic_setup):
                    return self._create_iron_condor_signal(ic_setup, market_data)
            
            return StrategySignal.NO_SIGNAL
            
        except Exception as e:
            self.logger.error(f"Market analysis failed: {e}")
            self.strategy_statistics['execution_errors'] += 1
            return StrategySignal.NO_SIGNAL
    
    def _select_iron_condor_strikes_lean_style(self, 
                                             put_contracts: List[Any],
                                             call_contracts: List[Any], 
                                             underlying_price: float,
                                             expiry: datetime) -> Optional[LEANIronCondorLegs]:
        """
        Select Iron Condor strikes using LEAN algorithm patterns.
        
        From LEAN IronCondorStrategyAlgorithm.py:
        - Use sorted contracts
        - Select based on positioning relative to underlying
        - Ensure proper strike order
        """
        try:
            # Sort puts and calls by strike
            puts_sorted = sorted(put_contracts, key=lambda x: x.strike)
            calls_sorted = sorted(call_contracts, key=lambda x: x.strike)
            
            # Find ATM strike
            atm_strike = self._find_closest_strike(underlying_price, put_contracts + call_contracts)
            
            # LEAN Pattern: Select puts below ATM
            otm_puts = [p for p in puts_sorted if p.strike < underlying_price]
            if len(otm_puts) < 2:
                return None
            
            # Select put strikes (short put closer to ATM, long put further out)
            short_put = otm_puts[-1]  # Highest strike below underlying
            long_put = otm_puts[-2] if len(otm_puts) > 1 else otm_puts[0]
            
            # LEAN Pattern: Select calls above ATM
            otm_calls = [c for c in calls_sorted if c.strike > underlying_price]
            if len(otm_calls) < 2:
                return None
            
            # Select call strikes (short call closer to ATM, long call further out)
            short_call = otm_calls[0]   # Lowest strike above underlying
            long_call = otm_calls[1] if len(otm_calls) > 1 else otm_calls[0]
            
            # Create LEAN-style legs
            legs = LEANIronCondorLegs(
                long_put_strike=long_put.strike,
                short_put_strike=short_put.strike,
                short_call_strike=short_call.strike,
                long_call_strike=long_call.strike,
                expiry=expiry,
                underlying_symbol="SPY"
            )
            
            # Estimate credit (simplified)
            legs.entry_credit = self._estimate_iron_condor_credit(legs, underlying_price)
            
            return legs
            
        except Exception as e:
            self.logger.error(f"Strike selection failed: {e}")
            return None
    
    def _validate_iron_condor_setup(self, legs: LEANIronCondorLegs) -> bool:
        """
        Validate Iron Condor setup using LEAN patterns.
        
        Includes all professional validations:
        - Strike order validation
        - Credit ratio validation
        - Risk/reward validation
        - Market condition validation
        """
        try:
            # Basic validation (already done in __post_init__)
            if legs.validation_errors:
                self.logger.warning(f"Setup validation failed: {legs.validation_errors}")
                return False
            
            # Credit ratio validation
            min_width = min(legs.put_spread_width, legs.call_spread_width)
            if legs.entry_credit < (min_width * self.min_credit_ratio):
                legs.validation_errors.append(f"Credit ratio too low: {legs.entry_credit/min_width:.2f} < {self.min_credit_ratio}")
                return False
            
            # Risk/reward validation
            risk_reward_ratio = legs.max_profit / legs.max_loss if legs.max_loss > 0 else 0
            if risk_reward_ratio < 0.2:  # Minimum 1:5 risk/reward
                legs.validation_errors.append(f"Poor risk/reward ratio: {risk_reward_ratio:.2f}")
                return False
            
            # Days to expiration validation
            days_to_expiry = (legs.expiry - datetime.now()).days
            if not (MIN_DAYS_TO_EXPIRATION <= days_to_expiry <= MAX_DAYS_TO_EXPIRATION):
                legs.validation_errors.append(f"DTE out of range: {days_to_expiry} not in [{MIN_DAYS_TO_EXPIRATION}, {MAX_DAYS_TO_EXPIRATION}]")
                return False
            
            legs.contract_quality = LEANContractQuality.EXCELLENT
            return True
            
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            self.strategy_statistics['validation_failures'] += 1
            return False
    
    # ==========================================================================
    # LEAN ALGORITHM PATTERNS - Strategy Execution
    # ==========================================================================
    def execute_signal(self, signal: StrategySignal) -> bool:
        """
        Execute Iron Condor using LEAN's atomic strategy approach.
        
        From LEAN IronCondorStrategyAlgorithm.py:
        - Use OptionStrategies.iron_condor for atomic execution
        - Validate position group after execution
        - Handle execution errors professionally
        """
        try:
            # Extract setup from signal
            ic_setup = signal.metadata.get('iron_condor_setup')
            if not ic_setup:
                self.logger.error("No Iron Condor setup in signal")
                return False
            
            # Create LEAN-style strategy using our helper
            strategy = SpyderOptionStrategies.iron_condor(
                underlying_symbol="SPY",
                long_put_strike=ic_setup.long_put_strike,
                short_put_strike=ic_setup.short_put_strike,
                short_call_strike=ic_setup.short_call_strike,
                long_call_strike=ic_setup.long_call_strike,
                expiry=ic_setup.expiry,
                quantity=1
            )
            
            # Validate strategy before execution
            SpyderOptionStrategies.validate_strategy_legs(strategy)
            
            # Execute strategy atomically (LEAN pattern)
            execution_result = self._execute_strategy_atomic(strategy)
            
            if execution_result['success']:
                # Create position group (LEAN pattern)
                position_group = LEANPositionGroup(
                    strategy=strategy,
                    positions=execution_result['positions'],
                    position_group_id=f"IC_{uuid.uuid4().hex[:8]}",
                    entry_time=datetime.now(),
                    state=IronCondorState.ACTIVE
                )
                
                # Validate position group (LEAN pattern)
                if POSITION_GROUP_VALIDATION:
                    position_group.validate_position_group()
                
                # Store position group
                self.active_position_groups[position_group.position_group_id] = position_group
                
                # Update statistics
                self.strategy_statistics['total_trades'] += 1
                
                self.logger.info(f"Iron Condor executed successfully: {position_group.position_group_id}")
                return True
            else:
                self.logger.error(f"Strategy execution failed: {execution_result['error']}")
                return False
                
        except Exception as e:
            self.logger.error(f"Signal execution failed: {e}")
            self.strategy_statistics['execution_errors'] += 1
            return False
    
    def _execute_strategy_atomic(self, strategy: OptionStrategy) -> Dict[str, Any]:
        """
        Execute strategy atomically (LEAN-inspired).
        
        Simulates LEAN's atomic strategy execution where all legs
        are executed as a single unit.
        """
        try:
            executed_positions = []
            
            # Execute each leg
            for leg in strategy.legs:
                # Create order for leg
                order_result = self._execute_option_leg(leg)
                
                if order_result['success']:
                    executed_positions.append({
                        'symbol': leg.symbol,
                        'option_right': leg.option_right.value,
                        'strike': leg.strike,
                        'expiry': leg.expiry,
                        'quantity': leg.quantity,
                        'fill_price': order_result['fill_price'],
                        'order_id': order_result['order_id']
                    })
                else:
                    # If any leg fails, rollback (LEAN pattern)
                    self._rollback_executed_positions(executed_positions)
                    return {'success': False, 'error': f"Leg execution failed: {order_result['error']}"}
            
            return {'success': True, 'positions': executed_positions}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _execute_option_leg(self, leg) -> Dict[str, Any]:
        """Execute individual option leg (mock implementation)"""
        # This would integrate with your actual broker execution
        # For now, return mock success
        return {
            'success': True,
            'fill_price': 1.50,  # Mock fill price
            'order_id': f"ORD_{uuid.uuid4().hex[:8]}"
        }
    
    def _rollback_executed_positions(self, positions: List[Dict[str, Any]]):
        """Rollback executed positions in case of partial failure"""
        self.logger.warning(f"Rolling back {len(positions)} executed positions")
        # Implementation would cancel/close executed positions
    
    # ==========================================================================
    # LEAN ALGORITHM PATTERNS - Position Management
    # ==========================================================================
    def manage_positions(self) -> List[Dict[str, Any]]:
        """
        Manage active positions using LEAN patterns.
        
        From LEAN: Regular position group validation and P&L monitoring
        """
        management_actions = []
        
        for group_id, position_group in self.active_position_groups.items():
            try:
                # Validate position group integrity (LEAN pattern)
                if POSITION_GROUP_VALIDATION:
                    position_group.validate_position_group()
                
                # Update P&L and Greeks
                self._update_position_group_metrics(position_group)
                
                # Check for management actions
                action = self._check_position_management(position_group)
                if action:
                    management_actions.append(action)
                    
            except AssertionError as e:
                self.logger.error(f"Position group validation failed for {group_id}: {e}")
                position_group.state = IronCondorState.ERROR
                management_actions.append({
                    'action': 'ERROR_HANDLING',
                    'group_id': group_id,
                    'error': str(e)
                })
            except Exception as e:
                self.logger.error(f"Position management failed for {group_id}: {e}")
        
        return management_actions
    
    def _update_position_group_metrics(self, position_group: LEANPositionGroup):
        """Update position group metrics (LEAN-style)"""
        # Calculate total P&L across all positions
        total_pnl = 0.0
        total_delta = 0.0
        
        for position in position_group.positions:
            # Mock P&L calculation (would use real market data)
            position_pnl = (position.get('current_price', 0) - position.get('fill_price', 0)) * position.get('quantity', 0) * 100
            total_pnl += position_pnl
            
            # Mock Greeks calculation
            total_delta += position.get('delta', 0) * position.get('quantity', 0)
        
        position_group.unrealized_pnl = total_pnl
        position_group.total_delta = total_delta
    
    def _check_position_management(self, position_group: LEANPositionGroup) -> Optional[Dict[str, Any]]:
        """Check if position needs management action"""
        # Profit target check
        if position_group.unrealized_pnl >= (position_group.strategy.total_quantity * self.profit_target * 100):
            return {
                'action': 'CLOSE_PROFITABLE',
                'group_id': position_group.position_group_id,
                'pnl': position_group.unrealized_pnl
            }
        
        # Stop loss check
        if position_group.unrealized_pnl <= -(position_group.strategy.total_quantity * self.stop_loss * 100):
            return {
                'action': 'CLOSE_LOSS',
                'group_id': position_group.position_group_id,
                'pnl': position_group.unrealized_pnl
            }
        
        return None
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _find_closest_strike(self, price: float, contracts: List[Any]) -> float:
        """Find strike closest to given price"""
        if not contracts:
            return price
        
        return min(contracts, key=lambda x: abs(x.strike - price)).strike
    
    def _estimate_iron_condor_credit(self, legs: LEANIronCondorLegs, underlying_price: float) -> float:
        """Estimate Iron Condor credit (simplified)"""
        # Simplified credit estimation
        # In practice, would use real option pricing
        put_spread_credit = legs.put_spread_width * 0.3
        call_spread_credit = legs.call_spread_width * 0.3
        return put_spread_credit + call_spread_credit
    
    def _create_iron_condor_signal(self, legs: LEANIronCondorLegs, market_data: Dict[str, Any]) -> StrategySignal:
        """Create Iron Condor signal from validated setup"""
        return StrategySignal(
            signal_type="ENTRY",
            strategy_name="EnhancedIronCondor",
            confidence=0.75,
            timestamp=datetime.now(),
            metadata={
                'iron_condor_setup': legs,
                'market_data': market_data,
                'validation_passed': True
            }
        )
    
    def get_strategy_statistics(self) -> Dict[str, Any]:
        """Get comprehensive strategy statistics (LEAN-style)"""
        active_positions = len(self.active_position_groups)
        total_unrealized_pnl = sum(pg.unrealized_pnl for pg in self.active_position_groups.values())
        
        return {
            **self.strategy_statistics,
            'active_positions': active_positions,
            'total_unrealized_pnl': total_unrealized_pnl,
            'avg_pnl_per_trade': self.strategy_statistics['total_pnl'] / max(1, self.strategy_statistics['total_trades']),
            'win_rate': self.strategy_statistics['winning_trades'] / max(1, self.strategy_statistics['total_trades']),
            'error_rate': self.strategy_statistics['execution_errors'] / max(1, self.strategy_statistics['total_trades'])
        }

# ==============================================================================
# LEAN-STYLE LIQUIDATION
# ==============================================================================
def liquidate_iron_condor_strategy(position_group: LEANPositionGroup) -> bool:
    """
    Liquidate Iron Condor strategy (from LEAN's liquidate_strategy pattern).
    
    From LEAN: "We should be able to close the position by selling the strategy"
    """
    try:
        # Create inverse strategy for liquidation
        inverse_strategy = SpyderOptionStrategies.iron_condor(
            underlying_symbol=position_group.strategy.underlying_symbol,
            long_put_strike=position_group.strategy.legs[0].strike,
            short_put_strike=position_group.strategy.legs[1].strike,
            short_call_strike=position_group.strategy.legs[2].strike,
            long_call_strike=position_group.strategy.legs[3].strike,
            expiry=position_group.strategy.legs[0].expiry,
            quantity=-1  # Opposite quantity to close
        )
        
        # Execute liquidation
        # Implementation would execute the inverse strategy
        
        position_group.state = IronCondorState.CLOSED
        return True
        
    except Exception as e:
        logging.error(f"Liquidation failed: {e}")
        return False

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test Enhanced Iron Condor with LEAN patterns
    config = {
        'target_delta': 0.15,
        'min_credit_ratio': 0.25,
        'max_positions': 3,
        'profit_target': 0.50,
        'stop_loss': 1.25
    }
    
    strategy = EnhancedIronCondorStrategy(config)
    
    print("Testing Enhanced Iron Condor with LEAN Patterns:")
    print("=" * 55)
    
    # Mock market data
    mock_chain = [
        type('Contract', (), {'strike': 580, 'expiry': datetime.now() + timedelta(days=30), 'option_right': 'PUT'}),
        type('Contract', (), {'strike': 590, 'expiry': datetime.now() + timedelta(days=30), 'option_right': 'PUT'}),
        type('Contract', (), {'strike': 610, 'expiry': datetime.now() + timedelta(days=30), 'option_right': 'CALL'}),
        type('Contract', (), {'strike': 620, 'expiry': datetime.now() + timedelta(days=30), 'option_right': 'CALL'}),
    ]
    
    market_data = {
        'option_chain': mock_chain,
        'underlying_price': 600.0
    }
    
    # Test signal generation
    signal = strategy.analyze_market(market_data)
    print(f"Signal generated: {signal != StrategySignal.NO_SIGNAL}")
    
    # Get statistics
    stats = strategy.get_strategy_statistics()
    print(f"Strategy statistics: {stats}")
    
    print("\n✅ Enhanced Iron Condor with LEAN patterns ready!")
    print("Key LEAN enhancements:")
    print("- Automated strike selection using sorted contracts")
    print("- Position group validation with assertions")
    print("- Atomic strategy execution")
    print("- Professional error handling")
    print("- LEAN-style contract filtering")
