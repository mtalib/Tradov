#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT43_OrderManager_Test.py
Purpose: Unit tests for SpyderB02_OrderManager (Tradier-based)

Author: GitHub Copilot
Year Created: 2026
Last Updated: 2026-02-25 Time: 20:00:00

Description:
    Comprehensive unit tests for the OrderManager module covering:
    - Order submission (equity, option, multileg)
    - Order cancellation and modification
    - Order queries (by ID, symbol, state)
    - State transitions and TRADIER_STATUS_MAP
    - Iron Condor and Credit Spread convenience methods
    - Callbacks (on_fill, on_state_change)
    - Metrics tracking
    - Singleton / factory functions
    - Async wrappers
    - Error handling

Usage:
    pytest Spyder/SpyderT_Testing/SpyderT43_OrderManager_Test.py -v
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime

# Import module under test
from Spyder.SpyderB_Broker.SpyderB02_OrderManager import (
    OrderManager,
    Order,
    OrderResult,
    OrderState,
    OrderStatus,
    OrderRequest,
    ExecutionReport,
    SecurityType,
    TRADIER_STATUS_MAP,
    create_order_manager,
)
from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
    TradierAPIError,
    OptionLeg,
    OrderSide as TradierOrderSide,
    OrderType as TradierOrderType,
    OrderDuration as TradierOrderDuration,
    OrderClass as TradierOrderClass,
)


# ==============================================================================
# ENUM AND DATA STRUCTURE TESTS
# ==============================================================================


class TestOrderState:
    """Tests for OrderState enum and state classification."""

    def test_all_states_defined(self):
        """All expected states exist."""
        expected = {
            "PENDING", "SUBMITTED", "OPEN", "PARTIALLY_FILLED", "FILLED",
            "CANCELLED", "REJECTED", "EXPIRED", "PENDING_CANCEL", "ERROR",
            "UNKNOWN",
        }
        actual = {s.name for s in OrderState}
        assert expected == actual

    def test_active_states(self):
        """Active states include SUBMITTED, OPEN, PARTIALLY_FILLED, PENDING_CANCEL."""
        assert OrderState.SUBMITTED.is_active
        assert OrderState.OPEN.is_active
        assert OrderState.PARTIALLY_FILLED.is_active
        assert OrderState.PENDING_CANCEL.is_active
        # Non-active
        assert not OrderState.PENDING.is_active
        assert not OrderState.FILLED.is_active
        assert not OrderState.CANCELLED.is_active
        assert not OrderState.REJECTED.is_active

    def test_terminal_states(self):
        """Terminal states include FILLED, CANCELLED, REJECTED, EXPIRED, ERROR."""
        assert OrderState.FILLED.is_terminal
        assert OrderState.CANCELLED.is_terminal
        assert OrderState.REJECTED.is_terminal
        assert OrderState.EXPIRED.is_terminal
        assert OrderState.ERROR.is_terminal
        # Non-terminal
        assert not OrderState.PENDING.is_terminal
        assert not OrderState.SUBMITTED.is_terminal
        assert not OrderState.OPEN.is_terminal

    def test_backward_compat_alias(self):
        """OrderStatus is an alias for OrderState."""
        assert OrderStatus is OrderState

    def test_order_request_alias(self):
        """OrderRequest is an alias for Order."""
        assert OrderRequest is Order


class TestTradierStatusMap:
    """Tests for the TRADIER_STATUS_MAP constant."""

    def test_all_tradier_statuses_mapped(self):
        """All critical Tradier statuses are mapped."""
        assert TRADIER_STATUS_MAP["pending"] == OrderState.SUBMITTED
        assert TRADIER_STATUS_MAP["open"] == OrderState.OPEN
        assert TRADIER_STATUS_MAP["partially_filled"] == OrderState.PARTIALLY_FILLED
        assert TRADIER_STATUS_MAP["filled"] == OrderState.FILLED
        assert TRADIER_STATUS_MAP["canceled"] == OrderState.CANCELLED
        assert TRADIER_STATUS_MAP["rejected"] == OrderState.REJECTED
        assert TRADIER_STATUS_MAP["expired"] == OrderState.EXPIRED

    def test_unknown_status_fallback(self):
        """Unknown status strings give UNKNOWN via .get() default."""
        assert TRADIER_STATUS_MAP.get("bogus", OrderState.UNKNOWN) == OrderState.UNKNOWN


