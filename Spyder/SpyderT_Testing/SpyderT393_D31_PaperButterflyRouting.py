"""Focused regressions for D31 paper Butterfly routing."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta
import re
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


def _wrapped_butterfly_signal() -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "signal": TradingSignal(
            signal_id="wrapped-bfly-1",
            signal_type=SignalType.BUY,
            symbol="SPY",
            strength=SignalStrength.STRONG,
            confidence=0.81,
            entry_price=0.35,
            stop_loss=0.15,
            take_profit=0.63,
            position_size=1,
            timestamp=now,
            expires_at=now + timedelta(minutes=15),
            metadata={
                "strategy_id": "Butterfly",
                "strategy_type": "butterfly",
                "action": "buy",
                "structure": "long_call_butterfly",
                "lower_strike": 598.0,
                "body_strike": 599.0,
                "upper_strike": 600.0,
                "expected_debit": 0.35,
                "target_dte": 0,
                "days_to_expiry": 0,
            },
        )
    }


def test_build_paper_butterfly_leg_orders_for_entry() -> None:
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")

    raw_signal = _wrapped_butterfly_signal()["signal"].to_dict()
    leg_orders = orch._build_paper_butterfly_family_leg_orders(
        raw_signal,
        "SPY",
        1,
        "Butterfly",
    )

    symbols = [order["symbol"] for order in leg_orders]
    assert len(leg_orders) == 3
    assert [order["side"] for order in leg_orders] == [
        "buy_to_open",
        "sell_to_open",
        "buy_to_open",
    ]
    assert [order["quantity"] for order in leg_orders] == [1, 2, 1]
    # D32 can shift to the nearest listed expiration for weekends/holidays.
    assert [bool(re.fullmatch(r"SPY\d{6}C\d{8}", symbol)) for symbol in symbols] == [
        True,
        True,
        True,
    ]
    assert [symbol[-8:] for symbol in symbols] == ["00598000", "00599000", "00600000"]
    assert len({symbol[3:9] for symbol in symbols}) == 1


def test_build_paper_butterfly_leg_orders_prefers_live_chain_mid_prices(monkeypatch) -> None:
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")

    d32_mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD32_MultiLegStrategyCoordinator"
    )

    def _fake_get_live_option_chain_strikes(self, symbol: str, expiration: str):
        self._live_chain_prices_cache = {
            ("call", 598.0): 1.54,
            ("call", 599.0): 0.94,
            ("call", 600.0): 0.69,
        }
        return {"call": [598.0, 599.0, 600.0]}

    monkeypatch.setattr(
        d32_mod.MultiLegStrategyConstructor,
        "_get_live_option_chain_strikes",
        _fake_get_live_option_chain_strikes,
    )

    raw_signal = _wrapped_butterfly_signal()["signal"].to_dict()
    leg_orders = orch._build_paper_butterfly_family_leg_orders(
        raw_signal,
        "SPY",
        1,
        "Butterfly",
    )

    assert [order["price"] for order in leg_orders] == [1.54, 0.94, 0.69]


def test_selector_chosen_butterfly_is_allowed_in_lean_mode() -> None:
    orch = _make_orchestrator()

    assert "Butterfly" in orch.lean_strategy_allowlist
    assert "ButterflyStrategy" in orch.lean_strategy_allowlist


def test_range_calm_butterfly_smoke_selects_strategy_and_dispatches(monkeypatch) -> None:
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
            selected_strategy=SimpleNamespace(value="butterfly"),
            reason="Range/calm — Butterfly (feature-flag enabled)",
            selector_feature_flag="SPYDER_ENABLE_BUTTERFLY",
        )
    )

    orch.add_strategy = MagicMock(return_value="butterfly-strategy-id")
    orch._configure_strategies_for_regime()

    assert orch.add_strategy.call_count == 1
    strategy_cls = orch.add_strategy.call_args.args[0]
    assert strategy_cls.__name__ == "ButterflyStrategy"

    dispatched_orders: list[dict[str, object]] = []

    class _EngineStub:
        def execute_order(self, order):
            dispatched_orders.append(dict(order))
            return {"status": "accepted", "order_id": f"ORD_{len(dispatched_orders)}"}

    orch._live_engine = _EngineStub()
    orch._order_manager = None

    orch._dispatch_approved_signal(_wrapped_butterfly_signal())

    assert len(dispatched_orders) == 3
    assert [order["side"] for order in dispatched_orders] == [
        "buy_to_open",
        "sell_to_open",
        "buy_to_open",
    ]
    assert [order["quantity"] for order in dispatched_orders] == [1, 2, 1]
    assert all(order["symbol"] != "SPY" for order in dispatched_orders)
    assert all(order["strategy_id"] == "Butterfly" for order in dispatched_orders)
    assert all(order["multileg_leg_execution"] is True for order in dispatched_orders)


def test_dispatch_approved_signal_rolls_back_accepted_butterfly_legs_when_later_leg_rejects(monkeypatch) -> None:
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")
    monkeypatch.setattr(orch, "_get_duplicate_open_position_source", lambda *a, **k: None)

    submitted_orders: list[dict[str, object]] = []
    cancel_attempts: list[str] = []

    class _EngineStub:
        def execute_order(self, order):
            submitted_orders.append(dict(order))
            call_no = len(submitted_orders)
            if call_no == 1:
                return {"status": "accepted", "order_id": "LEG_1"}
            if call_no == 2:
                return {"status": "accepted", "order_id": "LEG_2"}
            if call_no == 3:
                return {"status": "rejected", "reason": "quote_unavailable"}
            return {"status": "accepted", "order_id": f"ROLL_{call_no}"}

        def cancel_order(self, order_id):
            cancel_attempts.append(str(order_id))
            return False

    orch._live_engine = _EngineStub()
    orch._order_manager = None

    orch._dispatch_approved_signal(_wrapped_butterfly_signal())

    assert cancel_attempts == ["LEG_2", "LEG_1"]
    assert len(submitted_orders) == 5
    assert [order["side"] for order in submitted_orders[:3]] == [
        "buy_to_open",
        "sell_to_open",
        "buy_to_open",
    ]
    assert [order["side"] for order in submitted_orders[3:]] == [
        "buy_to_close",
        "sell_to_close",
    ]
    assert [order["quantity"] for order in submitted_orders[3:]] == [2, 1]
    assert [order["symbol"] for order in submitted_orders[3:]] == [
        submitted_orders[1]["symbol"],
        submitted_orders[0]["symbol"],
    ]
    assert all(order["order_type"] == "market" for order in submitted_orders[3:])
    assert all(order["rollback_compensation"] is True for order in submitted_orders[3:])
