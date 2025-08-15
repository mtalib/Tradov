#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderI15_IBTradingInterface.py
Group: I (Integration)
Purpose: High-level trading operations interface for SPY options trading via ib_async
Author: Mohamed Talib
Date Created: 2025-08-15
Last Updated: 2025-08-15 Time: 16:00:00

Description:
    Comprehensive trading interface for SPY options trading using ib_async library.
    Provides market data management, options chain retrieval, order management, position
    tracking, and real-time Greeks monitoring. Integrates with IBConnectionManager for
    connection management and provides async/await based interface for modern Python
    development. Optimized specifically for SPY options with built-in risk management.
"""

import logging
import asyncio
import threading
import time
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any, List, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import json
from decimal import Decimal

# Import ib_async
try:
    from ib_async import IB, Stock, Option, Contract, Order, MarketOrder, LimitOrder
    from ib_async import OptionChain, Ticker, PortfolioItem, Position, AccountValue
    from ib_async import util
    IB_ASYNC_AVAILABLE = True
except ImportError:
    IB_ASYNC_AVAILABLE = False

# Import connection manager
try:
    from SpyderI14_IBConnectionManager import IBConnectionManager, ConnectionState, ConnectionEvent
    CONNECTION_MANAGER_AVAILABLE = True
except ImportError:
    CONNECTION_MANAGER_AVAILABLE = False

# ================================================================================================
# TRADING DATA STRUCTURES
# ================================================================================================

class OptionType(Enum):
    """Option types"""
    CALL = "C"
    PUT = "P"

class OrderAction(Enum):
    """Order actions"""
    BUY = "BUY"
    SELL = "SELL"

class OrderType(Enum):
    """Order types"""
    MARKET = "MKT"
    LIMIT = "LMT"

class OrderStatus(Enum):
    """Order status"""
    PENDING = "PendingSubmit"
    SUBMITTED = "Submitted"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    INACTIVE = "Inactive"

class TradingEvent(Enum):
    """Trading events"""
    MARKET_DATA_RECEIVED = "market_data_received"
    OPTIONS_CHAIN_RECEIVED = "options_chain_received"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    POSITION_UPDATED = "position_updated"
    PORTFOLIO_UPDATED = "portfolio_updated"
    TICKER_UPDATED = "ticker_updated"
    ERROR_OCCURRED = "error_occurred"

@dataclass
class SpyderOptionContract:
    """SPY option contract data structure"""
    symbol: str = "SPY"
    expiry: str = ""  # YYYYMMDD format
    strike: float = 0.0
    option_type: OptionType = OptionType.CALL
    
    # Market data
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    
    # Greeks
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    implied_volatility: Optional[float] = None
    
    # Internal
    ib_contract: Optional[Contract] = None
    ticker: Optional[Ticker] = None
    last_update: Optional[datetime] = None
    
    def to_ib_contract(self) -> Contract:
        """Convert to ib_async Contract"""
        if self.ib_contract:
            return self.ib_contract
            
        return Option(
            symbol=self.symbol,
            lastTradeDateOrContractMonth=self.expiry,
            strike=self.strike,
            right=self.option_type.value,
            exchange="SMART",
            currency="USD"
        )

@dataclass
class SpyderOrder:
    """Trading order information"""
    order_id: Optional[int] = None
    contract: Optional[SpyderOptionContract] = None
    action: Optional[OrderAction] = None
    order_type: Optional[OrderType] = None
    quantity: int = 0
    limit_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    avg_fill_price: Optional[float] = None
    remaining_quantity: int = 0
    submission_time: Optional[datetime] = None
    fill_time: Optional[datetime] = None
    ib_order: Optional[Order] = None
    error_message: Optional[str] = None

@dataclass
class SpyderPosition:
    """Position information"""
    contract: SpyderOptionContract
    quantity: int
    avg_cost: float
    market_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    last_update: Optional[datetime] = None

@dataclass
class PortfolioSummary:
    """Portfolio summary"""
    total_cash: float = 0.0
    net_liquidation_value: float = 0.0
    buying_power: float = 0.0
    total_unrealized_pnl: float = 0.0
    positions_count: int = 0
    equity_with_loan_value: float = 0.0
    last_update: Optional[datetime] = None

@dataclass
class MarketSnapshot:
    """Market data snapshot"""
    spy_price: Optional[float] = None
    spy_bid: Optional[float] = None
    spy_ask: Optional[float] = None
    spy_volume: Optional[int] = None
    timestamp: Optional[datetime] = None

# ================================================================================================
# ASYNC EVENT EMITTER
# ================================================================================================

class AsyncEventEmitter:
    """Async event emitter for trading events"""
    
    def __init__(self):
        self._handlers: Dict[TradingEvent, List[Callable]] = {}
        self.logger = logging.getLogger(f"{__name__}.AsyncEventEmitter")
    
    def on(self, event: TradingEvent, handler: Callable):
        """Register event handler"""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)
        self.logger.debug(f"Registered handler for {event.value}")
    
    def off(self, event: TradingEvent, handler: Callable):
        """Remove event handler"""
        if event in self._handlers:
            try:
                self._handlers[event].remove(handler)
            except ValueError:
                pass
    
    async def emit(self, event: TradingEvent, data: Any = None):
        """Emit event to all handlers"""
        if event in self._handlers:
            event_data = {
                "event": event.value,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            
            for handler in self._handlers[event]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event_data)
                    else:
                        handler(event_data)
                except Exception as e:
                    self.logger.error(f"Error in event handler for {event.value}: {e}")

# ================================================================================================
# MAIN TRADING INTERFACE
# ================================================================================================

class IBTradingInterface:
    """
    High-level async trading interface for SPY options trading
    
    Features:
    - Async/await based interface using ib_async
    - Real-time market data for SPY and options
    - Options chain retrieval and management
    - Order placement and tracking
    - Position and portfolio monitoring
    - Event-driven architecture
    - Built-in risk management hooks
    """
    
    def __init__(self, connection_manager: IBConnectionManager):
        """
        Initialize trading interface
        
        Args:
            connection_manager: IBConnectionManager instance
        """
        if not IB_ASYNC_AVAILABLE:
            raise RuntimeError("ib_async not available - install with: pip install ib_async")
        
        if not CONNECTION_MANAGER_AVAILABLE:
            raise RuntimeError("Connection manager not available")
        
        self.connection_manager = connection_manager
        self.logger = logging.getLogger(f"{__name__}.IBTradingInterface")
        
        # ib_async client
        self.ib = IB()
        self.ib.errorEvent += self._on_error
        self.ib.orderStatusEvent += self._on_order_status
        self.ib.openOrderEvent += self._on_open_order
        self.ib.positionEvent += self._on_position
        self.ib.accountValueEvent += self._on_account_value
        self.ib.portfolioEvent += self._on_portfolio
        
        # Data storage
        self._spy_contract = Stock("SPY", "SMART", "USD")
        self._spy_ticker: Optional[Ticker] = None
        self._option_contracts: Dict[str, SpyderOptionContract] = {}
        self._active_orders: Dict[int, SpyderOrder] = {}
        self._positions: Dict[str, SpyderPosition] = {}
        self._portfolio_summary = PortfolioSummary()
        self._market_snapshot = MarketSnapshot()
        
        # Event system
        self.event_emitter = AsyncEventEmitter()
        
        # State
        self._connected = False
        self._subscribed_contracts: Dict[str, Contract] = {}
        
        # Threading for event loop
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._running = False
        
        self.logger.info("IBTradingInterface initialized with ib_async")
    
    # ==============================================================================================
    # CONNECTION MANAGEMENT
    # ==============================================================================================
    
    async def connect(self) -> bool:
        """
        Connect to IB Gateway using ib_async
        
        Returns:
            True if connected successfully, False otherwise
        """
        try:
            if not self.connection_manager.is_connected():
                self.logger.error("Connection manager not connected")
                return False
            
            port = self.connection_manager.config.port
            client_id = self.connection_manager.config.client_id
            
            self.logger.info(f"Connecting to IB API on port {port} with client ID {client_id}")
            
            # Connect using ib_async
            await self.ib.connectAsync("127.0.0.1", port, clientId=client_id)
            
            if self.ib.isConnected():
                self._connected = True
                self.logger.info("✅ Connected to IB API via ib_async")
                
                # Subscribe to SPY market data
                await self._subscribe_spy_data()
                
                # Request account summary
                await self._request_account_data()
                
                return True
            else:
                self.logger.error("❌ Failed to connect to IB API")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Connection error: {e}")
            return False
    
    def start(self) -> bool:
        """
        Start the trading interface in a separate thread
        
        Returns:
            True if started successfully, False otherwise
        """
        try:
            if self._running:
                self.logger.warning("Trading interface already running")
                return True
            
            # Start event loop in separate thread
            self._running = True
            self._loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
            self._loop_thread.start()
            
            # Wait for connection
            timeout = 10
            start_time = time.time()
            while not self._connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if self._connected:
                self.logger.info("✅ Trading interface started successfully")
                return True
            else:
                self.logger.error("❌ Trading interface connection timeout")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error starting trading interface: {e}")
            return False
    
    def stop(self) -> bool:
        """
        Stop the trading interface
        
        Returns:
            True if stopped successfully, False otherwise
        """
        try:
            self.logger.info("Stopping trading interface...")
            
            self._running = False
            
            # Disconnect from IB
            if self._event_loop and not self._event_loop.is_closed():
                future = asyncio.run_coroutine_threadsafe(self._disconnect(), self._event_loop)
                future.result(timeout=5)
            
            # Wait for thread to finish
            if self._loop_thread and self._loop_thread.is_alive():
                self._loop_thread.join(timeout=5)
            
            self.logger.info("✅ Trading interface stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping trading interface: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if connected to IB API"""
        return self._connected and self.ib.isConnected()
    
    # ==============================================================================================
    # MARKET DATA METHODS
    # ==============================================================================================
    
    def get_spy_price(self) -> Optional[float]:
        """Get current SPY price"""
        if self._spy_ticker and self._spy_ticker.last:
            return float(self._spy_ticker.last)
        return None
    
    def get_market_snapshot(self) -> MarketSnapshot:
        """Get current market snapshot"""
        if self._spy_ticker:
            self._market_snapshot.spy_price = float(self._spy_ticker.last) if self._spy_ticker.last else None
            self._market_snapshot.spy_bid = float(self._spy_ticker.bid) if self._spy_ticker.bid else None
            self._market_snapshot.spy_ask = float(self._spy_ticker.ask) if self._spy_ticker.ask else None
            self._market_snapshot.spy_volume = int(self._spy_ticker.volume) if self._spy_ticker.volume else None
            self._market_snapshot.timestamp = datetime.now()
        
        return self._market_snapshot
    
    def get_options_chain(self, expiry_date: str, strikes_around_spot: int = 10) -> List[SpyderOptionContract]:
        """
        Get SPY options chain for specified expiry (synchronous wrapper)
        
        Args:
            expiry_date: Expiry date in YYYYMMDD format
            strikes_around_spot: Number of strikes around current SPY price
            
        Returns:
            List of option contracts
        """
        if not self._event_loop:
            self.logger.error("Event loop not available")
            return []
        
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._get_options_chain_async(expiry_date, strikes_around_spot),
                self._event_loop
            )
            return future.result(timeout=30)
        except Exception as e:
            self.logger.error(f"❌ Error getting options chain: {e}")
            return []
    
    async def _get_options_chain_async(self, expiry_date: str, strikes_around_spot: int = 10) -> List[SpyderOptionContract]:
        """
        Get SPY options chain async implementation
        
        Args:
            expiry_date: Expiry date in YYYYMMDD format
            strikes_around_spot: Number of strikes around current SPY price
            
        Returns:
            List of option contracts
        """
        try:
            self.logger.info(f"Requesting options chain for SPY {expiry_date}")
            
            # Get SPY price for strike selection
            spy_price = self.get_spy_price()
            if not spy_price:
                self.logger.error("SPY price not available")
                return []
            
            # Create option chain request
            chains = await self.ib.reqSecDefOptParamsAsync(
                underlyingSymbol="SPY",
                futFopExchange="",
                underlyingSecType="STK",
                underlyingConId=756733  # SPY conId
            )
            
            if not chains:
                self.logger.error("No option chains received")
                return []
            
            # Find the right chain for our expiry
            target_chain = None
            for chain in chains:
                if expiry_date in chain.expirations:
                    target_chain = chain
                    break
            
            if not target_chain:
                self.logger.error(f"No chain found for expiry {expiry_date}")
                return []
            
            # Get strikes around current price
            all_strikes = sorted([float(s) for s in target_chain.strikes])
            center_idx = min(range(len(all_strikes)), key=lambda i: abs(all_strikes[i] - spy_price))
            
            start_idx = max(0, center_idx - strikes_around_spot // 2)
            end_idx = min(len(all_strikes), center_idx + strikes_around_spot // 2)
            selected_strikes = all_strikes[start_idx:end_idx]
            
            # Create option contracts
            option_contracts = []
            
            for strike in selected_strikes:
                # Create CALL
                call_contract = SpyderOptionContract(
                    symbol="SPY",
                    expiry=expiry_date,
                    strike=strike,
                    option_type=OptionType.CALL
                )
                call_contract.ib_contract = call_contract.to_ib_contract()
                option_contracts.append(call_contract)
                
                # Create PUT
                put_contract = SpyderOptionContract(
                    symbol="SPY",
                    expiry=expiry_date,
                    strike=strike,
                    option_type=OptionType.PUT
                )
                put_contract.ib_contract = put_contract.to_ib_contract()
                option_contracts.append(put_contract)
            
            self.logger.info(f"✅ Retrieved {len(option_contracts)} option contracts")
            
            # Emit event
            await self.event_emitter.emit(TradingEvent.OPTIONS_CHAIN_RECEIVED, {
                "expiry": expiry_date,
                "contracts": option_contracts,
                "spy_price": spy_price
            })
            
            return option_contracts
            
        except Exception as e:
            self.logger.error(f"❌ Error getting options chain: {e}")
            return []
    
    def subscribe_option_data(self, option_contract: SpyderOptionContract) -> bool:
        """
        Subscribe to real-time data for an option contract
        
        Args:
            option_contract: Option contract to subscribe to
            
        Returns:
            True if subscription successful, False otherwise
        """
        if not self._event_loop:
            return False
        
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._subscribe_option_data_async(option_contract),
                self._event_loop
            )
            return future.result(timeout=10)
        except Exception as e:
            self.logger.error(f"❌ Error subscribing to option data: {e}")
            return False
    
    async def _subscribe_option_data_async(self, option_contract: SpyderOptionContract) -> bool:
        """Subscribe to option data async implementation"""
        try:
            ib_contract = option_contract.to_ib_contract()
            
            # Qualify the contract first
            qualified_contracts = await self.ib.qualifyContractsAsync(ib_contract)
            if not qualified_contracts:
                self.logger.error(f"Could not qualify contract: {option_contract.symbol} {option_contract.expiry} {option_contract.strike}{option_contract.option_type.value}")
                return False
            
            qualified_contract = qualified_contracts[0]
            
            # Subscribe to market data
            ticker = self.ib.reqMktData(qualified_contract, "", False, False)
            
            # Store subscription
            contract_key = f"{option_contract.symbol}_{option_contract.expiry}_{option_contract.strike}_{option_contract.option_type.value}"
            self._subscribed_contracts[contract_key] = qualified_contract
            option_contract.ticker = ticker
            option_contract.ib_contract = qualified_contract
            self._option_contracts[contract_key] = option_contract
            
            self.logger.info(f"✅ Subscribed to option data: {contract_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error subscribing to option data: {e}")
            return False
    
    # ==============================================================================================
    # ORDER MANAGEMENT METHODS
    # ==============================================================================================
    
    def place_option_order(self, option_contract: SpyderOptionContract, action: OrderAction, 
                          quantity: int, order_type: OrderType = OrderType.MARKET, 
                          limit_price: Optional[float] = None) -> Optional[SpyderOrder]:
        """
        Place an option order (synchronous wrapper)
        
        Args:
            option_contract: Option contract to trade
            action: BUY or SELL
            quantity: Number of contracts
            order_type: MARKET or LIMIT
            limit_price: Limit price (required for LIMIT orders)
            
        Returns:
            SpyderOrder if successful, None otherwise
        """
        if not self._event_loop:
            self.logger.error("Event loop not available")
            return None
        
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._place_option_order_async(option_contract, action, quantity, order_type, limit_price),
                self._event_loop
            )
            return future.result(timeout=10)
        except Exception as e:
            self.logger.error(f"❌ Error placing option order: {e}")
            return None
    
    async def _place_option_order_async(self, option_contract: SpyderOptionContract, action: OrderAction,
                                       quantity: int, order_type: OrderType = OrderType.MARKET,
                                       limit_price: Optional[float] = None) -> Optional[SpyderOrder]:
        """Place option order async implementation"""
        try:
            # Get qualified contract
            ib_contract = option_contract.to_ib_contract()
            qualified_contracts = await self.ib.qualifyContractsAsync(ib_contract)
            
            if not qualified_contracts:
                self.logger.error("Could not qualify contract")
                return None
            
            qualified_contract = qualified_contracts[0]
            
            # Create order
            if order_type == OrderType.MARKET:
                ib_order = MarketOrder(action.value, quantity)
            elif order_type == OrderType.LIMIT:
                if limit_price is None:
                    self.logger.error("Limit price required for LIMIT orders")
                    return None
                ib_order = LimitOrder(action.value, quantity, limit_price)
            else:
                self.logger.error(f"Unsupported order type: {order_type}")
                return None
            
            # Place order
            trade = self.ib.placeOrder(qualified_contract, ib_order)
            
            # Create SpyderOrder
            spyder_order = SpyderOrder(
                order_id=ib_order.orderId,
                contract=option_contract,
                action=action,
                order_type=order_type,
                quantity=quantity,
                limit_price=limit_price,
                submission_time=datetime.now(),
                ib_order=ib_order
            )
            
            # Store order
            self._active_orders[ib_order.orderId] = spyder_order
            
            self.logger.info(f"📤 Placed {action.value} order for {quantity} {option_contract.symbol} {option_contract.expiry} {option_contract.strike}{option_contract.option_type.value}")
            
            # Emit event
            await self.event_emitter.emit(TradingEvent.ORDER_SUBMITTED, spyder_order)
            
            return spyder_order
            
        except Exception as e:
            self.logger.error(f"❌ Error placing option order: {e}")
            return None
    
    def cancel_order(self, order_id: int) -> bool:
        """Cancel an order"""
        if not self._event_loop:
            return False
        
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._cancel_order_async(order_id),
                self._event_loop
            )
            return future.result(timeout=10)
        except Exception as e:
            self.logger.error(f"❌ Error cancelling order: {e}")
            return False
    
    async def _cancel_order_async(self, order_id: int) -> bool:
        """Cancel order async implementation"""
        try:
            if order_id not in self._active_orders:
                self.logger.error(f"Order {order_id} not found")
                return False
            
            spyder_order = self._active_orders[order_id]
            if spyder_order.ib_order:
                self.ib.cancelOrder(spyder_order.ib_order)
                self.logger.info(f"🚫 Cancelled order {order_id}")
                return True
            else:
                self.logger.error(f"No IB order found for {order_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error cancelling order: {e}")
            return False
    
    def get_active_orders(self) -> List[SpyderOrder]:
        """Get all active orders"""
        return list(self._active_orders.values())
    
    def get_order_status(self, order_id: int) -> Optional[SpyderOrder]:
        """Get status of specific order"""
        return self._active_orders.get(order_id)
    
    # ==============================================================================================
    # POSITION AND PORTFOLIO METHODS
    # ==============================================================================================
    
    def get_positions(self) -> List[SpyderPosition]:
        """Get all current positions"""
        return list(self._positions.values())
    
    def get_spy_options_positions(self) -> List[SpyderPosition]:
        """Get SPY options positions only"""
        return [pos for pos in self.get_positions() if pos.contract.symbol == "SPY"]
    
    def get_portfolio_summary(self) -> PortfolioSummary:
        """Get portfolio summary"""
        return self._portfolio_summary
    
    def calculate_portfolio_greeks(self) -> Dict[str, float]:
        """Calculate total portfolio Greeks for SPY options"""
        greeks = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
        
        for position in self.get_spy_options_positions():
            contract = position.contract
            quantity = position.quantity
            
            if contract.delta is not None:
                greeks["delta"] += contract.delta * quantity
            if contract.gamma is not None:
                greeks["gamma"] += contract.gamma * quantity
            if contract.theta is not None:
                greeks["theta"] += contract.theta * quantity
            if contract.vega is not None:
                greeks["vega"] += contract.vega * quantity
        
        return greeks
    
    # ==============================================================================================
    # EVENT HANDLERS
    # ==============================================================================================
    
    def on_market_data(self, handler: Callable):
        """Register handler for market data events"""
        self.event_emitter.on(TradingEvent.MARKET_DATA_RECEIVED, handler)
    
    def on_options_chain(self, handler: Callable):
        """Register handler for options chain events"""
        self.event_emitter.on(TradingEvent.OPTIONS_CHAIN_RECEIVED, handler)
    
    def on_order_filled(self, handler: Callable):
        """Register handler for order filled events"""
        self.event_emitter.on(TradingEvent.ORDER_FILLED, handler)
    
    def on_position_updated(self, handler: Callable):
        """Register handler for position update events"""
        self.event_emitter.on(TradingEvent.POSITION_UPDATED, handler)
    
    def on_portfolio_updated(self, handler: Callable):
        """Register handler for portfolio update events"""
        self.event_emitter.on(TradingEvent.PORTFOLIO_UPDATED, handler)
    
    def on_ticker_updated(self, handler: Callable):
        """Register handler for ticker update events"""
        self.event_emitter.on(TradingEvent.TICKER_UPDATED, handler)
    
    def on_error(self, handler: Callable):
        """Register handler for error events"""
        self.event_emitter.on(TradingEvent.ERROR_OCCURRED, handler)
    
    # ==============================================================================================
    # PRIVATE METHODS
    # ==============================================================================================
    
    def _run_event_loop(self):
        """Run async event loop in separate thread"""
        try:
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)
            
            # Connect to IB
            self._event_loop.run_until_complete(self.connect())
            
            # Keep loop running
            while self._running:
                try:
                    self._event_loop.run_until_complete(asyncio.sleep(0.1))
                except Exception as e:
                    if self._running:  # Only log if we're supposed to be running
                        self.logger.error(f"Event loop error: {e}")
            
        except Exception as e:
            self.logger.error(f"Event loop thread error: {e}")
        finally:
            if self._event_loop and not self._event_loop.is_closed():
                self._event_loop.close()
    
    async def _disconnect(self):
        """Disconnect from IB"""
        try:
            if self.ib.isConnected():
                self.ib.disconnect()
            self._connected = False
            self.logger.info("Disconnected from IB API")
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
    
    async def _subscribe_spy_data(self):
        """Subscribe to SPY market data"""
        try:
            self._spy_ticker = self.ib.reqMktData(self._spy_contract, "", False, False)
            
            # Setup ticker update callback
            def on_ticker_update(ticker):
                asyncio.create_task(self._on_spy_ticker_update(ticker))
            
            self._spy_ticker.updateEvent += on_ticker_update
            
            self.logger.info("📈 Subscribed to SPY market data")
            
        except Exception as e:
            self.logger.error(f"❌ Error subscribing to SPY data: {e}")
    
    async def _request_account_data(self):
        """Request account data"""
        try:
            # Request positions
            positions = self.ib.positions()
            for position in positions:
                await self._on_position(position)
            
            # Request account summary
            account_values = self.ib.accountValues()
            for av in account_values:
                await self._on_account_value(av)
            
            self.logger.info("📊 Requested account data")
            
        except Exception as e:
            self.logger.error(f"❌ Error requesting account data: {e}")
    
    async def _on_spy_ticker_update(self, ticker):
        """Handle SPY ticker updates"""
        try:
            await self.event_emitter.emit(TradingEvent.MARKET_DATA_RECEIVED, {
                "symbol": "SPY",
                "bid": float(ticker.bid) if ticker.bid else None,
                "ask": float(ticker.ask) if ticker.ask else None,
                "last": float(ticker.last) if ticker.last else None,
                "volume": int(ticker.volume) if ticker.volume else None
            })
        except Exception as e:
            self.logger.error(f"Error handling SPY ticker update: {e}")
    
    def _on_error(self, reqId, errorCode, errorString, contract):
        """Handle IB errors"""
        error_msg = f"Error {errorCode}: {errorString}"
        if reqId != -1:
            error_msg = f"Request {reqId} - {error_msg}"
        
        self.logger.error(f"❌ IB API Error: {error_msg}")
        
        # Emit error event
        asyncio.create_task(self.event_emitter.emit(TradingEvent.ERROR_OCCURRED, {
            "request_id": reqId,
            "error_code": errorCode,
            "error_string": errorString,
            "contract": str(contract) if contract else None
        }))
    
    def _on_order_status(self, trade):
        """Handle order status updates"""
        try:
            order_id = trade.order.orderId
            
            if order_id in self._active_orders:
                spyder_order = self._active_orders[order_id]
                spyder_order.status = OrderStatus(trade.orderStatus.status) if hasattr(OrderStatus, trade.orderStatus.status) else OrderStatus.PENDING
                spyder_order.filled_quantity = int(trade.orderStatus.filled)
                spyder_order.remaining_quantity = int(trade.orderStatus.remaining)
                spyder_order.avg_fill_price = float(trade.orderStatus.avgFillPrice) if trade.orderStatus.avgFillPrice else None
                
                if trade.orderStatus.status == "Filled":
                    spyder_order.fill_time = datetime.now()
                    asyncio.create_task(self.event_emitter.emit(TradingEvent.ORDER_FILLED, spyder_order))
                elif trade.orderStatus.status == "Cancelled":
                    asyncio.create_task(self.event_emitter.emit(TradingEvent.ORDER_CANCELLED, spyder_order))
        except Exception as e:
            self.logger.error(f"Error handling order status: {e}")
    
    def _on_open_order(self, trade):
        """Handle open order updates"""
        # Additional order tracking if needed
        pass
    
    async def _on_position(self, position):
        """Handle position updates"""
        try:
            if position.contract.secType == "OPT" and position.contract.symbol == "SPY":
                # Create SpyderOptionContract
                option_contract = SpyderOptionContract(
                    symbol=position.contract.symbol,
                    expiry=position.contract.lastTradeDateOrContractMonth,
                    strike=float(position.contract.strike),
                    option_type=OptionType.CALL if position.contract.right == "C" else OptionType.PUT,
                    ib_contract=position.contract
                )
                
                # Create SpyderPosition
                spyder_position = SpyderPosition(
                    contract=option_contract,
                    quantity=int(position.position),
                    avg_cost=float(position.avgCost),
                    last_update=datetime.now()
                )
                
                # Store position
                position_key = f"{option_contract.symbol}_{option_contract.expiry}_{option_contract.strike}_{option_contract.option_type.value}"
                
                if abs(position.position) > 0:
                    self._positions[position_key] = spyder_position
                else:
                    self._positions.pop(position_key, None)
                
                await self.event_emitter.emit(TradingEvent.POSITION_UPDATED, spyder_position)
                
        except Exception as e:
            self.logger.error(f"Error handling position update: {e}")
    
    async def _on_account_value(self, account_value):
        """Handle account value updates"""
        try:
            key = account_value.tag
            value = account_value.value
            
            if key == "TotalCashValue":
                self._portfolio_summary.total_cash = float(value)
            elif key == "NetLiquidation":
                self._portfolio_summary.net_liquidation_value = float(value)
            elif key == "BuyingPower":
                self._portfolio_summary.buying_power = float(value)
            elif key == "UnrealizedPnL":
                self._portfolio_summary.total_unrealized_pnl = float(value)
            elif key == "EquityWithLoanValue":
                self._portfolio_summary.equity_with_loan_value = float(value)
            
            self._portfolio_summary.last_update = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error handling account value update: {e}")
    
    async def _on_portfolio(self, item):
        """Handle portfolio updates"""
        try:
            await self.event_emitter.emit(TradingEvent.PORTFOLIO_UPDATED, {
                "contract": str(item.contract),
                "position": float(item.position),
                "market_price": float(item.marketPrice),
                "market_value": float(item.marketValue),
                "unrealized_pnl": float(item.unrealizedPNL)
            })
        except Exception as e:
            self.logger.error(f"Error handling portfolio update: {e}")

