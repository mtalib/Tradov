#!/usr/bin/env python3
"""Focused regressions for D31 butterfly-family regime allowlists."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


def _make_orchestrator():
    mod = importlib.import_module("Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator")
    orch = mod.StrategyOrchestrator.__new__(mod.StrategyOrchestrator)
    policy_path = Path(__file__).resolve().parents[2] / "config" / "regime_policy.json"
    orch._regime_policy = json.loads(policy_path.read_text(encoding="utf-8"))
    return orch


@pytest.mark.parametrize(
    ("regime", "strategy_type"),
    [
        ("range_calm", "butterfly"),
        ("high_vol_mean_reversion", "iron_butterfly"),
        ("high_vol_mean_reversion", "broken_wing_butterfly"),
        ("recovery", "broken_wing_butterfly"),
    ],
)
def test_d31_regime_policy_allows_butterfly_family_strategy(regime: str, strategy_type: str) -> None:
    orch = _make_orchestrator()

    allowed, reason = orch._passes_regime_policy_gate(
        {"strategy_type": strategy_type},
        {"regime": regime},
    )

    assert allowed is True
    assert reason == ""


def test_d31_event_transition_remains_no_trade_for_butterfly_family() -> None:
    orch = _make_orchestrator()

    allowed, reason = orch._passes_regime_policy_gate(
        {"strategy_type": "broken_wing_butterfly"},
        {"regime": "event_transition"},
    )

    assert allowed is False
    assert reason == "regime_policy:no_trade:event_transition"
