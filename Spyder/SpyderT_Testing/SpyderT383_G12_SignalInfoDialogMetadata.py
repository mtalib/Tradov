#!/usr/bin/env python3
"""Focused regressions for shared SignalInfoDialog metadata."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from Spyder.SpyderG_GUI.SpyderG06_DashboardData import (
    SYMBOL_DESCRIPTIONS,
    get_market_signal_dialog_metadata,
)
from Spyder.SpyderG_GUI.SpyderG12_SignalInfoDialog import SignalInfoDialog


def _build_dialog(signal_type: str, live_data: dict | None = None) -> SignalInfoDialog:
    QApplication.instance() or QApplication([])
    return SignalInfoDialog(signal_type, live_data=live_data or {})


def test_shared_market_metric_dialog_metadata_matches_dashboard_registry() -> None:
    signal_to_symbol = {
        "VIX MONITOR": "VIX",
        "GEX": "GEX",
        "DIX": "DIX",
        "OGL": "OGL",
        "DEX": "DEX",
        "BLACK SWAN": "SWAN",
        "SKEW": "SKEW",
    }

    for signal_type, symbol in signal_to_symbol.items():
        dialog = _build_dialog(signal_type)
        content = dialog.get_signal_content()
        shared = get_market_signal_dialog_metadata(symbol)

        assert shared is not None
        assert content["full_name"] == shared["full_name"]
        assert content["description"] == SYMBOL_DESCRIPTIONS[symbol]
        assert content["concept"] == shared["concept"]
        assert content["signal_colors"] == shared["signal_colors"]
        dialog.close()


def test_specialized_signal_descriptions_remain_local() -> None:
    dialog = _build_dialog("AI DECISION")
    content = dialog.get_signal_content()

    assert content["description"] == "Machine Learning-based trade signal generator"
    dialog.close()


def test_shared_signal_current_status_still_uses_live_payload() -> None:
    dialog = _build_dialog("GEX", live_data={"GEX": 1_500_000_000.0})
    content = dialog.get_signal_content()

    assert "+1.50B" in content["current_status"]
    assert "Positive Gamma" in content["current_status"]
    dialog.close()
