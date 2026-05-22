#!/usr/bin/env python3
"""Regression tests for G110 gate/stance startup fallback (§10.36 P3 fix).

Verifies that build_regime_pill_status_plan() correctly:
- Uses execution_truth gate/stance when D31 has classified a regime
- Falls back to display-regime-derived labels when execution_truth is empty
  (the startup window before D31 first classifies)
- Returns sensible defaults and not empty strings in the startup case
"""

from __future__ import annotations

import pytest

from Spyder.SpyderG_GUI.SpyderG110_RegimePillStatusHelper import (
    build_regime_pill_status_plan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _plan(
    regime: str = "RANGE",
    swan: float = 1.5,
    s07_live: bool = False,
    execution_truth: dict | None = None,
    fallback_stress: str | None = None,
):
    return build_regime_pill_status_plan(
        regime=regime,
        swan=swan,
        s07_live=s07_live,
        execution_truth=execution_truth or {},
        fallback_stress=fallback_stress,
    )


# ---------------------------------------------------------------------------
# Startup fallback — execution_truth empty (D31 not yet classified)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_gate_falls_back_to_bull_trend_when_display_is_bull() -> None:
    """execution_truth empty + display BULL → GATE=BULL TREND (not empty string)."""
    result = _plan(regime="BULL")
    assert result.gate == "BULL TREND"


@pytest.mark.unit
def test_gate_falls_back_to_range_calm_when_display_is_range() -> None:
    """execution_truth empty + display RANGE → GATE=RANGE CALM."""
    result = _plan(regime="RANGE")
    assert result.gate == "RANGE CALM"


@pytest.mark.unit
def test_gate_falls_back_to_bear_trend_when_display_is_bear() -> None:
    """execution_truth empty + display BEAR → GATE=BEAR TREND."""
    result = _plan(regime="BEAR")
    assert result.gate == "BEAR TREND"


@pytest.mark.unit
def test_gate_falls_back_to_high_vol_when_display_is_volatile() -> None:
    """execution_truth empty + display VOLATILE → GATE=HIGH VOL."""
    result = _plan(regime="VOLATILE")
    assert result.gate == "HIGH VOL"


@pytest.mark.unit
def test_gate_falls_back_to_crisis_when_display_is_crisis() -> None:
    """execution_truth empty + display CRISIS → GATE=CRISIS."""
    result = _plan(regime="CRISIS")
    assert result.gate == "CRISIS"


@pytest.mark.unit
def test_stance_falls_back_to_bullish_when_display_is_bull() -> None:
    """execution_truth empty + display BULL → STANCE=BULLISH."""
    result = _plan(regime="BULL")
    assert result.stance == "BULLISH"


@pytest.mark.unit
def test_stance_falls_back_to_choppy_when_display_is_range() -> None:
    """execution_truth empty + display RANGE → STANCE=CHOPPY."""
    result = _plan(regime="RANGE")
    assert result.stance == "CHOPPY"


@pytest.mark.unit
def test_gate_never_empty_for_unknown_regime() -> None:
    """Unknown display regime should return a non-empty gate (default RANGE CALM)."""
    result = _plan(regime="UNKNOWN_REGIME")
    assert result.gate != ""


# ---------------------------------------------------------------------------
# execution_truth present — D31 values win
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_execution_truth_gate_overrides_display_regime() -> None:
    """When D31 provides a gate label it must override the display-regime fallback."""
    result = _plan(
        regime="RANGE",
        execution_truth={"gate": "BULL TREND", "stance": "BULLISH"},
    )
    assert result.gate == "BULL TREND"
    assert result.stance == "BULLISH"


@pytest.mark.unit
def test_execution_truth_gate_case_normalised() -> None:
    """Gate from execution_truth is upper-cased; lowercase input works."""
    result = _plan(
        regime="RANGE",
        execution_truth={"gate": "bull trend", "stance": "bullish"},
    )
    assert result.gate == "BULL TREND"
    assert result.stance == "BULLISH"


# ---------------------------------------------------------------------------
# Stress label — s07_live governs path
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_stress_uses_swan_when_s07_live() -> None:
    """S07 live: swan=1.2 → stress=LOW."""
    result = _plan(regime="BULL", swan=1.2, s07_live=True)
    assert result.stress == "LOW"


@pytest.mark.unit
def test_stress_uses_fallback_when_s07_offline() -> None:
    """S07 offline: fallback_stress=MEDIUM is returned."""
    result = _plan(regime="BULL", s07_live=False, fallback_stress="MEDIUM")
    assert result.stress == "MEDIUM"


@pytest.mark.unit
def test_stress_unknown_when_s07_offline_and_no_fallback() -> None:
    """S07 offline + no fallback → stress=UNKNOWN (never empty)."""
    result = _plan(regime="RANGE", s07_live=False, fallback_stress=None)
    assert result.stress == "UNKNOWN"
