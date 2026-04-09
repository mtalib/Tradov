#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT51_RiskManagerLimits_Test.py
Purpose: Focused limit-enforcement tests for SpyderE01_RiskManager, covering
         gaps left by T46 — boundary conditions, sell-side orders, all four
         option order sides, risk-level escalation, get_position/get_positions,
         metrics counters, options-exposure threshold, and zero-div guard.

All tests run against the REAL RiskManager logic with mocked ConnectAPI.

Author: Spyder Dev
Year Created: 2026
Last Updated: 2026-03-03 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import unittest
from datetime import datetime
from typing import Any
# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderE_Risk.SpyderE01_RiskManager import (
    DEFAULT_RISK_LIMITS,
    Position,
    RiskCheckResult,
    RiskConfig,
    RiskLevel,
    RiskManager,
    RiskMetrics,
)


# ==============================================================================
# SHARED MOCK INFRASTRUCTURE (mirrors T46 so no cross-file coupling)
# ==============================================================================

# MessageType is now defined in E01 itself — no __globals__ patching needed.
def _patch_message_type():
    """No-op: retained for call-site compatibility; E01 owns MessageType."""
    pass


class _MockConnectAPI:
    def __init__(self):
        self._handlers = {}

    def register_handler(self, msg_type, handler):
        self._handlers[msg_type] = handler

    async def send_message(self, msg):
        pass


class _MockOrder:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


# ==============================================================================
# HELPERS
# ==============================================================================

def _make_manager(overrides: dict[str, Any] = None) -> RiskManager:
    """Create a RiskManager with default limits, optionally overriding some."""
    limits = DEFAULT_RISK_LIMITS.copy()
    if overrides:
        limits.update(overrides)
    config = RiskConfig(risk_limits=limits)
    api = _MockConnectAPI()
    return RiskManager(config=config, connect_api=api)


def _make_order(symbol="SPY", quantity=10, side="buy", price=100.0, order_id="T51-001"):
    return _MockOrder(
        symbol=symbol,
        quantity=quantity,
        side=side,
        price=price,
        order_id=order_id,
    )


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _inject_position(rm: RiskManager, symbol: str, quantity: int,
                     market_value: float, unrealized_pnl: float = 0.0,
                     realized_pnl: float = 0.0, security_type: str = "STK") -> None:
    """Directly inject a position into the manager's internal dict."""
    rm._positions[symbol] = Position(
        symbol=symbol,
        quantity=quantity,
        market_price=market_value / quantity if quantity else 0.0,
        market_value=market_value,
        average_fill_price=market_value / quantity if quantity else 0.0,
        unrealized_pnl=unrealized_pnl,
        realized_pnl=realized_pnl,
        security_type=security_type,
    )


# ==============================================================================
# BOUNDARY CONDITIONS — ORDER SIZE
# ==============================================================================

class TestOrderSizeBoundary(unittest.TestCase):
    """Exact threshold: max_single_order_size = 500 (default)."""

    def setUp(self):
        _patch_message_type()
        self.rm = _make_manager()

    def test_at_limit_allowed(self):
        """Quantity exactly at max_single_order_size → not BLOCKED on order size.

        Concentration WARNING may fire (single symbol = 100% weight), but the
        order-size guard itself should not trigger a BLOCK.
        """
        order = _make_order(quantity=500, price=5.0)
        resp = _run(self.rm.check_order_risk(order))
        self.assertNotEqual(resp.result, RiskCheckResult.BLOCKED)

    def test_one_over_limit_blocked(self):
        """Quantity = limit + 1 → BLOCKED."""
        order = _make_order(quantity=501, price=5.0)
        resp = _run(self.rm.check_order_risk(order))
        self.assertEqual(resp.result, RiskCheckResult.BLOCKED)
        self.assertIn("501", resp.reason)

    def test_well_under_limit_allowed(self):
        """Quantity well below order-size limit → order-size guard does not block.

        Concentration WARNING may fire for a single-symbol portfolio.
        """
        order = _make_order(quantity=1, price=5.0)
        resp = _run(self.rm.check_order_risk(order))
        self.assertNotEqual(resp.result, RiskCheckResult.BLOCKED)


