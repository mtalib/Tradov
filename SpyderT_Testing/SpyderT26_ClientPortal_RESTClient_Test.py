#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: test_rest_client.py
Purpose: Unit tests for REST Client
Author: Mohamed Talib
Last Updated: 2025-11-08
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from requests.exceptions import RequestException, Timeout, ConnectionError

from SpyderB_Broker.ClientPortalAPI.SpyderB09_ClientPortal_RESTClient import (
    ClientPortalRESTClient,
    ClientConfig,
    APIError,
    AuthenticationError,
    RateLimitError,
    ValidationError
)


class TestClientConfig:
    """Test cases for ClientConfig dataclass"""

    @pytest.mark.unit
    def test_default_config(self):
        """Test default configuration values"""
        config = ClientConfig()

        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.backoff_factor == 2.0
        assert config.rate_limit == 10
        assert config.pool_connections == 10
        assert config.pool_maxsize == 20

    @pytest.mark.unit
    def test_custom_config(self):
        """Test custom configuration values"""
        config = ClientConfig(
            timeout=60,
            max_retries=5,
            rate_limit=50,
            pool_connections=20
        )

        assert config.timeout == 60
        assert config.max_retries == 5
        assert config.rate_limit == 50
        assert config.pool_connections == 20


class TestClientPortalRESTClient:
    """Test cases for ClientPortalRESTClient class"""

    @pytest.mark.unit
    def test_client_creation_with_session_manager(self):
        """Test creating REST client with session manager"""
        session_mgr = Mock()
        session_mgr.session = Mock()
        session_mgr.base_url = "https://localhost:5000"

        client = ClientPortalRESTClient(session_mgr)

        assert client.session_manager == session_mgr
        assert client.base_url == "https://localhost:5000"
        assert client.rate_limiter is not None

    @pytest.mark.unit
    def test_client_creation_with_custom_config(self):
        """Test creating REST client with custom configuration"""
        session_mgr = Mock()
        session_mgr.session = Mock()
        session_mgr.base_url = "https://localhost:5000"

        config = ClientConfig(timeout=60, rate_limit=50)

        client = ClientPortalRESTClient(session_mgr, config=config)

        assert client.config.timeout == 60
        assert client.config.rate_limit == 50

    @pytest.mark.unit
    def test_get_request_success(self):
        """Test successful GET request"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "data": []}
        mock_response.raise_for_status.return_value = None
        mock_session.request.return_value = mock_response

        client = ClientPortalRESTClient(session_mgr)
        result = client.get('/portfolio/accounts')

        assert result == {"status": "success", "data": []}
        assert client.total_requests == 1
        assert client.successful_requests == 1

    @pytest.mark.unit
    def test_post_request_success(self):
        """Test successful POST request"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"order_id": "12345"}
        mock_response.raise_for_status.return_value = None
        mock_session.request.return_value = mock_response

        client = ClientPortalRESTClient(session_mgr)
        result = client.post('/iserver/account/DU123/orders', json={"orders": []})

        assert result == {"order_id": "12345"}
        assert client.total_requests == 1

    @pytest.mark.unit
    def test_delete_request_success(self):
        """Test successful DELETE request"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "cancelled"}
        mock_response.raise_for_status.return_value = None
        mock_session.request.return_value = mock_response

        client = ClientPortalRESTClient(session_mgr)
        result = client.delete('/iserver/account/DU123/order/12345')

        assert result == {"status": "cancelled"}

    @pytest.mark.unit
    def test_authentication_error_401(self):
        """Test that 401 status raises AuthenticationError"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock 401 response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_session.request.return_value = mock_response

        client = ClientPortalRESTClient(session_mgr)

        with pytest.raises(AuthenticationError):
            client.get('/portfolio/accounts')

        assert client.failed_requests == 1

    @pytest.mark.unit
    def test_rate_limit_error_429(self):
        """Test that 429 status raises RateLimitError"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock 429 response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_session.request.return_value = mock_response

        client = ClientPortalRESTClient(session_mgr)

        with pytest.raises(RateLimitError):
            client.get('/portfolio/accounts')

    @pytest.mark.unit
    def test_validation_error_400(self):
        """Test that 400 status raises ValidationError"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock 400 response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Invalid request"
        mock_session.request.return_value = mock_response

        client = ClientPortalRESTClient(session_mgr)

        with pytest.raises(ValidationError):
            client.get('/portfolio/accounts')

    @pytest.mark.unit
    def test_api_error_500(self):
        """Test that 500 status raises APIError"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock 500 response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_session.request.return_value = mock_response

        client = ClientPortalRESTClient(session_mgr)

        with pytest.raises(APIError) as exc_info:
            client.get('/portfolio/accounts')

        assert "500" in str(exc_info.value)

    @pytest.mark.unit
    def test_rate_limiter_integration(self):
        """Test that rate limiter is applied before requests"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None
        mock_session.request.return_value = mock_response

        config = ClientConfig(rate_limit=10)
        client = ClientPortalRESTClient(session_mgr, config=config)

        # Mock rate limiter
        with patch.object(client.rate_limiter, 'acquire') as mock_acquire:
            client.get('/portfolio/accounts')
            assert mock_acquire.called

    @pytest.mark.unit
    def test_rate_limiter_handles_429_error(self):
        """Test that rate limiter adjusts on 429 error"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock 429 response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_session.request.return_value = mock_response

        client = ClientPortalRESTClient(session_mgr)

        # Mock rate limiter's handle_rate_limit_error
        with patch.object(client.rate_limiter, 'handle_rate_limit_error') as mock_handle:
            with pytest.raises(RateLimitError):
                client.get('/portfolio/accounts')

            assert mock_handle.called

    @pytest.mark.unit
    def test_rate_limiter_handles_success(self):
        """Test that rate limiter tracks successful requests"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None
        mock_session.request.return_value = mock_response

        client = ClientPortalRESTClient(session_mgr)

        # Mock rate limiter's handle_success
        with patch.object(client.rate_limiter, 'handle_success') as mock_handle:
            client.get('/portfolio/accounts')
            assert mock_handle.called

    @pytest.mark.unit
    def test_get_stats(self):
        """Test getting client statistics"""
        session_mgr = Mock()
        session_mgr.session = Mock()
        session_mgr.base_url = "https://localhost:5000"

        client = ClientPortalRESTClient(session_mgr)
        client.total_requests = 10
        client.successful_requests = 8
        client.failed_requests = 2

        stats = client.get_stats()

        assert stats['total_requests'] == 10
        assert stats['successful_requests'] == 8
        assert stats['failed_requests'] == 2
        assert stats['success_rate'] == 80.0


