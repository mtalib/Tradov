#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT40_TradierClient_Test.py
Purpose: Unit tests for Tradier API client

Author: Claude (Maestro)
Year Created: 2025
Last Updated: 2025-11-18 Time: 20:00:00

Description:
    Comprehensive unit tests for the TradierClient module.
    Tests authentication, order placement, account queries, and error handling.

Usage:
    pytest SpyderT_Testing/SpyderT40_TradierClient_Test.py -v
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
import requests

# Import module under test
from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
    TradierClient,
    TradingEnvironment,
    OptionLeg,
    OrderSide,
    OrderType,
    OrderDuration,
    OrderClass,
    TradierAPIError,
    TradierAuthenticationError,
    TradierValidationError,
    TradierServerError,
    TradierRateLimitError,
    create_tradier_client_from_env
)


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv("TRADIER_API_KEY", "test_api_key_12345678")
    monkeypatch.setenv("TRADIER_ACCOUNT_ID", "TEST123456")
    monkeypatch.setenv("TRADING_MODE", "paper")


@pytest.fixture
def tradier_client():
    """Create Tradier client for testing."""
    return TradierClient(
        api_key="test_api_key_12345678",
        account_id="TEST123456",
        environment=TradingEnvironment.SANDBOX
    )


@pytest.fixture
def mock_session():
    """Create mock requests session."""
    with patch('requests.Session') as mock:
        session = mock.return_value
        yield session


# ==============================================================================
# CLIENT INITIALIZATION TESTS
# ==============================================================================

class TestTradierClientInitialization:
    """Test client initialization."""

    def test_client_initialization_sandbox(self):
        """Test client initialization in sandbox mode."""
        client = TradierClient(
            api_key="test_key",
            account_id="test_account",
            environment=TradingEnvironment.SANDBOX
        )

        assert client.api_key == "test_key"
        assert client.account_id == "test_account"
        assert client.environment == TradingEnvironment.SANDBOX
        assert "sandbox" in client.base_url.lower()

    def test_client_initialization_live(self):
        """Test client initialization in live mode."""
        client = TradierClient(
            api_key="test_key",
            account_id="test_account",
            environment=TradingEnvironment.LIVE
        )

        assert client.environment == TradingEnvironment.LIVE
        assert "api.tradier.com" in client.base_url

    def test_client_from_env(self, mock_env_vars):
        """Test client creation from environment variables."""
        client = create_tradier_client_from_env(TradingEnvironment.SANDBOX)

        assert client.api_key == "test_api_key_12345678"
        assert client.account_id == "TEST123456"

    def test_client_from_env_missing_api_key(self, monkeypatch):
        """Test error when API key missing."""
        monkeypatch.delenv("TRADIER_API_KEY", raising=False)
        monkeypatch.setenv("TRADIER_ACCOUNT_ID", "TEST123")

        with pytest.raises(ValueError, match="TRADIER_API_KEY"):
            create_tradier_client_from_env()

    def test_client_from_env_missing_account_id(self, monkeypatch):
        """Test error when account ID missing."""
        monkeypatch.setenv("TRADIER_API_KEY", "test_key")
        monkeypatch.delenv("TRADIER_ACCOUNT_ID", raising=False)

        with pytest.raises(ValueError, match="TRADIER_ACCOUNT_ID"):
            create_tradier_client_from_env()


# ==============================================================================
# USER & ACCOUNT ENDPOINT TESTS
# ==============================================================================

