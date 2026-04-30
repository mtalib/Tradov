#!/usr/bin/env python3
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
from datetime import datetime, timezone, timedelta
from typing import Any
from collections.abc import Callable
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from pathlib import Path
from threading import RLock, Event as ThreadEvent

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType

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
    create_tradier_client_from_env,
)

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_ORDER_TIMEOUT = 30.0
ORDER_STATE_PERSISTENCE_INTERVAL = 60  # seconds
EXECUTION_FEED_VERSION = "1.0"
LIQUIDITY_FEED_VERSION = "1.0"

_DEFAULT_LIQUIDITY_THRESHOLDS: dict[str, float] = {
    "max_spread_pct": 0.12,
    "max_spread_abs": 0.20,
    "max_quote_age_ms": 1500,
    "min_top_of_book_size": 10,
    "min_open_interest": 500,
    "min_volume": 50,
    "min_oi_change_pct": -0.20,
}

# Tradier order status string → OrderState mapping
TRADIER_STATUS_MAP: dict[str, "OrderState"] = {}  # populated after OrderState defined

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
    tradier_order_id: int | None = None  # Tradier's integer order ID

    # Core order fields
    symbol: str = ""
    side: str = "buy"                        # Tradier-style: buy, sell, buy_to_open, etc.
    order_type: str = "market"               # Tradier-style: market, limit, stop, stop_limit
    quantity: int = 0
    price: float | None = None            # Limit price
    stop_price: float | None = None       # Stop price
    duration: str = "day"                     # day, gtc, pre, post

    # Security classification
    security_type: SecurityType = SecurityType.EQUITY
    order_class: str = "equity"              # equity, option, multileg, combo
    option_symbol: str | None = None      # OCC-format option symbol

    # Options fields (for single-leg option orders)
    expiry: str | None = None             # YYYY-MM-DD
    strike: float | None = None
    right: str | None = None              # "call" or "put"

    # Multi-leg support
    legs: list[OptionLeg] = field(default_factory=list)

    # State tracking
    state: OrderState = field(default=OrderState.PENDING)
    submitted_time: datetime | None = None
    filled_quantity: int = 0
    remaining_quantity: int = 0
    average_fill_price: float = 0.0
    last_fill_price: float = 0.0
    last_fill_time: datetime | None = None

    # Error / warning tracking
    error_message: str | None = None
    warning_message: str | None = None

    # Metadata
    strategy_name: str | None = None
    tag: str | None = None               # Tradier order tag
    decision_mid_price: float | None = None
    liquidity_snapshot: dict[str, Any] | None = None

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

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
    tradier_order_id: int | None = None
    operation: str = ""          # submit, cancel, modify
    message: str | None = None
    error_code: str | None = None
    raw_response: dict[str, Any] | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ExecutionReport:
    """Execution / fill report."""
    order_id: str
    tradier_order_id: int | None = None
    symbol: str = ""
    side: str = ""
    quantity: int = 0
    price: float = 0.0
    execution_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    commission: float | None = None

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
        tradier_client: TradierClient | None = None,
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
        self._orders: dict[str, Order] = {}
        self._order_lock = RLock()
        self._shutdown_event = ThreadEvent()

        # Callbacks for external listeners (GUI, risk manager, etc.)
        self._on_fill_callbacks: list[Callable[[Order, ExecutionReport], None]] = []
        self._on_state_change_callbacks: list[Callable[[Order, OrderState], None]] = []

        # SSE streaming for real-time fills
        self._sse_stream: TradierAccountStream | None = None
        self._streaming_enabled = enable_streaming

        # State persistence
        self._persistence_thread: threading.Thread | None = None
        self._persistence_enabled = True
        self._persistence_dir = Path(__file__).parent.parent.parent / "data" / "order_state"

        # Metrics
        self.metrics: dict[str, Any] = {
            "orders_submitted": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_rejected": 0,
            "total_volume": 0.0,
            "total_commission": 0.0,
            "start_time": datetime.now(timezone.utc),
        }

        # Execution telemetry feed envelope cache (newest last).
        self._execution_feed_events: list[dict[str, Any]] = []
        self._execution_feed_max = 1000
        self._execution_session_id = str(uuid.uuid4())
        self._liquidity_feed_events: list[dict[str, Any]] = []
        self._liquidity_feed_max = 1000
        self._execution_quality_policy = self._load_execution_quality_policy()
        self._execution_quality_window_seconds = 300

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

                order.submitted_time = datetime.now(timezone.utc)
                order.updated_at = datetime.now(timezone.utc)
                self._orders[order.order_id] = order

            self.logger.info(
                f"Submitting order {order.order_id}: "
                f"{order.side} {order.quantity} {order.symbol} "
                f"@ {order.price or 'MKT'}"
            )

            blocked, reasons = self._evaluate_liquidity_gate(order)
            if blocked:
                with self._order_lock:
                    order.state = OrderState.REJECTED
                    order.error_message = "; ".join(reasons)
                    order.updated_at = datetime.now(timezone.utc)
                    self.metrics["orders_rejected"] += 1

                self._record_liquidity_feed(order, gate_passed=False, reasons=reasons)
                self._record_execution_feed(
                    order=order,
                    lifecycle_event=EventType.ORDER_REJECTED,
                    reject_reason=f"liquidity_gate_block: {'; '.join(reasons)}",
                )
                return OrderResult(
                    success=False,
                    order_id=order.order_id,
                    operation="submit",
                    message="Liquidity gate blocked order",
                    error_code="LIQUIDITY_GATE_BLOCK",
                )

            self._record_liquidity_feed(order, gate_passed=True, reasons=[])

            blocked, reasons = self._evaluate_execution_quality_gate()
            if blocked:
                with self._order_lock:
                    order.state = OrderState.REJECTED
                    order.error_message = "; ".join(reasons)
                    order.updated_at = datetime.now(timezone.utc)
                    self.metrics["orders_rejected"] += 1

                self._record_execution_feed(
                    order=order,
                    lifecycle_event=EventType.ORDER_REJECTED,
                    reject_reason=f"execution_quality_block: {'; '.join(reasons)}",
                )
                try:
                    event_manager = get_event_manager()
                    event_manager.emit(
                        EventType.KILL_SWITCH,
                        {
                            "type": "execution_quality_breach",
                            "reasons": reasons,
                            "order_id": order.order_id,
                        },
                        priority="high",
                    )
                except Exception:
                    pass
                return OrderResult(
                    success=False,
                    order_id=order.order_id,
                    operation="submit",
                    message="Execution quality gate blocked order",
                    error_code="EXECUTION_QUALITY_BLOCK",
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

                order.updated_at = datetime.now(timezone.utc)

            success = tradier_id is not None
            if success:
                self._record_execution_feed(
                    order=order,
                    lifecycle_event=EventType.ORDER_SUBMITTED,
                )
            else:
                self._record_execution_feed(
                    order=order,
                    lifecycle_event=EventType.ORDER_REJECTED,
                    reject_reason=order.error_message or "missing_tradier_order_id",
                )

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
        except (ConnectionError, TimeoutError) as e:
            return self._handle_submission_error(order, e)
        except Exception:
            self.logger.exception("Unexpected error in order submission — re-raising")
            raise

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
                order.updated_at = datetime.now(timezone.utc)

            self.logger.info("Cancelling order %s (Tradier #%s)", order_id, order.tradier_order_id)

            response = self.tradier.cancel_order(order.tradier_order_id)

            with self._order_lock:
                order.state = OrderState.CANCELLED
                order.updated_at = datetime.now(timezone.utc)
                self.metrics["orders_cancelled"] += 1

            self._record_execution_feed(
                order=order,
                lifecycle_event=EventType.ORDER_CANCELLED,
            )

            return OrderResult(
                success=True,
                order_id=order_id,
                tradier_order_id=order.tradier_order_id,
                operation="cancel",
                message="Order cancelled",
                raw_response=response,
            )

        except TradierAPIError as e:
            self.logger.error("Cancel failed for %s: %s", order_id, e)
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
        price: float | None = None,
        stop_price: float | None = None,
        order_type: str | None = None,
        duration: str | None = None,
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

            self.logger.info("Modifying order %s (Tradier #%s)", order_id, order.tradier_order_id)

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
                order.updated_at = datetime.now(timezone.utc)

            return OrderResult(
                success=True,
                order_id=order_id,
                tradier_order_id=order.tradier_order_id,
                operation="modify",
                message="Order modified",
                raw_response=response,
            )

        except TradierAPIError as e:
            self.logger.error("Modify failed for %s: %s", order_id, e)
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
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.submit_order, order)

    async def cancel_order_async(self, order_id: str) -> OrderResult:
        """Cancel an order asynchronously."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.cancel_order, order_id)

    async def modify_order_async(
        self,
        order_id: str,
        price: float | None = None,
        stop_price: float | None = None,
        order_type: str | None = None,
        duration: str | None = None,
    ) -> OrderResult:
        """Modify an order asynchronously."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.modify_order, order_id, price, stop_price, order_type, duration
        )

    # ==========================================================================
    # CONVENIENCE — MULTILEG / STRATEGY ORDERS
    # ==========================================================================

    def submit_multileg_order(
        self,
        symbol: str,
        legs: list[OptionLeg],
        order_type: str = "market",
        duration: str = "day",
        price: float | None = None,
        tag: str | None = None,
        strategy_name: str | None = None,
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
                order.submitted_time = datetime.now(timezone.utc)
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
                order.updated_at = datetime.now(timezone.utc)

            return OrderResult(
                success=tradier_id is not None,
                order_id=order.order_id,
                tradier_order_id=tradier_id,
                operation="submit_multileg",
                message="Multileg order submitted" if tradier_id else "Submission failed",
                raw_response=response,
            )

        except TradierAPIError as e:
            return self._handle_submission_error(order, e)
        except (ConnectionError, TimeoutError) as e:
            return self._handle_submission_error(order, e)
        except Exception:
            self.logger.exception("Unexpected error in multileg submission — re-raising")
            raise

    def submit_iron_condor(
        self,
        symbol: str,
        expiration: str,
        put_buy_strike: float,
        put_sell_strike: float,
        call_sell_strike: float,
        call_buy_strike: float,
        quantity: int = 1,
        price: float | None = None,
        duration: str = "day",
        strategy_name: str | None = None,
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
                order.submitted_time = datetime.now(timezone.utc)
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
                order.updated_at = datetime.now(timezone.utc)

            return OrderResult(
                success=tradier_id is not None,
                order_id=order.order_id,
                tradier_order_id=tradier_id,
                operation="submit_iron_condor",
                raw_response=response,
            )

        except TradierAPIError as e:
            return self._handle_submission_error(order, e)
        except (ConnectionError, TimeoutError) as e:
            return self._handle_submission_error(order, e)
        except Exception:
            self.logger.exception("Unexpected error in iron condor submission — re-raising")
            raise

    def submit_credit_spread(
        self,
        symbol: str,
        expiration: str,
        sell_strike: float,
        buy_strike: float,
        option_type: str = "P",
        quantity: int = 1,
        price: float | None = None,
        duration: str = "day",
        strategy_name: str | None = None,
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
                order.submitted_time = datetime.now(timezone.utc)
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
                order.updated_at = datetime.now(timezone.utc)

            return OrderResult(
                success=tradier_id is not None,
                order_id=order.order_id,
                tradier_order_id=tradier_id,
                operation="submit_credit_spread",
                raw_response=response,
            )

        except TradierAPIError as e:
            return self._handle_submission_error(order, e)
        except (ConnectionError, TimeoutError) as e:
            return self._handle_submission_error(order, e)
        except Exception:
            self.logger.exception("Unexpected error in credit spread submission — re-raising")
            raise

    # ==========================================================================
    # SMART LIMIT ORDER — MID-PRICE WALK
    # ==========================================================================

    def submit_limit_with_walk(
        self,
        symbol: str,
        side: str,
        quantity: int,
        bid: float,
        ask: float,
        option_symbol: str | None = None,
        duration: str = "day",
        strategy_name: str | None = None,
        max_slippage_pct: float = 0.05,
        min_tick_size: float = 0.01,
        tick_interval_secs: float = 0.5,
        max_walk_ticks: int = 10,
        underlying_entry_price: float | None = None,
        underlying_spot_fn: Callable[[], float] | None = None,
        underlying_abort_pct: float = 0.0015,
        vix: float | None = None,
    ) -> OrderResult:
        """
        Submit a limit order starting at the mid-price, then walk toward the
        natural ask (buys) or bid (sells) using spread-proportional steps until
        filled or the walk budget is exhausted.

        Four improvements over a naive fixed-penny walk:

        1. **Spread-proportional steps** — step size is
           ``max(min_tick_size, (ask - bid) / max_walk_ticks)`` so the walk
           always traverses the full spread in at most ``max_walk_ticks`` steps,
           regardless of spread width.

        2. **IOC-ping behaviour** — after each ``tick_interval_secs`` wait the
           unfilled order is *cancelled* and a fresh limit is submitted at the
           next price level (instead of modifying a resting order).  This avoids
           signalling intent to HFT algorithms that monitor slowly-creeping
           resting limit queues.

        3. **Underlying price abort** — if ``underlying_spot_fn`` and
           ``underlying_entry_price`` are supplied, the walk is aborted whenever
           ``|SPY_now - SPY_entry| / SPY_entry > underlying_abort_pct``.  This
           prevents buying the top of a bounce that has already completed before
           the fill.

        4. **VIX-scaled slippage budget** — when ``vix`` is supplied the
           effective slippage cap scales up smoothly above VIX 15 so that
           ordinarily wide spreads in high-volatility regimes do not cause every
           trade to be abandoned:
           ``effective = min(0.10, max_slippage_pct * (1 + max(0, (vix-15)/25)))``.

        Args:
            symbol: Underlying or option symbol (equity or options root).
            side: Tradier order side string (``"buy_to_open"``, ``"sell_to_open"``, etc.).
            quantity: Number of contracts / shares.
            bid: Current best bid at signal generation time.
            ask: Current best ask at signal generation time.
            option_symbol: OCC-format option symbol (for single-leg options).
            duration: ``"day"`` or ``"gtc"``.
            strategy_name: Strategy tag for tracking.
            max_slippage_pct: Base slippage fraction of mid before aborting
                (default 5 %).  Scaled dynamically when ``vix`` is supplied.
            min_tick_size: Floor for the spread-proportional step (default $0.01).
            tick_interval_secs: Seconds between ping attempts (default 0.5 s).
            max_walk_ticks: Maximum number of price walks before giving up
                (default 10).
            underlying_entry_price: SPY price at signal generation time.  Required
                together with ``underlying_spot_fn`` to enable the underlying-move
                abort guard.
            underlying_spot_fn: Zero-argument callable that returns the current
                SPY price.  Called once per tick inside the walk loop.
            underlying_abort_pct: Fractional move in the underlying that triggers
                an abort (default 0.15 %).
            vix: Current VIX level.  Enables dynamic slippage scaling when
                supplied.

        Returns:
            ``OrderResult`` from the final (or only) submission attempt.
        """
        if bid <= 0 or ask <= 0 or ask < bid:
            return OrderResult(
                success=False,
                order_id="",
                operation="submit_limit_with_walk",
                message=f"Invalid bid/ask: bid={bid} ask={ask}",
                error_code="INVALID_QUOTE",
            )

        mid = (bid + ask) / 2.0
        spread = ask - bid

        # ── 1. Spread-proportional step size ─────────────────────────────────
        step = max(min_tick_size, spread / max(max_walk_ticks, 1))

        # ── 4. VIX-scaled slippage budget ─────────────────────────────────────
        if vix is not None and vix > 15.0:
            effective_slippage = min(0.10, max_slippage_pct * (1.0 + (vix - 15.0) / 25.0))
        else:
            effective_slippage = max_slippage_pct
        max_walk_distance = mid * effective_slippage

        # Walk direction: buys walk UP toward the ask; sells walk DOWN toward the bid.
        is_buy = side.startswith("buy")
        limit_price = round(mid, 2)  # Always start at mid

        self.logger.info(
            f"MidWalk: {side} {quantity} {option_symbol or symbol} "
            f"bid={bid:.2f} ask={ask:.2f} mid={limit_price:.2f} "
            f"spread={spread:.3f} step={step:.3f} "
            f"slippage_budget={effective_slippage:.1%} "
            f"max_walk_ticks={max_walk_ticks}"
        )

        result: OrderResult | None = None
        current_order_id: str | None = None
        walk_start_time = datetime.now(timezone.utc)

        for tick in range(max_walk_ticks + 1):
            # ── Timeout guard ─────────────────────────────────────────────────
            elapsed = (datetime.now(timezone.utc) - walk_start_time).total_seconds()
            if elapsed > DEFAULT_ORDER_TIMEOUT:
                self.logger.warning(
                    f"MidWalk order {current_order_id} timed out after "
                    f"{elapsed:.0f}s (>{DEFAULT_ORDER_TIMEOUT}s)"
                )
                if current_order_id:
                    order_obj = self.get_order(current_order_id)
                    if order_obj:
                        with self._order_lock:
                            order_obj.state = OrderState.EXPIRED
                    self.cancel_order(current_order_id)
                return OrderResult(
                    success=False,
                    order_id=current_order_id or "",
                    operation="submit_limit_with_walk",
                    message=f"Order timed out after {elapsed:.0f}s",
                    error_code="ORDER_TIMEOUT",
                )

            # ── 3. Underlying price abort ─────────────────────────────────────
            if (
                underlying_spot_fn is not None
                and underlying_entry_price is not None
                and underlying_entry_price > 0
            ):
                try:
                    current_underlying = underlying_spot_fn()
                    drift = abs(current_underlying - underlying_entry_price) / underlying_entry_price  # noqa: E501
                    if drift > underlying_abort_pct:
                        self.logger.warning(
                            f"MidWalk: underlying moved {drift:.3%} "
                            f"(>{underlying_abort_pct:.3%}) — thesis invalidated, aborting"
                        )
                        if current_order_id:
                            self.cancel_order(current_order_id)
                        return OrderResult(
                            success=False,
                            order_id=current_order_id or "",
                            operation="submit_limit_with_walk",
                            message=f"Underlying moved {drift:.3%} — walk aborted",
                            error_code="UNDERLYING_MOVED",
                        )
                except Exception as exc:
                    self.logger.warning(
                        "MidWalk: underlying_spot_fn raised %s — skipping abort check", exc
                    )

            # ── Slippage budget guard ─────────────────────────────────────────
            walk_distance = abs(limit_price - mid)
            if walk_distance > max_walk_distance:
                self.logger.warning(
                    f"MidWalk: walk distance {walk_distance:.3f} exceeds "
                    f"max allowed {max_walk_distance:.3f} — aborting"
                )
                if current_order_id:
                    self.cancel_order(current_order_id)
                return OrderResult(
                    success=False,
                    order_id=current_order_id or "",
                    operation="submit_limit_with_walk",
                    message="Max slippage budget exceeded — order aborted",
                    error_code="MAX_SLIPPAGE_EXCEEDED",
                )

            if tick == 0:
                # First submission — always at mid-price
                order = Order(
                    symbol=symbol,
                    side=side,
                    order_type="limit",
                    quantity=quantity,
                    price=limit_price,
                    duration=duration,
                    security_type=SecurityType.OPTION if option_symbol else SecurityType.EQUITY,
                    order_class="option" if option_symbol else "equity",
                    option_symbol=option_symbol,
                    strategy_name=strategy_name,
                )
                result = self.submit_order(order)
                if not result.success:
                    return result
                current_order_id = result.order_id
            else:
                # ── 2. IOC-ping: cancel the resting order, advance price, resubmit ──
                # Cancelling rather than modifying prevents HFT algorithms from
                # detecting a slowly-creeping resting order and stepping in front.
                if current_order_id:
                    self.cancel_order(current_order_id)

                limit_price = round(limit_price + (step if is_buy else -step), 2)
                self.logger.info(
                    "MidWalk tick %s: pinging limit at %.2f (step=%.3f)",
                    tick, limit_price, step,
                )
                order = Order(
                    symbol=symbol,
                    side=side,
                    order_type="limit",
                    quantity=quantity,
                    price=limit_price,
                    duration=duration,
                    security_type=SecurityType.OPTION if option_symbol else SecurityType.EQUITY,
                    order_class="option" if option_symbol else "equity",
                    option_symbol=option_symbol,
                    strategy_name=strategy_name,
                )
                result = self.submit_order(order)
                if not result.success:
                    return result
                current_order_id = result.order_id

            # Wait, then check fill status
            time.sleep(tick_interval_secs)  # intentional: thread-safe blocking wait
            refreshed = self.refresh_order(current_order_id)
            if refreshed and refreshed.state == OrderState.FILLED:
                self.logger.info(
                    f"MidWalk: filled at {refreshed.average_fill_price:.2f} "
                    f"(tick {tick}, mid was {mid:.2f}, step={step:.3f})"
                )
                return OrderResult(
                    success=True,
                    order_id=current_order_id,
                    tradier_order_id=refreshed.tradier_order_id,
                    operation="submit_limit_with_walk",
                    message=(
                        f"Filled at {refreshed.average_fill_price:.2f} "
                        f"after {tick} walk(s)"
                    ),
                )

        # Exhausted all ticks — cancel the last unfilled ping
        self.logger.warning(
            "MidWalk: exhausted %s ticks without fill — cancelling", max_walk_ticks
        )
        if current_order_id:
            self.cancel_order(current_order_id)

        return OrderResult(
            success=False,
            order_id=current_order_id or "",
            operation="submit_limit_with_walk",
            message=f"Not filled after {max_walk_ticks} price walks — order cancelled",
            error_code="WALK_EXHAUSTED",
        )

    # ==========================================================================
    # ORDER QUERIES
    # ==========================================================================

    def get_order(self, order_id: str) -> Order | None:
        """Get order by local ID."""
        with self._order_lock:
            return self._orders.get(order_id)

    def get_order_by_tradier_id(self, tradier_id: int) -> Order | None:
        """Get order by Tradier order ID."""
        with self._order_lock:
            for order in self._orders.values():
                if order.tradier_order_id == tradier_id:
                    return order
        return None

    def get_orders_by_symbol(self, symbol: str) -> list[Order]:
        """Get all orders for a symbol."""
        with self._order_lock:
            return [o for o in self._orders.values() if o.symbol == symbol]

    def get_orders_by_state(self, state: OrderState) -> list[Order]:
        """Get all orders in a specific state."""
        with self._order_lock:
            return [o for o in self._orders.values() if o.state == state]

    def get_active_orders(self) -> list[Order]:
        """Get all active (non-terminal) orders."""
        with self._order_lock:
            return [o for o in self._orders.values() if o.state.is_active]

    def get_all_orders(self) -> list[Order]:
        """Get all tracked orders."""
        with self._order_lock:
            return list(self._orders.values())

    def refresh_order(self, order_id: str) -> Order | None:
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
            self.logger.error("Failed to refresh order %s: %s", order_id, e)
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
        price: float | None = None,
        stop_price: float | None = None,
        duration: str = "day",
        option_symbol: str | None = None,
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
            self.logger.error("Failed to start SSE stream: %s", e)

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
                data.get("status", "").lower()

                order = self.get_order_by_tradier_id(tradier_id) if tradier_id else None
                if not order:
                    self.logger.debug("SSE event for unknown Tradier order #%s", tradier_id)
                    return

                old_state = order.state
                self._apply_tradier_status(order, data)

                # Notify state-change listeners
                if order.state != old_state:
                    for cb in list(self._on_state_change_callbacks):  # snapshot for thread safety
                        try:
                            cb(order, old_state)
                        except Exception as e:
                            self.logger.error("State-change callback error: %s", e)

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
            self.logger.error("SSE event processing error: %s", e)

    # ==========================================================================
    # PRIVATE — ORDER ROUTING
    # ==========================================================================

    def _route_order(self, order: Order) -> dict[str, Any]:
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

    def _extract_order_id(self, response: dict[str, Any]) -> int | None:
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
            order.updated_at = datetime.now(timezone.utc)
            self.metrics["orders_rejected"] += 1

        self._record_execution_feed(
            order=order,
            lifecycle_event=EventType.ORDER_REJECTED,
            reject_reason=str(error),
        )

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

    def _apply_tradier_status(self, order: Order, tradier_data: dict[str, Any]):
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

            order.updated_at = datetime.now(timezone.utc)

            # Update metrics on terminal transitions
            if new_state.is_terminal and not old_state.is_terminal:
                if new_state == OrderState.FILLED:
                    self.metrics["orders_filled"] += 1
                elif new_state == OrderState.CANCELLED:
                    self.metrics["orders_cancelled"] += 1
                elif new_state == OrderState.REJECTED:
                    self.metrics["orders_rejected"] += 1

        if new_state == OrderState.REJECTED and old_state != OrderState.REJECTED:
            self._record_execution_feed(
                order=order,
                lifecycle_event=EventType.ORDER_REJECTED,
                reject_reason=str(tradier_data.get("reject_reason") or tradier_data.get("reason") or "rejected"),  # noqa: E501
            )
        elif new_state == OrderState.CANCELLED and old_state != OrderState.CANCELLED:
            self._record_execution_feed(
                order=order,
                lifecycle_event=EventType.ORDER_CANCELLED,
            )

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

            order.updated_at = datetime.now(timezone.utc)

            # Volume metrics
            self.metrics["total_volume"] += report.price * report.quantity
            if report.commission:
                self.metrics["total_commission"] += report.commission

        self.logger.info(
            f"Fill: {order.order_id} — {report.quantity} @ {report.price} "
            f"({order.filled_quantity}/{order.quantity} filled)"
        )

        # P2-3: emit ORDER_PARTIALLY_FILLED synchronously when a partial fill is recorded
        if order.state == OrderState.PARTIALLY_FILLED:
            feed_payload = self._record_execution_feed(
                order=order,
                lifecycle_event=EventType.ORDER_PARTIALLY_FILLED,
                report=report,
            )
            try:
                get_event_manager().emit(
                    EventType.ORDER_PARTIALLY_FILLED,
                    {
                        "order_id": order.order_id,
                        "symbol": order.symbol,
                        "filled_quantity": order.filled_quantity,
                        "remaining_quantity": order.remaining_quantity,
                        "last_fill_price": report.price,
                        "average_fill_price": order.average_fill_price,
                        "execution_feed": feed_payload,
                    },
                )
            except Exception as _e:
                self.logger.error("ORDER_PARTIALLY_FILLED emit failed: %s", _e)

        if order.state == OrderState.FILLED:
            feed_payload = self._record_execution_feed(
                order=order,
                lifecycle_event=EventType.ORDER_FILLED,
                report=report,
            )
            try:
                get_event_manager().emit(
                    EventType.ORDER_FILLED,
                    {
                        "order_id": order.order_id,
                        "symbol": order.symbol,
                        "filled_quantity": order.filled_quantity,
                        "average_fill_price": order.average_fill_price,
                        "execution_feed": feed_payload,
                    },
                )
            except Exception as _e:
                self.logger.error("ORDER_FILLED emit failed: %s", _e)

        # Notify fill listeners
        for cb in list(self._on_fill_callbacks):  # snapshot copy for thread safety
            try:
                cb(order, report)
            except Exception as e:
                self.logger.error("Fill callback error: %s", e)

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
                self.logger.error("Persistence error: %s", e)
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
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = self._persistence_dir / f"orders_{ts}.json"

            # Atomic write: write to .tmp then rename to prevent corrupt reads
            tmp_path = str(path) + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(orders_data, f, indent=2, default=str)
            os.replace(tmp_path, str(path))  # atomic on POSIX

            self.logger.debug("Order state saved to %s", path)

        except Exception as e:
            self.logger.error("Failed to save order state: %s", e)

    # ==========================================================================
    # METRICS
    # ==========================================================================

    def get_metrics(self) -> dict[str, Any]:
        """Get order manager metrics."""
        with self._order_lock:
            total = self.metrics["orders_submitted"]
            success_rate = (
                (self.metrics["orders_filled"] / total * 100) if total > 0 else 0.0
            )
            uptime = (datetime.now(timezone.utc) - self.metrics["start_time"]).total_seconds()

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

    def get_status(self) -> dict[str, Any]:
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

    def get_recent_execution_feeds(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent execution telemetry envelopes (newest last)."""
        with self._order_lock:
            if limit <= 0:
                return []
            return list(self._execution_feed_events[-limit:])

    def get_recent_liquidity_feeds(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent liquidity gate telemetry envelopes (newest last)."""
        with self._order_lock:
            if limit <= 0:
                return []
            return list(self._liquidity_feed_events[-limit:])

    def _record_execution_feed(
        self,
        order: Order,
        lifecycle_event: EventType,
        report: ExecutionReport | None = None,
        reject_reason: str | None = None,
    ) -> dict[str, Any]:
        """Create and store unified execution telemetry envelope, then publish to event bus."""
        payload = self._build_execution_feed_payload(
            order=order,
            lifecycle_event=lifecycle_event,
            report=report,
            reject_reason=reject_reason,
        )

        with self._order_lock:
            self._execution_feed_events.append(payload)
            if len(self._execution_feed_events) > self._execution_feed_max:
                del self._execution_feed_events[:-self._execution_feed_max]

        # Publish execution telemetry to event bus (Phase 5-C)
        try:
            event_manager = get_event_manager()
            event_manager.emit(
                EventType.TRADE,
                {
                    "execution_telemetry": payload,
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "event": lifecycle_event.value,
                },
                priority="high" if lifecycle_event == EventType.ORDER_REJECTED else "normal",
            )
        except Exception as e:
            self.logger.warning("Failed to publish execution telemetry: %s", e)

        return payload

    def _build_execution_feed_payload(
        self,
        order: Order,
        lifecycle_event: EventType,
        report: ExecutionReport | None = None,
        reject_reason: str | None = None,
    ) -> dict[str, Any]:
        """Build execution telemetry envelope for order lifecycle events."""
        decision_mid = order.decision_mid_price
        avg_fill_price = order.average_fill_price or (report.price if report else 0.0)

        slippage_bps = None
        if decision_mid and decision_mid > 0 and avg_fill_price > 0:
            slippage_bps = ((avg_fill_price - decision_mid) / decision_mid) * 10000.0

        fill_latency_ms = None
        if order.submitted_time and (order.last_fill_time or (report.timestamp if report else None)):  # noqa: E501
            fill_ts = order.last_fill_time or (report.timestamp if report else None)
            if fill_ts is not None:
                submitted_ts = order.submitted_time
                # Accept legacy naive timestamps by interpreting them as UTC.
                if submitted_ts.tzinfo is None:
                    submitted_ts = submitted_ts.replace(tzinfo=timezone.utc)
                if fill_ts.tzinfo is None:
                    fill_ts = fill_ts.replace(tzinfo=timezone.utc)
                fill_latency_ms = max(
                    0.0,
                    (fill_ts - submitted_ts).total_seconds() * 1000.0,
                )

        partial_fill_ratio = 0.0
        if order.quantity > 0:
            partial_fill_ratio = min(1.0, max(0.0, float(order.filled_quantity) / float(order.quantity)))  # noqa: E501

        data = {
            "event": lifecycle_event.value,
            "order_id": order.order_id,
            "strategy_id": order.strategy_name,
            "symbol": order.symbol,
            "decision_ts": order.created_at.isoformat() if order.created_at else None,
            "submit_ts": order.submitted_time.isoformat() if order.submitted_time else None,
            "ack_ts": order.updated_at.isoformat() if order.updated_at else None,
            "fill_ts": (order.last_fill_time.isoformat() if order.last_fill_time else (report.timestamp.isoformat() if report else None)),  # noqa: E501
            "decision_mid": decision_mid,
            "submit_limit": order.price,
            "avg_fill_price": avg_fill_price if avg_fill_price > 0 else None,
            "slippage_bps": slippage_bps,
            "fill_latency_ms": fill_latency_ms,
            "partial_fill_ratio": partial_fill_ratio,
            "reject_flag": lifecycle_event == EventType.ORDER_REJECTED,
            "reject_reason": reject_reason,
            "cancel_replace_count": 0,
            "session_id": self._execution_session_id,
        }

        return {
            "feed": "execution",
            "version": EXECUTION_FEED_VERSION,
            "mode": self.tradier.environment.value if self.tradier else "unknown",
            "session_id": self._execution_session_id,
            "published_ts": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

    def _evaluate_liquidity_gate(self, order: Order) -> tuple[bool, list[str]]:
        """Evaluate liquidity thresholds and return (blocked, reasons)."""
        if order.security_type not in {SecurityType.OPTION, SecurityType.MULTILEG} and not order.legs:  # noqa: E501
            return False, []

        snapshot = order.liquidity_snapshot or {}
        if not snapshot:
            # No snapshot: do not block here to avoid accidental hard-fail on missing upstream wiring.  # noqa: E501
            return False, []

        t = dict(_DEFAULT_LIQUIDITY_THRESHOLDS)
        custom_thresholds = snapshot.get("thresholds")
        if isinstance(custom_thresholds, dict):
            for key, val in custom_thresholds.items():
                if key in t and isinstance(val, (int, float)):
                    t[key] = float(val)

        reasons: list[str] = []

        spread_pct = snapshot.get("spread_pct")
        if isinstance(spread_pct, (int, float)) and float(spread_pct) > t["max_spread_pct"]:
            reasons.append(
                f"spread_pct {float(spread_pct):.4f} > max_spread_pct {t['max_spread_pct']:.4f}"
            )

        spread_abs = snapshot.get("spread_abs")
        if isinstance(spread_abs, (int, float)) and float(spread_abs) > t["max_spread_abs"]:
            reasons.append(
                f"spread_abs {float(spread_abs):.4f} > max_spread_abs {t['max_spread_abs']:.4f}"
            )

        quote_age_ms = snapshot.get("quote_age_ms")
        if isinstance(quote_age_ms, (int, float)) and float(quote_age_ms) > t["max_quote_age_ms"]:
            reasons.append(
                f"quote_age_ms {float(quote_age_ms):.0f} > max_quote_age_ms {t['max_quote_age_ms']:.0f}"  # noqa: E501
            )

        top_of_book_size = snapshot.get("top_of_book_size")
        if isinstance(top_of_book_size, (int, float)) and float(top_of_book_size) < t["min_top_of_book_size"]:  # noqa: E501
            reasons.append(
                f"top_of_book_size {float(top_of_book_size):.0f} < min_top_of_book_size {t['min_top_of_book_size']:.0f}"  # noqa: E501
            )

        open_interest = snapshot.get("open_interest")
        if isinstance(open_interest, (int, float)) and float(open_interest) < t["min_open_interest"]:  # noqa: E501
            reasons.append(
                f"open_interest {float(open_interest):.0f} < min_open_interest {t['min_open_interest']:.0f}"  # noqa: E501
            )

        volume = snapshot.get("volume")
        if isinstance(volume, (int, float)) and float(volume) < t["min_volume"]:
            reasons.append(f"volume {float(volume):.0f} < min_volume {t['min_volume']:.0f}")

        oi_change_pct = snapshot.get("oi_change_pct")
        if isinstance(oi_change_pct, (int, float)) and float(oi_change_pct) < t["min_oi_change_pct"]:  # noqa: E501
            reasons.append(
                f"oi_change_pct {float(oi_change_pct):.4f} < min_oi_change_pct {t['min_oi_change_pct']:.4f}"  # noqa: E501
            )

        return len(reasons) > 0, reasons

    def _load_execution_quality_policy(self) -> dict[str, Any]:
        """Load execution quality thresholds from config manager when available."""
        defaults = {
            "max_slippage_bps": 25.0,
            "max_fill_latency_ms": 2500.0,
            "max_reject_rate_5m": 0.08,
            "halt_on_quality_breach": True,
        }
        try:
            from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager
            cfg = get_config_manager()
            exec_cfg = cfg.get("autonomous_readiness.execution", {})
            if isinstance(exec_cfg, dict):
                merged = dict(defaults)
                merged.update({
                    "max_slippage_bps": float(exec_cfg.get("max_slippage_bps", defaults["max_slippage_bps"])),
                    "max_fill_latency_ms": float(exec_cfg.get("max_fill_latency_ms", defaults["max_fill_latency_ms"])),
                    "max_reject_rate_5m": float(exec_cfg.get("max_reject_rate_5m", defaults["max_reject_rate_5m"])),
                    "halt_on_quality_breach": bool(exec_cfg.get("halt_on_quality_breach", defaults["halt_on_quality_breach"])),
                })
                return merged
        except Exception:
            pass
        return defaults

    def _evaluate_execution_quality_gate(self) -> tuple[bool, list[str]]:
        """Block new orders when execution telemetry breaches quality thresholds."""
        policy = self._execution_quality_policy
        if not policy.get("halt_on_quality_breach", False):
            return False, []

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=self._execution_quality_window_seconds)

        slippage_limit = float(policy.get("max_slippage_bps", 25.0))
        latency_limit = float(policy.get("max_fill_latency_ms", 2500.0))
        reject_limit = float(policy.get("max_reject_rate_5m", 0.08))

        recent = []
        with self._order_lock:
            recent = list(self._execution_feed_events)

        total = 0
        rejects = 0
        reasons: list[str] = []

        for payload in reversed(recent):
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, dict):
                continue
            published = data.get("published_ts") or payload.get("published_ts")
            try:
                ts = datetime.fromisoformat(published) if published else None
            except Exception:
                ts = None
            if ts is None or ts < window_start:
                continue

            total += 1
            if data.get("reject_flag") is True:
                rejects += 1

            slippage = data.get("slippage_bps")
            if isinstance(slippage, (int, float)) and slippage > slippage_limit:
                reasons.append(f"slippage_bps {slippage:.2f} > {slippage_limit:.2f}")

            latency = data.get("fill_latency_ms")
            if isinstance(latency, (int, float)) and latency > latency_limit:
                reasons.append(f"fill_latency_ms {latency:.0f} > {latency_limit:.0f}")

        if total > 0:
            reject_rate = rejects / total
            if reject_rate > reject_limit:
                reasons.append(f"reject_rate_5m {reject_rate:.2%} > {reject_limit:.2%}")

        if reasons:
            return True, sorted(set(reasons))

        return False, []

    def _record_liquidity_feed(self, order: Order, gate_passed: bool, reasons: list[str]) -> dict[str, Any]:  # noqa: E501
        """Create and store unified liquidity telemetry envelope."""
        snapshot = dict(order.liquidity_snapshot or {})
        snapshot.pop("thresholds", None)

        payload = {
            "feed": "liquidity",
            "version": LIQUIDITY_FEED_VERSION,
            "mode": self.tradier.environment.value if self.tradier else "unknown",
            "session_id": self._execution_session_id,
            "published_ts": datetime.now(timezone.utc).isoformat(),
            "data": {
                "order_id": order.order_id,
                "strategy_id": order.strategy_name,
                "symbol": order.symbol,
                "gate_passed": gate_passed,
                "reasons": list(reasons),
                "snapshot": snapshot,
            },
        }

        with self._order_lock:
            self._liquidity_feed_events.append(payload)
            if len(self._liquidity_feed_events) > self._liquidity_feed_max:
                del self._liquidity_feed_events[:-self._liquidity_feed_max]

        return payload


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def create_order_manager(
    tradier_client: TradierClient | None = None,
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
_order_manager_instance: OrderManager | None = None


def get_order_manager(
    tradier_client: TradierClient | None = None,
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

    try:
        mgr = create_order_manager()

        # Show current orders from Tradier
        orders_resp = mgr.tradier.get_orders()
        orders_list = orders_resp.get("orders", {})
        if orders_list == "null" or not orders_list:
            pass
        else:
            pass

    except Exception:
        pass

