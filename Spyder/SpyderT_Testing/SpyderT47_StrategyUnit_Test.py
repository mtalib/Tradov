#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT47_StrategyUnit_Test.py
Purpose: Unit tests for BaseStrategy, data structures, and strategy lifecycle

Author: GitHub Copilot
Year Created: 2026
Last Updated: 2026-02-26 Time: 12:00:00

Module Description:
    Unit tests covering BaseStrategy lifecycle (start/stop/pause/resume),
    position management, signal validation, performance tracking, and
    data structures (TradingSignal, StrategyPosition, PerformanceMetrics,
    RiskProfile, EventManager).

Change Log:
    2026-02-26 (v1.0.0):
        - Initial test suite: 20 tests for D01_BaseStrategy
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import unittest
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional
# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (
    STRATEGY_ACTIVE,
    STRATEGY_INACTIVE,
    STRATEGY_PAUSED,
    BaseStrategy,
    Event,
    EventManager,
    EventType,
    PerformanceMetrics,
    PositionState,
    PositionType,
    RiskLevel,
    RiskProfile,
    SignalStrength,
    SignalType,
    StrategyPosition,
    TradingSignal,
)


# ==============================================================================
# CONCRETE STRATEGY FOR TESTING
# ==============================================================================

class _TestStrategy(BaseStrategy):
    """Minimal concrete strategy for testing the abstract BaseStrategy."""

    def __init__(self, name="TestStrategy", **kwargs):
        event_manager = kwargs.pop("event_manager", EventManager())
        risk_profile = kwargs.pop(
            "risk_profile",
            RiskProfile(account_size=100_000)
        )
        config = kwargs.pop("config", {"max_positions": 5, "max_daily_trades": 10})
        super().__init__(
            name=name,
            event_manager=event_manager,
            risk_profile=risk_profile,
            config=config,
        )
        # Track calls for verification
        self._generated_signals: list[TradingSignal] = []

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        return self._generated_signals

    def validate_signal(self, signal: TradingSignal) -> bool:
        return signal.is_valid() and signal.confidence > 0.3

    def calculate_position_size(self, signal: TradingSignal) -> int:
        return signal.position_size

    def should_exit_position(
        self, position: StrategyPosition, market_data: pd.DataFrame
    ) -> tuple[bool, str]:
        if position.unrealized_pnl < -(position.entry_price * position.position_size * 0.05):
            return True, "stop_loss"
        return False, ""


def _make_signal(
    symbol="SPY",
    signal_type=SignalType.BUY,
    strength=SignalStrength.STRONG,
    confidence=0.8,
    entry_price=550.0,
    stop_loss=540.0,
    take_profit=565.0,
    position_size=10,
    expires_seconds=300,
):
    """Helper to create a valid TradingSignal."""
    now = datetime.now()
    return TradingSignal(
        signal_id=str(uuid.uuid4()),
        signal_type=signal_type,
        symbol=symbol,
        strength=strength,
        confidence=confidence,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_size=position_size,
        timestamp=now,
        expires_at=now + timedelta(seconds=expires_seconds),
    )


# ==============================================================================
# DATA STRUCTURE TESTS
# ==============================================================================

class TestTradingSignal(unittest.TestCase):
    """Tests for TradingSignal dataclass."""

    def test_01_signal_is_valid(self):
        """Fresh signal is valid (not expired)."""
        sig = _make_signal()
        self.assertTrue(sig.is_valid())

    def test_02_signal_expired(self):
        """Signal with past expiry is invalid."""
        sig = _make_signal(expires_seconds=-10)
        self.assertFalse(sig.is_valid())

    def test_03_signal_to_dict(self):
        """to_dict() returns serializable dictionary with all fields."""
        sig = _make_signal(symbol="QQQ")
        d = sig.to_dict()

        self.assertEqual(d["symbol"], "QQQ")
        self.assertEqual(d["signal_type"], "buy")
        self.assertEqual(d["strength"], "strong")
        self.assertIn("signal_id", d)
        self.assertIn("timestamp", d)


