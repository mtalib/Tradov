#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderZ_Communication
Module: SpyderZ00_BrokerProtocol.py
Purpose: Typed Protocol interfaces for the B-Series ↔ Z-Series series boundary

Defines:
    OrderSide               — canonical order direction enum
    OrderType               — canonical order execution type enum
    NormalizedOrderRequest  — provider-agnostic order submission dataclass
    NormalizedOrderResult   — provider-agnostic order response dataclass
    BrokerClientProtocol    — structural Protocol that B-Series broker clients must satisfy
    OrderRouterProtocol     — structural Protocol that Z-Series routing modules must satisfy

Any object that implements all methods of a Protocol satisfies it without
inheriting from it (structural subtyping).

Concrete satisfiers (no inheritance required):
    TradierClient (SpyderB40) already satisfies BrokerClientProtocol structurally.
    OrderRouter (SpyderZ05) already satisfies OrderRouterProtocol structurally.

Usage::

    from Spyder.SpyderZ_Communication.SpyderZ00_BrokerProtocol import (
        NormalizedOrderRequest, NormalizedOrderResult,
        BrokerClientProtocol, OrderRouterProtocol,
    )
    assert isinstance(my_tradier_client, BrokerClientProtocol)   # runtime check

Author: Spyder Dev
Year Created: 2026
Last Updated: 2026-04-01 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

try:
    from typing import Protocol, runtime_checkable
except ImportError:                                     # Python < 3.8 fallback
    from typing import Protocol, runtime_checkable  # type: ignore[assignment]

# ==============================================================================
# LOGGER
# ==============================================================================
logger = logging.getLogger(__name__)

# ==============================================================================
# CANONICAL ENUMS
# ==============================================================================


class OrderSide(Enum):
    """Canonical order side at the B↔Z series boundary.

    Z-Series routing modules translate Tradier-specific side strings to this
    enum before crossing the boundary so that the broker layer is decoupled
    from routing logic.
    """

    BUY = "buy"
    SELL = "sell"
    BUY_TO_OPEN = "buy_to_open"
    BUY_TO_CLOSE = "buy_to_close"
    SELL_TO_OPEN = "sell_to_open"
    SELL_TO_CLOSE = "sell_to_close"


