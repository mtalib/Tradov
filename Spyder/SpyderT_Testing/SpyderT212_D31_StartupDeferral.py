#!/usr/bin/env python3
"""Focused regressions for paper-mode D31 startup deferral."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class _StubEventManager:
    def subscribe(self, *args, **kwargs):
        return None

    def emit(self, *args, **kwargs):
        return None

    def publish(self, *args, **kwargs):
        return None


class _ThreadStub:
    started_targets: list[object] = []

    def __init__(self, target=None, daemon=None, name=None):
        self.target = target
        self.daemon = daemon
        self.name = name

    def start(self) -> None:
        self.started_targets.append(self.target)


def test_d31_can_defer_initial_strategy_activation() -> None:
    mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )
    _ThreadStub.started_targets = []

    orch = mod.StrategyOrchestrator(event_manager=_StubEventManager())
    orch._live_engine = object()
    orch.logger = SimpleNamespace(
        debug=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
        critical=lambda *args, **kwargs: None,
    )

    with (
        patch.object(mod.threading, "Thread", _ThreadStub),
        patch.object(orch, "_update_market_regime") as update_regime,
        patch.object(orch, "_configure_strategies_for_regime") as configure,
        patch.object(orch, "_perform_initial_allocation") as allocate,
    ):
        assert orch.start_orchestration(defer_initial_strategy_activation=True) is True

        update_regime.assert_called_once_with()
        configure.assert_not_called()
        allocate.assert_not_called()
        assert orch._initial_strategy_activation_pending is True
        assert len(_ThreadStub.started_targets) == 2

        orch._run_initial_strategy_activation_if_pending()

        configure.assert_called_once_with()
        allocate.assert_called_once_with()
        assert orch._initial_strategy_activation_pending is False

    orch.orchestration_active = False
    orch.shutdown_event.set()


def test_d31_deferred_initial_strategy_activation_is_single_claim() -> None:
    mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )

    orch = mod.StrategyOrchestrator(event_manager=_StubEventManager())
    orch._live_engine = object()
    orch.logger = SimpleNamespace(
        debug=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
        critical=lambda *args, **kwargs: None,
    )
    orch._initial_strategy_activation_pending = True

    def _reentrant_configure() -> None:
        orch._run_initial_strategy_activation_if_pending()

    with (
        patch.object(orch, "_configure_strategies_for_regime", side_effect=_reentrant_configure) as configure,
        patch.object(orch, "_perform_initial_allocation") as allocate,
    ):
        orch._run_initial_strategy_activation_if_pending()

    configure.assert_called_once_with()
    allocate.assert_called_once_with()
    assert orch._initial_strategy_activation_pending is False
    assert orch._initial_strategy_activation_running is False


def test_market_data_warmup_claims_pending_initial_activation_once() -> None:
    mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )

    orch = mod.StrategyOrchestrator(event_manager=_StubEventManager())
    orch._live_engine = object()
    orch.logger = SimpleNamespace(
        debug=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
        critical=lambda *args, **kwargs: None,
    )
    orch.market_regime.current_regime = mod.MarketRegime.SIDEWAYS_LOW_VOL
    orch._initial_strategy_activation_pending = True

    event = SimpleNamespace(
        data={
            "symbol": "SPY",
            "tick": {
                "symbol": "SPY",
                "price": 500.0,
                "last": 500.0,
                "close": 500.0,
                "high": 500.1,
                "low": 499.9,
                "volume": 1000,
            },
        }
    )

    with (
        patch.object(orch, "_update_market_regime") as update_regime,
        patch.object(orch, "_configure_strategies_for_regime") as configure,
        patch.object(orch, "_perform_initial_allocation") as allocate,
    ):
        orch._on_market_data_event(event)
        orch._run_initial_strategy_activation_if_pending()

    update_regime.assert_called_once_with()
    configure.assert_called_once_with()
    allocate.assert_called_once_with()
    assert orch._initial_strategy_activation_pending is False


def test_r12_paper_mode_defers_initial_strategy_activation() -> None:
    from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import SessionSupervisor

    supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
    supervisor.em = MagicMock()
    supervisor.engine = MagicMock(name="LiveEngine")

    fake_orchestrator = MagicMock()
    fake_orchestrator.start_orchestration.return_value = True
    fake_orchestrator.emit_decision_audit_marker = MagicMock()

    with patch(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator.StrategyOrchestrator",
        return_value=fake_orchestrator,
    ):
        ok = supervisor._start_orchestrator()

    assert ok is True
    fake_orchestrator.start_orchestration.assert_called_once_with(
        defer_initial_strategy_activation=True
    )


def test_r12_paper_mode_defers_l09_initialization_until_after_startup() -> None:
    from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import SessionSupervisor

    supervisor = SessionSupervisor(mode="paper", dry_run=False, skip_orphan_sweep=True)
    supervisor.em = MagicMock()
    supervisor.engine = MagicMock(name="LiveEngine")
    supervisor.risk = MagicMock(name="RiskManager")

    fake_orchestrator = MagicMock()
    fake_orchestrator.start_orchestration.return_value = True
    fake_orchestrator.emit_decision_audit_marker = MagicMock()

    with (
        patch(
            "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator.StrategyOrchestrator",
            return_value=fake_orchestrator,
        ) as orchestrator_cls,
        patch.object(
            supervisor,
            "_start_deferred_orchestrator_regime_engine_initialization",
        ) as deferred_l09_init,
    ):
        ok = supervisor._start_orchestrator()

    assert ok is True
    assert orchestrator_cls.call_args.kwargs["regime_engine"] is None
    deferred_l09_init.assert_called_once_with(fake_orchestrator)


def test_r12_deferred_l09_uses_lean_attach_config() -> None:
    from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import SessionSupervisor

    supervisor = SessionSupervisor(mode="paper", dry_run=False, skip_orphan_sweep=True)
    supervisor.logger = SimpleNamespace(
        debug=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
    )
    supervisor._deferred_l09_cancel.clear()
    supervisor._running = True
    orchestrator = MagicMock()
    supervisor.orchestrator = orchestrator

    class _ImmediateThread:
        def __init__(self, target=None, daemon=None, name=None):
            self.target = target

        def start(self) -> None:
            assert self.target is not None
            self.target()

    fake_engine = object()

    with (
        patch(
            "Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor.threading.Thread",
            _ImmediateThread,
        ),
        patch(
            "Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor.time.sleep",
            lambda *_args, **_kwargs: None,
        ),
        patch(
            "Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor._PAPER_ORCHESTRATOR_L09_DEFER_SECONDS",
            0.0,
        ),
        patch(
            "Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine.create_unified_regime_engine",
            return_value=fake_engine,
        ) as create_engine,
    ):
        supervisor._start_deferred_orchestrator_regime_engine_initialization(orchestrator)

    create_engine.assert_called_once_with(
        {
            "defer_attribution_until_after_first_regime": True,
            "enable_quant_models": False,
            "enable_hmm": False,
            "connect_metrics_orchestrator": False,
        }
    )
    orchestrator.set_regime_engine.assert_called_once_with(fake_engine)
