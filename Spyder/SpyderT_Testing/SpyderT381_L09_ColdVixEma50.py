#!/usr/bin/env python3
"""Regression tests for L09 cold-start vix_ema50 guard fix (§10.36 P2 fix).

Verifies that _detect_lean_regime() correctly returns BULL_TRENDING (≥0.70 conf)
when vix_ema50 is NaN/unavailable but SPY > EMA50 and VIX is low — the
split-guard path added to handle the cold-start / warm-up period.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine import (
    MarketConditions,
    MarketRegime,
    RegimeDetectionResult,
    UnifiedRegimeEngine,
)

# ---------------------------------------------------------------------------
# Minimal engine fixture — avoids the heavyweight __init__
# ---------------------------------------------------------------------------

_LEAN_SETTINGS = {
    "atr_band_multiplier": 1.0,
    "atr_elevated_pct": 0.015,
    "vix_high_percentile": 80.0,
    "vix_high_level": 25.0,
}

_TS = datetime(2026, 5, 20, 14, 30, 0, tzinfo=timezone.utc)


def _make_engine() -> UnifiedRegimeEngine:
    """Return an engine with only the attributes needed by _detect_lean_regime."""
    eng = UnifiedRegimeEngine.__new__(UnifiedRegimeEngine)
    eng.lean_settings = _LEAN_SETTINGS
    return eng


def _cond(
    spy_price: float = 525.0,
    spy_ema50: float = 518.0,
    vix: float = 18.0,
    vix_ema50: float = float("nan"),
    vix9d: float = float("nan"),
    event_state: str = "clear",
) -> MarketConditions:
    return MarketConditions(
        timestamp=_TS,
        spy_price=spy_price,
        spy_change_pct=0.3,
        volume_ratio=1.0,
        vix_level=vix,
        vix9d_level=vix9d,
        spy_ema50=spy_ema50,
        vix_ema50=vix_ema50,
        event_clock_state=event_state,
    )


# ---------------------------------------------------------------------------
# Tests: vix_ema50 NaN (cold-start / warm-up scenario)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_detect_lean_regime_bull_partial_when_vix_ema50_missing() -> None:
    """SPY > EMA50 and VIX=18 (< 22 proxy) with NaN vix_ema50 → BULL_TRENDING >= 0.70."""
    eng = _make_engine()
    result = eng._detect_lean_regime(_cond(spy_price=525.0, spy_ema50=518.0, vix=18.0))
    assert result.regime == MarketRegime.BULL_TRENDING
    assert result.confidence >= 0.70, f"confidence too low: {result.confidence}"
    assert "partial" in result.metadata.get("reason", "")


@pytest.mark.unit
def test_detect_lean_regime_not_bull_when_vix_too_high_for_partial() -> None:
    """VIX=25 exceeds proxy ceiling of 22 → no BULL even with SPY > EMA50."""
    eng = _make_engine()
    result = eng._detect_lean_regime(_cond(spy_price=525.0, spy_ema50=518.0, vix=25.0))
    assert result.regime != MarketRegime.BULL_TRENDING


@pytest.mark.unit
def test_detect_lean_regime_not_bull_when_spy_below_ema50_partial() -> None:
    """SPY < EMA50 — partial path cannot produce BULL."""
    eng = _make_engine()
    result = eng._detect_lean_regime(_cond(spy_price=510.0, spy_ema50=518.0, vix=18.0))
    assert result.regime != MarketRegime.BULL_TRENDING


@pytest.mark.unit
def test_detect_lean_regime_bear_partial_when_vix_ema50_missing() -> None:
    """SPY < EMA50 and VIX=30 (> 28 proxy) with NaN vix_ema50 → BEAR_TRENDING >= 0.70."""
    eng = _make_engine()
    result = eng._detect_lean_regime(_cond(spy_price=510.0, spy_ema50=518.0, vix=30.0))
    assert result.regime == MarketRegime.BEAR_TRENDING
    assert result.confidence >= 0.70


@pytest.mark.unit
def test_detect_lean_regime_bull_full_when_vix_ema50_available() -> None:
    """Full path: SPY > EMA50 and VIX < vix_ema50 → BULL_TRENDING at confidence 0.90."""
    eng = _make_engine()
    result = eng._detect_lean_regime(_cond(spy_price=525.0, spy_ema50=518.0, vix=18.0, vix_ema50=22.0))
    assert result.regime == MarketRegime.BULL_TRENDING
    assert result.confidence == pytest.approx(0.90)
    assert result.metadata.get("reason") == "bull_trend"


@pytest.mark.unit
def test_detect_lean_regime_crisis_overrides_partial_on_inversion() -> None:
    """VIX9D > VIX inversion fires before any trend check."""
    eng = _make_engine()
    result = eng._detect_lean_regime(
        _cond(spy_price=525.0, spy_ema50=518.0, vix=18.0, vix9d=22.0)
    )
    assert result.regime == MarketRegime.CRISIS_MODE


@pytest.mark.unit
def test_detect_lean_regime_no_bull_when_all_data_missing() -> None:
    """All NaN inputs → cannot be BULL (falls through to neutral fallback)."""
    eng = _make_engine()
    result = eng._detect_lean_regime(
        _cond(
            spy_price=float("nan"),
            spy_ema50=float("nan"),
            vix=float("nan"),
        )
    )
    assert result.regime != MarketRegime.BULL_TRENDING