class TestStrategyPosition(unittest.TestCase):
    """Tests for StrategyPosition dataclass."""

    def test_04_update_pnl_long(self):
        """Long position PnL is (current - entry) * size."""
        pos = StrategyPosition(
            position_id="P1", strategy_name="Test", symbol="SPY",
            position_type=PositionType.LONG, state=PositionState.OPEN,
            entry_time=datetime.now(), entry_price=550.0,
            position_size=10, stop_loss=540.0, take_profit=565.0,
        )
        pos.update_pnl(555.0)
        self.assertAlmostEqual(pos.unrealized_pnl, 50.0)  # (555-550)*10

    def test_05_update_pnl_short(self):
        """Short position PnL is (entry - current) * size."""
        pos = StrategyPosition(
            position_id="P2", strategy_name="Test", symbol="SPY",
            position_type=PositionType.SHORT, state=PositionState.OPEN,
            entry_time=datetime.now(), entry_price=550.0,
            position_size=10, stop_loss=560.0, take_profit=535.0,
        )
        pos.update_pnl(545.0)
        self.assertAlmostEqual(pos.unrealized_pnl, 50.0)  # (550-545)*10

    def test_06_close_position_long(self):
        """Closing a long position calculates realized PnL correctly."""
        pos = StrategyPosition(
            position_id="P3", strategy_name="Test", symbol="SPY",
            position_type=PositionType.LONG, state=PositionState.OPEN,
            entry_time=datetime.now(), entry_price=550.0,
            position_size=10, stop_loss=540.0, take_profit=565.0,
        )
        pos.close_position(exit_price=560.0, exit_reason="take_profit")

        self.assertEqual(pos.state, PositionState.CLOSED)
        self.assertAlmostEqual(pos.realized_pnl, 100.0)  # (560-550)*10
        self.assertEqual(pos.unrealized_pnl, 0.0)
        self.assertEqual(pos.exit_reason, "take_profit")


class TestPerformanceMetrics(unittest.TestCase):
    """Tests for PerformanceMetrics tracking."""

    def test_07_update_winning_trade(self):
        """Winning trade updates metrics correctly."""
        pm = PerformanceMetrics()
        pos = StrategyPosition(
            position_id="P", strategy_name="Test", symbol="SPY",
            position_type=PositionType.LONG, state=PositionState.CLOSED,
            entry_time=datetime.now(), entry_price=550.0,
            position_size=10, stop_loss=540.0, take_profit=565.0,
            realized_pnl=100.0
        )
        pm.update(pos)

        self.assertEqual(pm.total_trades, 1)
        self.assertEqual(pm.winning_trades, 1)
        self.assertEqual(pm.win_rate, 1.0)
        self.assertAlmostEqual(pm.average_win, 100.0)

    def test_08_update_losing_trade(self):
        """Losing trade updates metrics correctly."""
        pm = PerformanceMetrics()
        pos = StrategyPosition(
            position_id="P", strategy_name="Test", symbol="SPY",
            position_type=PositionType.LONG, state=PositionState.CLOSED,
            entry_time=datetime.now(), entry_price=550.0,
            position_size=10, stop_loss=540.0, take_profit=565.0,
            realized_pnl=-50.0
        )
        pm.update(pos)

        self.assertEqual(pm.total_trades, 1)
        self.assertEqual(pm.losing_trades, 1)
        self.assertEqual(pm.win_rate, 0.0)
        self.assertAlmostEqual(pm.average_loss, 50.0)

    def test_09_mixed_trades_win_rate(self):
        """Win rate calculated correctly for mixed results."""
        pm = PerformanceMetrics()

        for pnl in [100.0, -50.0, 75.0]:
            pos = StrategyPosition(
                position_id=str(uuid.uuid4()), strategy_name="Test",
                symbol="SPY", position_type=PositionType.LONG,
                state=PositionState.CLOSED, entry_time=datetime.now(),
                entry_price=550.0, position_size=10,
                stop_loss=540.0, take_profit=565.0,
                realized_pnl=pnl
            )
            pm.update(pos)

        self.assertEqual(pm.total_trades, 3)
        self.assertEqual(pm.winning_trades, 2)
        self.assertAlmostEqual(pm.win_rate, 2 / 3)

    def test_10_skip_non_closed(self):
        """Non-closed position is not counted."""
        pm = PerformanceMetrics()
        pos = StrategyPosition(
            position_id="P", strategy_name="Test", symbol="SPY",
            position_type=PositionType.LONG, state=PositionState.OPEN,
            entry_time=datetime.now(), entry_price=550.0,
            position_size=10, stop_loss=540.0, take_profit=565.0,
            realized_pnl=100.0
        )
        pm.update(pos)
        self.assertEqual(pm.total_trades, 0)


