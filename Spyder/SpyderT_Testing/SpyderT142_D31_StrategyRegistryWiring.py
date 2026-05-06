#!/usr/bin/env python3
"""Focused tests for D31 strategy registry and auto-selection wiring."""

import importlib
from unittest.mock import MagicMock
from types import SimpleNamespace
from datetime import datetime, timezone

import pandas as pd


def _make_orchestrator():
    """Lazily import D31 to avoid heavy GUI/native import at collection time."""
    mod = importlib.import_module("Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator")
    strategy_orchestrator_cls = mod.StrategyOrchestrator
    orchestrator = strategy_orchestrator_cls(event_manager=_StubEventManager())
    # These tests validate legacy/full registry wiring rather than lean-mode allowlisting.
    orchestrator.lean_mode = False
    orchestrator._initialize_strategy_registry()
    return orchestrator


class _StubEventManager:
    def __init__(self):
        self.handlers = {}

    def subscribe(self, event_type, handler):
        self.handlers.setdefault(event_type, []).append(handler)

    def emit(self, *args, **kwargs):
        return None


def test_d31_registry_includes_first_wave_base_strategies():
    orchestrator = _make_orchestrator()
    base_strategy_cls = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy"
    ).BaseStrategy

    expected = {
        "RSIMeanReversion",
        "MACrossover",
        "RenaissanceMeanReversion",
        "PivotMeanReversion",
        "EvolvedCreditSpread",
        "VIXHedging",
        "BullCallSpread",
        "BearPutSpread",
    }

    missing = expected - set(orchestrator.available_strategies)
    assert not missing, f"Missing strategy registrations: {sorted(missing)}"

    for name in expected:
        strategy_cls = orchestrator.available_strategies[name]
        assert issubclass(strategy_cls, base_strategy_cls) or any(
            base.__name__ == "BaseStrategy" for base in strategy_cls.__mro__
        )


def test_d31_configure_regime_selects_newly_wired_strategies():
    orchestrator = _make_orchestrator()

    # Force a deterministic weight map so we only test selection logic.
    orchestrator._get_regime_strategy_weights = lambda: {
        "RSIMeanReversion": 0.3,
        "MACrossover": 0.2,
        "RenaissanceMeanReversion": 0.6,
        "PivotMeanReversion": 0.4,
    }
    orchestrator.add_strategy = MagicMock(return_value="strategy-id")

    orchestrator._configure_strategies_for_regime()

    called_classes = [call.args[0] for call in orchestrator.add_strategy.call_args_list]
    assert orchestrator.available_strategies["RSIMeanReversion"] in called_classes
    assert orchestrator.available_strategies["MACrossover"] in called_classes
    assert orchestrator.available_strategies["RenaissanceMeanReversion"] in called_classes
    assert orchestrator.available_strategies["PivotMeanReversion"] in called_classes


def test_d31_current_regime_weights_are_registry_reachable_and_constructible():
    orchestrator = _make_orchestrator()
    weights = orchestrator._get_regime_strategy_weights()

    if weights and all(isinstance(v, (int, float)) for v in weights.values()):
        weighted_names = set(weights.keys())
    else:
        weighted_names = set().union(*[set(v.keys()) for v in weights.values()]) if weights else set()

    missing = weighted_names - set(orchestrator.available_strategies)
    assert not missing, f"Current-regime weighted strategies missing from registry: {sorted(missing)}"

    risk_profile = SimpleNamespace(account_size=100000)
    for name in sorted(weighted_names):
        cls = orchestrator.available_strategies[name]
        try:
            instance = cls(name=name, event_manager=_StubEventManager(), risk_profile=risk_profile, config={})
        except TypeError:
            instance = cls(event_manager=_StubEventManager(), risk_profile=risk_profile, config={})
        assert instance is not None, f"Failed to construct weighted strategy: {name}"


