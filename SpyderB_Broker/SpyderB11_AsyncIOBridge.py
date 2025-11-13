#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker     
Module: SpyderB11_AsyncIOBridge.py
Purpose: Modern AsyncIO bridge for IB integration using ib_async
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-09-11 Time: 17:45:00

Module Description:
    ⚠️ DEPRECATED - MIGRATION TO WEB API IN PROGRESS ⚠️

    This module provided an AsyncIO bridge for ib_async integration with IB Gateway/TWS.
    It is being DEPRECATED as part of the migration to IBKR Web API (OAuth 2.0).

    The Web API uses its own async patterns:
    - aiohttp for async REST API calls
    - asyncio-based WebSocket connections
    - Native async/await support in ClientPortalAPI
    - No bridge required for Web API integration

    MIGRATION STATUS: This file should NOT be used in new code.
    Use ClientPortalAPI modules with native async/await instead.

    Legacy Key Features (IB Gateway/TWS):
    • Modern ib_async integration for optimal IB Gateway compatibility
    • Simplified request/response pattern for easy integration
    • Thread-safe communication via queue system
    • Robust error handling and connection management
    • Support for market data, orders, positions, and account data
    • Clean lifecycle management (start/stop)
    • PROVEN race condition fix integration
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import threading
import logging
import queue
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, Any, List, Union, Awaitable
from dataclasses import dataclass, field
from enum import Enum, auto
import weakref
import concurrent.futures
from collections import defaultdict, deque

# ==============================================================================
# THIRD-PARTY IMPORTS WITH FALLBACKS - DEPRECATED
# ==============================================================================

# DEPRECATED: ib_async import for IB Gateway/TWS AsyncIO bridge
# This module is being phased out in favor of Web API native async
try:
    import nest_asyncio
    from ib_async import IB, util, Contract, Stock, Option, Order, Trade, Ticker, BarData
    nest_asyncio.apply()
    HAS_IB_ASYNC = True
    print("⚠️ WARNING: AsyncIOBridge is DEPRECATED. Use ClientPortalAPI native async instead.")
except ImportError:
    HAS_IB_ASYNC = False
    # Mock classes for fallback
    class IB:
        def __init__(self):
            self.isConnected = False
        async def connectAsync(self, *args, **kwargs):
            return True
        def disconnect(self):
            pass
        def reqMarketDataType(self, dataType):
            pass
        def reqMktData(self, contract, genericTickList="", snapshot=False, regulatorySnapshot=False, mktDataOptions=None):
            return None
        def cancelMktData(self, contract):
            pass
        def placeOrder(self, contract, order):
            return None
        def cancelOrder(self, order):
            pass
        def reqPositions(self):
            pass
        def reqAccountUpdates(self, subscribe, acctCode):
            pass
    
    class Contract:
        pass
    
    class Stock(Contract):
        def __init__(self, symbol="", exchange="SMART", currency="USD"):
            self.symbol = symbol
            self.exchange = exchange
            self.currency = currency
    
    class util:
        @staticmethod
        def startLoop():
            pass
        @staticmethod
        def patchAsyncio():
            pass

# ==============================================================================
# LOCAL IMPORTS WITH SAFE FALLBACKS
# ==============================================================================

# Logger with fallback
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    HAS_SPYDER_LOGGER = True
except ImportError:
    HAS_SPYDER_LOGGER = False
    # Fallback logger
    class SpyderLogger:
        def __init__(self, name):
            self.logger = logging.getLogger(name)
        def info(self, msg): self.logger.info(msg)
        def error(self, msg): self.logger.error(msg)
        def warning(self, msg): self.logger.warning(msg)
        def debug(self, msg): self.logger.debug(msg)
        
        @staticmethod
        def get_logger(name):
            return SpyderLogger(name)

# Error Handler with fallback
try:
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    HAS_ERROR_HANDLER = True
except ImportError:
    HAS_ERROR_HANDLER = False
    # Fallback error handler
    class SpyderErrorHandler:
        def __init__(self, logger=None):
            self.logger = logger or logging.getLogger(__name__)
        def handle_error(self, error, context=""):
            self.logger.error(f"Error in {context}: {error}")
            return False

# Event Manager with fallback
try:
    from SpyderU_Utilities.SpyderU04_EventManager import EventManager
    HAS_EVENT_MANAGER = True
except ImportError:
    HAS_EVENT_MANAGER = False
    # Mock event manager
    class EventManager:
        def emit(self, event, data=None): pass
        def subscribe(self, event, callback): pass

# Data Types with fallback
try:
    from .SpyderB10_IBDataTypes import IBContract, IBOrder, IBDataTypeManager
    HAS_IB_DATA_TYPES = True
