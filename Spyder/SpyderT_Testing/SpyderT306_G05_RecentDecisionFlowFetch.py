#!/usr/bin/env python3
"""Focused tests for G05 recent decision-flow fetch wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard, TradingMode
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.trading_mode = TradingMode.PAPER
    dash._decision_flow_recent_limit = 2
    return dash


def test_g05_get_recent_decision_flow_for_panel_uses_helper_plan(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash.trading_mode = TradingMode.LIVE
    helper_calls: list[dict[str, object]] = []
    diagnostics_calls: list[dict[str, object]] = []
    expected_result = {"dispatch": ["ok"], "drops": [], "decision_log": "path"}
    dash._decision_flow_diagnostics = SimpleNamespace(
        collect_recent_decision_flow=lambda **kwargs: diagnostics_calls.append(dict(kwargs)) or expected_result,
    )

    monkeypatch.setattr(
        g05,
        "build_recent_decision_flow_fetch_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            run_mode="live",
            limit=7,
            fallback_result={"limit": 7, "dispatch": [], "drops": [], "decision_log": None},
        ),
    )

    assert dash._get_recent_decision_flow_for_panel() is expected_result
    assert helper_calls == [{"live_mode": True, "limit": 2}]
    assert diagnostics_calls == [{"run_mode": "live", "limit": 7}]


def test_g05_get_recent_decision_flow_for_panel_returns_helper_fallback(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[dict[str, object]] = []
    fallback_result = {"limit": 3, "dispatch": [], "drops": [], "decision_log": None}

    def _raise_fetch(**_kwargs):
        raise RuntimeError("boom")

    dash._decision_flow_diagnostics = SimpleNamespace(collect_recent_decision_flow=_raise_fetch)
    dash.logger.debug = MagicMock()

    monkeypatch.setattr(
        g05,
        "build_recent_decision_flow_fetch_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            run_mode="paper",
            limit=3,
            fallback_result=fallback_result,
        ),
    )

    assert dash._get_recent_decision_flow_for_panel() == fallback_result
    assert helper_calls == [{"live_mode": False, "limit": 2}]
    dash.logger.debug.assert_called_once()
