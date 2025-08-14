#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderB11_AsyncIOBridge.py
Group: B (Broker Integration)
Purpose: Simplified asyncio bridge for IB integration

Description:
    This module provides a simplified bridge between ib_insync's asyncio event loop
    and other parts of the system. It's been refactored to reduce complexity while
    maintaining essential functionality for systems that need async IB operations.

Author: Mohamed Talib
Date: 2025-01-04
Version: 2.0 (Simplified)
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
    from ib_insync import IB, util

    nest_asyncio.apply()
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False
    print("WARNING: ib_insync not available")

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


class SimplifiedAsyncIOBridge:
    """
    Simplified AsyncIO bridge for IB integration.

    This class provides a cleaner interface for running ib_insync operations
    in a separate thread with its own event loop. It's designed to be used
    when you need async IB operations but want to keep the rest of your
    application synchronous.

    Key simplifications:
    - Removed Qt dependencies (can work with any UI framework or none)
    - Simplified request/response pattern
    - Cleaner error handling
    - Reduced coupling with other modules

    Example:
        >>> bridge = SimplifiedAsyncIOBridge()
        >>> bridge.start()
        >>>
        >>> # Connect to IB
        >>> connected = bridge.connect_ib('127.0.0.1', 4002)
        >>>
        >>> # Request market data
        >>> def on_ticker(ticker):
        ...     print(f"Price: {ticker.last}")
        >>>
        >>> bridge.request_market_data('SPY', callback=on_ticker)
        >>>
        >>> # Stop when done
        >>> bridge.stop()
    """

    def __init__(self):
        """Initialize the AsyncIO bridge."""
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
        }

        # Active subscriptions
        self._market_data_subscriptions: Dict[str, Any] = {}

        self.logger.info("SimplifiedAsyncIOBridge initialized")

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================

    def start(self) -> bool:
        """
        Start the async bridge.

        Returns:
            bool: True if started successfully
        """
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

            # Wait for startup
            for _ in range(30):  # 3 second timeout
                if self.state == BridgeState.RUNNING:
                    self.logger.info("AsyncIO bridge started successfully")
                    return True
                threading.Event().wait(0.1)

            raise TimeoutError("Bridge startup timeout")

        except Exception as e:
            self.logger.error(f"Failed to start bridge: {e}")
            self.state = BridgeState.ERROR
            return False

    def stop(self) -> bool:
        """
        Stop the async bridge.

        Returns:
            bool: True if stopped successfully
        """
        if self.state not in [BridgeState.RUNNING, BridgeState.ERROR]:
            return True

        try:
            self.logger.info("Stopping AsyncIO bridge...")
            self.state = BridgeState.STOPPING

            # Signal shutdown
            self._shutdown_event.set()

            # Send stop request
            self.request_queue.put(AsyncRequest("stop"))

            # Wait for thread to finish
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5)

            self.state = BridgeState.STOPPED
            self.logger.info("AsyncIO bridge stopped")
            return True

        except Exception as e:
            self.logger.error(f"Error stopping bridge: {e}")
            return False

    # ==========================================================================
    # PUBLIC INTERFACE (SIMPLIFIED)
    # ==========================================================================

    def connect_ib(
        self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, client_id: int = 1
    ) -> bool:
        """
        Connect to IB Gateway/TWS.

        Args:
            host: IB Gateway host
            port: IB Gateway port
            client_id: Client ID

        Returns:
            bool: True if connected
        """
        future = asyncio.Future()

        def callback(response: AsyncResponse):
            if not future.done():
                future.set_result(response.success)

        request = AsyncRequest(
            "connect",
            callback=callback,
            kwargs={"host": host, "port": port, "client_id": client_id},
        )

        self.request_queue.put(request)

        try:
            return future.result(timeout=CONNECTION_TIMEOUT)
        except BaseException:
            return False

    def disconnect_ib(self) -> bool:
        """Disconnect from IB."""
        request = AsyncRequest("disconnect")
        self.request_queue.put(request)
        return True

    def request_market_data(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """
        Request market data for a symbol.

        Args:
            symbol: Stock symbol
            callback: Function to call with ticker updates

        Returns:
            bool: True if request submitted
        """
        if callback:
            self.add_callback("ticker", callback)

        request = AsyncRequest("market_data", kwargs={"symbol": symbol})

        self.request_queue.put(request)
        return True

    def cancel_market_data(self, symbol: str) -> bool:
        """Cancel market data for a symbol."""
        request = AsyncRequest("cancel_market_data", kwargs={"symbol": symbol})

        self.request_queue.put(request)
        return True

    def get_positions(self, callback: Optional[Callable] = None) -> bool:
        """
        Get current positions.

        Args:
            callback: Function to call with positions

        Returns:
            bool: True if request submitted
        """
        request = AsyncRequest("get_positions", callback=callback)

        self.request_queue.put(request)
        return True

    def place_order(self, contract: Any, order: Any, callback: Optional[Callable] = None) -> bool:
        """
        Place an order.

        Args:
            contract: IB contract
            order: IB order
            callback: Function to call with order updates

        Returns:
            bool: True if request submitted
        """
        if callback:
            self.add_callback("order_status", callback)

        request = AsyncRequest("place_order", kwargs={"contract": contract, "order": order})

        self.request_queue.put(request)
        return True

    # ==========================================================================
    # CALLBACK MANAGEMENT
    # ==========================================================================

    def add_callback(self, event_type: str, callback: Callable) -> bool:
        """Add a callback for an event type."""
        if event_type in self._callbacks:
            if callback not in self._callbacks[event_type]:
                self._callbacks[event_type].append(callback)
            return True
        return False

    def remove_callback(self, event_type: str, callback: Callable) -> bool:
        """Remove a callback."""
        if event_type in self._callbacks:
            if callback in self._callbacks[event_type]:
                self._callbacks[event_type].remove(callback)
            return True
        return False

    def clear_callbacks(self, event_type: Optional[str] = None):
        """Clear callbacks."""
        if event_type:
            self._callbacks[event_type] = []
        else:
            for key in self._callbacks:
                self._callbacks[key] = []

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
            self._trigger_callbacks("error", e)
        finally:
            # Cleanup
            if self.ib and self.ib.isConnected():
                self.ib.disconnect()
            if self.loop:
                self.loop.close()

    async def _process_requests(self):
        """Process requests from the queue."""
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

            # Call request callback if provided
            if request.callback:
                request.callback(response)

        except Exception as e:
            self.logger.error(f"Request handling error: {e}")
            response.error = str(e)
            if request.callback:
                request.callback(response)

    async def _connect(self, host: str, port: int, client_id: int) -> bool:
        """Connect to IB."""
        try:
            await self.ib.connectAsync(host, port, clientId=client_id)

            if self.ib.isConnected():
                self.logger.info(f"Connected to IB at {host}:{port}")
                self._trigger_callbacks("connected", None)
                return True

            return False

        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            return False

    async def _request_market_data(self, symbol: str):
        """Request market data."""
        try:
            from ib_insync import Stock

            contract = Stock(symbol, "SMART", "USD")
            ticker = self.ib.reqMktData(contract)

            # Store subscription
            self._market_data_subscriptions[symbol] = ticker

            # Setup ticker callback
            def on_ticker_update(ticker):
                self._trigger_callbacks("ticker", ticker)

            ticker.updateEvent += on_ticker_update

        except Exception as e:
            self.logger.error(f"Market data request failed: {e}")

    async def _cancel_market_data(self, symbol: str):
        """Cancel market data."""
        try:
            ticker = self._market_data_subscriptions.get(symbol)
            if ticker:
                self.ib.cancelMktData(ticker)
                del self._market_data_subscriptions[symbol]

        except Exception as e:
            self.logger.error(f"Cancel market data failed: {e}")

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
        self._trigger_callbacks("connected", None)

    def _on_disconnected(self):
        """Handle disconnection event."""
        self._trigger_callbacks("disconnected", None)

    def _on_error(self, reqId, errorCode, errorString, contract):
        """Handle error event."""
        error_data = {
            "req_id": reqId,
            "code": errorCode,
            "message": errorString,
            "contract": contract,
        }
        self._trigger_callbacks("error", error_data)

    def _on_order_status(self, trade):
        """Handle order status update."""
        self._trigger_callbacks("order_status", trade)

    def _on_position(self, position):
        """Handle position update."""
        self._trigger_callbacks("position", position)

    def _trigger_callbacks(self, event_type: str, data: Any):
        """Trigger callbacks for an event."""
        for callback in self._callbacks.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                self.logger.error(f"Callback error: {e}")


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================


def create_async_bridge() -> SimplifiedAsyncIOBridge:
    """
    Create a simplified async bridge instance.

    Returns:
        SimplifiedAsyncIOBridge instance
    """
    return SimplifiedAsyncIOBridge()


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================


if __name__ == "__main__":
    # Example usage
    import time

    logging.basicConfig(level=logging.INFO)

    print("SimplifiedAsyncIOBridge Example")
    print("=" * 50)

    # Create bridge
    bridge = SimplifiedAsyncIOBridge()

    # Start bridge
    if bridge.start():
        print("✅ Bridge started")

        # Connect to IB
        if bridge.connect_ib():
            print("✅ Connected to IB")

            # Request market data
            def on_ticker(ticker):
                if ticker and hasattr(ticker, "last") and ticker.last:
                    print(f"SPY: ${ticker.last}")

            bridge.request_market_data("SPY", callback=on_ticker)
            print("✅ Market data requested")

            # Run for a bit
            time.sleep(5)

            # Disconnect
            bridge.disconnect_ib()
            print("✅ Disconnected")

        # Stop bridge
        bridge.stop()
        print("✅ Bridge stopped")

    print("\nSimplified bridge demonstration complete!")
