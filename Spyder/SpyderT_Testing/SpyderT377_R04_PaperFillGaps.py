"""Regression for R04 paper-fill gaps: H05 persistence, symbol in event, position tracker.

Three bugs fixed in _execute_order_internal for the no-reconciler branch:

B1 — ORDER_FILLED event was emitted without 'symbol', so D31's
     _on_terminal_order_event could not clear pending entry reservations.

B2 — _session_db.record_trade() was never called for paper fills
     (only _on_reconciler_fill called it, which is gated on source="FillReconciler").

B3 — _position_tracker.record_fill() was never called for paper fills,
     leaving active_positions empty and POSITION_UPDATED events unsent.
"""
from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch, call


def _load_live_engine_class():
    mod = importlib.import_module("Spyder.SpyderR_Runtime.SpyderR04_LiveEngine")
    return mod.LiveEngine


def _make_engine(session_db=None, position_tracker=None):
    """Return a minimally wired LiveEngine instance for paper mode."""
    import threading
    cls = _load_live_engine_class()
    engine = cls.__new__(cls)

    # Minimal required attributes
    engine.logger = __import__("logging").getLogger("test_r04_paper")
    engine.mode = MagicMock()
    engine.mode.value = "paper"
    engine._reconciler = None  # paper mode — no FillReconciler
    engine.metrics = MagicMock()
    engine.metrics.successful_executions = 0
    engine.metrics.failed_executions = 0
    engine.metrics.total_orders = 0
    engine.daily_trades = 0
    engine.current_session = None
    engine._session_db = session_db
    engine._position_tracker = position_tracker

    # Thread-safety primitives used by _resolve_order_future
    engine._pending_orders_lock = threading.RLock()
    engine.pending_orders = {}

    # Event manager: capture emitted events
    engine._event_manager = MagicMock()
    engine._event_manager.emit = MagicMock()

    # Helpers that must not throw
    engine.reset_api_error_count = MagicMock()
    engine.record_api_server_error = MagicMock()
    engine._broker_submit = MagicMock(return_value={
        "status": "accepted",
        "tradier_order_id": "PAPER-000001",
    })

    return engine


class TestPaperFillSymbolInOrderFilledEvent:
    """B1 — ORDER_FILLED must carry 'symbol' so D31 clears pending reservations."""

    def test_symbol_present_in_order_filled_event(self):
        engine = _make_engine()
        order = {
            "order_id": "test-001",
            "symbol": "SPY231215C00500000",
            "side": "sell_to_open",
            "quantity": 1,
            "price": 1.50,
        }
        engine._execute_order_internal(order)

        emitted_calls = engine._event_manager.emit.call_args_list
        filled_calls = [
            c for c in emitted_calls
            if "ORDER_FILLED" in str(c) or "order_filled" in str(c).lower()
        ]
        assert filled_calls, "ORDER_FILLED event must be emitted"
        # The event data must contain the symbol
        last_call = filled_calls[-1]
        event_data = last_call.args[1] if len(last_call.args) > 1 else last_call.kwargs.get("data", {})
        assert event_data.get("symbol") == "SPY231215C00500000", (
            f"ORDER_FILLED event must include 'symbol'; got: {event_data}"
        )

    def test_empty_symbol_still_emits_event(self):
        """Even with no symbol, the event must still fire (backward compat)."""
        engine = _make_engine()
        order = {"order_id": "test-002", "side": "sell", "quantity": 1}
        engine._execute_order_internal(order)

        emitted_calls = engine._event_manager.emit.call_args_list
        filled_calls = [
            c for c in emitted_calls
            if "ORDER_FILLED" in str(c) or "order_filled" in str(c).lower()
        ]
        assert filled_calls, "ORDER_FILLED event must be emitted even with no symbol"

    def test_symbol_present_in_direct_fill_status(self):
        """Same check for status='filled' branch."""
        engine = _make_engine()
        engine._broker_submit = MagicMock(return_value={
            "status": "filled",
            "fill_price": 1.50,
        })
        order = {
            "order_id": "test-003",
            "symbol": "SPY231215P00480000",
            "side": "sell_to_open",
            "quantity": 1,
            "price": 1.20,
        }
        engine._execute_order_internal(order)

        emitted_calls = engine._event_manager.emit.call_args_list
        filled_calls = [
            c for c in emitted_calls
            if "ORDER_FILLED" in str(c) or "order_filled" in str(c).lower()
        ]
        assert filled_calls, "ORDER_FILLED event must be emitted for 'filled' status"
        event_data = filled_calls[-1].args[1] if len(filled_calls[-1].args) > 1 else {}
        assert event_data.get("symbol") == "SPY231215P00480000"