class TestSecurityType:
    """Tests for SecurityType enum."""

    def test_security_types(self):
        """All expected security types exist."""
        assert SecurityType.EQUITY.value == "equity"
        assert SecurityType.OPTION.value == "option"
        assert SecurityType.MULTILEG.value == "multileg"


class TestOrderDataclass:
    """Tests for the Order dataclass."""

    def test_default_values(self):
        """Order has sensible defaults."""
        order = Order()
        assert order.symbol == ""
        assert order.side == "buy"
        assert order.order_type == "market"
        assert order.quantity == 0
        assert order.state == OrderState.PENDING
        assert order.security_type == SecurityType.EQUITY
        assert order.legs == []

    def test_remaining_quantity_set_from_quantity(self):
        """remaining_quantity is auto-set to quantity in __post_init__."""
        order = Order(quantity=50)
        assert order.remaining_quantity == 50

    def test_security_type_string_coercion(self):
        """String security_type is coerced to enum."""
        order = Order(security_type="option")
        assert order.security_type == SecurityType.OPTION

    def test_order_id_auto_generated(self):
        """Each order gets a unique UUID."""
        o1 = Order()
        o2 = Order()
        assert o1.order_id != o2.order_id
        assert len(o1.order_id) == 36  # UUID format


# ==============================================================================
# ORDER MANAGER INITIALIZATION TESTS
# ==============================================================================


class TestOrderManagerInit:
    """Tests for OrderManager initialization."""

    def test_init_with_client(self, mock_tradier_client):
        """OrderManager accepts a TradierClient instance."""
        mgr = OrderManager(tradier_client=mock_tradier_client, enable_streaming=False)
        assert mgr.tradier is mock_tradier_client
        assert not mgr._streaming_enabled

    def test_init_creates_empty_orders(self, mock_tradier_client):
        """OrderManager starts with empty order store."""
        mgr = OrderManager(tradier_client=mock_tradier_client)
        assert len(mgr._orders) == 0

    def test_init_metrics_zeroed(self, mock_tradier_client):
        """Metrics are zeroed on init."""
        mgr = OrderManager(tradier_client=mock_tradier_client)
        assert mgr.metrics["orders_submitted"] == 0
        assert mgr.metrics["orders_filled"] == 0
        assert mgr.metrics["orders_cancelled"] == 0
        assert mgr.metrics["orders_rejected"] == 0


# ==============================================================================
# ORDER SUBMISSION TESTS
# ==============================================================================


