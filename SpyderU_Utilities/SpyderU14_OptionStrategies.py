#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderU14_OptionStrategies.py
Group: U (Utilities)
Purpose: Options strategy utilities and payoff calculations

Description:
    This module provides utilities for options strategy construction, payoff
    calculations, and risk analysis. Inspired by QuantConnect LEAN's 
    OptionStrategies helper class, it offers atomic strategy creation for 
    complex multi-leg options strategies with built-in validation.

Author: Mohamed Talib
Date: 2025-07-18
Version: 1.5
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Union, List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum, auto
import math

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
RISK_FREE_RATE = 0.05  # 5% default risk-free rate
DAYS_PER_YEAR = 365.25
CONTRACT_MULTIPLIER = 100

# ==============================================================================
# ENUMS
# ==============================================================================
class OptionType(Enum):
    """Option types"""
    CALL = "CALL"
    PUT = "PUT"

class PositionType(Enum):
    """Position types"""
    LONG = "LONG"
    SHORT = "SHORT"

class StrategyType(Enum):
    """Option strategy types"""
    NAKED_CALL = "naked_call"
    NAKED_PUT = "naked_put"
    COVERED_CALL = "covered_call"
    PROTECTIVE_PUT = "protective_put"
    BULL_CALL_SPREAD = "bull_call_spread"
    BEAR_PUT_SPREAD = "bear_put_spread"
    IRON_CONDOR = "iron_condor"
    IRON_BUTTERFLY = "iron_butterfly"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    CALENDAR_SPREAD = "calendar_spread"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OptionLeg:
    """Single option leg in a strategy"""
    option_type: OptionType
    position_type: PositionType
    strike: float
    expiry: datetime
    premium: float
    quantity: int = 1
    
    @property
    def is_call(self) -> bool:
        """Check if leg is a call option"""
        return self.option_type == OptionType.CALL
    
    @property
    def is_put(self) -> bool:
        """Check if leg is a put option"""
        return self.option_type == OptionType.PUT
    
    @property
    def is_long(self) -> bool:
        """Check if position is long"""
        return self.position_type == PositionType.LONG
    
    @property
    def is_short(self) -> bool:
        """Check if position is short"""
        return self.position_type == PositionType.SHORT
    
    @property
    def net_premium(self) -> float:
        """Calculate net premium (positive for credit, negative for debit)"""
        multiplier = -1 if self.is_long else 1
        return multiplier * self.premium * self.quantity

@dataclass
class OptionStrategy:
    """Multi-leg option strategy"""
    name: str
    strategy_type: StrategyType
    legs: List[OptionLeg]
    underlying_price: float
    max_profit: Optional[float] = None
    max_loss: Optional[float] = None
    breakeven_points: List[float] = field(default_factory=list)
    
    @property
    def net_premium(self) -> float:
        """Calculate total net premium"""
        return sum(leg.net_premium for leg in self.legs)
    
    @property
    def is_credit_strategy(self) -> bool:
        """Check if strategy receives net credit"""
        return self.net_premium > 0
    
    @property
    def is_debit_strategy(self) -> bool:
        """Check if strategy pays net debit"""
        return self.net_premium < 0

@dataclass
class PayoffResult:
    """Option payoff calculation result"""
    spot_prices: np.ndarray
    payoffs: np.ndarray
    max_profit: float
    max_loss: float
    breakeven_points: List[float]
    profit_probability: Optional[float] = None

