#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC07_OPRAFeed.py
Purpose: OPRA real-time options data feed with ib_async integration
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-21 Time: 22:00:00

⚠️ DEPRECATION WARNING ⚠️
    This module is DEPRECATED and should be replaced with Polygon.io integration.

    Migration Status:
    - ❌ Uses deprecated ib_async for OPRA data (line 60: from ib_async import *)
    - ❌ IBKR no longer primary data source for Spyder
    - 🎯 Polygon.io provides direct OPRA feed access without broker

    For New Development:
    - Use SpyderC25_PolygonDataHandler for options data
    - Polygon WebSocket: wss://socket.polygon.io/options
    - Channels: T.* (trades), Q.* (quotes), AM.* (aggregates)
    - No IB Gateway required, cleaner architecture

    Current System:
    - ✅ Polygon.io: Real-time options quotes and trades
    - ✅ Tradier: Options chain data and execution
    - ❌ IBKR: Deprecated (legacy only)

Module Description:
    This module provides high-quality real-time options data feed from OPRA for SPY
    options trading using modern ib_async library for enhanced IB Gateway 10.37
    compatibility. It handles options quotes, trades, volume, open interest, and
    Greeks calculations from live market data with Level 2 options market data
    support, real-time options chain updates, and integration with the broader
    Spyder market data infrastructure for comprehensive options analytics.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import json
import asyncio
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any, Set, Callable, Union
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum, auto
import bisect
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ⚠️ DEPRECATED: ib_async wildcard import is legacy code
# This module should be replaced with SpyderC25_PolygonDataHandler
# Polygon provides direct OPRA feed without broker dependency
from ib_async import *
import pytz
from scipy import stats
from py_vollib.black_scholes import black_scholes
from py_vollib.black_scholes.greeks import delta, gamma, theta, vega, rho

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import TradingTimeUtils, MarketSession
from Spyder.SpyderU_Utilities.SpyderU07_Constants import TimeFrame
from Spyder.SpyderU_Utilities.SpyderU16_TechnicalAnalysis import ImpliedVolatilityCalculator
from Spyder.SpyderC_MarketData.SpyderC01_DataFeed import DataFeedManager
from Spyder.SpyderC_MarketData.SpyderC06_DataValidator import DataValidator

try:
    from Spyder.SpyderB_Broker.SpyderB01_SpyderClient import IBClient
except ImportError:
    IBClient = None

from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

# ==============================================================================
# CONSTANTS
# ==============================================================================
# OPRA Configuration
OPRA_EXCHANGE_CODES = {
    'A': 'AMEX',
    'B': 'BOX',
    'C': 'CBOE',
    'H': 'ISE_GEMINI',
    'I': 'ISE',
    'M': 'MIAX',
    'N': 'NYSE',
    'O': 'OPRA',
    'P': 'PHLX',
    'Q': 'NASDAQ',
    'T': 'BATS',
    'W': 'CBOE_BZX',
    'X': 'PHLX',
    'Z': 'BATS_BZX'
}

# Options Configuration
SPY_OPTION_SYMBOL = "SPY"
OPTION_MULTIPLIER = 100
MIN_OPTION_PRICE = 0.01
MAX_OPTION_PRICE = 1000.0
MIN_VOLUME = 1
DEFAULT_DTE_FILTER = [0, 1, 2, 3, 5, 7, 14, 21, 30, 45, 60, 90]

# Greeks Configuration
RISK_FREE_RATE = 0.05  # 5% default risk-free rate
MIN_IMPLIED_VOL = 0.01  # 1% minimum IV
MAX_IMPLIED_VOL = 5.0   # 500% maximum IV
GREEKS_UPDATE_INTERVAL = 1.0  # Update Greeks every second

# Data Quality
STALE_DATA_THRESHOLD = 30  # seconds
MAX_BID_ASK_SPREAD = 5.0  # Maximum spread ratio
MIN_TIME_TO_EXPIRY = 0.001  # Minimum time to expiry (hours)

# Performance
MAX_OPTION_CONTRACTS = 10000  # Maximum contracts to track
TICK_BUFFER_SIZE = 50000
QUOTE_BUFFER_SIZE = 20000
TRADE_BUFFER_SIZE = 10000

# ==============================================================================
# ENUMS
# ==============================================================================
class OptionType(Enum):
    """Option contract type."""
    CALL = "C"
    PUT = "P"

class QuoteType(Enum):
    """Quote type classification."""
    BID = "bid"
    ASK = "ask"
    TRADE = "trade"
    IMPLIED_BID = "implied_bid"
    IMPLIED_ASK = "implied_ask"

class DataQuality(Enum):
    """Data quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    STALE = "stale"
    INVALID = "invalid"

class FlowDirection(Enum):
    """Options flow direction."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OptionContract:
    """Option contract specification."""
    symbol: str
    expiration: date
    strike: float
    option_type: OptionType
    multiplier: int = OPTION_MULTIPLIER
    
    @property
    def contract_symbol(self) -> str:
        """Generate standard option symbol."""
        exp_str = self.expiration.strftime("%y%m%d")
        strike_str = f"{int(self.strike * 1000):08d}"
        return f"{self.symbol}{exp_str}{self.option_type.value}{strike_str}"
    
    @property
    def dte(self) -> int:
        """Days to expiration."""
        return (self.expiration - date.today()).days
    
    @property
    def tte(self) -> float:
        """Time to expiration in years."""
        days = max(self.dte, 0)
        return days / 365.25

