#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderN03_OptionsChainManager.py
Group: N (Options Analytics)
Purpose: Comprehensive option chain data management and analysis
Author: Mohamed Talib
Date Created: 2025-08-07
Last Updated: 2025-08-07 Time: 19:30:00

Description:
    This module provides comprehensive option chain data management, including
    efficient data structures, strike selection algorithms, expiration cycle
    management, chain filtering/sorting, Greeks aggregation, and volume/OI
    analysis. It serves as the data layer between market data feeds and
    options analytics modules.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
import threading
from datetime import datetime, timedelta
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from pathlib import Path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
import logging

# Import pricing and IV engines if available
try:
    from SpyderN_OptionsAnalytics.SpyderN01_OptionsPricer import OptionsPricer
    from SpyderN_OptionsAnalytics.SpyderN02_ImpliedVolatilityEngine import ImpliedVolatilityEngine
    PRICING_AVAILABLE = True
except ImportError:
    PRICING_AVAILABLE = False
    logging.info("⚠️ Options pricing modules not available - some features disabled")

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Chain parameters
MAX_STRIKES_PER_EXPIRY = 50
DEFAULT_STRIKE_WIDTH = 10  # Strikes above/below ATM
MIN_VOLUME_THRESHOLD = 10
MIN_OI_THRESHOLD = 100
STALE_DATA_SECONDS = 60

# Expiration cycles
WEEKLY_EXPIRATIONS = ['SPY', 'QQQ', 'IWM', 'DIA']  # Symbols with weeklies
MONTHLY_EXPIRATIONS = ['VIX', 'GLD', 'TLT']  # Monthly only

# Greeks thresholds
MAX_DELTA = 0.95
MIN_DELTA = -0.95
MAX_GAMMA = 0.10
MAX_VEGA = 1.0

# ==============================================================================
# ENUMS
# ==============================================================================
class OptionType(Enum):
    """Option type enumeration"""
    CALL = "CALL"
    PUT = "PUT"

class Moneyness(Enum):
    """Option moneyness categories"""
    DEEP_ITM = "DEEP_ITM"      # Delta > 0.80
    ITM = "ITM"                # Delta 0.60-0.80
    ATM = "ATM"                # Delta 0.40-0.60
    OTM = "OTM"                # Delta 0.20-0.40
    DEEP_OTM = "DEEP_OTM"      # Delta < 0.20

class ChainFilter(Enum):
    """Chain filtering options"""
    ALL = "ALL"
    HIGH_VOLUME = "HIGH_VOLUME"
    HIGH_OI = "HIGH_OI"
    LIQUID = "LIQUID"
    NEAR_MONEY = "NEAR_MONEY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class OptionContract:
    """Individual option contract data"""
    symbol: str
    strike: float
    expiry: datetime
    option_type: OptionType
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    volume: int = 0
    open_interest: int = 0
    implied_volatility: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    exchange: str = "CBOE"

    @property
    def mid_price(self) -> float:
        """Calculate mid price"""
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2
        return self.last

    @property
    def spread(self) -> float:
        """Calculate bid-ask spread"""
        if self.ask > 0 and self.bid > 0:
            return self.ask - self.bid
        return 0.0

    @property
    def spread_pct(self) -> float:
        """Calculate spread as percentage of mid price"""
        mid = self.mid_price
        if mid > 0:
            return (self.spread / mid) * 100
        return 0.0

    @property
    def days_to_expiry(self) -> int:
        """Calculate days to expiration"""
        return max(0, (self.expiry.date() - datetime.now().date()).days)

    @property
    def contract_name(self) -> str:
        """Generate standard contract name"""
        exp_str = self.expiry.strftime("%y%m%d")
        type_char = "C" if self.option_type == OptionType.CALL else "P"
        strike_str = f"{int(self.strike * 1000):08d}"
        return f"{self.symbol}{exp_str}{type_char}{strike_str}"

@dataclass
class ExpirationCycle:
    """Expiration cycle information"""
    expiry_date: datetime
    dte: int
    is_weekly: bool
    is_monthly: bool
    is_quarterly: bool
    total_volume: int = 0
    total_oi: int = 0
    num_strikes: int = 0
    atm_iv: float = 0.0

@dataclass
class ChainAnalytics:
    """Option chain analytics summary"""
    total_call_volume: int = 0
    total_put_volume: int = 0
    total_call_oi: int = 0
    total_put_oi: int = 0
    put_call_ratio: float = 0.0
    oi_put_call_ratio: float = 0.0
    average_iv: float = 0.0
    iv_skew: float = 0.0
    max_pain_strike: float = 0.0
    high_volume_strikes: list[float] = field(default_factory=list)
    high_oi_strikes: list[float] = field(default_factory=list)
    unusual_activity: list[dict] = field(default_factory=list)

