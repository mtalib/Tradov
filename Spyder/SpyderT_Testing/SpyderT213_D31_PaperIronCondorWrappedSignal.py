"""Regression for wrapped TradingSignal payloads on D31 paper iron-condor dispatch."""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone, UTC

from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (
    SignalStrength,
    SignalType,
    TradingSignal,
)


class _StubEM:
    def subscribe(self, *a, **k):
        return None

    def emit(self, *a, **k):
        return None

    def publish(self, *a, **k):
        return None

    def unsubscribe(self, *a, **k):
        return None


def _make_orchestrator():
    mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )
    return mod.StrategyOrchestrator(event_manager=_StubEM())


def _wrapped_iron_condor_signal() -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "signal": TradingSignal(
            signal_id="wrapped-ic-1",
            signal_type=SignalType.SELL,
            symbol="SPY",
            strength=SignalStrength.STRONG,
            confidence=0.72,
            entry_price=1.25,
            stop_loss=0.0,
            take_profit=0.0,
            position_size=1,
            timestamp=now,
            expires_at=now + timedelta(minutes=30),
            metadata={
                "strategy_id": "iron_condor",
                "strategy_type": "iron_condor",
                "optimal_strikes": {
                    "long_put_strike": 730.0,
                    "short_put_strike": 735.0,
                    "short_call_strike": 750.0,
                    "long_call_strike": 755.0,
                },
            },
        )
    }


def test_dispatch_approved_signal_preserves_wrapped_iron_condor_payload(monkeypatch):
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")
    orch._live_engine = object()
    monkeypatch.setattr(orch, "_has_duplicate_open_position", lambda *a, **k: False)

    captured: dict[str, object] = {}

    def _capture_dispatch(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(orch, "_dispatch_paper_iron_condor", _capture_dispatch)

    orch._dispatch_approved_signal(_wrapped_iron_condor_signal())

    assert captured
    raw_signal = captured["raw_signal"]
    assert isinstance(raw_signal, dict)
    assert raw_signal["strategy_id"] == "iron_condor"
    assert raw_signal["metadata"]["optimal_strikes"]["short_put_strike"] == 735.0

    leg_orders = orch._build_paper_iron_condor_leg_orders(
        raw_signal,
        "SPY",
        1,
        "iron_condor",
    )

    assert len(leg_orders) == 4
    assert [order["side"] for order in leg_orders] == [
        "buy_to_open",
        "sell_to_open",
        "sell_to_open",
        "buy_to_open",
    ]


def test_dispatch_approved_signal_keeps_option_leg_close_off_condor_builder(monkeypatch):
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")

    captured_order: dict[str, object] = {}

    class _EngineStub:
        def execute_order(self, order):
            captured_order.update(order)
            return {"status": "accepted", "order_id": "ORD_CLOSE_1"}

    orch._live_engine = _EngineStub()
    orch._order_manager = None
    monkeypatch.setattr(orch, "_get_duplicate_open_position_source", lambda *a, **k: None)

    condor_dispatch_called = {"value": False}

    def _unexpected_condor_dispatch(**kwargs):
        condor_dispatch_called["value"] = True

    monkeypatch.setattr(orch, "_dispatch_paper_iron_condor", _unexpected_condor_dispatch)

    orch._dispatch_approved_signal(
        {
            "strategy_id": "iron_condor",
            "strategy_type": "iron_condor",
            "symbol": "SPY260618P00699000",
            "action": "close",
            "side": "buy",
            "quantity": 1,
            "price": 4.21,
            "confidence": 0.8,
        }
    )

    assert condor_dispatch_called["value"] is False
    assert captured_order["symbol"] == "SPY260618P00699000"
    assert captured_order["side"] == "close"
    assert captured_order["quantity"] == 1
