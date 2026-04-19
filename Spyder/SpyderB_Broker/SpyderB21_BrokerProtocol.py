#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB21_BrokerProtocol.py
Purpose: Structural Protocol for all broker implementations (B40, PaperBroker)

Author: SPYDER Trading System
Year Created: 2026
Last Updated: 2026-04-18 Time: 12:30:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from __future__ import annotations

from typing import Any
try:
    from typing import Protocol, runtime_checkable
except ImportError:  # Python 3.7 fallback
    from typing_extensions import Protocol, runtime_checkable  # type: ignore

# ==============================================================================
# BROKER PROTOCOL
# ==============================================================================

@runtime_checkable
class BrokerProtocol(Protocol):
    """Structural interface every broker must satisfy.

    Both ``SpyderB40_TradierClient`` (live) and ``SpyderR15_PaperBroker``
    (paper) conform to this protocol, allowing ``SpyderR04_LiveEngine``
    to work identically with either broker and making mode switches
    purely a construction-time decision.

    All methods return plain ``dict`` so callers require no broker-specific
    imports at runtime.
    """

    def place_order(
        self,
        symbol: str,
        side: Any,
        quantity: int,
        order_type: Any,
        limit_price: float | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Submit a new order.

        Returns:
            ``{"order": {"id": "<broker-assigned-id>"}}`` on success,
            or ``{}`` / error dict on failure.
        """
        ...

    def get_order(self, order_id: str | int) -> dict[str, Any]:
        """Retrieve order status by broker-assigned ID.

        Returns:
            ``{"order": {"id": ..., "status": ..., "avg_fill_price": ...}}``
        """
        ...

    def cancel_order(self, order_id: str | int) -> bool:
        """Cancel an open order.

        Returns:
            ``True`` if the cancellation was accepted.
        """
        ...

    def get_positions(self) -> list[dict[str, Any]] | dict[str, Any]:
        """Return current open positions.

        Returns:
            List or dict of position records.
        """
        ...

    def close_position(
        self,
        symbol: str,
        urgency: str = "IMMEDIATE",
        reason: str = "close_position",
        force: bool = False,
    ) -> dict[str, Any]:
        """Close an existing position with a market order.

        Returns:
            Order response dict, or ``{}`` if there was nothing to close.
        """
        ...

    def close_position_verified(
        self,
        symbol: str,
        timeout_s: float = 10.0,
        urgency: str = "IMMEDIATE",
        reason: str = "close_position_verified",
    ) -> dict[str, Any]:
        """A23/O7 (v14): close ``symbol`` and **verify** the fill before returning.

        Submits a close order and waits up to ``timeout_s`` seconds for the
        matching ``ORDER_FILLED`` event. This exists because the bare
        ``close_position`` returns once the broker acknowledges the order,
        but during shutdown we need proof the position is actually flat —
        an unverified close on the session-flatten path has been the root
        cause of positions surviving a shutdown.

        Returns:
            ``{"status": "verified", "order": {...}, "fill": {...}}`` on success,
            or ``{"status": "unverified", "order": {...}, "reason": "<why>"}``
            on timeout. Unverified outcomes SHOULD emit ``KILL_SWITCH`` in
            the caller so a human operator sees the drift.
        """
        ...

    def get_account_balances(self) -> dict[str, Any]:
        """Return account snapshot (balance, buying power, etc.).

        Returns:
            ``{"balances": {...}}`` shaped dict.
        """
        ...


def is_broker_compliant(broker: object) -> bool:
    """Return True if *broker* satisfies :class:`BrokerProtocol` at runtime.

    Uses ``isinstance`` with ``@runtime_checkable`` for a fast structural
    check without importing broker-specific modules.
    """
    return isinstance(broker, BrokerProtocol)
