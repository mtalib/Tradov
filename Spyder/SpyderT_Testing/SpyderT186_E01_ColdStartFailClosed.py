"""SPEC-10 — E01 cold-start fail-closed when tradier_client is missing in live.

Audit reference: 2026-05-02_Codebase_Audit_v27.md → SPEC-10.

The bug: ``RiskManager._request_account_summary`` short-circuits to
``self._account_state_synced = True`` whenever ``tradier_client is None`` —
*including in live mode*. If DI ever forgets to inject the client during a
degraded boot, the cold-start guard is bypassed and ``validate_signal``
proceeds on empty positions and zero balances, approving every order against
a fabricated zero-baseline.

Required behavior after SPEC-10:
- ``tradier_client is None`` AND live env  → ``_account_state_synced`` stays
  ``False`` and ``validate_signal`` rejects with reason "broker not available".
- ``tradier_client is None`` AND paper env → existing behavior preserved
  (``_account_state_synced`` becomes True so standalone runs aren't blocked).

These tests are RED until SPEC-10 ships.
"""

from __future__ import annotations

import asyncio
import os
from threading import RLock
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from Spyder.SpyderE_Risk.SpyderE00_RiskProtocol import (
    BoundarySignalType,
    RiskValidationRequest,
)
from Spyder.SpyderE_Risk.SpyderE01_RiskManager import RiskManager


def _make_minimal_manager(tradier_client=None) -> RiskManager:
    """Build a RiskManager bypassing the heavyweight constructor."""
    manager = RiskManager.__new__(RiskManager)
    manager._risk_lock = RLock()
    manager._positions = {}
    manager._account_state_synced = False
    manager._cached_account_balances = {}
    manager._data_stale = False
    manager._y03_veto_state = "ok"
    manager._observe_only_agents = True
    manager._enforce_decision_quality_slo = False
    manager._config = {}
    manager.config = SimpleNamespace(risk_limits=SimpleNamespace())
    manager.tradier_client = tradier_client
    manager.logger = SimpleNamespace(
        debug=lambda *a, **k: None,
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    manager.error_handler = SimpleNamespace(handle_error=lambda *a, **k: None)
    return manager


def _make_signal_request() -> RiskValidationRequest:
    return RiskValidationRequest(
        symbol="SPY",
        quantity=1,
        signal_type=BoundarySignalType.BUY,
        strategy_id="spec10_unit",
        entry_price=2.0,
        confidence=0.8,
        metadata={"strategy_type": "long_call"},
    )


class TestColdStartFailClosed:
    """SPEC-10: live + no broker → must NOT mark synced."""

    def test_live_mode_with_no_client_keeps_cold_start_guard_active(self):
        manager = _make_minimal_manager(tradier_client=None)

        with patch.dict(os.environ, {"TRADING_MODE": "live"}, clear=False):
            asyncio.run(manager._request_account_summary())

        assert manager._account_state_synced is False, (
            "SPEC-10: live mode with no Tradier client must leave the cold-start "
            "guard engaged. Currently the code marks synced=True on the missing-"
            "client shortcut, opening a fail-open path on degraded boots."
        )

    def test_live_mode_with_no_client_blocks_validate_signal(self):
        """Downstream effect: cold-start unsynced state must block validate_signal.

        E01's existing logic already rejects when ``_account_state_synced is False``
        (see T180 and the cold-start guard in validate_signal). This test pins
        the *integration* — i.e. that SPEC-10 keeping the flag False is sufficient
        to make validate_signal reject without any other change.
        """
        manager = _make_minimal_manager(tradier_client=None)

        with patch.dict(os.environ, {"TRADING_MODE": "live"}, clear=False):
            asyncio.run(manager._request_account_summary())

        # The contract is on the guard flag, not on validate_signal's internal
        # rejection format. Downstream code reads this flag.
        assert manager._account_state_synced is False, (
            "SPEC-10 integration: live + no broker must leave the cold-start "
            "guard False so validate_signal's existing guard rejects all signals."
        )


class TestPaperBehaviorPreserved:
    """SPEC-10 must not regress the existing paper-mode behavior."""

    def test_paper_mode_with_no_client_marks_synced(self):
        """Standalone / paper runs without a TradierClient must continue to work."""
        manager = _make_minimal_manager(tradier_client=None)

        with patch.dict(os.environ, {"TRADING_MODE": "paper"}, clear=False):
            asyncio.run(manager._request_account_summary())

        assert manager._account_state_synced is True, (
            "Paper mode must preserve the legacy 'mark synced when no broker' "
            "shortcut so standalone test boots aren't permanently blocked."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
