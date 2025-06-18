#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD02_IronCondor.py
Group: D (Trading Strategies)
Purpose: Iron Condor options strategy implementation

Description:
    This module implements the Iron Condor strategy for SPY options trading.
    An Iron Condor is a neutral options strategy that profits from low volatility
    and time decay. It consists of selling an OTM call spread and an OTM put spread
    with the same expiration date. The strategy achieves maximum profit when the
    underlying stays between the short strikes at expiration.

Author: Mohamed Talib
Date: 2024-12-07
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
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
from SpyderB_Broker.SpyderB01_IBClient import get_ib_client
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
# CONSTANTS
# ==============================================================================
# Strategy-specific constants
MIN_DAYS_TO_EXPIRATION = 20
MAX_DAYS_TO_EXPIRATION = 45
TARGET_DELTA_SHORT = 0.15  # Target delta for short strikes
TARGET_DELTA_RANGE = 0.05  # Acceptable delta range (0.10 - 0.20)
MIN_CREDIT_RATIO = 0.25  # Minimum credit as ratio of width
MAX_IV_RANK = 50  # Max IV rank to enter trade
MIN_VOLUME = 100  # Minimum option volume
MIN_OPEN_INTEREST = 500  # Minimum open interest

# Position management
MAX_POSITIONS = 3  # Maximum concurrent positions
ADJUSTMENT_THRESHOLD = 0.30  # Delta threshold for adjustments
ROLL_DAYS_BEFORE_EXPIRY = 7  # Days before expiry to consider rolling

# ==============================================================================
# ENUMERATIONS
# ==============================================================================
class IronCondorState(Enum):
    """States for Iron Condor position lifecycle."""
    SCANNING = "scanning"
    PENDING_ENTRY = "pending_entry"
    ACTIVE = "active"
    ADJUSTING = "adjusting"
    CLOSING = "closing"
    CLOSED = "closed"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class IronCondorLegs:
    """Represents the four legs of an Iron Condor position."""
    call_spread_long: float
    call_spread_short: float
    put_spread_short: float
    put_spread_long: float
    expiration: str
    entry_credit: float
    max_loss: float
    quantity: int = 1
    
    @property
    def call_spread_width(self) -> float:
        """Width of the call spread."""
        return self.call_spread_long - self.call_spread_short
    
    @property
    def put_spread_width(self) -> float:
        """Width of the put spread."""
        return self.put_spread_short - self.put_spread_long
    
    @property
    def breakeven_upper(self) -> float:
        """Upper breakeven point."""
        return self.call_spread_short + self.entry_credit
    
    @property
    def breakeven_lower(self) -> float:
        """Lower breakeven point."""
        return self.put_spread_short - self.entry_credit

@dataclass
class IronCondorPosition:
    """Represents an active Iron Condor position."""
    position_id: str
    legs: IronCondorLegs
    order_ids: Dict[str, int]
    entry_time: datetime
    state: IronCondorState
    current_price: float = 0.0
    current_credit: float = 0.0
    pnl: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0

