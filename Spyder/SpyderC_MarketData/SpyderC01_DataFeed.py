#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC01_DataFeed.py
Purpose: Central market data feed orchestrator with provider abstraction layer

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-02-25 Time: 16:00:00

Module Description:
    Central data feed orchestrator for the Spyder trading system.  Manages all
    market data operations by coordinating between pluggable data providers,
    the MarketDataCache, and subscriber callbacks.

    Provider Abstraction:
        ``MarketDataProvider`` is the abstract base class that any data source
        must implement.  The concrete provider is:

        - **DatabentoProvider** — wraps ``SpyderC26_DatabentoClient``
          for OPRA options + equities via Databento.

        The active provider is selected from ``config/config.py``
        ``DATA_PROVIDER`` setting (default ``"databento"``).

    Data flow:
        Provider stream → _on_provider_data() → validate → MarketTick
        → cache → notify subscribers → EventManager publish

Change Log:
    2026-02-25 (Phase 3 — Tradier+Databento migration):
        - Replaced IBKR (SpyderB01_SpyderClient / SpyderC07_MarketDataHub)
          with provider abstraction layer
        - Added DataSource.DATABENTO to enum
        - Added MarketDataProvider ABC with DatabentoProvider
        - Rewired get_historical_data() to use Databento historical REST
        - Updated singleton factory and __main__ test block
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any, Callable, Set, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import TradingTimeUtils
from Spyder.SpyderU_Utilities.SpyderU09_DataTypes import MarketDataType
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager, EventType, Event
from Spyder.SpyderC_MarketData.SpyderC16_MarketDataCache import MarketDataCache, DataGranularity
from Spyder.SpyderC_MarketData.SpyderC06_DataValidator import DataValidator

# Provider imports (defensive — providers may not be installed)
try:
    from Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient import (
        DatabentoClient,
        MarketDataUpdate as DatabentoMarketUpdate,
        ConnectionStatus as DatabentoConnectionStatus,
        create_databento_client_from_env,
    )
    HAS_DATABENTO = True
except ImportError:
    HAS_DATABENTO = False
    DatabentoClient = None

# ==============================================================================
# CONFIGURATION DEFAULTS
# ==============================================================================
DEFAULT_FEED_CONFIG = {
    'cache_enabled': True,
    'validation_enabled': True,
    'buffer_size': 1000,
    'update_interval': 0.1,  # 100ms
    'heartbeat_interval': 30,
    'error_threshold': 10,
    'custom_metrics': {
        'gex': {'enabled': True, 'module': 'SpyderC15_GEXDEXCalculator'},
        'dix': {'enabled': True, 'module': 'SpyderS01_DIXCalculator'},
        'swan': {'enabled': True, 'module': 'SpyderS06_BlackSwanDataCollector'}
    }
}

# Symbol Groups for Efficient Management
SYMBOL_GROUPS = {
    'CORE': ['SPY', 'SPX', '/ES'],
    'VOLATILITY': ['VIX', 'VIX9D', 'VXV', 'VXMT', 'VVIX', 'UVXY'],
    'INTERNALS': ['TICK-NYSE', 'TRIN-NYSE', 'ADD-NYSE', 'CPC', 'PCALL', 'SKEW'],
    'INDICES': ['DIA', 'QQQ', 'IWM'],
    'FIXED_INCOME': ['TLT', 'LQD'],
    'CORRELATIONS': ['DXY', 'GLD']
}


# ==============================================================================
# ENUMS
# ==============================================================================
class DataFeedStatus(Enum):
    """Data feed connection status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"
    DEGRADED = "degraded"


class DataSource(Enum):
    """Available data sources."""
    DATABENTO = "databento"
    CACHE = "cache"
    CUSTOM = "custom"
    SYNTHETIC = "synthetic"
    # Legacy alias — kept so code referencing DataSource.IBKR still parses
    IBKR = "ibkr"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MarketTick:
    """Enhanced market tick data structure."""
    symbol: str
    timestamp: datetime
    price: float
    size: int
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    volume: Optional[int] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    vwap: Optional[float] = None
    source: DataSource = DataSource.DATABENTO
    quality: str = "realtime"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'size': self.size,
            'bid': self.bid,
            'ask': self.ask,
            'bid_size': self.bid_size,
            'ask_size': self.ask_size,
            'volume': self.volume,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'vwap': self.vwap,
            'source': self.source.value,
            'quality': self.quality
        }


@dataclass
class DataFeedConfig:
    """Enhanced data feed configuration."""
    provider: str = "databento"
    cache_enabled: bool = True
    validation_enabled: bool = True
    buffer_size: int = 1000
    update_interval: float = 0.1
    heartbeat_interval: int = 30
    error_threshold: int = 10
    custom_metrics_config: Dict[str, Any] = field(default_factory=dict)
    # Databento-specific
    databento_schema: str = "mbp-1"
    databento_dataset: str = "OPRA.PILLAR"

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'DataFeedConfig':
        """Create from dictionary, ignoring unknown keys."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in config_dict.items() if k in valid_keys}
        return cls(**filtered)


