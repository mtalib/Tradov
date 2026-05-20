#!/usr/bin/env python3
"""Focused tests for G05 pending-orders gate behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard, TradingMode
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash._log_lines: list[str] = []
    dash.add_system_log = lambda message: dash._log_lines.append(str(message))
    return dash


def test_handle_pending_orders_gate_uses_helper_prompt_and_success(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash._fetch_pending_orders = lambda _mode: [{"id": 101, "symbol": "SPY", "side": "sell", "quantity": 1, "status": "open"}]
    dash._cancel_orders = lambda orders, mode: (len(orders), 0)
    prompt_calls: list[dict[str, object]] = []
    outcome_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "build_pending_orders_gate_prompt",
        lambda **kwargs: prompt_calls.append(dict(kwargs)) or SimpleNamespace(
            prompt_title="prompt-title",
            prompt_text="prompt-text",
            declined_log_message="declined-log",
        ),
    )
    monkeypatch.setattr(
        g05,
        "build_pending_orders_gate_outcome",
        lambda **kwargs: outcome_calls.append(dict(kwargs)) or SimpleNamespace(
            failure_dialog_title="failure-title",
            failure_dialog_text="failure-text",
            success_log_message="success-log",
        ),
    )
    warning_calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        g05.QMessageBox,
        "warning",
        lambda *args: warning_calls.append(args) or g05.QMessageBox.StandardButton.Yes,
    )

    assert dash._handle_pending_orders_gate(TradingMode.PAPER, "LIVE", "contact support") is True
    assert prompt_calls == [
        {
            "pending_orders": [
                {"id": 101, "symbol": "SPY", "side": "sell", "quantity": 1, "status": "open"}
            ],
            "pending_mode_name": "paper",
            "target_label": "LIVE",
        }
    ]
    assert outcome_calls == [
        {
            "pending_mode_name": "paper",
            "support_suffix": "contact support",
            "cancelled_count": 1,
            "failed_count": 0,
        }
    ]
    assert warning_calls[0][1] == "prompt-title"
    assert warning_calls[0][2] == "prompt-text"
    assert dash._log_lines == ["success-log"]


def test_handle_pending_orders_gate_logs_decline_without_cancelling(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash._fetch_pending_orders = lambda _mode: [{"id": 101, "symbol": "SPY", "side": "sell", "quantity": 1, "status": "open"}]
    dash._cancel_orders = MagicMock(return_value=(0, 0))

    monkeypatch.setattr(
        g05,
        "build_pending_orders_gate_prompt",
        lambda **_kwargs: SimpleNamespace(
            prompt_title="prompt-title",
            prompt_text="prompt-text",
            declined_log_message="declined-log",
        ),
    )
    monkeypatch.setattr(
        g05.QMessageBox,
        "warning",
        lambda *_args: g05.QMessageBox.StandardButton.No,
    )

    assert dash._handle_pending_orders_gate(TradingMode.LIVE, "PAPER", "contact support") is False
    dash._cancel_orders.assert_not_called()
    assert dash._log_lines == ["declined-log"]
