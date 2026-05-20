#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT116_RSeries.py
Purpose: Unit tests for SpyderR04_LiveEngine

Coverage targets:
    R04 LiveEngine:
        - LiveTradingConfig has close_positions_on_emergency field
        - emergency_stop_all sets emergency_stop flag and EMERGENCY_STOP mode
        - emergency_stop_all calls _emergency_close_all_positions when configured
        - execute_order rejected when engine is not in TRADING state
        - execute_order rejected when daily trade limit reached
        - execute_order rejected when order quantity exceeds position size limit
        - _verify_broker_connection / _verify_account_access return False on
          ordinary Exception (not BaseException) — regression guard for bare
          except-BaseException bug
        - KeyboardInterrupt propagates from _verify_broker_connection and
          _verify_account_access (confirms except Exception, not BaseException)
        - pause_trading / resume_trading state transitions
        - get_execution_status returns expected top-level keys
        - _cancel_all_pending_orders iterates a snapshot (no RuntimeError on
          mutation of pending_orders during iteration)
        - _should_trigger_stop_loss returns True when loss >= stop_loss_pct
"""

import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_broker(account_id: str = "ACC_001"):
    """Return a MagicMock broker that satisfies LiveEngine's expectations."""
    broker = MagicMock()
    broker.is_connected.return_value = True
    broker.get_account_info.return_value = {
        "account_id": account_id,
        "trading_enabled": True,
        "buying_power": 100_000.0,
    }
    broker.get_positions.return_value = []
    broker.heartbeat.return_value = True
    broker.cancel_order.return_value = True
    broker.submit_order.return_value = {"status": "filled", "fill_time_ms": 50, "slippage": 0.0}
    broker.close_position.return_value = True
    return broker


def _make_mock_risk_manager():
    rm = MagicMock()
    rm.check_daily_limits.return_value = True
    return rm


def _make_live_engine(account_id: str = "ACC_001", close_on_emergency: bool = False):
    """Construct a LiveEngine with mocked dependencies (no threads started)."""
    from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import LiveEngine, LiveTradingConfig

    config = LiveTradingConfig(
        account_id=account_id,
        close_positions_on_emergency=close_on_emergency,
    )
    broker = _make_mock_broker(account_id)
    risk_manager = _make_mock_risk_manager()
    engine = LiveEngine(broker, risk_manager, config)
    return engine, broker, risk_manager


# ---------------------------------------------------------------------------
# R04 - LiveEngine / LiveTradingConfig
# ---------------------------------------------------------------------------


class TestR04LiveTradingConfig(unittest.TestCase):
    """LiveTradingConfig must have close_positions_on_emergency."""

    def test_close_positions_on_emergency_field_exists(self):
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import LiveTradingConfig

        cfg = LiveTradingConfig(account_id="ACC_001")
        self.assertFalse(cfg.close_positions_on_emergency)

    def test_close_positions_on_emergency_can_be_set_true(self):
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import LiveTradingConfig

        cfg = LiveTradingConfig(account_id="ACC_001", close_positions_on_emergency=True)
        self.assertTrue(cfg.close_positions_on_emergency)


class TestR04LiveEngineInstantiation(unittest.TestCase):
    """LiveEngine.__init__ must complete without errors."""

    def test_instantiation_sets_initial_state(self):
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import ExecutionState, TradingMode

        engine, _, _ = _make_live_engine()
        self.assertEqual(engine.state, ExecutionState.INITIALIZED)
        self.assertEqual(engine.mode, TradingMode.LIVE)
        self.assertFalse(engine.emergency_stop)
        self.assertEqual(engine.daily_trades, 0)

    def test_config_stored_on_engine(self):
        engine, _, _ = _make_live_engine(account_id="MY_ACCT")
        self.assertEqual(engine.config.account_id, "MY_ACCT")


class TestR04EmergencyStop(unittest.TestCase):
    """emergency_stop_all must set flag, switch mode, and conditionally close positions."""

    def test_emergency_stop_sets_emergency_flag(self):
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import TradingMode

        engine, broker, _ = _make_live_engine()
        engine.emergency_stop_all("unit test")
        self.assertTrue(engine.emergency_stop)
        self.assertEqual(engine.mode, TradingMode.EMERGENCY_STOP)

    def test_emergency_stop_without_close_does_not_call_close_position(self):
        engine, broker, _ = _make_live_engine(close_on_emergency=False)
        # Pre-populate active positions to confirm they are NOT closed
        engine.active_positions = {"SPY": {"id": 1, "symbol": "SPY"}}
        engine.emergency_stop_all("no-close test")
        broker.close_position.assert_not_called()

    def test_emergency_stop_with_close_calls_close_position(self):
        engine, broker, _ = _make_live_engine(close_on_emergency=True)
        engine.active_positions = {"SPY": {"id": 1, "symbol": "SPY"}}
        engine.emergency_stop_all("close test")
        broker.close_position.assert_called()

    def test_emergency_stop_drains_order_queue(self):
        """Order queue must be empty after emergency stop."""
        engine, _, _ = _make_live_engine()
        # Push dummy orders into the queue
        for i in range(5):
            engine.order_queue.put({"order_id": f"ORD_{i}"})
        engine.emergency_stop_all("drain test")
        self.assertTrue(engine.order_queue.empty())

    def test_emergency_stop_returns_true(self):
        engine, _, _ = _make_live_engine()
        result = engine.emergency_stop_all("return test")
        self.assertTrue(result)


