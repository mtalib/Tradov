#!/usr/bin/env python3
"""Focused tests for G05 signal-panel sync wiring from custom metrics."""

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
    dash.current_dialog = None
    dash.signal_panel = SimpleNamespace(
        update_regime=MagicMock(),
        update_live_data=MagicMock(),
    )
    dash.update_regime_pills = MagicMock()
    dash.add_system_log = MagicMock()
    dash._regime_value = "RISK OFF"
    return dash


def test_on_custom_metrics_updated_uses_signal_panel_sync_helper(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "build_custom_metric_signal_panel_sync_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            regime_value="RISK OFF",
            swan=2.1,
            dix=43.0,
            skew=121.0,
            gex=1.25,
            live_data={"GEX": 1.25, "SWAN": 2.1},
        ),
    )

    SpyderTradingDashboard._on_custom_metrics_updated(dash, {"GEX": {"value": 1.25}})

    assert helper_calls == [
        {
            "metrics": {"GEX": {"value": 1.25}},
            "metric_routing": SpyderTradingDashboard._S07_METRIC_ROUTING,
            "regime_value": "RISK OFF",
        }
    ]
    dash.signal_panel.update_regime.assert_called_once_with("RISK OFF", 2.1, 43.0, 121.0, 1.25)
    dash.signal_panel.update_live_data.assert_called_once_with({"GEX": 1.25, "SWAN": 2.1})


def test_on_custom_metrics_updated_skips_signal_panel_live_sync_when_helper_has_no_data(
    monkeypatch,
) -> None:
    dash = _build_dashboard_stub()

    monkeypatch.setattr(
        g05,
        "build_custom_metric_signal_panel_sync_plan",
        lambda **_kwargs: SimpleNamespace(
            regime_value="NEUTRAL",
            swan=1.9,
            dix=42.0,
            skew=120.0,
            gex=0.0,
            live_data={},
        ),
    )

    SpyderTradingDashboard._on_custom_metrics_updated(dash, {})

    dash.signal_panel.update_regime.assert_called_once_with("NEUTRAL", 1.9, 42.0, 120.0, 0.0)
    dash.signal_panel.update_live_data.assert_not_called()