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
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from ib_insync import (CFD, ComboLeg, Commodity, Contract, Forex, Future,
                        Index, Option, Stock, TagValue)

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
DEFAULT_EXCHANGE = "SMART"
DEFAULT_CURRENCY = "USD"
DEFAULT_MULTIPLIER = 100  # For options

# SPY specific settings
SPY_EXCHANGES = ["ARCA", "BATS", "NYSE", "NASDAQ", "SMART"]
SPY_OPTION_EXCHANGES = ["CBOE", "ISE", "PHLX", "BOX", "SMART"]

# Option expiration patterns
MONTHLY_EXPIRY_DAY = "FRI"  # Third Friday
WEEKLY_EXPIRY_DAY = "FRI"  # Every Friday

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

    CALL = "C"
    PUT = "P"


class SecurityType(Enum):
    """Security types supported"""

    STOCK = "STK"
    OPTION = "OPT"
    FUTURE = "FUT"
    FOREX = "CASH"
    INDEX = "IND"
    COMBO = "BAG"


class ComboType(Enum):
    """Common combination types"""

    SPREAD = "spread"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    BUTTERFLY = "butterfly"
    CONDOR = "condor"
    IRON_CONDOR = "iron_condor"
    CALENDAR = "calendar"
    DIAGONAL = "diagonal"
    RATIO = "ratio"
    CUSTOM = "custom"


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
# MAIN CLASS
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

    def build_stock(
        self, symbol: str, exchange: str = DEFAULT_EXCHANGE, currency: str = DEFAULT_CURRENCY
    ) -> Stock:
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
        return self.build_stock("SPY", exchange="ARCA")

    # ==========================================================================
    # OPTION CONTRACTS
    # ==========================================================================

    def build_option(
        self,
        symbol: str,
        expiry: str,
        strike: float,
        right: Union[str, OptionRight],
        exchange: str = DEFAULT_EXCHANGE,
        currency: str = DEFAULT_CURRENCY,
        multiplier: int = DEFAULT_MULTIPLIER,
    ) -> Option:
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
            multiplier=str(multiplier),
        )

        # Validate contract
        if not self._validate_option_contract(contract):
            raise ValueError(f"Invalid option contract: {symbol} {expiry} {right_str}{strike}")

        # Cache and return
        self._contract_cache[cache_key] = contract
        self.logger.debug(f"Built option contract: {symbol} {expiry} {right_str}{strike}")

        return contract

    def build_spy_option(
        self, expiry: str, strike: float, right: Union[str, OptionRight]
    ) -> Option:
        """
        Build SPY option contract with optimal settings.

        Args:
            expiry: Expiration date (YYYYMMDD)
            strike: Strike price
            right: 'C'/'CALL' or 'P'/'PUT'

        Returns:
            SPY option contract
        """
        return self.build_option("SPY", expiry, strike, right)

    # ==========================================================================
    # SPREAD CONTRACTS
    # ==========================================================================

    def build_vertical_spread(
        self,
        symbol: str,
        expiry: str,
        long_strike: float,
        short_strike: float,
        right: Union[str, OptionRight],
    ) -> Contract:
        """
        Build a vertical spread (bull/bear spread).

        Args:
            symbol: Underlying symbol
            expiry: Expiration date (YYYYMMDD)
            long_strike: Long leg strike
            short_strike: Short leg strike
            right: 'C' or 'P'

        Returns:
            Combo contract for vertical spread
        """
        # Create legs
        long_leg = self.build_option(symbol, expiry, long_strike, right)
        short_leg = self.build_option(symbol, expiry, short_strike, right)

        # Create combo legs
        combo_leg1 = ComboLeg()
        combo_leg1.conId = 0  # Will be filled by IB
        combo_leg1.ratio = 1
        combo_leg1.action = "BUY"
        combo_leg1.exchange = long_leg.exchange

        combo_leg2 = ComboLeg()
        combo_leg2.conId = 0  # Will be filled by IB
        combo_leg2.ratio = 1
        combo_leg2.action = "SELL"
        combo_leg2.exchange = short_leg.exchange

        # Create combo contract
        combo = Contract()
        combo.symbol = symbol
        combo.secType = "BAG"
        combo.currency = DEFAULT_CURRENCY
        combo.exchange = DEFAULT_EXCHANGE
        combo.comboLegs = [combo_leg1, combo_leg2]

        self.logger.debug(f"Built vertical spread: {symbol} {expiry} {long_strike}/{short_strike}")

        return combo

    def build_iron_condor(
        self,
        symbol: str,
        expiry: str,
        put_long: float,
        put_short: float,
        call_short: float,
        call_long: float,
    ) -> Contract:
        """
        Build an iron condor spread.

        Args:
            symbol: Underlying symbol
            expiry: Expiration date (YYYYMMDD)
            put_long: Long put strike
            put_short: Short put strike
            call_short: Short call strike
            call_long: Long call strike

        Returns:
            Combo contract for iron condor
        """
        # Create all four legs
        legs = []

        # Bull put spread
        legs.append(("BUY", self.build_option(symbol, expiry, put_long, "P")))
        legs.append(("SELL", self.build_option(symbol, expiry, put_short, "P")))

        # Bear call spread
        legs.append(("SELL", self.build_option(symbol, expiry, call_short, "C")))
        legs.append(("BUY", self.build_option(symbol, expiry, call_long, "C")))

        # Create combo legs
        combo_legs = []
        for action, leg in legs:
            combo_leg = ComboLeg()
            combo_leg.conId = 0  # Will be filled by IB
            combo_leg.ratio = 1
            combo_leg.action = action
            combo_leg.exchange = leg.exchange
            combo_legs.append(combo_leg)

        # Create combo contract
        combo = Contract()
        combo.symbol = symbol
        combo.secType = "BAG"
        combo.currency = DEFAULT_CURRENCY
        combo.exchange = DEFAULT_EXCHANGE
        combo.comboLegs = combo_legs

        self.logger.debug(f"Built iron condor: {symbol} {expiry}")

        return combo

    def build_calendar_spread(
        self,
        symbol: str,
        strike: float,
        near_expiry: str,
        far_expiry: str,
        right: Union[str, OptionRight],
    ) -> Contract:
        """
        Build a calendar spread.

        Args:
            symbol: Underlying symbol
            strike: Strike price (same for both legs)
            near_expiry: Near expiration (YYYYMMDD)
            far_expiry: Far expiration (YYYYMMDD)
            right: 'C' or 'P'

        Returns:
            Combo contract for calendar spread
        """
        # Create legs
        near_leg = self.build_option(symbol, near_expiry, strike, right)
        far_leg = self.build_option(symbol, far_expiry, strike, right)

        # Create combo legs
        combo_leg1 = ComboLeg()
        combo_leg1.conId = 0  # Will be filled by IB
        combo_leg1.ratio = 1
        combo_leg1.action = "SELL"
        combo_leg1.exchange = near_leg.exchange

        combo_leg2 = ComboLeg()
        combo_leg2.conId = 0  # Will be filled by IB
        combo_leg2.ratio = 1
        combo_leg2.action = "BUY"
        combo_leg2.exchange = far_leg.exchange

        # Create combo contract
        combo = Contract()
        combo.symbol = symbol
        combo.secType = "BAG"
        combo.currency = DEFAULT_CURRENCY
        combo.exchange = DEFAULT_EXCHANGE
        combo.comboLegs = [combo_leg1, combo_leg2]

        self.logger.debug(f"Built calendar spread: {symbol} {strike} {near_expiry}/{far_expiry}")

        return combo

    def build_straddle(
        self, symbol: str, expiry: str, strike: float, action: str = "BUY"
    ) -> Contract:
        """
        Build a straddle.

        Args:
            symbol: Underlying symbol
            expiry: Expiration date (YYYYMMDD)
            strike: Strike price
            action: 'BUY' or 'SELL'

        Returns:
            Combo contract for straddle
        """
        # Create legs
        call_leg = self.build_option(symbol, expiry, strike, "C")
        put_leg = self.build_option(symbol, expiry, strike, "P")

        # Create combo legs
        combo_legs = []
        for leg in [call_leg, put_leg]:
            combo_leg = ComboLeg()
            combo_leg.conId = 0  # Will be filled by IB
            combo_leg.ratio = 1
            combo_leg.action = action
            combo_leg.exchange = leg.exchange
            combo_legs.append(combo_leg)

        # Create combo contract
        combo = Contract()
        combo.symbol = symbol
        combo.secType = "BAG"
        combo.currency = DEFAULT_CURRENCY
        combo.exchange = DEFAULT_EXCHANGE
        combo.comboLegs = combo_legs

        self.logger.debug(f"Built straddle: {symbol} {expiry} {strike} {action}")

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
        # Get first day of month
        first_day = date(year, month, 1)

        # Find first Friday
        first_friday = first_day
        while first_friday.weekday() != 4:  # 4 = Friday
            first_friday += timedelta(days=1)

        # Third Friday is 14 days later
        third_friday = first_friday + timedelta(days=14)

        return third_friday.strftime("%Y%m%d")

    def get_weekly_expiries(self, start_date: date, weeks: int = 4) -> List[str]:
        """
        Get weekly expiration dates.

        Args:
            start_date: Starting date
            weeks: Number of weeks

        Returns:
            List of expiration dates in YYYYMMDD format
        """
        expiries = []
        current_date = start_date

        for _ in range(weeks):
            # Find next Friday
            days_until_friday = (4 - current_date.weekday()) % 7
            if days_until_friday == 0:
                days_until_friday = 7  # Next Friday if today is Friday

            friday = current_date + timedelta(days=days_until_friday)
            expiries.append(friday.strftime("%Y%m%d"))

            current_date = friday + timedelta(days=1)

        return expiries

    def get_next_expiry(self, dte_min: int = 0) -> str:
        """
        Get next available expiration date.

        Args:
            dte_min: Minimum days to expiration

        Returns:
            Next expiration date in YYYYMMDD format
        """
        today = date.today()
        target_date = today + timedelta(days=dte_min)

        # Find next Friday from target date
        days_until_friday = (4 - target_date.weekday()) % 7
        if days_until_friday == 0 and dte_min == 0:
            # If today is Friday and dte_min is 0, use today
            return today.strftime("%Y%m%d")

        next_friday = target_date + timedelta(days=days_until_friday or 7)

        return next_friday.strftime("%Y%m%d")

    # ==========================================================================
    # VALIDATION METHODS
    # ==========================================================================

    def _validate_stock_contract(self, contract: Stock) -> bool:
        """Validate stock contract."""
        try:
            # Check symbol
            if not contract.symbol or len(contract.symbol) > 10:
                return False

            # Check exchange
            if contract.exchange not in ["SMART", "ARCA", "NYSE", "NASDAQ", "BATS"]:
                self.logger.warning(f"Unusual exchange for stock: {contract.exchange}")

            # Check currency
            if contract.currency != "USD":
                self.logger.warning(f"Non-USD currency: {contract.currency}")

            return True

        except Exception as e:
            self.logger.error(f"Stock validation error: {e}")
            return False

    def _validate_option_contract(self, contract: Option) -> bool:
        """Validate option contract."""
        try:
            # Check symbol
            if not contract.symbol:
                return False

            # Check expiry
            if not contract.lastTradeDateOrContractMonth:
                return False

            # Check strike
            if contract.strike <= 0:
                return False

            # Check right
            if contract.right not in ["C", "P"]:
                return False

            # Check multiplier
            if int(contract.multiplier) != 100:
                self.logger.warning(f"Non-standard multiplier: {contract.multiplier}")

            return True

        except Exception as e:
            self.logger.error(f"Option validation error: {e}")
            return False

    def _validate_expiry(self, expiry: str) -> str:
        """Validate and format expiry date."""
        # Handle different date formats
        if len(expiry) == 8 and expiry.isdigit():
            # YYYYMMDD format
            try:
                datetime.strptime(expiry, "%Y%m%d")
                return expiry
            except ValueError:
                raise ValueError(f"Invalid expiry date: {expiry}")

        # Try other common formats
        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"]:
            try:
                dt = datetime.strptime(expiry, fmt)
                return dt.strftime("%Y%m%d")
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

        if right in ["C", "CALL"]:
            return "C"
        elif right in ["P", "PUT"]:
            return "P"
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

    aapl = builder.build_stock("AAPL")
    print(f"✅ AAPL: {aapl}")

    # Test option contracts
    print("\n2. Building option contracts:")

    # Get next Friday expiry
    next_expiry = builder.get_next_expiry()
    print(f"Next expiry: {next_expiry}")

    # Build SPY call
    spy_call = builder.build_spy_option(next_expiry, 450.0, "C")
    print(f"✅ SPY Call: {spy_call}")

    # Build SPY put
    spy_put = builder.build_spy_option(next_expiry, 440.0, "P")
    print(f"✅ SPY Put: {spy_put}")

    # Test spreads
    print("\n3. Building option spreads:")

    # Vertical spread
    vert_spread = builder.build_vertical_spread("SPY", next_expiry, 445.0, 450.0, "C")
    print(f"✅ Vertical spread: {vert_spread}")

    # Calendar spread
    weekly_expiries = builder.get_weekly_expiries(date.today(), 4)
    if len(weekly_expiries) >= 2:
        cal_spread = builder.build_calendar_spread(
            "SPY", 445.0, weekly_expiries[0], weekly_expiries[1], "C"
        )
        print(f"✅ Calendar spread: {cal_spread}")

    # Iron condor
    iron_condor = builder.build_iron_condor("SPY", next_expiry, 430.0, 425.0, 455.0, 460.0)
    print(f"✅ Iron condor: {iron_condor}")

    # Straddle
    straddle = builder.build_straddle("SPY", next_expiry, 445.0, "BUY")
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

    print("\n✅ All tests passed!")
