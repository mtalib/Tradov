#!/usr/bin/env python3
"""Focused tests for G05 PAPER-to-LIVE switch dialog wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import TradingMode
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.trading_active = False
    dash.trading_mode = TradingMode.PAPER
    dash.connection_info = SimpleNamespace(api_connected=False, mkt_data_connected=False)
    dash.api_connected = False
    dash.mkt_data_connected = False
    dash._update_mode_buttons = MagicMock()
    dash._handle_pending_orders_gate = MagicMock(return_value=True)
    dash._confirm_live_trading = MagicMock(return_value=True)
    dash._apply_mode_change = MagicMock()
    dash._log_lines = []
    dash.add_system_log = lambda message: dash._log_lines.append(str(message))
    return dash


def test_on_mode_btn_clicked_uses_helper_for_api_connection_gate(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[str] = []
    critical_calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(
        g05,
        "build_paper_to_live_switch_plan",
        lambda: helper_calls.append("called")
        or SimpleNamespace(
            api_disconnected=SimpleNamespace(dialog_title="api-title", dialog_text="api-text"),
            market_data_disconnected=SimpleNamespace(dialog_title="data-title", dialog_text="data-text"),
            confirmation=SimpleNamespace(
                required_phrase="phrase",
                dialog_title="confirm-title",
                header_text="confirm-header",
                confirm_button_text="confirm-button",
                declined_log_message="confirm-log",
            ),
        ),
    )
    monkeypatch.setattr(
        g05.QMessageBox,
        "critical",
        lambda *args: critical_calls.append(args),
    )

    dash._on_mode_btn_clicked(TradingMode.LIVE)

    assert helper_calls == ["called"]
    assert critical_calls[0][1] == "api-title"
    assert critical_calls[0][2] == "api-text"
    dash._update_mode_buttons.assert_called_once_with()
    dash._confirm_live_trading.assert_not_called()
    dash._apply_mode_change.assert_not_called()


def test_on_mode_btn_clicked_uses_helper_for_market_data_gate(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash.api_connected = True
    helper_calls: list[str] = []
    critical_calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(
        g05,
        "build_paper_to_live_switch_plan",
        lambda: helper_calls.append("called")
        or SimpleNamespace(
            api_disconnected=SimpleNamespace(dialog_title="api-title", dialog_text="api-text"),
            market_data_disconnected=SimpleNamespace(dialog_title="data-title", dialog_text="data-text"),
            confirmation=SimpleNamespace(
                required_phrase="phrase",
                dialog_title="confirm-title",
                header_text="confirm-header",
                confirm_button_text="confirm-button",
                declined_log_message="confirm-log",
            ),
        ),
    )
    monkeypatch.setattr(
        g05.QMessageBox,
        "critical",
        lambda *args: critical_calls.append(args),
    )

    dash._on_mode_btn_clicked(TradingMode.LIVE)

    assert helper_calls == ["called"]
    assert critical_calls[0][1] == "data-title"
    assert critical_calls[0][2] == "data-text"
    dash._update_mode_buttons.assert_called_once_with()
    dash._confirm_live_trading.assert_not_called()
    dash._apply_mode_change.assert_not_called()


def test_on_mode_btn_clicked_uses_helper_for_live_confirmation(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash.api_connected = True
    dash.mkt_data_connected = True
    dash._confirm_live_trading = MagicMock(return_value=False)
    helper_calls: list[str] = []

    monkeypatch.setattr(
        g05,
        "build_paper_to_live_switch_plan",
        lambda: helper_calls.append("called")
        or SimpleNamespace(
            api_disconnected=SimpleNamespace(dialog_title="api-title", dialog_text="api-text"),
            market_data_disconnected=SimpleNamespace(dialog_title="data-title", dialog_text="data-text"),
            confirmation=SimpleNamespace(
                required_phrase="phrase",
                dialog_title="confirm-title",
                header_text="confirm-header",
                confirm_button_text="confirm-button",
                declined_log_message="confirm-log",
            ),
        ),
    )

    dash._on_mode_btn_clicked(TradingMode.LIVE)

    assert helper_calls == ["called"]
    dash._confirm_live_trading.assert_called_once_with(
        required_phrase="phrase",
        dialog_title="confirm-title",
        header_text="confirm-header",
        confirm_button_text="confirm-button",
    )
    assert dash._log_lines == ["confirm-log"]
    dash._update_mode_buttons.assert_called_once_with()
    dash._apply_mode_change.assert_not_called()