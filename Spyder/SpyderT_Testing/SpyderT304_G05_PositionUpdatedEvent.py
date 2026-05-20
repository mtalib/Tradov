#!/usr/bin/env python3
"""Focused tests for G05 POSITION_UPDATED event wiring."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard, TradingMode
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.trading_mode = TradingMode.PAPER
    dash._refresh_positions_table = MagicMock()
    return dash


def test_g05_handle_position_updated_event_uses_helper_output(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_inputs: list[object] = []
    timer_calls: list[tuple[int, object]] = []

    monkeypatch.setattr(
        g05,
        "extract_position_update_symbol",
        lambda event: helper_inputs.append(event) or "SPY",
    )
    monkeypatch.setattr(
        g05,
        "QTimer",
        type("_FakeQTimer", (), {"singleShot": staticmethod(lambda ms, cb: (timer_calls.append((ms, cb)), cb()))}),
    )

    with patch(
        "Spyder.SpyderG_GUI.SpyderG05_TradingDashboard.QMetaObject.invokeMethod",
        side_effect=lambda obj, method_name, _conn: getattr(obj, method_name)(),
    ):
        dash._handle_position_updated_event({"raw": "event"})

    assert helper_inputs == [{"raw": "event"}]
    assert dash._refresh_positions_table.call_count == 2
    dash._refresh_positions_table.assert_called_with()
    assert timer_calls == [(150, dash._refresh_positions_table)]


def test_g05_handle_position_updated_event_skips_when_helper_rejects(monkeypatch) -> None:
    dash = _build_dashboard_stub()

    monkeypatch.setattr(g05, "extract_position_update_symbol", lambda _event: None)

    dash._handle_position_updated_event({"raw": "event"})

    dash._refresh_positions_table.assert_not_called()
