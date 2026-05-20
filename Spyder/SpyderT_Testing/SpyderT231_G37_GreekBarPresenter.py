#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
"""Focused regressions for G37 Greek bar risk mapping extraction."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # pyright: ignore[reportAttributeAccessIssue]

from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard  # pyright: ignore[reportMissingImports]
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import TradingMode  # pyright: ignore[reportMissingImports]
from Spyder.SpyderG_GUI.SpyderG37_GreekBarPresenter import build_greek_bar_updates  # pyright: ignore[reportMissingImports]


class _BarStub:
    def __init__(self) -> None:
        self.calls: list[tuple[float, str]] = []

    def set_value(self, value: float, status: str) -> None:
        self.calls.append((value, status))


def test_build_greek_bar_updates_maps_thresholds_and_invalid_values() -> None:
    updates = {update.key: update for update in build_greek_bar_updates(
        {
            "delta": 85.0,
            "gamma": 6.5,
            "theta": -100.0,
            "vega": "bad",
        }
    )}

    assert updates["delta"].value == 85.0
    assert updates["delta"].status == "HIGH RISK"
    assert updates["gamma"].value == 6.5
    assert updates["gamma"].status == "ELEVATED"
    assert updates["theta"].value == -100.0
    assert updates["theta"].status == "NORMAL"
    assert updates["vega"].value == 0.0
    assert updates["vega"].status == "NORMAL"


def test_refresh_spreads_panel_uses_greek_bar_presenter_output() -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.atm_iv_label = None
    dash.iv_rank_label = None
    dash._trade_audit_dialog = None
    dash.spreads_summary_label = None
    dash.bp_used_label = None
    dash.realized_today_label = None
    dash.trading_mode = TradingMode.PAPER
    dash.positions_table = None
    dash.spreads_table = None
    dash.port_delta_label = None
    dash.port_gamma_label = None
    dash.port_theta_label = None
    dash.port_vega_label = None
    dash.port_charm_label = None
    dash.port_vanna_label = None
    dash.greek_bars = {
        "delta": _BarStub(),
        "gamma": _BarStub(),
        "theta": _BarStub(),
        "vega": _BarStub(),
    }
    dash._portfolio_summary_dialog = None
    dash._render_paper_spreads_in_tree = lambda *args, **kwargs: None

    refresh_spreads_panel = getattr(dash, "_refresh_spreads_panel")
    refresh_spreads_panel(
        {
            "portfolio_greeks": {
                "delta": 85.0,
                "gamma": 6.5,
                "theta": -100.0,
                "vega": -550.0,
            },
        }
    )

    assert dash.greek_bars["delta"].calls == [(85.0, "HIGH RISK")]
    assert dash.greek_bars["gamma"].calls == [(6.5, "ELEVATED")]
    assert dash.greek_bars["theta"].calls == [(-100.0, "NORMAL")]
    assert dash.greek_bars["vega"].calls == [(-550.0, "HIGH RISK")]
