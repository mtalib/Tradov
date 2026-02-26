#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB02_OrderManager.py
Purpose: Order management orchestration via Tradier API

Author: SPYDER Trading System
Year Created: 2025
Last Updated: 2026-02-25 Time: 18:00:00

Module Description:
    High-level order management layer built on top of SpyderB40_TradierClient.
    Provides order tracking, state persistence, multileg/options support,
    and real-time fill updates via Tradier SSE streaming.

    This module acts as an orchestration layer between:
    - Strategy modules (D-series) that generate order requests
    - Risk management (E-series) that validates orders
    - TradierClient (B40) that executes orders via REST API
    - GUI components (G-series) that display order state

    KEY FEATURES:
    - Thin delegation to TradierClient for all order execution
    - In-memory order tracking with thread-safe state management
    - Optional SSE streaming for real-time fill/cancel notifications
    - Order state persistence to disk (JSON)
    - Support for equity, option, multileg, Iron Condor, and credit spread orders
    - Sync and async interfaces
    - Backward-compatible with consumers importing Order, OrderState, etc.

Module Constants:
    DEFAULT_ORDER_TIMEOUT (float): Default order timeout in seconds (default: 30.0)
    ORDER_STATE_PERSISTENCE_INTERVAL (int): Interval for saving state in seconds (default: 60)
    TRADIER_STATUS_MAP (dict): Mapping from Tradier status strings to OrderState enum

Change Log:
    2026-02-25 (v2.0.0):
        - Complete rewrite: replaced dead ConnectAPI with TradierClient
        - Added multileg, iron condor, credit spread order delegation
        - Added SSE streaming integration for real-time fills
        - Added sync + async order methods
        - Added modify_order() support
        - Consolidated enums with B40 (import + alias)
        - Added OrderStatus alias for backward compatibility
        - Kept order persistence and metrics

    2025-10-20 (v1.0.0):
        - Initial module creation with ConnectAPI (now removed)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import time
import threading
import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from pathlib import Path
from threading import RLock, Event as ThreadEvent

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Import TradierClient and its enums — the actual execution layer
from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
    TradierClient,
    OrderSide as TradierOrderSide,
    OrderType as TradierOrderType,
    OrderDuration as TradierOrderDuration,
    OrderClass as TradierOrderClass,
    OptionLeg,
    TradierAPIError,
    TradierAccountStream,
    AccountEvent,
    build_option_symbol,
    create_tradier_client_from_env,
)

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_ORDER_TIMEOUT = 30.0
ORDER_STATE_PERSISTENCE_INTERVAL = 60  # seconds

# Tradier order status string → OrderState mapping
TRADIER_STATUS_MAP: Dict[str, "OrderState"] = {}  # populated after OrderState defined

# ==============================================================================
# ENUMS
# ==============================================================================


class OrderState(Enum):
    """Order lifecycle states."""
    PENDING = auto()           # Created locally, not yet submitted
    SUBMITTED = auto()         # Sent to Tradier
    OPEN = auto()              # Acknowledged by exchange
    PARTIALLY_FILLED = auto()  # Partial fill received
    FILLED = auto()            # Fully filled
    CANCELLED = auto()         # Cancelled
    REJECTED = auto()          # Rejected by broker/exchange
    EXPIRED = auto()           # Expired (end of duration)
    PENDING_CANCEL = auto()    # Cancel request sent
    ERROR = auto()             # Internal error
    UNKNOWN = auto()           # Unmapped status

    @property
    def is_active(self) -> bool:
        """True if order is still live (could fill or cancel)."""
        return self in {
            OrderState.SUBMITTED,
            OrderState.OPEN,
            OrderState.PARTIALLY_FILLED,
            OrderState.PENDING_CANCEL,
        }

    @property
    def is_terminal(self) -> bool:
        """True if order has reached a final state."""
        return self in {
            OrderState.FILLED,
            OrderState.CANCELLED,
            OrderState.REJECTED,
            OrderState.EXPIRED,
            OrderState.ERROR,
        }


# Backward-compat alias — some consumers import OrderStatus
OrderStatus = OrderState

# Populate the Tradier→OrderState mapping
TRADIER_STATUS_MAP = {
    "pending": OrderState.SUBMITTED,
    "open": OrderState.OPEN,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "filled": OrderState.FILLED,
    "expired": OrderState.EXPIRED,
    "canceled": OrderState.CANCELLED,
    "rejected": OrderState.REJECTED,
}


