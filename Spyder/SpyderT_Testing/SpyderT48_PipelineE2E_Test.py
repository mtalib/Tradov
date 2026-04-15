#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT48_PipelineE2E_Test.py
Purpose: End-to-end pipeline test: Massive-style market data → DataFeed → OrderManager → Tradier

Author: GitHub Copilot
Year Created: 2026
Last Updated: 2026-02-25 Time: 20:00:00

Description:
    Integration-style tests that verify the full data pipeline from
    market data ingestion through order execution, all with mocked
    external services.

    Pipeline under test:
        Massive-style market data → DataFeed (C01) → [Strategy signal]
                                            ↓
                                      OrderManager (B02) → TradierClient (B40)

Usage:
    pytest Spyder/SpyderT_Testing/SpyderT48_PipelineE2E_Test.py -v
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# OrderManager layer
from Spyder.SpyderB_Broker.SpyderB02_OrderManager import (
    OrderManager,
    Order,
    OrderState,
    SecurityType,
    ExecutionReport,
    TRADIER_STATUS_MAP,
)
from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
    TradierClient,
    TradingEnvironment,
    OrderSide,
    OrderType,
    OrderDuration,
    OptionLeg,
    TradierAPIError,
)

from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import MassiveClient


class MockMarketDataUpdate:
    """Minimal market-data update shape for pipeline tests."""

    def __init__(self, symbol, timestamp_ns, schema, data, underlying, is_option):
        self.symbol = symbol
        self.timestamp_ns = timestamp_ns
        self.schema = schema
        self.data = data
        self.underlying = underlying
        self.is_option = is_option


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def mock_tradier():
    """Fully-mocked TradierClient for pipeline tests."""
    client = MagicMock(spec=TradierClient)
    client.api_key = "pipeline_test_key"
    client.account_id = "PIPELINE_ACCT"
    client.environment = TradingEnvironment.SANDBOX
    client.base_url = "https://sandbox.tradier.com/v1"
    client.test_connection.return_value = True

    # Order responses
    client.place_order.return_value = {"order": {"id": 50001, "status": "ok"}}
    client.place_multileg_order.return_value = {"order": {"id": 50002, "status": "ok"}}
    client.place_iron_condor.return_value = {"order": {"id": 50003, "status": "ok"}}
    client.place_credit_spread.return_value = {"order": {"id": 50004, "status": "ok"}}
    client.cancel_order.return_value = {"order": {"id": 50001, "status": "ok"}}

    # Quote
    client.get_quotes.return_value = {
        "quotes": {
            "quote": {"symbol": "SPY", "last": 585.25, "bid": 585.23, "ask": 585.27}
        }
    }

    return client


@pytest.fixture
def pipeline_order_manager(mock_tradier):
    """OrderManager wired to mock Tradier."""
    mgr = OrderManager(tradier_client=mock_tradier, enable_streaming=False)
    yield mgr
    try:
        mgr.stop()
    except Exception:
        pass


# ==============================================================================
# PIPELINE: MARKET DATA → SIGNAL → ORDER
# ==============================================================================


