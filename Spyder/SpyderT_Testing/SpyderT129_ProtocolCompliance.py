#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT129_ProtocolCompliance.py
Purpose: Runtime protocol compliance tests for recently-touched series
Author: SPYDER Trading System
Year Created: 2026
Last Updated: 2026-04-14

Module Description:
    Fast-running contract tests that would have caught the v5/v3 audit
    findings at merge time:
      - E01 RiskManager missing validate_signal() and the wrong
        get_risk_metrics() return type relative to RiskManagerProtocol.
      - F10 MarketRegimeDetector returning empty IndicatorSnapshot stubs
        that passed structural Protocol check but delivered no data.
      - C04 MarketInternals referencing non-existent MarketCondition.UNKNOWN.

    These tests rely on runtime-checkable Protocols plus a handful of
    semantic assertions (return type, shape, non-empty where required).
    Keep them cheap — no network, no broker, no GUI imports.
"""

from __future__ import annotations

import unittest
from typing import Any, Optional


class E01RiskManagerProtocolTest(unittest.TestCase):
    """Verify SpyderE01 RiskManager satisfies E00 RiskManagerProtocol."""

    def test_risk_manager_exposes_validate_signal(self) -> None:
        from Spyder.SpyderE_Risk.SpyderE01_RiskManager import RiskManager

        self.assertTrue(
            hasattr(RiskManager, "validate_signal"),
            "E01 RiskManager must implement validate_signal() per E00 protocol",
        )

    def test_risk_manager_factory_accepts_tradier_client(self) -> None:
        from Spyder.SpyderE_Risk.SpyderE01_RiskManager import create_risk_manager, RiskConfig

        rm = create_risk_manager(
            RiskConfig(enable_real_time_monitoring=False),
            connect_api=None,
            tradier_client=None,
        )
        self.assertIsNotNone(rm)
        self.assertIsNone(rm.tradier_client)


class F10RegimeDetectorStubContractTest(unittest.TestCase):
    """F10 is a regime detector; it must NOT silently return empty indicators."""

    def test_calculate_all_indicators_returns_none(self) -> None:
        from Spyder.SpyderF_Analysis.SpyderF10_MarketRegimeDetector import MarketRegimeDetector

        detector = MarketRegimeDetector()
        result = detector.calculate_all_indicators("SPY")
        self.assertIsNone(
            result,
            "F10 must return None (not an empty snapshot) — callers should "
            "route indicator requests to F01 IndicatorEngine",
        )


class C04MarketConditionEnumTest(unittest.TestCase):
    """C04 must only reference MarketCondition members that actually exist."""

    def test_get_current_condition_returns_valid_enum(self) -> None:
        from Spyder.SpyderC_MarketData.SpyderC04_MarketInternals import (
            MarketInternals,
            MarketCondition,
        )

        internals = MarketInternals()
        # Must not raise AttributeError from .UNKNOWN lookup.
        condition = internals.get_current_condition()
        self.assertIsInstance(condition, MarketCondition)


class F00AnalyticsProtocolSurfaceTest(unittest.TestCase):
    """F00 surface must match implementors — catches rename drift."""

    def test_protocol_exports_renamed_methods(self) -> None:
        from Spyder.SpyderF_Analysis import SpyderF00_AnalysisProtocol as protocol

        self.assertTrue(hasattr(protocol, "AnalyticsProviderProtocol"))
        proto: Any = protocol.AnalyticsProviderProtocol
        # The v5 rename moved from get_indicator_snapshot -> calculate_all_indicators.
        self.assertTrue(
            hasattr(proto, "calculate_all_indicators")
            or "calculate_all_indicators" in getattr(proto, "__abstractmethods__", set())
            or "calculate_all_indicators" in dir(proto),
            "F00 AnalyticsProviderProtocol must expose calculate_all_indicators",
        )


class RegimeCanonicalWiringTest(unittest.TestCase):
    """Verify that no production module calls E21/M06 regime APIs directly
    when L09 UnifiedRegimeEngine is available, per Overview §1."""

    def test_d30_regime_gated_selector_prefers_l09(self) -> None:
        """D30 must declare L09 as primary regime source (fallback to E21 is OK)."""
        import ast
        import pathlib

        d30_path = pathlib.Path(__file__).resolve().parents[1] / "SpyderD_Strategies" / "SpyderD30_RegimeGatedSelector.py"
        source = d30_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        # Collect all import aliases
        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)

        self.assertIn(
            "UnifiedRegimeEngine",
            imported_names,
            "D30 must import UnifiedRegimeEngine from L09 (canonical regime source)",
        )
        # E21 import is allowed as a fallback but L09 must be declared first
        l09_lineno: int | None = None
        e21_lineno: int | None = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if "SpyderL09" in node.module or "L09_Unified" in node.module:
                    l09_lineno = node.lineno
                if "SpyderE21" in node.module:
                    e21_lineno = node.lineno
        if l09_lineno is not None and e21_lineno is not None:
            self.assertLess(
                l09_lineno,
                e21_lineno,
                "D30 must import L09 before E21 (L09 is the canonical primary source)",
            )

    def test_y01_market_sense_agent_prefers_l09(self) -> None:
        """Y01 MarketSenseAgent must import L09 and try it before E21."""
        import pathlib

        y01_path = pathlib.Path(__file__).resolve().parents[1] / "SpyderY_AutoAgents" / "SpyderY01_MarketSenseAgent.py"
        source = y01_path.read_text(encoding="utf-8")

        self.assertIn(
            "L09_AVAILABLE",
            source,
            "Y01 must declare L09_AVAILABLE flag (signals canonical regime wiring)",
        )
        # L09 import block should appear before E21 import block
        l09_idx = source.find("L09_AVAILABLE")
        e21_idx = source.find("HMM_AVAILABLE")
        self.assertLess(
            l09_idx,
            e21_idx,
            "Y01 must check L09 availability before E21 (L09 is canonical primary)",
        )


class EndToEndHappyPathTest(unittest.TestCase):
    """P2-3 — End-to-end integration: strategy signal → orchestrator → broker → PM → ExitMonitor.

    Uses PaperBroker (no network) and a mock PortfolioManager so the test
    runs hermetically and quickly.  The goal is to exercise the real wiring
    between R15, R13, R14 and P01 without requiring live market data.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_event_manager():
        from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager
        em = get_event_manager()
        if not em.is_running:
            em.start()
        return em

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_paper_broker_place_order_returns_ack(self) -> None:
        """R15 PaperBroker.place_order() must return a dict with 'order' key."""
        from Spyder.SpyderR_Runtime.SpyderR15_PaperBroker import PaperBroker

        broker = PaperBroker()
        result = broker.place_order(
            symbol="SPY",
            side="buy",
            quantity=1,
            order_type="market",
        )
        self.assertIsInstance(result, dict, "place_order must return a dict")
        self.assertIn("order", result, "place_order result must contain 'order' key")

    def test_fill_reconciler_tracks_paper_order(self) -> None:
        """R13 FillReconciler.track() must accept a PaperBroker order without raising."""
        import unittest.mock as mock
        from Spyder.SpyderR_Runtime.SpyderR13_FillReconciler import FillReconciler
        from Spyder.SpyderR_Runtime.SpyderR15_PaperBroker import PaperBroker

        em = self._make_event_manager()
        broker = PaperBroker()
        result = broker.place_order(symbol="SPY", side="buy", quantity=1, order_type="market")
        tradier_id = result.get("order", {}).get("id", "paper-001")

        reconciler = FillReconciler(broker=broker, event_manager=em)
        # Should not raise
        reconciler.track(order_id="spyder-001", tradier_order_id=tradier_id, order_type="market")
        self.assertEqual(reconciler.tracked_count, 1)

    def test_exit_monitor_sweep_with_registered_position(self) -> None:
        """R14 ExitMonitor._sweep_once() must handle a portfolio position without crashing.

        A strategy registered in the strategy_map should suppress the orphan path.
        """
        import unittest.mock as mock
        from Spyder.SpyderR_Runtime.SpyderR14_ExitMonitor import ExitMonitor

        em = self._make_event_manager()

        # Build a minimal fake portfolio manager with one open position
        fake_pm = mock.MagicMock()
        fake_pm.portfolio_positions = {
            "SPY240620C00500000": {
                "symbol": "SPY240620C00500000",
                "quantity": 1.0,
                "cost_basis": 3.50,
                "current_price": 3.60,
                "unrealized_pnl": 10.0,
                "strategy_id": "test_strategy",
            }
        }

        # Build a strategy that says HOLD for the position
        fake_strategy = mock.MagicMock()
        fake_strategy.check_exit.return_value = None  # hold

        monitor = ExitMonitor(
            portfolio_manager=fake_pm,
            strategy_map={"test_strategy": fake_strategy},
            event_manager=em,
        )

        # _sweep_once must complete without raising
        monitor._sweep_once()

        # strategy.check_exit was called once for the position
        fake_strategy.check_exit.assert_called_once()

    def test_exit_monitor_orphan_position_emits_event(self) -> None:
        """R14 ExitMonitor._sweep_once() must flag positions with no strategy owner."""
        import unittest.mock as mock
        from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType
        from Spyder.SpyderR_Runtime.SpyderR14_ExitMonitor import ExitMonitor

        em = self._make_event_manager()
        received: list[Any] = []
        try:
            em.subscribe(EventType.RISK_VIOLATION, lambda e: received.append(e))
        except Exception:
            pass  # event subscription optional for this test

        fake_pm = mock.MagicMock()
        fake_pm.portfolio_positions = {
            "SPY_ORPHAN": {
                "symbol": "SPY_ORPHAN",
                "quantity": 2.0,
                "cost_basis": 1.0,
                "current_price": 0.5,
                "unrealized_pnl": -100.0,
                "strategy_id": "ghost_strategy",  # not registered
            }
        }

        monitor = ExitMonitor(
            portfolio_manager=fake_pm,
            strategy_map={},  # no strategies registered
            event_manager=em,
        )
        monitor._sweep_once()
        # The orphan should have been recorded in _orphan_alerted
        self.assertIn("ghost_strategy", monitor._orphan_alerted)

    def test_strategy_orchestrator_instantiates_and_has_registry(self) -> None:
        """P0-1 regression — StrategyOrchestrator must instantiate and expose available_strategies."""
        from Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator import StrategyOrchestrator

        orch = StrategyOrchestrator(event_manager=None)
        self.assertIsNotNone(orch)
        self.assertTrue(
            hasattr(orch, "available_strategies"),
            "StrategyOrchestrator must have available_strategies after __init__",
        )
        self.assertTrue(
            hasattr(orch, "active_strategies"),
            "StrategyOrchestrator must have active_strategies after __init__",
        )

    def test_strategy_orchestrator_modules_available(self) -> None:
        """O-8 / I-5 — SPYDER_MODULES_AVAILABLE must be True after a clean import.

        Fails on any stale soft-import (e.g. the PerformanceMetrics / StrategySignal
        names that used to block D31 from subscribing to events — audit v10 P0-A).
        """
        from Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator import (
            SPYDER_MODULES_AVAILABLE,
        )
        self.assertTrue(
            SPYDER_MODULES_AVAILABLE,
            "SPYDER_MODULES_AVAILABLE is False — D31 has a stale soft-import that "
            "would disable all event subscriptions (audit v10 P0-A).",
        )

    def test_strategy_orchestrator_subscribes_to_events(self) -> None:
        """O-8 — After construction, D31 must hold live subscriptions for STRATEGY_SIGNAL.

        A D31 that cannot subscribe is silent: strategies generate signals that
        nobody dispatches to the broker (audit v10 P0-A, deeper consequence).
        """
        from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType, get_event_manager
        from Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator import StrategyOrchestrator

        em = get_event_manager()
        if not em.is_running:
            em.start()

        before = len(em.handlers.get(EventType.STRATEGY_SIGNAL, []))
        StrategyOrchestrator(event_manager=em)
        after = len(em.handlers.get(EventType.STRATEGY_SIGNAL, []))

        self.assertGreater(
            after, before,
            "StrategyOrchestrator did not subscribe to STRATEGY_SIGNAL — "
            "EventType may be None (audit v10 P0-A hardening failed).",
        )

    def test_strategy_signal_dispatched_through_risk_gate(self) -> None:
        """O-7 — STRATEGY_SIGNAL dict must reach validate_signal as RiskValidationRequest.

        Regression guard for audit v10 P0-A (EventType=None, no subscriptions)
        and P0-B (raw dict passed to validate_signal, TypeError silently dropped).

        The test emits a bare signal dict, wires a strict mock risk manager that
        raises AssertionError if it receives anything other than a
        RiskValidationRequest, and confirms the signal is dispatched.
        """
        import threading
        import unittest.mock as mock

        from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType, get_event_manager
        from Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator import StrategyOrchestrator
        from Spyder.SpyderE_Risk.SpyderE00_RiskProtocol import (
            RiskValidationRequest,
            RiskValidationResult,
        )

        em = get_event_manager()
        if not em.is_running:
            em.start()

        dispatched_event = threading.Event()

        risk = mock.MagicMock()

        def strict_validate(req: object) -> RiskValidationResult:
            if not isinstance(req, RiskValidationRequest):
                raise AssertionError(
                    f"validate_signal received {type(req).__name__} instead of "
                    "RiskValidationRequest (audit v10 P0-B)"
                )
            dispatched_event.set()
            return RiskValidationResult(approved=True, risk_score=0.1)

        risk.validate_signal.side_effect = strict_validate

        orch = StrategyOrchestrator(event_manager=em)
        orch.risk_manager = risk
        orch._dispatch_approved_signal = lambda _s: None  # stub — broker not needed here

        em.emit(
            EventType.STRATEGY_SIGNAL,
            {
                "signal_id": "t-o7",
                "strategy_id": "test",
                "symbol": "SPY",
                "action": "buy",
                "quantity": 1,
                "price": 500.0,
            },
            source="test",
        )

        reached = dispatched_event.wait(timeout=2.0)
        self.assertTrue(
            reached,
            "STRATEGY_SIGNAL did not reach validate_signal within 2 s — "
            "P0-A or P0-B is still broken.",
        )


