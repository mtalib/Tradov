#!/usr/bin/env python3
# pyright: reportPrivateUsage=false
"""Thin regression for G05 P&L table refresh orchestration."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import TradingMode


class _SummaryAdapter:
    def __init__(self) -> None:
        self.session_db = None

    def fetch_pnl_summary(self, session_db, *, log_error=None):
        _ = log_error
        self.session_db = session_db
        return {
            "today": 25.0,
            "week": 40.0,
        }


class _TableItem:
    def __init__(self, value: str) -> None:
        self._value = value

    def text(self) -> str:
        return self._value

    def setText(self, value: str) -> None:  # noqa: N802 - Qt-style method name
        self._value = value

    def setForeground(self, _value) -> None:  # noqa: N802 - Qt-style method name
        return None


class _TableWidget:
    def __init__(self, rows: int, cols: int) -> None:
        self._grid: dict[tuple[int, int], _TableItem] = {}
        self.rows = rows
        self.cols = cols

    def item(self, row: int, col: int):
        return self._grid.get((row, col))

    def setItem(self, row: int, col: int, item) -> None:  # noqa: N802 - Qt-style method name
        self._grid[(row, col)] = item


def test_refresh_pnl_table_uses_session_adapter_overlay() -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.pnl_table = _TableWidget(4, 8)
    dash._h07_performance_analytics = None
    dash._pnl_stats_by_mode = {}
    dash.trading_mode = TradingMode.PAPER
    dash._session_db_adapter = _SummaryAdapter()
    session_db = object()
    dash._get_mode_session_db = lambda: session_db

    qtwidgets = sys.modules.get("PySide6.QtWidgets")
    assert qtwidgets is not None
    with patch.object(qtwidgets, "QTableWidgetItem", _TableItem, create=True):
        dash._refresh_pnl_table({"today_pnl": "$+10.00"})

    assert dash._session_db_adapter.session_db is session_db
    assert dash.pnl_table.item(0, 1).text() == "$+10.00"
    assert dash.pnl_table.item(1, 1).text() == "$+40.00"
    assert dash._pnl_stats_by_mode[TradingMode.PAPER]["week_pnl"] == "$+40.00"
