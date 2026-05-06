#!/usr/bin/env python3
"""Deterministic v2 regime and strategy-gating contract tests."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


def _load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module spec for {module_name} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ROOT = Path(__file__).resolve().parents[1]


def _refresh_runtime_modules():
    l09 = _load_module(
        "Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine",
        _ROOT / "SpyderL_ML" / "SpyderL09_UnifiedRegimeEngine.py",
    )

    # Ensure all import paths resolve to the same L09 module object.
    sys.modules["Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine"] = l09
    sys.modules["SpyderL_ML.SpyderL09_UnifiedRegimeEngine"] = l09
    sys.modules["SpyderL09_UnifiedRegimeEngine"] = l09

    sys.modules.pop("Spyder.SpyderD_Strategies.SpyderD30_RegimeGatedSelector", None)
    d30 = importlib.import_module("Spyder.SpyderD_Strategies.SpyderD30_RegimeGatedSelector")
    return l09, d30


def _base_conditions(l09):
    return l09.MarketConditions(
        timestamp=datetime.now(timezone.utc),
        spy_price=500.0,
        spy_change_pct=0.0,
        volume_ratio=1.0,
        vix_level=18.0,
        vix9d_level=17.0,
        vxv_level=20.0,
        vix_percentile=50.0,
        spy_ema50=495.0,
        vix_ema50=20.0,
        spy_atr=5.0,
        spy_atr_pct=0.01,
        event_clock_state="clear",
    )


def _regime_member(regime_enum, *names: str):
    for name in names:
        if hasattr(regime_enum, name):
            return getattr(regime_enum, name)
    raise AttributeError(f"No matching regime member found for candidates: {names}")


def test_l09_event_transition_has_top_priority() -> None:
    l09, _ = _refresh_runtime_modules()
    engine = l09.UnifiedRegimeEngine()
    conditions = _base_conditions(l09)
    conditions.event_clock_state = "live"

    result = engine._detect_lean_regime(conditions)

    assert result.regime.value == "event_transition"
    assert result.source.value == "lean_rules"


def test_l09_crisis_uses_vix9d_inversion() -> None:
    l09, _ = _refresh_runtime_modules()
    engine = l09.UnifiedRegimeEngine()
    conditions = _base_conditions(l09)
    conditions.vix9d_level = 25.0
    conditions.vix_level = 20.0

    result = engine._detect_lean_regime(conditions)

    assert result.regime.value == "crisis_mode"


def test_l09_bull_trigger_matches_spec() -> None:
    l09, _ = _refresh_runtime_modules()
    engine = l09.UnifiedRegimeEngine()
    conditions = _base_conditions(l09)
    conditions.spy_price = 505.0
    conditions.spy_ema50 = 500.0
    conditions.vix_level = 17.0
    conditions.vix_ema50 = 20.0
    conditions.vix9d_level = 16.0

    result = engine._detect_lean_regime(conditions)

    assert result.regime.value == "bull_trending"


def test_l09_bear_trigger_matches_spec() -> None:
    l09, _ = _refresh_runtime_modules()
    engine = l09.UnifiedRegimeEngine()
    conditions = _base_conditions(l09)
    conditions.spy_price = 490.0
    conditions.spy_ema50 = 500.0
    conditions.vix_level = 24.0
    conditions.vix_ema50 = 20.0
    conditions.vix9d_level = 22.0

    result = engine._detect_lean_regime(conditions)

    assert result.regime.value == "bear_trending"


def test_l09_neutral_trigger_matches_spec() -> None:
    l09, _ = _refresh_runtime_modules()
    engine = l09.UnifiedRegimeEngine()
    conditions = _base_conditions(l09)
    conditions.spy_price = 500.0
    conditions.spy_ema50 = 500.0
    conditions.spy_atr = 5.0
    conditions.vix_level = 18.0
    conditions.vix9d_level = 17.0
    conditions.vxv_level = 20.0

    result = engine._detect_lean_regime(conditions)

    assert result.regime.value == "sideways_range"


def test_l09_volatile_trigger_matches_spec() -> None:
    l09, _ = _refresh_runtime_modules()
    engine = l09.UnifiedRegimeEngine()
    conditions = _base_conditions(l09)
    # Avoid neutral rule by moving far outside ATR band.
    conditions.spy_price = 520.0
    conditions.spy_ema50 = 500.0
    conditions.spy_atr = 5.0
    conditions.spy_atr_pct = 0.02
    conditions.vix_percentile = 90.0
    conditions.vix_ema50 = 18.0
    conditions.vix9d_level = 18.0
    conditions.vix_level = 19.0

    result = engine._detect_lean_regime(conditions)

    assert result.regime.value == "high_volatility"


def test_l09_get_current_regime_uses_deterministic_source() -> None:
    l09, _ = _refresh_runtime_modules()
    engine = l09.UnifiedRegimeEngine()
    consensus = engine.get_current_regime(_base_conditions(l09))

    assert [source.value for source in consensus.contributing_sources] == ["lean_rules"]


def test_d30_consensus_mapping_is_restricted_to_four_strategies_and_halts() -> None:
    _, d30 = _refresh_runtime_modules()
    selector = d30.RegimeGatedSelector()

    def _consensus_for(regime):
        return SimpleNamespace(
            regime=regime,
            confidence=0.90,
            timestamp=datetime.now(timezone.utc),
        )

    bull_regime = _regime_member(d30.L09MarketRegime, "BULL_TRENDING", "BULL")
    bear_regime = _regime_member(d30.L09MarketRegime, "BEAR_TRENDING", "BEAR")
    neutral_regime = _regime_member(d30.L09MarketRegime, "SIDEWAYS_RANGE", "SIDEWAYS")
    volatile_regime = _regime_member(d30.L09MarketRegime, "HIGH_VOLATILITY", "VOLATILE")
    crisis_regime = _regime_member(d30.L09MarketRegime, "CRISIS_MODE", "CRISIS")
    event_regime = _regime_member(d30.L09MarketRegime, "EVENT_TRANSITION", "EVENT")

    assert selector.select_strategy_from_consensus(_consensus_for(bull_regime)).selected_strategy.value == "bull_put_spread"
    assert selector.select_strategy_from_consensus(_consensus_for(bear_regime)).selected_strategy.value == "bear_call_spread"
    assert selector.select_strategy_from_consensus(_consensus_for(neutral_regime)).selected_strategy.value == "iron_condor"
    assert selector.select_strategy_from_consensus(_consensus_for(volatile_regime)).selected_strategy.value == "iron_butterfly"
    assert selector.select_strategy_from_consensus(_consensus_for(crisis_regime)).selected_strategy.value == "no_trade"
    assert selector.select_strategy_from_consensus(_consensus_for(event_regime)).selected_strategy.value == "no_trade"


def test_d30_consensus_mapping_enables_bull_call_spread_via_flag(monkeypatch) -> None:
    monkeypatch.setenv("SPYDER_ENABLE_BULL_CALL_SPREAD", "true")
    _, d30 = _refresh_runtime_modules()
    selector = d30.RegimeGatedSelector()

    bull_regime = _regime_member(d30.L09MarketRegime, "BULL_TRENDING", "BULL")
    selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=bull_regime,
            confidence=0.90,
            timestamp=datetime.now(timezone.utc),
        )
    )

    assert selection.selected_strategy.value == "bull_call_spread"
    assert selection.selector_feature_flag == "SPYDER_ENABLE_BULL_CALL_SPREAD"


def test_d30_consensus_mapping_enables_bear_put_spread_via_flag(monkeypatch) -> None:
    monkeypatch.setenv("SPYDER_ENABLE_BEAR_PUT_SPREAD", "true")
    _, d30 = _refresh_runtime_modules()
    selector = d30.RegimeGatedSelector()

    bear_regime = _regime_member(d30.L09MarketRegime, "BEAR_TRENDING", "BEAR")
    selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=bear_regime,
            confidence=0.90,
            timestamp=datetime.now(timezone.utc),
        )
    )

    assert selection.selected_strategy.value == "bear_put_spread"
    assert selection.selector_feature_flag == "SPYDER_ENABLE_BEAR_PUT_SPREAD"