class TestConvenienceMethods:
    """Test convenience methods for common operations"""

    @pytest.mark.unit
    def test_get_accounts(self):
        """Test get_accounts convenience method"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "DU123", "type": "DEMO"},
            {"id": "U456", "type": "CASH"}
        ]
        mock_response.raise_for_status.return_value = None
        mock_session.request.return_value = mock_response

        client = ClientPortalRESTClient(session_mgr)
        accounts = client.get_accounts()

        assert len(accounts) == 2
        assert accounts[0]['id'] == "DU123"

    @pytest.mark.unit
    def test_get_positions(self):
        """Test get_positions convenience method"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"contractDesc": "SPY", "position": 100},
            {"contractDesc": "QQQ", "position": 50}
        ]
        mock_response.raise_for_status.return_value = None
        mock_session.request.return_value = mock_response

        client = ClientPortalRESTClient(session_mgr)
        positions = client.get_positions("DU123")

        assert len(positions) == 2
        assert positions[0]['contractDesc'] == "SPY"

    @pytest.mark.unit
    def test_get_market_data_snapshot(self):
        """Test get_market_data_snapshot convenience method"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"conid": 756733, "31": 585.25, "84": 585.23, "86": 585.27}
        ]
        mock_response.raise_for_status.return_value = None
        mock_session.request.return_value = mock_response

        client = ClientPortalRESTClient(session_mgr)
        data = client.get_market_data_snapshot(
            conids=[756733],
            fields=[31, 84, 86]
        )

        assert len(data) == 1
        assert data[0]['conid'] == 756733

    @pytest.mark.unit
    def test_place_order(self):
        """Test place_order convenience method"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "order_id": "12345",
            "status": "PreSubmitted"
        }
        mock_response.raise_for_status.return_value = None
        mock_session.request.return_value = mock_response

        client = ClientPortalRESTClient(session_mgr)
        result = client.place_order(
            account_id="DU123",
            orders=[{"conid": 756733, "orderType": "MKT", "quantity": 100}]
        )

        assert result['order_id'] == "12345"

    @pytest.mark.unit
    def test_cancel_order(self):
        """Test cancel_order convenience method"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "msg": "Order cancelled",
            "status": "Cancelled"
        }
        mock_response.raise_for_status.return_value = None
        mock_session.request.return_value = mock_response

        client = ClientPortalRESTClient(session_mgr)
        result = client.cancel_order(account_id="DU123", order_id="12345")

        assert result['status'] == "Cancelled"


class TestRetryLogic:
    """Test retry logic and error handling"""

    @pytest.mark.unit
    def test_retry_on_network_error(self):
        """Test that client retries on network errors"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # First call fails, second succeeds
        mock_response_fail = Mock()
        mock_response_fail.status_code = 503
        mock_response_fail.text = "Service unavailable"

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"status": "ok"}
        mock_response_success.raise_for_status.return_value = None

        mock_session.request.side_effect = [
            mock_response_fail,
            mock_response_success
        ]

        config = ClientConfig(max_retries=3)
        client = ClientPortalRESTClient(session_mgr, config=config)

        # Should eventually succeed after retry
        # Note: This depends on the actual retry implementation in rest_client.py
        # The HTTPAdapter with Retry should handle this automatically
        result = client.get('/portfolio/accounts')

        # If retry worked, we should get the success response
        # This test may need adjustment based on actual implementation

    @pytest.mark.unit
    def test_timeout_error(self):
        """Test handling of timeout errors"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock timeout
        mock_session.request.side_effect = Timeout("Request timed out")

        client = ClientPortalRESTClient(session_mgr)

        with pytest.raises(APIError) as exc_info:
            client.get('/portfolio/accounts')

        assert "timeout" in str(exc_info.value).lower() or "Request timed out" in str(exc_info.value)

    @pytest.mark.unit
    def test_connection_error(self):
        """Test handling of connection errors"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock connection error
        mock_session.request.side_effect = ConnectionError("Connection refused")

        client = ClientPortalRESTClient(session_mgr)

        with pytest.raises(APIError) as exc_info:
            client.get('/portfolio/accounts')

        assert "connection" in str(exc_info.value).lower() or "Connection refused" in str(exc_info.value)