@dataclass
class OptionQuote:
    """Option quote data with ib_async integration."""
    contract: OptionContract
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    last: float
    last_size: int
    volume: int
    open_interest: int
    timestamp: datetime
    exchange: str
    implied_vol: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None
    ib_library: str = "ib_async"  # Track which library is used
    
    @property
    def mid(self) -> float:
        """Calculate mid price."""
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        elif self.last > 0:
            return self.last
        return 0.0
    
    @property
    def spread(self) -> float:
        """Calculate bid-ask spread."""
        if self.bid > 0 and self.ask > 0:
            return self.ask - self.bid
        return 0.0
    
    @property
    def spread_pct(self) -> float:
        """Calculate spread percentage."""
        mid = self.mid
        if mid > 0 and self.spread > 0:
            return self.spread / mid
        return 0.0

@dataclass
class OptionTrade:
    """Option trade data with ib_async integration."""
    contract: OptionContract
    price: float
    size: int
    timestamp: datetime
    exchange: str
    conditions: List[str] = field(default_factory=list)
    ib_library: str = "ib_async"  # Track which library is used
    
    @property
    def notional_value(self) -> float:
        """Calculate notional value of trade."""
        return self.price * self.size * self.contract.multiplier

@dataclass
class OptionsChainSnapshot:
    """Complete options chain snapshot with ib_async integration."""
    underlying_symbol: str
    underlying_price: float
    expiration: date
    calls: Dict[float, OptionQuote]
    puts: Dict[float, OptionQuote]
    timestamp: datetime
    ib_library: str = "ib_async"  # Track which library is used
    
    @property
    def all_strikes(self) -> List[float]:
        """Get all strike prices."""
        strikes = set(self.calls.keys()) | set(self.puts.keys())
        return sorted(strikes)
    
    @property
    def atm_strike(self) -> float:
        """Get at-the-money strike."""
        strikes = self.all_strikes
        if not strikes:
            return 0.0
        return min(strikes, key=lambda x: abs(x - self.underlying_price))

