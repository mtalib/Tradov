#!/usr/bin/env python3
"""Focused tests for D31 strategy admission guardrails."""

import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest


def _get_base_strategy_class():
    """Lazily import BaseStrategy to avoid package-path drift at analysis time."""
    mod = importlib.import_module("Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy")
    return mod.BaseStrategy


def _get_strategy_orchestrator_class():
    """Lazily import D31 to avoid heavy import side-effects at collection time."""
    mod = importlib.import_module("Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator")
    return mod.StrategyOrchestrator


class _StubEventManager:
    def __init__(self):
        self.handlers = {}

    def subscribe(self, event_type, handler):
        self.handlers.setdefault(event_type, []).append(handler)

    def emit(self, *_args, **_kwargs):
        return None


class _BaseMockStrategy(_get_base_strategy_class()):
    """Lightweight concrete strategy for orchestrator admission tests."""

    def __init__(self, name=None, event_manager=None, risk_profile=None, config=None):
        self.name = name or self.__class__.__name__
        self.event_manager = event_manager
        self.risk_profile = risk_profile
        self.config = config or {}
        self.total_pnl = 0.0

    def generate_signal(self):
        return None

    def generate_signals(self, _market_data: pd.DataFrame):
        return []

    def validate_signal(self, _signal):
        return True

    def calculate_position_size(self, _signal):
        return 1

    def should_exit_position(self, _position, _market_data: pd.DataFrame):
        return False, ""


class MockShortStrategy(_BaseMockStrategy):
    pass


class MockZeroDTEStrategy(_BaseMockStrategy):
    pass


class MockCalendarSpreadStrategy(_BaseMockStrategy):
    pass


def _make_orchestrator():
    orchestrator_cls = _get_strategy_orchestrator_class()
    orchestrator = orchestrator_cls(event_manager=_StubEventManager())
    orchestrator.error_handler = SimpleNamespace(handle_error=lambda *a, **k: None)
    orchestrator.lean_mode = False
    return orchestrator


def test_d31_rejects_add_strategy_when_concurrent_cap_reached():
    orchestrator = _make_orchestrator()
    orchestrator.max_concurrent_strategies = 1
    orchestrator.max_active_horizon_buckets = 3

    strategy_id = orchestrator.add_strategy(MockShortStrategy, config={}, initial_allocation=0.1)
    assert strategy_id in orchestrator.active_strategies

    with pytest.raises(ValueError, match="Concurrent strategy limit reached"):
        orchestrator.add_strategy(MockShortStrategy, config={}, initial_allocation=0.1)


def test_d31_rejects_add_strategy_when_horizon_bucket_cap_reached():
    orchestrator = _make_orchestrator()
    orchestrator.max_concurrent_strategies = 8
    orchestrator.max_active_horizon_buckets = 1

    # First strategy consumes the ultra_short horizon bucket.
    strategy_id = orchestrator.add_strategy(MockZeroDTEStrategy, config={}, initial_allocation=0.1)
    assert strategy_id in orchestrator.active_strategies

    # Adding a swing bucket strategy should fail when only one bucket is allowed.
    with pytest.raises(ValueError, match="Horizon-bucket limit reached"):
        orchestrator.add_strategy(MockCalendarSpreadStrategy, config={}, initial_allocation=0.1)


def test_d31_dispatch_midwalk_handles_result_without_message_attribute():
    """Regression: mid-walk result objects may not include a .message field."""
    orchestrator = _make_orchestrator()

    # Force path-1 dispatch via order manager using bid/ask quotes.
    orchestrator._order_manager = SimpleNamespace(
        submit_limit_with_walk=MagicMock(
            return_value=SimpleNamespace(success=True, error_code=None)
        )
    )
    orchestrator._record_signal_dispatch_outcome = MagicMock()
    orchestrator._record_signal_drop = MagicMock()

    signal = {
        "symbol": "SPY",
        "quantity": 1,
        "action": "buy",
        "strategy_id": "TestStrategy",
        "bid": 1.0,
        "ask": 1.2,
    }

    orchestrator._dispatch_approved_signal(signal)

    orchestrator._order_manager.submit_limit_with_walk.assert_called_once()
    orchestrator._record_signal_dispatch_outcome.assert_called_once_with("dispatch_submitted")
    orchestrator._record_signal_drop.assert_not_called()
