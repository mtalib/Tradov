#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovZ_Communication
Module: TradovZ11_SignalOrderHandler.py
Purpose: Turn an inbound SignalEnvelope into a risk-checked order proposal

Author: Mohamed Talib (with Claude)
Year Created: 2026
Last Updated: 2026-06-26

Module Description:
    The Phase-4 handler injected into TradovZ10_InboundSignalReceiver. It runs an
    external signal through the full proposal pipeline:

        SignalEnvelope
          -> readiness gate   (R13 ReadinessGateCoordinator + C30 probe)
          -> risk check       (E01 RiskManager.check_trade — injected)
          -> mode routing
               * paper (default) -> TradovBox (R02 PaperEngine)
               * live            -> blocked unless explicitly enabled, and even
                                    then returned as pending_approval (no
                                    auto-fire; dual-approval is future work)

    Design boundaries:
        - The risk check is *injected* (a Callable matching E01.check_trade). The
          RiskManager is owned/configured by the session (R12), so this handler
          uses it rather than constructing it — no RiskConfig guessing here.
        - The readiness check is injected as a callable so handler logic is
          time-independent and unit-testable; the default wires R13 + C30.
        - Fail-closed: any stage that cannot positively approve results in a
          non-executed disposition.

    This module has no Qt dependency.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from Tradov.TradovZ_Communication.TradovZ10_InboundSignalReceiver import SignalEnvelope
from Tradov.TradovR_Runtime.TradovR13_ReadinessGateCoordinator import (
    ReadinessGateCoordinator,
    gather_inputs,
)
from Tradov.TradovC_MarketData.TradovC30_ConnectionProbe import check_api_connection

_logger = logging.getLogger(__name__)

_ORDER_TYPE_TO_PAPER = {"market": "MKT", "limit": "LMT", "stop": "STP"}

# Type aliases for the injected collaborators.
ReadinessCheck = Callable[[], tuple[bool, str]]
RiskCheck = Callable[[dict[str, Any]], dict[str, Any]]
PaperExecutor = Callable[[SignalEnvelope, int], dict[str, Any]]


def _disposition(
    status: str, stage: str, executed: bool, reason: str = "", **extra: Any
) -> dict[str, Any]:
    return {
        "disposition": status,
        "stage": stage,
        "executed": executed,
        "reason": reason,
        **extra,
    }


def _resolve_quantity(requested: int | None, max_safe: int | None) -> int:
    """Honor a requested size but let the risk layer clamp it (design §6).

    A ``max_safe`` of 0 is an explicit clamp to zero (reject); ``None`` means the
    risk layer returned no cap, so the requested size stands.
    """
    if max_safe is None:
        return int(requested) if requested is not None else 0
    cap = int(max_safe)
    if requested is None:
        return cap
    return min(int(requested), cap)


