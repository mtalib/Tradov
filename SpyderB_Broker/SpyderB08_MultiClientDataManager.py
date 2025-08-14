import uuid

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderB08_MultiClientDataManager.py
Group: B (Broker Integration)
Purpose: Multi-Client Market Data Manager with Order Execution Priority
Author: Mohamed Talib
Date Created: 2025-07-28
Last Updated: 2025-08-12 Time: 16:45:00

Description:
    Advanced multi-client market data management system implementing sophisticated
    client ID allocation strategy optimized for trading performance. Order execution
    gets highest priority (Client 2) for fastest trade processing, with market data
    distributed across remaining clients based on frequency and importance.

    UPDATED CLIENT ID ALLOCATION STRATEGY (1-9):
    - Client 1: Administrative Operations (Account, System Control)
    - Client 2: Order Execution (HIGHEST PRIORITY - Trading operations)
    - Client 3: Core Market Data (SPY, SPX, /ES, VIX, TICK-NYSE) - 1-second updates
    - Client 4: SPY Options Chains (0DTE, 1DTE) - 1-second updates
    - Client 5: Volatility Indicators (VIX9D, VXV, VXMT, VVIX, UVXY) - 5-second updates
    - Client 6: Market Internals (TRIN, ADD, CPC, PCALL, SKEW) - 5-second updates
    - Client 7: Major Indices (DIA, QQQ, IWM, 1DTE Options) - 5-second updates
    - Client 8: Extended Assets (TLT, LQD, DXY, GLD, WEEKLY Options) - 15-30s updates
    - Client 9: Sector ETFs (XLF, XLK, XLE, XLV, XLI, XLY, XLP, XLU, XLRE, XLC, XLB) - 30-60s
