#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB11_AsyncIOBridge.py
Purpose: Modern AsyncIO bridge for IB integration using ib_async
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-01-21 Time: 14:30:00

Module Description:
    This module provides a modern bridge between ib_async's asyncio event loop
    and other parts of the Spyder system. It has been updated to use ib_async
    (the actively maintained successor to ib_insync) for improved stability
    and performance with IB Gateway 10.37. Provides essential functionality
    for systems that need async IB operations while maintaining clean separation
    from synchronous components.

Key Features:
    • Modern ib_async integration for optimal IB Gateway compatibility
    • Simplified request/response pattern for easy integration  
    • Thread-safe communication via queue system
    • Robust error handling and connection management
    • Support for market data, orders, positions, and account data
    • Clean lifecycle management (start/stop)

Dependencies:
    • ib_async (modern IB API wrapper)
    • nest_asyncio (for asyncio compatibility)
    • Standard Python asyncio libraries

Installation Note:
    pip install ib_async nest-asyncio

Usage Example:
    bridge = ModernAsyncIOBridge()
    bridge.start()
    if bridge.connect_ib('127.0.0.1', 4002):
        bridge.request_market_data('SPY', callback=on_ticker)
    bridge.stop()
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import logging
import queue
import threading
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import nest_asyncio
    from ib_async import IB, util

    nest_asyncio.apply()
    HAS_IB_ASYNC = True
except ImportError:
    HAS_IB_ASYNC = False
    print("WARNING: ib_async not available - install with: pip install ib_async")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4002
CONNECTION_TIMEOUT = 30
QUEUE_TIMEOUT = 1.0

# ==============================================================================
# ENUMS
# ==============================================================================


class BridgeState(Enum):
    """Bridge state enumeration"""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


# ==============================================================================
# DATA CLASSES
# ==============================================================================


@dataclass
class AsyncRequest:
    """Request to be processed in async loop"""

    request_type: str
    callback: Optional[Callable] = None
    args: tuple = ()
    kwargs: dict = None

    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}