class TestSubmitOrder:
    """Tests for order submission routing."""

    def test_submit_equity_order(self, order_manager, sample_equity_order, mock_tradier_client):
        """Equity order is routed to place_order with EQUITY class."""
        result = order_manager.submit_order(sample_equity_order)

        assert result.success is True
        assert result.tradier_order_id == 99001
        assert result.operation == "submit"
        mock_tradier_client.place_order.assert_called_once()

        # Verify the order state was updated
        stored = order_manager.get_order(sample_equity_order.order_id)
        assert stored.state == OrderState.OPEN
        assert stored.tradier_order_id == 99001

    def test_submit_option_order(self, order_manager, sample_option_order, mock_tradier_client):
        """Option order is routed via place_order with OPTION class."""
        result = order_manager.submit_order(sample_option_order)

        assert result.success is True
        mock_tradier_client.place_order.assert_called_once()

        # Verify option-specific params
        call_kwargs = mock_tradier_client.place_order.call_args.kwargs
        assert call_kwargs["symbol"].startswith("SPXW")

    def test_submit_option_order_rejects_non_spxw_entry(self, order_manager, mock_tradier_client):
        """Non-SPXW option entry orders are fail-closed before Tradier routing."""
        order = Order(
            symbol="SPY",
            side="buy_to_open",
            order_type="limit",
            quantity=1,
            price=1.25,
            duration="day",
            security_type=SecurityType.OPTION,
            order_class="option",
            option_symbol="SPY260220C00585000",
        )

        result = order_manager.submit_order(order)

        assert result.success is False
        assert result.error_code == "SPXW_ONLY_OPTION_ENTRY_POLICY"
        mock_tradier_client.place_order.assert_not_called()

    def test_submit_option_close_allows_non_spxw_symbol(self, order_manager, mock_tradier_client):
        """Risk-reducing option closes remain allowed for legacy positions."""
        order = Order(
            symbol="SPY",
            side="sell_to_close",
            order_type="limit",
            quantity=1,
            price=1.25,
            duration="day",
            security_type=SecurityType.OPTION,
            order_class="option",
            option_symbol="SPY260220C00585000",
        )

        result = order_manager.submit_order(order)

        assert result.success is True
        call_kwargs = mock_tradier_client.place_order.call_args.kwargs
        assert call_kwargs["symbol"] == "SPY260220C00585000"

    def test_submit_multileg_order(self, order_manager, sample_multileg_order, mock_tradier_client):
        """Multileg order is routed to place_multileg_order."""
        result = order_manager.submit_order(sample_multileg_order)

        assert result.success is True
        assert result.tradier_order_id == 99002
        mock_tradier_client.place_multileg_order.assert_called_once()

    def test_submit_duplicate_rejected(self, order_manager, sample_equity_order):
        """Submitting the same order_id twice returns DUPLICATE error."""
        order_manager.submit_order(sample_equity_order)
        result = order_manager.submit_order(sample_equity_order)

        assert result.success is False
        assert result.error_code == "DUPLICATE_ORDER_ID"

    def test_submit_order_api_error(self, order_manager, sample_equity_order, mock_tradier_client):
        """TradierAPIError during submission marks order REJECTED."""
        mock_tradier_client.place_order.side_effect = TradierAPIError("Server error")

        result = order_manager.submit_order(sample_equity_order)

        assert result.success is False
        assert result.error_code == "SUBMISSION_ERROR"
        stored = order_manager.get_order(sample_equity_order.order_id)
        assert stored.state == OrderState.REJECTED

    def test_submit_order_no_id_in_response(self, order_manager, sample_equity_order, mock_tradier_client):
        """Missing order ID in response marks order REJECTED."""
        mock_tradier_client.place_order.return_value = {"order": {}}

        result = order_manager.submit_order(sample_equity_order)

        assert result.success is False
        stored = order_manager.get_order(sample_equity_order.order_id)
        assert stored.state == OrderState.REJECTED

    def test_submit_increments_metrics(self, order_manager, sample_equity_order):
        """Successful submission increments orders_submitted metric."""
        order_manager.submit_order(sample_equity_order)
        assert order_manager.metrics["orders_submitted"] == 1


# ==============================================================================
# IRON CONDOR & CREDIT SPREAD TESTS
# ==============================================================================