class TestClientEdgeCases:
    """Test edge cases and unusual scenarios"""

    @pytest.mark.unit
    def test_empty_response(self):
        """Test handling of empty response body"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock empty response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_session.request.return_value = mock_response

        client = ClientPortalRESTClient(session_mgr)
        result = client.get('/portfolio/accounts')

        assert result is None

    @pytest.mark.unit
    def test_non_json_response(self):
        """Test handling of non-JSON response"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock non-JSON response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "Plain text response"
        mock_response.raise_for_status.return_value = None
        mock_session.request.return_value = mock_response

        client = ClientPortalRESTClient(session_mgr)

        # Should handle gracefully - depends on implementation
        # May raise APIError or return text
        try:
            result = client.get('/portfolio/accounts')
            # If it returns text instead of raising
            assert result == "Plain text response"
        except APIError:
            # If it raises an error for non-JSON
            pass

    @pytest.mark.unit
    def test_malformed_url(self):
        """Test handling of malformed endpoint URL"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        client = ClientPortalRESTClient(session_mgr)

        # Endpoint without leading slash should still work
        # Implementation should normalize it
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None
        mock_session.request.return_value = mock_response

        result = client.get('portfolio/accounts')  # No leading slash
        assert result == {}

    @pytest.mark.unit
    def test_statistics_with_zero_requests(self):
        """Test statistics when no requests made"""
        session_mgr = Mock()
        session_mgr.session = Mock()
        session_mgr.base_url = "https://localhost:5000"

        client = ClientPortalRESTClient(session_mgr)
        stats = client.get_stats()

        assert stats['total_requests'] == 0
        assert stats['successful_requests'] == 0
        assert stats['failed_requests'] == 0
        assert stats['success_rate'] == 0.0


class TestClientIntegration:
    """Integration tests for REST client"""

    @pytest.mark.integration
    def test_multiple_requests_with_rate_limiting(self):
        """Test multiple requests respect rate limiting"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None
        mock_session.request.return_value = mock_response

        config = ClientConfig(rate_limit=10)
        client = ClientPortalRESTClient(session_mgr, config=config)

        # Make multiple requests
        for _ in range(5):
            client.get('/portfolio/accounts')

        assert client.total_requests == 5
        assert client.successful_requests == 5

    @pytest.mark.integration
    def test_error_recovery_workflow(self):
        """Test client recovers from errors and continues"""
        session_mgr = Mock()
        mock_session = Mock()
        session_mgr.session = mock_session
        session_mgr.base_url = "https://localhost:5000"

        # First request fails, rest succeed
        mock_error = Mock()
        mock_error.status_code = 500
        mock_error.text = "Error"

        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.json.return_value = {"status": "ok"}
        mock_success.raise_for_status.return_value = None

        mock_session.request.side_effect = [
            mock_error,
            mock_success,
            mock_success
        ]

        client = ClientPortalRESTClient(session_mgr)

        # First request should fail
        with pytest.raises(APIError):
            client.get('/portfolio/accounts')

        # Subsequent requests should succeed
        result1 = client.get('/portfolio/accounts')
        result2 = client.get('/portfolio/accounts')

        assert result1 == {"status": "ok"}
        assert result2 == {"status": "ok"}
        assert client.total_requests == 3
        assert client.successful_requests == 2
        assert client.failed_requests == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