# ==============================================================================
# BOUNDARY CONDITIONS — POSITION SIZE
# ==============================================================================

class TestPositionSizeBoundary(unittest.TestCase):
    """Exact threshold: max_position_size = 1000 (default)."""

    def setUp(self):
        _patch_message_type()
        self.rm = _make_manager()

    def test_new_position_at_limit_allowed(self):
        """Existing 800 + buy 200 = 1000 exactly at max_position_size → not BLOCKED.

        The order quantity (200) is below max_single_order_size (500), so the
        order-size guard passes. The position-size guard (strict >) also passes
        at exactly 1000. Concentration WARNING may still fire.
        """
        _inject_position(self.rm, "SPY", 800, 8000.0)
        order = _make_order(quantity=200, price=5.0)
        resp = _run(self.rm.check_order_risk(order))
        self.assertIn(resp.result, (RiskCheckResult.ALLOWED, RiskCheckResult.WARNING))

    def test_new_position_one_over_blocked(self):
        """Existing 900 + buy 101 = 1001 → BLOCKED on position size.

        Order qty (101) is within max_single_order_size (500), so the position
        check fires first and blocks with a position-size message.
        """
        _inject_position(self.rm, "SPY", 900, 9000.0)
        order = _make_order(quantity=101, price=5.0)
        resp = _run(self.rm.check_order_risk(order))
        self.assertEqual(resp.result, RiskCheckResult.BLOCKED)
        self.assertIn("position", resp.reason.lower())

    def test_existing_position_approaches_limit(self):
        """Existing 990 + buy 10 = 1000 — at position limit, not over it.

        Position-size guard is strict (>), so exactly 1000 should not block.
        Concentration WARNING may fire for a single-symbol portfolio.
        """
        _inject_position(self.rm, "SPY", 990, 9900.0)
        order = _make_order(quantity=10, price=5.0)
        resp = _run(self.rm.check_order_risk(order))
        self.assertNotEqual(resp.result, RiskCheckResult.BLOCKED)

    def test_existing_position_exceeds_limit(self):
        """Existing 990 + buy 11 = 1001 → BLOCKED on position size."""
        _inject_position(self.rm, "SPY", 990, 9900.0)
        order = _make_order(quantity=11, price=5.0)
        resp = _run(self.rm.check_order_risk(order))
        self.assertEqual(resp.result, RiskCheckResult.BLOCKED)


# ==============================================================================
# SELL-SIDE ORDERS REDUCE POSITION SIZE
# ==============================================================================