class OrderType(Enum):
    """Canonical order execution type at the B↔Z series boundary."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    DEBIT = "debit"
    CREDIT = "credit"
    EVEN = "even"


# ==============================================================================
# CANONICAL DATA TYPES
# ==============================================================================


@dataclass
class NormalizedOrderRequest:
    """Provider-agnostic order submission request.

    Z-Series routing modules produce this dataclass when crossing the boundary
    to a B-Series broker client so that the routing layer is fully decoupled
    from Tradier-specific parameter names and types.

    Attributes:
        symbol:       Ticker symbol or OCC-formatted options symbol
                      (e.g., ``"SPY"`` or ``"SPY240405C00520000"``).
        side:         Canonical order direction.
        quantity:     Number of shares / contracts (positive integer).
        order_type:   Execution type (market, limit, etc.).
        limit_price:  Limit price; 0.0 for MARKET orders.
        stop_price:   Stop trigger price; 0.0 when not applicable.
        duration:     Time-in-force code (``"day"``, ``"gtc"``, ``"ioc"``).
        account_id:   Broker account identifier; empty string means default.
        strategy_id:  Originating strategy identifier for position attribution
                      and audit trail.
        metadata:     Arbitrary key-value pairs for extensibility (e.g.,
                      leg labels for multi-leg orders).
    """

    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    quantity: int = 0
    order_type: OrderType = OrderType.MARKET
    limit_price: float = 0.0
    stop_price: float = 0.0
    duration: str = "day"
    account_id: str = ""
    strategy_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedOrderResult:
    """Provider-agnostic order submission / query result.

    Returned by BrokerClientProtocol.place_order() and get_order() so that
    Z-Series routing modules track order lifecycle without parsing
    Tradier-specific response structures.

    Attributes:
        order_id:        Broker-assigned order identifier (string form).
        status:          Order status string (e.g., ``"open"``, ``"filled"``,
                         ``"canceled"``, ``"rejected"``).
        filled_quantity: Number of shares / contracts executed so far.
        avg_fill_price:  Volume-weighted average execution price; 0.0 when the
                         order has not been filled yet.
        error_message:   Non-empty when the broker rejected the request.
        raw:             Original provider response dict for fields not yet
                         normalised.
    """

    order_id: str = ""
    status: str = ""
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    error_message: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_filled(self) -> bool:
        """True when the order status indicates a complete fill."""
        return self.status == "filled"

    @property
    def is_rejected(self) -> bool:
        """True when the broker rejected the order."""
        return self.status == "rejected" or bool(self.error_message)

    @property
    def is_open(self) -> bool:
        """True when the order is resting in the book."""
        return self.status == "open"


# ==============================================================================
# PROTOCOL DEFINITIONS
# ==============================================================================


@runtime_checkable
class BrokerClientProtocol(Protocol):
    """Structural Protocol for B-Series broker client implementations.

    Any B-Series module that executes orders against a live or paper broker
    satisfies this Protocol without inheriting from it.  TradierClient
    (SpyderB40) already satisfies it structurally.

    Methods:
        place_order:     Submit a new order and return the broker's response.
        cancel_order:    Request cancellation of an outstanding order.
        get_order:       Retrieve the current state of a specific order.
        get_quotes:      Fetch current market quotes for one or more symbols.
        get_positions:   Retrieve all open positions from the broker account.
        test_connection: Return True when the broker API is reachable.
    """

    def place_order(self, request: NormalizedOrderRequest) -> NormalizedOrderResult:
        """Submit a new order to the broker.

        Args:
            request: Provider-agnostic order request at the series boundary.

        Returns:
            NormalizedOrderResult with broker-assigned order_id and initial
            status.
        """
        ...

    def cancel_order(self, order_id: str) -> bool:
        """Request cancellation of an outstanding order.

        Args:
            order_id: Broker-assigned order identifier (string form).

        Returns:
            True if the cancellation request was accepted by the broker.
        """
        ...

    def get_order(self, order_id: str) -> NormalizedOrderResult:
        """Retrieve the current state of a specific order.

        Args:
            order_id: Broker-assigned order identifier (string form).

        Returns:
            NormalizedOrderResult reflecting the latest order status.
        """
        ...

    def get_quotes(self, symbols: list[str]) -> dict[str, Any]:
        """Fetch current market quotes for one or more symbols.

        Args:
            symbols: List of ticker symbols to quote.

        Returns:
            Mapping of symbol → quote data dict.
        """
        ...

    def get_positions(self) -> dict[str, Any]:
        """Retrieve all open positions from the broker account.

        Returns:
            Mapping of symbol → position data dict; empty dict when flat.
        """
        ...

    def test_connection(self) -> bool:
        """Return True when the broker API endpoint is reachable.

        Returns:
            True if the connectivity probe succeeds, False otherwise.
        """
        ...


@runtime_checkable
class OrderRouterProtocol(Protocol):
    """Structural Protocol for Z-Series order routing implementations.

    Higher-level modules (strategy coordinators, trade engines) use this
    Protocol to submit orders without coupling to Z-Series internals.
    OrderRouter (SpyderZ05) already satisfies it structurally.

    Methods:
        submit_order:     Route a normalised order request to the best venue.
        cancel_order:     Cancel an in-flight order through the router.
        get_order_status: Retrieve router-layer order state by identifier.
    """

    def submit_order(self, request: NormalizedOrderRequest) -> NormalizedOrderResult:
        """Route a normalised order to the best available broker venue.

        Args:
            request: Normalised order request at the series boundary.

        Returns:
            NormalizedOrderResult with router-assigned tracking data.
        """
        ...

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an in-flight order via the routing layer.

        Args:
            order_id: Order identifier returned by submit_order.

        Returns:
            True if the cancellation was accepted by the router.
        """
        ...

    def get_order_status(self, order_id: str) -> NormalizedOrderResult | None:
        """Retrieve the current routing-layer state of an order.

        Args:
            order_id: Order identifier returned by submit_order.

        Returns:
            NormalizedOrderResult if the order is known to the router,
            None if the identifier is unrecognised.
        """
        ...
