#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC21_MarketDataFeed.py
Purpose: Market data feed using Connect API

Author: SPYDER Trading System
Year Created: 2025
Last Updated: 2025-10-20 Time: 22:05:00

Module Description:
    This module provides market data feed functionality using the Connect API.
    It replaces the IB Gateway/TWS API market data components with a single
    WebSocket connection, providing real-time market data for equities,
    options, futures, and indices.

Module Constants:
    DEFAULT_RECONNECT_DELAY (float): Default reconnection delay in seconds (default: 5.0)
    MAX_RECONNECT_ATTEMPTS (int): Maximum reconnection attempts (default: 10)
    DATA_STALENESS_THRESHOLD (float): Data staleness threshold in seconds (default: 30.0)

Change Log:
    2025-10-20 (v1.0.0):
        - Initial module creation
        - Implemented core market data feed functionality
        - Added integration with Connect API
        - Implemented data quality monitoring

    2025-10-15 (v0.9.0):
        - Beta version for testing
        - Basic data feed structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import threading
import asyncio
from datetime import datetime
from typing import Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum, auto

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from threading import Event as ThreadEvent, RLock

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ConnectAPI / MessageType: removed with IB Gateway (SpyderB01_ConnectAPI deleted).
# Databento integration uses SpyderC26_DatabentoClient directly.
ConnectAPI = None
MessageType = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_RECONNECT_DELAY = 5.0
MAX_RECONNECT_ATTEMPTS = 10
DATA_STALENESS_THRESHOLD = 30.0  # seconds

# ==============================================================================
# ENUMS
# ==============================================================================
class DataFeedState(Enum):
    """Data feed operational states"""
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    SUBSCRIBING = auto()
    RUNNING = auto()
    ERROR = auto()
    STOPPING = auto()

class DataQuality(Enum):
    """Data quality levels"""
    EXCELLENT = auto()
    GOOD = auto()
    FAIR = auto()
    POOR = auto()
    STALE = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MarketDataConfig:
    """Configuration for market data feed"""
    symbols: list[str]
    options_symbols: list[str] = field(default_factory=list)
    update_frequencies: dict[str, float] = field(default_factory=dict)
    exchanges: dict[str, str] = field(default_factory=dict)
    currencies: dict[str, str] = field(default_factory=dict)

    # Data quality settings
    staleness_threshold: float = DATA_STALENESS_THRESHOLD
    enable_quality_monitoring: bool = True

    # Connection settings
    reconnect_attempts: int = MAX_RECONNECT_ATTEMPTS
    reconnect_delay: float = DEFAULT_RECONNECT_DELAY

@dataclass
class MarketDataTick:
    """Market data tick representation"""
    symbol: str
    timestamp: datetime
    last_price: float
    bid_price: float | None = None
    ask_price: float | None = None
    bid_size: int | None = None
    ask_size: int | None = None
    volume: int | None = None
    exchange: str = "SMART"
    currency: str = "USD"