# ==============================================================================
# PROVIDER ABSTRACTION
# ==============================================================================
class MarketDataProvider(ABC):
    """
    Abstract base class for market data providers.

    All providers must implement connect/disconnect, subscribe/unsubscribe,
    and expose ``is_connected`` and ``active_source`` properties.

    Data is delivered via the ``on_data`` callback set by the DataFeedManager.
    """

    def __init__(self) -> None:
        self.on_data: Optional[Callable[[MarketTick], None]] = None
        self.on_status_change: Optional[Callable[[DataFeedStatus], None]] = None

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Return True when the provider is actively delivering data."""
        ...

    @property
    @abstractmethod
    def active_source(self) -> DataSource:
        """Return the DataSource enum for ticks produced by this provider."""
        ...

    @abstractmethod
    def connect(self) -> bool:
        """Start the provider — called by DataFeedManager.start()."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Stop the provider — called by DataFeedManager.stop()."""
        ...

    @abstractmethod
    def subscribe(self, symbol: str) -> bool:
        """Request data for *symbol*."""
        ...

    @abstractmethod
    def unsubscribe(self, symbol: str) -> bool:
        """Cancel data for *symbol*."""
        ...

    def get_historical(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        granularity: str = "1min",
    ) -> pd.DataFrame:
        """Return historical data (override if provider supports it)."""
        return pd.DataFrame()


