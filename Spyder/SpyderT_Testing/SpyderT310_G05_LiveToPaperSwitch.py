#!/usr/bin/env python3
"""Focused tests for G05 LIVE-to-PAPER switch dialog wiring."""

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
    dash.trading_mode = TradingMode.LIVE
    dash._update_mode_buttons = MagicMock()
    dash._handle_pending_orders_gate = MagicMock(return_value=True)
    dash._count_open_live_positions = MagicMock(return_value=0)
    dash._apply_mode_change = MagicMock()
    dash._log_lines = []
    dash.add_system_log = lambda message: dash._log_lines.append(str(message))
    return dash


def test_on_mode_btn_clicked_uses_helper_for_open_positions_warning(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash._count_open_live_positions.return_value = 2
    helper_calls: list[dict[str, object]] = []
    question_calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(
        g05,
        "build_live_to_paper_switch_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            open_positions_warning=SimpleNamespace(
                dialog_title="warning-title",
                dialog_text="warning-text",
                declined_log_message="warning-declined-log",
            ),
            final_confirmation=SimpleNamespace(
                dialog_title="final-title",
                dialog_text="final-text",
                declined_log_message="final-declined-log",
            ),
        ),
    )
    monkeypatch.setattr(
        g05.QMessageBox,
        "warning",
        lambda *_args: g05.QMessageBox.StandardButton.No,
    )
    monkeypatch.setattr(
        g05.QMessageBox,
        "question",
        lambda *args: question_calls.append(args) or g05.QMessageBox.StandardButton.Yes,
    )

    dash._on_mode_btn_clicked(TradingMode.PAPER)

    assert helper_calls == [{"open_positions_count": 2}]
    assert question_calls == []
    assert dash._log_lines == ["warning-declined-log"]
    dash._update_mode_buttons.assert_called_once_with()
    dash._apply_mode_change.assert_not_called()


def test_on_mode_btn_clicked_uses_helper_for_final_confirmation(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[dict[str, object]] = []
    question_calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(
        g05,
        "build_live_to_paper_switch_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            open_positions_warning=None,
            final_confirmation=SimpleNamespace(
                dialog_title="final-title",
                dialog_text="final-text",
                declined_log_message="final-declined-log",
            ),
        ),
    )
    monkeypatch.setattr(
        g05.QMessageBox,
        "question",
        lambda *args: question_calls.append(args) or g05.QMessageBox.StandardButton.Yes,
    )

    dash._on_mode_btn_clicked(TradingMode.PAPER)

    assert helper_calls == [{"open_positions_count": 0}]
    assert question_calls[0][1] == "final-title"
    assert question_calls[0][2] == "final-text"
    dash._apply_mode_change.assert_called_once_with(
        TradingMode.PAPER,
        arm_selected_mode=False,
    )
    dash._update_mode_buttons.assert_not_called()
    assert dash._log_lines == []
