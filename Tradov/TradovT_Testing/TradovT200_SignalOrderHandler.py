#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovT_Testing
Module: TradovT200_SignalOrderHandler.py
Purpose: Tests for the signal -> proposal pipeline handler (Z11)

Covers the gate/risk/mode/execute pipeline with injected fakes (time-independent),
the real TradovBox paper executor, and an end-to-end POST through Z10.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest

from Tradov.TradovZ_Communication.TradovZ10_InboundSignalReceiver import (
    InboundSignalReceiver,
    SignalEnvelope,
)
from Tradov.TradovZ_Communication.TradovZ11_SignalOrderHandler import (
    SignalOrderHandler,
    TradovBoxExecutor,
)

ENVELOPE = SignalEnvelope(symbol="SPY", side="buy", quantity=10, order_type="market")


def _handler(**overrides):
    base = dict(
        risk_check=lambda req: {"approved": True, "max_safe_quantity": 100},
        readiness_check=lambda: (True, ""),
        paper_executor=lambda env, qty: {"order_id": "PAPER_1", "status": "filled", "avg_fill_price": 400.0},
        runtime_context=None,
        live_enabled=False,
    )
    base.update(overrides)
    return SignalOrderHandler(**base)


# --------------------------------------------------------------------------- #
# Pipeline stages
# --------------------------------------------------------------------------- #
def test_rejected_when_not_ready():
    h = _handler(readiness_check=lambda: (False, "Tradier execution API is disconnected"))
    out = h(ENVELOPE)
    assert out["disposition"] == "rejected"
    assert out["stage"] == "readiness"
    assert out["executed"] is False
    assert "disconnected" in out["reason"]


def test_rejected_by_risk():
    h = _handler(risk_check=lambda req: {"approved": False, "reason": "daily loss limit"})
    out = h(ENVELOPE)
    assert out["disposition"] == "rejected"
    assert out["stage"] == "risk"
    assert "daily loss limit" in out["reason"]


def test_paper_execution_accepted():
    captured = {}
    def exec_(env, qty):
        captured["qty"] = qty
        return {"order_id": "PAPER_42", "status": "filled", "avg_fill_price": 399.5}

    out = _handler(paper_executor=exec_)(ENVELOPE)
    assert out["disposition"] == "accepted"
    assert out["executed"] is True
    assert out["order_id"] == "PAPER_42"
    assert out["mode"] == "paper"
    assert captured["qty"] == 10


def test_quantity_clamped_by_risk():
    captured = {}
    out = _handler(
        risk_check=lambda req: {"approved": True, "max_safe_quantity": 3},
        paper_executor=lambda env, qty: captured.update(qty=qty) or {"order_id": "P", "status": "filled"},
    )(ENVELOPE)
    assert captured["qty"] == 3  # requested 10, clamped to 3
    assert out["executed"] is True


def test_quantity_sized_from_risk_when_unspecified():
    captured = {}
    env = SignalEnvelope(symbol="SPY", side="buy", quantity=None, order_type="market")
    _handler(
        risk_check=lambda req: {"approved": True, "max_safe_quantity": 7},
        paper_executor=lambda e, qty: captured.update(qty=qty) or {"order_id": "P", "status": "filled"},
    )(env)
    assert captured["qty"] == 7


def test_no_permitted_quantity_rejected():
    out = _handler(risk_check=lambda req: {"approved": True, "max_safe_quantity": 0})(ENVELOPE)
    assert out["disposition"] == "rejected"
    assert out["stage"] == "risk"


# --------------------------------------------------------------------------- #
# Mode routing
# --------------------------------------------------------------------------- #
def test_live_blocked_unless_enabled():
    live_ctx = SimpleNamespace(is_live=True)
    fired = {"called": False}
    out = _handler(
        runtime_context=live_ctx,
        live_enabled=False,
        paper_executor=lambda env, qty: fired.update(called=True) or {"order_id": "X"},
    )(ENVELOPE)
    assert out["disposition"] == "blocked"
    assert out["stage"] == "mode"
    assert fired["called"] is False  # never executed


def test_live_enabled_is_pending_not_fired():
    live_ctx = SimpleNamespace(is_live=True)
    fired = {"called": False}
    out = _handler(
        runtime_context=live_ctx,
        live_enabled=True,
        paper_executor=lambda env, qty: fired.update(called=True) or {"order_id": "X"},
    )(ENVELOPE)
    assert out["disposition"] == "pending_approval"
    assert out["executed"] is False
    assert fired["called"] is False  # no auto-fire even when enabled


def test_executor_error_fails_closed():
    def boom(env, qty):
        raise RuntimeError("engine down")

    out = _handler(paper_executor=boom)(ENVELOPE)
    assert out["disposition"] == "error"
    assert out["executed"] is False


# --------------------------------------------------------------------------- #
# Real TradovBox paper executor (R02 PaperEngine)
# --------------------------------------------------------------------------- #
def test_tradovbox_executor_fills_paper_order():
    executor = TradovBoxExecutor()
    result = executor(ENVELOPE, 10)
    assert result["order_id"]
    assert result["status"] in {"filled", "submitted"}


# --------------------------------------------------------------------------- #
# End-to-end: POST signal -> Z10 -> handler -> paper accepted
# --------------------------------------------------------------------------- #
def test_end_to_end_post_executes_paper():
    secret = "e2e-secret"
    handler = _handler()  # all fakes: ready, risk-approved, paper fill
    receiver = InboundSignalReceiver(secret=secret, host="127.0.0.1", port=0, handler=handler)
    receiver.start()
    try:
        body = json.dumps(
            {"symbol": "SPY", "side": "buy", "quantity": 10, "order_type": "market"}
        ).encode()
        req = urllib.request.Request(
            f"{receiver.url}/signal/{secret}", data=body, method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            status, payload = resp.status, json.loads(resp.read().decode())
        assert status == 200
        assert payload["disposition"] == "accepted"
        assert payload["executed"] is True
        assert payload["order_id"] == "PAPER_1"
    finally:
        receiver.stop()
