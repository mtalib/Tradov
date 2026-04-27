#!/usr/bin/env python3
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

                - **MassiveProvider** — wraps ``SpyderC27_MassiveClient``
                    for current live and fallback market data.

        The active provider is selected from ``config/config.py``
                ``DATA_PROVIDER`` setting (default ``"massive"`` within this module).

    Data flow:
        Provider stream → _on_provider_data() → validate → MarketTick
        → cache → notify subscribers → EventManager publish

Change Log:
        2026-02-25 (Phase 3 — Tradier+Massive provider abstraction):
        - Replaced legacy broker (SpyderB01_SpyderClient / SpyderC07_MarketDataHub)
          with provider abstraction layer
                - Added MarketDataProvider ABC with MassiveProvider
                - Rewired get_historical_data() to use provider-backed historical REST
        - Updated singleton factory and __main__ test block
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys  # noqa: F401
import time
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional, Any
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU44_ShutdownCoordinator import get_shutdown_coordinator
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager, EventType, Event, get_event_manager  # noqa: E501


def _is_massive_disabled() -> bool:
    """Return whether Massive usage is disabled for the current process."""
    return os.getenv("SPYDER_DISABLE_MASSIVE", "1").lower().strip() in {
        "1",
        "true",
        "yes",
        "on",
    }
from Spyder.SpyderC_MarketData.SpyderC16_MarketDataCache import MarketDataCache, DataGranularity  # noqa: E402
from Spyder.SpyderC_MarketData.SpyderC06_DataValidator import DataValidator  # noqa: E402

try:
    from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import (
        MassiveClient,
        MassiveQuoteUpdate,
        MassiveTradeUpdate,
        ConnectionStatus as MassiveConnectionStatus,  # noqa: F401
        create_massive_client_from_env,
    )
    HAS_MASSIVE = True