@dataclass
class AsyncResponse:
    """Response from async operation"""

    success: bool
    result: Any = None
    error: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class ModernAsyncIOBridge:
    """
    Modern AsyncIO bridge for IB integration using ib_async.

    This class provides a clean interface for running ib_async operations
    in a separate thread with its own event loop. It's designed to work
    seamlessly with IB Gateway 10.37 and provides robust error handling.

    Key improvements over legacy ib_insync version:
    - Uses modern ib_async library for better IB Gateway compatibility
    - Enhanced error handling and connection stability
    - Improved performance with IB Gateway 10.37
    - Better async/await pattern implementation
    - More robust connection lifecycle management

    Example:
        >>> bridge = ModernAsyncIOBridge()
        >>> bridge.start()
        >>>
        >>> # Connect to IB Gateway
        >>> connected = bridge.connect_ib('127.0.0.1', 4002)
        >>>
        >>> # Request market data with callback
        >>> def on_ticker(ticker):
        ...     print(f"SPY Price: {ticker.last}")
        >>>
        >>> bridge.request_market_data('SPY', callback=on_ticker)
        >>>
        >>> # Clean shutdown
        >>> bridge.stop()
    """

    def __init__(self):
        """Initialize the Modern AsyncIO bridge."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Core components
        self.ib: Optional[IB] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None

        # State management
        self.state = BridgeState.STOPPED
        self._shutdown_event = threading.Event()

        # Request queue for thread-safe communication
        self.request_queue: queue.Queue[AsyncRequest] = queue.Queue()

        # Callbacks storage
        self._callbacks: Dict[str, List[Callable]] = {
            "connected": [],
            "disconnected": [],
            "error": [],
            "ticker": [],
            "order_status": [],
            "position": [],
            "account_update": [],
        }

        # Active subscriptions
        self._market_data_subscriptions: Dict[str, Any] = {}

        self.logger.info("ModernAsyncIOBridge initialized with ib_async")

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================

    def start(self) -> bool:
        """
        Start the async bridge.

        Returns:
            bool: True if started successfully
        """
        if not HAS_IB_ASYNC:
            self.logger.error("ib_async not available - install with: pip install ib_async")
            return False

        if self.state != BridgeState.STOPPED:
            self.logger.warning(f"Cannot start from state: {self.state}")
            return False

        try:
            self.state = BridgeState.STARTING
            self._shutdown_event.clear()

            # Start async thread
            self.thread = threading.Thread(
                target=self._run_async_loop, name="IBAsyncBridge", daemon=True
            )
            self.thread.start()

            # Wait for startup with timeout
            for _ in range(30):  # 3 second timeout
                if self.state == BridgeState.RUNNING:
                    self.logger.info("Modern AsyncIO bridge started successfully")
                    return True
                threading.Event().wait(0.1)

            raise TimeoutError("Bridge startup timeout")

        except Exception as e:
            self.logger.error(f"Failed to start bridge: {e}")
            self.state = BridgeState.ERROR
            return False

    def stop(self) -> bool:
        """
        Stop the async bridge gracefully.

        Returns:
            bool: True if stopped successfully
        """
        if self.state not in [BridgeState.RUNNING, BridgeState.ERROR]:
            return True

        try:
            self.logger.info("Stopping Modern AsyncIO bridge...")
            self.state = BridgeState.STOPPING

            # Signal shutdown
            self._shutdown_event.set()

            # Send stop request
            try:
                self.request_queue.put(AsyncRequest("stop"), timeout=1.0)
            except queue.Full:
                self.logger.warning("Request queue full during shutdown")

            # Wait for thread to finish
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5)
                if self.thread.is_alive():
                    self.logger.warning("Thread did not stop cleanly")

            self.state = BridgeState.STOPPED
            self.logger.info("Modern AsyncIO bridge stopped")
            return True

        except Exception as e:
            self.logger.error(f"Error stopping bridge: {e}")
            return False

    # ==========================================================================
    # PUBLIC INTERFACE - IB OPERATIONS
    # ==========================================================================

    def connect_ib(
        self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, client_id: int = 1
    ) -> bool:
        """
        Connect to IB Gateway/TWS.

        Args:
            host: IB Gateway host address
            port: IB Gateway port
            client_id: Unique client ID

        Returns:
            bool: True if connected successfully
        """
        if self.state != BridgeState.RUNNING:
            self.logger.error("Bridge must be running to connect")
            return False

        future = asyncio.Future()

        def callback(response: AsyncResponse):
            if not future.done():
                future.set_result(response.success)

        request = AsyncRequest(
            "connect",
            callback=callback,
            kwargs={"host": host, "port": port, "client_id": client_id},
        )

        try:
            self.request_queue.put(request, timeout=QUEUE_TIMEOUT)
            return future.result(timeout=CONNECTION_TIMEOUT)
        except (queue.Full, asyncio.TimeoutError):
            self.logger.error("Connection request timeout")
            return False
        except Exception as e:
            self.logger.error(f"Connection request failed: {e}")
            return False

    def disconnect_ib(self) -> bool:
        """
        Disconnect from IB Gateway.

        Returns:
            bool: True if disconnect request submitted
        """
        try:
            request = AsyncRequest("disconnect")
            self.request_queue.put(request, timeout=QUEUE_TIMEOUT)
            return True
        except queue.Full:
            self.logger.error("Cannot submit disconnect request - queue full")
            return False

    def request_market_data(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """
        Request market data for a symbol.

        Args:
            symbol: Stock symbol (e.g., 'SPY', 'AAPL')
            callback: Function to call with ticker updates

        Returns:
            bool: True if request submitted successfully
        """
        if callback:
            self.add_callback("ticker", callback)

        try:
            request = AsyncRequest("market_data", kwargs={"symbol": symbol})
            self.request_queue.put(request, timeout=QUEUE_TIMEOUT)
            return True
        except queue.Full:
            self.logger.error(f"Cannot request market data for {symbol} - queue full")
            return False

    def cancel_market_data(self, symbol: str) -> bool:
        """
        Cancel market data for a symbol.

        Args:
            symbol: Stock symbol to cancel

        Returns:
            bool: True if cancel request submitted
        """
        try:
            request = AsyncRequest("cancel_market_data", kwargs={"symbol": symbol})
            self.request_queue.put(request, timeout=QUEUE_TIMEOUT)
            return True
        except queue.Full:
            self.logger.error(f"Cannot cancel market data for {symbol} - queue full")
            return False

    def get_positions(self, callback: Optional[Callable] = None) -> bool:
        """
        Get current positions.

        Args:
            callback: Function to call with positions list

        Returns:
            bool: True if request submitted
        """
        try:
            request = AsyncRequest("get_positions", callback=callback)
            self.request_queue.put(request, timeout=QUEUE_TIMEOUT)
            return True
        except queue.Full:
            self.logger.error("Cannot get positions - queue full")
            return False

    def place_order(self, contract: Any, order: Any, callback: Optional[Callable] = None) -> bool:
        """
        Place an order.

        Args:
            contract: IB contract object
            order: IB order object
            callback: Function to call with order updates

        Returns:
            bool: True if order submitted
        """
        if callback:
            self.add_callback("order_status", callback)

        try:
            request = AsyncRequest(
                "place_order", 
                kwargs={"contract": contract, "order": order}
            )
            self.request_queue.put(request, timeout=QUEUE_TIMEOUT)
            return True
        except queue.Full:
            self.logger.error("Cannot place order - queue full")
            return False

    def get_account_info(self, callback: Optional[Callable] = None) -> bool:
        """
        Get account information.

        Args:
            callback: Function to call with account data

        Returns:
            bool: True if request submitted
        """
        try:
            request = AsyncRequest("get_account", callback=callback)
            self.request_queue.put(request, timeout=QUEUE_TIMEOUT)
            return True
        except queue.Full:
            self.logger.error("Cannot get account info - queue full")
            return False

    # ==========================================================================
    # CALLBACK MANAGEMENT
    # ==========================================================================

    def add_callback(self, event_type: str, callback: Callable) -> bool:
        """
        Add a callback for an event type.

        Args:
            event_type: Type of event ('connected', 'ticker', 'order_status', etc.)
            callback: Function to call when event occurs

        Returns:
            bool: True if callback added successfully
        """
        if event_type in self._callbacks:
            if callback not in self._callbacks[event_type]:
                self._callbacks[event_type].append(callback)
                self.logger.debug(f"Added callback for {event_type}")
            return True
        else:
            self.logger.warning(f"Unknown event type: {event_type}")
            return False

    def remove_callback(self, event_type: str, callback: Callable) -> bool:
        """
        Remove a callback.

        Args:
            event_type: Event type
            callback: Callback function to remove

        Returns:
            bool: True if callback removed
        """
        if event_type in self._callbacks:
            if callback in self._callbacks[event_type]:
                self._callbacks[event_type].remove(callback)
                self.logger.debug(f"Removed callback for {event_type}")
            return True
        return False

    def clear_callbacks(self, event_type: Optional[str] = None):
        """
        Clear callbacks.

        Args:
            event_type: Specific event type to clear, or None for all
        """
        if event_type:
            self._callbacks[event_type] = []
            self.logger.debug(f"Cleared callbacks for {event_type}")
        else:
            for key in self._callbacks:
                self._callbacks[key] = []
            self.logger.debug("Cleared all callbacks")

    # ==========================================================================
    # PROPERTIES AND STATUS
    # ==========================================================================

    @property
    def is_connected(self) -> bool:
        """Check if connected to IB."""
        return self.ib is not None and self.ib.isConnected() if self.ib else False

    @property
    def is_running(self) -> bool:
        """Check if bridge is running."""
        return self.state == BridgeState.RUNNING

    def get_status(self) -> Dict[str, Any]:
        """
        Get bridge status information.

        Returns:
            Dictionary with status details
        """
        return {
            "state": self.state.value,
            "is_connected": self.is_connected,
            "is_running": self.is_running,
            "has_ib_async": HAS_IB_ASYNC,
            "active_subscriptions": len(self._market_data_subscriptions),
            "callback_counts": {k: len(v) for k, v in self._callbacks.items()},
        }

    # ==========================================================================
    # ASYNC EVENT LOOP (PRIVATE)
    # ==========================================================================

    def _run_async_loop(self):
        """Run the async event loop in a separate thread."""
        try:
            # Create new event loop for this thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            # Create IB instance
            self.ib = IB()

            # Setup IB callbacks
            self._setup_ib_callbacks()

            # Mark as running
            self.state = BridgeState.RUNNING

            # Run the processing loop
            self.loop.run_until_complete(self._process_requests())

        except Exception as e:
            self.logger.error(f"Async loop error: {e}")
            self.state = BridgeState.ERROR
            self._trigger_callbacks("error", {"error": str(e), "source": "async_loop"})
        finally:
            # Cleanup
            try:
                if self.ib and self.ib.isConnected():
                    self.ib.disconnect()
            except Exception as e:
                self.logger.warning(f"Cleanup error: {e}")
            finally:
                if self.loop and not self.loop.is_closed():
                    self.loop.close()

    async def _process_requests(self):
        """Process requests from the queue."""
        self.logger.debug("Starting request processing loop")

        while not self._shutdown_event.is_set():
            try:
                # Check for requests (non-blocking)
                try:
                    request = self.request_queue.get_nowait()
                    await self._handle_request(request)
                except queue.Empty:
                    pass

                # Small delay to prevent CPU spinning
                await asyncio.sleep(0.01)

            except Exception as e:
                self.logger.error(f"Request processing error: {e}")
                self._trigger_callbacks("error", {"error": str(e), "source": "request_processing"})

        self.logger.debug("Request processing loop ended")

    async def _handle_request(self, request: AsyncRequest):
        """Handle a single request."""
        try:
            response = AsyncResponse(success=False)

            if request.request_type == "stop":
                self._shutdown_event.set()
                response.success = True

            elif request.request_type == "connect":
                success = await self._connect(**request.kwargs)
                response.success = success

            elif request.request_type == "disconnect":
                self.ib.disconnect()
                response.success = True

            elif request.request_type == "market_data":
                await self._request_market_data(**request.kwargs)
                response.success = True

            elif request.request_type == "cancel_market_data":
                await self._cancel_market_data(**request.kwargs)
                response.success = True

            elif request.request_type == "get_positions":
                positions = self.ib.positions()
                response.success = True
                response.result = positions

            elif request.request_type == "place_order":
                trade = self.ib.placeOrder(**request.kwargs)
                response.success = True
                response.result = trade

            elif request.request_type == "get_account":
                account_values = self.ib.accountValues()
                response.success = True
                response.result = account_values

            else:
                self.logger.warning(f"Unknown request type: {request.request_type}")
                response.error = f"Unknown request type: {request.request_type}"

            # Call request callback if provided
            if request.callback:
                request.callback(response)

        except Exception as e:
            self.logger.error(f"Request handling error: {e}")
            response.error = str(e)
            if request.callback:
                request.callback(response)

    async def _connect(self, host: str, port: int, client_id: int) -> bool:
        """Connect to IB Gateway using ib_async."""
        try:
            self.logger.info(f"Connecting to IB Gateway at {host}:{port} with client_id={client_id}")
            
            # Use ib_async connect method
            await self.ib.connectAsync(host, port, clientId=client_id)

            if self.ib.isConnected():
                self.logger.info(f"Successfully connected to IB Gateway at {host}:{port}")
                self._trigger_callbacks("connected", {"host": host, "port": port, "client_id": client_id})
                return True
            else:
                self.logger.error("Connection failed - not connected after connectAsync")
                return False

        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self._trigger_callbacks("error", {"error": str(e), "source": "connection"})
            return False

    async def _request_market_data(self, symbol: str):
        """Request market data using ib_async."""
        try:
            from ib_async import Stock

            contract = Stock(symbol, "SMART", "USD")
            ticker = self.ib.reqMktData(contract)

            # Store subscription
            self._market_data_subscriptions[symbol] = ticker

            # Setup ticker callback
            def on_ticker_update(ticker):
                self._trigger_callbacks("ticker", ticker)

            ticker.updateEvent += on_ticker_update

            self.logger.debug(f"Market data requested for {symbol}")

        except Exception as e:
            self.logger.error(f"Market data request failed for {symbol}: {e}")
            self._trigger_callbacks("error", {"error": str(e), "source": "market_data", "symbol": symbol})

    async def _cancel_market_data(self, symbol: str):
        """Cancel market data subscription."""
        try:
            ticker = self._market_data_subscriptions.get(symbol)
            if ticker:
                self.ib.cancelMktData(ticker)
                del self._market_data_subscriptions[symbol]
                self.logger.debug(f"Market data cancelled for {symbol}")
            else:
                self.logger.warning(f"No active subscription for {symbol}")

        except Exception as e:
            self.logger.error(f"Cancel market data failed for {symbol}: {e}")

    # ==========================================================================
    # IB CALLBACKS
    # ==========================================================================

    def _setup_ib_callbacks(self):
        """Setup IB event callbacks."""
        self.ib.connectedEvent += self._on_connected
        self.ib.disconnectedEvent += self._on_disconnected
        self.ib.errorEvent += self._on_error
        self.ib.orderStatusEvent += self._on_order_status
        self.ib.positionEvent += self._on_position

    def _on_connected(self):
        """Handle connection event."""
        self.logger.info("IB connection established")
        self._trigger_callbacks("connected", None)

    def _on_disconnected(self):
        """Handle disconnection event."""
        self.logger.warning("IB connection lost")
        self._trigger_callbacks("disconnected", None)

    def _on_error(self, reqId, errorCode, errorString, contract):
        """Handle error event."""
        error_data = {
            "req_id": reqId,
            "code": errorCode,
            "message": errorString,
            "contract": contract,
        }
        
        # Log based on error severity
        if errorCode in [2104, 2106, 2158]:  # Informational messages
            self.logger.debug(f"IB Info {errorCode}: {errorString}")
        else:
            self.logger.error(f"IB Error {errorCode}: {errorString}")
        
        self._trigger_callbacks("error", error_data)

    def _on_order_status(self, trade):
        """Handle order status update."""
        self.logger.debug(f"Order status update: {trade.order.orderId}")
        self._trigger_callbacks("order_status", trade)

    def _on_position(self, position):
        """Handle position update."""
        self.logger.debug(f"Position update: {position.contract.symbol}")
        self._trigger_callbacks("position", position)

    def _trigger_callbacks(self, event_type: str, data: Any):
        """Trigger callbacks for an event."""
        for callback in self._callbacks.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                self.logger.error(f"Callback error for {event_type}: {e}")


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================


def create_async_bridge() -> ModernAsyncIOBridge:
    """
    Create a modern async bridge instance.

    Returns:
        ModernAsyncIOBridge instance ready for use
    """
    return ModernAsyncIOBridge()


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================


if __name__ == "__main__":
    # Example usage and testing
    import time

    logging.basicConfig(level=logging.INFO)

    print("ModernAsyncIOBridge Example (using ib_async)")
    print("=" * 60)

    # Create bridge
    bridge = ModernAsyncIOBridge()

    # Start bridge
    if bridge.start():
        print("✅ Bridge started successfully")

        # Connect to IB Gateway
        if bridge.connect_ib(host="127.0.0.1", port=4002, client_id=1):
            print("✅ Connected to IB Gateway")

            # Request market data
            def on_ticker(ticker):
                if ticker and hasattr(ticker, "last") and ticker.last:
                    print(f"📈 SPY: ${ticker.last}")

            bridge.request_market_data("SPY", callback=on_ticker)
            print("✅ Market data requested for SPY")

            # Show status
            status = bridge.get_status()
            print(f"📊 Bridge Status: {status}")

            # Run for a short time
            print("⏱️  Running for 5 seconds...")
            time.sleep(5)

            # Disconnect
            bridge.disconnect_ib()
            print("✅ Disconnected from IB")

        # Stop bridge
        bridge.stop()
        print("✅ Bridge stopped cleanly")

    else:
        print("❌ Failed to start bridge")

    print("\n🎉 Modern AsyncIO bridge demonstration complete!")
    print("💡 Remember to install: pip install ib_async")
