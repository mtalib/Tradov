#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC25_PolygonDataHandler.py
Purpose: Polygon.io WebSocket streaming data handler for real-time market data

Author: Claude (Maestro)
Year Created: 2025
Last Updated: 2025-11-18 Time: 19:30:00

Module Description:
    Real-time market data streaming from Polygon.io (formerly known as Massive)
    using WebSocket connections. This module replaces IBKR's market data feed
    with Polygon's professional-grade SIP-consolidated data.

    Polygon.io provides:
    - <50ms latency real-time streaming
    - SIP-consolidated data (official exchange feeds)
    - Tick-by-tick trades and quotes
    - Aggregates (1s, 1m, 5m, 15m, 30m, 1h)
    - No session timeouts or connection management complexity

    This module is designed for integration with Spyder's event-driven
    architecture and uses Qt signals/slots for thread-safe communication
    between the WebSocket thread and the main UI/strategy threads.

Module Constants:
    POLYGON_WS_URL (str): Polygon WebSocket endpoint
    POLYGON_REST_URL (str): Polygon REST API endpoint
    RECONNECT_DELAY (int): Delay before reconnection attempt in seconds
    MAX_RECONNECT_ATTEMPTS (int): Maximum reconnection attempts
    HEARTBEAT_INTERVAL (int): WebSocket heartbeat/ping interval
    MESSAGE_BUFFER_SIZE (int): Internal message buffer size

Change Log:
    2025-11-18 (v1.0.0):
        - Initial implementation for Tradier+Polygon migration
        - WebSocket streaming for trades, quotes, aggregates
        - Qt Signal/Slot integration for thread safety
        - Automatic reconnection with exponential backoff
        - Message normalization for Spyder data structures

References:
    - Polygon.io WebSocket API: https://polygon.io/docs/stocks/ws_getting-started
    - Polygon.io Data Specifications: https://polygon.io/docs/stocks/ws_stocks
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import time
import threading
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from datetime import datetime
from collections import deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import websocket
import requests
import asyncio

# Try to import PySide6 for Qt integration
try:
    from PySide6.QtCore import QThread, Signal, QObject
    HAS_QT = True
except ImportError:
    # Fallback to threading if Qt not available
    HAS_QT = False
    QThread = threading.Thread
    Signal = None

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU40_RateLimiter import rate_limit, acquire_polygon
from Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker import polygon_breaker

# ==============================================================================
# CONSTANTS
# ==============================================================================
POLYGON_WS_URL = "wss://socket.polygon.io/stocks"
POLYGON_REST_URL = "https://api.polygon.io"
RECONNECT_DELAY = 5  # seconds
MAX_RECONNECT_ATTEMPTS = 10
HEARTBEAT_INTERVAL = 30  # seconds
MESSAGE_BUFFER_SIZE = 1000

# ==============================================================================
# MODULE LOGGER
# ==============================================================================
logger = SpyderLogger.get_logger(__name__)

