#!/usr/bin/env python3
"""Focused tests for G05 close-strategy confirmation dialog wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


class _Button:
    def __init__(self) -> None:
        self.text = ""
        self.style = ""

    def setText(self, value: str) -> None:  # noqa: N802
        self.text = value

    def setStyleSheet(self, value: str) -> None:  # noqa: N802
        self.style = value


class _MessageBox:
    StandardButton = g05.QMessageBox.StandardButton
    Icon = g05.QMessageBox.Icon
    last_instance = None

    def __init__(self, _parent) -> None:
        self.window_title = ""
        self.icon = None
        self.text = ""
        self.buttons = None
        self.default_button = None
        self.stylesheet = ""
        self.exec_result = g05.QMessageBox.StandardButton.Yes
        self._yes = _Button()
        self._cancel = _Button()
        _MessageBox.last_instance = self

    def setWindowTitle(self, value: str) -> None:  # noqa: N802
        self.window_title = value

    def setIcon(self, value) -> None:  # noqa: ANN001, N802
        self.icon = value

    def setText(self, value: str) -> None:  # noqa: N802
        self.text = value

    def setStandardButtons(self, value) -> None:  # noqa: ANN001, N802
        self.buttons = value

    def setDefaultButton(self, value) -> None:  # noqa: ANN001, N802
        self.default_button = value

    def button(self, value):  # noqa: ANN001
        if value == g05.QMessageBox.StandardButton.Yes:
            return self._yes
        return self._cancel

    def setStyleSheet(self, value: str) -> None:  # noqa: N802
        self.stylesheet = value

    def exec(self):  # noqa: A003
        return self.exec_result


class _MessageBoxFactory:
    StandardButton = _MessageBox.StandardButton
    Icon = _MessageBox.Icon

    def __init__(self, message_box: _MessageBox) -> None:
        self._message_box = message_box

    def __call__(self, _parent):  # noqa: ANN001
        return self._message_box


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.close_strategy = MagicMock()
    return dash


def test_confirm_close_strategy_uses_confirm_plan_helper(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(g05, "QMessageBox", _MessageBox)
    monkeypatch.setattr(
        g05,
        "build_close_strategy_confirm_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            title="Close Strategy",
            text="confirm copy",
            yes_button_text="close all",
            yes_button_style="yes-style",
            cancel_button_style="cancel-style",
            dialog_style="dialog-style",
        ),
    )

    strategy_data = {
        "strategy": "Iron Condor",
        "timestamp": "2026-05-15 09:45:00",
        "dte": 0,
        "legs": [1, 2, 3, 4],
        "net_pnl": "$125",
        "pct_return": "4.2%",
        "status": "OPEN",
    }

    SpyderTradingDashboard.confirm_close_strategy(dash, strategy_data)

    assert helper_calls == [{"strategy_data": strategy_data, "colors": g05.COLORS}]
    msg_box = _MessageBox.last_instance
    assert msg_box.window_title == "Close Strategy"
    assert msg_box.text == "confirm copy"
    assert msg_box._yes.text == "close all"
    assert msg_box._yes.style == "yes-style"
    assert msg_box._cancel.style == "cancel-style"
    assert msg_box.stylesheet == "dialog-style"
    dash.close_strategy.assert_called_once_with(strategy_data)


def test_confirm_close_strategy_skips_close_on_cancel(monkeypatch) -> None:
    dash = _build_dashboard_stub()

    monkeypatch.setattr(g05, "QMessageBox", _MessageBox)
    monkeypatch.setattr(
        g05,
        "build_close_strategy_confirm_plan",
        lambda **_kwargs: SimpleNamespace(
            title="Close Strategy",
            text="confirm copy",
            yes_button_text="close all",
            yes_button_style="yes-style",
            cancel_button_style="cancel-style",
            dialog_style="dialog-style",
        ),
    )
    _MessageBox.last_instance = None
    strategy_data = {
        "strategy": "Iron Condor",
        "timestamp": "2026-05-15 09:45:00",
        "dte": 0,
        "legs": [1, 2, 3, 4],
        "net_pnl": "$125",
        "pct_return": "4.2%",
        "status": "OPEN",
    }

    msg_box = _MessageBox(dash)
    msg_box.exec_result = g05.QMessageBox.StandardButton.Cancel
    monkeypatch.setattr(g05, "QMessageBox", _MessageBoxFactory(msg_box))

    SpyderTradingDashboard.confirm_close_strategy(dash, strategy_data)

    dash.close_strategy.assert_not_called()