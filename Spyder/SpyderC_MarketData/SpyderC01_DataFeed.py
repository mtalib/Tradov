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
        must implement.  The concrete live provider is Tradier (via B40);
        ``DataFeedManager`` holds a ``NullProvider`` when no streaming feed
        is wired in.

    Data flow:
        Provider stream → _on_provider_data() → validate → MarketTick
        → cache → notify subscribers → EventManager publish

Change Log:
        2026-02-25 (Phase 3 — Tradier provider abstraction):
        - Replaced legacy broker (SpyderB01_SpyderClient / SpyderC07_MarketDataHub)
          with provider abstraction layer
                - Added MarketDataProvider ABC with NullProvider
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
import math
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
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


from Spyder.SpyderC_MarketData.SpyderC16_MarketDataCache import MarketDataCache, DataGranularity  # noqa: E402
from Spyder.SpyderC_MarketData.SpyderC06_DataValidator import DataValidator  # noqa: E402
from Spyder.SpyderU_Utilities.SpyderU49_SymbolCatalog import get_backend_symbol_groups

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

# Symbol Groups for Efficient Management (canonical source)
SYMBOL_GROUPS = get_backend_symbol_groups()


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
    TRADIER = "tradier"
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
    source: DataSource = DataSource.TRADIER
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
    provider: str = "tradier"
    cache_enabled: bool = True
    validation_enabled: bool = True
    buffer_size: int = 1000
    update_interval: float = 0.1
    heartbeat_interval: int = 30
    error_threshold: int = 10
    custom_metrics_config: dict[str, Any] = field(default_factory=dict)

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
# NULL PROVIDER (stub — no streaming feed wired)
# ==============================================================================
class NullProvider(MarketDataProvider):
    """
    No-op provider used when no streaming data feed is configured.

    The live market data is delivered by ``SpyderB40_TradierClient``
    (option chains / quotes via Tradier REST), not via a streaming feed
    from this module.  NullProvider satisfies the MarketDataProvider ABC
    so that DataFeedManager can be constructed without error.
    """

    @property
    def is_connected(self) -> bool:
        return False

    @property
    def active_source(self) -> DataSource:
        return DataSource.TRADIER

    def connect(self) -> bool:
        return False

    def disconnect(self) -> None:
        pass

    def subscribe(self, symbol: str) -> bool:
        return True

    def unsubscribe(self, symbol: str) -> bool:
        return True


