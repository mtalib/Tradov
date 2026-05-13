#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderR_Runtime
Module: SpyderR12_SessionSupervisor.py
Purpose: Single lifecycle owner for all backend components (S-12 / O-01)

Author: Spyder Dev
Year Created: 2025
Last Updated: 2026-04-18 Time: 00:00:00

Module Description:
    SessionSupervisor owns the ordered startup and shutdown of every backend
    component required for a live or paper trading session:

        EventManager → DataFeed → DataFreshnessMonitor → FillReconciler
        → RiskManager → LiveEngine → StrategyOrchestrator

    On ``start()`` each component is started in dependency order.  If any
    component fails to start the session is aborted and all already-started
    components are stopped (clean rollback).

    On ``stop(flatten=False)`` components are stopped in reverse order.  Pass
    ``flatten=True`` to attempt position flattening before the broker is torn
    down.

    Q14 (SpyderQ14_MainLauncher) becomes a thin argument-parser + signal
    handler that delegates all backend lifecycle to this class.

Usage::

    supervisor = SessionSupervisor(mode="paper")
    if not supervisor.start():
        sys.exit(1)

    # … block on SIGTERM / KeyboardInterrupt …
    supervisor.stop()
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging  # noqa: F401
import os
import signal
import threading
import time
import uuid
import asyncio
from typing import Any, List, Literal, Optional

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

# ==============================================================================
# CONSTANTS
# ==============================================================================
_DEFAULT_SYMBOLS = ["SPY", "SPX", "VIX"]
_PAPER_ORCHESTRATOR_L09_DEFER_SECONDS = 0.25
_PAPER_ORCHESTRATOR_L09_DEFER_CONFIG = {
    "defer_attribution_until_after_first_regime": True,
    "enable_quant_models": False,
    "enable_hmm": False,
    "connect_metrics_orchestrator": False,
}

# ==============================================================================
# TYPES
# ==============================================================================


