#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: conftest.py
Purpose: Shared pytest fixtures and configuration
Author: Mohamed Talib
Last Updated: 2025-11-08

Module Description:
    Pytest configuration and shared fixtures for all tests.
    Fixtures defined here are available to all test files.
"""

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta
import tempfile
import json

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


# ==============================================================================
# PYTEST CONFIGURATION HOOKS
# ==============================================================================

def pytest_configure(config):
    """Configure pytest before test collection"""
    # Create logs directory if it doesn't exist
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Set environment variables for testing
    os.environ['SPYDER_TEST_MODE'] = 'true'
    os.environ['SPYDER_ENV'] = 'test'


def pytest_collection_modifyitems(config, items):
    """Modify test items after collection"""
    # Auto-mark tests based on their location/name
    for item in items:
        # Mark integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Mark slow tests (can be skipped with -m "not slow")
        if "slow" in item.nodeid.lower():
            item.add_marker(pytest.mark.slow)

        # Mark tests requiring network
        if any(keyword in item.nodeid.lower() for keyword in ['api', 'network', 'http', 'websocket']):
            item.add_marker(pytest.mark.network)


# ==============================================================================
# SESSION-SCOPED FIXTURES (Run once per test session)
# ==============================================================================

@pytest.fixture(scope="session")
def test_data_dir():
    """Temporary directory for test data (session scope)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="session")
def project_root_path():
    """Project root directory path"""
    return project_root


# ==============================================================================
# FUNCTION-SCOPED FIXTURES (Run for each test)
# ==============================================================================

@pytest.fixture
def temp_dir():
    """Temporary directory for a single test"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_env_file(temp_dir):
    """Create a sample .env file for testing"""
    env_file = temp_dir / ".env"
    env_content = """
# Test Environment Configuration
IBKR_CONSUMER_KEY=test_consumer_key
IBKR_PRIVATE_KEY_PATH=/test/path/to/key.pem
IBKR_ACCOUNT_ID=DU123456

CP_GATEWAY_HOST=localhost
CP_GATEWAY_PORT=5000
CP_GATEWAY_SSL=true

IBKR_RATE_LIMIT=10
IBKR_TICKLE_INTERVAL=240
"""
    env_file.write_text(env_content.strip())
    yield env_file


@pytest.fixture
def mock_logger():
    """Mock SpyderLogger for testing"""
    logger = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.debug = Mock()
    logger.critical = Mock()
    return logger


@pytest.fixture
def mock_error_handler():
    """Mock SpyderErrorHandler for testing"""
    handler = Mock()
    handler.log_error = Mock()
    handler.handle_exception = Mock()
    return handler


# ==============================================================================
# CLIENT PORTAL API FIXTURES
# ==============================================================================

@pytest.fixture
def mock_oauth_config():
    """Mock OAuth configuration"""
    return {
        'consumer_key': 'test_consumer_key_12345',
        'private_key_path': '/test/path/to/private_key.pem',
        'token_url': 'https://api.ibkr.com/v1/oauth2/token'
    }


@pytest.fixture
def mock_gateway_config():
    """Mock CP Gateway configuration"""
    return {
        'host': 'localhost',
        'port': 5000,
        'ssl': True,
        'cacert': '/test/path/to/cacert.pem'
    }


@pytest.fixture
def mock_ib_client():
    """Mock IB client for testing"""
    client = MagicMock()
    client.is_connected = Mock(return_value=True)
    client.reqMarketData = Mock()
    client.placeOrder = Mock()
    client.reqPositions = Mock()
    client.reqAccountSummary = Mock()
    return client


@pytest.fixture
def mock_http_session():
    """Mock requests.Session for testing"""
    session = MagicMock()
    session.get = Mock()
    session.post = Mock()
    session.delete = Mock()
    session.headers = {}
    return session


@pytest.fixture
def mock_http_response():
    """Mock HTTP response"""
    response = Mock()
    response.status_code = 200
    response.json = Mock(return_value={'status': 'success'})
    response.text = '{"status": "success"}'
    response.headers = {'Content-Type': 'application/json'}
    response.raise_for_status = Mock()
    return response


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection"""
    ws = MagicMock()
    ws.send = Mock()
    ws.recv = Mock(return_value='{"type": "ping"}')
    ws.close = Mock()
    ws.connected = True
    return ws


# ==============================================================================
# MARKET DATA FIXTURES
# ==============================================================================

