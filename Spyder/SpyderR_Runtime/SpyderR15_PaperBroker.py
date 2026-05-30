#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderR_Runtime
Module: SpyderR15_PaperBroker.py
Purpose: Paper broker that plugs into R04 LiveEngine in place of B40
         TradierClient, producing real ORDER_FILLED events without any
         Tradier API calls.

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-18 Time: 00:00:00

Module Description:
    Implements the same ``place_order`` / ``get_order`` / ``cancel_order``
    interface that B40 TradierClient exposes so that R04's existing
    ``_broker_submit`` (Path 2 — place_order) works unchanged.

    Fill simulation:
    - ``place_order(**kwargs)`` → accepted immediately;
      returns ``{"order": {"id": "PAPER-xxxxxx"}}``.
    - ``get_order(order_id)`` → "pending" until ``fill_delay_s``
      elapses, then transitions to "filled" at the last known market
      price (or the order's own limit price as fallback).
    - ``cancel_order(order_id)`` → marks "cancelled"; FillReconciler
      will emit ORDER_CANCELLED on its next poll.

    The broker optionally subscribes to MARKET_DATA events so fill prices
    track the live (or mock) market.  If no event_manager is supplied the
    class still works — fills are priced at the order's stated price, or
    a 1.0 fallback.

    Lifecycle:  ``start()`` / ``stop()`` / ``is_running`` satisfy the
    SessionSupervisor ``_components`` interface.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import threading
import time
import uuid  # noqa: F401
from datetime import datetime, UTC
from typing import Any, Optional  # noqa: F401

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_FILL_DELAY_S: float = 0.10   # seconds before a market order "fills"
DEFAULT_ACCOUNT_BALANCE: float = 100_000.0


# ==============================================================================
# MAIN CLASS
# ==============================================================================

class PaperBroker:
    """Simulated broker for paper/backtesting mode.

    Implements the B40-compatible ``place_order`` / ``get_order`` /
    ``cancel_order`` / ``get_positions`` / ``get_account`` surface so that
    ``SpyderR04_LiveEngine._broker_submit`` (Path 2) works without
    modification.

    Args:
        event_manager: Optional shared A05 EventManager.  When supplied,
            the broker subscribes to MARKET_DATA to track live prices for
            realistic fill pricing.
        fill_delay_s: Seconds to wait before transitioning a pending order
            to "filled".  Default 0.10 s; set to 0 for instant fills in
            fast unit tests.
        account_balance: Paper account starting balance in USD.
    """

    def __init__(
        self,
        event_manager: Any = None,
        fill_delay_s: float = DEFAULT_FILL_DELAY_S,
        account_balance: float = DEFAULT_ACCOUNT_BALANCE,
        slippage_bps: int = 5,
    ) -> None:
        self.logger = SpyderLogger.get_logger(__name__)
        self._fill_delay = fill_delay_s
        self._account_balance = account_balance
        self._slippage_bps = slippage_bps  # basis points of slippage applied at fill

        self._orders: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._counter = 0
        self._last_prices: dict[str, float] = {}
        self._running = False
        # A23 (v14): retained for verified-close (needed by live broker only;
        # paper verifies via get_order polling).
        self._event_manager = event_manager

        if event_manager is not None:
            try:
                from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType
                event_manager.subscribe(EventType.MARKET_DATA, self._on_tick)
            except Exception as exc:
                self.logger.warning("PaperBroker: could not subscribe to MARKET_DATA: %s", exc)

        self.logger.debug(
            "PaperBroker created (fill_delay=%.2fs balance=%.0f slippage=%dbps)",
            fill_delay_s,
            account_balance,
            slippage_bps,
        )

    # --------------------------------------------------------------------------
    # LIFECYCLE
    # --------------------------------------------------------------------------

    def start(self) -> bool:
        self._running = True
        self.logger.debug("PaperBroker started")
        return True

    def stop(self) -> None:
        self._running = False
        self.logger.info("PaperBroker stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def connect(self) -> bool:
        """Compatibility shim for broker clients that require explicit connect."""
        return self.start()

    def disconnect(self) -> None:
        """Compatibility shim for broker clients that expose disconnect()."""
        self.stop()

    def is_connected(self) -> bool:
        """Return connection state expected by LiveEngine checks."""
        return self._running

    def get_account_info(self) -> dict[str, Any]:
        """Return Tradier-like account metadata used by LiveEngine guards."""
        return {
            "account_id": "PAPER-ACCOUNT",
            "trading_enabled": True,
            "status": "active",
            "type": "paper",
        }

    async def get_positions_async(self) -> dict[str, Any]:
        """Async compatibility shim matching Tradier response shape."""
        positions = self.get_positions()
        if not positions:
            return {"positions": "null"}
        return {"positions": {"position": positions}}

    async def get_account_balances_async(self) -> dict[str, Any]:
        """Async compatibility shim matching Tradier balances response shape."""
        account = (self.get_account_balances() or {}).get("account") or {}
        equity = float(account.get("balance", self._account_balance) or self._account_balance)
        return {
            "balances": {
                "total_equity": equity,
                "total_cash": equity,
                "margin": {"option_buying_power": 0.0},
                "option_short_value": equity,
            }
        }

    # --------------------------------------------------------------------------
    # MARKET DATA SUBSCRIPTION
    # --------------------------------------------------------------------------

    def _on_tick(self, event: Any) -> None:
        """Update last-known price from MARKET_DATA events."""
        data = getattr(event, "data", event) or {}
        symbol = data.get("symbol")
        price = (
            data.get("price")
            or data.get("last")
            or data.get("close")
            or data.get("bid")
        )
        if symbol and price:
            self._last_prices[symbol] = float(price)

    # --------------------------------------------------------------------------
    # BROKER INTERFACE — B40-compatible
    # --------------------------------------------------------------------------

    def place_order(
        self,
        symbol: str = "",
        side: Any = None,
        quantity: int = 1,
        order_type: Any = None,
        limit_price: float | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Accept an order immediately and return a Tradier-shaped response.

        Accepts arbitrary kwargs (same surface as B40 place_equity_order /
        place_option_order).  Only ``symbol``, ``quantity``, and ``price`` /
        ``limit_price`` are used for fill simulation.

        Returns:
            ``{"order": {"id": "<PAPER-xxxxxx>"}}``
        """
        with self._lock:
            self._counter += 1
            oid = f"PAPER-{self._counter:06d}"
            # Prefer explicit params; fall back to kwargs for backward compat.
            sym = symbol or kwargs.get("symbol", "")
            qty = int(quantity or kwargs.get("quantity", kwargs.get("qty", 1)))

            # P1-7: Mirror live OCC strike validation so paper catches
            # invalid option strikes early (e.g. non-0.05 increment).
            self._validate_option_symbol_strike(sym)

            price = float(
                limit_price
                or kwargs.get("price")
                or kwargs.get("limit_price")
                or kwargs.get("stop")
                or 0.0
            )
            self._orders[oid] = {
                "id": oid,
                "status": "pending",
                "symbol": sym,
                "quantity": qty,
                "price": price,
                "side": str(side or kwargs.get("side", "buy")).lower(),
                "placed_at": time.monotonic(),
            }

        self.logger.info(
            "PaperBroker.place_order: %s qty=%d → %s", sym, qty, oid
        )
        return {"order": {"id": oid}}

    @staticmethod
    def _validate_option_symbol_strike(symbol: str) -> None:
        """Validate OCC option strike tick size (0.05 increments).

        No-op for non-option symbols or symbols that cannot be parsed as OCC.
        """
        if not symbol:
            return

        idx = 0
        while idx < len(symbol) and not symbol[idx].isdigit():
            idx += 1

        # OCC shape must contain YYMMDD + C/P + 8-digit strike.
        if idx == 0 or idx + 15 > len(symbol):
            return
        opt_char = symbol[idx + 6:idx + 7]
        if opt_char not in {"C", "P"}:
            return

        strike_str = symbol[idx + 7:idx + 15]
        if not strike_str.isdigit():
            return

        strike = int(strike_str) / 1000.0
        steps = strike * 20.0
        if abs(round(steps) - steps) > 1e-9:
            raise ValueError(
                f"Invalid option strike in symbol {symbol}: {strike:.4f} is not a 0.05 increment"
            )

    def get_order(self, order_id: "str | int") -> dict[str, Any]:
        """Return current status of a paper order.

        Mirrors the Tradier ``GET /v1/accounts/.../orders/{id}`` response
        shape so that ``FillReconciler._poll_one`` can parse it unchanged.

        Returns:
            ``{"order": {"id": ..., "status": "pending"|"filled"|"canceled", ...}}``
        """
        oid = str(order_id)
        with self._lock:
            order = self._orders.get(oid)

        if order is None:
            return {"order": {"id": oid, "status": "unknown"}}

        if order["status"] == "cancelled":
            return {"order": {"id": oid, "status": "canceled"}}

        if order["status"] == "filled":
            return self._filled_response(order)

        # Simulate fill latency
        age = time.monotonic() - order["placed_at"]
        if age >= self._fill_delay:
            with self._lock:
                if oid in self._orders:
                    self._orders[oid]["status"] = "filled"
            return self._filled_response(order)

        return {"order": {"id": oid, "status": "pending"}}

    def cancel_order(self, order_id: "str | int") -> bool:
        """Cancel a pending paper order.

        Returns:
            True if the order existed and was cancelled, False if not found
            or already in a terminal state.
        """
        oid = str(order_id)
        with self._lock:
            order = self._orders.get(oid)
            if order is None:
                return False
            if order["status"] in ("filled", "cancelled"):
                return False
            self._orders[oid]["status"] = "cancelled"

        self.logger.info("PaperBroker.cancel_order: %s cancelled", oid)
        return True

    def get_positions(self) -> list[dict[str, Any]]:
        """Return open positions.  Position tracking is owned by B03/P01; we
        return an empty list here (same as Tradier would if none exist)."""
        return []

    def close_position(
        self,
        symbol: str,
        force: bool = False,
        *,
        urgency: str = "IMMEDIATE",
        reason: str = "close_position",
        position_quantity: int | None = None,
    ) -> dict[str, Any]:
        """Close a paper position by placing an offsetting market order.

        Matches the ``BrokerProtocol.close_position`` signature so that
        ``SessionSupervisor._flatten_positions`` works identically in paper
        and live mode. If a signed ``position_quantity`` is supplied, the
        offsetting side and full order size are derived from that quantity.

        Args:
            symbol: The security symbol to close.
            force: If True, submit the close even when no position is
                   currently tracked locally.

        Returns:
            Tradier-shaped order response dict, or ``{}`` on no-op.
        """
        self.logger.info(
            "PaperBroker.close_position: %s (force=%s urgency=%s reason=%s qty=%s)",
            symbol,
            force,
            urgency,
            reason,
            position_quantity,
        )
        # C8 (v18): use OCC shape validation instead of a naive single-char
        # membership test which false-positives on equity tickers like "PG",
        # "CP", "PCG" etc.  OCC option symbols are at least 15 chars long and
        # follow the pattern: <underlying><YYMMDD><C|P><8-digit-strike>.
        # We reuse the same offset logic from _validate_option_symbol_strike().
        def _is_occ_option(sym: str) -> bool:
            idx = 0
            while idx < len(sym) and not sym[idx].isdigit():
                idx += 1
            # Underlying must be ≥1 char; tail must have room for 6+1+8 chars.
            if idx == 0 or idx + 15 > len(sym):
                return False
            return (
                sym[idx:idx + 6].isdigit()
                and sym[idx + 6] in "CP"
                and sym[idx + 7:idx + 15].isdigit()
            )

        is_option = _is_occ_option(symbol)
        signed_qty = int(position_quantity or 0)
        quantity = abs(signed_qty) or 1
        if signed_qty:
            if is_option:
                side = "sell_to_close" if signed_qty > 0 else "buy_to_close"
            else:
                side = "sell" if signed_qty > 0 else "buy"
        else:
            side = "buy_to_close" if is_option else "sell"

        return self.place_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type="market",
            tag=f"paper-close-{symbol}-{int(time.time())}",
        )

    def close_position_verified(
        self,
        symbol: str,
        timeout_s: float = 10.0,
        urgency: str = "IMMEDIATE",
        reason: str = "close_position_verified",
        position_quantity: int | None = None,
    ) -> dict[str, Any]:
        """A23 (v14): close and wait for the fill before returning.

        For paper, we poll ``get_order`` (which auto-transitions to filled
        after ``_fill_delay``) up to ``timeout_s``. This is sufficient for
        simulation; the live broker uses a Future-based event wait.
        """
        response = self.close_position(
            symbol,
            urgency=urgency,
            reason=reason,
            position_quantity=position_quantity,
        )
        oid = ((response or {}).get("order") or {}).get("id")
        if not oid:
            return {
                "status": "unverified",
                "order": response,
                "reason": "no_order_id_returned",
            }
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        while time.monotonic() < deadline:
            status = self.get_order(oid).get("order", {}).get("status")
            if status == "filled":
                return {
                    "status": "verified",
                    "order": response,
                    "fill": self.get_order(oid),
                }
            if status in ("canceled", "cancelled", "rejected"):
                return {
                    "status": "unverified",
                    "order": response,
                    "reason": f"terminal_non_fill:{status}",
                }
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
        return {
            "status": "unverified",
            "order": response,
            "reason": "timeout",
        }

    def get_account_balances(self) -> dict[str, Any]:
        """Return a minimal paper account snapshot."""
        return {
            "account": {
                "type": "paper",
                "balance": self._account_balance,
                "account_number": "PAPER-ACCOUNT",
                "status": "active",
            }
        }

    # --------------------------------------------------------------------------
    # PRIVATE HELPERS
    # --------------------------------------------------------------------------

    def _filled_response(self, order: dict[str, Any]) -> dict[str, Any]:
        """Build a Tradier-shaped filled-order dict."""
        symbol = order.get("symbol", "")
        raw_price = float(
            self._last_prices.get(symbol)
            or order.get("price")
            or 1.0          # options priced < $1 are common; avoid zero
        )
        # Apply slippage: buys pay more, sells receive less.
        side = str(order.get("side", "buy")).lower()
        direction = -1.0 if side in ("sell", "sell_to_open", "sell_to_close") else 1.0
        slippage_fraction = self._slippage_bps / 10_000.0
        fill_price = raw_price * (1.0 + direction * slippage_fraction)
        return {
            "order": {
                "id": order["id"],
                "status": "filled",
                "avg_fill_price": round(fill_price, 4),
                "quantity": order.get("quantity", 1),
                "transaction_date": datetime.now(UTC).isoformat(),
                "symbol": symbol,
            }
        }


# ==============================================================================
# FACTORY
# ==============================================================================

def create_paper_broker(
    event_manager: Any = None,
    fill_delay_s: float = DEFAULT_FILL_DELAY_S,
    account_balance: float = DEFAULT_ACCOUNT_BALANCE,
    slippage_bps: int = 5,
) -> PaperBroker:
    """Create and return a PaperBroker instance.

    Args:
        event_manager: Shared EventManager for live-price subscriptions.
        fill_delay_s: Seconds before orders transition to filled.
        account_balance: Starting paper capital.
        slippage_bps: One-way slippage in basis points applied to fill price
            (default 5 bps = 0.05%).  Buys fill higher, sells fill lower.
            Set to 0 for zero-slippage fills (unit tests).

    Returns:
        Configured PaperBroker ready to plug into SessionSupervisor.
    """
    return PaperBroker(
        event_manager=event_manager,
        fill_delay_s=fill_delay_s,
        account_balance=account_balance,
        slippage_bps=slippage_bps,
    )