class TestR04ExecuteOrderRejections(unittest.TestCase):
    """execute_order must reject orders for various safety-check failures."""

    def test_rejected_when_not_in_trading_state(self):
        """Engine starts in INITIALIZED — every order must be rejected."""
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import ExecutionState

        engine, _, _ = _make_live_engine()
        self.assertEqual(engine.state, ExecutionState.INITIALIZED)
        result = engine.execute_order({"symbol": "SPY", "quantity": 1})
        self.assertEqual(result["status"], "rejected")

    def test_rejected_when_daily_trade_limit_reached(self):
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import ExecutionState

        engine, _, _ = _make_live_engine()
        engine.state = ExecutionState.TRADING
        engine.daily_trades = engine.config.max_daily_trades  # exhaust limit
        result = engine.execute_order({"symbol": "SPY", "quantity": 1})
        self.assertEqual(result["status"], "rejected")
        self.assertIn("daily", result["reason"].lower())

    def test_rejected_when_position_size_too_large(self):
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import ExecutionState

        engine, _, _ = _make_live_engine()
        engine.state = ExecutionState.TRADING
        oversized_qty = engine.config.max_position_size + 1
        result = engine.execute_order({"symbol": "SPY", "quantity": oversized_qty})
        self.assertEqual(result["status"], "rejected")

    def test_execute_order_allows_explicit_close_when_entry_gates_would_block(self):
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import ExecutionState

        engine, broker, _ = _make_live_engine()
        engine.state = ExecutionState.TRADING
        engine._run_a02_decision_gate = MagicMock(return_value=(False, "data_gate:blocked"))
        engine._regime_allows_entry = MagicMock(return_value=(False, "regime_blocked"))
        engine._perform_order_safety_checks = MagicMock(side_effect=AssertionError("close orders must bypass entry-only safety checks"))
        engine._check_order_confirmation_required = MagicMock(side_effect=AssertionError("close orders must bypass confirmation checks"))
        engine._wait_for_execution = MagicMock(return_value={"status": "accepted"})
        engine._update_execution_metrics = MagicMock()

        result = engine.execute_order(
            {
                "symbol": "SPY260618P00699000",
                "action": "close",
                "side": "buy",
                "quantity": 1,
                "price": 4.21,
                "strategy_id": "iron_condor",
            }
        )

        self.assertEqual(result["status"], "accepted")
        engine._run_a02_decision_gate.assert_not_called()
        engine._regime_allows_entry.assert_not_called()
        engine._perform_order_safety_checks.assert_not_called()
        engine._check_order_confirmation_required.assert_not_called()
        engine._wait_for_execution.assert_called_once()
        broker.submit_order.assert_not_called()

    def test_rejected_when_a02_preflight_gate_blocks(self):
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import ExecutionState

        class _GateStub:
            def _run_decision_flow_pipeline(self, strategy_id, signal, include_execution=True):
                return False, "data_gate:stale_quote"

        engine, _, _ = _make_live_engine()
        engine.state = ExecutionState.TRADING
        engine._a02_decision_gate_enabled = True
        engine.set_trading_engine(_GateStub())

        result = engine.execute_order(
            {
                "symbol": "SPY",
                "side": "buy",
                "quantity": 1,
                "price": 2.10,
                "strategy_id": "bull_put_spread",
            }
        )
        self.assertEqual(result["status"], "rejected")
        self.assertIn("data_gate", result["reason"])

    def test_a02_preflight_gate_passes_with_gates_only_mode(self):
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import ExecutionState, SafetyCheck, SafetyCheckResult

        captures = {}

        class _GateStub:
            def _run_decision_flow_pipeline(self, strategy_id, signal, include_execution=True):
                captures["strategy_id"] = strategy_id
                captures["signal"] = signal
                captures["include_execution"] = include_execution
                return True, ""

        engine, _, _ = _make_live_engine()
        engine.state = ExecutionState.TRADING
        engine._a02_decision_gate_enabled = True
        engine.set_trading_engine(_GateStub())

        # Stop the flow after preflight so this stays a unit test and avoids broker queue path.
        engine._perform_order_safety_checks = MagicMock(
            return_value=SafetyCheck(
                check_name="test_safety",
                result=SafetyCheckResult.FAILED,
                message="unit-stop",
                timestamp=datetime.now(),
            )
        )

        result = engine.execute_order(
            {
                "symbol": "SPY",
                "side": "buy",
                "quantity": 1,
                "price": 2.10,
                "strategy_id": "bull_put_spread",
            }
        )

        self.assertEqual(result["status"], "rejected")
        self.assertTrue(captures)
        self.assertEqual(captures["strategy_id"], "bull_put_spread")
        self.assertEqual(captures["signal"]["symbol"], "SPY")
        self.assertFalse(captures["include_execution"])


class TestR04VerifyConnectionExceptionHandling(unittest.TestCase):
    """_verify_broker_connection and _verify_account_access must catch Exception but
    let KeyboardInterrupt / SystemExit propagate (i.e. they use except Exception,
    not except BaseException)."""

    def test_verify_broker_connection_returns_false_on_exception(self):
        engine, broker, _ = _make_live_engine()
        broker.is_connected.side_effect = RuntimeError("connection refused")
        result = engine._verify_broker_connection()
        self.assertFalse(result)

    def test_verify_account_access_returns_false_on_exception(self):
        engine, broker, _ = _make_live_engine()
        broker.get_account_info.side_effect = RuntimeError("auth failure")
        result = engine._verify_account_access()
        self.assertFalse(result)

    def test_verify_broker_connection_propagates_keyboard_interrupt(self):
        """KeyboardInterrupt must NOT be swallowed by _verify_broker_connection."""
        engine, broker, _ = _make_live_engine()
        broker.is_connected.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            engine._verify_broker_connection()

    def test_verify_account_access_propagates_keyboard_interrupt(self):
        """KeyboardInterrupt must NOT be swallowed by _verify_account_access."""
        engine, broker, _ = _make_live_engine()
        broker.get_account_info.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            engine._verify_account_access()


class TestR04PauseResume(unittest.TestCase):
    """pause_trading / resume_trading must transition state correctly."""

    def test_pause_from_trading_succeeds(self):
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import ExecutionState

        engine, _, _ = _make_live_engine()
        engine.state = ExecutionState.TRADING
        self.assertTrue(engine.pause_trading())
        self.assertEqual(engine.state, ExecutionState.PAUSED)

    def test_pause_from_non_trading_fails(self):
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import ExecutionState

        engine, _, _ = _make_live_engine()
        # State is INITIALIZED by default
        self.assertFalse(engine.pause_trading())

    def test_resume_from_paused_succeeds(self):
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import ExecutionState

        engine, _, _ = _make_live_engine()
        engine.state = ExecutionState.PAUSED
        self.assertTrue(engine.resume_trading())
        self.assertEqual(engine.state, ExecutionState.TRADING)

    def test_resume_from_non_paused_fails(self):
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import ExecutionState

        engine, _, _ = _make_live_engine()
        engine.state = ExecutionState.TRADING
        self.assertFalse(engine.resume_trading())


class TestR04StartTrading(unittest.TestCase):
    """start_trading must distinguish paper after-hours from true blockers."""

    def test_paper_start_trading_succeeds_after_hours_when_only_market_closed(self):
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import ExecutionState, TradingMode

        engine, _, _ = _make_live_engine(account_id="PAPER-ACCOUNT")
        engine.mode = TradingMode.PAPER
        engine.state = ExecutionState.CONNECTED
        engine._is_market_open = MagicMock(return_value=False)
        engine.risk_manager.check_daily_limits.return_value = True

        result = engine.start_trading()

        self.assertTrue(result)
        self.assertEqual(engine.state, ExecutionState.TRADING)
        self.assertIsNotNone(engine.current_session)
        self.assertEqual(engine.current_session.mode, TradingMode.PAPER)

    def test_paper_start_trading_fails_when_risk_limits_exceeded_after_hours(self):
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import ExecutionState, TradingMode

        engine, _, _ = _make_live_engine(account_id="PAPER-ACCOUNT")
        engine.mode = TradingMode.PAPER
        engine.state = ExecutionState.CONNECTED
        engine._is_market_open = MagicMock(return_value=False)
        engine.risk_manager.check_daily_limits.return_value = False

        result = engine.start_trading()

        self.assertFalse(result)
        self.assertEqual(engine.state, ExecutionState.CONNECTED)
        self.assertIsNone(engine.current_session)


