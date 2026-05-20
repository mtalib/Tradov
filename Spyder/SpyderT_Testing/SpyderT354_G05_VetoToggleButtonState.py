#!/usr/bin/env python3
"""Focused tests for G05 veto toggle button presentation routing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


def _build_button_stub() -> SimpleNamespace:
    return SimpleNamespace(
        setChecked=MagicMock(),
        setText=MagicMock(),
        setStyleSheet=MagicMock(),
        setToolTip=MagicMock(),
    )


def test_apply_veto_toggle_button_state_uses_helper_presentation(monkeypatch) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.veto_toggle_btn = _build_button_stub()
    dash._veto_controls_enabled = True
    helper_calls: list[bool] = []

    monkeypatch.setattr(
        g05,
        "build_veto_toggle_button_presentation",
        lambda enabled: helper_calls.append(enabled)
        or SimpleNamespace(
            checked=True,
            text="enabled",
            style="green",
            tooltip="tip",
        ),
    )

    SpyderTradingDashboard._apply_veto_toggle_button_state(dash)

    assert helper_calls == [True]
    dash.veto_toggle_btn.setChecked.assert_called_once_with(True)
    dash.veto_toggle_btn.setText.assert_called_once_with("enabled")
    dash.veto_toggle_btn.setStyleSheet.assert_called_once_with("green")
    dash.veto_toggle_btn.setToolTip.assert_called_once_with("tip")


def test_apply_veto_toggle_button_state_skips_when_button_missing(monkeypatch) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash._veto_controls_enabled = False
    helper_calls: list[bool] = []

    monkeypatch.setattr(
        g05,
        "build_veto_toggle_button_presentation",
        lambda enabled: helper_calls.append(enabled),
    )

    SpyderTradingDashboard._apply_veto_toggle_button_state(dash)

    assert helper_calls == []