# ==============================================================================
# DATABENTO PROVIDER
# ==============================================================================
class DatabentoProvider(MarketDataProvider):
    """
    Wraps ``SpyderC26_DatabentoClient`` as a ``MarketDataProvider``.

    Databento streams all options for a set of underlyings.  Equities (SPY,
    VIX, etc.) are subscribed individually via raw_symbol.

    Historical data is served by Databento's REST API.
    """

    # Symbols that should be streamed as equities (not options underlyings)
    EQUITY_SYMBOLS: Set[str] = {
        'SPY', 'QQQ', 'IWM', 'DIA', 'TLT', 'LQD', 'GLD',
        'UVXY', 'VIX', 'VIX9D', 'VXV', 'VXMT', 'VVIX',
    }

    def __init__(
        self,
        schema: str = "mbp-1",
        dataset: str = "OPRA.PILLAR",
    ) -> None:
        super().__init__()

        if not HAS_DATABENTO:
            raise ImportError(
                "databento package not installed.  Run: pip install databento"
            )

        self._logger = SpyderLogger.get_logger(f"{__name__}.DatabentoProvider")
        self._schema = schema
        self._dataset = dataset
        self._client: Optional[DatabentoClient] = None
        self._subscribed_symbols: Set[str] = set()
        self._started = False

    # ------------------------------------------------------------------
    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    @property
    def active_source(self) -> DataSource:
        return DataSource.DATABENTO

    def connect(self) -> bool:
        """Create the Databento client and start live streaming."""
        try:
            self._client = create_databento_client_from_env()

            # Wire callbacks
            self._client.on_quote = self._on_quote
            self._client.on_trade = self._on_trade
            self._client.on_ohlcv = self._on_ohlcv
            self._client.on_status_change = self._on_connection_status

            # Separate equity vs option underlying symbols
            underlyings: List[str] = []
            equity_symbols: List[str] = []
            for sym in self._subscribed_symbols:
                if sym in self.EQUITY_SYMBOLS:
                    equity_symbols.append(sym)
                else:
                    underlyings.append(sym)

            # Start live stream
            if underlyings or equity_symbols:
                self._client.start_live(
                    underlyings=underlyings or None,
                    symbols=equity_symbols or None,
                    schema=self._schema,
                    dataset=self._dataset,
                )
            else:
                self._client.start_live(
                    underlyings=["SPY"],
                    schema=self._schema,
                    dataset=self._dataset,
                )

            self._started = True
            self._logger.info("DatabentoProvider connected")
            return True

        except Exception as e:
            self._logger.error(f"DatabentoProvider connect failed: {e}")
            return False

    def disconnect(self) -> None:
        if self._client:
            self._client.stop_live()
            self._client = None
        self._started = False
        self._logger.info("DatabentoProvider disconnected")

    def subscribe(self, symbol: str) -> bool:
        self._subscribed_symbols.add(symbol)
        return True

    def unsubscribe(self, symbol: str) -> bool:
        self._subscribed_symbols.discard(symbol)
        return True

    def get_historical(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        granularity: str = "1min",
    ) -> pd.DataFrame:
        """Fetch historical bars from Databento REST API."""
        if self._client is None:
            self._client = create_databento_client_from_env()

        schema_map = {
            'tick': 'trades',
            '1s': 'ohlcv-1s',
            '1min': 'ohlcv-1m',
            '5min': 'ohlcv-1m',  # fetch 1m then resample
            '1hour': 'ohlcv-1h',
            'daily': 'ohlcv-1d',
        }
        db_schema = schema_map.get(granularity, 'ohlcv-1m')

        try:
            df = self._client.get_historical_bars(
                symbols=[symbol],
                start=start.strftime("%Y-%m-%dT%H:%M:%S"),
                end=end.strftime("%Y-%m-%dT%H:%M:%S"),
                schema=db_schema,
            )
            if granularity == '5min' and df is not None and not df.empty:
                df = df.resample('5min').agg({
                    col: ('sum' if col == 'volume' else 'last')
                    for col in df.columns
                }).dropna()
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            self._logger.error(f"Historical data fetch failed for {symbol}: {e}")
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # Databento callbacks → MarketTick
    # ------------------------------------------------------------------
    def _on_quote(self, update: 'DatabentoMarketUpdate') -> None:
        if not self.on_data:
            return
        data = update.data
        bid = data.get('bid_price')
        ask = data.get('ask_price')
        price = round((bid + ask) / 2, 4) if bid and ask else (bid or ask or 0.0)
        tick = MarketTick(
            symbol=update.symbol,
            timestamp=update.datetime,
            price=price,
            size=data.get('bid_size', 0),
            bid=bid,
            ask=ask,
            bid_size=data.get('bid_size'),
            ask_size=data.get('ask_size'),
            source=DataSource.DATABENTO,
            quality="realtime",
        )
        self.on_data(tick)

    def _on_trade(self, update: 'DatabentoMarketUpdate') -> None:
        if not self.on_data:
            return
        data = update.data
        tick = MarketTick(
            symbol=update.symbol,
            timestamp=update.datetime,
            price=data.get('price', 0.0),
            size=data.get('size', 0),
            volume=data.get('volume'),
            source=DataSource.DATABENTO,
            quality="realtime",
        )
        self.on_data(tick)

    def _on_ohlcv(self, update: 'DatabentoMarketUpdate') -> None:
        if not self.on_data:
            return
        data = update.data
        tick = MarketTick(
            symbol=update.symbol,
            timestamp=update.datetime,
            price=data.get('close', 0.0),
            size=0,
            open=data.get('open'),
            high=data.get('high'),
            low=data.get('low'),
            close=data.get('close'),
            volume=data.get('volume'),
            vwap=data.get('vwap'),
            source=DataSource.DATABENTO,
            quality="realtime",
        )
        self.on_data(tick)

    def _on_connection_status(self, status) -> None:
        if not self.on_status_change:
            return
        status_map = {
            'connected': DataFeedStatus.CONNECTED,
            'streaming': DataFeedStatus.CONNECTED,
            'connecting': DataFeedStatus.CONNECTING,
            'reconnecting': DataFeedStatus.CONNECTING,
            'disconnected': DataFeedStatus.DISCONNECTED,
            'stopped': DataFeedStatus.DISCONNECTED,
            'error': DataFeedStatus.ERROR,
        }
        feed_status = status_map.get(status.value, DataFeedStatus.ERROR)
        self.on_status_change(feed_status)


