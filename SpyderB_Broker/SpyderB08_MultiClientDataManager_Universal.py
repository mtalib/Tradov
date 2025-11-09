#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Universal 8-Client Data Manager

Author: SPYDER AI System
Created: 2025-01-07
Module: SpyderB08_MultiClientDataManager_Universal.py

UNIVERSAL 8-CLIENT ARCHITECTURE:
===============================
Simplified design that works consistently with both IB Gateway and TWS API.
No dual-mode complexity - single configuration for maximum reliability.

CLIENT ALLOCATION:
- Client 1: Order Execution (CRITICAL) - Trading only
- Client 2: Administrative + News (SYSTEM) - System control + news feeds
- Client 3: Core Data (HIGH) - SPY, SPX, /ES, VIX - 1s updates
- Client 4: SPY Options (HIGH) - Options chains - 1s updates
- Client 5: Volatility + Market Internals (NORMAL) - 5s updates
- Client 6: Major Indices (NORMAL) - DIA, QQQ, IWM - 5s updates
- Client 7: Extended Assets + Sectors (LOW) - Bonds, ETFs - 30s updates
- Client 8: International (BATCH) - Global markets - 60s updates

BENEFITS:
- 100% symbol coverage (47 instruments)
- Single configuration to maintain
- Consistent behavior across all connections
- Simplified testing and debugging
- Future-proof architecture
"""

import asyncio
import logging
import threading
import time
import queue
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Union, Tuple
import json
from pathlib import Path

# Third-party imports
try:
    from ib_async import IB, util, Contract, Order, Ticker

    IB_ASYNC_AVAILABLE = True
except ImportError:
    IB_ASYNC_AVAILABLE = False
    print("⚠️ ib_async not available - using simulation mode")

# SPYDER imports
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

    UTILITIES_AVAILABLE = True
except ImportError:
    UTILITIES_AVAILABLE = False
    print("⚠️ SPYDER utilities not available - using basic logging")

# ================================================================================
# ENUMS AND CONSTANTS
# ================================================================================


class ClientPurpose(Enum):
    """Client purposes for universal 8-client architecture"""

    ORDER_EXECUTION = "order_execution"
    ADMIN_NEWS = "admin_news"  # Administrative + News consolidated
    CORE_DATA = "core_data"
    OPTIONS_DATA = "options_data"
    VOLATILITY_INTERNALS = "volatility_internals"  # Volatility + Market Internals
    MAJOR_INDICES = "major_indices"
    EXTENDED_SECTORS = "extended_sectors"  # Extended Assets + Sectors
    INTERNATIONAL = "international"


class DataPriority(Enum):
    """Data request priority levels"""

    CRITICAL = 1  # Order execution
    SYSTEM = 2  # Administrative + News
    HIGH = 3  # Real-time trading data
    NORMAL = 4  # Important market data
    LOW = 5  # Background data
    BATCH = 6  # Bulk operations


class NewsType(Enum):
    """News data types"""

    MARKET_NEWS = "market_news"
    EARNINGS = "earnings"
    ECONOMIC_DATA = "economic_data"
    CORPORATE_ACTIONS = "corporate_actions"
    ANALYST_UPGRADES = "analyst_upgrades"
    BREAKING_NEWS = "breaking_news"


# ================================================================================
# DATA CLASSES
# ================================================================================


@dataclass
class ClientInfo:
    """Universal client information"""

    client_id: int
    purpose: ClientPurpose
    symbols: List[str] = field(default_factory=list)
    update_frequency: float = 0.0
    is_connected: bool = False
    last_update: Optional[datetime] = None
    message_count: int = 0
    error_count: int = 0
    client_instance: Optional[Any] = None
    priority: DataPriority = DataPriority.NORMAL
    description: str = ""
    news_types: List[NewsType] = field(default_factory=list)


@dataclass
class NewsData:
    """News data structure"""

    news_id: str
    timestamp: datetime
    news_type: NewsType
    headline: str
    summary: str
    source: str
    symbols: List[str] = field(default_factory=list)
    urgency: str = "normal"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketDataTick:
    """Market data tick with enhanced metadata"""

    symbol: str
    timestamp: datetime
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    volume: Optional[int] = None
    client_id: Optional[int] = None
    tick_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderRequest:
    """Order request structure"""

    order_id: int
    symbol: str
    action: str
    quantity: int
    order_type: str
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    status: str = "pending"


# ================================================================================
# UNIVERSAL 8-CLIENT DATA MANAGER
# ================================================================================


class Universal8ClientDataManager:
    """
    Universal 8-Client Data Manager

    Simplified, consistent architecture that works identically with both
    IB Gateway and TWS API. No dual-mode complexity - single configuration
    for maximum reliability and maintainability.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 4002):
        """Initialize universal 8-client manager"""

        # Core components
        if UTILITIES_AVAILABLE:
            self.logger = SpyderLogger.get_logger("SpyderB08.Universal")
            self.error_handler = SpyderErrorHandler()
        else:
            self.logger = logging.getLogger("SpyderB08.Universal")
            self.error_handler = None

        # Connection settings
        self.host = host
        self.port = port
        self.readonly = True  # MAESTRO fix for stability
        self.timeout = 15.0
        self.race_condition_delay = 1.0  # MAESTRO proven delay

        # Client management
        self.clients: Dict[int, ClientInfo] = {}
        self.active_connections: Dict[int, IB] = {}
        self.is_running = False

        # Data management
        self.market_data: Dict[str, MarketDataTick] = {}
        self.news_data: Dict[str, NewsData] = {}
        self.data_callbacks: Dict[str, List[Callable]] = {}
        self.news_callbacks: List[Callable] = []

        # Order management
        self.order_queue = queue.Queue()
        self.active_orders: Dict[int, OrderRequest] = {}
        self.order_callbacks: List[Callable] = []

        # Threading and synchronization
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self.executor = ThreadPoolExecutor(
            max_workers=10, thread_name_prefix="Universal8Client"
        )

        # Performance tracking
        self.performance_metrics = {
            "total_messages": 0,
            "total_errors": 0,
            "successful_connections": 0,
            "news_items_processed": 0,
            "orders_processed": 0,
            "start_time": None,
            "last_heartbeat": None,
        }

        # Initialize client allocation
        self._initialize_universal_client_allocation()

        self.logger.info("🚀 Universal 8-Client Data Manager initialized")

    def _initialize_universal_client_allocation(self):
        """Initialize universal 8-client allocation"""

        self.logger.info("🔧 Initializing Universal 8-Client Architecture")

        # Universal 8-client configuration
        self.client_configs = {
            1: {
                "purpose": ClientPurpose.ORDER_EXECUTION,
                "symbols": [],
                "frequency": 0.0,
                "description": "Order Execution - CRITICAL PRIORITY",
                "priority": DataPriority.CRITICAL,
                "news_types": [],
            },
            2: {
                "purpose": ClientPurpose.ADMIN_NEWS,
                "symbols": [],
                "frequency": 0.0,
                "description": "Administrative + News - SYSTEM CONTROL",
                "priority": DataPriority.SYSTEM,
                "news_types": [
                    NewsType.BREAKING_NEWS,
                    NewsType.MARKET_NEWS,
                    NewsType.EARNINGS,
                    NewsType.ECONOMIC_DATA,
                    NewsType.CORPORATE_ACTIONS,
                    NewsType.ANALYST_UPGRADES,
                ],
            },
            3: {
                "purpose": ClientPurpose.CORE_DATA,
                "symbols": ["SPY", "SPX", "/ES", "VIX", "TICK-NYSE"],
                "frequency": 1.0,
                "description": "Core Market Data - 1s updates",
                "priority": DataPriority.HIGH,
                "news_types": [],
            },
            4: {
                "purpose": ClientPurpose.OPTIONS_DATA,
                "symbols": ["SPY_OPTIONS_0DTE", "SPY_OPTIONS_1DTE"],
                "frequency": 1.0,
                "description": "SPY Options Chains - 1s updates",
                "priority": DataPriority.HIGH,
                "news_types": [],
            },
            5: {
                "purpose": ClientPurpose.VOLATILITY_INTERNALS,
                "symbols": [
                    "VXV",
                    "VXMT",
                    "VVIX",
                    "UVXY",
                    "VIX9D",  # Volatility
                    "VUD",
                    "TRIN",
                    "ADD",
                    "CPC",
                    "PCALL",
                    "SKEW",  # Market Internals
                ],
                "frequency": 5.0,
                "description": "Volatility + Market Internals - 5s updates",
                "priority": DataPriority.NORMAL,
                "news_types": [],
            },
            6: {
                "purpose": ClientPurpose.MAJOR_INDICES,
                "symbols": [
                    "DIA",
                    "QQQ",
                    "IWM",
                    "DIA_OPTIONS_1DTE",
                    "QQQ_OPTIONS_1DTE",
                ],
                "frequency": 5.0,
                "description": "Major Indices - 5s updates",
                "priority": DataPriority.NORMAL,
                "news_types": [],
            },
            7: {
                "purpose": ClientPurpose.EXTENDED_SECTORS,
                "symbols": [
                    # Extended Assets
                    "TLT",
                    "LQD",
                    "DXY",
                    "GLD",
                    "SPY_OPTIONS_WEEKLY",
                    # Sector ETFs
                    "XLF",
                    "XLK",
                    "XLE",
                    "XLV",
                    "XLI",
                    "XLY",
                    "XLP",
                    "XLU",
                    "XLRE",
                    "XLC",
                    "XLB",
                ],
                "frequency": 30.0,
                "description": "Extended Assets + Sector ETFs - 30s updates",
                "priority": DataPriority.LOW,
                "news_types": [],
            },
            8: {
                "purpose": ClientPurpose.INTERNATIONAL,
                "symbols": [
                    "FTLC",
                    "AUD.JPY",
                    "DAX",
                    "HSI",
                    "EWJ",
                    "EWG",
                    "EWU",
                    "EWC",
                ],
                "frequency": 60.0,
                "description": "International Markets - 60s updates",
                "priority": DataPriority.BATCH,
                "news_types": [],
            },
        }

        # Create client instances
        for client_id, config in self.client_configs.items():
            client_info = ClientInfo(
                client_id=client_id,
                purpose=config["purpose"],
                symbols=config["symbols"].copy(),
                update_frequency=config["frequency"],
                priority=config["priority"],
                description=config["description"],
                news_types=config["news_types"].copy(),
            )
            self.clients[client_id] = client_info

        self.logger.info("✅ Universal 8-Client allocation initialized")
        self.logger.info(
            f"   Total symbols: {sum(len(c.symbols) for c in self.clients.values())}"
        )
        self.logger.info(
            f"   News client: Client 2 ({len(self.clients[2].news_types)} news types)"
        )

    # ================================================================================
    # CONNECTION MANAGEMENT
    # ================================================================================

    async def start(self):
        """Start the universal 8-client manager"""

        if self.is_running:
            self.logger.warning("Manager already running")
            return

        self.logger.info("🚀 Starting Universal 8-Client Data Manager...")

        try:
            # Start performance tracking
            self.performance_metrics["start_time"] = datetime.now()
            self.performance_metrics["last_heartbeat"] = datetime.now()

            # Start clients if IB API is available
            if IB_ASYNC_AVAILABLE:
                await self._start_all_clients()
            else:
                self.logger.info("📊 Running in simulation mode")
                # Simulate connections for testing
                for client_id in self.clients:
                    self.clients[client_id].is_connected = True

            self.is_running = True
            self.logger.info("✅ Universal 8-Client Manager started successfully")

        except Exception as e:
            self.logger.error(f"❌ Failed to start manager: {e}")
            if self.error_handler:
                self.error_handler.handle_error("STARTUP_ERROR", e)
            raise

    async def stop(self):
        """Stop the universal 8-client manager"""

        if not self.is_running:
            return

        self.logger.info("🛑 Stopping Universal 8-Client Data Manager...")

        try:
            # Signal stop
            self._stop_event.set()

            # Stop all clients
            await self._stop_all_clients()

            # Clean up resources
            self.executor.shutdown(wait=True)

            self.is_running = False
            self.logger.info("✅ Universal 8-Client Manager stopped")

        except Exception as e:
            self.logger.error(f"❌ Error during shutdown: {e}")
            if self.error_handler:
                self.error_handler.handle_error("SHUTDOWN_ERROR", e)

    async def _start_all_clients(self):
        """Start all 8 clients in priority order"""

        self.logger.info("🔌 Starting 8 clients in priority order...")

        # Sort by priority for optimal startup
        sorted_clients = sorted(self.clients.items(), key=lambda x: x[1].priority.value)

        for client_id, client_info in sorted_clients:
            try:
                await self._start_single_client(client_id)

                # MAESTRO race condition delay
                await asyncio.sleep(self.race_condition_delay)

            except Exception as e:
                self.logger.error(f"❌ Failed to start client {client_id}: {e}")
                if self.error_handler:
                    self.error_handler.handle_error(
                        f"CLIENT_{client_id}_START_ERROR", e
                    )

    async def _start_single_client(self, client_id: int):
        """Start a single client connection"""

        client_info = self.clients[client_id]

        try:
            self.logger.info(
                f"🔌 Starting Client {client_id}: {client_info.description}"
            )

            # Create and configure IB instance
            ib = IB()
            ib.RequestTimeout = self.timeout

            # Connect with MAESTRO proven settings
            await ib.connectAsync(
                host=self.host,
                port=self.port,
                clientId=client_id,
                timeout=self.timeout,
                readonly=self.readonly,  # MAESTRO fix: prevents reqExecutions timeout
            )

            # Store connection
            self.active_connections[client_id] = ib
            client_info.is_connected = True
            client_info.client_instance = ib
            client_info.last_update = datetime.now()

            # Set up event handlers
            self._setup_client_handlers(client_id, ib)

            # Subscribe to data if needed
            if client_info.symbols:
                await self._subscribe_client_data(client_id)

            # Set up news subscriptions for admin+news client
            if client_info.purpose == ClientPurpose.ADMIN_NEWS:
                await self._setup_news_subscriptions(client_id)

            self.performance_metrics["successful_connections"] += 1
            self.logger.info(f"✅ Client {client_id} connected successfully")

        except Exception as e:
            self.logger.error(f"❌ Failed to connect client {client_id}: {e}")
            if self.error_handler:
                self.error_handler.handle_error(f"CLIENT_{client_id}_CONNECT_ERROR", e)
            raise

    def _setup_client_handlers(self, client_id: int, ib: IB):
        """Set up event handlers for a client"""

        def on_pending_tickers(tickers):
            self._handle_market_data(client_id, tickers)

        def on_error(reqId, errorCode, errorString, contract):
            self._handle_client_error(
                client_id, reqId, errorCode, errorString, contract
            )

        def on_news_tick(news):
            self._handle_news_data(client_id, news)

        # Connect standard handlers
        ib.pendingTickersEvent += on_pending_tickers
        ib.errorEvent += on_error

        # News handler for admin+news client
        client_info = self.clients[client_id]
        if client_info.purpose == ClientPurpose.ADMIN_NEWS:
            ib.newsBulletinEvent += on_news_tick

    async def _stop_all_clients(self):
        """Stop all active clients"""

        self.logger.info("🔌 Stopping all clients...")

        for client_id in list(self.active_connections.keys()):
            await self._stop_single_client(client_id)

    async def _stop_single_client(self, client_id: int):
        """Stop a single client connection"""

        try:
            if client_id in self.active_connections:
                ib = self.active_connections[client_id]
                if ib.isConnected():
                    ib.disconnect()
                del self.active_connections[client_id]

            if client_id in self.clients:
                self.clients[client_id].is_connected = False
                self.clients[client_id].client_instance = None

            self.logger.info(f"✅ Client {client_id} stopped")

        except Exception as e:
            self.logger.error(f"❌ Error stopping client {client_id}: {e}")

    # ================================================================================
    # DATA SUBSCRIPTION MANAGEMENT
    # ================================================================================

    async def _subscribe_client_data(self, client_id: int):
        """Subscribe client to its assigned data feeds"""

        client_info = self.clients[client_id]
        ib = self.active_connections.get(client_id)

        if not ib or not client_info.symbols:
            return

        try:
            self.logger.info(
                f"📊 Subscribing Client {client_id} to {len(client_info.symbols)} symbols"
            )

            for symbol in client_info.symbols:
                # Create contract (simplified for demo - needs proper contract creation)
                contract = Contract()
                contract.symbol = symbol
                contract.secType = "STK"
                contract.exchange = "SMART"
                contract.currency = "USD"

                # Request market data
                ib.reqMktData(contract, "", False, False)

                await asyncio.sleep(0.1)  # Rate limiting

            self.logger.info(f"✅ Client {client_id} subscriptions completed")

        except Exception as e:
            self.logger.error(f"❌ Failed to subscribe client {client_id}: {e}")
            if self.error_handler:
                self.error_handler.handle_error(
                    f"CLIENT_{client_id}_SUBSCRIBE_ERROR", e
                )

    async def _setup_news_subscriptions(self, client_id: int):
        """Set up news subscriptions for admin+news client"""

        client_info = self.clients[client_id]
        ib = self.active_connections.get(client_id)

        if not ib:
            return

        try:
            self.logger.info(f"📰 Setting up news subscriptions for Client {client_id}")

            # Subscribe to news bulletins
            ib.reqNewsBulletins(allMsgs=True)

            self.logger.info(f"✅ News subscriptions active for Client {client_id}")

        except Exception as e:
            self.logger.error(f"❌ Failed to set up news for client {client_id}: {e}")

    # ================================================================================
    # DATA HANDLING
    # ================================================================================

    def _handle_market_data(self, client_id: int, tickers):
        """Handle incoming market data"""

        try:
            client_info = self.clients[client_id]

            for ticker in tickers:
                # Create market data tick
                tick = MarketDataTick(
                    symbol=ticker.contract.symbol,
                    timestamp=datetime.now(),
                    bid=getattr(ticker, "bid", None),
                    ask=getattr(ticker, "ask", None),
                    last=getattr(ticker, "last", None),
                    volume=getattr(ticker, "volume", None),
                    client_id=client_id,
                    tick_type="market_data",
                )

                # Store data
                self.market_data[ticker.contract.symbol] = tick

                # Update client metrics
                client_info.message_count += 1
                client_info.last_update = datetime.now()

                # Call data callbacks
                symbol_callbacks = self.data_callbacks.get(ticker.contract.symbol, [])
                for callback in symbol_callbacks:
                    try:
                        callback(tick)
                    except Exception as e:
                        self.logger.error(f"❌ Data callback error: {e}")

            self.performance_metrics["total_messages"] += len(tickers)

        except Exception as e:
            self.logger.error(f"❌ Error handling market data: {e}")
            self.performance_metrics["total_errors"] += 1

    def _handle_news_data(self, client_id: int, news):
        """Handle incoming news data"""

        try:
            # Create news data object
            news_item = NewsData(
                news_id=f"news_{int(time.time())}_{client_id}",
                timestamp=datetime.now(),
                news_type=NewsType.MARKET_NEWS,  # Default, could be parsed from content
                headline=getattr(news, "headline", "Unknown"),
                summary=getattr(news, "text", ""),
                source=getattr(news, "source", "IB"),
                urgency="normal",
            )

            # Store news
            self.news_data[news_item.news_id] = news_item

            # Update metrics
            self.performance_metrics["news_items_processed"] += 1

            # Call news callbacks
            for callback in self.news_callbacks:
                try:
                    callback(news_item)
                except Exception as e:
                    self.logger.error(f"❌ News callback error: {e}")

            self.logger.info(f"📰 News processed: {news_item.headline[:50]}...")

        except Exception as e:
            self.logger.error(f"❌ Error handling news data: {e}")
            self.performance_metrics["total_errors"] += 1

    def _handle_client_error(
        self, client_id: int, reqId, errorCode, errorString, contract
    ):
        """Handle client errors"""

        client_info = self.clients[client_id]
        client_info.error_count += 1
        self.performance_metrics["total_errors"] += 1

        self.logger.error(f"❌ Client {client_id} error {errorCode}: {errorString}")

        if self.error_handler:
            self.error_handler.handle_error(
                f"CLIENT_{client_id}_API_ERROR",
                f"Code: {errorCode}, Message: {errorString}",
            )

    # ================================================================================
    # ORDER MANAGEMENT
    # ================================================================================

    async def place_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str = "MKT",
        limit_price: float = None,
    ) -> int:
        """Place order through Client 1 (Order Execution)"""

        if not self.is_running:
            raise RuntimeError("Manager not running")

        # Generate order ID
        order_id = int(time.time() * 1000) % 1000000

        # Create order request
        order_request = OrderRequest(
            order_id=order_id,
            symbol=symbol,
            action=action,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
        )

        try:
            # Use Client 1 for order execution
            client_1 = self.active_connections.get(1)
            if not client_1:
                raise RuntimeError("Order execution client not available")

            # Store order
            self.active_orders[order_id] = order_request

            # Create IB contract and order (simplified)
            contract = Contract()
            contract.symbol = symbol
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"

            order = Order()
            order.action = action
            order.totalQuantity = quantity
            order.orderType = order_type
            if limit_price:
                order.lmtPrice = limit_price

            # Place order
            client_1.placeOrder(order_id, contract, order)

            order_request.status = "submitted"
            self.performance_metrics["orders_processed"] += 1

            self.logger.info(
                f"📋 Order {order_id} placed: {action} {quantity} {symbol}"
            )

            return order_id

        except Exception as e:
            order_request.status = "failed"
            self.logger.error(f"❌ Failed to place order {order_id}: {e}")
            if self.error_handler:
                self.error_handler.handle_error("ORDER_PLACEMENT_ERROR", e)
            raise

    async def cancel_order(self, order_id: int):
        """Cancel order through Client 1"""

        try:
            client_1 = self.active_connections.get(1)
            if not client_1:
                raise RuntimeError("Order execution client not available")

            client_1.cancelOrder(order_id)

            if order_id in self.active_orders:
                self.active_orders[order_id].status = "cancelled"

            self.logger.info(f"🚫 Order {order_id} cancelled")

        except Exception as e:
            self.logger.error(f"❌ Failed to cancel order {order_id}: {e}")
            raise

    # ================================================================================
    # PUBLIC API
    # ================================================================================

    def subscribe_to_data(self, symbol: str, callback: Callable):
        """Subscribe to data updates for a symbol"""

        if symbol not in self.data_callbacks:
            self.data_callbacks[symbol] = []

        self.data_callbacks[symbol].append(callback)
        self.logger.info(f"📊 Callback registered for symbol: {symbol}")

    def subscribe_to_news(self, callback: Callable):
        """Subscribe to news updates"""

        self.news_callbacks.append(callback)
        self.logger.info("📰 News callback registered")

    def add_order_callback(self, callback: Callable):
        """Add order status callback"""

        self.order_callbacks.append(callback)
        self.logger.info("📋 Order callback registered")

    def get_market_data(self, symbol: str) -> Optional[MarketDataTick]:
        """Get latest market data for a symbol"""

        return self.market_data.get(symbol)

    def get_recent_news(self, limit: int = 10) -> List[NewsData]:
        """Get recent news items"""

        sorted_news = sorted(
            self.news_data.values(), key=lambda x: x.timestamp, reverse=True
        )
        return sorted_news[:limit]

    def get_client_status(self, client_id: int) -> Optional[Dict[str, Any]]:
        """Get status of a specific client"""

        if client_id not in self.clients:
            return None

        client_info = self.clients[client_id]
        return {
            "client_id": client_id,
            "purpose": client_info.purpose.value,
            "description": client_info.description,
            "is_connected": client_info.is_connected,
            "symbols_count": len(client_info.symbols),
            "message_count": client_info.message_count,
            "error_count": client_info.error_count,
            "last_update": client_info.last_update.isoformat()
            if client_info.last_update
            else None,
            "priority": client_info.priority.name,
            "news_types": [nt.value for nt in client_info.news_types],
        }

    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""

        connected_clients = sum(1 for c in self.clients.values() if c.is_connected)
        total_messages = sum(c.message_count for c in self.clients.values())
        total_errors = sum(c.error_count for c in self.clients.values())

        uptime = None
        if self.performance_metrics["start_time"]:
            uptime = (
                datetime.now() - self.performance_metrics["start_time"]
            ).total_seconds()

        return {
            "is_running": self.is_running,
            "architecture": "universal_8_client",
            "connected_clients": connected_clients,
            "total_clients": len(self.clients),
            "total_symbols": sum(len(c.symbols) for c in self.clients.values()),
            "total_messages": total_messages,
            "total_errors": total_errors,
            "news_items": len(self.news_data),
            "active_orders": len(self.active_orders),
            "uptime_seconds": uptime,
            "performance_metrics": self.performance_metrics.copy(),
        }

    def get_all_symbols(self) -> List[str]:
        """Get all symbols across all clients"""

        all_symbols = set()
        for client_info in self.clients.values():
            all_symbols.update(client_info.symbols)
        return sorted(list(all_symbols))

    # ================================================================================
    # UTILITY METHODS
    # ================================================================================

    def export_configuration(self) -> Dict[str, Any]:
        """Export current configuration for backup/analysis"""

        return {
            "architecture": "universal_8_client",
            "connection_settings": {
                "host": self.host,
                "port": self.port,
                "readonly": self.readonly,
                "timeout": self.timeout,
                "race_condition_delay": self.race_condition_delay,
            },
            "client_configs": {
                str(client_id): {
                    "purpose": info.purpose.value,
                    "description": info.description,
                    "symbols": info.symbols,
                    "frequency": info.update_frequency,
                    "priority": info.priority.value,
                    "news_types": [nt.value for nt in info.news_types],
                }
                for client_id, info in self.clients.items()
            },
            "performance_summary": {
                "total_symbols": sum(len(c.symbols) for c in self.clients.values()),
                "news_enabled": any(c.news_types for c in self.clients.values()),
                "client_load_distribution": {
                    "low": sum(1 for c in self.clients.values() if len(c.symbols) <= 5),
                    "medium": sum(
                        1 for c in self.clients.values() if 5 < len(c.symbols) <= 10
                    ),
                    "high": sum(
                        1 for c in self.clients.values() if len(c.symbols) > 10
                    ),
                },
            },
            "timestamp": datetime.now().isoformat(),
        }