# ==============================================================================
# OPTIONS CHAIN MANAGER CLASS
# ==============================================================================
class OptionsChainManager:
    """
    Comprehensive option chain data management system.

    Features:
        - Efficient chain data storage and retrieval
        - Strike selection algorithms
        - Expiration cycle management
        - Volume/OI analysis
        - Greeks aggregation
        - Max pain calculation
        - Unusual activity detection
    """

    def __init__(self, config: dict | None = None):
        """
        Initialize the Options Chain Manager

        Args:
            config: Configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config or {}
        self.max_strikes = self.config.get('max_strikes', MAX_STRIKES_PER_EXPIRY)
        self.strike_width = self.config.get('strike_width', DEFAULT_STRIKE_WIDTH)

        # Data storage
        self.chains: dict[str, dict[datetime, dict[float, dict[str, OptionContract]]]] = {}
        self.underlying_prices: dict[str, float] = {}
        self.expirations: dict[str, list[ExpirationCycle]] = {}
        self.analytics: dict[str, ChainAnalytics] = {}

        # Threading
        self.lock = threading.Lock()

        # Pricing engines
        self.pricer = OptionsPricer() if PRICING_AVAILABLE else None
        self.iv_engine = ImpliedVolatilityEngine() if PRICING_AVAILABLE else None

        # Cache
        self.cache = {}
        self.cache_timestamp = {}
        self._cache_maxsize = 500

        self.logger.debug("OptionsChainManager initialized")

    # ==========================================================================
    # DATA MANAGEMENT
    # ==========================================================================

    def add_contract(self, contract: OptionContract) -> None:
        """
        Add or update an option contract in the chain

        Args:
            contract: OptionContract object
        """
        with self.lock:
            symbol = contract.symbol

            # Initialize chain structure if needed
            if symbol not in self.chains:
                self.chains[symbol] = {}

            if contract.expiry not in self.chains[symbol]:
                self.chains[symbol][contract.expiry] = {}

            if contract.strike not in self.chains[symbol][contract.expiry]:
                self.chains[symbol][contract.expiry][contract.strike] = {}

            # Store contract by type
            type_key = "CALL" if contract.option_type == OptionType.CALL else "PUT"
            self.chains[symbol][contract.expiry][contract.strike][type_key] = contract

            # Clear cache for this symbol
            self._clear_symbol_cache(symbol)

    def update_underlying_price(self, symbol: str, price: float) -> None:
        """
        Update underlying asset price

        Args:
            symbol: Asset symbol
            price: Current price
        """
        with self.lock:
            self.underlying_prices[symbol] = price
            self._clear_symbol_cache(symbol)

            # Update moneyness for all contracts
            if symbol in self.chains:
                self._update_moneyness(symbol)

    def get_chain(self, symbol: str,
                  expiry: datetime | None = None,
                  filter_type: ChainFilter = ChainFilter.ALL) -> pd.DataFrame:
        """
        Get option chain as DataFrame

        Args:
            symbol: Asset symbol
            expiry: Specific expiration date (None for all)
            filter_type: Type of filtering to apply

        Returns:
            DataFrame with option chain data
        """
        with self.lock:
            if symbol not in self.chains:
                return pd.DataFrame()

            contracts = []

            # Get contracts for specified expiry or all
            if expiry:
                if expiry in self.chains[symbol]:
                    for _strike, types in self.chains[symbol][expiry].items():
                        for _option_type, contract in types.items():
                            contracts.append(self._contract_to_dict(contract))
            else:
                for _exp_date, strikes in self.chains[symbol].items():
                    for _strike, types in strikes.items():
                        for _option_type, contract in types.items():
                            contracts.append(self._contract_to_dict(contract))

            if not contracts:
                return pd.DataFrame()

            # Create DataFrame
            df = pd.DataFrame(contracts)

            # Apply filters
            df = self._apply_chain_filter(df, filter_type)

            # Sort by expiry and strike
            df = df.sort_values(['expiry', 'strike', 'option_type'])

            return df

    # ==========================================================================
    # STRIKE SELECTION
    # ==========================================================================

    def get_atm_strike(self, symbol: str, expiry: datetime) -> float:
        """
        Get at-the-money strike for given expiry

        Args:
            symbol: Asset symbol
            expiry: Expiration date

        Returns:
            ATM strike price
        """
        if symbol not in self.underlying_prices:
            return 0.0

        underlying = self.underlying_prices[symbol]

        if symbol not in self.chains or expiry not in self.chains[symbol]:
            return underlying

        # Find closest strike to underlying
        strikes = list(self.chains[symbol][expiry].keys())
        if not strikes:
            return underlying

        return min(strikes, key=lambda x: abs(x - underlying))

    def get_strike_range(self, symbol: str, expiry: datetime,
                        num_strikes: int | None = None,
                        delta_range: tuple[float, float] | None = None) -> list[float]:
        """
        Get range of strikes based on criteria

        Args:
            symbol: Asset symbol
            expiry: Expiration date
            num_strikes: Number of strikes above/below ATM
            delta_range: Delta range (min, max) for selection

        Returns:
            List of selected strikes
        """
        if symbol not in self.chains or expiry not in self.chains[symbol]:
            return []

        strikes = sorted(self.chains[symbol][expiry].keys())

        if not strikes:
            return []

        if delta_range:
            # Select by delta range
            selected = []
            for strike in strikes:
                if "CALL" in self.chains[symbol][expiry][strike]:
                    contract = self.chains[symbol][expiry][strike]["CALL"]
                    if delta_range[0] <= contract.delta <= delta_range[1]:
                        selected.append(strike)
            return selected

        elif num_strikes:
            # Select by number around ATM
            atm = self.get_atm_strike(symbol, expiry)
            atm_idx = min(range(len(strikes)),
                         key=lambda i: abs(strikes[i] - atm))

            start = max(0, atm_idx - num_strikes)
            end = min(len(strikes), atm_idx + num_strikes + 1)

            return strikes[start:end]

        else:
            # Return all strikes
            return strikes

    def select_optimal_strikes(self, symbol: str, expiry: datetime,
                              strategy: str = "credit_spread",
                              risk_level: str = "moderate") -> dict[str, float]:
        """
        Select optimal strikes for given strategy

        Args:
            symbol: Asset symbol
            expiry: Expiration date
            strategy: Trading strategy type
            risk_level: Risk tolerance level

        Returns:
            Dictionary of selected strikes
        """
        strikes = {}

        if symbol not in self.chains or expiry not in self.chains[symbol]:
            return strikes

        atm = self.get_atm_strike(symbol, expiry)
        sorted(self.chains[symbol][expiry].keys())

        if strategy == "credit_spread":
            # Bull put spread or bear call spread
            if risk_level == "conservative":
                # Far OTM strikes
                delta_short = 0.20
                delta_long = 0.10
            elif risk_level == "moderate":
                # Moderate OTM strikes
                delta_short = 0.30
                delta_long = 0.20
            else:  # aggressive
                # Near ATM strikes
                delta_short = 0.40
                delta_long = 0.30

            # Find strikes matching target deltas
            strikes["short"] = self._find_strike_by_delta(
                symbol, expiry, delta_short, OptionType.PUT
            )
            strikes["long"] = self._find_strike_by_delta(
                symbol, expiry, delta_long, OptionType.PUT
            )

        elif strategy == "iron_condor":
            # Four strikes for iron condor
            if risk_level == "conservative":
                put_short_delta = 0.20
                put_long_delta = 0.10
                call_short_delta = 0.20
                call_long_delta = 0.10
            elif risk_level == "moderate":
                put_short_delta = 0.25
                put_long_delta = 0.15
                call_short_delta = 0.25
                call_long_delta = 0.15
            else:
                put_short_delta = 0.30
                put_long_delta = 0.20
                call_short_delta = 0.30
                call_long_delta = 0.20

            strikes["put_short"] = self._find_strike_by_delta(
                symbol, expiry, put_short_delta, OptionType.PUT
            )
            strikes["put_long"] = self._find_strike_by_delta(
                symbol, expiry, put_long_delta, OptionType.PUT
            )
            strikes["call_short"] = self._find_strike_by_delta(
                symbol, expiry, call_short_delta, OptionType.CALL
            )
            strikes["call_long"] = self._find_strike_by_delta(
                symbol, expiry, call_long_delta, OptionType.CALL
            )

        elif strategy == "straddle":
            strikes["atm"] = atm

        elif strategy == "strangle":
            # OTM put and call
            if risk_level == "conservative":
                delta = 0.25
            elif risk_level == "moderate":
                delta = 0.30
            else:
                delta = 0.35

            strikes["put"] = self._find_strike_by_delta(
                symbol, expiry, delta, OptionType.PUT
            )
            strikes["call"] = self._find_strike_by_delta(
                symbol, expiry, delta, OptionType.CALL
            )

        return strikes

    # ==========================================================================
    # EXPIRATION MANAGEMENT
    # ==========================================================================

    def get_expirations(self, symbol: str,
                       min_dte: int = 0,
                       max_dte: int = 365) -> list[ExpirationCycle]:
        """
        Get available expiration cycles

        Args:
            symbol: Asset symbol
            min_dte: Minimum days to expiry
            max_dte: Maximum days to expiry

        Returns:
            List of expiration cycles
        """
        if symbol not in self.chains:
            return []

        cycles = []

        for expiry in sorted(self.chains[symbol].keys()):
            dte = (expiry.date() - datetime.now().date()).days

            if min_dte <= dte <= max_dte:
                cycle = self._analyze_expiration(symbol, expiry)
                cycles.append(cycle)

        return cycles

    def get_next_expiry(self, symbol: str,
                       weekly: bool = False,
                       min_dte: int = 0) -> datetime | None:
        """
        Get next expiration date

        Args:
            symbol: Asset symbol
            weekly: Whether to get weekly expiry
            min_dte: Minimum days to expiry

        Returns:
            Next expiration datetime or None
        """
        cycles = self.get_expirations(symbol, min_dte=min_dte)

        if not cycles:
            return None

        if weekly:
            # Find next weekly
            for cycle in cycles:
                if cycle.is_weekly:
                    return cycle.expiry_date

        # Return next available
        return cycles[0].expiry_date if cycles else None

    # ==========================================================================
    # GREEKS AGGREGATION
    # ==========================================================================

    def aggregate_greeks(self, symbol: str,
                        expiry: datetime | None = None) -> dict[str, float]:
        """
        Aggregate Greeks across chain or expiry

        Args:
            symbol: Asset symbol
            expiry: Specific expiry (None for all)

        Returns:
            Dictionary of aggregated Greeks
        """
        greeks = {
            'total_delta': 0.0,
            'total_gamma': 0.0,
            'total_theta': 0.0,
            'total_vega': 0.0,
            'total_rho': 0.0,
            'call_delta': 0.0,
            'put_delta': 0.0,
            'call_gamma': 0.0,
            'put_gamma': 0.0
        }

        if symbol not in self.chains:
            return greeks

        # Determine expiries to process
        if expiry:
            expiries = [expiry] if expiry in self.chains[symbol] else []
        else:
            expiries = list(self.chains[symbol].keys())

        # Aggregate Greeks
        for exp in expiries:
            for _strike, types in self.chains[symbol][exp].items():
                for option_type, contract in types.items():
                    # Weight by open interest
                    weight = contract.open_interest

                    greeks['total_delta'] += contract.delta * weight
                    greeks['total_gamma'] += contract.gamma * weight
                    greeks['total_theta'] += contract.theta * weight
                    greeks['total_vega'] += contract.vega * weight
                    greeks['total_rho'] += contract.rho * weight

                    if option_type == "CALL":
                        greeks['call_delta'] += contract.delta * weight
                        greeks['call_gamma'] += contract.gamma * weight
                    else:
                        greeks['put_delta'] += contract.delta * weight
                        greeks['put_gamma'] += contract.gamma * weight

        return greeks

    # ==========================================================================
    # VOLUME/OI ANALYSIS
    # ==========================================================================

    def analyze_volume_oi(self, symbol: str,
                         expiry: datetime | None = None) -> ChainAnalytics:
        """
        Analyze volume and open interest patterns

        Args:
            symbol: Asset symbol
            expiry: Specific expiry (None for all)

        Returns:
            ChainAnalytics object
        """
        analytics = ChainAnalytics()

        if symbol not in self.chains:
            return analytics

        # Determine expiries to analyze
        if expiry:
            expiries = [expiry] if expiry in self.chains[symbol] else []
        else:
            expiries = list(self.chains[symbol].keys())

        call_volumes = []
        put_volumes = []
        call_ois = []
        put_ois = []
        all_ivs = []
        volume_by_strike = defaultdict(int)
        oi_by_strike = defaultdict(int)

        for exp in expiries:
            for strike, types in self.chains[symbol][exp].items():
                for option_type, contract in types.items():
                    if option_type == "CALL":
                        call_volumes.append(contract.volume)
                        call_ois.append(contract.open_interest)
                    else:
                        put_volumes.append(contract.volume)
                        put_ois.append(contract.open_interest)

                    volume_by_strike[strike] += contract.volume
                    oi_by_strike[strike] += contract.open_interest

                    if contract.implied_volatility > 0:
                        all_ivs.append(contract.implied_volatility)

        # Calculate analytics
        analytics.total_call_volume = sum(call_volumes)
        analytics.total_put_volume = sum(put_volumes)
        analytics.total_call_oi = sum(call_ois)
        analytics.total_put_oi = sum(put_ois)

        # Put/Call ratios
        if analytics.total_call_volume > 0:
            analytics.put_call_ratio = (
                analytics.total_put_volume / analytics.total_call_volume
            )

        if analytics.total_call_oi > 0:
            analytics.oi_put_call_ratio = (
                analytics.total_put_oi / analytics.total_call_oi
            )

        # IV metrics
        if all_ivs:
            analytics.average_iv = np.mean(all_ivs)
            analytics.iv_skew = self._calculate_iv_skew(symbol, expiry)

        # High activity strikes
        if volume_by_strike:
            vol_threshold = np.percentile(list(volume_by_strike.values()), 90)
            analytics.high_volume_strikes = [
                strike for strike, vol in volume_by_strike.items()
                if vol >= vol_threshold
            ]

        if oi_by_strike:
            oi_threshold = np.percentile(list(oi_by_strike.values()), 90)
            analytics.high_oi_strikes = [
                strike for strike, oi in oi_by_strike.items()
                if oi >= oi_threshold
            ]

        # Max pain calculation
        analytics.max_pain_strike = self.calculate_max_pain(symbol, expiry)

        # Detect unusual activity
        analytics.unusual_activity = self._detect_unusual_activity(symbol, expiry)

        # Cache result
        cache_key = f"analytics_{symbol}_{expiry}"
        self.cache[cache_key] = analytics
        self.cache_timestamp[cache_key] = datetime.now()

        return analytics

    def calculate_max_pain(self, symbol: str,
                          expiry: datetime) -> float:
        """
        Calculate max pain strike price

        Args:
            symbol: Asset symbol
            expiry: Expiration date

        Returns:
            Max pain strike price
        """
        if symbol not in self.chains or expiry not in self.chains[symbol]:
            return 0.0

        strikes = sorted(self.chains[symbol][expiry].keys())
        if not strikes:
            return 0.0

        max_pain_values = {}

        for test_strike in strikes:
            total_pain = 0.0

            for strike, types in self.chains[symbol][expiry].items():
                # Calculate pain for calls
                if "CALL" in types:
                    call = types["CALL"]
                    if test_strike > strike:
                        # Call expires ITM
                        total_pain += (test_strike - strike) * call.open_interest

                # Calculate pain for puts
                if "PUT" in types:
                    put = types["PUT"]
                    if test_strike < strike:
                        # Put expires ITM
                        total_pain += (strike - test_strike) * put.open_interest

            max_pain_values[test_strike] = total_pain

        # Find strike with minimum total pain
        if max_pain_values:
            return min(max_pain_values.keys(),
                      key=lambda k: max_pain_values[k])

        return 0.0

    # ==========================================================================
    # PRIVATE HELPER METHODS
    # ==========================================================================

    def _contract_to_dict(self, contract: OptionContract) -> dict:
        """Convert contract to dictionary"""
        return {
            'symbol': contract.symbol,
            'strike': contract.strike,
            'expiry': contract.expiry,
            'option_type': contract.option_type.value,
            'bid': contract.bid,
            'ask': contract.ask,
            'last': contract.last,
            'mid_price': contract.mid_price,
            'volume': contract.volume,
            'open_interest': contract.open_interest,
            'implied_volatility': contract.implied_volatility,
            'delta': contract.delta,
            'gamma': contract.gamma,
            'theta': contract.theta,
            'vega': contract.vega,
            'rho': contract.rho,
            'spread': contract.spread,
            'spread_pct': contract.spread_pct,
            'dte': contract.days_to_expiry,
            'moneyness': self._get_moneyness(contract),
            'timestamp': contract.timestamp
        }

    def _get_moneyness(self, contract: OptionContract) -> str:
        """Determine contract moneyness"""
        if contract.symbol not in self.underlying_prices:
            return "UNKNOWN"

        underlying = self.underlying_prices[contract.symbol]

        if contract.option_type == OptionType.CALL:
            if contract.strike < underlying * 0.95:
                return Moneyness.DEEP_ITM.value
            elif contract.strike < underlying * 0.99:
                return Moneyness.ITM.value
            elif contract.strike < underlying * 1.01:
                return Moneyness.ATM.value
            elif contract.strike < underlying * 1.05:
                return Moneyness.OTM.value
            else:
                return Moneyness.DEEP_OTM.value
        else:  # PUT
            if contract.strike > underlying * 1.05:
                return Moneyness.DEEP_ITM.value
            elif contract.strike > underlying * 1.01:
                return Moneyness.ITM.value
            elif contract.strike > underlying * 0.99:
                return Moneyness.ATM.value
            elif contract.strike > underlying * 0.95:
                return Moneyness.OTM.value
            else:
                return Moneyness.DEEP_OTM.value

    def _update_moneyness(self, symbol: str) -> None:
        """Update moneyness for all contracts"""
        # This would recalculate moneyness based on new underlying price
        pass

    def _apply_chain_filter(self, df: pd.DataFrame,
                          filter_type: ChainFilter) -> pd.DataFrame:
        """Apply filter to chain DataFrame"""
        if filter_type == ChainFilter.ALL:
            return df

        elif filter_type == ChainFilter.HIGH_VOLUME:
            threshold = df['volume'].quantile(0.75)
            return df[df['volume'] >= threshold]

        elif filter_type == ChainFilter.HIGH_OI:
            threshold = df['open_interest'].quantile(0.75)
            return df[df['open_interest'] >= threshold]

        elif filter_type == ChainFilter.LIQUID:
            return df[
                (df['volume'] >= MIN_VOLUME_THRESHOLD) &
                (df['open_interest'] >= MIN_OI_THRESHOLD) &
                (df['spread_pct'] <= 5.0)
            ]

        elif filter_type == ChainFilter.NEAR_MONEY:
            return df[df['moneyness'].isin([
                Moneyness.ITM.value,
                Moneyness.ATM.value,
                Moneyness.OTM.value
            ])]

        elif filter_type == ChainFilter.WEEKLY:
            # Filter for weekly expirations
            return df[df['dte'] <= 7]

        elif filter_type == ChainFilter.MONTHLY:
            # Filter for monthly expirations
            return df[df['dte'].isin(range(20, 40))]

        return df

    def _find_strike_by_delta(self, symbol: str, expiry: datetime,
                            target_delta: float,
                            option_type: OptionType) -> float:
        """Find strike closest to target delta"""
        if symbol not in self.chains or expiry not in self.chains[symbol]:
            return 0.0

        best_strike = 0.0
        best_diff = float('inf')
        type_key = option_type.value

        for strike, types in self.chains[symbol][expiry].items():
            if type_key in types:
                contract = types[type_key]
                delta_diff = abs(abs(contract.delta) - target_delta)

                if delta_diff < best_diff:
                    best_diff = delta_diff
                    best_strike = strike

        return best_strike

    def _analyze_expiration(self, symbol: str,
                           expiry: datetime) -> ExpirationCycle:
        """Analyze single expiration"""
        cycle = ExpirationCycle(
            expiry_date=expiry,
            dte=(expiry.date() - datetime.now().date()).days,
            is_weekly=self._is_weekly_expiry(expiry),
            is_monthly=self._is_monthly_expiry(expiry),
            is_quarterly=self._is_quarterly_expiry(expiry)
        )

        if symbol in self.chains and expiry in self.chains[symbol]:
            total_volume = 0
            total_oi = 0
            ivs = []

            for _strike, types in self.chains[symbol][expiry].items():
                for _option_type, contract in types.items():
                    total_volume += contract.volume
                    total_oi += contract.open_interest
                    if contract.implied_volatility > 0:
                        ivs.append(contract.implied_volatility)

            cycle.total_volume = total_volume
            cycle.total_oi = total_oi
            cycle.num_strikes = len(self.chains[symbol][expiry])

            if ivs:
                # Get ATM IV
                atm_strike = self.get_atm_strike(symbol, expiry)
                if atm_strike in self.chains[symbol][expiry]:
                    for _option_type, contract in self.chains[symbol][expiry][atm_strike].items():
                        if contract.implied_volatility > 0:
                            cycle.atm_iv = contract.implied_volatility
                            break

        return cycle

    def _is_weekly_expiry(self, expiry: datetime) -> bool:
        """Check if expiry is weekly"""
        # Weeklies expire on Fridays (weekday 4)
        return expiry.weekday() == 4 and expiry.day not in [15, 16, 17, 18, 19, 20, 21]

    def _is_monthly_expiry(self, expiry: datetime) -> bool:
        """Check if expiry is monthly"""
        # Monthly options expire on 3rd Friday
        return expiry.weekday() == 4 and 15 <= expiry.day <= 21

    def _is_quarterly_expiry(self, expiry: datetime) -> bool:
        """Check if expiry is quarterly"""
        # Quarterly options expire in Mar, Jun, Sep, Dec
        return expiry.month in [3, 6, 9, 12] and self._is_monthly_expiry(expiry)

    def _calculate_iv_skew(self, symbol: str,
                          expiry: datetime | None = None) -> float:
        """Calculate implied volatility skew"""
        if symbol not in self.chains:
            return 0.0

        # Get ATM strike
        if expiry:
            atm = self.get_atm_strike(symbol, expiry)
            if expiry not in self.chains[symbol]:
                return 0.0
            strikes_data = self.chains[symbol][expiry]
        else:
            # Use front month
            expiries = sorted(self.chains[symbol].keys())
            if not expiries:
                return 0.0
            expiry = expiries[0]
            atm = self.get_atm_strike(symbol, expiry)
            strikes_data = self.chains[symbol][expiry]

        # Find 25-delta put and call IVs
        put_ivs = []
        call_ivs = []

        for strike, types in strikes_data.items():
            if strike < atm and "PUT" in types:
                put = types["PUT"]
                if 0.20 <= abs(put.delta) <= 0.30:
                    put_ivs.append(put.implied_volatility)
            elif strike > atm and "CALL" in types:
                call = types["CALL"]
                if 0.20 <= call.delta <= 0.30:
                    call_ivs.append(call.implied_volatility)

        # Calculate skew as difference
        if put_ivs and call_ivs:
            return np.mean(put_ivs) - np.mean(call_ivs)

        return 0.0

    def _detect_unusual_activity(self, symbol: str,
                                expiry: datetime | None = None) -> list[dict]:
        """Detect unusual options activity"""
        unusual = []

        if symbol not in self.chains:
            return unusual

        # Determine expiries to check
        if expiry:
            expiries = [expiry] if expiry in self.chains[symbol] else []
        else:
            expiries = list(self.chains[symbol].keys())

        for exp in expiries:
            for strike, types in self.chains[symbol][exp].items():
                for _option_type, contract in types.items():
                    # Check for unusual volume vs OI
                    if contract.open_interest > 0:
                        vol_oi_ratio = contract.volume / contract.open_interest

                        if vol_oi_ratio > 5.0:  # Volume 5x higher than OI
                            unusual.append({
                                'contract': contract.contract_name,
                                'type': 'HIGH_VOLUME_VS_OI',
                                'volume': contract.volume,
                                'open_interest': contract.open_interest,
                                'ratio': vol_oi_ratio,
                                'strike': strike,
                                'expiry': exp
                            })

                    # Check for large single trades
                    if contract.volume > 1000 and contract.volume > contract.open_interest * 0.5:
                        unusual.append({
                            'contract': contract.contract_name,
                            'type': 'LARGE_TRADE',
                            'volume': contract.volume,
                            'strike': strike,
                            'expiry': exp
                        })

        return unusual

    def _clear_symbol_cache(self, symbol: str) -> None:
        """Clear cache for specific symbol"""
        keys_to_remove = [
            key for key in self.cache
            if symbol in key
        ]
        for key in keys_to_remove:
            del self.cache[key]
            if key in self.cache_timestamp:
                del self.cache_timestamp[key]
        # Enforce cache maxsize
        while len(self.cache) > self._cache_maxsize:
            oldest_key = min(self.cache_timestamp, key=self.cache_timestamp.get)
            del self.cache[oldest_key]
            del self.cache_timestamp[oldest_key]

    def prune_expired_chains(self, as_of: datetime | None = None) -> int:
        """Remove expired option contracts from the chains dict.

        Args:
            as_of: Reference datetime; defaults to now.

        Returns:
            Number of expiration buckets removed.
        """
        cutoff = (as_of or datetime.now()).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        removed = 0
        with self.lock:
            for symbol in list(self.chains):
                for expiry in list(self.chains[symbol]):
                    if expiry < cutoff:
                        del self.chains[symbol][expiry]
                        removed += 1
                if not self.chains[symbol]:
                    del self.chains[symbol]
        if removed:
            self.logger.info("Pruned %s expired option chain buckets", removed)
        return removed

    # ==========================================================================
    # PUBLIC UTILITY METHODS
    # ==========================================================================

    def get_chain_summary(self, symbol: str) -> dict[str, Any]:
        """
        Get comprehensive chain summary

        Args:
            symbol: Asset symbol

        Returns:
            Dictionary with chain summary
        """
        summary = {
            'symbol': symbol,
            'underlying_price': self.underlying_prices.get(symbol, 0.0),
            'num_expirations': 0,
            'total_contracts': 0,
            'total_volume': 0,
            'total_oi': 0,
            'analytics': None,
            'greeks': None,
            'expirations': []
        }

        if symbol not in self.chains:
            return summary

        summary['num_expirations'] = len(self.chains[symbol])

        # Count contracts and aggregate metrics
        for _expiry, strikes in self.chains[symbol].items():
            for _strike, types in strikes.items():
                summary['total_contracts'] += len(types)
                for _option_type, contract in types.items():
                    summary['total_volume'] += contract.volume
                    summary['total_oi'] += contract.open_interest

        # Get analytics
        summary['analytics'] = self.analyze_volume_oi(symbol)

        # Get aggregated Greeks
        summary['greeks'] = self.aggregate_greeks(symbol)

        # Get expiration list
        summary['expirations'] = self.get_expirations(symbol)

        return summary

    def export_chain(self, symbol: str, filename: str,
                    format: str = "csv") -> bool:
        """
        Export chain data to file

        Args:
            symbol: Asset symbol
            filename: Output filename
            format: Export format (csv, json, pickle)

        Returns:
            Success status
        """
        try:
            df = self.get_chain(symbol)

            if df.empty:
                self.logger.warning("No data to export for %s", symbol)
                return False

            if format == "csv":
                df.to_csv(filename, index=False)
            elif format == "json":
                df.to_json(filename, orient='records', date_format='iso')
            elif format == "pickle":
                df.to_pickle(filename)
            else:
                self.logger.error("Unknown export format: %s", format)
                return False

            self.logger.info("Exported %s chain to %s", symbol, filename)
            return True

        except Exception as e:
            self.logger.error("Export failed: %s", e, exc_info=True)
            return False

# ==============================================================================
# TEST/DEMO CODE
# ==============================================================================
if __name__ == "__main__":

    # Create manager
    manager = OptionsChainManager()

    # Create test data

    # Test symbol and price
    symbol = "SPY"
    underlying_price = 585.0
    manager.update_underlying_price(symbol, underlying_price)

    # Create test expiration dates
    expiry1 = datetime.now() + timedelta(days=7)   # Weekly
    expiry2 = datetime.now() + timedelta(days=30)  # Monthly

    # Add test contracts
    strikes = [575, 580, 585, 590, 595]

    for strike in strikes:
        for expiry in [expiry1, expiry2]:
            # Add call
            call = OptionContract(
                symbol=symbol,
                strike=strike,
                expiry=expiry,
                option_type=OptionType.CALL,
                bid=max(0, underlying_price - strike) + np.random.rand(),
                ask=max(0, underlying_price - strike) + np.random.rand() + 0.5,
                volume=np.random.randint(100, 5000),
                open_interest=np.random.randint(1000, 10000),
                implied_volatility=0.15 + np.random.rand() * 0.05,
                delta=0.5 + (strike - underlying_price) * 0.01,
                gamma=0.01 + np.random.rand() * 0.005,
                theta=-0.05 - np.random.rand() * 0.02,
                vega=0.10 + np.random.rand() * 0.05
            )
            manager.add_contract(call)

            # Add put
            put = OptionContract(
                symbol=symbol,
                strike=strike,
                expiry=expiry,
                option_type=OptionType.PUT,
                bid=max(0, strike - underlying_price) + np.random.rand(),
                ask=max(0, strike - underlying_price) + np.random.rand() + 0.5,
                volume=np.random.randint(100, 5000),
                open_interest=np.random.randint(1000, 10000),
                implied_volatility=0.15 + np.random.rand() * 0.05,
                delta=-0.5 + (underlying_price - strike) * 0.01,
                gamma=0.01 + np.random.rand() * 0.005,
                theta=-0.05 - np.random.rand() * 0.02,
                vega=0.10 + np.random.rand() * 0.05
            )
            manager.add_contract(put)


    # Test chain retrieval
    chain_df = manager.get_chain(symbol)

    # Test strike selection
    atm = manager.get_atm_strike(symbol, expiry1)

    strikes_range = manager.get_strike_range(symbol, expiry1, num_strikes=2)

    # Test optimal strike selection
    optimal = manager.select_optimal_strikes(
        symbol, expiry1, strategy="iron_condor", risk_level="moderate"
    )

    # Test expiration management
    expirations = manager.get_expirations(symbol)
    for _exp in expirations:
        pass

    # Test Greeks aggregation
    greeks = manager.aggregate_greeks(symbol)
    for _greek, _value in greeks.items():
        pass

    # Test volume/OI analysis
    analytics = manager.analyze_volume_oi(symbol)

    if analytics.unusual_activity:
        for _activity in analytics.unusual_activity[:3]:
            pass

    # Test chain summary
    summary = manager.get_chain_summary(symbol)

    # Test export
    export_file = "test_chain_export.csv"
    if manager.export_chain(symbol, export_file, format="csv"):
        # Clean up
        import os
        os.remove(export_file)