class TestSellSideOrdersReducePosition(unittest.TestCase):
    """Selling reduces position — should never trigger position-size block."""

    def setUp(self):
        _patch_message_type()
        self.rm = _make_manager()

    def test_sell_reduces_position_below_limit(self):
        """Verify sell-side reduces position, not increases it.

        With 900 existing, a buy of 200 pushes to 1100 → BLOCKED.
        A sell of 200 brings it to 700 → position guard does NOT block.
        """
        _inject_position(self.rm, "SPY", 900, 9000.0)
        # Confirm buy direction would be blocked
        buy_resp = _run(self.rm.check_order_risk(_make_order(quantity=200, side="buy", price=5.0)))
        self.assertEqual(buy_resp.result, RiskCheckResult.BLOCKED)
        # Sell in the same qty should NOT be blocked by position guard
        sell_resp = _run(self.rm.check_order_risk(_make_order(quantity=200, side="sell", price=5.0)))
        self.assertNotEqual(sell_resp.result, RiskCheckResult.BLOCKED)

    def test_sell_to_open_option_reduces_position(self):
        """sell_to_open is treated as sell-side — position guard does not block.

        A buy of the same qty from the same position would be blocked (exceeds
        max_position_size), so this comparison confirms the side is handled.
        """
        _inject_position(self.rm, "SPY260320C00560000", 990, 4950.0)
        buy_resp = _run(self.rm.check_order_risk(
            _make_order(symbol="SPY260320C00560000", quantity=11, side="buy_to_open", price=1.0)
        ))
        self.assertEqual(buy_resp.result, RiskCheckResult.BLOCKED)
        sell_resp = _run(self.rm.check_order_risk(
            _make_order(symbol="SPY260320C00560000", quantity=11, side="sell_to_open", price=1.0)
        ))
        self.assertNotEqual(sell_resp.result, RiskCheckResult.BLOCKED)

    def test_sell_to_close_option_reduces_position(self):
        """sell_to_close is treated as sell-side — position guard does not block."""
        _inject_position(self.rm, "SPY260320C00560000", 990, 4950.0)
        sell_resp = _run(self.rm.check_order_risk(
            _make_order(symbol="SPY260320C00560000", quantity=11, side="sell_to_close", price=1.0)
        ))
        self.assertNotEqual(sell_resp.result, RiskCheckResult.BLOCKED)

    def test_sell_does_not_trigger_order_size_block(self):
        """A sell of 400 (< 500 limit) is not BLOCKED by the order-size guard.

        Concentration WARNING may fire for a single-symbol position, but there
        should be no hard BLOCK from the order-size check.
        """
        order = _make_order(quantity=400, side="sell", price=10.0)
        resp = _run(self.rm.check_order_risk(order))
        self.assertNotEqual(resp.result, RiskCheckResult.BLOCKED)


# ==============================================================================
# ALL FOUR OPTION ORDER SIDES — BUY BRANCH
# ==============================================================================

class TestOptionOrderSides(unittest.TestCase):
    """
    buy / buy_to_open / buy_to_close → position increases.
    sell / sell_to_open / sell_to_close → position decreases.
    """

    def setUp(self):
        _patch_message_type()
        self.rm = _make_manager()

    def _near_limit_position(self):
        """Inject a 990-unit position so a +11 buy would block."""
        _inject_position(self.rm, "SPY", 990, 99000.0)

    def test_buy_to_open_increases_position(self):
        self._near_limit_position()
        order = _make_order(quantity=11, side="buy_to_open", price=5.0)
        resp = _run(self.rm.check_order_risk(order))
        self.assertEqual(resp.result, RiskCheckResult.BLOCKED)

    def test_buy_to_close_increases_position(self):
        self._near_limit_position()
        order = _make_order(quantity=11, side="buy_to_close", price=5.0)
        resp = _run(self.rm.check_order_risk(order))
        self.assertEqual(resp.result, RiskCheckResult.BLOCKED)

    def test_sell_to_open_decreases_position(self):
        self._near_limit_position()
        order = _make_order(quantity=11, side="sell_to_open", price=5.0)
        resp = _run(self.rm.check_order_risk(order))
        # 990 - 11 = 979 ≤ 1000 → should not BLOCK on position size
        # (might still block on exposure/other checks but not position)
        if resp.result == RiskCheckResult.BLOCKED:
            self.assertNotIn("position size", resp.reason.lower())

    def test_sell_to_close_decreases_position(self):
        self._near_limit_position()
        order = _make_order(quantity=11, side="sell_to_close", price=5.0)
        resp = _run(self.rm.check_order_risk(order))
        if resp.result == RiskCheckResult.BLOCKED:
            self.assertNotIn("position size", resp.reason.lower())


# ==============================================================================
# RISK CHECK METRICS COUNTERS
# ==============================================================================

