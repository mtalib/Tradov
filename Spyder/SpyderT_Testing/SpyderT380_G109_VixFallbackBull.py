#!/usr/bin/env python3
"""Regression tests for G109 VIX-fallback BULL detection (§10.36 P1 fix).

Verifies that _classify_vix_regime() correctly returns BULL for realistic
bull-market VIX/SPX combinations under the widened thresholds
(spx_change_pct >= 0.3, vix < 24).
"""

from __future__ import annotations

import pytest

from Spyder.SpyderG_GUI.SpyderG109_RegimePillStateHelper import (
    _classify_vix_regime,
    build_regime_pill_state_plan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snap(vix: float, spx_chg: float, vix9d: float = 0.0) -> dict:
    return {
        "VIX": {"last": vix},
        "VIX9D": {"last": vix9d},
        "SPX": {"change_pct": spx_chg},
    }


# ---------------------------------------------------------------------------
# _classify_vix_regime — direct unit tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_classify_vix_regime_bull_moderate_gain_normal_vix() -> None:
    """VIX=18, SPX+0.5%: classic bull-market day → BULL."""
    result = _classify_vix_regime(_snap(18.0, 0.5))
    assert result == "BULL"


@pytest.mark.unit
def test_classify_vix_regime_bull_at_lower_threshold() -> None:
    """SPX+0.3% is exactly the new lower bound → BULL."""
    result = _classify_vix_regime(_snap(18.0, 0.3))
    assert result == "BULL"


@pytest.mark.unit
def test_classify_vix_regime_bull_at_upper_vix_boundary() -> None:
    """VIX=23.9 is just inside the new upper limit (< 24) → BULL."""
    result = _classify_vix_regime(_snap(23.9, 0.4))
    assert result == "BULL"


@pytest.mark.unit
def test_classify_vix_regime_range_when_vix_too_high() -> None:
    """VIX=24 is at the boundary — not < 24 → RANGE, not BULL."""
    result = _classify_vix_regime(_snap(24.0, 0.5))
    assert result == "RANGE"


@pytest.mark.unit
def test_classify_vix_regime_range_when_gain_below_threshold() -> None:
    """SPX+0.2% is below the 0.3 floor → RANGE."""
    result = _classify_vix_regime(_snap(18.0, 0.2))
    assert result == "RANGE"


@pytest.mark.unit
def test_classify_vix_regime_crisis_wins_over_bull_via_inversion() -> None:
    """VIX9D > VIX (inverted) overrides any bull signal → CRISIS."""
    result = _classify_vix_regime(_snap(18.0, 0.5, vix9d=22.0))
    assert result == "CRISIS"


@pytest.mark.unit
def test_classify_vix_regime_crisis_high_vix() -> None:
    """VIX >= 35 → CRISIS regardless of SPX change."""
    result = _classify_vix_regime(_snap(36.0, 1.5))
    assert result == "CRISIS"


@pytest.mark.unit
def test_classify_vix_regime_volatile() -> None:
    """VIX in 25-34 range → VOLATILE."""
    result = _classify_vix_regime(_snap(28.0, 0.5))
    assert result == "VOLATILE"


@pytest.mark.unit
def test_classify_vix_regime_bear() -> None:
    """SPX -1.6% → BEAR (threshold is <= -1.5%)."""
    result = _classify_vix_regime(_snap(22.0, -1.6))
    assert result == "BEAR"


@pytest.mark.unit
def test_classify_vix_regime_returns_range_for_none() -> None:
    """None snapshot → RANGE safe fallback."""
    assert _classify_vix_regime(None) == "RANGE"


# ---------------------------------------------------------------------------
# build_regime_pill_state_plan — integration: VIX fallback BULL commits
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_pill_plan_vix_fallback_commits_bull_after_three_cycles() -> None:
    """S07 offline: after 3 matching BULL candidates the pill commits to BULL."""
    plan = build_regime_pill_state_plan(
        metrics={},
        regime_sticky=None,
        vix_candidate_regime="BULL",
        vix_candidate_count=2,
        vix_snapshot=_snap(18.0, 0.5),
    )
    assert plan.s07_live is False
    assert plan.regime == "BULL"
    assert plan.next_vix_candidate_regime == "BULL"
    assert plan.next_vix_candidate_count == 3


@pytest.mark.unit
def test_pill_plan_vix_fallback_does_not_commit_bull_before_three_cycles() -> None:
    """Only 1 matching BULL candidate — still in debounce, uses sticky RANGE."""
    plan = build_regime_pill_state_plan(
        metrics={},
        regime_sticky="RANGE",
        vix_candidate_regime="BULL",
        vix_candidate_count=1,
        vix_snapshot=_snap(18.0, 0.5),
    )
    assert plan.s07_live is False
    assert plan.regime == "RANGE"  # sticky still governs
    assert plan.next_vix_candidate_regime == "BULL"
    assert plan.next_vix_candidate_count == 2
