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
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock


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


class TestR04PositionHydration(unittest.TestCase):
    """Paper-mode engines should hydrate active positions from H05 when attached."""

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

            engine.set_session_db(db)

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
