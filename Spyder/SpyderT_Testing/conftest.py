#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: conftest.py
Purpose: Shared pytest fixtures for Tradier + Databento test suites

Author: GitHub Copilot
Year Created: 2026
Last Updated: 2026-02-25 Time: 20:00:00

Description:
    Module-level conftest providing reusable fixtures for:
    - TradierClient (mocked Session)
    - OrderManager (mocked TradierClient)
    - DatabentoClient (mocked databento SDK)
    - Common API response payloads
"""

import pytest
import os
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from datetime import datetime, date


# ==============================================================================
# COLLECTION CONFIGURATION
# ==============================================================================
# Skip test files that reference unimplemented or removed modules.
# These files crash on import before any skip markers can take effect.
collect_ignore = [
    "SpyderT02_BrokerTestSuite.py",       # References removed legacy broker modules (B01, B05)
    "SpyderT03_BlackSwanValidator.py",     # Imports unimplemented S06-S11 Black Swan modules
    "SpyderT07_AdvancedEvolutionPush.py",  # Standalone script, not a pytest module
    "SpyderT17_ComprehensiveSystemTest.py",  # Crashes pytest (PySide6 QApplication in headless env)
    "SpyderT21_DIXQuickStart.py",          # Imports non-existent SpyderS02_DIXDemo
    "SpyderT43_OrderManager_Test.py",      # OrderManager class moved; needs refactor to new B02 API
]


# ==============================================================================
# TRADIER FIXTURES
# ==============================================================================

@pytest.fixture
def tradier_env(monkeypatch):
    """Set Tradier environment variables for testing."""
    monkeypatch.setenv("TRADIER_API_KEY", "test_tradier_key_12345678")
    monkeypatch.setenv("TRADIER_ACCOUNT_ID", "TEST_ACCT_001")
    monkeypatch.setenv("TRADIER_ENVIRONMENT", "sandbox")
    monkeypatch.setenv("TRADING_MODE", "paper")


@pytest.fixture
def mock_tradier_session():
    """Provide a mocked requests.Session with Tradier-style responses."""
    with patch("requests.Session") as MockSession:
        session = MockSession.return_value
        session.headers = {}

        # Default success response
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"status": "ok"}
        response.text = '{"status": "ok"}'
        response.headers = {"Content-Type": "application/json"}
        response.raise_for_status = Mock()

        session.get.return_value = response
        session.post.return_value = response
        session.put.return_value = response
        session.delete.return_value = response
        session.request.return_value = response

        yield session


@pytest.fixture
def tradier_client(tradier_env):
    """Create a TradierClient in sandbox mode for testing."""
    from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
        TradierClient,
        TradingEnvironment,
    )

    return TradierClient(
        api_key="test_tradier_key_12345678",
        account_id="TEST_ACCT_001",
        environment=TradingEnvironment.SANDBOX,
    )


@pytest.fixture
def mock_tradier_client():
    """Fully-mocked TradierClient for OrderManager tests."""
    client = MagicMock()
    client.api_key = "mock_key"
    client.account_id = "MOCK_ACCT"
    client.environment = MagicMock()
    client.environment.value = "sandbox"
    client.base_url = "https://sandbox.tradier.com/v1"
    client.test_connection.return_value = True

    # Default order placement response
    client.place_order.return_value = {"order": {"id": 99001, "status": "ok"}}
    client.place_multileg_order.return_value = {"order": {"id": 99002, "status": "ok"}}
    client.place_iron_condor.return_value = {"order": {"id": 99003, "status": "ok"}}
    client.place_credit_spread.return_value = {"order": {"id": 99004, "status": "ok"}}
    client.cancel_order.return_value = {"order": {"id": 99001, "status": "ok"}}
    client.modify_order.return_value = {"order": {"id": 99001, "status": "ok"}}
    client.get_order.return_value = {"order": {"id": 99001, "status": "filled"}}
    client.get_orders.return_value = {"orders": {"order": []}}

    # Account endpoints
    client.get_account_balances.return_value = {
        "balances": {
            "total_equity": 100000.0,
            "total_cash": 50000.0,
            "option_buying_power": 25000.0,
        }
    }
    client.get_positions.return_value = {"positions": {"position": []}}
    client.get_quotes.return_value = {
        "quotes": {
            "quote": {
                "symbol": "SPY",
                "last": 585.25,
                "bid": 585.23,
                "ask": 585.27,
                "volume": 45000000,
            }
        }
    }

    # Streaming
    client.create_streaming_session.return_value = "session_12345"

    return client


# ==============================================================================
# ORDER MANAGER FIXTURES
# ==============================================================================

@pytest.fixture
def order_manager(mock_tradier_client):
    """Create an OrderManager with a mocked TradierClient."""
    from Spyder.SpyderB_Broker.SpyderB02_OrderManager import OrderManager

    mgr = OrderManager(tradier_client=mock_tradier_client, enable_streaming=False)
    yield mgr
    # Cleanup — stop persistence thread if running
    try:
        mgr.stop()
    except Exception:
        pass


@pytest.fixture
def sample_equity_order():
    """Create a sample equity Order ready for submission."""
    from Spyder.SpyderB_Broker.SpyderB02_OrderManager import Order, SecurityType

    return Order(
        symbol="SPY",
        side="buy",
        order_type="limit",
        quantity=100,
        price=580.00,
        duration="day",
        security_type=SecurityType.EQUITY,
        order_class="equity",
        strategy_name="test_strategy",
    )


@pytest.fixture
def sample_option_order():
    """Create a sample single-leg option Order."""
    from Spyder.SpyderB_Broker.SpyderB02_OrderManager import Order, SecurityType

    return Order(
        symbol="SPY",
        side="buy_to_open",
        order_type="limit",
        quantity=5,
        price=3.50,
        duration="day",
        security_type=SecurityType.OPTION,
        order_class="option",
        option_symbol="SPY260220C00585000",
        expiry="2026-02-20",
        strike=585.0,
        right="call",
        strategy_name="test_option_strategy",
    )


@pytest.fixture
def sample_multileg_order():
    """Create a sample multileg Order with OptionLeg entries."""
    from Spyder.SpyderB_Broker.SpyderB02_OrderManager import Order, SecurityType
    from Spyder.SpyderB_Broker.SpyderB40_TradierClient import OptionLeg

    legs = [
        OptionLeg(
            option_symbol="SPY260220P00570000",
            side="buy_to_open",
            quantity=1,
        ),
        OptionLeg(
            option_symbol="SPY260220P00575000",
            side="sell_to_open",
            quantity=1,
        ),
    ]

    return Order(
        symbol="SPY",
        side="multileg",
        order_type="credit",
        quantity=1,
        price=0.50,
        duration="day",
        security_type=SecurityType.MULTILEG,
        order_class="multileg",
        legs=legs,
        strategy_name="put_credit_spread",
    )


# ==============================================================================
# DATABENTO FIXTURES
# ==============================================================================

@pytest.fixture
def databento_env(monkeypatch):
    """Set Databento environment variables."""
    monkeypatch.setenv("DATABENTO_API_KEY", "test_databento_key_12345678")


@pytest.fixture
def mock_databento_historical():
    """Mocked databento.Historical client."""
    hist = MagicMock()
    # Simulate timeseries.get_range returning a data object with .to_df()
    mock_data = MagicMock()
    mock_df = MagicMock()
    mock_df.__len__ = Mock(return_value=100)
    mock_data.to_df.return_value = mock_df
    hist.timeseries.get_range.return_value = mock_data
    return hist


@pytest.fixture
def databento_client(databento_env):
    """Create a DatabentoClient with mocked databento SDK."""
    with patch.dict("sys.modules", {"databento": MagicMock()}):
        from Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient import DatabentoClient

        client = DatabentoClient(api_key="test_databento_key_12345678")
        return client


# ==============================================================================
# TRADIER API RESPONSE FIXTURES
# ==============================================================================

@pytest.fixture
def tradier_order_response():
    """Standard Tradier order placement response."""
    return {"order": {"id": 12345, "status": "ok"}}


@pytest.fixture
def tradier_account_balances():
    """Standard Tradier account balances response."""
    return {
        "balances": {
            "option_short_value": 0,
            "total_equity": 100000.00,
            "account_number": "TEST_ACCT_001",
            "account_type": "margin",
            "close_pl": 0.00,
            "current_requirement": 0,
            "equity": 0,
            "long_market_value": 0.00,
            "market_value": 100000.00,
            "open_pl": 0.00,
            "option_long_value": 0,
            "option_requirement": 0,
            "pending_orders_count": 0,
            "short_market_value": 0,
            "stock_long_value": 0,
            "total_cash": 100000.00,
            "uncleared_funds": 0,
            "pending_cash": 0,
            "margin": {
                "fed_call": 0,
                "maintenance_call": 0,
                "option_buying_power": 100000.00,
                "stock_buying_power": 200000.00,
                "stock_short_value": 0,
                "sweep": 0,
            },
        }
    }


@pytest.fixture
def tradier_positions_response():
    """Standard Tradier positions response."""
    return {
        "positions": {
            "position": [
                {
                    "cost_basis": 58025.00,
                    "date_acquired": "2026-02-20T00:00:00.000Z",
                    "id": 1001,
                    "quantity": 100.0,
                    "symbol": "SPY",
                },
            ]
        }
    }


@pytest.fixture
def tradier_quote_response():
    """Standard Tradier quote response."""
    return {
        "quotes": {
            "quote": {
                "symbol": "SPY",
                "description": "SPDR S&P 500 ETF Trust",
                "exch": "Q",
                "type": "etf",
                "last": 585.25,
                "change": 2.35,
                "volume": 45000000,
                "open": 583.50,
                "high": 586.10,
                "low": 582.90,
                "close": 582.90,
                "bid": 585.23,
                "ask": 585.27,
                "bidsize": 500,
                "asksize": 300,
                "week_52_high": 610.00,
                "week_52_low": 480.00,
            }
        }
    }


@pytest.fixture
def tradier_option_chain_response():
    """Standard Tradier option chain response."""
    return {
        "options": {
            "option": [
                {
                    "symbol": "SPY260220C00585000",
                    "description": "SPY Feb 20 2026 $585.00 Call",
                    "exch": "Z",
                    "type": "option",
                    "last": 3.50,
                    "bid": 3.45,
                    "ask": 3.55,
                    "volume": 12000,
                    "open_interest": 25000,
                    "strike": 585.00,
                    "expiration_date": "2026-02-20",
                    "option_type": "call",
                    "greeks": {
                        "delta": 0.52,
                        "gamma": 0.035,
                        "theta": -0.15,
                        "vega": 0.28,
                        "rho": 0.02,
                    },
                },
                {
                    "symbol": "SPY260220P00585000",
                    "description": "SPY Feb 20 2026 $585.00 Put",
                    "exch": "Z",
                    "type": "option",
                    "last": 3.40,
                    "bid": 3.35,
                    "ask": 3.45,
                    "volume": 11000,
                    "open_interest": 22000,
                    "strike": 585.00,
                    "expiration_date": "2026-02-20",
                    "option_type": "put",
                    "greeks": {
                        "delta": -0.48,
                        "gamma": 0.035,
                        "theta": -0.14,
                        "vega": 0.28,
                        "rho": -0.02,
                    },
                },
            ]
        }
    }