class TradovBoxExecutor:
    """Paper executor backed by TradovBox (R02 PaperEngine)."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        from Tradov.TradovR_Runtime.TradovR02_PaperEngine import create_paper_engine

        self._engine = create_paper_engine(config or {})
        self._engine.start()

    def __call__(self, envelope: SignalEnvelope, quantity: int) -> dict[str, Any]:
        contract = SimpleNamespace(symbol=envelope.symbol)
        order = SimpleNamespace(
            action="BUY" if envelope.side == "buy" else "SELL",
            totalQuantity=quantity,
            orderType=_ORDER_TYPE_TO_PAPER[envelope.order_type],
            lmtPrice=envelope.limit_price,
            auxPrice=envelope.stop_price,
        )
        order_id = self._engine.place_order(contract, order)
        if not order_id:
            return {"order_id": "", "status": "rejected"}
        placed = self._engine.get_order_history().get(order_id) or self._engine.get_open_orders().get(
            order_id
        )
        return {
            "order_id": order_id,
            "status": placed.status.name.lower() if placed else "submitted",
            "avg_fill_price": getattr(placed, "avg_fill_price", None) if placed else None,
        }


def default_readiness_check(runtime_context: Any = None) -> ReadinessCheck:
    """Wire R13 + C30 into a time-aware (bool, reason) readiness check."""
    gate = ReadinessGateCoordinator()

    def _check() -> tuple[bool, str]:
        inputs = gather_inputs(
            connection_probe=lambda: check_api_connection(runtime_context)
        )
        ok = gate.is_go(inputs)
        if ok:
            return True, ""
        reasons = (gate.last_result or {}).get("reasons", [])
        return False, "; ".join(reasons) or "system not ready"

    return _check


class SignalOrderHandler:
    """Pipeline handler injected into the inbound signal receiver (Z10)."""

    def __init__(
        self,
        *,
        risk_check: RiskCheck,
        readiness_check: ReadinessCheck,
        paper_executor: PaperExecutor,
        runtime_context: Any = None,
        live_enabled: bool = False,
    ) -> None:
        self._risk_check = risk_check
        self._readiness_check = readiness_check
        self._paper_executor = paper_executor
        self._runtime_context = runtime_context
        self._live_enabled = bool(live_enabled)

    def _is_live(self) -> bool:
        ctx = self._runtime_context
        return bool(getattr(ctx, "is_live", False)) if ctx is not None else False

    def __call__(self, envelope: SignalEnvelope) -> dict[str, Any]:
        # 1. System readiness gate.
        ready, reason = self._readiness_check()
        if not ready:
            return _disposition("rejected", "readiness", False, reason)

        # 2. Order-specific risk validation.
        trade_request = {
            "symbol": envelope.symbol,
            "action": envelope.side,
            "quantity": envelope.quantity or 0,
            "price": envelope.limit_price or 0.0,
            "strategy_id": envelope.strategy,
            "type": "equity",
        }
        verdict = self._risk_check(trade_request)
        if not verdict.get("approved", False):
            return _disposition(
                "rejected", "risk", False, str(verdict.get("reason") or "risk rejected")
            )

        quantity = _resolve_quantity(envelope.quantity, verdict.get("max_safe_quantity"))
        if quantity <= 0:
            return _disposition("rejected", "risk", False, "no permitted quantity")

        # 3. Mode routing.
        if self._is_live():
            if not self._live_enabled:
                return _disposition(
                    "blocked", "mode", False,
                    "live trading not confirmed", quantity=quantity,
                )
            # Even when enabled, never auto-fire live: hand to dual-approval.
            return _disposition(
                "pending_approval", "live", False,
                "queued for dual-approval", quantity=quantity,
            )

        # 4. Paper execution via TradovBox.
        try:
            result = self._paper_executor(envelope, quantity)
        except Exception as exc:  # fail closed on executor error
            _logger.exception("paper execution failed")
            return _disposition("error", "execute", False, str(exc))

        if not result.get("order_id"):
            return _disposition(
                "rejected", "execute", False,
                str(result.get("status") or "paper engine rejected order"),
            )
        return _disposition(
            "accepted", "executed", True, "",
            mode="paper",
            order_id=result["order_id"],
            quantity=quantity,
            avg_fill_price=result.get("avg_fill_price"),
        )


def build_default_handler(
    *,
    risk_check: RiskCheck,
    runtime_context: Any = None,
    paper_config: dict[str, Any] | None = None,
    live_enabled: bool = False,
) -> SignalOrderHandler:
    """Construct a handler wired to the real R13/C30 readiness + TradovBox paper.

    ``risk_check`` must be supplied by the caller (the session's configured
    E01 RiskManager.check_trade) — this handler does not own risk configuration.
    """
    return SignalOrderHandler(
        risk_check=risk_check,
        readiness_check=default_readiness_check(runtime_context),
        paper_executor=TradovBoxExecutor(paper_config),
        runtime_context=runtime_context,
        live_enabled=live_enabled,
    )