# ==============================================================================
# OPTIONS STRATEGIES CLASS
# ==============================================================================
class OptionStrategies:
    """
    Option strategies utility class for payoff calculations and strategy construction.
    
    Features:
    - Payoff calculations for individual options and strategies
    - Common strategy builders (spreads, straddles, condors)
    - Risk metrics calculation
    - Breakeven analysis
    - Greeks aggregation for strategies
    """
    
    def __init__(self):
        """Initialize option strategies utility"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        self.logger.info("OptionStrategies initialized")
    
    # ==========================================================================
    # PAYOFF CALCULATIONS
    # ==========================================================================
    def calculate_option_payoff(self, option_type: str, position_type: str,
                              strike: float, premium: float, spot_price: Union[float, np.ndarray],
                              quantity: int = 1) -> Union[float, np.ndarray]:
        """
        Calculate option payoff at expiration.
        
        Args:
            option_type: "CALL" or "PUT"
            position_type: "LONG" or "SHORT"
            strike: Strike price
            premium: Option premium paid/received
            spot_price: Underlying price(s) at expiration
            quantity: Number of contracts
            
        Returns:
            Payoff value(s)
        """
        try:
            # Convert to enums for validation
            opt_type = OptionType(option_type.upper())
            pos_type = PositionType(position_type.upper())
            
            # Convert spot price to numpy array for vectorized calculation
            spot = np.array(spot_price) if not isinstance(spot_price, np.ndarray) else spot_price
            
            # Calculate intrinsic value
            if opt_type == OptionType.CALL:
                intrinsic = np.maximum(spot - strike, 0)
            else:  # PUT
                intrinsic = np.maximum(strike - spot, 0)
            
            # Apply position direction and premium
            if pos_type == PositionType.LONG:
                payoff = (intrinsic - premium) * quantity
            else:  # SHORT
                payoff = (premium - intrinsic) * quantity
            
            # Apply contract multiplier
            payoff *= CONTRACT_MULTIPLIER
            
            return payoff
            
        except Exception as e:
            self.logger.error(f"Error calculating option payoff: {str(e)}")
            return 0.0
    
    def calculate_strategy_payoff(self, strategy: OptionStrategy, 
                                spot_prices: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Calculate total payoff for a multi-leg strategy.
        
        Args:
            strategy: OptionStrategy object
            spot_prices: Underlying price(s) at expiration
            
        Returns:
            Total strategy payoff
        """
        try:
            total_payoff = 0
            
            for leg in strategy.legs:
                leg_payoff = self.calculate_option_payoff(
                    option_type=leg.option_type.value,
                    position_type=leg.position_type.value,
                    strike=leg.strike,
                    premium=leg.premium,
                    spot_price=spot_prices,
                    quantity=leg.quantity
                )
                total_payoff += leg_payoff
            
            return total_payoff
            
        except Exception as e:
            self.logger.error(f"Error calculating strategy payoff: {str(e)}")
            return 0.0
    
    def get_payoff_diagram(self, strategy: OptionStrategy, 
                          price_range: Optional[Tuple[float, float]] = None,
                          num_points: int = 100) -> PayoffResult:
        """
        Generate payoff diagram data for a strategy.
        
        Args:
            strategy: OptionStrategy object
            price_range: (min_price, max_price) tuple
            num_points: Number of price points to calculate
            
        Returns:
            PayoffResult with diagram data
        """
        try:
            # Determine price range if not provided
            if price_range is None:
                strikes = [leg.strike for leg in strategy.legs]
                min_strike = min(strikes)
                max_strike = max(strikes)
                range_width = max_strike - min_strike
                
                # Extend range by 20% on each side
                extension = max(range_width * 0.2, 10)
                price_range = (min_strike - extension, max_strike + extension)
            
            # Generate price points
            spot_prices = np.linspace(price_range[0], price_range[1], num_points)
            
            # Calculate payoffs
            payoffs = self.calculate_strategy_payoff(strategy, spot_prices)
            
            # Calculate key metrics
            max_profit = float(np.max(payoffs))
            max_loss = float(np.min(payoffs))
            
            # Find breakeven points
            breakeven_points = self._find_breakeven_points(spot_prices, payoffs)
            
            return PayoffResult(
                spot_prices=spot_prices,
                payoffs=payoffs,
                max_profit=max_profit,
                max_loss=max_loss,
                breakeven_points=breakeven_points
            )
            
        except Exception as e:
            self.logger.error(f"Error generating payoff diagram: {str(e)}")
            return PayoffResult(
                spot_prices=np.array([]),
                payoffs=np.array([]),
                max_profit=0.0,
                max_loss=0.0,
                breakeven_points=[]
            )
    
    # ==========================================================================
    # STRATEGY BUILDERS
    # ==========================================================================
    def create_bull_call_spread(self, long_strike: float, short_strike: float,
                               expiry: datetime, long_premium: float, short_premium: float,
                               underlying_price: float, quantity: int = 1) -> OptionStrategy:
        """
        Create a bull call spread strategy.
        
        Args:
            long_strike: Strike of long call (lower)
            short_strike: Strike of short call (higher)
            expiry: Expiration date
            long_premium: Premium of long call
            short_premium: Premium of short call
            underlying_price: Current underlying price
            quantity: Number of spreads
            
        Returns:
            OptionStrategy object
        """
        legs = [
            OptionLeg(
                option_type=OptionType.CALL,
                position_type=PositionType.LONG,
                strike=long_strike,
                expiry=expiry,
                premium=long_premium,
                quantity=quantity
            ),
            OptionLeg(
                option_type=OptionType.CALL,
                position_type=PositionType.SHORT,
                strike=short_strike,
                expiry=expiry,
                premium=short_premium,
                quantity=quantity
            )
        ]
        
        strategy = OptionStrategy(
            name=f"Bull Call Spread {long_strike}/{short_strike}",
            strategy_type=StrategyType.BULL_CALL_SPREAD,
            legs=legs,
            underlying_price=underlying_price
        )
        
        # Calculate key metrics
        self._calculate_spread_metrics(strategy)
        
        return strategy
    
    def create_bear_put_spread(self, long_strike: float, short_strike: float,
                              expiry: datetime, long_premium: float, short_premium: float,
                              underlying_price: float, quantity: int = 1) -> OptionStrategy:
        """
        Create a bear put spread strategy.
        
        Args:
            long_strike: Strike of long put (higher)
            short_strike: Strike of short put (lower)
            expiry: Expiration date
            long_premium: Premium of long put
            short_premium: Premium of short put
            underlying_price: Current underlying price
            quantity: Number of spreads
            
        Returns:
            OptionStrategy object
        """
        legs = [
            OptionLeg(
                option_type=OptionType.PUT,
                position_type=PositionType.LONG,
                strike=long_strike,
                expiry=expiry,
                premium=long_premium,
                quantity=quantity
            ),
            OptionLeg(
                option_type=OptionType.PUT,
                position_type=PositionType.SHORT,
                strike=short_strike,
                expiry=expiry,
                premium=short_premium,
                quantity=quantity
            )
        ]
        
        strategy = OptionStrategy(
            name=f"Bear Put Spread {long_strike}/{short_strike}",
            strategy_type=StrategyType.BEAR_PUT_SPREAD,
            legs=legs,
            underlying_price=underlying_price
        )
        
        # Calculate key metrics
        self._calculate_spread_metrics(strategy)
        
        return strategy
    
    def create_iron_condor(self, put_long_strike: float, put_short_strike: float,
                          call_short_strike: float, call_long_strike: float,
                          expiry: datetime, premiums: List[float],
                          underlying_price: float, quantity: int = 1) -> OptionStrategy:
        """
        Create an iron condor strategy.
        
        Args:
            put_long_strike: Long put strike (lowest)
            put_short_strike: Short put strike
            call_short_strike: Short call strike
            call_long_strike: Long call strike (highest)
            expiry: Expiration date
            premiums: [long_put_premium, short_put_premium, short_call_premium, long_call_premium]
            underlying_price: Current underlying price
            quantity: Number of iron condors
            
        Returns:
            OptionStrategy object
        """
        legs = [
            OptionLeg(
                option_type=OptionType.PUT,
                position_type=PositionType.LONG,
                strike=put_long_strike,
                expiry=expiry,
                premium=premiums[0],
                quantity=quantity
            ),
            OptionLeg(
                option_type=OptionType.PUT,
                position_type=PositionType.SHORT,
                strike=put_short_strike,
                expiry=expiry,
                premium=premiums[1],
                quantity=quantity
            ),
            OptionLeg(
                option_type=OptionType.CALL,
                position_type=PositionType.SHORT,
                strike=call_short_strike,
                expiry=expiry,
                premium=premiums[2],
                quantity=quantity
            ),
            OptionLeg(
                option_type=OptionType.CALL,
                position_type=PositionType.LONG,
                strike=call_long_strike,
                expiry=expiry,
                premium=premiums[3],
                quantity=quantity
            )
        ]
        
        strategy = OptionStrategy(
            name=f"Iron Condor {put_long_strike}/{put_short_strike}/{call_short_strike}/{call_long_strike}",
            strategy_type=StrategyType.IRON_CONDOR,
            legs=legs,
            underlying_price=underlying_price
        )
        
        # Calculate key metrics
        self._calculate_condor_metrics(strategy)
        
        return strategy
    
    def create_straddle(self, strike: float, expiry: datetime,
                       call_premium: float, put_premium: float,
                       underlying_price: float, position_type: str = "LONG",
                       quantity: int = 1) -> OptionStrategy:
        """
        Create a straddle strategy.
        
        Args:
            strike: Strike price (same for call and put)
            expiry: Expiration date
            call_premium: Call option premium
            put_premium: Put option premium
            underlying_price: Current underlying price
            position_type: "LONG" or "SHORT"
            quantity: Number of straddles
            
        Returns:
            OptionStrategy object
        """
        pos_type = PositionType(position_type.upper())
        
        legs = [
            OptionLeg(
                option_type=OptionType.CALL,
                position_type=pos_type,
                strike=strike,
                expiry=expiry,
                premium=call_premium,
                quantity=quantity
            ),
            OptionLeg(
                option_type=OptionType.PUT,
                position_type=pos_type,
                strike=strike,
                expiry=expiry,
                premium=put_premium,
                quantity=quantity
            )
        ]
        
        strategy = OptionStrategy(
            name=f"{position_type.title()} Straddle {strike}",
            strategy_type=StrategyType.STRADDLE,
            legs=legs,
            underlying_price=underlying_price
        )
        
        # Calculate key metrics
        self._calculate_straddle_metrics(strategy)
        
        return strategy
    
    # ==========================================================================
    # RISK ANALYSIS
    # ==========================================================================
    def calculate_max_profit(self, strategy: OptionStrategy) -> float:
        """Calculate maximum profit for a strategy"""
        try:
            payoff_result = self.get_payoff_diagram(strategy)
            return payoff_result.max_profit
        except Exception as e:
            self.logger.error(f"Error calculating max profit: {str(e)}")
            return 0.0
    
    def calculate_max_loss(self, strategy: OptionStrategy) -> float:
        """Calculate maximum loss for a strategy"""
        try:
            payoff_result = self.get_payoff_diagram(strategy)
            return payoff_result.max_loss
        except Exception as e:
            self.logger.error(f"Error calculating max loss: {str(e)}")
            return 0.0
    
    def calculate_breakeven_points(self, strategy: OptionStrategy) -> List[float]:
        """Calculate breakeven points for a strategy"""
        try:
            payoff_result = self.get_payoff_diagram(strategy)
            return payoff_result.breakeven_points
        except Exception as e:
            self.logger.error(f"Error calculating breakeven points: {str(e)}")
            return []
    
    def calculate_profit_probability(self, strategy: OptionStrategy,
                                   expected_move: float, 
                                   time_to_expiry: float) -> float:
        """
        Calculate probability of profit (simplified model).
        
        Args:
            strategy: OptionStrategy object
            expected_move: Expected price movement (percentage)
            time_to_expiry: Time to expiration in days
            
        Returns:
            Probability of profit (0-1)
        """
        try:
            breakeven_points = self.calculate_breakeven_points(strategy)
            if not breakeven_points:
                return 0.0
            
            current_price = strategy.underlying_price
            
            # Simple normal distribution approximation
            std_dev = expected_move * current_price * math.sqrt(time_to_expiry / 365.25)
            
            # Calculate probability based on breakeven points
            # This is a simplified calculation
            if len(breakeven_points) == 1:
                # Single breakeven (directional strategy)
                be_point = breakeven_points[0]
                if strategy.is_credit_strategy:
                    # Profit if price stays between breakevens or outside for credit spreads
                    z_score = abs(be_point - current_price) / std_dev if std_dev > 0 else 0
                    prob = 1 - 2 * (1 - self._normal_cdf(z_score))
                else:
                    # Profit if price moves beyond breakeven
                    z_score = abs(be_point - current_price) / std_dev if std_dev > 0 else 0
                    prob = 2 * (1 - self._normal_cdf(z_score))
            else:
                # Multiple breakevens (e.g., iron condor, straddle)
                be_min, be_max = min(breakeven_points), max(breakeven_points)
                
                if strategy.is_credit_strategy:
                    # Profit if price stays between breakevens
                    z1 = (be_min - current_price) / std_dev if std_dev > 0 else 0
                    z2 = (be_max - current_price) / std_dev if std_dev > 0 else 0
                    prob = self._normal_cdf(z2) - self._normal_cdf(z1)
                else:
                    # Profit if price moves outside breakevens
                    z1 = (be_min - current_price) / std_dev if std_dev > 0 else 0
                    z2 = (be_max - current_price) / std_dev if std_dev > 0 else 0
                    prob = 1 - (self._normal_cdf(z2) - self._normal_cdf(z1))
            
            return max(0.0, min(1.0, prob))
            
        except Exception as e:
            self.logger.error(f"Error calculating profit probability: {str(e)}")
            return 0.0
    
    # ==========================================================================
    # PRIVATE HELPER METHODS
    # ==========================================================================
    def _find_breakeven_points(self, prices: np.ndarray, payoffs: np.ndarray) -> List[float]:
        """Find breakeven points where payoff crosses zero"""
        breakevens = []
        
        for i in range(len(payoffs) - 1):
            if (payoffs[i] <= 0 and payoffs[i+1] > 0) or (payoffs[i] >= 0 and payoffs[i+1] < 0):
                # Linear interpolation to find exact crossover point
                if payoffs[i+1] != payoffs[i]:
                    x = prices[i] + (prices[i+1] - prices[i]) * (-payoffs[i] / (payoffs[i+1] - payoffs[i]))
                    breakevens.append(round(x, 2))
        
        return breakevens
    
    def _calculate_spread_metrics(self, strategy: OptionStrategy) -> None:
        """Calculate metrics for spread strategies"""
        net_premium = strategy.net_premium
        strikes = [leg.strike for leg in strategy.legs]
        strike_diff = abs(max(strikes) - min(strikes)) * CONTRACT_MULTIPLIER
        
        if strategy.is_debit_strategy:
            strategy.max_loss = abs(net_premium)
            strategy.max_profit = strike_diff - abs(net_premium)
        else:
            strategy.max_profit = net_premium
            strategy.max_loss = strike_diff - net_premium
    
    def _calculate_condor_metrics(self, strategy: OptionStrategy) -> None:
        """Calculate metrics for iron condor strategies"""
        net_premium = strategy.net_premium
        
        # Find wing widths
        strikes = sorted([leg.strike for leg in strategy.legs])
        put_wing = (strikes[1] - strikes[0]) * CONTRACT_MULTIPLIER
        call_wing = (strikes[3] - strikes[2]) * CONTRACT_MULTIPLIER
        max_wing = max(put_wing, call_wing)
        
        strategy.max_profit = net_premium
        strategy.max_loss = max_wing - net_premium
    
    def _calculate_straddle_metrics(self, strategy: OptionStrategy) -> None:
        """Calculate metrics for straddle strategies"""
        net_premium = strategy.net_premium
        
        if strategy.legs[0].is_long:  # Long straddle
            strategy.max_loss = abs(net_premium)
            strategy.max_profit = float('inf')  # Theoretically unlimited
        else:  # Short straddle
            strategy.max_profit = net_premium
            strategy.max_loss = float('inf')  # Theoretically unlimited
    
    def _normal_cdf(self, x: float) -> float:
        """Cumulative distribution function for standard normal distribution"""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_option_strategies: Optional[OptionStrategies] = None

