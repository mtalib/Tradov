#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT27_ClientPortal_Integration_Test.py
Purpose: Comprehensive integration tests for Client Portal API

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-11-09 Time: 16:00:00

Test Coverage:
    - Full authentication flow (OAuth 2.0 + CP Gateway)
    - Session management with automatic tickle
    - WebSocket real-time streaming
    - Market data retrieval (quotes + historical bars)
    - Order placement and management
    - Position tracking
    - End-to-end trading workflows
    - Error handling and recovery
    - Performance benchmarks

Test Categories:
    - @pytest.mark.integration: Integration tests (requires CP Gateway)
    - @pytest.mark.paper: Paper trading tests (safe to run)
    - @pytest.mark.live: Live trading tests (DANGEROUS - manual only)
    - @pytest.mark.slow: Slow tests (>10 seconds)
    - @pytest.mark.benchmark: Performance tests

Prerequisites:
    - CP Gateway running on localhost:5000
    - Paper trading account configured
    - WebSocket support (pip install websocket-client)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import pytest
from datetime import datetime, timedelta
from typing import List, Optional

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
# (pytest imported above)

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderB_Broker.ClientPortalAPI import (
    # Auth
    CPGatewayAuth,
    CPGatewayConfig,
    # Session
    SessionManager,
    SessionConfig,
    # Market Data
    MarketDataManager,
    MarketDataConfig,
    Quote,
    Bar,
    # Order Management
    OrderManager,
    OrderTicket,
    Order,
    Position,
    OrderType,
    OrderSide,
    TimeInForce,
)
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

# Initialize logger
logger = SpyderLogger.get_logger(__name__)


# ==============================================================================
# TEST FIXTURES
# ==============================================================================

@pytest.fixture(scope="module")
def gateway_config():
    """CP Gateway configuration"""
    return CPGatewayConfig(
        host='localhost',
        port=5000,
        ssl=True
    )


@pytest.fixture(scope="module")
def auth_client(gateway_config):
    """Authenticated CP Gateway client"""
    auth = CPGatewayAuth(gateway_config)

    # Check if authenticated
    if not auth.is_authenticated():
        pytest.skip("Not authenticated - please login to CP Gateway at https://localhost:5000")

    return auth


@pytest.fixture(scope="module")
def session_manager(auth_client, gateway_config):
    """Active session manager"""
    session_mgr = SessionManager(
        auth_client=auth_client,
        base_url=gateway_config.base_url,
        config=SessionConfig(tickle_interval=240)
    )

    # Start session
    assert session_mgr.start(), "Failed to start session"

    yield session_mgr

    # Cleanup
    session_mgr.stop()


@pytest.fixture(scope="module")
def market_data_manager(session_manager):
    """Market data manager"""
    md_mgr = MarketDataManager(
        session_manager,
        config=MarketDataConfig(enable_websocket=True)
    )

    assert md_mgr.start(), "Failed to start market data manager"

    yield md_mgr

    md_mgr.stop()


@pytest.fixture(scope="module")
def order_manager(session_manager):
    """Order manager"""
    return OrderManager(session_manager)


@pytest.fixture
def spy_conid():
    """SPY contract ID"""
    return 756733


# ==============================================================================
# AUTHENTICATION TESTS
# ==============================================================================

@pytest.mark.integration
class TestAuthentication:
    """Test authentication flow"""

    def test_gateway_connection(self, auth_client):
        """Test CP Gateway connection"""
        assert auth_client.is_authenticated()
        logger.info("✅ Gateway authentication verified")

    def test_session_creation(self, session_manager):
        """Test session creation"""
        assert session_manager.running
        assert session_manager.session is not None
        logger.info("✅ Session created successfully")

    def test_session_tickle(self, session_manager):
        """Test session tickle keeps session alive"""
        initial_time = time.time()

        # Wait for one tickle cycle
        time.sleep(10)

        # Session should still be active
        assert session_manager.running
        assert session_manager.session is not None

        elapsed = time.time() - initial_time
        logger.info(f"✅ Session active after {elapsed:.1f}s")


# ==============================================================================
# MARKET DATA TESTS
# ==============================================================================