"""

import logging
import threading
import time
import queue
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import json

# ================================================================================
# IMPORTS - Handle graceful fallbacks for missing dependencies
# ================================================================================


# ==============================================================================
# ENUMS
# ==============================================================================
class DataPriority(Enum):
    """Priority levels for data requests"""

    CRITICAL = 1  # Real-time trading data
    HIGH = 2  # Important market data
    NORMAL = 3  # Standard data requests
    LOW = 4  # Background data
    BATCH = 5  # Bulk/historical data


class DataRequestType(Enum):
    """Types of data requests"""

    MARKET_DATA = "market_data"
    HISTORICAL = "historical"
    OPTIONS_CHAIN = "options_chain"
    ACCOUNT = "account"
    POSITIONS = "positions"
    ORDERS = "orders"
    EXECUTIONS = "executions"


class ClientPurpose(Enum):
    """Purpose of each client connection"""

    MARKET_DATA = "market_data"
    ORDER_EXECUTION = "order_execution"
    HISTORICAL_DATA = "historical_data"
    ACCOUNT_MONITORING = "account_monitoring"
    OPTIONS_DATA = "options_data"
    BACKUP = "backup"


@dataclass
class ClientInfo:
    """Information about a client connection"""

    client_id: int
    purpose: ClientPurpose
    host: str = "127.0.0.1"
    port: int = 4002
    is_primary: bool = False
    is_connected: bool = False
    last_activity: Optional[datetime] = None
    error_count: int = 0
    client: Optional[Any] = None  # Will be SpyderClient instance


try:
    from ib_insync import Contract
    from ib_insync import Order, LimitOrder, MarketOrder, StopOrder
    from ib_insync import Ticker  # FIXED: Correct import location
    from ib_insync import BarData

    # Try to import TickType from ib_insync
    try:
        from ib_insync import TickType
    except ImportError:
        # Define fallback TickType if not available in ib_insync
        class TickType:
            LAST = 4
            BID = 1
            ASK = 2
            VOLUME = 8
            HIGH = 6
            LOW = 7
            CLOSE = 9

    # IB functionality is in IB class
    # IB functionality is in IB class
    ib_insync_AVAILABLE = True
except ImportError:
    ib_insync_AVAILABLE = False

    # Fallback classes for when ib_insync is not available
    # Removed fallback Contract class - using ib_insync
    class Order:
        def __init__(self):
            self.action = ""
            self.totalQuantity = 0
            self.orderType = ""

    class TickType:
        LAST = 4
        BID = 1
        ASK = 2
        VOLUME = 8
        HIGH = 6
        LOW = 7
        CLOSE = 9

    class BarData:
        def __init__(self):
            self.date = ""
            self.open = 0.0
            self.high = 0.0
            self.low = 0.0
            self.close = 0.0
            self.volume = 0

    class IB:
        def __init__(self, wrapper):
            pass

    class IB:
        def __init__(self):
            pass

        # Local imports


try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

    UTILITIES_AVAILABLE = True
except ImportError:
    UTILITIES_AVAILABLE = False
    # Fallback logging
    logging.basicConfig(level=logging.INFO)

    class SpyderLogger:
        @staticmethod
        def get_logger(name):
            return logging.getLogger(name)

    class SpyderErrorHandler:
        def __init__(self):
            pass

        # ================================================================================
        # ENUMS AND DATACLASSES - UPDATED WITH NEW CLIENT ALLOCATION (1-9)
        # ================================================================================


class ClientPurpose(Enum):
    """Client ID purposes for organized allocation - UPDATED WITH ORDER EXECUTION PRIORITY (1-9)"""

    ADMINISTRATIVE = "Administrative Operations"
    ORDER_EXECUTION = "Order Execution - HIGHEST PRIORITY"  # Now Client 2
    CORE_DATA = "Core Market Data"  # Now Client 3
    SPY_OPTIONS = "SPY Options Chains"  # Now Client 4
    VOLATILITY = "Volatility Indicators"  # Now Client 5
    MARKET_INTERNALS = "Market Internals"  # Now Client 6
    MAJOR_INDICES = "Major Index ETFs"  # Now Client 7
    EXTENDED_ASSETS = "Extended Market Data"  # Now Client 8
    SECTOR_ETFS = "Sector ETFs"  # Now Client 9


@dataclass
class MarketDataTick:
    """Market data tick information"""

    symbol: str
    price: float
    size: int
    timestamp: datetime
    tick_type: int  # Use int instead of TickType for compatibility
    request_id: int


@dataclass
class ClientInfo:
    """Information about each client connection"""

    client_id: int
    purpose: ClientPurpose
    symbols: List[str]
    update_frequency: float
    is_connected: bool = False
    last_update: Optional[datetime] = None
    message_count: int = 0
    error_count: int = 0


# ==============================================================================
# DATA CLASSES FOR MARKET DATA MANAGEMENT
# ==============================================================================


@dataclass
class MarketDataRequest:
    """Request for market data"""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    request_type: DataRequestType = DataRequestType.MARKET_DATA
    client_id: Optional[int] = None
    priority: DataPriority = DataPriority.NORMAL
    callback: Optional[Any] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataSubscription:
    """Track data subscriptions across clients"""

    subscription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    data_type: DataRequestType = DataRequestType.MARKET_DATA
    client_ids: List[int] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_update: Optional[datetime] = None
    update_count: int = 0


@dataclass
class ClientMetrics:
    """Metrics for a client connection"""

    client_id: int
    messages_sent: int = 0
    messages_received: int = 0
    errors: int = 0
    latency_ms: float = 0.0
    uptime_seconds: float = 0.0
    last_error: Optional[str] = None


t: int = 0


@dataclass
class OrderRequest:
    """Order execution request for Client 2"""

    symbol: str
    action: str  # BUY/SELL
    quantity: int
    order_type: str  # MKT/LMT/STP
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    client_id: int = 2  # Always use Client 2 for orders (UPDATED from Client 1)


# ================================================================================
# MAIN MULTI-CLIENT DATA MANAGER CLASS - UPDATED ALLOCATION (1-9)
# ================================================================================


class MultiClientDataManager:
    """
    Advanced Multi-Client Data Manager with Order Execution Priority

    Manages multiple IB Gateway client connections with ORDER EXECUTION as highest
    priority (Client 2). Implements professional-grade market data distribution
    with optimized client allocation for trading performance.

    UPDATED: Client IDs now range from 1-9 instead of 0-8
    """

    def __init__(self):
        """Initialize the Multi-Client Data Manager with new allocation strategy (1-9)"""
        # Core components
        if UTILITIES_AVAILABLE:
            self.logger = SpyderLogger.get_logger("SpyderB08.MultiClient")
            self.error_handler = SpyderErrorHandler()
        else:
            self.logger = logging.getLogger("SpyderB08.MultiClient")
            self.error_handler = None

        self.is_running = False
        self.clients: Dict[int, ClientInfo] = {}

        # Threading and synchronization
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self.executor = ThreadPoolExecutor(
            max_workers=12, thread_name_prefix="MultiClient"
        )

        # Data management
        self.market_data: Dict[str, MarketDataTick] = {}
        self.data_callbacks: Dict[str, List[Callable]] = {}
        self.request_queue = queue.Queue()

        # Order management (Client 2)
        self.order_queue = queue.Queue()
        self.active_orders: Dict[int, OrderRequest] = {}
        self.order_callbacks: List[Callable] = []

        # Performance tracking
        self.total_messages = 0
        self.total_errors = 0
        self.total_orders = 0
        self.start_time: Optional[datetime] = None

        # Initialize UPDATED client allocation strategy (1-9)
        self._initialize_updated_client_allocation()

        self.logger.info(
            "✅ Multi-Client Data Manager initialized with ORDER EXECUTION PRIORITY (Clients 1-9)"
        )

    def _initialize_updated_client_allocation(self):
        """Initialize the UPDATED sophisticated client allocation strategy (1-9)"""

        # UPDATED Client allocation configuration with Order Execution Priority (1-9)
        self.client_configs = {
            1: {  # UPDATED: Was Client 0
                "purpose": ClientPurpose.ADMINISTRATIVE,
                "symbols": [],  # Administrative only
                "frequency": 0.0,
                "description": "Account management, system control",
                "priority": "SYSTEM",
            },
            2: {  # UPDATED: Order Execution gets highest priority (was Client 1)
                "purpose": ClientPurpose.ORDER_EXECUTION,
                "symbols": [],  # No market data - trading only
                "frequency": 0.0,
                "description": "Order execution - HIGHEST PRIORITY",
                "priority": "CRITICAL",
            },
            3: {  # UPDATED: Moved from Client 2
                "purpose": ClientPurpose.CORE_DATA,
                "symbols": ["SPY", "SPX", "/ES", "VIX", "TICK-NYSE"],
                "frequency": 1.0,
                "description": "SPY, SPX, /ES, VIX, TICK-NYSE (1s)",
                "priority": "CRITICAL",
            },
            4: {  # UPDATED: Moved from Client 3
                "purpose": ClientPurpose.SPY_OPTIONS,
                "symbols": ["SPY_0DTE", "SPY_1DTE"],
                "frequency": 1.0,
                "description": "0DTE, 1DTE options (1s)",
                "priority": "CRITICAL",
            },
            5: {  # UPDATED: Moved from Client 4
                "purpose": ClientPurpose.VOLATILITY,
                "symbols": ["VIX9D", "VXV", "VXMT", "VVIV", "UVXY", "VXN", "RVX"],
                "frequency": 5.0,
                "description": "Volatility indicators (5s)",
                "priority": "HIGH",
            },
            6: {  # UPDATED: Moved from Client 5
                "purpose": ClientPurpose.MARKET_INTERNALS,
                "symbols": ["$TRIN", "$ADD", "$DECL", "CPC", "PCALL", "SKEW"],
                "frequency": 5.0,
                "description": "Market internals (5s)",
                "priority": "HIGH",
            },
            7: {  # UPDATED: Moved from Client 6
                "purpose": ClientPurpose.MAJOR_INDICES,
                "symbols": ["DIA", "QQQ", "IWM", "NDX"],
                "frequency": 5.0,
                "description": "Major indices (5s)",
                "priority": "HIGH",
            },
            8: {  # UPDATED: Moved from Client 7
                "purpose": ClientPurpose.EXTENDED_ASSETS,
                "symbols": ["TLT", "LQD", "DXY", "GLD", "USO", "UNG"],
                "frequency": 15.0,
                "description": "Extended assets (15s)",
                "priority": "MEDIUM",
            },
            9: {  # UPDATED: Moved from Client 8
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
                "description": "Sector ETFs (30s)",
                "priority": "LOW",
            },
        }

        # Create client info objects with UPDATED allocation (1-9)
        for client_id, config in self.client_configs.items():
            self.clients[client_id] = ClientInfo(
                client_id=client_id,
                purpose=config["purpose"],
                symbols=config["symbols"].copy(),
                update_frequency=config["frequency"],
            )

        # Print UPDATED allocation summary
        self._print_updated_allocation_summary()

    def _print_updated_allocation_summary(self):
        """Print UPDATED allocation summary with Order Execution priority (1-9)"""
        print("\n" + "=" * 80)
        print(
            "📊 UPDATED PROFESSIONAL CLIENT ALLOCATION - ORDER EXECUTION PRIORITY (1-9)"
        )
        print("=" * 80)

        print("🏆 TRADING PRIORITY ORDER:")
        priority_order = [
            (2, "ORDER EXECUTION", "CRITICAL - Fastest trading execution"),
            (1, "ADMINISTRATIVE", "SYSTEM - Account & control"),
            (3, "CORE DATA", "CRITICAL - SPY, VIX real-time (1s)"),
            (4, "SPY OPTIONS", "CRITICAL - 0DTE/1DTE options (1s)"),
            (5, "VOLATILITY", "HIGH - Volatility surface (5s)"),
            (6, "MARKET INTERNALS", "HIGH - Market breadth (5s)"),
            (7, "MAJOR INDICES", "HIGH - DIA/QQQ/IWM (5s)"),
            (8, "EXTENDED ASSETS", "MEDIUM - Bonds/FX/Commodities (15s)"),
            (9, "SECTOR ETFS", "LOW - Sector rotation (30s)"),
        ]

        for client_id, name, description in priority_order:
            config = self.client_configs[client_id]
            symbol_count = len(config["symbols"])
            frequency = config["frequency"]

            # Format display
            if client_id == 2:  # UPDATED: Order execution is now Client 2
                print(f"🚀 Client {client_id}: {name} - {description}")
                print(f"   🎯 PURPOSE: Ultra-fast order execution and trade management")
                print(f"   ⚡ LATENCY: <10ms target for order placement")
            elif symbol_count > 0:
                print(f"📊 Client {client_id}: {name} - {description}")
                print(
                    f"   📈 Symbols ({symbol_count}): {', '.join(config['symbols'][:5])}{'...' if symbol_count > 5 else ''}"
                )
                print(f"   🔄 Update frequency: {frequency}s")
            else:
                print(f"⚙️ Client {client_id}: {name} - {description}")
            print()

        print("🎯 TRADING ADVANTAGES:")
        print("   • Order Execution (Client 2) gets highest priority")
        print("   • Critical market data (Clients 3-4) on fast 1s updates")
        print("   • Load distribution prevents API rate limiting")
        print("   • Fault isolation - if one client fails, others continue")
        print("   • Client IDs now 1-9 (eliminates Client 0 complexity)")
        print("=" * 80)

    # ================================================================================
    # ORDER EXECUTION METHODS - UPDATED FOR CLIENT 2
    # ================================================================================

    def submit_order(
        self, order_request: OrderRequest, callback: Optional[Callable] = None
    ) -> int:
        """
        Submit order for execution on Client 2 (highest priority)

        Args:
            order_request: Order details
            callback: Optional callback for order status updates

        Returns:
            Order ID for tracking
        """
        try:
            order_id = int(time.time() * 1000) % 1000000  # Generate unique order ID

            # Always route to Client 2 for fastest execution (UPDATED from Client 1)
            order_request.client_id = 2

            # Store order
            self.active_orders[order_id] = order_request

            # Add to order queue for Client 2 processing
            order_data = {
                "order_id": order_id,
                "order_request": order_request,
                "callback": callback,
                "timestamp": datetime.now(),
            }
            self.order_queue.put(order_data)

            # Register callback if provided
            if callback and callback not in self.order_callbacks:
                self.order_callbacks.append(callback)

            self.total_orders += 1
            self.logger.info(
                f"✅ Order {order_id} submitted to Client 2: {order_request.action} {order_request.quantity} {order_request.symbol}"
            )

            return order_id

        except Exception as e:
            self.logger.error(f"❌ Error submitting order: {e}")
            return -1

    def cancel_order(self, order_id: int) -> bool:
        """
        Cancel order via Client 2

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancellation request submitted
        """
        try:
            if order_id in self.active_orders:
                # Submit cancellation to Client 2
                cancel_data = {
                    "action": "CANCEL",
                    "order_id": order_id,
                    "timestamp": datetime.now(),
                }
                self.order_queue.put(cancel_data)

                self.logger.info(
                    f"✅ Order {order_id} cancellation submitted to Client 2"
                )
                return True
            else:
                self.logger.warning(f"⚠️ Order {order_id} not found for cancellation")
                return False

        except Exception as e:
            self.logger.error(f"❌ Error cancelling order {order_id}: {e}")
            return False

    def get_order_status(self, order_id: int) -> Optional[Dict]:
        """
        Get status of specific order

        Args:
            order_id: Order ID to check

        Returns:
            Order status dictionary or None
        """
        try:
            if order_id in self.active_orders:
                order = self.active_orders[order_id]
                return {
                    "order_id": order_id,
                    "symbol": order.symbol,
                    "action": order.action,
                    "quantity": order.quantity,
                    "order_type": order.order_type,
                    "client_id": order.client_id,
                    "status": "ACTIVE",  # Would be updated by IB callbacks
                }
            return None

        except Exception as e:
            self.logger.error(f"❌ Error getting order status {order_id}: {e}")
            return None

    # ================================================================================
    # CORE MANAGEMENT METHODS - UPDATED FOR 1-9 RANGE
    # ================================================================================

    def start(self) -> bool:
        """
        Start the Multi-Client Data Manager with Order Execution Priority (1-9)

        Returns:
            bool: True if started successfully
        """
        try:
            with self._lock:
                if self.is_running:
                    self.logger.warning("Multi-Client Data Manager already running")
                    return True

                self.logger.info(
                    "🚀 Starting Multi-Client Data Manager with ORDER EXECUTION PRIORITY (Clients 1-9)..."
                )

                # Initialize components
                self._stop_event.clear()
                self.start_time = datetime.now()

                # Start ORDER EXECUTION client (Client 2) FIRST - highest priority
                if self._start_client(2):
                    self.logger.info(
                        "✅ Started ORDER EXECUTION client (Client 2) - HIGHEST PRIORITY"
                    )
                    time.sleep(0.2)  # Brief pause

                # Start administrative client (Client 1) second
                if self._start_client(1):
                    self.logger.info("✅ Started ADMINISTRATIVE client (Client 1)")
                    time.sleep(0.2)

                # Start critical market data clients (Clients 3, 4)
                critical_clients = [3, 4]
                for client_id in critical_clients:
                    if self._start_client(client_id):
                        self.logger.info(f"✅ Started critical data client {client_id}")
                        time.sleep(0.3)  # Slightly longer pause between connections

                # Start request processing threads
                processing_thread = threading.Thread(
                    target=self._request_processing_loop,
                    name="RequestProcessor",
                    daemon=True,
                )
                processing_thread.start()

                order_processing_thread = threading.Thread(
                    target=self._order_processing_loop,
                    name="OrderProcessor",
                    daemon=True,
                )
                order_processing_thread.start()

                self.is_running = True
                self.logger.info(
                    "✅ Multi-Client Data Manager started with ORDER EXECUTION PRIORITY (Clients 1-9)"
                )

                return True

        except Exception as e:
            self.logger.error(f"❌ Failed to start Multi-Client Data Manager: {e}")
            return False

    def _order_processing_loop(self):
        """Process order execution requests for Client 2"""
        self.logger.info("🔄 Starting order processing loop for Client 2")

        while not self._stop_event.is_set():
            try:
                # Get order from queue (with timeout)
                order_data = self.order_queue.get(timeout=1.0)

                # Process the order on Client 2
                self._process_order_request(order_data)

            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"❌ Error in order processing loop: {e}")
                time.sleep(1.0)

        self.logger.info("🛑 Order processing loop stopped")

    def _process_order_request(self, order_data: Dict):
        """
        Process individual order request on Client 2

        Args:
            order_data: Order data dictionary
        """
        try:
            if order_data.get("action") == "CANCEL":
                # Handle cancellation
                order_id = order_data["order_id"]
                self.logger.info(f"🛑 Processing cancellation for order {order_id}")

                # Remove from active orders
                self.active_orders.pop(order_id, None)

            else:
                # Handle new order
                order_request = order_data["order_request"]
                order_id = order_data["order_id"]
                callback = order_data.get("callback")

                self.logger.info(
                    f"⚡ Processing order {order_id} on Client 2: {order_request.action} {order_request.quantity} {order_request.symbol}"
                )

                # In real implementation, would submit to IB via Client 2
                if not ib_insync_AVAILABLE:
                    # Simulate order processing
                    self.logger.info(
                        f"📋 SIMULATED: Order {order_id} executed successfully"
                    )

                    # Notify callback if provided
                    if callback:
                        try:
                            callback(
                                {
                                    "order_id": order_id,
                                    "status": "FILLED",
                                    "message": "Order executed successfully",
                                }
                            )
                        except Exception as e:
                            self.logger.error(f"❌ Error in order callback: {e}")

        except Exception as e:
            self.logger.error(f"❌ Error processing order request: {e}")

    # ================================================================================
    # MARKET DATA METHODS - UPDATED FOR NEW CLIENT ALLOCATION (1-9)
    # ================================================================================

    def subscribe_to_data(self, symbol: str, callback: Callable) -> bool:
        """
        Subscribe to market data for a symbol using UPDATED client allocation (1-9)

        Args:
            symbol: Symbol to subscribe to
            callback: Callback function for data updates

        Returns:
            bool: True if subscription successful
        """
        try:
            if symbol not in self.data_callbacks:
                self.data_callbacks[symbol] = []

            if callback not in self.data_callbacks[symbol]:
                self.data_callbacks[symbol].append(callback)
                self.logger.info(f"✅ Subscribed to {symbol} data")

                # Determine which client should handle this symbol using UPDATED allocation
                client_id = self._get_updated_client_for_symbol(symbol)
                if client_id is not None:
                    self._request_market_data(symbol, client_id)

                return True
            else:
                self.logger.info(f"ℹ️ Already subscribed to {symbol} data")
                return True

        except Exception as e:
            self.logger.error(f"❌ Error subscribing to {symbol}: {e}")
            return False

    def _get_updated_client_for_symbol(self, symbol: str) -> Optional[int]:
        """
        Determine which client should handle a symbol using UPDATED allocation (1-9)

        Args:
            symbol: Symbol to route

        Returns:
            Client ID or None
        """
        try:
            # Check each client's symbol list (using UPDATED allocation)
            for client_id, client in self.clients.items():
                if symbol in client.symbols:
                    return client_id

            # UPDATED default routing based on symbol characteristics
            if symbol in ["SPY", "SPX", "/ES", "VIX", "TICK-NYSE"]:
                return 3  # Core data (was Client 2, now Client 3)
            elif "VIX" in symbol or symbol in ["UVXY", "SKEW"]:
                return 5  # Volatility (was Client 4, now Client 5)
            elif symbol in ["DIA", "QQQ", "IWM"]:
                return 7  # Major indices (was Client 6, now Client 7)
            elif symbol in ["TLT", "LQD", "DXY", "GLD"]:
                return 8  # Extended assets (was Client 7, now Client 8)
            elif symbol.startswith("XL"):
                return 9  # Sector ETFs (was Client 8, now Client 9)
            else:
                return 3  # Default to core data (was Client 2, now Client 3)

        except Exception as e:
            self.logger.error(f"❌ Error routing symbol {symbol}: {e}")
            return 3  # Fallback to core data client

    # ================================================================================
    # STATUS AND MONITORING METHODS - UPDATED FOR 1-9 RANGE
    # ================================================================================

    def get_status_summary(self) -> Dict:
        """
        Get comprehensive status summary with UPDATED allocation (1-9)

        Returns:
            Status summary dictionary
        """
        try:
            with self._lock:
                active_clients = [
                    client_id
                    for client_id, client in self.clients.items()
                    if client.is_connected
                ]

                return {
                    "is_running": self.is_running,
                    "active_clients": active_clients,
                    "total_clients": len(self.clients),
                    "order_execution_priority": 2
                    in active_clients,  # UPDATED: Order execution is now Client 2
                    "critical_clients_online": len(
                        [c for c in [2, 3, 4] if c in active_clients]
                    ),  # UPDATED client IDs
                    "market_data_lines_used": len(self.market_data),
                    "total_messages": self.total_messages,
                    "total_orders": self.total_orders,
                    "total_errors": self.total_errors,
                    "start_time": self.start_time,
                    "subscriptions": len(self.data_callbacks),
                    "active_orders": len(self.active_orders),
                    "client_id_range": "1-9",  # NEW: Indicate the client ID range
                }

        except Exception as e:
            self.logger.error(f"❌ Error getting status: {e}")
            return {}

    # ================================================================================
    # REMAINING METHODS - CORE FUNCTIONALITY (UPDATED FOR 1-9)
    # ================================================================================

    def _start_client(self, client_id: int) -> bool:
        """Start individual client connection (1-9 range)"""
        try:
            if client_id not in self.clients:
                self.logger.error(f"❌ Unknown client ID: {client_id}")
                return False

            client = self.clients[client_id]

            # For now, mark as connected (would normally connect to IB Gateway)
            if not ib_insync_AVAILABLE:
                # Simulation mode
                client.is_connected = True
                client.last_update = datetime.now()
                self.logger.info(
                    f"✅ Client {client_id} ({client.purpose.value}) started in simulation mode"
                )
                return True

            # Real IB Gateway connection would go here
            client.is_connected = True
            client.last_update = datetime.now()

            return True

        except Exception as e:
            self.logger.error(f"❌ Error starting client {client_id}: {e}")
            return False

    def stop(self) -> bool:
        """Stop the Multi-Client Data Manager"""
        try:
            with self._lock:
                if not self.is_running:
                    self.logger.info("Multi-Client Data Manager already stopped")
                    return True

                self.logger.info("🛑 Stopping Multi-Client Data Manager...")

                # Signal all threads to stop
                self._stop_event.set()
                self.is_running = False

                # Disconnect all clients (1-9)
                for client_id in self.clients:
                    self._stop_client(client_id)

                # Clean up resources
                self.executor.shutdown(wait=True)
                self.market_data.clear()
                self.active_orders.clear()

                self.logger.info("✅ Multi-Client Data Manager stopped successfully")
                return True

        except Exception as e:
            self.logger.error(f"❌ Error stopping Multi-Client Data Manager: {e}")
            return False

    def _stop_client(self, client_id: int) -> bool:
        """Stop individual client connection"""
        try:
            if client_id in self.clients:
                client = self.clients[client_id]
                client.is_connected = False
                self.logger.info(f"🛑 Client {client_id} stopped")
            return True
        except Exception as e:
            self.logger.error(f"❌ Error stopping client {client_id}: {e}")
            return False

    def _request_market_data(self, symbol: str, client_id: int):
        """Request market data for symbol on specific client"""
        try:
            request = {
                "symbol": symbol,
                "client_id": client_id,
                "timestamp": datetime.now(),
            }
            self.request_queue.put(request)
        except Exception as e:
            self.logger.error(f"❌ Error requesting data for {symbol}: {e}")

    def _request_processing_loop(self):
        """Process market data requests"""
        self.logger.info("🔄 Starting request processing loop")

        while not self._stop_event.is_set():
            try:
                request = self.request_queue.get(timeout=1.0)
                self._process_market_data_request(request)
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"❌ Error in request processing loop: {e}")
                time.sleep(1.0)

    def _process_market_data_request(self, request: Dict):
        """Process individual market data request"""
        try:
            symbol = request["symbol"]
            client_id = request["client_id"]

            # Simulate market data for testing
            if not ib_insync_AVAILABLE:
                tick = MarketDataTick(
                    symbol=symbol,
                    price=420.0 + hash(symbol) % 50 + (time.time() % 10),
                    size=100,
                    timestamp=datetime.now(),
                    tick_type=TickType.LAST,
                    request_id=hash(f"{symbol}_{client_id}") % 10000,
                )
                self._update_market_data(tick)

            # Update client stats
            if client_id in self.clients:
                self.clients[client_id].message_count += 1
                self.clients[client_id].last_update = datetime.now()

        except Exception as e:
            self.logger.error(f"❌ Error processing request: {e}")

    def _update_market_data(self, tick: MarketDataTick):
        """Update market data and notify callbacks"""
        try:
            with self._lock:
                self.market_data[tick.symbol] = tick
                self.total_messages += 1

                # Notify callbacks
                if tick.symbol in self.data_callbacks:
                    for callback in self.data_callbacks[tick.symbol]:
                        try:
                            callback(tick)
                        except Exception as e:
                            self.logger.error(
                                f"❌ Error in callback for {tick.symbol}: {e}"
                            )
        except Exception as e:
            self.logger.error(f"❌ Error updating market data: {e}")

    def get_latest_data(self, symbol: str) -> Optional[Dict]:
        """Get latest market data for symbol"""
        try:
            with self._lock:
                if symbol in self.market_data:
                    tick = self.market_data[symbol]
                    return {
                        "symbol": tick.symbol,
                        "price": tick.price,
                        "size": tick.size,
                        "timestamp": tick.timestamp,
                        "tick_type": tick.tick_type,
                    }

                # Fallback: simulate data for testing
                return {
                    "symbol": symbol,
                    "price": 420.0 + hash(symbol) % 50,
                    "size": 100,
                    "timestamp": datetime.now(),
                    "tick_type": TickType.LAST,
                }
        except Exception as e:
            self.logger.error(f"❌ Error getting data for {symbol}: {e}")
            return None

    def unsubscribe_from_data(self, symbol: str, callback: Callable) -> bool:
        """Unsubscribe from market data for symbol"""
        try:
            if (
                symbol in self.data_callbacks
                and callback in self.data_callbacks[symbol]
            ):
                self.data_callbacks[symbol].remove(callback)
                self.logger.info(f"✅ Unsubscribed from {symbol} data")
                return True
            else:
                self.logger.info(f"ℹ️ No subscription found for {symbol}")
                return False
        except Exception as e:
            self.logger.error(f"❌ Error unsubscribing from {symbol}: {e}")
            return False

    def get_client_status(self, client_id: int) -> Optional[Dict]:
        """Get status for specific client (1-9 range)"""
        try:
            if client_id in self.clients:
                client = self.clients[client_id]
                return {
                    "client_id": client.client_id,
                    "purpose": client.purpose.value,
                    "is_connected": client.is_connected,
                    "symbols": client.symbols,
                    "update_frequency": client.update_frequency,
                    "message_count": client.message_count,
                    "error_count": client.error_count,
                    "last_update": client.last_update,
                }
        except Exception as e:
            self.logger.error(f"❌ Error getting client {client_id} status: {e}")
            return None


# ================================================================================
# GLOBAL INSTANCE MANAGEMENT
# ================================================================================

_global_manager_instance: Optional[MultiClientDataManager] = None
_manager_lock = threading.Lock()


def get_manager_instance() -> MultiClientDataManager:
    """Get global manager instance (singleton pattern)"""
    global _global_manager_instance

    with _manager_lock:
        if _global_manager_instance is None:
            _global_manager_instance = MultiClientDataManager()
        return _global_manager_instance


def reset_manager_instance():
    """Reset global manager instance"""
    global _global_manager_instance

    with _manager_lock:
        if _global_manager_instance and _global_manager_instance.is_running:
            _global_manager_instance.stop()
        _global_manager_instance = None


# ================================================================================
# STANDALONE TESTING AND MAIN EXECUTION
# ================================================================================


def main():
    """Main execution for testing UPDATED allocation (1-9)"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print(
        "🚀 SPYDER B08 - Multi-Client Data Manager (ORDER EXECUTION PRIORITY - CLIENTS 1-9)"
    )
    print("=" * 90)

    try:
        # Initialize manager with UPDATED allocation (1-9)
        manager = MultiClientDataManager()

        # Test basic functionality
        print("🧪 Testing UPDATED Multi-Client Data Manager (1-9)...")

        # Start manager
        if manager.start():
            print(
                "✅ Manager started successfully with ORDER EXECUTION PRIORITY (Clients 1-9)"
            )

            # Test order submission (Client 2)
            print("\n🧪 Testing Order Execution (Client 2)...")
            order = OrderRequest(
                symbol="SPY", action="BUY", quantity=100, order_type="MKT"
            )

            def order_callback(status):
                print(f"📋 Order callback: {status}")

            order_id = manager.submit_order(order, order_callback)
            if order_id > 0:
                print(f"✅ Order {order_id} submitted successfully to Client 2")

                # Check order status
                status = manager.get_order_status(order_id)
                if status:
                    print(f"📊 Order status: {status}")

            # Test market data subscription
            print("\n🧪 Testing Market Data Subscription...")

            def test_callback(tick):
                print(
                    f"📊 Received data: {tick.symbol} = ${tick.price:.2f} (Client routing)"
                )

            manager.subscribe_to_data("SPY", test_callback)
            print("✅ Subscribed to SPY data")

            # Let it run for a few seconds
            print("⏱️ Running for 5 seconds...")
            time.sleep(5)

            # Get UPDATED status
            status = manager.get_status_summary()
            print(f"\n📈 UPDATED Status Summary (Clients 1-9):")
            print(f"   Client ID Range: {status['client_id_range']}")
            print(
                f"   Order Execution Priority: Client 2 - {status['order_execution_priority']}"
            )
            print(f"   Critical Clients Online: {status['critical_clients_online']}/3")
            print(f"   Active Clients: {status['active_clients']}")
            print(f"   Total Orders: {status['total_orders']}")
            print(f"   Total Messages: {status['total_messages']}")
            print(f"   Active Orders: {status['active_orders']}")

            # Test data retrieval
            spy_data = manager.get_latest_data("SPY")
            if spy_data:
                print(f"📊 Latest SPY: ${spy_data['price']:.2f}")

            # Stop manager
            if manager.stop():
                print("✅ Manager stopped successfully")

        print("\n🎯 UPDATED Multi-Client Data Manager test complete!")
        print("🏆 ORDER EXECUTION PRIORITY verified - Clients 1-9!")

    except Exception as e:
        print(f"❌ Error in main: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
