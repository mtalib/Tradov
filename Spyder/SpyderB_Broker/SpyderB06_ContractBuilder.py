#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker [Application Name] [Series Letter] [Series Name]
Module: SpyderB06_ContractBuilder.py [Application Name][Series Letter] [Module Number]_[Purpose].py
Purpose: IB contract construction with validation and caching for ib_async compatibility
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-21 Time: 20:47:00

⚠️ DEPRECATION WARNING ⚠️
    This module is DEPRECATED and scheduled for removal.
    The Spyder system has migrated to:
    - Tradier API for order execution (SpyderB40_TradierClient.py)
    - Polygon.io for market data (SpyderC25_PolygonDataHandler.py)

    This legacy ib_async module is no longer maintained and should not be used
    for new development. It remains only for historical reference.

Module Description:
    This module provides comprehensive contract building functionality for
    Interactive Brokers using ib_async (compatible with IB Gateway 10.37+).
    It creates and validates contracts for stocks, options, futures, and
    complex strategies. Includes contract caching for performance, validation
    against IB requirements, and support for all SPY option specifications
    including weekly expirations and multi-leg strategies.

Key Features:
    - Full ib_async integration for IB Gateway 10.37+ compatibility
    - Contract building for stocks, options, futures, forex, indices
    - SPY options specialization with weekly/monthly expirations  
    - Contract validation and caching for performance
    - Multi-leg strategy support with combo contracts
    - Comprehensive error handling and logging

Dependencies:
    - ib_async: Modern Interactive Brokers API client
    - Standard Python libraries for date/time handling
    - Caching utilities for performance optimization

