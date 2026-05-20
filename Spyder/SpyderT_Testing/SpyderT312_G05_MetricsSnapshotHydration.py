#!/usr/bin/env python3
"""Focused tests for G05 metrics snapshot hydration wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash._on_custom_metrics_updated = MagicMock()
    dash._metrics_orchestrator = object()
    return dash


def test_hydrate_metrics_orchestrator_snapshot_uses_helper_result(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[object] = []
    formatted_payload = {"formatted": {"PCA-PROXY": 0.84}}

    monkeypatch.setattr(
        g05,
        "inspect_metrics_orchestrator_snapshot",
        lambda orchestrator: helper_calls.append(orchestrator)
        or SimpleNamespace(
            snapshot={"PCA-PROXY": 0.84},
            formatter=lambda snapshot: {"formatted": snapshot},
        ),
    )

    assert dash._hydrate_metrics_orchestrator_snapshot() is True
    assert helper_calls == [dash._metrics_orchestrator]
    dash._on_custom_metrics_updated.assert_called_once_with(formatted_payload)


def test_hydrate_metrics_orchestrator_snapshot_returns_false_when_helper_has_no_snapshot(
    monkeypatch,
) -> None:
    dash = _build_dashboard_stub()

    monkeypatch.setattr(
        g05,
        "inspect_metrics_orchestrator_snapshot",
        lambda _orchestrator: SimpleNamespace(snapshot=None, formatter=None),
    )

    assert dash._hydrate_metrics_orchestrator_snapshot() is False
    dash._on_custom_metrics_updated.assert_not_called()
