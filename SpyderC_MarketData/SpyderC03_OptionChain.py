#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderC03_OptionChain.py
Group: C (Market Data)
Purpose: Options chain data management

Description:
    This module manages option chain data for the Spyder trading system. It fetches
    and maintains real-time option chains, calculates Greeks, tracks open interest
    and volume, and provides option selection utilities based on various criteria
    such as delta, gamma, and probability metrics.

Author: Mohamed Talib
Date: 2025-05-29
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import threading
import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
import bisect
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from scipy.stats import norm
from ibapi.contract import Contract

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU09_DataTypes import OptionData
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient
from SpyderB_Broker.SpyderB06_ContractBuilder import ContractBuilder, OptionRight
from SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Update intervals
CHAIN_UPDATE_INTERVAL = 30  # seconds
GREEKS_UPDATE_INTERVAL = 10  # seconds
STALE_DATA_THRESHOLD = 300  # 5 minutes

# Option chain parameters
DEFAULT_STRIKE_COUNT = 40  # Number of strikes around ATM
MIN_OPEN_INTEREST = 100
MIN_VOLUME = 10
MAX_SPREAD_PERCENT = 0.10  # 10% bid-ask spread

# Risk-free rate
RISK_FREE_RATE = 0.05  # 5% annual

# ==============================================================================
# ENUMS
# ==============================================================================
class OptionType(Enum):
    """Option type"""
    CALL = "C"
    PUT = "P"

class ExpirationCycle(Enum):
    """Expiration cycle types"""
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class OptionData:
    """Single option contract data"""
    contract: Contract
    symbol: str
    strike: float
    expiration: datetime.date
    option_type: OptionType
    
    # Market data
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    volume: int = 0
    open_interest: int = 0
    
    # Greeks
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    implied_volatility: float = 0.0
    
    # Calculated fields
    mid_price: float = 0.0
    spread: float = 0.0
    spread_percent: float = 0.0
    intrinsic_value: float = 0.0
    extrinsic_value: float = 0.0
    
    # Timestamps
    last_update: datetime.datetime = field(default_factory=datetime.datetime.now)
    
    def update_calculated_fields(self, underlying_price: float) -> None:
        """Update calculated fields"""
        # Mid price and spread
        if self.bid > 0 and self.ask > 0:
            self.mid_price = (self.bid + self.ask) / 2
            self.spread = self.ask - self.bid
            self.spread_percent = self.spread / self.mid_price if self.mid_price > 0 else 0
        
        # Intrinsic and extrinsic value
        if self.option_type == OptionType.CALL:
            self.intrinsic_value = max(0, underlying_price - self.strike)
        else:
            self.intrinsic_value = max(0, self.strike - underlying_price)
        
        self.extrinsic_value = self.mid_price - self.intrinsic_value
    
    def is_itm(self, underlying_price: float) -> bool:
        """Check if option is in the money"""
        if self.option_type == OptionType.CALL:
            return underlying_price > self.strike
        else:
            return underlying_price < self.strike
    
    def moneyness(self, underlying_price: float) -> float:
        """Calculate moneyness (underlying/strike for calls, strike/underlying for puts)"""
        if self.option_type == OptionType.CALL:
            return underlying_price / self.strike if self.strike > 0 else 0
        else:
            return self.strike / underlying_price if underlying_price > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'symbol': self.symbol,
            'strike': self.strike,
            'expiration': self.expiration.isoformat(),
            'type': self.option_type.value,
            'bid': self.bid,
            'ask': self.ask,
            'last': self.last,
            'volume': self.volume,
            'open_interest': self.open_interest,
            'delta': self.delta,
            'gamma': self.gamma,
            'theta': self.theta,
            'vega': self.vega,
            'implied_volatility': self.implied_volatility,
            'mid_price': self.mid_price,
            'spread_percent': self.spread_percent,
            'intrinsic_value': self.intrinsic_value,
            'extrinsic_value': self.extrinsic_value
        }