# ==============================================================================
# IRON CONDOR STRATEGY CLASS
# ==============================================================================
class IronCondorStrategy(BaseStrategy):
    """
    Iron Condor options strategy implementation for SPY.
    
    This strategy sells out-of-the-money call and put spreads to collect
    premium in low volatility environments.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Iron Condor strategy."""
        super().__init__("IronCondor", config)
        
        # Initialize components
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.ib_client = get_ib_client()
        self.option_chain_manager = OptionChainManager()
        self.greeks_calculator = GreeksCalculator()
        self.risk_manager = get_risk_manager()
        self.event_manager = get_event_manager()
        self.indicators = TechnicalIndicators()
        
        # Strategy parameters
        self.target_delta = config.get("target_delta", TARGET_DELTA_SHORT)
        self.min_credit_ratio = config.get("min_credit_ratio", MIN_CREDIT_RATIO)
        self.max_positions = config.get("max_positions", MAX_POSITIONS)
        self.profit_target = config.get("profit_target", IRON_CONDOR_PROFIT_TARGET)
        self.stop_loss = config.get("stop_loss", IRON_CONDOR_STOP_LOSS)
        
        # Position tracking
        self.active_positions: Dict[str, IronCondorPosition] = {}
        self.pending_orders: Dict[int, Dict[str, Any]] = {}
        self.historical_performance: List[Dict[str, Any]] = []
        
        # Market data
        self.current_spy_price = 0.0
        self.current_iv = 0.0
        self.iv_rank = 0.0
        self.iv_percentile = 0.0
        
        self.logger.info(f"Iron Condor strategy initialized with target delta: {self.target_delta}")
    
    # ==========================================================================
    # STRATEGY IMPLEMENTATION
    # ==========================================================================
    
    def analyze_market(self, market_data: Dict[str, Any]) -> StrategySignal:
        """Analyze market conditions for Iron Condor opportunities."""
        try:
            # Update market data
            self.current_spy_price = market_data.get('last_price', 0)
            self.current_iv = market_data.get('implied_volatility', 0)
            
            # Calculate IV metrics
            self.iv_rank = self._calculate_iv_rank()
            self.iv_percentile = self._calculate_iv_percentile()
            
            # Check entry conditions
            if not self._should_enter_position():
                return StrategySignal(PositionType.NONE)
            
            # Find optimal strikes
            optimal_strikes = self._find_optimal_strikes()
            
            if not optimal_strikes:
                return StrategySignal(PositionType.NONE)
            
            # Calculate position details
            position_details = self._calculate_position_details(optimal_strikes)
            
            # Validate the trade
            if not self._validate_trade(position_details):
                return StrategySignal(PositionType.NONE)
            
            # Create entry signal
            signal = StrategySignal(
                position_type=PositionType.IRON_CONDOR,
                contracts=position_details,
                confidence=self._calculate_confidence_score(),
                entry_price=self.current_spy_price,
                stop_loss=position_details['max_loss'],
                profit_target=position_details['target_profit']
            )
            
            self.logger.info(f"Iron Condor signal generated: {signal}")
            return signal
            
        except Exception as e:
            self.logger.error(f"Error analyzing market: {str(e)}")
            self.error_handler.handle_error(e)
            return StrategySignal(PositionType.NONE)
    
    def execute_signal(self, signal: StrategySignal) -> bool:
        """Execute Iron Condor entry signal."""
        if signal.position_type != PositionType.IRON_CONDOR:
            return False
        
        try:
            # Create position ID
            position_id = f"IC_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            # Create Iron Condor legs
            legs = IronCondorLegs(
                call_spread_long=signal.contracts['call_long_strike'],
                call_spread_short=signal.contracts['call_short_strike'],
                put_spread_short=signal.contracts['put_short_strike'],
                put_spread_long=signal.contracts['put_long_strike'],
                expiration=signal.contracts['expiration'],
                entry_credit=signal.contracts['net_credit'],
                max_loss=signal.contracts['max_loss'],
                quantity=signal.contracts['quantity']
            )
            
            # Place orders
            order_ids = self._place_iron_condor_orders(legs)
            
            if not order_ids:
                return False
            
            # Create position object
            position = IronCondorPosition(
                position_id=position_id,
                legs=legs,
                order_ids=order_ids,
                entry_time=datetime.now(),
                state=IronCondorState.PENDING_ENTRY,
                current_price=self.current_spy_price
            )
            
            # Add to active positions
            self.active_positions[position_id] = position
            
            # Update risk manager
            self.risk_manager.add_position(position_id, {
                'strategy': 'IronCondor',
                'max_loss': legs.max_loss * legs.quantity,
                'current_risk': 0,
                'contracts': signal.contracts
            })
            
            # Emit position opened event
            self.event_manager.create_event(
                EventType.POSITION,
                {
                    'action': 'opened',
                    'position_id': position_id,
                    'strategy': 'IronCondor',
                    'details': legs
                },
                source='IronCondorStrategy'
            )
            
            self.logger.info(f"Iron Condor position {position_id} orders placed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error executing signal: {str(e)}")
            self.error_handler.handle_error(e)
            return False
    
    def manage_positions(self) -> None:
        """Manage active Iron Condor positions."""
        for position_id, position in list(self.active_positions.items()):
            try:
                # Skip if position is already closing
                if position.state == IronCondorState.CLOSING:
                    continue
                
                # Update position metrics
                self._update_position_metrics(position)
                
                # Check exit conditions
                if self._check_profit_target(position):
                    self.logger.info(f"Profit target reached for {position_id}")
                    self._close_position(position, "PROFIT_TARGET")
                    continue
                
                if self._check_stop_loss(position):
                    self.logger.info(f"Stop loss triggered for {position_id}")
                    self._close_position(position, "STOP_LOSS")
                    continue
                
                # Check if adjustment needed
                if self._needs_adjustment(position):
                    self.logger.info(f"Position {position_id} needs adjustment")
                    self._adjust_position(position)
                    continue
                
                # Check expiration management
                if self._needs_rolling(position):
                    self.logger.info(f"Position {position_id} approaching expiration")
                    self._roll_position(position)
                
            except Exception as e:
                self.logger.error(f"Error managing position {position_id}: {str(e)}")
                self.error_handler.handle_error(e)
    
    # ==========================================================================
    # POSITION ENTRY METHODS
    # ==========================================================================
    
    def _should_enter_position(self) -> bool:
        """Check if conditions are suitable for entering a new position."""
        # Check max positions limit
        active_count = len([p for p in self.active_positions.values() 
                          if p.state == IronCondorState.ACTIVE])
        if active_count >= self.max_positions:
            self.logger.debug("Max positions limit reached")
            return False
        
        # Check IV rank
        if self.iv_rank > MAX_IV_RANK:
            self.logger.debug(f"IV rank too high: {self.iv_rank}")
            return False
        
        # Check market hours
        if not self._is_market_hours():
            return False
        
        # Check account buying power
        buying_power = self.ib_client.get_account_value('BuyingPower')
        if buying_power < 10000:
            self.logger.warning(f"Insufficient buying power: {buying_power}")
            return False
        
        return True
    
    def _find_optimal_strikes(self) -> Optional[Dict[str, Any]]:
        """Find optimal strikes for Iron Condor based on delta targets."""
        try:
            # Get options chain
            chain_data = self.option_chain_manager.get_options_chain('SPY')
            if not chain_data:
                return None
            
            # Find suitable expiration
            target_expiration = self._find_target_expiration(chain_data)
            if not target_expiration:
                return None
            
            # Get chain for target expiration
            expiry_chain = chain_data[target_expiration]
            
            # Find strikes based on delta
            call_short = self._find_strike_by_delta(
                expiry_chain['calls'], -self.target_delta
            )
            put_short = self._find_strike_by_delta(
                expiry_chain['puts'], self.target_delta
            )
            
            if not call_short or not put_short:
                return None
            
            # Find protective strikes
            spread_width = self.config.get('spread_width', 5.0)
            call_long = call_short + spread_width
            put_long = put_short - spread_width
            
            # Validate strikes exist
            if not self._validate_strikes_liquidity(
                expiry_chain, call_short, call_long, put_short, put_long
            ):
                return None
            
            return {
                'call_long_strike': call_long,
                'call_short_strike': call_short,
                'put_short_strike': put_short,
                'put_long_strike': put_long,
                'expiration': target_expiration,
                'spread_width': spread_width
            }
            
        except Exception as e:
            self.logger.error(f"Error finding optimal strikes: {str(e)}")
            return None
    
    def _find_target_expiration(self, chain_data: Dict) -> Optional[str]:
        """Find suitable expiration date."""
        expirations = sorted(chain_data.keys())
        
        for exp_str in expirations:
            exp_date = datetime.strptime(exp_str, "%Y%m%d")
            dte = (exp_date - datetime.now()).days
            
            if MIN_DAYS_TO_EXPIRATION <= dte <= MAX_DAYS_TO_EXPIRATION:
                return exp_str
        
        return None
    
    def _find_strike_by_delta(self, options: pd.DataFrame, target_delta: float) -> Optional[float]:
        """Find strike price that matches target delta."""
        if options.empty:
            return None
        
        # Find closest delta match
        options['delta_diff'] = abs(options['delta'] - target_delta)
        
        # Filter within acceptable range
        valid_options = options[options['delta_diff'] <= TARGET_DELTA_RANGE]
        
        if valid_options.empty:
            return None
        
        # Get strike with closest delta
        best_match = valid_options.loc[valid_options['delta_diff'].idxmin()]
        
        return best_match['strike']
    
    def _validate_strikes_liquidity(self, chain: Dict, *strikes: float) -> bool:
        """Validate all strikes have sufficient liquidity."""
        for strike in strikes:
            # Check calls
            call_option = chain['calls'][chain['calls']['strike'] == strike]
            if not call_option.empty:
                if (call_option['volume'].iloc[0] < MIN_VOLUME or
                    call_option['open_interest'].iloc[0] < MIN_OPEN_INTEREST):
                    return False
            
            # Check puts
            put_option = chain['puts'][chain['puts']['strike'] == strike]
            if not put_option.empty:
                if (put_option['volume'].iloc[0] < MIN_VOLUME or
                    put_option['open_interest'].iloc[0] < MIN_OPEN_INTEREST):
                    return False
        
        return True
    
    def _calculate_position_details(self, strikes: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate position sizing and risk details."""
        # Get current option prices
        chain = self.option_chain_manager.get_options_chain('SPY')[strikes['expiration']]
        
        # Calculate net credit
        call_short_price = self._get_option_price(
            chain['calls'], strikes['call_short_strike'], 'bid'
        )
        call_long_price = self._get_option_price(
            chain['calls'], strikes['call_long_strike'], 'ask'
        )
        put_short_price = self._get_option_price(
            chain['puts'], strikes['put_short_strike'], 'bid'
        )
        put_long_price = self._get_option_price(
            chain['puts'], strikes['put_long_strike'], 'ask'
        )
        
        net_credit = (call_short_price - call_long_price + 
                     put_short_price - put_long_price)
        
        # Maximum loss per contract
        max_loss = strikes['spread_width'] - net_credit
        
        # Calculate position size
        max_risk_amount = self.risk_manager.get_max_position_risk()
        quantity = int(max_risk_amount / (max_loss * SPY_CONTRACT_MULTIPLIER))
        quantity = min(quantity, 10)  # Cap at 10 contracts
        
        # Total position metrics
        total_credit = net_credit * quantity * SPY_CONTRACT_MULTIPLIER
        total_max_loss = max_loss * quantity * SPY_CONTRACT_MULTIPLIER
        
        # Target profit
        target_profit = total_credit * self.profit_target
        
        return {
            **strikes,
            'quantity': quantity,
            'net_credit': net_credit,
            'total_credit': total_credit,
            'max_loss': max_loss,
            'total_max_loss': total_max_loss,
            'target_profit': target_profit,
            'credit_ratio': net_credit / strikes['spread_width']
        }
    
    def _get_option_price(self, options: pd.DataFrame, strike: float, 
                         price_type: str) -> float:
        """Get option price from chain."""
        option = options[options['strike'] == strike]
        
        if option.empty:
            return 0.0
        
        return option[price_type].iloc[0]
    
    # ==========================================================================
    # POSITION MANAGEMENT METHODS
    # ==========================================================================
    
    def _update_position_metrics(self, position: IronCondorPosition) -> None:
        """Update position Greeks and P&L."""
        try:
            # Get current option prices
            chain = self.option_chain_manager.get_options_chain('SPY')[position.legs.expiration]
            
            # Calculate current value
            call_long_value = self._get_option_price(
                chain['calls'], position.legs.call_spread_long, 'mid'
            )
            call_short_value = self._get_option_price(
                chain['calls'], position.legs.call_spread_short, 'mid'
            )
            put_short_value = self._get_option_price(
                chain['puts'], position.legs.put_spread_short, 'mid'
            )
            put_long_value = self._get_option_price(
                chain['puts'], position.legs.put_spread_long, 'mid'
            )
            
            # Current credit (negative value means we'd pay to close)
            position.current_credit = (call_short_value - call_long_value + 
                                     put_short_value - put_long_value)
            
            # P&L calculation
            position.pnl = (position.legs.entry_credit - position.current_credit) * \
                          position.legs.quantity * SPY_CONTRACT_MULTIPLIER
            
            # Update current price
            position.current_price = self.current_spy_price
            
            # Calculate aggregate Greeks
            dte = (datetime.strptime(position.legs.expiration, "%Y%m%d") - 
                   datetime.now()).days
            
            # Simplified Greeks calculation
            position.delta = self._calculate_position_delta(position, dte)
            position.gamma = self._calculate_position_gamma(position, dte)
            position.theta = self._calculate_position_theta(position, dte)
            position.vega = self._calculate_position_vega(position, dte)
            
        except Exception as e:
            self.logger.error(f"Error updating position metrics: {str(e)}")
    
    def _calculate_position_delta(self, position: IronCondorPosition, dte: int) -> float:
        """Calculate net delta for position."""
        # Simplified calculation - would use actual Greeks
        delta = 0.0
        
        # Estimate based on distance from strikes
        if self.current_spy_price > position.legs.call_spread_short:
            delta = -0.5  # Negative delta when threatened on call side
        elif self.current_spy_price < position.legs.put_spread_short:
            delta = 0.5  # Positive delta when threatened on put side
        else:
            delta = 0.0  # Neutral when between strikes
        
        return delta * position.legs.quantity
    
    def _calculate_position_gamma(self, position: IronCondorPosition, dte: int) -> float:
        """Calculate net gamma for position."""
        # Simplified - gamma is highest ATM
        return -0.1 * position.legs.quantity  # Negative gamma for short options
    
    def _calculate_position_theta(self, position: IronCondorPosition, dte: int) -> float:
        """Calculate net theta for position."""
        # Positive theta for credit spreads
        return position.legs.entry_credit * 0.02 * position.legs.quantity * SPY_CONTRACT_MULTIPLIER
    
    def _calculate_position_vega(self, position: IronCondorPosition, dte: int) -> float:
        """Calculate net vega for position."""
        # Negative vega for short volatility
        return -10 * position.legs.quantity  # $10 per 1% IV move per contract
    
    def _check_profit_target(self, position: IronCondorPosition) -> bool:
        """Check if position has reached profit target."""
        target_profit = position.legs.entry_credit * self.profit_target * \
                       position.legs.quantity * SPY_CONTRACT_MULTIPLIER
        
        return position.pnl >= target_profit
    
    def _check_stop_loss(self, position: IronCondorPosition) -> bool:
        """Check if position has hit stop loss."""
        max_loss = position.legs.max_loss * self.stop_loss * \
                  position.legs.quantity * SPY_CONTRACT_MULTIPLIER
        
        return position.pnl <= -max_loss
    
    def _needs_adjustment(self, position: IronCondorPosition) -> bool:
        """Check if position needs adjustment due to market movement."""
        # Check if price has moved too close to short strikes
        buffer = position.legs.call_spread_width * 0.5
        
        too_close_to_call = (self.current_spy_price >= 
                           position.legs.call_spread_short - buffer)
        too_close_to_put = (self.current_spy_price <= 
                          position.legs.put_spread_short + buffer)
        
        # Check delta threshold
        delta_breach = abs(position.delta) > ADJUSTMENT_THRESHOLD
        
        return (too_close_to_call or too_close_to_put or delta_breach) and \
               position.state == IronCondorState.ACTIVE
    
    def _needs_rolling(self, position: IronCondorPosition) -> bool:
        """Check if position needs rolling due to approaching expiration."""
        dte = (datetime.strptime(position.legs.expiration, "%Y%m%d") - 
               datetime.now()).days
        
        return dte <= ROLL_DAYS_BEFORE_EXPIRY and position.pnl > 0
    
    def _close_position(self, position: IronCondorPosition, reason: str) -> None:
        """Close an Iron Condor position."""
        try:
            position.state = IronCondorState.CLOSING
            
            # Create closing orders
            closing_orders = self._create_closing_orders(position)
            
            if closing_orders:
                # Record the trade
                self._record_trade(position, reason)
                
                # Update position state
                position.state = IronCondorState.CLOSED
                
                # Remove from active positions
                del self.active_positions[position.position_id]
                
                # Update risk manager
                self.risk_manager.remove_position(position.position_id)
                
                # Emit position closed event
                self.event_manager.create_event(
                    EventType.POSITION,
                    {
                        'action': 'closed',
                        'position_id': position.position_id,
                        'reason': reason,
                        'pnl': position.pnl
                    },
                    source='IronCondorStrategy'
                )
                
                self.logger.info(f"Closed position {position.position_id} - "
                               f"Reason: {reason}, P&L: ${position.pnl:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error closing position: {str(e)}")
            position.state = IronCondorState.ACTIVE
    
    def _adjust_position(self, position: IronCondorPosition) -> None:
        """Adjust a threatened Iron Condor position."""
        try:
            position.state = IronCondorState.ADJUSTING
            
            # Determine which side is threatened
            if self.current_spy_price > position.legs.call_spread_short:
                # Call side threatened - roll up the call spread
                self._roll_call_spread(position)
            elif self.current_spy_price < position.legs.put_spread_short:
                # Put side threatened - roll down the put spread
                self._roll_put_spread(position)
            
            # Update position state
            position.state = IronCondorState.ACTIVE
            
        except Exception as e:
            self.logger.error(f"Error adjusting position: {str(e)}")
            position.state = IronCondorState.ACTIVE
    
    def _roll_position(self, position: IronCondorPosition) -> None:
        """Roll position to next expiration."""
        try:
            # Close current position
            self._close_position(position, "ROLL")
            
            # Signal to open new position in next expiration
            self.event_manager.create_event(
                EventType.STRATEGY,
                {
                    'action': 'ROLL_POSITION',
                    'strategy': 'IronCondor',
                    'previous_position': position.position_id
                },
                source='IronCondorStrategy'
            )
            
        except Exception as e:
            self.logger.error(f"Error rolling position: {str(e)}")
    
    # ==========================================================================
    # ORDER MANAGEMENT METHODS
    # ==========================================================================
    
    def _place_iron_condor_orders(self, legs: IronCondorLegs) -> Dict[str, int]:
        """Place orders for Iron Condor legs."""
        try:
            order_ids = {}
            
            # Create contracts for each leg
            contracts = {
                'call_long': ContractBuilder.create_option_contract(
                    'SPY', legs.expiration, legs.call_spread_long, 'C'
                ),
                'call_short': ContractBuilder.create_option_contract(
                    'SPY', legs.expiration, legs.call_spread_short, 'C'
                ),
                'put_short': ContractBuilder.create_option_contract(
                    'SPY', legs.expiration, legs.put_spread_short, 'P'
                ),
                'put_long': ContractBuilder.create_option_contract(
                    'SPY', legs.expiration, legs.put_spread_long, 'P'
                )
            }
            
            # Place orders as a combo
            combo_order = self.ib_client.create_combo_order(
                contracts,
                [1, -1, -1, 1],  # Buy/sell ratios
                'LMT',
                legs.entry_credit,
                legs.quantity
            )
            
            order_id = self.ib_client.place_order(combo_order)
            order_ids['combo'] = order_id
            
            return order_ids
            
        except Exception as e:
            self.logger.error(f"Error placing Iron Condor orders: {str(e)}")
            return {}
    
    def _create_closing_orders(self, position: IronCondorPosition) -> Dict[str, int]:
        """Create orders to close Iron Condor position."""
        try:
            # Create opposite combo order to close
            contracts = {
                'call_long': ContractBuilder.create_option_contract(
                    'SPY', position.legs.expiration, position.legs.call_spread_long, 'C'
                ),
                'call_short': ContractBuilder.create_option_contract(
                    'SPY', position.legs.expiration, position.legs.call_spread_short, 'C'
                ),
                'put_short': ContractBuilder.create_option_contract(
                    'SPY', position.legs.expiration, position.legs.put_spread_short, 'P'
                ),
                'put_long': ContractBuilder.create_option_contract(
                    'SPY', position.legs.expiration, position.legs.put_spread_long, 'P'
                )
            }
            
            # Opposite ratios to close
            closing_order = self.ib_client.create_combo_order(
                contracts,
                [-1, 1, 1, -1],  # Opposite of opening
                'MKT',
                0,  # Market order
                position.legs.quantity
            )
            
            order_id = self.ib_client.place_order(closing_order)
            
            return {'combo': order_id}
            
        except Exception as e:
            self.logger.error(f"Error creating closing orders: {str(e)}")
            return {}
    
    def _roll_call_spread(self, position: IronCondorPosition) -> None:
        """Roll call spread to higher strikes."""
        # Implementation for rolling call spread
        pass
    
    def _roll_put_spread(self, position: IronCondorPosition) -> None:
        """Roll put spread to lower strikes."""
        # Implementation for rolling put spread
        pass
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def _validate_trade(self, position_details: Dict[str, Any]) -> bool:
        """Validate trade meets all criteria."""
        # Check minimum credit ratio
        if position_details['credit_ratio'] < self.min_credit_ratio:
            self.logger.debug(f"Credit ratio too low: {position_details['credit_ratio']}")
            return False
        
        # Check risk/reward ratio
        risk_reward = position_details['target_profit'] / position_details['total_max_loss']
        if risk_reward < 0.25:  # Minimum 1:4 risk/reward
            self.logger.debug(f"Risk/reward too low: {risk_reward}")
            return False
        
        # Validate with risk manager
        if not self.risk_manager.validate_new_position(
            position_details['total_max_loss']
        ):
            self.logger.debug("Risk manager rejected position")
            return False
        
        return True
    
    def _calculate_confidence_score(self) -> float:
        """Calculate confidence score for the trade."""
        score = 0.5  # Base score
        
        # Adjust based on IV rank
        if self.iv_rank < 20:
            score += 0.2
        elif self.iv_rank < 35:
            score += 0.1
        
        # Adjust based on market trend
        if self._is_market_neutral():
            score += 0.2
        
        # Adjust based on time of day
        if self._is_optimal_trading_time():
            score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_iv_rank(self) -> float:
        """Calculate IV rank based on historical data."""
        # Simplified calculation
        return 30.0  # Placeholder
    
    def _calculate_iv_percentile(self) -> float:
        """Calculate IV percentile based on historical data."""
        # Simplified calculation
        return 35.0  # Placeholder
    
    def _is_market_neutral(self) -> bool:
        """Check if market is in neutral/ranging condition."""
        # Would implement actual market regime detection
        return True
    
    def _is_optimal_trading_time(self) -> bool:
        """Check if current time is optimal for trading."""
        now = datetime.now()
        return 10 <= now.hour <= 15
    
    def _is_market_hours(self) -> bool:
        """Check if market is open."""
        now = datetime.now()
        return (now.weekday() < 5 and 
                time(9, 30) <= now.time() <= time(16, 0))
    
    def _record_trade(self, position: IronCondorPosition, close_reason: str) -> None:
        """Record completed trade for analysis."""
        trade_record = {
            'position_id': position.position_id,
            'entry_time': position.entry_time,
            'close_time': datetime.now(),
            'close_reason': close_reason,
            'legs': {
                'call_long': position.legs.call_spread_long,
                'call_short': position.legs.call_spread_short,
                'put_short': position.legs.put_spread_short,
                'put_long': position.legs.put_spread_long
            },
            'entry_credit': position.legs.entry_credit,
            'exit_debit': position.current_credit,
            'pnl': position.pnl,
            'days_held': (datetime.now() - position.entry_time).days
        }
        
        self.historical_performance.append(trade_record)
        
        # Emit trade completion event
        self.event_manager.create_event(
            EventType.TRADE,
            {
                'action': 'completed',
                'trade': trade_record
            },
            source='IronCondorStrategy'
        )
    
    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get strategy performance statistics."""
        if not self.historical_performance:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_pnl': 0,
                'total_pnl': 0,
                'sharpe_ratio': 0
            }
        
        trades_df = pd.DataFrame(self.historical_performance)
        
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        
        return {
            'total_trades': total_trades,
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
            'avg_pnl': trades_df['pnl'].mean(),
            'total_pnl': trades_df['pnl'].sum(),
            'avg_days_held': trades_df['days_held'].mean(),
            'best_trade': trades_df['pnl'].max(),
            'worst_trade': trades_df['pnl'].min(),
            'current_positions': len(self.active_positions)
        }

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_iron_condor_strategy(config: Dict[str, Any]) -> IronCondorStrategy:
    """Factory function to create Iron Condor strategy instance."""
    return IronCondorStrategy(config)