@pytest.fixture
def sample_market_data():
    """Sample market data for testing"""
    return {
        'SPY': {
            'symbol': 'SPY',
            'last': 585.25,
            'bid': 585.23,
            'ask': 585.27,
            'volume': 45000000,
            'change': 2.35,
            'change_pct': 0.40,
            'timestamp': datetime.now().isoformat()
        },
        'QQQ': {
            'symbol': 'QQQ',
            'last': 485.92,
            'bid': 485.90,
            'ask': 485.94,
            'volume': 32000000,
            'change': -1.23,
            'change_pct': -0.25,
            'timestamp': datetime.now().isoformat()
        }
    }


@pytest.fixture
def sample_position():
    """Sample position for testing"""
    return {
        'symbol': 'SPY',
        'quantity': 100,
        'avg_cost': 580.00,
        'current_price': 585.25,
        'unrealized_pnl': 525.00,
        'realized_pnl': 0.00,
        'position_type': 'STOCK'
    }


@pytest.fixture
def sample_order():
    """Sample order for testing"""
    return {
        'order_id': 'TEST12345',
        'symbol': 'SPY',
        'action': 'BUY',
        'order_type': 'LIMIT',
        'quantity': 100,
        'limit_price': 585.00,
        'status': 'SUBMITTED',
        'filled_quantity': 0,
        'timestamp': datetime.now().isoformat()
    }


@pytest.fixture
def sample_greeks():
    """Sample options Greeks for testing"""
    return {
        'delta': 45.5,
        'gamma': -2.3,
        'theta': -156.8,
        'vega': -245.2,
        'rho': 12.5
    }


# ==============================================================================
# RATE LIMITER FIXTURES
# ==============================================================================

@pytest.fixture
def rate_limiter_config():
    """Configuration for rate limiter"""
    return {
        'rate_limit': 10,
        'per_seconds': 1,
        'backoff_factor': 0.8,
        'recovery_factor': 1.05,
        'min_rate': 1,
        'recovery_threshold': 50
    }


# ==============================================================================
# JWT/OAUTH FIXTURES
# ==============================================================================

@pytest.fixture
def sample_jwt_payload():
    """Sample JWT payload for testing"""
    now = datetime.now()
    return {
        'iss': 'test_consumer_key',
        'sub': 'test_consumer_key',
        'aud': 'https://api.ibkr.com/v1/oauth2/token',
        'exp': int((now + timedelta(minutes=5)).timestamp()),
        'iat': int(now.timestamp()),
        'jti': f'test_jti_{now.timestamp()}'
    }


@pytest.fixture
def sample_oauth_token_response():
    """Sample OAuth token response"""
    return {
        'access_token': 'test_access_token_abcdef123456',
        'token_type': 'Bearer',
        'expires_in': 3600,
        'scope': 'read write'
    }


@pytest.fixture
def mock_private_key():
    """Mock RSA private key for testing"""
    # Note: This is a placeholder. In real tests, we'd use a test key
    return b"""-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3VS6JqPi6S...
-----END RSA PRIVATE KEY-----"""


# ==============================================================================
# FILE SYSTEM FIXTURES
# ==============================================================================

@pytest.fixture
def mock_config_file(temp_dir):
    """Create a mock configuration file"""
    config_file = temp_dir / "config.json"
    config = {
        'api_mode': 'oauth',
        'rate_limit': 50,
        'session_timeout': 360,
        'max_retries': 3
    }
    config_file.write_text(json.dumps(config, indent=2))
    yield config_file


# ==============================================================================
# PYTEST MARKERS DOCUMENTATION
# ==============================================================================

"""
Available pytest markers:

@pytest.mark.unit
    Unit tests - fast, no external dependencies

@pytest.mark.integration
    Integration tests - may require external services

@pytest.mark.slow
    Slow tests (> 1 second) - can be skipped with -m "not slow"

@pytest.mark.paper
    Requires paper trading account

@pytest.mark.live
    Requires live trading account (DANGEROUS - use with extreme caution)

@pytest.mark.ibkr
    Requires IBKR connection (Gateway or OAuth)

@pytest.mark.gui
    GUI tests - require display

@pytest.mark.network
    Requires network access

@pytest.mark.oauth
    Requires OAuth credentials

@pytest.mark.gateway
    Requires CP Gateway running

@pytest.mark.smoke
    Smoke tests - quick sanity checks

@pytest.mark.regression
    Regression tests

Example usage:

@pytest.mark.unit
def test_something_simple():
    assert True

@pytest.mark.integration
@pytest.mark.ibkr
def test_ib_connection():
    # Test that requires IB connection
    pass

@pytest.mark.slow
@pytest.mark.network
def test_api_endpoint():
    # Slow test that requires network
    pass
"""
