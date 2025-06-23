#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderB02_OrderManager.py
Group: B (Broker Integration)
Purpose: Order creation and execution management

Description:
    This module manages all order-related operations for the Spyder trading system.
    It handles order creation, submission, modification, cancellation, and tracking.
    The module ensures proper order validation, risk checks, and execution monitoring
    while maintaining a complete audit trail of all order activities.

Author: Mohamed Talib
Date: 2025-05-29
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import threading
import datetime
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum, auto
from dataclasses import dataclass, field
from collections import defaultdict, deque
import uuid
import json

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from ibapi.order import Order as IBOrder
from ibapi.contract import Contract
from ibapi.order_state import OrderState
from ibapi.common import OrderId

# ==============================================================================
# LOCAL IMPORTS
from .SpyderB10_IBDataTypes import OrderStatus, OrderType
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import TradingConstants
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType, EventPriority
from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Order defaults
DEFAULT_TIF = "DAY"  # Time in Force
DEFAULT_ORDER_TYPE = "LMT"  # Limit order
OPTION_MULTIPLIER = 100

# Order validation
MAX_ORDER_SIZE = 100  # Maximum contracts per order
MAX_PENDING_ORDERS = 50
ORDER_TIMEOUT = 300  # 5 minutes

# Retry settings
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 2  # seconds

