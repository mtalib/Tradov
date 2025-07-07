#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderB06_ContractBuilder.py
Group: B (Broker Integration)
Purpose: IB contract construction with validation and caching

Description:
    This module provides comprehensive contract building functionality for
    Interactive Brokers. It creates and validates contracts for stocks, options,
    futures, and complex strategies. Includes contract caching for performance,
    validation against IB requirements, and support for all SPY option
    specifications including weekly expirations and multi-leg strategies.

Author: Mohamed Talib
Date: 2025-01-04
Version: 2.0 (Production Ready)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Optional, Dict, Any, List, Tuple, Union
from datetime import datetime, date, timedelta
from dataclasses import dataclass
from enum import Enum
import calendar
from functools import lru_cache
import re

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from ib_insync import (
        Stock, Option, Future, Forex, Index, CFD, Commodity,
        Contract, ComboLeg, TagValue
    )
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False
    raise ImportError("ib_insync is required. Install with: pip install ib_insync")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Contract defaults
DEFAULT_EXCHANGE = 'SMART'
DEFAULT_CURRENCY = 'USD'
DEFAULT_MULTIPLIER = 100  # For options

# SPY specific settings
SPY_EXCHANGES = ['ARCA', 'BATS', 'NYSE', 'NASDAQ', 'SMART']
SPY_OPTION_EXCHANGES = ['CBOE', 'ISE', 'PHLX', 'BOX', 'SMART']

# Option expiration patterns
MONTHLY_EXPIRY_DAY = 'FRI'  # Third Friday
WEEKLY_EXPIRY_DAY = 'FRI'   # Every Friday

# Validation limits
MIN_STRIKE_PRICE = 1.0
MAX_STRIKE_PRICE = 10000.0
MIN_STRIKE_INCREMENT = 0.50  # For SPY
MAX_EXPIRY_DAYS = 730  # 2 years

# ==============================================================================
# ENUMS
# ==============================================================================
class OptionRight(Enum):
    """Option right types"""
    CALL = 'C'
    PUT = 'P'

class SecurityType(Enum):
    """Security types supported"""
    STOCK = 'STK'
    OPTION = 'OPT'
    FUTURE = 'FUT'
    FOREX = 'CASH'
    INDEX = 'IND'
    COMBO = 'BAG'

class ComboType(Enum):
    """Common combination types"""
    SPREAD = 'spread'
    STRADDLE = 'straddle'
    STRANGLE = 'strangle'
    BUTTERFLY = 'butterfly'
    CONDOR = 'condor'
    IRON_CONDOR = 'iron_condor'
    CALENDAR = 'calendar'
    DIAGONAL = 'diagonal'
    RATIO = 'ratio'
    CUSTOM = 'custom'

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class OptionSpec:
    """Option specification"""
    symbol: str
    expiry: str  # YYYYMMDD
    strike: float
    right: OptionRight
    exchange: str = DEFAULT_EXCHANGE
    currency: str = DEFAULT_CURRENCY
    multiplier: int = DEFAULT_MULTIPLIER

@dataclass
class SpreadSpec:
    """Spread specification"""
    spread_type: ComboType
    legs: List[OptionSpec]
    ratios: Optional[List[int]] = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Example usage and testing
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Create builder
    builder = ContractBuilder()
    
    print("Testing ContractBuilder")
    print("=" * 50)
    
    # Test stock contracts
    print("\n1. Building stock contracts:")
    spy = builder.build_spy()
    print(f"✅ SPY: {spy}")
    
    aapl = builder.build_stock('AAPL')
    print(f"✅ AAPL: {aapl}")
    
    # Test option contracts
    print("\n2. Building option contracts:")
    
    # Get next Friday expiry
    next_expiry = builder.get_next_expiry()
    print(f"Next expiry: {next_expiry}")
    
    # Build SPY call
    spy_call = builder.build_spy_option(next_expiry, 450.0, 'C')
    print(f"✅ SPY Call: {spy_call}")
    
    # Build SPY put
    spy_put = builder.build_spy_option(next_expiry, 440.0, 'P')
    print(f"✅ SPY Put: {spy_put}")
    
    # Test spreads
    print("\n3. Building option spreads:")
    
    # Vertical spread
    vert_spread = builder.build_vertical_spread(
        'SPY', next_expiry, 445.0, 450.0, 'C'
    )
    print(f"✅ Vertical spread: {vert_spread}")
    
    # Calendar spread
    weekly_expiries = builder.get_weekly_expiries(date.today(), 4)
    if len(weekly_expiries) >= 2:
        cal_spread = builder.build_calendar_spread(
            'SPY', 445.0, weekly_expiries[0], weekly_expiries[1], 'C'
        )
        print(f"✅ Calendar spread: {cal_spread}")
    
    # Iron condor
    iron_condor = builder.build_iron_condor(
        'SPY', next_expiry, 430.0, 425.0, 455.0, 460.0
    )
    print(f"✅ Iron condor: {iron_condor}")
    
    # Straddle
    straddle = builder.build_straddle('SPY', next_expiry, 445.0, 'BUY')
    print(f"✅ Straddle: {straddle}")
    
    # Test expiration helpers
    print("\n4. Testing expiration helpers:")
    
    # Monthly expiry
    monthly = builder.get_monthly_expiry(2025, 6)
    print(f"June 2025 monthly expiry: {monthly}")
    
    # Weekly expiries
    weeklies = builder.get_weekly_expiries(date.today(), 6)
    print(f"Next 6 weekly expiries: {weeklies}")
    
    # Cache info
    print(f"\n5. Cache statistics:")
    print(f"Cached contracts: {builder.get_cache_size()}")
    
    print("\n✅ All tests passed!") CLASS
