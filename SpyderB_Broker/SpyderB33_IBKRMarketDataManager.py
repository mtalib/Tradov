#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB33_IBKRMarketDataManager.py
Purpose: IBKR Client Portal Web API market data retrieval and management

Author: SPYDER Trading System
Year Created: 2025
Last Updated: 2025-01-24 Time: 12:00:00

Module Description:
    This module handles market data retrieval and management for the IBKR Client Portal Web API.
    It provides a unified interface for accessing real-time and historical market data,
    managing subscriptions, and caching data efficiently. The module implements
    robust rate limiting, caching mechanisms, and error handling for reliable
    market data operations.

    Note: Only SPY options are supported for trading. DIA and QQQ options have been removed
    to reduce system burden and focus on the most predictable options instrument.

Module Constants:
    DEFAULT_TIMEOUT (int): Default request timeout in seconds (default: 10)
    DEFAULT_RETRY_ATTEMPTS (int): Maximum number of retry attempts (default: 3)
    DEFAULT_RETRY_DELAY (float): Default delay between retry attempts in seconds (default: 1.0)
    DEFAULT_CACHE_DURATION (int): Default cache duration in seconds (default: 5)
    DEFAULT_MAX_CACHE_SIZE (int): Maximum number of cached items (default: 1000)
    DEFAULT_RATE_LIMIT_DELAY (float): Default delay between requests in seconds (default: 0.1)

Change Log:
    2025-01-24 (v1.0.0):
        - Initial module creation following Spyder template standards
        - Implemented comprehensive market data management
        - Added real-time and historical data retrieval
        - Implemented option chain data handling
        - Added contract search functionality
        - Implemented caching and rate limiting
        - Added proper error handling and recovery
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import json
import threading
import asyncio
import uuid
import warnings
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum, auto
from pathlib import Path
import copy
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import requests
from threading import Lock, Event as ThreadEvent, RLock

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Safe imports with fallbacks
try:
    from SpyderU_Utilities.SpyderU07_Constants import BaseConstants
except ImportError:
    BaseConstants = None

from typing import TYPE_CHECKING

# Import session manager
if TYPE_CHECKING:
    try:
        from SpyderB_Broker.SpyderB32_IBKRSessionManager import SessionManager, AuthStatus
    except ImportError:
        # Fallback for testing
        SessionManager = None
        AuthStatus = None

try:
    from SpyderB_Broker.SpyderB32_IBKRSessionManager import SessionManager, AuthStatus
except ImportError:
    # Fallback for testing
    SessionManager = None
    AuthStatus = None


# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_TIMEOUT = 10
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_CACHE_DURATION = 5  # seconds
DEFAULT_MAX_CACHE_SIZE = 1000
DEFAULT_RATE_LIMIT_DELAY = 0.1  # seconds between requests

# Update frequencies in seconds
FREQUENCY_1_SECOND = 1
FREQUENCY_5_SECONDS = 5
FREQUENCY_15_SECONDS = 15
FREQUENCY_30_SECONDS = 30
FREQUENCY_60_SECONDS = 60
FREQUENCY_300_SECONDS = 300  # 5 minutes for DIX

# ==============================================================================
# ENUMS
# ==============================================================================
class ModuleState(Enum):
    """Module operational states"""
    INITIALIZING = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPED = auto()
    ERROR = auto()

class UpdateFrequency(Enum):
    """Update frequency enumeration."""
    CRITICAL = "1s"      # 1 second
    HIGH = "5s"          # 5 seconds
    NORMAL = "15s"       # 15 seconds
    LOW = "30s"          # 30 seconds
    BACKGROUND = "60s"   # 60 seconds
    BATCH = "300s"       # 5 minutes

class SymbolType(Enum):
    """Symbol type enumeration."""
    EQUITY = "equity"
    INDEX = "index"
    ETF = "etf"
    FUTURE = "future"
    OPTION = "option"
    VOLATILITY = "volatility"
    CURRENCY = "currency"
    BOND = "bond"
    COMMODITY = "commodity"
    CALCULATED = "calculated"

class MarketDataType(Enum):
    """Market data type enumeration."""
    SNAPSHOT = "snapshot"
    REALTIME = "realtime"
    HISTORICAL = "historical"
    OPTION_CHAIN = "option_chain"


class MarketDataField(Enum):
    """Market data field enumeration."""
    LAST_PRICE = "31"
    BID = "84"
    ASK = "86"
    BID_SIZE = "88"
    ASK_SIZE = "85"
    VOLUME = "7059"
    HIGH = "70"
    LOW = "71"
    OPEN = "7051"
    CLOSE = "7052"
    IMPLIED_VOLATILITY = "29"
    DELTA = "46"
    GAMMA = "47"
    THETA = "48"
    VEGA = "49"
    RHO = "50"


@dataclass
class MarketDataSnapshot:
    """Market data snapshot."""
    symbol: str
    conid: Optional[int] = None
    last_price: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    volume: Optional[int] = None
    high: Optional[float] = None
    low: Optional[float] = None
    open: Optional[float] = None
    close: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'conid': self.conid,
            'last_price': self.last_price,
            'bid': self.bid,
            'ask': self.ask,
            'bid_size': self.bid_size,
            'ask_size': self.ask_size,
            'volume': self.volume,
            'high': self.high,
            'low': self.low,
            'open': self.open,
            'close': self.close,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class HistoricalDataPoint:
    """Historical data point."""
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'date': self.date.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }


@dataclass
class OptionContract:
    """Option contract information."""
    conid: int
    symbol: str
    right: str  # CALL or PUT
    strike: float
    expiration: datetime
    multiplier: float = 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'conid': self.conid,
            'symbol': self.symbol,
            'right': self.right,
            'strike': self.strike,
            'expiration': self.expiration.isoformat(),
            'multiplier': self.multiplier
        }


@dataclass
class SymbolConfig:
    """Configuration for a market data symbol."""
    symbol: str
    conid: Optional[int] = None
    symbol_type: SymbolType = SymbolType.EQUITY
    update_frequency: UpdateFrequency = UpdateFrequency.NORMAL
    is_hidden: bool = False
    is_option_chain: bool = False
    option_underlying: Optional[str] = None
    option_expiration: Optional[str] = None
    fields: List[str] = field(default_factory=lambda: [
        MarketDataField.LAST_PRICE.value,
        MarketDataField.BID.value,
        MarketDataField.ASK.value
    ])
    description: str = ""

    def __post_init__(self):
        """Post-initialization processing."""
        # Convert string frequency to enum if needed
        if isinstance(self.update_frequency, str):
            self.update_frequency = UpdateFrequency(self.update_frequency)

        # Convert string symbol_type to enum if needed
        if isinstance(self.symbol_type, str):
            self.symbol_type = SymbolType(self.symbol_type)


@dataclass
class SubscriptionConfig:
    """Configuration for market data subscriptions."""
    enable_critical: bool = True      # 1 second updates
    enable_high: bool = True          # 5 second updates
    enable_normal: bool = True        # 15 second updates
    enable_low: bool = True           # 30 second updates
    enable_background: bool = True    # 60 second updates
    enable_options: bool = True       # Option chains
    enable_hidden: bool = True        # Hidden symbols
    batch_size_limit: int = 50        # Max symbols per request
    prioritize_critical: bool = True   # Prioritize critical data


@dataclass
class MarketDataConfig:
    """Configuration for market data management."""
    default_timeout: int = 10
    retry_attempts: int = 3
    retry_delay: float = 1.0
    cache_duration: int = 5  # seconds
    max_cache_size: int = 1000
    rate_limit_delay: float = 0.1  # seconds between requests
    default_fields: List[str] = field(default_factory=lambda: [
        MarketDataField.LAST_PRICE.value,
        MarketDataField.BID.value,
        MarketDataField.ASK.value
    ])
    subscription_config: SubscriptionConfig = field(default_factory=SubscriptionConfig)


