#!/usr/bin/env python3
"""Focused tests for the retired D31 strategy registry."""

from __future__ import annotations

import importlib


class _StubEventManager:
    def __init__(self):
        self.handlers = {}

    def subscribe(self, event_type, handler):
        self.handlers.setdefault(event_type, []).append(handler)

    def emit(self, *args, **kwargs):
        return None


def _make_orchestrator():
    mod = importlib.import_module("Tradov.TradovD_Strategies.TradovD31_StrategyOrchestrator")
    orchestrator = mod.StrategyOrchestrator(event_manager=_StubEventManager())
    orchestrator.lean_mode = False
    orchestrator._initialize_strategy_registry()
    return orchestrator


def test_d31_registry_is_retired():
    orchestrator = _make_orchestrator()

    assert orchestrator.available_strategies == {}
    assert orchestrator.lean_strategy_allowlist == set()


def test_d31_registry_stays_retired_in_lean_mode():
    mod = importlib.import_module("Tradov.TradovD_Strategies.TradovD31_StrategyOrchestrator")
    orchestrator = mod.StrategyOrchestrator(event_manager=_StubEventManager())
    orchestrator.lean_mode = True
    orchestrator._initialize_strategy_registry()

    assert orchestrator.available_strategies == {}


def test_d31_selector_helpers_are_neutral():
    mod = importlib.import_module("Tradov.TradovD_Strategies.TradovD31_StrategyOrchestrator")

    assert mod.StrategyOrchestrator._map_selector_strategy_to_registry_name("bull_put_spread") is None
    assert mod.StrategyOrchestrator._map_selector_strategy_to_registry_name("opening_range_breakout") is None
    assert mod.StrategyOrchestrator._map_selector_strategy_to_registry_name("pivot_mean_reversion") is None
