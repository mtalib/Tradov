#!/usr/bin/env python3
"""Drift guard for autonomous decision and regime input contracts."""

from __future__ import annotations

from pathlib import Path
import json


REPO_SPYDER_ROOT = Path(__file__).resolve().parents[1]

A02_PATH = REPO_SPYDER_ROOT / "SpyderA_Core/SpyderA02_TradingEngine.py"
D31_PATH = REPO_SPYDER_ROOT / "SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py"
F09_PATH = REPO_SPYDER_ROOT / "SpyderF_Analysis/SpyderF09_EntryFilters.py"
S07_PATH = REPO_SPYDER_ROOT / "SpyderS_Signals/SpyderS07_CustomMetricsOrchestrator.py"
L09_PATH = REPO_SPYDER_ROOT / "SpyderL_ML/SpyderL09_UnifiedRegimeEngine.py"
REGIME_POLICY_PATH = REPO_SPYDER_ROOT.parent / "config/regime_policy.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _slice_between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    assert start >= 0, f"Missing marker: {start_marker}"
    end = text.find(end_marker, start)
    assert end >= 0, f"Missing marker: {end_marker}"
    return text[start:end]


def test_a02_and_d31_call_full_trust_gate_sequence() -> None:
    """A02 and D31 should call the agreed trust-gate checks in sequence."""
    a02 = _read(A02_PATH)
    d31 = _read(D31_PATH)

    required_calls = [
        "_check_data_quality_filter(params)",
        "_check_vol_surface_structure_filter(params)",
        "_check_dealer_flow_filter(params)",
        "_check_vix_term_structure_filter()",
        "_check_cboe_skew_filter()",
        "_check_market_internals_filter()",
        "_check_short_term_vol_stress_filter(params)",
        "_check_vol_of_vol_stress_filter(params)",
        "_check_put_call_sentiment_filter(params)",
        "_check_participation_filter(params)",
        "_check_qqq_confirmation_filter(params)",
        "_check_iwm_confirmation_filter(params)",
        "_check_xlk_confirmation_filter(params)",
        "_check_xlf_confirmation_filter(params)",
    ]

    for call in required_calls:
        assert call in a02, f"A02 trust-gate call missing: {call}"
        assert call in d31, f"D31 trust-gate call missing: {call}"


def test_a02_and_d31_currently_build_entry_filters_without_analyzer_injection() -> None:
    """Current contract documents analyzer-dependent checks as non-wired by default."""
    a02 = _read(A02_PATH)
    d31 = _read(D31_PATH)

    assert "EntryFilters(config_manager)" in a02
    assert "EntryFilters(config_manager)" in d31


def test_f09_analyzer_dependent_filters_still_short_circuit_when_dependencies_absent() -> None:
    """These filters must remain explicit about dependency-based no-op behavior."""
    f09 = _read(F09_PATH)

    assert "if self._vix_analyzer is None:" in f09
    assert "if self._skew_calculator is None:" in f09
    assert "if self._market_internals is None:" in f09


def test_s07_market_conditions_expose_current_active_trust_gate_keys() -> None:
    """S07 contract keys used by active trust-gate checks must stay available."""
    s07 = _read(S07_PATH)
    method_body = _slice_between(
        s07,
        "def get_current_market_conditions(self) -> dict[str, Any]:",
        "# ==============================================================================\n# MODULE FUNCTIONS",
    )

    expected_keys = [
        "'vix':",
        "'vix9d':",
        "'vxv':",
        "'vvix':",
        "'cpc':",
        "'rvol':",
        "'spy_change_pct':",
        "'qqq_change_pct':",
        "'iwm_change_pct':",
        "'xlk_change_pct':",
        "'xlf_change_pct':",
        "'data_quality_feed':",
        "'surface_confidence':",
        "'surface_age_ms':",
        "'term_slope_0_7':",
        "'rr_25d':",
        "'fly_25d':",
        "'dealer_flow':",
        "'wall_confidence':",
        "'flow_imbalance':",
    ]

    for key in expected_keys:
        assert key in method_body, f"S07 market-conditions key missing: {key}"


def test_l09_short_term_regime_scoring_excludes_macro_indicators() -> None:
    """Short-term regime scoring must not use macro/yield/sentiment indicators."""
    l09 = _read(L09_PATH)
    scoring_body = _slice_between(
        l09,
        "def _analyze_signals(self, signals: dict[str, float]) -> tuple[MarketRegime, float]:",
        "# Determine best regime",
    )

    forbidden_tokens = [
        "yield_slope",
        "yield_inverted",
        "yield_10y",
        "naaim",
        "aaii_bullish",
        "aaii_bearish",
    ]

    for token in forbidden_tokens:
        assert token not in scoring_body, f"Macro token leaked into short-term scoring: {token}"


def test_regime_policy_file_has_required_six_regimes() -> None:
    """Regime policy artifact must exist with required six-regime keys."""
    assert REGIME_POLICY_PATH.exists(), f"Missing regime policy file: {REGIME_POLICY_PATH}"
    policy = json.loads(REGIME_POLICY_PATH.read_text(encoding="utf-8"))

    assert isinstance(policy, dict)
    assert "regimes" in policy and isinstance(policy["regimes"], dict)

    required = {
        "bull_trend",
        "bear_trend",
        "range_calm",
        "high_vol_mean_reversion",
        "crisis_turbulent",
        "event_transition",
    }
    assert required.issubset(set(policy["regimes"].keys())), "Missing required regime keys"


def test_a02_and_d31_apply_regime_policy_gate_after_entry_trust_checks() -> None:
    """A02 and D31 should invoke regime policy gate from trust-gate path."""
    a02 = _read(A02_PATH)
    d31 = _read(D31_PATH)

    assert "return self._passes_regime_policy_gate(signal, market_conditions)" in a02
    assert "return self._passes_regime_policy_gate(signal, market_conditions)" in d31
