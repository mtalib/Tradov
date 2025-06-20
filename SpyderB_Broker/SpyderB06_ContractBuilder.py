#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderB06_ContractBuilder.py
Group: B (Broker Integration)
Purpose: Options contract creation and validation

Description:
    This module handles the creation and validation of option contracts for the
    Spyder trading system. It provides utilities for building SPY option contracts,
    finding options by criteria (strike, delta, DTE), and validating contract
    specifications. The module ensures proper contract formatting for IB API.

Author: Mohamed Talib
Date: 2025-05-29
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass, field
import calendar
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from ibapi.contract import Contract, ComboLeg
from scipy.stats import norm

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar
from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient

# ==============================================================================
# CONSTANTS
# ==============================================================================
# SPY specifications
SPY_SYMBOL = "SPY"
SPY_EXCHANGE = "SMART"
SPY_CURRENCY = "USD"
OPTION_MULTIPLIER = 100

# Option chain parameters
STRIKE_INTERVAL = 1.0  # SPY has $1 strike intervals
MAX_STRIKES_FROM_ATM = 50  # Look at strikes within $50 of ATM
DEFAULT_DTE_RANGE = (0, 60)  # 0-60 days to expiration

# Greeks targets
DEFAULT_DELTA_TOLERANCE = 0.05  # +/- 5 delta points
DEFAULT_TIME_DECAY_THRESHOLD = -0.10  # Minimum theta for income strategies

# ==============================================================================
# ENUMS
# ==============================================================================
class OptionRight(Enum):
    """Option right (Call/Put)"""
    CALL = "C"
    PUT = "P"

class OptionStyle(Enum):
    """Option exercise style"""
    AMERICAN = "american"
    EUROPEAN = "european"

class ExpirationType(Enum):
    """Option expiration type"""
    REGULAR = "regular"
    WEEKLY = "weekly"
    QUARTERLY = "quarterly"
    MONTHLY = "monthly"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class OptionSpecification:
    """Option contract specification"""
    symbol: str
    strike: float
    expiration: datetime.date
    right: OptionRight
    exchange: str = SPY_EXCHANGE
    currency: str = SPY_CURRENCY
    multiplier: int = OPTION_MULTIPLIER
    
    def to_contract(self) -> Contract:
        """Convert to IB Contract object"""
        contract = Contract()
        contract.symbol = self.symbol
        contract.secType = "OPT"
        contract.exchange = self.exchange
        contract.currency = self.currency
        contract.strike = self.strike
        contract.right = self.right.value
        contract.lastTradeDateOrContractMonth = self.expiration.strftime("%Y%m%d")
        contract.multiplier = str(self.multiplier)
        return contract
    
    def to_string(self) -> str:
        """Convert to string representation"""
        return f"{self.symbol}_{self.expiration.strftime('%y%m%d')}{self.right.value}{int(self.strike)}"

class OptionSearchCriteria:
    """Criteria for searching option contracts"""
    target_delta: Optional[float] = None
    delta_range: Optional[Tuple[float, float]] = None
    dte_range: Tuple[int, int] = DEFAULT_DTE_RANGE
    min_volume: Optional[int] = None
    min_open_interest: Optional[int] = None
    strike_range: Optional[Tuple[float, float]] = None
    expiration_type: Optional[ExpirationType] = None

class SpreadSpecification:
    """Option spread specification"""
    spread_type: str
    legs: List[OptionSpecification]
    ratios: List[int] = field(default_factory=lambda: [1, -1])  # Buy/sell ratios
    
    def to_combo_contract(self) -> Tuple[Contract, List[ComboLeg]]:
        """Convert to IB combo contract"""
        contract = Contract()
        contract.symbol = self.legs[0].symbol
        contract.secType = "BAG"
        contract.exchange = self.legs[0].exchange
        contract.currency = self.legs[0].currency
        
        combo_legs = []
        for i, (spec, ratio) in enumerate(zip(self.legs, self.ratios)):
            leg = ComboLeg()
            leg.conId = 0  # Will be filled by IB
            leg.ratio = abs(ratio)
            leg.action = "BUY" if ratio > 0 else "SELL"
            leg.exchange = spec.exchange
            combo_legs.append(leg)
        
        return contract, combo_legs

