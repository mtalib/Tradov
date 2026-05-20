#!/usr/bin/env python3
"""Focused tests for G48 REAL/PAPER arming presenter helpers."""

from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import COLORS
from Spyder.SpyderG_GUI.SpyderG48_TradingArmingPresenter import (
    build_trading_arming_presentation,
)


def test_build_trading_arming_presentation_when_real_is_armed() -> None:
    presentation = build_trading_arming_presentation(
        real_armed=True,
        paper_armed=False,
        colors=COLORS,
    )

    assert presentation.real_status.text == "LIVE TRADING"
    assert COLORS["positive"] in presentation.real_status.style
    assert presentation.real_toggle.text == "DISABLE REAL"
    assert "#5a5a5a" in presentation.real_toggle.style
    assert presentation.paper_status.text == "PAPER TRADING"
    assert COLORS["panel"] in presentation.paper_status.style
    assert presentation.paper_toggle.text == "ENABLE PAPER"
    assert COLORS["blue"] in presentation.paper_toggle.style


def test_build_trading_arming_presentation_when_paper_is_armed() -> None:
    presentation = build_trading_arming_presentation(
        real_armed=False,
        paper_armed=True,
        colors=COLORS,
    )

    assert presentation.real_status.text == "LIVE TRADING"
    assert COLORS["panel"] in presentation.real_status.style
    assert presentation.real_toggle.text == "ENABLE REAL"
    assert COLORS["blue"] in presentation.real_toggle.style
    assert presentation.paper_status.text == "PAPER TRADING"
    assert COLORS["orange"] in presentation.paper_status.style
    assert presentation.paper_toggle.text == "DISABLE PAPER"
    assert "#5a5a5a" in presentation.paper_toggle.style