except ImportError:
    HAS_MASSIVE = False
    MassiveClient = None

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
    'CORRELATIONS': ['DXY', 'GLD', 'USO']
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
    MASSIVE = "massive"
    CACHE = "cache"
    CUSTOM = "custom"
    SYNTHETIC = "synthetic"


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
    bid: float | None = None
    ask: float | None = None
    bid_size: int | None = None
    ask_size: int | None = None
    volume: int | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    vwap: float | None = None
    source: DataSource = DataSource.MASSIVE
    quality: str = "realtime"

    def to_dict(self) -> dict[str, Any]:
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
    provider: str = "massive"
    cache_enabled: bool = True
    validation_enabled: bool = True
    buffer_size: int = 1000
    update_interval: float = 0.1
    heartbeat_interval: int = 30
    error_threshold: int = 10
    custom_metrics_config: dict[str, Any] = field(default_factory=dict)
    # Massive-specific
    massive_schema: str = "quotes"
    massive_dataset: str = "massive-live"
    massive_api_key: str = ""
    massive_symbols: list[str] = field(default_factory=lambda: ["SPY"])

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> 'DataFeedConfig':
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
        self.on_data: Callable[[MarketTick], None] | None = None
        self.on_status_change: Callable[[DataFeedStatus], None] | None = None

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
# MASSIVE PROVIDER
# ==============================================================================
class MassiveProvider(MarketDataProvider):
    """
    Wraps ``SpyderC27_MassiveClient`` as a ``MarketDataProvider``.

    Streams real-time SPY equity quotes and trades from the Massive
    WebSocket, delivering normalized ``MarketTick`` objects.
    Historical OHLCV bars are served by the Massive REST API.

    This is the preferred provider for SPY equity price ticks when pairing
    Spyder with Tradier for order execution.
    """

    def __init__(
        self,
        symbols: list[str] | None = None,
        api_key: str | None = None,
    ) -> None:
        super().__init__()

        if not HAS_MASSIVE:
            raise ImportError(
                "massive package not installed.  Run: pip install massive"
            )

        self._logger = SpyderLogger.get_logger(f"{__name__}.MassiveProvider")
        self._symbols: list[str] = symbols or ["SPY"]
        self._api_key = api_key
        self._client: MassiveClient | None = None
        self._started = False

    # ------------------------------------------------------------------
    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_streaming

    @property
    def active_source(self) -> DataSource:
        return DataSource.MASSIVE

    def connect(self) -> bool:
        """Create the Massive client and start WebSocket streaming."""
        if _is_massive_disabled():
            self._logger.info(
                "MassiveProvider connect skipped: SPYDER_DISABLE_MASSIVE is enabled"
            )
            return False

        try:
            self._client = (
                MassiveClient(api_key=self._api_key)
                if self._api_key
                else create_massive_client_from_env()
            )
            self._client.on_status_change = self._on_connection_status
            self._client.start_stream(
                symbols=self._symbols,
                on_quote=self._on_quote,
                on_trade=self._on_trade,
                include_quotes=True,
                include_trades=True,
            )
            self._started = True
            self._logger.info(
                "MassiveProvider connected, streaming %s", self._symbols
            )
            return True

        except Exception as exc:
            self._logger.error("MassiveProvider connect failed: %s", exc)
            return False

    def disconnect(self) -> None:
        if self._client:
            self._client.stop_stream()
            self._client = None
        self._started = False
        self._logger.info("MassiveProvider disconnected")

    def subscribe(self, symbol: str) -> bool:
        if symbol not in self._symbols:
            self._symbols.append(symbol)
            if self._client and self._client.is_streaming:
                self._client.update_subscriptions(self._symbols)
        return True

    def unsubscribe(self, symbol: str) -> bool:
        if symbol in self._symbols:
            self._symbols.remove(symbol)
            if self._client and self._client.is_streaming:
                self._client.update_subscriptions(self._symbols)
        return True

    def get_historical(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        granularity: str = "1min",
    ) -> pd.DataFrame:
        """Fetch historical OHLCV bars from Massive REST API."""
        if self._client is None:
            self._client = (
                MassiveClient(api_key=self._api_key)
                if self._api_key
                else create_massive_client_from_env()
            )
        timespan_map = {
            "tick":  ("second", 1),
            "1s":    ("second", 1),
            "1min":  ("minute", 1),
            "5min":  ("minute", 5),
            "1hour": ("hour",   1),
            "daily": ("day",    1),
        }
        timespan, multiplier = timespan_map.get(granularity, ("minute", 1))
        try:
            return self._client.get_historical_bars(
                symbol=symbol,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                timespan=timespan,
                multiplier=multiplier,
            )
        except Exception as exc:
            self._logger.error(
                "MassiveProvider.get_historical(%s) failed: %s", symbol, exc
            )
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # Massive callbacks → MarketTick
    # ------------------------------------------------------------------
    def _on_quote(self, update: "MassiveQuoteUpdate") -> None:
        if not self.on_data:
            return
        tick = MarketTick(
            symbol=update.symbol,
            timestamp=update.timestamp,
            price=update.mid,
            size=update.bid_size,
            bid=update.bid,
            ask=update.ask,
            bid_size=update.bid_size,
            ask_size=update.ask_size,
            source=DataSource.MASSIVE,
            quality="realtime",
        )
        self.on_data(tick)

    def _on_trade(self, update: "MassiveTradeUpdate") -> None:
        if not self.on_data:
            return
        tick = MarketTick(
            symbol=update.symbol,
            timestamp=update.timestamp,
            price=update.price,
            size=update.size,
            source=DataSource.MASSIVE,
            quality="realtime",
        )
        self.on_data(tick)

    def _on_connection_status(self, status) -> None:
        if not self.on_status_change:
            return
        from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import ConnectionStatus
        status_map = {
            ConnectionStatus.STREAMING:    DataFeedStatus.CONNECTED,
            ConnectionStatus.CONNECTED:    DataFeedStatus.CONNECTED,
            ConnectionStatus.CONNECTING:   DataFeedStatus.CONNECTING,
            ConnectionStatus.RECONNECTING: DataFeedStatus.CONNECTING,
            ConnectionStatus.DISCONNECTED: DataFeedStatus.DISCONNECTED,
            ConnectionStatus.STOPPED:      DataFeedStatus.DISCONNECTED,
            ConnectionStatus.ERROR:        DataFeedStatus.ERROR,
        }
        feed_status = status_map.get(status, DataFeedStatus.ERROR)
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
        provider_name: ``"massive"`` or ``"tradier"``.
        config: Optional feed configuration for provider-specific settings.

    Returns:
        Configured ``MarketDataProvider`` instance.

    Raises:
        ValueError: If the provider name is unknown or not installed.
    """
    name = provider_name.lower().strip()
    cfg = config or DataFeedConfig()

    if name == "massive":
        if _is_massive_disabled():
            raise ValueError(
                "Massive provider requested but disabled by SPYDER_DISABLE_MASSIVE"
            )
        if not HAS_MASSIVE:
            raise ValueError(
                "Massive provider requested but massive package is not "
                "installed.  Run: pip install massive"
            )
        return MassiveProvider(
            symbols=cfg.massive_symbols,
            api_key=cfg.massive_api_key or None,
        )

    else:
        raise ValueError(
            f"Unknown provider '{provider_name}'.  "
            f"Supported: 'massive'."
        )

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class DataFeedManager:
    """
    Central data feed orchestrator with provider abstraction.

    Coordinates between:
    - A pluggable ``MarketDataProvider`` (Massive)
    - ``MarketDataCache`` for efficient storage
    - Custom metric calculators
    - Event-based distribution system

    Usage::

        from SpyderC_MarketData.SpyderC01_DataFeed import DataFeedManager

        feed = DataFeedManager(provider="massive")
        feed.subscribe("SPY", my_callback)
        feed.start()
    """

    def __init__(
        self,
        provider: str | MarketDataProvider | None = None,
        event_manager: EventManager | None = None,
        config: DataFeedConfig | dict | None = None,
    ):
        """
        Initialize enhanced data feed manager.

        Args:
            provider: Provider name (``"massive"``) or a
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
        self.event_manager = event_manager or get_event_manager()

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
        self.market_cache: MarketDataCache | None = None
        self.data_validator = DataValidator()

        # State management
        self.status = DataFeedStatus.DISCONNECTED
        self.is_running = False
        self._stop_event = threading.Event()
        self.last_update: datetime | None = None

        # Data storage
        self.data_buffers: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.config.buffer_size)
        )
        self.current_data: dict[str, MarketTick] = {}
        self.symbol_status: dict[str, dict[str, Any]] = {}

        # Subscribers
        self.subscribers: dict[str, list[Callable]] = defaultdict(list)
        self.group_subscribers: dict[str, list[Callable]] = defaultdict(list)

        # Custom metric handlers
        self.custom_handlers: dict[str, Any] = {}

        # Threading
        self._lock = threading.RLock()
        self._update_thread: threading.Thread | None = None
        self._monitor_thread: threading.Thread | None = None
        self.executor = ThreadPoolExecutor(max_workers=5)

        # Error tracking
        self.error_counts: dict[str, int] = defaultdict(int)
        self.last_errors: dict[str, str] = {}

        # Initialize non-provider components
        self._initialize_components()

        self.logger.info(
            "DataFeedManager initialized — provider=%s", self._provider.__class__.__name__
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_provider_name() -> str:
        """Read the preferred provider from config/config.py."""
        try:
            from config.config import DATA_PROVIDER
            return DATA_PROVIDER
        except Exception:
            return "massive"

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
            self.logger.error("Failed to initialize components: %s", e)
            self.error_handler.handle_error(e, {"method": "_initialize_components"})

    def _setup_event_subscriptions(self) -> None:
        """Setup event subscriptions for custom metric and system events."""
        def on_custom_metric(event: Event):
            self._handle_custom_metric_update(event.data)

        def on_system_error(event: Event):
            self._handle_system_error(event.data)

        self.event_manager.subscribe(
            EventType.CUSTOM_METRIC_UPDATE,
            on_custom_metric,
            name="DataFeedManager._on_custom_metric",
        )
        self.event_manager.subscribe(
            EventType.SYSTEM_ERROR,
            on_system_error,
            name="DataFeedManager._on_system_error",
        )

    def _load_custom_handlers(self) -> None:
        """Load custom metric calculation handlers."""
        for metric_name, cfg in self.config.custom_metrics_config.items():
            if cfg.get('enabled'):
                try:
                    cfg['module']
                    self.logger.info("Loaded custom handler for %s", metric_name)
                except Exception as e:
                    self.logger.error("Failed to load %s handler: %s", metric_name, e)

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

            # Background threads — registered with ShutdownCoordinator for
            # clean teardown; _stop_event is already polled in their loops.
            _coord = get_shutdown_coordinator()
            self._update_thread = threading.Thread(
                target=self._update_loop, daemon=True
            )
            _coord.register_thread(self._update_thread, name="DataFeed-update")
            self._update_thread.start()

            self._monitor_thread = threading.Thread(
                target=self._monitor_loop, daemon=True
            )
            _coord.register_thread(self._monitor_thread, name="DataFeed-monitor")
            _coord.register_cleanup(self.stop)
            self._monitor_thread.start()

            # Allow connection to settle
            time.sleep(2)  # thread-safe: time.sleep() intentional

            if provider_ok and self._provider.is_connected:
                self.status = DataFeedStatus.CONNECTED
            else:
                self.status = DataFeedStatus.DEGRADED

            self.logger.info("Data feed started — status: %s", self.status.value)
            return True

        except Exception as e:
            self.logger.error("Failed to start data feed: %s", e)
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
            self._stop_event.set()

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
            self.logger.error("Error stopping data feed: %s", e)
            return False

    def subscribe(
        self,
        symbol: str,
        callback: Callable[[MarketTick], None],
        priority: str | None = None,
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
        callback: Callable | None = None,
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
        callback: Callable[[dict[str, MarketTick]], None],
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
            self.logger.error("Unknown symbol group: %s", group_name)
            return False

        with self._lock:
            self.group_subscribers[group_name].append(callback)

            for symbol in SYMBOL_GROUPS[group_name]:
                self.subscribe(symbol, self._create_group_callback(group_name))

            return True

    def get_market_data(
        self, symbol: str, use_cache: bool = True
    ) -> MarketTick | None:
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

        First tries the provider's historical API (Massive REST), then
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
        self, symbols: list[str] | None = None
    ) -> dict[str, MarketTick]:
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

    def get_status(self) -> dict[str, Any]:
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
                    self.logger.warning("Invalid tick data for %s", symbol)
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
                EventType.MARKET_DATA,
                {'symbol': symbol, 'tick': tick.to_dict()},
            ))

            # Reset error count on success
            self.error_counts[symbol] = 0

        except Exception as e:
            self.logger.error("Error handling provider data: %s", e)
            self.error_handler.handle_error(
                e, {"method": "_on_provider_data"}
            )

    def _on_provider_status(self, new_status: DataFeedStatus) -> None:
        """Handle provider status changes."""
        old = self.status
        self.status = new_status
        if old != new_status:
            self.logger.info("Feed status: %s → %s", old.value, new_status.value)

    # ==========================================================================
    # CUSTOM / SYSTEM EVENT HANDLERS
    # ==========================================================================
    def _handle_custom_metric_update(self, data: dict[str, Any]) -> None:
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
            self.logger.error("Error handling custom metric: %s", e)

    def _handle_system_error(self, data: dict[str, Any]) -> None:
        """Handle system error event."""
        component = data.get('component', 'Unknown')
        error = data.get('error', 'Unknown error')
        severity = data.get('severity', 'warning')

        self.logger.error("System error from %s: %s", component, error)

        if severity == 'critical' and component in ('MassiveProvider', 'MarketDataHub'):
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
                self.logger.error("Error in update loop: %s", e)
            if self._stop_event.wait(timeout=self.config.update_interval):
                break

    def _monitor_loop(self) -> None:
        """Monitor loop for system health."""
        while self.is_running:
            try:
                self._check_component_health()
                self._publish_status_update()
                self._cleanup_old_data()
            except Exception as e:
                self.logger.error("Error in monitor loop: %s", e)
            if self._stop_event.wait(timeout=self.config.heartbeat_interval):
                break

    def _update_custom_metrics(self) -> None:
        """Update custom calculated metrics."""
        for metric_name, handler in self.custom_handlers.items():
            try:
                self.executor.submit(handler.update)
            except Exception as e:
                self.logger.error("Error updating %s: %s", metric_name, e)

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

    def _check_component_health(self) -> None:
        """Monitor provider/cache health and update feed status."""
        provider_connected = bool(self._provider and self._provider.is_connected)

        if provider_connected:
            if self.status in {DataFeedStatus.CONNECTING, DataFeedStatus.DEGRADED, DataFeedStatus.ERROR}:  # noqa: E501
                self.status = DataFeedStatus.CONNECTED
        else:
            # During runtime, disconnected provider means degraded service.
            if self.status == DataFeedStatus.CONNECTED:
                self.status = DataFeedStatus.DEGRADED


