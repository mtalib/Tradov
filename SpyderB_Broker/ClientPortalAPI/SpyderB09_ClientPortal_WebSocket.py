#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB09_ClientPortal_WebSocket.py
Purpose: WebSocket client for real-time market data streaming from Client Portal API

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-11-09 Time: 14:00:00

Module Description:
    WebSocket client for IBKR Client Portal API real-time market data streaming.

    CORE FEATURES:
    - WebSocket connection management with auto-reconnect
    - Real-time market data subscription (quotes, trades, order book)
    - Multiple instrument subscriptions (stocks, options, futures)
    - Heartbeat/ping-pong keepalive
    - Automatic session refresh integration
    - Thread-safe message queue

    SUBSCRIPTION TYPES:
    - Market Data (md): Last price, bid/ask, volume
    - Market Depth (depth): Order book (Level II)
    - Trades (trades): Time & sales data
    - Bars (bars): Real-time OHLCV bars

    WEBSOCKET ENDPOINTS:
    - Production: wss://api.ibkr.com/v1/api/ws
    - Paper: wss://localhost:5000/v1/api/ws (CP Gateway)

    MESSAGE FORMAT:
    All messages are JSON with format:
    {
        "topic": "smd+265598",  # Market data for conid 265598
        "args": {"fields": ["31", "84", "86"]},  # Last, bid, ask
        "data": [{"31": 450.25, "84": 450.20, "86": 450.30}]
    }

Module Constants:
    WS_PROD_URL (str): Production WebSocket URL
    WS_PAPER_URL (str): Paper trading WebSocket URL
    HEARTBEAT_INTERVAL (int): Ping interval in seconds (30)
    RECONNECT_DELAY (int): Delay before reconnect attempt (5 seconds)
    MAX_RECONNECT_ATTEMPTS (int): Maximum reconnection attempts (10)
    MESSAGE_QUEUE_SIZE (int): Max queued messages (1000)

Change Log:
    2025-11-09 (v1.0.0):
        - Initial implementation with WebSocket support
        - Real-time market data subscriptions
        - Auto-reconnect with exponential backoff
        - Thread-safe message handling
        - Heartbeat keepalive

References:
    - CLIENT_PORTAL_WEB_API_BEST_PRACTICES.md
    - https://interactivebrokers.github.io/cpwebapi/
    - https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/#md-stock
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import time
import threading
from typing import Optional, Dict, Any, Callable, List, Set
from dataclasses import dataclass, field
from datetime import datetime
from queue import Queue, Empty
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from .SpyderB09_ClientPortal_Session import SessionManager
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

logger = SpyderLogger.get_logger(__name__)


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

__all__ = [
    # Enums
    'SubscriptionType',
    'ConnectionState',
    # Configuration
    'WebSocketConfig',
    # Client
    'ClientPortalWebSocket',
    # Constants
    'WS_PROD_URL',
    'WS_PAPER_URL',
]


# ==============================================================================
# MODULE CONSTANTS
# ==============================================================================

WS_PROD_URL = "wss://api.ibkr.com/v1/api/ws"
WS_PAPER_URL = "wss://localhost:5000/v1/api/ws"
HEARTBEAT_INTERVAL = 30  # seconds
RECONNECT_DELAY = 5  # seconds
MAX_RECONNECT_ATTEMPTS = 10
MESSAGE_QUEUE_SIZE = 1000


# ==============================================================================
# ENUMERATIONS
# ==============================================================================

class SubscriptionType(Enum):
    """WebSocket subscription types"""
    MARKET_DATA = "smd"  # Streaming market data
    MARKET_DEPTH = "sbd"  # Streaming book depth
    TRADES = "str"  # Streaming trades
    BARS = "smh"  # Streaming market history (bars)