# ==============================================================================
# CONTRACT BUILDER CLASS
# ==============================================================================
class ContractBuilder:
    """
    Builds and validates option contracts.
    
    Features:
    - SPY option contract creation
    - Option chain navigation
    - Strike/delta/DTE selection
    - Spread construction
    - Contract validation
    - Expiration date calculation
    """
    
    def __init__(self, ib_client: Optional[SpyderClient] = None):
        """
        Initialize contract builder.
        
        Args:
            ib_client: Optional IB client for contract validation
        """
        self.ib_client = ib_client
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Trading calendar
        self.calendar = TradingCalendar()
        
        # Cache for option chains
        self._option_chain_cache: Dict[str, pd.DataFrame] = {}
        self._cache_timestamp: Dict[str, datetime.datetime] = {}
        self._cache_ttl = 300  # 5 minutes
        
        self.logger.info("ContractBuilder initialized")
    
    # ==========================================================================
    # STOCK CONTRACTS
    # ==========================================================================
    def create_spy_stock(self) -> Contract:
        """
        Create SPY stock contract.
        
        Returns:
            SPY stock contract
        """
        contract = Contract()
        contract.symbol = SPY_SYMBOL
        contract.secType = "STK"
        contract.exchange = SPY_EXCHANGE
        contract.currency = SPY_CURRENCY
        return contract
    
    # ==========================================================================
    # OPTION CONTRACTS
    # ==========================================================================
    def create_spy_option(
        self,
        strike: float,
        expiration: datetime.date,
        right: OptionRight
    ) -> Contract:
        """
        Create SPY option contract.
        
        Args:
            strike: Strike price
            expiration: Expiration date
            right: Call or Put
            
        Returns:
            Option contract
        """
        spec = OptionSpecification(
            symbol=SPY_SYMBOL,
            strike=strike,
            expiration=expiration,
            right=right
        )
        return spec.to_contract()
    
    def find_option_by_delta(
        self,
        target_delta: float,
        expiration: datetime.date,
        right: OptionRight,
        underlying_price: float,
        volatility: float = 0.15
    ) -> Optional[OptionSpecification]:
        """
        Find option contract closest to target delta.
        
        Args:
            target_delta: Target delta (e.g., 0.30 for 30 delta)
            expiration: Expiration date
            right: Call or Put
            underlying_price: Current SPY price
            volatility: Implied volatility
            
        Returns:
            Option specification or None
        """
        # Calculate time to expiration
        dte = (expiration - datetime.date.today()).days
        time_to_expiry = dte / 365.0
        
        # Risk-free rate (approximate)
        risk_free_rate = 0.05
        
        # Find strikes around ATM
        atm_strike = round(underlying_price)
        strikes = self._generate_strike_range(atm_strike)
        
        # Calculate delta for each strike
        best_strike = None
        min_delta_diff = float('inf')
        
        for strike in strikes:
            # Calculate Black-Scholes delta
            d1 = (
                np.log(underlying_price / strike) +
                (risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry
            ) / (volatility * np.sqrt(time_to_expiry))
            
            if right == OptionRight.CALL:
                delta = norm.cdf(d1)
            else:
                delta = norm.cdf(d1) - 1
            
            # Check if closer to target
            delta_diff = abs(abs(delta) - abs(target_delta))
            if delta_diff < min_delta_diff:
                min_delta_diff = delta_diff
                best_strike = strike
        
        if best_strike and min_delta_diff <= DEFAULT_DELTA_TOLERANCE:
            return OptionSpecification(
                symbol=SPY_SYMBOL,
                strike=best_strike,
                expiration=expiration,
                right=right
            )
        
        return None
    
    def find_options_by_criteria(
        self,
        criteria: OptionSearchCriteria,
        underlying_price: float,
        right: OptionRight,
        volatility: float = 0.15
    ) -> List[OptionSpecification]:
        """
        Find options matching search criteria.
        
        Args:
            criteria: Search criteria
            underlying_price: Current SPY price
            right: Call or Put
            volatility: Implied volatility
            
        Returns:
            List of matching option specifications
        """
        matching_options = []
        
        # Get expiration dates within DTE range
        expirations = self.get_expiration_dates(
            criteria.dte_range[0],
            criteria.dte_range[1],
            criteria.expiration_type
        )
        
        for expiration in expirations:
            # Skip if looking for specific delta
            if criteria.target_delta:
                option = self.find_option_by_delta(
                    criteria.target_delta,
                    expiration,
                    right,
                    underlying_price,
                    volatility
                )
                if option:
                    matching_options.append(option)
            else:
                # Get strikes within range
                atm_strike = round(underlying_price)
                strikes = self._generate_strike_range(
                    atm_strike,
                    criteria.strike_range
                )
                
                for strike in strikes:
                    # Apply filters
                    if criteria.delta_range:
                        # Calculate delta for this strike
                        dte = (expiration - datetime.date.today()).days
                        time_to_expiry = dte / 365.0
                        
                        d1 = (
                            np.log(underlying_price / strike) +
                            (0.05 + 0.5 * volatility ** 2) * time_to_expiry
                        ) / (volatility * np.sqrt(time_to_expiry))
                        
                        if right == OptionRight.CALL:
                            delta = norm.cdf(d1)
                        else:
                            delta = norm.cdf(d1) - 1
                        
                        if not (criteria.delta_range[0] <= abs(delta) <= criteria.delta_range[1]):
                            continue
                    
                    # Create option specification
                    option = OptionSpecification(
                        symbol=SPY_SYMBOL,
                        strike=strike,
                        expiration=expiration,
                        right=right
                    )
                    matching_options.append(option)
        
        return matching_options
    
    # ==========================================================================
    # SPREAD CONTRACTS
    # ==========================================================================
    def create_vertical_spread(
        self,
        long_strike: float,
        short_strike: float,
        expiration: datetime.date,
        right: OptionRight,
        is_debit: bool = True
    ) -> SpreadSpecification:
        """
        Create vertical spread (bull/bear spread).
        
        Args:
            long_strike: Long leg strike
            short_strike: Short leg strike
            expiration: Expiration date
            right: Call or Put
            is_debit: True for debit spread, False for credit
            
        Returns:
            Spread specification
        """
        long_leg = OptionSpecification(
            symbol=SPY_SYMBOL,
            strike=long_strike,
            expiration=expiration,
            right=right
        )
        
        short_leg = OptionSpecification(
            symbol=SPY_SYMBOL,
            strike=short_strike,
            expiration=expiration,
            right=right
        )
        
        if is_debit:
            legs = [long_leg, short_leg]
            ratios = [1, -1]
        else:
            legs = [short_leg, long_leg]
            ratios = [1, -1]
        
        return SpreadSpecification(
            spread_type="vertical",
            legs=legs,
            ratios=ratios
        )
    
    def create_iron_condor(
        self,
        put_short_strike: float,
        put_long_strike: float,
        call_short_strike: float,
        call_long_strike: float,
        expiration: datetime.date
    ) -> SpreadSpecification:
        """
        Create iron condor spread.
        
        Args:
            put_short_strike: Short put strike
            put_long_strike: Long put strike
            call_short_strike: Short call strike
            call_long_strike: Long call strike
            expiration: Expiration date
            
        Returns:
            Spread specification
        """
        # Validate strikes
        if not (put_long_strike < put_short_strike < call_short_strike < call_long_strike):
            raise ValueError("Invalid strike prices for iron condor")
        
        legs = [
            OptionSpecification(SPY_SYMBOL, put_long_strike, expiration, OptionRight.PUT),
            OptionSpecification(SPY_SYMBOL, put_short_strike, expiration, OptionRight.PUT),
            OptionSpecification(SPY_SYMBOL, call_short_strike, expiration, OptionRight.CALL),
            OptionSpecification(SPY_SYMBOL, call_long_strike, expiration, OptionRight.CALL)
        ]
        
        ratios = [1, -1, -1, 1]  # Buy long, sell short
        
        return SpreadSpecification(
            spread_type="iron_condor",
            legs=legs,
            ratios=ratios
        )
    
    def create_butterfly(
        self,
        lower_strike: float,
        middle_strike: float,
        upper_strike: float,
        expiration: datetime.date,
        right: OptionRight
    ) -> SpreadSpecification:
        """
        Create butterfly spread.
        
        Args:
            lower_strike: Lower strike
            middle_strike: Middle strike (ATM)
            upper_strike: Upper strike
            expiration: Expiration date
            right: Call or Put
            
        Returns:
            Spread specification
        """
        # Validate strikes
        if not (lower_strike < middle_strike < upper_strike):
            raise ValueError("Invalid strikes for butterfly")
        
        # Check symmetry
        if abs((middle_strike - lower_strike) - (upper_strike - middle_strike)) > 0.01:
            self.logger.warning("Butterfly strikes are not symmetric")
        
        legs = [
            OptionSpecification(SPY_SYMBOL, lower_strike, expiration, right),
            OptionSpecification(SPY_SYMBOL, middle_strike, expiration, right),
            OptionSpecification(SPY_SYMBOL, upper_strike, expiration, right)
        ]
        
        ratios = [1, -2, 1]  # Buy 1 lower, sell 2 middle, buy 1 upper
        
        return SpreadSpecification(
            spread_type="butterfly",
            legs=legs,
            ratios=ratios
        )
    
    def create_calendar_spread(
        self,
        strike: float,
        near_expiration: datetime.date,
        far_expiration: datetime.date,
        right: OptionRight
    ) -> SpreadSpecification:
        """
        Create calendar (horizontal) spread.
        
        Args:
            strike: Strike price
            near_expiration: Near-term expiration
            far_expiration: Far-term expiration
            right: Call or Put
            
        Returns:
            Spread specification
        """
        if near_expiration >= far_expiration:
            raise ValueError("Near expiration must be before far expiration")
        
        legs = [
            OptionSpecification(SPY_SYMBOL, strike, near_expiration, right),
            OptionSpecification(SPY_SYMBOL, strike, far_expiration, right)
        ]
        
        ratios = [-1, 1]  # Sell near, buy far
        
        return SpreadSpecification(
            spread_type="calendar",
            legs=legs,
            ratios=ratios
        )
    
    # ==========================================================================
    # EXPIRATION DATES
    # ==========================================================================
    def get_expiration_dates(
        self,
        min_dte: int = 0,
        max_dte: int = 60,
        expiration_type: Optional[ExpirationType] = None
    ) -> List[datetime.date]:
        """
        Get available option expiration dates.
        
        Args:
            min_dte: Minimum days to expiration
            max_dte: Maximum days to expiration
            expiration_type: Filter by expiration type
            
        Returns:
            List of expiration dates
        """
        today = datetime.date.today()
        start_date = today + datetime.timedelta(days=min_dte)
        end_date = today + datetime.timedelta(days=max_dte)
        
        expirations = []
        current_date = start_date
        
        while current_date <= end_date:
            # SPY options expire on Mon, Wed, Fri
            if current_date.weekday() in [0, 2, 4]:  # Monday, Wednesday, Friday
                # Check if it's a trading day
                if self.calendar.is_trading_day(current_date):
                    # Determine expiration type
                    exp_type = self._get_expiration_type(current_date)
                    
                    if expiration_type is None or exp_type == expiration_type:
                        expirations.append(current_date)
            
            current_date += datetime.timedelta(days=1)
        
        return expirations
    
    def get_monthly_expirations(
        self,
        min_dte: int = 0,
        max_dte: int = 180
    ) -> List[datetime.date]:
        """
        Get monthly expiration dates (3rd Friday).
        
        Args:
            min_dte: Minimum days to expiration
            max_dte: Maximum days to expiration
            
        Returns:
            List of monthly expiration dates
        """
        expirations = []
        today = datetime.date.today()
        
        # Start from current month
        current_date = today.replace(day=1)
        
        for _ in range(6):  # Look at next 6 months
            # Find 3rd Friday
            third_friday = self._get_third_friday(current_date.year, current_date.month)
            
            # Check if within DTE range
            dte = (third_friday - today).days
            if min_dte <= dte <= max_dte:
                expirations.append(third_friday)
            
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        return expirations
    
    def get_next_expiration(
        self,
        min_dte: int = 0,
        expiration_type: Optional[ExpirationType] = None
    ) -> Optional[datetime.date]:
        """
        Get next available expiration date.
        
        Args:
            min_dte: Minimum days to expiration
            expiration_type: Preferred expiration type
            
        Returns:
            Next expiration date or None
        """
        expirations = self.get_expiration_dates(
            min_dte,
            min_dte + 60,
            expiration_type
        )
        
        if expirations:
            return expirations[0]
        
        return None
    
    # ==========================================================================
    # VALIDATION
    # ==========================================================================
    def validate_contract(self, contract: Contract) -> Tuple[bool, Optional[str]]:
        """
        Validate contract specifications.
        
        Args:
            contract: Contract to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Basic validation
            if not contract.symbol:
                return False, "Symbol is required"
            
            if contract.secType == "OPT":
                # Option validation
                if not contract.strike or contract.strike <= 0:
                    return False, "Invalid strike price"
                
                if contract.right not in ['C', 'P']:
                    return False, "Invalid option right"
                
                if not contract.lastTradeDateOrContractMonth:
                    return False, "Expiration date is required"
                
                # Validate expiration format
                try:
                    datetime.datetime.strptime(
                        contract.lastTradeDateOrContractMonth,
                        "%Y%m%d"
                    )
                except ValueError:
                    return False, "Invalid expiration date format"
            
            # IB validation if client available
            if self.ib_client:
                # This would make an actual API call to validate
                # For now, we assume it's valid
                pass
            
            return True, None
            
        except Exception as e:
            return False, str(e)
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def _generate_strike_range(
        self,
        atm_strike: float,
        strike_range: Optional[Tuple[float, float]] = None
    ) -> List[float]:
        """Generate list of strikes around ATM"""
        if strike_range:
            min_strike = max(strike_range[0], atm_strike - MAX_STRIKES_FROM_ATM)
            max_strike = min(strike_range[1], atm_strike + MAX_STRIKES_FROM_ATM)
        else:
            min_strike = atm_strike - MAX_STRIKES_FROM_ATM
            max_strike = atm_strike + MAX_STRIKES_FROM_ATM
        
        strikes = []
        current = math.floor(min_strike)
        
        while current <= max_strike:
            strikes.append(float(current))
            current += STRIKE_INTERVAL
        
        return strikes
    
    def _get_expiration_type(self, date: datetime.date) -> ExpirationType:
        """Determine expiration type for a date"""
        # Third Friday of the month
        third_friday = self._get_third_friday(date.year, date.month)
        
        if date == third_friday:
            return ExpirationType.MONTHLY
        elif date.weekday() == 4:  # Friday
            return ExpirationType.WEEKLY
        else:
            return ExpirationType.REGULAR
    
    def _get_third_friday(self, year: int, month: int) -> datetime.date:
        """Get third Friday of a month"""
        # First day of month
        first_day = datetime.date(year, month, 1)
        
        # First Friday
        first_friday = first_day + datetime.timedelta(
            days=(4 - first_day.weekday()) % 7
        )
        
        # Third Friday is 14 days later
        third_friday = first_friday + datetime.timedelta(days=14)
        
        return third_friday
    
    def option_string_to_contract(self, option_string: str) -> Optional[Contract]:
        """
        Convert option string to contract.
        
        Args:
            option_string: Format "SPY_250620C450"
            
        Returns:
            Contract or None
        """
        try:
            parts = option_string.split('_')
            if len(parts) != 2:
                return None
            
            symbol = parts[0]
            option_part = parts[1]
            
            # Parse option part
            # Format: YYMMDDCP###
            if len(option_part) < 8:
                return None
            
            year = int("20" + option_part[0:2])
            month = int(option_part[2:4])
            day = int(option_part[4:6])
            right = option_part[6]
            strike = float(option_part[7:])
            
            expiration = datetime.date(year, month, day)
            
            return self.create_spy_option(
                strike=strike,
                expiration=expiration,
                right=OptionRight.CALL if right == 'C' else OptionRight.PUT
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing option string: {e}")
            return None

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test contract builder
    builder = ContractBuilder()
    
    # Create SPY stock contract
    spy_stock = builder.create_spy_stock()
    print(f"SPY Stock: {spy_stock.symbol} {spy_stock.secType}")
    
    # Get next monthly expiration
    next_monthly = builder.get_next_expiration(
        min_dte=20,
        expiration_type=ExpirationType.MONTHLY
    )
    print(f"\nNext monthly expiration: {next_monthly}")
    
    # Find 30-delta put
    if next_monthly:
        put_option = builder.find_option_by_delta(
            target_delta=0.30,
            expiration=next_monthly,
            right=OptionRight.PUT,
            underlying_price=450.0,
            volatility=0.15
        )
        if put_option:
            print(f"\n30-delta put: {put_option.to_string()}")
            print(f"Strike: ${put_option.strike}")
    
    # Create vertical spread
    vertical = builder.create_vertical_spread(
        long_strike=445,
        short_strike=450,
        expiration=next_monthly,
        right=OptionRight.PUT,
        is_debit=False  # Credit spread
    )
    print(f"\nVertical spread: {vertical.spread_type}")
    for i, leg in enumerate(vertical.legs):
        print(f"  Leg {i+1}: {leg.to_string()} (ratio: {vertical.ratios[i]})")
    
    # Create iron condor
    iron_condor = builder.create_iron_condor(
        put_short_strike=440,
        put_long_strike=435,
        call_short_strike=460,
        call_long_strike=465,
        expiration=next_monthly
    )
    print(f"\nIron Condor:")
    for i, leg in enumerate(iron_condor.legs):
        action = "BUY" if iron_condor.ratios[i] > 0 else "SELL"
        print(f"  {action} {leg.to_string()}")
    
    # Get all expirations in next 30 days
    expirations = builder.get_expiration_dates(0, 30)
    print(f"\nExpirations in next 30 days: {len(expirations)}")
    for exp in expirations[:5]:
        print(f"  {exp} ({builder._get_expiration_type(exp).value})")
    
    # Parse option string
    option_string = "SPY_250620C450"
    contract = builder.option_string_to_contract(option_string)
    if contract:
        print(f"\nParsed option: {contract.symbol} {contract.strike} {contract.right}")

# Alias for backward compatibility
OptionContract = OptionSpecification
