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

# Version information
__version__ = "1.0.1"
__author__ = "Mohamed Talib"
__email__ = "mtalib@spyder-trading.com"

# Z00 — Protocol contracts (B↔Z boundary)
try:
    from .SpyderZ00_BrokerProtocol import (
        NormalizedOrderRequest,
        NormalizedOrderResult,
        BrokerClientProtocol,
        OrderRouterProtocol,
    )
    Z00_AVAILABLE = True
except ImportError as e:
    logging.info("Warning: Could not import SpyderZ00_BrokerProtocol: %s", e)
    Z00_AVAILABLE = False

# Module imports — ZMQ required; guard individually so partial availability is
# reported correctly and __all__ only advertises successfully imported submodules.
_Z_MODULES_AVAILABLE: list[str] = []

try:
    from . import SpyderZ01_ZeroMQIntegration
    _Z_MODULES_AVAILABLE.append("SpyderZ01_ZeroMQIntegration")
except ImportError as e:
    logging.info("Warning: SpyderZ01_ZeroMQIntegration not available: %s", e)

try:
    from . import SpyderZ02_MessageProtocol
    _Z_MODULES_AVAILABLE.append("SpyderZ02_MessageProtocol")
except ImportError as e:
    logging.info("Warning: SpyderZ02_MessageProtocol not available: %s", e)

try:
    from . import SpyderZ03_TradingCoordinator
    _Z_MODULES_AVAILABLE.append("SpyderZ03_TradingCoordinator")
except ImportError as e:
    logging.info("Warning: SpyderZ03_TradingCoordinator not available: %s", e)

try:
    from . import SpyderZ04_VolatilityEngine
    _Z_MODULES_AVAILABLE.append("SpyderZ04_VolatilityEngine")
except ImportError as e:
    logging.info("Warning: SpyderZ04_VolatilityEngine not available: %s", e)

try:
    from . import SpyderZ05_OrderRouter
    _Z_MODULES_AVAILABLE.append("SpyderZ05_OrderRouter")
except ImportError as e:
    logging.info("Warning: SpyderZ05_OrderRouter not available: %s", e)

try:
    from . import SpyderZ06_AutoHedger
    _Z_MODULES_AVAILABLE.append("SpyderZ06_AutoHedger")
except ImportError as e:
    logging.info("Warning: SpyderZ06_AutoHedger not available: %s", e)

try:
    from . import SpyderZ07_MultiProcessManager
    _Z_MODULES_AVAILABLE.append("SpyderZ07_MultiProcessManager")
except ImportError as e:
    logging.info("Warning: SpyderZ07_MultiProcessManager not available: %s", e)

# Package exports
__all__ = [
    # Z00 — Protocol contracts (always available)
    "NormalizedOrderRequest",
    "NormalizedOrderResult",
    "BrokerClientProtocol",
    "OrderRouterProtocol",
]

# Only advertise submodules that were successfully imported
__all__.extend(_Z_MODULES_AVAILABLE)
