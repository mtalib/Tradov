#!/usr/bin/env python3
"""Focused tests for G05 Market Internals dialog sync from custom metrics."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SimpleNamespace(debug=lambda *_args, **_kwargs: None)
    dash._last_custom_metrics_payload = {}
    dash._custom_metrics_live_announced = True
    dash._merge_metrics_payload = lambda current, incoming: {**current, **incoming}
    dash._persist_custom_metrics_snapshot = MagicMock()
    dash.symbol_widgets = {}
    dash._update_liquidity_diagnostics_panel = MagicMock()
    dash.current_dialog = SimpleNamespace(on_breadth_updated=MagicMock())
    dash.signal_panel = None
    dash.update_regime_pills = MagicMock()
    dash.add_system_log = MagicMock()
    return dash


def test_on_custom_metrics_updated_uses_breadth_dialog_helper(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "build_custom_metric_breadth_dialog_payload",
        lambda metrics: helper_calls.append(dict(metrics))
        or {
            "tick": 1200.0,
            "add": 250.0,
            "trin": 0.86,
            "nymo": -12.0,
            "breadth_regime": "risk_on",
        },
    )

    SpyderTradingDashboard._on_custom_metrics_updated(dash, {"TICK": {"value": 1200.0}})

    assert helper_calls == [{"TICK": {"value": 1200.0}}]
    dash.current_dialog.on_breadth_updated.assert_called_once_with(
        {
            "tick": 1200.0,
            "add": 250.0,
            "trin": 0.86,
            "nymo": -12.0,
            "breadth_regime": "risk_on",
        }
    )


def test_on_custom_metrics_updated_skips_breadth_dialog_when_helper_rejects(monkeypatch) -> None:
    dash = _build_dashboard_stub()

    monkeypatch.setattr(
        g05,
        "build_custom_metric_breadth_dialog_payload",
        lambda _metrics: None,
    )

    SpyderTradingDashboard._on_custom_metrics_updated(dash, {"TICK": {"value": float("nan")}})

    dash.current_dialog.on_breadth_updated.assert_not_called()
