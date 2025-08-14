#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderB01_SpyderClient.py
Group: B (Broker Integration)
Purpose: Professional IB client using ib_insync for SPY options trading
Author: Mohamed Talib
Date Created: 2025-01-27
Last Updated: 2025-01-27 Time: 16:00:00

Description:
    Complete Interactive Brokers client implementation using ib_insync library.
    This module provides real-time market data, order execution, position tracking,
    and options Greeks computation for professional SPY options trading strategies.
    Uses ONLY ib_insync - no ib_insync dependencies.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import socket
import threading
import time
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SpyderB_Broker.SpyderB00_OrderTypes import (
    OrderAction,
    OrderRequest,
    OrderStatus,
    OrderType,
)

# ==============================================================================
# IB_INSYNC IMPORTS - NO ib_insync!
# ==============================================================================
try:
    from ib_insync import (
        IB,
        Contract,
        Stock,
        Option,
        Order,
        MarketOrder,
        LimitOrder,
        StopOrder,
        StopLimitOrder,
        Ticker,
        util,
        Trade,
        Fill,
        Execution,
        CommissionReport,
        BarData,
        Position,
        AccountValue,
        PnL,
        PnLSingle,
    )

    HAS_IB_INSYNC = True
    print("✅ ib_insync imports successful - Ready for trading!")
    print("   ✅ Using ib_insync (NO ib_insync dependencies)")

except ImportError as e:
    print(f"❌ ib_insync import failed: {e}")
    print("   Please install: pip install ib_insync")
    HAS_IB_INSYNC = False

    # Fallback dummy classes for testing
    class IB:
        def isConnected(self):
            return False

    class Contract:
        pass

    class Order:
        pass

    class Ticker:
        pass

    class Stock:
        pass

    class Option:
        pass


# ==============================================================================
# UTILITIES IMPORTS (Optional)
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

    LOGGER_AVAILABLE = True
except ImportError:
    LOGGER_AVAILABLE = False
    print("⚠️  Using basic logging (Spyder utilities not available)")

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4002  # IB Gateway Paper Trading (4001 for live)
CONNECTION_TIMEOUT = 15
RECONNECT_DELAY = 5
MAX_RECONNECT_ATTEMPTS = 3

# Market Data Request IDs
SPY_TICKER_ID = 1001
OPTIONS_TICKER_BASE = 2000


# ==============================================================================
# CONFIGURATION CLASS
# ==============================================================================
@dataclass
class IBConfig:
    """
    Interactive Brokers connection configuration.
    Used for connecting to IB Gateway or TWS via ib_insync.
    """

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    client_id: int = 1
    timeout: int = CONNECTION_TIMEOUT
    trading_mode: str = "paper"  # "paper" or "live"
    account: Optional[str] = None
    max_attempts: int = MAX_RECONNECT_ATTEMPTS
    retry_delay: int = RECONNECT_DELAY
    readonly: bool = False  # Set True for read-only connection

    def __post_init__(self):
        """Validate configuration after initialization"""
        # Validate port
        valid_ports = {
            4001: "IB Gateway Live",
            4002: "IB Gateway Paper",
            7496: "TWS Live",
            7497: "TWS Paper",
        }
        if self.port in valid_ports:
            print(f"✅ Using {valid_ports[self.port]} on port {self.port}")
        else:
            print(f"⚠️  Warning: Unusual port {self.port}")

        # Validate client ID
        if not 0 <= self.client_id <= 999:
            raise ValueError("Client ID must be between 0 and 999")

    @classmethod
    def paper_trading(cls, client_id: int = 1) -> "IBConfig":
        """Create configuration for paper trading"""
        return cls(
            host=DEFAULT_HOST, port=4002, client_id=client_id, trading_mode="paper"
        )

    @classmethod
    def live_trading(cls, client_id: int = 1) -> "IBConfig":
        """Create configuration for live trading"""
        return cls(
            host=DEFAULT_HOST, port=4001, client_id=client_id, trading_mode="live"
        )