# ================================================================================
# SINGLETON PATTERN
# ================================================================================

_manager_instance: Optional[Universal8ClientDataManager] = None


def get_universal_manager_instance() -> Universal8ClientDataManager:
    """Get the singleton manager instance"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = Universal8ClientDataManager()
    return _manager_instance


def reset_universal_manager_instance():
    """Reset the singleton manager instance"""
    global _manager_instance
    if _manager_instance and _manager_instance.is_running:
        asyncio.run(_manager_instance.stop())
    _manager_instance = None


# ================================================================================
# MAIN FUNCTION FOR TESTING
# ================================================================================


async def main():
    """Test the universal 8-client manager"""

    print("🚀 Testing Universal 8-Client Data Manager")
    print("=" * 60)

    # Create manager
    manager = Universal8ClientDataManager()

    try:
        # Start manager
        await manager.start()

        # Test callbacks
        def test_data_callback(tick: MarketDataTick):
            print(f"📊 Data: {tick.symbol} = {tick.last} @ {tick.timestamp}")

        def test_news_callback(news: NewsData):
            print(f"📰 News: {news.headline}")

        def test_order_callback(order_status):
            print(f"📋 Order: {order_status}")

        # Subscribe to test data
        manager.subscribe_to_data("SPY", test_data_callback)
        manager.subscribe_to_news(test_news_callback)
        manager.add_order_callback(test_order_callback)

        # Show system status
        status = manager.get_system_status()
        print(f"\n📊 System Status:")
        print(f"   Architecture: {status['architecture']}")
        print(f"   Clients: {status['connected_clients']}/{status['total_clients']}")
        print(f"   Total Symbols: {status['total_symbols']}")
        print(f"   Messages: {status['total_messages']}")
        print(f"   Errors: {status['total_errors']}")
        print(f"   News Items: {status['news_items']}")
        print(f"   Active Orders: {status['active_orders']}")

        # Show client details
        print(f"\n🔌 Universal 8-Client Status:")
        for client_id in sorted(manager.clients.keys()):
            client_status = manager.get_client_status(client_id)
            if client_status:
                status_icon = "✅" if client_status["is_connected"] else "❌"
                print(
                    f"   {status_icon} Client {client_id}: {client_status['description']}"
                )
                print(
                    f"      └─ {client_status['symbols_count']} symbols, Priority: {client_status['priority']}"
                )
                if client_status["news_types"]:
                    print(f"      └─ News: {', '.join(client_status['news_types'])}")

        # Show all symbols
        all_symbols = manager.get_all_symbols()
        print(f"\n📈 All Symbols ({len(all_symbols)}):")
        print(
            f"   {', '.join(all_symbols[:10])}{'...' if len(all_symbols) > 10 else ''}"
        )

        # Export configuration
        config = manager.export_configuration()
        config_file = Path("universal_8client_config.json")
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        print(f"\n💾 Configuration exported to: {config_file}")

        # Keep running for a bit
        print(f"\n⏳ Running for 30 seconds...")
        await asyncio.sleep(30)

    finally:
        # Clean shutdown
        await manager.stop()
        print("\n✅ Test completed")


if __name__ == "__main__":
    asyncio.run(main())