class TestR04PositionHydration(unittest.TestCase):
    """Paper-mode engines should hydrate active positions from H05 when attached."""

    def test_set_session_db_ignores_paper_active_positions_without_carryover_manifest(self):
        from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import TradingMode

        with TemporaryDirectory() as tmpdir:
            db = TradingSessionDB(Path(tmpdir) / "paper_positions.db")
            db.upsert_position(
                position_id="paper:SPY",
                symbol="SPY",
                strategy="iron_condor",
                quantity=-7,
                entry_price=733.10,
                current_price=733.20,
                status="OPEN",
            )

            engine, _, _ = _make_live_engine(account_id="PAPER-ACCOUNT")
            engine.mode = TradingMode.PAPER

            engine.set_session_db(db)

            self.assertEqual(engine.active_positions, {})

    def test_set_session_db_hydrates_paper_active_positions_from_h05(self):
        from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import TradingMode

        with TemporaryDirectory() as tmpdir:
            db = TradingSessionDB(Path(tmpdir) / "paper_positions.db")
            db.upsert_position(
                position_id="paper:SPY",
                symbol="SPY",
                strategy="iron_condor",
                quantity=-7,
                entry_price=733.10,
                current_price=733.20,
                status="OPEN",
            )

            engine, _, _ = _make_live_engine(account_id="PAPER-ACCOUNT")
            engine.mode = TradingMode.PAPER

            self.assertEqual(engine.active_positions, {})

            db.save_paper_carryover_manifest(
                [
                    {
                        "position_id": "paper:SPY",
                        "symbol": "SPY",
                        "strategy": "iron_condor",
                        "quantity": -7,
                    }
                ]
            )

            engine.set_session_db(db)

            self.assertEqual(engine.active_positions["SPY"]["quantity"], -7)
            self.assertEqual(engine.active_positions["SPY"]["strategy"], "iron_condor")
            self.assertEqual(
                engine.active_positions["SPY"]["position_source"],
                "session_db_hydration",
            )

    def test_set_session_db_hydrates_current_paper_session_positions_from_h05(self):
        from Spyder.SpyderH_Storage import SpyderH05_TradingSessionDB as h05
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import TradingMode

        class _MarkerDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                current = datetime.fromisoformat("2026-05-19T14:50:14.499121+00:00")
                if tz is None:
                    return current.replace(tzinfo=None)
                return current.astimezone(tz)

        class _PositionDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                current = datetime.fromisoformat("2026-05-19T14:50:22.532676+00:00")
                if tz is None:
                    return current.replace(tzinfo=None)
                return current.astimezone(tz)

        with TemporaryDirectory() as tmpdir:
            db = h05.TradingSessionDB(Path(tmpdir) / "paper_positions.db")
            with patch.object(h05, "datetime", _MarkerDateTime):
                db.mark_paper_session_active("PAPER_20260519_105014", owner="unit-test")

            with patch.object(h05, "datetime", _PositionDateTime):
                db.upsert_position(
                    position_id="paper:SPY",
                    symbol="SPY",
                    strategy="iron_condor",
                    quantity=-7,
                    entry_price=733.10,
                    current_price=733.20,
                    status="OPEN",
                )

            engine, _, _ = _make_live_engine(account_id="PAPER-ACCOUNT")
            engine.mode = TradingMode.PAPER

            engine.set_session_db(db)

            self.assertEqual(engine.active_positions["SPY"]["quantity"], -7)
            self.assertEqual(engine.active_positions["SPY"]["strategy"], "iron_condor")
            self.assertEqual(
                engine.active_positions["SPY"]["position_source"],
                "session_db_hydration",
            )

    def test_set_session_db_falls_back_to_open_rows_when_manifest_api_is_not_callable(self):
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import TradingMode

        class _LegacyPaperDB:
            get_resume_eligible_open_positions = None

            def get_open_positions(self):
                return [
                    {
                        "symbol": "SPY",
                        "strategy": "iron_condor",
                        "quantity": -7,
                    }
                ]

        engine, _, _ = _make_live_engine(account_id="PAPER-ACCOUNT")
        engine.mode = TradingMode.PAPER

        engine.set_session_db(_LegacyPaperDB())

        self.assertEqual(engine.active_positions["SPY"]["quantity"], -7)
        self.assertEqual(engine.active_positions["SPY"]["strategy"], "iron_condor")
        self.assertEqual(
            engine.active_positions["SPY"]["position_source"],
            "session_db_hydration",
        )

    def test_monitor_positions_does_not_clear_h05_hydrated_paper_positions(self):
        from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import TradingMode

        with TemporaryDirectory() as tmpdir:
            db = TradingSessionDB(Path(tmpdir) / "paper_positions.db")
            db.upsert_position(
                position_id="paper:SPY",
                symbol="SPY",
                strategy="iron_condor",
                quantity=-7,
                entry_price=733.10,
                current_price=733.20,
                status="OPEN",
            )

            engine, broker, _ = _make_live_engine(account_id="PAPER-ACCOUNT")
            engine.mode = TradingMode.PAPER
            broker.get_positions.return_value = []

            db.save_paper_carryover_manifest(
                [
                    {
                        "position_id": "paper:SPY",
                        "symbol": "SPY",
                        "strategy": "iron_condor",
                        "quantity": -7,
                    }
                ]
            )

            engine.set_session_db(db)
            engine._monitor_positions()

            self.assertEqual(engine.active_positions["SPY"]["quantity"], -7)
            self.assertEqual(engine.active_positions["SPY"]["strategy"], "iron_condor")


class TestH05PositionPersistence(unittest.TestCase):
    """TradingSessionDB position upserts should track the latest net quantity."""

    def test_upsert_position_updates_quantity_and_entry_price(self):
        from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB

        with TemporaryDirectory() as tmpdir:
            db = TradingSessionDB(Path(tmpdir) / "positions.db")
            db.upsert_position(
                position_id="paper:SPY",
                symbol="SPY",
                strategy="iron_condor",
                quantity=-1,
                entry_price=733.50,
                current_price=733.50,
                status="OPEN",
            )
            db.upsert_position(
                position_id="paper:SPY",
                symbol="SPY",
                strategy="iron_condor",
                quantity=-4,
                entry_price=733.10,
                current_price=733.25,
                status="OPEN",
            )

            rows = db.get_open_positions()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "SPY")
        self.assertEqual(rows[0]["strategy"], "iron_condor")
        self.assertEqual(rows[0]["quantity"], -4)
        self.assertEqual(rows[0]["entry_price"], 733.10)
        self.assertEqual(rows[0]["current_price"], 733.25)

    def test_upsert_position_refreshes_opened_at_when_closed_row_reopens(self):
        from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB

        with TemporaryDirectory() as tmpdir:
            db = TradingSessionDB(Path(tmpdir) / "positions.db")
            first_opened = datetime.fromisoformat("2026-05-14T17:14:08+00:00")
            first_closed = datetime.fromisoformat("2026-05-14T18:12:04+00:00")
            reopened_at = datetime.fromisoformat("2026-05-14T18:39:04+00:00")

            db.upsert_position(
                position_id="paper:SPY260613C00783500",
                symbol="SPY260613C00783500",
                strategy="iron_condor",
                quantity=-1,
                entry_price=8.5743,
                current_price=8.5743,
                status="CLOSED",
                opened_at=first_opened,
                closed_at=first_closed,
                expiration="2026-06-13",
                strike=783.5,
                option_type="call",
            )
            db.upsert_position(
                position_id="paper:SPY260613C00783500",
                symbol="SPY260613C00783500",
                strategy="iron_condor",
                quantity=-1,
                entry_price=8.5843,
                current_price=8.5843,
                status="OPEN",
                opened_at=reopened_at,
                expiration="2026-06-13",
                strike=783.5,
                option_type="call",
            )

            rows = db.get_open_positions()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "SPY260613C00783500")
        self.assertEqual(rows[0]["status"], "OPEN")
        self.assertEqual(rows[0]["opened_at"], reopened_at.isoformat())
        self.assertIsNone(rows[0]["closed_at"])
        self.assertEqual(rows[0]["entry_price"], 8.5843)

    def test_resume_eligibility_rejects_stale_manifest_opened_at_for_reopened_position(self):
        from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB

        with TemporaryDirectory() as tmpdir:
            db = TradingSessionDB(Path(tmpdir) / "paper_positions.db")
            stale_opened = datetime.fromisoformat("2026-05-14T17:14:08+00:00")
            current_opened = datetime.fromisoformat("2026-05-14T18:39:04+00:00")

            db.upsert_position(
                position_id="paper:SPY260613C00783500",
                symbol="SPY260613C00783500",
                strategy="iron_condor",
                quantity=-1,
                entry_price=8.5843,
                current_price=8.5843,
                status="OPEN",
                opened_at=current_opened,
                expiration="2026-06-13",
                strike=783.5,
                option_type="call",
            )

            db.save_paper_carryover_manifest(
                [
                    {
                        "position_id": "paper:SPY260613C00783500",
                        "symbol": "SPY260613C00783500",
                        "strategy": "iron_condor",
                        "quantity": -1,
                        "opened_at": stale_opened.isoformat(),
                    }
                ]
            )

            self.assertEqual(db.get_resume_eligible_open_positions(), [])

            db.save_paper_carryover_manifest(
                [
                    {
                        "position_id": "paper:SPY260613C00783500",
                        "symbol": "SPY260613C00783500",
                        "strategy": "iron_condor",
                        "quantity": -1,
                        "opened_at": current_opened.isoformat(),
                    }
                ]
            )

            rows = db.get_resume_eligible_open_positions()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["opened_at"], current_opened.isoformat())