# ==============================================================================
# BLOCKER REGRESSION TESTS  (Gate v3 — one test per BLOCKER fix)
# ==============================================================================


class B1PaperBrokerClosePosTest(unittest.TestCase):
    """T129-B1: PaperBroker.close_position() submits an offsetting market order."""

    def test_close_equity_position_submits_sell_order(self) -> None:
        from Spyder.SpyderR_Runtime.SpyderR15_PaperBroker import PaperBroker

        broker = PaperBroker()
        result = broker.close_position("SPY")
        self.assertIsInstance(result, dict)
        self.assertIn("order", result, "close_position must return Tradier-shaped dict")
        order_id = result["order"]["id"]
        # Verify the offsetting order was recorded with a sell side
        order = broker._orders.get(order_id, {})
        self.assertEqual(order.get("side", ""), "sell",
                         "Equity close must use 'sell' side")

    def test_close_option_position_submits_buy_to_close_order(self) -> None:
        from Spyder.SpyderR_Runtime.SpyderR15_PaperBroker import PaperBroker

        broker = PaperBroker()
        # SPY 500C — valid OCC symbol with 0.05-increment strike (500.00)
        sym = "SPY240620C00500000"
        result = broker.close_position(sym)
        self.assertIsInstance(result, dict)
        self.assertIn("order", result)
        order = broker._orders.get(result["order"]["id"], {})
        self.assertEqual(order.get("side", ""), "buy_to_close",
                         "Option close must use 'buy_to_close' side")

    def test_close_position_returns_empty_dict_for_no_position_no_force(self) -> None:
        """close_position with force=False still submits an order (PaperBroker tracks via B03)."""
        from Spyder.SpyderR_Runtime.SpyderR15_PaperBroker import PaperBroker

        broker = PaperBroker()
        result = broker.close_position("SPY", force=False)
        # PaperBroker defers position tracking to B03; close_position always submits
        self.assertIsInstance(result, dict)