def get_option_strategies() -> OptionStrategies:
    """
    Get singleton instance of option strategies utility.
    
    Returns:
        OptionStrategies instance
    """
    global _option_strategies
    if _option_strategies is None:
        _option_strategies = OptionStrategies()
    return _option_strategies

def calculate_option_payoff(option_type: str, position_type: str, strike: float,
                          premium: float, spot_price: Union[float, np.ndarray],
                          quantity: int = 1) -> Union[float, np.ndarray]:
    """
    Quick option payoff calculation.
    
    Args:
        option_type: "CALL" or "PUT"
        position_type: "LONG" or "SHORT"
        strike: Strike price
        premium: Option premium
        spot_price: Underlying price at expiration
        quantity: Number of contracts
        
    Returns:
        Option payoff
    """
    strategies = get_option_strategies()
    return strategies.calculate_option_payoff(
        option_type, position_type, strike, premium, spot_price, quantity
    )

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test option strategies
    print("Testing Option Strategies...")
    
    strategies = get_option_strategies()
    
    # Test individual option payoff
    print(f"\n✅ Testing individual option payoff...")
    spot_prices = np.array([450, 455, 460, 465, 470])
    call_payoffs = calculate_option_payoff("CALL", "LONG", 460, 5.0, spot_prices)
    put_payoffs = calculate_option_payoff("PUT", "LONG", 460, 5.0, spot_prices)
    
    print(f"   Spot prices: {spot_prices}")
    print(f"   Long 460 Call payoffs: {call_payoffs}")
    print(f"   Long 460 Put payoffs: {put_payoffs}")
    
    # Test bull call spread
    print(f"\n✅ Testing bull call spread...")
    expiry = datetime.now() + timedelta(days=30)
    bull_call = strategies.create_bull_call_spread(
        long_strike=450,
        short_strike=460,
        expiry=expiry,
        long_premium=8.0,
        short_premium=3.0,
        underlying_price=455
    )
    
    print(f"   Strategy: {bull_call.name}")
    print(f"   Net premium: ${bull_call.net_premium:.2f}")
    print(f"   Max profit: ${bull_call.max_profit:.2f}")
    print(f"   Max loss: ${bull_call.max_loss:.2f}")
    
    # Test payoff diagram
    print(f"\n✅ Testing payoff diagram...")
    payoff_result = strategies.get_payoff_diagram(bull_call)
    print(f"   Price range: ${payoff_result.spot_prices[0]:.2f} - ${payoff_result.spot_prices[-1]:.2f}")
    print(f"   Breakeven points: {payoff_result.breakeven_points}")
    
    # Test iron condor
    print(f"\n✅ Testing iron condor...")
    iron_condor = strategies.create_iron_condor(
        put_long_strike=440,
        put_short_strike=450,
        call_short_strike=470,
        call_long_strike=480,
        expiry=expiry,
        premiums=[2.0, 6.0, 6.0, 2.0],  # [long_put, short_put, short_call, long_call]
        underlying_price=460
    )
    
    print(f"   Strategy: {iron_condor.name}")
    print(f"   Net premium: ${iron_condor.net_premium:.2f}")
    print(f"   Max profit: ${iron_condor.max_profit:.2f}")
    print(f"   Max loss: ${iron_condor.max_loss:.2f}")
    
    # Test straddle
    print(f"\n✅ Testing long straddle...")
    straddle = strategies.create_straddle(
        strike=460,
        expiry=expiry,
        call_premium=8.0,
        put_premium=8.0,
        underlying_price=460,
        position_type="LONG"
    )
    
    print(f"   Strategy: {straddle.name}")
    print(f"   Net premium: ${straddle.net_premium:.2f}")
    print(f"   Max loss: ${straddle.max_loss:.2f}")
    
    # Test profit probability
    print(f"\n✅ Testing profit probability...")
    prob = strategies.calculate_profit_probability(bull_call, 0.15, 30)  # 15% expected move, 30 days
    print(f"   Bull call spread profit probability: {prob:.2%}")
    
    print("\n✅ Option strategies test completed!")
