#!/usr/bin/env python3
"""Focused regressions for shared Market Internals panel copy."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from Spyder.SpyderG_GUI.SpyderG06_DashboardData import get_market_overview_dialog_metadata
from Spyder.SpyderG_GUI.SpyderG17_MarketInternalsWidget import (
    _build_internal_panel_guidance,
    _build_internal_panel_tooltip,
    _get_internal_alert_copy,
    _get_internal_panel_metadata,
)


def test_internal_panel_metadata_uses_shared_overview_registry() -> None:
    tick_metadata = _get_internal_panel_metadata("TICK")
    shared_metadata = get_market_overview_dialog_metadata("$TICK")

    assert shared_metadata is not None
    assert tick_metadata == shared_metadata


def test_internal_panel_guidance_uses_shared_threshold_copy() -> None:
    assert _build_internal_panel_guidance("TICK", 700.0) == "Green: Above +600 signals broad buying pressure"
    assert _build_internal_panel_guidance("TICK", -700.0) == "Orange: Below -600 signals oversold breadth pressure"
    assert _build_internal_panel_guidance("TRIN", 1.6) == "Red: Above 1.50 signals bearish or defensive breadth pressure"
    assert _build_internal_panel_guidance("NYMO", 0.0) == "Yellow: Between -40 and +40 signals neutral breadth momentum"


def test_internal_panel_tooltip_includes_shared_metadata_copy() -> None:
    tooltip = _build_internal_panel_tooltip("ADD")

    assert "NYSE ADD - Advance/Decline Line" in tooltip
    assert "Advance-Decline Line - Net advancing issues" in tooltip
    assert "participation is broadening or narrowing" in tooltip
    assert "Green: Above +500 signals broad participation to the upside" in tooltip


def test_internal_panel_alert_copy_uses_shared_threshold_wording() -> None:
    tick_high = _get_internal_alert_copy("TICK", "high")
    trin_low = _get_internal_alert_copy("TRIN", "low")

    assert tick_high == {
        "label": "Broad buying pressure",
        "tooltip": "Green: Above +600 signals broad buying pressure",
    }
    assert trin_low == {
        "label": "Strong bullish participation",
        "tooltip": "Green: Below 0.70 signals strong bullish participation",
    }
