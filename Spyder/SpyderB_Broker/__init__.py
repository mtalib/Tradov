#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v2.0

Series: SpyderB_Broker
Module: __init__.py
Purpose: Package initialization for Tradier + Polygon broker integration
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-11-24

Module Description:
    Updated package initialization for SpyderB_Broker with Tradier API integration
    for order execution and Polygon.io for market data.

    MIGRATION NOTES:
    - Removed all IBKR/Interactive Brokers dependencies
    - TradierClient is now the primary broker interface
    - Market data provided by Polygon.io (see SpyderC_MarketData)
    - Simplified authentication (Bearer token vs OAuth 2.0)
"""

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__version__ = "3.0.0"
__author__ = "Mohamed Talib"
__description__ = "SPYDER Broker Package - Tradier API Integration"

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
from typing import Dict, Any, Optional

# ==============================================================================
# PACKAGE INITIALIZATION LOGGING
# ==============================================================================
_logger = logging.getLogger(__name__)
_module_status = {}


def _log_import_status(module_name: str, success: bool, error: str = None):
    """Log import status for debugging and validation."""
    _module_status[module_name] = success
    if success:
        _logger.debug(f"[OK] {module_name} imported successfully")
    else:
        _logger.warning(f"[FAIL] {module_name} import failed: {error}")


def get_module_status() -> Dict[str, bool]:
    """Get status of all module imports for diagnostics."""
    return _module_status.copy()


def get_package_status() -> Dict[str, Any]:
    """Get comprehensive package status for diagnostics."""
    return {
        "version": __version__,
        "modules_loaded": sum(_module_status.values()),
        "modules_total": len(_module_status),
        "success_rate": sum(_module_status.values()) / max(1, len(_module_status)),
        "module_details": _module_status.copy(),
        "broker": "Tradier",
        "data_provider": "Polygon.io",
    }


def print_package_status():
    """Print formatted package status."""
    status = get_package_status()
    print(f"SpyderB_Broker Package Status (v{status['version']}):")
    print(f"  Broker: {status['broker']}")
    print(f"  Data Provider: {status['data_provider']}")
    print(f"  Modules loaded: {status['modules_loaded']}/{status['modules_total']}")
    print(f"  Success rate: {status['success_rate']:.1%}")


# ==============================================================================
# CORE MODULE IMPORTS
# ==============================================================================

# Order Types (B00) - Generic order type definitions
try:
    from .SpyderB00_OrderTypes import *
    _log_import_status("SpyderB00_OrderTypes", True)
except ImportError as e:
    _log_import_status("SpyderB00_OrderTypes", False, str(e))

# ==============================================================================
# TRADIER CLIENT (B40) - PRIMARY BROKER INTERFACE
# ==============================================================================
try:
    from .SpyderB40_TradierClient import (
        TradierClient,
        TradingEnvironment,
        OrderSide,
        OrderType,
        OrderDuration,
        TradierError,
        TradierAuthenticationError,
        TradierValidationError,
        TradierServerError,
        TradierRateLimitError,
        create_tradier_client_from_env,
    )
    _log_import_status("SpyderB40_TradierClient", True)
except ImportError as e:
    _log_import_status("SpyderB40_TradierClient", False, str(e))
    TradierClient = None
    TradingEnvironment = None
    OrderSide = None
    OrderType = None
    OrderDuration = None
    TradierError = None
    TradierAuthenticationError = None
    TradierValidationError = None
    TradierServerError = None
    TradierRateLimitError = None
    create_tradier_client_from_env = None

# ==============================================================================
# SUPPORTING MODULES (TO BE REFACTORED FOR TRADIER)
# ==============================================================================

# Order Manager (B02) - Needs refactoring to use TradierClient
try:
    from .SpyderB02_OrderManager import OrderManager, OrderRequest
    _log_import_status("SpyderB02_OrderManager", True)
except ImportError as e:
    _log_import_status("SpyderB02_OrderManager", False, str(e))
    OrderManager = None
    OrderRequest = None

# Position Tracker (B03) - Needs refactoring to use Tradier positions
try:
    from .SpyderB03_PositionTracker import PositionTracker
    _log_import_status("SpyderB03_PositionTracker", True)
except ImportError as e:
    _log_import_status("SpyderB03_PositionTracker", False, str(e))
    PositionTracker = None

# Account Manager (B04) - Needs refactoring to use Tradier accounts
try:
    from .SpyderB04_AccountManager import AccountManager
    _log_import_status("SpyderB04_AccountManager", True)
except ImportError as e:
    _log_import_status("SpyderB04_AccountManager", False, str(e))
    AccountManager = None

# Contract Builder (B06) - Needs refactoring for Tradier symbol format
try:
    from .SpyderB06_ContractBuilder import ContractBuilder
    _log_import_status("SpyderB06_ContractBuilder", True)
except ImportError as e:
    _log_import_status("SpyderB06_ContractBuilder", False, str(e))
    ContractBuilder = None

# Market Data Manager (B07) - Needs refactoring to use Polygon
try:
    from .SpyderB07_MarketDataManager import MarketDataManager
    _log_import_status("SpyderB07_MarketDataManager", True)
except ImportError as e:
    _log_import_status("SpyderB07_MarketDataManager", False, str(e))
    MarketDataManager = None

# ==============================================================================
# UTILITY MODULES
# ==============================================================================

# Prometheus Metrics (B15) - Generic metrics collection
try:
    from .SpyderB15_PrometheusMetrics import PrometheusMetrics
    _log_import_status("SpyderB15_PrometheusMetrics", True)
except ImportError as e:
    _log_import_status("SpyderB15_PrometheusMetrics", False, str(e))
    PrometheusMetrics = None

# PySide Async Bridge (B26) - Qt/async integration
try:
    from .SpyderB26_PySideAsyncBridge import PySideAsyncBridge
    _log_import_status("SpyderB26_PySideAsyncBridge", True)
except ImportError as e:
    _log_import_status("SpyderB26_PySideAsyncBridge", False, str(e))
    PySideAsyncBridge = None

# SPY Options Chain Manager (B30) - Options chain utilities
try:
    from .SpyderB30_SPYOptionsChainManager import SPYOptionsChainManager
    _log_import_status("SpyderB30_SPYOptionsChainManager", True)
except ImportError as e:
    _log_import_status("SpyderB30_SPYOptionsChainManager", False, str(e))
    SPYOptionsChainManager = None


# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_broker_client(
    api_key: Optional[str] = None,
    account_id: Optional[str] = None,
    environment: str = "sandbox"
) -> Optional[TradierClient]:
    """
    Create a Tradier broker client.

    Args:
        api_key: Tradier API key (or load from env)
        account_id: Tradier account ID (or load from env)
        environment: 'live', 'sandbox', or 'paper'

    Returns:
        TradierClient instance or None if creation fails
    """
    try:
        if api_key and account_id:
            env = TradingEnvironment[environment.upper()]
            return TradierClient(
                api_key=api_key,
                account_id=account_id,
                environment=env
            )
        else:
            return create_tradier_client_from_env()
    except Exception as e:
        _logger.error(f"Failed to create broker client: {e}")
        return None


def diagnose_broker_package():
    """Run comprehensive broker package diagnostics."""
    print("SpyderB_Broker Package Diagnostics")
    print("=" * 50)

    status = get_package_status()
    print(f"Package Version: {status['version']}")
    print(f"Broker: {status['broker']}")
    print(f"Data Provider: {status['data_provider']}")
    print(f"Modules Loaded: {status['modules_loaded']}/{status['modules_total']}")
    print(f"Success Rate: {status['success_rate']:.1%}")
    print()

    print("Module Status:")
    for module, success in _module_status.items():
        status_icon = "[OK]" if success else "[FAIL]"
        print(f"  {status_icon} {module}")

    print()
    if TradierClient:
        print("[OK] TradierClient available - ready for trading")
    else:
        print("[FAIL] TradierClient not available - check installation")


# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    # Package management
    "get_package_status",
    "get_module_status",
    "print_package_status",
    "diagnose_broker_package",
    # Factory functions
    "create_broker_client",
]

# Add Tradier exports
if TradierClient:
    __all__.extend([
        "TradierClient",
        "TradingEnvironment",
        "OrderSide",
        "OrderType",
        "OrderDuration",
        "TradierError",
        "TradierAuthenticationError",
        "TradierValidationError",
        "TradierServerError",
        "TradierRateLimitError",
        "create_tradier_client_from_env",
    ])

# Add other available components
for component_name in [
    "OrderManager",
    "OrderRequest",
    "PositionTracker",
    "AccountManager",
    "ContractBuilder",
    "MarketDataManager",
    "PrometheusMetrics",
    "PySideAsyncBridge",
    "SPYOptionsChainManager",
]:
    if globals().get(component_name) is not None:
        __all__.append(component_name)

# ==============================================================================
# PACKAGE INITIALIZATION COMPLETE
# ==============================================================================

_logger.info(f"SpyderB_Broker package initialized (v{__version__}) - Tradier integration")
_logger.info(f"Loaded {sum(_module_status.values())}/{len(_module_status)} modules")
