"""Focused regressions for D31 paper Iron Butterfly routing."""

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


def _wrapped_iron_butterfly_signal() -> dict[str, object]:
    now = datetime.now(UTC)
    expiration = "2026-06-19T00:00:00+00:00"
    return {
        "signal": TradingSignal(
            signal_id="wrapped-ib-1",
            signal_type=SignalType.SELL,
            symbol="SPY",
            strength=SignalStrength.STRONG,
            confidence=0.77,
            entry_price=1.28,
            stop_loss=0.0,
            take_profit=0.0,
            position_size=1,
            timestamp=now,
            expires_at=now + timedelta(minutes=15),
            metadata={
                "strategy_id": "IronButterfly",
                "strategy_type": "iron_butterfly",
                "action": "sell",
                "atm_strike": 599.0,
                "short_put_strike": 599.0,
                "short_call_strike": 599.0,
                "long_put_strike": 594.0,
                "long_call_strike": 604.0,
                "expected_credit": 1.28,
                "target_dte": 25,
                "expiration_date": expiration,
                "setup": {
                    "strikes": {
                        "put_long": 594.0,
                        "put_short": 599.0,
                        "call_short": 599.0,
                        "call_long": 604.0,
                    },
                    "credit": 1.28,
                    "dte": 25,
                    "expiration_time": expiration,
                },
            },
        )
    }


def test_build_paper_iron_butterfly_leg_orders_for_entry() -> None:
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")
    orch._resolve_paper_multileg_expiration = (
        lambda signal, symbol, constructor, expiration_dt, dte_value: datetime(2026, 6, 19, tzinfo=UTC)
    )

    raw_signal = _wrapped_iron_butterfly_signal()["signal"].to_dict()
    leg_orders = orch._build_paper_iron_butterfly_leg_orders(
        raw_signal,
        "SPY",
        1,
        "IronButterfly",
    )

    assert len(leg_orders) == 4
    assert [order["side"] for order in leg_orders] == [
        "buy_to_open",
        "sell_to_open",
        "sell_to_open",
        "buy_to_open",
    ]
    assert [order["symbol"] for order in leg_orders] == [
        "SPXW260619P00594000",
        "SPXW260619P00599000",
        "SPXW260619C00599000",
        "SPXW260619C00604000",
    ]
    assert all(order["multileg_parent_symbol"] == "SPX" for order in leg_orders)


def test_build_paper_iron_butterfly_leg_orders_prefers_live_chain_mid_prices(monkeypatch) -> None:
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")
    orch._resolve_paper_multileg_expiration = (
        lambda signal, symbol, constructor, expiration_dt, dte_value: datetime(2026, 6, 19, tzinfo=UTC)
    )

    d32_mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD32_MultiLegStrategyCoordinator"
    )

    def _fake_get_live_option_chain_strikes(self, symbol: str, expiration: str):
        self._live_chain_prices_cache = {
            ("put", 594.0): 0.55,
            ("put", 599.0): 1.15,
            ("call", 599.0): 1.18,
            ("call", 604.0): 0.50,
        }
        return {"put": [594.0, 599.0], "call": [599.0, 604.0]}

    monkeypatch.setattr(
        d32_mod.MultiLegStrategyConstructor,
        "_get_live_option_chain_strikes",
        _fake_get_live_option_chain_strikes,
    )

    raw_signal = _wrapped_iron_butterfly_signal()["signal"].to_dict()
    leg_orders = orch._build_paper_iron_butterfly_leg_orders(
        raw_signal,
        "SPY",
        1,
        "IronButterfly",
    )

    assert [order["price"] for order in leg_orders] == [0.55, 1.15, 1.18, 0.50]


def test_dispatch_approved_signal_routes_wrapped_iron_butterfly_in_paper_mode(monkeypatch) -> None:
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")
    monkeypatch.setattr(orch, "_get_duplicate_open_position_source", lambda *a, **k: None)
    monkeypatch.setattr(
        orch,
        "_resolve_paper_multileg_expiration",
        lambda signal, symbol, constructor, expiration_dt, dte_value: datetime(2026, 6, 19, tzinfo=UTC),
    )

    dispatched_orders: list[dict[str, object]] = []

    class _EngineStub:
        def execute_order(self, order):
            dispatched_orders.append(dict(order))
            return {"status": "accepted", "order_id": f"ORD_{len(dispatched_orders)}"}

    orch._live_engine = _EngineStub()
    orch._order_manager = None

    orch._dispatch_approved_signal(_wrapped_iron_butterfly_signal())

    assert len(dispatched_orders) == 4
    assert [order["side"] for order in dispatched_orders] == [
        "buy_to_open",
        "sell_to_open",
        "sell_to_open",
        "buy_to_open",
    ]
    assert all(order["symbol"] != "SPY" for order in dispatched_orders)
    assert all(order["strategy_id"] == "IronButterfly" for order in dispatched_orders)
    assert all(order["multileg_leg_execution"] is True for order in dispatched_orders)
