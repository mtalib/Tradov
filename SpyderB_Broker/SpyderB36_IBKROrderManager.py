#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB36_IBKROrderManager.py
Purpose: Order management using IBKR Client Portal Web API

Author: SPYDER Trading System
Year Created: 2025
Last Updated: 2025-10-22 Time: 07:58:00

Module Description:
    This module handles all order operations with the IBKR Client Portal Web API.
    It provides a unified interface for placing, canceling, modifying, and tracking
    orders while handling the complexities of IBKR's order format and validation.
    This module complements the existing SpyderB02_OrderManager.py by providing
    Web API functionality as an alternative to the Connect API.

Module Constants:
    DEFAULT_ORDER_TIMEOUT (int): Default order timeout in seconds (default: 10)
    RETRY_ATTEMPTS (int): Number of retry attempts for failed requests (default: 3)
    RETRY_DELAY (float): Delay between retry attempts in seconds (default: 1.0)
    ORDER_CACHE_DURATION (int): Order cache duration in seconds (default: 300)
    MAX_ORDER_HISTORY (int): Maximum number of order history records (default: 1000)

Change Log:
    2025-10-22 (v1.0.0):
        - Initial module creation from IBKR Client Portal Web API order_manager.py
        - Renumbered to SpyderB36 following project naming convention
        - Updated module header to match Spyder standards
        - Reformatted code according to PEP 8 guidelines
        - Added comprehensive type annotations
        - Enhanced error handling and logging integration
        - Added thread safety improvements
        - Integrated with Spyder utility modules

    2025-10-20 (v0.9.0):
        - Original order_manager.py implementation
        - Basic IBKR Web API order management functionality
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import json
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union, TYPE_CHECKING
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
import requests

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Import session manager
if TYPE_CHECKING:
    from .SpyderB32_IBKRSessionManager import SessionManager, AuthStatus

try:
    from .SpyderB32_IBKRSessionManager import SessionManager, AuthStatus
except ImportError:
    # Fallback for testing
    SessionManager = None
    AuthStatus = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_ORDER_TIMEOUT = 10
RETRY_ATTEMPTS = 3
RETRY_DELAY = 1.0
ORDER_CACHE_DURATION = 300  # 5 minutes
MAX_ORDER_HISTORY = 1000

# ==============================================================================
# ENUMS
# ==============================================================================


class OrderType(Enum):
    """Order type enumeration."""
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STPLMT"
    MARKET_ON_CLOSE = "MOC"
    LIMIT_ON_CLOSE = "LOC"
    MARKET_ON_OPEN = "MOO"
    LIMIT_ON_OPEN = "LOO"


class OrderSide(Enum):
    """Order side enumeration."""
    BUY = "BUY"
    SELL = "SELL"
    SELL_SHORT = "SELL_SHORT"