class SecurityType(Enum):
    """Security type for order routing."""
    EQUITY = "equity"
    OPTION = "option"
    MULTILEG = "multileg"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class Order:
    """
    Order representation for the Spyder trading system.

    This dataclass carries all information needed to place, track, and
    persist an order throughout its lifecycle.
    """
    # Identity
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tradier_order_id: Optional[int] = None  # Tradier's integer order ID

    # Core order fields
    symbol: str = ""
    side: str = "buy"                        # Tradier-style: buy, sell, buy_to_open, etc.
    order_type: str = "market"               # Tradier-style: market, limit, stop, stop_limit
    quantity: int = 0
    price: Optional[float] = None            # Limit price
    stop_price: Optional[float] = None       # Stop price
    duration: str = "day"                     # day, gtc, pre, post

    # Security classification
    security_type: SecurityType = SecurityType.EQUITY
    order_class: str = "equity"              # equity, option, multileg, combo
    option_symbol: Optional[str] = None      # OCC-format option symbol

    # Options fields (for single-leg option orders)
    expiry: Optional[str] = None             # YYYY-MM-DD
    strike: Optional[float] = None
    right: Optional[str] = None              # "call" or "put"

    # Multi-leg support
    legs: List[OptionLeg] = field(default_factory=list)

    # State tracking
    state: OrderState = field(default=OrderState.PENDING)
    submitted_time: Optional[datetime] = None
    filled_quantity: int = 0
    remaining_quantity: int = 0
    average_fill_price: float = 0.0
    last_fill_price: float = 0.0
    last_fill_time: Optional[datetime] = None

    # Error / warning tracking
    error_message: Optional[str] = None
    warning_message: Optional[str] = None

    # Metadata
    strategy_name: Optional[str] = None
    tag: Optional[str] = None               # Tradier order tag

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Set remaining_quantity from quantity if not set."""
        if self.remaining_quantity == 0 and self.quantity > 0:
            self.remaining_quantity = self.quantity
        # Normalise security_type
        if isinstance(self.security_type, str):
            try:
                self.security_type = SecurityType(self.security_type.lower())
            except ValueError:
                self.security_type = SecurityType.EQUITY


# Backward-compat alias — __init__.py tries to import OrderRequest
OrderRequest = Order


@dataclass
class OrderResult:
    """Result of an order operation (submit / cancel / modify)."""
    success: bool
    order_id: str
    tradier_order_id: Optional[int] = None
    operation: str = ""          # submit, cancel, modify
    message: Optional[str] = None
    error_code: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ExecutionReport:
    """Execution / fill report."""
    order_id: str
    tradier_order_id: Optional[int] = None
    symbol: str = ""
    side: str = ""
    quantity: int = 0
    price: float = 0.0
    execution_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    commission: Optional[float] = None

# ==============================================================================
# MAIN CLASS
# ==============================================================================


class OrderManager:
    """
    Order management orchestration layer built on TradierClient.

    This class provides:
    - High-level order submission (equity, option, multileg)
    - In-memory order state tracking (thread-safe)
    - Real-time fill/cancel updates via Tradier SSE streaming (optional)
    - Order state persistence to disk
    - Metrics tracking (submitted, filled, cancelled, rejected)

    All actual REST calls delegate to ``TradierClient`` (B40).

    Attributes:
        tradier: TradierClient instance for REST API calls.
        _orders: Thread-safe in-memory order store.
        _sse_stream: Optional Tradier account event stream.
    """

    def __init__(
        self,
        tradier_client: Optional[TradierClient] = None,
        enable_streaming: bool = False,
    ):
        """
        Initialize the order manager.

        Args:
            tradier_client: TradierClient instance. If ``None``, one is
                created automatically from environment variables.
            enable_streaming: If ``True``, start SSE streaming for
                real-time order fill/cancel notifications.
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # Tradier API client — the execution engine
        self.tradier: TradierClient = tradier_client or create_tradier_client_from_env()

        # Order tracking
        self._orders: Dict[str, Order] = {}
        self._order_lock = RLock()
        self._shutdown_event = ThreadEvent()

        # Callbacks for external listeners (GUI, risk manager, etc.)
        self._on_fill_callbacks: List[Callable[[Order, ExecutionReport], None]] = []
        self._on_state_change_callbacks: List[Callable[[Order, OrderState], None]] = []

        # SSE streaming for real-time fills
        self._sse_stream: Optional[TradierAccountStream] = None
        self._streaming_enabled = enable_streaming

        # State persistence
        self._persistence_thread: Optional[threading.Thread] = None
        self._persistence_enabled = True
        self._persistence_dir = Path("data/order_state")

        # Metrics
        self.metrics: Dict[str, Any] = {
            "orders_submitted": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_rejected": 0,
            "total_volume": 0.0,
            "total_commission": 0.0,
            "start_time": datetime.now(),
        }

        self.logger.info("OrderManager initialized (Tradier API)")

    # ==========================================================================
    # LIFECYCLE
    # ==========================================================================

    def start(self):
        """Start the order manager (persistence + optional SSE streaming)."""
        self.start_persistence()
        if self._streaming_enabled:
            self._start_sse_stream()
        self.logger.info("OrderManager started")

    def stop(self):
        """Stop the order manager gracefully."""
        self.logger.info("Stopping OrderManager...")
        self._shutdown_event.set()
        self._stop_sse_stream()
        self.stop_persistence()
        self.logger.info("OrderManager stopped")

    # ==========================================================================
    # ORDER SUBMISSION — SYNC
    # ==========================================================================

    def submit_order(self, order: Order) -> OrderResult:
        """
        Submit an order to Tradier.

        Routes to the appropriate TradierClient method based on
        ``order.security_type`` and ``order.legs``.

        Args:
            order: Order to submit.

        Returns:
            OrderResult with success/failure and Tradier order ID.
        """
        try:
            with self._order_lock:
                # Prevent duplicates
                if order.order_id in self._orders:
                    return OrderResult(
                        success=False,
                        order_id=order.order_id,
                        operation="submit",
                        message="Duplicate order ID",
                        error_code="DUPLICATE_ORDER_ID",
                    )

                order.state = OrderState.SUBMITTED
                order.submitted_time = datetime.now()
                order.updated_at = datetime.now()
                self._orders[order.order_id] = order

            self.logger.info(
                f"Submitting order {order.order_id}: "
                f"{order.side} {order.quantity} {order.symbol} "
                f"@ {order.price or 'MKT'}"
            )

            # Route to correct Tradier method
            response = self._route_order(order)

            # Extract Tradier order ID from response
            tradier_id = self._extract_order_id(response)

            with self._order_lock:
                if tradier_id:
                    order.tradier_order_id = tradier_id
                    order.state = OrderState.OPEN
                    self.metrics["orders_submitted"] += 1
                else:
                    order.state = OrderState.REJECTED
                    order.error_message = "No order ID in response"
                    self.metrics["orders_rejected"] += 1

                order.updated_at = datetime.now()

            success = tradier_id is not None
            return OrderResult(
                success=success,
                order_id=order.order_id,
                tradier_order_id=tradier_id,
                operation="submit",
                message="Order submitted" if success else "Submission failed",
                raw_response=response,
            )

        except TradierAPIError as e:
            return self._handle_submission_error(order, e)
        except Exception as e:
            self.logger.error(f"Order submission failed: {e}", exc_info=True)
            return self._handle_submission_error(order, e)

    def cancel_order(self, order_id: str) -> OrderResult:
        """
        Cancel an order by its local order ID.

        Args:
            order_id: Local order ID (UUID).

        Returns:
            OrderResult with cancellation outcome.
        """
        try:
            with self._order_lock:
                order = self._orders.get(order_id)
                if not order:
                    return OrderResult(
                        success=False,
                        order_id=order_id,
                        operation="cancel",
                        message="Order not found",
                        error_code="ORDER_NOT_FOUND",
                    )

                if not order.state.is_active:
                    return OrderResult(
                        success=False,
                        order_id=order_id,
                        operation="cancel",
                        message=f"Cannot cancel order in state {order.state.name}",
                        error_code="INVALID_STATE",
                    )

                if not order.tradier_order_id:
                    return OrderResult(
                        success=False,
                        order_id=order_id,
                        operation="cancel",
                        message="No Tradier order ID",
                        error_code="NO_TRADIER_ID",
                    )

                order.state = OrderState.PENDING_CANCEL
                order.updated_at = datetime.now()

            self.logger.info(f"Cancelling order {order_id} (Tradier #{order.tradier_order_id})")

            response = self.tradier.cancel_order(order.tradier_order_id)

            with self._order_lock:
                order.state = OrderState.CANCELLED
                order.updated_at = datetime.now()
                self.metrics["orders_cancelled"] += 1

            return OrderResult(
                success=True,
                order_id=order_id,
                tradier_order_id=order.tradier_order_id,
                operation="cancel",
                message="Order cancelled",
                raw_response=response,
            )

        except TradierAPIError as e:
            self.logger.error(f"Cancel failed for {order_id}: {e}")
            with self._order_lock:
                if order_id in self._orders:
                    self._orders[order_id].warning_message = str(e)
                    # Revert to previous active state if cancel failed
                    if self._orders[order_id].state == OrderState.PENDING_CANCEL:
                        self._orders[order_id].state = OrderState.OPEN
            return OrderResult(
                success=False,
                order_id=order_id,
                operation="cancel",
                message=str(e),
                error_code="CANCEL_FAILED",
            )

    def modify_order(
        self,
        order_id: str,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        order_type: Optional[str] = None,
        duration: Optional[str] = None,
    ) -> OrderResult:
        """
        Modify an existing order.

        Args:
            order_id: Local order ID.
            price: New limit price.
            stop_price: New stop price.
            order_type: New order type.
            duration: New duration.

        Returns:
            OrderResult with modification outcome.
        """
        try:
            with self._order_lock:
                order = self._orders.get(order_id)
                if not order:
                    return OrderResult(
                        success=False,
                        order_id=order_id,
                        operation="modify",
                        message="Order not found",
                        error_code="ORDER_NOT_FOUND",
                    )

                if not order.state.is_active:
                    return OrderResult(
                        success=False,
                        order_id=order_id,
                        operation="modify",
                        message=f"Cannot modify order in state {order.state.name}",
                        error_code="INVALID_STATE",
                    )

                if not order.tradier_order_id:
                    return OrderResult(
                        success=False,
                        order_id=order_id,
                        operation="modify",
                        message="No Tradier order ID",
                        error_code="NO_TRADIER_ID",
                    )

            self.logger.info(f"Modifying order {order_id} (Tradier #{order.tradier_order_id})")

            response = self.tradier.modify_order(
                order_id=order.tradier_order_id,
                order_type=order_type,
                duration=duration,
                price=price,
                stop=stop_price,
            )

            # Update local order fields
            with self._order_lock:
                if price is not None:
                    order.price = price
                if stop_price is not None:
                    order.stop_price = stop_price
                if order_type:
                    order.order_type = order_type
                if duration:
                    order.duration = duration
                order.updated_at = datetime.now()

            return OrderResult(
                success=True,
                order_id=order_id,
                tradier_order_id=order.tradier_order_id,
                operation="modify",
                message="Order modified",
                raw_response=response,
            )

        except TradierAPIError as e:
            self.logger.error(f"Modify failed for {order_id}: {e}")
            return OrderResult(
                success=False,
                order_id=order_id,
                operation="modify",
                message=str(e),
                error_code="MODIFY_FAILED",
            )

    # ==========================================================================
    # ORDER SUBMISSION — ASYNC
    # ==========================================================================

    async def submit_order_async(self, order: Order) -> OrderResult:
        """
        Submit an order asynchronously.

        Delegates to the sync ``submit_order`` via ``run_in_executor``
        so that the event loop is not blocked by the REST call.

        Args:
            order: Order to submit.

        Returns:
            OrderResult.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.submit_order, order)

    async def cancel_order_async(self, order_id: str) -> OrderResult:
        """Cancel an order asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.cancel_order, order_id)

    async def modify_order_async(
        self,
        order_id: str,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        order_type: Optional[str] = None,
        duration: Optional[str] = None,
    ) -> OrderResult:
        """Modify an order asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.modify_order, order_id, price, stop_price, order_type, duration
        )

    # ==========================================================================
    # CONVENIENCE — MULTILEG / STRATEGY ORDERS
    # ==========================================================================

    def submit_multileg_order(
        self,
        symbol: str,
        legs: List[OptionLeg],
        order_type: str = "market",
        duration: str = "day",
        price: Optional[float] = None,
        tag: Optional[str] = None,
        strategy_name: Optional[str] = None,
    ) -> OrderResult:
        """
        Submit a multileg options order.

        Args:
            symbol: Underlying symbol (e.g., "SPY").
            legs: List of OptionLeg objects.
            order_type: "market", "debit", "credit", "even".
            duration: "day" or "gtc".
            price: Net debit/credit price.
            tag: Tradier order tag.
            strategy_name: Strategy name for tracking.

        Returns:
            OrderResult.
        """
        order = Order(
            symbol=symbol,
            side="multileg",
            order_type=order_type,
            quantity=legs[0].quantity if legs else 1,
            price=price,
            duration=duration,
            security_type=SecurityType.MULTILEG,
            order_class="multileg",
            legs=list(legs),
            tag=tag,
            strategy_name=strategy_name,
        )

        try:
            with self._order_lock:
                order.state = OrderState.SUBMITTED
                order.submitted_time = datetime.now()
                self._orders[order.order_id] = order

            self.logger.info(
                f"Submitting multileg order {order.order_id}: "
                f"{len(legs)} legs on {symbol}"
            )

            response = self.tradier.place_multileg_order(
                symbol=symbol,
                legs=legs,
                order_type=order_type,
                duration=TradierOrderDuration(duration),
                price=price,
                tag=tag,
            )

            tradier_id = self._extract_order_id(response)

            with self._order_lock:
                if tradier_id:
                    order.tradier_order_id = tradier_id
                    order.state = OrderState.OPEN
                    self.metrics["orders_submitted"] += 1
                else:
                    order.state = OrderState.REJECTED
                    self.metrics["orders_rejected"] += 1
                order.updated_at = datetime.now()

            return OrderResult(
                success=tradier_id is not None,
                order_id=order.order_id,
                tradier_order_id=tradier_id,
                operation="submit_multileg",
                message="Multileg order submitted" if tradier_id else "Submission failed",
                raw_response=response,
            )

        except Exception as e:
            self.logger.error(f"Multileg order failed: {e}", exc_info=True)
            return self._handle_submission_error(order, e)

    def submit_iron_condor(
        self,
        symbol: str,
        expiration: str,
        put_buy_strike: float,
        put_sell_strike: float,
        call_sell_strike: float,
        call_buy_strike: float,
        quantity: int = 1,
        price: Optional[float] = None,
        duration: str = "day",
        strategy_name: Optional[str] = None,
    ) -> OrderResult:
        """
        Submit an Iron Condor order (4-leg).

        Args:
            symbol: Underlying symbol.
            expiration: Expiration date (YYYY-MM-DD).
            put_buy_strike: Long put strike (lowest).
            put_sell_strike: Short put strike.
            call_sell_strike: Short call strike.
            call_buy_strike: Long call strike (highest).
            quantity: Number of contracts per leg.
            price: Net credit price.
            duration: Time-in-force.
            strategy_name: Strategy name for tracking.

        Returns:
            OrderResult.
        """
        order = Order(
            symbol=symbol,
            side="iron_condor",
            order_type="credit",
            quantity=quantity,
            price=price,
            duration=duration,
            security_type=SecurityType.MULTILEG,
            order_class="multileg",
            expiry=expiration,
            strategy_name=strategy_name or "iron_condor",
        )

        try:
            with self._order_lock:
                order.state = OrderState.SUBMITTED
                order.submitted_time = datetime.now()
                self._orders[order.order_id] = order

            self.logger.info(
                f"Submitting Iron Condor {order.order_id}: "
                f"{symbol} {expiration} "
                f"P{put_buy_strike}/{put_sell_strike} "
                f"C{call_sell_strike}/{call_buy_strike}"
            )

            response = self.tradier.place_iron_condor(
                symbol=symbol,
                expiration=expiration,
                put_buy_strike=put_buy_strike,
                put_sell_strike=put_sell_strike,
                call_sell_strike=call_sell_strike,
                call_buy_strike=call_buy_strike,
                quantity=quantity,
                price=price,
                duration=TradierOrderDuration(duration),
            )

            tradier_id = self._extract_order_id(response)

            with self._order_lock:
                if tradier_id:
                    order.tradier_order_id = tradier_id
                    order.state = OrderState.OPEN
                    self.metrics["orders_submitted"] += 1
                else:
                    order.state = OrderState.REJECTED
                    self.metrics["orders_rejected"] += 1
                order.updated_at = datetime.now()

            return OrderResult(
                success=tradier_id is not None,
                order_id=order.order_id,
                tradier_order_id=tradier_id,
                operation="submit_iron_condor",
                raw_response=response,
            )

        except Exception as e:
            self.logger.error(f"Iron Condor order failed: {e}", exc_info=True)
            return self._handle_submission_error(order, e)

    def submit_credit_spread(
        self,
        symbol: str,
        expiration: str,
        sell_strike: float,
        buy_strike: float,
        option_type: str = "P",
        quantity: int = 1,
        price: Optional[float] = None,
        duration: str = "day",
        strategy_name: Optional[str] = None,
    ) -> OrderResult:
        """
        Submit a credit spread order (2-leg).

        Args:
            symbol: Underlying symbol.
            expiration: Expiration date (YYYY-MM-DD).
            sell_strike: Short strike.
            buy_strike: Long strike.
            option_type: "P" for put spread, "C" for call spread.
            quantity: Number of contracts per leg.
            price: Net credit price.
            duration: Time-in-force.
            strategy_name: Strategy name for tracking.

        Returns:
            OrderResult.
        """
        spread_type = "put_credit_spread" if option_type == "P" else "call_credit_spread"
        order = Order(
            symbol=symbol,
            side=spread_type,
            order_type="credit",
            quantity=quantity,
            price=price,
            duration=duration,
            security_type=SecurityType.MULTILEG,
            order_class="multileg",
            expiry=expiration,
            strike=sell_strike,
            right=option_type.lower(),
            strategy_name=strategy_name or spread_type,
        )

        try:
            with self._order_lock:
                order.state = OrderState.SUBMITTED
                order.submitted_time = datetime.now()
                self._orders[order.order_id] = order

            self.logger.info(
                f"Submitting credit spread {order.order_id}: "
                f"{symbol} {expiration} {option_type} "
                f"sell={sell_strike} buy={buy_strike}"
            )

            response = self.tradier.place_credit_spread(
                symbol=symbol,
                expiration=expiration,
                sell_strike=sell_strike,
                buy_strike=buy_strike,
                option_type=option_type,
                quantity=quantity,
                price=price,
                duration=TradierOrderDuration(duration),
            )

            tradier_id = self._extract_order_id(response)

            with self._order_lock:
                if tradier_id:
                    order.tradier_order_id = tradier_id
                    order.state = OrderState.OPEN
                    self.metrics["orders_submitted"] += 1
                else:
                    order.state = OrderState.REJECTED
                    self.metrics["orders_rejected"] += 1
                order.updated_at = datetime.now()

            return OrderResult(
                success=tradier_id is not None,
                order_id=order.order_id,
                tradier_order_id=tradier_id,
                operation="submit_credit_spread",
                raw_response=response,
            )

        except Exception as e:
            self.logger.error(f"Credit spread order failed: {e}", exc_info=True)
            return self._handle_submission_error(order, e)

    # ==========================================================================
    # ORDER QUERIES
    # ==========================================================================

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by local ID."""
        with self._order_lock:
            return self._orders.get(order_id)

    def get_order_by_tradier_id(self, tradier_id: int) -> Optional[Order]:
        """Get order by Tradier order ID."""
        with self._order_lock:
            for order in self._orders.values():
                if order.tradier_order_id == tradier_id:
                    return order
        return None

    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        """Get all orders for a symbol."""
        with self._order_lock:
            return [o for o in self._orders.values() if o.symbol == symbol]

    def get_orders_by_state(self, state: OrderState) -> List[Order]:
        """Get all orders in a specific state."""
        with self._order_lock:
            return [o for o in self._orders.values() if o.state == state]

    def get_active_orders(self) -> List[Order]:
        """Get all active (non-terminal) orders."""
        with self._order_lock:
            return [o for o in self._orders.values() if o.state.is_active]

    def get_all_orders(self) -> List[Order]:
        """Get all tracked orders."""
        with self._order_lock:
            return list(self._orders.values())

    def refresh_order(self, order_id: str) -> Optional[Order]:
        """
        Refresh order status from Tradier API.

        Args:
            order_id: Local order ID.

        Returns:
            Updated Order, or None if not found.
        """
        with self._order_lock:
            order = self._orders.get(order_id)
            if not order or not order.tradier_order_id:
                return order

        try:
            response = self.tradier.get_order(order.tradier_order_id)
            tradier_order = response.get("order", {})
            self._apply_tradier_status(order, tradier_order)
            return order
        except TradierAPIError as e:
            self.logger.error(f"Failed to refresh order {order_id}: {e}")
            return order

    def refresh_all_orders(self) -> int:
        """
        Refresh all active orders from Tradier API.

        Returns:
            Number of orders updated.
        """
        active = self.get_active_orders()
        updated = 0
        for order in active:
            if self.refresh_order(order.order_id):
                updated += 1
        return updated

    # ==========================================================================
    # ORDER FACTORY
    # ==========================================================================

    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str = "market",
        quantity: int = 1,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        duration: str = "day",
        option_symbol: Optional[str] = None,
        **kwargs,
    ) -> Order:
        """
        Create an Order object (does not submit).

        Args:
            symbol: Symbol (e.g., "SPY").
            side: Order side ("buy", "sell", "buy_to_open", etc.).
            order_type: "market", "limit", "stop", "stop_limit".
            quantity: Number of shares/contracts.
            price: Limit price.
            stop_price: Stop price.
            duration: "day", "gtc".
            option_symbol: OCC option symbol for single-leg option orders.
            **kwargs: Additional Order fields.

        Returns:
            Order object ready for submission.
        """
        sec_type = SecurityType.EQUITY
        order_class = "equity"

        if option_symbol:
            sec_type = SecurityType.OPTION
            order_class = "option"

        return Order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            duration=duration,
            security_type=sec_type,
            order_class=order_class,
            option_symbol=option_symbol,
            **kwargs,
        )

    # ==========================================================================
    # CALLBACKS
    # ==========================================================================

    def on_fill(self, callback: Callable[[Order, ExecutionReport], None]):
        """Register a callback for order fills."""
        self._on_fill_callbacks.append(callback)

    def on_state_change(self, callback: Callable[[Order, OrderState], None]):
        """Register a callback for order state changes."""
        self._on_state_change_callbacks.append(callback)

    # ==========================================================================
    # SSE STREAMING
    # ==========================================================================

    def _start_sse_stream(self):
        """Start Tradier SSE account event stream for real-time fills."""
        try:
            session_id = self.tradier.create_streaming_session()
            if not session_id:
                self.logger.warning("Could not create SSE streaming session")
                return

            self._sse_stream = TradierAccountStream(
                session_id=session_id,
                account_id=self.tradier.account_id,
                api_key=self.tradier.api_key,
            )
            self._sse_stream.start(callback=self._on_sse_event)
            self.logger.info("SSE order streaming started")

        except Exception as e:
            self.logger.error(f"Failed to start SSE stream: {e}")

    def _stop_sse_stream(self):
        """Stop SSE stream."""
        if self._sse_stream:
            self._sse_stream.stop()
            self._sse_stream = None
            self.logger.info("SSE order streaming stopped")

    def _on_sse_event(self, event: AccountEvent):
        """Handle incoming SSE account event."""
        try:
            event_type = event.event_type
            data = event.data

            if event_type == "order":
                tradier_id = data.get("id")
                status = data.get("status", "").lower()

                order = self.get_order_by_tradier_id(tradier_id) if tradier_id else None
                if not order:
                    self.logger.debug(f"SSE event for unknown Tradier order #{tradier_id}")
                    return

                old_state = order.state
                self._apply_tradier_status(order, data)

                # Notify state-change listeners
                if order.state != old_state:
                    for cb in self._on_state_change_callbacks:
                        try:
                            cb(order, old_state)
                        except Exception as e:
                            self.logger.error(f"State-change callback error: {e}")

            elif event_type == "trade":
                # Fill notification
                tradier_id = data.get("order_id")
                order = self.get_order_by_tradier_id(tradier_id) if tradier_id else None
                if order:
                    report = ExecutionReport(
                        order_id=order.order_id,
                        tradier_order_id=tradier_id,
                        symbol=data.get("symbol", order.symbol),
                        side=data.get("side", order.side),
                        quantity=int(data.get("quantity", 0)),
                        price=float(data.get("price", 0.0)),
                        execution_id=str(data.get("id", "")),
                    )
                    self._process_fill(order, report)

        except Exception as e:
            self.logger.error(f"SSE event processing error: {e}")

    # ==========================================================================
    # PRIVATE — ORDER ROUTING
    # ==========================================================================

    def _route_order(self, order: Order) -> Dict[str, Any]:
        """
        Route an Order to the correct TradierClient method.

        Args:
            order: Order to route.

        Returns:
            Raw Tradier API response dict.
        """
        # Multileg orders
        if order.legs:
            return self.tradier.place_multileg_order(
                symbol=order.symbol,
                legs=order.legs,
                order_type=order.order_type,
                duration=TradierOrderDuration(order.duration),
                price=order.price,
                tag=order.tag,
            )

        # Single-leg option orders
        if order.security_type == SecurityType.OPTION or order.option_symbol:
            return self.tradier.place_order(
                symbol=order.option_symbol or order.symbol,
                side=TradierOrderSide(order.side),
                quantity=order.quantity,
                order_type=TradierOrderType(order.order_type),
                duration=TradierOrderDuration(order.duration),
                limit_price=order.price,
                stop_price=order.stop_price,
                order_class=TradierOrderClass.OPTION,
            )

        # Equity orders (default)
        return self.tradier.place_order(
            symbol=order.symbol,
            side=TradierOrderSide(order.side),
            quantity=order.quantity,
            order_type=TradierOrderType(order.order_type),
            duration=TradierOrderDuration(order.duration),
            limit_price=order.price,
            stop_price=order.stop_price,
            order_class=TradierOrderClass.EQUITY,
        )

    def _extract_order_id(self, response: Dict[str, Any]) -> Optional[int]:
        """Extract Tradier order ID from API response."""
        if not response:
            return None
        # Tradier returns {"order": {"id": 12345, "status": "ok"}}
        order_data = response.get("order", {})
        if isinstance(order_data, dict):
            return order_data.get("id")
        return None

    def _handle_submission_error(self, order: Order, error: Exception) -> OrderResult:
        """Handle order submission error consistently."""
        with self._order_lock:
            order.state = OrderState.REJECTED
            order.error_message = str(error)
            order.updated_at = datetime.now()
            self.metrics["orders_rejected"] += 1

        return OrderResult(
            success=False,
            order_id=order.order_id,
            operation="submit",
            message=str(error),
            error_code="SUBMISSION_ERROR",
        )

    # ==========================================================================
    # PRIVATE — STATE MANAGEMENT
    # ==========================================================================

    def _apply_tradier_status(self, order: Order, tradier_data: Dict[str, Any]):
        """
        Update an Order's state from a Tradier order response.

        Args:
            order: Local Order object.
            tradier_data: Tradier order dict (from GET /orders/{id} or SSE).
        """
        status_str = str(tradier_data.get("status", "")).lower()
        new_state = TRADIER_STATUS_MAP.get(status_str, OrderState.UNKNOWN)

        with self._order_lock:
            old_state = order.state
            order.state = new_state

            # Update fill info from Tradier response
            filled_qty = tradier_data.get("quantity_filled")
            if filled_qty is not None:
                order.filled_quantity = int(filled_qty)
                order.remaining_quantity = max(0, order.quantity - order.filled_quantity)

            avg_price = tradier_data.get("avg_fill_price")
            if avg_price is not None:
                order.average_fill_price = float(avg_price)

            last_price = tradier_data.get("last_fill_price")
            if last_price is not None:
                order.last_fill_price = float(last_price)

            order.updated_at = datetime.now()

            # Update metrics on terminal transitions
            if new_state.is_terminal and not old_state.is_terminal:
                if new_state == OrderState.FILLED:
                    self.metrics["orders_filled"] += 1
                elif new_state == OrderState.CANCELLED:
                    self.metrics["orders_cancelled"] += 1
                elif new_state == OrderState.REJECTED:
                    self.metrics["orders_rejected"] += 1

    def _process_fill(self, order: Order, report: ExecutionReport):
        """Process a fill report and notify listeners."""
        with self._order_lock:
            order.filled_quantity += report.quantity
            order.remaining_quantity = max(0, order.quantity - order.filled_quantity)
            order.last_fill_price = report.price
            order.last_fill_time = report.timestamp

            # Recalculate average fill price
            if order.filled_quantity > 0:
                prev_filled = order.filled_quantity - report.quantity
                if prev_filled > 0:
                    total_value = (
                        order.average_fill_price * prev_filled
                        + report.price * report.quantity
                    )
                    order.average_fill_price = total_value / order.filled_quantity
                else:
                    order.average_fill_price = report.price

            # Update state
            if order.remaining_quantity <= 0:
                order.state = OrderState.FILLED
                self.metrics["orders_filled"] += 1
            else:
                order.state = OrderState.PARTIALLY_FILLED

            order.updated_at = datetime.now()

            # Volume metrics
            self.metrics["total_volume"] += report.price * report.quantity
            if report.commission:
                self.metrics["total_commission"] += report.commission

        self.logger.info(
            f"Fill: {order.order_id} — {report.quantity} @ {report.price} "
            f"({order.filled_quantity}/{order.quantity} filled)"
        )

        # Notify fill listeners
        for cb in self._on_fill_callbacks:
            try:
                cb(order, report)
            except Exception as e:
                self.logger.error(f"Fill callback error: {e}")

    # ==========================================================================
    # STATE PERSISTENCE
    # ==========================================================================

    def start_persistence(self):
        """Start background order state persistence."""
        if self._persistence_enabled and not self._persistence_thread:
            self._persistence_thread = threading.Thread(
                target=self._persistence_loop,
                daemon=True,
                name="OrderPersistence",
            )
            self._persistence_thread.start()
            self.logger.info("Order state persistence started")

    def stop_persistence(self):
        """Stop persistence thread."""
        if self._persistence_thread:
            self._persistence_enabled = False
            self._persistence_thread.join(timeout=5.0)
            self._persistence_thread = None
            self.logger.info("Order state persistence stopped")

    def _persistence_loop(self):
        """Background loop to periodically save order state."""
        while self._persistence_enabled and not self._shutdown_event.is_set():
            try:
                self._save_order_state()
            except Exception as e:
                self.logger.error(f"Persistence error: {e}")
            self._shutdown_event.wait(timeout=ORDER_STATE_PERSISTENCE_INTERVAL)

    def _save_order_state(self):
        """Save current order state to JSON."""
        try:
            with self._order_lock:
                orders_data = {}
                for oid, order in self._orders.items():
                    od = {}
                    for k, v in order.__dict__.items():
                        if isinstance(v, datetime):
                            od[k] = v.isoformat()
                        elif isinstance(v, Enum):
                            od[k] = v.name
                        elif isinstance(v, list):
                            od[k] = [
                                (asdict(item) if hasattr(item, "__dataclass_fields__") else item)
                                for item in v
                            ]
                        else:
                            od[k] = v
                    orders_data[oid] = od

            self._persistence_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self._persistence_dir / f"orders_{ts}.json"

            with open(path, "w") as f:
                json.dump(orders_data, f, indent=2, default=str)

            self.logger.debug(f"Order state saved to {path}")

        except Exception as e:
            self.logger.error(f"Failed to save order state: {e}")

    # ==========================================================================
    # METRICS
    # ==========================================================================

    def get_metrics(self) -> Dict[str, Any]:
        """Get order manager metrics."""
        with self._order_lock:
            total = self.metrics["orders_submitted"]
            success_rate = (
                (self.metrics["orders_filled"] / total * 100) if total > 0 else 0.0
            )
            uptime = (datetime.now() - self.metrics["start_time"]).total_seconds()

            return {
                "orders_submitted": self.metrics["orders_submitted"],
                "orders_filled": self.metrics["orders_filled"],
                "orders_cancelled": self.metrics["orders_cancelled"],
                "orders_rejected": self.metrics["orders_rejected"],
                "success_rate": success_rate,
                "total_volume": self.metrics["total_volume"],
                "total_commission": self.metrics["total_commission"],
                "active_orders": len(self.get_active_orders()),
                "total_tracked": len(self._orders),
                "uptime_seconds": uptime,
                "start_time": self.metrics["start_time"].isoformat(),
                "streaming_enabled": self._streaming_enabled,
                "sse_connected": self._sse_stream is not None,
            }

    def get_status(self) -> Dict[str, Any]:
        """Get order manager status summary."""
        return {
            "broker": "Tradier",
            "account_id": self.tradier.account_id if self.tradier else None,
            "environment": self.tradier.environment.value if self.tradier else None,
            "connected": self.tradier.test_connection() if self.tradier else False,
            "streaming": self._sse_stream is not None,
            "active_orders": len(self.get_active_orders()),
            "metrics": self.get_metrics(),
        }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def create_order_manager(
    tradier_client: Optional[TradierClient] = None,
    enable_streaming: bool = False,
) -> OrderManager:
    """
    Factory function to create an OrderManager instance.

    Args:
        tradier_client: TradierClient instance. If ``None``, one is
            created from environment variables.
        enable_streaming: Enable SSE streaming for real-time fills.

    Returns:
        OrderManager instance.
    """
    return OrderManager(
        tradier_client=tradier_client,
        enable_streaming=enable_streaming,
    )


# Singleton holder
_order_manager_instance: Optional[OrderManager] = None


def get_order_manager(
    tradier_client: Optional[TradierClient] = None,
    enable_streaming: bool = False,
) -> OrderManager:
    """
    Get or create the singleton OrderManager.

    Args:
        tradier_client: TradierClient instance (used only on first call).
        enable_streaming: Enable SSE streaming (used only on first call).

    Returns:
        OrderManager singleton.
    """
    global _order_manager_instance
    if _order_manager_instance is None:
        _order_manager_instance = create_order_manager(tradier_client, enable_streaming)
    return _order_manager_instance


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    print("=" * 80)
    print("SPYDER Order Manager — Tradier API")
    print("=" * 80)

    try:
        mgr = create_order_manager()
        print(f"OrderManager created: {mgr.tradier}")
        print(f"Connection test: {mgr.tradier.test_connection()}")

        # Show current orders from Tradier
        orders_resp = mgr.tradier.get_orders()
        orders_list = orders_resp.get("orders", {})
        if orders_list == "null" or not orders_list:
            print("No orders found")
        else:
            print(f"Orders: {json.dumps(orders_list, indent=2)}")

    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 80)
    print("Module test completed.")
    print("=" * 80)