class TestStrategyOrders:
    """Tests for Iron Condor and Credit Spread convenience methods."""

    def test_submit_iron_condor(self, order_manager, mock_tradier_client):
        """Iron Condor order routes to place_iron_condor."""
        result = order_manager.submit_iron_condor(
            symbol="SPXW",
            expiration="2026-02-20",
            put_buy_strike=570.0,
            put_sell_strike=575.0,
            call_sell_strike=595.0,
            call_buy_strike=600.0,
            quantity=2,
            price=1.20,
        )

        assert result.success is True
        assert result.tradier_order_id == 99003
        assert result.operation == "submit_iron_condor"
        mock_tradier_client.place_iron_condor.assert_called_once()

    def test_submit_credit_spread_put(self, order_manager, mock_tradier_client):
        """Put credit spread routes to place_credit_spread."""
        result = order_manager.submit_credit_spread(
            symbol="SPXW",
            expiration="2026-02-20",
            sell_strike=575.0,
            buy_strike=570.0,
            option_type="P",
            quantity=5,
            price=0.65,
        )

        assert result.success is True
        assert result.tradier_order_id == 99004
        assert result.operation == "submit_credit_spread"
        mock_tradier_client.place_credit_spread.assert_called_once()

    def test_submit_credit_spread_call(self, order_manager, mock_tradier_client):
        """Call credit spread also works."""
        result = order_manager.submit_credit_spread(
            symbol="SPXW",
            expiration="2026-02-20",
            sell_strike=595.0,
            buy_strike=600.0,
            option_type="C",
            quantity=3,
        )

        assert result.success is True

    def test_iron_condor_error_handling(self, order_manager, mock_tradier_client):
        """Iron Condor handles exceptions gracefully."""
        mock_tradier_client.place_iron_condor.side_effect = TradierAPIError("Margin exceeded")

        result = order_manager.submit_iron_condor(
            symbol="SPXW",
            expiration="2026-02-20",
            put_buy_strike=570.0,
            put_sell_strike=575.0,
            call_sell_strike=595.0,
            call_buy_strike=600.0,
        )

        assert result.success is False


# ==============================================================================
# CANCEL ORDER TESTS
# ==============================================================================


class TestCancelOrder:
    """Tests for order cancellation."""

    def test_cancel_active_order(self, order_manager, sample_equity_order, mock_tradier_client):
        """Can cancel an order in OPEN state."""
        order_manager.submit_order(sample_equity_order)
        result = order_manager.cancel_order(sample_equity_order.order_id)

        assert result.success is True
        assert result.operation == "cancel"
        mock_tradier_client.cancel_order.assert_called_once_with(99001)

        stored = order_manager.get_order(sample_equity_order.order_id)
        assert stored.state == OrderState.CANCELLED

    def test_cancel_nonexistent_order(self, order_manager):
        """Cancelling non-existent order returns ORDER_NOT_FOUND."""
        result = order_manager.cancel_order("nonexistent-uuid")
        assert result.success is False
        assert result.error_code == "ORDER_NOT_FOUND"

    def test_cancel_terminal_order(self, order_manager, sample_equity_order):
        """Cannot cancel an order already in terminal state."""
        order_manager.submit_order(sample_equity_order)
        order_manager.cancel_order(sample_equity_order.order_id)

        # Try cancelling again — should fail (CANCELLED is terminal, not active)
        result = order_manager.cancel_order(sample_equity_order.order_id)
        assert result.success is False
        assert result.error_code == "INVALID_STATE"

    def test_cancel_api_error_reverts_state(self, order_manager, sample_equity_order, mock_tradier_client):
        """Cancel failure reverts order from PENDING_CANCEL to OPEN."""
        order_manager.submit_order(sample_equity_order)
        mock_tradier_client.cancel_order.side_effect = TradierAPIError("Cancel rejected")

        result = order_manager.cancel_order(sample_equity_order.order_id)

        assert result.success is False
        stored = order_manager.get_order(sample_equity_order.order_id)
        assert stored.state == OrderState.OPEN  # reverted

    def test_cancel_increments_metrics(self, order_manager, sample_equity_order):
        """Successful cancel increments orders_cancelled metric."""
        order_manager.submit_order(sample_equity_order)
        order_manager.cancel_order(sample_equity_order.order_id)
        assert order_manager.metrics["orders_cancelled"] == 1


# ==============================================================================
# MODIFY ORDER TESTS
# ==============================================================================


