## 14. Standards/Trading/IBKR-Integration.md

```markdown
# Interactive Brokers Integration Standards for Spyder Trading System

## Overview

This document defines the standards and best practices for integrating with Interactive Brokers (IBKR) API within the Spyder trading system. Proper IBKR integration is critical for reliable order execution, real-time data processing, and account management.

## Connection Management Standards

### Connection Architecture

```python
import asyncio
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import threading
import time

class ConnectionState(Enum):
    """IBKR connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    ERROR = "error"
    RECONNECTING = "reconnecting"

@dataclass
class IBKRConnectionConfig:
    """IBKR connection configuration."""
    host: str = "127.0.0.1"
    port: int = 4002  # Paper trading port
    client_id: int = 1
    timeout: int = 30
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 5
    reconnect_delay: int = 5

class IBKRConnectionManager:
    """
    Robust IBKR connection manager with automatic reconnection.
    
    Handles connection lifecycle, error recovery, and state management
    for reliable IBKR API integration.
    """
    
    def __init__(self, config: IBKRConnectionConfig):
        self.config = config
        self.state = ConnectionState.DISCONNECTED
        self.connection_time = None
        self.last_error = None
        self.reconnect_attempts = 0
        
        # Connection monitoring
        self._heartbeat_thread = None
        self._heartbeat_interval = 30  # seconds
        self._last_heartbeat = None
        
        # Event callbacks
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        # Thread safety
        self._connection_lock = threading.RLock()
        
        self.logger = SpyderLogger.get_logger("IBKRConnection")
    
    def connect(self) -> bool:
        """Establish connection to IBKR Gateway."""
        
        with self._connection_lock:
            if self.state in [ConnectionState.CONNECTED, ConnectionState.CONNECTING]:
                self.logger.warning("Connection already established or in progress")
                return self.state == ConnectionState.CONNECTED
            
            try:
                self.state = ConnectionState.CONNECTING
                self.logger.info(f"Connecting to IBKR at {self.config.host}:{self.config.port}")
                
                # Establish connection
                success = self._establish_connection()
                
                if success:
                    self.state = ConnectionState.CONNECTED
                    self.connection_time = datetime.now()
                    self._start_heartbeat_monitor()
                    
                    if self.on_connected:
                        self.on_connected()
                    
                    self.logger.info("IBKR connection established successfully")
                    return True
                else:
                    self.state = ConnectionState.ERROR
                    self.logger.error("Failed to establish IBKR connection")
                    return False
                    
            except Exception as e:
                self.state = ConnectionState.ERROR
                self.last_error = str(e)
                self.logger.error(f"Connection error: {e}")
                return False
    
    def disconnect(self) -> bool:
        """Disconnect from IBKR Gateway."""
        
        with self._connection_lock:
            if self.state == ConnectionState.DISCONNECTED:
                return True
            
            try:
                self.logger.info("Disconnecting from IBKR")
                
                # Stop heartbeat monitoring
                self._stop_heartbeat_monitor()
                
                # Close connection
                self._close_connection()
                
                self.state = ConnectionState.DISCONNECTED
                self.connection_time = None
                
                if self.on_disconnected:
                    self.on_disconnected()
                
                self.logger.info("IBKR connection closed")
                return True
                
            except Exception as e:
                self.logger.error(f"Disconnect error: {e}")
                return False
    
    def is_connected(self) -> bool:
        """Check if connection is active."""
        return self.state == ConnectionState.CONNECTED
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get comprehensive connection status."""
        
        uptime = None
        if self.connection_time:
            uptime = str(datetime.now() - self.connection_
            
            
               uptime = str(datetime.now() - self.connection_time)
        
        return {
            'state': self.state.value,
            'connected': self.is_connected(),
            'host': self.config.host,
            'port': self.config.port,
            'client_id': self.config.client_id,
            'connection_time': self.connection_time,
            'uptime': uptime,
            'last_error': self.last_error,
            'reconnect_attempts': self.reconnect_attempts,
            'last_heartbeat': self._last_heartbeat
        }
    
    def _establish_connection(self) -> bool:
        """Establish actual connection to IBKR."""
        try:
            # Initialize IBKR client
            from ib_async import IB, util
            
            self.ib = IB()
            
            # Connect with timeout
            self.ib.connect(
                host=self.config.host,
                port=self.config.port,
                clientId=self.config.client_id,
                timeout=self.config.timeout
            )
            
            # Verify connection
            if self.ib.isConnected():
                self.logger.info(f"Connected with client ID {self.config.client_id}")
                return True
            else:
                self.logger.error("Connection verification failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Connection establishment failed: {e}")
            return False
    
    def _close_connection(self) -> None:
        """Close IBKR connection."""
        try:
            if hasattr(self, 'ib') and self.ib.isConnected():
                self.ib.disconnect()
        except Exception as e:
            self.logger.error(f"Error closing connection: {e}")
    
    def _start_heartbeat_monitor(self) -> None:
        """Start heartbeat monitoring thread."""
        if self._heartbeat_thread is None or not self._heartbeat_thread.is_alive():
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_worker,
                name="IBKR_Heartbeat",
                daemon=True
            )
            self._heartbeat_thread.start()
    
    def _stop_heartbeat_monitor(self) -> None:
        """Stop heartbeat monitoring."""
        # Heartbeat thread will stop when connection state changes
        pass
    
    def _heartbeat_worker(self) -> None:
        """Heartbeat monitoring worker thread."""
        while self.state == ConnectionState.CONNECTED:
            try:
                # Send heartbeat request
                if hasattr(self, 'ib') and self.ib.isConnected():
                    # Request account info as heartbeat
                    accounts = self.ib.managedAccounts()
                    if accounts:
                        self._last_heartbeat = datetime.now()
                    else:
                        self.logger.warning("Heartbeat failed: No account response")
                        self._handle_connection_loss()
                        break
                else:
                    self.logger.warning("Connection lost during heartbeat")
                    self._handle_connection_loss()
                    break
                    
            except Exception as e:
                self.logger.warning(f"Heartbeat error: {e}")
                self._handle_connection_loss()
                break
            
            time.sleep(self._heartbeat_interval)
    
    def _handle_connection_loss(self) -> None:
        """Handle connection loss and attempt reconnection."""
        self.logger.warning("Connection loss detected")
        
        with self._connection_lock:
            if self.state == ConnectionState.CONNECTED:
                self.state = ConnectionState.ERROR
                
                if self.on_disconnected:
                    self.on_disconnected()
                
                # Attempt reconnection if enabled
                if self.config.auto_reconnect:
                    self._attempt_reconnection()
    
    def _attempt_reconnection(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        if self.reconnect_attempts >= self.config.max_reconnect_attempts:
            self.logger.error("Max reconnection attempts exceeded")
            return
        
        self.reconnect_attempts += 1
        delay = self.config.reconnect_delay * (2 ** (self.reconnect_attempts - 1))
        
        self.logger.info(f"Attempting reconnection {self.reconnect_attempts}/{self.config.max_reconnect_attempts} in {delay}s")
        
        time.sleep(delay)
        
        if self.connect():
            self.reconnect_attempts = 0
            self.logger.info("Reconnection successful")
        else:
            self.logger.warning(f"Reconnection attempt {self.reconnect_attempts} failed")
            
            # Schedule next attempt
            threading.Timer(1.0, self._attempt_reconnection).start()
```

### Client ID Management

```python
class IBKRClientManager:
    """Manage IBKR client IDs to avoid conflicts."""
    
    CLIENT_ID_RANGES = {
        'main_system': (1, 10),
        'strategies': (11, 50),
        'data_feeds': (51, 80),
        'testing': (81, 99),
        'paper_trading': (100, 150)
    }
    
    def __init__(self):
        self._allocated_ids: Dict[str, int] = {}
        self._id_lock = threading.Lock()
        
    def allocate_client_id(self, component_name: str, category: str = 'strategies') -> int:
        """Allocate unique client ID for component."""
        
        with self._id_lock:
            if component_name in self._allocated_ids:
                return self._allocated_ids[component_name]
            
            if category not in self.CLIENT_ID_RANGES:
                raise ValueError(f"Invalid category: {category}")
            
            start_id, end_id = self.CLIENT_ID_RANGES[category]
            allocated_ids = set(self._allocated_ids.values())
            
            # Find next available ID in range
            for client_id in range(start_id, end_id + 1):
                if client_id not in allocated_ids:
                    self._allocated_ids[component_name] = client_id
                    return client_id
            
            raise RuntimeError(f"No available client IDs in category {category}")
    
    def release_client_id(self, component_name: str) -> bool:
        """Release client ID for reuse."""
        with self._id_lock:
            if component_name in self._allocated_ids:
                del self._allocated_ids[component_name]
                return True
            return False
    
    def get_allocated_ids(self) -> Dict[str, int]:
        """Get all currently allocated client IDs."""
        return self._allocated_ids.copy()
```

## Order Management Standards

### Order Validation and Execution

```python
from typing import Union
from decimal import Decimal

@dataclass
class IBKROrder:
    """Standardized IBKR order structure."""
    symbol: str
    action: str  # BUY, SELL
    quantity: int
    order_type: str  # MKT, LMT, STP, etc.
    limit_price: Optional[Decimal] = None
    aux_price: Optional[Decimal] = None  # Stop price for stop orders
    time_in_force: str = "DAY"  # DAY, GTC, IOC, FOK
    account: Optional[str] = None
    
    # Options-specific fields
    strike: Optional[Decimal] = None
    expiry: Optional[str] = None  # YYYYMMDD format
    option_type: Optional[str] = None  # C or P
    
    # Advanced order fields
    parent_id: Optional[int] = None
    oca_group: Optional[str] = None
    trail_stop_price: Optional[Decimal] = None
    
    def __post_init__(self):
        """Validate order fields."""
        if self.action not in ['BUY', 'SELL']:
            raise ValueError(f"Invalid action: {self.action}")
        
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        if self.order_type == 'LMT' and self.limit_price is None:
            raise ValueError("Limit price required for limit orders")

class IBKROrderManager:
    """Manage IBKR order lifecycle with comprehensive validation."""
    
    def __init__(self, connection_manager: IBKRConnectionManager):
        self.connection_manager = connection_manager
        self.pending_orders: Dict[int, IBKROrder] = {}
        self.order_history: List[Dict[str, Any]] = []
        self.logger = SpyderLogger.get_logger("IBKROrderManager")
        
    def submit_order(self, order: IBKROrder) -> Optional[int]:
        """Submit order to IBKR with comprehensive validation."""
        
        try:
            # Pre-submission validation
            validation_result = self._validate_order(order)
            if not validation_result['valid']:
                self.logger.error(f"Order validation failed: {validation_result['errors']}")
                return None
            
            # Check connection
            if not self.connection_manager.is_connected():
                self.logger.error("Cannot submit order: No IBKR connection")
                return None
            
            # Create IBKR contract and order objects
            contract = self._create_contract(order)
            ib_order = self._create_ib_order(order)
            
            # Submit order
            trade = self.connection_manager.ib.placeOrder(contract, ib_order)
            
            if trade and trade.order.orderId:
                order_id = trade.order.orderId
                self.pending_orders[order_id] = order
                
                self.logger.info(f"Order submitted successfully: {order_id}")
                
                # Record order submission
                self._record_order_event(order_id, "SUBMITTED", order)
                
                return order_id
            else:
                self.logger.error("Order submission failed: No order ID returned")
                return None
                
        except Exception as e:
            self.logger.error(f"Order submission error: {e}")
            return None
    
    def cancel_order(self, order_id: int) -> bool:
        """Cancel pending order."""
        
        try:
            if order_id not in self.pending_orders:
                self.logger.warning(f"Order {order_id} not found in pending orders")
                return False
            
            # Cancel order via IBKR
            self.connection_manager.ib.cancelOrder(order_id)
            
            self.logger.info(f"Cancel request sent for order {order_id}")
            
            # Record cancellation attempt
            self._record_order_event(order_id, "CANCEL_REQUESTED", None)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Order cancellation error: {e}")
            return False
    
    def modify_order(self, order_id: int, modifications: Dict[str, Any]) -> bool:
        """Modify existing order."""
        
        try:
            if order_id not in self.pending_orders:
                self.logger.error(f"Order {order_id} not found")
                return False
            
            original_order = self.pending_orders[order_id]
            
            # Create modified order
            modified_order = self._apply_modifications(original_order, modifications)
            
            # Validate modified order
            validation_result = self._validate_order(modified_order)
            if not validation_result['valid']:
                self.logger.error(f"Modified order validation failed: {validation_result['errors']}")
                return False
            
            # Submit modification to IBKR
            contract = self._create_contract(modified_order)
            ib_order = self._create_ib_order(modified_order)
            ib_order.orderId = order_id  # Keep same order ID
            
            trade = self.connection_manager.ib.placeOrder(contract, ib_order)
            
            if trade:
                # Update pending order
                self.pending_orders[order_id] = modified_order
                
                self.logger.info(f"Order {order_id} modified successfully")
                self._record_order_event(order_id, "MODIFIED", modified_order)
                
                return True
            else:
                self.logger.error(f"Order modification failed for {order_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Order modification error: {e}")
            return False
    
    def _validate_order(self, order: IBKROrder) -> Dict[str, Any]:
        """Comprehensive order validation."""
        
        errors = []
        
        # Basic validation
        if not order.symbol:
            errors.append("Symbol is required")
        
        if order.quantity <= 0:
            errors.append("Quantity must be positive")
        
        # Order type specific validation
        if order.order_type == 'LMT':
            if order.limit_price is None or order.limit_price <= 0:
                errors.append("Valid limit price required for limit orders")
        
        elif order.order_type == 'STP':
            if order.aux_price is None or order.aux_price <= 0:
                errors.append("Valid stop price required for stop orders")
        
        # Options validation
        if order.strike is not None:  # Options order
            if not order.expiry:
                errors.append("Expiry required for options orders")
            
            if not order.option_type or order.option_type not in ['C', 'P']:
                errors.append("Valid option type (C or P) required")
            
            if order.strike <= 0:
                errors.append("Strike price must be positive")
        
        # Time in force validation
        valid_tif = ['DAY', 'GTC', 'IOC', 'FOK', 'OPG', 'DTC']
        if order.time_in_force not in valid_tif:
            errors.append(f"Invalid time in force: {order.time_in_force}")
        
        # Market hours validation
        if not self._is_valid_trading_time(order):
            errors.append("Order submitted outside valid trading hours")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _create_contract(self, order: IBKROrder):
        """Create IBKR contract object from order."""
        from ib_async import Stock, Option, Contract
        
        if order.strike is not None:  # Options contract
            contract = Option(
                symbol=order.symbol,
                lastTradeDateOrContractMonth=order.expiry,
                strike=float(order.strike),
                right=order.option_type,
                exchange='SMART',
                currency='USD'
            )
        else:  # Stock contract
            contract = Stock(
                symbol=order.symbol,
                exchange='SMART',
                currency='USD'
            )
        
        return contract
    
    def _create_ib_order(self, order: IBKROrder):
        """Create IBKR order object."""
        from ib_async import Order
        
        ib_order = Order(
            action=order.action,
            totalQuantity=order.quantity,
            orderType=order.order_type,
            tif=order.time_in_force
        )
        
        # Set price fields
        if order.limit_price is not None:
            ib_order.lmtPrice = float(order.limit_price)
        
        if order.aux_price is not None:
            ib_order.auxPrice = float(order.aux_price)
        
        # Set account if specified
        if order.account:
            ib_order.account = order.account
        
        # Advanced order properties
        if order.parent_id:
            ib_order.parentId = order.parent_id
        
        if order.oca_group:
            ib_order.ocaGroup = order.oca_group
        
        return ib_order
    
    def _record_order_event(self, order_id: int, event_type: str, order: Optional[IBKROrder]) -> None:
        """Record order event for audit trail."""
        
        event = {
            'timestamp': datetime.now(),
            'order_id': order_id,
            'event_type': event_type,
            'order_data': asdict(order) if order else None
        }
        
        self.order_history.append(event)
        
        # Keep history size manageable
        if len(self.order_history) > 10000:
            self.order_history = self.order_history[-5000:]
```

### Market Data Management

```python
class IBKRMarketDataManager:
    """Manage IBKR market data subscriptions and processing."""
    
    def __init__(self, connection_manager: IBKRConnectionManager):
        self.connection_manager = connection_manager
        self.subscriptions: Dict[str, Dict[str, Any]] = {}
        self.data_callbacks: Dict[str, List[Callable]] = {}
        self.logger = SpyderLogger.get_logger("IBKRMarketData")
        
    def subscribe_ticker(self, symbol: str, callback: Callable[[Dict[str, Any]], None]) -> bool:
        """Subscribe to real-time ticker data."""
        
        try:
            if not self.connection_manager.is_connected():
                self.logger.error("Cannot subscribe: No IBKR connection")
                return False
            
            # Create contract
            from ib_async import Stock
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Request market data
            ticker = self.connection_manager.ib.reqMktData(
                contract,
                genericTickList='',
                snapshot=False,
                regulatorySnapshot=False
            )
            
            # Store subscription
            self.subscriptions[symbol] = {
                'contract': contract,
                'ticker': ticker,
                'subscription_time': datetime.now()
            }
            
            # Register callback
            if symbol not in self.data_callbacks:
                self.data_callbacks[symbol] = []
            self.data_callbacks[symbol].append(callback)
            
            # Set up data handler
            ticker.updateEvent += self._create_data_handler(symbol)
            
            self.logger.info(f"Subscribed to ticker data for {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ticker subscription failed for {symbol}: {e}")
            return False
    
    def subscribe_option_chain(self, symbol: str, expiry: str, callback: Callable[[Dict[str, Any]], None]) -> bool:
        """Subscribe to options chain data."""
        
        try:
            if not self.connection_manager.is_connected():
                self.logger.error("Cannot subscribe: No IBKR connection")
                return False
            
            # Get underlying contract
            from ib_async import Stock
            underlying = Stock(symbol, 'SMART', 'USD')
            
            # Qualify contract
            self.connection_manager.ib.qualifyContracts(underlying)
            
            # Request option chains
            chains = self.connection_manager.ib.reqSecDefOptParams(
                underlying.symbol,
                '',
                underlying.secType,
                underlying.conId
            )
            
            # Process chains for specified expiry
            option_contracts = []
            for chain in chains:
                if expiry in chain.expirations:
                    for strike in chain.strikes:
                        # Create call and put contracts
                        call_contract = Option(
                            symbol, expiry, strike, 'C', 'SMART', currency='USD'
                        )
                        put_contract = Option(
                            symbol, expiry, strike, 'P', 'SMART', currency='USD'
                        )
                        option_contracts.extend([call_contract, put_contract])
            
            # Subscribe to option data
            chain_key = f"{symbol}_{expiry}"
            tickers = []
            
            for contract in option_contracts[:50]:  # Limit to prevent overload
                ticker = self.connection_manager.ib.reqMktData(contract)
                tickers.append(ticker)
                ticker.updateEvent += self._create_option_data_handler(symbol, expiry)
            
            # Store subscription
            self.subscriptions[chain_key] = {
                'contracts': option_contracts,
                'tickers': tickers,
                'subscription_time': datetime.now()
            }
            
            # Register callback
            if chain_key not in self.data_callbacks:
                self.data_callbacks[chain_key] = []
            self.data_callbacks[chain_key].append(callback)
            
            self.logger.info(f"Subscribed to option chain for {symbol} {expiry}")
            return True
            
        except Exception as e:
            self.logger.error(f"Option chain subscription failed: {e}")
            return False
    
    def _create_data_handler(self, symbol: str) -> Callable:
        """Create data update handler for symbol."""
        
        def handle_ticker_update(ticker):
            try:
                # Extract ticker data
                data = {
                    'symbol': symbol,
                    'timestamp': datetime.now(),
                    'bid': float(ticker.bid) if ticker.bid else None,
                    'ask': float(ticker.ask) if ticker.ask else None,
                    'last': float(ticker.last) if ticker.last else None,
                    'volume': int(ticker.volume) if ticker.volume else 0,
                    'high': float(ticker.high) if ticker.high else None,
                    'low': float(ticker.low) if ticker.low else None,
                    'close': float(ticker.close) if ticker.close else None
                }
                
                # Call registered callbacks
                for callback in self.data_callbacks.get(symbol, []):
                    try:
                        callback(data)
                    except Exception as e:
                        self.logger.error(f"Callback error for {symbol}: {e}")
                        
            except Exception as e:
                self.logger.error(f"Data handler error for {symbol}: {e}")
        
        return handle_ticker_update
    
    def _create_option_data_handler(self, symbol: str, expiry: str) -> Callable:
        """Create option data update handler."""
        
        def handle_option_update(ticker):
            try:
                contract = ticker.contract
                chain_key = f"{symbol}_{expiry}"
                
                # Extract option data
                data = {
                    'symbol': symbol,
                    'expiry': expiry,
                    'strike': contract.strike,
                    'right': contract.right,
                    'timestamp': datetime.now(),
                    'bid': float(ticker.bid) if ticker.bid else None,
                    'ask': float(ticker.ask) if ticker.ask else None,
                    'last': float(ticker.last) if ticker.last else None,
                    'volume': int(ticker.volume) if ticker.volume else 0,
                    'implied_volatility': float(ticker.impliedVolatility) if ticker.impliedVolatility else None,
                    'delta': float(ticker.delta) if ticker.delta else None,
                    'gamma': float(ticker.gamma) if ticker.gamma else None,
                    'theta': float(ticker.theta) if ticker.theta else None,
                    'vega': float(ticker.vega) if ticker.vega else None
                }
                
                # Call registered callbacks
                for callback in self.data_callbacks.get(chain_key, []):
                    try:
                        callback(data)
                    except Exception as e:
                        self.logger.error(f"Option callback error: {e}")
                        
            except Exception as e:
                self.logger.error(f"Option data handler error: {e}")
        
        return handle_option_update
    
    def unsubscribe(self, subscription_key: str) -> bool:
        """Unsubscribe from market data."""
        
        try:
            if subscription_key not in self.subscriptions:
                self.logger.warning(f"Subscription not found: {subscription_key}")
                return False
            
            subscription = self.subscriptions[subscription_key]
            
            # Cancel market data subscriptions
            if 'ticker' in subscription:
                self.connection_manager.ib.cancelMktData(subscription['ticker'].contract)
            
            if 'tickers' in subscription:
                for ticker in subscription['tickers']:
                    self.connection_manager.ib.cancelMktData(ticker.contract)
            
            # Remove subscription
            del self.subscriptions[subscription_key]
            
            # Remove callbacks
            if subscription_key in self.data_callbacks:
                del self.data_callbacks[subscription_key]
            
            self.logger.info(f"Unsubscribed from {subscription_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Unsubscription error: {e}")
            return False
```

## Error Handling Standards

### IBKR Error Code Management

```python
class IBKRErrorHandler:
    """Comprehensive IBKR error handling and recovery."""
    
    # Critical errors that require immediate attention
    CRITICAL_ERRORS = {
        502: "Couldn't connect to TWS",
        504: "Not connected",
        1100: "Connectivity between IB and TWS has been lost",
        1101: "Connectivity between IB and TWS has been restored - data maintained",
        1102: "Connectivity between IB and TWS has been restored - data lost",
        2104: "Market data farm connection is broken",
        2106: "A historical data farm is disconnected"
    }
    
    # Recoverable errors that can be handled automatically
    RECOVERABLE_ERRORS = {
        200: "No security definition found",
        201: "Order rejected - reason",
        202: "Order cancelled",
        399: "Order message error",
        434: "Order size does not conform to market rule",
        201: "Order rejected"
    }
    
    # Rate limiting errors
    RATE_LIMIT_ERRORS = {
        162: "Historical Market Data Service error",
        200: "No security definition found for request",
        162: "HMDS query returned no data"
    }
    
    def __init__(self):
        self.error_counts: Dict[int, int] = {}
        self.last_errors: Dict[int, datetime] = {}
        self.logger = SpyderLogger.get_logger("IBKRErrorHandler")
        
    def handle_error(self, error_code: int, error_msg: str, req_id: int = -1) -> str:
        """Handle IBKR error with appropriate response."""
        
        # Update error tracking
        self.error_counts[error_code] = self.error_counts.get(error_code, 0) + 1
        self.last_errors[error_code] = datetime.now()
        
        # Log error
        self.logger.error(f"IBKR Error {error_code}: {error_msg} (ReqId: {req_id})")
        
        # Determine response strategy
        if error_code in self.CRITICAL_ERRORS:
            return self._handle_critical_error(error_code, error_msg)
        elif error_code in self.RECOVERABLE_ERRORS:
            return self._handle_recoverable_error(error_code, error_msg, req_id)
        elif error_code in self.RATE_LIMIT_ERRORS:
            return self._handle_rate_limit_error(error_code, error_msg)
        else:
            return self._handle_unknown_error(error_code, error_msg)
    
    def _handle_critical_error(self, error_code: int, error_msg: str) -> str:
        """Handle critical errors that affect system operation."""
        
        if error_code in [502, 504, 1100]:
            # Connection lost - trigger reconnection
            self.logger.critical(f"Connection error: {error_msg}")
            return "RECONNECT_REQUIRED"
        
        elif error_code in [2104, 2106]:
            # Market data farm issues
            self.logger.critical(f"Market data issue: {error_msg}")
            return "DATA_FEED_ISSUE"
        
        else:
            self.logger.critical(f"Unhandled critical error: {error_code}")
            return "SYSTEM_HALT_REQUIRED"
    
    def _handle_recoverable_error(self, error_code: int, error_msg: str, req_id: int) -> str:
        """Handle recoverable errors."""
        
        if error_code in [200, 201, 202]:
            # Order-related errors
            self.logger.warning(f"Order error: {error_msg}")
            return "ORDER_FAILED"
        
        elif error_code == 434:
            # Invalid order size
            self.logger.warning(f"Order size error: {error_msg}")
            return "INVALID_ORDER_SIZE"
        
        else:
            self.logger.warning(f"Recoverable error: {error_code} - {error_msg}")
            return "RETRY_ALLOWED"
    
    def _handle_rate_limit_error(self, error_code: int, error_msg: str) -> str:
        """Handle rate limiting errors."""
        
        self.logger.warning(f"Rate limit error: {error_msg}")
        
        # Implement exponential backoff
        error_count = self.error_counts.get(error_code, 0)
        backoff_time = min(60, 2 ** error_count)  # Max 60 seconds
        
        self.logger.info(f"Backing off for {backoff_time} seconds")
        
        return f"BACKOFF_{backoff_time}"
    
    def _handle_unknown_error(self, error_code: int, error_msg: str) -> str:
        """Handle unknown or undocumented errors."""
        
        self.logger.error(f"Unknown error: {error_code} - {error_msg}")
        
        # If error occurs frequently, treat as critical
        if self.error_counts.get(error_code, 0) > 5:
            return "ESCALATE_TO_CRITICAL"
        else:
            return "MONITOR_AND_LOG"
```

## Performance and Rate Limiting

### API Rate Management

```python
class IBKRRateLimiter:
    """Manage IBKR API rate limits to prevent violations."""
    
    def __init__(self):
        # IBKR rate limits (conservative estimates)
        self.limits = {
            'market_data_requests': {'limit': 100, 'window': 60},  # 100 per minute
            'historical_data': {'limit': 60, 'window': 600},       # 60 per 10 minutes
            'order_submissions': {'limit': 50, 'window': 1},        # 50 per second
            'account_requests': {'limit': 50, 'window': 60}         # 50 per minute
        }
        
        self.request_history: Dict[str, List[datetime]] = {
            key: [] for key in self.limits.keys()
        }
        
        self.logger = SpyderLogger.get_logger("IBKRRateLimit")
    
    def can_make_request(self, request_type: str) -> bool:
        """Check if request can be made without violating rate limits."""
        
        if request_type not in self.limits:
            self.logger.warning(f"Unknown request type: {request_type}")
            return True
        
        now = datetime.now()
        limit_config = self.limits[request_type]
        window_start = now - timedelta(seconds=limit_config['window'])
        
        # Clean old requests
        self.request_history[request_type] = [
            req_time for req_time in self.request_history[request_type]
            if req_time > window_start
        ]
        
        # Check if under limit
        current_count = len(self.request_history[request_type])
        return current_count
            
            
