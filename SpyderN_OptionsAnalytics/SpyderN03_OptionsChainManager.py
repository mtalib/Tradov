#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderN03_OptionsChainManager.py
Group: N (Options Analytics)
Purpose: Comprehensive option chain data management and strike selection
Author: Mohamed Talib
Date Created: 2025-08-07
Last Updated: 2025-08-07 Time: 18:00:00

Description:
    This module provides efficient option chain management for the Spyder system.
    It handles option chain data structures, intelligent strike selection, expiration
    management, real-time updates, and provides analytical tools for volume/OI analysis.
    The manager integrates with the pricing and IV engines to provide complete
    chain analytics and optimal strike selection for various strategies.

Key Features:
    - Efficient option chain data structures
    - Intelligent strike selection algorithms
    - Expiration cycle management (weekly/monthly/quarterly)
    - Chain filtering by moneyness, volume, OI
    - Greeks aggregation across strikes and expiries
    - Volume/Open Interest analysis
    - Unusual activity detection
    - Real-time chain updates and caching
    - Strategy-specific strike recommendations
    - Pin risk and gamma exposure analysis
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import bisect
import json
import pickle
import threading
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Union, Any, Set, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, OrderedDict
from pathlib import Path
import heapq

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderN01_OptionsPricer import (
        OptionsPricer, OptionContract, MarketData, OptionType,
        ExerciseStyle, OptionPrice
    )
    from SpyderN02_ImpliedVolatilityEngine import (
        ImpliedVolatilityEngine, IVPoint
    )
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    LOCAL_IMPORTS = True
except ImportError:
    LOCAL_IMPORTS = False
    import logging
    
    # Mock imports for standalone testing
    class SpyderLogger:
        @staticmethod
        def get_logger(name):
            return logging.getLogger(name)
    
    class SpyderErrorHandler:
        def handle_error(self, error, context):
            print(f"Error in {context}: {error}")
    
    class OptionType(Enum):
        CALL = "CALL"
        PUT = "PUT"
    
    class ExerciseStyle(Enum):
        EUROPEAN = "EUROPEAN"
        AMERICAN = "AMERICAN"

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Chain parameters
MAX_CHAIN_SIZE = 10000             # Maximum options in chain
CACHE_TTL_SECONDS = 30             # Cache time-to-live
UPDATE_THROTTLE_MS = 100           # Minimum time between updates

# Strike selection parameters
DEFAULT_NUM_STRIKES = 10          # Default strikes to select
ATM_RANGE_PCT = 0.02              # 2% range for ATM
DEEP_ITM_THRESHOLD = 0.80         # 20% ITM
DEEP_OTM_THRESHOLD = 1.20         # 20% OTM
MIN_VOLUME_FILTER = 10            # Minimum volume
MIN_OI_FILTER = 100               # Minimum open interest

# Expiration parameters
MAX_DTE = 730                     # Maximum days to expiry (2 years)
WEEKLY_EXPIRY_DAY = 4             # Friday
MONTHLY_EXPIRY_WEEK = 3          # Third week
QUARTERLY_MONTHS = [3, 6, 9, 12] # March, June, Sept, Dec

# Greeks aggregation
DELTA_HEDGE_BUCKETS = [0.10, 0.25, 0.50, 0.75, 0.90]  # Delta buckets
GAMMA_CONCENTRATION_THRESHOLD = 0.20  # 20% of total gamma

# Volume analysis
UNUSUAL_VOLUME_RATIO = 3.0       # 3x average volume
UNUSUAL_OI_CHANGE = 0.50          # 50% OI change
FLOW_IMBALANCE_THRESHOLD = 0.30  # 30% flow imbalance

# Pin risk parameters
PIN_RISK_RANGE = 1.00             # $1 pin risk range
PIN_RISK_DTE = 2                  # Days before expiry

# Strategy parameters
IRON_CONDOR_DELTA = 0.20         # 20 delta for IC
BUTTERFLY_WIDTH = 5.00            # $5 width for butterflies
CALENDAR_MIN_SKEW = 0.05         # 5% IV skew for calendars

# ==============================================================================
# ENUMS
# ==============================================================================

class ExpiryType(Enum):
    """Option expiration types"""
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    LEAPS = "LEAPS"

class StrikeSelectionMethod(Enum):
    """Strike selection methods"""
    ATM = "AT_THE_MONEY"
    OTM = "OUT_OF_THE_MONEY"
    ITM = "IN_THE_MONEY"
    DELTA_BASED = "DELTA_BASED"
    VOLUME_WEIGHTED = "VOLUME_WEIGHTED"
    OI_WEIGHTED = "OPEN_INTEREST_WEIGHTED"
    LIQUIDITY_BASED = "LIQUIDITY_BASED"
    CUSTOM = "CUSTOM"

class ChainFilterType(Enum):
    """Chain filtering types"""
    MONEYNESS = "MONEYNESS"
    VOLUME = "VOLUME"
    OPEN_INTEREST = "OPEN_INTEREST"
    IMPLIED_VOL = "IMPLIED_VOL"
    SPREAD = "BID_ASK_SPREAD"
    GREEKS = "GREEKS"

class ActivityType(Enum):
    """Option activity types"""
    NORMAL = "NORMAL"
    UNUSUAL_VOLUME = "UNUSUAL_VOLUME"
    UNUSUAL_OI = "UNUSUAL_OI"
    SWEEP = "SWEEP"
    BLOCK = "BLOCK"
    SPREAD = "SPREAD"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class OptionData:
    """Complete option data point"""
    contract: Any  # OptionContract
    symbol: str
    underlying: str
    strike: float
    expiry: datetime
    option_type: OptionType
    
    # Market data
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    
    # Calculated fields
    mid_price: float = field(init=False)
    spread: float = field(init=False)
    spread_pct: float = field(init=False)
    moneyness: float = field(init=False)
    
    # Greeks (optional)
    delta: Optional[float] = None
    gamma: Optional[float] = None
    vega: Optional[float] = None
    theta: Optional[float] = None
    implied_vol: Optional[float] = None
    
    # Analytics
    volume_oi_ratio: float = field(init=False)
    liquidity_score: float = field(init=False)
    
    def __post_init__(self):
        """Calculate derived fields"""
        self.mid_price = (self.bid + self.ask) / 2 if self.bid and self.ask else self.last
        self.spread = self.ask - self.bid if self.bid and self.ask else 0
        self.spread_pct = self.spread / self.mid_price if self.mid_price > 0 else 0
        self.volume_oi_ratio = self.volume / self.open_interest if self.open_interest > 0 else 0
        self.liquidity_score = self._calculate_liquidity_score()
    
    def _calculate_liquidity_score(self) -> float:
        """Calculate liquidity score (0-100)"""
        score = 0
        
        # Volume component (40%)
        if self.volume > 1000:
            score += 40
        elif self.volume > 100:
            score += 20
        elif self.volume > 10:
            score += 10
        
        # OI component (40%)
        if self.open_interest > 5000:
            score += 40
        elif self.open_interest > 1000:
            score += 20
        elif self.open_interest > 100:
            score += 10
        
        # Spread component (20%)
        if self.spread_pct < 0.01:  # Less than 1%
            score += 20
        elif self.spread_pct < 0.02:
            score += 10
        elif self.spread_pct < 0.05:
            score += 5
        
        return score
    
    def update_moneyness(self, spot_price: float):
        """Update moneyness based on spot price"""
        self.moneyness = spot_price / self.strike if self.strike > 0 else 0