@dataclass
class OptionsFlow:
    """Options flow analysis with ib_async integration."""
    symbol: str
    direction: FlowDirection
    volume: int
    premium: float
    avg_price: float
    trades: int
    call_volume: int
    put_volume: int
    call_premium: float
    put_premium: float
    timestamp: datetime
    ib_library: str = "ib_async"  # Track which library is used
    
    @property
    def call_put_ratio(self) -> float:
        """Calculate call/put volume ratio."""
        if self.put_volume > 0:
            return self.call_volume / self.put_volume
        return float('inf') if self.call_volume > 0 else 0.0

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class OPRADataFeed:
    """
    OPRA real-time options data feed manager with ib_async integration.
    
    This class provides comprehensive real-time options data from OPRA including
    quotes, trades, volume, open interest, and calculated Greeks using modern
    ib_async library for enhanced IB Gateway 10.37 compatibility. It manages
    multiple option chains, performs real-time Greeks calculations, and provides
    institutional flow analysis for options trading strategies.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        data_validator: Data validation instance
        ib_client: Interactive Brokers client with ib_async
        option_chains: Current option chain data
        active_contracts: Currently tracked option contracts
        quotes_cache: Real-time quotes cache
        trades_cache: Recent trades cache
        
    Example:
        >>> opra_feed = OPRADataFeed()
        >>> opra_feed.initialize()
        >>> opra_feed.start_feed()
        >>> chain = opra_feed.get_option_chain("SPY", date(2025, 7, 18))
        >>> flow = opra_feed.get_options_flow("SPY")
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize OPRA data feed with ib_async."""
        self.logger = SpyderLogger.get_logger("OPRADataFeed")
        self.error_handler = SpyderErrorHandler()
        self.data_validator = DataValidator()
        
        # Configuration
        self.config = config or {}
        self.dte_filter = self.config.get('dte_filter', DEFAULT_DTE_FILTER)
        self.max_contracts = self.config.get('max_contracts', MAX_OPTION_CONTRACTS)
        self.risk_free_rate = self.config.get('risk_free_rate', RISK_FREE_RATE)
        
        # Interactive Brokers client with ib_async
        self.ib_client: Optional[IBClient] = None
        
        # Data storage
        self.option_chains: Dict[str, Dict[date, OptionsChainSnapshot]] = defaultdict(dict)
        self.active_contracts: Dict[str, OptionContract] = {}
        self.quotes_cache: Dict[str, OptionQuote] = {}
        self.trades_cache: deque = deque(maxlen=TRADE_BUFFER_SIZE)
        self.tick_data: deque = deque(maxlen=TICK_BUFFER_SIZE)
        
        # Greeks calculation
        self.underlying_prices: Dict[str, float] = {}
        self.implied_vols: Dict[str, float] = {}
        self.greeks_cache: Dict[str, Dict] = {}
        
        # Flow analysis
        self.options_flow: Dict[str, OptionsFlow] = {}
        self.flow_history: deque = deque(maxlen=1000)
        
        # State management
        self.is_running = False
        self.last_update = None
        self.request_counter = 0
        
        # Threading
        self._lock = threading.RLock()
        self._feed_thread = None
        self._greeks_thread = None
        self._stop_event = threading.Event()
        
        # Event manager integration
        self.event_manager = get_event_manager()
        
        # Performance tracking
        self.stats = {
            'quotes_received': 0,
            'trades_received': 0,
            'greeks_calculated': 0,
            'errors': 0,
            'last_performance_check': time.time(),
            'ib_library': 'ib_async'
        }
        
        self.logger.info("OPRA data feed initialized with ib_async")

    # ==========================================================================
    # INITIALIZATION METHODS
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize the OPRA data feed with ib_async.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Initialize IB client connection with ib_async
            if not self._initialize_ib_client():
                self.logger.error("Failed to initialize IB client with ib_async")
                return False
            
            # Register event callbacks
            self._register_event_callbacks()
            
            # Initialize option chains for key expirations
            self._initialize_option_chains()
            
            # Setup Greeks calculation
            self._initialize_greeks_calculator()
            
            self.logger.info("OPRA data feed initialized successfully with ib_async")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'initialize',
                'class': 'OPRADataFeed'
            })
            return False
    
    def _initialize_ib_client(self) -> bool:
        """Initialize Interactive Brokers client for options data with ib_async."""
        try:
            # Get IB client from broker module
            from SpyderB_Broker.SpyderB01_SpyderClient import get_ib_client
            self.ib_client = get_ib_client()
            
            if not self.ib_client or not self.ib_client.is_connected():
                self.logger.warning("IB client not connected, using simulation mode with ib_async")
                return True  # Allow running in simulation mode
            
            # Register callbacks for options data
            self.ib_client.register_callback('tickPrice', self._on_tick_price)
            self.ib_client.register_callback('tickSize', self._on_tick_size)
            self.ib_client.register_callback('tickOptionComputation', self._on_option_computation)
            
            return True
            
        except Exception as e:
            self.logger.warning(f"IB client initialization failed: {e}")
            return True  # Continue in simulation mode
    
    def _register_event_callbacks(self) -> None:
        """Register event manager callbacks."""
        if self.event_manager:
            self.event_manager.subscribe(EventType.MARKET_DATA, self._on_market_data_event)
            self.event_manager.subscribe(EventType.OPTION_DATA, self._on_option_data_event)
    
    def _initialize_option_chains(self) -> None:
        """Initialize option chains for key symbols and expirations."""
        symbols = [SPY_OPTION_SYMBOL]
        
        for symbol in symbols:
            self.option_chains[symbol] = {}
            self.underlying_prices[symbol] = 0.0
            self.options_flow[symbol] = OptionsFlow(
                symbol=symbol,
                direction=FlowDirection.NEUTRAL,
                volume=0,
                premium=0.0,
                avg_price=0.0,
                trades=0,
                call_volume=0,
                put_volume=0,
                call_premium=0.0,
                put_premium=0.0,
                timestamp=datetime.now()
            )
    
    def _initialize_greeks_calculator(self) -> None:
        """Initialize Greeks calculation system."""
        self.greeks_cache.clear()
        self.implied_vols.clear()

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start_feed(self) -> None:
        """Start OPRA data feed with ib_async."""
        if self.is_running:
            self.logger.warning("OPRA feed already running")
            return
        
        try:
            self.is_running = True
            self._stop_event.clear()
            
            # Start data feed thread
            self._feed_thread = threading.Thread(
                target=self._feed_loop,
                name="OPRADataFeed",
                daemon=True
            )
            self._feed_thread.start()
            
            # Start Greeks calculation thread
            self._greeks_thread = threading.Thread(
                target=self._greeks_loop,
                name="OPRAGreeksCalculation",
                daemon=True
            )
            self._greeks_thread.start()
            
            # Request market data for key options
            self._request_options_data()
            
            self.logger.info("OPRA data feed started with ib_async")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'start_feed'
            })
            self.is_running = False
    
    def stop_feed(self) -> None:
        """Stop OPRA data feed."""
        if not self.is_running:
            return
        
        try:
            self.is_running = False
            self._stop_event.set()
            
            # Stop market data requests
            self._stop_market_data_requests()
            
            # Wait for threads to finish
            if self._feed_thread and self._feed_thread.is_alive():
                self._feed_thread.join(timeout=5.0)
            
            if self._greeks_thread and self._greeks_thread.is_alive():
                self._greeks_thread.join(timeout=5.0)
            
            self.logger.info("OPRA data feed stopped")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'stop_feed'
            })

    # ==========================================================================
    # DATA REQUEST METHODS WITH ib_async
    # ==========================================================================
    def _request_options_data(self) -> None:
        """Request market data for option contracts via ib_async."""
        if not self.ib_client:
            return
        
        try:
            # Get option chains for key expirations
            for symbol in [SPY_OPTION_SYMBOL]:
                expirations = self._get_target_expirations(symbol)
                
                for expiration in expirations:
                    self._request_option_chain(symbol, expiration)
                    
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_request_options_data'
            })
    
    def _request_option_chain(self, symbol: str, expiration: date) -> None:
        """Request option chain for specific expiration via ib_async."""
        try:
            # Get underlying price first
            underlying_price = self._get_underlying_price(symbol)
            if underlying_price <= 0:
                return
            
            # Calculate strike range
            strikes = self._calculate_strike_range(underlying_price, expiration)
            
            # Request data for calls and puts
            for strike in strikes:
                for option_type in [OptionType.CALL, OptionType.PUT]:
                    contract = OptionContract(
                        symbol=symbol,
                        expiration=expiration,
                        strike=strike,
                        option_type=option_type
                    )
                    
                    self._request_option_quote(contract)
                    
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_request_option_chain',
                'symbol': symbol,
                'expiration': str(expiration)
            })
    
    def _request_option_quote(self, contract: OptionContract) -> None:
        """Request real-time quote for option contract via ib_async."""
        if not self.ib_client:
            return
        
        try:
            # Create IB contract using ib_async
            ib_contract = Option(
                symbol=contract.symbol,
                lastTradeDateOrContractMonth=contract.expiration.strftime("%Y%m%d"),
                strike=contract.strike,
                right=contract.option_type.value,
                exchange="SMART"
            )
            
            # Request market data
            request_id = self._get_next_request_id()
            self.active_contracts[str(request_id)] = contract
            
            # Request real-time data via ib_async
            self.ib_client.reqMktData(
                tickerId=request_id,
                contract=ib_contract,
                genericTickList="100,101,105,106,107,221,225",  # Greeks and IV
                snapshot=False,
                regulatorySnapshot=False,
                mktDataOptions=[]
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_request_option_quote',
                'contract': contract.contract_symbol
            })

    # ==========================================================================
    # DATA CALLBACK METHODS WITH ib_async
    # ==========================================================================
    def _on_tick_price(self, req_id: int, tick_type: int, price: float, attrib) -> None:
        """Handle tick price updates from ib_async."""
        try:
            contract = self.active_contracts.get(str(req_id))
            if not contract:
                return
            
            contract_symbol = contract.contract_symbol
            
            # Update quote cache
            if contract_symbol not in self.quotes_cache:
                self.quotes_cache[contract_symbol] = OptionQuote(
                    contract=contract,
                    bid=0.0,
                    ask=0.0,
                    bid_size=0,
                    ask_size=0,
                    last=0.0,
                    last_size=0,
                    volume=0,
                    open_interest=0,
                    timestamp=datetime.now(),
                    exchange="SMART"
                )
            
            quote = self.quotes_cache[contract_symbol]
            
            # Update based on tick type
            if tick_type == 1:  # Bid
                quote.bid = price
            elif tick_type == 2:  # Ask
                quote.ask = price
            elif tick_type == 4:  # Last
                quote.last = price
                # Create trade record
                self._record_option_trade(contract, price)
            
            quote.timestamp = datetime.now()
            self.stats['quotes_received'] += 1
            
            # Trigger quote update event
            self._emit_quote_update(quote)
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_on_tick_price',
                'req_id': req_id,
                'tick_type': tick_type
            })
    
    def _on_tick_size(self, req_id: int, tick_type: int, size: int) -> None:
        """Handle tick size updates from ib_async."""
        try:
            contract = self.active_contracts.get(str(req_id))
            if not contract:
                return
            
            contract_symbol = contract.contract_symbol
            quote = self.quotes_cache.get(contract_symbol)
            if not quote:
                return
            
            # Update based on tick type
            if tick_type == 0:  # Bid size
                quote.bid_size = size
            elif tick_type == 3:  # Ask size
                quote.ask_size = size
            elif tick_type == 5:  # Last size
                quote.last_size = size
            elif tick_type == 8:  # Volume
                quote.volume = size
            
            quote.timestamp = datetime.now()
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_on_tick_size',
                'req_id': req_id,
                'tick_type': tick_type
            })
    
    def _on_option_computation(self, req_id: int, tick_type: int, implied_vol: float,
                              delta: float, opt_price: float, pv_dividend: float,
                              gamma: float, vega: float, theta: float, under_price: float) -> None:
        """Handle option Greeks and implied volatility updates from ib_async."""
        try:
            contract = self.active_contracts.get(str(req_id))
            if not contract:
                return
            
            contract_symbol = contract.contract_symbol
            quote = self.quotes_cache.get(contract_symbol)
            if not quote:
                return
            
            # Update Greeks and IV
            if implied_vol > 0 and implied_vol < MAX_IMPLIED_VOL:
                quote.implied_vol = implied_vol
                self.implied_vols[contract_symbol] = implied_vol
            
            if abs(delta) <= 1.0:
                quote.delta = delta
            
            if gamma >= 0:
                quote.gamma = gamma
            
            if vega >= 0:
                quote.vega = vega
            
            quote.theta = theta
            
            # Update underlying price
            if under_price > 0:
                self.underlying_prices[contract.symbol] = under_price
            
            quote.timestamp = datetime.now()
            self.stats['greeks_calculated'] += 1
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_on_option_computation',
                'req_id': req_id
            })

    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    def _on_market_data_event(self, event: Event) -> None:
        """Handle market data events."""
        try:
            data = event.data
            if data.get('symbol') in self.underlying_prices:
                symbol = data['symbol']
                price = float(data.get('price', 0))
                if price > 0:
                    self.underlying_prices[symbol] = price
                    
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_on_market_data_event'
            })
    
    def _on_option_data_event(self, event: Event) -> None:
        """Handle option-specific data events."""
        try:
            # Process external option data if needed
            pass
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_on_option_data_event'
            })

    # ==========================================================================
    # ANALYSIS METHODS
    # ==========================================================================
    def _feed_loop(self) -> None:
        """Main data feed processing loop."""
        while not self._stop_event.is_set() and self.is_running:
            try:
                # Update option chains
                self._update_option_chains()
                
                # Analyze options flow
                self._analyze_options_flow()
                
                # Clean stale data
                self._clean_stale_data()
                
                # Performance monitoring
                self._monitor_performance()
                
                # Sleep
                time.sleep(1.0)
                
            except Exception as e:
                self.error_handler.handle_error(e, {
                    'method': '_feed_loop'
                })
                time.sleep(5.0)  # Longer sleep on error
    
    def _greeks_loop(self) -> None:
        """Greeks calculation loop."""
        while not self._stop_event.is_set() and self.is_running:
            try:
                # Calculate Greeks for all active contracts
                self._calculate_all_greeks()
                
                # Sleep
                time.sleep(GREEKS_UPDATE_INTERVAL)
                
            except Exception as e:
                self.error_handler.handle_error(e, {
                    'method': '_greeks_loop'
                })
                time.sleep(5.0)
    
    def _update_option_chains(self) -> None:
        """Update option chain snapshots."""
        with self._lock:
            for symbol in self.option_chains.keys():
                underlying_price = self.underlying_prices.get(symbol, 0.0)
                if underlying_price <= 0:
                    continue
                
                # Group quotes by expiration
                quotes_by_exp = defaultdict(lambda: {'calls': {}, 'puts': {}})
                
                for contract_symbol, quote in self.quotes_cache.items():
                    if quote.contract.symbol == symbol:
                        exp = quote.contract.expiration
                        strike = quote.contract.strike
                        
                        if quote.contract.option_type == OptionType.CALL:
                            quotes_by_exp[exp]['calls'][strike] = quote
                        else:
                            quotes_by_exp[exp]['puts'][strike] = quote
                
                # Create chain snapshots
                for expiration, data in quotes_by_exp.items():
                    chain = OptionsChainSnapshot(
                        underlying_symbol=symbol,
                        underlying_price=underlying_price,
                        expiration=expiration,
                        calls=data['calls'],
                        puts=data['puts'],
                        timestamp=datetime.now()
                    )
                    self.option_chains[symbol][expiration] = chain
    
    def _analyze_options_flow(self) -> None:
        """Analyze options flow for institutional activity."""
        try:
            # Get recent trades (last 5 minutes)
            cutoff_time = datetime.now() - timedelta(minutes=5)
            recent_trades = [trade for trade in self.trades_cache if trade.timestamp >= cutoff_time]
            
            # Group by underlying symbol
            trades_by_symbol = defaultdict(list)
            for trade in recent_trades:
                trades_by_symbol[trade.contract.symbol].append(trade)
            
            # Analyze flow for each symbol
            for symbol, trades in trades_by_symbol.items():
                if not trades:
                    continue
                
                # Calculate flow metrics
                total_volume = sum(trade.size for trade in trades)
                total_premium = sum(trade.notional_value for trade in trades)
                avg_price = total_premium / (total_volume * OPTION_MULTIPLIER) if total_volume > 0 else 0.0
                
                call_trades = [t for t in trades if t.contract.option_type == OptionType.CALL]
                put_trades = [t for t in trades if t.contract.option_type == OptionType.PUT]
                
                call_volume = sum(trade.size for trade in call_trades)
                put_volume = sum(trade.size for trade in put_trades)
                call_premium = sum(trade.notional_value for trade in call_trades)
                put_premium = sum(trade.notional_value for trade in put_trades)
                
                # Determine flow direction
                direction = FlowDirection.NEUTRAL
                if call_volume > put_volume * 1.5:
                    direction = FlowDirection.BULLISH
                elif put_volume > call_volume * 1.5:
                    direction = FlowDirection.BEARISH
                
                # Update flow analysis
                self.options_flow[symbol] = OptionsFlow(
                    symbol=symbol,
                    direction=direction,
                    volume=total_volume,
                    premium=total_premium,
                    avg_price=avg_price,
                    trades=len(trades),
                    call_volume=call_volume,
                    put_volume=put_volume,
                    call_premium=call_premium,
                    put_premium=put_premium,
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_analyze_options_flow'
            })
    
    def _calculate_all_greeks(self) -> None:
        """Calculate Greeks for all active option contracts."""
        for contract_symbol, quote in self.quotes_cache.items():
            try:
                self._calculate_greeks(quote)
            except Exception as e:
                self.error_handler.handle_error(e, {
                    'method': '_calculate_all_greeks',
                    'contract': contract_symbol
                })
    
    def _calculate_greeks(self, quote: OptionQuote) -> None:
        """Calculate Greeks for option quote."""
        try:
            contract = quote.contract
            underlying_price = self.underlying_prices.get(contract.symbol, 0.0)
            
            if underlying_price <= 0 or quote.mid <= 0 or contract.tte <= MIN_TIME_TO_EXPIRY:
                return
            
            # Use existing implied volatility or calculate from price
            iv = quote.implied_vol
            if not iv or iv <= 0:
                iv = self._calculate_implied_volatility(quote, underlying_price)
            
            if not iv or iv <= MIN_IMPLIED_VOL or iv >= MAX_IMPLIED_VOL:
                return
            
            # Calculate Greeks using py_vollib
            flag = 'c' if contract.option_type == OptionType.CALL else 'p'
            
            try:
                quote.delta = delta(flag, underlying_price, contract.strike, contract.tte, self.risk_free_rate, iv)
                quote.gamma = gamma(flag, underlying_price, contract.strike, contract.tte, self.risk_free_rate, iv)
                quote.theta = theta(flag, underlying_price, contract.strike, contract.tte, self.risk_free_rate, iv) / 365.25
                quote.vega = vega(flag, underlying_price, contract.strike, contract.tte, self.risk_free_rate, iv) / 100
                quote.rho = rho(flag, underlying_price, contract.strike, contract.tte, self.risk_free_rate, iv) / 100
                
                if not quote.implied_vol:
                    quote.implied_vol = iv
                
            except Exception as e:
                self.logger.debug(f"Greeks calculation failed for {contract.contract_symbol}: {e}")
                
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_calculate_greeks',
                'contract': quote.contract.contract_symbol
            })

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _get_underlying_price(self, symbol: str) -> float:
        """Get current underlying price."""
        return self.underlying_prices.get(symbol, 0.0)
    
    def _get_target_expirations(self, symbol: str) -> List[date]:
        """Get target expiration dates for options chains."""
        today = date.today()
        expirations = []
        
        for dte in self.dte_filter:
            exp_date = today + timedelta(days=dte)
            # Adjust to nearest Friday (typical option expiration)
            days_until_friday = (4 - exp_date.weekday()) % 7
            if days_until_friday == 0 and exp_date == today:
                days_until_friday = 7  # Next Friday if today is Friday
            exp_date += timedelta(days=days_until_friday)
            expirations.append(exp_date)
        
        return sorted(set(expirations))
    
    def _calculate_strike_range(self, underlying_price: float, expiration: date) -> List[float]:
        """Calculate relevant strike range for option chain."""
        dte = (expiration - date.today()).days
        
        # Adjust range based on DTE
        if dte <= 1:  # 0-1 DTE
            range_pct = 0.02  # ±2%
        elif dte <= 7:  # Weekly
            range_pct = 0.05  # ±5%
        elif dte <= 30:  # Monthly
            range_pct = 0.10  # ±10%
        else:  # Quarterly
            range_pct = 0.15  # ±15%
        
        # Calculate strike range
        range_amount = underlying_price * range_pct
        min_strike = underlying_price - range_amount
        max_strike = underlying_price + range_amount
        
        # Round to nearest dollar or half-dollar
        strike_increment = 1.0 if underlying_price > 200 else 0.5
        
        strikes = []
        strike = math.floor(min_strike / strike_increment) * strike_increment
        while strike <= max_strike:
            strikes.append(strike)
            strike += strike_increment
        
        return strikes
    
    def _calculate_implied_volatility(self, quote: OptionQuote, underlying_price: float) -> Optional[float]:
        """Calculate implied volatility from option price."""
        try:
            if quote.mid <= 0 or underlying_price <= 0:
                return None
            
            contract = quote.contract
            flag = 'c' if contract.option_type == OptionType.CALL else 'p'
            
            # Use py_vollib for IV calculation
            from py_vollib.black_scholes.implied_volatility import implied_volatility
            
            iv = implied_volatility(
                price=quote.mid,
                S=underlying_price,
                K=contract.strike,
                T=contract.tte,
                r=self.risk_free_rate,
                flag=flag
            )
            
            return iv if MIN_IMPLIED_VOL <= iv <= MAX_IMPLIED_VOL else None
            
        except Exception:
            return None
    
    def _record_option_trade(self, contract: OptionContract, price: float, size: int = 1) -> None:
        """Record option trade for flow analysis."""
        trade = OptionTrade(
            contract=contract,
            price=price,
            size=size,
            timestamp=datetime.now(),
            exchange="SMART"
        )
        
        self.trades_cache.append(trade)
        self.stats['trades_received'] += 1
    
    def _emit_quote_update(self, quote: OptionQuote) -> None:
        """Emit quote update event."""
        if self.event_manager:
            event = Event(
                event_type=EventType.OPTION_DATA,
                data={
                    'type': 'quote_update',
                    'contract_symbol': quote.contract.contract_symbol,
                    'bid': quote.bid,
                    'ask': quote.ask,
                    'last': quote.last,
                    'volume': quote.volume,
                    'implied_vol': quote.implied_vol,
                    'delta': quote.delta,
                    'gamma': quote.gamma,
                    'theta': quote.theta,
                    'vega': quote.vega,
                    'timestamp': quote.timestamp.isoformat(),
                    'ib_library': 'ib_async'
                },
                timestamp=quote.timestamp
            )
            self.event_manager.emit(event)
    
    def _clean_stale_data(self) -> None:
        """Clean stale data from caches."""
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(seconds=STALE_DATA_THRESHOLD)
        
        with self._lock:
            # Remove stale quotes
            stale_contracts = [
                contract_symbol for contract_symbol, quote in self.quotes_cache.items()
                if quote.timestamp < cutoff_time
            ]
            
            for contract_symbol in stale_contracts:
                del self.quotes_cache[contract_symbol]
                
            # Clean old trades
            while self.trades_cache and self.trades_cache[0].timestamp < cutoff_time:
                self.trades_cache.popleft()
    
    def _monitor_performance(self) -> None:
        """Monitor feed performance."""
        current_time = time.time()
        if current_time - self.stats['last_performance_check'] >= 60:  # Every minute
            self.logger.debug(f"OPRA Feed Stats (ib_async): "
                            f"Quotes: {self.stats['quotes_received']}, "
                            f"Trades: {self.stats['trades_received']}, "
                            f"Greeks: {self.stats['greeks_calculated']}, "
                            f"Errors: {self.stats['errors']}")
            
            self.stats['last_performance_check'] = current_time
    
    def _get_next_request_id(self) -> int:
        """Get next unique request ID."""
        self.request_counter += 1
        return self.request_counter
    
    def _stop_market_data_requests(self) -> None:
        """Stop all market data requests."""
        if self.ib_client:
            for req_id in self.active_contracts.keys():
                try:
                    self.ib_client.cancelMktData(int(req_id))
                except Exception:
                    pass

    # ==========================================================================
    # PUBLIC API METHODS
    # ==========================================================================
    def get_option_chain(self, symbol: str, expiration: date) -> Optional[OptionsChainSnapshot]:
        """
        Get option chain for specific symbol and expiration.
        
        Args:
            symbol: Underlying symbol
            expiration: Option expiration date
            
        Returns:
            OptionsChainSnapshot if available, None otherwise
        """
        return self.option_chains.get(symbol, {}).get(expiration)
    
    def get_option_quote(self, contract: OptionContract) -> Optional[OptionQuote]:
        """
        Get current quote for option contract.
        
        Args:
            contract: Option contract
            
        Returns:
            OptionQuote if available, None otherwise
        """
        return self.quotes_cache.get(contract.contract_symbol)
    
    def get_options_flow(self, symbol: str) -> Optional[OptionsFlow]:
        """
        Get current options flow analysis for symbol.
        
        Args:
            symbol: Underlying symbol
            
        Returns:
            OptionsFlow if available, None otherwise
        """
        return self.options_flow.get(symbol)
    
    def get_all_option_chains(self, symbol: str) -> Dict[date, OptionsChainSnapshot]:
        """
        Get all option chains for symbol.
        
        Args:
            symbol: Underlying symbol
            
        Returns:
            Dictionary of expiration dates to option chains
        """
        return self.option_chains.get(symbol, {}).copy()
    
    def get_atm_options(self, symbol: str, expiration: date) -> Dict[str, OptionQuote]:
        """
        Get at-the-money call and put options.
        
        Args:
            symbol: Underlying symbol
            expiration: Option expiration date
            
        Returns:
            Dictionary with 'call' and 'put' ATM quotes
        """
        chain = self.get_option_chain(symbol, expiration)
        if not chain:
            return {}
        
        atm_strike = chain.atm_strike
        result = {}
        
        if atm_strike in chain.calls:
            result['call'] = chain.calls[atm_strike]
        
        if atm_strike in chain.puts:
            result['put'] = chain.puts[atm_strike]
        
        return result
    
    def get_option_volume(self, symbol: str, expiration: date) -> Dict[str, int]:
        """
        Get total option volume for expiration.
        
        Args:
            symbol: Underlying symbol
            expiration: Option expiration date
            
        Returns:
            Dictionary with call and put volumes
        """
        chain = self.get_option_chain(symbol, expiration)
        if not chain:
            return {'call_volume': 0, 'put_volume': 0}
        
        call_volume = sum(quote.volume for quote in chain.calls.values())
        put_volume = sum(quote.volume for quote in chain.puts.values())
        
        return {
            'call_volume': call_volume,
            'put_volume': put_volume,
            'total_volume': call_volume + put_volume,
            'call_put_ratio': call_volume / put_volume if put_volume > 0 else float('inf')
        }
    
    def get_greeks_summary(self, symbol: str, expiration: date) -> Dict[str, float]:
        """
        Get aggregated Greeks for option chain.
        
        Args:
            symbol: Underlying symbol
            expiration: Option expiration date
            
        Returns:
            Dictionary with aggregated Greeks
        """
        chain = self.get_option_chain(symbol, expiration)
        if not chain:
            return {}
        
        total_delta = 0.0
        total_gamma = 0.0
        total_theta = 0.0
        total_vega = 0.0
        
        all_quotes = list(chain.calls.values()) + list(chain.puts.values())
        
        for quote in all_quotes:
            if quote.delta is not None:
                total_delta += quote.delta * quote.volume
            if quote.gamma is not None:
                total_gamma += quote.gamma * quote.volume
            if quote.theta is not None:
                total_theta += quote.theta * quote.volume
            if quote.vega is not None:
                total_vega += quote.vega * quote.volume
        
        return {
            'total_delta': total_delta,
            'total_gamma': total_gamma,
            'total_theta': total_theta,
            'total_vega': total_vega,
            'ib_library': 'ib_async'
        }
    
    def get_implied_volatility_smile(self, symbol: str, expiration: date) -> pd.DataFrame:
        """
        Get implied volatility smile for expiration.
        
        Args:
            symbol: Underlying symbol
            expiration: Option expiration date
            
        Returns:
            DataFrame with strike, call IV, put IV
        """
        chain = self.get_option_chain(symbol, expiration)
        if not chain:
            return pd.DataFrame()
        
        data = []
        all_strikes = chain.all_strikes
        
        for strike in all_strikes:
            row = {'strike': strike}
            
            if strike in chain.calls and chain.calls[strike].implied_vol:
                row['call_iv'] = chain.calls[strike].implied_vol
            
            if strike in chain.puts and chain.puts[strike].implied_vol:
                row['put_iv'] = chain.puts[strike].implied_vol
            
            if 'call_iv' in row or 'put_iv' in row:
                data.append(row)
        
        return pd.DataFrame(data)

    # ==========================================================================
    # CLEANUP METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up OPRA data feed resources."""
        try:
            # Stop feed
            self.stop_feed()
            
            # Clear data structures
            with self._lock:
                self.option_chains.clear()
                self.active_contracts.clear()
                self.quotes_cache.clear()
                self.trades_cache.clear()
                self.tick_data.clear()
                self.underlying_prices.clear()
                self.implied_vols.clear()
                self.greeks_cache.clear()
                self.options_flow.clear()
                self.flow_history.clear()
            
            self.logger.info("OPRA data feed cleanup completed")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'cleanup'
            })

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def get_opra_feed(config: Optional[Dict] = None) -> OPRADataFeed:
    """
    Get singleton instance of OPRA data feed.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        OPRADataFeed instance with ib_async integration
    """
    global _opra_feed_instance
    if _opra_feed_instance is None:
        _opra_feed_instance = OPRADataFeed(config)
    return _opra_feed_instance

