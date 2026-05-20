#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
"""Focused regressions for account-panel presentation extraction."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel  # pyright: ignore[reportAttributeAccessIssue]

from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard  # pyright: ignore[reportMissingImports]
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import COLORS  # pyright: ignore[reportMissingImports]
from Spyder.SpyderG_GUI.SpyderG28_AccountPanelPresenter import (  # pyright: ignore[reportMissingImports]
    build_account_pnl_presentation,
    build_account_snapshot_presentation,
    capture_account_snapshot_from_texts,
    format_account_money_text,
    parse_money_text,
)


def test_parse_money_text_handles_signed_unsigned_and_empty_values() -> None:
    assert parse_money_text("$100,024.40") == 100024.40
    assert parse_money_text("$+0.00") == 0.0
    assert parse_money_text("$-15.25") == -15.25
    assert parse_money_text("—") == 0.0


def test_capture_account_snapshot_from_texts_normalizes_label_values() -> None:
    snapshot = capture_account_snapshot_from_texts(
        settled_text="$100,000.00",
        buying_text="$75,500.25",
        realized_text="$+12.50",
        unrealized_text="$-3.25",
    )

    assert snapshot == {
        "settled_cash": 100000.0,
        "buying_power": 75500.25,
        "realized_pnl": 12.5,
        "unrealized_pnl": -3.25,
    }


def test_build_account_snapshot_presentation_formats_money_and_pnl() -> None:
    presentation = build_account_snapshot_presentation(
        {
            "settled_cash": 100000.0,
            "buying_power": 75000.5,
            "realized_pnl": 12.5,
            "unrealized_pnl": -3.25,
        },
        COLORS,
    )

    assert presentation.settled_text == "$100,000.00"
    assert presentation.buying_text == "$75,000.50"
    assert presentation.realized.text == "$+12.50"
    assert presentation.unrealized.text == "$-3.25"
    assert COLORS["positive"] in presentation.realized.style
    assert COLORS["negative"] in presentation.unrealized.style


def test_apply_account_snapshot_uses_presenter_output() -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.settled_value = QLabel()
    dash.buying_value = QLabel()
    dash.realized_value = QLabel()
    dash.unrealized_value = QLabel()
    dash.spyderbox_acct_number_lbl = QLabel()
    setattr(dash, "_sync_spyderbox_account_labels", lambda: dash.spyderbox_acct_number_lbl.setText("SpyderBox"))

    apply_account_snapshot = getattr(dash, "_apply_account_snapshot")
    apply_account_snapshot(
        {
            "settled_cash": 101000.0,
            "buying_power": 99000.0,
            "realized_pnl": 25.0,
            "unrealized_pnl": -5.0,
        }
    )

    assert dash.settled_value.text() == "$101,000.00"
    assert dash.buying_value.text() == "$99,000.00"
    assert dash.realized_value.text() == "$+25.00"
    assert dash.unrealized_value.text() == "$-5.00"
    assert COLORS["positive"] in dash.realized_value.styleSheet()
    assert COLORS["negative"] in dash.unrealized_value.styleSheet()
    assert dash.spyderbox_acct_number_lbl.text() == "SpyderBox"


def test_capture_account_snapshot_from_labels_uses_presenter_parsing() -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.settled_value = QLabel(format_account_money_text(100000.0))
    dash.buying_value = QLabel(format_account_money_text(75000.5))
    realized = build_account_pnl_presentation(10.0, COLORS)
    unrealized = build_account_pnl_presentation(-2.5, COLORS)
    dash.realized_value = QLabel(realized.text)
    dash.unrealized_value = QLabel(unrealized.text)

    capture_account_snapshot_from_labels = getattr(dash, "_capture_account_snapshot_from_labels")
    assert capture_account_snapshot_from_labels() == {
        "settled_cash": 100000.0,
        "buying_power": 75000.5,
        "realized_pnl": 10.0,
        "unrealized_pnl": -2.5,
    }


def test_on_balance_updated_formats_live_account_values_with_money_renderer() -> None:
    app = QApplication.instance() or QApplication([])
    assert app is not None

    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.settled_value = QLabel()
    dash.buying_value = QLabel()
    dash.trading_mode = None
    dash._remember_current_account_snapshot = lambda *args, **kwargs: None

    on_balance_updated = getattr(dash, "_on_balance_updated")
    on_balance_updated("live", 101000.0, 99000.0)

    assert dash.settled_value.text() == "$101,000.00"
    assert dash.buying_value.text() == "$99,000.00"