class TestAccountEndpoints:
    """Test account-related API endpoints."""

    @patch('requests.Session.request')
    def test_get_user_profile_success(self, mock_request, tradier_client):
        """Test successful user profile retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "profile": {
                "name": "Test User",
                "account": {"account_number": "TEST123456"}
            }
        }
        mock_request.return_value = mock_response

        profile = tradier_client.get_user_profile()

        assert profile["profile"]["name"] == "Test User"
        mock_request.assert_called_once()

    @patch('requests.Session.request')
    def test_get_account_balances_success(self, mock_request, tradier_client):
        """Test successful balance retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "balances": {
                "total_equity": 10000.50,
                "total_cash": 5000.25,
                "option_buying_power": 3000.00
            }
        }
        mock_request.return_value = mock_response

        balances = tradier_client.get_account_balances()

        assert balances["balances"]["total_equity"] == 10000.50
        assert "/balances" in mock_request.call_args[1]["url"]

    @patch('requests.Session.request')
    def test_get_positions_success(self, mock_request, tradier_client):
        """Test successful positions retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "positions": {
                "position": [
                    {"symbol": "SPY", "quantity": 100, "cost_basis": 45000.00}
                ]
            }
        }
        mock_request.return_value = mock_response

        positions = tradier_client.get_positions()

        assert len(positions["positions"]["position"]) == 1
        assert positions["positions"]["position"][0]["symbol"] == "SPY"


# ==============================================================================
# ORDER PLACEMENT TESTS
# ==============================================================================

class TestOrderPlacement:
    """Test order placement functionality."""

    @patch('requests.Session.request')
    def test_place_market_order(self, mock_request, tradier_client):
        """Test placing a market order."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "order": {
                "id": 123456,
                "status": "ok",
                "partner_id": "test"
            }
        }
        mock_request.return_value = mock_response

        order = tradier_client.place_order(
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET
        )

        assert order["order"]["id"] == 123456
        # Verify POST request was made
        assert mock_request.call_args.kwargs["method"] == "POST"
        # Verify order parameters
        call_data = mock_request.call_args.kwargs["data"]
        assert call_data["symbol"] == "SPY"
        assert call_data["quantity"] == 10
        assert call_data["type"] == "market"

    @patch('requests.Session.request')
    def test_place_limit_order(self, mock_request, tradier_client):
        """Test placing a limit order."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"order": {"id": 123457}}
        mock_request.return_value = mock_response

        tradier_client.place_order(
            symbol="SPY",
            side=OrderSide.SELL,
            quantity=5,
            order_type=OrderType.LIMIT,
            limit_price=450.50
        )

        call_data = mock_request.call_args.kwargs["data"]
        assert call_data["type"] == "limit"
        assert call_data["price"] == 450.50

    @patch('requests.Session.request')
    def test_cancel_order(self, mock_request, tradier_client):
        """Test order cancellation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"order": {"id": 123456, "status": "cancelled"}}
        mock_request.return_value = mock_response

        result = tradier_client.cancel_order(order_id=123456)

        # cancel_order() returns bool (True when API confirms the id)
        assert result is True
        assert mock_request.call_args.kwargs["method"] == "DELETE"

    def test_paper_mode_blocks_live_order_submission(self, monkeypatch):
        """Paper mode must reject order submission on live execution client."""
        monkeypatch.setenv("TRADING_MODE", "paper")
        monkeypatch.delenv("SPYDER_TRADING_MODE", raising=False)

        live_client = TradierClient(
            api_key="test_api_key_12345678",
            account_id="TEST123456",
            environment=TradingEnvironment.LIVE,
        )

        with patch("requests.Session.request") as mock_request:
            with pytest.raises(TradierValidationError, match="Paper-mode safety guard"):
                live_client.place_order(
                    symbol="SPY",
                    side=OrderSide.BUY,
                    quantity=1,
                    order_type=OrderType.MARKET,
                )

            mock_request.assert_not_called()

    @patch('requests.Session.request')
    def test_paper_mode_allows_live_preview_order(self, mock_request, monkeypatch):
        """Preview orders are non-mutating and should bypass execution guard."""
        monkeypatch.setenv("TRADING_MODE", "paper")
        monkeypatch.delenv("SPYDER_TRADING_MODE", raising=False)

        live_client = TradierClient(
            api_key="test_api_key_12345678",
            account_id="TEST123456",
            environment=TradingEnvironment.LIVE,
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "order": {
                "status": "ok",
                "preview": True,
            }
        }
        mock_request.return_value = mock_response

        response = live_client.preview_order(
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=1,
            order_type=OrderType.MARKET,
        )

        assert response["order"]["status"] == "ok"
        assert mock_request.call_args.kwargs["method"] == "POST"

    def test_paper_mode_blocks_live_multileg_order_submission(self, monkeypatch):
        """Paper mode must reject live-endpoint multileg order submission."""
        monkeypatch.setenv("TRADING_MODE", "paper")
        monkeypatch.delenv("SPYDER_TRADING_MODE", raising=False)

        live_client = TradierClient(
            api_key="test_api_key_12345678",
            account_id="TEST123456",
            environment=TradingEnvironment.LIVE,
        )

        legs = [
            OptionLeg("SPY260320P00535000", OrderSide.BUY_TO_OPEN, 1),
            OptionLeg("SPY260320P00540000", OrderSide.SELL_TO_OPEN, 1),
        ]

        with patch("requests.Session.request") as mock_request:
            with pytest.raises(TradierValidationError, match="Paper-mode safety guard"):
                live_client.place_multileg_order(
                    symbol="SPY",
                    legs=legs,
                    order_type="credit",
                    price=1.25,
                )

            mock_request.assert_not_called()

    @patch('requests.Session.request')
    def test_get_order_status(self, mock_request, tradier_client):
        """Test getting order status."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "order": {
                "id": 123456,
                "status": "filled",
                "avg_fill_price": 450.25
            }
        }
        mock_request.return_value = mock_response

        order = tradier_client.get_order(order_id=123456)

        assert order["order"]["status"] == "filled"
        assert order["order"]["avg_fill_price"] == 450.25


# ==============================================================================
# MARKET DATA TESTS
# ==============================================================================

class TestMarketData:
    """Test market data endpoints."""

    @patch('requests.Session.request')
    def test_get_quotes_single_symbol(self, mock_request, tradier_client):
        """Test getting quote for single symbol."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "quotes": {
                "quote": {
                    "symbol": "SPY",
                    "last": 450.25,
                    "bid": 450.20,
                    "ask": 450.30
                }
            }
        }
        mock_request.return_value = mock_response

        quotes = tradier_client.get_quotes(["SPY"])

        assert quotes["quotes"]["quote"]["symbol"] == "SPY"
        assert quotes["quotes"]["quote"]["last"] == 450.25

    @patch('requests.Session.request')
    def test_get_quotes_multiple_symbols(self, mock_request, tradier_client):
        """Test getting quotes for multiple symbols."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"quotes": {"quote": []}}
        mock_request.return_value = mock_response

        tradier_client.get_quotes(["SPY", "QQQ", "IWM"])

        # Verify symbols are joined with comma
        call_params = mock_request.call_args.kwargs["params"]
        assert "SPY,QQQ,IWM" in call_params["symbols"]


# ==============================================================================
# ERROR HANDLING TESTS
# ==============================================================================

class TestErrorHandling:
    """Test error handling for various API errors."""

    @patch('requests.Session.request')
    def test_authentication_error_401(self, mock_request, tradier_client):
        """Test handling of 401 authentication error."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_request.return_value = mock_response

        with pytest.raises(TradierAuthenticationError):
            tradier_client.get_user_profile()

    @patch('requests.Session.request')
    def test_validation_error_400(self, mock_request, tradier_client):
        """Test handling of 400 validation error."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Invalid request"
        mock_request.return_value = mock_response

        with pytest.raises(TradierValidationError):
            tradier_client.place_order(
                symbol="INVALID",
                side=OrderSide.BUY,
                quantity=-10  # Invalid quantity
            )

    @patch('requests.Session.request')
    def test_rate_limit_error_429(self, mock_request, tradier_client):
        """Test handling of 429 rate limit error."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_request.return_value = mock_response

        with pytest.raises(TradierRateLimitError):
            tradier_client.get_user_profile()

    @patch('requests.Session.request')
    def test_server_error_500(self, mock_request, tradier_client):
        """Test handling of 500 server error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_request.return_value = mock_response

        with pytest.raises(TradierServerError):
            tradier_client.get_user_profile()

    @patch('requests.Session.request')
    def test_connection_timeout(self, mock_request, tradier_client):
        """Test handling of connection timeout."""
        mock_request.side_effect = requests.exceptions.Timeout()

        with pytest.raises(TradierAPIError, match="timeout"):
            tradier_client.get_user_profile()

    @patch('requests.Session.request')
    def test_connection_error(self, mock_request, tradier_client):
        """Test handling of connection error."""
        mock_request.side_effect = requests.exceptions.ConnectionError()

        with pytest.raises(TradierAPIError, match="Connection error"):
            tradier_client.get_user_profile()


# ==============================================================================
# CONNECTION TEST
# ==============================================================================

class TestConnection:
    """Test connection testing functionality."""

    @patch('requests.Session.request')
    def test_connection_success(self, mock_request, tradier_client):
        """Test successful connection test."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"profile": {"name": "Test"}}
        mock_request.return_value = mock_response

        assert tradier_client.test_connection() is True

    @patch('requests.Session.request')
    def test_connection_failure(self, mock_request, tradier_client):
        """Test failed connection test."""
        mock_request.side_effect = requests.exceptions.ConnectionError()

        assert tradier_client.test_connection() is False


# ==============================================================================
# RUN TESTS
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