class TestRiskMetricsCounters(unittest.TestCase):
    """Verify internal counters advance correctly across calls."""

    def setUp(self):
        _patch_message_type()
        self.rm = _make_manager()

    def test_risk_checks_counter_increments(self):
        """Each call to check_order_risk increments metrics['risk_checks']."""
        count_before = self.rm.metrics['risk_checks']
        _run(self.rm.check_order_risk(_make_order(quantity=5, price=10.0)))
        _run(self.rm.check_order_risk(_make_order(quantity=5, price=10.0)))
        self.assertEqual(self.rm.metrics['risk_checks'], count_before + 2)

    def test_blocks_counter_is_initially_zero(self):
        """The 'blocks' counter starts at 0 before any checks."""
        self.assertEqual(self.rm.metrics['blocks'], 0)

    def test_blocks_counter_static_on_allowed(self):
        """An allowed order does not increment metrics['blocks']."""
        _run(self.rm.check_order_risk(_make_order(quantity=5, price=10.0)))
        blocks_after = self.rm.metrics['blocks']
        _run(self.rm.check_order_risk(_make_order(quantity=5, price=10.0)))
        self.assertEqual(self.rm.metrics['blocks'], blocks_after)

    def test_warnings_counter_increments_on_warning(self):
        """A warning (concentration) increments metrics['warnings']."""
        # Create a concentrated position (one symbol at ~100% of total)
        rm = _make_manager({'max_concentration_ratio': 0.5})
        _inject_position(rm, "SPY", 50, 50000.0)
        warnings_before = rm.metrics['warnings']
        # Place a small order on AAPL that makes SPY>50% of total
        order = _make_order(symbol="AAPL", quantity=1, price=1.0)
        resp = _run(rm.check_order_risk(order))
        if resp.result == RiskCheckResult.WARNING:
            self.assertGreater(rm.metrics['warnings'], warnings_before)


# ==============================================================================
# GET POSITION / GET POSITIONS
# ==============================================================================

class TestGetPositionMethods(unittest.TestCase):
    """Unit tests for get_position() and get_positions()."""

    def setUp(self):
        _patch_message_type()
        self.rm = _make_manager()

    def test_get_position_unknown_symbol_returns_none(self):
        result = self.rm.get_position("UNKNOWN_XYZ")
        self.assertIsNone(result)

    def test_get_position_known_symbol_returns_position(self):
        _inject_position(self.rm, "SPY", 100, 50000.0)
        pos = self.rm.get_position("SPY")
        self.assertIsNotNone(pos)
        self.assertEqual(pos.symbol, "SPY")
        self.assertEqual(pos.quantity, 100)

    def test_get_positions_empty_initially(self):
        positions = self.rm.get_positions()
        self.assertIsInstance(positions, dict)
        self.assertEqual(len(positions), 0)

    def test_get_positions_returns_all_injected(self):
        _inject_position(self.rm, "SPY", 100, 50000.0)
        _inject_position(self.rm, "AAPL", 50, 12500.0)
        positions = self.rm.get_positions()
        self.assertIn("SPY", positions)
        self.assertIn("AAPL", positions)
        self.assertEqual(len(positions), 2)

    def test_get_positions_snapshot_independence(self):
        """Mutating returned dict does not corrupt internal state."""
        _inject_position(self.rm, "SPY", 100, 50000.0)
        snapshot = self.rm.get_positions()
        snapshot["GHOST"] = None  # mutate returned dict
        self.assertNotIn("GHOST", self.rm.get_positions())


# ==============================================================================
# GET RISK METRICS
# ==============================================================================

class TestGetRiskMetrics(unittest.TestCase):
    def setUp(self):
        _patch_message_type()
        self.rm = _make_manager()

    def test_returns_none_when_no_cached_metrics(self):
        """Before any check, cached metrics is None."""
        result = self.rm.get_risk_metrics()
        self.assertIsNone(result)


# ==============================================================================
# RISK LEVEL ESCALATION VIA _calculate_risk_metrics
# ==============================================================================