class TestModifyOrder:
    """Tests for order modification."""

    def test_modify_price(self, order_manager, sample_equity_order, mock_tradier_client):
        """Can modify limit price of an active order."""
        order_manager.submit_order(sample_equity_order)

        result = order_manager.modify_order(
            sample_equity_order.order_id, price=582.00
        )

        assert result.success is True
        assert result.operation == "modify"
        mock_tradier_client.modify_order.assert_called_once()

        stored = order_manager.get_order(sample_equity_order.order_id)
        assert stored.price == 582.00

    def test_modify_nonexistent(self, order_manager):
        """Modifying non-existent order fails."""
        result = order_manager.modify_order("no-such-id", price=100.0)
        assert result.success is False
        assert result.error_code == "ORDER_NOT_FOUND"

    def test_modify_terminal_order(self, order_manager, sample_equity_order):
        """Cannot modify terminal order."""
        order_manager.submit_order(sample_equity_order)
        order_manager.cancel_order(sample_equity_order.order_id)

        result = order_manager.modify_order(
            sample_equity_order.order_id, price=590.00
        )
        assert result.success is False
        assert result.error_code == "INVALID_STATE"

    def test_modify_multiple_fields(self, order_manager, sample_equity_order, mock_tradier_client):
        """Can modify price, stop_price, order_type, and duration together."""
        order_manager.submit_order(sample_equity_order)

        result = order_manager.modify_order(
            sample_equity_order.order_id,
            price=581.00,
            stop_price=578.00,
            order_type="stop_limit",
            duration="gtc",
        )

        assert result.success is True
        stored = order_manager.get_order(sample_equity_order.order_id)
        assert stored.price == 581.00
        assert stored.stop_price == 578.00
        assert stored.order_type == "stop_limit"
        assert stored.duration == "gtc"


# ==============================================================================
# ORDER QUERY TESTS
# ==============================================================================


class TestOrderQueries:
    """Tests for order retrieval methods."""

    def test_get_order_by_id(self, order_manager, sample_equity_order):
        """Can retrieve order by local UUID."""
        order_manager.submit_order(sample_equity_order)
        found = order_manager.get_order(sample_equity_order.order_id)
        assert found is not None
        assert found.symbol == "SPY"

    def test_get_order_not_found(self, order_manager):
        """Returns None for unknown order ID."""
        assert order_manager.get_order("no-such-uuid") is None

    def test_get_order_by_tradier_id(self, order_manager, sample_equity_order):
        """Can retrieve order by Tradier integer ID."""
        order_manager.submit_order(sample_equity_order)
        found = order_manager.get_order_by_tradier_id(99001)
        assert found is not None
        assert found.order_id == sample_equity_order.order_id

    def test_get_orders_by_symbol(self, order_manager, sample_equity_order):
        """Can filter orders by symbol."""
        order_manager.submit_order(sample_equity_order)
        results = order_manager.get_orders_by_symbol("SPY")
        assert len(results) == 1
        assert results[0].symbol == "SPY"

        empty = order_manager.get_orders_by_symbol("AAPL")
        assert len(empty) == 0

    def test_get_orders_by_state(self, order_manager, sample_equity_order):
        """Can filter orders by OrderState."""
        order_manager.submit_order(sample_equity_order)
        open_orders = order_manager.get_orders_by_state(OrderState.OPEN)
        assert len(open_orders) == 1

        filled = order_manager.get_orders_by_state(OrderState.FILLED)
        assert len(filled) == 0

    def test_get_active_orders(self, order_manager, sample_equity_order):
        """get_active_orders returns only non-terminal orders."""
        order_manager.submit_order(sample_equity_order)
        active = order_manager.get_active_orders()
        assert len(active) == 1

        order_manager.cancel_order(sample_equity_order.order_id)
        active = order_manager.get_active_orders()
        assert len(active) == 0

    def test_get_all_orders(self, order_manager, sample_equity_order, sample_option_order):
        """get_all_orders returns all tracked orders."""
        order_manager.submit_order(sample_equity_order)
        order_manager.submit_order(sample_option_order)
        all_orders = order_manager.get_all_orders()
        assert len(all_orders) == 2


# ==============================================================================
# CALLBACK TESTS
# ==============================================================================


