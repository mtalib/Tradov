#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
"""Focused regressions for G38 legacy spreads table presentation extraction."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard  # pyright: ignore[reportMissingImports]
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import COLORS, TradingMode  # pyright: ignore[reportMissingImports]
from Spyder.SpyderG_GUI.SpyderG38_LegacySpreadsTablePresenter import build_legacy_spreads_table_rows  # pyright: ignore[reportMissingImports]

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _TableItem:
    def __init__(self, value: str) -> None:
        self._value = value
        self.foreground = None

    def text(self) -> str:
        return self._value

    def setForeground(self, value) -> None:  # noqa: N802
        self.foreground = value


class _TableWidget:
    def __init__(self, rows: int, cols: int) -> None:
        self._grid: dict[tuple[int, int], _TableItem] = {}
        self._row_count = rows
        self._col_count = cols

    def setRowCount(self, value: int) -> None:  # noqa: N802
        self._row_count = value

    def rowCount(self) -> int:  # noqa: N802
        return self._row_count

    def setItem(self, row: int, col: int, item: _TableItem) -> None:  # noqa: N802
        self._grid[(row, col)] = item

    def item(self, row: int, col: int) -> _TableItem | None:
        return self._grid.get((row, col))


def test_build_legacy_spreads_table_rows_formats_cells_and_negative_mtm() -> None:
    rows = build_legacy_spreads_table_rows(
        [
            {
                "id": "spread-1",
                "expiration": "2026-05-15",
                "short_strike": 500.0,
                "long_strike": 495.0,
                "qty": 2,
                "credit": 1.23,
                "debit": 0.45,
                "mtm_pnl": -12.5,
            }
        ],
        COLORS,
    )

    assert len(rows) == 1
    assert rows[0].cells == (
        "spread-1",
        "2026-05-15",
        "500/495",
        "2",
        "$1.23",
        "$0.45",
        "$-12.50",
    )
    assert rows[0].mtm_color == COLORS["negative"]


def test_refresh_spreads_panel_uses_legacy_spreads_table_presenter_output() -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.atm_iv_label = None
    dash.iv_rank_label = None
    dash._trade_audit_dialog = None
    dash.spreads_summary_label = None
    dash.bp_used_label = None
    dash.realized_today_label = None
    dash.trading_mode = TradingMode.PAPER
    dash.positions_table = None
    dash.spreads_table = _TableWidget(0, 7)
    dash.port_delta_label = None
    dash.port_gamma_label = None
    dash.port_theta_label = None
    dash.port_vega_label = None
    dash.port_charm_label = None
    dash.port_vanna_label = None
    dash.greek_bars = None
    dash._portfolio_summary_dialog = None
    dash._render_paper_spreads_in_tree = lambda *args, **kwargs: None

    refresh_spreads_panel = getattr(dash, "_refresh_spreads_panel")
    qtwidgets = sys.modules.get("PySide6.QtWidgets")
    assert qtwidgets is not None
    with patch.object(qtwidgets, "QTableWidgetItem", _TableItem, create=True):
        refresh_spreads_panel(
            {
                "open_spreads_detail": [
                    {
                        "id": "spread-1",
                        "expiration": "2026-05-15",
                        "short_strike": 500.0,
                        "long_strike": 495.0,
                        "qty": 2,
                        "credit": 1.23,
                        "debit": 0.45,
                        "mtm_pnl": -12.5,
                    }
                ],
            }
        )

    assert dash.spreads_table.rowCount() == 1
    assert dash.spreads_table.item(0, 0).text() == "spread-1"
    assert dash.spreads_table.item(0, 2).text() == "500/495"
    assert dash.spreads_table.item(0, 6).text() == "$-12.50"
