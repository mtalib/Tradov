"""Regression for wrapped TradingSignal payloads on D31 paper iron-condor dispatch."""

from __future__ import annotations

from collections import deque
import importlib
from datetime import datetime, timedelta, UTC
from types import SimpleNamespace

import pytest

from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (
    SignalStrength,
    SignalType,
    TradingSignal,
)
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType


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
    assert all(order["symbol"].startswith("SPXW") for order in leg_orders)
    assert all(order["multileg_parent_symbol"] == "SPX" for order in leg_orders)


def test_build_paper_iron_condor_leg_orders_resolves_listed_expiration(monkeypatch):
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")

    d31_mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )
    d32_mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD32_MultiLegStrategyCoordinator"
    )

    monkeypatch.setattr(
        d31_mod,
        "_d31_now_et",
        lambda: datetime(2026, 5, 20, 14, 30, tzinfo=UTC),
    )
    monkeypatch.setattr(
        d32_mod.MultiLegStrategyConstructor,
        "_get_live_option_expiration_dates",
        lambda self, symbol: [
            datetime(2026, 6, 18, tzinfo=UTC).date(),
            datetime(2026, 6, 26, tzinfo=UTC).date(),
        ],
    )

    leg_orders = orch._build_paper_iron_condor_leg_orders(
        {
            "strategy_id": "iron_condor",
            "strategy_type": "iron_condor",
            "symbol": "SPY",
            "action": "sell",
            "quantity": 1,
            "price": 1.25,
            "confidence": 0.72,
            "metadata": {
                "optimal_strikes": {
                    "long_put_strike": 730.0,
                    "short_put_strike": 735.0,
                    "short_call_strike": 750.0,
                    "long_call_strike": 755.0,
                },
            },
        },
        "SPY",
        1,
        "iron_condor",
    )

    assert len(leg_orders) == 4
    assert {order["expiration"] for order in leg_orders} == {"2026-06-18"}
    assert all(order["symbol"].startswith("SPXW260618") for order in leg_orders)
    assert all(order["multileg_parent_symbol"] == "SPX" for order in leg_orders)


def test_build_multileg_market_analysis_prefers_cached_symbol_price(monkeypatch):
    orch = _make_orchestrator()
    orch.market_data_cache = {"SPY": deque([{"last": 756.48}])}
    orch._regime_source_symbol = "SPY"
    monkeypatch.setattr(orch, "_enrich_market_df_with_options_metrics", lambda df: df)

    analysis = orch._build_multileg_market_analysis(
        {
            "strategy_id": "iron_condor",
            "strategy_type": "iron_condor",
            "symbol": "SPY",
            "price": 7580.0,
            "entry_price": 7580.0,
        },
        "SPY",
    )

    assert analysis is not None
    assert analysis.underlying_price == pytest.approx(756.48)


def test_build_paper_iron_condor_structure_binds_constructor_to_resolved_index_symbol(monkeypatch):
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")

    d32_mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD32_MultiLegStrategyCoordinator"
    )

    market_analysis = SimpleNamespace(
        underlying_price=756.48,
        implied_volatility=0.2,
        expected_move=12.0,
    )
    monkeypatch.setattr(orch, "_build_multileg_market_analysis", lambda *_args, **_kwargs: market_analysis)

    captured: dict[str, object] = {}
    dummy_structure = SimpleNamespace(strategy_type="iron_condor")

    def _capture_analysis(_signal, symbol):
        captured["analysis_symbol"] = symbol
        return market_analysis

    monkeypatch.setattr(orch, "_build_multileg_market_analysis", _capture_analysis)

    def _capture_construct(self, strategy_type, analysis, days_to_expiration=21):
        captured["config"] = dict(self.config)
        captured["strategy_type"] = strategy_type
        captured["analysis"] = analysis
        captured["days_to_expiration"] = days_to_expiration
        return dummy_structure

    monkeypatch.setattr(d32_mod.MultiLegStrategyConstructor, "construct_strategy", _capture_construct)

    structure = orch._build_paper_iron_condor_structure(
        {
            "strategy_id": "iron_condor",
            "strategy_type": "iron_condor",
            "symbol": "SPY",
            "price": 7580.0,
        },
        "SPY",
    )

    assert structure is dummy_structure
    assert captured["analysis_symbol"] == "SPX"
    assert captured["analysis"] is market_analysis
    assert captured["config"] == {"symbol": "SPX", "underlying_symbol": "SPX"}


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


