#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
"""Focused regressions for the dedicated recent-trades dialog."""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel  # pyright: ignore[reportAttributeAccessIssue]

from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard  # pyright: ignore[reportMissingImports]
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import TradingMode  # pyright: ignore[reportMissingImports]
from Spyder.SpyderG_GUI.SpyderG27_RecentTradesDialog import RecentTradesDialog  # pyright: ignore[reportMissingImports]


def test_recent_trades_dialog_renders_trade_row() -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    dialog = RecentTradesDialog(
        mode_name="PAPER",
        trades=[
            {
                "timestamp": "2026-05-18T17:27:41+00:00",
                "symbol": "SPY260617P00691500",
                "side": "buy_to_open",
                "quantity": 1,
                "price": 4.2321,
                "realized_pnl": 0.0,
            },
            {
                "structure": "iron_condor",
                "expiration": "2026-05-29",
                "credit": 1.48,
                "qty": 1,
                "closed_at": "2026-05-16T14:46:00+00:00",
                "realized_pnl": -38.0,
                "legs": [
                    {"side": "Sell Put", "strike": 581.0, "qty": 1, "type": "P", "cost": -101.0, "pnl": -16.0},
                    {"side": "Buy Put", "strike": 576.0, "qty": 1, "type": "P", "cost": 30.0, "pnl": 5.0},
                    {"side": "Sell Call", "strike": 596.0, "qty": 1, "type": "C", "cost": -87.0, "pnl": -24.0},
                    {"side": "Buy Call", "strike": 601.0, "qty": 1, "type": "C", "cost": 10.0, "pnl": -3.0},
                ],
            }
        ],
    )

    tree = getattr(dialog, "_table")
    assert [tree.headerItem().text(i) for i in range(tree.columnCount())] == [
        "     LEG",
        "STRIKE",
        "QTY",
        "PRICE",
        "COST",
        "EXPIRY",
        "P&L",
        "",
    ]
    assert tree.topLevelItemCount() == 7

    flat_summary = tree.topLevelItem(0)
    flat_detail = tree.topLevelItem(1)
    assert flat_summary.text(0) == (
        "2026-05-18 13:27:41 TRADE RECORD : SPY260617P00691500  |  ACTION: BUY TO OPEN"
    )
    assert flat_detail.text(0).strip() == "SPY260617P00691500"
    assert flat_detail.text(2) == "1"
    assert flat_detail.text(3) == "$4.23"
    assert flat_detail.text(6) == "$+0.00"

    summary = tree.topLevelItem(2)
    summary_widget = tree.itemWidget(summary, 0)
    assert summary_widget is not None
    label_texts = [label.text() for label in summary_widget.findChildren(QLabel)]
    assert any("2026-05-16 10:46" in text for text in label_texts)
    assert any("CLOSED TRADE : IRON CONDOR" in text for text in label_texts)
    assert any("STATUS: CLOSED" in text for text in label_texts)
    assert any("NET P&L -$38 (-25.7%)" in text for text in label_texts)

    assert tree.topLevelItem(3).text(0).strip() == "Sell Put"
    assert tree.topLevelItem(3).text(1) == "$581P"
    assert tree.topLevelItem(3).text(3) == "$1.01"
    assert tree.topLevelItem(3).text(4) == "-$101"
    assert tree.topLevelItem(6).text(0).strip() == "Buy Call"
    assert tree.topLevelItem(6).text(6) == "-$3"


def test_recent_trades_dialog_shows_empty_state() -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    dialog = RecentTradesDialog(mode_name="LIVE", trades=[])

    tree = getattr(dialog, "_table")
    assert tree.topLevelItemCount() == 1
    assert tree.topLevelItem(0).text(0) == "No recent trade records found"


def test_get_recent_trade_history_records_prefers_grouped_closed_paper_cache() -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.trading_mode = TradingMode.PAPER
    dash._closed_trades_cache = [
        {"id": 1, "closed_at": 10.0},
        {"id": 2, "closed_at": 20.0},
    ]
    setattr(dash, "_get_recent_trades", lambda limit=30: [{"id": "db"}])

    get_recent_trade_history_records = getattr(dash, "_get_recent_trade_history_records")
    assert get_recent_trade_history_records(limit=1) == [{"id": 2, "closed_at": 20.0}]


def test_get_recent_trade_history_records_hides_flat_paper_entry_fills() -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.trading_mode = TradingMode.PAPER
    dash._closed_trades_cache = []
    called = {"value": False}

    def _unexpected_recent_trades(limit: int = 30) -> list[dict]:
        called["value"] = True
        return [
            {
                "timestamp": "2026-05-19T13:52:10.693352+00:00",
                "symbol": "SPY260618C00780500",
                "trade_type": "BUY_TO_OPEN",
            }
        ]

    setattr(dash, "_get_recent_trades", _unexpected_recent_trades)

    get_recent_trade_history_records = getattr(dash, "_get_recent_trade_history_records")
    assert get_recent_trade_history_records(limit=30) == []
    assert called["value"] is False


def test_dashboard_recent_trades_dialog_reuses_existing_instance() -> None:
    class _SignalStub:
        def __init__(self) -> None:
            self.callbacks: list = []

        def connect(self, callback):
            self.callbacks.append(callback)

    class _FakeRecentTradesDialog:
        instances: list[_FakeRecentTradesDialog] = []

        def __init__(self, mode_name: str, trades: list[dict], parent=None) -> None:
            self.mode_name = mode_name
            self.trades = list(trades)
            self.parent = parent
            self.finished = _SignalStub()
            self.visible = False
            self.raise_called = False
            self.activate_called = False
            self.show_called = False
            self.update_calls: list[list[dict]] = []
            _FakeRecentTradesDialog.instances.append(self)

        def isVisible(self) -> bool:
            return self.visible

        def update_trades(self, trades: list[dict]) -> None:
            self.trades = list(trades)
            self.update_calls.append(list(trades))

        def raise_(self) -> None:
            self.raise_called = True

        def activateWindow(self) -> None:
            self.activate_called = True

        def show(self) -> None:
            self.visible = True
            self.show_called = True

    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.trading_mode = TradingMode.PAPER
    setattr(dash, "_recent_trades_dialog", None)
    setattr(
        dash,
        "_get_recent_trade_history_records",
        lambda limit=30: [{"symbol": "SPY", "timestamp": "2026-05-14T19:45:00+00:00"}],
    )
    open_recent_trades_history_dialog = getattr(dash, "_open_recent_trades_history_dialog")

    with patch(
        "Spyder.SpyderG_GUI.SpyderG05_TradingDashboard.RecentTradesDialog",
        _FakeRecentTradesDialog,
    ):
        open_recent_trades_history_dialog()

        assert len(_FakeRecentTradesDialog.instances) == 1
        created = _FakeRecentTradesDialog.instances[0]
        assert created.mode_name == "PAPER"
        assert created.show_called is True
        assert getattr(dash, "_recent_trades_dialog") is created

        created.visible = True
        setattr(
            dash,
            "_get_recent_trade_history_records",
            lambda limit=30: [{"symbol": "QQQ", "timestamp": "2026-05-14T20:00:00+00:00"}],
        )
        open_recent_trades_history_dialog()

        assert len(_FakeRecentTradesDialog.instances) == 1
        assert created.update_calls[-1] == [{"symbol": "QQQ", "timestamp": "2026-05-14T20:00:00+00:00"}]
        assert created.raise_called is True
        assert created.activate_called is True
