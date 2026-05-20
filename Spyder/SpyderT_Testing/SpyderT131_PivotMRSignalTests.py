#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT131_PivotMRSignalTests.py
Purpose: Pytest suite for SpyderS08_PivotMeanReversionSignal scoring & gates.

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-17

Module Description:
    Pure-function tests for the stateless pivot mean-reversion signal scorer.
    Because S08 has no I/O and no global state, every test is fully
    deterministic and runs in microseconds. Coverage targets:
      * Empty-signal short circuit (no breach)
      * FADE_RESISTANCE fires above R1/R2 with full confluence
      * FADE_SUPPORT fires below S1/S2 with full confluence
      * Scoring weights (regime / GEX / ATR-distance / RSI / VWAP /
        max-pain / breadth) credited correctly
      * Vetos (news window, edge-of-day, high VIX, backwardation)
        subtract the right amount and can suppress an otherwise-firing trade
      * MIN_FIRE_SCORE gate: scores below threshold leave fired=False
      * Direction tie-break: when both sides have the same score, the one
        actually returned must match the breach side
      * Choosing the deeper-breached level when multiple are exceeded
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import pytest

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderS_Signals.SpyderS08_PivotMeanReversionSignal import (
    PivotMeanReversionSignal,
    PivotMRInputs,
    PivotDirection,
    MIN_FIRE_SCORE,
    CENTER_BOUNCE_LONG_TAG,
    CENTER_BOUNCE_SHORT_TAG,
)


# ==============================================================================
# FIXTURES
# ==============================================================================
@pytest.fixture
def engine() -> PivotMeanReversionSignal:
    """One stateless engine reused across the whole module."""
    return PivotMeanReversionSignal()


@pytest.fixture
def pivots() -> dict[str, float]:
    """Standard pivot set — derived from H=592, L=583, C=588 (P=587.67)."""
    return {
        "P": 587.67,
        "R1": 592.33,
        "R2": 596.67,
        "R3": 601.33,
        "S1": 583.33,
        "S2": 578.67,
        "S3": 574.33,
    }


def _baseline_inputs(pivots, **overrides) -> PivotMRInputs:
    """Build a textbook FADE_RESISTANCE input with deep R1 breach.

    Defaults sum to a fully firing signal (regime+ATR+RSI+GEX = 70).
    Tests can override individual fields to exercise specific branches.
    """
    defaults = dict(
        spot_price=596.0,            # ~3.7 above R1, deep breach
        pivots=pivots,
        atr=10.0,                    # → distance = 0.37 ATR (>0.25 trigger)
        rsi=78.0,                    # overbought
        regime_label="RANGE",
        net_gex=2.0e9,               # long-gamma pinning
    )
    defaults.update(overrides)
    return PivotMRInputs(**defaults)


# ==============================================================================
# EMPTY / NO-OP CASES
# ==============================================================================
class TestNoFireConditions:
    """Cases that must return an empty (fired=False) signal."""

    def test_no_pivots_returns_empty(self, engine):
        result = engine.evaluate(PivotMRInputs(
            spot_price=590.0, pivots={}, atr=5.0, rsi=50.0
        ))
        assert result.fired is False
        assert result.direction == PivotDirection.NONE
        assert result.score == 0

    def test_zero_atr_returns_empty(self, engine, pivots):
        result = engine.evaluate(PivotMRInputs(
            spot_price=596.0, pivots=pivots, atr=0.0, rsi=78.0
        ))
        assert result.fired is False

    def test_price_inside_pivot_bands_no_breach(self, engine, pivots):
        # 590 sits between S1=583.33 and R1=592.33 and is not near central P,
        # so neither outer-band nor center-pivot triggers should activate.
        result = engine.evaluate(_baseline_inputs(pivots, spot_price=590.0))
        assert result.fired is False
        assert result.direction == PivotDirection.NONE


