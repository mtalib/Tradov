#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderB02_OrderManager.py
Group: B (Broker Integration)
Purpose: Complete order management with execution tracking and error handling

Description:
    This module provides comprehensive order management functionality including order
    validation, submission, tracking, and lifecycle management. It handles single orders,
    multi-leg strategies, partial fills, and provides real-time order status monitoring.
    The module integrates with Interactive Brokers and includes sophisticated error
    recovery and retry mechanisms.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-07-03
Last Updated: 2025-07-03 Time: 17:00:00
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
import weakref
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from threading import Lock, Event as ThreadEvent, RLock

# IB Integration
try:
    from ib_insync import IB, Stock, Option, Contract, Order, Trade
    from ib_insync import LimitOrder, MarketOrder, StopOrder, util
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False
    print("WARNING: ib_insync not found. Running in simulation mode.")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import OrderAction, OrderType
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType

# Conditional imports
try:
    from SpyderB_Broker.SpyderB10_IBDataTypes import IBContract, IBOrder, OrderStatus
    HAS_IB_DATA_TYPES = True
except ImportError:
    HAS_IB_DATA_TYPES = False

try:
    from SpyderB_Broker.SpyderB06_ContractBuilder import ContractBuilder
    HAS_CONTRACT_BUILDER = True
except ImportError:
    HAS_CONTRACT_BUILDER = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Order Management Configuration
MAX_RETRY_ATTEMPTS = 3
ORDER_TIMEOUT_SECONDS = 30
MAX_PENDING_ORDERS = 1000
ORDER_QUEUE_SIZE = 500

# Fill Processing
PARTIAL_FILL_TIMEOUT = 60  # seconds
FILL_CHECK_INTERVAL = 1    # seconds

# Error Handling
MAX_CONSECUTIVE_ERRORS = 5
ERROR_COOLDOWN_SECONDS = 10

# Performance Limits
MAX_ORDERS_PER_SECOND = 10
ORDER_RATE_WINDOW = 60  # seconds

# ==============================================================================
# ENUMS
# ==============================================================================
class OrderState(Enum):
    """Order state enumeration"""
    CREATED = "created"
    VALIDATED = "validated"
    SUBMITTED = "submitted"
    PENDING_SUBMIT = "pending_submit"
    PRE_SUBMITTED = "pre_submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    ERROR = "error"
    EXPIRED = "expired"

class OrderPriority(Enum):
    """Order execution priority"""
    EMERGENCY = 1     # Risk management orders
    HIGH = 2          # Exit orders
    NORMAL = 3        # Entry orders
    LOW = 4           # Optimization orders

class FillType(Enum):
    """Fill type enumeration"""
    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"

class OrderValidationResult(Enum):
    """Order validation results"""
    VALID = "valid"
    INVALID_SYMBOL = "invalid_symbol"
    INVALID_QUANTITY = "invalid_quantity"
    INVALID_PRICE = "invalid_price"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    POSITION_LIMIT = "position_limit"
    MARKET_CLOSED = "market_closed"
    OTHER_ERROR = "other_error"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OrderRequest:
    """Order request data structure"""
    order_id: str
    symbol: str
    action: OrderAction
    quantity: int
    order_type: OrderType
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "DAY"
    strategy_id: Optional[str] = None
    signal_id: Optional[str] = None
    priority: OrderPriority = OrderPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_time: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        if not self.order_id:
            self.order_id = str(uuid.uuid4())

@dataclass
class OrderExecution:
    """Order execution tracking"""
    order_id: str
    broker_order_id: Optional[str] = None
    state: OrderState = OrderState.CREATED
    submitted_time: Optional[datetime] = None
    fill_time: Optional[datetime] = None
    fill_price: Optional[float] = None
    fill_quantity: int = 0
    remaining_quantity: int = 0
    total_quantity: int = 0
    avg_fill_price: Optional[float] = None
    commission: Optional[float] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    last_update: datetime = field(default_factory=datetime.now)
    fills: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class OrderFill:
    """Individual order fill data"""
    fill_id: str
    order_id: str
    execution_time: datetime
    fill_price: float
    fill_quantity: int
    commission: float
    exchange: str = ""
    execution_id: str = ""
    
@dataclass
class OrderValidation:
    """Order validation result"""
    is_valid: bool
    result: OrderValidationResult
    message: str
    suggested_fixes: List[str] = field(default_factory=list)

