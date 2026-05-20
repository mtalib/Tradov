#!/usr/bin/env python3
"""Focused tests for G05 regime-pill status plan wiring."""

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

    def setText(self, value: str) -> None:  # noqa: N802
        self._text = value

    def text(self) -> str:
        return self._text

    def setStyleSheet(self, _value: str) -> None:  # noqa: N802
        pass

    def setToolTip(self, _value: str) -> None:  # noqa: N802
        pass


class _Widget:
    def setStyleSheet(self, _value: str) -> None:  # noqa: N802
        pass


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
                "stance": "",
                "gate": "",
                "gate_key": "range_calm",
            },
            get_dispatch_state=lambda: {
                "state": "IDLE",
                "reason": "no signals in last 120s",
                "age_s": None,
            },
        )
    )
    return dash


def test_update_regime_pills_uses_status_plan_helper(monkeypatch, tmp_path: Path) -> None:
    dash = _build_dashboard_stub(tmp_path)

    monkeypatch.setattr(
        g05,
        "build_regime_pill_state_plan",
        lambda **_kwargs: SimpleNamespace(
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
    helper_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        g05,
        "build_regime_pill_status_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(stance="BULLISH", stress="LOW", gate="BULL TREND"),
    )
    monkeypatch.setattr(
        g05,
        "build_regime_pill_bar_presentation",
        lambda **kwargs: RegimePillBarPresentation(
            regime_pill=PillPresentation("regime", "", ""),
            stress_pill=PillPresentation(f"stress:{kwargs['stress']}", "", ""),
            stance_pill=PillPresentation(f"stance:{kwargs['stance']}", "", ""),
            gate_pill=PillPresentation(f"gate:{kwargs['gate']}", "", ""),
            dispatch_pill=PillPresentation("dispatch", "", ""),
            bar_stylesheet="",
        ),
    )

    dash.update_regime_pills({"SWAN": {"value": 1.2}, "DIX": {"value": 47.0}})

    assert helper_calls == [
        {
            "regime": "BULL",
            "swan": 1.2,
            "s07_live": True,
            "execution_truth": {
                "regime": "bear_high_vol",
                "stance": "",
                "gate": "",
                "gate_key": "range_calm",
            },
            "fallback_stress": None,
        }
    ]
    assert dash.stress_pill.text() == "stress:LOW"
    assert dash.stance_pill.text() == "stance:BULLISH"
    assert dash.gate_pill.text() == "gate:BULL TREND"