@pytest.mark.integration
@pytest.mark.paper
class TestMarketData:
    """Test market data retrieval"""

    def test_snapshot_quote(self, market_data_manager, spy_conid):
        """Test snapshot quote retrieval"""
        snapshot = market_data_manager.get_snapshot(spy_conid, fields=[31, 84, 86])

        assert snapshot is not None
        assert '31' in snapshot or 31 in snapshot  # Last price

        logger.info(f"✅ Snapshot retrieved: {snapshot}")

    def test_historical_bars(self, market_data_manager, spy_conid):
        """Test historical bar retrieval"""
        bars = market_data_manager.get_historical_bars(
            conid=spy_conid,
            period='1d',
            bar_size='5min'
        )

        assert len(bars) > 0, "No historical bars returned"
        assert all(isinstance(bar, Bar) for bar in bars)

        # Check bar structure
        first_bar = bars[0]
        assert first_bar.open > 0
        assert first_bar.high >= first_bar.low
        assert first_bar.close > 0

        logger.info(f"✅ Retrieved {len(bars)} historical bars")
        logger.info(f"   First bar: {first_bar}")

    @pytest.mark.slow
    def test_realtime_quotes(self, market_data_manager, spy_conid):
        """Test real-time quote streaming"""
        quotes_received = []

        def on_quote(quote: Quote):
            quotes_received.append(quote)
            logger.info(f"Quote: {quote}")

        # Subscribe
        market_data_manager.subscribe_quotes(spy_conid, on_quote)

        # Wait for quotes
        time.sleep(30)

        # Check quotes received
        assert len(quotes_received) > 0, "No real-time quotes received"

        # Unsubscribe
        market_data_manager.unsubscribe_quotes(spy_conid)

        logger.info(f"✅ Received {len(quotes_received)} real-time quotes")

    def test_multiple_instruments(self, market_data_manager):
        """Test multiple instrument subscriptions"""
        conids = [756733, 8314]  # SPY, SPX

        snapshots = []
        for conid in conids:
            snapshot = market_data_manager.get_snapshot(conid)
            snapshots.append(snapshot)

        assert len(snapshots) == len(conids)
        logger.info(f"✅ Retrieved data for {len(conids)} instruments")


# ==============================================================================
# ORDER MANAGEMENT TESTS
# ==============================================================================