@dataclass
class DataQualityMetrics:
    """Data quality metrics"""
    symbol: str
    last_update: datetime
    staleness_seconds: float
    update_frequency: float
    data_gaps: int
    quality: DataQuality
    timestamp: datetime = field(default_factory=datetime.now)

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class MarketDataFeed:
    """
    Market data feed using Connect API.

    This class provides market data feed functionality using the Connect API.
    It replaces the IB Gateway/TWS API market data components with a single
    WebSocket connection, providing real-time market data for equities,
    options, futures, and indices.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling system
        config: Market data configuration
        connect_api: Connect API instance
        state: Current data feed state
        _data_lock: Thread lock for data operations
        _shutdown_event: Event for coordinated shutdown
    """

    def __init__(self, config: MarketDataConfig, connect_api: ConnectAPI):
        """
        Initialize the market data feed.

        Args:
            config: Market data configuration
            connect_api: Connect API instance
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config

        # Connect API
        self.connect_api = connect_api

        # Data management
        self._market_data: dict[str, MarketDataTick] = {}
        self._data_callbacks: dict[str, list[Callable]] = defaultdict(list)
        self._data_lock = RLock()
        self._shutdown_event = ThreadEvent()

        # State management
        self.state = DataFeedState.DISCONNECTED

        # Data quality monitoring
        self._quality_metrics: dict[str, DataQualityMetrics] = {}
        self._last_quality_check = datetime.now()

        # Metrics
        self.metrics = {
            'data_updates': 0,
            'data_gaps': 0,
            'reconnections': 0,
            'start_time': datetime.now()
        }

        # Register message handlers
        self._register_handlers()

        self.logger.info("MarketDataFeed initialized")

    def _register_handlers(self):
        """Register message handlers with the Connect API"""
        self.connect_api.register_handler(MessageType.MARKET_DATA_UPDATE, self._handle_market_data_update)
        self.connect_api.register_handler(MessageType.ERROR, self._handle_error_message)

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================

    async def start(self) -> bool:
        """
        Start the data feed.

        Returns:
            bool: True if start successful
        """
        try:
            self.logger.info("Starting MarketDataFeed...")
            self.state = DataFeedState.CONNECTING

            # Connect to Connect API if not already connected
            if self.connect_api.state != "AUTHENTICATED":
                if not await self.connect_api.connect():
                    self.state = DataFeedState.ERROR
                    return False

            # Subscribe to symbols
            await self._subscribe_symbols()

            # Start data quality monitoring
            if self.config.enable_quality_monitoring:
                self._start_quality_monitoring()

            self.state = DataFeedState.RUNNING
            self.logger.info("MarketDataFeed started successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start data feed: {e}")
            self.error_handler.handle_error(e, "start")
            self.state = DataFeedState.ERROR
            return False

    async def stop(self) -> bool:
        """
        Stop the data feed.

        Returns:
            bool: True if stop successful
        """
        try:
            self.logger.info("Stopping MarketDataFeed...")
            self.state = DataFeedState.STOPPING

            # Signal shutdown
            self._shutdown_event.set()

            # Stop quality monitoring
            self._stop_quality_monitoring()

            self.state = DataFeedState.DISCONNECTED
            self.logger.info("MarketDataFeed stopped successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to stop data feed: {e}")
            self.error_handler.handle_error(e, "stop")
            return False

    # ==========================================================================
    # DATA OPERATIONS
    # ==========================================================================

    def get_latest_data(self, symbol: str) -> MarketDataTick | None:
        """
        Get the latest market data for a symbol.

        Args:
            symbol: Symbol to get data for

        Returns:
            Latest market data tick or None if not available
        """
        with self._data_lock:
            return self._market_data.get(symbol)

    def get_latest_data_multiple(self, symbols: list[str]) -> dict[str, MarketDataTick]:
        """
        Get the latest market data for multiple symbols.

        Args:
            symbols: List of symbols to get data for

        Returns:
            Dictionary of latest market data ticks
        """
        with self._data_lock:
            return {
                symbol: data for symbol, data in self._market_data.items()
                if symbol in symbols
            }

    def register_callback(self, symbol: str, callback: Callable):
        """
        Register a callback for market data updates.

        Args:
            symbol: Symbol to register callback for
            callback: Callback function
        """
        with self._data_lock:
            self._data_callbacks[symbol].append(callback)
            self.logger.debug(f"Registered callback for {symbol}")

    def unregister_callback(self, symbol: str, callback: Callable):
        """
        Unregister a callback for market data updates.

        Args:
            symbol: Symbol to unregister callback for
            callback: Callback function
        """
        with self._data_lock:
            if callback in self._data_callbacks[symbol]:
                self._data_callbacks[symbol].remove(callback)
                self.logger.debug(f"Unregistered callback for {symbol}")

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================

    async def _subscribe_symbols(self):
        """Subscribe to symbols"""
        self.logger.info("Subscribing to symbols...")

        # Subscribe to equity symbols
        for symbol in self.config.symbols:
            message = {
                "MsgType": MessageType.MARKET_DATA_REQUEST.value,
                "Symbol": symbol,
                "SecurityType": "STK",
                "Exchange": self.config.exchanges.get(symbol, "SMART"),
                "Currency": self.config.currencies.get(symbol, "USD")
            }

            await self.connect_api.send_message(message)
            self.logger.debug(f"Subscribed to equity symbol: {symbol}")

        # Subscribe to options symbols
        for symbol in self.config.options_symbols:
            message = {
                "MsgType": MessageType.MARKET_DATA_REQUEST.value,
                "Symbol": symbol,
                "SecurityType": "OPTION",
                "Exchange": self.config.exchanges.get(symbol, "SMART"),
                "Currency": self.config.currencies.get(symbol, "USD")
            }

            await self.connect_api.send_message(message)
            self.logger.debug(f"Subscribed to options symbol: {symbol}")

        self.logger.info(f"Subscribed to {len(self.config.symbols)} equity symbols and {len(self.config.options_symbols)} options symbols")

    async def _handle_market_data_update(self, data: dict[str, Any]):
        """
        Handle market data update message.

        Args:
            data: Market data update
        """
        try:
            symbol = data.get("Symbol", "")
            if not symbol:
                self.logger.warning("Market data update missing Symbol")
                return

            # Create market data tick
            market_data = MarketDataTick(
                symbol=symbol,
                timestamp=datetime.now(),
                last_price=float(data.get("LastPx", 0.0)),
                bid_price=float(data.get("BidPrice", 0.0)) if data.get("BidPrice") else None,
                ask_price=float(data.get("AskPrice", 0.0)) if data.get("AskPrice") else None,
                bid_size=int(data.get("BidSize", 0)) if data.get("BidSize") else None,
                ask_size=int(data.get("AskSize", 0)) if data.get("AskSize") else None,
                volume=int(data.get("Volume", 0)) if data.get("Volume") else None,
                exchange=data.get("ExchangeDestination", "SMART"),
                currency=data.get("Currency", "USD")
            )

            # Update market data
            with self._data_lock:
                self._market_data[market_data.symbol] = market_data
                self.metrics['data_updates'] += 1

            # Update quality metrics
            if self.config.enable_quality_monitoring:
                self._update_quality_metrics(market_data)

            # Notify callbacks
            self._notify_callbacks(market_data)

        except Exception as e:
            self.logger.error(f"Error handling market data update: {e}")
            self.error_handler.handle_error(e, "_handle_market_data_update")

    async def _handle_error_message(self, data: dict[str, Any]):
        """
        Handle error message.

        Args:
            data: Error data
        """
        try:
            error_code = data.get("ErrorCode", "UNKNOWN")
            error_text = data.get("ErrorText", "Unknown error")

            self.logger.error(f"Data feed error: {error_code} - {error_text}")

            # Update state if appropriate
            if error_code == "CONNECTION_LOST":
                self.state = DataFeedState.ERROR
                # Attempt reconnection
                asyncio.create_task(self._reconnect())

        except Exception as e:
            self.logger.error(f"Error handling error message: {e}")
            self.error_handler.handle_error(e, "_handle_error_message")

    def _notify_callbacks(self, market_data: MarketDataTick):
        """
        Notify registered callbacks of market data update.

        Args:
            market_data: Market data update
        """
        callbacks = self._data_callbacks.get(market_data.symbol, [])
        for callback in callbacks:
            try:
                callback(market_data)
            except Exception as e:
                self.logger.error(f"Error in market data callback: {e}")

    def _update_quality_metrics(self, market_data: MarketDataTick):
        """
        Update data quality metrics.

        Args:
            market_data: Market data update
        """
        try:
            symbol = market_data.symbol
            now = datetime.now()

            # Calculate staleness
            staleness = (now - market_data.timestamp).total_seconds()

            # Get previous metrics if available
            previous_metrics = self._quality_metrics.get(symbol)

            # Calculate update frequency
            update_frequency = 0.0
            if previous_metrics:
                time_diff = (now - previous_metrics.last_update).total_seconds()
                if time_diff > 0:
                    update_frequency = 1.0 / time_diff

            # Determine quality
            if staleness <= 1.0:
                quality = DataQuality.EXCELLENT
            elif staleness <= 5.0:
                quality = DataQuality.GOOD
            elif staleness <= 15.0:
                quality = DataQuality.FAIR
            elif staleness <= self.config.staleness_threshold:
                quality = DataQuality.POOR
            else:
                quality = DataQuality.STALE
                self.metrics['data_gaps'] += 1

            # Update metrics
            self._quality_metrics[symbol] = DataQualityMetrics(
                symbol=symbol,
                last_update=market_data.timestamp,
                staleness_seconds=staleness,
                update_frequency=update_frequency,
                data_gaps=self.metrics['data_gaps'],
                quality=quality
            )

        except Exception as e:
            self.logger.error(f"Error updating quality metrics: {e}")

    async def _reconnect(self):
        """Attempt to reconnect to Connect API"""
        self.logger.info("Attempting to reconnect to Connect API...")

        for attempt in range(self.config.reconnect_attempts):
            try:
                self.logger.info(f"Reconnection attempt {attempt + 1}/{self.config.reconnect_attempts}")

                # Wait before reconnecting
                await asyncio.sleep(self.config.reconnect_delay)

                # Attempt to reconnect
                if await self.connect_api.connect():
                    self.logger.info("Successfully reconnected to Connect API")
                    self.metrics['reconnections'] += 1

                    # Subscribe to symbols again
                    await self._subscribe_symbols()

                    self.state = DataFeedState.RUNNING
                    return True

            except Exception as e:
                self.logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")

        self.logger.error("Failed to reconnect to Connect API after all attempts")
        self.state = DataFeedState.ERROR
        return False

    def _start_quality_monitoring(self):
        """Start data quality monitoring thread"""
        self._quality_thread = threading.Thread(
            target=self._quality_monitoring_loop,
            daemon=True,
            name="DataQualityMonitoring"
        )
        self._quality_thread.start()
        self.logger.info("Data quality monitoring started")

    def _stop_quality_monitoring(self):
        """Stop data quality monitoring thread"""
        if hasattr(self, '_quality_thread') and self._quality_thread:
            self._quality_thread.join(timeout=5.0)
            self._quality_thread = None
            self.logger.info("Data quality monitoring stopped")

    def _quality_monitoring_loop(self):
        """Quality monitoring loop"""
        while not self._shutdown_event.is_set():
            try:
                # Check data quality
                self._check_data_quality()

                # Wait for next check
                time.sleep(10.0)  # Check every 10 seconds

            except Exception as e:
                self.logger.error(f"Error in quality monitoring loop: {e}")
                time.sleep(5.0)  # Wait before retry

    def _check_data_quality(self):
        """Check data quality for all symbols"""
        try:
            now = datetime.now()

            for symbol, metrics in self._quality_metrics.items():
                # Check if data is stale
                staleness = (now - metrics.last_update).total_seconds()
                if staleness > self.config.staleness_threshold:
                    self.logger.warning(f"Data for {symbol} is stale: {staleness:.1f}s")
                    self.metrics['data_gaps'] += 1

                # Check update frequency
                if metrics.update_frequency < 0.1:  # Less than 1 update per 10 seconds
                    self.logger.warning(f"Low update frequency for {symbol}: {metrics.update_frequency:.2f}/s")

            self._last_quality_check = now

        except Exception as e:
            self.logger.error(f"Error checking data quality: {e}")

    # ==========================================================================
    # PUBLIC UTILITY METHODS
    # ==========================================================================

    def get_status(self) -> dict[str, Any]:
        """
        Get current data feed status.

        Returns:
            Dictionary containing status information
        """
        with self._data_lock:
            # Calculate uptime
            uptime = datetime.now() - self.metrics['start_time']

            # Count symbols by quality
            quality_counts = {}
            for metrics in self._quality_metrics.values():
                quality = metrics.quality.name
                quality_counts[quality] = quality_counts.get(quality, 0) + 1

            return {
                'state': self.state.name,
                'connect_api_state': self.connect_api.state.value,
                'symbols_subscribed': len(self.config.symbols) + len(self.config.options_symbols),
                'symbols_with_data': len(self._market_data),
                'data_updates': self.metrics['data_updates'],
                'data_gaps': self.metrics['data_gaps'],
                'reconnections': self.metrics['reconnections'],
                'quality_counts': quality_counts,
                'uptime_seconds': uptime.total_seconds(),
                'start_time': self.metrics['start_time'].isoformat()
            }

    def get_quality_metrics(self) -> dict[str, DataQualityMetrics]:
        """
        Get data quality metrics.

        Returns:
            Dictionary of quality metrics by symbol
        """
        with self._data_lock:
            return dict(self._quality_metrics)

    def get_metrics(self) -> dict[str, Any]:
        """
        Get data feed metrics.

        Returns:
            Dictionary containing metrics
        """
        with self._data_lock:
            # Calculate uptime
            uptime = datetime.now() - self.metrics['start_time']

            return {
                'data_updates': self.metrics['data_updates'],
                'data_gaps': self.metrics['data_gaps'],
                'reconnections': self.metrics['reconnections'],
                'uptime_seconds': uptime.total_seconds(),
                'start_time': self.metrics['start_time'].isoformat()
            }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_market_data_feed(
    config: MarketDataConfig,
    connect_api: ConnectAPI
) -> MarketDataFeed:
    """
    Factory function to create a market data feed instance.

    Args:
        config: Market data configuration
        connect_api: Connect API instance

    Returns:
        MarketDataFeed instance
    """
    return MarketDataFeed(config, connect_api)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code

    # This would require actual Connect API to test

    pass