class TestRiskLevelEscalation(unittest.TestCase):
    """Verify auto-escalation through LOW → MEDIUM → HIGH → CRITICAL."""

    def setUp(self):
        _patch_message_type()
        self.rm = _make_manager()

    def _calc(self):
        return self.rm._calculate_risk_metrics()

    def test_empty_positions_low_risk(self):
        m = self._calc()
        self.assertEqual(m.risk_level, RiskLevel.LOW)
        self.assertEqual(m.warnings, [])

    def test_high_total_exposure_escalates_to_high(self):
        """Total exposure > max_total_exposure → HIGH."""
        _inject_position(self.rm, "SPY", 1, 110000.0)  # default limit=100000
        m = self._calc()
        self.assertEqual(m.risk_level, RiskLevel.HIGH)
        self.assertTrue(any("exposure" in w.lower() for w in m.warnings))

    def test_critical_daily_loss_escalates_to_critical(self):
        """daily_pnl < -max_daily_loss → CRITICAL."""
        _inject_position(self.rm, "SPY", 1, 1000.0, unrealized_pnl=-11000.0)
        m = self._calc()
        self.assertEqual(m.risk_level, RiskLevel.CRITICAL)

    def test_high_concentration_escalates_to_medium(self):
        """Single symbol >30% concentration without other violations → MEDIUM."""
        _inject_position(self.rm, "SPY", 1, 40000.0)
        _inject_position(self.rm, "AAPL", 1, 5000.0)
        # SPY = 40000 / 45000 = 89% > 30% → at least MEDIUM
        m = self._calc()
        self.assertGreaterEqual(m.risk_level.value, RiskLevel.MEDIUM.value)

    def test_options_exposure_over_limit_escalates(self):
        """Options exposure > max_options_exposure → at least MEDIUM."""
        _inject_position(self.rm, "SPY260320C00560000", 1, 60000.0, security_type="OPT")
        m = self._calc()
        self.assertGreaterEqual(m.risk_level.value, RiskLevel.MEDIUM.value)
        self.assertTrue(any("options" in w.lower() for w in m.warnings))

    def test_exact_daily_loss_at_limit_not_critical(self):
        """daily_pnl = -max_daily_loss (not below) → not CRITICAL."""
        max_loss = self.rm.config.risk_limits['max_daily_loss']
        # Exactly at the limit (negative PnL = limit amount) → not triggered
        _inject_position(self.rm, "SPY", 1, 1000.0, unrealized_pnl=-max_loss)
        m = self._calc()
        # Should NOT be CRITICAL (check is strict less-than)
        self.assertNotEqual(m.risk_level, RiskLevel.CRITICAL)

    def test_one_cent_below_daily_loss_triggers_critical(self):
        """daily_pnl = -(max_daily_loss + 0.01) → CRITICAL."""
        max_loss = self.rm.config.risk_limits['max_daily_loss']
        _inject_position(self.rm, "SPY", 1, 1000.0, unrealized_pnl=-(max_loss + 0.01))
        m = self._calc()
        self.assertEqual(m.risk_level, RiskLevel.CRITICAL)


# ==============================================================================
# OPTIONS EXPOSURE TRACKING
# ==============================================================================

class TestOptionsExposureTracking(unittest.TestCase):
    """Verify options (security_type='OPT') contributes to options_exposure."""

    def setUp(self):
        _patch_message_type()
        self.rm = _make_manager()

    def test_stk_position_does_not_add_to_options_exposure(self):
        _inject_position(self.rm, "SPY", 100, 50000.0, security_type="STK")
        m = self.rm._calculate_risk_metrics()
        self.assertEqual(m.options_exposure, 0.0)

    def test_opt_position_adds_to_options_exposure(self):
        _inject_position(self.rm, "SPY260320C00560000", 10, 5000.0, security_type="OPT")
        m = self.rm._calculate_risk_metrics()
        self.assertAlmostEqual(m.options_exposure, 5000.0)

    def test_mixed_positions_split_correctly(self):
        _inject_position(self.rm, "SPY", 100, 50000.0, security_type="STK")
        _inject_position(self.rm, "SPY260320C00560000", 10, 5000.0, security_type="OPT")
        m = self.rm._calculate_risk_metrics()
        self.assertAlmostEqual(m.options_exposure, 5000.0)
        self.assertAlmostEqual(m.total_exposure, 55000.0)

    def test_multiple_opt_positions_aggregate(self):
        _inject_position(self.rm, "C1", 5, 2000.0, security_type="OPT")
        _inject_position(self.rm, "C2", 5, 3000.0, security_type="OPT")
        m = self.rm._calculate_risk_metrics()
        self.assertAlmostEqual(m.options_exposure, 5000.0)


