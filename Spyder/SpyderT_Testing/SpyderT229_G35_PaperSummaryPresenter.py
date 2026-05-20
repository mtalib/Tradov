#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
"""Focused regressions for G35 paper summary presentation extraction."""

from __future__ import annotations

import os

from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard  # pyright: ignore[reportMissingImports]
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import COLORS, TradingMode  # pyright: ignore[reportMissingImports]
from Spyder.SpyderG_GUI.SpyderG34_AccountCapitalMath import BuyingPowerUsage  # pyright: ignore[reportMissingImports]
from Spyder.SpyderG_GUI.SpyderG35_PaperSummaryPresenter import (  # pyright: ignore[reportMissingImports]
    build_buying_power_badge_presentation,
    build_portfolio_summary_rows,
    build_realized_today_badge_presentation,
    build_spreads_summary_badge_presentation,
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


def test_build_spreads_summary_badge_presentation_formats_negative_mtm() -> None:
    presentation = build_spreads_summary_badge_presentation(2, -25.5, COLORS)

    assert presentation.text == "OPEN  2   MTM  $-25.50"
    assert COLORS["negative"] in presentation.style


def test_build_buying_power_badge_presentation_uses_warning_thresholds() -> None:
    presentation = build_buying_power_badge_presentation(
        BuyingPowerUsage(used=60000.0, capital=100000.0, percent=60.0),
        COLORS,
    )

    assert presentation.text == "BP  $60,000 / $100,000  (60%)"
    assert COLORS.get("warning", COLORS["text"]) in presentation.style


def test_build_portfolio_summary_rows_formats_realized_and_bp_rows() -> None:
    rows = build_portfolio_summary_rows(
        open_count=3,
        spreads_mtm=125.0,
        realized=-45.25,
        atm_iv_raw=0.32,
        iv_rank=40.0,
        greeks={"delta": 15.0, "gamma": 0.1, "theta": 12.0, "vega": -150.0},
        bp_usage=BuyingPowerUsage(used=1250.0, capital=100000.0, percent=1.25),
        colors=COLORS,
    )

    assert rows[0].text == "OPEN  3"
    assert rows[1].text == "MTM  $+125.00"
    assert rows[2].text == "REALIZED  $-45.25"
    assert rows[2].color == COLORS["negative"]
    assert rows[-1].text == "BP USED  1%  ($1,250 / $100,000)"
    assert rows[-1].color == COLORS["positive"]


def test_build_realized_today_badge_presentation_formats_positive_values() -> None:
    presentation = build_realized_today_badge_presentation(12.5, COLORS)

    assert presentation.text == "REALIZED  $+12.50"
    assert COLORS["positive"] in presentation.style


def test_refresh_spreads_panel_uses_summary_presenter_output() -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.atm_iv_label = None
    dash.iv_rank_label = None
    dash._trade_audit_dialog = None
    dash.spreads_summary_label = _Label()
    dash.bp_used_label = _Label()
    dash.realized_today_label = _Label()
    dash.trading_mode = TradingMode.PAPER
    dash.positions_table = None
    dash.spreads_table = None
    dash.port_delta_label = None
    dash.port_gamma_label = None
    dash.port_theta_label = None
    dash.port_vega_label = None
    dash.port_charm_label = None
    dash.port_vanna_label = None
    dash.greek_bars = None
    dash._portfolio_summary_dialog = None
    dash._paper_initial_capital = 100000.0
    dash._render_paper_spreads_in_tree = lambda *args, **kwargs: None

    refresh_spreads_panel = getattr(dash, "_refresh_spreads_panel")
    refresh_spreads_panel(
        {
            "open_spreads_detail": [
                {"max_loss_per_contract": 500.0, "qty": 2},
                {"max_loss_per_contract": 250.0, "qty": 1},
            ],
            "spreads_unrealized_pnl": -25.5,
            "realized_pnl_today": 12.5,
        }
    )

    assert dash.spreads_summary_label.text() == "OPEN  2   MTM  $-25.50"
    assert dash.bp_used_label.text() == "BP  $1,250 / $100,000  (1%)"
    assert dash.realized_today_label.text() == "REALIZED  $+12.50"
    assert COLORS["negative"] in dash.spreads_summary_label.styleSheet()
    assert COLORS["positive"] in dash.bp_used_label.styleSheet()
    assert COLORS["positive"] in dash.realized_today_label.styleSheet()