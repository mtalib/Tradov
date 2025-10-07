#!/usr/bin/env python3
"""
Threading-Safe Dashboard Connection Manager
Fix for "Gateway death after few minutes" by eliminating threading conflicts
"""

import sys
import asyncio
import threading
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
import queue
import time

sys.path.append("/home/adam/Projects/Spyder")

try:
    from ib_async import IB, Stock, Contract
    from PySide6.QtCore import QObject, QThread, QTimer, Signal
    from PySide6.QtWidgets import QApplication

    print("✅ All required modules imported successfully")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


@dataclass
class MarketDataRequest:
    """Request for market data"""

    symbol: str
    callback: Callable
    request_id: str
    contract_type: str = "STK"
    exchange: str = "SMART"
    currency: str = "USD"


class ThreadSafeIBConnection(QObject):
    """Thread-safe IB connection that runs in dedicated thread"""

    # Qt signals for thread-safe communication
    data_received = Signal(str, dict)  # symbol, data
    connection_status_changed = Signal(bool)  # connected
    error_occurred = Signal(str)  # error message

    def __init__(self):
        super().__init__()
        self.ib = IB()
        self.is_connected = False
        self.client_id = 100  # Use dedicated client ID for dashboard
        self.requests = {}  # Track active requests
        self.request_queue = queue.Queue()
        self.running = True

    async def connect_to_gateway(self):
        """Connect to IB Gateway with threading fixes"""
        try:
            print(f"🔌 Connecting to Gateway (Client ID: {self.client_id})...")

            # Use our proven 60s timeout
            await self.ib.connectAsync(
                host="127.0.0.1", port=4002, clientId=self.client_id, timeout=60.0
            )

            self.is_connected = True
            self.connection_status_changed.emit(True)

            # Get accounts to verify connection
            accounts = self.ib.managedAccounts()
            print(f"✅ Connected successfully! Accounts: {accounts}")

            return True

        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.error_occurred.emit(str(e))
            return False

    async def request_market_data(self, request: MarketDataRequest):
        """Request market data for a symbol"""
        try:
            if not self.is_connected:
                print(f"⚠️ Not connected - skipping {request.symbol}")
                return

            # Create contract
            if request.contract_type == "STK":
                contract = Stock(request.symbol, request.exchange, request.currency)
            else:
                # Handle other contract types
                contract = Contract()
                contract.symbol = request.symbol
                contract.secType = request.contract_type
                contract.exchange = request.exchange
                contract.currency = request.currency

            # Request market data
            ticker = self.ib.reqMktData(contract, "", False, False)

            # Store the request
            self.requests[request.request_id] = {
                "ticker": ticker,
                "callback": request.callback,
                "symbol": request.symbol,
            }

            print(f"📡 Requesting data for {request.symbol}")

        except Exception as e:
            print(f"❌ Error requesting data for {request.symbol}: {e}")
            self.error_occurred.emit(f"Data request failed for {request.symbol}: {e}")

    async def process_market_data(self):
        """Process incoming market data"""
        while self.running and self.is_connected:
            try:
                # Check all active tickers for updates
                for request_id, request_info in self.requests.items():
                    ticker = request_info["ticker"]
                    symbol = request_info["symbol"]

                    # Check if we have data
                    if (
                        (ticker.last and not (ticker.last != ticker.last))
                        or (ticker.bid and not (ticker.bid != ticker.bid))
                        or (ticker.ask and not (ticker.ask != ticker.ask))
                    ):

                        # Prepare data
                        data = {
                            "symbol": symbol,
                            "last": ticker.last,
                            "bid": ticker.bid,
                            "ask": ticker.ask,
                            "volume": ticker.volume,
                            "timestamp": datetime.now(),
                        }

                        # Emit signal (thread-safe)
                        self.data_received.emit(symbol, data)

                # Wait before next check
                await asyncio.sleep(1.0)

            except Exception as e:
                print(f"❌ Error processing market data: {e}")
                await asyncio.sleep(5.0)  # Wait longer on error

    async def run_connection_loop(self):
        """Main connection loop"""
        try:
            # Connect to Gateway
            if not await self.connect_to_gateway():
                return

            # Start data processing
            await self.process_market_data()

        except Exception as e:
            print(f"❌ Connection loop error: {e}")
            self.error_occurred.emit(str(e))
        finally:
            await self.disconnect()

    async def disconnect(self):
        """Disconnect from Gateway"""
        try:
            if self.ib.isConnected():
                self.ib.disconnect()
                print("🔌 Disconnected from Gateway")

            self.is_connected = False
            self.connection_status_changed.emit(False)

        except Exception as e:
            print(f"❌ Disconnect error: {e}")


