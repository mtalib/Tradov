#!/usr/bin/env python3
"""Focused tests for the G52 regime pill bar presenter."""

from Spyder.SpyderG_GUI.SpyderG52_RegimePillBarPresenter import (
    build_regime_pill_bar_presentation,
)


def test_build_regime_pill_bar_presentation_formats_reconciliation_and_reason() -> None:
    presentation = build_regime_pill_bar_presentation(
        regime="BULL",
        stress="LOW",
        stance="CHOPPY",
        gate="CRISIS",
        dispatch_label="BLOCKED",
        dispatch_reason="risk gate",
        execution_regime="bear_high_vol",
        execution_gate_key="crisis_turbulent",
        s07_live=False,
        swan=1.2,
        pivot_enabled=True,
        panel_color="#111111",
        border_color="#222222",
    )

    assert "REGIME:" in presentation.regime_pill.text
    assert "BULL" in presentation.regime_pill.text
    assert "Reason:</b> risk gate" in presentation.dispatch_pill.tooltip
    assert "D31 execution regime=bear_high_vol" in presentation.dispatch_pill.tooltip
    assert "D31 policy bucket=crisis_turbulent" in presentation.dispatch_pill.tooltip
    assert "VIX fallback with debounce / sticky last-good S07" in presentation.dispatch_pill.tooltip
    assert "SpyderD34_PivotMeanReversion" in presentation.dispatch_pill.tooltip
    assert presentation.bar_stylesheet == "background-color: #111111; border: 1px solid #222222;"


def test_build_regime_pill_bar_presentation_highlights_bar_for_crisis() -> None:
    presentation = build_regime_pill_bar_presentation(
        regime="CRISIS",
        stress="CRISIS",
        stance="CRISIS",
        gate="CRISIS",
        dispatch_label="HALT",
        dispatch_reason="regime=CRISIS",
        execution_regime="",
        execution_gate_key="",
        s07_live=True,
        swan=3.1,
        pivot_enabled=False,
        panel_color="#111111",
        border_color="#222222",
    )

    assert "DISPATCH:" in presentation.dispatch_pill.text
    assert "HALT" in presentation.dispatch_pill.text
    assert presentation.bar_stylesheet == "background-color: #2a0a3a; border: 1px solid #6a2a9a;"
