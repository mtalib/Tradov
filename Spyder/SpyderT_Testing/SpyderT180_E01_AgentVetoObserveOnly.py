#!/usr/bin/env python3
"""Tests for E01 observe-only handling of Y03 agent veto state."""

from __future__ import annotations

from threading import RLock
from types import SimpleNamespace

from Spyder.SpyderE_Risk.SpyderE00_RiskProtocol import (
    BoundarySignalType,
    RiskValidationRequest,
)
from Spyder.SpyderE_Risk.SpyderE01_RiskManager import RiskManager


def _make_minimal_manager(observe_only_agents: bool) -> RiskManager:
    manager = RiskManager.__new__(RiskManager)
    manager._risk_lock = RLock()
    manager._positions = {"SPY": object()}
    manager._account_state_synced = True
    manager._data_stale = False
    manager._y03_veto_state = "halt"
    manager._observe_only_agents = observe_only_agents
    manager._enforce_decision_quality_slo = False
    manager.logger = SimpleNamespace(warning=lambda *args, **kwargs: None)
    return manager


def _make_naked_put_request() -> RiskValidationRequest:
    return RiskValidationRequest(
        symbol="SPY",
        quantity=1,
        signal_type=BoundarySignalType.BUY,
        strategy_id="unit_test",
        entry_price=2.0,
        confidence=0.8,
        metadata={"strategy_type": "naked_put"},
    )


def test_validate_signal_observe_only_agents_does_not_hard_block_veto() -> None:
    manager = _make_minimal_manager(observe_only_agents=True)

    result = manager.validate_signal(_make_naked_put_request())

    assert result.approved is False
    assert "AGENT_VETO" not in result.violations
    assert "NAKED_PUT_PROHIBITED" in result.violations


def test_validate_signal_blocking_mode_rejects_with_agent_veto() -> None:
    manager = _make_minimal_manager(observe_only_agents=False)

    result = manager.validate_signal(_make_naked_put_request())

    assert result.approved is False
    assert "AGENT_VETO" in result.violations
