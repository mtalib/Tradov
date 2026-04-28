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
        self.logger.info("SessionSupervisor.start() — mode=%s symbols=%s", self.mode, self.symbols)
        if self.dry_run:
            self.logger.warning("⚠️  DRY-RUN MODE — order submission is suppressed; no orders will reach the broker")  # noqa: E501

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

        # 8. LiveEngine
        if not self._start_live_engine():
            return self._abort("LiveEngine")

        # 9. StrategyOrchestrator
        if not self._start_orchestrator():
            return self._abort("StrategyOrchestrator")

        # 10. ExitMonitor — must come after orchestrator so strategy_map is populated
        self._start_exit_monitor()  # non-fatal

        # 11. LivenessMonitor — heartbeat + /healthz + deadman (v14 O1/O9/A13)
        self._start_liveness_monitor()  # non-fatal

        # O-2: One-shot orphan sweep immediately after boot to surface any
        # pre-existing broker positions not owned by a registered strategy
        # (e.g. left open after a crash).
        self._boot_orphan_sweep()

        # P1-13: Boot-time synthetic signal self-test. Fail closed if the
        # strategy signal path does not produce ORDER_REJECTED(reason=dry_run).
        if not self._run_boot_self_test(timeout_seconds=3.0):
            return self._abort("BootSelfTest")

        self._running = True
        self.logger.info("✅ SessionSupervisor fully started in %s mode", self.mode)

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
        self.logger.info("SHUTDOWN_PHASE_4_PROCESS_END")

        self.logger.info("SessionSupervisor stopped.")
        try:
            from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import (
                reset_global_portfolio_manager,
            )
            reset_global_portfolio_manager()
        except Exception:
            pass
        # C3 (v18): clear the singleton so get_session_supervisor() returns None
        # once this instance is stopped.  Prevents stale references from
        # accumulating in long-running processes that start multiple sessions.
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
            from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager
            self.em = get_event_manager()
            if not self.em.is_running:
                self.em.start()
            self.logger.info("✅ EventManager started")
            return True
        except Exception as exc:
            self.logger.error("❌ EventManager failed: %s", exc)
            return False

    def _start_data_feed(self) -> bool:
        try:
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
            self.logger.info("✅ DataFeed started — symbols: %s", self.symbols)
            return True
        except Exception as exc:
            self.logger.error("❌ DataFeed failed: %s", exc)
            return False

    def _start_freshness_monitor(self) -> bool:
        try:
            from Spyder.SpyderE_Risk.SpyderE24_DataFreshnessMonitor import create_freshness_monitor
            self.freshness_monitor = create_freshness_monitor(
                symbols=self.symbols, event_manager=self.em
            )
            self.freshness_monitor.start()
            self._components.append(self.freshness_monitor)
            self.logger.info("✅ DataFreshnessMonitor started")
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
        Paper broker: prefer PaperBroker (local, no Tradier creds needed).
        Falls back to Tradier sandbox if TRADIER_API_KEY is configured.
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
            self.logger.info("✅ PaperBroker started for paper mode")
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
            self.logger.info("✅ FillReconciler started")
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
            self.logger.info("✅ PositionTracker started")
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
            # R12-B1: register a sync stop shim so the component loop can
            # signal shutdown and join threads (RiskManager.stop is async).
            _risk = self.risk
            class _RiskStopper:
                def stop(self):
                    _risk.stop_sync()
            self._components.append(_RiskStopper())
            self.logger.info("✅ RiskManager ready and started")
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
                from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import (
                    set_global_portfolio_manager,
                )
                _pm = getattr(self.engine, "portfolio_manager", None)
                if _pm is not None:
                    set_global_portfolio_manager(_pm)
            except Exception as _pm_err:
                self.logger.debug("Could not publish global portfolio manager: %s", _pm_err)
            self._components.append(self.engine)
            self.logger.info("✅ LiveEngine started")
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
            self.orchestrator = StrategyOrchestrator(
                base_capital=base_capital,
                orchestration_mode=orchestration_mode,
                allocation_method=allocation_method,
                event_manager=self.em,
            )
            self.orchestrator.set_live_engine(self.engine)
            self.orchestrator.start_orchestration()
            self._components.append(self.orchestrator)
            self.logger.info("✅ StrategyOrchestrator started")
            return True
        except Exception as exc:
            self.logger.error("❌ StrategyOrchestrator failed: %s", exc)
            return False

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
            self.logger.info("✅ LivenessMonitor started")
        except Exception as exc:
            self.logger.warning("⚠️ LivenessMonitor non-fatal: %s", exc)

    def _start_exit_monitor(self) -> None:
        try:
            from Spyder.SpyderR_Runtime.SpyderR14_ExitMonitor import create_exit_monitor
            from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import (
                get_global_portfolio_manager,
            )

            portfolio_manager = get_global_portfolio_manager()
            if portfolio_manager is None and self.engine is not None:
                portfolio_manager = getattr(self.engine, "portfolio_manager", None)

            if portfolio_manager is None:
                try:
                    from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import (
                        create_portfolio_manager,
                        set_global_portfolio_manager,
                    )
                    portfolio_manager = create_portfolio_manager(
                        initial_capital=float(os.environ.get("BASE_CAPITAL", 100_000))
                    )
                    set_global_portfolio_manager(portfolio_manager)
                    self.logger.info("ℹ️ ExitMonitor using fallback PortfolioManager instance")
                except Exception as pm_exc:
                    self.logger.warning("⚠️ ExitMonitor fallback portfolio manager failed: %s", pm_exc)  # noqa: E501

            if portfolio_manager is None:
                self.logger.warning("⚠️ ExitMonitor skipped: portfolio manager unavailable")
                return

            strategy_map = (
                getattr(self.orchestrator, "active_strategies", {})
                if self.orchestrator is not None
                else {}
            )
            self.exit_monitor = create_exit_monitor(
                portfolio_manager=portfolio_manager,
                strategy_map=strategy_map,
                event_manager=self.em,
            )
            self.exit_monitor.start()
            self._components.append(self.exit_monitor)
            self.logger.info("✅ ExitMonitor started")
        except Exception as exc:
            self.logger.warning("⚠️ ExitMonitor non-fatal: %s", exc)

    def _boot_orphan_sweep(self) -> None:
        """O-2: Trigger one synthetic ExitMonitor sweep immediately after boot.

        Surfaces any pre-existing broker positions that are not claimed by a
        registered strategy (e.g. positions left open after a crash).  The
        sweep is fire-and-forget — failures are logged but never re-raised.
        """
        if self.exit_monitor is None:
            return
        try:
            # P1-3: Skip sweep if no strategies are loaded — nothing to reconcile
            # against, and orphan alerts on a cold boot are misleading.
            if self.orchestrator is not None:
                active = getattr(self.orchestrator, "active_strategies", None) or {}
                if not active:
                    self.logger.warning(
                        "⏭ Boot-time orphan sweep skipped — no strategies loaded yet."
                    )
                    return
            # P1-3: Honour the --skip-orphan-sweep CLI flag.
            if getattr(self, "skip_orphan_sweep", False):
                self.logger.info("⏭ Boot-time orphan sweep skipped (--skip-orphan-sweep).")
                return
            self.exit_monitor._sweep_once()
            self.logger.info("✅ Boot-time orphan sweep completed")
        except Exception as exc:
            self.logger.warning("⚠️ Boot-time orphan sweep error (non-fatal): %s", exc)

    def _run_boot_self_test(self, timeout_seconds: float = 3.0) -> bool:
        """P1-13: Verify signal-path wiring by requiring dry-run ORDER_REJECTED.

        Emits a synthetic STRATEGY_SIGNAL with ``dry_run=True`` and waits for
        an ``ORDER_REJECTED`` event carrying reason ``dry_run`` for the same
        synthetic order_id. Returns False on timeout or any hard failure.
        """
        if self.em is None:
            self.logger.error("❌ Boot self-test failed: EventManager unavailable")
            return False

        if self.orchestrator is None:
            self.logger.error("❌ Boot self-test failed: StrategyOrchestrator unavailable")
            return False

        try:
            from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType
        except Exception:
            self.logger.error("❌ Boot self-test failed: unable to import EventType")
            return False

        test_order_id = f"boot-self-test-{uuid.uuid4().hex[:12]}"
        done = threading.Event()
        result_ok = {"value": False}

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
                self.logger.error("❌ Boot self-test failed: STRATEGY_SIGNAL not published")
                return False

            if not done.wait(timeout=timeout_seconds):
                self.logger.error(
                    "❌ Boot self-test failed: ORDER_REJECTED(reason=dry_run) not observed within %.1fs",  # noqa: E501
                    timeout_seconds,
                )
                return False

            if not result_ok["value"]:
                self.logger.error("❌ Boot self-test failed: rejection reason was not dry_run")
                return False

            self.logger.info("✅ Boot self-test passed (order_id=%s)", test_order_id)
            return True
        finally:
            try:
                self.em.unsubscribe(handler_id)
            except Exception:
                pass

    # --------------------------------------------------------------------------
    # PRIVATE — helpers
    # --------------------------------------------------------------------------

    def _abort(self, failed_component: str) -> bool:
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
        return False

    def _flatten_positions(self) -> None:
        """Best-effort position flatten before shutdown.

        Calls ``broker.get_positions()`` to enumerate live positions, then
        submits a ``close_position()`` market order for each non-zero holding.
        Errors on individual legs are caught and logged so a single failure
        cannot block shutdown of the remaining positions.
        """
        try:
            pos_resp = self.broker.get_positions()
            # Tradier returns {"positions": {"position": [...]}}
            # _NullBroker / PaperBroker return a plain list.
            if isinstance(pos_resp, list):
                raw: list[Any] = pos_resp
            else:
                raw = (pos_resp.get("positions") or {}).get("position", [])
                if isinstance(raw, dict):  # single position returned as dict
                    raw = [raw]

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
                    # A23/O7 (v14): prefer the verified variant so shutdown
                    # actually confirms the close fills rather than returning
                    # on ACK. Fall back to plain close_position if the broker
                    # hasn't implemented the verified API (older PaperBroker).
                    if hasattr(self.broker, "close_position_verified"):
                        result = self.broker.close_position_verified(
                            symbol,
                            timeout_s=10.0,
                            urgency="IMMEDIATE",
                            reason="session_flatten",
                        )
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
                        result = self.broker.close_position(
                            symbol, urgency="IMMEDIATE", reason="session_flatten"
                        )
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
