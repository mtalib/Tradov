"""Focused regressions for D31 paper Broken Wing Butterfly routing."""

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


def _wrapped_bwb_signal() -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "signal": TradingSignal(
            signal_id="wrapped-bwb-1",
            signal_type=SignalType.SELL,
            symbol="SPY",
            strength=SignalStrength.STRONG,
            confidence=0.79,
            entry_price=0.65,
            stop_loss=0.0,
            take_profit=0.0,
            position_size=1,
            timestamp=now,
            expires_at=now + timedelta(minutes=15),
            metadata={
                "strategy_id": "BrokenWingButterfly",
                "strategy_type": "broken_wing_butterfly",
                "action": "sell",
                "upper_wing_strike": 600.0,
                "body_strike": 599.0,
                "lower_wing_strike": 596.0,
                "expected_credit": 0.65,
                "target_dte": 0,
            },
        )
    }


def test_build_paper_bwb_leg_orders_for_entry() -> None:
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")

    raw_signal = _wrapped_bwb_signal()["signal"].to_dict()
    leg_orders = orch._build_paper_butterfly_family_leg_orders(
        raw_signal,
        "SPY",
        1,
        "BrokenWingButterfly",
    )

    symbols = [order["symbol"] for order in leg_orders]
    assert len(leg_orders) == 3
    assert [order["side"] for order in leg_orders] == [
        "buy_to_open",
        "sell_to_open",
        "buy_to_open",
    ]
    assert [order["quantity"] for order in leg_orders] == [1, 2, 1]
    # D32 may normalize to the nearest listed expiration when the requested
    # same-day date is not listed (e.g., weekend/holiday). Validate stable
    # structure and strike mapping independent of calendar day.
    assert [bool(re.fullmatch(r"SPY\d{6}P\d{8}", symbol)) for symbol in symbols] == [
        True,
        True,
        True,
    ]
    assert [symbol[-8:] for symbol in symbols] == ["00600000", "00599000", "00596000"]
    assert len({symbol[3:9] for symbol in symbols}) == 1


def test_selector_chosen_bwb_is_allowed_in_lean_mode() -> None:
    orch = _make_orchestrator()

    assert "BrokenWingButterfly" in orch.lean_strategy_allowlist
    assert "BrokenWingButterflyStrategy" in orch.lean_strategy_allowlist


def test_high_vol_bullish_bwb_smoke_selects_strategy_and_dispatches(monkeypatch) -> None:
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")
    monkeypatch.setattr(orch, "_get_duplicate_open_position_source", lambda *a, **k: None)

    d31_mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )

    orch.lean_mode = True
    orch._initialize_strategy_registry()
    orch.market_regime.current_regime = d31_mod.MarketRegime.SIDEWAYS_HIGH_VOL
    orch._build_d30_consensus = MagicMock(return_value=SimpleNamespace())
    orch._d30_selector_init_attempted = True
    orch._d30_selector = SimpleNamespace(
        select_strategy_from_consensus=lambda *_args, **_kwargs: SimpleNamespace(
            selected_strategy=SimpleNamespace(value="broken_wing_butterfly"),
            reason="High-vol bullish pivot — Broken Wing Butterfly",
            selector_feature_flag=None,
        )
    )

    orch.add_strategy = MagicMock(return_value="bwb-strategy-id")
    orch._configure_strategies_for_regime()

    assert orch.add_strategy.call_count == 1
    strategy_cls = orch.add_strategy.call_args.args[0]
    assert strategy_cls.__name__ == "BrokenWingButterflyStrategy"

    dispatched_orders: list[dict[str, object]] = []

    class _EngineStub:
        def execute_order(self, order):
            dispatched_orders.append(dict(order))
            return {"status": "accepted", "order_id": f"ORD_{len(dispatched_orders)}"}

    orch._live_engine = _EngineStub()
    orch._order_manager = None

    orch._dispatch_approved_signal(_wrapped_bwb_signal())

    assert len(dispatched_orders) == 3
    assert [order["side"] for order in dispatched_orders] == [
        "buy_to_open",
        "sell_to_open",
        "buy_to_open",
    ]
    assert [order["quantity"] for order in dispatched_orders] == [1, 2, 1]
    assert all(order["symbol"] != "SPY" for order in dispatched_orders)
    assert all(order["strategy_id"] == "BrokenWingButterfly" for order in dispatched_orders)
    assert all(order["multileg_leg_execution"] is True for order in dispatched_orders)
