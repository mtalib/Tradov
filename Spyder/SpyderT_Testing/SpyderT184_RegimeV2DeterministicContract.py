#!/usr/bin/env python3
"""Deterministic v2 regime and strategy-gating contract tests."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from datetime import datetime, timezone, UTC
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
        timestamp=datetime.now(UTC),
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


def _clear_selector_feature_flags(monkeypatch) -> None:
    for name in (
        "SPYDER_ENABLE_BULL_CALL_SPREAD",
        "SPYDER_ENABLE_BEAR_PUT_SPREAD",
        "SPYDER_ENABLE_BUTTERFLY",
        "SPYDER_ENABLE_PIVOT_MEAN_REVERSION",
        "SPYDER_ENABLE_BULLISH_STRANGLE",
        "SPYDER_ENABLE_PUT_CREDIT_SPREAD_7",
    ):
        monkeypatch.delenv(name, raising=False)


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


def test_d30_consensus_mapping_is_restricted_to_four_strategies_and_halts(monkeypatch) -> None:
    _clear_selector_feature_flags(monkeypatch)
    _, d30 = _refresh_runtime_modules()
    selector = d30.RegimeGatedSelector()

    def _consensus_for(regime):
        return SimpleNamespace(
            regime=regime,
            confidence=0.90,
            timestamp=datetime.now(UTC),
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
            timestamp=datetime.now(UTC),
        )
    )

    assert selection.selected_strategy.value == "bull_call_spread"
    assert selection.selector_feature_flag == "SPYDER_ENABLE_BULL_CALL_SPREAD"


def test_d30_consensus_mapping_enables_put_credit_spread_7_via_flag_on_friday(monkeypatch) -> None:
    monkeypatch.setenv("SPYDER_ENABLE_PUT_CREDIT_SPREAD_7", "true")
    _, d30 = _refresh_runtime_modules()
    selector = d30.RegimeGatedSelector(clock=lambda: datetime(2026, 6, 5, 19, 45, tzinfo=UTC))

    bull_regime = _regime_member(d30.L09MarketRegime, "BULL_TRENDING", "BULL")
    selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=bull_regime,
            confidence=0.90,
            timestamp=datetime.now(UTC),
        )
    )

    assert selection.selected_strategy.value == "put_credit_spread_7"
    assert selection.selector_feature_flag == "SPYDER_ENABLE_PUT_CREDIT_SPREAD_7"
    assert selection.reason == "Bull trend — Put Credit Spread 7 (scheduled weekly entry, feature-flag enabled)"


def test_d30_consensus_mapping_keeps_put_credit_spread_7_before_entry_time(monkeypatch) -> None:
    monkeypatch.setenv("SPYDER_ENABLE_PUT_CREDIT_SPREAD_7", "true")
    _, d30 = _refresh_runtime_modules()
    selector = d30.RegimeGatedSelector(clock=lambda: datetime(2026, 6, 5, 14, 30, tzinfo=UTC))

    bull_regime = _regime_member(d30.L09MarketRegime, "BULL_TRENDING", "BULL")
    selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=bull_regime,
            confidence=0.90,
            timestamp=datetime.now(UTC),
        )
    )

    assert selection.selected_strategy.value == "bull_put_spread"


def test_d30_consensus_mapping_keeps_put_credit_spread_7_off_schedule(monkeypatch) -> None:
    monkeypatch.setenv("SPYDER_ENABLE_PUT_CREDIT_SPREAD_7", "true")
    _, d30 = _refresh_runtime_modules()
    selector = d30.RegimeGatedSelector(clock=lambda: datetime(2026, 6, 3, 14, 30, tzinfo=UTC))

    bull_regime = _regime_member(d30.L09MarketRegime, "BULL_TRENDING", "BULL")
    selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=bull_regime,
            confidence=0.90,
            timestamp=datetime.now(UTC),
        )
    )

    assert selection.selected_strategy.value == "bull_put_spread"


def test_d30_consensus_mapping_enables_bear_put_spread_via_flag(monkeypatch) -> None:
    monkeypatch.setenv("SPYDER_ENABLE_BEAR_PUT_SPREAD", "true")
    _, d30 = _refresh_runtime_modules()
    selector = d30.RegimeGatedSelector()

    bear_regime = _regime_member(d30.L09MarketRegime, "BEAR_TRENDING", "BEAR")
    selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=bear_regime,
            confidence=0.90,
            timestamp=datetime.now(UTC),
        )
    )

    assert selection.selected_strategy.value == "bear_put_spread"
    assert selection.selector_feature_flag == "SPYDER_ENABLE_BEAR_PUT_SPREAD"


def test_d30_consensus_mapping_enables_butterfly_via_flag(monkeypatch) -> None:
    monkeypatch.setenv("SPYDER_ENABLE_BUTTERFLY", "true")
    _, d30 = _refresh_runtime_modules()
    selector = d30.RegimeGatedSelector()

    neutral_regime = _regime_member(d30.L09MarketRegime, "SIDEWAYS_RANGE", "SIDEWAYS")
    selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=neutral_regime,
            confidence=0.90,
            timestamp=datetime.now(UTC),
        )
    )

    assert selection.selected_strategy.value == "butterfly"
    assert selection.selector_feature_flag == "SPYDER_ENABLE_BUTTERFLY"
    assert selection.reason == "Range/calm — Butterfly (feature-flag enabled)"


def test_d30_recovery_mode_maps_to_broken_wing_butterfly(monkeypatch) -> None:
    monkeypatch.delenv("SPYDER_ENABLE_BULLISH_STRANGLE", raising=False)
    _, d30 = _refresh_runtime_modules()
    selector = d30.RegimeGatedSelector()

    recovery_regime = _regime_member(d30.L09MarketRegime, "RECOVERY_MODE", "RECOVERY")
    selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=recovery_regime,
            confidence=0.90,
            timestamp=datetime.now(UTC),
        )
    )

    assert selection.selected_strategy.value == "broken_wing_butterfly"
    assert selection.reason == "Recovery regime — Broken Wing Butterfly"


def test_d30_recovery_mode_enables_bullish_strangle_via_flag(monkeypatch) -> None:
    monkeypatch.setenv("SPYDER_ENABLE_BULLISH_STRANGLE", "true")
    _, d30 = _refresh_runtime_modules()
    selector = d30.RegimeGatedSelector()

    recovery_regime = _regime_member(d30.L09MarketRegime, "RECOVERY_MODE", "RECOVERY")
    selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=recovery_regime,
            confidence=0.90,
            timestamp=datetime.now(UTC),
        )
    )

    assert selection.selected_strategy.value == "bullish_strangle"
    assert selection.selector_feature_flag == "SPYDER_ENABLE_BULLISH_STRANGLE"
    assert selection.reason == "Recovery regime — Bullish Strangle (feature-flag enabled)"


def test_d30_high_vol_bullish_pivot_maps_to_broken_wing_butterfly(monkeypatch) -> None:
    monkeypatch.delenv("SPYDER_ENABLE_BULLISH_STRANGLE", raising=False)
    _, d30 = _refresh_runtime_modules()
    selector = d30.RegimeGatedSelector()

    volatile_regime = _regime_member(d30.L09MarketRegime, "HIGH_VOLATILITY", "VOLATILE")
    selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=volatile_regime,
            confidence=0.90,
            timestamp=datetime.now(UTC),
        ),
        pivot_signal={"fired": True, "direction": "fade_support", "nearest_level_name": "S1"},
    )

    assert selection.selected_strategy.value == "broken_wing_butterfly"
    assert selection.reason.startswith("High-vol bullish pivot — Broken Wing Butterfly")


def test_d30_high_vol_bullish_pivot_enables_bullish_strangle_via_flag(monkeypatch) -> None:
    monkeypatch.setenv("SPYDER_ENABLE_BULLISH_STRANGLE", "true")
    _, d30 = _refresh_runtime_modules()
    selector = d30.RegimeGatedSelector()

    volatile_regime = _regime_member(d30.L09MarketRegime, "HIGH_VOLATILITY", "VOLATILE")
    selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=volatile_regime,
            confidence=0.90,
            timestamp=datetime.now(UTC),
        ),
        pivot_signal={"fired": True, "direction": "fade_support", "nearest_level_name": "S1"},
    )

    assert selection.selected_strategy.value == "bullish_strangle"
    assert selection.selector_feature_flag == "SPYDER_ENABLE_BULLISH_STRANGLE"
    assert selection.reason.startswith(
        "High-vol bullish pivot — Bullish Strangle (feature-flag enabled)"
    )


def test_d30_missing_l09_module_still_honors_consensus_regime(monkeypatch) -> None:
    _clear_selector_feature_flags(monkeypatch)
    _, d30 = _refresh_runtime_modules()
    monkeypatch.setattr(d30, "L09_AVAILABLE", False)
    monkeypatch.setattr(d30, "L09MarketRegime", None)
    selector = d30.RegimeGatedSelector()

    bull_selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=SimpleNamespace(value="bull_trending", name="BULL_TRENDING"),
            confidence=0.90,
            timestamp=datetime.now(UTC),
        )
    )
    volatile_selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=SimpleNamespace(value="high_volatility", name="HIGH_VOLATILITY"),
            confidence=0.90,
            timestamp=datetime.now(UTC),
        )
    )
    recovery_selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=SimpleNamespace(value="recovery_mode", name="RECOVERY_MODE"),
            confidence=0.90,
            timestamp=datetime.now(UTC),
        )
    )
    volatile_bwb_selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=SimpleNamespace(value="high_volatility", name="HIGH_VOLATILITY"),
            confidence=0.90,
            timestamp=datetime.now(UTC),
        ),
        pivot_signal={"fired": True, "direction": "fade_support", "nearest_level_name": "S1"},
    )

    assert bull_selection.selected_strategy.value == "bull_put_spread"
    assert bull_selection.reason.startswith("Bull fallback regime")
    assert volatile_selection.selected_strategy.value == "iron_butterfly"
    assert volatile_selection.reason.startswith("High-vol fallback regime")
    assert recovery_selection.selected_strategy.value == "broken_wing_butterfly"
    assert recovery_selection.reason.startswith("Recovery fallback regime")
    assert volatile_bwb_selection.selected_strategy.value == "broken_wing_butterfly"
    assert volatile_bwb_selection.reason.startswith("High-vol bullish-pivot fallback regime")


def test_d30_missing_l09_module_enables_bullish_strangle_via_flag(monkeypatch) -> None:
    monkeypatch.setenv("SPYDER_ENABLE_BULLISH_STRANGLE", "true")
    _, d30 = _refresh_runtime_modules()
    monkeypatch.setattr(d30, "L09_AVAILABLE", False)
    monkeypatch.setattr(d30, "L09MarketRegime", None)
    selector = d30.RegimeGatedSelector()

    recovery_selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=SimpleNamespace(value="recovery_mode", name="RECOVERY_MODE"),
            confidence=0.90,
            timestamp=datetime.now(UTC),
        )
    )
    volatile_bullish_selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=SimpleNamespace(value="high_volatility", name="HIGH_VOLATILITY"),
            confidence=0.90,
            timestamp=datetime.now(UTC),
        ),
        pivot_signal={"fired": True, "direction": "fade_support", "nearest_level_name": "S1"},
    )

    assert recovery_selection.selected_strategy.value == "bullish_strangle"
    assert recovery_selection.selector_feature_flag == "SPYDER_ENABLE_BULLISH_STRANGLE"
    assert recovery_selection.reason.startswith(
        "Recovery fallback regime — Bullish Strangle (feature-flag enabled)"
    )
    assert volatile_bullish_selection.selected_strategy.value == "bullish_strangle"
    assert volatile_bullish_selection.selector_feature_flag == "SPYDER_ENABLE_BULLISH_STRANGLE"
    assert volatile_bullish_selection.reason.startswith(
        "High-vol bullish-pivot fallback regime — Bullish Strangle (feature-flag enabled)"
    )


def test_d30_missing_l09_module_enables_butterfly_via_flag(monkeypatch) -> None:
    monkeypatch.setenv("SPYDER_ENABLE_BUTTERFLY", "true")
    monkeypatch.delenv("SPYDER_ENABLE_PIVOT_MEAN_REVERSION", raising=False)
    _, d30 = _refresh_runtime_modules()
    monkeypatch.setattr(d30, "L09_AVAILABLE", False)
    monkeypatch.setattr(d30, "L09MarketRegime", None)
    selector = d30.RegimeGatedSelector()

    selection = selector.select_strategy_from_consensus(
        SimpleNamespace(
            regime=SimpleNamespace(value="sideways_range", name="SIDEWAYS_RANGE"),
            confidence=0.90,
            timestamp=datetime.now(UTC),
        )
    )

    assert selection.selected_strategy.value == "butterfly"
    assert selection.reason == "Range/calm fallback regime — Butterfly (feature-flag enabled)"
    assert selection.selector_feature_flag == "SPYDER_ENABLE_BUTTERFLY"