# ==============================================================================
# SYMBOL REGISTRY
# ==============================================================================
class SymbolRegistry:
    """Registry of all SPYDER market data symbols with their configurations."""

    # Symbol to conid mappings for common symbols
    SYMBOL_CONID_MAP = {
        'SPY': 756733,
        'SPX': 416904,
        'VIX': 13455763,
        'QQQ': 320227571,
        'IWM': 9579970,
        'DIA': 12087892,
        'TLT': 16140655,
        'LQD': 12087825,
        'GLD': 12087816,
        'DXY': 12087820,
        'VX': 34124198,
        'VX9D': 42690455,
        'VXV': 34124199,
        'VXMT': 42690456,
        'VVIX': 42690457,
        'UVXY': 9558427,
        'VUD': 42690458,
        'TRIN': 42690459,
        'ADD': 42690460,
        'CPC': 42690461,
        'PCALL': 42690462,
        'SKEW': 42690463,
        'VXST': 42690464,
        'VXN': 42690465,
        'RVX': 42690466,
        'CPCE': 42690467,
        'CPCI': 42690468,
        'TICK-NYSE': 42690469,
        'TICK-NASDAQ': 42690470,
        'TRIN-NYSE': 42690471,
        'TRIN-NASDAQ': 42690472,
        'ADD-NYSE': 42690473,
        'ADVN-NYSE': 42690474,
        'DECN-NYSE': 42690475,
        'UVOL-NYSE': 42690476,
        'DVOL-NYSE': 42690477,
        'VOLD-NYSE': 42690478,
        'NYHL-NYSE': 42690479,
        '/ES': 42690480,
        'FTLC': 42690481,
        'AUD.JPY': 42690482,
        'DAX': 42690483,
        'HSI': 42690484,
        'EWJ': 42690485,
        'EWG': 42690486,
        'EWU': 42690487,
        'EWC': 42690488,
        'XLF': 42690489,
        'XLK': 42690490,
        'XLE': 42690491,
        'XLV': 42690492,
        'XLI': 42690493,
        'XLY': 42690494,
        'XLP': 42690495,
        'XLU': 42690496,
        'XLRE': 42690497,
        'XLC': 42690498,
        'XLB': 42690499
    }

    @classmethod
    def get_all_symbols(cls) -> Dict[str, SymbolConfig]:
        """Get all SPYDER symbols with their configurations."""
        symbols = {}

        # 1 SECOND UPDATES (Critical & High Priority)
        critical_symbols = [
            ('SPY', 'SPDR S&P 500 ETF', SymbolType.ETF),
            ('SPX', 'S&P 500 Index', SymbolType.INDEX),
            ('/ES', 'E-mini S&P 500 Future', SymbolType.FUTURE),
            ('VIX', 'CBOE Volatility Index', SymbolType.VOLATILITY),
            ('TICK-NYSE', 'NYSE TICK Index', SymbolType.INDEX)
        ]

        for symbol, desc, sym_type in critical_symbols:
            symbols[symbol] = SymbolConfig(
                symbol=symbol,
                conid=cls.SYMBOL_CONID_MAP.get(symbol),
                symbol_type=sym_type,
                update_frequency=UpdateFrequency.CRITICAL,
                is_hidden=False,
                description=desc
            )

        # SPY Options Chains
        spy_options = [
            ('SPY_OPTIONS_0DTE', 'SPY 0DTE Options', True),
            ('SPY_OPTIONS_1DTE', 'SPY 1DTE Options', True),
            ('SPY_OPTIONS_WEEKLY', 'SPY Weekly Options', True)
        ]

        for symbol, desc, is_hidden in spy_options:
            symbols[symbol] = SymbolConfig(
                symbol=symbol,
                symbol_type=SymbolType.OPTION,
                update_frequency=UpdateFrequency.CRITICAL,
                is_hidden=is_hidden,
                is_option_chain=True,
                option_underlying='SPY',
                description=desc
            )

        # 5 SECOND UPDATES (Normal Priority)
        high_priority_symbols = [
            # Volatility Indicators
            ('VIX9D', '9-Day VIX Index', SymbolType.VOLATILITY, False),
            ('VXV', '3-Month VIX Index', SymbolType.VOLATILITY, False),
            ('VXMT', '6-Month VIX Index', SymbolType.VOLATILITY, False),
            ('VVIX', 'VIX of VIX Index', SymbolType.VOLATILITY, False),
            ('UVXY', 'ProShares Ultra VIX Short-Term ETF', SymbolType.ETF, False),
            ('VX', 'VIX Futures', SymbolType.FUTURE, False),

            # Market Internals
            ('VUD', 'Up/Down Volume Ratio', SymbolType.INDEX, False),
            ('TRIN-NYSE', 'NYSE TRIN Index', SymbolType.INDEX, False),
            ('ADD-NYSE', 'NYSE Advance/Decline', SymbolType.INDEX, False),
            ('CPC', 'CBOE Put/Call Ratio', SymbolType.INDEX, False),
            ('PCALL', 'CBOE Equity Put/Call Ratio', SymbolType.INDEX, False),
            ('SKEW', 'CBOE SKEW Index', SymbolType.INDEX, False),

            # Additional Internals (Hidden)
            ('ADVN-NYSE', 'NYSE Advances', SymbolType.INDEX, True),
            ('DECN-NYSE', 'NYSE Declines', SymbolType.INDEX, True),
            ('UVOL-NYSE', 'NYSE Up Volume', SymbolType.INDEX, True),
            ('DVOL-NYSE', 'NYSE Down Volume', SymbolType.INDEX, True),
            ('VOLD-NYSE', 'NYSE Volume Difference', SymbolType.INDEX, True),

            # Major Indices
            ('DIA', 'SPDR Dow Jones Industrial Average ETF', SymbolType.ETF, False),
            ('QQQ', 'Invesco QQQ Trust', SymbolType.ETF, False),
            ('IWM', 'iShares Russell 2000 ETF', SymbolType.ETF, False)
        ]

        for symbol, desc, sym_type, is_hidden in high_priority_symbols:
            symbols[symbol] = SymbolConfig(
                symbol=symbol,
                conid=cls.SYMBOL_CONID_MAP.get(symbol),
                symbol_type=sym_type,
                update_frequency=UpdateFrequency.HIGH,
                is_hidden=is_hidden,
                description=desc
            )

        # Note: DIA and QQQ options have been removed to reduce system burden
        # Only SPY options are supported for trading

        # 15 SECOND UPDATES (Low Priority)
        low_priority_symbols = [
            ('TLT', 'iShares 20+ Year Treasury Bond ETF', SymbolType.BOND, False),
            ('LQD', 'iShares iBoxx $ Investment Grade Corporate Bond ETF', SymbolType.BOND, False),
            ('DXY', 'U.S. Dollar Index', SymbolType.CURRENCY, False),
            ('GLD', 'SPDR Gold Shares', SymbolType.COMMODITY, False)
        ]

        for symbol, desc, sym_type, is_hidden in low_priority_symbols:
            symbols[symbol] = SymbolConfig(
                symbol=symbol,
                conid=cls.SYMBOL_CONID_MAP.get(symbol),
                symbol_type=sym_type,
                update_frequency=UpdateFrequency.NORMAL,
                is_hidden=is_hidden,
                description=desc
            )

        # 30 SECOND UPDATES (Low Priority)
        sector_etfs = [
            ('XLF', 'Financial Select Sector SPDR Fund', SymbolType.ETF, False),
            ('XLK', 'Technology Select Sector SPDR Fund', SymbolType.ETF, False),
            ('XLE', 'Energy Select Sector SPDR Fund', SymbolType.ETF, False),
            ('XLV', 'Health Care Select Sector SPDR Fund', SymbolType.ETF, False),
            ('XLI', 'Industrial Select Sector SPDR Fund', SymbolType.ETF, False),
            ('XLY', 'Consumer Discretionary Select Sector SPDR Fund', SymbolType.ETF, False),
            ('XLP', 'Consumer Staples Select Sector SPDR Fund', SymbolType.ETF, False),
            ('XLU', 'Utilities Select Sector SPDR Fund', SymbolType.ETF, False),
            ('XLRE', 'Real Estate Select Sector SPDR Fund', SymbolType.ETF, False),
            ('XLC', 'Communication Services Select Sector SPDR Fund', SymbolType.ETF, False),
            ('XLB', 'Materials Select Sector SPDR Fund', SymbolType.ETF, False)
        ]

        for symbol, desc, sym_type, is_hidden in sector_etfs:
            symbols[symbol] = SymbolConfig(
                symbol=symbol,
                conid=cls.SYMBOL_CONID_MAP.get(symbol),
                symbol_type=sym_type,
                update_frequency=UpdateFrequency.LOW,
                is_hidden=is_hidden,
                description=desc
            )

        # Additional Volatility Indicators (Hidden)
        additional_volatility = [
            ('VXST', 'CBOE Short-Term Volatility Index', SymbolType.VOLATILITY, True),
            ('VXN', 'CBOE NASDAQ Volatility Index', SymbolType.VOLATILITY, True),
            ('RVX', 'Russell 2000 Volatility Index', SymbolType.VOLATILITY, True)
        ]

        for symbol, desc, sym_type, is_hidden in additional_volatility:
            symbols[symbol] = SymbolConfig(
                symbol=symbol,
                conid=cls.SYMBOL_CONID_MAP.get(symbol),
                symbol_type=sym_type,
                update_frequency=UpdateFrequency.LOW,
                is_hidden=is_hidden,
                description=desc
            )

        # Put/Call Ratios (Hidden)
        put_call_ratios = [
            ('CPCE', 'CBOE Equity Put/Call Ratio', SymbolType.INDEX, True),
            ('CPCI', 'CBOE Index Put/Call Ratio', SymbolType.INDEX, True)
        ]

        for symbol, desc, sym_type, is_hidden in put_call_ratios:
            symbols[symbol] = SymbolConfig(
                symbol=symbol,
                conid=cls.SYMBOL_CONID_MAP.get(symbol),
                symbol_type=sym_type,
                update_frequency=UpdateFrequency.LOW,
                is_hidden=is_hidden,
                description=desc
            )

        # NASDAQ Internals (Hidden)
        nasdaq_internals = [
            ('TICK-NASDAQ', 'NASDAQ TICK Index', SymbolType.INDEX, True),
            ('TRIN-NASDAQ', 'NASDAQ TRIN Index', SymbolType.INDEX, True)
        ]

        for symbol, desc, sym_type, is_hidden in nasdaq_internals:
            symbols[symbol] = SymbolConfig(
                symbol=symbol,
                conid=cls.SYMBOL_CONID_MAP.get(symbol),
                symbol_type=sym_type,
                update_frequency=UpdateFrequency.LOW,
                is_hidden=is_hidden,
                description=desc
            )

        # 60 SECOND UPDATES (Batch Priority)
        international_markets = [
            ('FTLC', 'FTSE Latin America Index', SymbolType.INDEX, False),
            ('AUD.JPY', 'Australian Dollar/Japanese Yen', SymbolType.CURRENCY, False),
            ('DAX', 'DAX Index', SymbolType.INDEX, False),
            ('HSI', 'Hang Seng Index', SymbolType.INDEX, False),
            ('EWJ', 'iShares MSCI Japan ETF', SymbolType.ETF, False),
            ('EWG', 'iShares MSCI Germany ETF', SymbolType.ETF, False),
            ('EWU', 'iShares MSCI United Kingdom ETF', SymbolType.ETF, False),
            ('EWC', 'iShares MSCI Canada ETF', SymbolType.ETF, False)
        ]

        for symbol, desc, sym_type, is_hidden in international_markets:
            symbols[symbol] = SymbolConfig(
                symbol=symbol,
                conid=cls.SYMBOL_CONID_MAP.get(symbol),
                symbol_type=sym_type,
                update_frequency=UpdateFrequency.BACKGROUND,
                is_hidden=is_hidden,
                description=desc
            )

        # NYSE High/Low (Hidden)
        symbols['NYHL-NYSE'] = SymbolConfig(
            symbol='NYHL-NYSE',
            conid=cls.SYMBOL_CONID_MAP.get('NYHL-NYSE'),
            symbol_type=SymbolType.INDEX,
            update_frequency=UpdateFrequency.BACKGROUND,
            is_hidden=True,
            description='NYSE New High/Low Index'
        )

        # Custom Calculated Metrics (Internal Calculations)
        calculated_metrics = [
            ('GEX', 'Gamma Exposure', UpdateFrequency.BACKGROUND),
            ('DEX', 'Delta Exposure', UpdateFrequency.BACKGROUND),
            ('OGL', 'Options Gamma Level', UpdateFrequency.BACKGROUND),
            ('SWAN', 'System Warning Alert Network', UpdateFrequency.BACKGROUND),
            ('DIX', 'Dark Index', UpdateFrequency.BATCH)
        ]

        for symbol, desc, freq in calculated_metrics:
            symbols[symbol] = SymbolConfig(
                symbol=symbol,
                symbol_type=SymbolType.CALCULATED,
                update_frequency=freq,
                is_hidden=True,
                description=desc
            )

        return symbols

    @classmethod
    def get_symbols_by_frequency(cls, frequency: UpdateFrequency) -> List[SymbolConfig]:
        """Get symbols filtered by update frequency."""
        all_symbols = cls.get_all_symbols()
        return [config for config in all_symbols.values()
                if config.update_frequency == frequency]

    @classmethod
    def get_visible_symbols(cls) -> List[SymbolConfig]:
        """Get only visible (non-hidden) symbols."""
        all_symbols = cls.get_all_symbols()
        return [config for config in all_symbols.values()
                if not config.is_hidden]

    @classmethod
    def get_option_chain_symbols(cls) -> List[SymbolConfig]:
        """Get all option chain symbols."""
        all_symbols = cls.get_all_symbols()
        return [config for config in all_symbols.values()
                if config.is_option_chain]


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class MarketDataManager:
    """
    Manages market data operations with IBKR Client Portal API.

    This class provides a high-level interface for all market data operations
    while handling caching, rate limiting, and error recovery.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling system
        state: Current module state
        config: Module configuration
        _state_lock: Thread lock for state management
        _shutdown_event: Event for coordinated shutdown
    """

    def __init__(self, session_manager, config: Optional[MarketDataConfig] = None):
        """
        Initialize Market Data Manager.

        Args:
            session_manager: SessionManager instance
            config: Market data configuration
        """
        if session_manager is None:
            raise ValueError("SessionManager is required")

        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.session_manager = session_manager
        self.config = config or MarketDataConfig()

        # State management
        self.state = ModuleState.INITIALIZING
        self._state_lock = RLock()
        self._shutdown_event = ThreadEvent()

        # API endpoints
        self.api_base = getattr(self.session_manager, 'api_base', 'https://localhost:5000/v1/api')

        # Data cache
        self._snapshot_cache: Dict[str, MarketDataSnapshot] = {}
        self._historical_cache: Dict[str, List[HistoricalDataPoint]] = {}
        self._contract_cache: Dict[str, List[OptionContract]] = {}
        self._cache_lock = threading.RLock()

        # Rate limiting
        self._last_request_time = 0.0
        self._request_lock = threading.Lock()

        # Statistics lock
        self._lock = threading.RLock()

        # Statistics
        self._stats = {
            'snapshot_requests': 0,
            'historical_requests': 0,
            'contract_searches': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': 0,
            'last_request_time': None,
            'subscription_updates': 0,
            'option_chain_updates': 0,
            'calculated_metrics': 0
        }

        # Event callbacks
        self._data_callbacks: List[Callable[[MarketDataSnapshot], None]] = []
        self._error_callbacks: List[Callable[[str, Dict], None]] = []

        # Symbol to conid mapping cache
        self._symbol_conid_map: Dict[str, int] = {}

        # Subscription system
        self._symbol_registry = SymbolRegistry.get_all_symbols()
        self._subscription_threads: Dict[str, threading.Thread] = {}
        self._subscription_active: Dict[str, bool] = {}
        self._frequency_to_seconds = {
            UpdateFrequency.CRITICAL: FREQUENCY_1_SECOND,
            UpdateFrequency.HIGH: FREQUENCY_5_SECONDS,
            UpdateFrequency.NORMAL: FREQUENCY_15_SECONDS,
            UpdateFrequency.LOW: FREQUENCY_30_SECONDS,
            UpdateFrequency.BACKGROUND: FREQUENCY_60_SECONDS,
            UpdateFrequency.BATCH: FREQUENCY_300_SECONDS
        }

        # Option chain cache
        self._option_chain_cache: Dict[str, Dict[str, Any]] = {}

        # Calculated metrics cache
        self._calculated_metrics_cache: Dict[str, Any] = {}

        self.logger.info(f"MarketDataManager initialized with {len(self._symbol_registry)} symbols")

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================

    def initialize(self) -> bool:
        """
        Initialize the market data manager with all necessary setup.

        Returns:
            bool: True if initialization successful
        """
        try:
            with self._state_lock:
                if self.state != ModuleState.INITIALIZING:
                    self.logger.warning(f"Cannot initialize from state: {self.state}")
                    return False

                self.logger.info(f"Initializing {self.__class__.__name__}...")

                # Perform initialization tasks
                if not self._validate_configuration():
                    return False

                if not self._setup_resources():
                    return False

                self.state = ModuleState.READY
                self.logger.info(f"{self.__class__.__name__} initialization completed")
                return True

        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            self.error_handler.handle_error(e, "initialize")
            self.state = ModuleState.ERROR
            return False

    def start(self) -> bool:
        """
        Start the market data manager.

        Returns:
            bool: True if start successful
        """
        try:
            with self._state_lock:
                if self.state != ModuleState.READY:
                    self.logger.warning(f"Cannot start from state: {self.state}")
                    return False

                self.logger.info(f"Starting {self.__class__.__name__}...")

                # Clear shutdown event
                self._shutdown_event.clear()

                # Start subscription threads for each frequency
                self._start_subscriptions()

                self.state = ModuleState.RUNNING
                self.logger.info(f"{self.__class__.__name__} started successfully")
                return True

        except Exception as e:
            self.logger.error(f"Failed to start {self.__class__.__name__}: {e}")
            self.error_handler.handle_error(e, "start")
            self.state = ModuleState.ERROR
            return False

    def stop(self) -> bool:
        """
        Stop the market data manager gracefully.

        Returns:
            bool: True if stop successful
        """
        try:
            with self._state_lock:
                if self.state not in [ModuleState.RUNNING, ModuleState.PAUSED]:
                    self.logger.warning(f"Cannot stop from state: {self.state}")
                    return False

                self.logger.info(f"Stopping {self.__class__.__name__}...")

                # Signal shutdown
                self._shutdown_event.set()

                # Stop subscription threads
                self._stop_subscriptions()

                # Clean up resources
                self._cleanup_resources()

                self.state = ModuleState.STOPPED
                self.logger.info(f"{self.__class__.__name__} stopped successfully")
                return True

        except Exception as e:
            self.logger.error(f"Error stopping {self.__class__.__name__}: {e}")
            self.error_handler.handle_error(e, "stop")
            return False

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================

    def _validate_configuration(self) -> bool:
        """Validate module configuration."""
        try:
            if self.config.default_timeout <= 0:
                self.logger.error("Invalid timeout value")
                return False

            if self.config.retry_attempts < 0:
                self.logger.error("Invalid retry attempts value")
                return False

            if self.config.cache_duration < 0:
                self.logger.error("Invalid cache duration value")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False

    def _setup_resources(self) -> bool:
        """Set up required resources."""
        try:
            # Initialize caches
            self._snapshot_cache.clear()
            self._historical_cache.clear()
            self._contract_cache.clear()

            self.logger.debug("Resources setup completed")
            return True

        except Exception as e:
            self.logger.error(f"Resource setup failed: {e}")
            return False

    def _cleanup_resources(self):
        """Clean up allocated resources."""
        try:
            # Clear caches
            self.clear_cache()

            # Clear callbacks
            self._data_callbacks.clear()
            self._error_callbacks.clear()

            self.logger.debug("Resources cleaned up")

        except Exception as e:
            self.logger.error(f"Resource cleanup failed: {e}")

    # ==========================================================================
    # CORE OPERATIONS
    # ==========================================================================

    def get_market_snapshot(self, symbols: Union[str, List[str]],
                          fields: Optional[List[str]] = None) -> Dict[str, MarketDataSnapshot]:
        """
        Get market data snapshots for symbols.

        Args:
            symbols: Symbol or list of symbols
            fields: Market data fields to request

        Returns:
            Dictionary mapping symbols to market data snapshots
        """
        try:
            # Normalize symbols to list
            if isinstance(symbols, str):
                symbols = [symbols]

            fields = fields or self.config.default_fields

            # Check cache first
            cached_snapshots = {}
            uncached_symbols = []

            with self._cache_lock:
                for symbol in symbols:
                    if symbol in self._snapshot_cache:
                        cached_snapshots[symbol] = self._snapshot_cache[symbol]
                        # Check if cache is fresh
                        if (datetime.now() - cached_snapshots[symbol].timestamp).seconds < self.config.cache_duration:
                            self._stats['cache_hits'] += 1
                        else:
                            uncached_symbols.append(symbol)
                            self._stats['cache_misses'] += 1
                    else:
                        uncached_symbols.append(symbol)
                        self._stats['cache_misses'] += 1

            # Return cached data if all symbols are cached and fresh
            if not uncached_symbols:
                return cached_snapshots

            # Check authentication
            if not getattr(self.session_manager, 'is_authenticated', lambda: False)():
                self.logger.error("Cannot get market data: Not authenticated")
                return cached_snapshots

            # Convert symbols to conids
            conids = []
            symbol_conid_map = {}
            for symbol in uncached_symbols:
                conid = self._symbol_to_conid(symbol)
                if conid:
                    conids.append(conid)
                    symbol_conid_map[conid] = symbol
                else:
                    self.logger.warning(f"Could not find conid for symbol: {symbol}")

            if not conids:
                return cached_snapshots

            # Apply rate limiting
            self._apply_rate_limit()

            # Make API request
            params = {
                'conids': ','.join(map(str, conids)),
                'fields': ','.join(fields)
            }

            endpoint = "/iserver/marketdata/snapshot"
            response = self._make_request('GET', endpoint, params=params)

            if not response:
                self.logger.error("Failed to get market data: No response")
                with self._lock:
                    self._stats['errors'] += 1
                return cached_snapshots

            data = response.json()
            new_snapshots = {}

            # Parse response
            for i, item in enumerate(data):
                if i < len(conids):
                    conid = conids[i]
                    symbol = symbol_conid_map[conid]

                    snapshot = self._parse_snapshot_response(item, symbol, conid)
                    if snapshot:
                        new_snapshots[symbol] = snapshot

                        # Update cache
                        with self._cache_lock:
                            self._snapshot_cache[symbol] = snapshot

                            # Clean old cache entries
                            self._clean_cache()

                        # Notify callbacks
                        self._notify_data_update(snapshot)

            # Update statistics
            with self._lock:
                self._stats['snapshot_requests'] += 1
                self._stats['last_request_time'] = datetime.now()

            # Combine cached and new data
            result = {**cached_snapshots, **new_snapshots}
            return result

        except Exception as e:
            self.logger.error(f"Error getting market snapshot: {e}")
            with self._lock:
                self._stats['errors'] += 1
            return {}

    def get_historical_data(self, symbol: str, period: str, bar_size: str) -> List[HistoricalDataPoint]:
        """
        Get historical market data.

        Args:
            symbol: Symbol to get data for
            period: Time period (e.g., "1d", "1w", "1m", "1y")
            bar_size: Bar size (e.g., "1min", "5min", "1hour", "1day")

        Returns:
            List of historical data points
        """
        try:
            # Check cache first
            cache_key = f"{symbol}_{period}_{bar_size}"
            with self._cache_lock:
                if cache_key in self._historical_cache:
                    self._stats['cache_hits'] += 1
                    return self._historical_cache[cache_key]
                self._stats['cache_misses'] += 1

            # Check authentication
            if not getattr(self.session_manager, 'is_authenticated', lambda: False)():
                self.logger.error("Cannot get historical data: Not authenticated")
                return []

            # Get conid for symbol
            conid = self._symbol_to_conid(symbol)
            if not conid:
                self.logger.error(f"Could not find conid for symbol: {symbol}")
                return []

            # Apply rate limiting
            self._apply_rate_limit()

            # Make API request
            params = {
                'conid': conid,
                'period': period,
                'bar': bar_size
            }

            endpoint = "/iserver/marketdata/history"
            response = self._make_request('GET', endpoint, params=params)

            if not response:
                self.logger.error("Failed to get historical data: No response")
                with self._lock:
                    self._stats['errors'] += 1
                return []

            data = response.json()
            historical_data = []

            # Parse response
            for item in data.get('data', []):
                data_point = self._parse_historical_response(item)
                if data_point:
                    historical_data.append(data_point)

            # Update cache
            with self._cache_lock:
                self._historical_cache[cache_key] = historical_data

            # Update statistics
            with self._lock:
                self._stats['historical_requests'] += 1

            return historical_data

        except Exception as e:
            self.logger.error(f"Error getting historical data: {e}")
            with self._lock:
                self._stats['errors'] += 1
            return []

    def search_contracts(self, symbol: str, sec_type: str = "STK") -> List[Dict[str, Any]]:
        """
        Search for contracts by symbol.

        Args:
            symbol: Symbol to search for
            sec_type: Security type (STK, OPT, FUT, etc.)

        Returns:
            List of contract information
        """
        try:
            # Check authentication
            if not getattr(self.session_manager, 'is_authenticated', lambda: False)():
                self.logger.error("Cannot search contracts: Not authenticated")
                return []

            # Apply rate limiting
            self._apply_rate_limit()

            # Make API request
            params = {
                'symbol': symbol,
                'secType': sec_type
            }

            endpoint = "/iserver/secdef/search"
            response = self._make_request('GET', endpoint, params=params)

            if not response:
                self.logger.error("Failed to search contracts: No response")
                with self._lock:
                    self._stats['errors'] += 1
                return []

            data = response.json()

            # Update statistics
            with self._lock:
                self._stats['contract_searches'] += 1

            return data if isinstance(data, list) else []

        except Exception as e:
            self.logger.error(f"Error searching contracts: {e}")
            with self._lock:
                self._stats['errors'] += 1
            return []

    def get_option_chain(self, symbol: str, expiration: str) -> Dict[str, List[OptionContract]]:
        """
        Get option chain for a symbol.

        Args:
            symbol: Underlying symbol
            expiration: Expiration date (YYYYMMDD format)

        Returns:
            Dictionary with 'calls' and 'puts' lists
        """
        try:
            # Check authentication
            if not getattr(self.session_manager, 'is_authenticated', lambda: False)():
                self.logger.error("Cannot get option chain: Not authenticated")
                return {'calls': [], 'puts': []}

            # Get conid for symbol
            conid = self._symbol_to_conid(symbol)
            if not conid:
                self.logger.error(f"Could not find conid for symbol: {symbol}")
                return {'calls': [], 'puts': []}

            # Apply rate limiting
            self._apply_rate_limit()

            # Make API request
            params = {
                'conid': conid,
                'sectype': 'OPT',
                'month': expiration
            }

            endpoint = "/iserver/secdef/strikes"
            response = self._make_request('GET', endpoint, params=params)

            if not response:
                self.logger.error("Failed to get option chain: No response")
                with self._lock:
                    self._stats['errors'] += 1
                return {'calls': [], 'puts': []}

            data = response.json()

            # Parse response
            calls = []
            puts = []

            for strike_data in data.get('call', []):
                option = self._parse_option_contract(strike_data, symbol, 'CALL')
                if option:
                    calls.append(option)

            for strike_data in data.get('put', []):
                option = self._parse_option_contract(strike_data, symbol, 'PUT')
                if option:
                    puts.append(option)

            return {'calls': calls, 'puts': puts}

        except Exception as e:
            self.logger.error(f"Error getting option chain: {e}")
            with self._lock:
                self._stats['errors'] += 1
            return {'calls': [], 'puts': []}

    # ==========================================================================
    # PUBLIC UTILITY METHODS
    # ==========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Get market data statistics."""
        with self._lock:
            return {
                'module_state': self.state.name,
                'snapshot_requests': self._stats['snapshot_requests'],
                'historical_requests': self._stats['historical_requests'],
                'contract_searches': self._stats['contract_searches'],
                'cache_hits': self._stats['cache_hits'],
                'cache_misses': self._stats['cache_misses'],
                'cache_hit_rate': self._stats['cache_hits'] / max(1, self._stats['cache_hits'] + self._stats['cache_misses']),
                'errors': self._stats['errors'],
                'last_request_time': self._stats['last_request_time'].isoformat() if self._stats['last_request_time'] else None,
                'cached_snapshots': len(self._snapshot_cache),
                'cached_historical': len(self._historical_cache),
                'symbol_conid_mappings': len(self._symbol_conid_map),
                'subscription_updates': self._stats['subscription_updates'],
                'option_chain_updates': self._stats['option_chain_updates'],
                'calculated_metrics': self._stats['calculated_metrics'],
                'active_subscriptions': len(self._subscription_active),
                'registered_symbols': len(self._symbol_registry),
                'option_chain_cache_size': len(self._option_chain_cache),
                'calculated_metrics_cache_size': len(self._calculated_metrics_cache)
            }

    def add_data_callback(self, callback: Callable[[MarketDataSnapshot], None]):
        """Add callback for market data updates."""
        self._data_callbacks.append(callback)

    def add_error_callback(self, callback: Callable[[str, Dict], None]):
        """Add callback for error events."""
        self._error_callbacks.append(callback)

    def clear_cache(self):
        """Clear all caches."""
        with self._cache_lock:
            self._snapshot_cache.clear()
            self._historical_cache.clear()
            self._contract_cache.clear()
            self._option_chain_cache.clear()
            self._calculated_metrics_cache.clear()
        self.logger.info("Market data cache cleared")

    # ==========================================================================
    # SUBSCRIPTION MANAGEMENT METHODS
    # ==========================================================================

    def get_symbol_registry(self) -> Dict[str, SymbolConfig]:
        """Get the complete symbol registry."""
        return self._symbol_registry.copy()

    def get_symbols_by_frequency(self, frequency: UpdateFrequency) -> List[SymbolConfig]:
        """Get symbols filtered by update frequency."""
        return SymbolRegistry.get_symbols_by_frequency(frequency)

    def get_visible_symbols(self) -> List[SymbolConfig]:
        """Get only visible (non-hidden) symbols."""
        return SymbolRegistry.get_visible_symbols()

    def get_option_chain_symbols(self) -> List[SymbolConfig]:
        """Get all option chain symbols."""
        return SymbolRegistry.get_option_chain_symbols()

    def get_cached_option_chain(self, symbol: str, expiration: Optional[str] = None) -> Dict[str, List[OptionContract]]:
        """
        Get option chain for a symbol with caching.

        Args:
            symbol: Underlying symbol
            expiration: Expiration date (YYYYMMDD format), if None will use nearest

        Returns:
            Dictionary with 'calls' and 'puts' lists
        """
        try:
            # Check cache first
            if not expiration:
                # For now, use the nearest monthly expiration
                current_date = datetime.now()
                if current_date.day <= 15:
                    expiration = current_date.strftime("%Y%m")
                else:
                    next_month = current_date.replace(day=1) + timedelta(days=32)
                    expiration = next_month.strftime("%Y%m")

            cache_key = f"{symbol}_{expiration}"
            with self._cache_lock:
                if cache_key in self._option_chain_cache:
                    cached_data = self._option_chain_cache[cache_key]
                    cached_time = cached_data.get('timestamp')
                    if cached_time and isinstance(cached_time, datetime) and (datetime.now() - cached_time).seconds < 60:
                        return cached_data.get('data', {'calls': [], 'puts': []})

            # Get fresh data
            option_chain = self.get_option_chain(symbol, expiration)

            # Update cache
            with self._cache_lock:
                self._option_chain_cache[cache_key] = {
                    'data': option_chain,
                    'timestamp': datetime.now()
                }

            return option_chain

        except Exception as e:
            self.logger.error(f"Error getting option chain for {symbol}: {e}")
            self.error_handler.handle_error(e, "get_cached_option_chain")
            return {'calls': [], 'puts': []}

    def get_calculated_metric(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get a calculated metric value.

        Args:
            symbol: Metric symbol (e.g., GEX, DEX, OGL, SWAN, DIX)

        Returns:
            Metric value dictionary or None
        """
        with self._cache_lock:
            return self._calculated_metrics_cache.get(symbol)

    def update_subscription_config(self, config: SubscriptionConfig):
        """
        Update subscription configuration.

        Args:
            config: New subscription configuration
        """
        self.config.subscription_config = config
        self.logger.info("Subscription configuration updated")

        # Restart subscriptions if already running
        if self.state == ModuleState.RUNNING:
            self._stop_subscriptions()
            self._start_subscriptions()

    def is_subscribed(self, symbol: str) -> bool:
        """
        Check if a symbol is currently subscribed.

        Args:
            symbol: Symbol to check

        Returns:
            True if symbol is subscribed
        """
        if symbol in self._symbol_registry:
            symbol_config = self._symbol_registry[symbol]
            frequency_str = symbol_config.update_frequency.value
            return self._subscription_active.get(frequency_str, False)
        return False

    # ==========================================================================
    # PRIVATE HELPER METHODS
    # ==========================================================================

    def _symbol_to_conid(self, symbol: str) -> Optional[int]:
        """Convert symbol to contract ID."""
        # Check cache first
        if symbol in self._symbol_conid_map:
            return self._symbol_conid_map[symbol]

        # Search for contract
        contracts = self.search_contracts(symbol)
        if contracts:
            # Use the first contract found
            conid = contracts[0].get('conid')
            if conid:
                self._symbol_conid_map[symbol] = conid
                return conid

        # Fallback to common symbols
        symbol_to_conid_map = {
            'SPY': 756733,
            'QQQ': 320227571,
            'IWM': 9579970,
            'VIX': 13455763,
            'SPX': 416904,
            'NDX': 416905
        }

        conid = symbol_to_conid_map.get(symbol.upper())
        if conid:
            self._symbol_conid_map[symbol] = conid

        return conid

    def _apply_rate_limit(self):
        """Apply rate limiting to requests."""
        with self._request_lock:
            current_time = time.time()
            time_since_last = current_time - self._last_request_time

            if time_since_last < self.config.rate_limit_delay:
                time.sleep(self.config.rate_limit_delay - time_since_last)

            self._last_request_time = time.time()

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        """
        Make HTTP request to IBKR API.

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request parameters

        Returns:
            Response object or None
        """
        try:
            url = f"{self.api_base}{endpoint}"
            timeout = self.config.default_timeout

            for attempt in range(self.config.retry_attempts):
                try:
                    session = getattr(self.session_manager, 'session', None)
                    if session is None:
                        raise ValueError("Session not available")

                    if method.upper() == 'GET':
                        response = session.get(url, timeout=timeout, **kwargs)
                    elif method.upper() == 'POST':
                        response = session.post(url, timeout=timeout, **kwargs)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")

                    if response.status_code == 200:
                        return response
                    else:
                        self.logger.warning(f"Request failed: {response.status_code} - {response.text}")

                except requests.exceptions.RequestException as e:
                    self.logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                    if attempt < self.config.retry_attempts - 1:
                        time.sleep(self.config.retry_delay)
                    else:
                        raise e

            return None

        except Exception as e:
            self.logger.error(f"Error making {method} request to {endpoint}: {e}")
            return None

    def _parse_snapshot_response(self, data: Dict, symbol: str, conid: int) -> Optional[MarketDataSnapshot]:
        """Parse snapshot response from IBKR API."""
        try:
            snapshot = MarketDataSnapshot(
                symbol=symbol,
                conid=conid,
                last_price=self._parse_float(data.get('31')),
                bid=self._parse_float(data.get('84')),
                ask=self._parse_float(data.get('86')),
                bid_size=self._parse_int(data.get('88')),
                ask_size=self._parse_int(data.get('85')),
                volume=self._parse_int(data.get('7059')),
                high=self._parse_float(data.get('70')),
                low=self._parse_float(data.get('71')),
                open=self._parse_float(data.get('7051')),
                close=self._parse_float(data.get('7052'))
            )

            return snapshot

        except Exception as e:
            self.logger.error(f"Error parsing snapshot response: {e}")
            return None

    def _parse_historical_response(self, data: Dict) -> Optional[HistoricalDataPoint]:
        """Parse historical data response from IBKR API."""
        try:
            # IBKR historical data format may vary
            date_str = data.get('date') or data.get('t')
            if not date_str:
                return None

            # Parse date (format may be YYYYMMDD or timestamp)
            if isinstance(date_str, str) and len(date_str) == 8:
                date = datetime.strptime(date_str, '%Y%m%d')
            else:
                date = datetime.fromtimestamp(float(date_str))

            data_point = HistoricalDataPoint(
                date=date,
                open=float(data.get('o', 0)),
                high=float(data.get('h', 0)),
                low=float(data.get('l', 0)),
                close=float(data.get('c', 0)),
                volume=int(data.get('v', 0))
            )

            return data_point

        except Exception as e:
            self.logger.error(f"Error parsing historical response: {e}")
            return None

    def _parse_option_contract(self, data: Dict, symbol: str, right: str) -> Optional[OptionContract]:
        """Parse option contract data."""
        try:
            contract = OptionContract(
                conid=data.get('conid', 0),
                symbol=symbol,
                right=right,
                strike=float(data.get('strike', 0)),
                expiration=datetime.strptime(data.get('expiry', ''), '%Y%m%d'),
                multiplier=float(data.get('multiplier', 100))
            )

            return contract

        except Exception as e:
            self.logger.error(f"Error parsing option contract: {e}")
            return None

    def _parse_float(self, value: Any) -> Optional[float]:
        """Parse float value from IBKR response."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _parse_int(self, value: Any) -> Optional[int]:
        """Parse integer value from IBKR response."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def _clean_cache(self):
        """Clean old cache entries."""
        current_time = datetime.now()

        # Clean snapshot cache
        expired_keys = [
            key for key, snapshot in self._snapshot_cache.items()
            if (current_time - snapshot.timestamp).seconds > self.config.cache_duration
        ]
        for key in expired_keys:
            del self._snapshot_cache[key]

        # Limit cache size
        if len(self._snapshot_cache) > self.config.max_cache_size:
            # Remove oldest entries
            sorted_items = sorted(
                self._snapshot_cache.items(),
                key=lambda x: x[1].timestamp
            )
            for key, _ in sorted_items[:len(self._snapshot_cache) - self.config.max_cache_size]:
                del self._snapshot_cache[key]

    def _notify_data_update(self, snapshot: MarketDataSnapshot):
        """Notify callbacks of data update."""
        for callback in self._data_callbacks:
            try:
                callback(snapshot)
            except Exception as e:
                self.logger.error(f"Error in data callback: {e}")

    def _notify_error(self, error_type: str, error_data: Dict):
        """Notify callbacks of error events."""
        for callback in self._error_callbacks:
            try:
                callback(error_type, error_data)
            except Exception as e:
                self.logger.error(f"Error in error callback: {e}")


    def _start_subscriptions(self):
        """Start subscription threads for each update frequency."""
    try:
        self.logger.info("Starting market data subscriptions...")

        # Start a thread for each frequency tier
        for frequency in UpdateFrequency:
            # Skip calculated metrics for now
            if frequency == UpdateFrequency.BATCH:
                continue

            # Check if this frequency is enabled in config
            if not self._is_frequency_enabled(frequency):
                self.logger.debug(f"Skipping {frequency.value} updates (disabled in config)")
                continue

            # Get symbols for this frequency
            symbols = SymbolRegistry.get_symbols_by_frequency(frequency)
            if not symbols:
                self.logger.debug(f"No symbols for {frequency.value} updates")
                continue

            # Filter out calculated metrics
            symbols = [s for s in symbols if s.symbol_type != SymbolType.CALCULATED]
            if not symbols:
                self.logger.debug(f"No non-calculated symbols for {frequency.value} updates")
                continue

            # Start subscription thread
            frequency_str = frequency.value
            self._subscription_active[frequency_str] = True
            thread = threading.Thread(
                target=self._subscription_loop,
                args=(frequency, symbols),
                name=f"MarketData-{frequency_str}",
                daemon=True
            )
            self._subscription_threads[frequency_str] = thread
            thread.start()

            self.logger.info(f"Started {frequency_str} subscription thread for {len(symbols)} symbols")

        # Start option chain update thread
        if self.config.subscription_config.enable_options:
            self._start_option_chain_subscriptions()

        # Start calculated metrics thread
        self._start_calculated_metrics_thread()

    except Exception as e:
        self.logger.error(f"Error starting subscriptions: {e}")
        self.error_handler.handle_error(e, "_start_subscriptions")

    def _stop_subscriptions(self):
        """Stop all subscription threads."""
        try:
            self.logger.info("Stopping market data subscriptions...")

            # Signal all threads to stop
            for frequency in self._subscription_active:
                self._subscription_active[frequency] = False

            # Wait for all threads to finish
            for frequency_str, thread in self._subscription_threads.items():
                if thread.is_alive():
                    self.logger.debug(f"Waiting for {frequency_str} thread to stop...")
                    thread.join(timeout=5)
                    if thread.is_alive():
                        self.logger.warning(f"{frequency_str} thread did not stop gracefully")

            # Clear thread references
            self._subscription_threads.clear()
            self._subscription_active.clear()

            self.logger.info("All subscription threads stopped")

        except Exception as e:
            self.logger.error(f"Error stopping subscriptions: {e}")
            self.error_handler.handle_error(e, "_stop_subscriptions")

    def _is_frequency_enabled(self, frequency: UpdateFrequency) -> bool:
        """Check if a frequency tier is enabled in the configuration."""
        config = self.config.subscription_config
        return {
            UpdateFrequency.CRITICAL: config.enable_critical,
            UpdateFrequency.HIGH: config.enable_high,
            UpdateFrequency.NORMAL: config.enable_normal,
            UpdateFrequency.LOW: config.enable_low,
            UpdateFrequency.BACKGROUND: config.enable_background,
            UpdateFrequency.BATCH: True  # Always enable batch for calculated metrics
        }.get(frequency, True)

    def _subscription_loop(self, frequency: UpdateFrequency, symbols: List[SymbolConfig]):
        """Main subscription loop for a specific frequency."""
        update_interval = self._frequency_to_seconds[frequency]
        frequency_str = frequency.value
        self.logger.debug(f"Starting {frequency_str} subscription loop ({update_interval}s interval)")

        try:
            while self._subscription_active.get(frequency_str, False) and not self._shutdown_event.is_set():
                try:
                    # Check authentication
                    if not getattr(self.session_manager, 'is_authenticated', lambda: False)():
                        self.logger.debug(f"Not authenticated, skipping {frequency.value} update")
                        time.sleep(update_interval)
                        continue

                    # Filter symbols based on visibility settings
                    filtered_symbols = symbols
                    if not self.config.subscription_config.enable_hidden:
                        filtered_symbols = [s for s in symbols if not s.is_hidden]

                    if not filtered_symbols:
                        time.sleep(update_interval)
                        continue

                    # Batch symbols to respect API limits
                    batch_size = self.config.subscription_config.batch_size_limit
                    for i in range(0, len(filtered_symbols), batch_size):
                        if not self._subscription_active.get(frequency_str, False) or self._shutdown_event.is_set():
                            break

                        batch = filtered_symbols[i:i + batch_size]
                        self._update_symbols_batch(batch, frequency)

                        # Update statistics
                        with self._lock:
                            self._stats['subscription_updates'] += 1

                    # Sleep until next update
                    time.sleep(update_interval)

                except Exception as e:
                    self.logger.error(f"Error in {frequency.value} subscription loop: {e}")
                    self.error_handler.handle_error(e, "_subscription_loop")
                    time.sleep(update_interval)

        except Exception as e:
            self.logger.error(f"Fatal error in {frequency.value} subscription loop: {e}")
            self.error_handler.handle_error(e, "_subscription_loop")

        self.logger.debug(f"{frequency.value} subscription loop ended")

    def _update_symbols_batch(self, symbols: List[SymbolConfig], frequency: UpdateFrequency):
        """Update a batch of symbols."""
        try:
            # Separate regular symbols from option chains
            regular_symbols = [s for s in symbols if not s.is_option_chain]
            option_symbols = [s for s in symbols if s.is_option_chain]

            # Update regular symbols
            if regular_symbols:
                symbol_names = [s.symbol for s in regular_symbols]
                snapshots = self.get_market_snapshot(symbol_names)

                # Notify callbacks for each updated symbol
                for symbol, snapshot in snapshots.items():
                    if snapshot:
                        self._notify_data_update(snapshot)

            # Update option chains
            if option_symbols and self.config.subscription_config.enable_options:
                for option_symbol in option_symbols:
                    if option_symbol.option_underlying:
                        self._update_option_chain(option_symbol, frequency)

        except Exception as e:
            self.logger.error(f"Error updating symbols batch: {e}")
            self.error_handler.handle_error(e, "_update_symbols_batch")

    def _start_option_chain_subscriptions(self):
        """Start option chain subscription thread."""
        try:
            option_symbols = SymbolRegistry.get_option_chain_symbols()
            if not option_symbols:
                return

            # Create a dedicated thread for option chain updates
            self._subscription_active['option_chains'] = True
            thread = threading.Thread(
                target=self._option_chain_loop,
                args=(option_symbols,),
                name="MarketData-OptionChains",
                daemon=True
            )
            self._subscription_threads['option_chains'] = thread
            thread.start()

            self.logger.info(f"Started option chain subscription thread for {len(option_symbols)} chains")

        except Exception as e:
            self.logger.error(f"Error starting option chain subscriptions: {e}")
            self.error_handler.handle_error(e, "_start_option_chain_subscriptions")

    def _option_chain_loop(self, option_symbols: List[SymbolConfig]):
        """Main option chain subscription loop."""
        # Determine update frequency based on the underlying symbol's frequency
        update_intervals = {}
        for option_symbol in option_symbols:
            if option_symbol.option_underlying in self._symbol_registry:
                underlying_config = self._symbol_registry[option_symbol.option_underlying]
                update_intervals[option_symbol.symbol] = self._frequency_to_seconds.get(
                    underlying_config.update_frequency, FREQUENCY_5_SECONDS
                )
            else:
                update_intervals[option_symbol.symbol] = FREQUENCY_5_SECONDS

        try:
            while self._subscription_active.get('option_chains', False) and not self._shutdown_event.is_set():
                try:
                    # Check authentication
                    if not getattr(self.session_manager, 'is_authenticated', lambda: False)():
                        self.logger.debug("Not authenticated, skipping option chain update")
                        time.sleep(5)
                        continue

                    # Update each option chain based on its frequency
                    for option_symbol in option_symbols:
                        if not self._subscription_active.get('option_chains', False) or self._shutdown_event.is_set():
                            break

                        if option_symbol.symbol in update_intervals:
                            self._update_option_chain(option_symbol, UpdateFrequency.HIGH)
                            time.sleep(1)  # Small delay between option chain updates

                    # Sleep before next cycle
                    time.sleep(5)

                except Exception as e:
                    self.logger.error(f"Error in option chain loop: {e}")
                    self.error_handler.handle_error(e, "_option_chain_loop")
                    time.sleep(5)

        except Exception as e:
            self.logger.error(f"Fatal error in option chain loop: {e}")
            self.error_handler.handle_error(e, "_option_chain_loop")

        self.logger.debug("Option chain subscription loop ended")

    def _update_option_chain(self, option_symbol: SymbolConfig, frequency: UpdateFrequency):
        """Update an option chain."""
        try:
            if not option_symbol.option_underlying:
                return

            underlying = option_symbol.option_underlying

            # Get current expiration or determine the appropriate one
            expiration = option_symbol.option_expiration
            if not expiration:
                # For now, use the nearest monthly expiration
                # In a real implementation, this would be more sophisticated
                current_date = datetime.now()
                if current_date.day <= 15:
                    # Current month expiration
                    expiration = current_date.strftime("%Y%m")
                else:
                    # Next month expiration
                    next_month = current_date.replace(day=1) + timedelta(days=32)
                    expiration = next_month.strftime("%Y%m")

            # Check cache first
            cache_key = f"{underlying}_{expiration}"
            with self._cache_lock:
                if cache_key in self._option_chain_cache:
                    cached_data = self._option_chain_cache[cache_key]
                    cached_time = cached_data.get('timestamp')
                    if cached_time and isinstance(cached_time, datetime) and (datetime.now() - cached_time).seconds < 60:  # Cache for 1 minute
                        return

            # Get option chain
            option_chain = self.get_option_chain(underlying, expiration)

            # Update cache
            with self._cache_lock:
                self._option_chain_cache[cache_key] = {
                    'data': option_chain,
                    'timestamp': datetime.now()
                }

            # Update statistics
            with self._lock:
                self._stats['option_chain_updates'] += 1

            self.logger.debug(f"Updated option chain for {underlying} {expiration}")

        except Exception as e:
            self.logger.error(f"Error updating option chain for {option_symbol.symbol}: {e}")
            self.error_handler.handle_error(e, "_update_option_chain")

    def _start_calculated_metrics_thread(self):
        """Start calculated metrics thread."""
        try:
            calculated_symbols = [s for s in self._symbol_registry.values()
                                if s.symbol_type == SymbolType.CALCULATED]
            if not calculated_symbols:
                return

            # Create a dedicated thread for calculated metrics
            self._subscription_active['calculated_metrics'] = True
            thread = threading.Thread(
                target=self._calculated_metrics_loop,
                args=(calculated_symbols,),
                name="MarketData-CalculatedMetrics",
                daemon=True
            )
            self._subscription_threads['calculated_metrics'] = thread
            thread.start()

            self.logger.info(f"Started calculated metrics thread for {len(calculated_symbols)} metrics")

        except Exception as e:
            self.logger.error(f"Error starting calculated metrics thread: {e}")
            self.error_handler.handle_error(e, "_start_calculated_metrics_thread")

    def _calculated_metrics_loop(self, calculated_symbols: List[SymbolConfig]):
        """Main calculated metrics loop."""
        try:
            while self._subscription_active.get('calculated_metrics', False) and not self._shutdown_event.is_set():
                try:
                    # Check authentication
                    if not getattr(self.session_manager, 'is_authenticated', lambda: False)():
                        self.logger.debug("Not authenticated, skipping calculated metrics update")
                        time.sleep(60)
                        continue

                    # Update each calculated metric based on its frequency
                    for metric_symbol in calculated_symbols:
                        if not self._subscription_active.get('calculated_metrics', False) or self._shutdown_event.is_set():
                            break

                        update_interval = self._frequency_to_seconds.get(
                            metric_symbol.update_frequency, FREQUENCY_60_SECONDS
                        )

                        # Calculate the metric
                        self._calculate_metric(metric_symbol)

                        # Update statistics
                        with self._lock:
                            self._stats['calculated_metrics'] += 1

                    # Sleep before next cycle
                    time.sleep(60)

                except Exception as e:
                    self.logger.error(f"Error in calculated metrics loop: {e}")
                    self.error_handler.handle_error(e, "_calculated_metrics_loop")
                    time.sleep(60)

        except Exception as e:
            self.logger.error(f"Fatal error in calculated metrics loop: {e}")
            self.error_handler.handle_error(e, "_calculated_metrics_loop")

        self.logger.debug("Calculated metrics loop ended")

    def _calculate_metric(self, metric_symbol: SymbolConfig):
        """Calculate a custom metric."""
        try:
            # This is a placeholder for calculated metrics
            # In a real implementation, this would calculate metrics like GEX, DEX, etc.

            # For now, just create a simple mock metric
            metric_value = {
                'symbol': metric_symbol.symbol,
                'value': 0.0,
                'timestamp': datetime.now().isoformat(),
                'description': metric_symbol.description
            }

            # Update cache
            self._calculated_metrics_cache[metric_symbol.symbol] = metric_value

            self.logger.debug(f"Calculated metric {metric_symbol.symbol}: {metric_value['value']}")

        except Exception as e:
            self.logger.error(f"Error calculating metric {metric_symbol.symbol}: {e}")
            self.error_handler.handle_error(e, "_calculate_metric")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level singleton instance (if needed)
_module_instance: Optional[MarketDataManager] = None
_module_lock = Lock()


def get_module_instance(session_manager, config: Optional[MarketDataConfig] = None) -> MarketDataManager:
    """
    Get singleton module instance.

    Args:
        session_manager: SessionManager instance
        config: Module configuration (required for first call)

    Returns:
        MarketDataManager singleton instance
    """
    global _module_instance

    with _module_lock:
        if _module_instance is None:
            if config is None:
                raise ValueError("Configuration required for first module creation")
            _module_instance = MarketDataManager(session_manager, config)

        return _module_instance


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_market_data_manager(session_manager, **kwargs) -> MarketDataManager:
    """
    Create a MarketDataManager instance with configuration.

    Args:
        session_manager: SessionManager instance
        **kwargs: Configuration parameters

    Returns:
        MarketDataManager instance
    """
    config = MarketDataConfig(**kwargs)
    return MarketDataManager(session_manager, config)


if __name__ == "__main__":
    # Example usage
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    def data_updated(snapshot):
        print(f"Data update: {snapshot.symbol} - {snapshot.last_price}")

    def error_occurred(error_type, error_data):
        print(f"Error {error_type}: {error_data}")

    # Create session and market data managers
    if SessionManager is None:
        print("SessionManager not available - create mock for testing")
        from unittest.mock import Mock
        session_manager = Mock()
        session_manager.is_authenticated.return_value = True
        session_manager.api_base = "https://localhost:5000/v1/api"
        session_manager.session = Mock()
    else:
        session_manager = SessionManager()

    market_data_manager = MarketDataManager(session_manager)

    market_data_manager.add_data_callback(data_updated)
    market_data_manager.add_error_callback(error_occurred)

    try:
        # Start session manager if available
        if hasattr(session_manager, 'start'):
            session_manager.start()

        # Check authentication
        if getattr(session_manager, 'is_authenticated', lambda: False)():
            print("✅ Authenticated")

            # Get market data
            snapshots = market_data_manager.get_market_snapshot(['SPY', 'QQQ'])
            for symbol, snapshot in snapshots.items():
                print(f"{symbol}: {snapshot.last_price} (Bid: {snapshot.bid}, Ask: {snapshot.ask})")

            # Get historical data
            historical = market_data_manager.get_historical_data('SPY', '1d', '1hour')
            print(f"Historical data points: {len(historical)}")

            # Search contracts
            contracts = market_data_manager.search_contracts('SPY')
            print(f"Found {len(contracts)} contracts for SPY")

        else:
            print("❌ Not authenticated. Please login via browser:")
            print("https://localhost:5000")

        # Keep running for demonstration
        time.sleep(30)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        if hasattr(session_manager, 'stop'):
            session_manager.stop()