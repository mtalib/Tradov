#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: test_auth.py
Purpose: Unit tests for Authentication module
Author: Mohamed Talib
Last Updated: 2025-11-08
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, MagicMock, patch, mock_open
from datetime import datetime, timedelta
from pathlib import Path

from SpyderB_Broker.ClientPortalAPI.auth import (
    OAuthClient,
    OAuthConfig,
    CPGatewayAuth,
    CPGatewayConfig,
    AuthenticationError,
    create_oauth_client_from_env,
    create_gateway_auth_from_env
)


class TestOAuthConfig:
    """Test cases for OAuthConfig dataclass"""

    @pytest.mark.unit
    def test_oauth_config_creation(self):
        """Test creating OAuth configuration"""
        config = OAuthConfig(
            consumer_key="test_key_12345",
            private_key_path="/path/to/key.pem"
        )

        assert config.consumer_key == "test_key_12345"
        assert config.private_key_path == "/path/to/key.pem"
        assert config.token_url == "https://api.ibkr.com/v1/oauth2/token"

    @pytest.mark.unit
    def test_oauth_config_custom_token_url(self):
        """Test OAuth config with custom token URL"""
        config = OAuthConfig(
            consumer_key="test_key",
            private_key_path="/path/to/key.pem",
            token_url="https://test.ibkr.com/token"
        )

        assert config.token_url == "https://test.ibkr.com/token"


class TestCPGatewayConfig:
    """Test cases for CPGatewayConfig dataclass"""

    @pytest.mark.unit
    def test_gateway_config_defaults(self):
        """Test default CP Gateway configuration"""
        config = CPGatewayConfig()

        assert config.host == "localhost"
        assert config.port == 5000
        assert config.ssl is True
        assert config.base_url == "https://localhost:5000"

    @pytest.mark.unit
    def test_gateway_config_custom(self):
        """Test custom CP Gateway configuration"""
        config = CPGatewayConfig(
            host="192.168.1.100",
            port=6000,
            ssl=False
        )

        assert config.host == "192.168.1.100"
        assert config.port == 6000
        assert config.ssl is False
        assert config.base_url == "http://192.168.1.100:6000"

    @pytest.mark.unit
    def test_gateway_config_with_cacert(self):
        """Test CP Gateway config with custom CA cert"""
        config = CPGatewayConfig(cacert="/path/to/cacert.pem")

        assert config.cacert == "/path/to/cacert.pem"