def create_option_contract(symbol: str, expiration: date, strike: float, 
                          option_type: str) -> OptionContract:
    """
    Create option contract helper function.
    
    Args:
        symbol: Underlying symbol
        expiration: Expiration date
        strike: Strike price
        option_type: 'C' for call, 'P' for put
        
    Returns:
        OptionContract instance
    """
    return OptionContract(
        symbol=symbol,
        expiration=expiration,
        strike=strike,
        option_type=OptionType.CALL if option_type.upper() == 'C' else OptionType.PUT
    )

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Global instance
_opra_feed_instance: Optional[OPRADataFeed] = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("📡 Testing OPRA Data Feed with ib_async...")
    
    feed = OPRADataFeed()
    
    if feed.initialize():
        print("✅ OPRA Feed initialized successfully with ib_async")
        
        # Start feed
        feed.start_feed()
        
        # Test contract creation
        contract = create_option_contract("SPY", date(2025, 7, 18), 450.0, "C")
        print(f"📋 Test Contract: {contract.contract_symbol}")
        print(f"   DTE: {contract.dte}")
        print(f"   TTE: {contract.tte:.4f}")
        
        # Simulate some option data
        quote = OptionQuote(
            contract=contract,
            bid=5.10,
            ask=5.20,
            bid_size=10,
            ask_size=15,
            last=5.15,
            last_size=5,
            volume=1000,
            open_interest=5000,
            timestamp=datetime.now(),
            exchange="CBOE",
            implied_vol=0.25,
            delta=0.55,
            gamma=0.08,
            theta=-0.05,
            vega=0.12
        )
        
        print(f"📊 Test Quote (ib_async):")
        print(f"   Bid/Ask: ${quote.bid:.2f} / ${quote.ask:.2f}")
        print(f"   Mid: ${quote.mid:.2f}")
        print(f"   IV: {quote.implied_vol:.1%}")
        print(f"   Delta: {quote.delta:.3f}")
        print(f"   Gamma: {quote.gamma:.3f}")
        print(f"   Volume: {quote.volume:,}")
        print(f"   Library: {quote.ib_library}")
        
        # Test flow analysis
        flow = OptionsFlow(
            symbol="SPY",
            direction=FlowDirection.BULLISH,
            volume=10000,
            premium=500000.0,
            avg_price=5.0,
            trades=50,
            call_volume=7000,
            put_volume=3000,
            call_premium=350000.0,
            put_premium=150000.0,
            timestamp=datetime.now()
        )
        
        print(f"🌊 Test Flow (ib_async):")
        print(f"   Direction: {flow.direction.value}")
        print(f"   C/P Ratio: {flow.call_put_ratio:.2f}")
        print(f"   Volume: {flow.volume:,}")
        print(f"   Premium: ${flow.premium:,.0f}")
        print(f"   Library: {flow.ib_library}")
        
        time.sleep(3)
        
        # Cleanup
        feed.cleanup()
        print("🧹 Cleanup completed")
        
    else:
        print("❌ OPRA Feed initialization failed")
