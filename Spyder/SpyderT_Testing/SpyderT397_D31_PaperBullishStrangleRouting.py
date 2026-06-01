"""Focused regressions for D31 paper Bullish Strangle routing."""

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


def _wrapped_bullish_strangle_signal() -> dict[str, object]:
    now = datetime.now(UTC)
    expiry = now + timedelta(days=30)
    return {
        "signal": TradingSignal(
            signal_id="wrapped-bullish-strangle-1",
            signal_type=SignalType.BUY,
            symbol="SPY",
            strength=SignalStrength.STRONG,
            confidence=0.78,
            entry_price=5.25,
            stop_loss=2.60,
            take_profit=8.65,
            position_size=1,
            timestamp=now,
            expires_at=now + timedelta(minutes=15),
            metadata={
                "strategy_id": "BullishStrangle",
                "strategy_name": "BullishStrangle",
                "strategy_type": "bullish_strangle",
                "action": "buy",
                "call_strike": 505.0,
                "put_strike": 492.0,
                "expiry": expiry.isoformat(),
                "legs": [
                    {
                        "role": "long_call",
                        "option_type": "call",
                        "position": "long",
                        "strike": 505.0,
                        "premium": 3.10,
                    },
                    {
                        "role": "long_put",
                        "option_type": "put",
                        "position": "long",
                        "strike": 492.0,
                        "premium": 2.15,
                    },
                ],
            },
        )
    }


def test_build_paper_bullish_strangle_leg_orders_for_entry() -> None:
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")

    raw_signal = _wrapped_bullish_strangle_signal()["signal"].to_dict()
    leg_orders = orch._build_paper_serialized_multileg_leg_orders(
        raw_signal,
        "SPY",
        1,
        "BullishStrangle",
    )

    expiry_code = datetime.fromisoformat(raw_signal["metadata"]["expiry"]).astimezone(UTC).strftime(
        "%y%m%d"
    )
    assert len(leg_orders) == 2
    assert [order["side"] for order in leg_orders] == ["buy_to_open", "buy_to_open"]
    assert [order["quantity"] for order in leg_orders] == [1, 1]
    assert [order["symbol"] for order in leg_orders] == [
        f"SPXW{expiry_code}C00505000",
        f"SPXW{expiry_code}P00492000",
    ]
    assert all(order["multileg_parent_symbol"] == "SPX" for order in leg_orders)


def test_recovery_bullish_strangle_smoke_selects_strategy_and_dispatches(monkeypatch) -> None:
    monkeypatch.setenv("SPYDER_ENABLE_BULLISH_STRANGLE", "1")

    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")
    monkeypatch.setattr(orch, "_get_duplicate_open_position_source", lambda *a, **k: None)

    d31_mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )

    orch.lean_mode = True
    orch._initialize_strategy_registry()
    orch.market_regime.current_regime = d31_mod.MarketRegime.RECOVERY
    orch._build_d30_consensus = MagicMock(return_value=SimpleNamespace())
    orch._d30_selector_init_attempted = True
    orch._d30_selector = SimpleNamespace(
        select_strategy_from_consensus=lambda *_args, **_kwargs: SimpleNamespace(
            selected_strategy=SimpleNamespace(value="bullish_strangle"),
            reason="Recovery regime — Bullish Strangle (feature-flag enabled)",
            selector_feature_flag="SPYDER_ENABLE_BULLISH_STRANGLE",
        )
    )

    orch.add_strategy = MagicMock(return_value="bullish-strangle-id")
    orch._configure_strategies_for_regime()

    assert orch.add_strategy.call_count == 1
    strategy_cls = orch.add_strategy.call_args.args[0]
    assert strategy_cls.__name__ == "BullishStrangleStrategy"

    dispatched_orders: list[dict[str, object]] = []

    class _EngineStub:
        def execute_order(self, order):
            dispatched_orders.append(dict(order))
            return {"status": "accepted", "order_id": f"ORD_{len(dispatched_orders)}"}

    orch._live_engine = _EngineStub()
    orch._order_manager = None

    orch._dispatch_approved_signal(_wrapped_bullish_strangle_signal())

    assert len(dispatched_orders) == 2
    assert [order["side"] for order in dispatched_orders] == ["buy_to_open", "buy_to_open"]
    assert [order["quantity"] for order in dispatched_orders] == [1, 1]
    assert all(order["symbol"] != "SPY" for order in dispatched_orders)
    assert all(order["strategy_id"] == "BullishStrangle" for order in dispatched_orders)
    assert all(order["multileg_leg_execution"] is True for order in dispatched_orders)