class TestR04GetExecutionStatus(unittest.TestCase):
    """get_execution_status must return a dict with expected top-level keys."""

    def test_status_structure(self):
        engine, _, _ = _make_live_engine()
        status = engine.get_execution_status()
        for key in ("state", "mode", "emergency_stop", "session", "daily_stats",
                    "pending_orders", "active_positions", "metrics"):
            self.assertIn(key, status, f"Missing key: {key}")

    def test_status_emergency_stop_is_false_initially(self):
        engine, _, _ = _make_live_engine()
        self.assertFalse(engine.get_execution_status()["emergency_stop"])

    def test_status_reflects_emergency_flag(self):
        engine, _, _ = _make_live_engine()
        engine.emergency_stop_all("status test")
        self.assertTrue(engine.get_execution_status()["emergency_stop"])


class TestR04FillAccounting(unittest.TestCase):
    """Unified R04 fill persistence should retain realized P&L for closes."""

    def test_reconciler_fill_records_realized_pnl_for_option_close(self):
        from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import TradingMode

        with TemporaryDirectory() as tmpdir:
            db = TradingSessionDB(Path(tmpdir) / "paper_accounting.db")
            engine, _, _ = _make_live_engine(account_id="PAPER-ACCOUNT")
            engine.mode = TradingMode.PAPER
            engine.set_session_db(db)
            symbol = "SPY260613P00712500"
            engine.active_positions = {
                symbol: {
                    "symbol": symbol,
                    "quantity": -1,
                    "entry_price": 8.5843,
                    "current_price": 8.5843,
                    "strategy": "iron_condor",
                }
            }
            engine.pending_orders = {
                "ORD-CLOSE-1": {
                    "order": {
                        "symbol": symbol,
                        "quantity": 1,
                        "side": "buy_to_close",
                        "strategy": "iron_condor",
                    }
                }
            }

            event = MagicMock(
                source="FillReconciler",
                data={
                    "order_id": "ORD-CLOSE-1",
                    "quantity": 1,
                    "raw": {
                        "id": "PAPER-1",
                        "symbol": symbol,
                        "avg_fill_price": 4.2921,
                        "quantity": 1,
                        "transaction_date": "2026-05-14T19:22:05+00:00",
                    },
                },
            )

            engine._on_reconciler_fill(event)

            trade = db.get_recent_trades(limit=1)[0]

        self.assertEqual(trade["symbol"], symbol)
        self.assertAlmostEqual(trade["realized_pnl"], 429.22, places=2)

    def test_position_updated_persists_realized_pnl_on_close(self):
        from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import TradingMode

        with TemporaryDirectory() as tmpdir:
            db = TradingSessionDB(Path(tmpdir) / "paper_positions.db")
            engine, _, _ = _make_live_engine(account_id="PAPER-ACCOUNT")
            engine.mode = TradingMode.PAPER
            engine.set_session_db(db)
            symbol = "SPY260613P00712500"
            engine.active_positions = {
                symbol: {
                    "symbol": symbol,
                    "quantity": -1,
                    "entry_price": 8.5843,
                    "current_price": 8.5843,
                    "strategy": "iron_condor",
                    "opened_at": datetime.fromisoformat("2026-05-14T15:25:02+00:00"),
                }
            }
            engine.pending_orders = {
                "ORD-CLOSE-2": {
                    "order": {
                        "symbol": symbol,
                        "quantity": 1,
                        "side": "buy_to_close",
                        "strategy": "iron_condor",
                    }
                }
            }

            event = MagicMock(
                source="PositionTracker",
                data={
                    "symbol": symbol,
                    "quantity": 0,
                    "fill_price": 4.2921,
                    "order_id": "ORD-CLOSE-2",
                },
            )

            engine._on_position_updated(event)

            with db._connect() as conn:
                row = conn.execute(
                    "SELECT symbol, status, current_price, realized_pnl FROM positions WHERE position_id = ?",
                    (f"paper:{symbol}",),
                ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["symbol"], symbol)
        self.assertEqual(row["status"], "CLOSED")
        self.assertAlmostEqual(row["current_price"], 4.2921, places=4)
        self.assertAlmostEqual(row["realized_pnl"], 429.22, places=2)

    def test_position_updated_persists_close_when_hydrated_opened_at_is_string(self):
        from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import TradingMode

        with TemporaryDirectory() as tmpdir:
            db = TradingSessionDB(Path(tmpdir) / "paper_positions.db")
            engine, _, _ = _make_live_engine(account_id="PAPER-ACCOUNT")
            engine.mode = TradingMode.PAPER
            engine.set_session_db(db)
            symbol = "SPY260613P00712500"
            engine.active_positions = {
                symbol: {
                    "symbol": symbol,
                    "quantity": -1,
                    "entry_price": 8.5843,
                    "current_price": 8.5843,
                    "strategy": "iron_condor",
                    "opened_at": "2026-05-14T15:25:02+00:00",
                }
            }
            engine.pending_orders = {
                "ORD-CLOSE-3": {
                    "order": {
                        "symbol": symbol,
                        "quantity": 1,
                        "side": "buy_to_close",
                        "strategy": "iron_condor",
                    }
                }
            }

            event = MagicMock(
                source="PositionTracker",
                data={
                    "symbol": symbol,
                    "quantity": 0,
                    "fill_price": 4.2921,
                    "order_id": "ORD-CLOSE-3",
                },
            )

            engine._on_position_updated(event)

            with db._connect() as conn:
                row = conn.execute(
                    "SELECT symbol, status, opened_at, current_price, realized_pnl FROM positions WHERE position_id = ?",
                    (f"paper:{symbol}",),
                ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["symbol"], symbol)
        self.assertEqual(row["status"], "CLOSED")
        self.assertEqual(row["opened_at"], "2026-05-14T15:25:02+00:00")
        self.assertAlmostEqual(row["current_price"], 4.2921, places=4)
        self.assertAlmostEqual(row["realized_pnl"], 429.22, places=2)