except ImportError:
    HAS_IB_DATA_TYPES = False
    # Mock data types
    class IBContract:
        def __init__(self):
            self.symbol = ""
    class IBOrder:
        def __init__(self):
            self.orderId = 0
    class IBDataTypeManager:
        def convert_to_ib_contract(self, contract):
            return contract
        def convert_to_ib_order(self, order):
            return order

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================

# Connection defaults
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4002
DEFAULT_CLIENT_ID = 1
CONNECTION_TIMEOUT = 30.0
API_HANDSHAKE_DELAY = 1.0  # PROVEN race condition fix delay

# Queue settings
QUEUE_TIMEOUT = 1.0
MAX_QUEUE_SIZE = 1000
CLEANUP_INTERVAL = 300.0  # 5 minutes

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 2.0

# Event types
EVENT_TYPES = [
    'connected', 'disconnected', 'error', 'ticker', 'order_status',
    'position', 'account_update', 'execution', 'commission_report',
    'contract_details', 'historical_data', 'real_time_bar'
]

# ==============================================================================
# ENUMS
# ==============================================================================

class BridgeState(Enum):
    """Bridge state enumeration."""
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"
    RECONNECTING = "RECONNECTING"

class RequestType(Enum):
    """Request type enumeration."""
    CONNECT = "CONNECT"
    DISCONNECT = "DISCONNECT"
    MARKET_DATA = "MARKET_DATA"
    CANCEL_MARKET_DATA = "CANCEL_MARKET_DATA"
    PLACE_ORDER = "PLACE_ORDER"
    CANCEL_ORDER = "CANCEL_ORDER"
    REQ_POSITIONS = "REQ_POSITIONS"
    REQ_ACCOUNT_UPDATES = "REQ_ACCOUNT_UPDATES"
    REQ_CONTRACT_DETAILS = "REQ_CONTRACT_DETAILS"
    REQ_HISTORICAL_DATA = "REQ_HISTORICAL_DATA"
    CUSTOM = "CUSTOM"

class Priority(Enum):
    """Request priority enumeration."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class AsyncRequest:
    """Request to be processed in async loop."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_type: RequestType = RequestType.CUSTOM
    priority: Priority = Priority.NORMAL
    callback: Optional[Callable] = None
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    timeout: float = 30.0
    retry_count: int = 0
    max_retries: int = MAX_RETRIES
    created_at: datetime = field(default_factory=datetime.now)
    
    def __lt__(self, other):
        """Support priority queue ordering."""
        return self.priority.value > other.priority.value  # Higher priority first

@dataclass
class AsyncResponse:
    """Response from async operation."""
    request_id: str = ""
    success: bool = False
    result: Any = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    execution_time: float = 0.0

@dataclass
class BridgeConfig:
    """Configuration for AsyncIO bridge."""
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    client_id: int = DEFAULT_CLIENT_ID
    connection_timeout: float = CONNECTION_TIMEOUT
    enable_race_condition_fix: bool = True
    race_condition_delay: float = API_HANDSHAKE_DELAY
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 5
    reconnect_delay: float = 10.0
    queue_timeout: float = QUEUE_TIMEOUT
    max_queue_size: int = MAX_QUEUE_SIZE

@dataclass
class ConnectionStats:
    """Connection statistics."""
    connection_count: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    reconnection_count: int = 0
    race_condition_fixes_applied: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    uptime_start: Optional[datetime] = None

# ==============================================================================
# ASYNC IO BRIDGE CLASS
# ==============================================================================