class OrderStatus(Enum):
    """Order status enumeration."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PRESUBMITTED = "presubmitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    INACTIVE = "inactive"


class TimeInForce(Enum):
    """Time in force enumeration."""
    DAY = "DAY"
    GOOD_TILL_CANCEL = "GTC"
    AT_THE_OPENING = "OPG"
    IMMEDIATE_OR_CANCEL = "IOC"
    FILL_OR_KILL = "FOK"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class OrderRequest:
    """Order request data structure."""
    account_id: str
    conid: int
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    outside_rth: bool = False
    order_ref: Optional[str] = None

    def to_ibkr_format(self) -> Dict[str, Any]:
        """Convert to IBKR API format."""
        order = {
            "conid": self.conid,
            "orderType": self.order_type.value,
            "side": self.side.value,
            "quantity": self.quantity,
            "tif": self.time_in_force.value
        }

        if self.limit_price is not None:
            order["price"] = self.limit_price

        if self.stop_price is not None:
            order["auxPrice"] = self.stop_price

        if self.outside_rth:
            order["outsideRTH"] = True

        if self.order_ref:
            order["orderRef"] = self.order_ref

        return order


@dataclass
class Order:
    """Order information."""
    order_id: str
    account_id: str
    conid: int
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    avg_fill_price: Optional[float] = None
    commission: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    order_ref: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'order_id': self.order_id,
            'account_id': self.account_id,
            'conid': self.conid,
            'symbol': self.symbol,
            'side': self.side.value,
            'order_type': self.order_type.value,
            'quantity': self.quantity,
            'limit_price': self.limit_price,
            'stop_price': self.stop_price,
            'time_in_force': self.time_in_force.value,
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'avg_fill_price': self.avg_fill_price,
            'commission': self.commission,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'order_ref': self.order_ref
        }


@dataclass
class OrderConfig:
    """Configuration for order management."""
    default_timeout: int = DEFAULT_ORDER_TIMEOUT
    retry_attempts: int = RETRY_ATTEMPTS
    retry_delay: float = RETRY_DELAY
    validate_orders: bool = True
    order_cache_duration: int = ORDER_CACHE_DURATION
    max_order_history: int = MAX_ORDER_HISTORY


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class OrderManager:
    """
    Manages order operations with IBKR Client Portal API.

    This class provides a high-level interface for all order operations
    while handling the complexities of IBKR's API requirements.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling system
        session_manager: SessionManager instance for authentication
        config: Order configuration
        api_base: Base URL for IBKR API
        _order_cache: Cache for order information
        _order_cache_lock: Thread lock for order cache
        _lock: Thread safety lock
        _stats: Order management statistics
        _order_callbacks: Callback functions for order updates
        _error_callbacks: Callback functions for error events
    """

    def __init__(self, session_manager, config: Optional[OrderConfig] = None):
        """
        Initialize Order Manager.

        Args:
            session_manager: SessionManager instance
            config: Order configuration
        """
        if session_manager is None:
            raise ValueError("SessionManager is required")

        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # Session management
        self.session_manager = session_manager
        self.config = config or OrderConfig()

        # API endpoints
        self.api_base = getattr(self.session_manager, 'api_base', 'https://localhost:5000/v1/api')

        # Order cache
        self._order_cache: Dict[str, Order] = {}
        self._order_cache_lock = threading.RLock()

        # Thread safety lock
        self._lock = threading.RLock()

        # Statistics
        self._stats = {
            'orders_placed': 0,
            'orders_cancelled': 0,
            'orders_modified': 0,
            'order_errors': 0,
            'validations': 0,
            'validation_failures': 0,
            'last_order_time': None,
            'last_error_time': None
        }

        # Event callbacks
        self._order_callbacks: List[Callable[[Order], None]] = []
        self._error_callbacks: List[Callable[[str, Dict], None]] = []

        self.logger.info("OrderManager initialized")

    # ==========================================================================
    # ORDER OPERATIONS
    # ==========================================================================

    def place_order(self, order_request: OrderRequest) -> Optional[str]:
        """
        Place an order with IBKR.

        Args:
            order_request: Order request details

        Returns:
            Order ID if successful, None otherwise
        """
        try:
            # Check authentication
            if not getattr(self.session_manager, 'is_authenticated', lambda: False)():
                self.logger.error("Cannot place order: Not authenticated")
                self._notify_error("AUTH_ERROR", {"message": "Not authenticated"})
                return None

            # Validate order if enabled
            if self.config.validate_orders:
                validation_result = self.validate_order(order_request)
                if not validation_result.get('valid', False):
                    self.logger.error(f"Order validation failed: {validation_result}")
                    self._notify_error("VALIDATION_ERROR", validation_result)
                    return None

            # Prepare order payload
            order_data = order_request.to_ibkr_format()
            payload = {"orders": [order_data]}

            # Make API request
            endpoint = f"/iserver/account/{order_request.account_id}/orders"
            response = self._make_request('POST', endpoint, json=payload)

            if not response:
                self.logger.error("Failed to place order: No response")
                with self._lock:
                    self._stats['order_errors'] += 1
                    self._stats['last_error_time'] = datetime.now()
                return None

            result = response.json()

            # Handle response
            if isinstance(result, list) and len(result) > 0:
                order_id = result[0].get('order_id')
                if order_id:
                    # Create order object
                    order = Order(
                        order_id=order_id,
                        account_id=order_request.account_id,
                        conid=order_request.conid,
                        symbol=order_request.symbol,
                        side=order_request.side,
                        order_type=order_request.order_type,
                        quantity=order_request.quantity,
                        limit_price=order_request.limit_price,
                        stop_price=order_request.stop_price,
                        time_in_force=order_request.time_in_force,
                        status=OrderStatus.SUBMITTED,
                        order_ref=order_request.order_ref
                    )

                    # Cache order
                    with self._order_cache_lock:
                        self._order_cache[order_id] = order

                    # Update statistics
                    with self._lock:
                        self._stats['orders_placed'] += 1
                        self._stats['last_order_time'] = datetime.now()

                    # Notify callbacks
                    self._notify_order_update(order)

                    self.logger.info(f"Order placed successfully: {order_id}")
                    return order_id
                else:
                    # Handle error response
                    error_msg = result[0].get('error', 'Unknown error')
                    self.logger.error(f"Order placement failed: {error_msg}")
                    self._notify_error("PLACE_ERROR", {"message": error_msg, "response": result})

            return None

        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            self.error_handler.handle_error(e, "place_order")

            with self._lock:
                self._stats['order_errors'] += 1
                self._stats['last_error_time'] = datetime.now()
            self._notify_error("SYSTEM_ERROR", {"message": str(e)})
            return None

    def cancel_order(self, order_id: str, account_id: str) -> bool:
        """
        Cancel an existing order.

        Args:
            order_id: Order ID to cancel
            account_id: Account ID

        Returns:
            True if cancellation successful
        """
        try:
            # Check authentication
            if not getattr(self.session_manager, 'is_authenticated', lambda: False)():
                self.logger.error("Cannot cancel order: Not authenticated")
                return False

            # Make API request
            endpoint = f"/iserver/account/{account_id}/orders/{order_id}"
            response = self._make_request('DELETE', endpoint)

            if response and response.status_code == 200:
                # Update cached order
                with self._order_cache_lock:
                    if order_id in self._order_cache:
                        self._order_cache[order_id].status = OrderStatus.CANCELLED
                        self._order_cache[order_id].updated_at = datetime.now()
                        self._notify_order_update(self._order_cache[order_id])

                # Update statistics
                with self._lock:
                    self._stats['orders_cancelled'] += 1

                self.logger.info(f"Order cancelled successfully: {order_id}")
                return True
            else:
                self.logger.error(f"Failed to cancel order: {order_id}")
                return False

        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            self.error_handler.handle_error(e, "cancel_order")
            return False

    def modify_order(self, order_id: str, modifications: Dict[str, Any], account_id: str) -> bool:
        """
        Modify an existing order.

        Args:
            order_id: Order ID to modify
            modifications: Order modifications
            account_id: Account ID

        Returns:
            True if modification successful
        """
        try:
            # Check authentication
            if not getattr(self.session_manager, 'is_authenticated', lambda: False)():
                self.logger.error("Cannot modify order: Not authenticated")
                return False

            # Prepare modification payload
            # Note: IBKR uses specific format for order modifications
            endpoint = f"/iserver/account/{account_id}/order"

            # Add order ID to modifications
            modifications['orderId'] = order_id

            response = self._make_request('POST', endpoint, json=modifications)

            if response and response.status_code == 200:
                # Update cached order
                with self._order_cache_lock:
                    if order_id in self._order_cache:
                        order = self._order_cache[order_id]
                        # Update fields based on modifications
                        if 'quantity' in modifications:
                            order.quantity = modifications['quantity']
                        if 'price' in modifications:
                            order.limit_price = modifications['price']
                        if 'auxPrice' in modifications:
                            order.stop_price = modifications['auxPrice']
                        order.updated_at = datetime.now()
                        self._notify_order_update(order)

                # Update statistics
                with self._lock:
                    self._stats['orders_modified'] += 1

                self.logger.info(f"Order modified successfully: {order_id}")
                return True
            else:
                self.logger.error(f"Failed to modify order: {order_id}")
                return False

        except Exception as e:
            self.logger.error(f"Error modifying order {order_id}: {e}")
            self.error_handler.handle_error(e, "modify_order")
            return False

    # ==========================================================================
    # ORDER QUERIES
    # ==========================================================================

    def get_order_status(self, order_id: str, account_id: str) -> Optional[Order]:
        """
        Get the current status of an order.

        Args:
            order_id: Order ID
            account_id: Account ID

        Returns:
            Order object if found
        """
        try:
            # Check cache first
            with self._order_cache_lock:
                if order_id in self._order_cache:
                    cached_order = self._order_cache[order_id]
                    # Return if cache is fresh
                    if cached_order.updated_at and (datetime.now() - cached_order.updated_at).seconds < self.config.order_cache_duration:
                        return cached_order

            # Check authentication
            if not getattr(self.session_manager, 'is_authenticated', lambda: False)():
                return None

            # Fetch from API
            endpoint = f"/iserver/account/{account_id}/order/{order_id}"
            response = self._make_request('GET', endpoint)

            if response:
                data = response.json()
                return self._parse_order_response(data, account_id)

            return None

        except Exception as e:
            self.logger.error(f"Error getting order status {order_id}: {e}")
            self.error_handler.handle_error(e, "get_order_status")
            return None

    def get_open_orders(self, account_id: str) -> List[Order]:
        """
        Get all open orders for an account.

        Args:
            account_id: Account ID

        Returns:
            List of open orders
        """
        try:
            # Check authentication
            if not getattr(self.session_manager, 'is_authenticated', lambda: False)():
                return []

            # Fetch from API
            endpoint = f"/iserver/account/{account_id}/orders"
            response = self._make_request('GET', endpoint)

            if response:
                data = response.json()
                orders = []
                for order_data in data:
                    order = self._parse_order_response(order_data, account_id)
                    if order and order.status not in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
                        orders.append(order)

                return orders

            return []

        except Exception as e:
            self.logger.error(f"Error getting open orders: {e}")
            self.error_handler.handle_error(e, "get_open_orders")
            return []

    def validate_order(self, order_request: OrderRequest) -> Dict[str, Any]:
        """
        Validate an order before submission.

        Args:
            order_request: Order to validate

        Returns:
            Validation result
        """
        try:
            # Check authentication
            if not getattr(self.session_manager, 'is_authenticated', lambda: False)():
                return {"valid": False, "error": "Not authenticated"}

            # Prepare validation payload
            order_data = order_request.to_ibkr_format()
            payload = {"orders": [order_data]}

            # Make validation request
            endpoint = f"/iserver/account/{order_request.account_id}/orders/whatif"
            response = self._make_request('POST', endpoint, json=payload)

            if response:
                result = response.json()

                # Update statistics
                with self._lock:
                    self._stats['validations'] += 1

                # Parse validation result
                if isinstance(result, list) and len(result) > 0:
                    order_result = result[0]
                    if 'error' in order_result:
                        with self._lock:
                            self._stats['validation_failures'] += 1
                        return {"valid": False, "error": order_result['error']}
                    else:
                        return {"valid": True, "result": order_result}

            return {"valid": False, "error": "Validation failed"}

        except Exception as e:
            self.logger.error(f"Error validating order: {e}")
            self.error_handler.handle_error(e, "validate_order")

            with self._lock:
                self._stats['validation_failures'] += 1
            return {"valid": False, "error": str(e)}

    def get_order_history(self, account_id: str, days: int = 7) -> List[Order]:
        """
        Get order history for an account.

        Args:
            account_id: Account ID
            days: Number of days of history to retrieve

        Returns:
            List of historical orders
        """
        try:
            # Check authentication
            if not getattr(self.session_manager, 'is_authenticated', lambda: False)():
                return []

            # Calculate date range
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            # Fetch trades (which include executed orders)
            endpoint = f"/iserver/account/{account_id}/trades"
            params = {
                'startTime': start_time.isoformat(),
                'endTime': end_time.isoformat()
            }

            response = self._make_request('GET', endpoint, params=params)

            if response:
                data = response.json()
                orders = []
                for trade_data in data:
                    # Convert trade to order format
                    order = self._parse_trade_to_order(trade_data, account_id)
                    if order:
                        orders.append(order)

                return orders

            return []

        except Exception as e:
            self.logger.error(f"Error getting order history: {e}")
            self.error_handler.handle_error(e, "get_order_history")
            return []

    # ==========================================================================
    # PUBLIC UTILITY METHODS
    # ==========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Get order management statistics."""
        with self._lock:
            return {
                'orders_placed': self._stats['orders_placed'],
                'orders_cancelled': self._stats['orders_cancelled'],
                'orders_modified': self._stats['orders_modified'],
                'order_errors': self._stats['order_errors'],
                'validations': self._stats['validations'],
                'validation_failures': self._stats['validation_failures'],
                'last_order_time': self._stats['last_order_time'].isoformat() if self._stats['last_order_time'] else None,
                'last_error_time': self._stats['last_error_time'].isoformat() if self._stats['last_error_time'] else None,
                'cached_orders': len(self._order_cache)
            }

    def add_order_callback(self, callback: Callable[[Order], None]):
        """Add callback for order updates."""
        self._order_callbacks.append(callback)

    def add_error_callback(self, callback: Callable[[str, Dict], None]):
        """Add callback for error events."""
        self._error_callbacks.append(callback)

    def clear_cache(self):
        """Clear order cache."""
        with self._order_cache_lock:
            self._order_cache.clear()
        self.logger.info("Order cache cleared")

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        """
        Make HTTP request to IBKR API.

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request parameters

        Returns:
            Response object or None
        """
        try:
            url = f"{self.api_base}{endpoint}"
            timeout = self.config.default_timeout

            for attempt in range(self.config.retry_attempts):
                try:
                    session = getattr(self.session_manager, 'session', None)
                    if session is None:
                        raise ValueError("Session not available")

                    if method.upper() == 'GET':
                        response = session.get(url, timeout=timeout, **kwargs)
                    elif method.upper() == 'POST':
                        response = session.post(url, timeout=timeout, **kwargs)
                    elif method.upper() == 'DELETE':
                        response = session.delete(url, timeout=timeout, **kwargs)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")

                    if response.status_code in [200, 201]:
                        return response
                    else:
                        self.logger.warning(f"Request failed: {response.status_code} - {response.text}")

                except requests.exceptions.RequestException as e:
                    self.logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                    if attempt < self.config.retry_attempts - 1:
                        time.sleep(self.config.retry_delay)
                    else:
                        raise e

            return None

        except Exception as e:
            self.logger.error(f"Error making {method} request to {endpoint}: {e}")
            self.error_handler.handle_error(e, "_make_request")
            return None

    def _parse_order_response(self, data: Dict, account_id: str) -> Optional[Order]:
        """Parse order response from IBKR API."""
        try:
            order = Order(
                order_id=data.get('orderId', ''),
                account_id=account_id,
                conid=data.get('conid', 0),
                symbol=data.get('ticker', ''),
                side=OrderSide(data.get('side', 'BUY')),
                order_type=OrderType(data.get('orderType', 'MKT')),
                quantity=float(data.get('totalSize', 0)),
                limit_price=data.get('price'),
                stop_price=data.get('auxPrice'),
                status=OrderStatus(data.get('status', 'pending').lower()),
                filled_quantity=float(data.get('filledQuantity', 0)),
                avg_fill_price=data.get('avgPrice'),
                order_ref=data.get('orderRef')
            )

            # Update timestamp
            if data.get('lastUpdateTime'):
                order.updated_at = datetime.fromisoformat(data['lastUpdateTime'])

            # Cache order
            with self._order_cache_lock:
                self._order_cache[order.order_id] = order

            return order

        except Exception as e:
            self.logger.error(f"Error parsing order response: {e}")
            self.error_handler.handle_error(e, "_parse_order_response")
            return None

    def _parse_trade_to_order(self, trade_data: Dict, account_id: str) -> Optional[Order]:
        """Parse trade data to order format."""
        try:
            # Convert trade execution to order
            order = Order(
                order_id=trade_data.get('orderId', ''),
                account_id=account_id,
                conid=trade_data.get('conid', 0),
                symbol=trade_data.get('symbol', ''),
                side=OrderSide(trade_data.get('side', 'BUY')),
                order_type=OrderType.LIMIT,  # Default to limit for executed trades
                quantity=float(trade_data.get('quantity', 0)),
                limit_price=trade_data.get('price'),
                filled_quantity=float(trade_data.get('quantity', 0)),
                avg_fill_price=trade_data.get('price'),
                status=OrderStatus.FILLED
            )

            # Set timestamps
            if trade_data.get('time'):
                order.created_at = datetime.fromisoformat(trade_data['time'])
                order.updated_at = datetime.fromisoformat(trade_data['time'])

            return order

        except Exception as e:
            self.logger.error(f"Error parsing trade to order: {e}")
            self.error_handler.handle_error(e, "_parse_trade_to_order")
            return None

    def _notify_order_update(self, order: Order):
        """Notify callbacks of order update."""
        for callback in self._order_callbacks:
            try:
                callback(order)
            except Exception as e:
                self.logger.error(f"Error in order callback: {e}")
                self.error_handler.handle_error(e, "_notify_order_update")

    def _notify_error(self, error_type: str, error_data: Dict):
        """Notify callbacks of error events."""
        for callback in self._error_callbacks:
            try:
                callback(error_type, error_data)
            except Exception as e:
                self.logger.error(f"Error in error callback: {e}")
                self.error_handler.handle_error(e, "_notify_error")


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def create_order_manager(session_manager, **kwargs) -> OrderManager:
    """
    Create an OrderManager instance with configuration.

    Args:
        session_manager: SessionManager instance
        **kwargs: Configuration parameters

    Returns:
        OrderManager instance
    """
    config = OrderConfig(**kwargs)
    return OrderManager(session_manager, config)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Example usage
    import logging
    # from ..session.session_manager import SessionManager
    SessionManager = None  # Placeholder for testing

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    def order_updated(order):
        print(f"Order updated: {order.order_id} - {order.status.value}")

    def error_occurred(error_type, error_data):
        print(f"Error {error_type}: {error_data}")

    # Create session and order managers
    if SessionManager is None:
        print("SessionManager not available - create manually for testing")
        # Create a mock session manager for testing
        from unittest.mock import Mock
        session_manager = Mock()
        session_manager.is_authenticated.return_value = True
        session_manager.api_base = "https://localhost:5000/v1/api"
        session_manager.session = Mock()
    else:
        session_manager = SessionManager()
    order_manager = OrderManager(session_manager)

    order_manager.add_order_callback(order_updated)
    order_manager.add_error_callback(error_occurred)

    try:
        # Start session manager
        session_manager.start()

        # Check authentication
        if session_manager.check_auth_status():
            print("✅ Authenticated")

            # Create sample order
            order_request = OrderRequest(
                account_id="DU1234567",
                conid=756733,  # SPY
                symbol="SPY",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=100,
                limit_price=450.0
            )

            # Validate order
            validation = order_manager.validate_order(order_request)
            print(f"Validation result: {validation}")

            # Place order
            order_id = order_manager.place_order(order_request)
            if order_id:
                print(f"✅ Order placed: {order_id}")

                # Get order status
                status = order_manager.get_order_status(order_id, order_request.account_id)
                if status:
                    print(f"Order status: {status.status.value}")

                # Cancel order
                if order_manager.cancel_order(order_id, order_request.account_id):
                    print(f"✅ Order cancelled: {order_id}")
            else:
                print("❌ Failed to place order")
        else:
            print("❌ Not authenticated. Please login via browser:")
            print("https://localhost:5000")

        # Keep running for demonstration
        time.sleep(30)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        session_manager.stop()