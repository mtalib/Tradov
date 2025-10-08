#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Enhanced Multi-Client Data Manager with TWS/Gateway Dual Compatibility

Author: SPYDER AI System
Created: 2025-01-07
Enhanced from: SpyderB08_MultiClientDataManager.py

MAJOR ENHANCEMENTS:
- TWS/Gateway dual compatibility (8 vs 11+ client modes)
- Dedicated News Client (Client 11)
- Smart client consolidation for TWS mode
- Dynamic connection type detection
- Enhanced error handling and failover
- Modern async/await patterns
- Comprehensive logging and monitoring

CONNECTION MODES:
- TWS MODE: 8 clients max (automatic consolidation)
- GATEWAY MODE: 11+ clients (full separation)
- AUTO-DETECT: Automatically selects optimal mode

CLIENT ALLOCATION STRATEGY:
TWS Mode (8 clients):
1. Order Execution (CRITICAL)
2. Administrative + News (SYSTEM)
3. Core Data (HIGH)
4. SPY Options (HIGH)
5. Volatility + Market Internals (NORMAL)
6. Major Indices (NORMAL)
7. Extended Assets + Sectors (LOW)
8. International + Batch (BATCH)

Gateway Mode (11 clients):
1. Order Execution (CRITICAL)
2. Administrative (SYSTEM)
3. Core Data (HIGH)
4. SPY Options (HIGH)
5. Volatility Data (NORMAL)
6. Market Internals (NORMAL)
7. Major Indices (NORMAL)
8. Extended Assets (LOW)
9. Sector ETFs (LOW)
10. International (BATCH)
11. News & Alerts (NEWS)
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


class ConnectionMode(Enum):
    """Connection mode for client management"""

    AUTO_DETECT = "auto_detect"
    TWS_MODE = "tws_mode"  # 8 clients max
    GATEWAY_MODE = "gateway_mode"  # 11+ clients
    SIMULATION = "simulation"


class ClientPurpose(Enum):
    """Enhanced client purposes with news support"""

    ORDER_EXECUTION = "order_execution"
    ADMINISTRATIVE = "administrative"
    CORE_DATA = "core_data"
    OPTIONS_DATA = "options_data"
    VOLATILITY_DATA = "volatility_data"
    MARKET_INTERNALS = "market_internals"
    MAJOR_INDICES = "major_indices"
    EXTENDED_ASSETS = "extended_assets"
    SECTOR_ETFS = "sector_etfs"
    INTERNATIONAL = "international"
    NEWS_ALERTS = "news_alerts"  # NEW: Dedicated news client
    CONSOLIDATED_LOW = "consolidated_low"  # NEW: For TWS mode consolidation
    CONSOLIDATED_BATCH = "consolidated_batch"  # NEW: For TWS mode consolidation


class DataPriority(Enum):
    """Data request priority levels"""

    CRITICAL = 1  # Order execution
    SYSTEM = 2  # Administrative
    HIGH = 3  # Real-time trading data
    NORMAL = 4  # Important market data
    LOW = 5  # Background data
    BATCH = 6  # Bulk operations
    NEWS = 7  # News and alerts


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
    """Enhanced client information with news support"""

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
    consolidated_purposes: List[ClientPurpose] = field(
        default_factory=list
    )  # For TWS mode
    news_types: List[NewsType] = field(default_factory=list)  # For news client


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
    urgency: str = "normal"  # low, normal, high, critical
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
class ConnectionConfig:
    """Connection configuration for different modes"""

    mode: ConnectionMode
    max_clients: int
    port: int
    host: str = "127.0.0.1"
    readonly: bool = True
    timeout: float = 15.0
    race_condition_delay: float = 1.0  # MAESTRO fix


# ================================================================================
# ENHANCED MULTI-CLIENT DATA MANAGER
# ================================================================================