"""

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from functools import lru_cache
# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Any, Dict, List, Optional, Tuple, Union

# ==============================================================================
# THIRD-PARTY IMPORTS - IB_ASYNC INTEGRATION (DEPRECATED)
# ==============================================================================
# ⚠️ DEPRECATED: ib_async is legacy code - use Tradier API instead
# The Spyder system no longer uses Interactive Brokers for order execution.
# See: SpyderB40_TradierClient.py for current broker integration.
try:
    from ib_async import (CFD, ComboLeg, Commodity, Contract, Forex, Future,
                        Index, Option, Stock, TagValue)

    HAS_IB_ASYNC = True
except ImportError:
    HAS_IB_ASYNC = False
    raise ImportError("ib_async is required. Install with: pip install ib_async")

# ==============================================================================
# SPYDER IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import get_logger

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Constants for contract building
DEFAULT_EXCHANGE = "SMART"
SPY_EXCHANGE = "ARCA"
OPTIONS_EXCHANGE = "CBOE"
DEFAULT_CURRENCY = "USD"

# SPY-specific settings
SPY_SYMBOL = "SPY"
SPY_MULTIPLIER = "100"
SPY_TRADING_CLASS = "SPY"

# Logger setup
logger = get_logger(__name__)

# ==============================================================================
# ENUMS AND DATA CLASSES
# ==============================================================================

class SecurityType(Enum):
    """Security type enumeration for contracts."""
    STOCK = "STK"
    OPTION = "OPT"
    FUTURE = "FUT"
    FOREX = "CASH"
    INDEX = "IND"
    CFD = "CFD"
    COMMODITY = "CMDTY"
    COMBO = "BAG"

class OptionRight(Enum):
    """Option rights enumeration."""
    CALL = "C"
    PUT = "P"

class ContractStatus(Enum):
    """Contract validation status."""
    VALID = "VALID"
    INVALID = "INVALID"
    PENDING = "PENDING"
    ERROR = "ERROR"

@dataclass
class ContractSpec:
    """Contract specification for building contracts."""
    symbol: str
    sec_type: SecurityType
    exchange: str = DEFAULT_EXCHANGE
    currency: str = DEFAULT_CURRENCY
    
    # Option-specific fields
    last_trade_date: Optional[str] = None
    strike: Optional[float] = None
    right: Optional[OptionRight] = None
    multiplier: Optional[str] = None
    trading_class: Optional[str] = None
    
    # Future-specific fields
    local_symbol: Optional[str] = None
    
    # Additional fields
    primary_exchange: Optional[str] = None
    include_expired: bool = False

@dataclass
class ValidationResult:
    """Result of contract validation."""
    is_valid: bool
    status: ContractStatus
    errors: List[str]
    warnings: List[str]
    contract: Optional[Contract] = None

# ==============================================================================
# CONTRACT BUILDER CLASS
# ==============================================================================

class ContractBuilder:
    """
    Advanced contract builder for Interactive Brokers using ib_async.
    
    Provides comprehensive contract creation, validation, and caching
    functionality specifically optimized for SPY options trading.
    """
    
    def __init__(self, cache_size: int = 1000):
        """
        Initialize contract builder with caching.
        
        Args:
            cache_size: Maximum number of contracts to cache
        """
        self.cache_size = cache_size
        self._contract_cache: Dict[str, Contract] = {}
        self._validation_cache: Dict[str, ValidationResult] = {}
        
        logger.info("ContractBuilder initialized with ib_async integration")
        
        if not HAS_IB_ASYNC:
            logger.error("ib_async not available - contract building will fail")
            raise ImportError("ib_async is required for contract building")
    
    # ==========================================================================
    # CACHE MANAGEMENT
    # ==========================================================================
    
    def _get_cache_key(self, **kwargs) -> str:
        """Generate cache key from contract parameters."""
        # Sort kwargs for consistent keys
        sorted_kwargs = sorted(kwargs.items())
        return "|".join(f"{k}={v}" for k, v in sorted_kwargs if v is not None)
    
    def _cache_contract(self, key: str, contract: Contract) -> None:
        """Cache a contract with size management."""
        if len(self._contract_cache) >= self.cache_size:
            # Remove oldest entries (simple FIFO)
            oldest_key = next(iter(self._contract_cache))
            del self._contract_cache[oldest_key]
        
        self._contract_cache[key] = contract
        logger.debug(f"Cached contract: {key}")
    
    def clear_cache(self) -> None:
        """Clear all cached contracts."""
        self._contract_cache.clear()
        self._validation_cache.clear()
        logger.info("Contract cache cleared")
    
    # ==========================================================================
    # STOCK CONTRACTS
    # ==========================================================================
    
    def build_stock(self, symbol: str, exchange: str = DEFAULT_EXCHANGE,
                   currency: str = DEFAULT_CURRENCY, 
                   primary_exchange: str = None) -> Contract:
        """
        Build a stock contract using ib_async.
        
        Args:
            symbol: Stock symbol (e.g., 'SPY', 'AAPL')
            exchange: Exchange code (default: 'SMART')
            currency: Currency code (default: 'USD')
            primary_exchange: Primary exchange for routing
            
        Returns:
            ib_async Stock contract
        """
        cache_key = self._get_cache_key(
            type="STK", symbol=symbol, exchange=exchange, 
            currency=currency, primary_exchange=primary_exchange
        )
        
        if cache_key in self._contract_cache:
            logger.debug(f"Cache hit for stock: {symbol}")
            return self._contract_cache[cache_key]
        
        try:
            contract = Stock(
                symbol=symbol,
                exchange=exchange,
                currency=currency
            )
            
            if primary_exchange:
                contract.primaryExchange = primary_exchange
            
            self._cache_contract(cache_key, contract)
            logger.info(f"Created stock contract: {symbol} on {exchange}")
            return contract
            
        except Exception as e:
            logger.error(f"Failed to build stock contract for {symbol}: {e}")
            raise
    
    def build_spy_stock(self) -> Contract:
        """Build SPY stock contract with optimized settings."""
        return self.build_stock(
            symbol=SPY_SYMBOL,
            exchange=SPY_EXCHANGE,
            currency=DEFAULT_CURRENCY,
            primary_exchange=SPY_EXCHANGE
        )
    
    # ==========================================================================
    # OPTION CONTRACTS
    # ==========================================================================
    
    def build_option(self, symbol: str, last_trade_date: str, strike: float,
                    right: str, exchange: str = OPTIONS_EXCHANGE,
                    currency: str = DEFAULT_CURRENCY,
                    multiplier: str = None,
                    trading_class: str = None) -> Contract:
        """
        Build an option contract using ib_async.
        
        Args:
            symbol: Underlying symbol (e.g., 'SPY')
            last_trade_date: Option expiration date (YYYYMMDD format)
            strike: Strike price
            right: 'C' for call, 'P' for put
            exchange: Options exchange (default: 'CBOE')
            currency: Currency code (default: 'USD')
            multiplier: Contract multiplier (default: '100' for stocks)
            trading_class: Trading class (default: same as symbol)
            
        Returns:
            ib_async Option contract
        """
        cache_key = self._get_cache_key(
            type="OPT", symbol=symbol, last_trade_date=last_trade_date,
            strike=strike, right=right, exchange=exchange, currency=currency,
            multiplier=multiplier, trading_class=trading_class
        )
        
        if cache_key in self._contract_cache:
            logger.debug(f"Cache hit for option: {symbol} {last_trade_date} {strike}{right}")
            return self._contract_cache[cache_key]
        
        try:
            contract = Option(
                symbol=symbol,
                lastTradeDateOrContractMonth=last_trade_date,
                strike=strike,
                right=right.upper(),
                exchange=exchange,
                currency=currency
            )
            
            if multiplier:
                contract.multiplier = multiplier
            if trading_class:
                contract.tradingClass = trading_class
            
            self._cache_contract(cache_key, contract)
            logger.info(f"Created option contract: {symbol} {last_trade_date} {strike}{right}")
            return contract
            
        except Exception as e:
            logger.error(f"Failed to build option contract: {e}")
            raise
    
    def build_spy_option(self, last_trade_date: str, strike: float,
                        right: str) -> Contract:
        """
        Build SPY option contract with optimized settings.
        
        Args:
            last_trade_date: Option expiration date (YYYYMMDD format)
            strike: Strike price
            right: 'C' for call, 'P' for put
            
        Returns:
            ib_async Option contract for SPY
        """
        return self.build_option(
            symbol=SPY_SYMBOL,
            last_trade_date=last_trade_date,
            strike=strike,
            right=right,
            exchange=OPTIONS_EXCHANGE,
            multiplier=SPY_MULTIPLIER,
            trading_class=SPY_TRADING_CLASS
        )
    
    # ==========================================================================
    # FUTURES CONTRACTS
    # ==========================================================================
    
    def build_future(self, symbol: str, last_trade_date: str,
                    exchange: str, currency: str = DEFAULT_CURRENCY,
                    local_symbol: str = None, multiplier: str = None) -> Contract:
        """
        Build a futures contract using ib_async.
        
        Args:
            symbol: Futures symbol (e.g., 'ES')
            last_trade_date: Contract month (YYYYMM format)
            exchange: Futures exchange (e.g., 'CME')
            currency: Currency code (default: 'USD')
            local_symbol: Local symbol for specific contract
            multiplier: Contract multiplier
            
        Returns:
            ib_async Future contract
        """
        cache_key = self._get_cache_key(
            type="FUT", symbol=symbol, last_trade_date=last_trade_date,
            exchange=exchange, currency=currency, local_symbol=local_symbol,
            multiplier=multiplier
        )
        
        if cache_key in self._contract_cache:
            logger.debug(f"Cache hit for future: {symbol} {last_trade_date}")
            return self._contract_cache[cache_key]
        
        try:
            contract = Future(
                symbol=symbol,
                lastTradeDateOrContractMonth=last_trade_date,
                exchange=exchange,
                currency=currency
            )
            
            if local_symbol:
                contract.localSymbol = local_symbol
            if multiplier:
                contract.multiplier = multiplier
            
            self._cache_contract(cache_key, contract)
            logger.info(f"Created futures contract: {symbol} {last_trade_date}")
            return contract
            
        except Exception as e:
            logger.error(f"Failed to build futures contract: {e}")
            raise
    
    # ==========================================================================
    # INDEX CONTRACTS
    # ==========================================================================
    
    def build_index(self, symbol: str, exchange: str,
                   currency: str = DEFAULT_CURRENCY) -> Contract:
        """
        Build an index contract using ib_async.
        
        Args:
            symbol: Index symbol (e.g., 'SPX')
            exchange: Exchange code (e.g., 'CBOE')
            currency: Currency code (default: 'USD')
            
        Returns:
            ib_async Index contract
        """
        cache_key = self._get_cache_key(
            type="IND", symbol=symbol, exchange=exchange, currency=currency
        )
        
        if cache_key in self._contract_cache:
            logger.debug(f"Cache hit for index: {symbol}")
            return self._contract_cache[cache_key]
        
        try:
            contract = Index(
                symbol=symbol,
                exchange=exchange,
                currency=currency
            )
            
            self._cache_contract(cache_key, contract)
            logger.info(f"Created index contract: {symbol} on {exchange}")
            return contract
            
        except Exception as e:
            logger.error(f"Failed to build index contract: {e}")
            raise
    
    # ==========================================================================
    # FOREX CONTRACTS
    # ==========================================================================
    
    def build_forex(self, symbol: str, exchange: str = "IDEALPRO",
                   currency: str = "USD") -> Contract:
        """
        Build a forex contract using ib_async.
        
        Args:
            symbol: Currency pair (e.g., 'EUR')
            exchange: Forex exchange (default: 'IDEALPRO')
            currency: Quote currency (default: 'USD')
            
        Returns:
            ib_async Forex contract
        """
        cache_key = self._get_cache_key(
            type="CASH", symbol=symbol, exchange=exchange, currency=currency
        )
        
        if cache_key in self._contract_cache:
            logger.debug(f"Cache hit for forex: {symbol}{currency}")
            return self._contract_cache[cache_key]
        
        try:
            contract = Forex(
                symbol=symbol,
                exchange=exchange,
                currency=currency
            )
            
            self._cache_contract(cache_key, contract)
            logger.info(f"Created forex contract: {symbol}{currency}")
            return contract
            
        except Exception as e:
            logger.error(f"Failed to build forex contract: {e}")
            raise
    
    # ==========================================================================
    # COMBO CONTRACTS (MULTI-LEG STRATEGIES)
    # ==========================================================================
    
    def build_combo(self, symbol: str, combo_legs: List[ComboLeg],
                   exchange: str = DEFAULT_EXCHANGE,
                   currency: str = DEFAULT_CURRENCY) -> Contract:
        """
        Build a combination contract for multi-leg strategies using ib_async.
        
        Args:
            symbol: Underlying symbol
            combo_legs: List of ComboLeg objects
            exchange: Exchange code
            currency: Currency code
            
        Returns:
            ib_async Contract with combination legs
        """
        cache_key = self._get_cache_key(
            type="BAG", symbol=symbol, exchange=exchange, currency=currency,
            legs=str([f"{leg.conId}:{leg.ratio}:{leg.action}" for leg in combo_legs])
        )
        
        if cache_key in self._contract_cache:
            logger.debug(f"Cache hit for combo: {symbol}")
            return self._contract_cache[cache_key]
        
        try:
            contract = Contract()
            contract.symbol = symbol
            contract.secType = "BAG"
            contract.exchange = exchange
            contract.currency = currency
            contract.comboLegs = combo_legs
            
            self._cache_contract(cache_key, contract)
            logger.info(f"Created combo contract: {symbol} with {len(combo_legs)} legs")
            return contract
            
        except Exception as e:
            logger.error(f"Failed to build combo contract: {e}")
            raise
    
    # ==========================================================================
    # CONTRACT VALIDATION
    # ==========================================================================
    
    def validate_contract(self, contract: Contract) -> ValidationResult:
        """
        Validate contract parameters and structure.
        
        Args:
            contract: Contract to validate
            
        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        
        try:
            # Basic validation
            if not contract.symbol:
                errors.append("Symbol is required")
            
            if not contract.secType:
                errors.append("Security type is required")
            
            if not contract.exchange:
                errors.append("Exchange is required")
            
            if not contract.currency:
                errors.append("Currency is required")
            
            # Option-specific validation
            if contract.secType == "OPT":
                if not contract.lastTradeDateOrContractMonth:
                    errors.append("Last trade date is required for options")
                
                if contract.strike is None or contract.strike <= 0:
                    errors.append("Valid strike price is required for options")
                
                if contract.right not in ["C", "P"]:
                    errors.append("Option right must be 'C' or 'P'")
            
            # SPY-specific validation
            if contract.symbol == SPY_SYMBOL:
                if contract.secType == "STK" and contract.exchange != SPY_EXCHANGE:
                    warnings.append(f"Consider using {SPY_EXCHANGE} for SPY stock")
                
                if contract.secType == "OPT" and contract.exchange != OPTIONS_EXCHANGE:
                    warnings.append(f"Consider using {OPTIONS_EXCHANGE} for SPY options")
            
            # Determine status
            if errors:
                status = ContractStatus.ERROR
                is_valid = False
            elif warnings:
                status = ContractStatus.VALID
                is_valid = True
            else:
                status = ContractStatus.VALID
                is_valid = True
            
            result = ValidationResult(
                is_valid=is_valid,
                status=status,
                errors=errors,
                warnings=warnings,
                contract=contract
            )
            
            logger.debug(f"Validated contract {contract.symbol}: {status.value}")
            return result
            
        except Exception as e:
            logger.error(f"Error validating contract: {e}")
            return ValidationResult(
                is_valid=False,
                status=ContractStatus.ERROR,
                errors=[f"Validation error: {e}"],
                warnings=[],
                contract=contract
            )
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def get_next_expiry(self, days_ahead: int = 0, weekly: bool = True) -> str:
        """
        Get next option expiration date in YYYYMMDD format.
        
        Args:
            days_ahead: Minimum days ahead to look
            weekly: Include weekly expirations
            
        Returns:
            Next expiration date as string
        """
        current_date = datetime.now().date()
        target_date = current_date + timedelta(days=days_ahead)
        
        if weekly:
            # Find next Friday
            days_until_friday = (4 - target_date.weekday()) % 7
            if days_until_friday == 0 and target_date <= current_date:
                days_until_friday = 7
            
            next_friday = target_date + timedelta(days=days_until_friday)
            return next_friday.strftime("%Y%m%d")
        else:
            # Find next monthly expiration (3rd Friday)
            year = target_date.year
            month = target_date.month
            
            # Get 3rd Friday of current month
            first_day = date(year, month, 1)
            first_friday = first_day + timedelta(days=(4 - first_day.weekday()) % 7)
            third_friday = first_friday + timedelta(days=14)
            
            # If past current month's expiry, go to next month
            if third_friday <= current_date:
                if month == 12:
                    year += 1
                    month = 1
                else:
                    month += 1
                
                first_day = date(year, month, 1)
                first_friday = first_day + timedelta(days=(4 - first_day.weekday()) % 7)
                third_friday = first_friday + timedelta(days=14)
            
            return third_friday.strftime("%Y%m%d")
    
    def calculate_strike_range(self, current_price: float, 
                             range_percent: float = 0.05,
                             strike_increment: float = 1.0) -> List[float]:
        """
        Calculate strike range around current price.
        
        Args:
            current_price: Current underlying price
            range_percent: Percentage range around current price
            strike_increment: Strike price increment
            
        Returns:
            List of strike prices
        """
        range_amount = current_price * range_percent
        min_strike = current_price - range_amount
        max_strike = current_price + range_amount
        
        # Round to nearest strike increment
        min_strike = round(min_strike / strike_increment) * strike_increment
        max_strike = round(max_strike / strike_increment) * strike_increment
        
        strikes = []
        current_strike = min_strike
        while current_strike <= max_strike:
            strikes.append(current_strike)
            current_strike += strike_increment
        
        return strikes
    
    def get_contract_description(self, contract: Contract) -> str:
        """
        Get human-readable contract description.
        
        Args:
            contract: Contract to describe
            
        Returns:
            Contract description string
        """
        if contract.secType == "STK":
            return f"{contract.symbol} Stock ({contract.exchange})"
        
        elif contract.secType == "OPT":
            return (f"{contract.symbol} "
                   f"{contract.lastTradeDateOrContractMonth} "
                   f"${contract.strike} "
                   f"{'Call' if contract.right == 'C' else 'Put'}")
        
        elif contract.secType == "FUT":
            return f"{contract.symbol} Future {contract.lastTradeDateOrContractMonth}"
        
        elif contract.secType == "IND":
            return f"{contract.symbol} Index ({contract.exchange})"
        
        elif contract.secType == "CASH":
            return f"{contract.symbol}/{contract.currency} Forex"
        
        elif contract.secType == "BAG":
            return f"{contract.symbol} Combo ({len(contract.comboLegs)} legs)"
        
        else:
            return f"{contract.symbol} {contract.secType}"
    
    # ==========================================================================
    # STATISTICS AND REPORTING
    # ==========================================================================
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get contract cache statistics."""
        return {
            "cache_size": len(self._contract_cache),
            "max_cache_size": self.cache_size,
            "cache_utilization": len(self._contract_cache) / self.cache_size,
            "validation_cache_size": len(self._validation_cache)
        }
    
    def __str__(self) -> str:
        """String representation of ContractBuilder."""
        stats = self.get_cache_stats()
        return (f"ContractBuilder(cache_size={stats['cache_size']}, "
                f"ib_async={HAS_IB_ASYNC})")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

# Global contract builder instance
_contract_builder: Optional[ContractBuilder] = None

def get_contract_builder() -> ContractBuilder:
    """
    Get global ContractBuilder instance.
    
    Returns:
        ContractBuilder: Global contract builder instance
    """
    global _contract_builder
    if _contract_builder is None:
        _contract_builder = ContractBuilder()
    return _contract_builder

def create_spy_stock() -> Contract:
    """Create SPY stock contract."""
    return get_contract_builder().build_spy_stock()

def create_spy_option(expiry: str, strike: float, right: str) -> Contract:
    """Create SPY option contract."""
    return get_contract_builder().build_spy_option(expiry, strike, right)

def create_stock(symbol: str, exchange: str = DEFAULT_EXCHANGE) -> Contract:
    """Create stock contract."""
    return get_contract_builder().build_stock(symbol, exchange)

def create_option(symbol: str, expiry: str, strike: float, right: str) -> Contract:
    """Create option contract."""
    return get_contract_builder().build_option(symbol, expiry, strike, right)

# ==============================================================================
# TESTING AND DEVELOPMENT
# ==============================================================================

def test_contract_builder():
    """Test contract builder functionality."""
    builder = ContractBuilder()
    
    print("Testing ContractBuilder with ib_async...")
    
    # Test SPY stock
    spy_stock = builder.build_spy_stock()
    print(f"SPY Stock: {builder.get_contract_description(spy_stock)}")
    
    # Test SPY option
    expiry = builder.get_next_expiry(days_ahead=1)
    spy_option = builder.build_spy_option(expiry, 450.0, "C")
    print(f"SPY Option: {builder.get_contract_description(spy_option)}")
    
    # Test validation
    result = builder.validate_contract(spy_stock)
    print(f"Validation: {result.status.value}, Errors: {len(result.errors)}")
    
    # Test cache stats
    stats = builder.get_cache_stats()
    print(f"Cache: {stats['cache_size']}/{stats['max_cache_size']} contracts")

if __name__ == "__main__":
    # Run tests if executed directly
    test_contract_builder()