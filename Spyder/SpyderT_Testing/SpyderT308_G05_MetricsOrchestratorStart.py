#!/usr/bin/env python3
"""Focused tests for G05 metrics orchestrator startup wiring."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

from Spyder.SpyderG_GUI import SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SimpleNamespace(error=lambda *_args, **_kwargs: None)
    dash._log_lines = []
    dash.add_system_log = lambda message: dash._log_lines.append(str(message))
    dash._on_custom_metrics_updated = lambda *_args, **_kwargs: None
    dash._on_market_stress_changed = lambda *_args, **_kwargs: None
    dash._custom_metrics_live_announced = False
    return dash


def test_start_metrics_orchestrator_uses_helper_plan(monkeypatch) -> None:
    dash = _build_dashboard_stub()

    class _Signal:
        def connect(self, _callback) -> None:
            return None

    orchestrator = SimpleNamespace(
        metrics_updated=_Signal(),
        stress_level_changed=_Signal(),
    )
    fake_s07_module = types.ModuleType(
        "SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator"
    )
    fake_s07_module.get_metrics_orchestrator = lambda: orchestrator
    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "build_metrics_orchestrator_start_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            live_announced_after_start=False,
            log_messages=("custom wait log",),
        ),
    )
    monkeypatch.setattr(
        SpyderTradingDashboard,
        "_hydrate_metrics_orchestrator_snapshot",
        lambda self: False,
    )

    with monkeypatch.context() as context:
        context.setitem(
            sys.modules,
            "SpyderS_Signals",
            sys.modules.get("SpyderS_Signals", types.ModuleType("SpyderS_Signals")),
        )
        context.setitem(
            sys.modules,
            "SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator",
            fake_s07_module,
        )
        dash._start_metrics_orchestrator()

    assert dash._metrics_orchestrator is orchestrator
    assert helper_calls == [{"hydrated_snapshot": False}]
    assert dash._custom_metrics_live_announced is False
    assert dash._log_lines == ["custom wait log"]