class TestRiskProfile(unittest.TestCase):
    """Tests for RiskProfile position sizing."""

    def test_11_position_size_by_strength(self):
        """Position size scales with signal strength."""
        rp = RiskProfile(account_size=100_000, max_position_size=0.02)

        size_weak = rp.calculate_position_size(SignalStrength.WEAK)
        size_strong = rp.calculate_position_size(SignalStrength.STRONG)
        size_very_strong = rp.calculate_position_size(SignalStrength.VERY_STRONG)

        self.assertAlmostEqual(size_weak, 1000.0)  # 100k * 0.02 * 0.5
        self.assertAlmostEqual(size_strong, 2000.0)  # 100k * 0.02 * 1.0
        self.assertAlmostEqual(size_very_strong, 2500.0)  # 100k * 0.02 * 1.25


class TestEventManager(unittest.TestCase):
    """Tests for EventManager pub/sub."""

    def test_12_publish_and_subscribe(self):
        """Subscriber receives published events."""
        em = EventManager()
        received = []
        em.subscribe(EventType.SIGNAL_GENERATED, lambda e: received.append(e))

        event = Event.create(EventType.SIGNAL_GENERATED, "Test", {"signal": "buy"})
        em.publish(event)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["signal"], "buy")

    def test_13_unsubscribe(self):
        """After unsubscribe, callback no longer receives events."""
        em = EventManager()
        received = []
        def callback(e):
            return received.append(e)
        em.subscribe(EventType.SIGNAL_GENERATED, callback)
        em.unsubscribe(EventType.SIGNAL_GENERATED, callback)

        event = Event.create(EventType.SIGNAL_GENERATED, "Test", {})
        em.publish(event)

        self.assertEqual(len(received), 0)

    def test_14_event_history(self):
        """Published events are kept in history."""
        em = EventManager()
        for i in range(5):
            em.publish(Event.create(EventType.PERFORMANCE_UPDATE, "Test", {"i": i}))

        history = em.get_recent_events(EventType.PERFORMANCE_UPDATE)
        self.assertEqual(len(history), 5)


# ==============================================================================
# LIFECYCLE TESTS
# ==============================================================================

class TestBaseStrategyLifecycle(unittest.TestCase):
    """Tests for BaseStrategy lifecycle methods."""

    def test_15_start_stop_lifecycle(self):
        """start() → ACTIVE, stop() → INACTIVE."""
        strat = _TestStrategy()
        self.assertEqual(strat.state, STRATEGY_INACTIVE)

        self.assertTrue(strat.start())
        self.assertEqual(strat.state, STRATEGY_ACTIVE)

        self.assertTrue(strat.stop())
        self.assertEqual(strat.state, STRATEGY_INACTIVE)

    def test_16_pause_resume(self):
        """pause() → PAUSED, resume() → ACTIVE."""
        strat = _TestStrategy()
        strat.start()

        self.assertTrue(strat.pause())
        self.assertEqual(strat.state, STRATEGY_PAUSED)

        self.assertTrue(strat.resume())
        self.assertEqual(strat.state, STRATEGY_ACTIVE)

        strat.stop()

    def test_17_cannot_start_twice(self):
        """start() returns False if already active."""
        strat = _TestStrategy()
        strat.start()
        self.assertFalse(strat.start())
        strat.stop()

    def test_18_cannot_stop_when_inactive(self):
        """stop() returns False if not active or paused."""
        strat = _TestStrategy()
        self.assertFalse(strat.stop())