class TestCallbacks:
    """Tests for fill and state-change callbacks."""

    def test_on_fill_callback(self, order_manager, sample_equity_order):
        """Fill callback is invoked when _process_fill is called."""
        fill_reports = []

        def capture_fill(order, report):
            fill_reports.append((order, report))

        order_manager.on_fill(capture_fill)
        order_manager.submit_order(sample_equity_order)

        # Simulate a fill
        report = ExecutionReport(
            order_id=sample_equity_order.order_id,
            tradier_order_id=99001,
            symbol="SPY",
            side="buy",
            quantity=100,
            price=580.50,
        )
        order_manager._process_fill(sample_equity_order, report)

        assert len(fill_reports) == 1
        assert fill_reports[0][1].price == 580.50

    def test_on_state_change_callback_registered(self, order_manager):
        """State change callbacks can be registered."""
        cb = Mock()
        order_manager.on_state_change(cb)
        assert cb in order_manager._on_state_change_callbacks

    def test_fill_updates_order_fields(self, order_manager, sample_equity_order):
        """_process_fill updates filled_quantity, average_fill_price, state."""
        order_manager.submit_order(sample_equity_order)

        report = ExecutionReport(
            order_id=sample_equity_order.order_id,
            quantity=100,
            price=580.50,
        )
        order_manager._process_fill(sample_equity_order, report)

        assert sample_equity_order.filled_quantity == 100
        assert sample_equity_order.remaining_quantity == 0
        assert sample_equity_order.average_fill_price == 580.50
        assert sample_equity_order.state == OrderState.FILLED

    def test_partial_fill(self, order_manager, sample_equity_order):
        """Partial fills leave order in PARTIALLY_FILLED state."""
        order_manager.submit_order(sample_equity_order)

        report = ExecutionReport(
            order_id=sample_equity_order.order_id,
            quantity=50,
            price=580.00,
        )
        order_manager._process_fill(sample_equity_order, report)

        assert sample_equity_order.filled_quantity == 50
        assert sample_equity_order.remaining_quantity == 50
        assert sample_equity_order.state == OrderState.PARTIALLY_FILLED


# ==============================================================================
# ORDER FACTORY TESTS
# ==============================================================================


class TestCreateOrder:
    """Tests for the create_order convenience method."""

    def test_create_equity_order(self, order_manager):
        """create_order defaults to EQUITY."""
        order = order_manager.create_order(
            symbol="SPY", side="buy", quantity=100, price=580.0
        )
        assert order.security_type == SecurityType.EQUITY
        assert order.order_class == "equity"
        assert order.state == OrderState.PENDING

    def test_create_option_order(self, order_manager):
        """create_order with option_symbol sets OPTION type."""
        order = order_manager.create_order(
            symbol="SPY",
            side="buy_to_open",
            quantity=5,
            price=3.50,
            option_symbol="SPY260220C00585000",
        )
        assert order.security_type == SecurityType.OPTION
        assert order.order_class == "option"


# ==============================================================================
# METRICS AND STATUS TESTS
# ==============================================================================


class TestMetricsAndStatus:
    """Tests for get_metrics and get_status."""

    def test_get_metrics_structure(self, order_manager):
        """get_metrics returns expected keys."""
        metrics = order_manager.get_metrics()
        expected_keys = {
            "orders_submitted", "orders_filled", "orders_cancelled",
            "orders_rejected", "success_rate", "total_volume",
            "total_commission", "active_orders", "total_tracked",
            "uptime_seconds", "start_time", "streaming_enabled",
            "sse_connected",
        }
        assert expected_keys.issubset(set(metrics.keys()))

    def test_success_rate_calculation(self, order_manager, sample_equity_order):
        """Success rate is filled / submitted * 100."""
        order_manager.submit_order(sample_equity_order)

        # Simulate fill
        report = ExecutionReport(
            order_id=sample_equity_order.order_id,
            quantity=100,
            price=580.50,
        )
        order_manager._process_fill(sample_equity_order, report)

        metrics = order_manager.get_metrics()
        assert metrics["success_rate"] == 100.0

    def test_get_status_structure(self, order_manager, mock_tradier_client):
        """get_status returns broker, account, environment info."""
        status = order_manager.get_status()
        assert status["broker"] == "Tradier"
        assert status["account_id"] == "MOCK_ACCT"
        assert "metrics" in status


