#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB09_ClientPortal_MarketData.py
Purpose: Unified market data interface for real-time and historical data from Client Portal API

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-11-09 Time: 14:30:00

Module Description:
    Unified market data interface combining WebSocket streaming and REST historical data.

    CORE FEATURES:
    - Real-time quotes via WebSocket
    - Historical OHLCV bars via REST
    - Multiple instrument management
    - Data caching and buffering
    - Automatic subscription management

    DATA TYPES:
    1. Real-Time Streaming (WebSocket):
       - Last price, bid/ask, volume
       - Market depth (Level II)
       - Time & sales (trades)

    2. Historical Data (REST):
       - OHLCV bars (1min, 5min, 1hour, 1day)
       - Historical period up to 1 year
       - Multiple bar sizes supported

    COMMON FIELD IDs (IBKR):
    - 31: Last price
    - 84: Bid price
    - 86: Ask price
    - 88: Total volume
    - 7295: Ask size
    - 7296: Bid size
    - 7308: Open price
    - 7309: High price
    - 7310: Low price
    - 7311: Close price

Module Constants:
    DEFAULT_BAR_SIZE (str): Default historical bar size ('1min')
    DEFAULT_PERIOD (str): Default historical period ('1d')
    MAX_CACHE_SIZE (int): Maximum cached quotes per instrument (1000)

Change Log:
    2025-11-09 (v1.0.0):
        - Initial implementation combining WebSocket + REST
        - Real-time quote streaming
        - Historical bar data retrieval
        - Quote caching and management

References:
    - CLIENT_PORTAL_WEB_API_BEST_PRACTICES.md
    - https://interactivebrokers.github.io/cpwebapi/
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
from threading import Lock

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
# (None required)

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from .SpyderB09_ClientPortal_RESTClient import ClientPortalRESTClient
from .SpyderB09_ClientPortal_WebSocket import ClientPortalWebSocket
from .SpyderB09_ClientPortal_Session import SessionManager
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

logger = SpyderLogger.get_logger(__name__)


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

__all__ = [
    # Data classes
    'Quote',
    'Bar',
    # Configuration
    'MarketDataConfig',
    # Manager
    'MarketDataManager',
]


# ==============================================================================
# MODULE CONSTANTS
# ==============================================================================

DEFAULT_BAR_SIZE = '1min'
DEFAULT_PERIOD = '1d'
MAX_CACHE_SIZE = 1000


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class Quote:
    """Real-time quote data"""
    conid: int
    timestamp: datetime
    last: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[int] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None

    @classmethod
    def from_websocket_data(cls, conid: int, data: Dict[str, Any]) -> 'Quote':
        """Create Quote from WebSocket message data"""
        return cls(
            conid=conid,
            timestamp=datetime.now(),
            last=data.get('31'),  # Last price
            bid=data.get('84'),  # Bid price
            ask=data.get('86'),  # Ask price
            volume=data.get('88'),  # Total volume
            bid_size=data.get('7296'),  # Bid size
            ask_size=data.get('7295'),  # Ask size
        )

    def __repr__(self) -> str:
        return (
            f"Quote(conid={self.conid}, last={self.last}, "
            f"bid={self.bid}, ask={self.ask}, volume={self.volume})"
        )


@dataclass
class Bar:
    """OHLCV bar data"""
    conid: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    @classmethod
    def from_api_data(cls, conid: int, data: Dict[str, Any]) -> 'Bar':
        """Create Bar from API response data"""
        return cls(
            conid=conid,
            timestamp=datetime.fromtimestamp(data.get('t', 0) / 1000),
            open=data.get('o', 0.0),
            high=data.get('h', 0.0),
            low=data.get('l', 0.0),
            close=data.get('c', 0.0),
            volume=data.get('v', 0),
        )

    def __repr__(self) -> str:
        return (
            f"Bar({self.timestamp.strftime('%Y-%m-%d %H:%M')}: "
            f"O={self.open}, H={self.high}, L={self.low}, "
            f"C={self.close}, V={self.volume})"
        )


# ==============================================================================
# CONFIGURATION
# ==============================================================================