class B2SafeStopSupervisorFlattenTest(unittest.TestCase):
    """T129-B2: _safe_stop_supervisor passes flatten=True in live mode, False in paper."""

    def _make_launcher(self, mode: str):
        """Return a MainLauncher-like object with a minimal args namespace."""
        import types
        from Spyder.SpyderQ_Scripts.SpyderQ14_MainLauncher import SpyderLauncher

        args = types.SimpleNamespace(
            mode=mode,
            gui=False,
            headless=True,
            debug=False,
            safe_mode=False,
            status=False,
            module=None,
            shutdown=False,
            clear_kill_lock=False,
        )
        launcher = SpyderLauncher.__new__(SpyderLauncher)
        launcher.args = args
        launcher.logger = None
        return launcher

    def _log_info(self, *args, **kwargs):  # noqa: D401
        pass  # suppress log output in tests

    def test_live_mode_calls_stop_with_flatten_true(self) -> None:
        import unittest.mock as mock

        launcher = self._make_launcher("live")
        launcher.log_info = self._log_info
        launcher.log_error = self._log_info

        supervisor = mock.MagicMock()
        launcher._supervisor = supervisor

        launcher._safe_stop_supervisor()
        supervisor.stop.assert_called_once_with(flatten=True)

    def test_paper_mode_calls_stop_with_flatten_false(self) -> None:
        import unittest.mock as mock

        launcher = self._make_launcher("paper")
        launcher.log_info = self._log_info
        launcher.log_error = self._log_info

        supervisor = mock.MagicMock()
        launcher._supervisor = supervisor

        launcher._safe_stop_supervisor()
        supervisor.stop.assert_called_once_with(flatten=False)

    def test_no_supervisor_is_noop(self) -> None:
        launcher = self._make_launcher("live")
        launcher.log_info = self._log_info
        launcher.log_error = self._log_info
        # _supervisor not set — must not raise
        launcher._safe_stop_supervisor()


class B3AsyncTagTest(unittest.TestCase):
    """T129-B3: place_order_async forwards the tag kwarg into the underlying place_order call."""

    def test_place_order_async_passes_tag_to_place_order(self) -> None:
        import asyncio
        import unittest.mock as mock
        from Spyder.SpyderB_Broker.SpyderB40_TradierClient import TradierClient

        client = TradierClient.__new__(TradierClient)
        client.logger = mock.MagicMock()
        client._api_key = "test"
        client._base_url = "https://sandbox.tradier.com/v1"
        client._timeout = 5
        client._session = mock.MagicMock()

        captured_tags: list[Any] = []

        def fake_place_order(*args, **kwargs):
            # tag is passed positionally (8th arg after self, symbol, side, qty, type, dur, lim, stop, class, tag)
            # functools.partial passes: symbol, side, qty, order_type, duration, limit_price, stop_price, order_class, tag
            # that's args[0..8] (0-indexed), so tag = args[8]
            captured_tags.append(args[8] if len(args) > 8 else kwargs.get("tag"))
            return {"order": {"id": "999"}}

        client.place_order = fake_place_order  # type: ignore[method-assign]

        async def _run():
            result = await client.place_order_async(
                symbol="SPY",
                side="buy",
                quantity=1,
                tag="spyder-order-001",
            )
            return result

        result = asyncio.run(_run())
        self.assertEqual(captured_tags, ["spyder-order-001"],
                         "place_order_async must forward tag to place_order")
        self.assertIn("order", result)

    def test_same_tag_on_duplicate_submission(self) -> None:
        """Identical tag on two async calls — broker-side dedup key is stable."""
        import asyncio
        import unittest.mock as mock
        from Spyder.SpyderB_Broker.SpyderB40_TradierClient import TradierClient

        client = TradierClient.__new__(TradierClient)
        client.logger = mock.MagicMock()
        client._api_key = "test"
        client._base_url = "https://sandbox.tradier.com/v1"
        client._timeout = 5
        client._session = mock.MagicMock()

        tags: list[Any] = []

        def fake_place_order(*args, **kwargs):
            tags.append(args[8] if len(args) > 8 else kwargs.get("tag"))
            return {"order": {"id": "123"}}

        client.place_order = fake_place_order  # type: ignore[method-assign]

        tag = "spyder-dedup-abc"

        async def _run():
            r1 = await client.place_order_async(symbol="SPY", side="buy", quantity=1, tag=tag)
            r2 = await client.place_order_async(symbol="SPY", side="buy", quantity=1, tag=tag)
            return r1, r2

        asyncio.run(_run())
        self.assertEqual(tags, [tag, tag], "Both async calls must carry the same tag")



