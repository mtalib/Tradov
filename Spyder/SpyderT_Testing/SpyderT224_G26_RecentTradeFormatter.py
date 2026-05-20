#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
"""Focused regressions for recent-trade formatting extraction."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QTableWidget, QTreeWidget  # pyright: ignore[reportAttributeAccessIssue]

from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard  # pyright: ignore[reportMissingImports]
from Spyder.SpyderG_GUI.SpyderG26_RecentTradeFormatter import (
    build_recent_trade_banner_text,
    build_recent_trade_display,
)  # pyright: ignore[reportMissingImports]


def test_build_recent_trade_display_formats_iso_trade() -> None:
    display = build_recent_trade_display(
        {
            "timestamp": "2026-05-14T19:45:00+00:00",
            "symbol": "SPY260515C00580000",
            "trade_type": "close",
            "quantity": "2",
            "price": 1.25,
            "cost_basis": -250.0,
            "realized_pnl": 45.5,
        }
    )

    assert display.timestamp_text == "2026-05-14 15:45:00"
    assert display.symbol == "SPY260515C00580000"
    assert display.action == "CLOSE"
    assert display.quantity_text == "2"
    assert display.price_text == "$1.25"
    assert display.cost_text == "$-250.00"
    assert display.realized_pnl_text == "$+45.50"
    assert display.realized_pnl_value == 45.5


def test_build_recent_trade_display_falls_back_to_side_and_placeholder() -> None:
    display = build_recent_trade_display(
        {
            "timestamp": "",
            "side": "sell_to_open",
            "quantity": None,
            "price": None,
            "realized_pnl": "",
        },
        symbol_placeholder="—",
    )

    assert display.timestamp_text == "--"
    assert display.symbol == "—"
    assert display.action == "SELL_TO_OPEN"
    assert display.quantity_text == "0"
    assert display.price_text == "$0.00"
    assert display.cost_text == "—"
    assert display.realized_pnl_text == "$+0.00"


def test_build_recent_trade_banner_text_uses_preformatted_values() -> None:
    display = build_recent_trade_display(
        {
            "timestamp": "2026-05-14T19:45:00Z",
            "symbol": "SPY",
            "side": "buy",
            "quantity": 1,
            "price": 7.5,
            "realized_pnl": -12.34,
        },
        symbol_placeholder="—",
    )

    assert build_recent_trade_banner_text(display) == (
        "RECENT TRADE | 2026-05-14 15:45:00 | SPY | BUY | "
        "QTY: 1 | PRICE: $7.50 | P&L: $-12.34"
    )


def test_build_recent_trade_display_treats_naive_h05_timestamp_as_utc() -> None:
    display = build_recent_trade_display(
        {
            "timestamp": "2026-05-14T19:45:00",
            "symbol": "SPY",
            "trade_type": "sell",
            "quantity": 1,
            "price": 2.0,
            "realized_pnl": 0.0,
        }
    )

    assert display.timestamp_text == "2026-05-14 15:45:00"


def test_populate_recent_trades_table_delegates_update_call() -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    class _DialogStub:
        def __init__(self) -> None:
            self.updated_with = None

        def update_trades(self, trades):
            self.updated_with = list(trades)

    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dialog = _DialogStub()

    populate_recent_trades_table = getattr(dash, "_populate_recent_trades_table")
    trades = [
        {
            "timestamp": "2026-05-14T19:45:00+00:00",
            "symbol": "SPY",
            "trade_type": "close",
            "quantity": 1,
            "price": 2.5,
            "realized_pnl": -10.0,
        }
    ]
    populate_recent_trades_table(dialog, trades)

    assert dialog.updated_with == trades


def test_add_recent_trade_rows_renders_helper_banner() -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.positions_table = QTreeWidget()
    dash.positions_table.setColumnCount(8)
    setattr(
        dash,
        "_get_recent_trades",
        lambda limit=3: [
        {
            "timestamp": "2026-05-14T19:45:00+00:00",
            "symbol": "SPY",
            "side": "buy",
            "quantity": 1,
            "price": 7.5,
            "realized_pnl": 12.0,
        }
        ],
    )

    add_recent_trade_rows = getattr(dash, "_add_recent_trade_rows")
    count = add_recent_trade_rows(limit=1)

    assert count == 1
    assert dash.positions_table.topLevelItem(0).text(0) == (
        "RECENT TRADE | 2026-05-14 15:45:00 | SPY | BUY | "
        "QTY: 1 | PRICE: $7.50 | P&L: $+12.00"
    )
