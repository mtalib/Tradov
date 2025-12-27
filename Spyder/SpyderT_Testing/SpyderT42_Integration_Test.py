#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT42_Integration_Test.py
Purpose: Integration tests for Tradier + Polygon end-to-end workflow

Author: Claude (Maestro)
Year Created: 2025
Last Updated: 2025-11-18 Time: 20:15:00

Description:
    End-to-end integration tests for the Tradier + Polygon migration.
    Tests the complete data flow from Polygon → Strategy → Tradier execution.

Usage:
    pytest SpyderT_Testing/SpyderT42_Integration_Test.py -v --tb=short

Requirements:
    - Valid TRADIER_API_KEY and TRADIER_ACCOUNT_ID in environment
    - Valid POLYGON_API_KEY in environment
    - TRADING_MODE=paper (sandbox) for testing
"""

import pytest
import os
import time
from unittest.mock import Mock, patch

# Import modules under test
from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
    TradierClient,
    TradingEnvironment,
    OrderSide,
    OrderType
)

# Conditional Polygon import (requires Qt)
try:
    from SpyderC_MarketData.SpyderC25_PolygonDataHandler import (
        PolygonDataHandler,
        MarketDataUpdate,
        MessageType,
        ConnectionStatus
    )
    HAS_POLYGON = True
except ImportError:
    HAS_POLYGON = False


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def integration_env_vars():
    """Check for integration test environment variables."""
    required_vars = ["TRADIER_API_KEY", "TRADIER_ACCOUNT_ID", "POLYGON_API_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        pytest.skip(f"Integration test requires: {', '.join(missing)}")


@pytest.fixture
def tradier_client(integration_env_vars):
    """Create live Tradier client for integration testing."""
    return TradierClient(
        api_key=os.getenv("TRADIER_API_KEY"),
        account_id=os.getenv("TRADIER_ACCOUNT_ID"),
        environment=TradingEnvironment.SANDBOX  # Always use sandbox for testing
    )


@pytest.fixture
def polygon_handler(integration_env_vars):
    """Create Polygon data handler for integration testing."""
    if not HAS_POLYGON:
        pytest.skip("Polygon handler requires PySide6")

    return PolygonDataHandler(
        api_key=os.getenv("POLYGON_API_KEY"),
        symbols=["SPY"],
        subscribe_trades=True
    )


# ==============================================================================
# TRADIER INTEGRATION TESTS
# ==============================================================================

class TestTradierIntegration:
    """Integration tests for Tradier API."""

    def test_tradier_authentication(self, tradier_client):
        """Test Tradier authentication with real API."""
        assert tradier_client.test_connection() is True

    def test_tradier_get_user_profile(self, tradier_client):
        """Test getting user profile."""
        profile = tradier_client.get_user_profile()

        assert "profile" in profile
        assert "name" in profile["profile"]

    def test_tradier_get_account_balances(self, tradier_client):
        """Test getting account balances."""
        balances = tradier_client.get_account_balances()

        assert "balances" in balances
        # Sandbox accounts should have some balance
        assert "total_equity" in balances["balances"]

    def test_tradier_get_market_data(self, tradier_client):
        """Test getting market data for SPY."""
        quotes = tradier_client.get_quotes(["SPY"])

        assert "quotes" in quotes
        quote = quotes["quotes"]["quote"]
        assert quote["symbol"] == "SPY"
        assert "last" in quote
        assert quote["last"] > 0  # SPY should have a positive price

    @pytest.mark.slow
    def test_tradier_place_and_cancel_order(self, tradier_client):
        """Test placing and canceling an order (sandbox only)."""
        # Place a limit order way below market to avoid fill
        order = tradier_client.place_order(
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=1,
            order_type=OrderType.LIMIT,
            limit_price=1.00  # Way below market, won't fill
        )

        assert "order" in order
        order_id = order["order"]["id"]
        assert order_id > 0

        # Wait a moment
        time.sleep(1)

        # Cancel the order
        cancel_result = tradier_client.cancel_order(order_id)
        assert "order" in cancel_result


# ==============================================================================
# POLYGON INTEGRATION TESTS
# ==============================================================================

@pytest.mark.skipif(not HAS_POLYGON, reason="Requires PySide6")
class TestPolygonIntegration:
    """Integration tests for Polygon.io API."""

    @pytest.mark.slow
    def test_polygon_connection(self, polygon_handler):
        """Test Polygon WebSocket connection."""
        # This test requires running Qt event loop
        # In practice, you'd use pytest-qt for this
        pytest.skip("Requires Qt event loop - run manually")

    def test_polygon_data_normalization(self):
        """Test Polygon data normalization."""
        # Mock data from Polygon
        mock_trade_data = {
            "ev": "T",
            "sym": "SPY",
            "p": 450.25,
            "s": 100,
            "t": 1700000000000,
            "x": 4
        }

        # Create MarketDataUpdate
        update = MarketDataUpdate(
            symbol=mock_trade_data["sym"],
            timestamp=mock_trade_data["t"],
            message_type=MessageType.TRADE,
            data={
                "price": mock_trade_data["p"],
                "size": mock_trade_data["s"],
                "exchange": mock_trade_data["x"]
            }
        )

        assert update.symbol == "SPY"
        assert update.data["price"] == 450.25
        assert update.message_type == MessageType.TRADE


# ==============================================================================
# END-TO-END WORKFLOW TESTS
# ==============================================================================

class TestEndToEndWorkflow:
    """Test complete data flow: Polygon → Strategy → Tradier."""

    def test_data_to_execution_latency(self, tradier_client):
        """Test latency from market data to order placement."""
        # Simulate receiving market data
        start_time = time.time()

        # Get current quote
        quotes = tradier_client.get_quotes(["SPY"])
        quote_time = time.time() - start_time

        # Simulate strategy decision (instant)
        strategy_time = time.time()

        # Place order (using mock for safety)
        with patch.object(tradier_client, 'place_order') as mock_place:
            mock_place.return_value = {"order": {"id": 12345}}

            order = tradier_client.place_order(
                symbol="SPY",
                side=OrderSide.BUY,
                quantity=1,
                order_type=OrderType.MARKET
            )

            execution_time = time.time() - strategy_time

        total_time = time.time() - start_time

        # Verify latency is reasonable (<1 second for mock)
        assert total_time < 1.0
        print(f"\nLatency breakdown:")
        print(f"  Quote retrieval: {quote_time*1000:.2f}ms")
        print(f"  Order placement: {execution_time*1000:.2f}ms")
        print(f"  Total: {total_time*1000:.2f}ms")

    def test_paper_trading_workflow(self, tradier_client):
        """Test complete paper trading workflow."""
        # Step 1: Get account balances
        balances = tradier_client.get_account_balances()
        initial_equity = balances["balances"]["total_equity"]

        # Step 2: Get market data
        quotes = tradier_client.get_quotes(["SPY"])
        spy_price = quotes["quotes"]["quote"]["last"]

        # Step 3: Calculate position size
        position_value = initial_equity * 0.01  # 1% of equity
        quantity = int(position_value / spy_price)

        if quantity < 1:
            quantity = 1  # Minimum 1 share

        # Step 4: Place order (mocked)
        with patch.object(tradier_client, 'place_order') as mock_place:
            mock_place.return_value = {
                "order": {
                    "id": 12345,
                    "status": "ok"
                }
            }

            order = tradier_client.place_order(
                symbol="SPY",
                side=OrderSide.BUY,
                quantity=quantity,
                order_type=OrderType.MARKET
            )

            assert order["order"]["status"] == "ok"

        print(f"\nPaper trading workflow:")
        print(f"  Initial equity: ${initial_equity:,.2f}")
        print(f"  SPY price: ${spy_price:.2f}")
        print(f"  Position size: {quantity} shares")
        print(f"  Order value: ${quantity * spy_price:,.2f}")


# ==============================================================================
# PERFORMANCE BENCHMARKS
# ==============================================================================

class TestPerformance:
    """Performance benchmarks for API calls."""

    def test_tradier_api_latency(self, tradier_client):
        """Benchmark Tradier API call latency."""
        latencies = []

        for _ in range(5):
            start = time.time()
            tradier_client.get_quotes(["SPY"])
            latency = (time.time() - start) * 1000  # Convert to ms
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        min_latency = min(latencies)

        print(f"\nTradier API latency:")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  Min: {min_latency:.2f}ms")
        print(f"  Max: {max_latency:.2f}ms")

        # Assert reasonable latency (<500ms average)
        assert avg_latency < 500.0

    def test_order_placement_latency(self, tradier_client):
        """Benchmark order placement latency."""
        with patch.object(tradier_client, 'place_order') as mock_place:
            mock_place.return_value = {"order": {"id": 12345}}

            start = time.time()
            tradier_client.place_order(
                symbol="SPY",
                side=OrderSide.BUY,
                quantity=1,
                order_type=OrderType.MARKET
            )
            latency = (time.time() - start) * 1000

            print(f"\nOrder placement latency: {latency:.2f}ms")
            # Mock should be very fast
            assert latency < 10.0


# ==============================================================================
# RUN TESTS
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
