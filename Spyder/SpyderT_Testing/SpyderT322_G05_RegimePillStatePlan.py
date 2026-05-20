#!/usr/bin/env python3
"""Focused tests for G05 regime-pill state plan wiring."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG52_RegimePillBarPresenter import (
    PillPresentation,
    RegimePillBarPresentation,
)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


class _Label:
    def __init__(self) -> None:
        self._text = ""
        self.style = ""
        self.tooltip = ""

    def setText(self, value: str) -> None:  # noqa: N802
        self._text = value

    def text(self) -> str:
        return self._text

    def setStyleSheet(self, value: str) -> None:  # noqa: N802
        self.style = value

    def setToolTip(self, value: str) -> None:  # noqa: N802
        self.tooltip = value


class _Widget:
    def __init__(self) -> None:
        self.style = ""

    def setStyleSheet(self, value: str) -> None:  # noqa: N802
        self.style = value


def _build_dashboard_stub(tmp_path: Path) -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.data_file = tmp_path / "live_data.json"
    dash.regime_pill = _Label()
    dash.stress_pill = _Label()
    dash.stance_pill = _Label()
    dash.gate_pill = _Label()
    dash.dispatch_pill = _Label()
    dash.regime_bar_widget = _Widget()
    dash._metrics_orchestrator = None
    dash._last_dispatch_state_key = ""
    dash.log_autonomous_event = lambda *args, **kwargs: None
    dash.add_system_log = lambda *args, **kwargs: None
    dash._session_supervisor = SimpleNamespace(
        orchestrator=SimpleNamespace(
            get_execution_pill_state=lambda: {
                "regime": "bear_high_vol",
                "stance": "CHOPPY",
                "gate": "CRISIS",
                "gate_key": "crisis_turbulent",
            },
            get_dispatch_state=lambda: {
                "state": "IDLE",
                "reason": "no signals in last 120s",
                "age_s": None,
            },
        )
    )
    return dash


def test_update_regime_pills_uses_state_plan_helper(monkeypatch, tmp_path: Path) -> None:
    dash = _build_dashboard_stub(tmp_path)
    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "build_regime_pill_state_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            swan=1.2,
            dix=47.0,
            skew=120.0,
            gex=1.0,
            s07_live=True,
            regime="BULL",
            next_regime_sticky="BULL",
            next_vix_candidate_regime="RANGE",
            next_vix_candidate_count=1,
        ),
    )
    monkeypatch.setattr(
        g05,
        "build_regime_pill_bar_presentation",
        lambda **kwargs: RegimePillBarPresentation(
            regime_pill=PillPresentation(f"REGIME:{kwargs['regime']}", "regime-style", "regime-tip"),
            stress_pill=PillPresentation("stress", "stress-style", "stress-tip"),
            stance_pill=PillPresentation("stance", "stance-style", "stance-tip"),
            gate_pill=PillPresentation("gate", "gate-style", "gate-tip"),
            dispatch_pill=PillPresentation("dispatch", "dispatch-style", "dispatch-tip"),
            bar_stylesheet="bar-style",
        ),
    )

    metrics = {
        "SWAN": {"value": 1.2},
        "DIX": {"value": 47.0},
    }
    dash.update_regime_pills(metrics)

    assert helper_calls == [
        {
            "metrics": metrics,
            "regime_sticky": None,
            "vix_candidate_regime": "RANGE",
            "vix_candidate_count": 0,
            "vix_snapshot": None,
        }
    ]
    assert dash._regime_sticky == "BULL"
    assert dash._vix_candidate_regime == "RANGE"
    assert dash._vix_candidate_count == 1
    assert dash.regime_pill.text() == "REGIME:BULL"