class TestOAuthClient:
    """Test cases for OAuthClient class"""

    @pytest.mark.unit
    def test_oauth_client_creation(self, mock_private_key, tmp_path):
        """Test creating OAuth client"""
        # Create temporary key file
        key_file = tmp_path / "test_key.pem"
        key_file.write_bytes(mock_private_key)

        config = OAuthConfig(
            consumer_key="test_key",
            private_key_path=str(key_file)
        )

        with patch('SpyderB_Broker.ClientPortalAPI.auth.serialization.load_pem_private_key') as mock_load:
            mock_load.return_value = Mock()
            client = OAuthClient(config)

            assert client.config == config
            assert client.access_token is None
            assert client.token_expiry is None

    @pytest.mark.unit
    def test_oauth_client_load_private_key(self, tmp_path):
        """Test loading RSA private key"""
        # Create a mock PEM key
        key_content = b"""-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3VS6JqPi6S1234567890...
-----END RSA PRIVATE KEY-----"""

        key_file = tmp_path / "test_key.pem"
        key_file.write_bytes(key_content)

        config = OAuthConfig(
            consumer_key="test_key",
            private_key_path=str(key_file)
        )

        with patch('SpyderB_Broker.ClientPortalAPI.auth.serialization.load_pem_private_key') as mock_load:
            mock_key = Mock()
            mock_load.return_value = mock_key

            client = OAuthClient(config)

            assert client.private_key == mock_key
            mock_load.assert_called_once()

    @pytest.mark.unit
    def test_oauth_client_missing_key_file(self):
        """Test OAuth client with missing private key file"""
        config = OAuthConfig(
            consumer_key="test_key",
            private_key_path="/nonexistent/key.pem"
        )

        with pytest.raises(FileNotFoundError):
            OAuthClient(config)

    @pytest.mark.unit
    @patch('SpyderB_Broker.ClientPortalAPI.auth.jwt.encode')
    def test_create_jwt_assertion(self, mock_jwt_encode, tmp_path):
        """Test creating JWT assertion"""
        # Setup
        key_content = b"fake_key_content"
        key_file = tmp_path / "test_key.pem"
        key_file.write_bytes(key_content)

        config = OAuthConfig(
            consumer_key="test_consumer_key",
            private_key_path=str(key_file)
        )

        mock_jwt_encode.return_value = "encoded.jwt.token"

        with patch('SpyderB_Broker.ClientPortalAPI.auth.serialization.load_pem_private_key') as mock_load:
            mock_key = Mock()
            mock_load.return_value = mock_key

            client = OAuthClient(config)
            jwt_assertion = client._create_jwt_assertion()

            assert jwt_assertion == "encoded.jwt.token"
            assert mock_jwt_encode.called

            # Verify JWT payload structure
            call_args = mock_jwt_encode.call_args
            payload = call_args[0][0]

            assert payload['iss'] == "test_consumer_key"
            assert payload['sub'] == "test_consumer_key"
            assert 'exp' in payload
            assert 'iat' in payload
            assert 'jti' in payload

    @pytest.mark.unit
    @patch('requests.post')
    def test_get_access_token_success(self, mock_post, tmp_path):
        """Test successful access token retrieval"""
        # Setup
        key_content = b"fake_key"
        key_file = tmp_path / "test_key.pem"
        key_file.write_bytes(key_content)

        config = OAuthConfig(
            consumer_key="test_key",
            private_key_path=str(key_file)
        )

        # Mock successful token response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'test_access_token_abc123',
            'token_type': 'Bearer',
            'expires_in': 3600
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with patch('SpyderB_Broker.ClientPortalAPI.auth.serialization.load_pem_private_key'):
            with patch.object(OAuthClient, '_create_jwt_assertion', return_value='fake.jwt.token'):
                client = OAuthClient(config)
                token = client.get_access_token()

                assert token == 'test_access_token_abc123'
                assert client.access_token == 'test_access_token_abc123'
                assert client.token_expiry is not None

    @pytest.mark.unit
    @patch('requests.post')
    def test_get_access_token_failure(self, mock_post, tmp_path):
        """Test failed access token retrieval"""
        # Setup
        key_content = b"fake_key"
        key_file = tmp_path / "test_key.pem"
        key_file.write_bytes(key_content)

        config = OAuthConfig(
            consumer_key="test_key",
            private_key_path=str(key_file)
        )

        # Mock failed token response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Invalid credentials"
        mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")
        mock_post.return_value = mock_response

        with patch('SpyderB_Broker.ClientPortalAPI.auth.serialization.load_pem_private_key'):
            with patch.object(OAuthClient, '_create_jwt_assertion', return_value='fake.jwt.token'):
                client = OAuthClient(config)

                with pytest.raises(AuthenticationError):
                    client.get_access_token()

    @pytest.mark.unit
    def test_is_token_valid_no_token(self, tmp_path):
        """Test token validity when no token exists"""
        key_file = tmp_path / "test_key.pem"
        key_file.write_bytes(b"fake_key")

        config = OAuthConfig(
            consumer_key="test_key",
            private_key_path=str(key_file)
        )

        with patch('SpyderB_Broker.ClientPortalAPI.auth.serialization.load_pem_private_key'):
            client = OAuthClient(config)

            assert client._is_token_valid() is False

    @pytest.mark.unit
    def test_is_token_valid_expired(self, tmp_path):
        """Test token validity when token is expired"""
        key_file = tmp_path / "test_key.pem"
        key_file.write_bytes(b"fake_key")

        config = OAuthConfig(
            consumer_key="test_key",
            private_key_path=str(key_file)
        )

        with patch('SpyderB_Broker.ClientPortalAPI.auth.serialization.load_pem_private_key'):
            client = OAuthClient(config)
            client.access_token = "expired_token"
            client.token_expiry = datetime.now() - timedelta(minutes=5)

            assert client._is_token_valid() is False

    @pytest.mark.unit
    def test_is_token_valid_near_expiry(self, tmp_path):
        """Test token validity near expiry (within buffer)"""
        key_file = tmp_path / "test_key.pem"
        key_file.write_bytes(b"fake_key")

        config = OAuthConfig(
            consumer_key="test_key",
            private_key_path=str(key_file)
        )

        with patch('SpyderB_Broker.ClientPortalAPI.auth.serialization.load_pem_private_key'):
            client = OAuthClient(config)
            client.access_token = "near_expiry_token"
            # Set expiry to 30 seconds from now (within 60-second buffer)
            client.token_expiry = datetime.now() + timedelta(seconds=30)

            assert client._is_token_valid() is False

    @pytest.mark.unit
    def test_is_token_valid_good(self, tmp_path):
        """Test token validity with valid token"""
        key_file = tmp_path / "test_key.pem"
        key_file.write_bytes(b"fake_key")

        config = OAuthConfig(
            consumer_key="test_key",
            private_key_path=str(key_file)
        )

        with patch('SpyderB_Broker.ClientPortalAPI.auth.serialization.load_pem_private_key'):
            client = OAuthClient(config)
            client.access_token = "valid_token"
            # Set expiry to 10 minutes from now (beyond 60-second buffer)
            client.token_expiry = datetime.now() + timedelta(minutes=10)

            assert client._is_token_valid() is True

    @pytest.mark.unit
    @patch('requests.post')
    def test_token_caching(self, mock_post, tmp_path):
        """Test that token is cached and not re-requested"""
        key_file = tmp_path / "test_key.pem"
        key_file.write_bytes(b"fake_key")

        config = OAuthConfig(
            consumer_key="test_key",
            private_key_path=str(key_file)
        )

        # Mock successful token response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'cached_token',
            'expires_in': 3600
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with patch('SpyderB_Broker.ClientPortalAPI.auth.serialization.load_pem_private_key'):
            with patch.object(OAuthClient, '_create_jwt_assertion', return_value='fake.jwt'):
                client = OAuthClient(config)

                # First call - should request token
                token1 = client.get_access_token()

                # Second call - should use cached token
                token2 = client.get_access_token()

                assert token1 == token2
                assert mock_post.call_count == 1  # Only called once