# ==============================================================================
# PROVIDER FACTORY
# ==============================================================================
def create_provider(
    provider_name: str,
    config: Optional['DataFeedConfig'] = None,
) -> MarketDataProvider:
    """
    Create a ``MarketDataProvider`` by name.

    Currently returns a ``NullProvider`` for all names because live data
    is delivered by ``SpyderB40_TradierClient``, not via a streaming feed.

    Args:
        provider_name: Any string (kept for API compatibility).
        config: Optional feed configuration (unused by NullProvider).

    Returns:
        A ``NullProvider`` instance.
    """
    return NullProvider()

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class DataFeedManager:
    """
    Central data feed orchestrator with provider abstraction.

    Coordinates between:
    - A pluggable ``MarketDataProvider`` (NullProvider by default)
    - ``MarketDataCache`` for efficient storage
    - Custom metric calculators
    - Event-based distribution system

    Usage::

        from SpyderC_MarketData.SpyderC01_DataFeed import DataFeedManager

        feed = DataFeedManager()
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
            provider: Provider name or a pre-built ``MarketDataProvider``
                instance.  Defaults to the value in ``config/config.py``
                → ``DATA_PROVIDER``.
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

        # NullProvider fallback: poll Tradier REST quotes so the backend still
        # emits MARKET_DATA ticks for strategy/risk pipelines.
        self._quote_client: Any = None
        self._last_quote_poll_monotonic: float = 0.0
        self._quote_poll_interval_s: float = max(
            1.0,
            float(os.environ.get("SPYDER_FEED_QUOTE_POLL_INTERVAL_S", "5.0")),
        )
        self._quote_client_failed: bool = False

        # Error tracking
        self.error_counts: dict[str, int] = defaultdict(int)
        self.last_errors: dict[str, str] = {}

        # Initialize non-provider components
        self._initialize_components()

        self.logger.debug(
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
            return "tradier"

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
                self.logger.debug("MarketDataCache initialized")

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

            self.logger.debug("Data feed started — status: %s", self.status.value)
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

    def _get_symbol_tier(self, symbol: str) -> str:
        """Return cache/event tier for a symbol."""
        normalized = (symbol or "").upper()

        if normalized in {"SPY", "SPX", "VIX"}:
            return "CRITICAL"

        for group_name, symbols in SYMBOL_GROUPS.items():
            if normalized in symbols:
                if group_name in {"VOLATILITY", "INTERNALS"}:
                    return "HIGH"
                if group_name in {"INDICES", "FIXED_INCOME"}:
                    return "MEDIUM"
                return "LOW"

        return "MEDIUM"

    def _get_symbol_priority(self, symbol: str) -> int:
        """Return numeric cache priority (1=highest, 4=lowest)."""
        tier = (
            self.symbol_status.get(symbol, {}).get("tier")
            or self._get_symbol_tier(symbol)
        )
        priority_map = {
            "CRITICAL": 1,
            "HIGH": 2,
            "MEDIUM": 3,
            "LOW": 4,
        }
        return priority_map.get(str(tier).upper(), 3)

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

    def _notify_subscribers(self, symbol: str, tick: MarketTick) -> None:
        """Dispatch a symbol tick to all registered symbol subscribers."""
        callbacks = list(self.subscribers.get(symbol, []))
        for callback in callbacks:
            try:
                callback(tick)
            except Exception as e:
                self.logger.error("Subscriber callback failed for %s: %s", symbol, e)

    def _create_group_callback(
        self,
        group_name: str,
    ) -> Callable[[MarketTick], None]:
        """Create a symbol callback that fans out grouped snapshots."""

        def _group_callback(_tick: MarketTick) -> None:
            symbols = SYMBOL_GROUPS.get(group_name, [])
            with self._lock:
                snapshot = {
                    sym: self.current_data[sym]
                    for sym in symbols
                    if sym in self.current_data
                }
                callbacks = list(self.group_subscribers.get(group_name, []))

            for callback in callbacks:
                try:
                    callback(snapshot)
                except Exception as e:
                    self.logger.error("Group callback failed for %s: %s", group_name, e)

        return _group_callback

    def _convert_cached_to_tick(self, symbol: str, cached_data: dict[str, Any]) -> MarketTick:
        """Convert cached dict payload to MarketTick with safe defaults."""
        timestamp_raw = cached_data.get('timestamp')
        if isinstance(timestamp_raw, str):
            try:
                timestamp = datetime.fromisoformat(timestamp_raw)
            except ValueError:
                timestamp = datetime.now(timezone.utc)
        elif isinstance(timestamp_raw, datetime):
            timestamp = timestamp_raw
        else:
            timestamp = datetime.now(timezone.utc)

        def _as_float(value: Any) -> float | None:
            if value is None:
                return None
            try:
                out = float(value)
            except (TypeError, ValueError):
                return None
            if not math.isfinite(out):
                return None
            return out

        price = _as_float(cached_data.get('price'))
        if price is None or price <= 0:
            price = _as_float(cached_data.get('last')) or _as_float(cached_data.get('close')) or 0.0

        source_raw = str(cached_data.get('source', DataSource.CACHE.value)).lower()
        source = DataSource.CACHE
        for candidate in DataSource:
            if candidate.value == source_raw:
                source = candidate
                break

        return MarketTick(
            symbol=symbol,
            timestamp=timestamp,
            price=price,
            size=int(cached_data.get('size') or 0),
            bid=_as_float(cached_data.get('bid')),
            ask=_as_float(cached_data.get('ask')),
            bid_size=int(cached_data.get('bid_size') or 0) if cached_data.get('bid_size') is not None else None,
            ask_size=int(cached_data.get('ask_size') or 0) if cached_data.get('ask_size') is not None else None,
            volume=int(cached_data.get('volume') or 0) if cached_data.get('volume') is not None else None,
            open=_as_float(cached_data.get('open')),
            high=_as_float(cached_data.get('high')),
            low=_as_float(cached_data.get('low')),
            close=_as_float(cached_data.get('close')),
            vwap=_as_float(cached_data.get('vwap')),
            source=source,
            quality=str(cached_data.get('quality') or 'cached'),
        )

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

            # Validate if enabled. C06 exposes validate_data(), not validate_tick().
            # Skip C06 validation for Tradier REST fallback ticks — price/finite
            # checks are already enforced in _poll_quotes_fallback(), and indices
            # (SPX, VIX) return bid=0/ask=0 which would trip SpreadValidationRule.
            _skip_validation = tick.source == DataSource.TRADIER
            if self.config.validation_enabled and not _skip_validation:
                validation_result = self.data_validator.validate_data(tick.to_dict())
                if not getattr(validation_result, "is_valid", False):
                    self.logger.warning("Invalid tick data for %s", symbol)
                    self.error_counts[symbol] += 1
                    return

            # Update storage
            with self._lock:
                self.current_data[symbol] = tick
                self.data_buffers[symbol].append(tick)
                self.last_update = datetime.now(timezone.utc)

                if symbol in self.symbol_status:
                    self.symbol_status[symbol]['last_update'] = datetime.now(timezone.utc)

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
                timestamp=datetime.now(timezone.utc),
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

        if severity == 'critical' and component in ('NullProvider', 'MarketDataHub'):
            self.status = DataFeedStatus.ERROR

    # ==========================================================================
    # UPDATE LOOPS
    # ==========================================================================
    def _update_loop(self) -> None:
        """Main update loop for processing market data."""
        while self.is_running:
            try:
                self._poll_quotes_fallback()
                self._update_custom_metrics()
                self._check_stale_data()
            except Exception as e:
                self.logger.error("Error in update loop: %s", e)
            if self._stop_event.wait(timeout=self.config.update_interval):
                break

    def _ensure_quote_client(self) -> Any | None:
        """Lazily initialise a Tradier quote client for NullProvider fallback."""
        if self._quote_client is not None:
            return self._quote_client
        if self._quote_client_failed:
            return None

        try:
            from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
                TradierClient,
                TradingEnvironment,
            )
        except Exception as exc:
            self.logger.debug("Quote fallback unavailable (Tradier import failed): %s", exc)
            self._quote_client_failed = True
            return None

        try:
            trading_mode = os.environ.get("TRADING_MODE", "paper").strip().lower()
            env_raw = os.environ.get("TRADIER_ENVIRONMENT", "sandbox").strip().lower()

            if trading_mode == "paper" and env_raw != "live":
                # Paper mode + sandbox data: use sandbox credentials and endpoint.
                api_key = (
                    os.environ.get("TRADIER_SANDBOX_API_KEY")
                    or os.environ.get("TRADIER_API_KEY")
                    or ""
                )
                account_id = (
                    os.environ.get("TRADIER_SANDBOX_ACCOUNT_ID")
                    or os.environ.get("TRADIER_ACCOUNT_ID")
                    or ""
                )
                environment = TradingEnvironment.SANDBOX
            else:
                # Live data (or paper+live): respect TRADIER_ENVIRONMENT so
                # TRADING_MODE=paper TRADIER_ENVIRONMENT=live hits api.tradier.com.
                api_key = os.environ.get("TRADIER_API_KEY", "")
                account_id = os.environ.get("TRADIER_ACCOUNT_ID", "")
                environment = TradingEnvironment.LIVE if env_raw == "live" else TradingEnvironment.SANDBOX

            if not api_key or not account_id:
                self._quote_client_failed = True
                self.logger.debug("Quote fallback disabled: Tradier credentials unavailable")
                return None

            self._quote_client = TradierClient(
                api_key=api_key,
                account_id=account_id,
                environment=environment,
            )
            self.logger.debug("DataFeed quote fallback enabled via Tradier REST (%s)", environment.value)
            return self._quote_client

        except Exception as exc:
            self._quote_client_failed = True
            self.logger.warning("Quote fallback init failed: %s", exc)
            return None

    def _poll_quotes_fallback(self) -> None:
        """Emit MarketTick updates when provider is NullProvider/degraded.

        This keeps backend strategies (D31) fed with MARKET_DATA events even
        when no streaming provider is wired.
        """
        # Only needed when the configured provider is not delivering stream data.
        if self._provider.is_connected:
            return

        now_mono = time.monotonic()
        if (now_mono - self._last_quote_poll_monotonic) < self._quote_poll_interval_s:
            return
        self._last_quote_poll_monotonic = now_mono

        symbols = [s for s in self.symbol_status.keys() if s]
        if not symbols:
            return

        client = self._ensure_quote_client()
        if client is None:
            return

        try:
            response = client.get_quotes(symbols)
        except Exception as exc:
            self.logger.debug("Quote fallback poll failed: %s", exc)
            return

        quote_node = ((response or {}).get("quotes") or {}).get("quote")
        if not quote_node:
            return

        quotes = quote_node if isinstance(quote_node, list) else [quote_node]
        for quote in quotes:
            if not isinstance(quote, dict):
                continue

            symbol = str(quote.get("symbol") or "").strip()
            if not symbol:
                continue

            last = quote.get("last")
            bid = quote.get("bid")
            ask = quote.get("ask")
            close = quote.get("close")

            try:
                price = float(last if last is not None else (close if close is not None else 0.0))
            except (TypeError, ValueError):
                price = 0.0

            if not math.isfinite(price) or price <= 0.0:
                continue

            def _to_float(value: Any) -> float | None:
                if value is None:
                    return None
                try:
                    out = float(value)
                except (TypeError, ValueError):
                    return None
                if not math.isfinite(out):
                    return None
                return out

            tick = MarketTick(
                symbol=symbol,
                timestamp=datetime.now(timezone.utc),
                price=price,
                size=0,
                bid=_to_float(bid),
                ask=_to_float(ask),
                volume=int(quote.get("volume") or 0),
                open=_to_float(quote.get("open")),
                high=_to_float(quote.get("high")),
                low=_to_float(quote.get("low")),
                close=_to_float(close),
                source=DataSource.TRADIER,
                quality="realtime",
            )

            self._on_provider_data(tick)

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
        now = datetime.now(timezone.utc)
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

    def _publish_status_update(self) -> None:
        """Publish periodic feed status for observability and downstream routing."""
        try:
            self.event_manager.emit(
                event_type=EventType.SYSTEM_METRICS,
                source=self.__class__.__name__,
                data={
                    "component": "DataFeedManager",
                    "feed_status": self.status.value,
                    "provider": self._provider.__class__.__name__,
                    "provider_connected": bool(self._provider.is_connected),
                    "active_symbols": len(self.current_data),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as e:
            self.logger.warning("Unable to publish data feed status update: %s", e)

    def _cleanup_old_data(self) -> None:
        """Remove stale entries from data buffers for symbols no longer receiving updates."""
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
            with self._lock:
                stale_symbols = [
                    sym for sym, status in self.symbol_status.items()
                    if status.get("last_update") and status["last_update"] < cutoff
                ]
                for sym in stale_symbols:
                    self.current_data.pop(sym, None)
                    if stale_symbols:
                        self.logger.debug(
                            "Cleaned up stale data for %d symbol(s)", len(stale_symbols)
                        )
        except Exception as e:
            self.logger.warning("Data cleanup error: %s", e)


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
        provider: Provider name (``"tradier"``) or a pre-built
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
            feed.subscribe(sym, lambda _tick: None, priority="HIGH")

    return feed


def get_data_feed_manager(
    provider: "str | MarketDataProvider | None" = None,
) -> DataFeedManager:
    """
    Convenience factory that creates a ``DataFeedManager`` for the given provider.

    Unlike ``create_data_feed``, this function is intentionally simple — it does
    not subscribe to any symbols and does not require symbols as input.  It is
    intended for modules that manage their own subscription lifecycle.

    Args:
        provider: Provider name (``"tradier"``) or a pre-built
            ``MarketDataProvider`` instance.  Defaults to the configured value.

    Returns:
        A configured (but not yet started) ``DataFeedManager`` instance.
    """
    from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager as _gem

    em = _gem()
    return DataFeedManager(provider=provider, event_manager=em)