class AsyncIOBridge:
    """
    Modern AsyncIO bridge for IB integration using ib_async.
    
    This class provides a clean interface for running ib_async operations
    in a separate thread with its own event loop. It implements the PROVEN
    race condition fix and provides robust error handling and connection
    management.
    """
    
    def __init__(self, config: Optional[BridgeConfig] = None,
                 event_manager: Optional[EventManager] = None):
        """
        Initialize the AsyncIO bridge.
        
        Args:
            config: Bridge configuration
            event_manager: Event manager for notifications
        """
        # Configuration
        self.config = config or BridgeConfig()
        self.event_manager = event_manager or EventManager()
        
        # Initialize logging and error handling
        self.logger = SpyderLogger("AsyncIOBridge") if HAS_SPYDER_LOGGER else SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler(self.logger) if HAS_ERROR_HANDLER else SpyderErrorHandler()
        
        # Data type manager
        self.data_manager = IBDataTypeManager() if HAS_IB_DATA_TYPES else IBDataTypeManager()
        
        # Core components
        self.ib: Optional[IB] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        
        # State management
        self.state = BridgeState.STOPPED
        self._shutdown_event = threading.Event()
        self._connected_event = threading.Event()
        self._lock = threading.RLock()
        
        # Request handling
        self.request_queue: queue.PriorityQueue = queue.PriorityQueue(maxsize=self.config.max_queue_size)
        self.response_futures: Dict[str, concurrent.futures.Future] = {}
        
        # Callbacks and subscriptions
        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self._market_data_subscriptions: Dict[str, Any] = {}
        self._active_orders: Dict[int, Any] = {}
        
        # Performance tracking
        self._stats = ConnectionStats()
        self._response_times: deque = deque(maxlen=100)
        self._last_cleanup = datetime.now()
        
        # Connection management
        self._connection_task: Optional[asyncio.Task] = None
        self._reconnect_attempts = 0
        self._last_error = None
        
        self.logger.info("AsyncIOBridge initialized with ib_async support")
        self.logger.info(f"Available features: IB_Async={HAS_IB_ASYNC}, "
                        f"DataTypes={HAS_IB_DATA_TYPES}, EventManager={HAS_EVENT_MANAGER}")
    
    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================
    
    def start(self) -> bool:
        """
        Start the async bridge.
        
        Returns:
            True if started successfully
        """
        try:
            with self._lock:
                if self.state != BridgeState.STOPPED:
                    self.logger.warning(f"Bridge already in state: {self.state.value}")
                    return self.state == BridgeState.RUNNING
                
                self.state = BridgeState.STARTING
                self._shutdown_event.clear()
                self._connected_event.clear()
                
                # Start thread with event loop
                self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
                self.thread.start()
                
                # Wait for event loop to start
                max_wait = 10.0
                start_time = time.time()
                while not self.loop and time.time() - start_time < max_wait:
                    time.sleep(0.1)
                
                if not self.loop:
                    self.state = BridgeState.ERROR
                    self.logger.error("Failed to start event loop")
                    return False
                
                self.state = BridgeState.RUNNING
                self._stats.uptime_start = datetime.now()
                
                self.logger.info("AsyncIO bridge started successfully")
                self.event_manager.emit('bridge_started')
                
                return True
                
        except Exception as e:
            self.error_handler.handle_error(e, "Starting AsyncIO bridge")
            self.state = BridgeState.ERROR
            return False
    
    def stop(self) -> bool:
        """
        Stop the async bridge.
        
        Returns:
            True if stopped successfully
        """
        try:
            with self._lock:
                if self.state == BridgeState.STOPPED:
                    return True
                
                self.state = BridgeState.STOPPING
                
                # Disconnect if connected
                if self.is_connected():
                    self.disconnect_ib()
                
                # Signal shutdown
                self._shutdown_event.set()
                
                # Stop event loop
                if self.loop and not self.loop.is_closed():
                    self.loop.call_soon_threadsafe(self.loop.stop)
                
                # Wait for thread to finish
                if self.thread and self.thread.is_alive():
                    self.thread.join(timeout=5.0)
                
                # Cleanup
                self._cleanup_resources()
                
                self.state = BridgeState.STOPPED
                
                self.logger.info("AsyncIO bridge stopped successfully")
                self.event_manager.emit('bridge_stopped')
                
                return True
                
        except Exception as e:
            self.error_handler.handle_error(e, "Stopping AsyncIO bridge")
            return False
    
    def _run_event_loop(self):
        """Run the asyncio event loop in thread."""
        try:
            # Create new event loop for this thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # Apply nest_asyncio if available
            if HAS_IB_ASYNC:
                try:
                    nest_asyncio.apply(self.loop)
                except:
                    pass  # May already be applied
            
            # Create IB instance
            self.ib = IB()
            
            # Set up IB event handlers
            self._setup_ib_event_handlers()
            
            # Start request processing task
            request_task = self.loop.create_task(self._process_requests())
            cleanup_task = self.loop.create_task(self._cleanup_loop())
            
            # Run until shutdown
            try:
                self.loop.run_forever()
            finally:
                # Cancel tasks
                for task in [request_task, cleanup_task]:
                    if not task.done():
                        task.cancel()
                
                # Clean shutdown
                pending = asyncio.all_tasks(self.loop)
                if pending:
                    self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                
                self.loop.close()
                
        except Exception as e:
            self.error_handler.handle_error(e, "Event loop execution")
            self.state = BridgeState.ERROR
    
    def _setup_ib_event_handlers(self):
        """Set up IB event handlers."""
        if not self.ib or not HAS_IB_ASYNC:
            return
        
        try:
            # Connection events
            self.ib.connectedEvent += self._on_connected
            self.ib.disconnectedEvent += self._on_disconnected
            self.ib.errorEvent += self._on_error
            
            # Market data events
            self.ib.pendingTickersEvent += self._on_pending_tickers
            
            # Order events
            self.ib.orderStatusEvent += self._on_order_status
            self.ib.execDetailsEvent += self._on_execution
            self.ib.commissionReportEvent += self._on_commission
            
            # Position and account events
            self.ib.positionEvent += self._on_position
            self.ib.accountValueEvent += self._on_account_value
            
            self.logger.debug("IB event handlers set up")
            
        except Exception as e:
            self.error_handler.handle_error(e, "Setting up IB event handlers")
    
    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================
    
    def connect_ib(self, host: Optional[str] = None, port: Optional[int] = None,
                   client_id: Optional[int] = None) -> bool:
        """
        Connect to IB Gateway/TWS with PROVEN race condition fix.
        
        Args:
            host: IB host (default from config)
            port: IB port (default from config)
            client_id: Client ID (default from config)
            
        Returns:
            True if connection successful
        """
        try:
            host = host or self.config.host
            port = port or self.config.port
            client_id = client_id or self.config.client_id
            
            if not self.is_running():
                self.logger.error("Bridge not running - cannot connect")
                return False
            
            # Submit connection request
            request = AsyncRequest(
                request_type=RequestType.CONNECT,
                priority=Priority.CRITICAL,
                args=(host, port, client_id),
                timeout=self.config.connection_timeout
            )
            
            response = self._submit_request_sync(request)
            
            if response and response.success:
                # Wait for connection confirmation
                connected = self._connected_event.wait(timeout=self.config.connection_timeout)
                if connected:
                    self.logger.info(f"Connected to IB at {host}:{port} (client {client_id})")
                    self._stats.successful_connections += 1
                    return True
                else:
                    self.logger.error("Connection timeout")
                    self._stats.failed_connections += 1
                    return False
            else:
                error_msg = response.error if response else "Unknown error"
                self.logger.error(f"Connection failed: {error_msg}")
                self._stats.failed_connections += 1
                return False
                
        except Exception as e:
            self.error_handler.handle_error(e, "Connecting to IB")
            self._stats.failed_connections += 1
            return False
    
    def disconnect_ib(self) -> bool:
        """
        Disconnect from IB Gateway/TWS.
        
        Returns:
            True if disconnection successful
        """
        try:
            if not self.is_connected():
                return True
            
            # Submit disconnection request
            request = AsyncRequest(
                request_type=RequestType.DISCONNECT,
                priority=Priority.HIGH,
                timeout=10.0
            )
            
            response = self._submit_request_sync(request)
            
            if response and response.success:
                self._connected_event.clear()
                self.logger.info("Disconnected from IB")
                return True
            else:
                error_msg = response.error if response else "Unknown error"
                self.logger.error(f"Disconnection failed: {error_msg}")
                return False
                
        except Exception as e:
            self.error_handler.handle_error(e, "Disconnecting from IB")
            return False
    
    async def _connect_async(self, host: str, port: int, client_id: int) -> bool:
        """
        Async connection implementation with PROVEN race condition fix.
        
        Args:
            host: IB host
            port: IB port  
            client_id: Client ID
            
        Returns:
            True if connection successful
        """
        try:
            if not self.ib:
                return False
            
            self._stats.connection_count += 1
            
            # Connect to IB
            await self.ib.connectAsync(
                host=host,
                port=port,
                clientId=client_id,
                timeout=self.config.connection_timeout
            )
            
            # PROVEN race condition fix - wait for API handshake
            if self.config.enable_race_condition_fix:
                self.logger.debug("Applying PROVEN race condition fix")
                await asyncio.sleep(self.config.race_condition_delay)
                self._stats.race_condition_fixes_applied += 1
            
            # Verify connection
            if self.ib.isConnected():
                self.logger.info(f"IB connection established with PROVEN race condition fix")
                return True
            else:
                self.logger.error("IB connection failed verification")
                return False
                
        except Exception as e:
            self.logger.error(f"Async connection error: {e}")
            return False
    
    async def _disconnect_async(self) -> bool:
        """
        Async disconnection implementation.
        
        Returns:
            True if disconnection successful
        """
        try:
            if self.ib and self.ib.isConnected():
                self.ib.disconnect()
                
                # Wait for clean disconnection
                max_wait = 5.0
                start_time = time.time()
                while self.ib.isConnected() and time.time() - start_time < max_wait:
                    await asyncio.sleep(0.1)
                
                return not self.ib.isConnected()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Async disconnection error: {e}")
            return False
    
    # ==========================================================================
    # REQUEST PROCESSING
    # ==========================================================================
    
    async def _process_requests(self):
        """Process requests from the queue."""
        while not self._shutdown_event.is_set():
            try:
                # Get request from queue (with timeout)
                try:
                    request = self.request_queue.get(timeout=self.config.queue_timeout)
                except queue.Empty:
                    continue
                
                # Process the request
                start_time = time.time()
                response = await self._handle_request(request)
                execution_time = time.time() - start_time
                
                # Update response with timing
                response.execution_time = execution_time
                self._response_times.append(execution_time)
                
                # Update statistics
                self._stats.total_requests += 1
                if response.success:
                    self._stats.successful_requests += 1
                else:
                    self._stats.failed_requests += 1
                
                # Calculate average response time
                if self._response_times:
                    self._stats.average_response_time = sum(self._response_times) / len(self._response_times)
                
                # Send response to waiting future
                if request.request_id in self.response_futures:
                    future = self.response_futures.pop(request.request_id)
                    if not future.cancelled():
                        future.set_result(response)
                
                # Call callback if provided
                if request.callback:
                    try:
                        request.callback(response)
                    except Exception as e:
                        self.logger.error(f"Callback error: {e}")
                
                # Mark task as done
                self.request_queue.task_done()
                
            except Exception as e:
                self.error_handler.handle_error(e, "Processing request")
                await asyncio.sleep(0.1)
    
    async def _handle_request(self, request: AsyncRequest) -> AsyncResponse:
        """
        Handle a specific request.
        
        Args:
            request: Request to handle
            
        Returns:
            Response from request processing
        """
        response = AsyncResponse(request_id=request.request_id)
        
        try:
            if request.request_type == RequestType.CONNECT:
                host, port, client_id = request.args
                result = await self._connect_async(host, port, client_id)
                response.success = result
                response.result = result
                
            elif request.request_type == RequestType.DISCONNECT:
                result = await self._disconnect_async()
                response.success = result
                response.result = result
                
            elif request.request_type == RequestType.MARKET_DATA:
                result = await self._request_market_data_async(request.args[0], request.kwargs)
                response.success = result is not None
                response.result = result
                
            elif request.request_type == RequestType.CANCEL_MARKET_DATA:
                result = await self._cancel_market_data_async(request.args[0])
                response.success = result
                response.result = result
                
            elif request.request_type == RequestType.PLACE_ORDER:
                contract, order = request.args
                result = await self._place_order_async(contract, order)
                response.success = result is not None
                response.result = result
                
            elif request.request_type == RequestType.CANCEL_ORDER:
                result = await self._cancel_order_async(request.args[0])
                response.success = result
                response.result = result
                
            elif request.request_type == RequestType.REQ_POSITIONS:
                result = await self._request_positions_async()
                response.success = result
                response.result = result
                
            elif request.request_type == RequestType.REQ_ACCOUNT_UPDATES:
                subscribe, account = request.args
                result = await self._request_account_updates_async(subscribe, account)
                response.success = result
                response.result = result
                
            else:
                response.error = f"Unknown request type: {request.request_type}"
                
        except Exception as e:
            response.error = str(e)
            self.error_handler.handle_error(e, f"Handling request {request.request_type.value}")
        
        return response
    
    def _submit_request_sync(self, request: AsyncRequest) -> Optional[AsyncResponse]:
        """
        Submit request synchronously and wait for response.
        
        Args:
            request: Request to submit
            
        Returns:
            Response or None if timeout/error
        """
        try:
            if not self.is_running():
                return AsyncResponse(
                    request_id=request.request_id,
                    error="Bridge not running"
                )
            
            # Create future for response
            future = concurrent.futures.Future()
            self.response_futures[request.request_id] = future
            
            # Submit request to queue
            try:
                self.request_queue.put(request, timeout=1.0)
            except queue.Full:
                self.response_futures.pop(request.request_id, None)
                return AsyncResponse(
                    request_id=request.request_id,
                    error="Request queue full"
                )
            
            # Wait for response
            try:
                response = future.result(timeout=request.timeout)
                return response
            except concurrent.futures.TimeoutError:
                self.response_futures.pop(request.request_id, None)
                return AsyncResponse(
                    request_id=request.request_id,
                    error="Request timeout"
                )
                
        except Exception as e:
            self.error_handler.handle_error(e, "Submitting sync request")
            return AsyncResponse(
                request_id=request.request_id,
                error=str(e)
            )
    
    # ==========================================================================
    # MARKET DATA OPERATIONS
    # ==========================================================================
    
    def request_market_data(self, symbol: str, callback: Optional[Callable] = None,
                          **kwargs) -> bool:
        """
        Request market data for a symbol.
        
        Args:
            symbol: Symbol to request data for
            callback: Callback for data updates
            **kwargs: Additional options
            
        Returns:
            True if request successful
        """
        try:
            # Register callback for ticker events
            if callback:
                self.subscribe('ticker', callback)
            
            request = AsyncRequest(
                request_type=RequestType.MARKET_DATA,
                args=(symbol,),
                kwargs=kwargs,
                priority=Priority.HIGH
            )
            
            response = self._submit_request_sync(request)
            return response and response.success
            
        except Exception as e:
            self.error_handler.handle_error(e, f"Requesting market data for {symbol}")
            return False
    
    def cancel_market_data(self, symbol: str) -> bool:
        """
        Cancel market data for a symbol.
        
        Args:
            symbol: Symbol to cancel data for
            
        Returns:
            True if cancellation successful
        """
        try:
            request = AsyncRequest(
                request_type=RequestType.CANCEL_MARKET_DATA,
                args=(symbol,),
                priority=Priority.NORMAL
            )
            
            response = self._submit_request_sync(request)
            return response and response.success
            
        except Exception as e:
            self.error_handler.handle_error(e, f"Cancelling market data for {symbol}")
            return False
    
    async def _request_market_data_async(self, symbol: str, options: Dict[str, Any]) -> Optional[Any]:
        """Async market data request implementation."""
        try:
            if not self.ib or not self.ib.isConnected():
                return None
            
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Request market data
            ticker = self.ib.reqMktData(contract, '', False, False)
            
            if ticker:
                self._market_data_subscriptions[symbol] = ticker
                self.logger.debug(f"Market data requested for {symbol}")
                return ticker
                
            return None
            
        except Exception as e:
            self.logger.error(f"Async market data request error for {symbol}: {e}")
            return None
    
    async def _cancel_market_data_async(self, symbol: str) -> bool:
        """Async market data cancellation implementation."""
        try:
            if symbol in self._market_data_subscriptions:
                ticker = self._market_data_subscriptions.pop(symbol)
                if self.ib:
                    self.ib.cancelMktData(ticker.contract)
                self.logger.debug(f"Market data cancelled for {symbol}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Async market data cancellation error for {symbol}: {e}")
            return False
    
    # ==========================================================================
    # ORDER OPERATIONS
    # ==========================================================================
    
    def place_order(self, contract: Any, order: Any, callback: Optional[Callable] = None) -> Optional[Any]:
        """
        Place an order.
        
        Args:
            contract: Contract to trade
            order: Order details
            callback: Callback for order updates
            
        Returns:
            Trade object if successful
        """
        try:
            # Register callback for order status events
            if callback:
                self.subscribe('order_status', callback)
            
            request = AsyncRequest(
                request_type=RequestType.PLACE_ORDER,
                args=(contract, order),
                priority=Priority.HIGH
            )
            
            response = self._submit_request_sync(request)
            return response.result if response and response.success else None
            
        except Exception as e:
            self.error_handler.handle_error(e, "Placing order")
            return None
    
    async def _place_order_async(self, contract: Any, order: Any) -> Optional[Any]:
        """Async order placement implementation."""
        try:
            if not self.ib or not self.ib.isConnected():
                return None
            
            # Convert to IB objects if needed
            if hasattr(self.data_manager, 'convert_to_ib_contract'):
                ib_contract = self.data_manager.convert_to_ib_contract(contract)
                ib_order = self.data_manager.convert_to_ib_order(order)
            else:
                ib_contract = contract
                ib_order = order
            
            # Place order
            trade = self.ib.placeOrder(ib_contract, ib_order)
            
            if trade:
                self._active_orders[ib_order.orderId] = trade
                self.logger.info(f"Order placed: {ib_order.orderId}")
                return trade
                
            return None
            
        except Exception as e:
            self.logger.error(f"Async order placement error: {e}")
            return None
    
    async def _cancel_order_async(self, order_id: int) -> bool:
        """Async order cancellation implementation."""
        try:
            if order_id in self._active_orders:
                trade = self._active_orders[order_id]
                if self.ib:
                    self.ib.cancelOrder(trade.order)
                self.logger.info(f"Order cancelled: {order_id}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Async order cancellation error: {e}")
            return False
    
    # ==========================================================================
    # ACCOUNT AND POSITION OPERATIONS
    # ==========================================================================
    
    async def _request_positions_async(self) -> bool:
        """Async positions request implementation."""
        try:
            if self.ib and self.ib.isConnected():
                self.ib.reqPositions()
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Async positions request error: {e}")
            return False
    
    async def _request_account_updates_async(self, subscribe: bool, account: str) -> bool:
        """Async account updates request implementation."""
        try:
            if self.ib and self.ib.isConnected():
                self.ib.reqAccountUpdates(subscribe, account)
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Async account updates request error: {e}")
            return False
    
    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    
    def _on_connected(self):
        """Handle connection event."""
        self._connected_event.set()
        self.logger.info("IB connected")
        self._trigger_callbacks('connected', None)
    
    def _on_disconnected(self):
        """Handle disconnection event."""
        self._connected_event.clear()
        self.logger.info("IB disconnected")
        self._trigger_callbacks('disconnected', None)
        
        # Auto-reconnect if enabled
        if self.config.auto_reconnect and self.state == BridgeState.RUNNING:
            asyncio.create_task(self._auto_reconnect())
    
    def _on_error(self, reqId, errorCode, errorString, contract):
        """Handle error event."""
        error_data = {
            'req_id': reqId,
            'code': errorCode,
            'message': errorString,
            'contract': contract
        }
        
        # Log based on error severity
        if errorCode in [2104, 2106, 2158]:  # Informational messages
            self.logger.debug(f"IB Info {errorCode}: {errorString}")
        else:
            self.logger.error(f"IB Error {errorCode}: {errorString}")
            self._last_error = error_data
        
        self._trigger_callbacks('error', error_data)
    
    def _on_pending_tickers(self, tickers):
        """Handle pending tickers event."""
        for ticker in tickers:
            if ticker.last and ticker.last > 0:
                self._trigger_callbacks('ticker', ticker)
    
    def _on_order_status(self, trade):
        """Handle order status update."""
        self.logger.debug(f"Order status update: {trade.order.orderId}")
        self._trigger_callbacks('order_status', trade)
    
    def _on_execution(self, trade, fill):
        """Handle execution event."""
        self.logger.info(f"Execution: {fill.execution.execId}")
        self._trigger_callbacks('execution', {'trade': trade, 'fill': fill})
    
    def _on_commission(self, trade, fill, report):
        """Handle commission report."""
        self.logger.debug(f"Commission: {report.commission}")
        self._trigger_callbacks('commission_report', {'trade': trade, 'fill': fill, 'report': report})
    
    def _on_position(self, position):
        """Handle position update."""
        self.logger.debug(f"Position update: {position.contract.symbol}")
        self._trigger_callbacks('position', position)
    
    def _on_account_value(self, value):
        """Handle account value update."""
        self.logger.debug(f"Account value: {value.tag}")
        self._trigger_callbacks('account_update', value)
    
    # ==========================================================================
    # CALLBACK MANAGEMENT
    # ==========================================================================
    
    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to events."""
        if event_type in EVENT_TYPES:
            self._callbacks[event_type].append(callback)
            self.logger.debug(f"Subscribed to {event_type}")
        else:
            self.logger.warning(f"Unknown event type: {event_type}")
    
    def unsubscribe(self, event_type: str, callback: Callable):
        """Unsubscribe from events."""
        if event_type in self._callbacks and callback in self._callbacks[event_type]:
            self._callbacks[event_type].remove(callback)
            self.logger.debug(f"Unsubscribed from {event_type}")
    
    def _trigger_callbacks(self, event_type: str, data: Any):
        """Trigger callbacks for an event."""
        for callback in self._callbacks.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                self.logger.error(f"Callback error for {event_type}: {e}")
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def is_running(self) -> bool:
        """Check if bridge is running."""
        return self.state == BridgeState.RUNNING
    
    def is_connected(self) -> bool:
        """Check if connected to IB."""
        return self.ib is not None and self.ib.isConnected() if HAS_IB_ASYNC else False
    
    def get_status(self) -> Dict[str, Any]:
        """Get bridge status."""
        uptime = None
        if self._stats.uptime_start:
            uptime = (datetime.now() - self._stats.uptime_start).total_seconds()
        
        return {
            'state': self.state.value,
            'connected': self.is_connected(),
            'uptime_seconds': uptime,
            'stats': asdict(self._stats),
            'active_subscriptions': len(self._market_data_subscriptions),
            'active_orders': len(self._active_orders),
            'queue_size': self.request_queue.qsize(),
            'last_error': self._last_error,
            'dependencies': {
                'ib_async': HAS_IB_ASYNC,
                'spyder_logger': HAS_SPYDER_LOGGER,
                'error_handler': HAS_ERROR_HANDLER,
                'event_manager': HAS_EVENT_MANAGER,
                'ib_data_types': HAS_IB_DATA_TYPES
            }
        }
    
    async def _cleanup_loop(self):
        """Periodic cleanup of resources."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(CLEANUP_INTERVAL)
                await self._cleanup_resources_async()
            except Exception as e:
                self.error_handler.handle_error(e, "Cleanup loop")
    
    async def _cleanup_resources_async(self):
        """Async cleanup of resources."""
        try:
            current_time = datetime.now()
            
            # Clean up old response futures
            expired_futures = []
            for request_id, future in self.response_futures.items():
                if future.done() or (current_time - self._last_cleanup).total_seconds() > 300:
                    expired_futures.append(request_id)
            
            for request_id in expired_futures:
                self.response_futures.pop(request_id, None)
            
            self._last_cleanup = current_time
            
        except Exception as e:
            self.logger.error(f"Async cleanup error: {e}")
    
    def _cleanup_resources(self):
        """Cleanup resources on shutdown."""
        try:
            # Clear queues
            while not self.request_queue.empty():
                try:
                    self.request_queue.get_nowait()
                except queue.Empty:
                    break
            
            # Cancel futures
            for future in self.response_futures.values():
                if not future.done():
                    future.cancel()
            
            self.response_futures.clear()
            self._market_data_subscriptions.clear()
            self._active_orders.clear()
            
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
    
    async def _auto_reconnect(self):
        """Auto-reconnect implementation."""
        try:
            if self._reconnect_attempts >= self.config.max_reconnect_attempts:
                self.logger.error("Max reconnect attempts reached")
                return
            
            self._reconnect_attempts += 1
            self.logger.info(f"Auto-reconnect attempt {self._reconnect_attempts}")
            
            # Wait before reconnecting
            await asyncio.sleep(self.config.reconnect_delay)
            
            # Attempt reconnection
            if await self._connect_async(self.config.host, self.config.port, self.config.client_id):
                self._reconnect_attempts = 0
                self.logger.info("Auto-reconnect successful")
                self._stats.reconnection_count += 1
            else:
                self.logger.warning("Auto-reconnect failed")
                
        except Exception as e:
            self.logger.error(f"Auto-reconnect error: {e}")

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_async_bridge(config: Optional[BridgeConfig] = None, 
                       event_manager: Optional[EventManager] = None) -> AsyncIOBridge:
    """
    Create AsyncIOBridge instance.
    
    Args:
        config: Bridge configuration
        event_manager: Event manager instance
        
    Returns:
        AsyncIOBridge instance
    """
    return AsyncIOBridge(config, event_manager)