# ==============================================================================
# PROVIDER FACTORY
# ==============================================================================
def create_provider(
    provider_name: str,
    config: Optional['DataFeedConfig'] = None,
) -> MarketDataProvider:
    """
    Create a ``MarketDataProvider`` by name.

    Args:
        provider_name: ``"databento"`` — the only supported provider.
        config: Optional feed configuration for provider-specific settings.

    Returns:
        Configured ``MarketDataProvider`` instance.

    Raises:
        ValueError: If the provider name is unknown or not installed.
    """
    name = provider_name.lower().strip()
    cfg = config or DataFeedConfig()

    if name == "databento":
        if not HAS_DATABENTO:
            raise ValueError(
                "Databento provider requested but databento package is not "
                "installed.  Run: pip install databento"
            )
        return DatabentoProvider(
            schema=cfg.databento_schema,
            dataset=cfg.databento_dataset,
        )

    else:
        raise ValueError(
            f"Unknown provider '{provider_name}'.  "
            f"Supported: 'databento'."
        )

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class DataFeedManager:
    """
    Central data feed orchestrator with provider abstraction.

    Coordinates between:
    - A pluggable ``MarketDataProvider`` (Databento)
    - ``MarketDataCache`` for efficient storage
    - Custom metric calculators
    - Event-based distribution system

    Usage::

        from SpyderC_MarketData.SpyderC01_DataFeed import DataFeedManager

        feed = DataFeedManager(provider="databento")
        feed.subscribe("SPY", my_callback)
        feed.start()
    """

    def __init__(
        self,
        provider: Optional[Union[str, MarketDataProvider]] = None,
        event_manager: Optional[EventManager] = None,
        config: Optional[Union[DataFeedConfig, Dict]] = None,
    ):
        """
        Initialize enhanced data feed manager.

        Args:
            provider: Provider name (``"databento"``) or a
                pre-built ``MarketDataProvider`` instance.  Defaults to the
                value in ``config/config.py`` → ``DATA_PROVIDER``.
            event_manager: Shared event manager instance.
            config: Feed configuration dict or ``DataFeedConfig``.
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        if isinstance(config, dict):
            self.config = DataFeedConfig.from_dict(config)
        else:
            self.config = config or DataFeedConfig()

        # Core components
        self.event_manager = event_manager or EventManager()

        # Provider
        if isinstance(provider, MarketDataProvider):
            self._provider = provider
        else:
            provider_name = provider or self._resolve_provider_name()
            self._provider = create_provider(provider_name, self.config)

        # Wire provider callbacks
        self._provider.on_data = self._on_provider_data
        self._provider.on_status_change = self._on_provider_status

        # Cache
        self.market_cache: Optional[MarketDataCache] = None
        self.data_validator = DataValidator()

        # State management
        self.status = DataFeedStatus.DISCONNECTED
        self.is_running = False
        self.last_update: Optional[datetime] = None

        # Data storage
        self.data_buffers: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.config.buffer_size)
        )
        self.current_data: Dict[str, MarketTick] = {}
        self.symbol_status: Dict[str, Dict[str, Any]] = {}

        # Subscribers
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.group_subscribers: Dict[str, List[Callable]] = defaultdict(list)

        # Custom metric handlers
        self.custom_handlers: Dict[str, Any] = {}

        # Threading
        self._lock = threading.RLock()
        self._update_thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self.executor = ThreadPoolExecutor(max_workers=5)

        # Error tracking
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.last_errors: Dict[str, str] = {}

        # Initialize non-provider components
        self._initialize_components()

        self.logger.info(
            f"DataFeedManager initialized — provider={self._provider.__class__.__name__}"
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_provider_name() -> str:
        """Read the preferred provider from config/config.py."""
        try:
            from config.config import DATA_PROVIDER
            return DATA_PROVIDER
        except Exception:
            return "databento"

    # ==========================================================================
    # INITIALIZATION
    # ==========================================================================
    def _initialize_components(self) -> None:
        """Initialize non-provider sub-components."""
        try:
            if self.config.cache_enabled:
                self.market_cache = MarketDataCache(
                    event_manager=self.event_manager
                )
                self.logger.info("MarketDataCache initialized")

            self._setup_event_subscriptions()
            self._load_custom_handlers()

        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            self.error_handler.handle_error(e, {"method": "_initialize_components"})

    def _setup_event_subscriptions(self) -> None:
        """Setup event subscriptions for custom metric and system events."""
        @self.event_manager.subscribe(EventType.CUSTOM_METRIC_UPDATE)
        def on_custom_metric(event: Event):
            self._handle_custom_metric_update(event.data)

        @self.event_manager.subscribe(EventType.SYSTEM_ERROR)
        def on_system_error(event: Event):
            self._handle_system_error(event.data)

    def _load_custom_handlers(self) -> None:
        """Load custom metric calculation handlers."""
        for metric_name, cfg in self.config.custom_metrics_config.items():
            if cfg.get('enabled'):
                try:
                    module_name = cfg['module']
                    self.logger.info(f"Loaded custom handler for {metric_name}")
                except Exception as e:
                    self.logger.error(f"Failed to load {metric_name} handler: {e}")

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    def start(self) -> bool:
        """
        Start the data feed system.

        Returns:
            True on success.
        """
        try:
            if self.is_running:
                self.logger.warning("Data feed already running")
                return True

            self.is_running = True
            self.status = DataFeedStatus.CONNECTING

            # Connect provider
            provider_ok = self._provider.connect()

            # Start cache
            if self.market_cache:
                self.market_cache.start()

            # Background threads
            self._update_thread = threading.Thread(
                target=self._update_loop, daemon=True
            )
            self._update_thread.start()

            self._monitor_thread = threading.Thread(
                target=self._monitor_loop, daemon=True
            )
            self._monitor_thread.start()

            # Allow connection to settle
            time.sleep(2)

            if provider_ok and self._provider.is_connected:
                self.status = DataFeedStatus.CONNECTED
            else:
                self.status = DataFeedStatus.DEGRADED

            self.logger.info(f"Data feed started — status: {self.status.value}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start data feed: {e}")
            self.status = DataFeedStatus.ERROR
            return False

    def stop(self) -> bool:
        """
        Stop the data feed system.

        Returns:
            True on success.
        """
        try:
            self.is_running = False

            self._provider.disconnect()

            if self.market_cache:
                self.market_cache.stop()

            if self._update_thread:
                self._update_thread.join(timeout=5)
            if self._monitor_thread:
                self._monitor_thread.join(timeout=5)

            self.executor.shutdown(wait=True)
            self.status = DataFeedStatus.DISCONNECTED
            self.logger.info("Data feed stopped")
            return True

        except Exception as e:
            self.logger.error(f"Error stopping data feed: {e}")
            return False

    def subscribe(
        self,
        symbol: str,
        callback: Callable[[MarketTick], None],
        priority: Optional[str] = None,
    ) -> bool:
        """
        Subscribe to market data updates for a symbol.

        Args:
            symbol: Market symbol.
            callback: Function to call on updates.
            priority: Subscription priority (CRITICAL, HIGH, MEDIUM, LOW).

        Returns:
            True on success.
        """
        with self._lock:
            self.subscribers[symbol].append(callback)

            tier = priority or self._get_symbol_tier(symbol)
            success = self._provider.subscribe(symbol)

            if success:
                self.symbol_status[symbol] = {
                    'subscribed': True,
                    'tier': tier,
                    'last_update': None,
                }

            return success

    def unsubscribe(
        self,
        symbol: str,
        callback: Optional[Callable] = None,
    ) -> bool:
        """
        Unsubscribe from market data updates.

        Args:
            symbol: Market symbol.
            callback: Specific callback to remove (None removes all).

        Returns:
            True on success.
        """
        with self._lock:
            if symbol in self.subscribers:
                if callback and callback in self.subscribers[symbol]:
                    self.subscribers[symbol].remove(callback)
                elif not callback:
                    self.subscribers[symbol].clear()

                if not self.subscribers[symbol]:
                    self._provider.unsubscribe(symbol)
                    self.symbol_status.pop(symbol, None)

                return True
            return False

    def subscribe_group(
        self,
        group_name: str,
        callback: Callable[[Dict[str, MarketTick]], None],
    ) -> bool:
        """
        Subscribe to a group of symbols.

        Args:
            group_name: Name of symbol group (CORE, VOLATILITY, etc.).
            callback: Function receiving ``{symbol: MarketTick}`` dict.

        Returns:
            True on success.
        """
        if group_name not in SYMBOL_GROUPS:
            self.logger.error(f"Unknown symbol group: {group_name}")
            return False

        with self._lock:
            self.group_subscribers[group_name].append(callback)

            for symbol in SYMBOL_GROUPS[group_name]:
                self.subscribe(symbol, self._create_group_callback(group_name))

            return True

    def get_market_data(
        self, symbol: str, use_cache: bool = True
    ) -> Optional[MarketTick]:
        """
        Get latest market data for a symbol.

        Args:
            symbol: Market symbol.
            use_cache: Whether to fall back to cached data.

        Returns:
            Latest ``MarketTick`` or None.
        """
        with self._lock:
            if symbol in self.current_data:
                return self.current_data[symbol]

        if use_cache and self.market_cache:
            cached_data = self.market_cache.get(symbol)
            if cached_data:
                return self._convert_cached_to_tick(symbol, cached_data)

        return None

    def get_historical_data(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        granularity: str = "1min",
    ) -> pd.DataFrame:
        """
        Get historical market data.

        First tries the provider's historical API (Databento REST), then
        falls back to cache.

        Args:
            symbol: Market symbol.
            start_time: Start timestamp.
            end_time: End timestamp.
            granularity: ``"tick"``, ``"1min"``, ``"5min"``, ``"1hour"``, ``"daily"``.

        Returns:
            DataFrame with historical data.
        """
        # Try provider historical first
        df = self._provider.get_historical(symbol, start_time, end_time, granularity)
        if df is not None and not df.empty:
            return df

        # Fall back to local cache
        if self.market_cache:
            gran_map = {
                'tick': DataGranularity.TICK,
                '1min': DataGranularity.MINUTE,
                '5min': DataGranularity.MINUTE,
                '1hour': DataGranularity.HOUR,
                'daily': DataGranularity.DAILY,
            }
            gran_enum = gran_map.get(granularity, DataGranularity.MINUTE)
            df = self.market_cache.get_range(symbol, start_time, end_time, gran_enum)

            if granularity == '5min' and not df.empty:
                df = df.resample('5min').agg({
                    'bid': 'last', 'ask': 'last',
                    'last': 'last', 'volume': 'sum',
                }).dropna()

            return df

        return pd.DataFrame()

    def get_snapshot(
        self, symbols: Optional[List[str]] = None
    ) -> Dict[str, MarketTick]:
        """
        Get snapshot of current market data.

        Args:
            symbols: List of symbols (None for all).

        Returns:
            ``{symbol: MarketTick}`` dict.
        """
        with self._lock:
            if symbols:
                return {
                    s: self.current_data[s]
                    for s in symbols
                    if s in self.current_data
                }
            return self.current_data.copy()

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the data feed system."""
        with self._lock:
            return {
                'feed_status': self.status.value,
                'is_running': self.is_running,
                'provider': self._provider.__class__.__name__,
                'provider_connected': self._provider.is_connected,
                'last_update': (
                    self.last_update.isoformat() if self.last_update else None
                ),
                'active_symbols': len(self.current_data),
                'subscribed_symbols': list(self.symbol_status.keys()),
                'error_symbols': [
                    s for s, c in self.error_counts.items() if c > 0
                ],
                'cache_stats': (
                    self.market_cache.get_stats() if self.market_cache else {}
                ),
            }

    # ==========================================================================
    # PROVIDER DATA CALLBACK
    # ==========================================================================
    def _on_provider_data(self, tick: MarketTick) -> None:
        """
        Central handler for all data arriving from the active provider.

        Replaces the old _handle_market_data_update from MarketDataHub.
        """
        try:
            symbol = tick.symbol

            # Validate if enabled
            if self.config.validation_enabled:
                if not self.data_validator.validate_tick(tick.to_dict()):
                    self.logger.warning(f"Invalid tick data for {symbol}")
                    self.error_counts[symbol] += 1
                    return

            # Update storage
            with self._lock:
                self.current_data[symbol] = tick
                self.data_buffers[symbol].append(tick)
                self.last_update = datetime.now()

                if symbol in self.symbol_status:
                    self.symbol_status[symbol]['last_update'] = datetime.now()

            # Store in cache
            if self.market_cache:
                self.market_cache.put(
                    symbol,
                    tick.to_dict(),
                    priority=self._get_symbol_priority(symbol),
                )

            # Notify subscribers
            self._notify_subscribers(symbol, tick)

            # Publish via event manager for cross-module consumption
            self.event_manager.publish(Event(
                EventType.MARKET_DATA_TICK,
                {'symbol': symbol, 'tick': tick.to_dict()},
            ))

            # Reset error count on success
            self.error_counts[symbol] = 0

        except Exception as e:
            self.logger.error(f"Error handling provider data: {e}")
            self.error_handler.handle_error(
                e, {"method": "_on_provider_data"}
            )

    def _on_provider_status(self, new_status: DataFeedStatus) -> None:
        """Handle provider status changes."""
        old = self.status
        self.status = new_status
        if old != new_status:
            self.logger.info(f"Feed status: {old.value} → {new_status.value}")

    # ==========================================================================
    # CUSTOM / SYSTEM EVENT HANDLERS
    # ==========================================================================
    def _handle_custom_metric_update(self, data: Dict[str, Any]) -> None:
        """Handle custom metric update (GEX, DIX, SWAN, etc.)."""
        try:
            symbol = data['symbol']
            value = data['value']

            tick = MarketTick(
                symbol=symbol,
                timestamp=datetime.now(),
                price=value,
                size=0,
                source=DataSource.CUSTOM,
            )

            with self._lock:
                self.current_data[symbol] = tick

            self._notify_subscribers(symbol, tick)

        except Exception as e:
            self.logger.error(f"Error handling custom metric: {e}")

    def _handle_system_error(self, data: Dict[str, Any]) -> None:
        """Handle system error event."""
        component = data.get('component', 'Unknown')
        error = data.get('error', 'Unknown error')
        severity = data.get('severity', 'warning')

        self.logger.error(f"System error from {component}: {error}")

        if severity == 'critical' and component in (
            'DatabentoProvider', 'MarketDataHub'
        ):
            self.status = DataFeedStatus.ERROR

    # ==========================================================================
    # UPDATE LOOPS
    # ==========================================================================
    def _update_loop(self) -> None:
        """Main update loop for processing market data."""
        while self.is_running:
            try:
                self._update_custom_metrics()
                self._check_stale_data()
            except Exception as e:
                self.logger.error(f"Error in update loop: {e}")
            time.sleep(self.config.update_interval)

    def _monitor_loop(self) -> None:
        """Monitor loop for system health."""
        while self.is_running:
            try:
                self._check_component_health()
                self._publish_status_update()
                self._cleanup_old_data()
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
            time.sleep(self.config.heartbeat_interval)

    def _update_custom_metrics(self) -> None:
        """Update custom calculated metrics."""
        for metric_name, handler in self.custom_handlers.items():
            try:
                self.executor.submit(handler.update)
            except Exception as e:
                self.logger.error(f"Error updating {metric_name}: {e}")

    def _check_stale_data(self) -> None:
        """Check for stale market data."""
        now = datetime.now()
        stale_threshold = timedelta(seconds=30)

        with self._lock:
            for symbol, status in self.symbol_status.items():
                if status['last_update']:
                    age = now - status['last_update']
                    if age > stale_threshold:
                        self.logger.warning(
                            f"Stale data for {symbol}: {age.total_seconds():.0f}s old"
                        )
                        if symbol in self.current_data:
                            self.current_data[symbol].quality = "stale"

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _notify_subscribers(self, symbol: str, tick: MarketTick) -> None:
        """Notify all subscribers of a symbol update."""
        if symbol in self.subscribers:
            for callback in self.subscribers[symbol]:
                try:
                    self.executor.submit(callback, tick)
                except Exception as e:
                    self.logger.error(f"Error in subscriber callback: {e}")

        for group_name, symbols in SYMBOL_GROUPS.items():
            if symbol in symbols and group_name in self.group_subscribers:
                group_data = self._get_group_snapshot(group_name)
                for callback in self.group_subscribers[group_name]:
                    try:
                        self.executor.submit(callback, group_data)
                    except Exception as e:
                        self.logger.error(f"Error in group callback: {e}")

    def _create_group_callback(self, group_name: str) -> Callable:
        """Create a no-op callback for group symbol subscriptions."""
        def _noop(tick: MarketTick) -> None:
            pass
        return _noop

    def _get_group_snapshot(self, group_name: str) -> Dict[str, MarketTick]:
        """Get snapshot of all symbols in a group."""
        symbols = SYMBOL_GROUPS.get(group_name, [])
        with self._lock:
            return {
                s: self.current_data[s]
                for s in symbols
                if s in self.current_data
            }

    def _convert_cached_to_tick(
        self, symbol: str, data: Dict[str, Any]
    ) -> MarketTick:
        """Convert cached data dict to MarketTick."""
        return MarketTick(
            symbol=symbol,
            timestamp=datetime.fromisoformat(
                data.get('timestamp', datetime.now().isoformat())
            ),
            price=data.get('last', data.get('price', 0.0)),
            size=data.get('last_size', data.get('size', 0)),
            bid=data.get('bid'),
            ask=data.get('ask'),
            bid_size=data.get('bid_size'),
            ask_size=data.get('ask_size'),
            volume=data.get('volume'),
            open=data.get('open'),
            high=data.get('high'),
            low=data.get('low'),
            close=data.get('close'),
            vwap=data.get('vwap'),
            source=DataSource.CACHE,
            quality="cached",
        )

    def _get_symbol_tier(self, symbol: str) -> str:
        """Determine subscription tier for a symbol."""
        for group, symbols in SYMBOL_GROUPS.items():
            if symbol in symbols:
                if group == 'CORE':
                    return 'CRITICAL'
                elif group in ('VOLATILITY', 'INTERNALS'):
                    return 'HIGH'
                elif group == 'INDICES':
                    return 'MEDIUM'
                else:
                    return 'LOW'
        return 'MEDIUM'

    def _get_symbol_priority(self, symbol: str) -> int:
        """Get cache priority for a symbol."""
        tier = self._get_symbol_tier(symbol)
        return {'CRITICAL': 1, 'HIGH': 2, 'MEDIUM': 3, 'LOW': 4}.get(tier, 3)

    def _check_component_health(self) -> None:
        """Check health of all components."""
        if not self._provider.is_connected:
            if self.status == DataFeedStatus.CONNECTED:
                self.status = DataFeedStatus.DEGRADED

        if self.market_cache:
            cache_stats = self.market_cache.get_stats()
            hit_rate = cache_stats.get('hit_rate', 1.0)
            if hit_rate < 0.5:
                self.logger.warning(f"Low cache hit rate: {hit_rate:.2%}")

        high_error_symbols = [
            s for s, c in self.error_counts.items()
            if c > self.config.error_threshold
        ]
        if high_error_symbols:
            self.logger.warning(f"High error rates for: {high_error_symbols}")

    def _publish_status_update(self) -> None:
        """Publish system status update via event manager."""
        status = self.get_status()
        self.event_manager.publish(Event(
            EventType.SYSTEM_STATUS,
            {
                'component': 'DataFeedManager',
                'status': status,
                'timestamp': datetime.now(),
            },
        ))

    def _cleanup_old_data(self) -> None:
        """Clean up old data from buffers."""
        cutoff = datetime.now() - timedelta(minutes=30)
        with self._lock:
            for symbol, buffer in self.data_buffers.items():
                while buffer and buffer[0].timestamp < cutoff:
                    buffer.popleft()

    # ==========================================================================
    # LIFECYCLE
    # ==========================================================================
    def shutdown(self) -> None:
        """Shutdown the data feed manager."""
        try:
            self.stop()
            with self._lock:
                self.data_buffers.clear()
                self.current_data.clear()
                self.subscribers.clear()
                self.group_subscribers.clear()
            self.logger.info("DataFeedManager shut down")
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    def cleanup(self) -> None:
        """Clean up resources."""
        self.shutdown()


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_data_feed_instance: Optional[DataFeedManager] = None