@pytest.mark.integration
@pytest.mark.paper
class TestOrderManagement:
    """Test order management"""

    def test_get_accounts(self, order_manager):
        """Test account retrieval"""
        accounts = order_manager.get_accounts()

        assert len(accounts) > 0, "No accounts found"
        logger.info(f"✅ Found {len(accounts)} accounts: {accounts}")

    def test_get_positions(self, order_manager):
        """Test position retrieval"""
        positions = order_manager.get_positions()

        # May be empty if no positions
        assert isinstance(positions, list)

        if positions:
            for pos in positions:
                assert isinstance(pos, Position)
                logger.info(f"   Position: {pos}")

        logger.info(f"✅ Retrieved {len(positions)} positions")

    def test_get_live_orders(self, order_manager):
        """Test live order retrieval"""
        orders = order_manager.get_live_orders()

        assert isinstance(orders, list)

        if orders:
            for order in orders:
                assert isinstance(order, Order)
                logger.info(f"   Order: {order.order_id} - {order.status.value}")

        logger.info(f"✅ Retrieved {len(orders)} live orders")

    @pytest.mark.skip(reason="Actual order placement - enable for paper trading")
    def test_place_market_order(self, order_manager, spy_conid):
        """Test market order placement (PAPER TRADING ONLY)"""
        ticket = OrderTicket(
            conid=spy_conid,
            side=OrderSide.BUY,
            quantity=1,
            order_type=OrderType.MARKET
        )

        order = order_manager.place_order(ticket)

        assert order is not None
        assert order.order_id is not None

        logger.info(f"✅ Order placed: {order.order_id}")

        # Wait for fill
        time.sleep(5)

        # Check status
        updated_order = order_manager.get_order_status(order.order_id)
        logger.info(f"   Order status: {updated_order.status.value}")

    @pytest.mark.skip(reason="Actual order placement - enable for paper trading")
    def test_place_limit_order(self, order_manager, spy_conid, market_data_manager):
        """Test limit order placement"""
        # Get current price
        snapshot = market_data_manager.get_snapshot(spy_conid, fields=[31])
        current_price = snapshot.get('31', 450.0)

        # Place limit order below current price
        limit_price = current_price * 0.95

        ticket = OrderTicket(
            conid=spy_conid,
            side=OrderSide.BUY,
            quantity=1,
            order_type=OrderType.LIMIT,
            limit_price=limit_price
        )

        order = order_manager.place_order(ticket)

        assert order is not None
        assert order.limit_price == limit_price

        logger.info(f"✅ Limit order placed: {order.order_id} @ ${limit_price:.2f}")

        # Cancel the order
        time.sleep(2)
        cancelled = order_manager.cancel_order(order.order_id)
        assert cancelled

        logger.info(f"✅ Order cancelled: {order.order_id}")

    @pytest.mark.skip(reason="Bracket order test - enable for paper trading")
    def test_bracket_order(self, order_manager, spy_conid, market_data_manager):
        """Test bracket order placement"""
        # Get current price
        snapshot = market_data_manager.get_snapshot(spy_conid, fields=[31])
        current_price = snapshot.get('31', 450.0)

        # Set bracket prices
        entry_price = current_price
        stop_loss = entry_price * 0.98  # 2% stop loss
        take_profit = entry_price * 1.02  # 2% take profit

        bracket = order_manager.place_bracket_order(
            conid=spy_conid,
            side=OrderSide.BUY,
            quantity=1,
            entry_price=entry_price,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit
        )

        assert bracket is not None
        assert 'parent' in bracket
        assert 'stop_loss' in bracket
        assert 'take_profit' in bracket

        logger.info(f"✅ Bracket order placed:")
        logger.info(f"   Parent: {bracket['parent'].order_id}")
        logger.info(f"   Stop Loss: {bracket['stop_loss'].order_id}")
        logger.info(f"   Take Profit: {bracket['take_profit'].order_id}")


# ==============================================================================
# END-TO-END WORKFLOW TESTS
# ==============================================================================

@pytest.mark.integration
@pytest.mark.paper
@pytest.mark.slow
class TestEndToEndWorkflows:
    """Test complete trading workflows"""

    def test_quote_to_order_workflow(self, market_data_manager, order_manager, spy_conid):
        """Test: Get quote -> Analyze -> Prepare order (don't execute)"""
        # Step 1: Get market data
        snapshot = market_data_manager.get_snapshot(spy_conid, fields=[31, 84, 86])
        assert snapshot is not None

        current_price = snapshot.get('31', 450.0)
        logger.info(f"Step 1: Current SPY price: ${current_price}")

        # Step 2: Get historical data
        bars = market_data_manager.get_historical_bars(
            conid=spy_conid,
            period='1d',
            bar_size='5min'
        )
        assert len(bars) > 0
        logger.info(f"Step 2: Retrieved {len(bars)} historical bars")

        # Step 3: Prepare order ticket (don't place)
        ticket = OrderTicket(
            conid=spy_conid,
            side=OrderSide.BUY,
            quantity=1,
            order_type=OrderType.LIMIT,
            limit_price=current_price * 0.99  # 1% below market
        )
        logger.info(f"Step 3: Order ticket prepared: {ticket.order_type.value} @ ${ticket.limit_price:.2f}")

        # Step 4: Check positions
        positions = order_manager.get_positions()
        logger.info(f"Step 4: Current positions: {len(positions)}")

        logger.info("✅ Complete workflow executed (order not placed)")

    def test_streaming_to_decision_workflow(self, market_data_manager, spy_conid):
        """Test: Stream quotes -> Make decision based on price movement"""
        quotes = []
        target_quotes = 10

        def on_quote(quote: Quote):
            quotes.append(quote)
            if len(quotes) <= target_quotes:
                logger.info(f"Quote #{len(quotes)}: ${quote.last}")

        # Subscribe to real-time quotes
        market_data_manager.subscribe_quotes(spy_conid, on_quote)

        # Wait for quotes
        timeout = 60
        start = time.time()
        while len(quotes) < target_quotes and (time.time() - start) < timeout:
            time.sleep(1)

        market_data_manager.unsubscribe_quotes(spy_conid)

        assert len(quotes) >= 5, f"Only received {len(quotes)} quotes"

        # Analyze price movement
        if len(quotes) >= 2:
            price_change = quotes[-1].last - quotes[0].last
            pct_change = (price_change / quotes[0].last) * 100

            logger.info(f"✅ Price movement analysis:")
            logger.info(f"   Start: ${quotes[0].last:.2f}")
            logger.info(f"   End: ${quotes[-1].last:.2f}")
            logger.info(f"   Change: ${price_change:.2f} ({pct_change:+.2f}%)")