@dataclass
class ExpirationCycle:
    """Option expiration cycle information"""
    expiry_date: datetime
    expiry_type: ExpiryType
    days_to_expiry: int
    trading_days_to_expiry: int
    
    # Chain statistics
    total_volume: int = 0
    total_oi: int = 0
    num_strikes: int = 0
    atm_iv: Optional[float] = None
    
    # Greeks aggregates
    total_delta: float = 0
    total_gamma: float = 0
    total_vega: float = 0
    total_theta: float = 0
    
    # Pin risk
    max_gamma_strike: Optional[float] = None
    pin_risk_level: float = 0

@dataclass
class OptionChain:
    """Complete option chain for an underlying"""
    underlying: str
    spot_price: float
    timestamp: datetime
    
    # Options organized by expiry and strike
    calls: Dict[datetime, Dict[float, OptionData]]
    puts: Dict[datetime, Dict[float, OptionData]]
    
    # Expiration cycles
    expirations: List[ExpirationCycle]
    
    # Chain-wide statistics
    total_call_volume: int = 0
    total_put_volume: int = 0
    total_call_oi: int = 0
    total_put_oi: int = 0
    put_call_ratio: float = 0
    
    # Greeks aggregates
    net_delta: float = 0
    total_gamma: float = 0
    total_vega: float = 0
    total_theta: float = 0
    
    def get_expiry_dates(self) -> List[datetime]:
        """Get sorted list of expiry dates"""
        expiries = set()
        expiries.update(self.calls.keys())
        expiries.update(self.puts.keys())
        return sorted(expiries)
    
    def get_strikes(self, expiry: datetime) -> List[float]:
        """Get sorted list of strikes for expiry"""
        strikes = set()
        if expiry in self.calls:
            strikes.update(self.calls[expiry].keys())
        if expiry in self.puts:
            strikes.update(self.puts[expiry].keys())
        return sorted(strikes)
    
    def get_option(self, strike: float, expiry: datetime, option_type: OptionType) -> Optional[OptionData]:
        """Get specific option"""
        if option_type == OptionType.CALL:
            return self.calls.get(expiry, {}).get(strike)
        else:
            return self.puts.get(expiry, {}).get(strike)

@dataclass
class StrikeSelection:
    """Strike selection result"""
    method: StrikeSelectionMethod
    strikes: List[float]
    expiry: datetime
    scores: Dict[float, float]  # Strike -> selection score
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class VolumeAnalysis:
    """Volume and flow analysis"""
    timestamp: datetime
    underlying: str
    
    # Volume metrics
    call_volume: int
    put_volume: int
    total_volume: int
    volume_ratio: float
    
    # Flow metrics
    call_premium: float
    put_premium: float
    net_premium: float
    
    # Unusual activity
    unusual_strikes: List[Tuple[float, datetime, str]]  # (strike, expiry, reason)
    sweeps: List[Dict[str, Any]]
    blocks: List[Dict[str, Any]]
    
    # Sentiment
    bullish_flow: float
    bearish_flow: float
    sentiment_score: float  # -100 to +100

@dataclass
class GammaExposure:
    """Gamma exposure analysis"""
    timestamp: datetime
    spot_price: float
    
    # Gamma by strike
    strikes: List[float]
    call_gamma: List[float]
    put_gamma: List[float]
    net_gamma: List[float]
    
    # Key levels
    zero_gamma_level: float
    max_gamma_strike: float
    flip_point: Optional[float]
    
    # Exposure metrics
    total_gamma_exposure: float
    dealer_gamma: float
    gamma_imbalance: float

# ==============================================================================
# OPTION CHAIN MANAGER
# ==============================================================================