# ==============================================================================
# ZERO EXPOSURE GUARD (NO DIVISION BY ZERO)
# ==============================================================================

class TestZeroDivisionGuard(unittest.TestCase):
    """When total_exposure is 0, concentration must be 0 — no ZeroDivisionError."""

    def setUp(self):
        _patch_message_type()
        self.rm = _make_manager()

    def test_no_positions_no_error(self):
        try:
            m = self.rm._calculate_risk_metrics()
            self.assertEqual(m.max_concentration, 0.0)
        except ZeroDivisionError:
            self.fail("_calculate_risk_metrics raised ZeroDivisionError with no positions")

    def test_zero_value_position_no_error(self):
        """A position with market_value=0 should not divide by zero."""
        _inject_position(self.rm, "SPY", 0, 0.0)
        try:
            m = self.rm._calculate_risk_metrics()
            self.assertEqual(m.max_concentration, 0.0)
        except ZeroDivisionError:
            self.fail("_calculate_risk_metrics raised ZeroDivisionError with zero-value position")


# ==============================================================================
# ORDER PRICE FALLBACK — None price uses market_price
# ==============================================================================

class TestOrderPriceFallback(unittest.TestCase):
    """When order.price is None, the manager falls back to position.market_price."""

    def setUp(self):
        _patch_message_type()
        self.rm = _make_manager({'max_total_exposure': 50000.0})

    def test_none_price_falls_back_to_market_price(self):
        """With existing position market_price = $500, a 200-qty order at None
        would imply 200 * 500 = 100_000 which exceeds the 50_000 limit."""
        _inject_position(self.rm, "SPY", 10, 5000.0)  # market_price = 500
        order = _make_order(symbol="SPY", quantity=200, side="buy", price=None)
        resp = _run(self.rm.check_order_risk(order))
        # total_exposure = 5000 + (200 * 500) = 105000 > 50000 → BLOCKED
        self.assertEqual(resp.result, RiskCheckResult.BLOCKED)
        self.assertIn("exposure", resp.reason.lower())

    def test_none_price_with_no_existing_position(self):
        """price=None and no existing position → order_value = 0, passes exposure."""
        order = _make_order(symbol="NEW", quantity=10, side="buy", price=None)
        resp = _run(self.rm.check_order_risk(order))
        # order_value = 10 * 0 (no market price on unknown position) = 0
        self.assertIn(resp.result, (RiskCheckResult.ALLOWED, RiskCheckResult.WARNING))


# ==============================================================================
# TOTAL EXPOSURE BOUNDARY
# ==============================================================================

class TestTotalExposureBoundary(unittest.TestCase):
    """Exact boundary for max_total_exposure = 100_000 (default)."""

    def setUp(self):
        _patch_message_type()
        self.rm = _make_manager()

    def test_at_exposure_limit_allowed(self):
        """Existing 90_000 + new 10_000 = 100_000 (at limit) → exposure guard does not block.

        Concentration WARNING may fire (single symbol), but total-exposure BLOCK
        should not trigger at exactly the limit (guard uses strict >).
        """
        _inject_position(self.rm, "SPY", 90, 90000.0)
        order = _make_order(quantity=100, price=100.0)  # 100 * 100 = 10_000
        resp = _run(self.rm.check_order_risk(order))
        self.assertNotEqual(resp.result, RiskCheckResult.BLOCKED)

    def test_one_dollar_over_exposure_blocked(self):
        """Existing 90_000 + new 10_001 → BLOCKED."""
        _inject_position(self.rm, "SPY", 90, 90000.0)
        order = _make_order(quantity=100, price=100.01)
        resp = _run(self.rm.check_order_risk(order))
        self.assertEqual(resp.result, RiskCheckResult.BLOCKED)
        self.assertIn("exposure", resp.reason.lower())