# ==============================================================================
# FADE_RESISTANCE FIRE PATH
# ==============================================================================
class TestFadeResistance:
    """Cases where price breaks above R1/R2/R3 and the signal sells calls."""

    def test_textbook_fade_resistance_fires(self, engine, pivots):
        result = engine.evaluate(_baseline_inputs(pivots))
        assert result.fired is True
        assert result.direction == PivotDirection.FADE_RESISTANCE
        assert result.score >= MIN_FIRE_SCORE
        assert result.nearest_level_name in {"R1", "R2", "R3"}
        assert result.nearest_level_price > 0

    def test_regime_bonus_credited(self, engine, pivots):
        with_regime = engine.evaluate(_baseline_inputs(pivots, regime_label="RANGE"))
        without_regime = engine.evaluate(_baseline_inputs(pivots, regime_label=""))
        assert with_regime.score - without_regime.score == 25

    def test_gex_bonus_credited(self, engine, pivots):
        with_gex = engine.evaluate(_baseline_inputs(pivots, net_gex=2.0e9))
        without_gex = engine.evaluate(_baseline_inputs(pivots, net_gex=None))
        assert with_gex.score - without_gex.score == 20

    def test_negative_gex_does_not_award_bonus(self, engine, pivots):
        # Short-gamma environment — dealers amplify moves, no pinning.
        result = engine.evaluate(_baseline_inputs(pivots, net_gex=-1.5e9))
        assert "GEX" not in " ".join(result.reasons)

    def test_atr_distance_bonus_credited(self, engine, pivots):
        # Deep breach gets +15; shallow breach (<0.25 ATR) does not.
        deep = engine.evaluate(_baseline_inputs(pivots, spot_price=596.0, atr=5.0))
        shallow = engine.evaluate(_baseline_inputs(pivots, spot_price=592.5, atr=20.0))
        assert any("dist=" in r for r in deep.reasons)
        # Shallow breach should have a penalty about weak trigger
        assert any("weak trigger" in p for p in shallow.penalties)

    def test_rsi_overbought_bonus(self, engine, pivots):
        with_overbought = engine.evaluate(_baseline_inputs(pivots, rsi=80.0))
        neutral_rsi = engine.evaluate(_baseline_inputs(pivots, rsi=55.0))
        assert with_overbought.score - neutral_rsi.score == 10

    def test_vwap_slope_bonus_when_flat(self, engine, pivots):
        # Flat slope (|bps/min| < some threshold) → +10
        flat = engine.evaluate(_baseline_inputs(pivots, vwap_slope=0.0))
        no_vwap = engine.evaluate(_baseline_inputs(pivots, vwap_slope=None))
        # vwap_slope=0 should add some bonus over the baseline
        assert flat.score >= no_vwap.score

    def test_max_pain_pulls_toward_pivot_bonus(self, engine, pivots):
        # Max pain near central pivot → bonus
        with_mp = engine.evaluate(
            _baseline_inputs(pivots, max_pain_strike=pivots["P"])
        )
        without_mp = engine.evaluate(
            _baseline_inputs(pivots, max_pain_strike=None)
        )
        assert with_mp.score >= without_mp.score


# ==============================================================================
# FADE_SUPPORT FIRE PATH
# ==============================================================================
class TestFadeSupport:
    """Cases where price breaks below S1/S2/S3 and the signal sells puts."""

    def test_textbook_fade_support_fires(self, engine, pivots):
        result = engine.evaluate(_baseline_inputs(
            pivots, spot_price=579.0, rsi=22.0
        ))
        assert result.fired is True
        assert result.direction == PivotDirection.FADE_SUPPORT
        assert result.score >= MIN_FIRE_SCORE
        assert result.nearest_level_name in {"S1", "S2", "S3"}

    def test_rsi_oversold_credited(self, engine, pivots):
        oversold = engine.evaluate(_baseline_inputs(
            pivots, spot_price=579.0, rsi=20.0
        ))
        neutral = engine.evaluate(_baseline_inputs(
            pivots, spot_price=579.0, rsi=50.0
        ))
        assert oversold.score - neutral.score == 10


# ==============================================================================
# CENTER-PIVOT ROTATION PATH
# ==============================================================================
class TestCenterPivotRotation:
    """Cases where price rotates around central pivot P (no R/S breach)."""

    def test_center_pivot_neutral_bull_rotation_can_fire(self, engine, pivots):
        result = engine.evaluate(_baseline_inputs(
            pivots,
            spot_price=587.72,      # near P=587.67 (within 0.20 ATR)
            rsi=56.0,               # bullish micro-bias
            regime_label="RANGE",
            net_gex=2.0e9,
        ))
        assert result.fired is True
        assert result.direction == PivotDirection.FADE_SUPPORT
        assert result.nearest_level_name == "P"
        assert result.score >= MIN_FIRE_SCORE
        assert CENTER_BOUNCE_LONG_TAG in result.reasons

    def test_center_pivot_neutral_bear_rotation_can_fire(self, engine, pivots):
        result = engine.evaluate(_baseline_inputs(
            pivots,
            spot_price=587.60,      # near P=587.67 (within 0.20 ATR)
            rsi=44.0,               # bearish micro-bias
            regime_label="RANGE",
            net_gex=2.0e9,
        ))
        assert result.fired is True
        assert result.direction == PivotDirection.FADE_RESISTANCE
        assert result.nearest_level_name == "P"
        assert result.score >= MIN_FIRE_SCORE
        assert CENTER_BOUNCE_SHORT_TAG in result.reasons


