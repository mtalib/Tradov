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
import importlib
from pathlib import Path
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta
import tempfile
import json

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def _is_workspace_module(module_obj) -> bool:
    """Return True when a module resolves to a file inside this workspace."""
    module_file = getattr(module_obj, "__file__", None)
    if not module_file:
        return False
    try:
        return os.path.abspath(module_file).startswith(str(project_root))
    except Exception:
        return False


def _cleanup_polluted_spyder_modules() -> None:
    """Remove in-memory stub modules that can poison later test collection."""
    watched_prefixes = (
        "SpyderU_Utilities",
        "Spyder.SpyderU_Utilities",
        "SpyderA_Core",
        "Spyder.SpyderA_Core",
        "SpyderG_GUI",
        "Spyder.SpyderG_GUI",
        "SpyderI_Integration",
        "Spyder.SpyderI_Integration",
    )

    for mod_name, mod_obj in list(sys.modules.items()):
        if not mod_name.startswith(watched_prefixes):
            continue
        if _is_workspace_module(mod_obj):
            continue
        sys.modules.pop(mod_name, None)


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

    # Prime canonical packages so test bootstraps don't replace them with stubs.
    for module_name in (
        "Spyder",
        "Spyder.SpyderU_Utilities",
        "Spyder.SpyderA_Core",
    ):
        try:
            importlib.import_module(module_name)
        except Exception:
            pass


def pytest_collectstart(collector):
    """Keep collection isolated by removing polluted module stubs between files."""
    _cleanup_polluted_spyder_modules()

    # Re-prime canonical utility modules commonly clobbered by test bootstraps.
    for module_name in (
        "Spyder",
        "Spyder.SpyderU_Utilities",
        "Spyder.SpyderU_Utilities.SpyderU01_Logger",
        "Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler",
        "Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils",
        "Spyder.SpyderA_Core",
        "Spyder.SpyderA_Core.SpyderA05_EventManager",
        "Spyder.SpyderG_GUI",
        "Spyder.SpyderG_GUI.SpyderG05_TradingDashboard",
        "Spyder.SpyderI_Integration",
        "Spyder.SpyderI_Integration.SpyderI06_AgentMessageBus",
    ):
        try:
            importlib.import_module(module_name)
        except Exception:
            pass


def pytest_runtest_setup(item):
    """Reset polluted module aliases before each test item runs."""
    pytest_collectstart(item)


def pytest_collection_modifyitems(config, items):
    """Modify test items after collection"""
    import re

    def _file_sort_key(item):
        """Sort SpyderT*.py files numerically so SpyderT93 < SpyderT100."""
        fname = os.path.basename(str(item.fspath))
        m = re.match(r'SpyderT(\d+)', fname)
        return int(m.group(1)) if m else 0

    # Sort items numerically by SpyderT number so SpyderT1xx always runs
    # after SpyderT09x, SpyderT08x, etc. (lexicographic order breaks this).
    items.sort(key=_file_sort_key)

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
TRADING_MODE=paper
RATE_LIMIT_REQUESTS_PER_SECOND=50
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
# HTTP & WEBSOCKET FIXTURES
# ==============================================================================


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
# FILE SYSTEM FIXTURES
# ==============================================================================

@pytest.fixture
def mock_config_file(temp_dir):
    """Create a mock configuration file"""
    config_file = temp_dir / "config.json"
    config = {
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

@pytest.mark.gui
    GUI tests - require display

@pytest.mark.network
    Requires network access

@pytest.mark.smoke
    Smoke tests - quick sanity checks

@pytest.mark.regression
    Regression tests

Example usage:

@pytest.mark.unit
def test_something_simple():
    assert True

@pytest.mark.integration
@pytest.mark.network
def test_api_connection():
    # Test that requires API connection
    pass

@pytest.mark.slow
@pytest.mark.network
def test_api_endpoint():
    # Slow test that requires network
    pass
"""