class TestDataToOrderPipeline:
    """
    Test the complete pipeline from receiving market data
    to placing an order via OrderManager → TradierClient.
    """

    def test_quote_triggers_equity_order(self, pipeline_order_manager, mock_tradier):
        """
        Simulate: market-data quote update → strategy decides to buy → equity order placed.
        """
        # Step 1: Simulate market data update
        quote = MockMarketDataUpdate(
            symbol="SPY",
            timestamp_ns=int(datetime.now().timestamp() * 1e9),
            schema="mbp-1",
            data={
                "bid_px": 585.23,
                "ask_px": 585.27,
                "bid_sz": 500,
                "ask_sz": 300,
            },
            underlying="SPY",
            is_option=False,
        )

        # Step 2: Strategy logic — buy if spread < $0.10
        spread = quote.data["ask_px"] - quote.data["bid_px"]
        assert spread < 0.10

        # Step 3: Create and submit equity order
        order = pipeline_order_manager.create_order(
            symbol=quote.symbol,
            side="buy",
            order_type="limit",
            quantity=100,
            price=quote.data["ask_px"],
        )

        result = pipeline_order_manager.submit_order(order)

        # Step 4: Verify full pipeline
        assert result.success is True
        assert result.tradier_order_id == 50001
        mock_tradier.place_order.assert_called_once()

        # Step 5: Verify order tracked correctly
        stored = pipeline_order_manager.get_order(order.order_id)
        assert stored.state == OrderState.OPEN
        assert stored.symbol == "SPY"

    def test_option_quote_triggers_option_order(self, pipeline_order_manager, mock_tradier):
        """
        Simulate: option quote → single-leg option order.
        """
        # Step 1: Option quote represented with a Massive ticker
        option_quote = MockMarketDataUpdate(
            symbol=MassiveClient.build_option_ticker("SPY", "2026-02-20", "call", 585.0),
            timestamp_ns=int(datetime.now().timestamp() * 1e9),
            schema="quotes",
            data={"bid_px": 3.45, "ask_px": 3.55},
            underlying="SPY",
            is_option=True,
        )

        tradier_sym = "SPY260220C00585000"

        # Step 3: Create and submit option order
        order = pipeline_order_manager.create_order(
            symbol="SPY",
            side="buy_to_open",
            order_type="limit",
            quantity=5,
            price=option_quote.data["ask_px"],
            option_symbol=tradier_sym,
        )

        result = pipeline_order_manager.submit_order(order)
        assert result.success is True
        assert order.security_type == SecurityType.OPTION

    def test_iron_condor_pipeline(self, pipeline_order_manager, mock_tradier):
        """
        Simulate: Multiple option quotes → Iron Condor order submission.
        """
        # Step 1: Simulate receiving multiple option quotes
        quotes = [
            MockMarketDataUpdate(
                symbol=f"SPY   260220{t}{s:08d}",
                timestamp_ns=int(datetime.now().timestamp() * 1e9),
                schema="mbp-1",
                data={"bid_px": bid, "ask_px": ask},
                underlying="SPY",
                is_option=True,
            )
            for t, s, bid, ask in [
                ("P", 570000, 0.15, 0.20),  # long put
                ("P", 575000, 0.45, 0.50),  # short put
                ("C", 595000, 0.50, 0.55),  # short call
                ("C", 600000, 0.20, 0.25),  # long call
            ]
        ]

        assert len(quotes) == 4

        # Step 2: Strategy determines IC is viable
        net_credit = (0.45 - 0.20) + (0.50 - 0.25)  # put spread + call spread credit
        assert net_credit > 0

        # Step 3: Submit Iron Condor
        result = pipeline_order_manager.submit_iron_condor(
            symbol="SPY",
            expiration="2026-02-20",
            put_buy_strike=570.0,
            put_sell_strike=575.0,
            call_sell_strike=595.0,
            call_buy_strike=600.0,
            quantity=2,
            price=round(net_credit, 2),
        )

        assert result.success is True
        assert result.tradier_order_id == 50003
        mock_tradier.place_iron_condor.assert_called_once()

    def test_credit_spread_pipeline(self, pipeline_order_manager, mock_tradier):
        """
        Simulate: Bull put credit spread from data to order.
        """
        result = pipeline_order_manager.submit_credit_spread(
            symbol="SPY",
            expiration="2026-02-20",
            sell_strike=575.0,
            buy_strike=570.0,
            option_type="P",
            quantity=10,
            price=0.30,
            strategy_name="bull_put_spread",
        )

        assert result.success is True
        assert result.tradier_order_id == 50004
        mock_tradier.place_credit_spread.assert_called_once()


# ==============================================================================
# PIPELINE: ORDER → FILL → CALLBACK
# ==============================================================================


class TestOrderFillPipeline:
    """Test order submission through fill notification."""

    def test_submit_fill_callback_pipeline(self, pipeline_order_manager, mock_tradier):
        """Full pipeline: submit → SSE fill event → callback fired."""
        fill_events = []
        state_events = []

        pipeline_order_manager.on_fill(lambda o, r: fill_events.append((o, r)))
        pipeline_order_manager.on_state_change(lambda o, s: state_events.append((o, s)))

        # Submit order
        order = pipeline_order_manager.create_order(
            symbol="SPY", side="buy", quantity=100, price=585.00
        )
        result = pipeline_order_manager.submit_order(order)
        assert result.success is True

        # Simulate SSE fill event
        mock_event = Mock()
        mock_event.event_type = "trade"
        mock_event.data = {
            "order_id": 50001,
            "symbol": "SPY",
            "side": "buy",
            "quantity": 100,
            "price": 585.10,
            "id": "exec_pipeline_001",
        }
        pipeline_order_manager._on_sse_event(mock_event)

        # Verify fill callback fired
        assert len(fill_events) == 1
        assert fill_events[0][1].price == 585.10

        # Verify order state is FILLED
        assert order.state == OrderState.FILLED
        assert order.filled_quantity == 100

    def test_partial_fill_then_full_fill(self, pipeline_order_manager, mock_tradier):
        """Simulate partial fill followed by remaining fill."""
        order = pipeline_order_manager.create_order(
            symbol="SPY", side="buy", quantity=200, price=585.00
        )
        pipeline_order_manager.submit_order(order)

        # Partial fill (100 of 200)
        report1 = ExecutionReport(
            order_id=order.order_id,
            tradier_order_id=50001,
            symbol="SPY",
            side="buy",
            quantity=100,
            price=585.00,
        )
        pipeline_order_manager._process_fill(order, report1)

        assert order.state == OrderState.PARTIALLY_FILLED
        assert order.filled_quantity == 100
        assert order.remaining_quantity == 100

        # Remaining fill (100 more)
        report2 = ExecutionReport(
            order_id=order.order_id,
            tradier_order_id=50001,
            symbol="SPY",
            side="buy",
            quantity=100,
            price=585.20,
        )
        pipeline_order_manager._process_fill(order, report2)

        assert order.state == OrderState.FILLED
        assert order.filled_quantity == 200
        assert order.remaining_quantity == 0

        # Average fill price should be weighted
        expected_avg = (585.00 * 100 + 585.20 * 100) / 200
        assert abs(order.average_fill_price - expected_avg) < 0.01