class OptionsChainManager:
    """
    Comprehensive option chain management system
    
    This class provides efficient option chain data management, intelligent
    strike selection, expiration management, and analytical tools for
    volume/OI analysis. It integrates with pricing and IV engines for
    complete chain analytics.
    
    Attributes:
        pricer: Options pricing engine
        iv_engine: Implied volatility engine
        chains: Active option chains by underlying
        
    Example:
        >>> manager = OptionsChainManager()
        >>> chain = manager.build_chain('SPY', market_data)
        >>> strikes = manager.select_strikes(chain, method=StrikeSelectionMethod.DELTA_BASED, delta=0.30)
        >>> analysis = manager.analyze_volume(chain)
    """
    
    def __init__(self):
        """Initialize chain manager"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Initialize engines
        if LOCAL_IMPORTS:
            self.pricer = OptionsPricer()
            self.iv_engine = ImpliedVolatilityEngine()
        else:
            self.pricer = None
            self.iv_engine = None
        
        # Chain storage
        self.chains: Dict[str, OptionChain] = {}
        self.chain_lock = threading.RLock()
        
        # Cache
        self.cache: Dict[str, Tuple[Any, datetime]] = {}
        self.last_update: Dict[str, datetime] = {}
        
        # Historical data
        self.volume_history: Dict[str, List[VolumeAnalysis]] = defaultdict(list)
        self.gamma_history: Dict[str, List[GammaExposure]] = defaultdict(list)
        
        # Configuration
        self.auto_calculate_greeks = True
        self.cache_enabled = True
        self.max_cache_age = timedelta(seconds=CACHE_TTL_SECONDS)
        
        self.logger.info("OptionsChainManager initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - CHAIN BUILDING
    # ==========================================================================
    
    def build_chain(self, underlying: str, spot_price: float,
                   option_data: List[Dict]) -> OptionChain:
        """
        Build option chain from market data
        
        Args:
            underlying: Underlying symbol
            spot_price: Current spot price
            option_data: List of option market data
            
        Returns:
            Complete OptionChain object
        """
        try:
            with self.chain_lock:
                # Initialize chain structure
                chain = OptionChain(
                    underlying=underlying,
                    spot_price=spot_price,
                    timestamp=datetime.now(),
                    calls=defaultdict(dict),
                    puts=defaultdict(dict),
                    expirations=[]
                )
                
                # Process each option
                for data in option_data:
                    option = self._create_option_data(data, spot_price)
                    if option:
                        # Add to chain
                        if option.option_type == OptionType.CALL:
                            chain.calls[option.expiry][option.strike] = option
                        else:
                            chain.puts[option.expiry][option.strike] = option
                        
                        # Update statistics
                        self._update_chain_statistics(chain, option)
                
                # Build expiration cycles
                chain.expirations = self._build_expiration_cycles(chain)
                
                # Calculate Greeks if enabled
                if self.auto_calculate_greeks:
                    self._calculate_chain_greeks(chain)
                
                # Calculate aggregates
                self._calculate_chain_aggregates(chain)
                
                # Store chain
                self.chains[underlying] = chain
                self.last_update[underlying] = datetime.now()
                
                self.logger.info(f"Built chain for {underlying}: {len(option_data)} options")
                
                return chain
                
        except Exception as e:
            self.logger.error(f"Error building chain: {e}")
            self.error_handler.handle_error(e, {"underlying": underlying})
            return self._create_empty_chain(underlying, spot_price)
    
    def update_chain(self, underlying: str, updates: List[Dict]) -> bool:
        """
        Update existing chain with new data
        
        Args:
            underlying: Underlying symbol
            updates: List of option updates
            
        Returns:
            Success status
        """
        try:
            if underlying not in self.chains:
                self.logger.warning(f"No chain exists for {underlying}")
                return False
            
            # Check throttling
            last_update = self.last_update.get(underlying)
            if last_update:
                elapsed = (datetime.now() - last_update).total_seconds() * 1000
                if elapsed < UPDATE_THROTTLE_MS:
                    return False  # Too soon
            
            with self.chain_lock:
                chain = self.chains[underlying]
                
                for update in updates:
                    strike = update['strike']
                    expiry = update['expiry']
                    option_type = OptionType[update['type']]
                    
                    # Find and update option
                    if option_type == OptionType.CALL:
                        if expiry in chain.calls and strike in chain.calls[expiry]:
                            self._update_option_data(chain.calls[expiry][strike], update)
                    else:
                        if expiry in chain.puts and strike in chain.puts[expiry]:
                            self._update_option_data(chain.puts[expiry][strike], update)
                
                # Recalculate aggregates
                self._calculate_chain_aggregates(chain)
                
                self.last_update[underlying] = datetime.now()
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error updating chain: {e}")
            return False
    
    # ==========================================================================
    # PUBLIC METHODS - STRIKE SELECTION
    # ==========================================================================
    
    def select_strikes(self, chain: OptionChain, 
                      method: StrikeSelectionMethod = StrikeSelectionMethod.ATM,
                      expiry: Optional[datetime] = None,
                      num_strikes: int = DEFAULT_NUM_STRIKES,
                      **kwargs) -> StrikeSelection:
        """
        Select strikes based on method
        
        Args:
            chain: Option chain
            method: Selection method
            expiry: Target expiry (uses nearest if None)
            num_strikes: Number of strikes to select
            **kwargs: Method-specific parameters
            
        Returns:
            StrikeSelection with selected strikes
        """
        # Get target expiry
        if expiry is None:
            expiries = chain.get_expiry_dates()
            if not expiries:
                return StrikeSelection(method, [], datetime.now(), {})
            expiry = expiries[0]  # Nearest expiry
        
        # Get available strikes
        strikes = chain.get_strikes(expiry)
        if not strikes:
            return StrikeSelection(method, [], expiry, {})
        
        # Select based on method
        if method == StrikeSelectionMethod.ATM:
            selected = self._select_atm_strikes(chain, strikes, num_strikes)
        elif method == StrikeSelectionMethod.OTM:
            selected = self._select_otm_strikes(chain, strikes, num_strikes)
        elif method == StrikeSelectionMethod.ITM:
            selected = self._select_itm_strikes(chain, strikes, num_strikes)
        elif method == StrikeSelectionMethod.DELTA_BASED:
            delta = kwargs.get('delta', 0.30)
            selected = self._select_delta_strikes(chain, expiry, delta)
        elif method == StrikeSelectionMethod.VOLUME_WEIGHTED:
            selected = self._select_volume_weighted_strikes(chain, expiry, num_strikes)
        elif method == StrikeSelectionMethod.OI_WEIGHTED:
            selected = self._select_oi_weighted_strikes(chain, expiry, num_strikes)
        elif method == StrikeSelectionMethod.LIQUIDITY_BASED:
            selected = self._select_liquid_strikes(chain, expiry, num_strikes)
        else:
            selected = strikes[:num_strikes]
        
        # Calculate scores
        scores = self._calculate_strike_scores(chain, expiry, selected, method)
        
        return StrikeSelection(
            method=method,
            strikes=selected,
            expiry=expiry,
            scores=scores,
            metadata=kwargs
        )
    
    def recommend_strikes_for_strategy(self, chain: OptionChain,
                                      strategy: str,
                                      expiry: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Recommend strikes for specific strategy
        
        Args:
            chain: Option chain
            strategy: Strategy name (e.g., 'iron_condor', 'butterfly', 'calendar')
            expiry: Target expiry
            
        Returns:
            Strategy-specific strike recommendations
        """
        recommendations = {}
        
        if strategy.lower() == 'iron_condor':
            recommendations = self._recommend_iron_condor_strikes(chain, expiry)
        elif strategy.lower() == 'butterfly':
            recommendations = self._recommend_butterfly_strikes(chain, expiry)
        elif strategy.lower() == 'calendar':
            recommendations = self._recommend_calendar_strikes(chain)
        elif strategy.lower() == 'straddle':
            recommendations = self._recommend_straddle_strikes(chain, expiry)
        elif strategy.lower() == 'strangle':
            recommendations = self._recommend_strangle_strikes(chain, expiry)
        elif strategy.lower() == 'vertical':
            recommendations = self._recommend_vertical_strikes(chain, expiry)
        
        return recommendations
    
    # ==========================================================================
    # PUBLIC METHODS - CHAIN FILTERING
    # ==========================================================================
    
    def filter_chain(self, chain: OptionChain,
                    filters: Dict[ChainFilterType, Any]) -> OptionChain:
        """
        Filter option chain based on criteria
        
        Args:
            chain: Original chain
            filters: Dictionary of filter types and values
            
        Returns:
            Filtered OptionChain
        """
        # Create filtered chain
        filtered = OptionChain(
            underlying=chain.underlying,
            spot_price=chain.spot_price,
            timestamp=chain.timestamp,
            calls=defaultdict(dict),
            puts=defaultdict(dict),
            expirations=[]
        )
        
        # Apply filters
        for expiry in chain.get_expiry_dates():
            for strike in chain.get_strikes(expiry):
                # Check call
                call = chain.get_option(strike, expiry, OptionType.CALL)
                if call and self._passes_filters(call, filters):
                    filtered.calls[expiry][strike] = call
                
                # Check put
                put = chain.get_option(strike, expiry, OptionType.PUT)
                if put and self._passes_filters(put, filters):
                    filtered.puts[expiry][strike] = put
        
        # Rebuild statistics
        filtered.expirations = self._build_expiration_cycles(filtered)
        self._calculate_chain_aggregates(filtered)
        
        return filtered
    
    # ==========================================================================
    # PUBLIC METHODS - ANALYSIS
    # ==========================================================================
    
    def analyze_volume(self, chain: OptionChain) -> VolumeAnalysis:
        """
        Analyze volume and option flow
        
        Args:
            chain: Option chain
            
        Returns:
            VolumeAnalysis with flow metrics
        """
        analysis = VolumeAnalysis(
            timestamp=datetime.now(),
            underlying=chain.underlying,
            call_volume=0,
            put_volume=0,
            total_volume=0,
            volume_ratio=0,
            call_premium=0,
            put_premium=0,
            net_premium=0,
            unusual_strikes=[],
            sweeps=[],
            blocks=[],
            bullish_flow=0,
            bearish_flow=0,
            sentiment_score=0
        )
        
        # Calculate volume metrics
        for expiry in chain.get_expiry_dates():
            for strike in chain.get_strikes(expiry):
                # Analyze calls
                call = chain.get_option(strike, expiry, OptionType.CALL)
                if call:
                    analysis.call_volume += call.volume
                    analysis.call_premium += call.volume * call.mid_price * 100
                    
                    # Check for unusual activity
                    if self._is_unusual_volume(call):
                        analysis.unusual_strikes.append((strike, expiry, "High call volume"))
                    
                    # Detect sweeps/blocks
                    if self._is_sweep(call):
                        analysis.sweeps.append(self._create_sweep_info(call))
                    elif self._is_block(call):
                        analysis.blocks.append(self._create_block_info(call))
                
                # Analyze puts
                put = chain.get_option(strike, expiry, OptionType.PUT)
                if put:
                    analysis.put_volume += put.volume
                    analysis.put_premium += put.volume * put.mid_price * 100
                    
                    # Check for unusual activity
                    if self._is_unusual_volume(put):
                        analysis.unusual_strikes.append((strike, expiry, "High put volume"))
        
        # Calculate ratios and flows
        analysis.total_volume = analysis.call_volume + analysis.put_volume
        analysis.volume_ratio = analysis.put_volume / analysis.call_volume if analysis.call_volume > 0 else 0
        analysis.net_premium = analysis.call_premium - analysis.put_premium
        
        # Calculate sentiment
        analysis.bullish_flow = analysis.call_premium
        analysis.bearish_flow = analysis.put_premium
        
        if analysis.call_premium + analysis.put_premium > 0:
            analysis.sentiment_score = 100 * (analysis.call_premium - analysis.put_premium) / (analysis.call_premium + analysis.put_premium)
        
        # Store in history
        self.volume_history[chain.underlying].append(analysis)
        
        return analysis
    
    def calculate_gamma_exposure(self, chain: OptionChain) -> GammaExposure:
        """
        Calculate gamma exposure across strikes
        
        Args:
            chain: Option chain
            
        Returns:
            GammaExposure analysis
        """
        strikes_set = set()
        for expiry in chain.get_expiry_dates():
            strikes_set.update(chain.get_strikes(expiry))
        
        strikes = sorted(strikes_set)
        
        call_gamma = []
        put_gamma = []
        net_gamma = []
        
        total_gamma = 0
        max_gamma = 0
        max_gamma_strike = chain.spot_price
        
        for strike in strikes:
            strike_call_gamma = 0
            strike_put_gamma = 0
            
            for expiry in chain.get_expiry_dates():
                # Sum gamma across expiries
                call = chain.get_option(strike, expiry, OptionType.CALL)
                if call and call.gamma:
                    strike_call_gamma += call.gamma * call.open_interest * 100
                
                put = chain.get_option(strike, expiry, OptionType.PUT)
                if put and put.gamma:
                    strike_put_gamma += put.gamma * put.open_interest * 100
            
            call_gamma.append(strike_call_gamma)
            put_gamma.append(strike_put_gamma)
            
            # Net gamma (market maker perspective)
            strike_net_gamma = strike_call_gamma - strike_put_gamma
            net_gamma.append(strike_net_gamma)
            
            total_gamma += abs(strike_net_gamma)
            
            if abs(strike_net_gamma) > max_gamma:
                max_gamma = abs(strike_net_gamma)
                max_gamma_strike = strike
        
        # Find zero gamma level
        zero_gamma_level = self._find_zero_gamma_level(strikes, net_gamma)
        
        # Find flip point
        flip_point = self._find_gamma_flip_point(strikes, net_gamma)
        
        # Calculate dealer gamma
        dealer_gamma = -sum(net_gamma)  # Opposite of customer gamma
        
        # Calculate imbalance
        gamma_imbalance = sum(call_gamma) - sum(put_gamma)
        
        exposure = GammaExposure(
            timestamp=datetime.now(),
            spot_price=chain.spot_price,
            strikes=strikes,
            call_gamma=call_gamma,
            put_gamma=put_gamma,
            net_gamma=net_gamma,
            zero_gamma_level=zero_gamma_level,
            max_gamma_strike=max_gamma_strike,
            flip_point=flip_point,
            total_gamma_exposure=total_gamma,
            dealer_gamma=dealer_gamma,
            gamma_imbalance=gamma_imbalance
        )
        
        # Store in history
        self.gamma_history[chain.underlying].append(exposure)
        
        return exposure
    
    def find_pin_risk(self, chain: OptionChain, days_to_expiry: int = PIN_RISK_DTE) -> List[Tuple[float, float]]:
        """
        Find strikes with pin risk
        
        Args:
            chain: Option chain
            days_to_expiry: Maximum DTE to consider
            
        Returns:
            List of (strike, pin_risk_score) tuples
        """
        pin_risks = []
        
        for expiry in chain.get_expiry_dates():
            dte = (expiry - datetime.now()).days
            
            if dte <= days_to_expiry:
                strikes = chain.get_strikes(expiry)
                
                for strike in strikes:
                    # Calculate open interest concentration
                    call = chain.get_option(strike, expiry, OptionType.CALL)
                    put = chain.get_option(strike, expiry, OptionType.PUT)
                    
                    total_oi = 0
                    if call:
                        total_oi += call.open_interest
                    if put:
                        total_oi += put.open_interest
                    
                    # Check if near spot
                    if abs(strike - chain.spot_price) <= PIN_RISK_RANGE:
                        # Calculate pin risk score
                        distance = abs(strike - chain.spot_price)
                        time_factor = 1.0 / (dte + 1)  # Higher score closer to expiry
                        oi_factor = total_oi / 10000  # Normalize by 10k OI
                        
                        pin_score = oi_factor * time_factor * (1 - distance/PIN_RISK_RANGE)
                        
                        if pin_score > 0.1:  # Threshold
                            pin_risks.append((strike, pin_score))
        
        # Sort by pin risk score
        pin_risks.sort(key=lambda x: x[1], reverse=True)
        
        return pin_risks
    
    # ==========================================================================
    # PUBLIC METHODS - UTILITIES
    # ==========================================================================
    
    def get_nearest_expiry(self, chain: OptionChain, target_dte: int) -> Optional[datetime]:
        """Get expiry closest to target DTE"""
        expiries = chain.get_expiry_dates()
        if not expiries:
            return None
        
        # Find closest
        best_expiry = None
        min_diff = float('inf')
        
        for expiry in expiries:
            dte = (expiry - datetime.now()).days
            diff = abs(dte - target_dte)
            
            if diff < min_diff:
                min_diff = diff
                best_expiry = expiry
        
        return best_expiry
    
    def get_atm_strike(self, chain: OptionChain, expiry: datetime) -> float:
        """Get ATM strike for expiry"""
        strikes = chain.get_strikes(expiry)
        if not strikes:
            return chain.spot_price
        
        # Find closest to spot
        atm_strike = min(strikes, key=lambda s: abs(s - chain.spot_price))
        return atm_strike
    
    def get_chain_summary(self, chain: OptionChain) -> Dict[str, Any]:
        """Get chain summary statistics"""
        return {
            'underlying': chain.underlying,
            'spot_price': chain.spot_price,
            'num_expiries': len(chain.get_expiry_dates()),
            'total_strikes': len(set().union(*[chain.get_strikes(e) for e in chain.get_expiry_dates()])),
            'total_volume': chain.total_call_volume + chain.total_put_volume,
            'total_oi': chain.total_call_oi + chain.total_put_oi,
            'put_call_ratio': chain.put_call_ratio,
            'net_delta': chain.net_delta,
            'total_gamma': chain.total_gamma,
            'total_vega': chain.total_vega,
            'total_theta': chain.total_theta
        }
    
    # ==========================================================================
    # PRIVATE METHODS - CHAIN BUILDING
    # ==========================================================================
    
    def _create_option_data(self, data: Dict, spot_price: float) -> Optional[OptionData]:
        """Create OptionData from raw data"""
        try:
            option = OptionData(
                contract=None,  # Would create actual contract in production
                symbol=data['symbol'],
                underlying=data.get('underlying', ''),
                strike=data['strike'],
                expiry=data['expiry'],
                option_type=OptionType[data['type']],
                bid=data.get('bid', 0),
                ask=data.get('ask', 0),
                last=data.get('last', 0),
                volume=data.get('volume', 0),
                open_interest=data.get('open_interest', 0)
            )
            
            option.update_moneyness(spot_price)
            
            return option
            
        except Exception as e:
            self.logger.debug(f"Error creating option data: {e}")
            return None
    
    def _update_option_data(self, option: OptionData, update: Dict):
        """Update existing option data"""
        if 'bid' in update:
            option.bid = update['bid']
        if 'ask' in update:
            option.ask = update['ask']
        if 'last' in update:
            option.last = update['last']
        if 'volume' in update:
            option.volume = update['volume']
        if 'open_interest' in update:
            option.open_interest = update['open_interest']
        
        # Recalculate derived fields
        option.__post_init__()
    
    def _update_chain_statistics(self, chain: OptionChain, option: OptionData):
        """Update chain statistics with new option"""
        if option.option_type == OptionType.CALL:
            chain.total_call_volume += option.volume
            chain.total_call_oi += option.open_interest
        else:
            chain.total_put_volume += option.volume
            chain.total_put_oi += option.open_interest
    
    def _build_expiration_cycles(self, chain: OptionChain) -> List[ExpirationCycle]:
        """Build expiration cycle information"""
        cycles = []
        
        for expiry in chain.get_expiry_dates():
            dte = (expiry - datetime.now()).days
            
            # Determine expiry type
            if dte > 365:
                expiry_type = ExpiryType.LEAPS
            elif expiry.month in QUARTERLY_MONTHS and expiry.day > 15:
                expiry_type = ExpiryType.QUARTERLY
            elif expiry.weekday() == WEEKLY_EXPIRY_DAY:
                expiry_type = ExpiryType.WEEKLY
            else:
                expiry_type = ExpiryType.DAILY
            
            cycle = ExpirationCycle(
                expiry_date=expiry,
                expiry_type=expiry_type,
                days_to_expiry=dte,
                trading_days_to_expiry=self._calculate_trading_days(dte)
            )
            
            # Calculate statistics
            for strike in chain.get_strikes(expiry):
                call = chain.get_option(strike, expiry, OptionType.CALL)
                if call:
                    cycle.total_volume += call.volume
                    cycle.total_oi += call.open_interest
                    cycle.num_strikes += 1
                
                put = chain.get_option(strike, expiry, OptionType.PUT)
                if put:
                    cycle.total_volume += put.volume
                    cycle.total_oi += put.open_interest
            
            cycles.append(cycle)
        
        return cycles
    
    def _calculate_trading_days(self, calendar_days: int) -> int:
        """Calculate trading days from calendar days"""
        # Simplified calculation
        return int(calendar_days * 5 / 7)
    
    def _calculate_chain_greeks(self, chain: OptionChain):
        """Calculate Greeks for all options in chain"""
        if not self.pricer:
            return
        
        for expiry in chain.get_expiry_dates():
            for strike in chain.get_strikes(expiry):
                # Calculate for calls
                call = chain.get_option(strike, expiry, OptionType.CALL)
                if call:
                    self._calculate_option_greeks(call, chain.spot_price)
                
                # Calculate for puts
                put = chain.get_option(strike, expiry, OptionType.PUT)
                if put:
                    self._calculate_option_greeks(put, chain.spot_price)
    
    def _calculate_option_greeks(self, option: OptionData, spot_price: float):
        """Calculate Greeks for single option"""
        # This would use actual pricer in production
        # For now, use simplified estimates
        
        moneyness = option.moneyness
        dte = (option.expiry - datetime.now()).days / 365.0
        
        if option.option_type == OptionType.CALL:
            # Simplified delta
            if moneyness > 1.1:
                option.delta = 0.9
            elif moneyness < 0.9:
                option.delta = 0.1
            else:
                option.delta = 0.5 + 0.4 * (moneyness - 1.0)
        else:
            # Put delta
            if moneyness < 0.9:
                option.delta = -0.9
            elif moneyness > 1.1:
                option.delta = -0.1
            else:
                option.delta = -0.5 + 0.4 * (moneyness - 1.0)
        
        # Simplified gamma (highest ATM)
        atm_distance = abs(moneyness - 1.0)
        option.gamma = 0.05 * np.exp(-10 * atm_distance) / np.sqrt(max(dte, 0.01))
        
        # Simplified vega
        option.vega = spot_price * 0.02 * np.sqrt(dte) * np.exp(-5 * atm_distance)
        
        # Simplified theta
        option.theta = -option.mid_price / max(dte * 252, 1)
    
    def _calculate_chain_aggregates(self, chain: OptionChain):
        """Calculate aggregate Greeks and statistics"""
        chain.net_delta = 0
        chain.total_gamma = 0
        chain.total_vega = 0
        chain.total_theta = 0
        
        for expiry in chain.get_expiry_dates():
            for strike in chain.get_strikes(expiry):
                # Add call Greeks
                call = chain.get_option(strike, expiry, OptionType.CALL)
                if call and call.delta:
                    chain.net_delta += call.delta * call.open_interest * 100
                    chain.total_gamma += call.gamma * call.open_interest * 100 if call.gamma else 0
                    chain.total_vega += call.vega * call.open_interest * 100 if call.vega else 0
                    chain.total_theta += call.theta * call.open_interest * 100 if call.theta else 0
                
                # Add put Greeks
                put = chain.get_option(strike, expiry, OptionType.PUT)
                if put and put.delta:
                    chain.net_delta += put.delta * put.open_interest * 100
                    chain.total_gamma += put.gamma * put.open_interest * 100 if put.gamma else 0
                    chain.total_vega += put.vega * put.open_interest * 100 if put.vega else 0
                    chain.total_theta += put.theta * put.open_interest * 100 if put.theta else 0
        
        # Calculate put-call ratio
        if chain.total_call_volume > 0:
            chain.put_call_ratio = chain.total_put_volume / chain.total_call_volume
        else:
            chain.put_call_ratio = 0
    
    def _create_empty_chain(self, underlying: str, spot_price: float) -> OptionChain:
        """Create empty chain when no data available"""
        return OptionChain(
            underlying=underlying,
            spot_price=spot_price,
            timestamp=datetime.now(),
            calls=defaultdict(dict),
            puts=defaultdict(dict),
            expirations=[]
        )
    
    # ==========================================================================
    # PRIVATE METHODS - STRIKE SELECTION
    # ==========================================================================
    
    def _select_atm_strikes(self, chain: OptionChain, strikes: List[float],
                           num_strikes: int) -> List[float]:
        """Select ATM strikes"""
        # Find ATM strike
        atm_strike = min(strikes, key=lambda s: abs(s - chain.spot_price))
        atm_idx = strikes.index(atm_strike)
        
        # Select surrounding strikes
        half = num_strikes // 2
        start_idx = max(0, atm_idx - half)
        end_idx = min(len(strikes), start_idx + num_strikes)
        
        return strikes[start_idx:end_idx]
    
    def _select_otm_strikes(self, chain: OptionChain, strikes: List[float],
                           num_strikes: int) -> List[float]:
        """Select OTM strikes"""
        otm_calls = [s for s in strikes if s > chain.spot_price]
        otm_puts = [s for s in strikes if s < chain.spot_price]
        
        selected = []
        
        # Get half from each side
        half = num_strikes // 2
        selected.extend(otm_puts[-half:] if otm_puts else [])
        selected.extend(otm_calls[:half] if otm_calls else [])
        
        return sorted(selected)
    
    def _select_itm_strikes(self, chain: OptionChain, strikes: List[float],
                           num_strikes: int) -> List[float]:
        """Select ITM strikes"""
        itm_calls = [s for s in strikes if s < chain.spot_price]
        itm_puts = [s for s in strikes if s > chain.spot_price]
        
        selected = []
        
        # Get half from each side
        half = num_strikes // 2
        selected.extend(itm_calls[-half:] if itm_calls else [])
        selected.extend(itm_puts[:half] if itm_puts else [])
        
        return sorted(selected)
    
    def _select_delta_strikes(self, chain: OptionChain, expiry: datetime,
                             target_delta: float) -> List[float]:
        """Select strikes by delta"""
        selected = []
        
        # Find call with target delta
        for strike in chain.get_strikes(expiry):
            call = chain.get_option(strike, expiry, OptionType.CALL)
            if call and call.delta:
                if abs(call.delta - target_delta) < 0.05:
                    selected.append(strike)
                    break
        
        # Find put with target delta
        for strike in chain.get_strikes(expiry):
            put = chain.get_option(strike, expiry, OptionType.PUT)
            if put and put.delta:
                if abs(abs(put.delta) - target_delta) < 0.05:
                    selected.append(strike)
                    break
        
        return sorted(selected)
    
    def _select_volume_weighted_strikes(self, chain: OptionChain, expiry: datetime,
                                       num_strikes: int) -> List[float]:
        """Select strikes weighted by volume"""
        strike_volumes = []
        
        for strike in chain.get_strikes(expiry):
            total_volume = 0
            
            call = chain.get_option(strike, expiry, OptionType.CALL)
            if call:
                total_volume += call.volume
            
            put = chain.get_option(strike, expiry, OptionType.PUT)
            if put:
                total_volume += put.volume
            
            if total_volume > 0:
                strike_volumes.append((strike, total_volume))
        
        # Sort by volume
        strike_volumes.sort(key=lambda x: x[1], reverse=True)
        
        # Return top strikes
        return [s for s, _ in strike_volumes[:num_strikes]]
    
    def _select_oi_weighted_strikes(self, chain: OptionChain, expiry: datetime,
                                   num_strikes: int) -> List[float]:
        """Select strikes weighted by open interest"""
        strike_oi = []
        
        for strike in chain.get_strikes(expiry):
            total_oi = 0
            
            call = chain.get_option(strike, expiry, OptionType.CALL)
            if call:
                total_oi += call.open_interest
            
            put = chain.get_option(strike, expiry, OptionType.PUT)
            if put:
                total_oi += put.open_interest
            
            if total_oi > 0:
                strike_oi.append((strike, total_oi))
        
        # Sort by OI
        strike_oi.sort(key=lambda x: x[1], reverse=True)
        
        # Return top strikes
        return [s for s, _ in strike_oi[:num_strikes]]
    
    def _select_liquid_strikes(self, chain: OptionChain, expiry: datetime,
                              num_strikes: int) -> List[float]:
        """Select most liquid strikes"""
        strike_liquidity = []
        
        for strike in chain.get_strikes(expiry):
            total_score = 0
            
            call = chain.get_option(strike, expiry, OptionType.CALL)
            if call:
                total_score += call.liquidity_score
            
            put = chain.get_option(strike, expiry, OptionType.PUT)
            if put:
                total_score += put.liquidity_score
            
            if total_score > 0:
                strike_liquidity.append((strike, total_score))
        
        # Sort by liquidity
        strike_liquidity.sort(key=lambda x: x[1], reverse=True)
        
        # Return top strikes
        return [s for s, _ in strike_liquidity[:num_strikes]]
    
    def _calculate_strike_scores(self, chain: OptionChain, expiry: datetime,
                                strikes: List[float], method: StrikeSelectionMethod) -> Dict[float, float]:
        """Calculate selection scores for strikes"""
        scores = {}
        
        for strike in strikes:
            score = 0
            
            # Get options
            call = chain.get_option(strike, expiry, OptionType.CALL)
            put = chain.get_option(strike, expiry, OptionType.PUT)
            
            # Score based on method
            if method == StrikeSelectionMethod.VOLUME_WEIGHTED:
                if call:
                    score += call.volume
                if put:
                    score += put.volume
            elif method == StrikeSelectionMethod.OI_WEIGHTED:
                if call:
                    score += call.open_interest
                if put:
                    score += put.open_interest
            elif method == StrikeSelectionMethod.LIQUIDITY_BASED:
                if call:
                    score += call.liquidity_score
                if put:
                    score += put.liquidity_score
            else:
                # Default scoring
                score = 1.0 / (1.0 + abs(strike - chain.spot_price))
            
            scores[strike] = score
        
        return scores
    
    # ==========================================================================
    # PRIVATE METHODS - STRATEGY RECOMMENDATIONS
    # ==========================================================================
    
    def _recommend_iron_condor_strikes(self, chain: OptionChain,
                                       expiry: Optional[datetime]) -> Dict[str, Any]:
        """Recommend strikes for iron condor"""
        if not expiry:
            expiry = self.get_nearest_expiry(chain, 30)  # 30 DTE target
        
        # Select by delta
        call_strikes = self._select_delta_strikes(chain, expiry, IRON_CONDOR_DELTA)
        put_strikes = self._select_delta_strikes(chain, expiry, IRON_CONDOR_DELTA)
        
        recommendations = {
            'strategy': 'iron_condor',
            'expiry': expiry,
            'short_put': min(put_strikes) if put_strikes else None,
            'long_put': None,
            'short_call': max(call_strikes) if call_strikes else None,
            'long_call': None
        }
        
        # Find protective strikes
        strikes = chain.get_strikes(expiry)
        if recommendations['short_put'] and strikes:
            idx = bisect.bisect_left(strikes, recommendations['short_put'])
            if idx > 0:
                recommendations['long_put'] = strikes[idx - 1]
        
        if recommendations['short_call'] and strikes:
            idx = bisect.bisect_right(strikes, recommendations['short_call'])
            if idx < len(strikes):
                recommendations['long_call'] = strikes[idx]
        
        return recommendations
    
    def _recommend_butterfly_strikes(self, chain: OptionChain,
                                    expiry: Optional[datetime]) -> Dict[str, Any]:
        """Recommend strikes for butterfly"""
        if not expiry:
            expiry = self.get_nearest_expiry(chain, 30)
        
        atm_strike = self.get_atm_strike(chain, expiry)
        strikes = chain.get_strikes(expiry)
        
        # Find wings
        lower_wing = None
        upper_wing = None
        
        for strike in strikes:
            if strike < atm_strike - BUTTERFLY_WIDTH:
                lower_wing = strike
            elif strike > atm_strike + BUTTERFLY_WIDTH and not upper_wing:
                upper_wing = strike
                break
        
        return {
            'strategy': 'butterfly',
            'expiry': expiry,
            'lower_wing': lower_wing,
            'body': atm_strike,
            'upper_wing': upper_wing
        }
    
    def _recommend_calendar_strikes(self, chain: OptionChain) -> Dict[str, Any]:
        """Recommend strikes for calendar spread"""
        # Find expiries with good IV skew
        expiries = chain.get_expiry_dates()
        
        if len(expiries) < 2:
            return {'strategy': 'calendar', 'error': 'Insufficient expiries'}
        
        near_expiry = expiries[0]
        far_expiry = expiries[1]
        
        # Find ATM strike
        atm_strike = self.get_atm_strike(chain, near_expiry)
        
        return {
            'strategy': 'calendar',
            'strike': atm_strike,
            'near_expiry': near_expiry,
            'far_expiry': far_expiry
        }
    
    def _recommend_straddle_strikes(self, chain: OptionChain,
                                   expiry: Optional[datetime]) -> Dict[str, Any]:
        """Recommend strikes for straddle"""
        if not expiry:
            expiry = self.get_nearest_expiry(chain, 7)  # Weekly
        
        atm_strike = self.get_atm_strike(chain, expiry)
        
        return {
            'strategy': 'straddle',
            'expiry': expiry,
            'strike': atm_strike
        }
    
    def _recommend_strangle_strikes(self, chain: OptionChain,
                                   expiry: Optional[datetime]) -> Dict[str, Any]:
        """Recommend strikes for strangle"""
        if not expiry:
            expiry = self.get_nearest_expiry(chain, 7)
        
        # Select OTM strikes
        otm_strikes = self._select_otm_strikes(chain, chain.get_strikes(expiry), 2)
        
        put_strike = min(otm_strikes) if otm_strikes else None
        call_strike = max(otm_strikes) if otm_strikes else None
        
        return {
            'strategy': 'strangle',
            'expiry': expiry,
            'put_strike': put_strike,
            'call_strike': call_strike
        }
    
    def _recommend_vertical_strikes(self, chain: OptionChain,
                                   expiry: Optional[datetime]) -> Dict[str, Any]:
        """Recommend strikes for vertical spread"""
        if not expiry:
            expiry = self.get_nearest_expiry(chain, 30)
        
        atm_strike = self.get_atm_strike(chain, expiry)
        strikes = chain.get_strikes(expiry)
        
        # Find adjacent strikes
        idx = bisect.bisect_left(strikes, atm_strike)
        
        long_strike = strikes[idx] if idx < len(strikes) else atm_strike
        short_strike = strikes[idx + 1] if idx + 1 < len(strikes) else None
        
        return {
            'strategy': 'vertical',
            'expiry': expiry,
            'long_strike': long_strike,
            'short_strike': short_strike
        }
    
    # ==========================================================================
    # PRIVATE METHODS - FILTERING
    # ==========================================================================
    
    def _passes_filters(self, option: OptionData, filters: Dict[ChainFilterType, Any]) -> bool:
        """Check if option passes all filters"""
        for filter_type, filter_value in filters.items():
            if filter_type == ChainFilterType.MONEYNESS:
                min_m, max_m = filter_value
                if not (min_m <= option.moneyness <= max_m):
                    return False
            
            elif filter_type == ChainFilterType.VOLUME:
                if option.volume < filter_value:
                    return False
            
            elif filter_type == ChainFilterType.OPEN_INTEREST:
                if option.open_interest < filter_value:
                    return False
            
            elif filter_type == ChainFilterType.IMPLIED_VOL:
                if option.implied_vol:
                    min_iv, max_iv = filter_value
                    if not (min_iv <= option.implied_vol <= max_iv):
                        return False
            
            elif filter_type == ChainFilterType.SPREAD:
                if option.spread_pct > filter_value:
                    return False
            
            elif filter_type == ChainFilterType.GREEKS:
                # Filter by specific Greek
                greek_name, min_val, max_val = filter_value
                greek_value = getattr(option, greek_name, None)
                if greek_value is not None:
                    if not (min_val <= greek_value <= max_val):
                        return False
        
        return True
    
    # ==========================================================================
    # PRIVATE METHODS - VOLUME ANALYSIS
    # ==========================================================================
    
    def _is_unusual_volume(self, option: OptionData) -> bool:
        """Check if option has unusual volume"""
        if option.volume_oi_ratio > UNUSUAL_VOLUME_RATIO:
            return True
        
        # Check against historical average
        # This would use actual historical data in production
        avg_volume = 100  # Placeholder
        if option.volume > avg_volume * UNUSUAL_VOLUME_RATIO:
            return True
        
        return False
    
    def _is_sweep(self, option: OptionData) -> bool:
        """Detect sweep order"""
        # Simplified detection
        if option.volume > 100 and option.spread_pct < 0.02:
            if option.volume > option.open_interest * 0.10:
                return True
        return False
    
    def _is_block(self, option: OptionData) -> bool:
        """Detect block trade"""
        # Simplified detection
        if option.volume >= 500:  # Large single trade
            return True
        return False
    
    def _create_sweep_info(self, option: OptionData) -> Dict[str, Any]:
        """Create sweep information"""
        return {
            'timestamp': datetime.now(),
            'symbol': option.symbol,
            'strike': option.strike,
            'type': option.option_type.value,
            'volume': option.volume,
            'price': option.mid_price,
            'premium': option.volume * option.mid_price * 100
        }
    
    def _create_block_info(self, option: OptionData) -> Dict[str, Any]:
        """Create block trade information"""
        return {
            'timestamp': datetime.now(),
            'symbol': option.symbol,
            'strike': option.strike,
            'type': option.option_type.value,
            'volume': option.volume,
            'price': option.mid_price,
            'premium': option.volume * option.mid_price * 100
        }
    
    # ==========================================================================
    # PRIVATE METHODS - GAMMA ANALYSIS
    # ==========================================================================
    
    def _find_zero_gamma_level(self, strikes: List[float], net_gamma: List[float]) -> float:
        """Find strike where net gamma crosses zero"""
        if not strikes or not net_gamma:
            return 0
        
        # Find zero crossing
        for i in range(len(net_gamma) - 1):
            if net_gamma[i] * net_gamma[i + 1] < 0:  # Sign change
                # Linear interpolation
                strike1, strike2 = strikes[i], strikes[i + 1]
                gamma1, gamma2 = net_gamma[i], net_gamma[i + 1]
                
                # Find zero point
                zero_strike = strike1 - gamma1 * (strike2 - strike1) / (gamma2 - gamma1)
                return zero_strike
        
        # No zero crossing found
        return strikes[0] if abs(net_gamma[0]) < abs(net_gamma[-1]) else strikes[-1]
    
    def _find_gamma_flip_point(self, strikes: List[float], net_gamma: List[float]) -> Optional[float]:
        """Find strike where gamma flips from positive to negative"""
        for i in range(len(net_gamma) - 1):
            if net_gamma[i] > 0 and net_gamma[i + 1] < 0:
                return (strikes[i] + strikes[i + 1]) / 2
        return None

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_chain_manager() -> OptionsChainManager:
    """Factory function to create chain manager"""
    return OptionsChainManager()

