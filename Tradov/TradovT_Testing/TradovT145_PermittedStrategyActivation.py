#!/usr/bin/env python3
"""Phase-1 tests for the operator-curated permitted-strategy loader (D31).

Validates ``activate_permitted_strategies`` hosts the permitted stat-arb
strategies via ``add_strategy`` (the live signal-producer path) without reviving
the retired regime-weight registry.
"""

from __future__ import annotations

import importlib


class _StubEventManager:
    def __init__(self):
        self.handlers = {}

    def subscribe(self, event_type, handler):
        self.handlers.setdefault(event_type, []).append(handler)

    def emit(self, *args, **kwargs):
        return None


def _orchestrator():
    mod = importlib.import_module(
        "Tradov.TradovD_Strategies.TradovD31_StrategyOrchestrator"
    )
    return mod, mod.StrategyOrchestrator(event_manager=_StubEventManager())


def test_permitted_map_matches_gui_candidates():
    """The D31 loader map keys must mirror the GUI permitted-strategy list."""
    mod, _ = _orchestrator()
    assert set(mod._D31_PERMITTED_STRATEGY_CLASSES) == {
        "PairTrading",
        "DistanceApproach",
        "PCAStatArb",
    }


def test_activate_single_permitted_strategy_hosts_it():
    mod, orch = _orchestrator()
    activated = orch.activate_permitted_strategies(["PCAStatArb"])
    assert activated == ["PCAStatArbStrategy"]
    # Hosted in active_strategies and admitted under the lean-mode gate.
    hosted = {type(s).__name__ for s in orch.active_strategies.values()}
    assert "PCAStatArbStrategy" in hosted
    assert "PCAStatArbStrategy" in orch.lean_strategy_allowlist


def test_unknown_token_is_ignored():
    _mod, orch = _orchestrator()
    assert orch.activate_permitted_strategies(["NotAStrategy"]) == []
    assert orch.active_strategies == {}


def test_activation_is_idempotent_per_strategy():
    _mod, orch = _orchestrator()
    first = orch.activate_permitted_strategies(["DistanceApproach"])
    assert first == ["DistanceTradingStrategy"]
    # Re-activating the same token does not double-host it.
    second = orch.activate_permitted_strategies(["DistanceApproach"])
    assert second == []
    hosted = [
        type(s).__name__ for s in orch.active_strategies.values()
        if type(s).__name__ == "DistanceTradingStrategy"
    ]
    assert len(hosted) == 1


def test_all_three_stat_arb_strategies_run_concurrently():
    """All three stat-arb strategies share the exempt 'stat_arb' bucket and
    co-exist up to the concurrency cap."""
    _mod, orch = _orchestrator()
    activated = orch.activate_permitted_strategies(
        ["PairTrading", "DistanceApproach", "PCAStatArb"]
    )
    assert set(activated) == {
        "PairTradingStrategy",
        "DistanceTradingStrategy",
        "PCAStatArbStrategy",
    }
    assert len(orch.active_strategies) == 3
    assert len(orch.active_strategies) <= orch.max_concurrent_strategies


def test_stat_arb_strategies_get_equal_capital_slice():
    """Each hosted strategy is sized to an equal slot share of base capital."""
    _mod, orch = _orchestrator()
    orch.activate_permitted_strategies(["PCAStatArb"])
    strat = next(iter(orch.active_strategies.values()))
    expected = orch.base_capital / orch.max_concurrent_strategies
    assert abs(strat.risk_profile.account_size - expected) < 1e-6
