#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
"""Focused regressions for G36 IV and Greek strip presentation extraction."""

from __future__ import annotations

import os

from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard  # pyright: ignore[reportMissingImports]
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import COLORS, TradingMode  # pyright: ignore[reportMissingImports]
from Spyder.SpyderG_GUI.SpyderG36_StripMetricsPresenter import (  # pyright: ignore[reportMissingImports]
    build_atm_iv_label_presentation,
    build_iv_rank_label_presentation,
    build_portfolio_greek_strip_presentations,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _Label:
    def __init__(self) -> None:
        self._text = ""
        self._style = ""

    def setText(self, value: str) -> None:  # noqa: N802
        self._text = value

    def text(self) -> str:
        return self._text

    def setStyleSheet(self, value: str) -> None:  # noqa: N802
        self._style = value

    def styleSheet(self) -> str:
        return self._style


def test_build_atm_iv_label_presentation_uses_negative_threshold() -> None:
    presentation = build_atm_iv_label_presentation(0.55, COLORS)

    assert presentation.text == "ATM IV  55.0%"
    assert COLORS["negative"] in presentation.style


def test_build_iv_rank_label_presentation_uses_positive_low_vol_signal() -> None:
    presentation = build_iv_rank_label_presentation(10.0, COLORS)

    assert presentation.text == "IVR  10"
    assert COLORS["positive"] in presentation.style


def test_build_portfolio_greek_strip_presentations_formats_thresholds() -> None:
    presentations = build_portfolio_greek_strip_presentations(
        {
            "delta": 35.0,
            "gamma": 0.31,
            "theta": 12.5,
            "vega": -450.0,
            "charm": 0.1234,
            "vanna": -0.2222,
        },
        COLORS,
    )

    assert presentations.delta.text == "Δ  +35.0"
    assert COLORS.get("warning", COLORS["text"]) in presentations.delta.style
    assert presentations.gamma.text == "Γ  +0.31"
    assert COLORS["negative"] in presentations.gamma.style
    assert presentations.theta.text == "Θ  $+12.50/day"
    assert COLORS["positive"] in presentations.theta.style
    assert presentations.vega.text == "V  -450.0"
    assert COLORS.get("warning", COLORS["text"]) in presentations.vega.style
    assert presentations.charm_text == "Chr: +0.123"
    assert presentations.vanna_text == "Van: -0.222"


def test_refresh_spreads_panel_uses_strip_metrics_presenter_output() -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.atm_iv_label = _Label()
    dash.iv_rank_label = _Label()
    dash._trade_audit_dialog = None
    dash.spreads_summary_label = None
    dash.bp_used_label = None
    dash.realized_today_label = None
    dash.trading_mode = TradingMode.PAPER
    dash.positions_table = None
    dash.spreads_table = None
    dash.port_delta_label = _Label()
    dash.port_gamma_label = _Label()
    dash.port_theta_label = _Label()
    dash.port_vega_label = _Label()
    dash.port_charm_label = _Label()
    dash.port_vanna_label = _Label()
    dash.greek_bars = None
    dash._portfolio_summary_dialog = None
    dash._render_paper_spreads_in_tree = lambda *args, **kwargs: None

    refresh_spreads_panel = getattr(dash, "_refresh_spreads_panel")
    refresh_spreads_panel(
        {
            "atm_iv": 0.55,
            "iv_rank": 10.0,
            "portfolio_greeks": {
                "delta": 35.0,
                "gamma": 0.31,
                "theta": 12.5,
                "vega": -450.0,
                "charm": 0.1234,
                "vanna": -0.2222,
            },
        }
    )

    assert dash.atm_iv_label.text() == "ATM IV  55.0%"
    assert dash.iv_rank_label.text() == "IVR  10"
    assert dash.port_delta_label.text() == "Δ  +35.0"
    assert dash.port_gamma_label.text() == "Γ  +0.31"
    assert dash.port_theta_label.text() == "Θ  $+12.50/day"
    assert dash.port_vega_label.text() == "V  -450.0"
    assert dash.port_charm_label.text() == "Chr: +0.123"
    assert dash.port_vanna_label.text() == "Van: -0.222"
    assert COLORS["negative"] in dash.atm_iv_label.styleSheet()
    assert COLORS["positive"] in dash.iv_rank_label.styleSheet()
    assert COLORS.get("warning", COLORS["text"]) in dash.port_delta_label.styleSheet()
    assert COLORS["negative"] in dash.port_gamma_label.styleSheet()
    assert COLORS["positive"] in dash.port_theta_label.styleSheet()
    assert COLORS.get("warning", COLORS["text"]) in dash.port_vega_label.styleSheet()