# ==============================================================================
# PIPELINE: ORDER LIFECYCLE
# ==============================================================================


class TestOrderLifecyclePipeline:
    """Test full order lifecycle: create → submit → modify → cancel."""

    def test_full_lifecycle(self, pipeline_order_manager, mock_tradier):
        """Order goes through create → submit → modify → cancel."""
        # Create
        order = pipeline_order_manager.create_order(
            symbol="SPY", side="buy", order_type="limit",
            quantity=50, price=580.00,
        )
        assert order.state == OrderState.PENDING

        # Submit
        result = pipeline_order_manager.submit_order(order)
        assert result.success is True
        assert order.state == OrderState.OPEN

        # Modify
        result = pipeline_order_manager.modify_order(
            order.order_id, price=581.00
        )
        assert result.success is True
        assert order.price == 581.00

        # Cancel
        result = pipeline_order_manager.cancel_order(order.order_id)
        assert result.success is True
        assert order.state == OrderState.CANCELLED

        # Verify metrics
        metrics = pipeline_order_manager.get_metrics()
        assert metrics["orders_submitted"] == 1
        assert metrics["orders_cancelled"] == 1


# ==============================================================================
# PIPELINE: ERROR RECOVERY
# ==============================================================================


class TestErrorRecoveryPipeline:
    """Test error handling across the pipeline."""

    def test_tradier_api_error_during_submit(self, pipeline_order_manager, mock_tradier):
        """API error during submit is handled gracefully."""
        mock_tradier.place_order.side_effect = TradierAPIError("Insufficient funds")

        order = pipeline_order_manager.create_order(
            symbol="SPY", side="buy", quantity=100, price=585.00
        )
        result = pipeline_order_manager.submit_order(order)

        assert result.success is False
        assert order.state == OrderState.REJECTED
        assert "Insufficient funds" in order.error_message

    def test_cancel_failure_reverts_state(self, pipeline_order_manager, mock_tradier):
        """Failed cancel reverts order to OPEN state."""
        order = pipeline_order_manager.create_order(
            symbol="SPY", side="buy", quantity=100, price=585.00
        )
        pipeline_order_manager.submit_order(order)

        mock_tradier.cancel_order.side_effect = TradierAPIError("Cannot cancel")
        result = pipeline_order_manager.cancel_order(order.order_id)

        assert result.success is False
        assert order.state == OrderState.OPEN  # reverted

    def test_multiple_orders_independent(self, pipeline_order_manager, mock_tradier):
        """Multiple orders are tracked independently."""
        order1 = pipeline_order_manager.create_order(
            symbol="SPY", side="buy", quantity=100, price=580.00
        )
        order2 = pipeline_order_manager.create_order(
            symbol="SPY", side="sell", quantity=50, price=590.00
        )

        pipeline_order_manager.submit_order(order1)
        pipeline_order_manager.submit_order(order2)

        pipeline_order_manager.cancel_order(order1.order_id)

        assert order1.state == OrderState.CANCELLED
        assert order2.state == OrderState.OPEN

        active = pipeline_order_manager.get_active_orders()
        assert len(active) == 1
        assert active[0].order_id == order2.order_id


# ==============================================================================
# PIPELINE: SYMBOL CONVERSION INTEGRATION
# ==============================================================================


class TestOptionSymbolPipeline:
    """Test option symbol handling in the data→order pipeline."""

    def test_tradier_option_symbol_passes_through(self, pipeline_order_manager, mock_tradier):
        """Tradier-formatted option symbols pass through unchanged for order placement."""
        tradier_sym = "SPY260220C00585000"

        order = pipeline_order_manager.create_order(
            symbol="SPY",
            side="buy_to_open",
            quantity=1,
            price=3.50,
            option_symbol=tradier_sym,
        )

        result = pipeline_order_manager.submit_order(order)
        assert result.success is True

        assert order.option_symbol == tradier_sym


# ==============================================================================
# RUN TESTS
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
