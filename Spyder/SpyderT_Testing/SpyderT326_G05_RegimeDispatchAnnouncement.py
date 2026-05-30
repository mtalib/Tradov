#!/usr/bin/env python3
"""Focused tests for G05 regime dispatch announcement wiring."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

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
    dash.log_autonomous_event = MagicMock()
    dash.add_system_log = MagicMock()
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


def test_update_regime_pills_uses_dispatch_announcement_helper(monkeypatch, tmp_path: Path) -> None:
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
    monkeypatch.setattr(
        g05,
        "build_regime_pill_status_plan",
        lambda **_kwargs: SimpleNamespace(stance="CHOPPY", stress="LOW", gate="CRISIS"),
    )
    helper_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        g05,
        "build_regime_dispatch_announcement_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            dispatch_state={"state": "BLOCKED", "reason": "entry_gate", "age_s": None},
            dispatch_label="BLOCKED",
            dispatch_state_key="BLOCKED|entry_gate",
            should_announce=True,
            autonomous_message="D31 DISPATCH -> BLOCKED (entry_gate)",
            system_log_message="⚠️ D31 DISPATCH -> BLOCKED (entry_gate)",
        ),
    )
    monkeypatch.setattr(g05, "is_market_hours", lambda *_: True)
    monkeypatch.setattr(
        g05,
        "build_regime_pill_bar_presentation",
        lambda **kwargs: RegimePillBarPresentation(
            regime_pill=PillPresentation("regime", "", ""),
            stress_pill=PillPresentation("stress", "", ""),
            stance_pill=PillPresentation("stance", "", ""),
            gate_pill=PillPresentation("gate", "", ""),
            dispatch_pill=PillPresentation(f"dispatch:{kwargs['dispatch_label']}", "", ""),
            bar_stylesheet="",
        ),
    )

    dash.update_regime_pills({"SWAN": {"value": 1.2}, "DIX": {"value": 47.0}})

    assert helper_calls == [
        {
            "regime": "BULL",
            "raw_dispatch_state": {
                "state": "IDLE",
                "reason": "no signals in last 120s",
                "age_s": None,
            },
            "last_dispatch_state_key": "",
        }
    ]
    assert dash._last_dispatch_state_key == "BLOCKED|entry_gate"
    dash.log_autonomous_event.assert_called_once_with(
        "D31 DISPATCH -> BLOCKED (entry_gate)",
        event_type="AGENT_OBSERVATION",
        source="D31",
    )
    dash.add_system_log.assert_called_once_with("⚠️ D31 DISPATCH -> BLOCKED (entry_gate)")
    assert dash.dispatch_pill.text() == "dispatch:BLOCKED"


def test_update_regime_pills_does_not_reannounce_idle_when_session_supervisor_attaches(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._session_supervisor = None
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
    monkeypatch.setattr(
        g05,
        "build_regime_pill_status_plan",
        lambda **_kwargs: SimpleNamespace(stance="BULLISH", stress="LOW", gate="BULL TREND"),
    )
    monkeypatch.setattr(g05, "is_market_hours", lambda *_: True)
    monkeypatch.setattr(
        g05,
        "build_regime_pill_bar_presentation",
        lambda **kwargs: RegimePillBarPresentation(
            regime_pill=PillPresentation("regime", "", ""),
            stress_pill=PillPresentation("stress", "", ""),
            stance_pill=PillPresentation("stance", "", ""),
            gate_pill=PillPresentation("gate", "", ""),
            dispatch_pill=PillPresentation(f"dispatch:{kwargs['dispatch_label']}", "", ""),
            bar_stylesheet="",
        ),
    )

    dash.update_regime_pills({"SWAN": {"value": 1.2}, "DIX": {"value": 47.0}})

    dash._session_supervisor = SimpleNamespace(
        orchestrator=SimpleNamespace(
            get_execution_pill_state=lambda: {
                "regime": "bull_low_vol",
                "stance": "BULLISH",
                "gate": "BULL TREND",
                "gate_key": "bull_trend",
            },
            get_dispatch_state=lambda: {
                "state": "IDLE",
                "reason": "no signals in last 120s",
                "age_s": None,
            },
        )
    )

    dash.update_regime_pills({"SWAN": {"value": 1.2}, "DIX": {"value": 47.0}})

    dash.log_autonomous_event.assert_called_once_with(
        "D31 DISPATCH -> IDLE (no signals in last 120s)",
        event_type="AGENT_OBSERVATION",
        source="D31",
    )
    dash.add_system_log.assert_not_called()
    assert dash._last_dispatch_state_key == "IDLE|no signals in last 120s"
    assert dash.dispatch_pill.text() == "dispatch:IDLE"
