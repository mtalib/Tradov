#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
"""Focused regressions for dashboard positions-table money-column widths."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # pyright: ignore[reportAttributeAccessIssue]

from Spyder.SpyderG_GUI.SpyderG20_DashboardBuilder import create_positions_table  # pyright: ignore[reportMissingImports]


pytestmark = [pytest.mark.gui, pytest.mark.regression]


class _DashboardStub:
    def _positions_context_menu(self, *_args, **_kwargs) -> None:
        return None


def test_create_positions_table_labels_and_explains_money_columns() -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    tree = create_positions_table(_DashboardStub())

    assert tree.headerItem().text(5) == "CASH FLOW"
    assert tree.headerItem().text(7) == "P&L"
    assert tree.headerItem().toolTip(5) == (
        "Entry cash flow for each leg: SELL credits are positive, BUY debits are negative."
    )
    assert tree.headerItem().toolTip(7) == (
        "Current unrealized mark-to-market P&L for each leg or spread: green means gain, red means loss."
    )
    assert "font-size: 12px;" in tree.styleSheet()
    assert tree.columnWidth(5) >= 124
    assert tree.columnWidth(7) >= 110