def generate_test_chain(underlying: str = "SPY", spot: float = 585.0) -> List[Dict]:
    """Generate test option chain data"""
    chain_data = []
    
    # Generate options for multiple expiries
    expiries = [
        datetime.now() + timedelta(days=d)
        for d in [1, 7, 14, 21, 30, 45, 60, 90]
    ]
    
    for expiry in expiries:
        # Generate strikes
        strikes = np.arange(spot * 0.80, spot * 1.20, 5)
        
        for strike in strikes:
            for option_type in ['CALL', 'PUT']:
                # Generate realistic data
                moneyness = spot / strike
                
                # Volume and OI based on moneyness
                if 0.95 <= moneyness <= 1.05:  # ATM
                    volume = np.random.randint(500, 2000)
                    oi = np.random.randint(5000, 20000)
                else:  # OTM/ITM
                    volume = np.random.randint(10, 500)
                    oi = np.random.randint(100, 5000)
                
                # Pricing
                if option_type == 'CALL':
                    intrinsic = max(spot - strike, 0)
                else:
                    intrinsic = max(strike - spot, 0)
                
                time_value = np.random.uniform(0.5, 5.0)
                price = intrinsic + time_value
                
                chain_data.append({
                    'symbol': f"{underlying}{expiry.strftime('%y%m%d')}{option_type[0]}{int(strike*1000):08d}",
                    'underlying': underlying,
                    'strike': strike,
                    'expiry': expiry,
                    'type': option_type,
                    'bid': price * 0.98,
                    'ask': price * 1.02,
                    'last': price,
                    'volume': volume,
                    'open_interest': oi
                })
    
    return chain_data

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("SPYDER N03 - OPTIONS CHAIN MANAGER TEST")
    print("=" * 80)
    
    # Create manager
    manager = create_chain_manager()
    
    # Generate test data
    underlying = "SPY"
    spot_price = 585.00
    chain_data = generate_test_chain(underlying, spot_price)
    
    print(f"\n📊 Test Parameters:")
    print(f"  Underlying: {underlying}")
    print(f"  Spot Price: ${spot_price:.2f}")
    print(f"  Options Generated: {len(chain_data)}")
    
    # Build chain
    print("\n🔨 Building Option Chain...")
    chain = manager.build_chain(underlying, spot_price, chain_data)
    
    # Display summary
    summary = manager.get_chain_summary(chain)
    print(f"\n📈 CHAIN SUMMARY:")
    print("-" * 50)
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")
    
    # Test strike selection methods
    print(f"\n🎯 STRIKE SELECTION TESTS:")
    print("-" * 50)
    
    # ATM strikes
    atm_selection = manager.select_strikes(chain, StrikeSelectionMethod.ATM, num_strikes=5)
    print(f"  ATM Strikes: {atm_selection.strikes}")
    
    # Delta-based
    delta_selection = manager.select_strikes(chain, StrikeSelectionMethod.DELTA_BASED, delta=0.30)
    print(f"  30-Delta Strikes: {delta_selection.strikes}")
    
    # Volume-weighted
    volume_selection = manager.select_strikes(chain, StrikeSelectionMethod.VOLUME_WEIGHTED, num_strikes=5)
    print(f"  Top Volume Strikes: {volume_selection.strikes}")
    
    # Strategy recommendations
    print(f"\n📋 STRATEGY RECOMMENDATIONS:")
    print("-" * 50)
    
    # Iron Condor
    ic_rec = manager.recommend_strikes_for_strategy(chain, 'iron_condor')
    print(f"  Iron Condor:")
    print(f"    Short Put: {ic_rec.get('short_put')}")
    print(f"    Long Put: {ic_rec.get('long_put')}")
    print(f"    Short Call: {ic_rec.get('short_call')}")
    print(f"    Long Call: {ic_rec.get('long_call')}")
    
    # Butterfly
    bf_rec = manager.recommend_strikes_for_strategy(chain, 'butterfly')
    print(f"  Butterfly:")
    print(f"    Lower: {bf_rec.get('lower_wing')}")
    print(f"    Body: {bf_rec.get('body')}")
    print(f"    Upper: {bf_rec.get('upper_wing')}")
    
    # Volume analysis
    print(f"\n📊 VOLUME ANALYSIS:")
    print("-" * 50)
    volume_analysis = manager.analyze_volume(chain)
    print(f"  Call Volume: {volume_analysis.call_volume:,}")
    print(f"  Put Volume: {volume_analysis.put_volume:,}")
    print(f"  Put/Call Ratio: {volume_analysis.volume_ratio:.2f}")
    print(f"  Net Premium: ${volume_analysis.net_premium:,.0f}")
    print(f"  Sentiment Score: {volume_analysis.sentiment_score:.1f}")
    
    if volume_analysis.unusual_strikes:
        print(f"  Unusual Activity: {len(volume_analysis.unusual_strikes)} strikes")
    
    # Gamma exposure
    print(f"\n⚡ GAMMA EXPOSURE:")
    print("-" * 50)
    gamma_exposure = manager.calculate_gamma_exposure(chain)
    print(f"  Max Gamma Strike: ${gamma_exposure.max_gamma_strike:.2f}")
    print(f"  Zero Gamma Level: ${gamma_exposure.zero_gamma_level:.2f}")
    print(f"  Total Gamma: {gamma_exposure.total_gamma_exposure:.0f}")
    print(f"  Dealer Gamma: {gamma_exposure.dealer_gamma:.0f}")
    
    # Pin risk
    print(f"\n📌 PIN RISK ANALYSIS:")
    print("-" * 50)
    pin_risks = manager.find_pin_risk(chain, days_to_expiry=2)
    if pin_risks:
        print(f"  Top Pin Risk Strikes:")
        for strike, score in pin_risks[:3]:
            print(f"    ${strike:.2f}: {score:.2f}")
    else:
        print(f"  No significant pin risk detected")
    
    # Chain filtering
    print(f"\n🔍 CHAIN FILTERING:")
    print("-" * 50)
    
    filters = {
        ChainFilterType.MONEYNESS: (0.95, 1.05),  # Near ATM
        ChainFilterType.VOLUME: 100,  # Min volume
        ChainFilterType.OPEN_INTEREST: 1000  # Min OI
    }
    
    filtered_chain = manager.filter_chain(chain, filters)
    filtered_summary = manager.get_chain_summary(filtered_chain)
    print(f"  Filtered to ATM + Liquid:")
    print(f"    Strikes: {filtered_summary['total_strikes']}")
    print(f"    Volume: {filtered_summary['total_volume']:,}")
    
    print("\n✅ Options Chain Manager test completed successfully!")