class TestPaperFillH05Persistence:
    """B2 — _session_db.record_trade must be called for paper fills."""

    def test_record_trade_called_on_paper_accepted(self):
        session_db = MagicMock()
        engine = _make_engine(session_db=session_db)
        order = {
            "order_id": "test-010",
            "symbol": "SPY231215C00500000",
            "side": "sell_to_open",
            "quantity": 2,
            "price": 1.50,
            "strategy_id": "iron_condor",
            "expiration": "2023-12-15",
            "strike": 500.0,
            "option_type": "call",
        }
        engine._execute_order_internal(order)

        session_db.record_trade.assert_called_once()
        kwargs = session_db.record_trade.call_args.kwargs
        assert kwargs["symbol"] == "SPY231215C00500000"
        assert kwargs["side"] == "sell_to_open"
        assert kwargs["quantity"] == 2
        assert kwargs["strategy"] == "iron_condor"
        assert kwargs["notes"] == "paper fill via LiveEngine"

    def test_record_trade_called_on_paper_direct_fill(self):
        session_db = MagicMock()
        engine = _make_engine(session_db=session_db)
        engine._broker_submit = MagicMock(return_value={
            "status": "filled",
            "fill_price": 1.30,
        })
        order = {
            "order_id": "test-011",
            "symbol": "SPY231215P00480000",
            "side": "sell_to_open",
            "quantity": 1,
            "price": 1.30,
            "strategy_id": "iron_condor",
        }
        engine._execute_order_internal(order)

        session_db.record_trade.assert_called_once()
        kwargs = session_db.record_trade.call_args.kwargs
        assert kwargs["symbol"] == "SPY231215P00480000"
        assert kwargs["notes"] == "paper fill via LiveEngine"

    def test_record_trade_not_called_when_no_session_db(self):
        """No error raised if _session_db is None."""
        engine = _make_engine(session_db=None)
        order = {
            "order_id": "test-012",
            "symbol": "SPY231215C00500000",
            "side": "sell",
            "quantity": 1,
            "price": 1.50,
        }
        # Must not raise
        engine._execute_order_internal(order)

    def test_record_trade_not_called_for_rejected_order(self):
        """record_trade must NOT be called when broker rejects the order."""
        session_db = MagicMock()
        engine = _make_engine(session_db=session_db)
        engine._broker_submit = MagicMock(return_value={"status": "rejected", "reason": "margin"})
        order = {
            "order_id": "test-013",
            "symbol": "SPY231215C00500000",
            "side": "sell",
            "quantity": 1,
        }
        engine._execute_order_internal(order)
        session_db.record_trade.assert_not_called()

    def test_record_trade_strike_none_when_missing(self):
        """strike must be passed as None when not in order dict."""
        session_db = MagicMock()
        engine = _make_engine(session_db=session_db)
        order = {
            "order_id": "test-014",
            "symbol": "SPY",
            "side": "buy",
            "quantity": 100,
            "price": 450.0,
            # No 'strike' or 'option_type'
        }
        engine._execute_order_internal(order)

        kwargs = session_db.record_trade.call_args.kwargs
        assert kwargs["strike"] is None
        assert kwargs["option_type"] is None


class TestPaperFillPositionTracker:
    """B3 — _position_tracker.record_fill must be called for paper fills."""

    def test_position_tracker_called_on_paper_accepted(self):
        position_tracker = MagicMock()
        engine = _make_engine(position_tracker=position_tracker)
        order = {
            "order_id": "test-020",
            "symbol": "SPY231215C00500000",
            "side": "sell_to_open",
            "quantity": 1,
            "price": 1.50,
            "strategy_id": "iron_condor",
        }
        engine._execute_order_internal(order)

        position_tracker.record_fill.assert_called_once()
        fill_arg = position_tracker.record_fill.call_args.args[0]
        assert fill_arg["symbol"] == "SPY231215C00500000"
        assert fill_arg["side"] == "sell_to_open"
        assert fill_arg["quantity"] == 1
        assert fill_arg["strategy_id"] == "iron_condor"

    def test_position_tracker_called_on_direct_fill_status(self):
        position_tracker = MagicMock()
        engine = _make_engine(position_tracker=position_tracker)
        engine._broker_submit = MagicMock(return_value={
            "status": "filled",
            "fill_price": 1.20,
        })
        order = {
            "order_id": "test-021",
            "symbol": "SPY231215P00480000",
            "side": "sell_to_open",
            "quantity": 2,
            "price": 1.20,
            "strategy_id": "iron_condor",
        }
        engine._execute_order_internal(order)

        position_tracker.record_fill.assert_called_once()
        fill_arg = position_tracker.record_fill.call_args.args[0]
        assert fill_arg["symbol"] == "SPY231215P00480000"
        assert fill_arg["quantity"] == 2
        assert fill_arg["strategy_id"] == "iron_condor"

    def test_position_tracker_not_called_when_none(self):
        """Must not crash when _position_tracker is None."""
        engine = _make_engine(position_tracker=None)
        order = {
            "order_id": "test-022",
            "symbol": "SPY231215C00500000",
            "side": "sell",
            "quantity": 1,
        }
        engine._execute_order_internal(order)  # must not raise

    def test_position_tracker_not_called_for_zero_quantity(self):
        """Should not call record_fill when quantity resolves to 0."""
        position_tracker = MagicMock()
        engine = _make_engine(position_tracker=position_tracker)
        order = {
            "order_id": "test-023",
            "symbol": "SPY231215C00500000",
            "side": "sell",
            "quantity": 0,
        }
        engine._execute_order_internal(order)
        position_tracker.record_fill.assert_not_called()

    def test_position_tracker_not_called_for_rejected_order(self):
        position_tracker = MagicMock()
        engine = _make_engine(position_tracker=position_tracker)
        engine._broker_submit = MagicMock(return_value={"status": "rejected"})
        order = {
            "order_id": "test-024",
            "symbol": "SPY231215C00500000",
            "side": "sell",
            "quantity": 1,
        }
        engine._execute_order_internal(order)
        position_tracker.record_fill.assert_not_called()
