#!/usr/bin/env python3
"""Focused tests for D31 strategy admission guardrails."""

import importlib
import logging
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


class BrokenWingButterflyStrategy(_BaseMockStrategy):
    pass


class MockCalendarSpreadStrategy(_BaseMockStrategy):
    pass


class PivotMeanReversionStrategy(_BaseMockStrategy):
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


def test_d31_defaults_bwb_to_ultra_short_bucket():
    orchestrator = _make_orchestrator()
    orchestrator.max_concurrent_strategies = 4
    orchestrator.max_active_horizon_buckets = 3

    strategy_id = orchestrator.add_strategy(
        BrokenWingButterflyStrategy,
        config={},
        initial_allocation=0.1,
    )

    assert strategy_id in orchestrator.active_strategies
    assert orchestrator.strategy_allocations[strategy_id].horizon_bucket == "ultra_short"

    with pytest.raises(ValueError, match="Horizon-bucket already occupied"):
        orchestrator.add_strategy(MockZeroDTEStrategy, config={}, initial_allocation=0.1)


def test_d31_respects_explicit_longer_dte_override_for_bwb():
    orchestrator = _make_orchestrator()

    strategy_id = orchestrator.add_strategy(
        BrokenWingButterflyStrategy,
        config={"target_dte": 5},
        initial_allocation=0.1,
    )

    assert strategy_id in orchestrator.active_strategies
    assert orchestrator.strategy_allocations[strategy_id].horizon_bucket == "short"


def test_d31_warns_when_unimplemented_overlay_flag_is_requested(monkeypatch):
    monkeypatch.setenv("SPYDER_ENABLE_ODTE_PIVOT_OVERLAY_SLOT", "true")
    mod = importlib.import_module("Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator")
    mocked_logger = MagicMock()
    monkeypatch.setattr(
        mod,
        "SpyderLogger",
        SimpleNamespace(get_logger=lambda *_args, **_kwargs: mocked_logger),
    )

    orchestrator = _make_orchestrator()

    assert orchestrator.max_concurrent_strategies == 3
    assert orchestrator.max_active_horizon_buckets == 2
    mocked_logger.warning.assert_called_once()
    warning_text = mocked_logger.warning.call_args.args[0]
    assert "SPYDER_ENABLE_ODTE_PIVOT_OVERLAY_SLOT is experimental" in warning_text
    assert "third ultra_short PivotMeanReversion slot" in warning_text


def test_d31_allows_overlay_registration_only_for_third_pmr_slot(monkeypatch):
    monkeypatch.setenv("SPYDER_ENABLE_ODTE_PIVOT_OVERLAY_SLOT", "true")
    orchestrator = _make_orchestrator()

    first_strategy_id = orchestrator.add_strategy(
        MockZeroDTEStrategy,
        config={},
        initial_allocation=0.1,
    )
    second_strategy_id = orchestrator.add_strategy(
        MockCalendarSpreadStrategy,
        config={},
        initial_allocation=0.1,
    )

    overlay_strategy_id = orchestrator.add_strategy(
        PivotMeanReversionStrategy,
        config={},
        initial_allocation=0.1,
    )

    assert first_strategy_id in orchestrator.active_strategies
    assert second_strategy_id in orchestrator.active_strategies
    assert overlay_strategy_id in orchestrator.active_strategies
    assert len(orchestrator.active_strategies) == 3
    assert orchestrator.strategy_allocations[overlay_strategy_id].horizon_bucket == "ultra_short"


def test_d31_rejects_second_overlay_registration_when_one_is_active(monkeypatch):
    monkeypatch.setenv("SPYDER_ENABLE_ODTE_PIVOT_OVERLAY_SLOT", "true")
    orchestrator = _make_orchestrator()

    orchestrator.add_strategy(MockZeroDTEStrategy, config={}, initial_allocation=0.1)
    orchestrator.add_strategy(MockCalendarSpreadStrategy, config={}, initial_allocation=0.1)
    orchestrator.add_strategy(
        PivotMeanReversionStrategy,
        config={},
        initial_allocation=0.1,
    )

    with pytest.raises(ValueError, match="Concurrent strategy limit reached"):
        orchestrator.add_strategy(
            PivotMeanReversionStrategy,
            config={},
            initial_allocation=0.1,
        )


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
    orchestrator._record_signal_dispatch_outcome.assert_called_once()
    call_args, call_kwargs = orchestrator._record_signal_dispatch_outcome.call_args
    assert call_args[0] == "dispatch_submitted"
    if "signal" in call_kwargs:
        assert call_kwargs["signal"] == signal
    orchestrator._record_signal_drop.assert_not_called()


def test_d31_paused_strategy_does_not_block_same_bucket_add():
    """Regression: a paused strategy must not block a new strategy in the same horizon bucket.

    During a regime transition, _adaptive_strategy_management pauses the outgoing
    strategy before adding the incoming one.  The bucket should be claimable
    immediately after the pause so the add_strategy call succeeds.
    """
    orchestrator = _make_orchestrator()
    orchestrator.max_concurrent_strategies = 4
    orchestrator.max_active_horizon_buckets = 3

    # Register and pause an initial short-horizon strategy.
    strategy_id = orchestrator.add_strategy(MockShortStrategy, config={}, initial_allocation=0.1)
    assert strategy_id in orchestrator.active_strategies

    # Simulate the pause that _adaptive_strategy_management performs.
    orchestrator.active_strategies[strategy_id].pause = MagicMock()
    orchestrator.active_strategies[strategy_id].pause()
    orchestrator.paused_strategies.add(strategy_id)

    # Adding a second strategy of the same horizon bucket must now succeed.
    new_id = orchestrator.add_strategy(MockShortStrategy, config={}, initial_allocation=0.1)
    assert new_id in orchestrator.active_strategies
