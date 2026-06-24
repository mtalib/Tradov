from __future__ import annotations

import os

from Tradov.TradovU_Utilities.TradovU51_RuntimeContext import RuntimeContext


def test_session_supervisor_does_not_mutate_runtime_mode_env(monkeypatch):
    from Tradov.TradovR_Runtime.TradovR12_SessionSupervisor import SessionSupervisor

    monkeypatch.delenv("TRADOV_TRADING_MODE", raising=False)
    monkeypatch.delenv("TRADING_MODE", raising=False)

    supervisor = SessionSupervisor(mode="paper", dry_run=True)
    monkeypatch.setattr(supervisor, "_start_event_manager", lambda: True)
    monkeypatch.setattr(supervisor, "_start_data_feed", lambda: True)
    monkeypatch.setattr(supervisor, "_start_freshness_monitor", lambda: True)
    monkeypatch.setattr(supervisor, "_start_broker", lambda: True)
    monkeypatch.setattr(supervisor, "_start_fill_reconciler", lambda: None)
    monkeypatch.setattr(supervisor, "_start_position_tracker", lambda: None)
    monkeypatch.setattr(supervisor, "_start_risk_manager", lambda: True)
    monkeypatch.setattr(supervisor, "_start_live_engine", lambda: True)
    monkeypatch.setattr(supervisor, "_start_orchestrator", lambda: True)
    monkeypatch.setattr(supervisor, "_start_exit_monitor", lambda: None)
    monkeypatch.setattr(supervisor, "_start_liveness_monitor", lambda: None)
    monkeypatch.setattr(supervisor, "_boot_orphan_sweep", lambda: None)
    monkeypatch.setattr(supervisor, "_run_boot_self_test", lambda timeout_seconds=3.0: True)
    monkeypatch.setattr(supervisor, "_emit_startup_routing_receipt", lambda: None)
    monkeypatch.setattr(supervisor, "_begin_startup_profile", lambda: None)
    monkeypatch.setattr(supervisor, "_log_startup_profile", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(supervisor, "_end_startup_profile", lambda: None)

    assert "TRADOV_TRADING_MODE" not in os.environ
    assert "TRADING_MODE" not in os.environ
    assert supervisor.runtime_context.mode == "paper"
    assert supervisor.start() is True
    assert "TRADOV_TRADING_MODE" not in os.environ
    assert "TRADING_MODE" not in os.environ
    supervisor.stop()


def test_d31_runtime_context_overrides_conflicting_env(monkeypatch):
    from Tradov.TradovD_Strategies.TradovD31_StrategyOrchestrator import StrategyOrchestrator

    monkeypatch.setenv("TRADOV_TRADING_MODE", "live")
    context = RuntimeContext(mode="paper", session_id="paper-test")

    orchestrator = StrategyOrchestrator(runtime_context=context)

    assert orchestrator._is_live_mode() is False
    assert orchestrator._audit_run_mode == "paper"
    assert orchestrator._audit_session_id == "paper-test"