class B4PendingOrdersThreadSafetyTest(unittest.TestCase):
    """T129-B4: pending_orders dict is safe under concurrent access from 4 threads."""

    def test_concurrent_pending_orders_no_exception(self) -> None:
        import threading
        import time
        import unittest.mock as mock
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import LiveEngine, LiveTradingConfig

        broker = mock.MagicMock()
        broker.place_order.return_value = {"order": {"id": "B-001"}}
        risk = mock.MagicMock()
        risk.validate_signal.return_value = mock.MagicMock(approved=True, risk_score=0.0)
        config = LiveTradingConfig(account_id="TEST-ACCOUNT")

        from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager
        em = get_event_manager()
        if not em.is_running:
            em.start()

        engine = LiveEngine(
            broker_interface=broker,
            risk_manager=risk,
            config=config,
            event_manager=em,
        )

        errors: list[Exception] = []
        deadline = time.monotonic() + 3.0  # 3 s stress run

        counter = {"n": 0}
        lock = threading.Lock()

        def _register_thread():
            while time.monotonic() < deadline:
                try:
                    with lock:
                        counter["n"] += 1
                        oid = f"test-{counter['n']}"
                    with engine._pending_orders_lock:
                        engine.pending_orders[oid] = {
                            "order_id": oid,
                            "submitted_at": __import__("datetime").datetime.now(
                                __import__("zoneinfo").ZoneInfo("America/New_York")
                            ),
                        }
                except Exception as exc:
                    errors.append(exc)

        def _remove_thread():
            while time.monotonic() < deadline:
                try:
                    with engine._pending_orders_lock:
                        keys = list(engine.pending_orders.keys())
                    for k in keys[:5]:
                        engine.pending_orders.pop(k, None)
                except Exception as exc:
                    errors.append(exc)

        def _gc_thread():
            while time.monotonic() < deadline:
                try:
                    with engine._pending_orders_lock:
                        stale = [
                            k for k, v in list(engine.pending_orders.items())
                            if not isinstance(v.get("submitted_at"), __import__("datetime").datetime)
                        ]
                    for k in stale:
                        engine.pending_orders.pop(k, None)
                except Exception as exc:
                    errors.append(exc)

        def _read_thread():
            while time.monotonic() < deadline:
                try:
                    with engine._pending_orders_lock:
                        _ = len(engine.pending_orders)
                except Exception as exc:
                    errors.append(exc)

        threads = [
            threading.Thread(target=_register_thread, daemon=True),
            threading.Thread(target=_remove_thread, daemon=True),
            threading.Thread(target=_gc_thread, daemon=True),
            threading.Thread(target=_read_thread, daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(errors, [], f"Thread-safety errors: {errors}")


class B5DataFreshUnpauseTest(unittest.TestCase):
    """T129-B5: D31 unpauses on DATA_FRESH; KILL_SWITCH pause is sticky."""

    def _make_orchestrator(self):
        from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager
        from Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator import StrategyOrchestrator

        em = get_event_manager()
        if not em.is_running:
            em.start()
        orch = StrategyOrchestrator(event_manager=em)
        return orch, em

    def test_data_stale_pauses_then_data_fresh_resumes(self) -> None:
        import time
        from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType

        orch, em = self._make_orchestrator()

        # Emit DATA_STALE
        em.emit(EventType.DATA_STALE, {"reason": "test"}, source="test")
        time.sleep(0.1)
        self.assertTrue(orch._paused_stale, "Orchestrator must be paused after DATA_STALE")
        self.assertFalse(orch._paused_kill, "Kill-switch must remain clear")

        # Emit DATA_FRESH
        em.emit(EventType.DATA_FRESH, {"symbols": ["SPY"]}, source="test")
        time.sleep(0.1)
        self.assertFalse(orch._paused_stale, "Orchestrator must resume after DATA_FRESH")

    def test_kill_switch_pause_is_sticky_after_data_fresh(self) -> None:
        import time
        from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType

        orch, em = self._make_orchestrator()

        # Emit KILL_SWITCH
        em.emit(EventType.KILL_SWITCH, {"reason": "test_sticky"}, source="test")
        time.sleep(0.1)
        self.assertTrue(orch._paused_kill, "Kill-switch pause must be set")

        # Emit DATA_FRESH — must NOT clear the kill-switch pause
        em.emit(EventType.DATA_FRESH, {"symbols": ["SPY"]}, source="test")
        time.sleep(0.1)
        self.assertTrue(orch._paused_kill, "Kill-switch pause must survive DATA_FRESH (sticky)")


class E13EmergencyEmissionTest(unittest.TestCase):
    """T129-E13: DayProfitTargetEngine._emit_profit_target_emergency() emits EMERGENCY."""

    def test_emit_profit_target_emergency_fires_emergency_event(self) -> None:
        import threading
        import unittest.mock as mock
        import Spyder.SpyderE_Risk.SpyderE13_DayProfitTarget as e13_mod
        from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType, Event, get_event_manager
        from Spyder.SpyderE_Risk.SpyderE13_DayProfitTarget import DayProfitTargetEngine

        em = get_event_manager()
        if not em.is_running:
            em.start()

        received: list[Any] = []
        done = threading.Event()

        def _capture(event: Any) -> None:
            received.append(event)
            done.set()

        em.subscribe(EventType.EMERGENCY, _capture)

        engine = DayProfitTargetEngine.__new__(DayProfitTargetEngine)
        engine.logger = mock.MagicMock()
        engine.event_manager = em
        engine.target_config = None
        engine.current_progress = None

        # Ensure the module flag is set so the emit branch is taken
        orig_flag = e13_mod.SPYDER_MODULES_AVAILABLE
        e13_mod.SPYDER_MODULES_AVAILABLE = True
        # Patch Event and EventType into the module namespace in case they failed to import
        e13_mod.Event = Event
        e13_mod.EventType = EventType
        try:
            engine._emit_profit_target_emergency()
        finally:
            e13_mod.SPYDER_MODULES_AVAILABLE = orig_flag
        arrived = done.wait(timeout=1.0)

        self.assertTrue(arrived, "EMERGENCY event must be emitted within 1 s of profit target breach")
        self.assertTrue(len(received) >= 1)
        data = (getattr(received[0], "data", None) or {})
        self.assertEqual(data.get("reason"), "DAY_PROFIT_TARGET_HIT",
                         "EMERGENCY payload must carry reason=DAY_PROFIT_TARGET_HIT")


class N1KillSwitchPersistenceTest(unittest.TestCase):
    """T129-N1: _write_kill_lock writes ~/.spyder_kill_lock; launcher refuses start if present."""

    def test_on_emergency_bridge_writes_kill_lock(self) -> None:
        import json
        import tempfile
        import unittest.mock as mock
        from pathlib import Path
        from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType, get_event_manager
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import LiveEngine, LiveTradingConfig

        em = get_event_manager()
        if not em.is_running:
            em.start()

        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / ".spyder_kill_lock"

            broker = mock.MagicMock()
            risk = mock.MagicMock()
            config = LiveTradingConfig(account_id="TEST-ACCOUNT")
            engine = LiveEngine(broker_interface=broker, risk_manager=risk,
                                config=config, event_manager=em)

            # Patch the kill-lock path to a temp location so we don't pollute home dir
            engine._KILL_LOCK_PATH = lock_path  # type: ignore[attr-defined]

            engine._write_kill_lock("test_emergency")

            self.assertTrue(lock_path.exists(), "Kill-lock file must be written")
            data = json.loads(lock_path.read_text())
            self.assertIn("reason", data)
            self.assertEqual(data["reason"], "test_emergency")
            self.assertIn("ts", data)

    def test_launcher_preflight_returns_false_when_kill_lock_present(self) -> None:
        import json
        import os
        import tempfile
        import types
        import unittest.mock as mock
        from pathlib import Path
        from Spyder.SpyderQ_Scripts.SpyderQ14_MainLauncher import SpyderLauncher

        launcher = SpyderLauncher.__new__(SpyderLauncher)
        log_msgs: list[str] = []
        launcher.log_info = lambda *a, **k: log_msgs.append(str(a))
        launcher.log_error = lambda *a, **k: log_msgs.append(str(a))

        args = types.SimpleNamespace(
            mode="live",
            clear_kill_lock=False,
            gui=False, headless=True, debug=False, safe_mode=False,
            status=False, module=None, shutdown=False,
        )
        launcher.args = args

        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / ".spyder_kill_lock"
            lock_path.write_text(json.dumps({
                "reason": "test",
                "ts": "2026-04-19T00:00:00",
                "account_id": "TEST123",
            }))

            # Set required env vars and patch the lock path
            with mock.patch.dict(os.environ, {
                "LIVE_TRADING_CONFIRMED": "true",
                "TRADIER_API_KEY": "test",
                "TRADIER_ACCOUNT_ID": "TEST123",
                # A12 (v14): additional safety-config env required for live preflight
                "CLOSE_POSITIONS_ON_EMERGENCY": "true",
                "MAX_DAILY_LOSS": "500",
                "MAX_POSITION_SIZE": "100",
            }):
                # Patch Path.home() so the launcher finds our temp lock
                with mock.patch(
                    "Spyder.SpyderQ_Scripts.SpyderQ14_MainLauncher.Path"
                ) as MockPath:
                    # Make Path.home() / ".spyder_kill_lock" return our temp lock
                    mock_home_dir = mock.MagicMock()
                    MockPath.home.return_value = mock_home_dir
                    mock_home_dir.__truediv__ = lambda self, other: lock_path
                    # Also let Path("/tmp/...") work normally for PID lock
                    MockPath.side_effect = lambda *a, **k: Path(*a, **k)

                    import fcntl  # noqa: F401 — imported by _live_preflight_checks
                    result = launcher._live_preflight_checks()

            self.assertFalse(result,
                             "_live_preflight_checks must return False when kill-lock present")
            self.assertTrue(any("kill" in m.lower() or "kill-lock" in m.lower()
                                for m in log_msgs),
                            "Must log a kill-lock rejection message")


class N2TransientErrorEscalationTest(unittest.TestCase):
    """T129-N2: _broker_submit records API errors for transient connectivity failures."""

    def _make_paper_engine(self, broker, em):
        """Create a LiveEngine in PAPER mode to bypass the FillReconciler guard."""
        import unittest.mock as mock
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import LiveEngine, LiveTradingConfig, TradingMode
        risk = mock.MagicMock()
        risk.validate_signal.return_value = mock.MagicMock(approved=True, risk_score=0.0)
        config = LiveTradingConfig(account_id="TEST-ACCOUNT")
        engine = LiveEngine(broker_interface=broker, risk_manager=risk,
                            config=config, event_manager=em)
        engine.mode = TradingMode.PAPER  # bypass FillReconciler guard
        return engine

    def test_timeout_error_increments_api_error_count(self) -> None:
        import unittest.mock as mock
        from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager

        em = get_event_manager()
        if not em.is_running:
            em.start()

        broker = mock.MagicMock()
        broker.place_order.side_effect = TimeoutError("connect timeout")
        engine = self._make_paper_engine(broker, em)

        order = {
            "order_id": "test-n2",
            "symbol": "SPY",
            "side": "buy",
            "quantity": 1,
            "order_type": "market",
            "strategy_id": "test",
        }

        # _broker_submit catches TimeoutError, calls record_api_server_error, re-raises
        for _ in range(3):
            try:
                engine._broker_submit(order)
            except Exception:
                pass

        self.assertGreaterEqual(engine._api_error_count, 3,
                                "3 TimeoutErrors must register 3 API server errors")

    def test_threshold_errors_trigger_api_panic_mode(self) -> None:
        """After API_PANIC_THRESHOLD transient errors, engine enters panic mode."""
        import os
        import unittest.mock as mock
        from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager

        em = get_event_manager()
        if not em.is_running:
            em.start()

        broker = mock.MagicMock()
        broker.place_order.side_effect = ConnectionError("network down")
        engine = self._make_paper_engine(broker, em)
        threshold = int(os.environ.get("API_PANIC_THRESHOLD", "3"))

        order = {
            "order_id": "test-n2b",
            "symbol": "SPY",
            "side": "buy",
            "quantity": 1,
            "order_type": "market",
            "strategy_id": "test",
        }
        for _ in range(threshold):
            try:
                engine._broker_submit(order)
            except Exception:
                pass

        self.assertTrue(engine._api_panic_mode,
                        f"After {threshold} transient errors _api_panic_mode must be True")


class N3OrphanOrderTest(unittest.TestCase):
    """T129-N3: FillReconciler emits ORDER_ORPHANED and writes orphans.jsonl after MAX errors."""

    def test_orphan_event_emitted_once_after_max_consecutive_errors(self) -> None:
        import threading
        import tempfile
        import unittest.mock as mock
        from pathlib import Path
        from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType, get_event_manager
        import Spyder.SpyderR_Runtime.SpyderR13_FillReconciler as r13_module
        from Spyder.SpyderR_Runtime.SpyderR13_FillReconciler import FillReconciler, MAX_CONSECUTIVE_ERRORS
        from Spyder.SpyderR_Runtime.SpyderR15_PaperBroker import PaperBroker

        em = get_event_manager()
        if not em.is_running:
            em.start()

        orphan_events: list[Any] = []
        done = threading.Event()

        def _capture(event: Any) -> None:
            orphan_events.append(event)
            done.set()

        em.subscribe(EventType.ORDER_ORPHANED, _capture)

        # Broker that always raises on get_order
        broker = mock.MagicMock(spec=PaperBroker)
        broker.get_order.side_effect = ConnectionError("simulated network failure")

        with tempfile.TemporaryDirectory() as tmp:
            dead_letter = Path(tmp) / "orphans.jsonl"
            # Patch ORPHAN_DEAD_LETTER_PATH inside the module
            original_path = r13_module.ORPHAN_DEAD_LETTER_PATH
            r13_module.ORPHAN_DEAD_LETTER_PATH = dead_letter

            try:
                reconciler = FillReconciler(broker=broker, event_manager=em)
                reconciler.track(order_id="spyder-orphan-test",
                                 tradier_order_id="PAPER-999999",
                                 order_type="market")

                # Poll enough times to exceed MAX_CONSECUTIVE_ERRORS
                # _poll_one takes an entry; grab it from the internal dict
                for _ in range(MAX_CONSECUTIVE_ERRORS + 2):
                    with reconciler._lock:
                        entries = list(reconciler._tracked.values())
                    for entry in entries:
                        reconciler._poll_one(entry)

                arrived = done.wait(timeout=2.0)

                # Check file while tempdir still exists
                self.assertTrue(arrived, "ORDER_ORPHANED must be emitted within 2 s")
                self.assertEqual(len(orphan_events), 1, "ORDER_ORPHANED must be emitted exactly once")
                self.assertTrue(dead_letter.exists(), "orphans.jsonl dead-letter file must be written")
                import json
                line = json.loads(dead_letter.read_text().strip().splitlines()[-1])
                self.assertEqual(line["order_id"], "spyder-orphan-test")
            finally:
                r13_module.ORPHAN_DEAD_LETTER_PATH = original_path
        self.assertEqual(line["order_id"], "spyder-orphan-test")


class P113BootSelfTestTest(unittest.TestCase):
    """T129-P1-13: SessionSupervisor._run_boot_self_test() succeeds when wiring is intact."""

    def test_boot_self_test_returns_true_with_wired_orchestrator(self) -> None:
        import time
        import unittest.mock as mock
        from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager
        from Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator import StrategyOrchestrator
        from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import SessionSupervisor

        em = get_event_manager()
        if not em.is_running:
            em.start()

        # Give D31 a moment to subscribe to STRATEGY_SIGNAL
        orch = StrategyOrchestrator(event_manager=em)
        time.sleep(0.05)

        sup = SessionSupervisor.__new__(SessionSupervisor)
        sup.logger = mock.MagicMock()
        sup.em = em
        sup.orchestrator = orch
        sup.dry_run = True
        sup.mode = "paper"

        result = sup._run_boot_self_test(timeout_seconds=5.0)
        self.assertTrue(result,
                        "Boot self-test must return True when orchestrator is wired to EventManager")

    def test_boot_self_test_returns_false_without_orchestrator(self) -> None:
        import unittest.mock as mock
        from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import SessionSupervisor

        sup = SessionSupervisor.__new__(SessionSupervisor)
        sup.logger = mock.MagicMock()
        sup.em = None
        sup.orchestrator = None
        sup.dry_run = False
        sup.mode = "paper"

        result = sup._run_boot_self_test(timeout_seconds=1.0)
        self.assertFalse(result, "Boot self-test must fail when EventManager is None")


# =============================================================================
# v14 BLOCKER regression tests (A1–A6)
# =============================================================================

def _make_live_engine_for_v14(broker=None):
    """Helper: construct a LiveEngine with minimal mocked deps for v14 tests."""
    import unittest.mock as mock
    from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import LiveEngine, LiveTradingConfig
    from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager

    broker = broker if broker is not None else mock.MagicMock()
    risk = mock.MagicMock()
    risk.validate_signal.return_value = mock.MagicMock(approved=True, risk_score=0.0)
    cfg = LiveTradingConfig(account_id="TEST-ACCOUNT")
    em = get_event_manager()
    if not em.is_running:
        em.start()
    return LiveEngine(
        broker_interface=broker,
        risk_manager=risk,
        config=cfg,
        event_manager=em,
    )


class A1ActivePositionsThreadSafetyTest(unittest.TestCase):
    """T129-A1: active_positions is safe under concurrent monitor + emergency close."""

    def test_monitor_and_emergency_close_are_thread_safe(self) -> None:
        import threading
        import unittest.mock as mock

        broker = mock.MagicMock()
        # Broker returns a rotating batch of positions per poll.
        broker.get_positions.side_effect = lambda: [
            {"symbol": f"SYM{i}", "id": f"pid-{i}",
             "entry_price": 1.0, "current_price": 1.0}
            for i in range(20)
        ]
        broker.close_position.return_value = {"status": "ok"}

        engine = _make_live_engine_for_v14(broker=broker)
        errors: list[Exception] = []

        def _monitor_spin() -> None:
            for _ in range(200):
                try:
                    engine._monitor_positions()
                except Exception as exc:  # pragma: no cover
                    errors.append(exc)

        def _emergency_spin() -> None:
            for _ in range(200):
                try:
                    engine._emergency_close_all_positions()
                except Exception as exc:  # pragma: no cover
                    errors.append(exc)

        threads = [
            threading.Thread(target=_monitor_spin, daemon=True),
            threading.Thread(target=_emergency_spin, daemon=True),
            threading.Thread(target=_monitor_spin, daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(errors, [], f"Concurrency errors: {errors}")

    def test_get_active_positions_snapshot_is_independent(self) -> None:
        engine = _make_live_engine_for_v14()
        engine.active_positions["SPY"] = {"symbol": "SPY", "quantity": 1}
        snap = engine.get_active_positions_snapshot()
        snap["SPY"]["quantity"] = 999
        self.assertEqual(engine.active_positions["SPY"]["quantity"], 1,
                         "snapshot must be independent of the live dict")


class A2ResolveOrderFutureIdempotentTest(unittest.TestCase):
    """T129-A2/A11: _resolve_order_future is idempotent under double-resolve."""

    def test_double_resolve_does_not_raise(self) -> None:
        import concurrent.futures

        engine = _make_live_engine_for_v14()
        fut: concurrent.futures.Future = concurrent.futures.Future()
        engine.pending_orders["oid-1"] = {"order": {"id": "oid-1"}, "future": fut}

        engine._resolve_order_future("oid-1", {"id": "oid-1"}, {"status": "filled", "n": 1})
        # Second resolve: simulate a reconciler re-emit. Must not raise.
        engine._resolve_order_future("oid-1", {"id": "oid-1"}, {"status": "filled", "n": 2})

        self.assertTrue(fut.done())
        self.assertEqual(fut.result()["n"], 1, "first resolution wins — idempotent")

    def test_resolve_is_thread_safe(self) -> None:
        import concurrent.futures
        import threading

        engine = _make_live_engine_for_v14()
        errors: list[Exception] = []

        for i in range(50):
            oid = f"oid-{i}"
            fut: concurrent.futures.Future = concurrent.futures.Future()
            engine.pending_orders[oid] = {"order": {"id": oid}, "future": fut}

        def _spin(offset: int) -> None:
            for i in range(50):
                try:
                    engine._resolve_order_future(
                        f"oid-{i}", {"id": f"oid-{i}"}, {"status": "filled", "src": offset}
                    )
                except Exception as exc:  # pragma: no cover
                    errors.append(exc)

        threads = [threading.Thread(target=_spin, args=(k,), daemon=True) for k in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(errors, [], f"Concurrent resolve raised: {errors}")


class A3CancelAllPopNotDelTest(unittest.TestCase):
    """T129-A3: _cancel_all_pending_orders uses pop() so concurrent pops don't KeyError."""

    def test_cancel_all_tolerates_concurrent_removal(self) -> None:
        import unittest.mock as mock

        broker = mock.MagicMock()

        def _cancel_side_effect(oid):
            # Simulate a reconciler terminal-event handler racing us and popping
            # the entry between our snapshot and our own pop.
            engine.pending_orders.pop(oid, None)
            return {"status": "cancelled"}

        broker.cancel_order.side_effect = _cancel_side_effect

        engine = _make_live_engine_for_v14(broker=broker)
        for i in range(5):
            engine.pending_orders[f"oid-{i}"] = {"order": {"id": f"oid-{i}"}}

        # Must not raise KeyError.
        engine._cancel_all_pending_orders()
        self.assertEqual(len(engine.pending_orders), 0)


class A4A5TimezoneAwareTimestampsTest(unittest.TestCase):
    """T129-A4/A5: dead-letter & state-save timestamps are timezone-aware."""

    def test_r13_orphan_payload_is_tz_aware(self) -> None:
        from datetime import datetime
        import json as _json
        import tempfile
        import unittest.mock as mock
        from pathlib import Path

        import Spyder.SpyderR_Runtime.SpyderR13_FillReconciler as r13

        rec = mock.MagicMock()
        # Patch the module-level path to a temp file so the test does not
        # touch logs/orphans.jsonl in the repo.
        tmp = Path(tempfile.mkstemp(suffix=".jsonl")[1])
        with mock.patch.object(r13, "ORPHAN_DEAD_LETTER_PATH", tmp):
            entry = mock.MagicMock()
            entry.order_id = "o-1"
            entry.tradier_order_id = "t-1"
            entry.consecutive_errors = 5
            fr = r13.FillReconciler.__new__(r13.FillReconciler)
            fr.logger = mock.MagicMock()
            fr._em = mock.MagicMock()
            fr._emit_orphaned(entry, last_error="boom")
        payload = _json.loads(tmp.read_text().strip())
        # "+00:00" is the isoformat rendering for datetime.now(timezone.utc).
        self.assertIn("+00:00", payload["ts"],
                      f"R13 orphan ts not tz-aware: {payload['ts']!r}")
        self.assertFalse(payload["ts"].endswith("Z"),
                         "naive isoformat + 'Z' should be gone (A4)")
        # Parses cleanly as an aware datetime.
        parsed = datetime.fromisoformat(payload["ts"])
        self.assertIsNotNone(parsed.tzinfo)

    def test_b03_save_state_is_tz_aware(self) -> None:
        import json as _json
        import tempfile
        import unittest.mock as mock
        from datetime import datetime
        from pathlib import Path

        from Spyder.SpyderB_Broker.SpyderB03_PositionTracker import PositionTracker

        tmp = Path(tempfile.mkstemp(suffix=".json")[1])
        tracker = PositionTracker.__new__(PositionTracker)
        tracker.logger = mock.MagicMock()
        tracker._position_lock = __import__("threading").RLock()
        tracker.positions = {}
        tracker._state_path = tmp

        self.assertTrue(tracker.save_state(tmp))
        payload = _json.loads(tmp.read_text())
        self.assertIn("+00:00", payload["saved_at"],
                      f"B03 saved_at not tz-aware: {payload['saved_at']!r}")
        parsed = datetime.fromisoformat(payload["saved_at"])
        self.assertIsNotNone(parsed.tzinfo)


class A6FillPriceGuardTest(unittest.TestCase):
    """T129-A6: E01 rejects POSITION_UPDATED events with invalid fill_price."""

    def _make_risk_manager(self):
        import unittest.mock as mock
        from Spyder.SpyderE_Risk.SpyderE01_RiskManager import RiskManager

        rm = RiskManager.__new__(RiskManager)
        rm.logger = mock.MagicMock()
        rm._risk_lock = __import__("threading").RLock()
        rm._positions = {}
        rm.metrics = {}
        return rm

    def _make_event(self, **data):
        import unittest.mock as mock
        ev = mock.MagicMock()
        ev.data = data
        return ev

    def test_rejects_zero_fill_price(self) -> None:
        rm = self._make_risk_manager()
        rm._on_position_updated(self._make_event(symbol="SPY", quantity=1, fill_price=0.0))
        self.assertNotIn("SPY", rm._positions,
                         "position created with fill_price=0 must be rejected")

    def test_rejects_none_fill_price(self) -> None:
        rm = self._make_risk_manager()
        rm._on_position_updated(self._make_event(symbol="SPY", quantity=1, fill_price=None))
        self.assertNotIn("SPY", rm._positions)

    def test_rejects_negative_fill_price(self) -> None:
        rm = self._make_risk_manager()
        rm._on_position_updated(self._make_event(symbol="SPY", quantity=1, fill_price=-1.0))
        self.assertNotIn("SPY", rm._positions)

    def test_accepts_valid_fill_price(self) -> None:
        rm = self._make_risk_manager()
        rm._on_position_updated(self._make_event(symbol="SPY", quantity=2, fill_price=123.45))
        self.assertIn("SPY", rm._positions)
        self.assertAlmostEqual(rm._positions["SPY"].market_price, 123.45)

    def test_close_out_allowed_with_missing_price(self) -> None:
        rm = self._make_risk_manager()
        # pre-seed a position so the close-out has something to pop
        from Spyder.SpyderE_Risk.SpyderE01_RiskManager import Position
        rm._positions["SPY"] = Position(
            symbol="SPY", quantity=1, market_price=10.0, market_value=10.0,
            average_fill_price=10.0, unrealized_pnl=0.0, realized_pnl=0.0,
        )
        rm._on_position_updated(self._make_event(symbol="SPY", quantity=0))
        self.assertNotIn("SPY", rm._positions, "qty=0 must close out regardless of price")


# =============================================================================
# v14 HIGH regression tests (A7–A15)
# =============================================================================


class A8CancelAllEscalationTest(unittest.TestCase):
    """T129-A8: partial cancel failures must escalate to KILL_SWITCH."""

    def test_cancel_all_escalates_on_partial_failure(self) -> None:
        import unittest.mock as mock

        from Spyder.SpyderA_Core.SpyderA05_EventManager import (
            EventType,
            get_event_manager,
        )

        broker = mock.MagicMock()
        call_count = {"n": 0}

        def _cancel(order_id):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("broker reject")
            return {"status": "ok"}

        broker.cancel_order.side_effect = _cancel
        engine = _make_live_engine_for_v14(broker=broker)
        engine.pending_orders = {"a": {}, "b": {}, "c": {}}

        em = get_event_manager()
        captured: list[dict] = []

        def _capture(evt):
            captured.append({"type": evt.event_type, "data": dict(evt.data)})

        em.subscribe(EventType.KILL_SWITCH, _capture)

        engine._cancel_all_pending_orders()

        import time
        time.sleep(0.2)

        kill_events = [c for c in captured if c["type"] is EventType.KILL_SWITCH]
        self.assertTrue(kill_events, "KILL_SWITCH must fire on partial cancel failure")
        self.assertIn("failed_order_ids", kill_events[-1]["data"])


class A9R13OrphanRecoveryTest(unittest.TestCase):
    """T129-A9: FillReconciler recovers orphans via ORDER_UN_ORPHANED + terminal event."""

    def _make_reconciler(self, broker):
        import unittest.mock as mock

        from Spyder.SpyderR_Runtime.SpyderR13_FillReconciler import FillReconciler

        rec = FillReconciler.__new__(FillReconciler)
        rec.logger = mock.MagicMock()
        rec._broker = broker
        rec._em = mock.MagicMock()
        rec._poll_cadence_market = 0.01
        rec._poll_cadence_limit = 0.01
        rec._tracked = {}
        rec._orphaned = {}
        import threading
        rec._lock = threading.Lock()
        rec._stop_event = threading.Event()
        rec._thread = None
        rec._prom = None
        return rec

    def test_orphan_recovers_to_filled(self) -> None:
        import unittest.mock as mock

        from Spyder.SpyderR_Runtime.SpyderR13_FillReconciler import _TrackedOrder
        from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType

        broker = mock.MagicMock()
        broker.get_order.return_value = {"order": {"status": "filled",
                                                   "avg_fill_price": 1.23,
                                                   "quantity": 1}}
        rec = self._make_reconciler(broker)
        entry = _TrackedOrder(
            order_id="oid-1",
            tradier_order_id="8675309",
            order_type="market",
            cadence=0.01,
        )
        rec._orphaned["8675309"] = entry

        rec._poll_orphaned(entry)

        # ORDER_UN_ORPHANED + ORDER_FILLED both emitted, and orphan dropped.
        emitted_types = [c.args[0] for c in rec._em.emit.call_args_list]
        self.assertIn(EventType.ORDER_UN_ORPHANED, emitted_types)
        self.assertIn(EventType.ORDER_FILLED, emitted_types)
        self.assertNotIn("8675309", rec._orphaned)

    def test_orphan_still_failing_stays_orphaned(self) -> None:
        import unittest.mock as mock

        from Spyder.SpyderR_Runtime.SpyderR13_FillReconciler import _TrackedOrder

        broker = mock.MagicMock()
        broker.get_order.side_effect = RuntimeError("still down")
        rec = self._make_reconciler(broker)
        entry = _TrackedOrder(
            order_id="oid-1",
            tradier_order_id="42",
            order_type="market",
            cadence=0.01,
        )
        rec._orphaned["42"] = entry

        rec._poll_orphaned(entry)

        self.assertIn("42", rec._orphaned,
                      "orphan must stay orphaned while broker still errors")
        rec._em.emit.assert_not_called()


class A10EventManagerBoundedDrainTest(unittest.TestCase):
    """T129-A10: EventManager.stop() returns within the supplied timeout."""

    def test_stop_returns_within_timeout_under_load(self) -> None:
        import time

        from Spyder.SpyderA_Core.SpyderA05_EventManager import (
            EventManager,
            EventType,
        )

        em = EventManager()
        em.start()

        # Slow handler that intentionally exceeds the timeout budget.
        def _slow(_evt):
            time.sleep(0.5)

        em.subscribe(EventType.SYSTEM_ERROR, _slow)
        for _ in range(20):
            em.emit(EventType.SYSTEM_ERROR, {"i": 1}, source="test")

        t0 = time.monotonic()
        em.stop(timeout=0.5)
        elapsed = time.monotonic() - t0

        # Must honor the bounded drain contract.
        self.assertLess(elapsed, 2.0,
                        f"stop() exceeded bounded-drain budget: {elapsed:.2f}s")


class A12LivePreflightTest(unittest.TestCase):
    """T129-A12: Q14 live preflight catches missing safety-config env vars."""

    def _make_launcher(self):
        import argparse
        import unittest.mock as mock

        from Spyder.SpyderQ_Scripts.SpyderQ14_MainLauncher import SpyderLauncher

        launcher = SpyderLauncher.__new__(SpyderLauncher)
        launcher.logger = mock.MagicMock()
        launcher.log_error = mock.MagicMock()
        launcher.log_info = mock.MagicMock()
        launcher.log_warning = mock.MagicMock()
        launcher.args = argparse.Namespace(mode="live", clear_kill_lock=False)
        return launcher

    def _base_env(self):
        return {
            "LIVE_TRADING_CONFIRMED": "true",
            "TRADIER_API_KEY": "x",
            "TRADIER_ACCOUNT_ID": "y",
            "CLOSE_POSITIONS_ON_EMERGENCY": "true",
            "MAX_DAILY_LOSS": "500",
            "MAX_POSITION_SIZE": "100",
        }

    def test_rejects_missing_emergency_close(self) -> None:
        import os
        import unittest.mock as mock

        env = self._base_env()
        env["CLOSE_POSITIONS_ON_EMERGENCY"] = "false"
        with mock.patch.dict(os.environ, env, clear=True):
            launcher = self._make_launcher()
            self.assertFalse(launcher._live_preflight_checks())

    def test_rejects_paper_account_profile_in_live_mode(self) -> None:
        import os
        import unittest.mock as mock

        env = self._base_env()
        env["ACCOUNT_PROFILE"] = "paper"
        with mock.patch.dict(os.environ, env, clear=True):
            launcher = self._make_launcher()
            self.assertFalse(launcher._live_preflight_checks())

    def test_rejects_negative_max_daily_loss(self) -> None:
        import os
        import unittest.mock as mock

        env = self._base_env()
        env["MAX_DAILY_LOSS"] = "-10"
        with mock.patch.dict(os.environ, env, clear=True):
            launcher = self._make_launcher()
            self.assertFalse(launcher._live_preflight_checks())


class A14OrderStatusTransitionTest(unittest.TestCase):
    """T129-A14: OrderStatus.validate_transition rejects invalid transitions."""

    def test_terminal_states_reject_outbound(self) -> None:
        from Spyder.SpyderB_Broker.SpyderB00_OrderTypes import OrderStatus

        for terminal in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
            for target in (OrderStatus.SUBMITTED, OrderStatus.WORKING,
                           OrderStatus.PARTIALLY_FILLED, OrderStatus.PENDING):
                self.assertFalse(
                    OrderStatus.validate_transition(terminal, target),
                    f"{terminal} → {target} should be invalid",
                )

    def test_happy_path_transitions(self) -> None:
        from Spyder.SpyderB_Broker.SpyderB00_OrderTypes import OrderStatus

        valid = [
            (OrderStatus.PENDING, OrderStatus.SUBMITTED),
            (OrderStatus.SUBMITTED, OrderStatus.WORKING),
            (OrderStatus.WORKING, OrderStatus.PARTIALLY_FILLED),
            (OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED),
            (OrderStatus.SUBMITTED, OrderStatus.CANCELLED),
            (OrderStatus.SUBMITTED, OrderStatus.REJECTED),
        ]
        for src, dst in valid:
            self.assertTrue(
                OrderStatus.validate_transition(src, dst),
                f"{src} → {dst} should be valid",
            )

    def test_transition_to_logs_but_does_not_raise(self) -> None:
        from Spyder.SpyderB_Broker.SpyderB00_OrderTypes import (
            OrderRequest, OrderAction, OrderType, OrderStatus,
            ContractDetails, SecType,
        )

        order = OrderRequest(
            contract=ContractDetails(symbol="SPY", sec_type=SecType.STOCK),
            action=OrderAction.BUY,
            total_quantity=1,
            order_type=OrderType.MARKET,
        )
        order.status = OrderStatus.FILLED  # terminal
        # Invalid: FILLED → PENDING — must not raise, must return False.
        valid = order.transition_to(OrderStatus.PENDING)
        self.assertFalse(valid)
        self.assertIs(order.status, OrderStatus.PENDING,
                      "log-only mode applies the transition regardless")


class A15StubGatedTest(unittest.TestCase):
    """T129-A15: R11/L16 abstract stubs no longer raise NotImplementedError."""

    def test_r11_strategy_adapter_defaults_do_not_raise(self) -> None:
        from datetime import datetime

        from Spyder.SpyderR_Runtime.SpyderR11_PaperStrategyRunner import StrategyAdapter

        adapter = StrategyAdapter()
        self.assertFalse(adapter.within_entry_window(datetime.now()))
        self.assertIsNone(adapter.evaluate_entry(None, None))  # type: ignore[arg-type]

    def test_l16_env_defaults_do_not_raise(self) -> None:
        import unittest.mock as mock

        from Spyder.SpyderL_ML.SpyderL16_OptionsAdjustmentRL import (
            OptionsEnvironment,
        )

        env = OptionsEnvironment.__new__(OptionsEnvironment)
        env.logger = mock.MagicMock()
        self.assertEqual(env._initialize_position(), {})
        self.assertEqual(env._calculate_position_greeks(), {})
        self.assertEqual(env._calculate_pnl(), 0.0)
        self.assertEqual(env._calculate_closing_cost(), 0.0)
        self.assertEqual(env._roll_position("up"), {})
        self.assertEqual(env._add_hedge(), {})
        self.assertEqual(env._adjust_size("up"), {})
        self.assertEqual(env._convert_position("other"), {})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