# ================================================================================================
# CONVENIENCE FUNCTIONS
# ================================================================================================

def create_trading_interface(connection_manager: IBConnectionManager) -> IBTradingInterface:
    """
    Create trading interface with ib_async
    
    Args:
        connection_manager: IBConnectionManager instance
        
    Returns:
        Configured trading interface
    """
    return IBTradingInterface(connection_manager)

def get_spy_expiry_dates(days_ahead: int = 60) -> List[str]:
    """
    Get upcoming SPY option expiry dates
    
    Args:
        days_ahead: Number of days to look ahead
        
    Returns:
        List of expiry dates in YYYYMMDD format
    """
    expiry_dates = []
    current_date = date.today()
    
    # SPY options expire on Fridays (typically)
    for i in range(days_ahead):
        check_date = current_date + timedelta(days=i)
        if check_date.weekday() == 4:  # Friday
            expiry_dates.append(check_date.strftime("%Y%m%d"))
    
    return expiry_dates

def create_spy_option_contract(expiry: str, strike: float, option_type: str) -> SpyderOptionContract:
    """
    Create a SPY option contract
    
    Args:
        expiry: Expiry date in YYYYMMDD format
        strike: Strike price
        option_type: "C" for call, "P" for put
        
    Returns:
        SpyderOptionContract
    """
    return SpyderOptionContract(
        symbol="SPY",
        expiry=expiry,
        strike=strike,
        option_type=OptionType.CALL if option_type.upper() == "C" else OptionType.PUT
    )