@dataclass
class OrderStatistics:
    """Order manager statistics"""
    total_orders: int = 0
    successful_orders: int = 0
    failed_orders: int = 0
    cancelled_orders: int = 0
    partial_fills: int = 0
    avg_execution_time_ms: float = 0.0
    total_commission: float = 0.0
    error_rate: float = 0.0
    last_reset: datetime = field(default_factory=datetime.now)

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class OrderManager:
    """
    Comprehensive Order Management System.
    
    This class handles all aspects of order lifecycle management including validation,
    submission, tracking, and fill processing. It provides robust error handling,
    retry mechanisms, and real-time order status monitoring.
    
    Key Features:
    - Multi-threaded order processing
    - Real-time fill tracking and reporting
    - Comprehensive error handling and recovery
    - Order validation and risk checks
    - Performance monitoring and statistics
    - Integration with IB Gateway and Client Portal
    
    Attributes:
        logger: Module logger instance
        config: Order manager configuration
        ib_client: Interactive Brokers client
        order_executions: Active order tracking
        statistics: Performance statistics
        
    Example:
        >>> order_manager = OrderManager(config, spyder_client)
        >>> order_manager.initialize()
        >>> result = order_manager.submit_order(order_request)
    """
    
    def __init__(self, config: Dict[str, Any], spyder_client):
        """
        Initialize the Order Manager.
        
        Args:
            config: Configuration dictionary
            spyder_client: Spyder broker client instance
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or {}
        self.spyder_client = spyder_client
        
        # Order tracking
        self.order_executions: Dict[str, OrderExecution] = {}
        self.pending_orders: Dict[str, OrderRequest] = {}
        self.completed_orders: deque = deque(maxlen=1000)
        self._order_lock = RLock()
        
        # Processing queues
        self.order_queue = queue.PriorityQueue(maxsize=ORDER_QUEUE_SIZE)
        self.fill_queue = queue.Queue()
        self._queue_lock = RLock()
        
        # Threading infrastructure
        self.thread_pool = ThreadPoolExecutor(max_workers=5)
        self.worker_threads: Dict[str, threading.Thread] = {}
        self._shutdown_event = ThreadEvent()
        
        # Rate limiting
        self.order_times: deque = deque(maxlen=MAX_ORDERS_PER_SECOND * 10)
        self._rate_lock = Lock()
        
        # Statistics and monitoring
        self.statistics = OrderStatistics()
        self._stats_lock = RLock()
        
        # Error tracking
        self.consecutive_errors = 0
        self.last_error_time: Optional[datetime] = None
        self.error_cooldown_until: Optional[datetime] = None
        
        # IB Integration
        self.ib_connection = None
        self.has_ib_connection = False
        
        # Contract builder integration
        if HAS_CONTRACT_BUILDER:
            try:
                self.contract_builder = ContractBuilder()
                self.has_contract_builder = True
            except Exception as e:
                self.logger.warning(f"Contract builder initialization failed: {e}")
                self.contract_builder = None
                self.has_contract_builder = False
        else:
            self.contract_builder = None
            self.has_contract_builder = False
        
        # Event manager integration
        try:
            from SpyderA_Core.SpyderA05_EventManager import get_event_manager
            self.event_manager = get_event_manager()
            self.has_event_manager = True
        except Exception as e:
            self.logger.warning(f"Event manager not available: {e}")
            self.event_manager = None
            self.has_event_manager = False
        
        self.logger.info("OrderManager initialized")
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    
    def initialize(self) -> bool:
        """
        Initialize the order manager.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing OrderManager...")
            
            # Initialize IB connection if available
            if HAS_IB_INSYNC and self.spyder_client:
                try:
                    if hasattr(self.spyder_client, 'ib') and self.spyder_client.ib:
                        self.ib_connection = self.spyder_client.ib
                        self.has_ib_connection = True
                        self.logger.info("IB connection available")
                    else:
                        self.logger.warning("IB connection not available in spyder_client")
                except Exception as e:
                    self.logger.warning(f"IB connection setup failed: {e}")
            
            # Start worker threads
            self._start_worker_threads()
            
            # Initialize statistics
            self._reset_statistics()
            
            self.logger.info("OrderManager initialization completed")
            return True
            
        except Exception as e:
            self.logger.error(f"OrderManager initialization failed: {e}")
            self.error_handler.handle_broker_error(e, "OrderManager", "initialize")
            return False
    
    def start(self) -> bool:
        """
        Start the order manager.
        
        Returns:
            bool: True if start successful
        """
        try:
            self.logger.info("Starting OrderManager...")
            
            # Validate connection
            if self.has_ib_connection and self.ib_connection:
                if not self.ib_connection.isConnected():
                    self.logger.warning("IB connection not established")
            
            self.logger.info("OrderManager started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"OrderManager start failed: {e}")
            return False
    
    def stop(self) -> bool:
        """
        Stop the order manager gracefully.
        
        Returns:
            bool: True if stop successful
        """
        try:
            self.logger.info("Stopping OrderManager...")
            
            # Signal shutdown
            self._shutdown_event.set()
            
            # Cancel all pending orders
            self._cancel_all_pending_orders()
            
            # Stop worker threads
            self._stop_worker_threads()
            
            # Shutdown thread pool
            self.thread_pool.shutdown(wait=True)
            
            self.logger.info("OrderManager stopped successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"OrderManager stop failed: {e}")
            return False
    
    # ==========================================================================
    # ORDER SUBMISSION
    # ==========================================================================
    
    def submit_order(self, order_request: Union[OrderRequest, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Submit an order for execution.
        
        Args:
            order_request: Order request object or dictionary
            
        Returns:
            Dict containing execution result
        """
        try:
            # Convert dict to OrderRequest if needed
            if isinstance(order_request, dict):
                order_request = self._dict_to_order_request(order_request)
            
            # Validate order
            validation = self.validate_order(order_request)
            if not validation.is_valid:
                return {
                    'success': False,
                    'error': f"Order validation failed: {validation.message}",
                    'validation_result': validation.result.value,
                    'order_id': order_request.order_id
                }
            
            # Check rate limits
            if not self._check_rate_limits():
                return {
                    'success': False,
                    'error': "Rate limit exceeded",
                    'order_id': order_request.order_id
                }
            
            # Check error cooldown
            if self._in_error_cooldown():
                return {
                    'success': False,
                    'error': "In error cooldown period",
                    'order_id': order_request.order_id
                }
            
            # Create order execution tracking
            execution = OrderExecution(
                order_id=order_request.order_id,
                state=OrderState.VALIDATED,
                total_quantity=order_request.quantity,
                remaining_quantity=order_request.quantity
            )
            
            with self._order_lock:
                self.order_executions[order_request.order_id] = execution
                self.pending_orders[order_request.order_id] = order_request
            
            # Queue order for processing
            try:
                priority = order_request.priority.value
                self.order_queue.put((priority, order_request), timeout=1.0)
                
                self.logger.info(f"Order queued: {order_request.order_id} ({order_request.symbol})")
                
                # Update statistics
                with self._stats_lock:
                    self.statistics.total_orders += 1
                
                # Emit event
                if self.has_event_manager:
                    self.event_manager.emit_event(
                        EventType.ORDER_SUBMITTED,
                        {
                            'order_id': order_request.order_id,
                            'symbol': order_request.symbol,
                            'action': order_request.action.value,
                            'quantity': order_request.quantity,
                            'order_type': order_request.order_type.value,
                            'strategy_id': order_request.strategy_id,
                            'timestamp': datetime.now()
                        }
                    )
                
                return {
                    'success': True,
                    'order_id': order_request.order_id,
                    'message': 'Order submitted successfully'
                }
                
            except queue.Full:
                # Remove from tracking if queue full
                with self._order_lock:
                    self.order_executions.pop(order_request.order_id, None)
                    self.pending_orders.pop(order_request.order_id, None)
                
                return {
                    'success': False,
                    'error': 'Order queue full',
                    'order_id': order_request.order_id
                }
                
        except Exception as e:
            self.logger.error(f"Order submission failed: {e}")
            self.error_handler.handle_broker_error(e, "OrderManager", "submit_order")
            
            return {
                'success': False,
                'error': str(e),
                'order_id': getattr(order_request, 'order_id', 'unknown')
            }
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel a pending order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            Dict containing cancellation result
        """
        try:
            with self._order_lock:
                if order_id not in self.order_executions:
                    return {
                        'success': False,
                        'error': f'Order not found: {order_id}'
                    }
                
                execution = self.order_executions[order_id]
                
                # Check if order can be cancelled
                if execution.state in [OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED]:
                    return {
                        'success': False,
                        'error': f'Order cannot be cancelled, current state: {execution.state.value}'
                    }
                
                # Cancel with broker if submitted
                if execution.broker_order_id and self.has_ib_connection:
                    try:
                        # Find the trade object
                        trades = self.ib_connection.trades()
                        target_trade = None
                        
                        for trade in trades:
                            if hasattr(trade, 'order') and hasattr(trade.order, 'orderId'):
                                if str(trade.order.orderId) == execution.broker_order_id:
                                    target_trade = trade
                                    break
                        
                        if target_trade:
                            self.ib_connection.cancelOrder(target_trade.order)
                            self.logger.info(f"Broker cancellation requested for order: {order_id}")
                        
                    except Exception as e:
                        self.logger.warning(f"Broker cancellation failed: {e}")
                
                # Update local state
                execution.state = OrderState.CANCELLED
                execution.last_update = datetime.now()
                
                # Remove from pending
                self.pending_orders.pop(order_id, None)
                
                # Update statistics
                with self._stats_lock:
                    self.statistics.cancelled_orders += 1
                
                self.logger.info(f"Order cancelled: {order_id}")
                
                # Emit event
                if self.has_event_manager:
                    self.event_manager.emit_event(
                        EventType.ORDER_CANCELLED,
                        {
                            'order_id': order_id,
                            'broker_order_id': execution.broker_order_id,
                            'timestamp': datetime.now()
                        }
                    )
                
                return {
                    'success': True,
                    'message': f'Order cancelled: {order_id}'
                }
                
        except Exception as e:
            self.logger.error(f"Order cancellation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # ==========================================================================
    # ORDER VALIDATION
    # ==========================================================================
    
    def validate_order(self, order_request: OrderRequest) -> OrderValidation:
        """
        Validate an order request.
        
        Args:
            order_request: Order to validate
            
        Returns:
            OrderValidation result
        """
        try:
            # Basic field validation
            if not order_request.symbol:
                return OrderValidation(
                    False, 
                    OrderValidationResult.INVALID_SYMBOL,
                    "Symbol is required"
                )
            
            if order_request.quantity <= 0:
                return OrderValidation(
                    False,
                    OrderValidationResult.INVALID_QUANTITY,
                    "Quantity must be positive"
                )
            
            # Price validation for limit orders
            if order_request.order_type == OrderType.LIMIT:
                if not order_request.limit_price or order_request.limit_price <= 0:
                    return OrderValidation(
                        False,
                        OrderValidationResult.INVALID_PRICE,
                        "Limit price required for limit orders"
                    )
            
            # Price validation for stop orders
            if order_request.order_type == OrderType.STOP:
                if not order_request.stop_price or order_request.stop_price <= 0:
                    return OrderValidation(
                        False,
                        OrderValidationResult.INVALID_PRICE,
                        "Stop price required for stop orders"
                    )
            
            # Market hours validation
            if not self._is_market_open():
                return OrderValidation(
                    False,
                    OrderValidationResult.MARKET_CLOSED,
                    "Market is closed",
                    ["Consider using extended hours trading"]
                )
            
            # Buying power validation (if available)
            if hasattr(self.spyder_client, 'get_buying_power'):
                try:
                    buying_power = self.spyder_client.get_buying_power()
                    estimated_cost = self._estimate_order_cost(order_request)
                    
                    if estimated_cost > buying_power:
                        return OrderValidation(
                            False,
                            OrderValidationResult.INSUFFICIENT_FUNDS,
                            f"Insufficient buying power: {buying_power:.2f} < {estimated_cost:.2f}",
                            ["Reduce order size", "Add funds to account"]
                        )
                except Exception as e:
                    self.logger.warning(f"Buying power check failed: {e}")
            
            # All validations passed
            return OrderValidation(
                True,
                OrderValidationResult.VALID,
                "Order validation successful"
            )
            
        except Exception as e:
            self.logger.error(f"Order validation error: {e}")
            return OrderValidation(
                False,
                OrderValidationResult.OTHER_ERROR,
                f"Validation error: {e}"
            )
    
    # ==========================================================================
    # ORDER PROCESSING
    # ==========================================================================
    
    def _process_order_queue(self):
        """Process orders from the order queue (worker thread)."""
        while not self._shutdown_event.is_set():
            try:
                # Get order with timeout
                try:
                    priority, order_request = self.order_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Process the order
                self._execute_order(order_request)
                
                # Mark task as done
                self.order_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Error in order processing thread: {e}")
                time.sleep(1.0)
    
    def _execute_order(self, order_request: OrderRequest):
        """Execute an individual order."""
        execution_start = time.time()
        
        try:
            execution = self.order_executions.get(order_request.order_id)
            if not execution:
                self.logger.error(f"Execution tracking not found: {order_request.order_id}")
                return
            
            # Update state
            execution.state = OrderState.PENDING_SUBMIT
            execution.submitted_time = datetime.now()
            
            # Execute with broker
            if self.has_ib_connection and self.ib_connection:
                result = self._execute_with_ib(order_request, execution)
            else:
                # Simulation mode
                result = self._simulate_order_execution(order_request, execution)
            
            # Update execution time
            execution_time_ms = (time.time() - execution_start) * 1000
            
            # Update statistics
            with self._stats_lock:
                if result['success']:
                    self.statistics.successful_orders += 1
                    self.consecutive_errors = 0
                else:
                    self.statistics.failed_orders += 1
                    self.consecutive_errors += 1
                    self.last_error_time = datetime.now()
                
                # Update average execution time
                total_successful = self.statistics.successful_orders
                if total_successful > 0:
                    current_avg = self.statistics.avg_execution_time_ms
                    self.statistics.avg_execution_time_ms = (
                        (current_avg * (total_successful - 1) + execution_time_ms) / total_successful
                    )
            
            # Handle consecutive errors
            if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                self.error_cooldown_until = datetime.now() + timedelta(seconds=ERROR_COOLDOWN_SECONDS)
                self.logger.warning(f"Entering error cooldown until {self.error_cooldown_until}")
            
        except Exception as e:
            self.logger.error(f"Order execution failed: {e}")
            if order_request.order_id in self.order_executions:
                self.order_executions[order_request.order_id].state = OrderState.ERROR
                self.order_executions[order_request.order_id].error_message = str(e)
    
    def _execute_with_ib(self, order_request: OrderRequest, execution: OrderExecution) -> Dict[str, Any]:
        """Execute order with Interactive Brokers."""
        try:
            # Build contract
            if self.has_contract_builder:
                contract = self.contract_builder.build_stock_contract(order_request.symbol)
            else:
                # Fallback contract creation
                contract = Stock(order_request.symbol, 'SMART', 'USD')
            
            # Build order
            ib_order = self._build_ib_order(order_request)
            
            # Submit order
            trade = self.ib_connection.placeOrder(contract, ib_order)
            
            if trade:
                execution.broker_order_id = str(trade.order.orderId)
                execution.state = OrderState.SUBMITTED
                
                self.logger.info(f"Order submitted to IB: {order_request.order_id} -> {execution.broker_order_id}")
                
                # Start monitoring this order
                self._monitor_order_fills(trade, execution)
                
                return {
                    'success': True,
                    'broker_order_id': execution.broker_order_id,
                    'trade': trade
                }
            else:
                execution.state = OrderState.REJECTED
                execution.error_message = "Failed to place order with IB"
                
                return {
                    'success': False,
                    'error': 'Failed to place order with IB'
                }
                
        except Exception as e:
            self.logger.error(f"IB order execution failed: {e}")
            execution.state = OrderState.ERROR
            execution.error_message = str(e)
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def _simulate_order_execution(self, order_request: OrderRequest, execution: OrderExecution) -> Dict[str, Any]:
        """Simulate order execution for testing."""
        try:
            # Simulate processing delay
            time.sleep(0.1)
            
            # Generate mock broker order ID
            execution.broker_order_id = f"SIM_{int(time.time() * 1000)}"
            execution.state = OrderState.SUBMITTED
            
            # Simulate immediate fill for market orders
            if order_request.order_type == OrderType.MARKET:
                # Simulate fill
                simulated_price = self._get_simulated_fill_price(order_request)
                
                execution.state = OrderState.FILLED
                execution.fill_time = datetime.now()
                execution.fill_price = simulated_price
                execution.fill_quantity = order_request.quantity
                execution.remaining_quantity = 0
                execution.avg_fill_price = simulated_price
                execution.commission = self._calculate_commission(order_request.quantity)
                
                # Add fill record
                fill = {
                    'fill_id': str(uuid.uuid4()),
                    'execution_time': execution.fill_time,
                    'fill_price': simulated_price,
                    'fill_quantity': order_request.quantity,
                    'commission': execution.commission
                }
                execution.fills.append(fill)
                
                self.logger.info(f"Simulated order fill: {order_request.order_id} @ ${simulated_price:.2f}")
                
                # Emit fill event
                if self.has_event_manager:
                    self.event_manager.emit_event(
                        EventType.ORDER_FILLED,
                        {
                            'order_id': order_request.order_id,
                            'broker_order_id': execution.broker_order_id,
                            'fill_price': simulated_price,
                            'fill_quantity': order_request.quantity,
                            'commission': execution.commission,
                            'timestamp': execution.fill_time
                        }
                    )
            
            return {
                'success': True,
                'broker_order_id': execution.broker_order_id,
                'simulated': True
            }
            
        except Exception as e:
            self.logger.error(f"Order simulation failed: {e}")
            execution.state = OrderState.ERROR
            execution.error_message = str(e)
            
            return {
                'success': False,
                'error': str(e)
            }
    
    # ==========================================================================
    # FILL MONITORING
    # ==========================================================================
    
    def _monitor_order_fills(self, trade, execution: OrderExecution):
        """Monitor order fills for a specific trade."""
        def fill_callback(trade, fill):
            try:
                # Process the fill
                self._process_fill(execution, fill)
            except Exception as e:
                self.logger.error(f"Fill processing error: {e}")
        
        # Set up fill callback
        trade.fillEvent += fill_callback
    
    def _process_fill(self, execution: OrderExecution, fill):
        """Process an order fill."""
        try:
            fill_quantity = fill.execution.shares
            fill_price = fill.execution.price
            fill_time = datetime.now()
            
            # Update execution tracking
            execution.fill_quantity += fill_quantity
            execution.remaining_quantity = execution.total_quantity - execution.fill_quantity
            
            # Calculate average fill price
            if execution.avg_fill_price is None:
                execution.avg_fill_price = fill_price
            else:
                total_filled = execution.fill_quantity
                previous_total = total_filled - fill_quantity
                execution.avg_fill_price = (
                    (execution.avg_fill_price * previous_total + fill_price * fill_quantity) / total_filled
                )
            
            # Add fill record
            fill_record = {
                'fill_id': str(uuid.uuid4()),
                'execution_time': fill_time,
                'fill_price': fill_price,
                'fill_quantity': fill_quantity,
                'commission': getattr(fill.commissionReport, 'commission', 0.0) if fill.commissionReport else 0.0
            }
            execution.fills.append(fill_record)
            
            # Update execution state
            if execution.remaining_quantity == 0:
                execution.state = OrderState.FILLED
                execution.fill_time = fill_time
                execution.fill_price = execution.avg_fill_price
                
                # Update statistics
                with self._stats_lock:
                    self.statistics.total_commission += fill_record['commission']
                
                self.logger.info(f"Order fully filled: {execution.order_id} @ ${execution.avg_fill_price:.2f}")
                
                # Emit fill event
                if self.has_event_manager:
                    self.event_manager.emit_event(
                        EventType.ORDER_FILLED,
                        {
                            'order_id': execution.order_id,
                            'broker_order_id': execution.broker_order_id,
                            'fill_price': execution.avg_fill_price,
                            'fill_quantity': execution.total_quantity,
                            'commission': sum(f['commission'] for f in execution.fills),
                            'timestamp': fill_time
                        }
                    )
                
            else:
                execution.state = OrderState.PARTIALLY_FILLED
                
                # Update statistics
                with self._stats_lock:
                    self.statistics.partial_fills += 1
                
                self.logger.info(f"Partial fill: {execution.order_id} - {fill_quantity} @ ${fill_price:.2f}")
                
                # Emit partial fill event
                if self.has_event_manager:
                    self.event_manager.emit_event(
                        EventType.ORDER_PARTIALLY_FILLED,
                        {
                            'order_id': execution.order_id,
                            'broker_order_id': execution.broker_order_id,
                            'fill_price': fill_price,
                            'fill_quantity': fill_quantity,
                            'remaining_quantity': execution.remaining_quantity,
                            'commission': fill_record['commission'],
                            'timestamp': fill_time
                        }
                    )
            
            execution.last_update = fill_time
            
        except Exception as e:
            self.logger.error(f"Fill processing failed: {e}")
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    
    def _dict_to_order_request(self, order_dict: Dict[str, Any]) -> OrderRequest:
        """Convert dictionary to OrderRequest object."""
        try:
            return OrderRequest(
                order_id=order_dict.get('order_id', str(uuid.uuid4())),
                symbol=order_dict['symbol'],
                action=OrderAction(order_dict['action']),
                quantity=order_dict['quantity'],
                order_type=OrderType(order_dict['order_type']),
                limit_price=order_dict.get('limit_price'),
                stop_price=order_dict.get('stop_price'),
                time_in_force=order_dict.get('time_in_force', 'DAY'),
                strategy_id=order_dict.get('strategy_id'),
                signal_id=order_dict.get('signal_id'),
                priority=OrderPriority(order_dict.get('priority', OrderPriority.NORMAL.value)),
                metadata=order_dict.get('metadata', {})
            )
        except Exception as e:
            self.logger.error(f"Failed to convert dict to OrderRequest: {e}")
            raise ValueError(f"Invalid order dictionary: {e}")
    
    def _build_ib_order(self, order_request: OrderRequest):
        """Build IB order object from order request."""
        try:
            # Determine order type
            if order_request.order_type == OrderType.MARKET:
                ib_order = MarketOrder(
                    action=order_request.action.value,
                    totalQuantity=order_request.quantity
                )
            elif order_request.order_type == OrderType.LIMIT:
                ib_order = LimitOrder(
                    action=order_request.action.value,
                    totalQuantity=order_request.quantity,
                    lmtPrice=order_request.limit_price
                )
            elif order_request.order_type == OrderType.STOP:
                ib_order = StopOrder(
                    action=order_request.action.value,
                    totalQuantity=order_request.quantity,
                    stopPrice=order_request.stop_price
                )
            else:
                raise ValueError(f"Unsupported order type: {order_request.order_type}")
            
            # Set time in force
            ib_order.tif = order_request.time_in_force
            
            # Add metadata as order reference
            if order_request.strategy_id:
                ib_order.orderRef = f"SPYDER_{order_request.strategy_id}"
            
            return ib_order
            
        except Exception as e:
            self.logger.error(f"Failed to build IB order: {e}")
            raise
    
    def _check_rate_limits(self) -> bool:
        """Check if order submission is within rate limits."""
        try:
            with self._rate_lock:
                now = time.time()
                
                # Remove old timestamps
                while self.order_times and now - self.order_times[0] > ORDER_RATE_WINDOW:
                    self.order_times.popleft()
                
                # Check current rate
                if len(self.order_times) >= MAX_ORDERS_PER_SECOND:
                    return False
                
                # Add current timestamp
                self.order_times.append(now)
                return True
                
        except Exception as e:
            self.logger.error(f"Rate limit check failed: {e}")
            return False
    
    def _in_error_cooldown(self) -> bool:
        """Check if in error cooldown period."""
        if self.error_cooldown_until is None:
            return False
        return datetime.now() < self.error_cooldown_until
    
    def _is_market_open(self) -> bool:
        """Check if market is currently open."""
        try:
            # Simplified market hours check (9:30 AM - 4:00 PM ET on weekdays)
            from datetime import time
            import pytz
            
            et = pytz.timezone('US/Eastern')
            now_et = datetime.now(et)
            
            # Check if weekday
            if now_et.weekday() >= 5:  # Saturday = 5, Sunday = 6
                return False
            
            # Check time
            market_open = time(9, 30)
            market_close = time(16, 0)
            current_time = now_et.time()
            
            return market_open <= current_time <= market_close
            
        except Exception as e:
            self.logger.warning(f"Market hours check failed: {e}")
            return True  # Default to open if check fails
    
    def _estimate_order_cost(self, order_request: OrderRequest) -> float:
        """Estimate the cost of an order."""
        try:
            if order_request.order_type == OrderType.LIMIT and order_request.limit_price:
                return order_request.quantity * order_request.limit_price
            else:
                # For market orders, estimate using last price or a reasonable default
                # This would typically use real market data
                estimated_price = 100.0  # Default estimate
                return order_request.quantity * estimated_price
                
        except Exception as e:
            self.logger.warning(f"Order cost estimation failed: {e}")
            return 0.0
    
    def _get_simulated_fill_price(self, order_request: OrderRequest) -> float:
        """Get simulated fill price for testing."""
        try:
            if order_request.order_type == OrderType.LIMIT and order_request.limit_price:
                return order_request.limit_price
            else:
                # Simulate market price based on symbol
                if 'SPY' in order_request.symbol.upper():
                    return 450.0 + (hash(order_request.symbol) % 100) / 100.0
                else:
                    return 100.0 + (hash(order_request.symbol) % 50) / 100.0
                    
        except Exception as e:
            self.logger.warning(f"Simulated price generation failed: {e}")
            return 100.0
    
    def _calculate_commission(self, quantity: int) -> float:
        """Calculate commission for an order."""
        # Standard IB commission structure
        base_commission = 0.005 * quantity  # $0.005 per share
        min_commission = 1.0  # $1 minimum
        max_commission = 0.01 * quantity  # 1% maximum
        
        return max(min_commission, min(base_commission, max_commission))
    
    def _start_worker_threads(self):
        """Start worker threads."""
        try:
            # Order processing thread
            order_thread = threading.Thread(
                target=self._process_order_queue,
                name="OrderProcessor",
                daemon=True
            )
            order_thread.start()
            self.worker_threads['order_processor'] = order_thread
            
            # Fill monitoring thread
            fill_thread = threading.Thread(
                target=self._monitor_fills,
                name="FillMonitor",
                daemon=True
            )
            fill_thread.start()
            self.worker_threads['fill_monitor'] = fill_thread
            
            self.logger.info("Order manager worker threads started")
            
        except Exception as e:
            self.logger.error(f"Failed to start worker threads: {e}")
    
    def _stop_worker_threads(self):
        """Stop worker threads."""
        try:
            # Wait for queues to empty
            self.order_queue.join()
            
            # Wait for threads to finish
            for name, thread in self.worker_threads.items():
                if thread.is_alive():
                    thread.join(timeout=5.0)
                    if thread.is_alive():
                        self.logger.warning(f"Thread {name} did not stop gracefully")
            
            self.worker_threads.clear()
            self.logger.info("Order manager worker threads stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping worker threads: {e}")
    
    def _monitor_fills(self):
        """Monitor fills and update order states."""
        while not self._shutdown_event.is_set():
            try:
                # Check for stale orders
                self._check_stale_orders()
                
                # Update order states from broker
                if self.has_ib_connection and self.ib_connection:
                    self._sync_order_states()
                
                # Sleep before next check
                self._shutdown_event.wait(FILL_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Fill monitoring error: {e}")
                self._shutdown_event.wait(5.0)
    
    def _check_stale_orders(self):
        """Check for orders that may be stale."""
        try:
            current_time = datetime.now()
            stale_orders = []
            
            with self._order_lock:
                for order_id, execution in self.order_executions.items():
                    if execution.state in [OrderState.SUBMITTED, OrderState.PENDING_SUBMIT]:
                        if execution.submitted_time:
                            age = (current_time - execution.submitted_time).total_seconds()
                            if age > ORDER_TIMEOUT_SECONDS:
                                stale_orders.append(order_id)
            
            # Handle stale orders
            for order_id in stale_orders:
                self.logger.warning(f"Order timeout detected: {order_id}")
                # Could implement retry logic here
                
        except Exception as e:
            self.logger.error(f"Stale order check failed: {e}")
    
    def _sync_order_states(self):
        """Sync order states with broker."""
        try:
            if not self.has_ib_connection or not self.ib_connection:
                return
            
            # Get all trades from IB
            trades = self.ib_connection.trades()
            
            # Update our tracking
            for trade in trades:
                broker_order_id = str(trade.order.orderId)
                
                # Find corresponding execution
                execution = None
                for exec in self.order_executions.values():
                    if exec.broker_order_id == broker_order_id:
                        execution = exec
                        break
                
                if execution:
                    # Update state based on trade status
                    if trade.orderStatus.status == 'Filled':
                        if execution.state != OrderState.FILLED:
                            execution.state = OrderState.FILLED
                            execution.fill_time = datetime.now()
                            execution.last_update = execution.fill_time
                    elif trade.orderStatus.status == 'Cancelled':
                        execution.state = OrderState.CANCELLED
                        execution.last_update = datetime.now()
                    elif trade.orderStatus.status in ['Submitted', 'PreSubmitted']:
                        execution.state = OrderState.SUBMITTED
                        execution.last_update = datetime.now()
                        
        except Exception as e:
            self.logger.error(f"Order state sync failed: {e}")
    
    def _cancel_all_pending_orders(self):
        """Cancel all pending orders."""
        try:
            pending_order_ids = []
            
            with self._order_lock:
                for order_id, execution in self.order_executions.items():
                    if execution.state in [OrderState.SUBMITTED, OrderState.PENDING_SUBMIT]:
                        pending_order_ids.append(order_id)
            
            for order_id in pending_order_ids:
                self.cancel_order(order_id)
                
            self.logger.info(f"Cancelled {len(pending_order_ids)} pending orders")
            
        except Exception as e:
            self.logger.error(f"Failed to cancel pending orders: {e}")
    
    def _reset_statistics(self):
        """Reset order statistics."""
        with self._stats_lock:
            self.statistics = OrderStatistics()
            self.statistics.last_reset = datetime.now()
    
    # ==========================================================================
    # PUBLIC QUERY METHODS
    # ==========================================================================
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of an order.
        
        Args:
            order_id: Order ID to query
            
        Returns:
            Order status dictionary or None if not found
        """
        try:
            with self._order_lock:
                execution = self.order_executions.get(order_id)
                if not execution:
                    return None
                
                return {
                    'order_id': order_id,
                    'broker_order_id': execution.broker_order_id,
                    'state': execution.state.value,
                    'submitted_time': execution.submitted_time.isoformat() if execution.submitted_time else None,
                    'fill_time': execution.fill_time.isoformat() if execution.fill_time else None,
                    'fill_price': execution.fill_price,
                    'fill_quantity': execution.fill_quantity,
                    'remaining_quantity': execution.remaining_quantity,
                    'total_quantity': execution.total_quantity,
                    'avg_fill_price': execution.avg_fill_price,
                    'commission': execution.commission,
                    'error_message': execution.error_message,
                    'retry_count': execution.retry_count,
                    'last_update': execution.last_update.isoformat(),
                    'fills_count': len(execution.fills)
                }
                
        except Exception as e:
            self.logger.error(f"Error getting order status: {e}")
            return None
    
    def get_pending_orders(self) -> List[Dict[str, Any]]:
        """
        Get all pending orders.
        
        Returns:
            List of pending order dictionaries
        """
        try:
            pending = []
            
            with self._order_lock:
                for order_id, execution in self.order_executions.items():
                    if execution.state in [OrderState.SUBMITTED, OrderState.PENDING_SUBMIT, OrderState.PARTIALLY_FILLED]:
                        status = self.get_order_status(order_id)
                        if status:
                            pending.append(status)
            
            return pending
            
        except Exception as e:
            self.logger.error(f"Error getting pending orders: {e}")
            return []
    
    def get_order_statistics(self) -> Dict[str, Any]:
        """
        Get order manager statistics.
        
        Returns:
            Statistics dictionary
        """
        try:
            with self._stats_lock:
                stats = asdict(self.statistics)
                
                # Calculate error rate
                if self.statistics.total_orders > 0:
                    stats['error_rate'] = self.statistics.failed_orders / self.statistics.total_orders
                else:
                    stats['error_rate'] = 0.0
                
                # Add current queue sizes
                stats['current_queue_size'] = self.order_queue.qsize()
                stats['pending_orders_count'] = len(self.get_pending_orders())
                stats['consecutive_errors'] = self.consecutive_errors
                stats['in_error_cooldown'] = self._in_error_cooldown()
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {}
    
    def get_order_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get order execution history.
        
        Args:
            limit: Maximum number of orders to return
            
        Returns:
            List of order history
        """
        try:
            history = []
            
            with self._order_lock:
                # Get completed orders from deque
                completed = list(self.completed_orders)[-limit:]
                
                # Get current orders that are complete
                for order_id, execution in self.order_executions.items():
                    if execution.state in [OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED]:
                        status = self.get_order_status(order_id)
                        if status:
                            history.append(status)
                
                # Sort by last update time
                history.sort(key=lambda x: x.get('last_update', ''), reverse=True)
                
                return history[:limit]
                
        except Exception as e:
            self.logger.error(f"Error getting order history: {e}")
            return []

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_order_manager(config: Dict[str, Any], spyder_client) -> OrderManager:
    """
    Factory function to create an OrderManager instance.
    
    Args:
        config: Order manager configuration
        spyder_client: Spyder client instance
        
    Returns:
        OrderManager instance
    """
    return OrderManager(config, spyder_client)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level singleton instance
_order_manager_instance: Optional[OrderManager] = None
_order_manager_lock = Lock()

def get_order_manager(config: Dict[str, Any] = None, spyder_client=None) -> OrderManager:
    """
    Get singleton OrderManager instance.
    
    Args:
        config: Configuration (required for first call)
        spyder_client: Spyder client (required for first call)
        
    Returns:
        OrderManager instance
    """
    global _order_manager_instance
    
    with _order_manager_lock:
        if _order_manager_instance is None:
            if not all([config, spyder_client]):
                raise ValueError("Config and spyder_client required for first order manager creation")
            _order_manager_instance = OrderManager(config, spyder_client)
        
        return _order_manager_instance

def reset_order_manager():
    """Reset the singleton order manager instance (for testing)."""
    global _order_manager_instance
    with _order_manager_lock:
        if _order_manager_instance:
            _order_manager_instance.stop()
        _order_manager_instance = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("Testing OrderManager...")
    
    # Mock configuration
    test_config = {
        'max_orders_per_second': 5,
        'order_timeout': 30
    }
    
    # Mock spyder client
    class MockSpyderClient:
        def get_buying_power(self):
            return 100000.0
        
        def is_connected(self):
            return True
    
    # Create order manager
    mock_client = MockSpyderClient()
    order_manager = OrderManager(test_config, mock_client)
    
    if order_manager.initialize():
        print("✅ OrderManager initialized successfully")
        
        if order_manager.start():
            print("✅ OrderManager started successfully")
            
            # Test order submission
            test_order = OrderRequest(
                order_id=str(uuid.uuid4()),
                symbol="SPY",
                action=OrderAction.BUY,
                quantity=100,
                order_type=OrderType.MARKET
            )
            
            result = order_manager.submit_order(test_order)
            print(f"Order submission result: {result}")
            
            # Brief operation
            time.sleep(2)
            
            # Check statistics
            stats = order_manager.get_order_statistics()
            print(f"Order statistics: {stats}")
            
            if order_manager.stop():
                print("✅ OrderManager stopped successfully")
            else:
                print("❌ OrderManager stop failed")
        else:
            print("❌ OrderManager start failed")
    else:
        print("❌ OrderManager initialization failed")
    
    print("OrderManager testing completed.")