class _Lifecycle:
    """Minimal duck-type required for component list entries."""

    def start(self) -> bool: ...  # noqa: E704
    def stop(self) -> None: ...   # noqa: E704


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class SessionSupervisor:
    """
    Owns the complete lifecycle of one trading session.

    Args:
        mode: ``"live"`` or ``"paper"``.
        symbols: Market symbols to subscribe to.  Defaults to
            ``FEED_SYMBOLS`` env-var, falling back to ``["SPY", "SPX", "VIX"]``.

    Attributes:
        mode: Active trading mode.
        is_running: ``True`` while the session is fully started.
    """

    def __init__(
        self,
        mode: Literal["paper", "live"],
        symbols: Optional[List[str]] = None,
        dry_run: bool = False,
        skip_orphan_sweep: bool = False,
    ) -> None:
        self.logger = SpyderLogger.get_logger(__name__)
        self.mode = mode
        os.environ["SPYDER_TRADING_MODE"] = str(mode)
        self.session_id: str = ""
        self.dry_run: bool = dry_run
        self.skip_orphan_sweep: bool = skip_orphan_sweep
        self.symbols: List[str] = symbols or [
            s.strip()
            for s in os.environ.get("FEED_SYMBOLS", "SPY,SPX,VIX").split(",")
            if s.strip()
        ]

        # Ordered list of started components — stopped in reverse on shutdown.
        self._components: List[Any] = []
        self._lock = threading.Lock()
        self._running = False

        # References kept for external access (e.g., tests, CLI status checks).
        self.em: Any = None
        self.broker: Any = None
        self.risk: Any = None
        self.feed: Any = None
        self.freshness_monitor: Any = None
        self.reconciler: Any = None
        self.position_tracker: Any = None
        self.engine: Any = None
        self.orchestrator: Any = None
        self.exit_monitor: Any = None
        # O1/O9/A13 (v14): LivenessMonitor — heartbeat + /healthz + deadman.
        self.liveness: Any = None
        self._flatten_request_handler_id: Optional[str] = None
        self._startup_profile_enabled: bool = self._is_truthy_env(
            os.getenv("SPYDER_SESSION_SUPERVISOR_PROFILE_STARTUP")
        )
        self._startup_profile_started_at: float | None = None
        self._deferred_l09_cancel = threading.Event()
        self._deferred_l09_thread: threading.Thread | None = None

    # --------------------------------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> bool:
        """
        Build and start all backend components in dependency order.

        Returns:
            ``True`` on success, ``False`` if any required component fails.
        """
        self.session_id = f"{self.mode}-{uuid.uuid4().hex[:12]}"
        self._deferred_l09_cancel.clear()
        self.logger.debug(
            "SessionSupervisor.start() — mode=%s symbols=%s session_id=%s",
            self.mode,
            self.symbols,
            self.session_id,
        )
        self._begin_startup_profile()
        if self.dry_run:
            self.logger.warning("⚠️  DRY-RUN MODE — order submission is suppressed; no orders will reach the broker")  # noqa: E501

        policy_ok, policy_violation = self._validate_live_only_tradier_policy()
        if not policy_ok:
            self.logger.critical(
                "❌ Live-only Tradier policy violation; refusing startup (%s)",
                policy_violation,
            )
            return self._abort("LiveOnlyTradierPolicy")

        # 1. EventManager ── shared event bus
        if not self._start_event_manager():
            return self._abort("EventManager")

        # 2. DataFeed ── market data → MARKET_DATA events
        if not self._start_data_feed():
            return self._abort("DataFeed")

        # 3. DataFreshnessMonitor ── writes DATA_STALE / DATA_FRESH (fixes H-05)
        if not self._start_freshness_monitor():
            return self._abort("DataFreshnessMonitor")

        # 4. FillReconciler ── background fill poller (needs broker, built below)
        # Broker must exist first.

        # 5. Broker
        if not self._start_broker():
            return self._abort("Broker")

        # 6. FillReconciler (now broker is available)
        self._start_fill_reconciler()  # non-fatal

        # 6.5 PositionTracker — must exist before LiveEngine so fills are recorded
        self._start_position_tracker()  # non-fatal

        # 7. RiskManager ── mandatory fail-closed startup
        if not self._start_risk_manager():
            return self._abort("RiskManager")
        self._log_startup_profile("risk_manager_ready")

        # 8. LiveEngine
        if not self._start_live_engine():
            return self._abort("LiveEngine")
        self._log_startup_profile("live_engine_ready")

        # 9. StrategyOrchestrator
        if not self._start_orchestrator():
            return self._abort("StrategyOrchestrator")
        self._log_startup_profile("strategy_orchestrator_ready")

        # 10. ExitMonitor — must come after orchestrator so strategy_map is populated
        self._start_exit_monitor()  # non-fatal
        self._log_startup_profile("exit_monitor_ready")

        # 11. LivenessMonitor — heartbeat + /healthz + deadman (v14 O1/O9/A13)
        self._start_liveness_monitor()  # non-fatal
        self._log_startup_profile("liveness_monitor_ready")

        # O-2: One-shot orphan sweep immediately after boot to surface any
        # pre-existing broker positions not owned by a registered strategy
        # (e.g. left open after a crash).
        self._boot_orphan_sweep()
        self._log_startup_profile("boot_orphan_sweep_complete")

        # P1-13: Boot-time synthetic signal self-test. Fail closed if the
        # strategy signal path does not produce ORDER_REJECTED(reason=dry_run).
        if not self._run_boot_self_test(timeout_seconds=3.0):
            return self._abort("BootSelfTest")
        self._log_startup_profile("boot_self_test_complete")

        self._running = True
        self._log_startup_profile("start_complete")
        self._end_startup_profile()
        self.logger.debug("✅ SessionSupervisor fully started in %s mode", self.mode)

        return True

    def stop(self, flatten: bool = False) -> None:
        """
        Stop all components in reverse order.

        Args:
            flatten: Attempt to flatten (close) all open positions before
                stopping the broker.  Only attempted when ``True`` and a live
                engine is available.
        """
        with self._lock:
            if not self._running:
                return
            self._running = False

        self._deferred_l09_cancel.set()
        deferred_l09_thread = self._deferred_l09_thread
        if (
            deferred_l09_thread is not None
            and deferred_l09_thread.is_alive()
            and deferred_l09_thread is not threading.current_thread()
        ):
            deferred_l09_thread.join(timeout=2.0)
            if deferred_l09_thread.is_alive():
                self.logger.warning("Deferred L09 attach thread still active during shutdown")
            elif self._deferred_l09_thread is deferred_l09_thread:
                self._deferred_l09_thread = None

        # O10 (v14): formalized shutdown phases with named log lines so an
        # operator (or the Q24 watchdog) can pinpoint where a shutdown hung.
        self.logger.info("SessionSupervisor.stop() — flatten=%s", flatten)

        # ---- Phase 1/4 — flatten (optional) ----
        self.logger.info("SHUTDOWN_PHASE_1_FLATTEN_BEGIN")
        if flatten and self.engine is not None:
            self._flatten_positions()
        self.logger.info("SHUTDOWN_PHASE_1_FLATTEN_END")

        # ---- Phase 2/4 — stop strategy/engine layer (reverse order) ----
        self.logger.info("SHUTDOWN_PHASE_2_COMPONENTS_BEGIN")
        for component in reversed(self._components):
            name = type(component).__name__
            try:
                component.stop()
                self.logger.info("  stopped %s", name)
            except Exception as exc:
                self.logger.warning("  stop %s raised: %s", name, exc)
        self.logger.info("SHUTDOWN_PHASE_2_COMPONENTS_END")

        # ---- Phase 3/4 — broker disconnect (already handled in component loop) ----
        self.logger.info("SHUTDOWN_PHASE_3_BROKER_END")

        # ---- Phase 4/4 — process cleanup ----
        # Note: the EventManager is a shared singleton — we do NOT stop it here.
        # Its lifecycle is managed by the process (Python GC / main thread shutdown).
        if self.em is not None and self._flatten_request_handler_id:
            try:
                self.em.unsubscribe(self._flatten_request_handler_id)
            except Exception as exc:
                self.logger.warning("Failed to unsubscribe FLATTEN_REQUEST handler: %s", exc)
            finally:
                self._flatten_request_handler_id = None
        self.logger.info("SHUTDOWN_PHASE_4_PROCESS_END")

        self.logger.info("SessionSupervisor stopped.")
        try:
            from Spyder.SpyderP_PortfolioMgmt import (
                reset_global_portfolio_manager,
            )
            reset_global_portfolio_manager()
        except Exception:
            pass
        # C3 (v18): clear the singleton so get_session_supervisor() returns None
        # once this instance is stopped.  Prevents stale references from
        # accumulating in long-running processes that start multiple sessions.
        self._deferred_l09_thread = None
        set_session_supervisor(None)

    def block_until_signal(self) -> None:
        """
        Block the calling thread until SIGTERM or KeyboardInterrupt.

        Suitable for headless operation::

            supervisor.start()
            supervisor.block_until_signal()
            supervisor.stop()
        """
        stop_event = threading.Event()

        def _handler(signum, frame):  # noqa: ANN001
            self.logger.info("Signal %s received — initiating graceful shutdown", signum)
            stop_event.set()

        signal.signal(signal.SIGTERM, _handler)
        signal.signal(signal.SIGINT, _handler)

        self.logger.info("Blocking — send SIGTERM or Ctrl-C to stop")
        try:
            while not stop_event.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass

    # --------------------------------------------------------------------------
    # PRIVATE — component builders
    # --------------------------------------------------------------------------

    def _start_event_manager(self) -> bool:
        try:
            from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType, get_event_manager
            self.em = get_event_manager()
            if not self.em.is_running:
                self.em.start()
            if self._flatten_request_handler_id is None:
                self._flatten_request_handler_id = self.em.subscribe(
                    EventType.FLATTEN_REQUEST,
                    self._on_flatten_request,
                )
            self.logger.debug("✅ EventManager started")
            return True
        except Exception as exc:
            self.logger.error("❌ EventManager failed: %s", exc)
            return False

    def _start_data_feed(self) -> bool:
        try:
            market_data_env = (
                os.getenv("TRADIER_MARKET_DATA_ENVIRONMENT")
                or os.getenv("TRADIER_ENVIRONMENT")
                or "live"
            ).strip().lower()
            is_live_env = market_data_env in {"live", "production"}

            if not is_live_env:
                self.logger.warning(
                    "SessionSupervisor forcing LIVE market-data endpoint "
                    "(TRADIER_MARKET_DATA_ENVIRONMENT=%s ignored).",
                    market_data_env or "<empty>",
                )

            os.environ["TRADIER_MARKET_DATA_ENVIRONMENT"] = "live"

            provider_name = os.getenv("MARKET_DATA_PROVIDER", "tradier").lower().strip()
            from Spyder.SpyderC_MarketData.SpyderC01_DataFeed import create_data_feed
            self.feed = create_data_feed(
                symbols=self.symbols,
                event_manager=self.em,
                provider=provider_name,
            )
            if not self.feed.start():
                self.logger.error("❌ DataFeed.start() returned False")
                return False
            self._components.append(self.feed)
            self.logger.debug("✅ DataFeed started — symbols: %s", self.symbols)
            return True
        except Exception as exc:
            self.logger.error("❌ DataFeed failed: %s", exc)
            return False

    def _start_freshness_monitor(self) -> bool:
        try:
            from Spyder.SpyderE_Risk.SpyderE24_DataFreshnessMonitor import create_freshness_monitor
            self.freshness_monitor = create_freshness_monitor(
                symbols=self.symbols, event_manager=self.em,
                startup_grace_s=30.0,  # suppress DATA_STALE for 30s on startup
            )
            self.freshness_monitor.start()
            self._components.append(self.freshness_monitor)
            self.logger.debug("✅ DataFreshnessMonitor started (startup_grace=30s)")
            return True
        except Exception as exc:
            self.logger.error("❌ DataFreshnessMonitor failed: %s", exc)
            return False

    def _start_broker(self) -> bool:
        if self.mode == "live":
            return self._start_live_broker()
        return self._start_paper_broker()

    def _start_live_broker(self) -> bool:
        try:
            from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
                create_tradier_client_from_env,
            )
            self.broker = create_tradier_client_from_env()
            self.logger.info("✅ Tradier broker (LIVE) created")
            return True
        except Exception as exc:
            self.logger.error("❌ Tradier broker failed: %s", exc)
            return False

    def _start_paper_broker(self) -> bool:
        """
        Paper broker: PaperBroker only (local, no Tradier paper account).
        """
        try:
            from Spyder.SpyderR_Runtime.SpyderR15_PaperBroker import create_paper_broker
            self.broker = create_paper_broker(event_manager=self.em, slippage_bps=0 if self.dry_run else 5)  # noqa: E501
            if self.dry_run:
                # Wrap place_order to be a no-op in dry_run mode.
                _real_place = self.broker.place_order
                def _dry_place_order(*a, **kw):
                    self.logger.info("[DRY RUN] place_order suppressed: %s", kw)
                    return {"order": {"id": "DRY-RUN-NOOP"}}
                self.broker.place_order = _dry_place_order  # type: ignore[method-assign]
            self.broker.start()
            self._components.append(self.broker)
            self.logger.debug("✅ PaperBroker started for paper mode")
            return True
        except Exception as exc:
            self.logger.error("❌ PaperBroker failed in paper mode: %s", exc)
            return False

    def _start_fill_reconciler(self) -> None:
        try:
            from Spyder.SpyderR_Runtime.SpyderR13_FillReconciler import FillReconciler
            self.reconciler = FillReconciler(broker=self.broker, event_manager=self.em)
            self.reconciler.start()
            self._components.append(self.reconciler)
            self.logger.debug("✅ FillReconciler started")
        except Exception as exc:
            self.logger.warning("⚠️ FillReconciler non-fatal: %s", exc)

    def _start_position_tracker(self) -> None:
        try:
            from Spyder.SpyderB_Broker.SpyderB03_PositionTracker import create_position_tracker
            self.position_tracker = create_position_tracker(
                spyder_client=self.broker,
                event_manager=self.em,
            )
            self.position_tracker.start()
            self._components.append(self.position_tracker)
            self.logger.debug("✅ PositionTracker started")
        except Exception as exc:
            self.logger.warning("⚠️ PositionTracker non-fatal: %s", exc)

    def _run_coroutine_sync(self, coro: Any) -> Any:
        """Run an async coroutine from this synchronous supervisor context."""
        try:
            return asyncio.run(coro)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

    def _start_risk_manager(self) -> bool:
        try:
            from Spyder.SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
            self.risk = get_risk_manager(tradier_client=self.broker)
            started = bool(self._run_coroutine_sync(self.risk.start()))
            if not started:
                self.logger.error("❌ RiskManager.start() returned False")
                return False
            # In paper mode the broker is a PaperBroker with no live Tradier account.
            # Force-mark the cold-start gate so signals are not silently dropped
            # even if the balance call succeeded (belt-and-suspenders).
            if self.mode != "live":
                self.risk.mark_account_synced()
                if hasattr(self.risk, "_enforce_decision_quality_slo"):
                    self.risk._enforce_decision_quality_slo = False
            # R12-B1: register a sync stop shim so the component loop can
            # signal shutdown and join threads (RiskManager.stop is async).
            _risk = self.risk
            class _RiskStopper:
                def stop(self):
                    _risk.stop_sync()
            self._components.append(_RiskStopper())
            self.logger.debug("✅ RiskManager ready and started")
            return True
        except Exception as exc:
            self.logger.error("❌ RiskManager failed: %s", exc)
            return False

    def _start_live_engine(self) -> bool:
        try:
            from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import create_live_engine
            account_id = (
                os.environ.get("TRADIER_ACCOUNT_ID")
                if self.mode == "live"
                else "PAPER-ACCOUNT"
            )
            config = {
                "account_id": account_id,
                "max_daily_trades": int(os.environ.get("MAX_DAILY_TRADES", 100)),
                "max_daily_loss": float(os.environ.get("MAX_DAILY_LOSS_USD", 10_000)),
                "require_confirmation": (self.mode == "live"),
            }
            self.engine = create_live_engine(
                self.broker, self.risk, config,
                event_manager=self.em,
                fill_reconciler=self.reconciler,
                position_tracker=self.position_tracker,
            )
            if not self.engine.initialize():
                self.logger.error("❌ LiveEngine.initialize() returned False")
                return False

            # H05: inject mode-specific session DB so confirmed fills are
            # persisted to the correct file with identical live/paper schema.
            try:
                from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB
                _session_db = (
                    TradingSessionDB.for_live()
                    if self.mode == "live"
                    else TradingSessionDB.for_paper()
                )
                self.engine.set_session_db(_session_db)
                self.logger.info(
                    "✅ Session DB (H05) attached to LiveEngine (mode=%s)",
                    self.mode,
                )
            except Exception as _h05_err:
                self.logger.warning("H05 session DB unavailable: %s", _h05_err)

            self.engine.start_trading()
            try:
                from Spyder.SpyderP_PortfolioMgmt import (
                    set_global_portfolio_manager,
                )
                _pm = getattr(self.engine, "portfolio_manager", None)
                if _pm is not None:
                    set_global_portfolio_manager(_pm)
            except Exception as _pm_err:
                self.logger.debug("Could not publish global portfolio manager: %s", _pm_err)
            self._components.append(self.engine)
            self.logger.debug("✅ LiveEngine started")
            return True
        except Exception as exc:
            self.logger.error("❌ LiveEngine failed: %s", exc)
            return False

    def _start_orchestrator(self) -> bool:
        try:
            from Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator import (
                StrategyOrchestrator,
                OrchestrationMode,
                AllocationMethod,
            )
            base_capital = float(os.environ.get("BASE_CAPITAL", 100_000))
            # B10 (v15): orchestration mode and allocation method driven by env
            # vars so operators can tune without changing code.
            _mode_map = {
                "adaptive": OrchestrationMode.ADAPTIVE,
                "conservative": OrchestrationMode.CONSERVATIVE,
                "aggressive": OrchestrationMode.AGGRESSIVE,
            }
            _alloc_map = {
                "risk_parity": AllocationMethod.RISK_PARITY,
                "equal_weight": AllocationMethod.EQUAL_WEIGHT,
                "performance_based": AllocationMethod.PERFORMANCE_BASED,
                "kelly_criterion": AllocationMethod.KELLY_CRITERION,
            }
            _mode_key = os.environ.get("ORCHESTRATION_MODE", "adaptive").lower()
            _alloc_key = os.environ.get("ALLOCATION_METHOD", "risk_parity").lower()
            orchestration_mode = _mode_map.get(_mode_key, OrchestrationMode.ADAPTIVE)
            allocation_method = _alloc_map.get(_alloc_key, AllocationMethod.RISK_PARITY)

            l09_engine = None
            if self.mode != "paper":
                try:
                    from Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine import (
                        get_unified_regime_engine,
                    )

                    l09_engine = get_unified_regime_engine(
                        {"defer_attribution_until_after_first_regime": True}
                    )
                    self.logger.debug(
                        "✅ L09 UnifiedRegimeEngine initialized for StrategyOrchestrator"
                    )
                except Exception as l09_exc:
                    self.logger.warning(
                        "⚠️ L09 UnifiedRegimeEngine unavailable for StrategyOrchestrator "
                        "(fallback heuristic mode): %s",
                        l09_exc,
                    )
            elif not self.dry_run:
                self.logger.info(
                    "Paper mode: deferring L09 UnifiedRegimeEngine initialization "
                    "until after orchestrator startup"
                )

            self.orchestrator = StrategyOrchestrator(
                base_capital=base_capital,
                orchestration_mode=orchestration_mode,
                allocation_method=allocation_method,
                event_manager=self.em,
                regime_engine=l09_engine,
            )
            if hasattr(self.orchestrator, "set_decision_audit_context"):
                self.orchestrator.set_decision_audit_context(
                    run_mode=self.mode,
                    source_context="session_supervisor",
                    session_id=self.session_id or f"{self.mode}-unknown",
                )
            self.orchestrator.set_live_engine(self.engine)
            # Inject the already-started and (if non-live) force-synced RiskManager so
            # D31's lazy resolver doesn't create a second fresh un-synced instance and
            # reject every signal with risk_state_cold.
            if self.risk is not None and hasattr(self.orchestrator, "set_risk_manager"):
                self.orchestrator.set_risk_manager(self.risk)
                self.logger.debug("✅ RiskManager injected into StrategyOrchestrator")
            # In paper mode we intentionally skip OrderManager mid-walk.
            # This avoids accidental live-endpoint order submissions when
            # OrderManager auto-creates a Tradier client from environment.
            if self.mode == "paper":
                self.logger.info(
                    "Paper mode: skipping OrderManager wiring; "
                    "dispatch will use engine -> PaperBroker path"
                )
                if hasattr(self.orchestrator, "emit_decision_audit_marker"):
                    self.orchestrator.emit_decision_audit_marker(
                        "order_manager_skipped_paper_mode",
                        detail=(
                            "mid-walk disabled in paper mode; "
                            "using engine/PaperBroker dispatch"
                        ),
                    )
            else:
                # v27 SPEC-6: wire OrderManager in live mode so D31's
                # _dispatch_approved_signal can use the mid-price walk path.
                try:
                    from Spyder.SpyderB_Broker.SpyderB02_OrderManager import OrderManager
                    # Reuse the already-constructed Tradier client from the broker
                    # phase if available, so we don't open a second session.
                    tradier_client = getattr(self.broker, "tradier", None)
                    om = OrderManager(tradier_client=tradier_client)
                    self.orchestrator.set_order_manager(om)
                    self._components.append(om)
                    self.logger.debug("✅ OrderManager wired to StrategyOrchestrator")
                except Exception as om_exc:
                    self.logger.error(
                        "❌ OrderManager wiring failed (mid-price walk disabled, "
                        "orders will fall back to market through LiveEngine): %s",
                        om_exc,
                    )
            self.orchestrator.start_orchestration(
                defer_initial_strategy_activation=(self.mode == "paper")
            )
            if hasattr(self.orchestrator, "emit_decision_audit_marker"):
                self.orchestrator.emit_decision_audit_marker(
                    "session_started",
                    detail=f"mode={self.mode}; source=session_supervisor",
                )
            self._components.append(self.orchestrator)
            if self.mode == "paper" and not self.dry_run:
                self._start_deferred_orchestrator_regime_engine_initialization(
                    self.orchestrator
                )
            self.logger.debug("✅ StrategyOrchestrator started")
            return True
        except Exception as exc:
            self.logger.error("❌ StrategyOrchestrator failed: %s", exc)
            return False

    def _start_deferred_orchestrator_regime_engine_initialization(
        self,
        orchestrator: Any,
    ) -> None:
        """Attach L09 to the paper-mode orchestrator after startup returns."""

        def _hydrate() -> None:
            try:
                if self._deferred_l09_cancel.wait(_PAPER_ORCHESTRATOR_L09_DEFER_SECONDS):
                    return
                from Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine import (
                    create_unified_regime_engine,
                )

                l09_engine = create_unified_regime_engine(
                    _PAPER_ORCHESTRATOR_L09_DEFER_CONFIG
                )
                if (
                    self._deferred_l09_cancel.is_set()
                    or not self._running
                    or self.orchestrator is not orchestrator
                ):
                    return

                if hasattr(orchestrator, "set_regime_engine"):
                    orchestrator.set_regime_engine(l09_engine)
                else:
                    setattr(orchestrator, "_l09_engine", l09_engine)

                self.logger.info(
                    "✅ L09 UnifiedRegimeEngine attached to StrategyOrchestrator after startup"
                )
            except Exception as l09_exc:
                self.logger.warning(
                    "⚠️ Deferred L09 UnifiedRegimeEngine initialization failed: %s",
                    l09_exc,
                )
            finally:
                if self._deferred_l09_thread is threading.current_thread():
                    self._deferred_l09_thread = None

        self._deferred_l09_thread = threading.Thread(
            target=_hydrate,
            daemon=True,
            name="SpyderR12DeferredL09Init",
        )
        self._deferred_l09_thread.start()

    def _start_liveness_monitor(self) -> None:
        """Start the LivenessMonitor (v14 O1/O9/A13)."""
        try:
            from Spyder.SpyderR_Runtime.SpyderR05_LivenessMonitor import (
                create_liveness_monitor,
            )

            self.liveness = create_liveness_monitor(
                event_manager=self.em, engine=self.engine
            )
            self.liveness.start()
            self._components.append(self.liveness)
            self.logger.debug("✅ LivenessMonitor started")
        except Exception as exc:
            self.logger.warning("⚠️ LivenessMonitor non-fatal: %s", exc)

    def _start_exit_monitor(self) -> None:
        try:
            from Spyder.SpyderR_Runtime.SpyderR14_ExitMonitor import create_exit_monitor
            from Spyder.SpyderP_PortfolioMgmt import (
                get_global_portfolio_manager,
            )

            def _resolve_portfolio_manager() -> Any | None:
                portfolio_manager = get_global_portfolio_manager()
                if portfolio_manager is None and self.engine is not None:
                    portfolio_manager = getattr(self.engine, "portfolio_manager", None)
                return portfolio_manager

            portfolio_manager = _resolve_portfolio_manager()
            if portfolio_manager is None:
                self.logger.info(
                    "ℹ️ ExitMonitor starting without PortfolioManager; will adopt one lazily"
                )

            strategy_map = (
                getattr(self.orchestrator, "active_strategies", {})
                if self.orchestrator is not None
                else {}
            )
            self.exit_monitor = create_exit_monitor(
                portfolio_manager=portfolio_manager,
                strategy_map=strategy_map,
                event_manager=self.em,
                portfolio_manager_provider=(
                    _resolve_portfolio_manager if portfolio_manager is None else None
                ),
            )
            self.exit_monitor.start()
            self._components.append(self.exit_monitor)
            self.logger.debug("✅ ExitMonitor started")
        except Exception as exc:
            self.logger.warning("⚠️ ExitMonitor non-fatal: %s", exc)

    def _boot_orphan_sweep(self) -> None:
        """O-2: Trigger one synthetic ExitMonitor sweep immediately after boot.

        Surfaces any pre-existing broker positions that are not claimed by a
        registered strategy (e.g. positions left open after a crash).  The
        sweep is fire-and-forget — failures are logged but never re-raised.
        """
        if self.exit_monitor is None:
            self._log_startup_profile("boot_orphan_sweep_skipped_no_exit_monitor")
            return
        try:
            self._log_startup_profile("boot_orphan_sweep_begin")
            # P1-3: Skip sweep if no strategies are loaded — nothing to reconcile
            # against, and orphan alerts on a cold boot are misleading.
            if self.orchestrator is not None:
                active = getattr(self.orchestrator, "active_strategies", None) or {}
                if not active:
                    self.logger.warning(
                        "⏭ Boot-time orphan sweep skipped — no strategies loaded yet."
                    )
                    self._log_startup_profile("boot_orphan_sweep_skipped_no_strategies")
                    return
            # P1-3: Honour the --skip-orphan-sweep CLI flag.
            if getattr(self, "skip_orphan_sweep", False):
                self.logger.info("⏭ Boot-time orphan sweep skipped (--skip-orphan-sweep).")
                self._log_startup_profile("boot_orphan_sweep_skipped_flag")
                return
            self.exit_monitor._sweep_once()
            self._log_startup_profile("boot_orphan_sweep_end")
            self.logger.debug("✅ Boot-time orphan sweep completed")
        except Exception as exc:
            self._log_startup_profile("boot_orphan_sweep_error")
            self.logger.warning("⚠️ Boot-time orphan sweep error (non-fatal): %s", exc)

    def _run_boot_self_test(self, timeout_seconds: float = 3.0) -> bool:
        """P1-13: Verify signal-path wiring by requiring dry-run ORDER_REJECTED.

        Emits a synthetic STRATEGY_SIGNAL with ``dry_run=True`` and waits for
        an ``ORDER_REJECTED`` event carrying reason ``dry_run`` for the same
        synthetic order_id. Returns False on timeout or any hard failure.
        """
        if self.em is None:
            self._log_startup_profile("boot_self_test_failed_no_event_manager")
            self.logger.error("❌ Boot self-test failed: EventManager unavailable")
            return False

        if self.orchestrator is None:
            self._log_startup_profile("boot_self_test_failed_no_orchestrator")
            self.logger.error("❌ Boot self-test failed: StrategyOrchestrator unavailable")
            return False

        try:
            from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType
        except Exception:
            self._log_startup_profile("boot_self_test_failed_no_event_type")
            self.logger.error("❌ Boot self-test failed: unable to import EventType")
            return False

        test_order_id = f"boot-self-test-{uuid.uuid4().hex[:12]}"
        done = threading.Event()
        result_ok = {"value": False}
        self._log_startup_profile("boot_self_test_begin")

        def _on_order_rejected(event: Any) -> None:
            data = (getattr(event, "data", None) or {})
            event_order_id = str(data.get("order_id") or "")
            if event_order_id != test_order_id:
                return

            reason = str(
                data.get("reason") or (data.get("result") or {}).get("reason") or ""
            ).lower()
            if reason == "dry_run":
                result_ok["value"] = True
                done.set()

        handler_id = self.em.subscribe(EventType.ORDER_REJECTED, _on_order_rejected)
        try:
            published = self.em.emit(
                EventType.STRATEGY_SIGNAL,
                {
                    "order_id": test_order_id,
                    "strategy_id": "BOOT_SELF_TEST",
                    "symbol": "SPY",
                    "action": "buy",
                    "quantity": 1,
                    "dry_run": True,
                    "source": "SessionSupervisor",
                },
                source="SessionSupervisor",
            )
            if not published:
                self._log_startup_profile("boot_self_test_publish_failed")
                self.logger.error("❌ Boot self-test failed: STRATEGY_SIGNAL not published")
                return False
            self._log_startup_profile("boot_self_test_signal_emitted")

            if not done.wait(timeout=timeout_seconds):
                self._log_startup_profile("boot_self_test_timeout")
                self.logger.error(
                    "❌ Boot self-test failed: ORDER_REJECTED(reason=dry_run) not observed within %.1fs",  # noqa: E501
                    timeout_seconds,
                )
                return False

            if not result_ok["value"]:
                self._log_startup_profile("boot_self_test_wrong_reason")
                self.logger.error("❌ Boot self-test failed: rejection reason was not dry_run")
                return False

            self._log_startup_profile("boot_self_test_rejected_dry_run")
            self.logger.debug("✅ Boot self-test passed (order_id=%s)", test_order_id)
            return True
        finally:
            try:
                self.em.unsubscribe(handler_id)
            except Exception:
                pass

    # --------------------------------------------------------------------------
    # PRIVATE — helpers
    # --------------------------------------------------------------------------

    @staticmethod
    def _is_truthy_env(raw_value: Optional[str]) -> bool:
        """Return ``True`` when an env-var string is an enabled/true token."""
        return str(raw_value or "").strip().lower() in {"1", "true", "yes", "on"}

    def _validate_live_only_tradier_policy(self) -> tuple[bool, str]:
        """Reject startup unless all Tradier routes are explicitly live-only."""
        violations: list[str] = []

        broker_env = str(os.getenv("TRADIER_ENVIRONMENT", "live")).strip().lower()
        if broker_env not in {"live", "production"}:
            violations.append(f"TRADIER_ENVIRONMENT={broker_env}")

        market_data_env = str(
            os.getenv("TRADIER_MARKET_DATA_ENVIRONMENT", broker_env or "live")
        ).strip().lower()
        if market_data_env not in {"live", "production"}:
            violations.append(f"TRADIER_MARKET_DATA_ENVIRONMENT={market_data_env}")

        if self._is_truthy_env(os.getenv("SPYDER_ALLOW_SANDBOX_MARKET_DATA")):
            violations.append("SPYDER_ALLOW_SANDBOX_MARKET_DATA=true")

        if violations:
            return False, ", ".join(violations)
        return True, ""

    def _begin_startup_profile(self) -> None:
        """Start env-gated startup timing for late-session profiling."""
        if not self._startup_profile_enabled:
            return
        self._startup_profile_started_at = time.perf_counter()
        self._log_startup_profile("start_entered")

    def _log_startup_profile(self, stage: str) -> None:
        """Emit a startup timing marker when profiling is enabled."""
        if not self._startup_profile_enabled:
            return
        started_at = self._startup_profile_started_at
        if started_at is None:
            return
        self.logger.info(
            "⏱ SessionSupervisor startup %s at %.3fs",
            stage,
            time.perf_counter() - started_at,
        )

    def _end_startup_profile(self) -> None:
        """Clear startup profiling state after startup or rollback ends."""
        self._startup_profile_started_at = None

    def _abort(self, failed_component: str) -> bool:
        self._log_startup_profile(f"abort_{failed_component}")
        self.logger.error(
            "❌ Session aborted — %s failed to start.  "
            "Cleaning up already-started components.",
            failed_component,
        )
        # Reverse-stop whatever started successfully.
        for component in reversed(self._components):
            try:
                component.stop()
            except Exception:
                pass
        # Note: EM singleton not stopped here — see stop().
        self._end_startup_profile()
        return False

    @staticmethod
    def _normalize_position_rows(pos_resp: Any) -> list[dict[str, Any]]:
        """Normalize mixed broker/tracker position payloads into row dicts."""
        if isinstance(pos_resp, list):
            return [dict(pos) for pos in pos_resp if isinstance(pos, dict)]

        if isinstance(pos_resp, dict):
            if "positions" in pos_resp:
                raw = (pos_resp.get("positions") or {}).get("position", [])
                if isinstance(raw, dict):
                    raw = [raw]
                return [dict(pos) for pos in raw if isinstance(pos, dict)]

            rows: list[dict[str, Any]] = []
            for symbol, pos in pos_resp.items():
                if isinstance(pos, dict):
                    row = dict(pos)
                else:
                    row = {
                        "quantity": getattr(pos, "quantity", 0),
                        "average_fill_price": getattr(pos, "average_fill_price", 0.0),
                    }
                row.setdefault("symbol", str(symbol))
                rows.append(row)
            return rows

        return []

    def _get_positions_for_flatten(self) -> list[dict[str, Any]]:
        """Resolve flatten inventory from the broker first, then paper-local state."""
        raw = self._normalize_position_rows(getattr(self.broker, "get_positions", lambda: [])())
        if raw or self.mode != "paper":
            return raw

        tracker = getattr(self, "position_tracker", None)
        if tracker is not None and hasattr(tracker, "get_positions"):
            try:
                raw = self._normalize_position_rows(tracker.get_positions())
            except Exception as exc:
                self.logger.warning("_get_positions_for_flatten tracker lookup failed: %s", exc)
                raw = []
            if raw:
                self.logger.warning(
                    "Using PositionTracker inventory for paper flatten (%d position(s))",
                    len(raw),
                )
                return raw

        engine = getattr(self, "engine", None)
        if engine is not None and hasattr(engine, "get_active_positions_snapshot"):
            try:
                raw = self._normalize_position_rows(engine.get_active_positions_snapshot())
            except Exception as exc:
                self.logger.warning("_get_positions_for_flatten engine lookup failed: %s", exc)
                raw = []
            if raw:
                self.logger.warning(
                    "Using LiveEngine inventory for paper flatten (%d position(s))",
                    len(raw),
                )
                return raw

        return []

    def _submit_flatten_close(self, symbol: str, qty: int, reason: str) -> dict[str, Any]:
        """Submit a flatten close, carrying signed paper quantity when supported."""
        broker = self.broker
        close_kwargs = {
            "urgency": "IMMEDIATE",
            "reason": reason,
        }

        if self.mode == "paper":
            close_kwargs["position_quantity"] = qty

        verified_close = getattr(broker, "close_position_verified", None)
        if callable(verified_close):
            try:
                return verified_close(
                    symbol,
                    timeout_s=10.0,
                    **close_kwargs,
                )
            except TypeError:
                close_kwargs.pop("position_quantity", None)
                return verified_close(
                    symbol,
                    timeout_s=10.0,
                    **close_kwargs,
                )

        close_position = getattr(broker, "close_position")
        try:
            return close_position(symbol, **close_kwargs)
        except TypeError:
            close_kwargs.pop("position_quantity", None)
            return close_position(symbol, **close_kwargs)

    def _flatten_positions(self) -> None:
        """Best-effort position flatten before shutdown.

        Calls ``broker.get_positions()`` to enumerate live positions, then
        submits a ``close_position()`` market order for each non-zero holding.
        Errors on individual legs are caught and logged so a single failure
        cannot block shutdown of the remaining positions.
        """
        try:
            raw = self._get_positions_for_flatten()

            if not raw:
                self.logger.info("_flatten_positions: no open positions — nothing to do")
                return

            self.logger.warning("Flattening %d open position(s)\u2026", len(raw))
            unverified: list[str] = []
            for pos in raw:
                symbol: str = pos.get("symbol", "")
                qty: int = int(pos.get("quantity", 0))
                if not symbol or qty == 0:
                    continue
                try:
                    result = self._submit_flatten_close(
                        symbol,
                        qty,
                        reason="session_flatten",
                    )
                    if hasattr(self.broker, "close_position_verified"):
                        status = (result or {}).get("status")
                        order_id = (
                            ((result or {}).get("order") or {})
                            .get("order", {})
                            .get("id", "?")
                        )
                        if status != "verified":
                            unverified.append(symbol)
                            self.logger.error(
                                "Flatten UNVERIFIED for %s (qty=%s) — reason=%s id=%s",
                                symbol,
                                qty,
                                (result or {}).get("reason"),
                                order_id,
                            )
                        else:
                            self.logger.info(
                                "Flatten VERIFIED for %s (qty=%s) — broker id=%s",
                                symbol, qty, order_id,
                            )
                    else:
                        order_id = (result or {}).get("order", {}).get("id", "?")
                        self.logger.info(
                            "Flatten order submitted for %s (qty=%s) — broker id=%s",
                            symbol, qty, order_id,
                        )
                except Exception as exc:
                    self.logger.error(
                        "_flatten_positions: failed to close %s: %s", symbol, exc
                    )
                    unverified.append(symbol)

            # A23 (v14): any unverified close is a safety problem worth a
            # kill-switch — position may still be live on the broker.
            if unverified:
                try:
                    from Spyder.SpyderA_Core.SpyderA05_EventManager import (
                        EventType,
                        get_event_manager,
                    )
                    get_event_manager().emit(
                        EventType.KILL_SWITCH,
                        {
                            "reason": "flatten_unverified",
                            "symbols": unverified,
                        },
                        source="R12",
                    )
                except Exception as exc:
                    self.logger.error(
                        "R12: failed to emit KILL_SWITCH after unverified flatten: %s",
                        exc,
                    )
        except Exception as exc:
            self.logger.warning("_flatten_positions raised: %s", exc)

    def _on_flatten_request(self, event: Any) -> None:
        """Handle FLATTEN_REQUEST events from scheduler/risk layers."""
        payload = (getattr(event, "data", None) or {}) if event is not None else {}
        flatten_type = str(payload.get("type") or "").strip().lower()
        reason = str(payload.get("reason") or "flatten_request")

        self.logger.warning(
            "Received FLATTEN_REQUEST type=%s reason=%s",
            flatten_type or "unspecified",
            reason,
        )

        if flatten_type == "broker_cutoff_flatten_guard":
            closed = self._flatten_at_risk_short_options(reason=reason)
            self.logger.warning(
                "Broker cutoff flatten guard closed %d at-risk short option symbol(s)",
                closed,
            )
            return

        self._flatten_positions()

    def _flatten_at_risk_short_options(self, reason: str) -> int:
        """Best-effort flatten of short option positions only."""
        try:
            raw = self._get_positions_for_flatten()

            if not raw:
                self.logger.info("_flatten_at_risk_short_options: no open positions")
                return 0

            closed = 0
            for pos in raw:
                symbol = str(pos.get("symbol") or "").strip()
                qty = self._safe_int(pos.get("quantity", 0))

                if not symbol or qty >= 0:
                    continue
                if not self._looks_like_option_symbol(symbol):
                    continue

                try:
                    result = self._submit_flatten_close(symbol, qty, reason=reason)
                    if hasattr(self.broker, "close_position_verified"):
                        status = (result or {}).get("status")
                        if status == "verified":
                            closed += 1
                        else:
                            self.logger.error(
                                "At-risk short option flatten unverified for %s: %s",
                                symbol,
                                (result or {}).get("reason"),
                            )
                    else:
                        closed += 1
                except Exception as exc:
                    self.logger.error("Failed to flatten at-risk short option %s: %s", symbol, exc)

            return closed
        except Exception as exc:
            self.logger.error("_flatten_at_risk_short_options failed: %s", exc)
            return 0

    @staticmethod
    def _safe_int(value: Any) -> int:
        """Convert mixed quantity payloads from broker responses into int."""
        try:
            return int(float(value))
        except Exception:
            return 0

    @staticmethod
    def _looks_like_option_symbol(symbol: str) -> bool:
        """Heuristic option symbol check for OCC/Tradier-style contracts."""
        upper = symbol.upper()
        if "_" in upper:
            return True
        return len(upper) >= 15 and ("C" in upper or "P" in upper)