class OptionChain:
    """Complete option chain for an expiration"""
    symbol: str
    expiration: datetime.date
    underlying_price: float
    calls: Dict[float, OptionData]  # Strike -> OptionData
    puts: Dict[float, OptionData]   # Strike -> OptionData
    
    # Chain statistics
    total_call_volume: int = 0
    total_put_volume: int = 0
    total_call_oi: int = 0
    total_put_oi: int = 0
    put_call_ratio: float = 0.0
    
    # ATM data
    atm_strike: float = 0.0
    atm_iv_call: float = 0.0
    atm_iv_put: float = 0.0
    
    # Timestamps
    last_update: datetime.datetime = field(default_factory=datetime.datetime.now)
    
    def update_statistics(self) -> None:
        """Update chain statistics"""
        # Volume and OI
        self.total_call_volume = sum(call.volume for call in self.calls.values())
        self.total_put_volume = sum(put.volume for put in self.puts.values())
        self.total_call_oi = sum(call.open_interest for call in self.calls.values())
        self.total_put_oi = sum(put.open_interest for put in self.puts.values())
        
        # Put/Call ratio
        if self.total_call_volume > 0:
            self.put_call_ratio = self.total_put_volume / self.total_call_volume
        
        # Find ATM strike
        strikes = sorted(self.calls.keys())
        if strikes and self.underlying_price > 0:
            # Find closest strike to underlying
            idx = bisect.bisect_left(strikes, self.underlying_price)
            if idx < len(strikes):
                self.atm_strike = strikes[idx]
                
                # Get ATM IVs
                if self.atm_strike in self.calls:
                    self.atm_iv_call = self.calls[self.atm_strike].implied_volatility
                if self.atm_strike in self.puts:
                    self.atm_iv_put = self.puts[self.atm_strike].implied_volatility
    
    def get_strikes(self) -> List[float]:
        """Get all unique strikes"""
        return sorted(set(list(self.calls.keys()) + list(self.puts.keys())))
    
    def get_otm_options(self) -> Tuple[List[OptionData], List[OptionData]]:
        """Get OTM calls and puts"""
        otm_calls = []
        otm_puts = []
        
        for strike, call in self.calls.items():
            if strike > self.underlying_price:
                otm_calls.append(call)
        
        for strike, put in self.puts.items():
            if strike < self.underlying_price:
                otm_puts.append(put)
        
        return otm_calls, otm_puts
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert chain to DataFrame"""
        data = []
        
        # Add calls
        for strike, option in self.calls.items():
            data.append({**option.to_dict(), 'strike': strike})
        
        # Add puts
        for strike, option in self.puts.items():
            data.append({**option.to_dict(), 'strike': strike})
        
        if data:
            df = pd.DataFrame(data)
            df.sort_values(['type', 'strike'], inplace=True)
            return df
        
        return pd.DataFrame()

class OptionSelectionCriteria:
    """Criteria for option selection"""
    min_delta: Optional[float] = None
    max_delta: Optional[float] = None
    min_gamma: Optional[float] = None
    min_theta: Optional[float] = None
    min_volume: Optional[int] = None
    min_open_interest: Optional[int] = None
    max_spread_percent: Optional[float] = None
    min_days_to_expiry: Optional[int] = None
    max_days_to_expiry: Optional[int] = None
    otm_only: bool = False
    itm_only: bool = False

# ==============================================================================
# OPTION CHAIN MANAGER CLASS
# ==============================================================================
class OptionChainManager:
    """
    Manages option chain data and analysis.
    
    Features:
    - Real-time option chain updates
    - Greeks calculation and monitoring
    - Option selection by various criteria
    - Volatility smile analysis
    - Put/call ratio tracking
    - Open interest analysis
    """
    
    def __init__(self, ib_client: IBClient, event_manager: EventManager):
        """
        Initialize option chain manager.
        
        Args:
            ib_client: IB client instance
            event_manager: Event manager instance
        """
        self.ib_client = ib_client
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Contract builder and Greeks calculator
        self.contract_builder = ContractBuilder(ib_client)
        self.greeks_calculator = GreeksCalculator()
        
        # Trading calendar
        self.calendar = TradingCalendar()
        
        # Option chains storage
        self.option_chains: Dict[datetime.date, OptionChain] = {}
        self.active_subscriptions: Set[str] = set()
        self.ticker_to_option: Dict[int, str] = {}  # ticker_id -> option_key
        self._next_ticker_id = 30000
        
        # Underlying data
        self.underlying_symbol = "SPY"
        self.underlying_price = 0.0
        self.underlying_ticker_id = 29999
        
        # Update threads
        self._chain_update_thread: Optional[threading.Thread] = None
        self._greeks_update_thread: Optional[threading.Thread] = None
        self._running = False
        self._data_lock = threading.RLock()
        
        # IB callbacks
        self._register_ib_callbacks()
        
        self.logger.info("OptionChainManager initialized")
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start option chain manager"""
        if self._running:
            return
        
        self._running = True
        
        # Subscribe to underlying
        self._subscribe_underlying()
        
        # Start update threads
        self._chain_update_thread = threading.Thread(
            target=self._update_chains_loop,
            daemon=True,
            name="OptionChainUpdater"
        )
        self._chain_update_thread.start()
        
        self._greeks_update_thread = threading.Thread(
            target=self._update_greeks_loop,
            daemon=True,
            name="GreeksUpdater"
        )
        self._greeks_update_thread.start()
        
        self.logger.info("Option chain manager started")
    
    def stop(self) -> None:
        """Stop option chain manager"""
        self._running = False
        
        # Cancel all subscriptions
        self._cancel_all_subscriptions()
        
        # Wait for threads
        if self._chain_update_thread:
            self._chain_update_thread.join(timeout=5.0)
        if self._greeks_update_thread:
            self._greeks_update_thread.join(timeout=5.0)
        
        self.logger.info("Option chain manager stopped")
    
    # ==========================================================================
    # CHAIN MANAGEMENT
    # ==========================================================================
    def load_option_chain(
        self,
        expiration: datetime.date,
        strike_count: int = DEFAULT_STRIKE_COUNT
    ) -> bool:
        """
        Load option chain for an expiration.
        
        Args:
            expiration: Expiration date
            strike_count: Number of strikes to load
            
        Returns:
            Success status
        """
        try:
            # Create option chain
            chain = OptionChain(
                symbol=self.underlying_symbol,
                expiration=expiration,
                underlying_price=self.underlying_price,
                calls={},
                puts={}
            )
            
            # Get strikes around current price
            strikes = self._generate_strikes(self.underlying_price, strike_count)
            
            # Create option contracts
            for strike in strikes:
                # Call option
                call_contract = self.contract_builder.create_spy_option(
                    strike=strike,
                    expiration=expiration,
                    right=OptionRight.CALL
                )
                
                call_data = OptionData(
                    contract=call_contract,
                    symbol=self.underlying_symbol,
                    strike=strike,
                    expiration=expiration,
                    option_type=OptionType.CALL
                )
                
                chain.calls[strike] = call_data
                self._subscribe_option(call_data)
                
                # Put option
                put_contract = self.contract_builder.create_spy_option(
                    strike=strike,
                    expiration=expiration,
                    right=OptionRight.PUT
                )
                
                put_data = OptionData(
                    contract=put_contract,
                    symbol=self.underlying_symbol,
                    strike=strike,
                    expiration=expiration,
                    option_type=OptionType.PUT
                )
                
                chain.puts[strike] = put_data
                self._subscribe_option(put_data)
            
            # Store chain
            with self._data_lock:
                self.option_chains[expiration] = chain
            
            self.logger.info(f"Loaded option chain for {expiration} with {len(strikes)} strikes")
            
            # Emit event
            self.event_manager.emit(Event(
                EventType.MARKET_DATA,
                {
                    'type': 'option_chain_loaded',
                    'symbol': self.underlying_symbol,
                    'expiration': expiration.isoformat(),
                    'strike_count': len(strikes)
                }
            ))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load option chain: {e}")
            return False
    
    def load_expirations(
        self,
        min_dte: int = 0,
        max_dte: int = 60,
        max_expirations: int = 5
    ) -> List[datetime.date]:
        """
        Load multiple expiration chains.
        
        Args:
            min_dte: Minimum days to expiry
            max_dte: Maximum days to expiry
            max_expirations: Maximum number of expirations to load
            
        Returns:
            List of loaded expirations
        """
        # Get available expirations
        expirations = self.contract_builder.get_expiration_dates(
            min_dte=min_dte,
            max_dte=max_dte
        )
        
        # Load chains
        loaded = []
        for exp in expirations[:max_expirations]:
            if self.load_option_chain(exp):
                loaded.append(exp)
                time.sleep(0.5)  # Rate limiting
        
        return loaded
    
    def _generate_strikes(self, atm_price: float, count: int) -> List[float]:
        """Generate strikes around ATM price"""
        strikes = []
        
        # Round to nearest strike
        atm_strike = round(atm_price)
        
        # Generate strikes above and below
        half_count = count // 2
        
        for i in range(-half_count, half_count + 1):
            strike = atm_strike + i
            if strike > 0:
                strikes.append(float(strike))
        
        return sorted(strikes)
    
    # ==========================================================================
    # OPTION SELECTION
    # ==========================================================================
    def find_options_by_delta(
        self,
        target_delta: float,
        option_type: OptionType,
        expiration: Optional[datetime.date] = None,
        tolerance: float = 0.05
    ) -> List[OptionData]:
        """
        Find options by target delta.
        
        Args:
            target_delta: Target delta (e.g., 0.30)
            option_type: Call or Put
            expiration: Specific expiration (None = all)
            tolerance: Delta tolerance
            
        Returns:
            List of matching options
        """
        matching_options = []
        
        with self._data_lock:
            chains = self.option_chains.values()
            if expiration:
                chains = [c for c in chains if c.expiration == expiration]
            
            for chain in chains:
                options = chain.calls if option_type == OptionType.CALL else chain.puts
                
                for option in options.values():
                    if abs(abs(option.delta) - abs(target_delta)) <= tolerance:
                        matching_options.append(option)
        
        # Sort by expiration and strike
        matching_options.sort(key=lambda x: (x.expiration, x.strike))
        
        return matching_options
    
    def find_options_by_criteria(
        self,
        criteria: OptionSelectionCriteria,
        option_type: Optional[OptionType] = None
    ) -> List[OptionData]:
        """
        Find options matching criteria.
        
        Args:
            criteria: Selection criteria
            option_type: Call, Put, or None (both)
            
        Returns:
            List of matching options
        """
        matching_options = []
        
        with self._data_lock:
            for chain in self.option_chains.values():
                # Check DTE
                dte = (chain.expiration - datetime.date.today()).days
                if criteria.min_days_to_expiry and dte < criteria.min_days_to_expiry:
                    continue
                if criteria.max_days_to_expiry and dte > criteria.max_days_to_expiry:
                    continue
                
                # Get options to check
                options_to_check = []
                if option_type in [None, OptionType.CALL]:
                    options_to_check.extend(chain.calls.values())
                if option_type in [None, OptionType.PUT]:
                    options_to_check.extend(chain.puts.values())
                
                for option in options_to_check:
                    # Check all criteria
                    if self._matches_criteria(option, criteria, chain.underlying_price):
                        matching_options.append(option)
        
        return matching_options
    
    def _matches_criteria(
        self,
        option: OptionData,
        criteria: OptionSelectionCriteria,
        underlying_price: float
    ) -> bool:
        """Check if option matches criteria"""
        # Delta
        if criteria.min_delta and abs(option.delta) < criteria.min_delta:
            return False
        if criteria.max_delta and abs(option.delta) > criteria.max_delta:
            return False
        
        # Greeks
        if criteria.min_gamma and option.gamma < criteria.min_gamma:
            return False
        if criteria.min_theta and option.theta > criteria.min_theta:  # Theta is negative
            return False
        
        # Liquidity
        if criteria.min_volume and option.volume < criteria.min_volume:
            return False
        if criteria.min_open_interest and option.open_interest < criteria.min_open_interest:
            return False
        
        # Spread
        if criteria.max_spread_percent and option.spread_percent > criteria.max_spread_percent:
            return False
        
        # Moneyness
        is_itm = option.is_itm(underlying_price)
        if criteria.otm_only and is_itm:
            return False
        if criteria.itm_only and not is_itm:
            return False
        
        return True
    
    def get_atm_options(
        self,
        expiration: datetime.date
    ) -> Tuple[Optional[OptionData], Optional[OptionData]]:
        """
        Get ATM call and put for an expiration.
        
        Args:
            expiration: Expiration date
            
        Returns:
            Tuple of (atm_call, atm_put)
        """
        with self._data_lock:
            chain = self.option_chains.get(expiration)
            if not chain:
                return None, None
            
            if chain.atm_strike in chain.calls:
                atm_call = chain.calls[chain.atm_strike]
            else:
                atm_call = None
            
            if chain.atm_strike in chain.puts:
                atm_put = chain.puts[chain.atm_strike]
            else:
                atm_put = None
            
            return atm_call, atm_put
    
    # ==========================================================================
    # ANALYSIS
    # ==========================================================================
    def get_volatility_smile(
        self,
        expiration: datetime.date,
        option_type: OptionType
    ) -> pd.DataFrame:
        """
        Get volatility smile data.
        
        Args:
            expiration: Expiration date
            option_type: Call or Put
            
        Returns:
            DataFrame with strike and IV
        """
        with self._data_lock:
            chain = self.option_chains.get(expiration)
            if not chain:
                return pd.DataFrame()
            
            options = chain.calls if option_type == OptionType.CALL else chain.puts
            
            data = []
            for strike, option in options.items():
                if option.implied_volatility > 0:
                    data.append({
                        'strike': strike,
                        'iv': option.implied_volatility,
                        'delta': option.delta,
                        'volume': option.volume,
                        'open_interest': option.open_interest
                    })
            
            if data:
                df = pd.DataFrame(data)
                df.sort_values('strike', inplace=True)
                return df
            
            return pd.DataFrame()
    
    def get_put_call_ratios(self) -> pd.DataFrame:
        """
        Get put/call ratios for all expirations.
        
        Returns:
            DataFrame with expiration and ratios
        """
        with self._data_lock:
            data = []
            for exp, chain in self.option_chains.items():
                data.append({
                    'expiration': exp,
                    'put_call_volume': chain.put_call_ratio,
                    'put_call_oi': (chain.total_put_oi / chain.total_call_oi 
                                   if chain.total_call_oi > 0 else 0),
                    'total_volume': chain.total_call_volume + chain.total_put_volume,
                    'total_oi': chain.total_call_oi + chain.total_put_oi
                })
            
            if data:
                df = pd.DataFrame(data)
                df.sort_values('expiration', inplace=True)
                return df
            
            return pd.DataFrame()
    
    def get_max_pain(self, expiration: datetime.date) -> Optional[float]:
        """
        Calculate max pain strike for an expiration.
        
        Args:
            expiration: Expiration date
            
        Returns:
            Max pain strike or None
        """
        with self._data_lock:
            chain = self.option_chains.get(expiration)
            if not chain:
                return None
            
            strikes = chain.get_strikes()
            if not strikes:
                return None
            
            min_pain = float('inf')
            max_pain_strike = None
            
            # Calculate pain at each strike
            for test_strike in strikes:
                total_pain = 0.0
                
                # Call pain (ITM calls)
                for strike, call in chain.calls.items():
                    if strike < test_strike:
                        pain = (test_strike - strike) * call.open_interest * 100
                        total_pain += pain
                
                # Put pain (ITM puts)
                for strike, put in chain.puts.items():
                    if strike > test_strike:
                        pain = (strike - test_strike) * put.open_interest * 100
                        total_pain += pain
                
                if total_pain < min_pain:
                    min_pain = total_pain
                    max_pain_strike = test_strike
            
            return max_pain_strike
    
    # ==========================================================================
    # MARKET DATA SUBSCRIPTIONS
    # ==========================================================================
    def _subscribe_underlying(self) -> None:
        """Subscribe to underlying market data"""
        contract = self.contract_builder.create_spy_stock()
        
        self.ib_client.reqMktData(
            self.underlying_ticker_id,
            contract,
            "",
            False,
            False,
            []
        )
        
        self.logger.info(f"Subscribed to {self.underlying_symbol} market data")
    
    def _subscribe_option(self, option_data: OptionData) -> None:
        """Subscribe to option market data"""
        ticker_id = self._get_next_ticker_id()
        option_key = self._get_option_key(option_data)
        
        self.ticker_to_option[ticker_id] = option_key
        self.active_subscriptions.add(option_key)
        
        # Request market data with Greeks
        self.ib_client.reqMktData(
            ticker_id,
            option_data.contract,
            "100,101,104,106",  # Option volume, open interest, Greeks
            False,
            False,
            []
        )
    
    def _cancel_all_subscriptions(self) -> None:
        """Cancel all market data subscriptions"""
        # Cancel underlying
        self.ib_client.cancelMktData(self.underlying_ticker_id)
        
        # Cancel options
        for ticker_id in list(self.ticker_to_option.keys()):
            self.ib_client.cancelMktData(ticker_id)
        
        self.ticker_to_option.clear()
        self.active_subscriptions.clear()
    
    def _get_next_ticker_id(self) -> int:
        """Get next ticker ID"""
        self._next_ticker_id += 1
        return self._next_ticker_id
    
    def _get_option_key(self, option_data: OptionData) -> str:
        """Generate unique key for option"""
        return f"{option_data.expiration}_{option_data.strike}_{option_data.option_type.value}"
    
    def _find_option_by_key(self, option_key: str) -> Optional[OptionData]:
        """Find option by key"""
        parts = option_key.split('_')
        if len(parts) != 3:
            return None
        
        expiration = datetime.date.fromisoformat(parts[0])
        strike = float(parts[1])
        option_type = OptionType(parts[2])
        
        with self._data_lock:
            chain = self.option_chains.get(expiration)
            if chain:
                if option_type == OptionType.CALL:
                    return chain.calls.get(strike)
                else:
                    return chain.puts.get(strike)
        
        return None
    
    # ==========================================================================
    # UPDATE LOOPS
    # ==========================================================================
    def _update_chains_loop(self) -> None:
        """Periodically update chain statistics"""
        while self._running:
            try:
                with self._data_lock:
                    for chain in self.option_chains.values():
                        chain.underlying_price = self.underlying_price
                        chain.update_statistics()
                        
                        # Check for stale data
                        for option in list(chain.calls.values()) + list(chain.puts.values()):
                            age = (datetime.datetime.now() - option.last_update).seconds
                            if age > STALE_DATA_THRESHOLD:
                                self.logger.warning(
                                    f"Stale data for {option.symbol} {option.strike} "
                                    f"{option.option_type.value}"
                                )
                
                time.sleep(CHAIN_UPDATE_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Error in chain update loop: {e}")
    
    def _update_greeks_loop(self) -> None:
        """Update Greeks calculations"""
        while self._running:
            try:
                with self._data_lock:
                    for chain in self.option_chains.values():
                        # Calculate time to expiry
                        dte = (chain.expiration - datetime.date.today()).days
                        time_to_expiry = dte / 365.0
                        
                        # Update Greeks for all options
                        for option in list(chain.calls.values()) + list(chain.puts.values()):
                            if option.implied_volatility > 0 and self.underlying_price > 0:
                                greeks = self.greeks_calculator.calculate_greeks(
                                    underlying_price=self.underlying_price,
                                    strike_price=option.strike,
                                    time_to_expiry=time_to_expiry,
                                    volatility=option.implied_volatility,
                                    risk_free_rate=RISK_FREE_RATE,
                                    option_type='C' if option.option_type == OptionType.CALL else 'P'
                                )
                                
                                option.delta = greeks['delta']
                                option.gamma = greeks['gamma']
                                option.theta = greeks['theta']
                                option.vega = greeks['vega']
                                option.rho = greeks['rho']
                
                time.sleep(GREEKS_UPDATE_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Error in Greeks update loop: {e}")
    
    # ==========================================================================
    # IB CALLBACKS
    # ==========================================================================
    def _register_ib_callbacks(self) -> None:
        """Register IB API callbacks"""
        self.ib_client.register_callback('tickPrice', self._on_tick_price)
        self.ib_client.register_callback('tickSize', self._on_tick_size)
        self.ib_client.register_callback('tickOptionComputation', self._on_tick_option)
        self.ib_client.register_callback('tickGeneric', self._on_tick_generic)
    
    def _on_tick_price(self, reqId: int, tickType: int, price: float, attrib) -> None:
        """Handle price tick"""
        if reqId == self.underlying_ticker_id:
            # Underlying price update
            if tickType == 4:  # Last price
                self.underlying_price = price
                self.logger.debug(f"Underlying price: {price}")
        else:
            # Option price update
            option_key = self.ticker_to_option.get(reqId)
            if option_key:
                option = self._find_option_by_key(option_key)
                if option:
                    if tickType == 1:  # Bid
                        option.bid = price
                    elif tickType == 2:  # Ask
                        option.ask = price
                    elif tickType == 4:  # Last
                        option.last = price
                    
                    option.update_calculated_fields(self.underlying_price)
                    option.last_update = datetime.datetime.now()
    
    def _on_tick_size(self, reqId: int, tickType: int, size: int) -> None:
        """Handle size tick"""
        if reqId != self.underlying_ticker_id:
            option_key = self.ticker_to_option.get(reqId)
            if option_key:
                option = self._find_option_by_key(option_key)
                if option:
                    if tickType == 8:  # Volume
                        option.volume = size
    
    def _on_tick_option(self, reqId: int, tickType: int, impliedVol: float,
                        delta: float, optPrice: float, pvDividend: float,
                        gamma: float, vega: float, theta: float, undPrice: float) -> None:
        """Handle option computation tick"""
        option_key = self.ticker_to_option.get(reqId)
        if option_key:
            option = self._find_option_by_key(option_key)
            if option:
                if impliedVol > 0:
                    option.implied_volatility = impliedVol
                
                # Update Greeks from IB
                if delta != -99:  # IB uses -99 for invalid
                    option.delta = delta
                    option.gamma = gamma
                    option.theta = theta
                    option.vega = vega
                
                option.last_update = datetime.datetime.now()
    
    def _on_tick_generic(self, reqId: int, tickType: int, value: float) -> None:
        """Handle generic tick"""
        if reqId != self.underlying_ticker_id:
            option_key = self.ticker_to_option.get(reqId)
            if option_key:
                option = self._find_option_by_key(option_key)
                if option:
                    if tickType == 101:  # Open interest
                        option.open_interest = int(value)
    
    # ==========================================================================
    # QUERIES
    # ==========================================================================
    def get_chain(self, expiration: datetime.date) -> Optional[OptionChain]:
        """Get option chain for expiration"""
        with self._data_lock:
            return self.option_chains.get(expiration)
    
    def get_all_chains(self) -> Dict[datetime.date, OptionChain]:
        """Get all option chains"""
        with self._data_lock:
            return self.option_chains.copy()
    
    def get_expirations(self) -> List[datetime.date]:
        """Get loaded expiration dates"""
        with self._data_lock:
            return sorted(self.option_chains.keys())
    
    def export_chain_data(self, expiration: datetime.date) -> pd.DataFrame:
        """Export chain data to DataFrame"""
        chain = self.get_chain(expiration)
        if chain:
            return chain.to_dataframe()
        return pd.DataFrame()

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test option chain manager
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    
    # Mock IB client
    class MockIBClient:
        def __init__(self):
            self.callbacks = defaultdict(list)
        
        def register_callback(self, event, callback):
            self.callbacks[event].append(callback)
        
        def reqMktData(self, tickerId, contract, genericTicks, snapshot, regulatorySnapshot, mktDataOptions):
            print(f"Requesting market data for ticker {tickerId}: {contract.symbol} {getattr(contract, 'strike', 'STK')}")
            
            # Simulate some data
            import random
            
            # Simulate price updates
            if hasattr(contract, 'strike'):
                # Option
                mid = 5.0 + random.random() * 2
                for cb in self.callbacks['tickPrice']:
                    cb(tickerId, 1, mid - 0.05, None)  # Bid
                    cb(tickerId, 2, mid + 0.05, None)  # Ask
                    cb(tickerId, 4, mid, None)  # Last
                
                # Greeks
                for cb in self.callbacks['tickOptionComputation']:
                    cb(tickerId, 10, 0.20, 0.30, mid, 0, 0.05, 0.10, -0.05, 450)
            else:
                # Stock
                for cb in self.callbacks['tickPrice']:
                    cb(tickerId, 4, 450.50, None)  # Last
        
        def cancelMktData(self, tickerId):
            print(f"Cancelling market data for ticker {tickerId}")
    
    # Initialize
    event_manager = EventManager()
    ib_client = MockIBClient()
    chain_manager = OptionChainManager(ib_client, event_manager)
    
    # Start manager
    chain_manager.start()
    
    # Load some chains
    print("Loading option chains...")
    expirations = chain_manager.load_expirations(min_dte=0, max_dte=30, max_expirations=2)
    print(f"Loaded {len(expirations)} chains: {expirations}")
    
    # Wait for data
    time.sleep(2)
    
    # Find 30-delta puts
    print("\nFinding 30-delta puts...")
    puts = chain_manager.find_options_by_delta(
        target_delta=0.30,
        option_type=OptionType.PUT,
        tolerance=0.10
    )
    print(f"Found {len(puts)} puts")
    for put in puts[:3]:
        print(f"  {put.strike} {put.expiration} - Delta: {put.delta:.2f}, IV: {put.implied_volatility:.2f}")
    
    # Get volatility smile
    if expirations:
        print(f"\nVolatility smile for {expirations[0]}:")
        smile = chain_manager.get_volatility_smile(expirations[0], OptionType.CALL)
        if not smile.empty:
            print(smile.head())
    
    # Get put/call ratios
    print("\nPut/Call ratios:")
    ratios = chain_manager.get_put_call_ratios()
    if not ratios.empty:
        print(ratios)
    
    # Find max pain
    if expirations:
        max_pain = chain_manager.get_max_pain(expirations[0])
        print(f"\nMax pain for {expirations[0]}: ${max_pain}")
    
    # Stop manager
    chain_manager.stop()