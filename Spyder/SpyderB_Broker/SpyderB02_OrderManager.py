#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB02_OrderManager.py
Purpose: Order management using Connect API

Author: SPYDER Trading System
Year Created: 2025
Last Updated: 2025-10-20 Time: 22:05:00

Module Description:
    This module manages order placement, tracking, and execution through the Connect API.
    It provides a high-level interface for order operations while handling
    order state persistence, and multileg options support. This module
    replaces the IB Gateway/TWS API order management components.

Module Constants:
    DEFAULT_ORDER_TIMEOUT (float): Default order timeout in seconds (default: 30.0)
    MAX_ORDER_ID_LENGTH (int): Maximum length for order IDs (default: 50)
    ORDER_STATE_PERSISTENCE_INTERVAL (int): Interval for saving state in seconds (default: 60)

Change Log:
    2025-10-20 (v1.0.0):
        - Initial module creation
        - Implemented core order management functionality
        - Added integration with Connect API
        - Implemented multileg options support

    2025-10-15 (v0.9.0):
        - Beta version for testing
        - Basic order placement logic
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import asyncio
import json
import uuid
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum, auto
from pathlib import Path
import copy
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from threading import Lock, Event as ThreadEvent, RLock

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Import Connect API
from Spyder.SpyderB_Broker.SpyderB01_ConnectAPI import ConnectAPI, MessageType

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_ORDER_TIMEOUT = 30.0
MAX_ORDER_ID_LENGTH = 50
ORDER_STATE_PERSISTENCE_INTERVAL = 60  # seconds

# ==============================================================================
# ENUMS
# ==============================================================================
class OrderType(Enum):
    """Order types supported by Connect API"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"

class OrderSide(Enum):
    """Order sides"""
    BUY = "BUY"
    SELL = "SELL"
    SELL_SHORT = "SELL_SHORT"

class OrderState(Enum):
    """Order states"""
    PENDING = auto()
    SUBMITTED = auto()
    PRE_SUBMITTED = auto()
    ACKNOWLEDGED = auto()
    FILLED = auto()
    PARTIALLY_FILLED = auto()
    CANCELLED = auto()
    REJECTED = auto()
    EXPIRED = auto()
    UNKNOWN = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class Order:
    """Order representation"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "DAY"
    exchange: str = "SMART"
    currency: str = "USD"

    # Additional fields for options
    security_type: str = "STK"
    expiry: Optional[str] = None
    strike: Optional[float] = None
    right: Optional[str] = None  # CALL/PUT

    # Multi-leg support
    legs: List[Dict[str, Any]] = field(default_factory=list)

    # Internal tracking
    state: OrderState = OrderState.PENDING
    submitted_time: Optional[datetime] = None
    filled_quantity: int = 0
    remaining_quantity: int = 0
    average_fill_price: float = 0.0
    last_fill_price: float = 0.0
    last_fill_time: Optional[datetime] = None

    # Error tracking
    error_message: Optional[str] = None
    warning_message: Optional[str] = None

    # Metadata
    client_order_id: str = ""
    parent_order_id: Optional[str] = None
    oca_group: Optional[str] = None  # One-Cancels-All group
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