# ==============================================================================
# POSITION MANAGEMENT TESTS
# ==============================================================================

class TestBaseStrategyPositions(unittest.TestCase):
    """Tests for BaseStrategy position management."""

    def setUp(self):
        self.strat = _TestStrategy()
        self.strat.start()

    def tearDown(self):
        if self.strat.state in [STRATEGY_ACTIVE, STRATEGY_PAUSED]:
            self.strat.stop()

    def test_19_add_position_from_signal(self):
        """add_position() creates a StrategyPosition from a valid signal."""
        signal = _make_signal()
        pos = self.strat.add_position(signal)

        self.assertIsNotNone(pos)
        self.assertEqual(pos.symbol, "SPY")
        self.assertEqual(pos.position_type, PositionType.LONG)
        self.assertEqual(len(self.strat.positions), 1)

    def test_20_add_position_rejected_expired(self):
        """add_position() rejects expired signal."""
        signal = _make_signal(expires_seconds=-10)
        pos = self.strat.add_position(signal)
        self.assertIsNone(pos)

    def test_21_add_position_rejected_low_confidence(self):
        """add_position() rejects signal with confidence ≤ 0.3."""
        signal = _make_signal(confidence=0.1)
        pos = self.strat.add_position(signal)
        self.assertIsNone(pos)

    def test_22_close_position(self):
        """close_position() finalizes PnL and moves to history."""
        signal = _make_signal()
        pos = self.strat.add_position(signal)
        pid = pos.position_id

        result = self.strat.close_position(pid, exit_price=560.0, reason="take_profit")

        self.assertTrue(result)
        self.assertEqual(len(self.strat.positions), 0)
        self.assertEqual(len(self.strat.position_history), 1)
        self.assertAlmostEqual(self.strat.position_history[0].realized_pnl, 100.0)

    def test_23_close_nonexistent_position(self):
        """close_position() returns False for unknown position ID."""
        result = self.strat.close_position("nonexistent", exit_price=550.0)
        self.assertFalse(result)

    def test_24_max_positions_enforced(self):
        """Cannot add more positions than max_positions config."""
        self.strat.max_positions = 2

        s1 = _make_signal()
        s2 = _make_signal()
        s3 = _make_signal()

        self.assertIsNotNone(self.strat.add_position(s1))
        self.assertIsNotNone(self.strat.add_position(s2))
        self.assertIsNone(self.strat.add_position(s3))  # Rejected


class TestBaseStrategyState(unittest.TestCase):
    """Tests for get_state() and get_performance()."""

    def test_25_get_state_contents(self):
        """get_state() returns dict with all expected keys."""
        strat = _TestStrategy()
        strat.start()

        state = strat.get_state()

        self.assertIn("strategy_id", state)
        self.assertIn("name", state)
        self.assertIn("state", state)
        self.assertIn("open_positions", state)
        self.assertIn("performance", state)
        self.assertEqual(state["state"], STRATEGY_ACTIVE)

        strat.stop()

    def test_26_process_market_data_inactive(self):
        """process_market_data() is a no-op when strategy is inactive."""
        strat = _TestStrategy()
        # Don't call start() — strategy is INACTIVE
        df = pd.DataFrame({"close": [550.0, 551.0, 552.0]})
        strat.process_market_data(df)  # Should not raise
        self.assertIsNone(strat.last_update)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    unittest.main()
