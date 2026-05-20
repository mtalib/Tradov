#!/usr/bin/env python3
"""Focused tests for G51 mode title presenter helpers."""

from Spyder.SpyderG_GUI.SpyderG51_ModeTitlePresenter import (
    build_orders_title_presentation,
    build_pnl_title_presentation,
)


def test_build_pnl_title_presentation_for_paper_mode() -> None:
    presentation = build_pnl_title_presentation(is_paper=True)

    assert presentation.text == "P&L PERFORMANCE - PAPER TRADING"
    assert presentation.style == "font-weight: normal; color: #FFA500;"


def test_build_orders_title_presentation_for_live_mode() -> None:
    presentation = build_orders_title_presentation(is_paper=False)

    assert presentation.text == "ORDERS & POSITIONS - LIVE TRADING"
    assert presentation.style == "font-weight: normal; color: #00FF00;"