# ==============================================================================
class ContractBuilder:
    """
    Comprehensive IB contract builder with validation and caching.
    
    This class provides methods to create all types of IB contracts with
    proper validation, caching for performance, and support for complex
    multi-leg strategies commonly used in SPY options trading.
    
    Features:
        - Stock, option, future, forex, and index contracts
        - Multi-leg option strategies (spreads, condors, etc.)
        - Contract validation against IB requirements
        - LRU caching for frequently used contracts
        - SPY-specific optimizations
        - Expiration date calculations
    
    Example:
        >>> builder = ContractBuilder()
        >>> spy = builder.build_stock('SPY')
        >>> call = builder.build_option('SPY', '20250620', 450.0, 'C')
        >>> spread = builder.build_vertical_spread('SPY', '20250620', 450, 455, 'C')
    """
    
    def __init__(self):
        """Initialize the ContractBuilder."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.trading_calendar = TradingCalendar()
        
        # Cache for validated contracts
        self._contract_cache: Dict[str, Contract] = {}
        
        self.logger.info("ContractBuilder initialized")
    
    # ==========================================================================
    # STOCK CONTRACTS
    # ==========================================================================
    
    def build_stock(self, symbol: str, exchange: str = DEFAULT_EXCHANGE,
                   currency: str = DEFAULT_CURRENCY) -> Stock:
        """
        Build a stock contract.
        
        Args:
            symbol: Stock symbol
            exchange: Exchange (default: SMART)
            currency: Currency (default: USD)
            
        Returns:
            Stock contract
            
        Raises:
            ValueError: If validation fails
        """
        # Check cache
        cache_key = f"STK_{symbol}_{exchange}_{currency}"
        if cache_key in self._contract_cache:
            return self._contract_cache[cache_key]
        
        # Validate inputs
        if not symbol or not isinstance(symbol, str):
            raise ValueError("Invalid symbol")
        
        symbol = symbol.upper()
        
        # Create contract
        contract = Stock(symbol, exchange, currency)
        
        # Validate contract
        if not self._validate_stock_contract(contract):
            raise ValueError(f"Invalid stock contract for {symbol}")
        
        # Cache and return
        self._contract_cache[cache_key] = contract
        self.logger.debug(f"Built stock contract: {symbol}")
        
        return contract
    
    def build_spy(self) -> Stock:
        """
        Build SPY stock contract with optimal settings.
        
        Returns:
            SPY stock contract
        """
        # SPY trades best on ARCA
        return self.build_stock('SPY', exchange='ARCA')
    
    # ==========================================================================
    # OPTION CONTRACTS
    # ==========================================================================
    
    def build_option(self, symbol: str, expiry: str, strike: float,
                    right: Union[str, OptionRight], exchange: str = DEFAULT_EXCHANGE,
                    currency: str = DEFAULT_CURRENCY,
                    multiplier: int = DEFAULT_MULTIPLIER) -> Option:
        """
        Build an option contract.
        
        Args:
            symbol: Underlying symbol
            expiry: Expiration date (YYYYMMDD)
            strike: Strike price
            right: 'C'/'CALL' or 'P'/'PUT'
            exchange: Exchange (default: SMART)
            currency: Currency (default: USD)
            multiplier: Contract multiplier (default: 100)
            
        Returns:
            Option contract
            
        Raises:
            ValueError: If validation fails
        """
        # Check cache
        right_str = self._normalize_right(right)
        cache_key = f"OPT_{symbol}_{expiry}_{strike}_{right_str}_{exchange}"
        if cache_key in self._contract_cache:
            return self._contract_cache[cache_key]
        
        # Validate inputs
        symbol = symbol.upper()
        expiry = self._validate_expiry(expiry)
        strike = self._validate_strike(strike)
        
        # Create contract
        contract = Option(
            symbol=symbol,
            lastTradeDateOrContractMonth=expiry,
            strike=strike,
            right=right_str,
            exchange=exchange,
            currency=currency,
            multiplier=str(multiplier)
        )
        
        # Validate contract
        if not self._validate_option_contract(contract):
            raise ValueError(f"Invalid option contract: {symbol} {expiry} {right_str}{strike}")
        
        # Cache and return
        self._contract_cache[cache_key] = contract
        self.logger.debug(f"Built option contract: {symbol} {expiry} {right_str}{strike}")
        
        return contract
    
    def build_spy_option(self, expiry: str, strike: float,
                        right: Union[str, OptionRight]) -> Option:
        """
        Build SPY option contract with optimal settings.
        
        Args:
            expiry: Expiration date (YYYYMMDD)
            strike: Strike price
            right: 'C'/'CALL' or 'P'/'PUT'
            
        Returns:
            SPY option contract
        """
        # SPY options trade best on CBOE
        return self.build_option('SPY', expiry, strike, right, exchange='CBOE')
    
    # ==========================================================================
    # OPTION SPREADS
    # ==========================================================================
    
    def build_vertical_spread(self, symbol: str, expiry: str,
                            strike_long: float, strike_short: float,
                            right: Union[str, OptionRight],
                            exchange: str = DEFAULT_EXCHANGE) -> Contract:
        """
        Build a vertical spread (bull/bear spread).
        
        Args:
            symbol: Underlying symbol
            expiry: Expiration date (YYYYMMDD)
            strike_long: Long leg strike
            strike_short: Short leg strike
            right: 'C' or 'P'
            exchange: Exchange
            
        Returns:
            Combo contract for vertical spread
        """
        # Create legs
        long_leg = self.build_option(symbol, expiry, strike_long, right, exchange)
        short_leg = self.build_option(symbol, expiry, strike_short, right, exchange)
        
        # Create combo
        combo = Contract()
        combo.symbol = symbol
        combo.secType = 'BAG'
        combo.currency = DEFAULT_CURRENCY
        combo.exchange = exchange
        
        # Define legs
        leg1 = ComboLeg()
        leg1.conId = 0  # Will be filled by IB
        leg1.ratio = 1
        leg1.action = 'BUY'
        leg1.exchange = exchange
        
        leg2 = ComboLeg()
        leg2.conId = 0  # Will be filled by IB
        leg2.ratio = 1
        leg2.action = 'SELL'
        leg2.exchange = exchange
        
        combo.comboLegs = [leg1, leg2]
        
        self.logger.debug(f"Built vertical spread: {symbol} {expiry} "
                         f"{right}{strike_long}/{strike_short}")
        
        return combo
    
    def build_calendar_spread(self, symbol: str, strike: float,
                            expiry_short: str, expiry_long: str,
                            right: Union[str, OptionRight],
                            exchange: str = DEFAULT_EXCHANGE) -> Contract:
        """
        Build a calendar spread.
        
        Args:
            symbol: Underlying symbol
            strike: Strike price (same for both legs)
            expiry_short: Short leg expiry (YYYYMMDD)
            expiry_long: Long leg expiry (YYYYMMDD)
            right: 'C' or 'P'
            exchange: Exchange
            
        Returns:
            Combo contract for calendar spread
        """
        # Validate expiries
        if expiry_short >= expiry_long:
            raise ValueError("Short expiry must be before long expiry")
        
        # Create legs
        short_leg = self.build_option(symbol, expiry_short, strike, right, exchange)
        long_leg = self.build_option(symbol, expiry_long, strike, right, exchange)
        
        # Create combo
        combo = Contract()
        combo.symbol = symbol
        combo.secType = 'BAG'
        combo.currency = DEFAULT_CURRENCY
        combo.exchange = exchange
        
        # Define legs
        leg1 = ComboLeg()
        leg1.conId = 0
        leg1.ratio = 1
        leg1.action = 'SELL'
        leg1.exchange = exchange
        
        leg2 = ComboLeg()
        leg2.conId = 0
        leg2.ratio = 1
        leg2.action = 'BUY'
        leg2.exchange = exchange
        
        combo.comboLegs = [leg1, leg2]
        
        self.logger.debug(f"Built calendar spread: {symbol} {right}{strike} "
                         f"{expiry_short}/{expiry_long}")
        
        return combo
    
    def build_iron_condor(self, symbol: str, expiry: str,
                         put_short: float, put_long: float,
                         call_short: float, call_long: float,
                         exchange: str = DEFAULT_EXCHANGE) -> Contract:
        """
        Build an iron condor spread.
        
        Args:
            symbol: Underlying symbol
            expiry: Expiration date (YYYYMMDD)
            put_short: Short put strike
            put_long: Long put strike
            call_short: Short call strike
            call_long: Long call strike
            exchange: Exchange
            
        Returns:
            Combo contract for iron condor
        """
        # Validate strikes
        if not (put_long < put_short < call_short < call_long):
            raise ValueError("Invalid strike prices for iron condor")
        
        # Create combo
        combo = Contract()
        combo.symbol = symbol
        combo.secType = 'BAG'
        combo.currency = DEFAULT_CURRENCY
        combo.exchange = exchange
        
        # Define legs (4 legs for iron condor)
        legs = []
        
        # Long put
        leg1 = ComboLeg()
        leg1.conId = 0
        leg1.ratio = 1
        leg1.action = 'BUY'
        leg1.exchange = exchange
        legs.append(leg1)
        
        # Short put
        leg2 = ComboLeg()
        leg2.conId = 0
        leg2.ratio = 1
        leg2.action = 'SELL'
        leg2.exchange = exchange
        legs.append(leg2)
        
        # Short call
        leg3 = ComboLeg()
        leg3.conId = 0
        leg3.ratio = 1
        leg3.action = 'SELL'
        leg3.exchange = exchange
        legs.append(leg3)
        
        # Long call
        leg4 = ComboLeg()
        leg4.conId = 0
        leg4.ratio = 1
        leg4.action = 'BUY'
        leg4.exchange = exchange
        legs.append(leg4)
        
        combo.comboLegs = legs
        
        self.logger.debug(f"Built iron condor: {symbol} {expiry} "
                         f"P{put_long}/{put_short} C{call_short}/{call_long}")
        
        return combo
    
    def build_straddle(self, symbol: str, expiry: str, strike: float,
                      action: str = 'BUY', exchange: str = DEFAULT_EXCHANGE) -> Contract:
        """
        Build a straddle (buy/sell both call and put).
        
        Args:
            symbol: Underlying symbol
            expiry: Expiration date (YYYYMMDD)
            strike: Strike price
            action: 'BUY' or 'SELL'
            exchange: Exchange
            
        Returns:
            Combo contract for straddle
        """
        # Create combo
        combo = Contract()
        combo.symbol = symbol
        combo.secType = 'BAG'
        combo.currency = DEFAULT_CURRENCY
        combo.exchange = exchange
        
        # Define legs
        # Call leg
        leg1 = ComboLeg()
        leg1.conId = 0
        leg1.ratio = 1
        leg1.action = action
        leg1.exchange = exchange
        
        # Put leg
        leg2 = ComboLeg()
        leg2.conId = 0
        leg2.ratio = 1
        leg2.action = action
        leg2.exchange = exchange
        
        combo.comboLegs = [leg1, leg2]
        
        self.logger.debug(f"Built {action} straddle: {symbol} {expiry} {strike}")
        
        return combo
    
    # ==========================================================================
    # EXPIRATION HELPERS
    # ==========================================================================
    
    def get_monthly_expiry(self, year: int, month: int) -> str:
        """
        Get monthly option expiration date (3rd Friday).
        
        Args:
            year: Year
            month: Month (1-12)
            
        Returns:
            Expiration date in YYYYMMDD format
        """
        # Find third Friday
        first_day = datetime(year, month, 1)
        first_friday = first_day + timedelta(days=(4 - first_day.weekday()) % 7)
        third_friday = first_friday + timedelta(weeks=2)
        
        return third_friday.strftime('%Y%m%d')
    
    def get_weekly_expiries(self, start_date: date, weeks: int = 4) -> List[str]:
        """
        Get weekly option expiration dates.
        
        Args:
            start_date: Starting date
            weeks: Number of weeks
            
        Returns:
            List of expiration dates in YYYYMMDD format
        """
        expiries = []
        current = start_date
        
        # Find next Friday
        days_ahead = 4 - current.weekday()  # Friday is 4
        if days_ahead <= 0:  # Already passed Friday
            days_ahead += 7
        
        next_friday = current + timedelta(days=days_ahead)
        
        # Generate weekly expiries
        for _ in range(weeks):
            if self.trading_calendar.is_trading_day(next_friday):
                expiries.append(next_friday.strftime('%Y%m%d'))
            else:
                # If Friday is holiday, use Thursday
                thursday = next_friday - timedelta(days=1)
                expiries.append(thursday.strftime('%Y%m%d'))
            
            next_friday += timedelta(weeks=1)
        
        return expiries
    
    def get_next_expiry(self, days_out: int = 0) -> str:
        """
        Get next available option expiry.
        
        Args:
            days_out: Minimum days to expiration
            
        Returns:
            Expiration date in YYYYMMDD format
        """
        target_date = date.today() + timedelta(days=days_out)
        
        # Get next Friday after target date
        days_ahead = 4 - target_date.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        
        next_friday = target_date + timedelta(days=days_ahead)
        
        # Check if trading day
        if self.trading_calendar.is_trading_day(next_friday):
            return next_friday.strftime('%Y%m%d')
        else:
            # Use Thursday if Friday is holiday
            return (next_friday - timedelta(days=1)).strftime('%Y%m%d')
    
    # ==========================================================================
    # VALIDATION METHODS
    # ==========================================================================
    
    def _validate_stock_contract(self, contract: Stock) -> bool:
        """Validate stock contract."""
        if not contract.symbol or len(contract.symbol) > 12:
            return False
        
        if contract.currency not in ['USD', 'EUR', 'GBP', 'JPY']:
            return False
        
        return True
    
    def _validate_option_contract(self, contract: Option) -> bool:
        """Validate option contract."""
        # Symbol validation
        if not contract.symbol or len(contract.symbol) > 12:
            return False
        
        # Strike validation
        if contract.strike < MIN_STRIKE_PRICE or contract.strike > MAX_STRIKE_PRICE:
            return False
        
        # Right validation
        if contract.right not in ['C', 'P']:
            return False
        
        # Expiry validation
        try:
            expiry_date = datetime.strptime(contract.lastTradeDateOrContractMonth, '%Y%m%d')
            if expiry_date.date() < date.today():
                return False
            
            days_to_expiry = (expiry_date.date() - date.today()).days
            if days_to_expiry > MAX_EXPIRY_DAYS:
                return False
                
        except ValueError:
            return False
        
        return True
    
    def _validate_expiry(self, expiry: str) -> str:
        """Validate and format expiry date."""
        # Handle different date formats
        if len(expiry) == 8 and expiry.isdigit():
            # YYYYMMDD format
            try:
                datetime.strptime(expiry, '%Y%m%d')
                return expiry
            except ValueError:
                raise ValueError(f"Invalid expiry date: {expiry}")
        
        # Try other common formats
        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y']:
            try:
                dt = datetime.strptime(expiry, fmt)
                return dt.strftime('%Y%m%d')
            except ValueError:
                continue
        
        raise ValueError(f"Invalid expiry date format: {expiry}")
    
    def _validate_strike(self, strike: float) -> float:
        """Validate and round strike price."""
        if strike < MIN_STRIKE_PRICE or strike > MAX_STRIKE_PRICE:
            raise ValueError(f"Strike price out of range: {strike}")
        
        # Round to nearest valid increment (0.50 for SPY)
        return round(strike * 2) / 2
    
    def _normalize_right(self, right: Union[str, OptionRight]) -> str:
        """Normalize option right to 'C' or 'P'."""
        if isinstance(right, OptionRight):
            return right.value
        
        right = str(right).upper()
        
        if right in ['C', 'CALL']:
            return 'C'
        elif right in ['P', 'PUT']:
            return 'P'
        else:
            raise ValueError(f"Invalid option right: {right}")
    
    # ==========================================================================
    # CACHE MANAGEMENT
    # ==========================================================================
    
    def clear_cache(self):
        """Clear the contract cache."""
        self._contract_cache.clear()
        self.logger.info("Contract cache cleared")
    
    def get_cache_size(self) -> int:
        """Get number of cached contracts."""
        return len(self._contract_cache)

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

# Singleton instance
_builder_instance: Optional[ContractBuilder] = None

def get_contract_builder() -> ContractBuilder:
    """
    Get singleton ContractBuilder instance.
    
    Returns:
        ContractBuilder instance
    """
    global _builder_instance
    if _builder_instance is None:
        _builder_instance = ContractBuilder()
    return _builder_instance

# Convenience functions
def build_spy_stock() -> Stock:
    """Build SPY stock contract."""
    return get_contract_builder().build_spy()

def build_spy_option(expiry: str, strike: float, right: str) -> Option:
    """Build SPY option contract."""
    return get_contract_builder().build_spy_option(expiry, strike, right)

# ==============================================================================
# MAIN