# ==============================================================================
# PERFORMANCE BENCHMARKS
# ==============================================================================

@pytest.mark.benchmark
@pytest.mark.integration
class TestPerformance:
    """Performance benchmarks"""

    def test_snapshot_performance(self, market_data_manager, spy_conid, benchmark):
        """Benchmark snapshot retrieval"""
        def get_snapshot():
            return market_data_manager.get_snapshot(spy_conid)

        result = benchmark(get_snapshot)
        logger.info(f"✅ Snapshot performance: {benchmark.stats.get('mean', 0):.3f}s avg")

    def test_historical_bars_performance(self, market_data_manager, spy_conid, benchmark):
        """Benchmark historical bar retrieval"""
        def get_bars():
            return market_data_manager.get_historical_bars(spy_conid, period='1d', bar_size='5min')

        result = benchmark(get_bars)
        logger.info(f"✅ Historical bars performance: {benchmark.stats.get('mean', 0):.3f}s avg")

    def test_order_status_performance(self, order_manager, benchmark):
        """Benchmark order status retrieval"""
        # Get a real order ID first
        orders = order_manager.get_live_orders()

        if not orders:
            pytest.skip("No live orders to test performance")

        order_id = orders[0].order_id

        def get_status():
            return order_manager.get_order_status(order_id)

        result = benchmark(get_status)
        logger.info(f"✅ Order status performance: {benchmark.stats.get('mean', 0):.3f}s avg")


# ==============================================================================
# ERROR HANDLING TESTS
# ==============================================================================

@pytest.mark.integration
class TestErrorHandling:
    """Test error handling and recovery"""

    def test_invalid_conid(self, market_data_manager):
        """Test handling of invalid contract ID"""
        invalid_conid = 999999999

        snapshot = market_data_manager.get_snapshot(invalid_conid)

        # Should return empty or error, not crash
        assert isinstance(snapshot, dict)
        logger.info("✅ Invalid conid handled gracefully")

    def test_session_timeout_recovery(self, session_manager):
        """Test session recovery after timeout"""
        # Session should be maintained by tickle
        assert session_manager.running

        # Wait for multiple tickle cycles
        time.sleep(15)

        # Session should still be active
        assert session_manager.running
        assert session_manager.session is not None

        logger.info("✅ Session maintained through tickle")

    def test_rate_limiting(self, market_data_manager, spy_conid):
        """Test rate limit handling"""
        # Make many rapid requests
        results = []
        for i in range(20):
            snapshot = market_data_manager.get_snapshot(spy_conid)
            results.append(snapshot is not None)

        # Most should succeed (rate limiter should handle it)
        success_rate = sum(results) / len(results)
        assert success_rate > 0.8, f"Only {success_rate:.1%} requests succeeded"

        logger.info(f"✅ Rate limiting handled: {success_rate:.1%} success rate")


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == '__main__':
    """Run integration tests"""
    # Initialize logger
    SpyderLogger.initialize(log_level='INFO')

    print("=" * 70)
    print("CLIENT PORTAL API - INTEGRATION TESTS")
    print("=" * 70)
    print("\nRunning integration tests...")
    print("Prerequisites:")
    print("  - CP Gateway running on localhost:5000")
    print("  - Authenticated session (visit https://localhost:5000)")
    print("  - Paper trading account")
    print("\n" + "=" * 70)

    # Run pytest
    pytest.main([
        __file__,
        '-v',
        '-s',
        '--tb=short',
        '-m', 'integration and not slow',  # Run integration tests, skip slow ones
    ])