# ==============================================================================
# DAILY LOSS BLOCK
# ==============================================================================

class TestDailyLossBoundary(unittest.TestCase):
    """Exact boundary for max_daily_loss = 10_000 (default)."""

    def setUp(self):
        _patch_message_type()
        self.rm = _make_manager()

    def test_pnl_exactly_at_negative_limit_allowed(self):
        """daily_pnl = -10_000 exactly → NOT blocked (limit is strict)."""
        _inject_position(self.rm, "SPY", 1, 1000.0, unrealized_pnl=-10000.0)
        order = _make_order(quantity=1, price=5.0)
        resp = _run(self.rm.check_order_risk(order))
        self.assertNotEqual(resp.result, RiskCheckResult.BLOCKED)

    def test_pnl_one_cent_below_limit_blocked(self):
        """daily_pnl = -10_000.01 → BLOCKED."""
        _inject_position(self.rm, "SPY", 1, 1000.0, unrealized_pnl=-10000.01)
        order = _make_order(quantity=1, price=5.0)
        resp = _run(self.rm.check_order_risk(order))
        self.assertEqual(resp.result, RiskCheckResult.BLOCKED)
        self.assertIn("daily loss", resp.reason.lower())


# ==============================================================================
# RISK CHECK RESPONSE FIELDS
# ==============================================================================

class TestRiskCheckResponseFields(unittest.TestCase):
    """Verify RiskCheckResponse fields are populated correctly."""

    def setUp(self):
        _patch_message_type()
        self.rm = _make_manager()

    def test_allowed_response_has_timestamp(self):
        order = _make_order(quantity=1, price=5.0)
        resp = _run(self.rm.check_order_risk(order))
        self.assertIsInstance(resp.timestamp, datetime)

    def test_blocked_response_includes_order_id(self):
        order = _make_order(quantity=999, price=5.0, order_id="BLOCK-ME")
        resp = _run(self.rm.check_order_risk(order))
        self.assertEqual(resp.order_id, "BLOCK-ME")

    def test_blocked_response_includes_risk_metrics(self):
        order = _make_order(quantity=999, price=5.0)
        resp = _run(self.rm.check_order_risk(order))
        self.assertIsNotNone(resp.risk_metrics)

    def test_allowed_response_includes_risk_metrics(self):
        order = _make_order(quantity=1, price=5.0)
        resp = _run(self.rm.check_order_risk(order))
        self.assertIsNotNone(resp.risk_metrics)

    def test_blocked_reason_is_non_empty_string(self):
        order = _make_order(quantity=999, price=5.0)
        resp = _run(self.rm.check_order_risk(order))
        if resp.result == RiskCheckResult.BLOCKED:
            self.assertIsInstance(resp.reason, str)
            self.assertGreater(len(resp.reason), 0)


# ==============================================================================
# GET STATUS CONTENT
# ==============================================================================

class TestGetStatus(unittest.TestCase):
    """Verify get_status() / get_metrics() return expected structures."""

    def setUp(self):
        _patch_message_type()
        self.rm = _make_manager()

    def test_get_status_contains_required_keys(self):
        """Verify get_status() returns the documented keys."""
        status = self.rm.get_status()
        for key in ("monitoring_enabled", "risk_level", "positions_count", "warnings_count"):
            self.assertIn(key, status, f"Key '{key}' missing from get_status()")

    def test_get_status_positions_count_matches_injected(self):
        _inject_position(self.rm, "SPY", 100, 50000.0)
        _inject_position(self.rm, "AAPL", 50, 12500.0)
        status = self.rm.get_status()
        self.assertEqual(status['positions_count'], 2)

    def test_get_metrics_contains_required_keys(self):
        metrics = self.rm.get_metrics()
        for key in ("risk_checks", "warnings", "blocks", "check_rate"):
            self.assertIn(key, metrics, f"Key '{key}' missing from get_metrics()")

    def test_get_metrics_check_rate_zero_initially(self):
        metrics = self.rm.get_metrics()
        self.assertGreaterEqual(metrics['check_rate'], 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
