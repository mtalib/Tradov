#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Package: SpyderZ_Communication
Purpose: Communication infrastructure and message handling
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-04-02

Package Description:
    The SpyderZ_Communication package provides comprehensive communication
    infrastructure including ZeroMQ integration, message protocols, trading
    coordination, order routing, and multi-process management.

Modules Overview:
    • SpyderZ00_BrokerProtocol: Typed Protocol contracts for B↔Z series boundary
    • SpyderZ01_ZeroMQIntegration: ZeroMQ messaging infrastructure
    • SpyderZ02_MessageProtocol: Standardized message formats
    • SpyderZ03_TradingCoordinator: Trading operation coordination
    • SpyderZ04_VolatilityEngine: ZMQ volatility engine subprocess worker
      (BSM/Greeks/surface computation delegated to SpyderV09_IVEngine)
    • SpyderZ05_OrderRouter: Intelligent order routing
    • SpyderZ06_AutoHedger: Automated hedging mechanisms
    • SpyderZ07_MultiProcessManager: Multi-process coordination
"""

import logging
from importlib import import_module

# Version information
__version__ = "1.0.1"
__author__ = "Mohamed Talib"
__email__ = "mtalib@spyder-trading.com"

_logger = logging.getLogger(__name__)

_LAZY_EXPORTS = {
    "NormalizedOrderRequest": ("SpyderZ00_BrokerProtocol", "NormalizedOrderRequest"),
    "NormalizedOrderResult": ("SpyderZ00_BrokerProtocol", "NormalizedOrderResult"),
    "BrokerClientProtocol": ("SpyderZ00_BrokerProtocol", "BrokerClientProtocol"),
    "OrderRouterProtocol": ("SpyderZ00_BrokerProtocol", "OrderRouterProtocol"),
    "SpyderZ01_ZeroMQIntegration": ("SpyderZ01_ZeroMQIntegration", None),
    "SpyderZ02_MessageProtocol": ("SpyderZ02_MessageProtocol", None),
    "SpyderZ03_TradingCoordinator": ("SpyderZ03_TradingCoordinator", None),
    "SpyderZ04_VolatilityEngine": ("SpyderZ04_VolatilityEngine", None),
    "SpyderZ05_OrderRouter": ("SpyderZ05_OrderRouter", None),
    "SpyderZ06_AutoHedger": ("SpyderZ06_AutoHedger", None),
    "SpyderZ07_MultiProcessManager": ("SpyderZ07_MultiProcessManager", None),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    module_attr = _LAZY_EXPORTS.get(name)
    if module_attr is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = module_attr
    try:
        module = import_module(f".{module_name}", __name__)
    except ImportError as exc:
        _logger.debug("Optional module %s not available for %s: %s", module_name, name, exc)
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    value = module if attr_name is None else getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS))
