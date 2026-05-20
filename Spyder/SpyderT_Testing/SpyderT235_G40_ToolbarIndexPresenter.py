#!/usr/bin/env python3
"""Focused tests for toolbar index presentation helpers."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytz
from PySide6.QtWidgets import QApplication, QLabel

from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import COLORS
from Spyder.SpyderG_GUI.SpyderG40_ToolbarIndexPresenter import (
    ToolbarIndexPresentation,
    build_toolbar_index_presentations,
)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


_ET = pytz.timezone("US/Eastern")


def _epoch_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _build_toolbar_stub() -> SpyderTradingDashboard:
    QApplication.instance() or QApplication([])
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash._dji_from_dia_multiplier = 100.0
    dash.spx_value = QLabel("old")
    dash.spx_change = QLabel("old")
    dash.ndx_value = QLabel("old")
    dash.ndx_change = QLabel("old")
    dash.dji_value = QLabel("old")
    dash.dji_change = QLabel("old")
    dash.rut_value = QLabel("old")
    dash.rut_change = QLabel("old")
    return dash


def test_build_toolbar_index_presentations_uses_proxy_fallbacks_and_clears_stale_spx() -> None:
    now_et = _ET.localize(datetime(2026, 5, 15, 10, 5, 0))
    fetch_time = now_et
    stale_quote = fetch_time - timedelta(hours=1)
    fresh_quote = fetch_time - timedelta(minutes=2)

    presentations = build_toolbar_index_presentations(
        {
            "_fetch_time_ms": _epoch_ms(fetch_time),
            "SPX": {"last": 5800.0, "change": 12.0, "change_pct": 0.2, "timestamp_ms": _epoch_ms(stale_quote)},
            "NDX": {"last": 21000.0, "change": 55.0, "change_pct": 0.3, "timestamp_ms": _epoch_ms(fetch_time - timedelta(hours=2))},
            "QQQ": {"last": 560.0, "change": 2.0, "change_pct": 0.4, "timestamp_ms": _epoch_ms(fresh_quote)},
            "$DJI": {"last": 42000.0, "change": -30.0, "change_pct": -0.1, "timestamp_ms": _epoch_ms(fetch_time - timedelta(hours=2))},
            "DIA": {"last": 420.0, "change": -0.4, "change_pct": -0.1, "timestamp_ms": _epoch_ms(fresh_quote)},
            "IWM": {"last": 210.0, "change": 1.0, "change_pct": 0.5, "timestamp_ms": _epoch_ms(fresh_quote)},
        },
        now_et=now_et,
        market_hours_open=True,
        realtime_quote_max_age_seconds=15.0,
        dji_from_dia_multiplier=100.0,
        positive_color=COLORS["positive"],
        negative_color=COLORS["negative"],
    )

    assert presentations["spx"].value_text == ""
    assert presentations["spx"].change_text == ""
    assert presentations["ndx"].value_text == " 21,000"
    assert presentations["ndx"].change_text == "  +75  +0.4%"
    assert presentations["dji"].value_text == " 42,000"
    assert presentations["dji"].change_text == "  -40  -0.1%"
    assert presentations["dji"].change_color == COLORS["negative"]
    assert presentations["rut"].value_text == " 2,100"
    assert presentations["rut"].change_text == "  +10  +0.5%"


def test_build_toolbar_index_presentations_keeps_nonzero_direct_indices_off_hours() -> None:
    now_et = _ET.localize(datetime(2026, 5, 15, 18, 15, 0))
    stale_quote = now_et - timedelta(hours=6)

    presentations = build_toolbar_index_presentations(
        {
            "_fetch_time_ms": _epoch_ms(now_et),
            "SPX": {"last": 5800.0, "change": 12.0, "change_pct": 0.2, "timestamp_ms": _epoch_ms(stale_quote)},
            "RUT": {"last": 2100.0, "change": 0.0, "change_pct": 0.0, "timestamp_ms": _epoch_ms(stale_quote), "change_available": False},
        },
        now_et=now_et,
        market_hours_open=False,
        realtime_quote_max_age_seconds=15.0,
        dji_from_dia_multiplier=100.0,
        positive_color=COLORS["positive"],
        negative_color=COLORS["negative"],
    )

    assert presentations["spx"].value_text == " 5800"
    assert presentations["spx"].change_text == "  +12  +0.2%"
    assert presentations["rut"].value_text == " 2,100"
    assert presentations["rut"].change_text == "  --"
    assert presentations["rut"].change_color == "#888888"


def test_update_toolbar_with_real_data_applies_presenter_output() -> None:
    dash = _build_toolbar_stub()
    presenter_output = {
        "spx": ToolbarIndexPresentation(" 5800", "  +12  +0.2%", COLORS["positive"]),
        "ndx": ToolbarIndexPresentation(" 21,000", "  +75  +0.4%", COLORS["positive"]),
        "dji": ToolbarIndexPresentation("", "", "#888888"),
        "rut": ToolbarIndexPresentation(" 2,100", "  --", "#888888"),
    }

    with patch(
        "Spyder.SpyderG_GUI.SpyderG05_TradingDashboard.build_toolbar_index_presentations",
        return_value=presenter_output,
    ) as build_presentations:
        dash.update_toolbar_with_real_data({"SPX": {"last": 5800.0}})

    build_presentations.assert_called_once()
    assert dash.spx_value.text() == " 5800"
    assert dash.spx_change.text() == "  +12  +0.2%"
    assert dash.ndx_value.text() == " 21,000"
    assert dash.dji_value.text() == ""
    assert dash.dji_change.text() == ""
    assert dash.rut_change.text() == "  --"