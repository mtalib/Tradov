#!/usr/bin/env python3
"""Focused tests for G05 veto toggle outcome routing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


def _build_dashboard_stub(initial_enabled: bool) -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash._veto_controls_enabled = initial_enabled
    dash._persist_veto_controls_state = MagicMock()
    dash._apply_veto_toggle_button_state = MagicMock()
    dash.add_system_log = MagicMock()
    return dash


def test_toggle_veto_controls_uses_helper_and_updates_state_on_success(monkeypatch) -> None:
    dash = _build_dashboard_stub(initial_enabled=False)
    dash._persist_veto_controls_state.return_value = (True, "/tmp/profile.json")
    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "build_veto_toggle_result_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            should_update_enabled_state=True,
            system_log_messages=("saved", "restart"),
        ),
    )

    SpyderTradingDashboard._toggle_veto_controls(dash)

    dash._persist_veto_controls_state.assert_called_once_with(True)
    assert helper_calls == [{"success": True, "next_state": True, "detail": "/tmp/profile.json"}]
    assert dash._veto_controls_enabled is True
    dash._apply_veto_toggle_button_state.assert_called_once_with()
    assert dash.add_system_log.call_args_list == [(("saved",), {}), (("restart",), {})]


def test_toggle_veto_controls_uses_helper_failure_plan_without_updating_state(monkeypatch) -> None:
    dash = _build_dashboard_stub(initial_enabled=True)
    dash._persist_veto_controls_state.return_value = (False, "write failed")

    monkeypatch.setattr(
        g05,
        "build_veto_toggle_result_plan",
        lambda **_kwargs: SimpleNamespace(
            should_update_enabled_state=False,
            system_log_messages=("failed",),
        ),
    )

    SpyderTradingDashboard._toggle_veto_controls(dash)

    dash._persist_veto_controls_state.assert_called_once_with(False)
    assert dash._veto_controls_enabled is True
    dash._apply_veto_toggle_button_state.assert_called_once_with()
    dash.add_system_log.assert_called_once_with("failed")
