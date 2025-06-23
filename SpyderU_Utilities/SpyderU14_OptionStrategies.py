#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderU14_OptionStrategies.py
Group: U (Utilities)
Purpose: Options strategy helper class inspired by LEAN's OptionStrategies

Description:
    Professional options strategy builder inspired by QuantConnect LEAN's 
    OptionStrategies helper class. Provides atomic strategy creation for 
    complex multi-leg options strategies with built-in validation and 
    position group management.

Based on: QuantConnect LEAN OptionStrategies patterns
Author: Mohamed Talib
Created: 2025-06-23
Version: 2.0 (Enhanced with LEAN patterns)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
import itertools
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
import uuid

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
from SpyderU_Utilities.SpyderU07_Constants import OptionType, OrderAction

# ==============================================================================
# ENUMS
# ==============================================================================
class StrategyType(Enum):
    """Option strategy types (from LEAN)"""
    IRON_CONDOR = "iron_condor"
    IRON_BUTTERFLY = "iron_butterfly"
    PUT_CALENDAR_SPREAD = "put_calendar_spread"
    CALL_CALENDAR_SPREAD = "call_calendar_spread"
    SHORT_PUT_CALENDAR_SPREAD = "short_put_calendar_spread"
    SHORT_CALL_CALENDAR_SPREAD = "short_call_calendar_spread"
    BULL_PUT_SPREAD = "bull_put_spread"
    BEAR_CALL_SPREAD = "bear_call_spread"
    LONG_STRADDLE = "long_straddle"
    SHORT_STRADDLE = "short_straddle"
    PROTECTIVE_PUT = "protective_put"
    COVERED_CALL = "covered_call"
    COLLAR = "collar"

class OptionRight(Enum):
    """Option rights (LEAN compatible)"""
    CALL = "Call"
    PUT = "Put"

class PositionSide(Enum):
    """Position side (LEAN compatible)"""
    LONG = 1
    SHORT = -1

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OptionLeg:
    """Individual option leg (inspired by LEAN's OptionLeg)"""
    symbol: str
    option_right: OptionRight
    strike: float
    expiry: datetime
    quantity: int  # Positive for buy, negative for sell
    
    @property
    def is_long(self) -> bool:
        return self.quantity > 0
    
    @property
    def is_short(self) -> bool:
        return self.quantity < 0

