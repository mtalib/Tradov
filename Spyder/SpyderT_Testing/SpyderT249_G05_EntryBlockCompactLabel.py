#!/usr/bin/env python3
"""Focused tests for G05 compact entry-block label delegation."""

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG50_EntryBlockCompactPresenter import (
    EntryBlockCompactPresentation,
)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


class _Label:
    def __init__(self) -> None:
        self.text = ""
        self.tooltip = ""
        self.style = ""

    def setText(self, value: str) -> None:  # noqa: N802
        self.text = value

    def setToolTip(self, value: str) -> None:  # noqa: N802
        self.tooltip = value

    def setStyleSheet(self, value: str) -> None:  # noqa: N802
        self.style = value


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.entry_block_compact_label = _Label()
    return dash


def test_g05_update_entry_block_compact_label_uses_presenter_output(monkeypatch) -> None:
    dash = _build_dashboard_stub()

    monkeypatch.setattr(
        g05,
        "build_entry_block_compact_presentation",
        lambda text: EntryBlockCompactPresentation(
            text="label",
            tooltip="tooltip",
            style="style",
        ),
    )

    dash._update_entry_block_compact_label("BLOCK: anything")

    assert dash.entry_block_compact_label.text == "label"
    assert dash.entry_block_compact_label.tooltip == "tooltip"
    assert dash.entry_block_compact_label.style == "style"


def test_g05_update_entry_block_compact_label_skips_when_label_missing() -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.entry_block_compact_label = None

    dash._update_entry_block_compact_label("BLOCK: anything")