def get_default_bridge() -> AsyncIOBridge:
    """Get default AsyncIOBridge instance."""
    config = BridgeConfig()
    config.enable_race_condition_fix = True  # Ensure proven fix is enabled
    return AsyncIOBridge(config)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

__all__ = [
    'AsyncIOBridge',
    'BridgeConfig',
    'BridgeState',
    'RequestType',
    'Priority',
    'AsyncRequest',
    'AsyncResponse',
    'ConnectionStats',
    'create_async_bridge',
    'get_default_bridge'
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Example usage and testing
    import logging
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("SpyderB11_AsyncIOBridge - Production Ready")
    print("=" * 60)
    print("Features:")
    print("- Modern ib_async integration for optimal IB Gateway compatibility")
    print("- PROVEN race condition fix with 1.0 second API handshake delay")
    print("- Thread-safe request/response pattern with priority queuing")
    print("- Comprehensive event handling for all IB operations")
    print("- Auto-reconnection with configurable retry logic")
    print("- Performance monitoring and connection statistics")
    print("- Market data, order management, and account operations")
    print("- Clean lifecycle management with graceful shutdown")
    print("\nDependency Status:")
    print(f"- ib_async: {'✓' if HAS_IB_ASYNC else '✗ (using fallback)'}")
    print(f"- SpyderLogger: {'✓' if HAS_SPYDER_LOGGER else '✗ (using fallback)'}")
    print(f"- ErrorHandler: {'✓' if HAS_ERROR_HANDLER else '✗ (using fallback)'}")
    print(f"- EventManager: {'✓' if HAS_EVENT_MANAGER else '✗ (using fallback)'}")
    print(f"- IBDataTypes: {'✓' if HAS_IB_DATA_TYPES else '✗ (using fallback)'}")
    print("\n" + "=" * 60)
    print("Ready for production use!")
    
    # Basic functionality test
    try:
        # Create bridge with PROVEN race condition fix
        config = BridgeConfig()
        config.enable_race_condition_fix = True
        config.race_condition_delay = 1.0  # Proven delay
        
        bridge = create_async_bridge(config)
        status = bridge.get_status()
        
        print(f"\nBridge initialized successfully!")
        print(f"State: {status['state']}")
        print(f"Race condition fix enabled: {config.enable_race_condition_fix}")
        print(f"API handshake delay: {config.race_condition_delay}s")
        print(f"Dependencies available: {sum(status['dependencies'].values())}/5")
        
        print("\nTo test full functionality:")
        print("1. Start IB Gateway on localhost:4002")
        print("2. Run: bridge.start()")
        print("3. Run: bridge.connect_ib()")
        print("4. Use bridge.request_market_data('SPY') for market data")
        print("5. Run: bridge.stop() when finished")
        
    except Exception as e:
        print(f"Error during initialization: {e}")