class ConnectionState(Enum):
    """WebSocket connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


# ==============================================================================
# CONFIGURATION
# ==============================================================================

@dataclass
class WebSocketConfig:
    """WebSocket client configuration"""
    url: str = WS_PAPER_URL
    heartbeat_interval: int = HEARTBEAT_INTERVAL
    reconnect_delay: int = RECONNECT_DELAY
    max_reconnect_attempts: int = MAX_RECONNECT_ATTEMPTS
    message_queue_size: int = MESSAGE_QUEUE_SIZE
    auto_reconnect: bool = True
    ssl_verify: bool = False  # CP Gateway uses self-signed cert

    # Market data fields (IBKR field IDs)
    default_fields: List[str] = field(default_factory=lambda: [
        "31",  # Last price
        "84",  # Bid price
        "86",  # Ask price
        "88",  # Total volume
        "7295",  # Ask size
        "7296",  # Bid size
    ])


# ==============================================================================
# WEBSOCKET CLIENT
# ==============================================================================

class ClientPortalWebSocket:
    """
    WebSocket client for IBKR Client Portal API real-time market data.

    Features:
    - Real-time market data streaming
    - Automatic reconnection with exponential backoff
    - Multiple instrument subscriptions
    - Thread-safe message handling
    - Heartbeat keepalive

    Usage:
        >>> from SpyderB_Broker.ClientPortalAPI import SessionManager, ClientPortalWebSocket
        >>> session_mgr = SessionManager(auth_client, base_url)
        >>> session_mgr.start()
        >>>
        >>> ws_client = ClientPortalWebSocket(session_mgr)
        >>> ws_client.connect()
        >>>
        >>> # Subscribe to SPY market data
        >>> def on_quote(data):
        ...     print(f"SPY: Last={data.get('31')}, Bid={data.get('84')}, Ask={data.get('86')}")
        >>>
        >>> ws_client.subscribe_market_data(conid=756733, callback=on_quote)
        >>>
        >>> # Keep running
        >>> time.sleep(60)
        >>> ws_client.disconnect()

    Important:
        - Requires active session (via SessionManager)
        - Session must be kept alive (tickle every 4 minutes)
        - CP Gateway: Self-signed cert, use ssl_verify=False
        - Max subscriptions: ~100 per connection
    """

    def __init__(
        self,
        session_manager: SessionManager,
        config: Optional[WebSocketConfig] = None
    ):
        """
        Initialize WebSocket client.

        Args:
            session_manager: Active SessionManager instance
            config: WebSocket configuration (default: CP Gateway)
        """
        if not HAS_WEBSOCKET:
            raise ImportError(
                "websocket-client not installed. "
                "Install with: pip install websocket-client"
            )

        self.session_manager = session_manager
        self.config = config or WebSocketConfig()

        # Connection state
        self.state = ConnectionState.DISCONNECTED
        self.ws: Optional[websocket.WebSocketApp] = None
        self.ws_thread: Optional[threading.Thread] = None

        # Subscriptions
        self.subscriptions: Dict[str, Dict[str, Any]] = {}  # topic -> subscription info
        self.callbacks: Dict[str, Callable] = {}  # topic -> callback function

        # Message handling
        self.message_queue: Queue = Queue(maxsize=self.config.message_queue_size)
        self.processing_thread: Optional[threading.Thread] = None
        self.running = False

        # Reconnection
        self.reconnect_attempts = 0
        self.last_reconnect_time = 0

        # Heartbeat
        self.heartbeat_thread: Optional[threading.Thread] = None
        self.last_heartbeat = time.time()

        logger.info(f"WebSocket client initialized: {self.config.url}")

    def connect(self) -> bool:
        """
        Connect to WebSocket server.

        Returns:
            True if connection successful, False otherwise
        """
        if self.state == ConnectionState.CONNECTED:
            logger.warning("Already connected")
            return True

        try:
            logger.info(f"Connecting to {self.config.url}...")
            self.state = ConnectionState.CONNECTING

            # Get session for authentication
            session = self.session_manager.get_session()

            # Create WebSocket connection
            self.ws = websocket.WebSocketApp(
                self.config.url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open,
                cookie=session.cookies.get_dict()  # Pass session cookies
            )

            # Start WebSocket thread
            self.running = True
            self.ws_thread = threading.Thread(
                target=self._run_websocket,
                daemon=True,
                name="WebSocket-Connection"
            )
            self.ws_thread.start()

            # Start message processing thread
            self.processing_thread = threading.Thread(
                target=self._process_messages,
                daemon=True,
                name="WebSocket-MessageProcessor"
            )
            self.processing_thread.start()

            # Wait for connection (max 10 seconds)
            timeout = time.time() + 10
            while self.state != ConnectionState.CONNECTED and time.time() < timeout:
                time.sleep(0.1)

            if self.state == ConnectionState.CONNECTED:
                logger.info("✅ WebSocket connected successfully")
                self.reconnect_attempts = 0
                return True
            else:
                logger.error("❌ WebSocket connection timeout")
                return False

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}", exc_info=True)
            self.state = ConnectionState.FAILED
            return False

    def disconnect(self):
        """Disconnect from WebSocket server and cleanup resources"""
        logger.info("Disconnecting WebSocket...")

        self.running = False
        self.state = ConnectionState.DISCONNECTED

        # Unsubscribe all
        for topic in list(self.subscriptions.keys()):
            self._unsubscribe(topic)

        # Close WebSocket
        if self.ws:
            self.ws.close()
            self.ws = None

        # Wait for threads to finish
        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=5)

        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=5)

        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=5)

        logger.info("✅ WebSocket disconnected")

    def subscribe_market_data(
        self,
        conid: int,
        callback: Callable[[Dict[str, Any]], None],
        fields: Optional[List[str]] = None
    ) -> str:
        """
        Subscribe to real-time market data for an instrument.

        Args:
            conid: Contract ID (e.g., 756733 for SPY)
            callback: Function to call when data received
            fields: List of field IDs to subscribe (default: last, bid, ask, volume)

        Returns:
            Subscription topic ID

        Example:
            >>> def on_quote(data):
            ...     print(f"Last: {data.get('31')}, Bid: {data.get('84')}")
            >>> topic = ws.subscribe_market_data(756733, on_quote)
        """
        fields = fields or self.config.default_fields
        topic = f"{SubscriptionType.MARKET_DATA.value}+{conid}"

        return self._subscribe(topic, {"fields": fields}, callback)

    def subscribe_market_depth(
        self,
        conid: int,
        callback: Callable[[Dict[str, Any]], None]
    ) -> str:
        """
        Subscribe to market depth (Level II) for an instrument.

        Args:
            conid: Contract ID
            callback: Function to call when depth data received

        Returns:
            Subscription topic ID
        """
        topic = f"{SubscriptionType.MARKET_DEPTH.value}+{conid}"
        return self._subscribe(topic, {}, callback)

    def subscribe_trades(
        self,
        conid: int,
        callback: Callable[[Dict[str, Any]], None]
    ) -> str:
        """
        Subscribe to time & sales (trades) for an instrument.

        Args:
            conid: Contract ID
            callback: Function to call when trade data received

        Returns:
            Subscription topic ID
        """
        topic = f"{SubscriptionType.TRADES.value}+{conid}"
        return self._subscribe(topic, {}, callback)

    def unsubscribe(self, topic: str):
        """
        Unsubscribe from a topic.

        Args:
            topic: Topic ID returned from subscribe_*
        """
        self._unsubscribe(topic)

    def _subscribe(
        self,
        topic: str,
        args: Dict[str, Any],
        callback: Callable
    ) -> str:
        """Internal subscribe method"""
        if topic in self.subscriptions:
            logger.warning(f"Already subscribed to {topic}")
            return topic

        message = {
            "topic": topic,
            "args": args
        }

        try:
            self.ws.send(json.dumps(message))
            self.subscriptions[topic] = {
                "args": args,
                "subscribed_at": datetime.now()
            }
            self.callbacks[topic] = callback
            logger.info(f"✅ Subscribed to {topic}")
            return topic

        except Exception as e:
            logger.error(f"Subscription failed for {topic}: {e}")
            raise

    def _unsubscribe(self, topic: str):
        """Internal unsubscribe method"""
        if topic not in self.subscriptions:
            logger.warning(f"Not subscribed to {topic}")
            return

        message = {
            "topic": topic,
            "unsub": True
        }

        try:
            if self.ws:
                self.ws.send(json.dumps(message))

            del self.subscriptions[topic]
            del self.callbacks[topic]
            logger.info(f"✅ Unsubscribed from {topic}")

        except Exception as e:
            logger.error(f"Unsubscribe failed for {topic}: {e}")

    def _run_websocket(self):
        """Run WebSocket connection (in thread)"""
        try:
            self.ws.run_forever(
                sslopt={"cert_reqs": 0} if not self.config.ssl_verify else None
            )
        except Exception as e:
            logger.error(f"WebSocket run error: {e}", exc_info=True)

    def _on_open(self, ws):
        """WebSocket connection opened"""
        logger.info("🔗 WebSocket connection opened")
        self.state = ConnectionState.CONNECTED

        # Start heartbeat
        self.heartbeat_thread = threading.Thread(
            target=self._send_heartbeat,
            daemon=True,
            name="WebSocket-Heartbeat"
        )
        self.heartbeat_thread.start()

    def _on_message(self, ws, message: str):
        """WebSocket message received"""
        try:
            # Add to queue for processing
            self.message_queue.put(message, block=False)
        except Exception as e:
            logger.warning(f"Message queue full, dropping message: {e}")

    def _on_error(self, ws, error):
        """WebSocket error occurred"""
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket connection closed"""
        logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.state = ConnectionState.DISCONNECTED

        # Auto-reconnect if enabled
        if self.config.auto_reconnect and self.running:
            self._reconnect()

    def _process_messages(self):
        """Process messages from queue (in thread)"""
        logger.info("Message processor started")

        while self.running:
            try:
                message = self.message_queue.get(timeout=1)
                self._handle_message(message)

            except Empty:
                continue
            except Exception as e:
                logger.error(f"Message processing error: {e}", exc_info=True)

        logger.info("Message processor stopped")

    def _handle_message(self, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)

            topic = data.get("topic")
            if not topic:
                logger.debug(f"Message without topic: {message}")
                return

            # Call registered callback
            if topic in self.callbacks:
                callback = self.callbacks[topic]
                callback(data.get("data", data))
            else:
                logger.debug(f"No callback for topic: {topic}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON message: {message} - {e}")
        except Exception as e:
            logger.error(f"Message handling error: {e}", exc_info=True)

    def _send_heartbeat(self):
        """Send periodic heartbeat/ping (in thread)"""
        logger.info("Heartbeat thread started")

        while self.running and self.state == ConnectionState.CONNECTED:
            try:
                time.sleep(self.config.heartbeat_interval)

                if self.ws:
                    self.ws.send(json.dumps({"ping": int(time.time() * 1000)}))
                    self.last_heartbeat = time.time()
                    logger.debug("❤️ Heartbeat sent")

            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

        logger.info("Heartbeat thread stopped")

    def _reconnect(self):
        """Attempt to reconnect with exponential backoff"""
        if self.reconnect_attempts >= self.config.max_reconnect_attempts:
            logger.error(f"Max reconnect attempts ({self.config.max_reconnect_attempts}) reached")
            self.state = ConnectionState.FAILED
            return

        # Exponential backoff
        delay = self.config.reconnect_delay * (2 ** self.reconnect_attempts)
        logger.info(f"Reconnecting in {delay}s (attempt {self.reconnect_attempts + 1})...")

        time.sleep(delay)

        self.reconnect_attempts += 1
        self.state = ConnectionState.RECONNECTING
        self.connect()

    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket statistics"""
        return {
            "state": self.state.value,
            "subscriptions": len(self.subscriptions),
            "queued_messages": self.message_queue.qsize(),
            "reconnect_attempts": self.reconnect_attempts,
            "last_heartbeat": datetime.fromtimestamp(self.last_heartbeat).isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"ClientPortalWebSocket("
            f"state={self.state.value}, "
            f"subscriptions={len(self.subscriptions)})"
        )


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================

if __name__ == '__main__':
    """Example usage of WebSocket client"""
    # Initialize SpyderLogger for main execution
    SpyderLogger.initialize(log_level='INFO')

    print("=" * 70)
    print("IBKR Client Portal API - WebSocket Example")
    print("=" * 70)

    try:
        from .SpyderB09_ClientPortal_Auth import CPGatewayAuth, CPGatewayConfig
        from .SpyderB09_ClientPortal_Session import SessionManager

        # Setup authentication
        gateway_config = CPGatewayConfig(host='localhost', port=5000)
        auth = CPGatewayAuth(gateway_config)

        # Create session manager
        session_mgr = SessionManager(auth, gateway_config.base_url)
        session_mgr.start()

        print("✅ Session started")

        # Create WebSocket client
        ws_client = ClientPortalWebSocket(session_mgr)
        ws_client.connect()

        print("✅ WebSocket connected")

        # Subscribe to SPY market data
        def on_spy_quote(data):
            print(f"SPY Quote: {data}")

        topic = ws_client.subscribe_market_data(
            conid=756733,  # SPY
            callback=on_spy_quote
        )

        print(f"✅ Subscribed to {topic}")
        print("\nReceiving market data... (Press Ctrl+C to stop)")

        # Keep running
        try:
            while True:
                time.sleep(1)
                stats = ws_client.get_stats()
                print(f"Stats: {stats}", end='\r')

        except KeyboardInterrupt:
            print("\n\nStopping...")

        # Cleanup
        ws_client.disconnect()
        session_mgr.stop()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("For more information, see:")
    print("  - CLIENT_PORTAL_WEB_API_BEST_PRACTICES.md")
    print("=" * 70)