# ================================================================================================
# MAIN EXECUTION
# ================================================================================================

if __name__ == "__main__":
    # Example usage and testing
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('spyder_trading_interface.log')
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("🎯 Testing Spyder IBTradingInterface with ib_async...")
        
        if not IB_ASYNC_AVAILABLE:
            logger.error("❌ ib_async not available - install with: pip install ib_async")
            sys.exit(1)
        
        if not CONNECTION_MANAGER_AVAILABLE:
            logger.error("❌ Connection manager not available")
            sys.exit(1)
        
        # Test expiry dates
        expiry_dates = get_spy_expiry_dates(30)
        logger.info(f"📅 Upcoming SPY expiry dates: {expiry_dates[:5]}")
        
        # Test option contract creation
        test_option = create_spy_option_contract("20250117", 450.0, "C")
        logger.info(f"📋 Test option contract: {test_option.symbol} {test_option.expiry} {test_option.strike}{test_option.option_type.value}")
        
        # Test ib_async contract conversion
        ib_contract = test_option.to_ib_contract()
        logger.info(f"🔄 Converted to ib_async contract: {ib_contract}")
        
        logger.info("✅ IBTradingInterface test completed successfully")
        logger.info("💡 Connect to IBConnectionManager to start live trading with ib_async")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)
