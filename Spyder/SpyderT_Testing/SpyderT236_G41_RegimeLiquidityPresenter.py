#!/usr/bin/env python3
"""Focused tests for regime/liquidity presentation helpers."""

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG41_RegimeLiquidityPresenter import (
    LiquidityDiagnosticsPanelPresentation,
    LiquidityDiagnosticsSummary,
    build_liquidity_diagnostics_panel_presentation,
    build_pill_stylesheet,
    summarize_liquidity_diagnostics,
)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


class _Label:
    def __init__(self) -> None:
        self._text = ""

    def setText(self, value: str) -> None:  # noqa: N802
        self._text = value

    def text(self) -> str:
        return self._text


def _build_liquidity_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.liquidity_candidates_value = _Label()
    dash.liquidity_pass_ratio_value = _Label()
    dash.liquidity_freshness_value = _Label()
    dash.liquidity_top_failure_value = _Label()
    return dash


def test_summarize_liquidity_diagnostics_aggregates_counts_and_median() -> None:
    summary = summarize_liquidity_diagnostics(
        {
            "data": {
                "candidates": [
                    {"pass": True, "snapshot": {"quote_age_ms": 120.0}},
                    {"pass": False, "fail_reasons": ["stale_quote"], "snapshot": {"quote_age_ms": 300.0}},
                    {"pass": False, "fail_reasons": ["stale_quote", "wide_spread"], "snapshot": {"quote_age_ms": 180.0}},
                ]
            }
        }
    )

    assert summary == LiquidityDiagnosticsSummary(
        total=3,
        pass_count=1,
        fail_count=2,
        top_failure="stale_quote",
        median_freshness_ms=180.0,
    )


def test_build_pill_stylesheet_maps_categories() -> None:
    crisis_style, crisis_fg = build_pill_stylesheet("CRISIS")
    blocked_style, blocked_fg = build_pill_stylesheet("blocked")
    idle_style, idle_fg = build_pill_stylesheet("IDLE")

    assert "#3a1055" in crisis_style
    assert crisis_fg == "#cc88ff"
    assert "#3a2800" in blocked_style
    assert blocked_fg == "#e09020"
    assert "#3a3a3a" in idle_style
    assert idle_fg == "#aaaaaa"


def test_build_liquidity_diagnostics_panel_presentation_formats_fallbacks() -> None:
    presentation = build_liquidity_diagnostics_panel_presentation(
        LiquidityDiagnosticsSummary(
            total=0,
            pass_count=0,
            fail_count=0,
            top_failure="stale_quote",
            median_freshness_ms=float("nan"),
        )
    )

    assert presentation.candidates_text == "0"
    assert presentation.pass_ratio_text == "0/0"
    assert presentation.freshness_text == "-"
    assert presentation.top_failure_text == "none"


def test_update_liquidity_diagnostics_panel_uses_summary_output() -> None:
    dash = _build_liquidity_stub()

    dash._update_liquidity_diagnostics_panel(
        {
            "data": {
                "candidates": [
                    {"pass": True, "snapshot": {"quote_age_ms": 100.0}},
                    {"pass": False, "fail_reasons": ["wide_spread"], "snapshot": {"quote_age_ms": 200.0}},
                ]
            }
        }
    )

    assert dash.liquidity_candidates_value.text() == "2"
    assert dash.liquidity_pass_ratio_value.text() == "1/2"
    assert dash.liquidity_freshness_value.text() == "150 ms"
    assert dash.liquidity_top_failure_value.text() == "wide_spread"


def test_update_liquidity_diagnostics_panel_uses_presenter_output(monkeypatch) -> None:
    dash = _build_liquidity_stub()

    monkeypatch.setattr(
        g05,
        "build_liquidity_diagnostics_panel_presentation",
        lambda summary: LiquidityDiagnosticsPanelPresentation(
            candidates_text="candidates",
            pass_ratio_text="ratio",
            freshness_text="freshness",
            top_failure_text="failure",
        ),
    )

    dash._update_liquidity_diagnostics_panel({"data": {"candidates": []}})

    assert dash.liquidity_candidates_value.text() == "candidates"
    assert dash.liquidity_pass_ratio_value.text() == "ratio"
    assert dash.liquidity_freshness_value.text() == "freshness"
    assert dash.liquidity_top_failure_value.text() == "failure"