class EnhancedMultiClientDataManager:
    """
    Enhanced Multi-Client Data Manager with TWS/Gateway Dual Compatibility

    Features:
    - Auto-detection of TWS vs Gateway
    - Smart client consolidation for TWS mode
    - Dedicated news client support
    - Modern async/await patterns
    - Comprehensive error handling
    - Performance monitoring
    """

    def __init__(self, connection_mode: ConnectionMode = ConnectionMode.AUTO_DETECT):
        """Initialize enhanced multi-client manager"""

        # Core components
        if UTILITIES_AVAILABLE:
            self.logger = SpyderLogger.get_logger("SpyderB08.Enhanced")
            self.error_handler = SpyderErrorHandler()
        else:
            self.logger = logging.getLogger("SpyderB08.Enhanced")
            self.error_handler = None

        # Connection management
        self.connection_mode = connection_mode
        self.detected_mode: Optional[ConnectionMode] = None
        self.connection_config: Optional[ConnectionConfig] = None

        # Client management
        self.clients: Dict[int, ClientInfo] = {}
        self.active_connections: Dict[int, IB] = {}
        self.is_running = False

        # Data management
        self.market_data: Dict[str, MarketDataTick] = {}
        self.news_data: Dict[str, NewsData] = {}
        self.data_callbacks: Dict[str, List[Callable]] = {}
        self.news_callbacks: List[Callable] = []

        # Threading and synchronization
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self.executor = ThreadPoolExecutor(
            max_workers=15, thread_name_prefix="EnhancedMultiClient"
        )

        # Performance tracking
        self.performance_metrics = {
            "total_messages": 0,
            "total_errors": 0,
            "connection_attempts": 0,
            "successful_connections": 0,
            "news_items_processed": 0,
            "start_time": None,
            "last_heartbeat": None,
        }

        self.logger.info("🚀 Enhanced Multi-Client Data Manager initialized")

    # ================================================================================
    # CONNECTION MODE DETECTION AND CONFIGURATION
    # ================================================================================

    async def detect_connection_mode(self) -> ConnectionMode:
        """Auto-detect optimal connection mode (TWS vs Gateway)"""

        self.logger.info("🔍 Auto-detecting connection mode...")

        # Test ports to determine available service
        test_configs = [
            (4002, ConnectionMode.GATEWAY_MODE, "IB Gateway Paper"),
            (4001, ConnectionMode.GATEWAY_MODE, "IB Gateway Live"),
            (7497, ConnectionMode.TWS_MODE, "TWS Paper"),
            (7496, ConnectionMode.TWS_MODE, "TWS Live"),
        ]

        for port, mode, description in test_configs:
            try:
                # Quick connection test
                import socket

                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex(("127.0.0.1", port))
                sock.close()

                if result == 0:
                    self.logger.info(f"✅ Detected {description} on port {port}")
                    self.detected_mode = mode
                    self.connection_config = ConnectionConfig(
                        mode=mode,
                        max_clients=8 if mode == ConnectionMode.TWS_MODE else 11,
                        port=port,
                    )
                    return mode

            except Exception as e:
                self.logger.debug(f"Port {port} test failed: {e}")
                continue

        # Fallback to simulation
        self.logger.warning("No IB service detected - using simulation mode")
        self.detected_mode = ConnectionMode.SIMULATION
        self.connection_config = ConnectionConfig(
            mode=ConnectionMode.SIMULATION, max_clients=11, port=0
        )
        return ConnectionMode.SIMULATION

    def _initialize_client_allocation(self):
        """Initialize client allocation based on detected mode"""

        if not self.connection_config:
            raise RuntimeError("Connection config not initialized")

        mode = self.connection_config.mode
        max_clients = self.connection_config.max_clients

        self.logger.info(
            f"🔧 Initializing client allocation for {mode.value} ({max_clients} clients)"
        )

        if mode == ConnectionMode.TWS_MODE:
            self._initialize_tws_allocation()
        elif mode in [ConnectionMode.GATEWAY_MODE, ConnectionMode.SIMULATION]:
            self._initialize_gateway_allocation()
        else:
            raise ValueError(f"Unsupported connection mode: {mode}")

    def _initialize_tws_allocation(self):
        """Initialize TWS mode allocation (8 clients with consolidation)"""

        self.client_configs = {
            1: {
                "purpose": ClientPurpose.ORDER_EXECUTION,
                "symbols": [],
                "frequency": 0.0,
                "description": "Order execution - CRITICAL PRIORITY",
                "priority": DataPriority.CRITICAL,
                "consolidated_purposes": [],
            },
            2: {
                "purpose": ClientPurpose.ADMINISTRATIVE,
                "symbols": [],
                "frequency": 0.0,
                "description": "Administrative + News (CONSOLIDATED)",
                "priority": DataPriority.SYSTEM,
                "consolidated_purposes": [
                    ClientPurpose.ADMINISTRATIVE,
                    ClientPurpose.NEWS_ALERTS,
                ],
                "news_types": [
                    NewsType.BREAKING_NEWS,
                    NewsType.MARKET_NEWS,
                    NewsType.EARNINGS,
                ],
            },
            3: {
                "purpose": ClientPurpose.CORE_DATA,
                "symbols": ["SPY", "SPX", "/ES", "VIX", "TICK-NYSE"],
                "frequency": 1.0,
                "description": "Core market data - 1s updates",
                "priority": DataPriority.HIGH,
                "consolidated_purposes": [],
            },
            4: {
                "purpose": ClientPurpose.OPTIONS_DATA,
                "symbols": ["SPY_OPTIONS_0DTE", "SPY_OPTIONS_1DTE"],
                "frequency": 1.0,
                "description": "SPY options chains - 1s updates",
                "priority": DataPriority.HIGH,
                "consolidated_purposes": [],
            },
            5: {
                "purpose": ClientPurpose.CONSOLIDATED_LOW,
                "symbols": [
                    "VXV",
                    "VXMT",
                    "VVIX",
                    "UVXY",
                    "VIX9D",
                    "VUD",
                    "TRIN",
                    "ADD",
                    "CPC",
                    "PCALL",
                    "SKEW",
                ],
                "frequency": 5.0,
                "description": "Volatility + Market Internals (CONSOLIDATED)",
                "priority": DataPriority.NORMAL,
                "consolidated_purposes": [
                    ClientPurpose.VOLATILITY_DATA,
                    ClientPurpose.MARKET_INTERNALS,
                ],
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
                "description": "Major indices - 5s updates",
                "priority": DataPriority.NORMAL,
                "consolidated_purposes": [],
            },
            7: {
                "purpose": ClientPurpose.CONSOLIDATED_LOW,
                "symbols": [
                    "TLT",
                    "LQD",
                    "DXY",
                    "GLD",
                    "SPY_OPTIONS_WEEKLY",
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
                "description": "Extended Assets + Sectors (CONSOLIDATED)",
                "priority": DataPriority.LOW,
                "consolidated_purposes": [
                    ClientPurpose.EXTENDED_ASSETS,
                    ClientPurpose.SECTOR_ETFS,
                ],
            },
            8: {
                "purpose": ClientPurpose.CONSOLIDATED_BATCH,
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
                "description": "International + Batch (CONSOLIDATED)",
                "priority": DataPriority.BATCH,
                "consolidated_purposes": [ClientPurpose.INTERNATIONAL],
            },
        }

        self._create_client_instances()
        self.logger.info(
            "✅ TWS mode client allocation initialized (8 clients with consolidation)"
        )

    def _initialize_gateway_allocation(self):
        """Initialize Gateway mode allocation (11 clients with dedicated news)"""

        self.client_configs = {
            1: {
                "purpose": ClientPurpose.ORDER_EXECUTION,
                "symbols": [],
                "frequency": 0.0,
                "description": "Order execution - CRITICAL PRIORITY",
                "priority": DataPriority.CRITICAL,
                "consolidated_purposes": [],
            },
            2: {
                "purpose": ClientPurpose.ADMINISTRATIVE,
                "symbols": [],
                "frequency": 0.0,
                "description": "Administrative operations",
                "priority": DataPriority.SYSTEM,
                "consolidated_purposes": [],
            },
            3: {
                "purpose": ClientPurpose.CORE_DATA,
                "symbols": ["SPY", "SPX", "/ES", "VIX", "TICK-NYSE"],
                "frequency": 1.0,
                "description": "Core market data - 1s updates",
                "priority": DataPriority.HIGH,
                "consolidated_purposes": [],
            },
            4: {
                "purpose": ClientPurpose.OPTIONS_DATA,
                "symbols": ["SPY_OPTIONS_0DTE", "SPY_OPTIONS_1DTE"],
                "frequency": 1.0,
                "description": "SPY options chains - 1s updates",
                "priority": DataPriority.HIGH,
                "consolidated_purposes": [],
            },
            5: {
                "purpose": ClientPurpose.VOLATILITY_DATA,
                "symbols": ["VXV", "VXMT", "VVIX", "UVXY", "VIX9D"],
                "frequency": 5.0,
                "description": "Volatility indicators - 5s updates",
                "priority": DataPriority.NORMAL,
                "consolidated_purposes": [],
            },
            6: {
                "purpose": ClientPurpose.MARKET_INTERNALS,
                "symbols": ["VUD", "TRIN", "ADD", "CPC", "PCALL", "SKEW"],
                "frequency": 5.0,
                "description": "Market internals - 5s updates",
                "priority": DataPriority.NORMAL,
                "consolidated_purposes": [],
            },
            7: {
                "purpose": ClientPurpose.MAJOR_INDICES,
                "symbols": [
                    "DIA",
                    "QQQ",
                    "IWM",
                    "DIA_OPTIONS_1DTE",
                    "QQQ_OPTIONS_1DTE",
                ],
                "frequency": 5.0,
                "description": "Major indices - 5s updates",
                "priority": DataPriority.NORMAL,
                "consolidated_purposes": [],
            },
            8: {
                "purpose": ClientPurpose.EXTENDED_ASSETS,
                "symbols": ["TLT", "LQD", "DXY", "GLD", "SPY_OPTIONS_WEEKLY"],
                "frequency": 15.0,
                "description": "Extended assets - 15s updates",
                "priority": DataPriority.LOW,
                "consolidated_purposes": [],
            },
            9: {
                "purpose": ClientPurpose.SECTOR_ETFS,
                "symbols": [
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
                "description": "Sector ETFs - 30s updates",
                "priority": DataPriority.LOW,
                "consolidated_purposes": [],
            },
            10: {
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
                "description": "International markets - 60s updates",
                "priority": DataPriority.BATCH,
                "consolidated_purposes": [],
            },
            11: {
                "purpose": ClientPurpose.NEWS_ALERTS,
                "symbols": [],
                "frequency": 0.0,
                "description": "News & Alerts - DEDICATED NEWS CLIENT",
                "priority": DataPriority.NEWS,
                "consolidated_purposes": [],
                "news_types": [
                    NewsType.BREAKING_NEWS,
                    NewsType.MARKET_NEWS,
                    NewsType.EARNINGS,
                    NewsType.ECONOMIC_DATA,
                    NewsType.CORPORATE_ACTIONS,
                    NewsType.ANALYST_UPGRADES,
                ],
            },
        }

        self._create_client_instances()
        self.logger.info(
            "✅ Gateway mode client allocation initialized (11 clients with dedicated news)"
        )

    def _create_client_instances(self):
        """Create ClientInfo instances from configuration"""

        for client_id, config in self.client_configs.items():
            client_info = ClientInfo(
                client_id=client_id,
                purpose=config["purpose"],
                symbols=config["symbols"].copy(),
                update_frequency=config["frequency"],
                priority=config["priority"],
                description=config["description"],
                consolidated_purposes=config.get("consolidated_purposes", []),
                news_types=config.get("news_types", []),
            )
            self.clients[client_id] = client_info

    # ================================================================================
    # CONNECTION MANAGEMENT
    # ================================================================================

    async def start(self):
        """Start the enhanced multi-client manager"""

        if self.is_running:
            self.logger.warning("Manager already running")
            return

        self.logger.info("🚀 Starting Enhanced Multi-Client Data Manager...")

        try:
            # Auto-detect connection mode if needed
            if self.connection_mode == ConnectionMode.AUTO_DETECT:
                await self.detect_connection_mode()

            # Initialize client allocation
            self._initialize_client_allocation()

            # Start performance tracking
            self.performance_metrics["start_time"] = datetime.now()
            self.performance_metrics["last_heartbeat"] = datetime.now()

            # Start clients based on mode
            if self.connection_config.mode != ConnectionMode.SIMULATION:
                await self._start_all_clients()
            else:
                self.logger.info("📊 Running in simulation mode")

            self.is_running = True
            self.logger.info("✅ Enhanced Multi-Client Manager started successfully")

        except Exception as e:
            self.logger.error(f"❌ Failed to start manager: {e}")
            if self.error_handler:
                self.error_handler.handle_error("STARTUP_ERROR", e)
            raise

    async def stop(self):
        """Stop the enhanced multi-client manager"""

        if not self.is_running:
            return

        self.logger.info("🛑 Stopping Enhanced Multi-Client Data Manager...")

        try:
            # Signal stop
            self._stop_event.set()

            # Stop all clients
            await self._stop_all_clients()

            # Clean up resources
            self.executor.shutdown(wait=True)

            self.is_running = False
            self.logger.info("✅ Enhanced Multi-Client Manager stopped")

        except Exception as e:
            self.logger.error(f"❌ Error during shutdown: {e}")
            if self.error_handler:
                self.error_handler.handle_error("SHUTDOWN_ERROR", e)

    async def _start_all_clients(self):
        """Start all configured clients"""

        self.logger.info(f"🔌 Starting {len(self.clients)} clients...")

        # Start clients in priority order
        sorted_clients = sorted(self.clients.items(), key=lambda x: x[1].priority.value)

        for client_id, client_info in sorted_clients:
            try:
                await self._start_single_client(client_id)

                # Add delay between connections (MAESTRO fix)
                if self.connection_config:
                    await asyncio.sleep(self.connection_config.race_condition_delay)

            except Exception as e:
                self.logger.error(f"❌ Failed to start client {client_id}: {e}")
                if self.error_handler:
                    self.error_handler.handle_error(
                        f"CLIENT_{client_id}_START_ERROR", e
                    )

    async def _start_single_client(self, client_id: int):
        """Start a single client connection"""

        if not IB_ASYNC_AVAILABLE:
            self.logger.warning(
                f"⚠️ ib_async not available - simulating client {client_id}"
            )
            self.clients[client_id].is_connected = True
            return

        client_info = self.clients[client_id]

        try:
            self.logger.info(
                f"🔌 Starting client {client_id}: {client_info.description}"
            )

            # Create IB instance
            ib = IB()

            # Configure timeouts
            if self.connection_config:
                ib.RequestTimeout = self.connection_config.timeout

            # Connect with MAESTRO fixes
            await ib.connectAsync(
                host=self.connection_config.host
                if self.connection_config
                else "127.0.0.1",
                port=self.connection_config.port if self.connection_config else 4002,
                clientId=client_id,
                timeout=self.connection_config.timeout
                if self.connection_config
                else 15.0,
                readonly=self.connection_config.readonly
                if self.connection_config
                else True,
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

            # Set up news subscriptions for news clients
            if (
                client_info.purpose == ClientPurpose.NEWS_ALERTS
                or ClientPurpose.NEWS_ALERTS in client_info.consolidated_purposes
            ):
                await self._setup_news_subscriptions(client_id)

            self.performance_metrics["successful_connections"] += 1
            self.logger.info(f"✅ Client {client_id} connected successfully")

        except Exception as e:
            self.performance_metrics["connection_attempts"] += 1
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

        # Connect handlers
        ib.pendingTickersEvent += on_pending_tickers
        ib.errorEvent += on_error

        # News handler for news clients
        client_info = self.clients[client_id]
        if (
            client_info.purpose == ClientPurpose.NEWS_ALERTS
            or ClientPurpose.NEWS_ALERTS in client_info.consolidated_purposes
        ):
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
                f"📊 Subscribing client {client_id} to {len(client_info.symbols)} symbols"
            )

            for symbol in client_info.symbols:
                # Create contract (simplified - would need proper contract creation)
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
        """Set up news subscriptions for news clients"""

        client_info = self.clients[client_id]
        ib = self.active_connections.get(client_id)

        if not ib:
            return

        try:
            self.logger.info(f"📰 Setting up news subscriptions for client {client_id}")

            # Subscribe to news bulletins
            ib.reqNewsBulletins(allMsgs=True)

            # Subscribe to specific news providers if available
            # This would depend on your IB account capabilities

            self.logger.info(f"✅ News subscriptions set up for client {client_id}")

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
            "priority": client_info.priority.value,
            "consolidated_purposes": [
                p.value for p in client_info.consolidated_purposes
            ],
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
            "connection_mode": self.detected_mode.value
            if self.detected_mode
            else "unknown",
            "max_clients": self.connection_config.max_clients
            if self.connection_config
            else 0,
            "connected_clients": connected_clients,
            "total_clients": len(self.clients),
            "total_messages": total_messages,
            "total_errors": total_errors,
            "news_items": len(self.news_data),
            "uptime_seconds": uptime,
            "performance_metrics": self.performance_metrics.copy(),
        }

    # ================================================================================
    # UTILITY METHODS
    # ================================================================================

    def export_configuration(self) -> Dict[str, Any]:
        """Export current configuration for backup/analysis"""

        return {
            "connection_mode": self.detected_mode.value if self.detected_mode else None,
            "connection_config": {
                "mode": self.connection_config.mode.value,
                "max_clients": self.connection_config.max_clients,
                "port": self.connection_config.port,
                "host": self.connection_config.host,
            }
            if self.connection_config
            else None,
            "client_configs": {
                str(client_id): {
                    "purpose": info.purpose.value,
                    "description": info.description,
                    "symbols": info.symbols,
                    "frequency": info.update_frequency,
                    "priority": info.priority.value,
                    "consolidated_purposes": [
                        p.value for p in info.consolidated_purposes
                    ],
                    "news_types": [nt.value for nt in info.news_types],
                }
                for client_id, info in self.clients.items()
            },
            "timestamp": datetime.now().isoformat(),
        }


# ================================================================================
# SINGLETON PATTERN
# ================================================================================

_manager_instance: Optional[EnhancedMultiClientDataManager] = None


def get_enhanced_manager_instance() -> EnhancedMultiClientDataManager:
    """Get the singleton manager instance"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = EnhancedMultiClientDataManager()
    return _manager_instance


def reset_enhanced_manager_instance():
    """Reset the singleton manager instance"""
    global _manager_instance
    if _manager_instance and _manager_instance.is_running:
        asyncio.run(_manager_instance.stop())
    _manager_instance = None


# ================================================================================
# MAIN FUNCTION FOR TESTING
# ================================================================================


async def main():
    """Test the enhanced multi-client manager"""

    print("🚀 Testing Enhanced Multi-Client Data Manager")
    print("=" * 60)

    # Create manager
    manager = EnhancedMultiClientDataManager(ConnectionMode.AUTO_DETECT)

    try:
        # Start manager
        await manager.start()

        # Test callbacks
        def test_data_callback(tick: MarketDataTick):
            print(f"📊 Data: {tick.symbol} = {tick.last} @ {tick.timestamp}")

        def test_news_callback(news: NewsData):
            print(f"📰 News: {news.headline}")

        # Subscribe to test data
        manager.subscribe_to_data("SPY", test_data_callback)
        manager.subscribe_to_news(test_news_callback)

        # Show system status
        status = manager.get_system_status()
        print(f"\n📊 System Status:")
        print(f"   Mode: {status['connection_mode']}")
        print(f"   Clients: {status['connected_clients']}/{status['total_clients']}")
        print(f"   Messages: {status['total_messages']}")
        print(f"   Errors: {status['total_errors']}")
        print(f"   News Items: {status['news_items']}")

        # Show client details
        print(f"\n🔌 Client Status:")
        for client_id in sorted(manager.clients.keys()):
            client_status = manager.get_client_status(client_id)
            if client_status:
                status_icon = "✅" if client_status["is_connected"] else "❌"
                print(
                    f"   {status_icon} Client {client_id}: {client_status['description']}"
                )
                if client_status["consolidated_purposes"]:
                    print(
                        f"      Consolidated: {', '.join(client_status['consolidated_purposes'])}"
                    )
                if client_status["news_types"]:
                    print(f"      News Types: {', '.join(client_status['news_types'])}")

        # Export configuration
        config = manager.export_configuration()
        config_file = Path("enhanced_client_config.json")
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
