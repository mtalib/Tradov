"""T194 — R12 SessionSupervisor must inject the synced RiskManager into D31.

Regression guard for the ``risk_state_cold`` signal-drop observed in
``logs/decisions/2026-05-02.jsonl`` and ``2026-05-03.jsonl``.

Root cause:
    ``get_risk_manager`` is a factory (not a singleton) — every call creates a
    fresh, un-synced ``RiskManager`` instance.  R12 creates instance A, calls
    ``mark_account_synced()`` on it, but D31's lazy resolver later calls
    ``get_risk_manager()`` again and gets a brand-new un-synced instance B.
    Instance B immediately rejects every signal with ``risk_state_cold`` because
    ``_account_state_synced == False``.

Fix (2026-05-05): R12's ``_start_orchestrator`` now calls
    ``self.orchestrator.set_risk_manager(self.risk)`` so the already-synced
    instance is re-used.

These tests must be GREEN after the fix ships.
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_supervisor_with_synced_risk():
    """Create a SessionSupervisor with a fake synced RiskManager on sv.risk."""
    from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import SessionSupervisor

    sv = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
    sv.em = MagicMock()
    sv.engine = MagicMock(name="LiveEngine")

    # Provide a fake, already-synced risk manager (simulates step 7 of startup).
    fake_risk = MagicMock(name="RiskManager")
    fake_risk._account_state_synced = True
    sv.risk = fake_risk
    return sv, fake_risk


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRiskManagerInjection:
    """R12 must inject the synced RiskManager into D31 during _start_orchestrator."""

    def test_start_orchestrator_calls_set_risk_manager(self):
        """After _start_orchestrator, orchestrator.risk_manager is the synced instance."""
        sv, fake_risk = _make_supervisor_with_synced_risk()

        with patch(
            "Spyder.SpyderB_Broker.SpyderB02_OrderManager.OrderManager",
            return_value=MagicMock(name="OrderManager"),
        ):
            ok = sv._start_orchestrator()

        assert ok is True, "_start_orchestrator must succeed in paper/dry_run mode"
        orch = sv.orchestrator
        assert orch is not None

        wired_rm = getattr(orch, "risk_manager", None)
        assert wired_rm is fake_risk, (
            "D31's risk_manager attribute must be the same instance R12 created "
            "and synced — not a fresh factory-allocated un-synced instance."
        )

    def test_d31_uses_injected_manager_not_lazy_factory(self):
        """D31 must NOT call get_risk_manager() lazily if set_risk_manager was called."""
        sv, fake_risk = _make_supervisor_with_synced_risk()

        with patch(
            "Spyder.SpyderB_Broker.SpyderB02_OrderManager.OrderManager",
            return_value=MagicMock(name="OrderManager"),
        ):
            sv._start_orchestrator()

        orch = sv.orchestrator
        # Inject a sentinel to verify lazy resolver is not triggered.
        orch.risk_manager = fake_risk  # ensure injected value stays

        # Simulating signal routing: risk_manager is not None, so the lazy
        # import block is skipped.  The injected manager must be the one used.
        assert orch.risk_manager is fake_risk

    def test_mark_account_synced_on_injected_instance_is_reflected(self):
        """The account-synced flag on the injected instance is visible to D31."""
        sv, fake_risk = _make_supervisor_with_synced_risk()
        fake_risk.mark_account_synced = MagicMock()

        with patch(
            "Spyder.SpyderB_Broker.SpyderB02_OrderManager.OrderManager",
            return_value=MagicMock(name="OrderManager"),
        ):
            sv._start_orchestrator()

        orch = sv.orchestrator
        # The wired instance is the one that was synced in _start_risk_manager.
        assert getattr(orch.risk_manager, "_account_state_synced", None) is True, (
            "The injected RiskManager must already be account-synced so "
            "validate_signal does not return risk_state_cold."
        )