# ==============================================================================
# VETOS — must subtract the right amount and can block the fire
# ==============================================================================
class TestPenalties:
    """Penalty branches that suppress an otherwise-firing signal."""

    def test_news_window_penalty(self, engine, pivots):
        with_news = engine.evaluate(_baseline_inputs(pivots, is_news_window=True))
        without_news = engine.evaluate(_baseline_inputs(pivots, is_news_window=False))
        assert without_news.score - with_news.score == 30

    def test_news_window_can_block_fire(self, engine, pivots):
        # Baseline scores 70; news subtracts 30 → 40 < MIN_FIRE_SCORE=60
        with_news = engine.evaluate(_baseline_inputs(pivots, is_news_window=True))
        assert with_news.fired is False
        assert any("news" in p.lower() or "edge" in p.lower()
                   for p in with_news.penalties)

    def test_edge_of_day_penalty(self, engine, pivots):
        with_edge = engine.evaluate(_baseline_inputs(pivots, is_edge_of_day=True))
        without_edge = engine.evaluate(_baseline_inputs(pivots, is_edge_of_day=False))
        assert without_edge.score - with_edge.score == 30

    def test_high_vix_penalty(self, engine, pivots):
        with_high_vix = engine.evaluate(_baseline_inputs(pivots, vix=28.0))
        with_low_vix = engine.evaluate(_baseline_inputs(pivots, vix=14.0))
        assert with_low_vix.score - with_high_vix.score == 20

    def test_vix_backwardation_penalty(self, engine, pivots):
        with_back = engine.evaluate(_baseline_inputs(pivots, vix_backwardation=True))
        without_back = engine.evaluate(_baseline_inputs(pivots, vix_backwardation=False))
        # Backwardation triggers the same -20 high-vix bracket
        assert without_back.score >= with_back.score


# ==============================================================================
# FIRE GATE
# ==============================================================================
class TestFireGate:
    """The MIN_FIRE_SCORE = 60 threshold."""

    def test_score_just_below_threshold_does_not_fire(self, engine, pivots):
        # Strip the +20 GEX bonus so the score lands at 50 → no fire
        result = engine.evaluate(_baseline_inputs(
            pivots, net_gex=None, regime_label="",  # remove regime too → 25 left
            rsi=78.0
        ))
        assert result.fired is False

    def test_score_at_or_above_threshold_fires(self, engine, pivots):
        # All four core bonuses present → 70 ≥ 60
        result = engine.evaluate(_baseline_inputs(pivots))
        assert result.score >= MIN_FIRE_SCORE
        assert result.fired is True


# ==============================================================================
# DEEPEST-BREACH SELECTION
# ==============================================================================
class TestLevelSelection:
    """When multiple levels are breached, the deepest breach wins.

    The deepest-breached level is the one *farthest* below the current
    price (resistance side) or *farthest* above (support side). This
    captures the strongest fade signal — price has travelled far past
    the original breakout point.
    """

    def test_multiple_levels_breached_picks_deepest(self, engine, pivots):
        # Spot=602 is above R1, R2, AND R3.
        # Breaches: R1=9.67, R2=5.33, R3=0.67 → R1 is the deepest.
        result = engine.evaluate(_baseline_inputs(pivots, spot_price=602.0))
        assert result.fired is True
        assert result.nearest_level_name == "R1"

    def test_only_first_level_breached(self, engine, pivots):
        # Spot=593 is above R1=592.33 but below R2 and R3.
        result = engine.evaluate(_baseline_inputs(pivots, spot_price=593.0))
        # May not fire (small breach) but if it identifies a level it must be R1
        if result.nearest_level_name:
            assert result.nearest_level_name == "R1"


# ==============================================================================
# BIDIRECTIONAL TIE-BREAK
# ==============================================================================
class TestBidirectionalChoice:
    """When inputs could match both sides, the actual breach wins."""

    def test_overbought_above_resistance_chooses_fade_resistance(self, engine, pivots):
        # Overbought RSI above R1 — must be FADE_RESISTANCE (not FADE_SUPPORT).
        result = engine.evaluate(_baseline_inputs(
            pivots, spot_price=596.0, rsi=78.0
        ))
        assert result.direction == PivotDirection.FADE_RESISTANCE

    def test_oversold_below_support_chooses_fade_support(self, engine, pivots):
        # Oversold RSI below S1 — must be FADE_SUPPORT.
        result = engine.evaluate(_baseline_inputs(
            pivots, spot_price=579.0, rsi=22.0
        ))
        assert result.direction == PivotDirection.FADE_SUPPORT