class TestR04PaperMarkToMarket(unittest.TestCase):
    """Paper-mode monitoring should mark positions to market and snapshot equity."""

    def test_monitor_positions_marks_paper_positions_and_records_snapshot(self):
        from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import TradingMode

        with TemporaryDirectory() as tmpdir:
            db = TradingSessionDB(Path(tmpdir) / "paper_mark_to_market.db")
            engine, broker, _ = _make_live_engine(account_id="PAPER-ACCOUNT")
            engine.mode = TradingMode.PAPER
            engine.set_session_db(db)
            symbol = "SPY260613P00712500"
            broker.get_positions.return_value = []
            broker.get_account_balances.return_value = {
                "account": {"balance": 100000.0}
            }
            broker._last_prices = {symbol: 4.2921}
            db.record_trade(
                symbol=symbol,
                trade_type="STO",
                side="sell",
                quantity=1,
                price=8.5843,
                strategy="iron_condor",
            )
            engine.active_positions = {
                symbol: {
                    "symbol": symbol,
                    "quantity": -1,
                    "entry_price": 8.5843,
                    "current_price": 8.5843,
                    "strategy": "iron_condor",
                }
            }

            engine._monitor_positions()

            open_position = engine.active_positions[symbol]
            latest_snapshot = db.get_latest_snapshot()
            open_rows = db.get_open_positions()

        self.assertAlmostEqual(open_position["current_price"], 4.2921, places=4)
        self.assertAlmostEqual(open_position["unrealized_pnl"], 429.22, places=2)
        self.assertEqual(len(open_rows), 1)
        self.assertAlmostEqual(open_rows[0]["current_price"], 4.2921, places=4)
        self.assertAlmostEqual(open_rows[0]["unrealized_pnl"], 429.22, places=2)
        self.assertIsNotNone(latest_snapshot)
        self.assertAlmostEqual(latest_snapshot["unrealized_pnl"], 429.22, places=2)
        self.assertAlmostEqual(latest_snapshot["equity"], 100429.22, places=2)

    def test_monitor_positions_fetches_live_quotes_for_paper_option_positions(self):
        from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import TradingMode

        with TemporaryDirectory() as tmpdir:
            db = TradingSessionDB(Path(tmpdir) / "paper_mark_to_market.db")
            engine, broker, _ = _make_live_engine(account_id="PAPER-ACCOUNT")
            engine.mode = TradingMode.PAPER
            engine.set_session_db(db)
            symbol = "SPY260618P00700000"
            quote_client = MagicMock()
            quote_client.get_quotes.return_value = {
                "quotes": {
                    "quote": {
                        "symbol": symbol,
                        "bid": 4.2000,
                        "ask": 4.3842,
                    }
                }
            }
            engine._paper_option_quote_client = quote_client
            broker.get_positions.return_value = []
            broker.get_account_balances.return_value = {
                "account": {"balance": 100000.0}
            }
            broker._last_prices = {}
            db.record_trade(
                symbol=symbol,
                trade_type="STO",
                side="sell",
                quantity=1,
                price=8.5843,
                strategy="iron_condor",
            )
            engine.active_positions = {
                symbol: {
                    "symbol": symbol,
                    "quantity": -1,
                    "entry_price": 8.5843,
                    "current_price": 8.5843,
                    "strategy": "iron_condor",
                }
            }

            engine._monitor_positions()

            open_position = engine.active_positions[symbol]
            latest_snapshot = db.get_latest_snapshot()
            open_rows = db.get_open_positions()

        quote_client.get_quotes.assert_called_once_with([symbol])
        self.assertAlmostEqual(broker._last_prices[symbol], 4.2921, places=4)
        self.assertAlmostEqual(open_position["current_price"], 4.2921, places=4)
        self.assertAlmostEqual(open_position["unrealized_pnl"], 429.22, places=2)
        self.assertEqual(len(open_rows), 1)
        self.assertAlmostEqual(open_rows[0]["current_price"], 4.2921, places=4)
        self.assertAlmostEqual(open_rows[0]["unrealized_pnl"], 429.22, places=2)
        self.assertIsNotNone(latest_snapshot)
        self.assertAlmostEqual(latest_snapshot["unrealized_pnl"], 429.22, places=2)
        self.assertAlmostEqual(latest_snapshot["equity"], 100429.22, places=2)

    def test_monitor_positions_repairs_invalid_paper_option_symbol_to_live_chain(self):
        from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import TradingMode

        with TemporaryDirectory() as tmpdir:
            db = TradingSessionDB(Path(tmpdir) / "paper_mark_to_market.db")
            engine, broker, _ = _make_live_engine(account_id="PAPER-ACCOUNT")
            engine.mode = TradingMode.PAPER
            engine.set_session_db(db)
            invalid_symbol = "SPY260618P00699500"
            repaired_symbol = "SPY260618P00699000"
            quote_client = MagicMock()
            quote_client.get_quotes.return_value = {
                "quotes": {
                    "quote": {
                        "symbol": repaired_symbol,
                        "bid": 4.2000,
                        "ask": 4.3842,
                    }
                }
            }
            engine._paper_option_quote_client = quote_client
            engine._paper_option_chain_cache = {
                ("SPY", "2026-06-18"): {
                    "put": [689.0, 690.0, 699.0, 700.0],
                    "call": [770.0, 780.0],
                }
            }
            engine._paper_option_chain_cache_at = {("SPY", "2026-06-18"): time.time()}
            broker.get_positions.return_value = []
            broker.get_account_balances.return_value = {
                "account": {"balance": 100000.0}
            }
            broker._last_prices = {}
            db.record_trade(
                symbol=invalid_symbol,
                trade_type="STO",
                side="sell",
                quantity=1,
                price=8.5843,
                strategy="iron_condor",
                expiration="2026-06-18",
                strike=699.5,
                option_type="put",
            )
            db.upsert_position(
                position_id=f"paper:{invalid_symbol}",
                symbol=invalid_symbol,
                strategy="iron_condor",
                quantity=-1,
                entry_price=8.5843,
                current_price=8.5843,
                status="OPEN",
                expiration="2026-06-18",
                strike=699.5,
                option_type="put",
            )
            engine.active_positions = {
                invalid_symbol: {
                    "symbol": invalid_symbol,
                    "quantity": -1,
                    "entry_price": 8.5843,
                    "current_price": 8.5843,
                    "strategy": "iron_condor",
                    "expiration": "2026-06-18",
                    "strike": 699.5,
                    "option_type": "put",
                }
            }

            engine._monitor_positions()

            latest_snapshot = db.get_latest_snapshot()
            open_rows = db.get_open_positions()
            with db._connect() as conn:
                old_row = conn.execute(
                    "SELECT symbol FROM positions WHERE position_id = ?",
                    (f"paper:{invalid_symbol}",),
                ).fetchone()

        quote_client.get_quotes.assert_called_once_with([repaired_symbol])
        self.assertNotIn(invalid_symbol, engine.active_positions)
        self.assertIn(repaired_symbol, engine.active_positions)
        repaired_position = engine.active_positions[repaired_symbol]
        self.assertAlmostEqual(repaired_position["strike"], 699.0, places=4)
        self.assertAlmostEqual(repaired_position["current_price"], 4.2921, places=4)
        self.assertAlmostEqual(broker._last_prices[repaired_symbol], 4.2921, places=4)
        self.assertEqual(len(open_rows), 1)
        self.assertEqual(open_rows[0]["position_id"], f"paper:{repaired_symbol}")
        self.assertEqual(open_rows[0]["symbol"], repaired_symbol)
        self.assertAlmostEqual(open_rows[0]["strike"], 699.0, places=4)
        self.assertIsNone(old_row)
        self.assertIsNotNone(latest_snapshot)
        self.assertAlmostEqual(latest_snapshot["unrealized_pnl"], 429.22, places=2)
        self.assertAlmostEqual(latest_snapshot["equity"], 100429.22, places=2)

    def test_monitor_positions_drops_superseded_invalid_paper_option_symbol_when_repaired_row_exists(self):
        from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import TradingMode

        with TemporaryDirectory() as tmpdir:
            db = TradingSessionDB(Path(tmpdir) / "paper_mark_to_market.db")
            engine, broker, _ = _make_live_engine(account_id="PAPER-ACCOUNT")
            engine.mode = TradingMode.PAPER
            engine.set_session_db(db)
            invalid_symbol = "SPY260618P00699500"
            repaired_symbol = "SPY260618P00699000"
            quote_client = MagicMock()
            quote_client.get_quotes.return_value = {
                "quotes": {
                    "quote": {
                        "symbol": repaired_symbol,
                        "bid": 4.2000,
                        "ask": 4.3842,
                    }
                }
            }
            engine._paper_option_quote_client = quote_client
            engine._paper_option_chain_cache = {
                ("SPY", "2026-06-18"): {
                    "put": [689.0, 690.0, 699.0, 700.0],
                    "call": [770.0, 780.0],
                }
            }
            engine._paper_option_chain_cache_at = {("SPY", "2026-06-18"): time.time()}
            broker.get_positions.return_value = []
            broker.get_account_balances.return_value = {
                "account": {"balance": 100000.0}
            }
            broker._last_prices = {}
            opened_at = datetime.fromisoformat("2026-05-19T14:57:49+00:00")
            db.upsert_position(
                position_id=f"paper:{invalid_symbol}",
                symbol=invalid_symbol,
                strategy="iron_condor",
                quantity=-1,
                entry_price=8.5843,
                current_price=8.5843,
                status="OPEN",
                opened_at=opened_at,
                expiration="2026-06-18",
                strike=699.5,
                option_type="put",
            )
            db.upsert_position(
                position_id=f"paper:{repaired_symbol}",
                symbol=repaired_symbol,
                strategy="iron_condor",
                quantity=-1,
                entry_price=8.5843,
                current_price=8.5843,
                status="OPEN",
                opened_at=opened_at,
                expiration="2026-06-18",
                strike=699.0,
                option_type="put",
            )
            engine.active_positions = {
                invalid_symbol: {
                    "symbol": invalid_symbol,
                    "quantity": -1,
                    "entry_price": 8.5843,
                    "current_price": 8.5843,
                    "strategy": "iron_condor",
                    "expiration": "2026-06-18",
                    "strike": 699.5,
                    "option_type": "put",
                },
                repaired_symbol: {
                    "symbol": repaired_symbol,
                    "quantity": -1,
                    "entry_price": 8.5843,
                    "current_price": 8.5843,
                    "strategy": "iron_condor",
                    "expiration": "2026-06-18",
                    "strike": 699.0,
                    "option_type": "put",
                },
            }

            engine._monitor_positions()

            latest_snapshot = db.get_latest_snapshot()
            open_rows = db.get_open_positions()
            with db._connect() as conn:
                old_row = conn.execute(
                    "SELECT symbol FROM positions WHERE position_id = ?",
                    (f"paper:{invalid_symbol}",),
                ).fetchone()

        quote_client.get_quotes.assert_called_once_with([repaired_symbol])
        self.assertNotIn(invalid_symbol, engine.active_positions)
        self.assertIn(repaired_symbol, engine.active_positions)
        self.assertEqual(len(open_rows), 1)
        self.assertEqual(open_rows[0]["position_id"], f"paper:{repaired_symbol}")
        self.assertEqual(open_rows[0]["symbol"], repaired_symbol)
        self.assertIsNone(old_row)
        self.assertIsNotNone(latest_snapshot)

    def test_monitor_positions_drops_stale_paper_positions_without_lineage(self):
        from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB
        from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import TradingMode

        with TemporaryDirectory() as tmpdir:
            db = TradingSessionDB(Path(tmpdir) / "paper_mark_to_market.db")
            engine, broker, _ = _make_live_engine(account_id="PAPER-ACCOUNT")
            engine.mode = TradingMode.PAPER
            engine.set_session_db(db)
            symbol = "SPY260613P00712500"
            broker.get_positions.return_value = []
            broker.get_account_balances.return_value = {
                "account": {"balance": 100000.0}
            }
            broker._last_prices = {symbol: 4.2921}
            engine.active_positions = {
                symbol: {
                    "symbol": symbol,
                    "quantity": -1,
                    "entry_price": 8.5843,
                    "current_price": 8.5843,
                    "strategy": "iron_condor",
                }
            }

            engine._monitor_positions()

            latest_snapshot = db.get_latest_snapshot()
            open_rows = db.get_open_positions()

        self.assertEqual(engine.active_positions, {})
        self.assertEqual(open_rows, [])
        self.assertIsNotNone(latest_snapshot)
        self.assertAlmostEqual(latest_snapshot["unrealized_pnl"], 0.0, places=2)
        self.assertAlmostEqual(latest_snapshot["equity"], 100000.0, places=2)