class TestCPGatewayAuth:
    """Test cases for CPGatewayAuth class"""

    @pytest.mark.unit
    def test_gateway_auth_creation(self):
        """Test creating CP Gateway auth client"""
        config = CPGatewayConfig(host="localhost", port=5000)

        auth = CPGatewayAuth(config)

        assert auth.config == config
        assert auth.base_url == "https://localhost:5000"

    @pytest.mark.unit
    @patch('requests.Session')
    def test_is_authenticated_success(self, mock_session_class):
        """Test checking authentication status when authenticated"""
        config = CPGatewayConfig()

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'authenticated': True,
            'competing': False,
            'connected': True
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        auth = CPGatayAuth(config)

        assert auth.is_authenticated() is True

    @pytest.mark.unit
    @patch('requests.Session')
    def test_is_authenticated_not_auth(self, mock_session_class):
        """Test checking authentication status when not authenticated"""
        config = CPGatewayConfig()

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'authenticated': False,
            'competing': False,
            'connected': False
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        auth = CPGatewayAuth(config)

        assert auth.is_authenticated() is False

    @pytest.mark.unit
    @patch('requests.Session')
    def test_is_authenticated_error(self, mock_session_class):
        """Test authentication check with network error"""
        config = CPGatewayConfig()

        mock_session = Mock()
        mock_session.get.side_effect = Exception("Connection refused")
        mock_session_class.return_value = mock_session

        auth = CPGatewayAuth(config)

        assert auth.is_authenticated() is False

    @pytest.mark.unit
    @patch('requests.Session')
    def test_reauthenticate(self, mock_session_class):
        """Test re-authentication process"""
        config = CPGatewayConfig()

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'ok'}
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        auth = CPGatewayAuth(config)
        result = auth.reauthenticate()

        assert result is True
        mock_session.post.assert_called_once()