@dataclass
class OptionStrategy:
    """Complete option strategy (inspired by LEAN's OptionStrategy)"""
    strategy_type: StrategyType
    underlying_symbol: str
    legs: List[OptionLeg]
    strategy_id: str = field(default_factory=lambda: f"STRAT_{uuid.uuid4().hex[:8]}")
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate strategy after creation"""
        self._validate_strategy()
    
    def _validate_strategy(self):
        """Validate strategy legs (LEAN-style validation)"""
        if not self.legs:
            raise ValueError("Strategy must have at least one leg")
        
        # Validate leg count for specific strategies
        expected_legs = {
            StrategyType.IRON_CONDOR: 4,
            StrategyType.IRON_BUTTERFLY: 4,
            StrategyType.PUT_CALENDAR_SPREAD: 2,
            StrategyType.CALL_CALENDAR_SPREAD: 2,
            StrategyType.BULL_PUT_SPREAD: 2,
            StrategyType.BEAR_CALL_SPREAD: 2,
            StrategyType.LONG_STRADDLE: 2,
            StrategyType.SHORT_STRADDLE: 2,
        }
        
        if self.strategy_type in expected_legs:
            expected = expected_legs[self.strategy_type]
            if len(self.legs) != expected:
                raise ValueError(f"{self.strategy_type.value} requires {expected} legs, got {len(self.legs)}")
    
    @property
    def total_quantity(self) -> int:
        """Total signed quantity across all legs"""
        return sum(leg.quantity for leg in self.legs)
    
    @property
    def is_net_long(self) -> bool:
        """Check if strategy is net long"""
        return self.total_quantity > 0
    
    @property
    def is_net_short(self) -> bool:
        """Check if strategy is net short"""
        return self.total_quantity < 0
    
    @property
    def is_net_neutral(self) -> bool:
        """Check if strategy is net neutral"""
        return self.total_quantity == 0

# ==============================================================================
# MAIN CLASS - Options Strategies Helper
# ==============================================================================
class SpyderOptionStrategies:
    """
    Options strategy builder inspired by QuantConnect LEAN's OptionStrategies.
    
    Provides atomic creation of complex multi-leg options strategies with
    built-in validation and professional error handling.
    
    Key Features:
    - LEAN-compatible strategy definitions
    - Automatic leg validation
    - Professional error handling
    - Strategy optimization utilities
    """
    
    def __init__(self):
        """Initialize the options strategies helper"""
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        
        self.logger.info("SpyderOptionStrategies initialized with LEAN patterns")
    
    # ==========================================================================
    # IRON STRATEGIES (From LEAN IronCondorStrategyAlgorithm.py)
    # ==========================================================================
    @staticmethod
    def iron_condor(underlying_symbol: str, 
                   long_put_strike: float,
                   short_put_strike: float, 
                   short_call_strike: float,
                   long_call_strike: float,
                   expiry: datetime,
                   quantity: int = 1) -> OptionStrategy:
        """
        Create Iron Condor strategy (from LEAN's IronCondorStrategyAlgorithm).
        
        Iron Condor = Bull Put Spread + Bear Call Spread
        
        Args:
            underlying_symbol: Underlying symbol (e.g., "SPY")
            long_put_strike: Long put strike (lowest)
            short_put_strike: Short put strike
            short_call_strike: Short call strike  
            long_call_strike: Long call strike (highest)
            expiry: Expiration date
            quantity: Number of spreads (default 1)
            
        Returns:
            OptionStrategy object
        """
        # Validate strike order (LEAN-style validation)
        strikes = [long_put_strike, short_put_strike, short_call_strike, long_call_strike]
        if strikes != sorted(strikes):
            raise ValueError("Iron Condor strikes must be in ascending order: long_put < short_put < short_call < long_call")
        
        legs = [
            # Bull Put Spread (put side)
            OptionLeg(f"{underlying_symbol}_{expiry.strftime('%y%m%d')}P{long_put_strike:08.0f}", 
                     OptionRight.PUT, long_put_strike, expiry, quantity),  # Buy long put
            OptionLeg(f"{underlying_symbol}_{expiry.strftime('%y%m%d')}P{short_put_strike:08.0f}", 
                     OptionRight.PUT, short_put_strike, expiry, -quantity),  # Sell short put
            
            # Bear Call Spread (call side)  
            OptionLeg(f"{underlying_symbol}_{expiry.strftime('%y%m%d')}C{short_call_strike:08.0f}", 
                     OptionRight.CALL, short_call_strike, expiry, -quantity),  # Sell short call
            OptionLeg(f"{underlying_symbol}_{expiry.strftime('%y%m%d')}C{long_call_strike:08.0f}", 
                     OptionRight.CALL, long_call_strike, expiry, quantity),  # Buy long call
        ]
        
        return OptionStrategy(StrategyType.IRON_CONDOR, underlying_symbol, legs)
    
    @staticmethod
    def iron_butterfly(underlying_symbol: str,
                      long_put_strike: float,
                      short_strike: float,  # ATM strike (both call and put)
                      long_call_strike: float,
                      expiry: datetime,
                      quantity: int = 1) -> OptionStrategy:
        """
        Create Iron Butterfly strategy.
        
        Iron Butterfly = Short Straddle + Long Strangle
        Higher credit than Iron Condor but narrower profit zone.
        
        Args:
            underlying_symbol: Underlying symbol
            long_put_strike: Long put strike (lower)
            short_strike: Short strike (ATM for both call and put)
            long_call_strike: Long call strike (higher)
            expiry: Expiration date
            quantity: Number of spreads
            
        Returns:
            OptionStrategy object
        """
        # Validate strikes
        if not (long_put_strike < short_strike < long_call_strike):
            raise ValueError("Iron Butterfly strikes must be: long_put < short_strike < long_call")
        
        legs = [
            # Long wings
            OptionLeg(f"{underlying_symbol}_{expiry.strftime('%y%m%d')}P{long_put_strike:08.0f}", 
                     OptionRight.PUT, long_put_strike, expiry, quantity),
            OptionLeg(f"{underlying_symbol}_{expiry.strftime('%y%m%d')}C{long_call_strike:08.0f}", 
                     OptionRight.CALL, long_call_strike, expiry, quantity),
            
            # Short body (double quantity at ATM)
            OptionLeg(f"{underlying_symbol}_{expiry.strftime('%y%m%d')}P{short_strike:08.0f}", 
                     OptionRight.PUT, short_strike, expiry, -quantity),
            OptionLeg(f"{underlying_symbol}_{expiry.strftime('%y%m%d')}C{short_strike:08.0f}", 
                     OptionRight.CALL, short_strike, expiry, -quantity),
        ]
        
        return OptionStrategy(StrategyType.IRON_BUTTERFLY, underlying_symbol, legs)
    
    # ==========================================================================
    # CALENDAR SPREADS (From LEAN Calendar Spread Algorithms)
    # ==========================================================================
    @staticmethod
    def put_calendar_spread(underlying_symbol: str,
                           strike: float,
                           near_expiry: datetime,
                           far_expiry: datetime,
                           quantity: int = 1) -> OptionStrategy:
        """
        Create Put Calendar Spread (from LEAN's LongAndShortPutCalendarSpreadStrategiesAlgorithm).
        
        Put Calendar = Sell near-term put + Buy far-term put (same strike)
        
        Args:
            underlying_symbol: Underlying symbol
            strike: Strike price (same for both legs)
            near_expiry: Near-term expiration (sell)
            far_expiry: Far-term expiration (buy)
            quantity: Number of spreads
            
        Returns:
            OptionStrategy object
        """
        if near_expiry >= far_expiry:
            raise ValueError("Near expiry must be before far expiry")
        
        legs = [
            # Sell near-term put
            OptionLeg(f"{underlying_symbol}_{near_expiry.strftime('%y%m%d')}P{strike:08.0f}", 
                     OptionRight.PUT, strike, near_expiry, -quantity),
            # Buy far-term put
            OptionLeg(f"{underlying_symbol}_{far_expiry.strftime('%y%m%d')}P{strike:08.0f}", 
                     OptionRight.PUT, strike, far_expiry, quantity),
        ]
        
        return OptionStrategy(StrategyType.PUT_CALENDAR_SPREAD, underlying_symbol, legs)
    
    @staticmethod
    def short_put_calendar_spread(underlying_symbol: str,
                                 strike: float,
                                 near_expiry: datetime,
                                 far_expiry: datetime,
                                 quantity: int = 1) -> OptionStrategy:
        """
        Create Short Put Calendar Spread (reverse of put calendar).
        
        Short Put Calendar = Buy near-term put + Sell far-term put
        """
        calendar = SpyderOptionStrategies.put_calendar_spread(
            underlying_symbol, strike, near_expiry, far_expiry, quantity
        )
        
        # Reverse the quantities
        for leg in calendar.legs:
            leg.quantity *= -1
        
        calendar.strategy_type = StrategyType.SHORT_PUT_CALENDAR_SPREAD
        return calendar
    
    @staticmethod
    def call_calendar_spread(underlying_symbol: str,
                            strike: float,
                            near_expiry: datetime,
                            far_expiry: datetime,
                            quantity: int = 1) -> OptionStrategy:
        """
        Create Call Calendar Spread (from LEAN's LongAndShortCallCalendarSpreadStrategiesAlgorithm).
        
        Call Calendar = Sell near-term call + Buy far-term call (same strike)
        """
        if near_expiry >= far_expiry:
            raise ValueError("Near expiry must be before far expiry")
        
        legs = [
            # Sell near-term call
            OptionLeg(f"{underlying_symbol}_{near_expiry.strftime('%y%m%d')}C{strike:08.0f}", 
                     OptionRight.CALL, strike, near_expiry, -quantity),
            # Buy far-term call
            OptionLeg(f"{underlying_symbol}_{far_expiry.strftime('%y%m%d')}C{strike:08.0f}", 
                     OptionRight.CALL, strike, far_expiry, quantity),
        ]
        
        return OptionStrategy(StrategyType.CALL_CALENDAR_SPREAD, underlying_symbol, legs)
    
    @staticmethod
    def short_call_calendar_spread(underlying_symbol: str,
                                  strike: float,
                                  near_expiry: datetime,
                                  far_expiry: datetime,
                                  quantity: int = 1) -> OptionStrategy:
        """Create Short Call Calendar Spread (reverse of call calendar)."""
        calendar = SpyderOptionStrategies.call_calendar_spread(
            underlying_symbol, strike, near_expiry, far_expiry, quantity
        )
        
        # Reverse the quantities
        for leg in calendar.legs:
            leg.quantity *= -1
        
        calendar.strategy_type = StrategyType.SHORT_CALL_CALENDAR_SPREAD
        return calendar
    
    # ==========================================================================
    # VERTICAL SPREADS
    # ==========================================================================
    @staticmethod
    def bull_put_spread(underlying_symbol: str,
                       long_put_strike: float,
                       short_put_strike: float,
                       expiry: datetime,
                       quantity: int = 1) -> OptionStrategy:
        """
        Create Bull Put Spread (credit spread).
        
        Bull Put = Sell higher strike put + Buy lower strike put
        """
        if long_put_strike >= short_put_strike:
            raise ValueError("Bull put spread: long_put_strike must be < short_put_strike")
        
        legs = [
            OptionLeg(f"{underlying_symbol}_{expiry.strftime('%y%m%d')}P{long_put_strike:08.0f}", 
                     OptionRight.PUT, long_put_strike, expiry, quantity),  # Buy lower strike
            OptionLeg(f"{underlying_symbol}_{expiry.strftime('%y%m%d')}P{short_put_strike:08.0f}", 
                     OptionRight.PUT, short_put_strike, expiry, -quantity),  # Sell higher strike
        ]
        
        return OptionStrategy(StrategyType.BULL_PUT_SPREAD, underlying_symbol, legs)
    
    @staticmethod
    def bear_call_spread(underlying_symbol: str,
                        short_call_strike: float,
                        long_call_strike: float,
                        expiry: datetime,
                        quantity: int = 1) -> OptionStrategy:
        """
        Create Bear Call Spread (credit spread).
        
        Bear Call = Sell lower strike call + Buy higher strike call
        """
        if short_call_strike >= long_call_strike:
            raise ValueError("Bear call spread: short_call_strike must be < long_call_strike")
        
        legs = [
            OptionLeg(f"{underlying_symbol}_{expiry.strftime('%y%m%d')}C{short_call_strike:08.0f}", 
                     OptionRight.CALL, short_call_strike, expiry, -quantity),  # Sell lower strike
            OptionLeg(f"{underlying_symbol}_{expiry.strftime('%y%m%d')}C{long_call_strike:08.0f}", 
                     OptionRight.CALL, long_call_strike, expiry, quantity),  # Buy higher strike
        ]
        
        return OptionStrategy(StrategyType.BEAR_CALL_SPREAD, underlying_symbol, legs)
    
    # ==========================================================================
    # STRADDLES AND STRANGLES
    # ==========================================================================
    @staticmethod
    def long_straddle(underlying_symbol: str,
                     strike: float,
                     expiry: datetime,
                     quantity: int = 1) -> OptionStrategy:
        """Create Long Straddle (buy call + buy put, same strike)."""
        legs = [
            OptionLeg(f"{underlying_symbol}_{expiry.strftime('%y%m%d')}C{strike:08.0f}", 
                     OptionRight.CALL, strike, expiry, quantity),
            OptionLeg(f"{underlying_symbol}_{expiry.strftime('%y%m%d')}P{strike:08.0f}", 
                     OptionRight.PUT, strike, expiry, quantity),
        ]
        
        return OptionStrategy(StrategyType.LONG_STRADDLE, underlying_symbol, legs)
    
    @staticmethod
    def short_straddle(underlying_symbol: str,
                      strike: float,
                      expiry: datetime,
                      quantity: int = 1) -> OptionStrategy:
        """Create Short Straddle (sell call + sell put, same strike)."""
        legs = [
            OptionLeg(f"{underlying_symbol}_{expiry.strftime('%y%m%d')}C{strike:08.0f}", 
                     OptionRight.CALL, strike, expiry, -quantity),
            OptionLeg(f"{underlying_symbol}_{expiry.strftime('%y%m%d')}P{strike:08.0f}", 
                     OptionRight.PUT, strike, expiry, -quantity),
        ]
        
        return OptionStrategy(StrategyType.SHORT_STRADDLE, underlying_symbol, legs)
    
    # ==========================================================================
    # UTILITY METHODS (LEAN-Style)
    # ==========================================================================
    @staticmethod
    def validate_strategy_legs(strategy: OptionStrategy) -> bool:
        """
        Validate strategy legs (inspired by LEAN's position group validation).
        
        Args:
            strategy: Strategy to validate
            
        Returns:
            True if valid, raises exception if invalid
        """
        if not strategy.legs:
            raise ValueError("Strategy must have at least one leg")
        
        # Check for duplicate legs
        leg_keys = [(leg.option_right, leg.strike, leg.expiry) for leg in strategy.legs]
        if len(leg_keys) != len(set(leg_keys)):
            raise ValueError("Strategy contains duplicate legs")
        
        # Strategy-specific validations
        if strategy.strategy_type == StrategyType.IRON_CONDOR:
            SpyderOptionStrategies._validate_iron_condor(strategy)
        elif strategy.strategy_type in [StrategyType.PUT_CALENDAR_SPREAD, StrategyType.CALL_CALENDAR_SPREAD]:
            SpyderOptionStrategies._validate_calendar_spread(strategy)
        
        return True
    
    @staticmethod
    def _validate_iron_condor(strategy: OptionStrategy):
        """Validate Iron Condor specific requirements"""
        if len(strategy.legs) != 4:
            raise ValueError("Iron Condor must have exactly 4 legs")
        
        puts = [leg for leg in strategy.legs if leg.option_right == OptionRight.PUT]
        calls = [leg for leg in strategy.legs if leg.option_right == OptionRight.CALL]
        
        if len(puts) != 2 or len(calls) != 2:
            raise ValueError("Iron Condor must have 2 puts and 2 calls")
        
        # Check quantities (should be +1, -1, -1, +1 pattern)
        quantities = sorted([leg.quantity for leg in strategy.legs])
        expected = [-1, -1, 1, 1]  # For quantity=1
        if quantities != expected:
            raise ValueError(f"Iron Condor quantities invalid. Expected pattern: {expected}, got: {quantities}")
    
    @staticmethod
    def _validate_calendar_spread(strategy: OptionStrategy):
        """Validate Calendar Spread specific requirements"""
        if len(strategy.legs) != 2:
            raise ValueError("Calendar Spread must have exactly 2 legs")
        
        leg1, leg2 = strategy.legs
        
        # Same strike, same option type, different expiries
        if leg1.strike != leg2.strike:
            raise ValueError("Calendar Spread legs must have same strike")
        
        if leg1.option_right != leg2.option_right:
            raise ValueError("Calendar Spread legs must be same option type")
        
        if leg1.expiry == leg2.expiry:
            raise ValueError("Calendar Spread legs must have different expiries")
        
        # One leg should be short, one long
        quantities = [leg1.quantity, leg2.quantity]
        if not (quantities[0] * quantities[1] < 0):  # Opposite signs
            raise ValueError("Calendar Spread must have one long and one short leg")
    
    @staticmethod
    def get_strategy_summary(strategy: OptionStrategy) -> Dict[str, Any]:
        """Get comprehensive strategy summary (LEAN-style)"""
        return {
            'strategy_type': strategy.strategy_type.value,
            'strategy_id': strategy.strategy_id,
            'underlying_symbol': strategy.underlying_symbol,
            'leg_count': len(strategy.legs),
            'total_quantity': strategy.total_quantity,
            'is_net_long': strategy.is_net_long,
            'is_net_short': strategy.is_net_short,
            'is_net_neutral': strategy.is_net_neutral,
            'created_at': strategy.created_at,
            'legs': [
                {
                    'symbol': leg.symbol,
                    'option_right': leg.option_right.value,
                    'strike': leg.strike,
                    'expiry': leg.expiry.strftime('%Y-%m-%d'),
                    'quantity': leg.quantity,
                    'side': 'LONG' if leg.is_long else 'SHORT'
                }
                for leg in strategy.legs
            ]
        }

# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================
def create_spy_iron_condor(long_put: float, short_put: float, 
                          short_call: float, long_call: float, 
                          expiry: datetime, quantity: int = 1) -> OptionStrategy:
    """Quick SPY Iron Condor creation"""
    return SpyderOptionStrategies.iron_condor("SPY", long_put, short_put, short_call, long_call, expiry, quantity)

def create_spy_calendar_spread(strike: float, near_expiry: datetime, 
                              far_expiry: datetime, option_type: str = "PUT") -> OptionStrategy:
    """Quick SPY Calendar Spread creation"""
    if option_type.upper() == "PUT":
        return SpyderOptionStrategies.put_calendar_spread("SPY", strike, near_expiry, far_expiry)
    else:
        return SpyderOptionStrategies.call_calendar_spread("SPY", strike, near_expiry, far_expiry)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test LEAN-inspired options strategies
    from datetime import datetime, timedelta
    
    print("Testing LEAN-inspired Options Strategies:")
    print("=" * 50)
    
    expiry = datetime.now() + timedelta(days=30)
    near_expiry = datetime.now() + timedelta(days=7)
    
    # Test Iron Condor
    ic = SpyderOptionStrategies.iron_condor("SPY", 580, 590, 610, 620, expiry)
    print(f"Iron Condor: {ic.strategy_type.value}")
    print(f"Legs: {len(ic.legs)}")
    print(f"Net Neutral: {ic.is_net_neutral}")
    
    # Test Calendar Spread
    calendar = SpyderOptionStrategies.put_calendar_spread("SPY", 600, near_expiry, expiry)
    print(f"\nPut Calendar: {calendar.strategy_type.value}")
    print(f"Net Long: {calendar.is_net_long}")
    
    # Test validation
    try:
        SpyderOptionStrategies.validate_strategy_legs(ic)
        print("\n✅ Iron Condor validation passed")
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
    
    print("\n✅ LEAN-inspired OptionStrategies implementation ready!")
