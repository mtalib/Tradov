#!/usr/bin/env python3
"""Pure regime-pill state planning for dashboard updates."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RegimePillStatePlan:
    """Normalized S07 values plus sticky/VIX fallback state updates."""

    swan: float
    dix: float
    skew: float
    gex: float
    s07_live: bool
    regime: str
    next_regime_sticky: str | None
    next_vix_candidate_regime: str
    next_vix_candidate_count: int


def _metric_value(metrics: Mapping[str, object], key: str, default: float) -> float:
    entry = metrics.get(key)
    if not isinstance(entry, dict):
        return default

    value = entry.get("value", default)
    if isinstance(value, float) and math.isnan(value):
        return default
    return float(value)


def _quote_last(snapshot: Mapping[str, object], key: str) -> float | None:
    entry = snapshot.get(key)
    if isinstance(entry, dict) and entry.get("last"):
        return float(entry["last"])
    return None


def _quote_change_pct(snapshot: Mapping[str, object], key: str) -> float:
    entry = snapshot.get(key)
    if isinstance(entry, dict):
        return float(entry.get("change_pct", 0.0))
    return 0.0


def _classify_vix_regime(snapshot: Mapping[str, object] | None) -> str:
    if not isinstance(snapshot, Mapping):
        return "RANGE"

    vix = _quote_last(snapshot, "VIX") or 0.0
    vix9d = _quote_last(snapshot, "VIX9D") or 0.0
    spx_change_pct = _quote_change_pct(snapshot, "SPX")
    inverted = vix9d > 0.0 and vix > 0.0 and vix9d > vix

    if inverted or vix >= 35:
        return "CRISIS"
    if vix >= 25:
        return "VOLATILE"
    if spx_change_pct <= -1.5:
        return "BEAR"
    if spx_change_pct >= 0.3 and vix < 24:
        return "BULL"
    return "RANGE"


def build_regime_pill_state_plan(
    *,
    metrics: Mapping[str, object],
    regime_sticky: str | None,
    vix_candidate_regime: str,
    vix_candidate_count: int,
    vix_snapshot: Mapping[str, object] | None,
    vix_commit_cycles: int = 3,
) -> RegimePillStatePlan:
    """Return normalized pill state and the next sticky/VIX fallback state."""
    swan = _metric_value(metrics, "SWAN", 1.9)
    dix = _metric_value(metrics, "DIX", 42.0)
    skew = _metric_value(metrics, "SKEW", 120.0)
    gex = _metric_value(metrics, "GEX", 0.0)

    swan_live = isinstance(metrics.get("SWAN"), dict) and metrics["SWAN"].get("value") is not None
    dix_live = isinstance(metrics.get("DIX"), dict) and metrics["DIX"].get("value") is not None
    s07_live = swan_live and dix_live

    vix_new_regime = _classify_vix_regime(vix_snapshot)
    if vix_new_regime == vix_candidate_regime:
        next_vix_candidate_regime = vix_candidate_regime
        next_vix_candidate_count = min(vix_candidate_count + 1, vix_commit_cycles)
    else:
        next_vix_candidate_regime = vix_new_regime
        next_vix_candidate_count = 1

    vix_regime = (
        next_vix_candidate_regime
        if next_vix_candidate_count >= vix_commit_cycles
        else (regime_sticky or "RANGE")
    )

    if not s07_live:
        regime = regime_sticky if regime_sticky is not None else vix_regime
    elif swan >= 2.0:
        regime = "CRISIS"
    elif swan >= 1.95 or skew >= 150:
        regime = "VOLATILE"
    elif skew >= 140 and dix < 42:
        regime = "RANGE"
    elif dix >= 46 and gex >= 0 and swan < 1.9:
        regime = "BULL"
    elif dix <= 40 and swan >= 1.85:
        regime = "BEAR"
    elif dix >= 43 and swan < 1.92:
        regime = "BULL"
    else:
        regime = "RANGE"

    next_regime_sticky = regime if s07_live else regime_sticky
    return RegimePillStatePlan(
        swan=swan,
        dix=dix,
        skew=skew,
        gex=gex,
        s07_live=s07_live,
        regime=regime,
        next_regime_sticky=next_regime_sticky,
        next_vix_candidate_regime=next_vix_candidate_regime,
        next_vix_candidate_count=next_vix_candidate_count,
    )
