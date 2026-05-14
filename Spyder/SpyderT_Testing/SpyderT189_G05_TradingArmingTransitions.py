#!/usr/bin/env python3
"""Focused tests for G05 REAL/PAPER arming transitions."""

import os

from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import TradingMode
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


class _Button:
    def __init__(self) -> None:
        self.text = ""
        self.style = ""

    def setText(self, value: str) -> None:  # noqa: N802
        self.text = value

    def setStyleSheet(self, value: str) -> None:  # noqa: N802
        self.style = value


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.trading_active = False
    dash.trading_mode = TradingMode.PAPER
    dash._real_trading_armed = False
    dash._paper_trading_armed = True
    dash.live_btn = _Button()
    dash.paper_btn = _Button()
    dash.spyderbox_paper_status_btn = _Button()
    dash.spyderbox_paper_toggle_btn = _Button()
    dash._log_lines = []
    dash.add_system_log = lambda msg: dash._log_lines.append(str(msg))
    return dash


def test_real_arm_toggle_enables_real_and_disables_paper(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash.trading_mode = TradingMode.LIVE
    dash._confirm_live_trading = lambda **_kwargs: True
    monkeypatch.setenv("SPYDER_TRADING_MODE", "paper")

    dash._on_real_arm_toggle_clicked()

    assert dash._real_trading_armed is True
    assert dash._paper_trading_armed is False
    assert os.environ["SPYDER_TRADING_MODE"] == "live"
    assert dash.paper_btn.text == "DISABLE REAL"
    assert dash.spyderbox_paper_toggle_btn.text == "ENABLE PAPER"
    assert dash._log_lines[-1] == "REAL trading enabled — PAPER trading will be disabled"


def test_real_disarm_rearms_paper_and_restores_paper_runtime(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash.trading_mode = TradingMode.LIVE
    dash._real_trading_armed = True
    dash._paper_trading_armed = False
    monkeypatch.setenv("SPYDER_TRADING_MODE", "live")

    dash._on_real_arm_toggle_clicked()

    assert dash._real_trading_armed is False
    assert dash._paper_trading_armed is True
    assert os.environ["SPYDER_TRADING_MODE"] == "paper"
    assert dash.paper_btn.text == "ENABLE REAL"
    assert dash.spyderbox_paper_toggle_btn.text == "DISABLE PAPER"
    assert dash._log_lines[-1] == "REAL trading disabled — PAPER trading is enabled"


def test_paper_arm_toggle_switches_mode_and_clears_real(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash.trading_mode = TradingMode.LIVE
    dash._real_trading_armed = True
    dash._paper_trading_armed = False
    mode_requests: list[TradingMode] = []

    def _fake_mode_switch(new_mode: TradingMode) -> None:
        mode_requests.append(new_mode)
        dash.trading_mode = new_mode

    dash._on_mode_btn_clicked = _fake_mode_switch
    monkeypatch.setenv("SPYDER_TRADING_MODE", "live")

    dash._on_paper_arm_toggle_clicked()

    assert mode_requests == [TradingMode.PAPER]
    assert dash.trading_mode == TradingMode.PAPER
    assert dash._real_trading_armed is False
    assert dash._paper_trading_armed is True
    assert os.environ["SPYDER_TRADING_MODE"] == "paper"
    assert dash.spyderbox_paper_toggle_btn.text == "DISABLE PAPER"
    assert dash._log_lines[-1] == "PAPER trading enabled"
