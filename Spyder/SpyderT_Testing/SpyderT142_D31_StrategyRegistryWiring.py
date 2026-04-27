#!/usr/bin/env python3
"""Focused tests for D31 strategy registry and auto-selection wiring."""

from unittest.mock import MagicMock
from types import SimpleNamespace

from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy
from Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator import StrategyOrchestrator


class _StubEventManager:
    def __init__(self):
        self.handlers = {}

    def subscribe(self, event_type, handler):
        self.handlers.setdefault(event_type, []).append(handler)

    def emit(self, *args, **kwargs):
        return None


def test_d31_registry_includes_first_wave_base_strategies():
    orchestrator = StrategyOrchestrator(event_manager=_StubEventManager())

    expected = {
        "RSIMeanReversion",
        "MACrossover",
        "RenaissanceMeanReversion",
        "PivotMeanReversion",
    }

    missing = expected - set(orchestrator.available_strategies)
    assert not missing, f"Missing strategy registrations: {sorted(missing)}"

    for name in expected:
        assert issubclass(orchestrator.available_strategies[name], BaseStrategy)


def test_d31_configure_regime_selects_newly_wired_strategies():
    orchestrator = StrategyOrchestrator(event_manager=_StubEventManager())

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
    orchestrator = StrategyOrchestrator(event_manager=_StubEventManager())
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