# ==============================================================================
# FACTORY  (S-02)
# ==============================================================================

def create_data_feed(
    symbols: list[str] | None = None,
    event_manager: "EventManager | None" = None,
    provider: "str | MarketDataProvider | None" = None,
    config: "DataFeedConfig | dict | None" = None,
) -> DataFeedManager:
    """
    Factory convenience function for constructing a ``DataFeedManager``.

    Creates a feed wired to the supplied *event_manager* (or the singleton
    from ``get_event_manager()`` if not provided) and, optionally, subscribes
    it to *symbols* before returning.  Callers still need to invoke
    ``feed.start()`` themselves.

    Args:
        symbols: Optional list of symbols to subscribe to (e.g. ``["SPY",
            "SPX", "VIX"]``).  Each is subscribed with a no-op callback so
            the feed will request data for the symbol on connect.
        event_manager: Shared EventManager instance. When ``None`` the
            singleton from ``get_event_manager()`` is used.
        provider: Provider name (``"massive"``) or pre-built
            ``MarketDataProvider`` instance.  Defaults to the value in
            ``config/config.py``.
        config: ``DataFeedConfig`` or raw dict overrides.

    Returns:
        A configured (but not yet started) ``DataFeedManager`` instance.
    """
    from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager as _gem

    em = event_manager or _gem()
    feed = DataFeedManager(provider=provider, event_manager=em, config=config)

    if symbols:
        for sym in symbols:
            # Register a no-op subscriber so the provider knows to pull data
            # for each symbol.  Real consumers add their own callbacks later.
            # Pass priority explicitly to avoid the unimplemented _get_symbol_tier.
            feed.subscribe(sym, lambda _tick: None, priority="HIGH")

    return feed