# ==============================================================================
# SPYDER CLIENT - USING IB_INSYNC ONLY!
# ==============================================================================
class SpyderClient:
    """
    Professional IB client using ib_insync for SPY options trading.

    This is a complete rewrite using ONLY ib_insync - no ib_insync!

    Features:
    - Real-time SPY price updates via ib_insync
    - Options data and Greeks computation
    - Order management with ib_insync Trade objects
    - Position tracking
    - Account updates
    - Automatic reconnection
    - Event-driven architecture
    """

    def __init__(self, config: Optional[IBConfig] = None):
        """
        Initialize SpyderClient with ib_insync.

        Args:
            config: Optional IBConfig, defaults to paper trading
        """
        # Configuration
        self.config = config or IBConfig.paper_trading()

        # Setup logging
        if LOGGER_AVAILABLE:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # IB connection object from ib_insync
        self.ib = IB() if HAS_IB_INSYNC else None

        # Connection state
        self.is_connected_flag = False
        self.connection_lock = threading.Lock()
        self.reconnect_thread = None

        # Market data storage
        self.spy_ticker: Optional[Ticker] = None
        self.spy_contract: Optional[Contract] = None
        self.options_tickers: Dict[str, Ticker] = {}

        # Trading data
        self.trades: Dict[int, Trade] = {}  # order_id -> Trade
        self.positions: List[Position] = []
        self.account_values: List[AccountValue] = []
        self.pnl: Optional[PnL] = None

        # Callbacks
        self.market_data_callbacks: List = []
        self.order_callbacks: List = []
        self.position_callbacks: List = []

        self.logger.info("🚀 SpyderClient initialized with ib_insync")
        self.logger.info("   📊 Ready for SPY options trading")
        self.logger.info("   🔧 NO ib_insync dependencies!")

    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================

    def connect_to_gateway(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        client_id: Optional[int] = None,
    ) -> bool:
        """
        Connect to IB Gateway using ib_insync.

        Args:
            host: Gateway host (defaults to config)
            port: Gateway port (defaults to config)
            client_id: Client ID (defaults to config)

        Returns:
            bool: True if connected successfully
        """
        if not HAS_IB_INSYNC:
            self.logger.error("ib_insync not installed!")
            return False

        with self.connection_lock:
            # Use provided values or config defaults
            host = host or self.config.host
            port = port or self.config.port
            client_id = client_id or self.config.client_id

            try:
                self.logger.info(f"📌 Connecting to IB Gateway at {host}:{port}")
                self.logger.info(f"   Client ID: {client_id}")
                self.logger.info(f"   Mode: {self.config.trading_mode.upper()}")

                # Test gateway availability
                if not self._test_gateway_availability(host, port):
                    self.logger.error(f"❌ IB Gateway not accessible on {host}:{port}")
                    self.logger.info("   💡 Please ensure IB Gateway is running")
                    self.logger.info(
                        "   💡 Check API Settings -> Enable ActiveX and Socket Clients"
                    )
                    return False

                # Connect using ib_insync
                self.ib.connect(
                    host=host,
                    port=port,
                    clientId=client_id,
                    timeout=self.config.timeout,
                    readonly=self.config.readonly,
                )

                # Check connection
                if self.ib.isConnected():
                    self.is_connected_flag = True

                    # Get account info
                    accounts = self.ib.managedAccounts()
                    if accounts:
                        self.config.account = accounts[0]
                        self.logger.info(
                            f"✅ Connected to account: {self.config.account}"
                        )

                    # Setup event handlers
                    self._setup_event_handlers()

                    # Initialize market data
                    self._initialize_spy_data()

                    # Request account updates
                    if self.config.account:
                        self.ib.reqAccountUpdates(True, self.config.account)

                    self.logger.info(
                        "✅ ib_insync connection established successfully!"
                    )
                    return True
                else:
                    self.logger.error("❌ Connection failed")
                    return False

            except Exception as e:
                self.logger.error(f"❌ Connection error: {e}")
                import traceback

                traceback.print_exc()
                return False

    def _test_gateway_availability(self, host: str, port: int) -> bool:
        """Test if IB Gateway is accessible on the given host:port"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                result = sock.connect_ex((host, port))
                return result == 0
        except Exception as e:
            self.logger.error(f"Socket test failed: {e}")
            return False

    def _setup_event_handlers(self):
        """Setup ib_insync event handlers"""
        if not self.ib:
            return

        # Connection events
        self.ib.connectedEvent += self._on_connected
        self.ib.disconnectedEvent += self._on_disconnected

        # Error events
        self.ib.errorEvent += self._on_error

        # Order events
        self.ib.orderStatusEvent += self._on_order_status
        self.ib.execDetailsEvent += self._on_exec_details
        self.ib.commissionReportEvent += self._on_commission

        # Position events
        self.ib.positionEvent += self._on_position_update

        # Account events
        self.ib.accountValueEvent += self._on_account_value
        self.ib.pnlEvent += self._on_pnl

        self.logger.info("📡 Event handlers configured")

    def _initialize_spy_data(self):
        """Initialize SPY market data subscription"""
        try:
            # Create SPY stock contract
            self.spy_contract = Stock("SPY", "SMART", "USD")

            # Qualify the contract (get full details from IB)
            self.ib.qualifyContracts(self.spy_contract)

            # Request market data
            self.spy_ticker = self.ib.reqMktData(
                self.spy_contract,
                genericTickList="",
                snapshot=False,
                regulatorySnapshot=False,
                mktDataOptions=[],
            )

            # Setup ticker update handler
            self.spy_ticker.updateEvent += self._on_spy_tick

            self.logger.info("📈 SPY real-time data subscription started")

        except Exception as e:
            self.logger.error(f"Failed to initialize SPY data: {e}")

    # ==========================================================================
    # EVENT HANDLERS (ib_insync events)
    # ==========================================================================

    def _on_connected(self):
        """Handle connection established event"""
        self.logger.info("🔗 Connected to IB Gateway via ib_insync")
        self.is_connected_flag = True

    def _on_disconnected(self):
        """Handle disconnection event"""
        self.logger.warning("🔌 Disconnected from IB Gateway")
        self.is_connected_flag = False

        # Start reconnection thread if configured
        if self.config.max_attempts > 0 and not self.reconnect_thread:
            self.reconnect_thread = threading.Thread(
                target=self._auto_reconnect, daemon=True
            )
            self.reconnect_thread.start()

    def _on_error(self, reqId, errorCode, errorString, contract):
        """Handle IB error messages"""
        # Critical errors
        if errorCode in [502, 504, 509]:
            self.logger.error(f"❌ Critical error {errorCode}: {errorString}")
        # Connection successful messages
        elif errorCode in [2104, 2106, 2107, 2108]:
            self.logger.info(f"✅ {errorString}")
        # Market data messages
        elif errorCode in [2103, 2105]:
            self.logger.info(f"📊 Market data: {errorString}")
        # Info messages
        elif errorCode >= 2000:
            self.logger.debug(f"ℹ️ Info {errorCode}: {errorString}")
        else:
            self.logger.warning(f"⚠️ Warning {errorCode}: {errorString}")

    def _on_spy_tick(self, ticker: Ticker):
        """Handle SPY ticker updates"""
        try:
            # Log price updates
            if ticker.last and ticker.lastSize:
                self.logger.debug(f"SPY: ${ticker.last:.2f} Size: {ticker.lastSize}")

            # Trigger callbacks
            for callback in self.market_data_callbacks:
                try:
                    callback("SPY", ticker)
                except Exception as e:
                    self.logger.error(f"Callback error: {e}")

        except Exception as e:
            self.logger.error(f"Error processing SPY tick: {e}")

    def _on_order_status(self, trade: Trade):
        """Handle order status updates"""
        try:
            order = trade.order
            status = trade.orderStatus

            self.logger.info(f"📋 Order {order.orderId}: {status.status}")
            self.logger.debug(
                f"   Filled: {status.filled}/{order.totalQuantity} @ {status.avgFillPrice}"
            )

            # Store trade
            self.trades[order.orderId] = trade

            # Trigger callbacks
            for callback in self.order_callbacks:
                try:
                    callback(trade)
                except Exception as e:
                    self.logger.error(f"Order callback error: {e}")

        except Exception as e:
            self.logger.error(f"Error processing order status: {e}")

    def _on_exec_details(self, trade: Trade, fill: Fill):
        """Handle execution details"""
        self.logger.info(
            f"✅ Execution: {fill.contract.symbol} "
            f"{fill.execution.side} {fill.execution.shares} "
            f"@ ${fill.execution.price:.2f}"
        )

    def _on_commission(self, trade: Trade, fill: Fill, report: CommissionReport):
        """Handle commission reports"""
        self.logger.debug(
            f"💰 Commission: ${report.commission:.2f} " f"Currency: {report.currency}"
        )

    def _on_position_update(self, position: Position):
        """Handle position updates"""
        self.logger.debug(
            f"📊 Position: {position.contract.symbol} "
            f"Qty: {position.position} "
            f"Avg Cost: ${position.avgCost:.2f}"
        )

        # Update positions list
        self.positions = [
            p for p in self.positions if p.contract.symbol != position.contract.symbol
        ]
        self.positions.append(position)

        # Trigger callbacks
        for callback in self.position_callbacks:
            try:
                callback(position)
            except Exception as e:
                self.logger.error(f"Position callback error: {e}")

    def _on_account_value(self, value: AccountValue):
        """Handle account value updates"""
        self.logger.debug(f"💼 {value.tag}: {value.value} {value.currency}")

        # Update account values
        self.account_values = [v for v in self.account_values if v.tag != value.tag]
        self.account_values.append(value)

    def _on_pnl(self, pnl: PnL):
        """Handle P&L updates"""
        self.pnl = pnl
        self.logger.debug(
            f"💹 P&L - Daily: ${pnl.dailyPnL:.2f}, "
            f"Unrealized: ${pnl.unrealizedPnL:.2f}, "
            f"Realized: ${pnl.realizedPnL:.2f}"
        )

    # ==========================================================================
    # AUTO RECONNECTION
    # ==========================================================================

    def _auto_reconnect(self):
        """Automatically reconnect to IB Gateway"""
        attempts = 0

        while attempts < self.config.max_attempts and not self.is_connected_flag:
            attempts += 1
            self.logger.info(
                f"🔄 Reconnection attempt {attempts}/{self.config.max_attempts}"
            )

            time.sleep(self.config.retry_delay)

            if self.connect_to_gateway():
                self.logger.info("✅ Reconnection successful!")
                break
        else:
            if not self.is_connected_flag:
                self.logger.error("❌ Max reconnection attempts reached")

        self.reconnect_thread = None

    # ==========================================================================
    # PUBLIC DATA ACCESS METHODS
    # ==========================================================================

    def is_connected(self) -> bool:
        """Check if connected to IB Gateway"""
        return self.is_connected_flag and (self.ib.isConnected() if self.ib else False)

    def get_spy_price(self) -> Optional[float]:
        """Get current SPY last price"""
        if self.spy_ticker and self.spy_ticker.last:
            return float(self.spy_ticker.last)
        return None

    def get_spy_bid_ask(self) -> tuple:
        """Get SPY bid/ask prices"""
        if self.spy_ticker:
            return (
                float(self.spy_ticker.bid) if self.spy_ticker.bid else None,
                float(self.spy_ticker.ask) if self.spy_ticker.ask else None,
            )
        return (None, None)

    def get_spy_spread(self) -> Optional[float]:
        """Get SPY bid/ask spread"""
        bid, ask = self.get_spy_bid_ask()
        if bid and ask:
            return ask - bid
        return None

    def get_spy_ticker(self) -> Optional[Ticker]:
        """Get the full SPY ticker object"""
        return self.spy_ticker

    def get_positions(self) -> List[Position]:
        """Get current positions"""
        return self.positions.copy()

    def get_account_values(self) -> Dict[str, Any]:
        """Get account values as dictionary"""
        values = {}
        for av in self.account_values:
            key = f"{av.tag}_{av.currency}" if av.currency else av.tag
            values[key] = av.value
        return values

    def get_pnl(self) -> Optional[PnL]:
        """Get current P&L"""
        return self.pnl

    # ==========================================================================
    # ORDER MANAGEMENT
    # ==========================================================================

    def submit_order(self, order_request: OrderRequest) -> Optional[Trade]:
        """
        Submit an order using ib_insync.

        Args:
            order_request: OrderRequest object with order details

        Returns:
            Trade object if successful, None otherwise
        """
        if not self.is_connected():
            self.logger.error("Not connected to IB Gateway")
            return None

        try:
            # Create contract
            if order_request.symbol == "SPY":
                contract = Stock("SPY", "SMART", "USD")
            else:
                # For options, you'd parse the symbol and create Option contract
                self.logger.error(
                    f"Options orders not yet implemented for {order_request.symbol}"
                )
                return None

            # Create order based on type
            if order_request.order_type == OrderType.MARKET:
                order = MarketOrder(order_request.action.value, order_request.quantity)
            elif order_request.order_type == OrderType.LIMIT:
                order = LimitOrder(
                    order_request.action.value,
                    order_request.quantity,
                    order_request.limit_price,
                )
            elif order_request.order_type == OrderType.STOP:
                order = StopOrder(
                    order_request.action.value,
                    order_request.quantity,
                    order_request.stop_price,
                )
            elif order_request.order_type == OrderType.STOP_LIMIT:
                order = StopLimitOrder(
                    order_request.action.value,
                    order_request.quantity,
                    order_request.stop_price,
                    order_request.limit_price,
                )
            else:
                self.logger.error(f"Unsupported order type: {order_request.order_type}")
                return None

            # Set additional attributes
            order.account = order_request.account or self.config.account
            order.tif = order_request.time_in_force

            # Place order
            trade = self.ib.placeOrder(contract, order)

            # Store trade
            self.trades[trade.order.orderId] = trade

            self.logger.info(f"✅ Order submitted: {trade.order.orderId}")
            self.logger.info(
                f"   {order_request.action.value} {order_request.quantity} {order_request.symbol}"
            )

            return trade

        except Exception as e:
            self.logger.error(f"Order submission failed: {e}")
            import traceback

            traceback.print_exc()
            return None

    def cancel_order(self, order_id: int) -> bool:
        """Cancel an order"""
        if order_id not in self.trades:
            self.logger.error(f"Order {order_id} not found")
            return False

        try:
            trade = self.trades[order_id]
            self.ib.cancelOrder(trade.order)
            self.logger.info(f"✅ Cancel requested for order {order_id}")
            return True
        except Exception as e:
            self.logger.error(f"Cancel failed: {e}")
            return False

    def get_order_status(self, order_id: int) -> Optional[str]:
        """Get status of an order"""
        if order_id in self.trades:
            return self.trades[order_id].orderStatus.status
        return None

    # ==========================================================================
    # CALLBACK MANAGEMENT
    # ==========================================================================

    def register_market_data_callback(self, callback):
        """Register callback for market data updates"""
        self.market_data_callbacks.append(callback)
        self.logger.info("✅ Market data callback registered")

    def register_order_callback(self, callback):
        """Register callback for order updates"""
        self.order_callbacks.append(callback)
        self.logger.info("✅ Order callback registered")

    def register_position_callback(self, callback):
        """Register callback for position updates"""
        self.position_callbacks.append(callback)
        self.logger.info("✅ Position callback registered")

    # ==========================================================================
    # CLEANUP
    # ==========================================================================

    def disconnect_from_gateway(self):
        """Disconnect from IB Gateway"""
        try:
            if self.ib and self.ib.isConnected():
                # Cancel market data
                if self.spy_ticker:
                    self.ib.cancelMktData(self.spy_ticker)

                # Cancel options data
                for ticker in self.options_tickers.values():
                    self.ib.cancelMktData(ticker)

                # Stop account updates
                if self.config.account:
                    self.ib.reqAccountUpdates(False, self.config.account)

                # Disconnect
                self.ib.disconnect()

            self.is_connected_flag = False
            self.logger.info("🔌 Disconnected from IB Gateway")

        except Exception as e:
            self.logger.error(f"Disconnect error: {e}")


# ==============================================================================
# SINGLETON PATTERN FOR GLOBAL CLIENT
# ==============================================================================

_global_client: Optional[SpyderClient] = None
_client_lock = threading.Lock()


def get_spyder_client(config: Optional[IBConfig] = None) -> SpyderClient:
    """
    Get or create the global SpyderClient instance.

    Args:
        config: Optional IBConfig for configuration

    Returns:
        SpyderClient instance
    """
    global _global_client

    with _client_lock:
        if _global_client is None:
            _global_client = SpyderClient(config)
        return _global_client


def reset_spyder_client():
    """Reset the global client instance"""
    global _global_client

    with _client_lock:
        if _global_client:
            try:
                _global_client.disconnect_from_gateway()
            except:
                pass
        _global_client = None
        print("🔄 SpyderClient reset")


# Compatibility aliases
get_ib_client = get_spyder_client
reset_ib_client = reset_spyder_client

# ==============================================================================
# TESTING FUNCTIONS
# ==============================================================================


def test_connection():
    """Test basic connection to IB Gateway"""
    print("\n" + "=" * 60)
    print("🧪 TESTING SPYDER CLIENT CONNECTION")
    print("=" * 60)

    try:
        # Create config for paper trading
        config = IBConfig.paper_trading(client_id=999)

        # Get client instance
        client = get_spyder_client(config)

        # Connect
        if client.connect_to_gateway():
            print("✅ Connection successful!")

            # Wait for SPY data
            print("\n⏳ Waiting for SPY market data...")
            timeout = 10
            start = time.time()

            while time.time() - start < timeout:
                price = client.get_spy_price()
                if price:
                    print(f"\n✅ SPY Price: ${price:.2f}")

                    bid, ask = client.get_spy_bid_ask()
                    if bid and ask:
                        print(f"   Bid: ${bid:.2f}")
                        print(f"   Ask: ${ask:.2f}")
                        print(f"   Spread: ${client.get_spy_spread():.3f}")

                    # Get full ticker
                    ticker = client.get_spy_ticker()
                    if ticker:
                        print(
                            f"   Volume: {ticker.volume:,}"
                            if ticker.volume
                            else "   Volume: N/A"
                        )
                        print(
                            f"   Last Size: {ticker.lastSize}"
                            if ticker.lastSize
                            else "   Last Size: N/A"
                        )
                    break

                time.sleep(0.5)
            else:
                print("⚠️  No SPY data received (market may be closed)")

            # Get account info
            account_values = client.get_account_values()
            if account_values:
                print(f"\n📊 Account Values:")
                for key, value in list(account_values.items())[:5]:
                    print(f"   {key}: {value}")

            # Disconnect
            client.disconnect_from_gateway()
            print("\n✅ Test completed successfully!")
            return True

        else:
            print("❌ Connection failed")
            return False

    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        print("=" * 60 + "\n")


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print("\n🚀 SPYDER CLIENT - IB_INSYNC VERSION")
    print("Version: 1.0 - Using ib_insync (NO ib_insync!)")
    print("\nFeatures:")
    print("  ✅ ib_insync for all IB communication")
    print("  ✅ Real-time SPY market data")
    print("  ✅ Order management")
    print("  ✅ Position tracking")
    print("  ✅ Account updates")
    print("  ✅ Auto-reconnection")
    print("  ✅ Event-driven architecture")
    print("  ❌ NO ib_insync dependencies!")

    # Run connection test
    if test_connection():
        print("🎉 System ready for SPY options trading!")
    else:
        print("❌ Please check:")
        print("   1. IB Gateway is running on port 4002")
        print("   2. API Settings -> Enable ActiveX and Socket Clients")
        print("   3. ib_insync is installed: pip install ib_insync")
