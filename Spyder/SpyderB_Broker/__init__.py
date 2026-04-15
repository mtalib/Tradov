#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v2.0

Series: SpyderB_Broker
Module: __init__.py
Purpose: Package initialization for Tradier broker integration
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-11-24

Module Description:
    Updated package initialization for SpyderB_Broker with Tradier API integration
    for order execution and Tradier/Massive market data.

    MIGRATION NOTES:
    - Removed all legacy broker dependencies
    - TradierClient is now the primary broker interface
    - Market data provided by Tradier by default, with Massive available as fallback
    - Simplified authentication (Bearer token vs OAuth 2.0)
"""
from __future__ import annotations

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__version__ = "5.0.0"
__author__ = "Mohamed Talib"
__description__ = "SPYDER Broker Package - Tradier API (OrderManager + Multileg + SSE)"

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
from typing import Any, Optional

# ==============================================================================
# PACKAGE INITIALIZATION LOGGING
# ==============================================================================
_logger = logging.getLogger(__name__)
_module_status = {}


def _log_import_status(module_name: str, success: bool, error: str = None):
    """Log import status for debugging and validation."""
    _module_status[module_name] = success
    if success:
        _logger.debug("[OK] %s imported successfully", module_name)
    else:
        _logger.warning("[FAIL] %s import failed: %s", module_name, error)


def get_module_status() -> dict[str, bool]:
    """Get status of all module imports for diagnostics."""
    return _module_status.copy()


def get_package_status() -> dict[str, Any]:
    """Get comprehensive package status for diagnostics."""
    return {
        "version": __version__,
        "modules_loaded": sum(_module_status.values()),
        "modules_total": len(_module_status),
        "success_rate": sum(_module_status.values()) / max(1, len(_module_status)),
        "module_details": _module_status.copy(),
        "broker": "Tradier",
        "data_provider": "Tradier / Massive",
    }


def print_package_status():
    """Print formatted package status."""
    status = get_package_status()
    logging.info("SpyderB_Broker Package Status (v%s):", status['version'])
    logging.info("  Broker: %s", status['broker'])
    logging.info("  Data Provider: %s", status['data_provider'])
    logging.info("  Modules loaded: %s/%s", status['modules_loaded'], status['modules_total'])
    logging.info(f"  Success rate: {status['success_rate']:.1%}")


# ==============================================================================
# CORE MODULE IMPORTS
# ==============================================================================

# Order Types (B00) - Generic order type definitions
try:
    from .SpyderB00_OrderTypes import (
        # Enums
        OrderAction, OrderStatus, TimeInForce, TriggerMethod,
        OCAType, SecType, OptionRight, OrderOrigin,
        # Core data structures
        ContractDetails, ComboLeg, OrderRequest,
        # Specialized orders
        BracketOrder, SpreadOrder,
        # Execution data
        Execution, Commission, Fill,
        # Factory functions
        create_market_order, create_limit_order, create_stop_order,
        create_stop_limit_order, create_spy_option_contract, create_iron_condor_spread,
        # Validation
        validate_order_request,
    )
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
        OrderClass,
        TradierAPIError,
        TradierAuthenticationError,
        TradierValidationError,
        TradierServerError,
        TradierRateLimitError,
        OptionLeg,
        GreekData,
        AccountEvent,
        TradierAccountStream,
        build_option_symbol,
        parse_option_symbol,
        create_tradier_client_from_env,
    )
    # Alias for backward compatibility
    TradierError = TradierAPIError
    _log_import_status("SpyderB40_TradierClient", True)
except ImportError as e:
    _log_import_status("SpyderB40_TradierClient", False, str(e))
    TradierClient = None
    TradingEnvironment = None
    OrderSide = None
    OrderType = None
    OrderDuration = None
    OrderClass = None
    TradierAPIError = None
    TradierError = None
    TradierAuthenticationError = None
    TradierValidationError = None
    TradierServerError = None
    TradierRateLimitError = None
    OptionLeg = None
    GreekData = None
    AccountEvent = None
    TradierAccountStream = None
    build_option_symbol = None
    parse_option_symbol = None
    create_tradier_client_from_env = None

# ==============================================================================
# SUPPORTING MODULES (TO BE REFACTORED FOR TRADIER)
# ==============================================================================

# Order Manager (B02) - Tradier-powered order orchestration
try:
    from .SpyderB02_OrderManager import (
        OrderManager,
        Order,
        OrderRequest,
        OrderResult,
        OrderState,
        OrderStatus,
        ExecutionReport,
        SecurityType,
        create_order_manager,
        get_order_manager,
    )
    _log_import_status("SpyderB02_OrderManager", True)
except ImportError as e:
    _log_import_status("SpyderB02_OrderManager", False, str(e))
    OrderManager = None
    Order = None
    OrderRequest = None
    OrderResult = None
    OrderState = None
    OrderStatus = None
    ExecutionReport = None
    SecurityType = None
    create_order_manager = None
    get_order_manager = None

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
    api_key: str | None = None,
    account_id: str | None = None,
    environment: str = "sandbox"
) -> TradierClient | None:
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
        _logger.error("Failed to create broker client: %s", e)
        return None


def diagnose_broker_package():
    """Run comprehensive broker package diagnostics."""
    logging.info("SpyderB_Broker Package Diagnostics")
    logging.info("=" * 50)

    status = get_package_status()
    logging.info("Package Version: %s", status['version'])
    logging.info("Broker: %s", status['broker'])
    logging.info("Data Provider: %s", status['data_provider'])
    logging.info("Modules Loaded: %s/%s", status['modules_loaded'], status['modules_total'])
    logging.info(f"Success Rate: {status['success_rate']:.1%}")
    logging.info()

    logging.info("Module Status:")
    for module, success in _module_status.items():
        status_icon = "[OK]" if success else "[FAIL]"
        logging.info("  %s %s", status_icon, module)

    logging.info()
    if TradierClient:
        logging.info("[OK] TradierClient available - ready for trading")
    else:
        logging.info("[FAIL] TradierClient not available - check installation")


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
        "OrderClass",
        "TradierAPIError",
        "TradierError",
        "TradierAuthenticationError",
        "TradierValidationError",
        "TradierServerError",
        "TradierRateLimitError",
        "OptionLeg",
        "GreekData",
        "AccountEvent",
        "TradierAccountStream",
        "build_option_symbol",
        "parse_option_symbol",
        "create_tradier_client_from_env",
    ])

# Add other available components
for component_name in [
    "OrderManager",
    "Order",
    "OrderRequest",
    "OrderResult",
    "OrderState",
    "OrderStatus",
    "ExecutionReport",
    "SecurityType",
    "create_order_manager",
    "get_order_manager",
    "PositionTracker",
    "AccountManager",
    "ContractBuilder",
    "MarketDataManager",
    "PrometheusMetrics",
    "SPYOptionsChainManager",
]:
    if globals().get(component_name) is not None:
        __all__.append(component_name)

# ==============================================================================
# PACKAGE INITIALIZATION COMPLETE
# ==============================================================================

_logger.info("SpyderB_Broker package initialized (v%s) - Tradier integration", __version__)
_logger.info("Loaded %s/%s modules", sum(_module_status.values()), len(_module_status))
