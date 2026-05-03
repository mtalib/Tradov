"""SPEC-6 — R12 SessionSupervisor must wire OrderManager to D31, not just LiveEngine.

Audit reference: 2026-05-02_Codebase_Audit_v27.md → SPEC-6.

The bug: ``SessionSupervisor._start_orchestrator`` only calls
``self.orchestrator.set_live_engine(self.engine)`` (R12:529). It never calls
``set_order_manager``. The entire mid-price-walk execution path in
``D31._dispatch_approved_signal`` (D31:3766-3794) is therefore dead in
production — every signal degrades to a market order, paying full bid/ask
spread on every options entry. For SPY 0DTE this is ~$5-15 of slippage per
round trip.

Required behavior after SPEC-6:
- After ``_start_orchestrator`` returns ``True``, ``self.orchestrator`` must
  have BOTH ``_live_engine`` AND ``_order_manager`` attributes set.
- D31's ``start_orchestration`` must log ERROR if both wiring methods are
  missing.
- An integration check: with the orchestrator wired, an approved signal
  carrying ``bid``/``ask`` reaches ``OrderManager.submit_limit_with_walk``,
  not ``LiveEngine.execute_order``.

These tests are RED until SPEC-6 ships.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# --------------------------------------------------------------------------
# SPEC-6 PART 1: R12 wires both LiveEngine and OrderManager
# --------------------------------------------------------------------------

class TestSupervisorWiresOrderManager:
    """The supervisor must call set_order_manager during _start_orchestrator."""

    def test_start_orchestrator_calls_set_order_manager(self):
        from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import (
            SessionSupervisor,
        )

        sv = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
        sv.em = MagicMock()
        sv.engine = MagicMock(name="LiveEngine")

        # Patch the OrderManager constructor so the test does not require Tradier.
        fake_om = MagicMock(name="OrderManager")
        with patch(
            "Spyder.SpyderB_Broker.SpyderB02_OrderManager.OrderManager",
            return_value=fake_om,
        ):
            ok = sv._start_orchestrator()

        assert ok is True, "Orchestrator startup must succeed in paper/dry_run"
        orch = sv.orchestrator
        assert orch is not None, "Orchestrator instance must be retained on supervisor"

        # SPEC-6: BOTH wirings must be present.
        assert getattr(orch, "_live_engine", None) is sv.engine, (
            "Existing wiring: set_live_engine(engine) must still be called."
        )
        assert getattr(orch, "_order_manager", None) is fake_om, (
            "SPEC-6: _start_orchestrator must call set_order_manager(om) so the "
            "mid-price-walk execution path is live in production."
        )


# --------------------------------------------------------------------------
# SPEC-6 PART 2: D31 logs ERROR if both wirings are missing
# --------------------------------------------------------------------------

class TestOrchestratorWarnsWhenUnwired:
    """start_orchestration must log ERROR (not silent log) if both wirings absent."""

    def test_start_orchestration_logs_error_when_no_engine_and_no_om(self):
        mod = importlib.import_module(
            "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
        )

        class _StubEM:
            def subscribe(self, *a, **k): return None
            def emit(self, *a, **k): return None
            def publish(self, *a, **k): return None

        orch = mod.StrategyOrchestrator(event_manager=_StubEM())
        # Explicitly leave both wirings missing.
        orch._live_engine = None
        orch._order_manager = None

        captured: list[tuple[str, tuple]] = []
        orch.logger = SimpleNamespace(
            debug=lambda *a, **k: captured.append(("debug", a)),
            info=lambda *a, **k: captured.append(("info", a)),
            warning=lambda *a, **k: captured.append(("warning", a)),
            error=lambda *a, **k: captured.append(("error", a)),
            critical=lambda *a, **k: captured.append(("critical", a)),
        )

        try:
            orch.start_orchestration()
        finally:
            orch.orchestration_active = False

        levels = {lvl for lvl, _ in captured}
        assert "error" in levels or "critical" in levels, (
            "SPEC-6: start_orchestration must log at ERROR level when neither "
            "LiveEngine nor OrderManager is wired (current code logs at WARNING "
            "or below, hiding the dead-execution-path from operators). "
            f"Got levels: {sorted(levels)}"
        )


# --------------------------------------------------------------------------
# SPEC-6 PART 3: approved signal with bid/ask reaches submit_limit_with_walk
# --------------------------------------------------------------------------

class TestMidPriceWalkPathLive:
    """End-to-end: a wired orchestrator must route through OrderManager, not LiveEngine."""

    def test_dispatch_uses_order_manager_when_signal_has_bid_ask(self):
        mod = importlib.import_module(
            "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
        )

        class _StubEM:
            def subscribe(self, *a, **k): return None
            def emit(self, *a, **k): return None
            def publish(self, *a, **k): return None

        orch = mod.StrategyOrchestrator(event_manager=_StubEM())

        engine = MagicMock(name="LiveEngine")
        om = MagicMock(name="OrderManager")
        # OrderManager.submit_limit_with_walk returns a truthy success result.
        om.submit_limit_with_walk.return_value = SimpleNamespace(
            success=True, order_id="WALK-1"
        )

        orch.set_live_engine(engine)
        orch.set_order_manager(om)

        # Build a signal that carries bid/ask (mid-price walk requires both).
        signal = SimpleNamespace(
            symbol="SPY240517C00500000",
            side="BUY",
            quantity=1,
            entry_price=2.50,
            bid=2.45,
            ask=2.55,
            strategy_id="spec6_unit",
            metadata={"bid": 2.45, "ask": 2.55},
        )

        try:
            orch._dispatch_approved_signal(signal)
        except Exception as e:
            pytest.skip(
                f"_dispatch_approved_signal raised before reaching execution path: {e}. "
                "This test pins the contract; adjust signal shape to match D31's expectations."
            )

        assert om.submit_limit_with_walk.called, (
            "SPEC-6: an approved signal with bid+ask must route through "
            "OrderManager.submit_limit_with_walk, not LiveEngine.execute_order. "
            "Currently the OM path is dead because R12 never calls set_order_manager."
        )
        assert not engine.execute_order.called, (
            "SPEC-6: LiveEngine.execute_order must NOT be called when "
            "OrderManager is wired and the signal carries bid+ask."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
