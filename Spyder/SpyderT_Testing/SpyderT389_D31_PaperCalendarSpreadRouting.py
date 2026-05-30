"""Focused regressions for D31 paper calendar-spread routing."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

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


def _calendar_setup_payload() -> dict[str, object]:
    return {
        "calendar_type": "call_calendar",
        "near_leg": {
            "option_type": "call",
            "strike": 600.0,
            "expiry": "2026-06-19",
            "position": -1,
            "contracts": 1,
            "premium": 2.1,
        },
        "far_leg": {
            "option_type": "call",
            "strike": 600.0,
            "expiry": "2026-07-17",
            "position": 1,
            "contracts": 1,
            "premium": 4.2,
        },
    }


def _calendar_signal_dict(action: str = "buy") -> dict[str, object]:
    return {
        "strategy_id": "CalendarSpread",
        "strategy_type": "CalendarSpread",
        "symbol": "SPY",
        "action": action,
        "quantity": 1,
        "price": 3.1,
        "confidence": 0.72,
        "metadata": {
            "strategy_id": "CalendarSpread",
            "strategy_type": "CalendarSpread",
            "action": action,
            "setup": _calendar_setup_payload(),
        },
    }


def _wrapped_calendar_signal() -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "signal": TradingSignal(
            signal_id="wrapped-calendar-1",
            signal_type=SignalType.BUY,
            symbol="SPY",
            strength=SignalStrength.MODERATE,
            confidence=0.72,
            entry_price=3.1,
            stop_loss=0.0,
            take_profit=0.0,
            position_size=1,
            timestamp=now,
            expires_at=now + timedelta(minutes=15),
            metadata={
                "strategy_id": "CalendarSpread",
                "strategy_type": "CalendarSpread",
                "action": "buy",
                "setup": _calendar_setup_payload(),
            },
        )
    }


def test_build_paper_calendar_spread_leg_orders_for_entry() -> None:
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")

    leg_orders = orch._build_paper_calendar_spread_leg_orders(
        _calendar_signal_dict(action="buy"),
        "SPY",
        1,
        "CalendarSpread",
    )

    assert len(leg_orders) == 2
    assert [order["side"] for order in leg_orders] == ["sell_to_open", "buy_to_open"]
    assert [order["symbol"] for order in leg_orders] == [
        "SPY260619C00600000",
        "SPY260717C00600000",
    ]


def test_build_paper_calendar_spread_leg_orders_for_close() -> None:
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")

    leg_orders = orch._build_paper_calendar_spread_leg_orders(
        _calendar_signal_dict(action="close"),
        "SPY",
        1,
        "CalendarSpread",
    )

    assert len(leg_orders) == 2
    assert [order["side"] for order in leg_orders] == ["buy_to_close", "sell_to_close"]


def test_dispatch_approved_signal_routes_wrapped_calendar_spread_in_paper_mode(monkeypatch) -> None:
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")
    monkeypatch.setenv("SPYDER_ENABLE_PAPER_CALENDAR_SPREAD_ROUTING", "1")
    monkeypatch.setattr(orch, "_get_duplicate_open_position_source", lambda *a, **k: None)

    dispatched_orders: list[dict[str, object]] = []

    class _EngineStub:
        def execute_order(self, order):
            dispatched_orders.append(dict(order))
            return {"status": "accepted", "order_id": f"ORD_{len(dispatched_orders)}"}

    orch._live_engine = _EngineStub()
    orch._order_manager = None

    orch._dispatch_approved_signal(_wrapped_calendar_signal())

    assert len(dispatched_orders) == 2
    assert [order["side"] for order in dispatched_orders] == ["sell_to_open", "buy_to_open"]


def test_low_vol_paper_calendar_smoke_selects_strategy_and_dispatches(monkeypatch) -> None:
    monkeypatch.setenv("SPYDER_ENABLE_PAPER_CALENDAR_SPREAD_ROUTING", "1")

    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")
    monkeypatch.setattr(orch, "_get_duplicate_open_position_source", lambda *a, **k: None)

    d31_mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )

    orch.lean_mode = True
    orch._initialize_strategy_registry()
    orch.market_regime.current_regime = d31_mod.MarketRegime.SIDEWAYS_LOW_VOL
    orch._build_d30_consensus = MagicMock(return_value=SimpleNamespace())
    orch._d30_selector_init_attempted = True
    orch._d30_selector = SimpleNamespace(
        select_strategy_from_consensus=lambda *_args, **_kwargs: SimpleNamespace(
            selected_strategy=SimpleNamespace(value="iron_condor"),
            reason="Range/calm — Iron Condor",
            selector_feature_flag=None,
        )
    )

    orch.add_strategy = MagicMock(return_value="calendar-strategy-id")
    orch._configure_strategies_for_regime()

    assert orch.add_strategy.call_count == 1
    strategy_cls = orch.add_strategy.call_args.args[0]
    assert strategy_cls.__name__ == "CalendarSpreadStrategy"

    dispatched_orders: list[dict[str, object]] = []

    class _EngineStub:
        def execute_order(self, order):
            dispatched_orders.append(dict(order))
            return {"status": "accepted", "order_id": f"ORD_{len(dispatched_orders)}"}

    orch._live_engine = _EngineStub()
    orch._order_manager = None

    orch._dispatch_approved_signal(_wrapped_calendar_signal())

    assert len(dispatched_orders) == 2
    assert [order["side"] for order in dispatched_orders] == ["sell_to_open", "buy_to_open"]
