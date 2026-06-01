"""Focused regressions for D31 paper Put Credit Spread 7 routing."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta

from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (
    SignalStrength,
    SignalType,
    TradingSignal,
)


class _StubEM:
    def subscribe(self, *args, **kwargs):
        return None

    def emit(self, *args, **kwargs):
        return None

    def publish(self, *args, **kwargs):
        return None

    def unsubscribe(self, *args, **kwargs):
        return None


def _make_orchestrator():
    mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )
    return mod.StrategyOrchestrator(event_manager=_StubEM())


def _wrapped_put_credit_spread_7_signal() -> dict[str, object]:
    now = datetime.now(UTC)
    expiry = now + timedelta(days=7)
    return {
        "signal": TradingSignal(
            signal_id="wrapped-pcs7-1",
            signal_type=SignalType.SELL,
            symbol="SPY",
            strength=SignalStrength.STRONG,
            confidence=0.79,
            entry_price=3.2,
            stop_loss=0.0,
            take_profit=0.0,
            position_size=40,
            timestamp=now,
            expires_at=now + timedelta(minutes=15),
            metadata={
                "strategy_id": "PutCreditSpread7",
                "strategy_name": "PutCreditSpread7",
                "strategy_type": "bull_put_credit_spread",
                "action": "sell",
                "short_put_strike": 557.0,
                "long_put_strike": 552.0,
                "spread_width": 5.0,
                "expiration_date": expiry.isoformat(),
                "legs": [
                    {
                        "role": "short_put",
                        "option_type": "put",
                        "position": "short",
                        "strike": 557.0,
                        "premium": 1.12,
                        "expiration_date": expiry.isoformat(),
                    },
                    {
                        "role": "long_put",
                        "option_type": "put",
                        "position": "long",
                        "strike": 552.0,
                        "premium": 0.80,
                        "expiration_date": expiry.isoformat(),
                    },
                ],
            },
        )
    }


def test_build_paper_put_credit_spread_7_leg_orders_for_entry() -> None:
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")

    raw_signal = _wrapped_put_credit_spread_7_signal()["signal"].to_dict()
    leg_orders = orch._build_paper_serialized_multileg_leg_orders(
        raw_signal,
        "SPY",
        40,
        "PutCreditSpread7",
    )

    expiry_code = datetime.fromisoformat(raw_signal["metadata"]["expiration_date"]).astimezone(UTC).strftime(
        "%y%m%d"
    )
    assert len(leg_orders) == 2
    assert [order["side"] for order in leg_orders] == ["sell_to_open", "buy_to_open"]
    assert [order["quantity"] for order in leg_orders] == [40, 40]
    assert [order["symbol"] for order in leg_orders] == [
        f"SPXW{expiry_code}P00557000",
        f"SPXW{expiry_code}P00552000",
    ]
    assert all(order["multileg_parent_symbol"] == "SPX" for order in leg_orders)


def test_dispatch_approved_signal_routes_put_credit_spread_7_in_paper_mode(monkeypatch) -> None:
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")
    monkeypatch.setattr(orch, "_get_duplicate_open_position_source", lambda *a, **k: None)

    dispatched_orders: list[dict[str, object]] = []

    class _EngineStub:
        def execute_order(self, order):
            dispatched_orders.append(dict(order))
            return {"status": "accepted", "order_id": f"ORD_{len(dispatched_orders)}"}

    orch._live_engine = _EngineStub()
    orch._order_manager = None

    orch._dispatch_approved_signal(_wrapped_put_credit_spread_7_signal())

    assert len(dispatched_orders) == 2
    assert [order["side"] for order in dispatched_orders] == ["sell_to_open", "buy_to_open"]
    assert [order["quantity"] for order in dispatched_orders] == [40, 40]
    assert all(order["symbol"] != "SPY" for order in dispatched_orders)
    assert all(order["strategy_id"] == "PutCreditSpread7" for order in dispatched_orders)
    assert all(order["multileg_leg_execution"] is True for order in dispatched_orders)
