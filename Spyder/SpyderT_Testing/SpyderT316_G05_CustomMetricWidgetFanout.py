#!/usr/bin/env python3
"""Focused tests for G05 custom-metric widget fan-out wiring."""

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
    dash.symbol_widgets = {
        "GEX": SimpleNamespace(update_data=MagicMock(), set_unavailable=MagicMock())
    }
    dash._update_liquidity_diagnostics_panel = MagicMock()
    dash.current_dialog = None
    dash.signal_panel = None
    dash.update_regime_pills = MagicMock()
    dash.add_system_log = MagicMock()
    return dash


def test_on_custom_metrics_updated_uses_widget_update_helper(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "build_custom_metric_widget_update_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            payload={
                "last": 1.25,
                "change": 0.05,
                "change_pct": 4.0,
                "status": "live",
                "phase": "active",
            },
            next_previous_value=1.25,
        ),
    )

    SpyderTradingDashboard._on_custom_metrics_updated(dash, {"GEX": {"value": 1.25}})

    assert helper_calls == [
        {
            "entry": {"value": 1.25},
            "scale": SpyderTradingDashboard._S07_METRIC_ROUTING["GEX"][1],
            "previous_value": None,
        }
    ]
    dash.symbol_widgets["GEX"].update_data.assert_called_once_with(
        {
            "last": 1.25,
            "change": 0.05,
            "change_pct": 4.0,
            "status": "live",
            "phase": "active",
        }
    )
    assert dash._cm_prev_GEX == 1.25


def test_on_custom_metrics_updated_skips_widget_when_helper_rejects(monkeypatch) -> None:
    dash = _build_dashboard_stub()

    monkeypatch.setattr(
        g05,
        "build_custom_metric_widget_update_plan",
        lambda **_kwargs: None,
    )

    SpyderTradingDashboard._on_custom_metrics_updated(dash, {"GEX": {"value": float("nan")}})

    dash.symbol_widgets["GEX"].update_data.assert_not_called()
    assert not hasattr(dash, "_cm_prev_GEX")


def test_on_custom_metrics_updated_marks_stale_widget_unavailable(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper = MagicMock()

    monkeypatch.setattr(g05, "build_custom_metric_widget_update_plan", helper)

    SpyderTradingDashboard._on_custom_metrics_updated(
        dash,
        {"GEX": {"value": 1.25, "stale": True}},
    )

    helper.assert_not_called()
    dash.symbol_widgets["GEX"].set_unavailable.assert_called_once_with("STALE")
    dash.symbol_widgets["GEX"].update_data.assert_not_called()