# ==============================================================================
# REFRESH ORDER TESTS
# ==============================================================================


class TestRefreshOrders:
    """Tests for refresh_order and refresh_all_orders."""

    def test_refresh_order_updates_state(self, order_manager, sample_equity_order, mock_tradier_client):
        """refresh_order applies Tradier status to local order."""
        order_manager.submit_order(sample_equity_order)

        # Tradier says filled
        mock_tradier_client.get_order.return_value = {
            "order": {
                "id": 99001,
                "status": "filled",
                "quantity_filled": 100,
                "avg_fill_price": 580.30,
            }
        }

        result = order_manager.refresh_order(sample_equity_order.order_id)
        assert result is not None
        assert result.state == OrderState.FILLED
        assert result.filled_quantity == 100
        assert result.average_fill_price == 580.30

    def test_refresh_all_orders(self, order_manager, sample_equity_order, mock_tradier_client):
        """refresh_all_orders returns count of updated orders."""
        order_manager.submit_order(sample_equity_order)
        count = order_manager.refresh_all_orders()
        assert count == 1


# ==============================================================================
# ASYNC WRAPPER TESTS
# ==============================================================================


class TestAsyncWrappers:
    """Tests for async order methods."""

    @pytest.mark.asyncio
    async def test_submit_order_async(self, order_manager, sample_equity_order):
        """Async submit wraps sync submit_order."""
        result = await order_manager.submit_order_async(sample_equity_order)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_cancel_order_async(self, order_manager, sample_equity_order):
        """Async cancel wraps sync cancel_order."""
        order_manager.submit_order(sample_equity_order)
        result = await order_manager.cancel_order_async(sample_equity_order.order_id)
        assert result.success is True


# ==============================================================================
# FACTORY / SINGLETON TESTS
# ==============================================================================


class TestFactoryFunctions:
    """Tests for create_order_manager and get_order_manager."""

    def test_create_order_manager(self, mock_tradier_client):
        """create_order_manager returns a new OrderManager."""
        mgr = create_order_manager(tradier_client=mock_tradier_client)
        assert isinstance(mgr, OrderManager)
        assert mgr.tradier is mock_tradier_client

    def test_get_order_manager_singleton(self, mock_tradier_client):
        """get_order_manager returns the same instance on repeated calls."""
        import Spyder.SpyderB_Broker.SpyderB02_OrderManager as om_module

        # Reset global singleton
        om_module._order_manager_instance = None

        mgr1 = om_module.get_order_manager(tradier_client=mock_tradier_client)
        mgr2 = om_module.get_order_manager()
        assert mgr1 is mgr2

        # Cleanup
        om_module._order_manager_instance = None


# ==============================================================================
# SSE EVENT HANDLING TESTS
# ==============================================================================


class TestSSEEventHandling:
    """Tests for SSE event processing (without active stream)."""

    def test_on_sse_order_event_updates_state(self, order_manager, sample_equity_order):
        """SSE order event updates local order state."""
        order_manager.submit_order(sample_equity_order)

        mock_event = Mock()
        mock_event.event_type = "order"
        mock_event.data = {
            "id": 99001,
            "status": "filled",
            "quantity_filled": 100,
            "avg_fill_price": 580.30,
        }

        order_manager._on_sse_event(mock_event)

        stored = order_manager.get_order(sample_equity_order.order_id)
        assert stored.state == OrderState.FILLED

    def test_on_sse_trade_event_processes_fill(self, order_manager, sample_equity_order):
        """SSE trade event triggers fill processing."""
        fills = []
        order_manager.on_fill(lambda o, r: fills.append(r))
        order_manager.submit_order(sample_equity_order)

        mock_event = Mock()
        mock_event.event_type = "trade"
        mock_event.data = {
            "order_id": 99001,
            "symbol": "SPY",
            "side": "buy",
            "quantity": 100,
            "price": 580.40,
            "id": "exec_001",
        }

        order_manager._on_sse_event(mock_event)

        assert len(fills) == 1
        assert fills[0].price == 580.40


# ==============================================================================
# RUN TESTS
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