class DashboardConnectionManager(QObject):
    """Thread-safe connection manager for trading dashboard"""

    # Signals for dashboard updates
    market_data_updated = Signal(str, dict)
    connection_status_changed = Signal(bool)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.connection_thread = None
        self.ib_connection = None
        self.is_running = False

    def start_connection(self):
        """Start the threaded IB connection"""
        if self.is_running:
            print("⚠️ Connection already running")
            return

        print("🚀 Starting thread-safe IB connection...")

        # Create connection object
        self.ib_connection = ThreadSafeIBConnection()

        # Connect signals
        self.ib_connection.data_received.connect(self.on_market_data_received)
        self.ib_connection.connection_status_changed.connect(
            self.on_connection_status_changed
        )
        self.ib_connection.error_occurred.connect(self.on_error_occurred)

        # Create and start thread
        self.connection_thread = QThread()
        self.ib_connection.moveToThread(self.connection_thread)

        # Connect thread signals
        self.connection_thread.started.connect(self.run_async_connection)

        # Start the thread
        self.connection_thread.start()
        self.is_running = True

        print("✅ Thread-safe connection started")

    def run_async_connection(self):
        """Run the async connection in the thread"""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Run the connection
            loop.run_until_complete(self.ib_connection.run_connection_loop())

        except Exception as e:
            print(f"❌ Async connection error: {e}")
            self.error_occurred.emit(str(e))

    def request_market_data(self, symbol: str, callback: Callable = None):
        """Request market data for a symbol"""
        if not self.ib_connection:
            print("⚠️ Connection not initialized")
            return

        request = MarketDataRequest(
            symbol=symbol, callback=callback, request_id=f"{symbol}_{int(time.time())}"
        )

        # Add to request queue (thread-safe)
        self.ib_connection.request_queue.put(request)
        print(f"📝 Queued data request for {symbol}")

    def on_market_data_received(self, symbol: str, data: dict):
        """Handle market data updates (thread-safe)"""
        self.market_data_updated.emit(symbol, data)

    def on_connection_status_changed(self, connected: bool):
        """Handle connection status changes"""
        status = "CONNECTED" if connected else "DISCONNECTED"
        print(f"🔗 Connection status: {status}")
        self.connection_status_changed.emit(connected)

    def on_error_occurred(self, error: str):
        """Handle errors"""
        print(f"❌ Connection error: {error}")
        self.error_occurred.emit(error)

    def stop_connection(self):
        """Stop the connection safely"""
        if not self.is_running:
            return

        print("🛑 Stopping thread-safe connection...")

        if self.ib_connection:
            self.ib_connection.running = False

        if self.connection_thread and self.connection_thread.isRunning():
            self.connection_thread.quit()
            self.connection_thread.wait(5000)  # Wait up to 5 seconds

        self.is_running = False
        print("✅ Thread-safe connection stopped")


# Test the threading fixes
def test_threading_fixes():
    """Test the thread-safe connection manager"""
    print("🧪 TESTING THREADING FIXES")
    print("=" * 50)

    app = QApplication(sys.argv)

    # Create connection manager
    manager = DashboardConnectionManager()

    # Test data callback
    def on_market_data(symbol, data):
        print(
            f"📊 {symbol}: Last=${data.get('last', 'N/A')}, Bid=${data.get('bid', 'N/A')}, Ask=${data.get('ask', 'N/A')}"
        )

    # Connect signals
    manager.market_data_updated.connect(on_market_data)

    def on_connected(connected):
        if connected:
            print("✅ Connected! Requesting test data...")
            # Request data for SPY
            manager.request_market_data("SPY")
        else:
            print("❌ Disconnected!")

    manager.connection_status_changed.connect(on_connected)

    # Start connection
    manager.start_connection()

    # Create timer to stop after 30 seconds
    timer = QTimer()
    timer.timeout.connect(lambda: [manager.stop_connection(), app.quit()])
    timer.start(30000)  # 30 seconds

    print("⏳ Testing for 30 seconds...")
    app.exec()

    print("🎯 Threading test completed!")


if __name__ == "__main__":
    test_threading_fixes()