def test_build_paper_serialized_multileg_leg_orders_normalizes_spy_to_spxw() -> None:
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")

    raw_signal = {
        "strategy_id": "BullishStrangle",
        "strategy_name": "BullishStrangle",
        "strategy_type": "bullish_strangle",
        "symbol": "SPY",
        "action": "buy",
        "quantity": 1,
        "metadata": {
            "strategy_id": "BullishStrangle",
            "strategy_type": "bullish_strangle",
            "expiration": "2026-06-18",
            "legs": [
                {
                    "role": "long_call",
                    "option_type": "call",
                    "position": "long",
                    "strike": 505.0,
                    "premium": 2.1,
                    "expiration": "2026-06-18",
                },
                {
                    "role": "long_put",
                    "option_type": "put",
                    "position": "long",
                    "strike": 492.0,
                    "premium": 1.9,
                    "expiration": "2026-06-18",
                },
            ],
        },
    }

    leg_orders = orch._build_paper_serialized_multileg_leg_orders(
        raw_signal,
        "SPY",
        1,
        "BullishStrangle",
    )

    assert len(leg_orders) == 2
    assert [order["symbol"] for order in leg_orders] == [
        "SPXW260618C00505000",
        "SPXW260618P00492000",
    ]
    assert all(order["multileg_parent_symbol"] == "SPX" for order in leg_orders)


def test_dispatch_approved_signal_blocks_paper_spy_option_entry(monkeypatch):
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")
    monkeypatch.setattr(orch, "_get_duplicate_open_position_source", lambda *a, **k: None)

    dispatched_orders: list[dict[str, object]] = []

    class _EngineStub:
        def execute_order(self, order):
            dispatched_orders.append(dict(order))
            return {"status": "accepted", "order_id": "ORD_OPEN_1"}

    orch._live_engine = _EngineStub()
    orch._order_manager = None

    orch._dispatch_approved_signal(
        {
            "strategy_id": "single_option",
            "strategy_type": "single_option",
            "symbol": "SPY260618C00750000",
            "action": "buy_to_open",
            "quantity": 1,
            "price": 1.23,
            "confidence": 0.8,
        }
    )

    assert dispatched_orders == []


def test_dispatch_approved_signal_suppresses_duplicate_close_until_position_updates(monkeypatch):
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")

    dispatched_orders: list[dict[str, object]] = []

    class _EngineStub:
        def execute_order(self, order):
            dispatched_orders.append(dict(order))
            return {"status": "accepted", "order_id": f"ORD_CLOSE_{len(dispatched_orders)}"}

    orch._live_engine = _EngineStub()
    orch._order_manager = None
    monkeypatch.setattr(orch, "_get_duplicate_open_position_source", lambda *a, **k: None)

    close_signal = {
        "strategy_id": "iron_condor",
        "strategy_type": "iron_condor",
        "symbol": "SPY260618C00776000",
        "action": "close",
        "side": "buy",
        "quantity": 1,
        "price": 1.37,
        "confidence": 0.8,
    }

    orch._dispatch_approved_signal(close_signal)
    orch._dispatch_approved_signal(close_signal)

    assert len(dispatched_orders) == 1

    orch._on_terminal_order_event(
        SimpleNamespace(
            event_type=EventType.ORDER_FILLED,
            data={
                "symbol": "SPY260618C00776000",
                "raw": {"symbol": "SPY260618C00776000"},
            },
        )
    )

    orch._dispatch_approved_signal(close_signal)

    assert len(dispatched_orders) == 1

    orch._on_position_updated(
        type(
            "_Evt",
            (),
            {"data": {"symbol": "SPY260618C00776000", "quantity": 0, "fill_price": 1.37}},
        )()
    )

    orch._dispatch_approved_signal(close_signal)

    assert len(dispatched_orders) == 2
