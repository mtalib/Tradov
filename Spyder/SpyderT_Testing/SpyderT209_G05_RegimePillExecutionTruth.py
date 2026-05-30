#!/usr/bin/env python3
"""Focused regression for G05 stance/gate execution-truth rendering."""

from __future__ import annotations

import json
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
    def __init__(self, text: str = "") -> None:
        self._text = text
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
    return dash


def test_update_regime_pills_prefers_d31_execution_truth_for_stance_and_gate_when_dispatch_active(tmp_path: Path) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._session_supervisor = SimpleNamespace(
        orchestrator=SimpleNamespace(
            get_execution_pill_state=lambda: {
                "regime": "bear_high_vol",
                "stance": "CHOPPY",
                "gate": "CRISIS",
                "gate_key": "crisis_turbulent",
            },
            get_dispatch_state=lambda: {
                "state": "BLOCKED",
                "reason": "risk_gate:risk_state_cold",
                "age_s": None,
            },
        )
    )
    metrics = {
        "SWAN": {"value": 1.2},
        "DIX": {"value": 47.0},
        "SKEW": {"value": 120.0},
        "GEX": {"value": 1.0},
    }

    dash.update_regime_pills(metrics)

    assert "BULL" in dash.regime_pill.text()
    assert "CHOPPY" in dash.stance_pill.text()
    assert "CRISIS" in dash.gate_pill.text()
    assert "DISPATCH" in dash.dispatch_pill.text()
    assert "D31 execution regime=bear_high_vol" in dash.dispatch_pill.tooltip
    assert "D31 policy bucket=crisis_turbulent" in dash.dispatch_pill.tooltip


def test_update_regime_pills_falls_back_to_display_regime_when_dispatch_is_idle(tmp_path: Path) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.data_file.write_text(
        json.dumps(
            {
                "VIX": {"last": 15.94},
                "VIX9D": {"last": 13.16},
                "SPX": {"change_pct": 0.51},
            }
        ),
        encoding="utf-8",
    )
    dash._session_supervisor = SimpleNamespace(
        orchestrator=SimpleNamespace(
            get_execution_pill_state=lambda: {
                "regime": "sideways_low_vol",
                "stance": "CHOPPY",
                "gate": "RANGE CALM",
                "gate_key": "range_calm",
            },
            get_dispatch_state=lambda: {
                "state": "IDLE",
                "reason": "no signals in last 120s",
                "age_s": None,
            },
        )
    )
    metrics = {
        "SWAN": {"value": 1.6},
        "DIX": {"value": 41.75226108521811},
        "SKEW": {"value": 98.29},
        "GEX": {"value": 34.218123921256},
    }

    dash.update_regime_pills(metrics)

    assert "BULL" in dash.regime_pill.text()
    assert "BULLISH" in dash.stance_pill.text()
    assert "BULL TREND" in dash.gate_pill.text()
    assert "DISPATCH" in dash.dispatch_pill.text()


def test_update_regime_pills_uses_presenter_output(monkeypatch, tmp_path: Path) -> None:
    dash = _build_dashboard_stub(tmp_path)
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
    metrics = {
        "SWAN": {"value": 1.2},
        "DIX": {"value": 47.0},
        "SKEW": {"value": 120.0},
        "GEX": {"value": 1.0},
    }

    monkeypatch.setattr(
        g05,
        "build_regime_pill_bar_presentation",
        lambda **kwargs: RegimePillBarPresentation(
            regime_pill=PillPresentation("regime", "regime-style", "regime-tip"),
            stress_pill=PillPresentation("stress", "stress-style", "stress-tip"),
            stance_pill=PillPresentation("stance", "stance-style", "stance-tip"),
            gate_pill=PillPresentation("gate", "gate-style", "gate-tip"),
            dispatch_pill=PillPresentation("dispatch", "dispatch-style", "dispatch-tip"),
            bar_stylesheet="bar-style",
        ),
    )

    dash.update_regime_pills(metrics)

    assert dash.regime_pill.text() == "regime"
    assert dash.regime_pill.style == "regime-style"
    assert dash.regime_pill.tooltip == "regime-tip"
    assert dash.stress_pill.text() == "stress"
    assert dash.stance_pill.text() == "stance"
    assert dash.gate_pill.text() == "gate"
    assert dash.dispatch_pill.text() == "dispatch"
    assert dash.dispatch_pill.tooltip == "dispatch-tip"
    assert dash.regime_bar_widget.style == "bar-style"


def test_update_regime_pills_passes_butterfly_flag_to_presenter(monkeypatch, tmp_path: Path) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._session_supervisor = SimpleNamespace(
        orchestrator=SimpleNamespace(
            get_execution_pill_state=lambda: {
                "regime": "range_calm",
                "stance": "CHOPPY",
                "gate": "RANGE CALM",
                "gate_key": "range_calm",
            },
            get_dispatch_state=lambda: {
                "state": "IDLE",
                "reason": "no signals in last 120s",
                "age_s": None,
            },
        )
    )
    metrics = {
        "SWAN": {"value": 1.2},
        "DIX": {"value": 47.0},
        "SKEW": {"value": 120.0},
        "GEX": {"value": 1.0},
    }
    monkeypatch.setenv("SPYDER_ENABLE_BUTTERFLY", "true")

    presenter_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        g05,
        "build_regime_pill_bar_presentation",
        lambda **kwargs: presenter_calls.append(dict(kwargs))
        or RegimePillBarPresentation(
            regime_pill=PillPresentation("regime", "regime-style", "regime-tip"),
            stress_pill=PillPresentation("stress", "stress-style", "stress-tip"),
            stance_pill=PillPresentation("stance", "stance-style", "stance-tip"),
            gate_pill=PillPresentation("gate", "gate-style", "gate-tip"),
            dispatch_pill=PillPresentation("dispatch", "dispatch-style", "dispatch-tip"),
            bar_stylesheet="bar-style",
        ),
    )

    dash.update_regime_pills(metrics)

    assert presenter_calls[-1]["butterfly_enabled"] is True