class TestH05PaperResetAudit(unittest.TestCase):
    """Paper DB reset auditing should surface unexpected wipes and guard active sessions."""

    def test_get_trades_today_uses_eastern_trading_day_boundary(self):
        from Spyder.SpyderH_Storage import SpyderH05_TradingSessionDB as h05

        class _FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                current = datetime(2026, 5, 19, 2, 0, 0, tzinfo=UTC)
                if tz is None:
                    return current.replace(tzinfo=None)
                return current.astimezone(tz)

        with TemporaryDirectory() as tmpdir:
            db = h05.TradingSessionDB(Path(tmpdir) / "spyder_paper.db")
            db.record_trade(
                symbol="SPY260519C00580000",
                trade_type="SELL_TO_OPEN",
                side="sell_to_open",
                quantity=1,
                price=1.5,
                strategy="iron_condor",
                realized_pnl=25.0,
                timestamp=datetime(2026, 5, 19, 1, 30, 0, tzinfo=UTC),
            )
            db.record_trade(
                symbol="SPY260519P00570000",
                trade_type="BUY_TO_OPEN",
                side="buy_to_open",
                quantity=1,
                price=2.0,
                strategy="iron_condor",
                realized_pnl=-10.0,
                timestamp=datetime(2026, 5, 19, 4, 30, 0, tzinfo=UTC),
            )

            with patch.object(h05, "datetime", _FixedDateTime):
                trades_today = db.get_trades_today()
                pnl_summary = db.get_pnl_summary()

        self.assertEqual(len(trades_today), 1)
        self.assertEqual(trades_today[0]["symbol"], "SPY260519C00580000")
        self.assertAlmostEqual(pnl_summary["today"], 25.0, places=2)
        self.assertAlmostEqual(pnl_summary["week"], 25.0, places=2)
        self.assertAlmostEqual(pnl_summary["month"], 25.0, places=2)
        self.assertAlmostEqual(pnl_summary["year"], 25.0, places=2)

    def test_unexpected_empty_paper_db_logs_warning_after_prior_activity(self):
        from Spyder.SpyderH_Storage import SpyderH05_TradingSessionDB as h05

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "spyder_paper.db"
            db = h05.TradingSessionDB(db_path)
            db.record_trade(
                symbol="SPY260613P00712500",
                trade_type="BUY_TO_OPEN",
                side="buy_to_open",
                quantity=1,
                price=4.2921,
                strategy="iron_condor",
            )
            with db._connect() as conn:
                conn.execute("DELETE FROM trades")
                conn.commit()

            logger = MagicMock()
            with patch.object(h05.SpyderLogger, "get_logger", return_value=logger):
                h05.TradingSessionDB(db_path)

        warning_messages = [call.args[0] for call in logger.warning.call_args_list if call.args]
        self.assertTrue(
            any("without an explicit reset marker" in message for message in warning_messages),
            f"expected unexpected-reset warning, got {warning_messages!r}",
        )

    def test_reset_paper_ledger_refuses_when_session_marker_active(self):
        from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB

        with TemporaryDirectory() as tmpdir:
            db = TradingSessionDB(Path(tmpdir) / "spyder_paper.db")
            db.mark_paper_session_active("PAPER_20260518_125258", owner="unit-test")

            with self.assertRaisesRegex(RuntimeError, "marked active"):
                db.reset_paper_ledger(reason="unit test reset")

    def test_purge_stale_paper_open_positions_removes_only_pre_session_rows(self):
        from Spyder.SpyderH_Storage import SpyderH05_TradingSessionDB as h05

        class _FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                current = datetime.fromisoformat("2026-05-19T14:50:14.499121+00:00")
                if tz is None:
                    return current.replace(tzinfo=None)
                return current.astimezone(tz)

        with TemporaryDirectory() as tmpdir:
            db = h05.TradingSessionDB(Path(tmpdir) / "spyder_paper.db")
            stale_opened_at = datetime.fromisoformat("2026-05-19T13:52:07.686759+00:00")
            current_opened_at = datetime.fromisoformat("2026-05-19T14:50:22.532676+00:00")

            db.upsert_position(
                position_id="paper:SPY260618P00690000",
                symbol="SPY260618P00690000",
                strategy="iron_condor",
                quantity=-1,
                entry_price=1.23,
                status="OPEN",
                opened_at=stale_opened_at,
            )
            db.upsert_position(
                position_id="paper:SPY260618P00687000",
                symbol="SPY260618P00687000",
                strategy="iron_condor",
                quantity=-1,
                entry_price=1.11,
                status="OPEN",
                opened_at=current_opened_at,
            )

            with patch.object(h05, "datetime", _FixedDateTime):
                db.mark_paper_session_active("PAPER_20260519_105014", owner="unit-test")

            result = db.purge_stale_paper_open_positions(actor="unit-test")
            remaining_rows = db.get_open_positions()

        self.assertEqual(result["deleted_positions"], 1)
        self.assertEqual(result["session_id"], "PAPER_20260519_105014")
        self.assertEqual(len(remaining_rows), 1)
        self.assertEqual(remaining_rows[0]["position_id"], "paper:SPY260618P00687000")

    def test_get_active_paper_open_positions_keeps_carryover_and_current_session_rows(self):
        from Spyder.SpyderH_Storage import SpyderH05_TradingSessionDB as h05

        class _InitialDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                current = datetime.fromisoformat("2026-05-19T14:00:00+00:00")
                if tz is None:
                    return current.replace(tzinfo=None)
                return current.astimezone(tz)

        class _FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                current = datetime.fromisoformat("2026-05-19T14:50:14.499121+00:00")
                if tz is None:
                    return current.replace(tzinfo=None)
                return current.astimezone(tz)

        with TemporaryDirectory() as tmpdir:
            db = h05.TradingSessionDB(Path(tmpdir) / "spyder_paper.db")
            carryover_opened_at = datetime.fromisoformat("2026-05-18T19:00:00+00:00")
            stale_opened_at = datetime.fromisoformat("2026-05-19T13:52:07.686759+00:00")
            current_opened_at = datetime.fromisoformat("2026-05-19T14:50:22.532676+00:00")

            with patch.object(h05, "datetime", _InitialDateTime):
                db.upsert_position(
                    position_id="paper:SPY260618P00680000",
                    symbol="SPY260618P00680000",
                    strategy="iron_condor",
                    quantity=-1,
                    entry_price=1.25,
                    status="OPEN",
                    opened_at=carryover_opened_at,
                )
                db.upsert_position(
                    position_id="paper:SPY260618P00690000",
                    symbol="SPY260618P00690000",
                    strategy="iron_condor",
                    quantity=-1,
                    entry_price=1.23,
                    status="OPEN",
                    opened_at=stale_opened_at,
                )
                db.upsert_position(
                    position_id="paper:SPY260618P00687000",
                    symbol="SPY260618P00687000",
                    strategy="iron_condor",
                    quantity=-1,
                    entry_price=1.11,
                    status="OPEN",
                    opened_at=current_opened_at,
                )

            db.save_paper_carryover_manifest(
                [
                    {
                        "position_id": "paper:SPY260618P00680000",
                        "symbol": "SPY260618P00680000",
                        "strategy": "iron_condor",
                        "quantity": -1,
                        "opened_at": carryover_opened_at.isoformat(),
                    }
                ],
                session_id="PAPER_20260518_150000",
            )

            with patch.object(h05, "datetime", _FixedDateTime):
                db.mark_paper_session_active("PAPER_20260519_105014", owner="unit-test")

            rows = db.get_active_paper_open_positions()

        assert_by_position_id = {row["position_id"]: row for row in rows}
        self.assertEqual(
            sorted(assert_by_position_id),
            ["paper:SPY260618P00680000", "paper:SPY260618P00687000"],
        )
        self.assertEqual(assert_by_position_id["paper:SPY260618P00680000"]["_paper_open_origin"], "carryover")
        self.assertEqual(assert_by_position_id["paper:SPY260618P00687000"]["_paper_open_origin"], "active_session")

    def test_get_active_paper_open_positions_keeps_reused_open_symbol_visible_after_session_start(self):
        from Spyder.SpyderH_Storage import SpyderH05_TradingSessionDB as h05

        class _StaleDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                current = datetime.fromisoformat("2026-05-19T13:52:07.686759+00:00")
                if tz is None:
                    return current.replace(tzinfo=None)
                return current.astimezone(tz)

        class _SessionStartDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                current = datetime.fromisoformat("2026-05-19T14:50:14.499121+00:00")
                if tz is None:
                    return current.replace(tzinfo=None)
                return current.astimezone(tz)

        with TemporaryDirectory() as tmpdir:
            db = h05.TradingSessionDB(Path(tmpdir) / "spyder_paper.db")
            stale_opened_at = datetime.fromisoformat("2026-05-19T13:52:07.686759+00:00")
            current_opened_at = datetime.fromisoformat("2026-05-19T14:50:22.532676+00:00")

            with patch.object(h05, "datetime", _StaleDateTime):
                db.upsert_position(
                    position_id="paper:SPY260618P00687000",
                    symbol="SPY260618P00687000",
                    strategy="iron_condor",
                    quantity=-1,
                    entry_price=1.11,
                    status="OPEN",
                    opened_at=stale_opened_at,
                )

            with patch.object(h05, "datetime", _SessionStartDateTime):
                db.mark_paper_session_active("PAPER_20260519_105014", owner="unit-test")

            db.upsert_position(
                position_id="paper:SPY260618P00687000",
                symbol="SPY260618P00687000",
                strategy="iron_condor",
                quantity=-1,
                entry_price=1.11,
                status="OPEN",
                opened_at=current_opened_at,
            )

            rows = db.get_active_paper_open_positions()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["position_id"], "paper:SPY260618P00687000")
        self.assertEqual(rows[0]["opened_at"], current_opened_at.isoformat())
        self.assertEqual(rows[0]["_paper_open_origin"], "active_session")

    def test_get_active_paper_open_positions_uses_updated_at_for_legacy_reused_open_rows(self):
        from Spyder.SpyderH_Storage import SpyderH05_TradingSessionDB as h05

        class _StaleDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                current = datetime.fromisoformat("2026-05-19T13:52:07.686759+00:00")
                if tz is None:
                    return current.replace(tzinfo=None)
                return current.astimezone(tz)

        class _SessionStartDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                current = datetime.fromisoformat("2026-05-19T14:50:14.499121+00:00")
                if tz is None:
                    return current.replace(tzinfo=None)
                return current.astimezone(tz)

        class _CurrentDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                current = datetime.fromisoformat("2026-05-19T14:50:22.532676+00:00")
                if tz is None:
                    return current.replace(tzinfo=None)
                return current.astimezone(tz)

        with TemporaryDirectory() as tmpdir:
            db = h05.TradingSessionDB(Path(tmpdir) / "spyder_paper.db")
            stale_opened_at = datetime.fromisoformat("2026-05-19T13:52:07.686759+00:00")

            with patch.object(h05, "datetime", _StaleDateTime):
                db.upsert_position(
                    position_id="paper:SPY260618P00687000",
                    symbol="SPY260618P00687000",
                    strategy="iron_condor",
                    quantity=-1,
                    entry_price=1.11,
                    status="OPEN",
                    opened_at=stale_opened_at,
                )

            with patch.object(h05, "datetime", _SessionStartDateTime):
                db.mark_paper_session_active("PAPER_20260519_105014", owner="unit-test")

            with patch.object(h05, "datetime", _CurrentDateTime):
                db.upsert_position(
                    position_id="paper:SPY260618P00687000",
                    symbol="SPY260618P00687000",
                    strategy="iron_condor",
                    quantity=-1,
                    entry_price=1.11,
                    status="OPEN",
                    opened_at=stale_opened_at,
                )

            rows = db.get_active_paper_open_positions()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["position_id"], "paper:SPY260618P00687000")
        self.assertEqual(rows[0]["opened_at"], stale_opened_at.isoformat())
        self.assertEqual(rows[0]["_paper_open_origin"], "active_session")

    def test_explicit_reset_clears_tables_without_startup_warning(self):
        from Spyder.SpyderH_Storage import SpyderH05_TradingSessionDB as h05

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "spyder_paper.db"
            db = h05.TradingSessionDB(db_path)
            db.record_trade(
                symbol="SPY260613P00712500",
                trade_type="SELL_TO_OPEN",
                side="sell_to_open",
                quantity=1,
                price=8.5843,
                strategy="iron_condor",
            )
            db.record_account_snapshot(
                cash=100000.0,
                equity=100000.0,
                buying_power=100000.0,
            )
            db.upsert_position(
                position_id="paper:SPY260613P00712500",
                symbol="SPY260613P00712500",
                strategy="iron_condor",
                quantity=-1,
                entry_price=8.5843,
            )

            cleared = db.reset_paper_ledger(reason="operator reset", actor="unit-test")

            self.assertEqual(cleared["trades"], 1)
            self.assertEqual(cleared["positions"], 1)
            self.assertEqual(cleared["account_snapshots"], 1)
            self.assertEqual(db.get_recent_trades(limit=5), [])
            self.assertEqual(db.get_open_positions(), [])
            self.assertIsNone(db.get_latest_snapshot())

            logger = MagicMock()
            with patch.object(h05.SpyderLogger, "get_logger", return_value=logger):
                h05.TradingSessionDB(db_path)

        warning_messages = [call.args[0] for call in logger.warning.call_args_list if call.args]
        self.assertFalse(
            any("without an explicit reset marker" in message for message in warning_messages),
            f"did not expect unexpected-reset warning, got {warning_messages!r}",
        )


