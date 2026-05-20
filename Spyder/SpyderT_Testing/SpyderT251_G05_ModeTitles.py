#!/usr/bin/env python3
"""Focused tests for G05 mode title delegation."""

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard, TradingMode
from Spyder.SpyderG_GUI.SpyderG51_ModeTitlePresenter import ModeTitlePresentation
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


class _Font:
    def __init__(self) -> None:
        self.bold = True

    def setBold(self, value: bool) -> None:  # noqa: N802
        self.bold = value


class _FontMetrics:
    def horizontalAdvance(self, text: str) -> int:  # noqa: N802
        return len(text) * 7


class _Label:
    def __init__(self) -> None:
        self.text = ""
        self.style = ""
        self.font = None
        self.minimum_width = None

    def setText(self, value: str) -> None:  # noqa: N802
        self.text = value

    def setStyleSheet(self, value: str) -> None:  # noqa: N802
        self.style = value

    def setFont(self, value) -> None:  # noqa: N802
        self.font = value

    def fontMetrics(self) -> _FontMetrics:  # noqa: N802
        return _FontMetrics()

    def setMinimumWidth(self, value: int) -> None:  # noqa: N802
        self.minimum_width = value


class _Group:
    def __init__(self) -> None:
        self._font = _Font()

    def font(self) -> _Font:
        return self._font


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.trading_mode = TradingMode.PAPER
    dash.system_log_group = _Group()
    dash.pnl_title_lbl = _Label()
    dash.orders_title_label = _Label()
    return dash


def test_g05_update_pnl_title_uses_presenter_output(monkeypatch) -> None:
    dash = _build_dashboard_stub()

    monkeypatch.setattr(
        g05,
        "build_pnl_title_presentation",
        lambda *, is_paper: ModeTitlePresentation(
            text="pnl-title",
            style="pnl-style",
        ),
    )

    dash._update_pnl_title()

    assert dash.pnl_title_lbl.text == "pnl-title"
    assert dash.pnl_title_lbl.style == "pnl-style"
    assert dash.pnl_title_lbl.font is dash.system_log_group.font()
    assert dash.pnl_title_lbl.font.bold is False


def test_g05_update_orders_title_uses_presenter_output_and_width(monkeypatch) -> None:
    dash = _build_dashboard_stub()

    monkeypatch.setattr(
        g05,
        "build_orders_title_presentation",
        lambda *, is_paper: ModeTitlePresentation(
            text="orders-title",
            style="orders-style",
        ),
    )

    dash._update_orders_title()

    assert dash.orders_title_label.text == "orders-title"
    assert dash.orders_title_label.style == "orders-style"
    assert dash.orders_title_label.font is dash.system_log_group.font()
    assert dash.orders_title_label.font.bold is False
    assert dash.orders_title_label.minimum_width == len("orders-title") * 7 + 18