def test_d31_lean_allowlist_enables_debit_spread_extensions_via_feature_flags(monkeypatch):
    monkeypatch.setenv("SPYDER_ENABLE_BULL_CALL_SPREAD", "true")
    monkeypatch.setenv("SPYDER_ENABLE_BEAR_PUT_SPREAD", "true")

    mod = importlib.import_module("Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator")
    orchestrator = mod.StrategyOrchestrator(event_manager=_StubEventManager())

    assert "BullCallSpread" in orchestrator.lean_strategy_allowlist
    assert "BearPutSpread" in orchestrator.lean_strategy_allowlist

    orchestrator.lean_mode = True
    orchestrator._initialize_strategy_registry()

    assert "BullCallSpread" in orchestrator.available_strategies
    assert "BearPutSpread" in orchestrator.available_strategies


def test_d31_lean_allowlist_keeps_debit_spread_extensions_disabled_without_flags(monkeypatch):
    monkeypatch.delenv("SPYDER_ENABLE_BULL_CALL_SPREAD", raising=False)
    monkeypatch.delenv("SPYDER_ENABLE_BEAR_PUT_SPREAD", raising=False)

    mod = importlib.import_module("Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator")
    orchestrator = mod.StrategyOrchestrator(event_manager=_StubEventManager())

    assert "BullCallSpread" not in orchestrator.lean_strategy_allowlist
    assert "BearPutSpread" not in orchestrator.lean_strategy_allowlist

    orchestrator.lean_mode = True
    orchestrator._initialize_strategy_registry()

    assert "BullCallSpread" not in orchestrator.available_strategies
    assert "BearPutSpread" not in orchestrator.available_strategies


def test_d31_evolved_credit_spread_adapter_maps_native_signal_to_base_signal():
    orchestrator = _make_orchestrator()
    cls = orchestrator.available_strategies["EvolvedCreditSpread"]

    adapter = cls(
        name="EvolvedCreditSpread",
        event_manager=_StubEventManager(),
        risk_profile=SimpleNamespace(account_size=100000),
        config={},
    )

    native_signal = SimpleNamespace(
        signal_id="ENTRY_TEST_1",
        action="ENTER_CREDIT_SPREAD",
        timestamp=datetime.now(timezone.utc),
        ai_confidence=0.82,
        signal_strength=0.74,
        position_details={"estimated_credit": 1.25, "max_loss": 3.75, "contracts": 2},
    )

    adapter._core = SimpleNamespace(
        analyze_market=lambda _market: SimpleNamespace(),
        generate_signals=lambda _analysis: [native_signal],
    )

    signals = adapter.generate_signals(
        pd.DataFrame({"SPY": [502.0, 503.5], "volume": [1000, 1200], "VIX": [18.0, 17.8]})
    )

    assert len(signals) == 1
    mapped = signals[0]
    assert mapped.signal_id == "ENTRY_TEST_1"
    assert mapped.signal_type.value == "sell"
    assert mapped.metadata["strategy_type"] == "evolved_credit_spread"
    assert mapped.metadata["action"] == "sell_to_open"
    assert mapped.position_size == 2
    assert adapter.validate_signal(mapped)


def test_d31_vix_hedging_adapter_maps_recommendation_to_base_signal():
    orchestrator = _make_orchestrator()
    cls = orchestrator.available_strategies["VIXHedging"]

    adapter = cls(
        name="VIXHedging",
        event_manager=_StubEventManager(),
        risk_profile=SimpleNamespace(account_size=100000),
        config={"risk_tolerance": "moderate", "current_hedge_ratio": 0.01},
    )

    recommendation = SimpleNamespace(
        action=SimpleNamespace(value="add_hedge"),
        hedge_type=SimpleNamespace(value="vix_call"),
        urgency="immediate",
        portfolio_hedge_ratio=0.06,
        notional_value=12000.0,
        rationale="Add hedge for rising turbulence",
        expected_cost=240.0,
        expected_protection=85.0,
    )

    adapter._core = SimpleNamespace(
        get_hedge_recommendation=lambda **_kwargs: recommendation,
    )

    signals = adapter.generate_signals(
        pd.DataFrame({"SPY": [500.0, 501.0], "VIX": [17.0, 18.2]})
    )

    assert len(signals) == 1
    mapped = signals[0]
    assert mapped.signal_type.value == "buy"
    assert mapped.symbol == "VIX"
    assert mapped.metadata["strategy_type"] == "vix_hedging"
    assert mapped.metadata["action"] == "buy_to_open"
    assert mapped.position_size >= 1
    assert adapter.validate_signal(mapped)
