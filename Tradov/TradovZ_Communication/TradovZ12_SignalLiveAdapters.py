#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovZ_Communication
Module: TradovZ12_SignalLiveAdapters.py
Purpose: Concrete live adapters + session bootstrap for the inbound signal path

Author: Mohamed Talib (with Claude)
Year Created: 2026
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    Phase-5 external adapters that wire the signal handler (Z11) to Tradov's real
    execution and persistence layers, kept separate from the pure handler logic:

      - TradierLiveExecutor: submits a live order via B02 OrderManager
        (create_order -> submit_order). Invoked ONLY through
        SignalOrderHandler.submit_approved after explicit manual approval —
        never auto-fired.
      - make_trade_recorder: persists executed fills via H05 record_trade.
      - bootstrap_inbound_receiver: builds a fully-wired receiver+handler from a
        session's collaborators (risk check, order manager, session DB). R12 may
        call this at startup; it is provided as a function so R12 need not be
        edited here.

    No Qt dependency.
"""

from __future__ import annotations

import logging
from typing import Any

from Tradov.TradovZ_Communication.TradovZ10_InboundSignalReceiver import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    InboundSignalReceiver,
    SignalEnvelope,
)
from Tradov.TradovZ_Communication.TradovZ11_SignalOrderHandler import (
    ManualApprovalGate,
    PendingProposalStore,
    SignalOrderHandler,
    TradovBoxExecutor,
    default_readiness_check,
)

_logger = logging.getLogger(__name__)


class TradierLiveExecutor:
    """Live order executor backed by B02 OrderManager.

    Submits via create_order -> submit_order. Used only behind manual approval.
    """

    def __init__(self, order_manager: Any) -> None:
        self._om = order_manager

    def __call__(self, envelope: SignalEnvelope, quantity: int) -> dict[str, Any]:
        order = self._om.create_order(
            symbol=envelope.symbol,
            side=envelope.side,
            order_type=envelope.order_type,
            quantity=quantity,
            price=envelope.limit_price,
            stop_price=envelope.stop_price,
            duration="day",
        )
        result = self._om.submit_order(order)
        if getattr(result, "success", False):
            return {
                "order_id": str(result.order_id),
                "status": "submitted",
                "tradier_order_id": getattr(result, "tradier_order_id", None),
            }
        return {"order_id": "", "status": str(getattr(result, "message", None) or "rejected")}


def make_trade_recorder(session_db: Any):
    """Return a TradeRecorder that persists executed fills via H05.record_trade."""

    def _record(envelope: SignalEnvelope, quantity: int, result: dict[str, Any]) -> None:
        session_db.record_trade(
            symbol=envelope.symbol,
            trade_type=envelope.side.upper(),  # BUY / SELL
            side=envelope.side,
            quantity=quantity,
            price=float(result.get("avg_fill_price") or 0.0),
            strategy=envelope.strategy,
            order_id=str(result.get("order_id") or ""),
            notes=f"inbound signal from {envelope.source}",
        )

    return _record


def bootstrap_inbound_receiver(
    *,
    secret: str,
    risk_check,
    runtime_context: Any = None,
    order_manager: Any | None = None,
    session_db: Any | None = None,
    live_enabled: bool = False,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    paper_config: dict[str, Any] | None = None,
    audit_sink=None,
    readiness_check=None,
) -> tuple[InboundSignalReceiver, SignalOrderHandler, ManualApprovalGate]:
    """Build a fully-wired (but not started) inbound receiver for a session.

    Pass the session's configured ``RiskManager.check_trade`` as ``risk_check``.
    Supply ``order_manager`` (B02) to enable the live path and ``session_db``
    (H05) to persist executed fills. Returns the receiver, the handler, and the
    approval gate (so the operator can ``approval_gate.approve(proposal_id)``
    then ``handler.submit_approved(proposal_id)``).
    """
    approval_gate = ManualApprovalGate()
    handler = SignalOrderHandler(
        risk_check=risk_check,
        readiness_check=readiness_check or default_readiness_check(runtime_context),
        paper_executor=TradovBoxExecutor(paper_config),
        runtime_context=runtime_context,
        live_enabled=live_enabled,
        live_executor=TradierLiveExecutor(order_manager) if order_manager is not None else None,
        approval_gate=approval_gate,
        pending_store=PendingProposalStore(),
        trade_recorder=make_trade_recorder(session_db) if session_db is not None else None,
    )
    receiver = InboundSignalReceiver(
        secret=secret,
        host=host,
        port=port,
        handler=handler,
        audit_sink=audit_sink,
    )
    _logger.info("Inbound signal receiver bootstrapped (live_enabled=%s)", live_enabled)
    return receiver, handler, approval_gate