# ==============================================================================
# ENUMS
# ==============================================================================
class OrderStatus(Enum):
    """Order status states"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    WORKING = "working"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ERROR = "error"

class OrderType(Enum):
    """Order types"""
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP LMT"
    TRAILING_STOP = "TRAIL"
    MARKET_ON_CLOSE = "MOC"
    LIMIT_ON_CLOSE = "LOC"

class OrderAction(Enum):
    """Order actions"""
    BUY = "BUY"
    SELL = "SELL"

class TimeInForce(Enum):
    """Time in force options"""
    DAY = "DAY"
    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill
    GTD = "GTD"  # Good Till Date
    OPG = "OPG"  # Opening

class OrderValidationError(Exception):
    """Order validation error"""
    pass

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class OrderRequest:
    """Order request details"""
    symbol: str
    action: OrderAction
    quantity: int
    order_type: OrderType
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    strategy_id: Optional[str] = None
    tag: Optional[str] = None
    parent_order_id: Optional[str] = None
    oca_group: Optional[str] = None  # One-Cancels-All
    transmit: bool = True
    
    def validate(self) -> None:
        """Validate order request"""
        if self.quantity <= 0 or self.quantity > MAX_ORDER_SIZE:
            raise OrderValidationError(f"Invalid quantity: {self.quantity}")
        
        if self.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
            if self.limit_price is None or self.limit_price <= 0:
                raise OrderValidationError("Limit price required for limit orders")
        
        if self.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
            if self.stop_price is None or self.stop_price <= 0:
                raise OrderValidationError("Stop price required for stop orders")

class OrderInfo:
    """Complete order information"""
    order_id: str
    broker_id: Optional[int] = None
    request: OrderRequest = None
    contract: Optional[Contract] = None
    ib_order: Optional[IBOrder] = None
    status: OrderStatus = OrderStatus.PENDING
    
    # Timestamps
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    submitted_at: Optional[datetime.datetime] = None
    filled_at: Optional[datetime.datetime] = None
    cancelled_at: Optional[datetime.datetime] = None
    
    # Execution details
    filled_quantity: int = 0
    remaining_quantity: int = 0
    average_fill_price: float = 0.0
    last_fill_price: float = 0.0
    commission: float = 0.0
    
    # Status tracking
    status_history: List[Tuple[datetime.datetime, OrderStatus]] = field(default_factory=list)
    error_message: Optional[str] = None
    retry_count: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'order_id': self.order_id,
            'broker_id': self.broker_id,
            'symbol': self.request.symbol if self.request else None,
            'action': self.request.action.value if self.request else None,
            'quantity': self.request.quantity if self.request else None,
            'order_type': self.request.order_type.value if self.request else None,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'filled_quantity': self.filled_quantity,
            'average_fill_price': self.average_fill_price,
            'commission': self.commission,
            'error_message': self.error_message
        }

class ExecutionReport:
    """Trade execution report"""
    order_id: str
    execution_id: str
    timestamp: datetime.datetime
    quantity: int
    price: float
    commission: float
    exchange: str
    side: str
    cumulative_quantity: int
    average_price: float

# ==============================================================================
# ORDER MANAGER CLASS
# ==============================================================================
class OrderManager:
    """
    Manages order lifecycle and execution.
    
    Features:
    - Order creation and validation
    - Order submission and tracking
    - Order modification and cancellation
    - Execution monitoring
    - Parent/child order relationships
    - OCA (One-Cancels-All) groups
    - Order persistence and recovery
    """
    
    def __init__(self, ib_client: SpyderClient, event_manager: EventManager):
        """
        Initialize order manager.
        
        Args:
            ib_client: IB client instance
            event_manager: Event manager instance
        """
        self.ib_client = ib_client
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Order tracking
        self.orders: Dict[str, OrderInfo] = {}
        self.broker_to_order_id: Dict[int, str] = {}
        self.pending_orders: deque = deque(maxlen=MAX_PENDING_ORDERS)
        self.active_orders: Dict[str, OrderInfo] = {}
        
        # Order grouping
        self.oca_groups: Dict[str, List[str]] = defaultdict(list)
        self.parent_child_map: Dict[str, List[str]] = defaultdict(list)
        
        # Execution tracking
        self.executions: List[ExecutionReport] = []
        self.daily_volume: Dict[str, int] = defaultdict(int)
        
        # Statistics
        self.order_stats = {
            'total_orders': 0,
            'filled_orders': 0,
            'cancelled_orders': 0,
            'rejected_orders': 0,
            'total_commission': 0.0
        }
        
        # Callbacks
        self.order_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        
        # Thread safety
        self._order_lock = threading.RLock()
        
        # Register IB callbacks
        self._register_ib_callbacks()
        
        self.logger.info("OrderManager initialized")
    
    # ==========================================================================
    # ORDER CREATION
    # ==========================================================================
    def create_order(self, request: OrderRequest) -> str:
        """
        Create a new order.
        
        Args:
            request: Order request details
            
        Returns:
            Order ID
        """
        try:
            # Validate request
            request.validate()
            
            # Generate order ID
            order_id = str(uuid.uuid4())
            
            # Create contract
            contract = self._create_contract(request)
            
            # Create IB order
            ib_order = self._create_ib_order(request)
            
            # Create order info
            order_info = OrderInfo(
                order_id=order_id,
                request=request,
                contract=contract,
                ib_order=ib_order,
                remaining_quantity=request.quantity
            )
            
            # Store order
            with self._order_lock:
                self.orders[order_id] = order_info
                self.pending_orders.append(order_id)
                
                # Track relationships
                if request.parent_order_id:
                    self.parent_child_map[request.parent_order_id].append(order_id)
                
                if request.oca_group:
                    self.oca_groups[request.oca_group].append(order_id)
            
            # Update status
            self._update_order_status(order_id, OrderStatus.PENDING)
            
            # Emit event
            self.event_manager.emit(Event(
                EventType.ORDER,
                {
                    'type': 'order_created',
                    'order_id': order_id,
                    'symbol': request.symbol,
                    'action': request.action.value,
                    'quantity': request.quantity,
                    'order_type': request.order_type.value
                },
                priority=EventPriority.HIGH
            ))
            
            self.logger.info(f"Order created: {order_id} - {request.symbol} {request.action.value} {request.quantity}")
            
            return order_id
            
        except Exception as e:
            self.logger.error(f"Failed to create order: {e}")
            raise
    
    def _create_contract(self, request: OrderRequest) -> Contract:
        """Create IB contract from request"""
        contract = Contract()
        
        # Parse symbol for options (e.g., "SPY_250620C450")
        if '_' in request.symbol:
            parts = request.symbol.split('_')
            contract.symbol = parts[0]
            
            if len(parts) == 2:  # Option
                option_part = parts[1]
                contract.secType = "OPT"
                contract.lastTradeDateOrContractMonth = "20" + option_part[:6]  # YYMMDD
                contract.right = option_part[6]  # C or P
                contract.strike = float(option_part[7:])
                contract.multiplier = str(OPTION_MULTIPLIER)
        else:
            contract.symbol = request.symbol
            contract.secType = "STK"
        
        contract.exchange = "SMART"
        contract.currency = "USD"
        
        return contract
    
    def _create_ib_order(self, request: OrderRequest) -> IBOrder:
        """Create IB order from request"""
        order = IBOrder()
        
        order.action = request.action.value
        order.totalQuantity = request.quantity
        order.orderType = request.order_type.value
        order.tif = request.time_in_force.value
        order.transmit = request.transmit
        
        # Set prices
        if request.limit_price is not None:
            order.lmtPrice = request.limit_price
        
        if request.stop_price is not None:
            order.auxPrice = request.stop_price
        
        # Set OCA group
        if request.oca_group:
            order.ocaGroup = request.oca_group
            order.ocaType = 1  # Cancel all remaining orders
        
        # Set order reference
        if request.tag:
            order.orderRef = request.tag
        
        return order
    
    # ==========================================================================
    # ORDER SUBMISSION
    # ==========================================================================
    def submit_order(self, order_id: str) -> bool:
        """
        Submit order to broker.
        
        Args:
            order_id: Order ID to submit
            
        Returns:
            Success status
        """
        with self._order_lock:
            order_info = self.orders.get(order_id)
            if not order_info:
                self.logger.error(f"Order not found: {order_id}")
                return False
            
            if order_info.status != OrderStatus.PENDING:
                self.logger.error(f"Order {order_id} not in pending state: {order_info.status}")
                return False
        
        try:
            # Get next order ID from broker
            broker_id = self.ib_client.get_next_order_id()
            
            # Update order info
            with self._order_lock:
                order_info.broker_id = broker_id
                order_info.submitted_at = datetime.datetime.now()
                self.broker_to_order_id[broker_id] = order_id
                
                # Move to active orders
                self.active_orders[order_id] = order_info
                if order_id in self.pending_orders:
                    self.pending_orders.remove(order_id)
            
            # Submit to broker
            self.ib_client.placeOrder(
                broker_id,
                order_info.contract,
                order_info.ib_order
            )
            
            # Update status
            self._update_order_status(order_id, OrderStatus.SUBMITTED)
            
            # Update statistics
            self.order_stats['total_orders'] += 1
            
            # Emit event
            self.event_manager.emit(Event(
                EventType.ORDER,
                {
                    'type': 'order_submitted',
                    'order_id': order_id,
                    'broker_id': broker_id,
                    'symbol': order_info.request.symbol,
                    'action': order_info.request.action.value,
                    'quantity': order_info.request.quantity
                },
                priority=EventPriority.HIGH
            ))
            
            self.logger.info(f"Order submitted: {order_id} (broker_id: {broker_id})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to submit order {order_id}: {e}")
            self._update_order_status(order_id, OrderStatus.ERROR, str(e))
            return False
    
    def submit_bracket_order(
        self,
        parent_request: OrderRequest,
        stop_loss_price: float,
        take_profit_price: float
    ) -> Tuple[str, str, str]:
        """
        Submit bracket order (parent + stop loss + take profit).
        
        Args:
            parent_request: Parent order request
            stop_loss_price: Stop loss price
            take_profit_price: Take profit price
            
        Returns:
            Tuple of (parent_id, stop_loss_id, take_profit_id)
        """
        # Create parent order
        parent_id = self.create_order(parent_request)
        
        # Create stop loss order
        stop_loss_request = OrderRequest(
            symbol=parent_request.symbol,
            action=OrderAction.SELL if parent_request.action == OrderAction.BUY else OrderAction.BUY,
            quantity=parent_request.quantity,
            order_type=OrderType.STOP,
            stop_price=stop_loss_price,
            parent_order_id=parent_id,
            transmit=False
        )
        stop_loss_id = self.create_order(stop_loss_request)
        
        # Create take profit order
        take_profit_request = OrderRequest(
            symbol=parent_request.symbol,
            action=OrderAction.SELL if parent_request.action == OrderAction.BUY else OrderAction.BUY,
            quantity=parent_request.quantity,
            order_type=OrderType.LIMIT,
            limit_price=take_profit_price,
            parent_order_id=parent_id,
            transmit=True  # Transmit all orders
        )
        take_profit_id = self.create_order(take_profit_request)
        
        # Link orders in OCA group
        oca_group = f"bracket_{parent_id}"
        with self._order_lock:
            self.orders[stop_loss_id].request.oca_group = oca_group
            self.orders[take_profit_id].request.oca_group = oca_group
            self.oca_groups[oca_group] = [stop_loss_id, take_profit_id]
        
        # Submit all orders
        self.submit_order(parent_id)
        self.submit_order(stop_loss_id)
        self.submit_order(take_profit_id)
        
        self.logger.info(f"Bracket order created: parent={parent_id}, sl={stop_loss_id}, tp={take_profit_id}")
        
        return parent_id, stop_loss_id, take_profit_id
    
    # ==========================================================================
    # ORDER MODIFICATION
    # ==========================================================================
    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> bool:
        """
        Modify an existing order.
        
        Args:
            order_id: Order ID to modify
            quantity: New quantity
            limit_price: New limit price
            stop_price: New stop price
            
        Returns:
            Success status
        """
        with self._order_lock:
            order_info = self.orders.get(order_id)
            if not order_info:
                self.logger.error(f"Order not found: {order_id}")
                return False
            
            if order_info.status not in [OrderStatus.SUBMITTED, OrderStatus.ACCEPTED, OrderStatus.WORKING]:
                self.logger.error(f"Cannot modify order in status: {order_info.status}")
                return False
            
            if not order_info.broker_id:
                self.logger.error(f"Order has no broker ID: {order_id}")
                return False
        
        try:
            # Update order object
            if quantity is not None:
                order_info.ib_order.totalQuantity = quantity
                order_info.request.quantity = quantity
            
            if limit_price is not None:
                order_info.ib_order.lmtPrice = limit_price
                order_info.request.limit_price = limit_price
            
            if stop_price is not None:
                order_info.ib_order.auxPrice = stop_price
                order_info.request.stop_price = stop_price
            
            # Submit modification to broker
            self.ib_client.placeOrder(
                order_info.broker_id,
                order_info.contract,
                order_info.ib_order
            )
            
            # Emit event
            self.event_manager.emit(Event(
                EventType.ORDER,
                {
                    'type': 'order_modified',
                    'order_id': order_id,
                    'quantity': quantity,
                    'limit_price': limit_price,
                    'stop_price': stop_price
                },
                priority=EventPriority.NORMAL
            ))
            
            self.logger.info(f"Order modified: {order_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to modify order {order_id}: {e}")
            return False
    
    # ==========================================================================
    # ORDER CANCELLATION
    # ==========================================================================
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            Success status
        """
        with self._order_lock:
            order_info = self.orders.get(order_id)
            if not order_info:
                self.logger.error(f"Order not found: {order_id}")
                return False
            
            if order_info.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                self.logger.warning(f"Order already in final state: {order_info.status}")
                return False
            
            if not order_info.broker_id:
                # Order not yet submitted, just mark as cancelled
                self._update_order_status(order_id, OrderStatus.CANCELLED)
                return True
        
        try:
            # Cancel at broker
            self.ib_client.cancelOrder(order_info.broker_id)
            
            # Note: Status will be updated when cancelOrder callback is received
            
            self.logger.info(f"Cancel request sent for order: {order_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def cancel_all_orders(self) -> int:
        """
        Cancel all active orders.
        
        Returns:
            Number of orders cancelled
        """
        cancelled_count = 0
        
        with self._order_lock:
            active_order_ids = list(self.active_orders.keys())
        
        for order_id in active_order_ids:
            if self.cancel_order(order_id):
                cancelled_count += 1
        
        self.logger.info(f"Cancelled {cancelled_count} orders")
        return cancelled_count
    
    # ==========================================================================
    # ORDER STATUS MANAGEMENT
    # ==========================================================================
    def _update_order_status(
        self,
        order_id: str,
        new_status: OrderStatus,
        error_message: Optional[str] = None
    ) -> None:
        """Update order status"""
        with self._order_lock:
            order_info = self.orders.get(order_id)
            if not order_info:
                return
            
            old_status = order_info.status
            order_info.status = new_status
            order_info.status_history.append((datetime.datetime.now(), new_status))
            
            if error_message:
                order_info.error_message = error_message
            
            # Update timestamps
            if new_status == OrderStatus.FILLED:
                order_info.filled_at = datetime.datetime.now()
                self.order_stats['filled_orders'] += 1
            elif new_status == OrderStatus.CANCELLED:
                order_info.cancelled_at = datetime.datetime.now()
                self.order_stats['cancelled_orders'] += 1
            elif new_status == OrderStatus.REJECTED:
                self.order_stats['rejected_orders'] += 1
            
            # Remove from active orders if terminal state
            if new_status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.ERROR]:
                self.active_orders.pop(order_id, None)
        
        # Execute callbacks
        self._execute_order_callbacks(order_id, old_status, new_status)
        
        # Emit event
        self.event_manager.emit(Event(
            EventType.ORDER,
            {
                'type': 'order_status_changed',
                'order_id': order_id,
                'old_status': old_status.value,
                'new_status': new_status.value,
                'error_message': error_message
            },
            priority=EventPriority.HIGH
        ))
        
        self.logger.info(f"Order {order_id} status: {old_status.value} -> {new_status.value}")
    
    # ==========================================================================
    # IB CALLBACKS
    # ==========================================================================
    def _register_ib_callbacks(self) -> None:
        """Register IB API callbacks"""
        self.ib_client.register_callback('orderStatus', self._on_order_status)
        self.ib_client.register_callback('openOrder', self._on_open_order)
        self.ib_client.register_callback('execDetails', self._on_exec_details)
        self.ib_client.register_callback('commissionReport', self._on_commission_report)
        self.ib_client.register_callback('error', self._on_error)
    
    def _on_order_status(
        self,
        orderId: int,
        status: str,
        filled: float,
        remaining: float,
        avgFillPrice: float,
        permId: int,
        parentId: int,
        lastFillPrice: float,
        clientId: int,
        whyHeld: str,
        mktCapPrice: float
    ) -> None:
        """Handle order status update from IB"""
        with self._order_lock:
            order_id = self.broker_to_order_id.get(orderId)
            if not order_id:
                self.logger.warning(f"Unknown broker order ID: {orderId}")
                return
            
            order_info = self.orders.get(order_id)
            if not order_info:
                return
            
            # Update execution details
            order_info.filled_quantity = int(filled)
            order_info.remaining_quantity = int(remaining)
            order_info.average_fill_price = avgFillPrice
            order_info.last_fill_price = lastFillPrice
        
        # Map IB status to our status
        status_map = {
            'PendingSubmit': OrderStatus.PENDING,
            'PendingCancel': OrderStatus.PENDING,
            'PreSubmitted': OrderStatus.SUBMITTED,
            'Submitted': OrderStatus.SUBMITTED,
            'ApiCancelled': OrderStatus.CANCELLED,
            'Cancelled': OrderStatus.CANCELLED,
            'Filled': OrderStatus.FILLED,
            'Inactive': OrderStatus.CANCELLED
        }
        
        new_status = status_map.get(status, OrderStatus.WORKING)
        
        # Handle partial fills
        if filled > 0 and remaining > 0:
            new_status = OrderStatus.PARTIAL
        
        self._update_order_status(order_id, new_status)
    
    def _on_open_order(
        self,
        orderId: int,
        contract: Contract,
        order: IBOrder,
        orderState: OrderState
    ) -> None:
        """Handle open order update from IB"""
        with self._order_lock:
            order_id = self.broker_to_order_id.get(orderId)
            if not order_id:
                return
            
            order_info = self.orders.get(order_id)
            if not order_info:
                return
            
            # Update order state
            if orderState.status == 'PreSubmitted' or orderState.status == 'Submitted':
                self._update_order_status(order_id, OrderStatus.ACCEPTED)
    
    def _on_exec_details(
        self,
        reqId: int,
        contract: Contract,
        execution
    ) -> None:
        """Handle execution details from IB"""
        with self._order_lock:
            order_id = self.broker_to_order_id.get(execution.orderId)
            if not order_id:
                return
            
            # Create execution report
            exec_report = ExecutionReport(
                order_id=order_id,
                execution_id=execution.execId,
                timestamp=datetime.datetime.now(),
                quantity=execution.shares,
                price=execution.price,
                commission=0.0,  # Will be updated in commission callback
                exchange=execution.exchange,
                side=execution.side,
                cumulative_quantity=execution.cumQty,
                average_price=execution.avgPrice
            )
            
            self.executions.append(exec_report)
            
            # Update daily volume
            order_info = self.orders.get(order_id)
            if order_info:
                self.daily_volume[order_info.request.symbol] += execution.shares
        
        # Emit execution event
        self.event_manager.emit(Event(
            EventType.FILL,
            {
                'type': 'order_filled',
                'order_id': order_id,
                'execution_id': execution.execId,
                'quantity': execution.shares,
                'price': execution.price,
                'exchange': execution.exchange
            },
            priority=EventPriority.CRITICAL
        ))
    
    def _on_commission_report(self, commissionReport) -> None:
        """Handle commission report from IB"""
        with self._order_lock:
            # Find execution by execution ID
            for exec_report in reversed(self.executions):
                if exec_report.execution_id == commissionReport.execId:
                    exec_report.commission = commissionReport.commission
                    
                    # Update order commission
                    order_info = self.orders.get(exec_report.order_id)
                    if order_info:
                        order_info.commission += commissionReport.commission
                        self.order_stats['total_commission'] += commissionReport.commission
                    break
    
    def _on_error(self, reqId: int, errorCode: int, errorString: str) -> None:
        """Handle error from IB"""
        # Order-related errors
        if reqId > 0:
            with self._order_lock:
                order_id = self.broker_to_order_id.get(reqId)
                if order_id:
                    if errorCode in [201, 202]:  # Order cancelled
                        self._update_order_status(order_id, OrderStatus.CANCELLED)
                    elif errorCode in [200, 203, 434]:  # Order rejected
                        self._update_order_status(order_id, OrderStatus.REJECTED, errorString)
                    else:
                        self.logger.error(f"Order {order_id} error {errorCode}: {errorString}")
    
    # ==========================================================================
    # ORDER QUERIES
    # ==========================================================================
    def get_order(self, order_id: str) -> Optional[OrderInfo]:
        """
        Get order information.
        
        Args:
            order_id: Order ID
            
        Returns:
            Order info or None
        """
        with self._order_lock:
            return self.orders.get(order_id)
    
    def get_active_orders(self) -> List[OrderInfo]:
        """
        Get all active orders.
        
        Returns:
            List of active orders
        """
        with self._order_lock:
            return list(self.active_orders.values())
    
    def get_orders_by_symbol(self, symbol: str) -> List[OrderInfo]:
        """
        Get orders for a specific symbol.
        
        Args:
            symbol: Symbol to filter by
            
        Returns:
            List of orders
        """
        with self._order_lock:
            return [
                order for order in self.orders.values()
                if order.request and order.request.symbol == symbol
            ]
    
    def get_order_statistics(self) -> Dict[str, Any]:
        """
        Get order statistics.
        
        Returns:
            Statistics dictionary
        """
        with self._order_lock:
            stats = self.order_stats.copy()
            stats['active_orders'] = len(self.active_orders)
            stats['pending_orders'] = len(self.pending_orders)
            stats['daily_volume'] = dict(self.daily_volume)
            return stats
    
    # ==========================================================================
    # CALLBACKS
    # ==========================================================================
    def register_order_callback(
        self,
        order_id: str,
        callback: Callable,
        events: Optional[List[OrderStatus]] = None
    ) -> None:
        """
        Register callback for order events.
        
        Args:
            order_id: Order ID to monitor
            callback: Callback function
            events: List of statuses to trigger callback (None = all)
        """
        key = f"{order_id}:{events}" if events else order_id
        self.order_callbacks[key].append(callback)
    
    def _execute_order_callbacks(
        self,
        order_id: str,
        old_status: OrderStatus,
        new_status: OrderStatus
    ) -> None:
        """Execute callbacks for order status change"""
        # General callbacks for this order
        for callback in self.order_callbacks.get(order_id, []):
            try:
                callback(order_id, old_status, new_status)
            except Exception as e:
                self.logger.error(f"Error in order callback: {e}")
        
        # Status-specific callbacks
        for status_list, callbacks in self.order_callbacks.items():
            if ':' in str(status_list) and order_id in str(status_list):
                if new_status in eval(status_list.split(':')[1]):
                    for callback in callbacks:
                        try:
                            callback(order_id, old_status, new_status)
                        except Exception as e:
                            self.logger.error(f"Error in order callback: {e}")

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test order manager
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    
    # Create mock IB client
    class MockSpyderClient:
        def __init__(self):
            self.next_order_id = 1000
            self.callbacks = defaultdict(list)
        
        def get_next_order_id(self):
            self.next_order_id += 1
            return self.next_order_id
        
        def placeOrder(self, orderId, contract, order):
            print(f"Placing order {orderId}: {contract.symbol} {order.action} {order.totalQuantity}")
        
        def cancelOrder(self, orderId):
            print(f"Cancelling order {orderId}")
        
        def register_callback(self, event, callback):
            self.callbacks[event].append(callback)
    
    # Initialize components
    event_manager = EventManager()
    ib_client = MockSpyderClient()
    order_manager = OrderManager(ib_client, event_manager)
    
    # Create test order
    request = OrderRequest(
        symbol="SPY",
        action=OrderAction.BUY,
        quantity=10,
        order_type=OrderType.LIMIT,
        limit_price=450.50,
        time_in_force=TimeInForce.DAY,
        strategy_id="test_strategy",
        tag="test_order"
    )
    
    # Create and submit order
    order_id = order_manager.create_order(request)
    print(f"Created order: {order_id}")
    
    success = order_manager.submit_order(order_id)
    print(f"Submitted order: {success}")
    
    # Get order info
    order_info = order_manager.get_order(order_id)
    if order_info:
        print(f"Order status: {order_info.status.value}")
    
    # Create bracket order
    bracket_request = OrderRequest(
        symbol="SPY_251219C460",  # SPY Call option
        action=OrderAction.BUY,
        quantity=5,
        order_type=OrderType.LIMIT,
        limit_price=5.50
    )
    
    parent_id, sl_id, tp_id = order_manager.submit_bracket_order(
        bracket_request,
        stop_loss_price=4.50,
        take_profit_price=7.50
    )
    print(f"Bracket order created: parent={parent_id}, sl={sl_id}, tp={tp_id}")
    
    # Get statistics
    stats = order_manager.get_order_statistics()
    print(f"\nOrder statistics:")
    print(json.dumps(stats, indent=2))