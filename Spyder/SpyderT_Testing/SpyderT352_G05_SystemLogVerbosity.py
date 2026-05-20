#!/usr/bin/env python3
"""Focused tests for G05 system-log verbosity routing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


class _Button:
    def __init__(self):
        self.checked = None

    def setChecked(self, value: bool) -> None:  # noqa: N802
        self.checked = value


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash._signal_noise_loggers = ["a", "b"]
    dash.system_log_normal_btn = _Button()
    dash.system_log_debug_btn = _Button()
    dash.add_system_log = MagicMock()
    return dash


def test_set_system_log_verbosity_uses_helper_plan(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[dict[str, object]] = []
    logger_a = MagicMock()
    logger_b = MagicMock()
    loggers = {"a": logger_a, "b": logger_b}

    monkeypatch.setattr(
        g05,
        "build_system_log_verbosity_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            selected_mode="DEBUG",
            logger_level=10,
            normal_button_checked=False,
            debug_button_checked=True,
            announcement_message="ℹ️ System log mode → DEBUG",
        ),
    )
    monkeypatch.setattr(
        g05.logging,
        "getLogger",
        lambda name=None: MagicMock() if name is None else loggers[name],
    )

    SpyderTradingDashboard._set_system_log_verbosity(dash, "debug", announce=True)

    assert helper_calls == [
        {
            "mode": "debug",
            "announce": True,
            "debug_level": g05.logging.DEBUG,
            "normal_level": g05.logging.ERROR,
        }
    ]
    assert dash.system_log_mode == "DEBUG"
    logger_a.setLevel.assert_called_once_with(10)
    logger_b.setLevel.assert_called_once_with(10)
    assert dash.system_log_normal_btn.checked is False
    assert dash.system_log_debug_btn.checked is True
    dash.add_system_log.assert_called_once_with("ℹ️ System log mode → DEBUG")


def test_set_system_log_verbosity_skips_announcement_when_helper_omits_copy(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    monkeypatch.setattr(
        g05,
        "build_system_log_verbosity_plan",
        lambda **_kwargs: SimpleNamespace(
            selected_mode="NORMAL",
            logger_level=40,
            normal_button_checked=True,
            debug_button_checked=False,
            announcement_message=None,
        ),
    )
    monkeypatch.setattr(g05.logging, "getLogger", lambda _name=None: MagicMock())

    SpyderTradingDashboard._set_system_log_verbosity(dash, "normal", announce=False)

    assert dash.system_log_mode == "NORMAL"
    assert dash.system_log_normal_btn.checked is True
    assert dash.system_log_debug_btn.checked is False
    dash.add_system_log.assert_not_called()