@dataclass
class OrderResult:
    """Result of an order operation"""
    success: bool
    order_id: str
    operation: str  # submit, cancel, modify
    message: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ExecutionReport:
    """Execution report representation"""
    order_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    execution_id: str
    timestamp: datetime
    commission: Optional[float] = None

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class OrderManager:
    """
    Order management using Connect API.

    This class manages order placement, tracking, and execution through the Connect API.
    It provides a high-level interface for order operations while handling
    order state persistence, and multileg options support.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling system
        connect_api: Connect API instance
        _orders: Dictionary of active orders
        _order_lock: Thread lock for order operations
        _shutdown_event: Event for coordinated shutdown
    """

    def __init__(self, connect_api: ConnectAPI):
        """
        Initialize the order manager.

        Args:
            connect_api: Connect API instance
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # Connect API
        self.connect_api = connect_api

        # Order management
        self._orders: Dict[str, Order] = {}
        self._order_lock = RLock()
        self._shutdown_event = ThreadEvent()

        # State persistence
        self._persistence_thread: Optional[threading.Thread] = None
        self._persistence_enabled = True

        # Metrics
        self.metrics = {
            'orders_submitted': 0,
            'orders_filled': 0,
            'orders_cancelled': 0,
            'orders_rejected': 0,
            'total_volume': 0.0,
            'total_commission': 0.0,
            'start_time': datetime.now()
        }

        # Register message handlers
        self._register_handlers()

        self.logger.info("OrderManager initialized")

    def _register_handlers(self):
        """Register message handlers with the Connect API"""
        self.connect_api.register_handler(MessageType.EXECUTION_REPORT, self._handle_execution_report)
        self.connect_api.register_handler(MessageType.ORDER_SINGLE_STATUS, self._handle_order_status)
        self.connect_api.register_handler(MessageType.ORDER_CANCEL_REJECT, self._handle_order_cancel_reject)
        self.connect_api.register_handler(MessageType.ERROR, self._handle_error_message)

    # ==========================================================================
    # ORDER OPERATIONS
    # ==========================================================================

    async def submit_order(self, order: Order) -> OrderResult:
        """
        Submit an order to the Connect API.

        Args:
            order: Order to submit

        Returns:
            OrderResult containing the submission outcome
        """
        order_id = order.order_id or str(uuid.uuid4())
        order.order_id = order_id
        order.client_order_id = order_id

        try:
            with self._order_lock:
                # Check if order already exists
                if order_id in self._orders:
                    return OrderResult(
                        success=False,
                        order_id=order_id,
                        operation="submit",
                        message="Order with this ID already exists",
                        error_code="DUPLICATE_ORDER_ID"
                    )

                # Add to order tracking
                order.state = OrderState.PRE_SUBMITTED
                order.submitted_time = datetime.now()
                order.remaining_quantity = order.quantity
                self._orders[order_id] = order

                # Log order submission
                self.logger.info(
                    f"Submitting order: {order_id} - {order.side.value} "
                    f"{order.quantity} {order.symbol} @ {order.price}"
                )

                # Prepare order message
                order_message = self._create_order_message(order)

                # Submit order
                response = await self.connect_api.send_message(order_message)

                if response:
                    order.state = OrderState.SUBMITTED
                    self.metrics['orders_submitted'] += 1

                    return OrderResult(
                        success=True,
                        order_id=order_id,
                        operation="submit",
                        message="Order submitted successfully"
                    )
                else:
                    order.state = OrderState.REJECTED
                    order.error_message = "No response from server"
                    self.metrics['orders_rejected'] += 1

                    return OrderResult(
                        success=False,
                        order_id=order_id,
                        operation="submit",
                        message="No response from server",
                        error_code="NO_RESPONSE"
                    )

        except Exception as e:
            self.logger.error(f"Order submission failed: {e}")
            self.error_handler.handle_error(e, "submit_order")

            with self._order_lock:
                if order_id in self._orders:
                    order.state = OrderState.REJECTED
                    order.error_message = str(e)
                    self.metrics['orders_rejected'] += 1

            return OrderResult(
                success=False,
                order_id=order_id,
                operation="submit",
                message=str(e),
                error_code="SUBMISSION_ERROR"
            )

    async def cancel_order(self, order_id: str) -> OrderResult:
        """
        Cancel an existing order.

        Args:
            order_id: Order ID to cancel

        Returns:
            OrderResult containing the cancellation outcome
        """
        try:
            with self._order_lock:
                if order_id not in self._orders:
                    return OrderResult(
                        success=False,
                        order_id=order_id,
                        operation="cancel",
                        message="Order not found",
                        error_code="ORDER_NOT_FOUND"
                    )

                order = self._orders[order_id]

                # Check if order can be cancelled
                if order.state not in [OrderState.SUBMITTED, OrderState.ACKNOWLEDGED, OrderState.PARTIALLY_FILLED]:
                    return OrderResult(
                        success=False,
                        order_id=order_id,
                        operation="cancel",
                        message=f"Order cannot be cancelled in state: {order.state.name}",
                        error_code="INVALID_ORDER_STATE"
                    )

                # Log cancellation
                self.logger.info(f"Cancelling order: {order_id}")

                # Prepare cancel message
                cancel_message = {
                    "MsgType": MessageType.ORDER_CANCEL.value,
                    "ClOrdID": str(uuid.uuid4()),
                    "OrigClOrdID": order_id,
                    "Account": "U1234567",  # TODO: Get from config
                    "SessionID": self.connect_api.session_id
                }

                # Submit cancellation
                response = await self.connect_api.send_message(cancel_message)

                if response:
                    order.state = OrderState.CANCELLED
                    self.metrics['orders_cancelled'] += 1

                    return OrderResult(
                        success=True,
                        order_id=order_id,
                        operation="cancel",
                        message="Order cancelled successfully"
                    )
                else:
                    return OrderResult(
                        success=False,
                        order_id=order_id,
                        operation="cancel",
                        message="No response from server",
                        error_code="NO_RESPONSE"
                    )

        except Exception as e:
            self.logger.error(f"Order cancellation failed: {e}")
            self.error_handler.handle_error(e, "cancel_order")

            return OrderResult(
                success=False,
                order_id=order_id,
                operation="cancel",
                message=str(e),
                error_code="CANCELLATION_ERROR"
            )

    # ==========================================================================
    # ORDER QUERIES
    # ==========================================================================

    def get_order(self, order_id: str) -> Optional[Order]:
        """
        Get order by ID.

        Args:
            order_id: Order ID

        Returns:
            Order object or None if not found
        """
        with self._order_lock:
            return self._orders.get(order_id)

    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        """
        Get all orders for a symbol.

        Args:
            symbol: Symbol to filter by

        Returns:
            List of orders for the symbol
        """
        with self._order_lock:
            return [
                order for order in self._orders.values()
                if order.symbol == symbol
            ]

    def get_orders_by_state(self, state: OrderState) -> List[Order]:
        """
        Get all orders in a specific state.

        Args:
            state: State to filter by

        Returns:
            List of orders in the state
        """
        with self._order_lock:
            return [
                order for order in self._orders.values()
                if order.state == state
            ]

    def get_all_orders(self) -> List[Order]:
        """
        Get all orders.

        Returns:
            List of all orders
        """
        with self._order_lock:
            return list(self._orders.values())

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================

    def _create_order_message(self, order: Order) -> Dict[str, Any]:
        """
        Create order message for Connect API.

        Args:
            order: Order to create message for

        Returns:
            Order message dictionary
        """
        message = {
            "MsgType": MessageType.ORDER_SINGLE.value,
            "ClOrdID": order.order_id,
            "Symbol": order.symbol,
            "Side": order.side.value,
            "OrderQty": str(order.quantity),
            "OrdType": order.order_type.value,
            "Account": "U1234567",  # TODO: Get from config
            "SessionID": self.connect_api.session_id,
            "TimeInForce": order.time_in_force,
            "Currency": order.currency
        }

        # Add optional fields
        if order.price:
            message["Price"] = str(order.price)

        if order.stop_price:
            message["StopPx"] = str(order.stop_price)

        # Add options fields if applicable
        if order.security_type == "OPT":
            message["SecurityType"] = "OPTION"
            if order.expiry:
                message["MaturityYearMonth"] = order.expiry[:6]  # YYYYMM
                message["MaturityDay"] = order.expiry[6:8] if len(order.expiry) > 6 else "20"
            if order.strike:
                message["StrikePrice"] = str(order.strike)
            if order.right:
                message["PutOrCall"] = order.right

        # Add multi-leg support
        if order.legs:
            message["SecurityType"] = "MULTILEG"
            message["Legs"] = order.legs

        return message

    async def _handle_execution_report(self, data: Dict[str, Any]):
        """
        Handle execution report message.

        Args:
            data: Execution report data
        """
        try:
            # Create execution from data
            execution = ExecutionReport(
                order_id=data.get("ClOrdID", ""),
                symbol=data.get("Symbol", ""),
                side=data.get("Side", ""),
                quantity=int(data.get("LastShares", 0)),
                price=float(data.get("LastPx", 0.0)),
                execution_id=data.get("ExecID", ""),
                timestamp=datetime.now()
            )

            with self._order_lock:
                order_id = execution.order_id
                if order_id not in self._orders:
                    self.logger.warning(f"Received execution for unknown order: {order_id}")
                    return

                order = self._orders[order_id]

                # Update order state
                if order.filled_quantity == 0:
                    order.state = OrderState.FILLED
                    self.metrics['orders_filled'] += 1
                else:
                    order.state = OrderState.PARTIALLY_FILLED

                # Update order fields
                order.filled_quantity += execution.quantity
                order.remaining_quantity = max(0, order.quantity - order.filled_quantity)
                order.last_fill_price = execution.price
                order.last_fill_time = execution.timestamp

                # Calculate average fill price
                if order.filled_quantity > 0:
                    total_value = (
                        (order.average_fill_price * (order.filled_quantity - execution.quantity)) +
                        (execution.price * execution.quantity)
                    )
                    order.average_fill_price = total_value / order.filled_quantity

                # Update metrics
                self.metrics['total_volume'] += execution.price * execution.quantity

                # Update commission if available
                if execution.commission:
                    self.metrics['total_commission'] += execution.commission

                # Log execution
                self.logger.info(
                    f"Order execution: {order_id} - {execution.side} "
                    f"{execution.quantity} {execution.symbol} @ {execution.price}"
                )

        except Exception as e:
            self.logger.error(f"Error handling execution report: {e}")
            self.error_handler.handle_error(e, "_handle_execution_report")

    async def _handle_order_status(self, data: Dict[str, Any]):
        """
        Handle order status message.

        Args:
            data: Order status data
        """
        try:
            order_id = data.get("ClOrdID")
            if not order_id:
                self.logger.warning("Order status message missing ClOrdID")
                return

            status = data.get("OrdStatus", "UNKNOWN")

            with self._order_lock:
                if order_id not in self._orders:
                    self.logger.warning(f"Received status for unknown order: {order_id}")
                    return

                order = self._orders[order_id]

                # Update order state based on status
                if status == "ACKNOWLEDGED":
                    order.state = OrderState.ACKNOWLEDGED
                elif status == "REJECTED":
                    order.state = OrderState.REJECTED
                    order.error_message = data.get("Text", "Order rejected")
                    self.metrics['orders_rejected'] += 1
                elif status == "CANCELLED":
                    order.state = OrderState.CANCELLED
                    self.metrics['orders_cancelled'] += 1
                elif status == "EXPIRED":
                    order.state = OrderState.EXPIRED

                # Log status update
                self.logger.debug(f"Order status: {order_id} - {status}")

        except Exception as e:
            self.logger.error(f"Error handling order status: {e}")
            self.error_handler.handle_error(e, "_handle_order_status")

    async def _handle_order_cancel_reject(self, data: Dict[str, Any]):
        """
        Handle order cancel reject message.

        Args:
            data: Cancel reject data
        """
        try:
            order_id = data.get("ClOrdID")
            if not order_id:
                self.logger.warning("Cancel reject message missing ClOrdID")
                return

            text = data.get("Text", "Cancel rejected")

            with self._order_lock:
                if order_id not in self._orders:
                    self.logger.warning(f"Received cancel reject for unknown order: {order_id}")
                    return

                order = self._orders[order_id]
                order.warning_message = text

                # Log cancel reject
                self.logger.warning(f"Order cancel rejected: {order_id} - {text}")

        except Exception as e:
            self.logger.error(f"Error handling order cancel reject: {e}")
            self.error_handler.handle_error(e, "_handle_order_cancel_reject")

    async def _handle_error_message(self, data: Dict[str, Any]):
        """
        Handle error message.

        Args:
            data: Error data
        """
        try:
            error_code = data.get("ErrorCode", "UNKNOWN")
            error_text = data.get("ErrorText", "Unknown error")
            order_id = data.get("ClOrdID")

            self.logger.error(f"Order error: {error_code} - {error_text}")

            if order_id:
                with self._order_lock:
                    if order_id in self._orders:
                        order = self._orders[order_id]
                        order.error_message = error_text

                        # Update order state if appropriate
                        if order.state in [OrderState.PRE_SUBMITTED, OrderState.SUBMITTED]:
                            order.state = OrderState.REJECTED
                            self.metrics['orders_rejected'] += 1

        except Exception as e:
            self.logger.error(f"Error handling error message: {e}")
            self.error_handler.handle_error(e, "_handle_error_message")

    # ==========================================================================
    # PUBLIC UTILITY METHODS
    # ==========================================================================

    def create_order(
        self,
        symbol: str,
        side: Union[str, OrderSide],
        order_type: Union[str, OrderType],
        quantity: int,
        price: Optional[float] = None,
        **kwargs
    ) -> Order:
        """
        Create an order object.

        Args:
            symbol: Symbol
            side: Order side
            order_type: Order type
            quantity: Quantity
            price: Price (required for limit orders)
            **kwargs: Additional order parameters

        Returns:
            Order object
        """
        # Convert enums if strings
        if isinstance(side, str):
            side = OrderSide(side.upper())

        if isinstance(order_type, str):
            order_type = OrderType(order_type.upper())

        # Create order
        order = Order(
            order_id=str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            **kwargs
        )

        return order

    def stop(self):
        """Stop the order manager"""
        self.logger.info("Stopping OrderManager...")

        # Signal shutdown
        self._shutdown_event.set()

        # Stop persistence
        self.stop_persistence()

        self.logger.info("OrderManager stopped")

    # ==========================================================================
    # STATE PERSISTENCE
    # ==========================================================================

    def start_persistence(self):
        """Start state persistence thread"""
        if self._persistence_enabled and not self._persistence_thread:
            self._persistence_thread = threading.Thread(
                target=self._persistence_loop,
                daemon=True,
                name="OrderPersistence"
            )
            self._persistence_thread.start()
            self.logger.info("Order state persistence started")

    def stop_persistence(self):
        """Stop state persistence thread"""
        if self._persistence_thread:
            self._persistence_enabled = False
            self._persistence_thread.join(timeout=5.0)
            self._persistence_thread = None
            self.logger.info("Order state persistence stopped")

    def _persistence_loop(self):
        """Persistence loop for saving order state"""
        while self._persistence_enabled:
            try:
                # Save order state
                self._save_order_state()

                # Wait for next iteration
                time.sleep(ORDER_STATE_PERSISTENCE_INTERVAL)

            except Exception as e:
                self.logger.error(f"Error in persistence loop: {e}")
                time.sleep(5.0)  # Wait before retry

    def _save_order_state(self):
        """Save order state to disk"""
        try:
            # Create orders data
            orders_data = {}
            with self._order_lock:
                for order_id, order in self._orders.items():
                    # Convert order to dict
                    order_dict = asdict(order)

                    # Convert datetime objects to strings
                    for key, value in order_dict.items():
                        if isinstance(value, datetime):
                            order_dict[key] = value.isoformat()
                        elif isinstance(value, Enum):
                            order_dict[key] = value.name

                    orders_data[order_id] = order_dict

            # Create persistence directory if it doesn't exist
            persistence_dir = Path("data/order_state")
            persistence_dir.mkdir(parents=True, exist_ok=True)

            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = persistence_dir / f"orders_{timestamp}.json"

            with open(file_path, 'w') as f:
                json.dump(orders_data, f, indent=2)

            self.logger.debug(f"Order state saved to {file_path}")

        except Exception as e:
            self.logger.error(f"Failed to save order state: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get order manager metrics.

        Returns:
            Dictionary containing metrics
        """
        with self._order_lock:
            # Calculate success rate
            total = self.metrics['orders_submitted']
            success_rate = 0.0
            if total > 0:
                success_rate = (self.metrics['orders_filled'] / total) * 100

            # Calculate uptime
            uptime = datetime.now() - self.metrics['start_time']

            return {
                'orders_submitted': self.metrics['orders_submitted'],
                'orders_filled': self.metrics['orders_filled'],
                'orders_cancelled': self.metrics['orders_cancelled'],
                'orders_rejected': self.metrics['orders_rejected'],
                'success_rate': success_rate,
                'total_volume': self.metrics['total_volume'],
                'total_commission': self.metrics['total_commission'],
                'active_orders': len([o for o in self._orders.values() if o.state in [
                    OrderState.SUBMITTED, OrderState.ACKNOWLEDGED, OrderState.PARTIALLY_FILLED
                ]]),
                'uptime_seconds': uptime.total_seconds(),
                'start_time': self.metrics['start_time'].isoformat()
            }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_order_manager(connect_api: ConnectAPI) -> OrderManager:
    """
    Factory function to create an order manager instance.

    Args:
        connect_api: Connect API instance

    Returns:
        OrderManager instance
    """
    return OrderManager(connect_api)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("="*80)
    print("SPYDER Order Manager Test")
    print("="*80)

    # This would require actual Connect API to test
    print("Order manager module loaded successfully")

    print("\n" + "="*80)
    print("Module testing completed.")
    print("="*80)