class TestFactoryFunctions:
    """Test factory functions for creating auth clients"""

    @pytest.mark.unit
    @patch.dict(os.environ, {
        'IBKR_CONSUMER_KEY': 'env_consumer_key',
        'IBKR_PRIVATE_KEY_PATH': '/env/path/to/key.pem'
    })
    @patch('SpyderB_Broker.ClientPortalAPI.auth.OAuthClient')
    def test_create_oauth_client_from_env(self, mock_oauth_class):
        """Test creating OAuth client from environment variables"""
        mock_client = Mock()
        mock_oauth_class.return_value = mock_client

        client = create_oauth_client_from_env()

        assert client == mock_client
        # Verify OAuthClient was called with correct config
        call_args = mock_oauth_class.call_args[0][0]
        assert call_args.consumer_key == 'env_consumer_key'
        assert call_args.private_key_path == '/env/path/to/key.pem'

    @pytest.mark.unit
    @patch.dict(os.environ, {}, clear=True)
    def test_create_oauth_client_from_env_missing_key(self):
        """Test creating OAuth client with missing environment variables"""
        with pytest.raises(ValueError) as exc_info:
            create_oauth_client_from_env()

        assert "IBKR_CONSUMER_KEY" in str(exc_info.value)

    @pytest.mark.unit
    @patch.dict(os.environ, {
        'CP_GATEWAY_HOST': '192.168.1.100',
        'CP_GATEWAY_PORT': '6000',
        'CP_GATEWAY_SSL': 'false'
    })
    @patch('SpyderB_Broker.ClientPortalAPI.auth.CPGatewayAuth')
    def test_create_gateway_auth_from_env(self, mock_gateway_class):
        """Test creating CP Gateway auth from environment variables"""
        mock_auth = Mock()
        mock_gateway_class.return_value = mock_auth

        auth = create_gateway_auth_from_env()

        assert auth == mock_auth
        # Verify CPGatewayAuth was called with correct config
        call_args = mock_gateway_class.call_args[0][0]
        assert call_args.host == '192.168.1.100'
        assert call_args.port == 6000
        assert call_args.ssl is False

    @pytest.mark.unit
    @patch.dict(os.environ, {}, clear=True)
    @patch('SpyderB_Broker.ClientPortalAPI.auth.CPGatewayAuth')
    def test_create_gateway_auth_from_env_defaults(self, mock_gateway_class):
        """Test creating CP Gateway auth with default values"""
        mock_auth = Mock()
        mock_gateway_class.return_value = mock_auth

        auth = create_gateway_auth_from_env()

        # Should use defaults when env vars not set
        call_args = mock_gateway_class.call_args[0][0]
        assert call_args.host == 'localhost'
        assert call_args.port == 5000
        assert call_args.ssl is True


class TestAuthIntegration:
    """Integration tests for authentication"""

    @pytest.mark.integration
    @pytest.mark.network
    @patch('requests.post')
    def test_oauth_full_flow(self, mock_post, tmp_path):
        """Test complete OAuth authentication flow"""
        # Setup
        key_file = tmp_path / "test_key.pem"
        key_file.write_bytes(b"fake_rsa_key_content")

        config = OAuthConfig(
            consumer_key="integration_test_key",
            private_key_path=str(key_file)
        )

        # Mock token response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'integration_test_token',
            'token_type': 'Bearer',
            'expires_in': 3600
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with patch('SpyderB_Broker.ClientPortalAPI.auth.serialization.load_pem_private_key'):
            with patch.object(OAuthClient, '_create_jwt_assertion', return_value='test.jwt'):
                # Create client
                client = OAuthClient(config)

                # Get token
                token = client.get_access_token()

                # Verify token
                assert token == 'integration_test_token'
                assert client._is_token_valid() is True

                # Get token again (should use cache)
                token2 = client.get_access_token()
                assert token2 == token
                assert mock_post.call_count == 1  # Only one request


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