# ==============================================================================
# NULL BROKER STUB
# ==============================================================================


class _NullBroker:
    """
    Minimal paper broker stub used when no Tradier credentials are available.

    All orders are immediately accepted and virtually filled for paper mode.
    """

    def submit_order(self, order: Any) -> dict:  # noqa: ANN401
        return {"status": "accepted", "order": {"id": "paper-0"}}

    def place_order(self, *args: Any, **kwargs: Any) -> dict:  # noqa: ANN401
        """Accept the call but emit a RISK_VIOLATION so the UI/alerts fire immediately.

        A NullBroker should only exist in paper mode (no credentials).  If it
        is reached in live mode something went wrong during broker init — we
        must not silently swallow orders.
        """
        try:
            from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType
            get_event_manager().emit(
                event_type=EventType.RISK_VIOLATION,
                data={
                    "type": "NULL_BROKER_ORDER",
                    "message": (
                        "_NullBroker.place_order called — no real broker is connected. "
                        "Order was NOT submitted to any exchange."
                    ),
                    "order_args": args,
                    "order_kwargs": {k: v for k, v in kwargs.items() if k != "credentials"},
                },
                source="_NullBroker",
            )
        except Exception:
            pass  # Must not raise inside a broker call
        return {"order": {"id": "null-0"}, "status": "null_broker"}

    def get_order(self, order_id: Any) -> dict:  # noqa: ANN401
        return {"order": {"status": "filled", "avg_fill_price": 0.0, "exec_quantity": 1}}

    def get_orders(self) -> list:
        return []

    def cancel_order(self, order_id: Any) -> bool:  # noqa: ANN401
        return True

    def get_positions(self) -> list:
        return []

    def close_position(
        self,
        symbol: str,
        urgency: str = "IMMEDIATE",
        reason: str = "close_position",
        force: bool = False,
    ) -> dict:  # noqa: ANN401
        """Paper stub: log and accept without hitting any exchange."""
        return {"order": {"id": "null-close-0"}, "status": "null_broker"}

    def get_account(self) -> dict:
        return {"account": {"type": "paper", "buying_power": 100_000.0}}

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass


# ==============================================================================
# FACTORY
# ==============================================================================


def create_session_supervisor(
    mode: Literal["paper", "live"],
    symbols: Optional[List[str]] = None,
    dry_run: bool = False,
    skip_orphan_sweep: bool = False,
) -> SessionSupervisor:
    """
    Factory that constructs a :class:`SessionSupervisor`.

    Args:
        mode: ``"paper"`` or ``"live"``.
        symbols: Symbols to watch.  Uses ``FEED_SYMBOLS`` env-var when omitted.
        dry_run: When ``True``, ``place_order`` calls are suppressed and logged
            instead of being forwarded to the broker.  Use for integration tests
            and rehearsal runs without live/paper order submission.
        skip_orphan_sweep: When ``True``, the boot-time orphan sweep is
            skipped (P1-3).  Pass ``args.skip_orphan_sweep`` from the CLI.

    Returns:
        A new, not-yet-started ``SessionSupervisor``.
    """
    supervisor = SessionSupervisor(mode=mode, symbols=symbols, dry_run=dry_run,
                                   skip_orphan_sweep=skip_orphan_sweep)
    # C3 (v18): register the instance as the module-level singleton so that
    # other modules (e.g. D31.add_strategy) can look it up via
    # get_session_supervisor() without a circular import.
    set_session_supervisor(supervisor)
    return supervisor


# Module-level reference to the active supervisor instance, set by the caller
# after ``create_session_supervisor`` so that other modules (e.g. D31) can
# retrieve it without creating a circular import cycle.
_active_supervisor: "SessionSupervisor | None" = None


def get_session_supervisor() -> "SessionSupervisor | None":
    """Return the currently active ``SessionSupervisor``, or ``None``."""
    return _active_supervisor


def set_session_supervisor(supervisor: "SessionSupervisor | None") -> None:
    """Register (or clear) the module-level active supervisor reference."""
    global _active_supervisor
    _active_supervisor = supervisor
