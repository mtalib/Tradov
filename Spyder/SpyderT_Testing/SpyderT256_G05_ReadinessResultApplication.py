#!/usr/bin/env python3
"""Focused tests for G05 readiness result application."""

from __future__ import annotations

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG54_ReadinessResultPresenter import (
    ReadinessResultLogPresentation,
)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.logged_messages: list[str] = []
    dash.display_updates: list[dict[str, object]] = []
    dash.add_system_log = lambda message: dash.logged_messages.append(str(message))
    dash._update_readiness_status_display = lambda result: dash.display_updates.append(result)
    dash._export_readiness_report = lambda result: "/tmp/readiness-report.json"
    dash._last_readiness_result = None
    dash._last_readiness_ts = None
    return dash


def test_g05_apply_readiness_result_uses_presenter_output(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    result = {"decision": "NO", "reasons": ["tradier disconnected"]}

    monkeypatch.setattr(
        g05,
        "build_readiness_result_log_presentation",
        lambda incoming: ReadinessResultLogPresentation(
            detail_lines=("detail-1", "detail-2"),
            summary_line="summary-line",
        ),
    )

    returned = dash._apply_readiness_result(result)

    assert returned is result
    assert dash._last_readiness_result is result
    assert dash._last_readiness_ts is not None
    assert dash.display_updates == [result]
    assert dash.logged_messages == [
        "detail-1",
        "detail-2",
        "summary-line",
        "Trading readiness report saved: /tmp/readiness-report.json",
    ]