# ==============================================================================
# ENUMS
# ==============================================================================
class ConnectionStatus(Enum):
    """WebSocket connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    ERROR = "error"

class MessageType(Enum):
    """Polygon message types."""
    TRADE = "T"  # Trade
    QUOTE = "Q"  # Quote (bid/ask)
    AGGREGATE = "A"  # Aggregate (second bars)
    AGGREGATE_MIN = "AM"  # Aggregate (minute bars)
    STATUS = "status"

# ==============================================================================
# DATA CLASSES
# ==============================================================================
class MarketDataUpdate:
    """
    Normalized market data update.

    This class standardizes Polygon data into Spyder's internal format.
    """

    def __init__(
        self,
        symbol: str,
        timestamp: int,
        message_type: MessageType,
        data: Dict[str, Any]
    ):
        """
        Initialize market data update.

        Args:
            symbol: Security symbol
            timestamp: Unix timestamp (milliseconds)
            message_type: Type of market data
            data: Raw data from Polygon
        """
        self.symbol = symbol
        self.timestamp = timestamp
        self.message_type = message_type
        self.data = data
        self.datetime = datetime.fromtimestamp(timestamp / 1000.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "datetime": self.datetime.isoformat(),
            "type": self.message_type.value,
            "data": self.data
        }

    def __repr__(self) -> str:
        """String representation."""
        return f"MarketDataUpdate({self.symbol}, {self.message_type.value}, {self.datetime})"


# ==============================================================================
# MAIN CLASS (Qt-based)
# ==============================================================================
if HAS_QT:
    class PolygonDataHandler(QThread):
        """
        Polygon.io WebSocket data handler (Qt-based).

        This class runs in a separate thread and streams real-time market data
        from Polygon.io. It emits Qt signals when new data arrives, allowing
        safe cross-thread communication with the UI and strategy engines.

        Signals:
            new_trade: Emitted when a new trade is received
            new_quote: Emitted when a new quote is received
            new_aggregate: Emitted when a new aggregate bar is received
            connection_status_changed: Emitted when connection status changes
            error_occurred: Emitted when an error occurs

        Example:
            >>> handler = PolygonDataHandler(api_key="your_api_key")
            >>> handler.new_trade.connect(on_trade_received)
            >>> handler.subscribe_to_trades(["SPY", "QQQ"])
            >>> handler.start()
        """

        # Qt Signals
        new_trade = Signal(MarketDataUpdate)
        new_quote = Signal(MarketDataUpdate)
        new_aggregate = Signal(MarketDataUpdate)
        connection_status_changed = Signal(ConnectionStatus)
        error_occurred = Signal(str)

        def __init__(
            self,
            api_key: str,
            symbols: Optional[List[str]] = None,
            subscribe_trades: bool = True,
            subscribe_quotes: bool = False,
            subscribe_aggregates: bool = False
        ):
            """
            Initialize Polygon data handler.

            Args:
                api_key: Polygon.io API key
                symbols: List of symbols to subscribe to (default: ["SPY"])
                subscribe_trades: Subscribe to trade stream
                subscribe_quotes: Subscribe to quote stream
                subscribe_aggregates: Subscribe to aggregate stream
            """
            super().__init__()

            self.api_key = api_key
            self.symbols = symbols or ["SPY"]
            self.subscribe_trades_flag = subscribe_trades
            self.subscribe_quotes_flag = subscribe_quotes
            self.subscribe_aggregates_flag = subscribe_aggregates

            # WebSocket connection
            self.ws = None
            self.status = ConnectionStatus.DISCONNECTED
            self.reconnect_attempts = 0
            self.running = False

            # Message buffer
            self.message_buffer = deque(maxlen=MESSAGE_BUFFER_SIZE)

            logger.info(f"PolygonDataHandler initialized for symbols: {self.symbols}")

        def run(self):
            """
            Main thread loop.

            This method runs in a separate thread and maintains the WebSocket
            connection to Polygon.io.
            """
            self.running = True
            self._connect()

        def _connect(self):
            """Connect to Polygon WebSocket."""
            logger.info("Connecting to Polygon WebSocket...")
            self._update_status(ConnectionStatus.CONNECTING)

            try:
                self.ws = websocket.WebSocketApp(
                    POLYGON_WS_URL,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )

                # Run forever (blocking call)
                self.ws.run_forever()

            except Exception as e:
                logger.error(f"Connection error: {str(e)}")
                self.error_occurred.emit(str(e))
                self._handle_reconnect()

        def _on_open(self, ws):
            """Callback when WebSocket connection opens."""
            logger.info("WebSocket connection opened")
            self._update_status(ConnectionStatus.CONNECTED)

            # Authenticate
            auth_message = {
                "action": "auth",
                "params": self.api_key
            }
            ws.send(json.dumps(auth_message))

        def _on_message(self, ws, message):
            """
            Callback when message is received.

            Args:
                ws: WebSocket app instance
                message: Raw message string
            """
            try:
                data = json.loads(message)

                # Handle different message types
                for item in data:
                    event_type = item.get("ev")

                    # Status message (authentication, etc.)
                    if event_type == "status":
                        self._handle_status_message(item)

                    # Trade message
                    elif event_type == "T":
                        self._handle_trade_message(item)

                    # Quote message
                    elif event_type == "Q":
                        self._handle_quote_message(item)

                    # Aggregate message (second bars)
                    elif event_type == "A":
                        self._handle_aggregate_message(item)

                    # Aggregate minute bars
                    elif event_type == "AM":
                        self._handle_aggregate_message(item)

                    else:
                        logger.debug(f"Unknown message type: {event_type}")

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse message: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")

        def _on_error(self, ws, error):
            """Callback when WebSocket error occurs."""
            logger.error(f"WebSocket error: {str(error)}")
            self._update_status(ConnectionStatus.ERROR)
            self.error_occurred.emit(str(error))

        def _on_close(self, ws, close_status_code, close_msg):
            """Callback when WebSocket connection closes."""
            logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
            self._update_status(ConnectionStatus.DISCONNECTED)

            if self.running:
                self._handle_reconnect()

        def _handle_status_message(self, item: Dict[str, Any]):
            """
            Handle status message from Polygon.

            Args:
                item: Status message data
            """
            status = item.get("status")
            message = item.get("message", "")

            logger.info(f"Status: {status} - {message}")

            if status == "auth_success":
                self._update_status(ConnectionStatus.AUTHENTICATED)
                self._subscribe_to_streams()

            elif status == "auth_failed":
                logger.error("Authentication failed!")
                self.error_occurred.emit("Authentication failed")
                self.stop()

        def _subscribe_to_streams(self):
            """Subscribe to requested data streams."""
            subscriptions = []

            # Build subscription list
            for symbol in self.symbols:
                if self.subscribe_trades_flag:
                    subscriptions.append(f"T.{symbol}")

                if self.subscribe_quotes_flag:
                    subscriptions.append(f"Q.{symbol}")

                if self.subscribe_aggregates_flag:
                    subscriptions.append(f"A.{symbol}")  # Second bars
                    subscriptions.append(f"AM.{symbol}")  # Minute bars

            if subscriptions:
                subscribe_message = {
                    "action": "subscribe",
                    "params": ",".join(subscriptions)
                }
                self.ws.send(json.dumps(subscribe_message))
                logger.info(f"Subscribed to: {subscriptions}")

        def _handle_trade_message(self, item: Dict[str, Any]):
            """
            Handle trade message.

            Trade message format:
            {
                "ev": "T",
                "sym": "SPY",
                "p": 450.12,  # price
                "s": 100,     # size
                "t": 1234567890000,  # timestamp (ms)
                "c": [14, 41],  # conditions
                "x": 4  # exchange
            }
            """
            symbol = item.get("sym")
            price = item.get("p")
            size = item.get("s")
            timestamp = item.get("t")

            trade_data = {
                "price": price,
                "size": size,
                "exchange": item.get("x"),
                "conditions": item.get("c", [])
            }

            update = MarketDataUpdate(
                symbol=symbol,
                timestamp=timestamp,
                message_type=MessageType.TRADE,
                data=trade_data
            )

            self.new_trade.emit(update)
            logger.debug(f"Trade: {symbol} @ ${price}, size={size}")

        def _handle_quote_message(self, item: Dict[str, Any]):
            """
            Handle quote message.

            Quote message format:
            {
                "ev": "Q",
                "sym": "SPY",
                "bp": 450.10,  # bid price
                "bs": 5,       # bid size
                "ap": 450.12,  # ask price
                "as": 3,       # ask size
                "t": 1234567890000
            }
            """
            symbol = item.get("sym")
            timestamp = item.get("t")

            quote_data = {
                "bid_price": item.get("bp"),
                "bid_size": item.get("bs"),
                "ask_price": item.get("ap"),
                "ask_size": item.get("as"),
                "bid_exchange": item.get("bx"),
                "ask_exchange": item.get("ax")
            }

            update = MarketDataUpdate(
                symbol=symbol,
                timestamp=timestamp,
                message_type=MessageType.QUOTE,
                data=quote_data
            )

            self.new_quote.emit(update)

        def _handle_aggregate_message(self, item: Dict[str, Any]):
            """
            Handle aggregate bar message.

            Aggregate message format:
            {
                "ev": "A",  # or "AM" for minute
                "sym": "SPY",
                "o": 450.00,  # open
                "h": 450.50,  # high
                "l": 449.80,  # low
                "c": 450.20,  # close
                "v": 1000000,  # volume
                "t": 1234567890000
            }
            """
            symbol = item.get("sym")
            timestamp = item.get("t")

            aggregate_data = {
                "open": item.get("o"),
                "high": item.get("h"),
                "low": item.get("l"),
                "close": item.get("c"),
                "volume": item.get("v"),
                "vwap": item.get("vw")  # volume-weighted average price
            }

            update = MarketDataUpdate(
                symbol=symbol,
                timestamp=timestamp,
                message_type=MessageType.AGGREGATE,
                data=aggregate_data
            )

            self.new_aggregate.emit(update)

        def _update_status(self, status: ConnectionStatus):
            """Update connection status."""
            self.status = status
            self.connection_status_changed.emit(status)

        def _handle_reconnect(self):
            """Handle reconnection logic with exponential backoff."""
            if self.reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                logger.error("Max reconnection attempts reached. Giving up.")
                self.running = False
                return

            self.reconnect_attempts += 1
            delay = RECONNECT_DELAY * (2 ** (self.reconnect_attempts - 1))  # Exponential backoff

            logger.info(f"Reconnecting in {delay}s (attempt {self.reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS})...")
            time.sleep(delay)

            if self.running:
                self._connect()

        def stop(self):
            """Stop the WebSocket connection."""
            logger.info("Stopping Polygon data handler...")
            self.running = False

            if self.ws:
                self.ws.close()

        def subscribe_to_trades(self, symbols: List[str]):
            """
            Subscribe to trade stream for additional symbols.

            Args:
                symbols: List of symbols to subscribe
            """
            if self.status == ConnectionStatus.AUTHENTICATED:
                subscriptions = [f"T.{sym}" for sym in symbols]
                subscribe_message = {
                    "action": "subscribe",
                    "params": ",".join(subscriptions)
                }
                self.ws.send(json.dumps(subscribe_message))
                logger.info(f"Subscribed to trades: {symbols}")
                self.symbols.extend(symbols)

        def unsubscribe_from_trades(self, symbols: List[str]):
            """
            Unsubscribe from trade stream.

            Args:
                symbols: List of symbols to unsubscribe
            """
            if self.status == ConnectionStatus.AUTHENTICATED:
                subscriptions = [f"T.{sym}" for sym in symbols]
                unsubscribe_message = {
                    "action": "unsubscribe",
                    "params": ",".join(subscriptions)
                }
                self.ws.send(json.dumps(unsubscribe_message))
                logger.info(f"Unsubscribed from trades: {symbols}")

        def __repr__(self) -> str:
            """String representation."""
            return f"PolygonDataHandler(symbols={self.symbols}, status={self.status.value})"

        # ==========================================================================
        # REST API METHODS WITH RATE LIMITING & CIRCUIT BREAKERS
        # ==========================================================================

        @rate_limit(service="polygon_rest")
        async def fetch_historical_bars_async(
            self,
            symbol: str,
            from_date: str,
            to_date: str,
            multiplier: int = 1,
            timespan: str = "day"
        ) -> Dict[str, Any]:
            """
            Fetch historical aggregate bars asynchronously with protection.

            This method provides:
            - Rate limiting based on Polygon tier (5/min starter, 100/min business)
            - Circuit breaker protection against outages
            - Non-blocking async execution

            Args:
                symbol: Stock symbol (e.g., "SPY")
                from_date: Start date (YYYY-MM-DD)
                to_date: End date (YYYY-MM-DD)
                multiplier: Size of timespan (e.g., 1 for 1-day, 5 for 5-minute)
                timespan: Size of time window (minute, hour, day, week, month)

            Returns:
                Historical bars data

            Example:
                >>> bars = await handler.fetch_historical_bars_async(
                ...     "SPY", "2025-01-01", "2025-01-31", multiplier=1, timespan="day"
                ... )
            """
            # Determine tier from environment or default to starter
            import os
            tier = os.getenv("POLYGON_TIER", "starter")

            # Additional tier-specific rate limiting
            await acquire_polygon(tier=tier)

            url = f"{POLYGON_REST_URL}/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
            params = {"apiKey": self.api_key, "adjusted": "true", "sort": "asc"}

            loop = asyncio.get_event_loop()

            async with polygon_breaker:
                # Use executor for blocking HTTP request
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.get(url, params=params, timeout=10)
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Fetched {len(data.get('results', []))} bars for {symbol}")
                    return data
                else:
                    error_msg = f"Polygon API error {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

        @rate_limit(service="polygon_rest")
        async def fetch_last_trade_async(self, symbol: str) -> Dict[str, Any]:
            """
            Fetch the last trade for a symbol asynchronously with protection.

            Args:
                symbol: Stock symbol (e.g., "SPY")

            Returns:
                Last trade data

            Example:
                >>> trade = await handler.fetch_last_trade_async("SPY")
                >>> print(f"Last price: ${trade['results']['p']}")
            """
            import os
            tier = os.getenv("POLYGON_TIER", "starter")
            await acquire_polygon(tier=tier)

            url = f"{POLYGON_REST_URL}/v2/last/trade/{symbol}"
            params = {"apiKey": self.api_key}

            loop = asyncio.get_event_loop()

            async with polygon_breaker:
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.get(url, params=params, timeout=10)
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    error_msg = f"Polygon API error {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

        @rate_limit(service="polygon_rest")
        async def fetch_snapshot_async(self, symbol: str) -> Dict[str, Any]:
            """
            Fetch current snapshot (latest trade, quote, and daily stats) asynchronously.

            Args:
                symbol: Stock symbol (e.g., "SPY")

            Returns:
                Snapshot data with current trade, quote, and daily statistics

            Example:
                >>> snapshot = await handler.fetch_snapshot_async("SPY")
                >>> print(f"Current: ${snapshot['ticker']['lastTrade']['p']}")
            """
            import os
            tier = os.getenv("POLYGON_TIER", "starter")
            await acquire_polygon(tier=tier)

            url = f"{POLYGON_REST_URL}/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}"
            params = {"apiKey": self.api_key}

            loop = asyncio.get_event_loop()

            async with polygon_breaker:
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.get(url, params=params, timeout=10)
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    error_msg = f"Polygon API error {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

        # ==========================================================================
        # CIRCUIT BREAKER MONITORING
        # ==========================================================================

        @staticmethod
        def get_circuit_breaker_status() -> Dict[str, Any]:
            """
            Get current circuit breaker status for Polygon API.

            Returns:
                Dictionary with circuit breaker statistics

            Example:
                >>> status = PolygonDataHandler.get_circuit_breaker_status()
                >>> if status['is_open']:
                ...     logger.warning(f"Polygon circuit open!")
            """
            return polygon_breaker.get_stats()

        @staticmethod
        def reset_circuit_breaker():
            """
            Manually reset the Polygon circuit breaker.

            Use after verifying service has recovered.

            Example:
                >>> PolygonDataHandler.reset_circuit_breaker()
            """
            polygon_breaker.reset()
            logger.info("Polygon circuit breaker has been manually reset")


# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================
def create_polygon_handler_from_env() -> PolygonDataHandler:
    """
    Create PolygonDataHandler from environment variables.

    Required environment variables:
        - POLYGON_API_KEY: Polygon.io API key

    Returns:
        Configured PolygonDataHandler instance

    Raises:
        ValueError: If POLYGON_API_KEY not set

    Example:
        >>> import os
        >>> os.environ["POLYGON_API_KEY"] = "your_api_key"
        >>> handler = create_polygon_handler_from_env()
        >>> handler.start()
    """
    import os

    api_key = os.getenv("POLYGON_API_KEY")

    if not api_key:
        raise ValueError("POLYGON_API_KEY environment variable not set")

    return PolygonDataHandler(api_key=api_key)


# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":
    """Test Polygon WebSocket connection."""
    import os
    import sys
    from PySide6.QtWidgets import QApplication

    print("Polygon Data Handler Test")
    print("=" * 60)

    # Create Qt application
    app = QApplication(sys.argv)

    # Test handler
    def on_trade(update: MarketDataUpdate):
        """Handle trade updates."""
        print(f"TRADE: {update.symbol} @ ${update.data['price']:.2f}, size={update.data['size']}")

    def on_status_change(status: ConnectionStatus):
        """Handle status changes."""
        print(f"STATUS: {status.value}")

    def on_error(error: str):
        """Handle errors."""
        print(f"ERROR: {error}")

    try:
        # Create handler from environment
        handler = create_polygon_handler_from_env()

        # Connect signals
        handler.new_trade.connect(on_trade)
        handler.connection_status_changed.connect(on_status_change)
        handler.error_occurred.connect(on_error)

        # Start handler
        print(f"Starting handler: {handler}")
        handler.start()

        # Run Qt event loop
        sys.exit(app.exec())

    except Exception as e:
        print(f"✗ Error: {str(e)}")