class TestR04CancelPendingOrders(unittest.TestCase):
    """_cancel_all_pending_orders must not raise even if dict is mutated."""

    def test_cancel_all_clears_pending_orders(self):
        engine, broker, _ = _make_live_engine()
        engine.pending_orders = {
            "ORD_001": {"order": {}, "result": None},
            "ORD_002": {"order": {}, "result": None},
        }
        engine._cancel_all_pending_orders()
        self.assertEqual(engine.pending_orders, {})
        self.assertEqual(broker.cancel_order.call_count, 2)

    def test_cancel_all_tolerates_broker_errors(self):
        """Broker errors during cancellation must not abort the loop."""
        engine, broker, _ = _make_live_engine()
        broker.cancel_order.side_effect = RuntimeError("network error")
        engine.pending_orders = {
            "ORD_001": {"order": {}, "result": None},
            "ORD_002": {"order": {}, "result": None},
        }
        try:
            engine._cancel_all_pending_orders()
        except RuntimeError:
            self.fail("_cancel_all_pending_orders raised RuntimeError to the caller")


class TestR04StopLoss(unittest.TestCase):
    """_should_trigger_stop_loss must evaluate position correctly."""

    def test_stop_triggered_when_loss_exceeds_threshold(self):
        engine, _, _ = _make_live_engine()
        position = {
            "symbol": "SPY",
            "entry_price": 100.0,
            "current_price": 94.0,  # -6% loss
            "stop_loss_pct": 0.05,   # 5% threshold
        }
        self.assertTrue(engine._should_trigger_stop_loss(position))

    def test_stop_not_triggered_when_loss_below_threshold(self):
        engine, _, _ = _make_live_engine()
        position = {
            "symbol": "SPY",
            "entry_price": 100.0,
            "current_price": 97.0,  # -3% loss
            "stop_loss_pct": 0.05,   # 5% threshold
        }
        self.assertFalse(engine._should_trigger_stop_loss(position))

    def test_stop_not_triggered_when_no_stop_loss_pct(self):
        engine, _, _ = _make_live_engine()
        position = {"symbol": "SPY", "entry_price": 100.0, "current_price": 50.0}
        self.assertFalse(engine._should_trigger_stop_loss(position))


if __name__ == "__main__":
    unittest.main()
