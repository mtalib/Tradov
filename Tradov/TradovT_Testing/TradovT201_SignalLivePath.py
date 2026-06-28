#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovT_Testing
Module: TradovT201_SignalLivePath.py
Purpose: Phase-5 tests — idempotency, manual-approval live path, adapters

Covers handler idempotency, the approval-gated live submission flow (no
auto-fire), trade recording, the B02/H05 adapters, and the session bootstrap.
"""

from __future__ import annotations

from types import SimpleNamespace

from Tradov.TradovZ_Communication.TradovZ10_InboundSignalReceiver import SignalEnvelope
from Tradov.TradovZ_Communication.TradovZ11_SignalOrderHandler import SignalOrderHandler
from Tradov.TradovZ_Communication.TradovZ12_SignalLiveAdapters import (
    TradierLiveExecutor,
    bootstrap_inbound_receiver,
    make_trade_recorder,
)

LIVE_CTX = SimpleNamespace(is_live=True)


def _handler(**overrides):
    base = dict(
        risk_check=lambda req: {"approved": True, "max_safe_quantity": 100},
        readiness_check=lambda: (True, ""),
        paper_executor=lambda env, qty: {"order_id": "PAPER_1", "status": "filled", "avg_fill_price": 400.0},
    )
    base.update(overrides)
    return SignalOrderHandler(**base)


# --------------------------------------------------------------------------- #
# Idempotency
# --------------------------------------------------------------------------- #
def test_idempotent_replay_does_not_re_execute():
    calls = {"n": 0}

    def exec_(env, qty):
        calls["n"] += 1
        return {"order_id": f"P{calls['n']}", "status": "filled"}

    h = _handler(paper_executor=exec_)
    env = SignalEnvelope(symbol="SPY", side="buy", quantity=1, client_tag="tv-1")
    first = h(env)
    second = h(env)
    assert calls["n"] == 1  # executed once
    assert first["order_id"] == "P1"
    assert second.get("idempotent_replay") is True
    assert second["order_id"] == "P1"


def test_no_tag_means_no_dedup():
    calls = {"n": 0}
    h = _handler(paper_executor=lambda e, q: calls.update(n=calls["n"] + 1) or {"order_id": "P", "status": "filled"})
    env = SignalEnvelope(symbol="SPY", side="buy", quantity=1)  # no client_tag
    h(env)
    h(env)
    assert calls["n"] == 2


# --------------------------------------------------------------------------- #
# Manual-approval live path
# --------------------------------------------------------------------------- #
def test_live_enabled_registers_pending_and_does_not_fire():
    fired = {"called": False}
    h = _handler(
        runtime_context=LIVE_CTX,
        live_enabled=True,
        live_executor=lambda env, qty: fired.update(called=True) or {"order_id": "L1"},
    )
    env = SignalEnvelope(symbol="SPY", side="buy", quantity=5, client_tag="tv-9")
    out = h(env)
    assert out["disposition"] == "pending_approval"
    assert out["proposal_id"] == "tv-9"
    assert fired["called"] is False
    assert h.pending.get("tv-9") is not None


def test_submit_approved_requires_approval():
    h = _handler(runtime_context=LIVE_CTX, live_enabled=True,
                 live_executor=lambda env, qty: {"order_id": "L1", "status": "submitted"})
    h(SignalEnvelope(symbol="SPY", side="buy", quantity=5, client_tag="tv-9"))
    # Not approved yet
    blocked = h.submit_approved("tv-9")
    assert blocked["disposition"] == "rejected"
    assert blocked["stage"] == "approval"


def test_approve_then_submit_fires_live():
    fired = {}
    h = _handler(
        runtime_context=LIVE_CTX,
        live_enabled=True,
        live_executor=lambda env, qty: fired.update(env=env, qty=qty) or {"order_id": "L42", "status": "submitted", "avg_fill_price": 401.0},
    )
    h(SignalEnvelope(symbol="SPY", side="buy", quantity=5, client_tag="tv-9"))
    h.approval_gate.approve("tv-9")
    out = h.submit_approved("tv-9")
    assert out["disposition"] == "accepted"
    assert out["mode"] == "live"
    assert out["order_id"] == "L42"
    assert fired["qty"] == 5
    assert h.pending.get("tv-9") is None  # consumed


def test_submit_approved_unknown_proposal():
    h = _handler(runtime_context=LIVE_CTX, live_enabled=True,
                 live_executor=lambda env, qty: {"order_id": "X"})
    h.approval_gate.approve("ghost")
    out = h.submit_approved("ghost")
    assert out["disposition"] == "rejected"


def test_live_without_executor_errors_on_submit():
    h = _handler(runtime_context=LIVE_CTX, live_enabled=True, live_executor=None)
    h(SignalEnvelope(symbol="SPY", side="buy", quantity=5, client_tag="tv-9"))
    h.approval_gate.approve("tv-9")
    out = h.submit_approved("tv-9")
    assert out["disposition"] == "error"


# --------------------------------------------------------------------------- #
# Trade recorder
# --------------------------------------------------------------------------- #
def test_trade_recorder_called_on_paper_fill():
    recorded = []
    h = _handler(trade_recorder=lambda env, qty, res: recorded.append((env.symbol, qty, res["order_id"])))
    h(SignalEnvelope(symbol="SPY", side="buy", quantity=2))
    assert recorded == [("SPY", 2, "PAPER_1")]


# --------------------------------------------------------------------------- #
# Adapters
# --------------------------------------------------------------------------- #
def test_tradier_live_executor_maps_to_order_manager():
    captured = {}

    class FakeOM:
        def create_order(self, **kw):
            captured.update(kw)
            return SimpleNamespace(**kw)

        def submit_order(self, order):
            return SimpleNamespace(success=True, order_id="OM-7", tradier_order_id=7, message=None)

    out = TradierLiveExecutor(FakeOM())(
        SignalEnvelope(symbol="SPY", side="buy", quantity=4, order_type="market"), 4
    )
    assert out["order_id"] == "OM-7"
    assert captured["symbol"] == "SPY"
    assert captured["quantity"] == 4


def test_tradier_live_executor_handles_rejection():
    class FakeOM:
        def create_order(self, **kw):
            return SimpleNamespace(**kw)

        def submit_order(self, order):
            return SimpleNamespace(success=False, order_id="", message="insufficient buying power")

    out = TradierLiveExecutor(FakeOM())(SignalEnvelope(symbol="SPY", side="buy", quantity=4), 4)
    assert out["order_id"] == ""
    assert "buying power" in out["status"]


def test_make_trade_recorder_calls_record_trade():
    captured = {}

    class FakeDB:
        def record_trade(self, **kw):
            captured.update(kw)
            return "trade-1"

    recorder = make_trade_recorder(FakeDB())
    recorder(
        SignalEnvelope(symbol="SPY", side="buy", quantity=3, strategy="manual", source="tv"),
        3,
        {"order_id": "P9", "avg_fill_price": 400.25},
    )
    assert captured["symbol"] == "SPY"
    assert captured["trade_type"] == "BUY"
    assert captured["quantity"] == 3
    assert captured["price"] == 400.25
    assert captured["order_id"] == "P9"


# --------------------------------------------------------------------------- #
# Bootstrap
# --------------------------------------------------------------------------- #
def test_bootstrap_wires_handler_and_gate():
    receiver, handler, gate = bootstrap_inbound_receiver(
        secret="s",
        risk_check=lambda req: {"approved": True, "max_safe_quantity": 10},
        readiness_check=lambda: (True, ""),  # avoid real time/network gate in test
        port=0,
    )
    assert isinstance(handler, SignalOrderHandler)
    assert gate is handler.approval_gate
    # paper path works end-to-end through the bootstrapped handler
    out = handler(SignalEnvelope(symbol="SPY", side="buy", quantity=1))
    assert out["disposition"] == "accepted"
    assert out["mode"] == "paper"