def get_data_feed_manager(
    provider: Optional[Union[str, MarketDataProvider]] = None,
    event_manager: Optional[EventManager] = None,
    config: Optional[Dict] = None,
) -> DataFeedManager:
    """
    Get singleton ``DataFeedManager`` instance.

    Args:
        provider: ``"databento"`` or a pre-built provider.
        event_manager: Event manager instance.
        config: Optional configuration dict.

    Returns:
        DataFeedManager singleton.
    """
    global _data_feed_instance
    if _data_feed_instance is None:
        _data_feed_instance = DataFeedManager(provider, event_manager, config)
    return _data_feed_instance


# ==============================================================================
# BACKWARD COMPATIBILITY — alias for consumers importing "DataFeed"
# ==============================================================================
DataFeed = DataFeedManager


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    import sys

    # Quick smoke-test using Databento from env vars
    event_manager = EventManager()

    # Select provider from CLI arg or default
    provider_name = sys.argv[1] if len(sys.argv) > 1 else "databento"

    feed_config = {
        'provider': provider_name,
        'cache_enabled': True,
        'validation_enabled': True,
    }

    feed_manager = DataFeedManager(
        provider=provider_name,
        event_manager=event_manager,
        config=feed_config,
    )

    # Define test callback
    def on_update(tick: MarketTick):
        print(
            f"  {tick.source.value} | {tick.symbol}: ${tick.price:.2f} "
            f"[{tick.bid or 0:.2f} x {tick.ask or 0:.2f}] "
            f"Vol: {tick.volume}"
        )

    # Subscribe
    feed_manager.subscribe('SPY', on_update, 'CRITICAL')
    feed_manager.subscribe('VIX', on_update, 'CRITICAL')
    feed_manager.subscribe('QQQ', on_update, 'HIGH')

    # Group subscription
    def on_group(group_data: Dict[str, MarketTick]):
        print(f"\n  CORE Group Update:")
        for sym, t in group_data.items():
            print(f"    {sym}: ${t.price:.2f}")

    feed_manager.subscribe_group('CORE', on_group)

    # Start
    if feed_manager.start():
        print(f"Data feed started ({provider_name})")

        try:
            time.sleep(30)
        except KeyboardInterrupt:
            pass

        status = feed_manager.get_status()
        print(f"\nFeed Status:\n{json.dumps(status, indent=2, default=str)}")

        # Historical test
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=5)
        hist = feed_manager.get_historical_data('SPY', start_time, end_time)
        if not hist.empty:
            print(f"\nHistorical SPY:\n{hist.tail()}")

        feed_manager.stop()
        print("Data feed stopped")
    else:
        print("Failed to start data feed", file=sys.stderr)