#!/usr/bin/env python3
"""Focused regressions for G17 stale breadth rendering."""

from __future__ import annotations

from collections import deque
from types import SimpleNamespace
from unittest.mock import MagicMock

from Spyder.SpyderG_GUI import SpyderG17_MarketInternalsWidget as g17


def test_internal_panel_set_stale_updates_labels_and_resets_state() -> None:
    panel = g17._InternalPanel.__new__(g17._InternalPanel)
    panel._value_lbl = SimpleNamespace(setText=MagicMock(), setStyleSheet=MagicMock())
    panel._status_lbl = SimpleNamespace(setText=MagicMock())
    panel._src_lbl = SimpleNamespace(setText=MagicMock())
    panel._history = deque([(object(), 1.0)])
    panel._plot_curve = None
    panel._alerted_high = True
    panel._alerted_low = True

    g17._InternalPanel.set_stale(panel, "stale S07 snapshot")

    panel._value_lbl.setText.assert_called_once_with("STALE")
    panel._status_lbl.setText.assert_called_once_with("Waiting for live breadth data")
    panel._src_lbl.setText.assert_called_once_with("source: stale S07 snapshot")
    assert len(panel._history) == 0
    assert panel._alerted_high is False
    assert panel._alerted_low is False


def test_market_internals_dialog_on_breadth_updated_marks_stale_state() -> None:
    dialog = g17.MarketInternalsDialog.__new__(g17.MarketInternalsDialog)
    dialog._panels = {
        sym: SimpleNamespace(set_stale=MagicMock())
        for sym in ("TICK", "ADD", "TRIN", "NYMO")
    }
    dialog._status_lbl = SimpleNamespace(setText=MagicMock())
    dialog._refresh_indicator = SimpleNamespace(setStyleSheet=MagicMock())

    g17.MarketInternalsDialog.on_breadth_updated(dialog, {"stale": True})

    for panel in dialog._panels.values():
        panel.set_stale.assert_called_once_with("stale S07 snapshot")
    dialog._status_lbl.setText.assert_called_once_with(
        "Breadth data stale — waiting for live update"
    )
    dialog._refresh_indicator.setStyleSheet.assert_called_once_with(
        f"color: {g17._YELLOW}; font-size: 14px;"
    )
