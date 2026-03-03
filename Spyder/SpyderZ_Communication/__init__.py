import logging
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Package: SpyderZ_Communication
Purpose: Communication infrastructure and message handling
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-29

Package Description:
    The SpyderZ_Communication package provides comprehensive communication
    infrastructure including ZeroMQ integration, message protocols, trading
    coordination, order routing, and multi-process management.

Modules Overview:
    • SpyderZ01_ZeroMQIntegration: ZeroMQ messaging infrastructure
    • SpyderZ02_MessageProtocol: Standardized message formats
    • SpyderZ03_TradingCoordinator: Trading operation coordination
    • SpyderZ04_VolatilityEngine: Volatility calculation
    • SpyderZ05_OrderRouter: Intelligent order routing
    • SpyderZ06_AutoHedger: Automated hedging mechanisms
    • SpyderZ07_MultiProcessManager: Multi-process coordination
"""

# Version information
__version__ = "1.0.0"
__author__ = "Mohamed Talib"
__email__ = "mtalib@spyder-trading.com"

# Module imports
try:
    from . import SpyderZ01_ZeroMQIntegration
    from . import SpyderZ02_MessageProtocol
    from . import SpyderZ03_TradingCoordinator
    from . import SpyderZ04_VolatilityEngine
    from . import SpyderZ05_OrderRouter
    from . import SpyderZ06_AutoHedger
    from . import SpyderZ07_MultiProcessManager
except ImportError as e:
    logging.info(f"Warning: Could not import communication modules: {e}")

# Package exports
__all__ = [
    "SpyderZ01_ZeroMQIntegration",
    "SpyderZ02_MessageProtocol",
    "SpyderZ03_TradingCoordinator",
    "SpyderZ04_VolatilityEngine",
    "SpyderZ05_OrderRouter",
    "SpyderZ06_AutoHedger",
    "SpyderZ07_MultiProcessManager",
]