@dataclass
class MarketDataConfig:
    """Market data manager configuration"""
    # Real-time settings
    enable_websocket: bool = True
    cache_quotes: bool = True
    max_cache_size: int = MAX_CACHE_SIZE

    # Historical data settings
    default_bar_size: str = DEFAULT_BAR_SIZE
    default_period: str = DEFAULT_PERIOD

    # Available bar sizes
    bar_sizes: List[str] = field(default_factory=lambda: [
        '1min', '2min', '3min', '5min', '10min', '15min', '30min',
        '1h', '2h', '3h', '4h', '8h',
        '1d', '1w', '1m'
    ])


# ==============================================================================
# MARKET DATA MANAGER
# ==============================================================================

class MarketDataManager:
    """
    Unified market data manager for real-time and historical data.

    Combines WebSocket streaming and REST API for comprehensive market data access.

    Features:
    - Real-time quote streaming (WebSocket)
    - Historical bar data (REST API)
    - Quote caching with size limits
    - Multiple instrument subscriptions
    - Thread-safe operations

    Usage:
        >>> from SpyderB_Broker.ClientPortalAPI import SessionManager, MarketDataManager
        >>> session_mgr = SessionManager(auth_client, base_url)
        >>> session_mgr.start()
        >>>
        >>> md_mgr = MarketDataManager(session_mgr)
        >>> md_mgr.start()
        >>>
        >>> # Subscribe to real-time quotes
        >>> def on_spy_quote(quote):
        ...     print(f"SPY: {quote.last} @ {quote.timestamp}")
        >>>
        >>> md_mgr.subscribe_quotes(756733, on_spy_quote)
        >>>
        >>> # Get historical bars
        >>> bars = md_mgr.get_historical_bars(
        ...     conid=756733,
        ...     period='1d',
        ...     bar_size='5min'
        ... )
        >>> print(f"Retrieved {len(bars)} bars")
        >>>
        >>> md_mgr.stop()

    Important:
        - Requires active SessionManager
        - WebSocket optional (can use REST only)
        - Quotes cached in memory (bounded by max_cache_size)
        - Historical data not cached (fetch as needed)
    """

    def __init__(
        self,
        session_manager: SessionManager,
        config: Optional[MarketDataConfig] = None
    ):
        """
        Initialize Market Data Manager.

        Args:
            session_manager: Active SessionManager instance
            config: Market data configuration
        """
        self.session_manager = session_manager
        self.config = config or MarketDataConfig()

        # REST client for historical data
        self.rest_client = ClientPortalRESTClient(session_manager)

        # WebSocket client for real-time data
        self.ws_client: Optional[ClientPortalWebSocket] = None

        # Quote cache: conid -> deque of Quote objects
        self.quote_cache: Dict[int, deque] = {}
        self.quote_cache_lock = Lock()

        # Subscriptions: conid -> list of callbacks
        self.subscriptions: Dict[int, List[Callable]] = {}
        self.subscription_lock = Lock()

        # State
        self.running = False

        logger.info("MarketDataManager initialized")

    def start(self) -> bool:
        """
        Start market data manager (connect WebSocket if enabled).

        Returns:
            True if started successfully
        """
        if self.running:
            logger.warning("Already running")
            return True

        try:
            self.running = True

            # Start WebSocket if enabled
            if self.config.enable_websocket:
                self.ws_client = ClientPortalWebSocket(self.session_manager)
                if not self.ws_client.connect():
                    logger.error("WebSocket connection failed")
                    return False
                logger.info("✅ WebSocket connected")

            logger.info("✅ MarketDataManager started")
            return True

        except Exception as e:
            logger.error(f"Failed to start MarketDataManager: {e}", exc_info=True)
            return False

    def stop(self):
        """Stop market data manager and cleanup resources"""
        logger.info("Stopping MarketDataManager...")

        self.running = False

        # Disconnect WebSocket
        if self.ws_client:
            self.ws_client.disconnect()
            self.ws_client = None

        # Clear subscriptions
        with self.subscription_lock:
            self.subscriptions.clear()

        # Clear cache
        with self.quote_cache_lock:
            self.quote_cache.clear()

        logger.info("✅ MarketDataManager stopped")

    def subscribe_quotes(
        self,
        conid: int,
        callback: Callable[[Quote], None]
    ) -> bool:
        """
        Subscribe to real-time quotes for an instrument.

        Args:
            conid: Contract ID
            callback: Function to call when quote received (receives Quote object)

        Returns:
            True if subscription successful

        Example:
            >>> def on_quote(quote: Quote):
            ...     print(f"SPY: {quote.last}")
            >>> md_mgr.subscribe_quotes(756733, on_quote)
        """
        if not self.ws_client:
            logger.error("WebSocket not enabled")
            return False

        try:
            # Add to subscriptions
            with self.subscription_lock:
                if conid not in self.subscriptions:
                    self.subscriptions[conid] = []
                self.subscriptions[conid].append(callback)

            # Initialize quote cache
            with self.quote_cache_lock:
                if conid not in self.quote_cache:
                    self.quote_cache[conid] = deque(maxlen=self.config.max_cache_size)

            # Subscribe via WebSocket
            def ws_callback(data: Dict[str, Any]):
                self._handle_quote_update(conid, data)

            self.ws_client.subscribe_market_data(conid, ws_callback)

            logger.info(f"✅ Subscribed to quotes for conid={conid}")
            return True

        except Exception as e:
            logger.error(f"Quote subscription failed for conid={conid}: {e}")
            return False

    def unsubscribe_quotes(self, conid: int):
        """
        Unsubscribe from quotes for an instrument.

        Args:
            conid: Contract ID
        """
        if not self.ws_client:
            return

        try:
            # Remove from subscriptions
            with self.subscription_lock:
                if conid in self.subscriptions:
                    del self.subscriptions[conid]

            # Unsubscribe from WebSocket
            topic = f"smd+{conid}"
            self.ws_client.unsubscribe(topic)

            logger.info(f"✅ Unsubscribed from quotes for conid={conid}")

        except Exception as e:
            logger.error(f"Unsubscribe failed for conid={conid}: {e}")

    def get_latest_quote(self, conid: int) -> Optional[Quote]:
        """
        Get the latest cached quote for an instrument.

        Args:
            conid: Contract ID

        Returns:
            Latest Quote or None if not available
        """
        with self.quote_cache_lock:
            if conid in self.quote_cache and len(self.quote_cache[conid]) > 0:
                return self.quote_cache[conid][-1]
        return None

    def get_historical_bars(
        self,
        conid: int,
        period: Optional[str] = None,
        bar_size: Optional[str] = None,
        outside_rth: bool = False
    ) -> List[Bar]:
        """
        Get historical OHLCV bars for an instrument.

        Args:
            conid: Contract ID
            period: Time period (e.g., '1d', '1w', '1m', '1y')
            bar_size: Bar size (e.g., '1min', '5min', '1h', '1d')
            outside_rth: Include outside regular trading hours

        Returns:
            List of Bar objects

        Example:
            >>> bars = md_mgr.get_historical_bars(
            ...     conid=756733,  # SPY
            ...     period='1d',
            ...     bar_size='5min'
            ... )
            >>> print(f"Retrieved {len(bars)} 5-minute bars for today")
        """
        period = period or self.config.default_period
        bar_size = bar_size or self.config.default_bar_size

        try:
            # Validate bar size
            if bar_size not in self.config.bar_sizes:
                logger.warning(f"Invalid bar size '{bar_size}', using default")
                bar_size = self.config.default_bar_size

            # Build API request
            endpoint = f"/iserver/marketdata/history"
            params = {
                'conid': conid,
                'period': period,
                'bar': bar_size,
                'outsideRth': outside_rth
            }

            # Make request
            response = self.rest_client.get(endpoint, params=params)

            # Parse response
            if 'data' not in response:
                logger.warning(f"No data in response for conid={conid}")
                return []

            bars = [
                Bar.from_api_data(conid, bar_data)
                for bar_data in response['data']
            ]

            logger.info(f"✅ Retrieved {len(bars)} bars for conid={conid}")
            return bars

        except Exception as e:
            logger.error(f"Failed to get historical bars for conid={conid}: {e}")
            return []

    def get_snapshot(self, conid: int, fields: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Get market data snapshot for an instrument (REST API).

        Args:
            conid: Contract ID
            fields: List of field IDs (default: 31, 84, 86)

        Returns:
            Dictionary with snapshot data

        Example:
            >>> snapshot = md_mgr.get_snapshot(756733, fields=[31, 84, 86])
            >>> print(f"SPY: Last={snapshot.get('31')}")
        """
        fields = fields or [31, 84, 86]  # Last, bid, ask

        try:
            endpoint = f"/iserver/marketdata/snapshot"
            params = {
                'conids': conid,
                'fields': ','.join(map(str, fields))
            }

            response = self.rest_client.get(endpoint, params=params)

            if isinstance(response, list) and len(response) > 0:
                return response[0]
            return response

        except Exception as e:
            logger.error(f"Failed to get snapshot for conid={conid}: {e}")
            return {}

    def _handle_quote_update(self, conid: int, data: Dict[str, Any]):
        """Handle quote update from WebSocket"""
        try:
            # Create Quote object
            quote = Quote.from_websocket_data(conid, data)

            # Cache quote
            if self.config.cache_quotes:
                with self.quote_cache_lock:
                    if conid in self.quote_cache:
                        self.quote_cache[conid].append(quote)

            # Call all callbacks
            with self.subscription_lock:
                if conid in self.subscriptions:
                    for callback in self.subscriptions[conid]:
                        try:
                            callback(quote)
                        except Exception as e:
                            logger.error(f"Callback error for conid={conid}: {e}")

        except Exception as e:
            logger.error(f"Quote update handling error for conid={conid}: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get market data manager statistics"""
        stats = {
            'running': self.running,
            'websocket_enabled': self.config.enable_websocket,
            'subscriptions': len(self.subscriptions),
            'cached_instruments': len(self.quote_cache),
        }

        if self.ws_client:
            stats['websocket'] = self.ws_client.get_stats()

        return stats

    def __repr__(self) -> str:
        return (
            f"MarketDataManager("
            f"running={self.running}, "
            f"subscriptions={len(self.subscriptions)})"
        )


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================

if __name__ == '__main__':
    """Example usage of Market Data Manager"""
    import time

    # Initialize SpyderLogger for main execution
    SpyderLogger.initialize(log_level='INFO')

    print("=" * 70)
    print("IBKR Client Portal API - Market Data Manager Example")
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

        # Create market data manager
        md_mgr = MarketDataManager(session_mgr)
        md_mgr.start()

        print("✅ Market data manager started")

        # Example 1: Subscribe to real-time quotes
        print("\n" + "-" * 70)
        print("Example 1: Real-time SPY quotes")
        print("-" * 70)

        quote_count = 0

        def on_spy_quote(quote: Quote):
            nonlocal quote_count
            quote_count += 1
            print(f"[{quote_count}] {quote}")

        md_mgr.subscribe_quotes(756733, on_spy_quote)  # SPY
        print("Subscribed to SPY quotes. Waiting for data...")

        # Let it run for 30 seconds
        time.sleep(30)

        # Example 2: Get historical bars
        print("\n" + "-" * 70)
        print("Example 2: Historical SPY 5-minute bars")
        print("-" * 70)

        bars = md_mgr.get_historical_bars(
            conid=756733,
            period='1d',
            bar_size='5min'
        )

        print(f"Retrieved {len(bars)} bars:")
        for bar in bars[:5]:  # Show first 5
            print(f"  {bar}")
        print(f"  ... ({len(bars) - 5} more)")

        # Example 3: Get snapshot
        print("\n" + "-" * 70)
        print("Example 3: Market data snapshot")
        print("-" * 70)

        snapshot = md_mgr.get_snapshot(756733)
        print(f"SPY Snapshot: {snapshot}")

        # Show statistics
        print("\n" + "-" * 70)
        print("Statistics")
        print("-" * 70)
        stats = md_mgr.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")

        # Cleanup
        print("\nCleaning up...")
        md_mgr.stop()
        session_mgr.stop()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("For more information, see:")
    print("  - CLIENT_PORTAL_WEB_API_BEST_PRACTICES.md")
    print("=" * 70)
